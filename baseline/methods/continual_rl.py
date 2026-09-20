"""Sequential LoRA + on-policy GRPO, adapted to PI0.5's continuous flow.

Unlike token GRPO, each stochastic Euler transition has an explicit Gaussian
density. Ratios use the sum of log densities of the SAME recorded transition,
not a behavior-cloning loss or an invented deterministic-flow log probability.
The initial Gaussian is fixed and cancels; all 50x32 latent coordinates count.
"""
import math

import torch
from torch import nn

from ..io import to_cpu


class LoRALinear(nn.Module):
    def __init__(self, base, rank, alpha):
        super().__init__()
        self.base = base.requires_grad_(False)
        self.rank, self.scale = rank, alpha / rank
        self.a = nn.Linear(base.in_features, rank, bias=False).to(base.weight.device)
        self.b = nn.Linear(rank, base.out_features, bias=False).to(base.weight.device)
        nn.init.kaiming_uniform_(self.a.weight, a=math.sqrt(5))
        nn.init.zeros_(self.b.weight)

    @property
    def weight(self):
        return self.base.weight

    def forward(self, x):
        result = self.base(x)
        return result + (self.b(self.a(x.float())) * self.scale).to(result.dtype)


def gaussian_log_prob(value, mean, std):
    # float64 reduction avoids cancellation of thousands of coordinate terms
    # in old/new log probabilities when bf16 policy velocities are identical.
    term = -0.5 * ((value.float() - mean.float()) / std).square() - math.log(std) - 0.5 * math.log(2 * math.pi)
    return term.double().flatten(1).sum(-1)


def group_advantages(returns):
    values = torch.as_tensor(returns, dtype=torch.float64)
    return ((values - values.mean()) / values.std(unbiased=False).clamp_min(1e-8)).float()


def grpo_loss(new_logp, old_logp, advantages, clip_ratio):
    log_ratio = new_logp.double() - old_logp.double()
    ratio = log_ratio.clamp(-30, 30).exp()
    advantage = advantages.to(ratio.device)
    return -torch.minimum(ratio * advantage, ratio.clamp(1 - clip_ratio, 1 + clip_ratio) * advantage).mean()


class ContinualRL:
    def __init__(self, runtime, cfg):
        self.runtime, self.cfg, self.stages = runtime, cfg, []
        self.modules = {}
        expert = runtime.model.paligemma_with_expert.gemma_expert
        targets = [(name, module) for name, module in expert.named_modules()
                   if isinstance(module, nn.Linear) and name.rsplit(".", 1)[-1] in
                   {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}]
        for name, module in targets:
            parent_name, attribute = name.rsplit(".", 1)
            wrapper = LoRALinear(module, cfg["rank"], cfg["alpha"])
            setattr(expert.get_submodule(parent_name), attribute, wrapper)
            self.modules[name] = wrapper
        if not self.modules:
            raise ValueError("no LoRA targets in PI0.5 action expert")

    def parameters(self):
        return [p for m in self.modules.values() for block in (m.a, m.b) for p in block.parameters()]

    @torch.no_grad()
    def sample(self, prefix):
        x = self.runtime.noise(len(prefix["padding"]))
        trajectory = []
        std = self.cfg["transition_std"]
        steps = self.runtime.cfg["inference_steps"]
        for i in range(steps):
            t = torch.full((len(x),), 1 - i / steps, device=x.device)
            mean = x - self.runtime.velocity(prefix, x, t) / steps
            following = mean + std * torch.randn_like(mean)
            logp = gaussian_log_prob(following, mean, std)
            trajectory.append(to_cpu({"x": x, "next": following, "time": t, "logp": logp}))
            x = following
        return x[..., :7], trajectory

    def transition_loss(self, prefix, transition, advantage):
        device = self.runtime.device
        x, y, t = (transition[k].to(device) for k in ("x", "next", "time"))
        mean = x - self.runtime.velocity(prefix, x, t) / self.runtime.cfg["inference_steps"]
        new_logp = gaussian_log_prob(y, mean, self.cfg["transition_std"])
        old_logp = transition["logp"].to(device)
        advantages = torch.as_tensor(advantage, device=device, dtype=new_logp.dtype).expand_as(new_logp)
        return grpo_loss(new_logp, old_logp, advantages, self.cfg["clip_ratio"])

    def state(self):
        return to_cpu({"stages": self.stages, "lora": {name: {"a": m.a.state_dict(), "b": m.b.state_dict()}
                                                       for name, m in self.modules.items()}})

    def restore(self, state):
        if set(state["lora"]) != set(self.modules):
            raise ValueError("LoRA topology changed")
        for name, module in self.modules.items():
            module.a.load_state_dict(state["lora"][name]["a"], strict=True)
            module.b.load_state_dict(state["lora"][name]["b"], strict=True)
        self.stages = state["stages"]
