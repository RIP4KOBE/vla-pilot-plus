"""RL²-VLA port: QAM, latent LSTM failure detection and velocity composition.

QAM follows the slow behavior flow / fast adjoint-matched flow and pessimistic
TD ensemble in rl2-vla/qam (56084df5). Time runs noise->action in QAM and
action->noise in PI0.5: composition MUST negate QAM's velocity at 1-t.
The Bridge-specific CoVer model is replaced by a separately supervised
PI0.5 latent/action success verifier, trained only on executed chunks.
"""
import copy
import math

import torch
from torch import nn
from torch.nn import functional as F

from ..io import to_cpu


def mlp(input_dim, output_dim, hidden, layers, layer_norm=False, paper_reference=False):
    modules = []
    for _ in range(layers):
        modules.append(nn.Linear(input_dim, hidden))
        if paper_reference:
            modules.append(nn.GELU(approximate="tanh"))
            if layer_norm:
                modules.append(nn.LayerNorm(hidden, eps=1e-6))
        elif layer_norm:
            modules.append(nn.LayerNorm(hidden))
        if not paper_reference:
            modules.append(nn.SiLU())
        input_dim = hidden
    modules.append(nn.Linear(input_dim, output_dim))
    return nn.Sequential(*modules)


class FlowActor(nn.Module):
    def __init__(self, latent_dim, action_dim, cfg):
        super().__init__()
        self.net = mlp(latent_dim + action_dim + 1, action_dim, cfg["hidden_dim"], cfg["hidden_layers"],
                       paper_reference=cfg.get("training_recipe") == "paper_reference")

    def forward(self, latent, action, time):
        return self.net(torch.cat((latent, action, time), -1))


class CriticEnsemble(nn.Module):
    def __init__(self, latent_dim, action_dim, cfg):
        super().__init__()
        self.members = nn.ModuleList([mlp(latent_dim + action_dim, 1, cfg["hidden_dim"], cfg["hidden_layers"], True,
                                         cfg.get("training_recipe") == "paper_reference")
                                      for _ in range(cfg["q_ensemble"])])

    def forward(self, latent, action):
        value = torch.cat((latent, action), -1)
        return torch.stack([network(value).squeeze(-1) for network in self.members])


class QAM(nn.Module):
    def __init__(self, latent_dim, action_dim, cfg):
        super().__init__()
        self.cfg, self.action_dim = cfg, action_dim
        self.slow = FlowActor(latent_dim, action_dim, cfg)
        self.fast = FlowActor(latent_dim, action_dim, cfg) if cfg.get("training_recipe") == "paper_reference" else copy.deepcopy(self.slow)
        self.critic = CriticEnsemble(latent_dim, action_dim, cfg)
        self.target_slow = copy.deepcopy(self.slow).requires_grad_(False)
        self.target_critic = copy.deepcopy(self.critic).requires_grad_(False)

    @torch.no_grad()
    def sample(self, latent):
        x = torch.randn(len(latent), self.action_dim, device=latent.device)
        for i in range(self.cfg["flow_steps"]):
            t = torch.full((len(x), 1), i / self.cfg["flow_steps"], device=x.device)
            actor = self.slow if self.cfg["inverse_temperature"] == 0 else self.fast
            x = x + actor(latent, x, t) / self.cfg["flow_steps"]
        return x.clamp(-self.cfg["action_clip"], self.cfg["action_clip"])

    def adjoint_targets(self, latent):
        h = 1 / self.cfg["flow_steps"]
        x = torch.randn(len(latent), self.action_dim, device=latent.device)
        xs, ts = [x], []
        with torch.no_grad():
            for i in range(self.cfg["flow_steps"]):
                t = torch.full((len(x), 1), i * h, device=x.device)
                sigma = (2 * (1 - t + h) / (t + h)).sqrt()
                if i == self.cfg["flow_steps"] - 1:
                    x = x + h * self.target_slow(latent, x, t)
                else:
                    x = x + h * (2 * self.fast(latent, x, t) - x / (t + h)) + math.sqrt(h) * sigma * torch.randn_like(x)
                xs.append(x)
                ts.append(t)
        with torch.enable_grad():
            terminal = xs[-1].detach().requires_grad_(True)
            value = self.target_critic(latent, terminal.clamp(-self.cfg["action_clip"], self.cfg["action_clip"])).mean(0).sum()
            adj = -self.cfg["inverse_temperature"] * torch.autograd.grad(value, terminal)[0]
            adjoints = []
            for i in reversed(range(self.cfg["flow_steps"])):
                point = xs[i].detach().requires_grad_(True)
                drift = 2 * self.target_slow(latent, point, ts[i] + h) - point / (ts[i] + h)
                product = torch.autograd.grad(drift, point, grad_outputs=adj, create_graph=False)[0]
                adj = (adj + h * product).detach()
                adjoints.append(adj)
        return torch.stack(xs[:-1]), torch.stack(ts), torch.stack(list(reversed(adjoints)))

    def losses(self, batch):
        latent, actions = batch["latent"], batch["actions"]
        with torch.no_grad():
            next_action = self.sample(batch["next_latent"])
            q = self.target_critic(batch["next_latent"], next_action)
            pessimistic = q.mean(0) - self.cfg["pessimism"] * q.std(0, unbiased=False)
            target = batch["reward"] + batch["bootstrap_discount"] * pessimistic
        critic_loss = (self.critic(latent, actions) - target[None]).square().mean()
        noise = torch.randn_like(actions)
        time = torch.rand(len(actions), 1, device=actions.device)
        x = (1 - time) * noise + time * actions
        flow_loss = (self.slow(latent, x, time) - (actions - noise)).square().mean()
        xs, ts, adj = self.adjoint_targets(latent.detach())
        repeated = latent[None].expand(len(xs), -1, -1)
        h = 1 / self.cfg["flow_steps"]
        sigma = (2 * (1 - ts + h) / (ts + h)).sqrt()
        with torch.no_grad():
            prior = self.target_slow(repeated, xs, ts)
        correction = 2 * (self.fast(repeated, xs, ts) - prior) / sigma + sigma * adj
        adj_loss = correction.square().sum(-1).sum(0).mean()
        return critic_loss + flow_loss + adj_loss, {
            "critic_loss": float(critic_loss.detach()), "flow_loss": float(flow_loss.detach()),
            "adjoint_loss": float(adj_loss.detach())}

    @torch.no_grad()
    def update_targets(self):
        for source, target in ((self.slow, self.target_slow), (self.critic, self.target_critic)):
            for p, target_p in zip(source.parameters(), target.parameters(), strict=True):
                target_p.lerp_(p, self.cfg["target_tau"])


class FailureLSTM(nn.Module):
    def __init__(self, latent_dim, hidden):
        super().__init__()
        self.lstm = nn.LSTM(latent_dim, hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, sequence, state=None):
        value, state = self.lstm(sequence, state)
        return self.head(value).squeeze(-1), state


def conformal_threshold(success_episode_scores, alpha):
    """Episode-maximum calibration gives a simultaneous, anytime success band.

    Calibrate on held-out SUCCESS episodes only, never on the evaluation set.
    Reject undersized calibration banks instead of silently inventing a gate.
    """
    maxima = sorted(float(torch.as_tensor(row).max()) for row in success_episode_scores)
    rank = math.ceil((len(maxima) + 1) * (1 - alpha))
    if not maxima or rank > len(maxima):
        raise ValueError(f"need at least {math.ceil(1 / alpha) - 1} held-out successful calibration episodes")
    if not all(math.isfinite(x) and 0 <= x <= 1 for x in maxima):
        raise ValueError("calibration probabilities must be finite and in [0,1]")
    return maxima[rank - 1]


def compose_velocity(base, qam_velocity, weights, horizon):
    """QAM flows in increasing time, opposite to PI0.5's decreasing time."""
    out = base.clone()
    rl = -qam_velocity.reshape(len(base), horizon, 7)
    w = weights.reshape(-1, 1, 1)
    out[:, :horizon, :7] = w * base[:, :horizon, :7] + (1 - w) * rl
    return out


class RL2VLA:
    def __init__(self, runtime, cfg):
        self.runtime, self.cfg = runtime, cfg
        self.horizon = runtime.cfg["execution_horizon"]
        self.qam = QAM(runtime.hidden_dim, self.horizon * 7, cfg).to(runtime.device)
        self.detector = FailureLSTM(runtime.hidden_dim, cfg["safe_hidden"]).to(runtime.device)
        self.verifier = mlp(runtime.hidden_dim + self.horizon * 7, 1, 256, 2).to(runtime.device)
        self.threshold = None
        self.recurrent_state = None
        self.stages = []

    def reset(self):
        self.recurrent_state = None

    @torch.no_grad()
    def action(self, embedded):
        prefix = self.runtime.prefix(embedded)
        latent = self.runtime.latent(prefix)
        logits, self.recurrent_state = self.detector(latent[:, None], self.recurrent_state)
        probability = float(logits.sigmoid()[0, -1])
        if self.cfg["trigger"] == "adaptive" and self.threshold is None:
            raise ValueError("adaptive RL2 requires a trained, calibrated failure detector")
        steering = self.cfg["trigger"] == "always" or (self.cfg["trigger"] == "adaptive" and probability > self.threshold)
        n = self.cfg["candidates"]
        batch = {k: v.expand(n, *v.shape[1:]) for k, v in embedded.items()}
        prefix = self.runtime.prefix(batch)
        latent = latent.expand(n, -1)
        weights = (torch.randn(n, device=latent.device) * self.cfg["compose_std"] + self.cfg["compose_mean"]).clamp(0, 1)
        def compose(x, t, base):
            actor = self.qam.slow if self.cfg["inverse_temperature"] == 0 else self.qam.fast
            qv = actor(latent, x[:, :self.horizon, :7].reshape(n, -1).float(), (1 - t)[:, None])
            return compose_velocity(base, qv, weights, self.horizon)
        samples = self.runtime.sample(prefix, compose=compose if steering else None)
        scores = self.verifier(torch.cat((latent, samples[:, :self.horizon].reshape(n, -1)), -1)).squeeze(-1)
        best = int(scores.argmax())
        return samples[best:best + 1], {"steering": steering, "failure_probability": probability,
                                       "candidate_count": n, "best_score": float(scores[best])}

    def state(self):
        return to_cpu({"qam": self.qam.state_dict(), "detector": self.detector.state_dict(),
                       "verifier": self.verifier.state_dict(), "threshold": self.threshold, "stages": self.stages})

    def restore(self, state):
        for name in ("qam", "detector", "verifier"):
            getattr(self, name).load_state_dict(state[name], strict=True)
        self.threshold, self.stages = state["threshold"], state["stages"]
