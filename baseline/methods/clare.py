"""CLARE: frozen FFNs, expandable side branches, AE novelty and task-free routing.

PI0.5 port: adapters cover every action-expert FFN. Routing uses the pooled
action-token features of each sample, so all tokens of a chunk share an adapter.
"""
from contextlib import contextmanager

import torch
from torch import nn

from ..io import to_cpu, assert_finite_step


class Adapter(nn.Sequential):
    def __init__(self, width, bottleneck):
        super().__init__(nn.Linear(width, bottleneck), nn.ReLU(), nn.Linear(bottleneck, width))


class Autoencoder(nn.Module):
    def __init__(self, width, hidden, latent):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(width, hidden), nn.ReLU(), nn.Linear(hidden, latent),
                                 nn.ReLU(), nn.Linear(latent, hidden), nn.ReLU(), nn.Linear(hidden, width))

    def error(self, x):
        x = x.float()
        return (self.net(x) - x).square().mean(-1)


class ExpandableFFN(nn.Module):
    def __init__(self, base, width, cfg):
        super().__init__()
        self.base = base.requires_grad_(False)
        self.width, self.cfg = width, cfg
        self.adapters = nn.ModuleList()
        self.discriminators = nn.ModuleList()
        self.links, self.statistics = [], []
        self.forced = None
        self.capture = None

    def pooled(self, x):
        return x.float().reshape(x.shape[0], -1, self.width).mean(1)

    def forward(self, x, *args, **kwargs):
        pooled = self.pooled(x)
        if self.capture is not None:
            self.capture.append(pooled.detach())
        base = self.base(x, *args, **kwargs)
        if not self.adapters:
            return base
        if self.forced is not None:
            return base + self.adapters[self.forced](x.float()).to(base.dtype)
        with torch.no_grad():
            errors = torch.stack([ae.error(pooled) for ae in self.discriminators], -1)
            links = torch.tensor(self.links, device=x.device)
            routing = links[errors.argmin(-1)]
        residual = torch.zeros_like(base)
        for index, adapter in enumerate(self.adapters):
            selected = routing == index
            if selected.any():
                residual[selected] = adapter(x[selected].float()).to(base.dtype)
        return base + residual

    def add_stage(self, features, *, force_expand=False):
        device = next(self.base.parameters()).device
        expand = not self.adapters
        closest = None
        zscores = []
        if self.discriminators:
            with torch.no_grad():
                errors = [float(ae.error(features).mean()) for ae in self.discriminators]
            zscores = [(value - stats[0]) / max(stats[1], 1e-6)
                       for value, stats in zip(errors, self.statistics)]
            expand = all(z > self.cfg["expansion_threshold"] for z in zscores)
            closest = self.links[min(range(len(errors)), key=errors.__getitem__)]
        expand |= force_expand
        if expand:
            self.adapters.append(Adapter(self.width, self.cfg["bottleneck"]).to(device))
            closest = len(self.adapters) - 1
        self.discriminators.append(Autoencoder(self.width, self.cfg["ae_hidden"], self.cfg["ae_latent"]).to(device))
        self.links.append(closest)
        self.forced = closest
        for module in self.adapters:
            module.requires_grad_(False)
        for module in self.discriminators:
            module.requires_grad_(False)
        if expand:
            self.adapters[closest].requires_grad_(True)
        return {"expanded": expand, "linked_adapter": closest, "z_scores": zscores}


class Clare:
    def __init__(self, runtime, cfg):
        self.runtime, self.cfg = runtime, cfg
        self.layers = {}
        self.stages = []
        for index, layer in enumerate(runtime.model.paligemma_with_expert.gemma_expert.model.layers):
            base = layer.mlp
            width = base.up_proj.in_features
            wrapped = ExpandableFFN(base, width, cfg)
            layer.mlp = wrapped
            self.layers[str(index)] = wrapped
        if not self.layers:
            raise ValueError("no action-expert FFNs discovered")

    @torch.no_grad()
    def collect(self, forward, batches):
        for layer in self.layers.values():
            layer.capture = []
        try:
            for _ in range(batches):
                forward()
            return {key: torch.cat(layer.capture) for key, layer in self.layers.items()}
        finally:
            for layer in self.layers.values():
                layer.capture = None

    def train_stage(self, task_key, forward, *, steps, learning_rate, max_norm, report, training_cfg=None):
        if task_key in self.stages:
            raise ValueError("task already learned; resume from a different stage checkpoint")
        features = self.collect(forward, self.cfg["feature_batches"])
        plan = {key: layer.add_stage(features[key]) for key, layer in self.layers.items()}
        if not any(v["expanded"] for v in plan.values()):
            # CLARE's forced shallowest-layer fallback. Replace just the newly
            # added discriminator link; historical modules remain untouched.
            key = next(iter(self.layers))
            layer = self.layers[key]
            device = features[key].device
            layer.adapters.append(Adapter(layer.width, self.cfg["bottleneck"]).to(device))
            layer.links[-1] = layer.forced = len(layer.adapters) - 1
            plan[key].update(expanded=True, forced=True, linked_adapter=layer.forced)
        parameters = [p for layer in self.layers.values() for a in layer.adapters for p in a.parameters() if p.requires_grad]
        from ..optimization import policy_optimizer, accumulated_step
        if training_cfg:
            optimizer, scheduler = policy_optimizer(parameters, training_cfg)
        else:
            optimizer, scheduler = torch.optim.AdamW(parameters, lr=learning_rate, weight_decay=0.0), None
        for step in range(steps):
            metrics = accumulated_step(lambda: (forward(), {}), parameters, optimizer,
                                       training_cfg["gradient_accumulation_steps"] if training_cfg else 1, max_norm, scheduler)
            report({"phase": "adapter", "step": step + 1, **metrics})
        features = self.collect(forward, self.cfg["feature_batches"])
        for layer in self.layers.values():
            for adapter in layer.adapters:
                adapter.requires_grad_(False)
            layer.discriminators[-1].requires_grad_(True)
        parameters = [p for layer in self.layers.values() for p in layer.discriminators[-1].parameters()]
        optimizer = torch.optim.Adam(parameters, lr=self.cfg["discriminator_lr"])
        for step in range(self.cfg["discriminator_steps"]):
            def discriminator_forward():
                losses = []
                for key, layer in self.layers.items():
                    rows = features[key]
                    count = training_cfg["batch_size"] if training_cfg else min(32, len(rows))
                    indices = torch.randint(len(rows), (count,), device=rows.device)
                    losses.append(layer.discriminators[-1].error(rows[indices]).mean())
                return torch.stack(losses).mean(), {}
            metrics = accumulated_step(discriminator_forward, parameters, optimizer,
                                       training_cfg["gradient_accumulation_steps"] if training_cfg else 1, max_norm)
            report({"phase": "discriminator", "step": step + 1, **metrics})
        with torch.no_grad():
            for key, layer in self.layers.items():
                error = layer.discriminators[-1].error(features[key])
                layer.statistics.append([float(error.mean()), max(float(error.std(unbiased=False)), 1e-6)])
                layer.discriminators[-1].requires_grad_(False)
                layer.forced = None
        self.stages.append(task_key)
        return plan

    def state(self):
        return to_cpu({"stages": self.stages, "layers": {
            key: {"adapters": [a.state_dict() for a in layer.adapters],
                  "discriminators": [a.state_dict() for a in layer.discriminators],
                  "links": layer.links, "statistics": layer.statistics}
            for key, layer in self.layers.items()}})

    def restore(self, state):
        if set(state["layers"]) != set(self.layers):
            raise ValueError("CLARE layer topology differs from this PI0.5")
        self.stages = list(state["stages"])
        for key, values in state["layers"].items():
            layer = self.layers[key]
            device = next(layer.base.parameters()).device
            if len(values["discriminators"]) != len(self.stages) or len(values["statistics"]) != len(self.stages):
                raise ValueError("incomplete CLARE discriminator history")
            for weights in values["adapters"]:
                module = Adapter(layer.width, self.cfg["bottleneck"]).to(device)
                module.load_state_dict(weights, strict=True)
                layer.adapters.append(module.requires_grad_(False))
            for weights in values["discriminators"]:
                module = Autoencoder(layer.width, self.cfg["ae_hidden"], self.cfg["ae_latent"]).to(device)
                module.load_state_dict(weights, strict=True)
                layer.discriminators.append(module.requires_grad_(False))
            layer.links, layer.statistics = values["links"], values["statistics"]
            if len(layer.links) != len(self.stages) or any(i < 0 or i >= len(layer.adapters) for i in layer.links):
                raise ValueError("invalid CLARE routing links")
