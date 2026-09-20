"""Multimodal latent replay with similarity-selected angular feature adjustment."""
from pathlib import Path
import math
import random

import torch
from torch import nn
from torch.nn import functional as F

from ..io import to_cpu, load_tensors


class ByteReplay:
    """Task-balanced retained memory, measured in actual serialized bytes.

    Current-stage input caches are separate from retained historical memory.
    The caller may delete only unselected cache files it created itself.
    """
    def __init__(self, budget, seed):
        self.budget, self.seed = int(budget), seed
        self.entries = []

    def update(self, current):
        candidates = self.entries + list(current)
        tasks = sorted({v["task_key"] for v in candidates})
        groups = {key: [v for v in candidates if v["task_key"] == key] for key in tasks}
        rng = random.Random(self.seed + len(tasks))
        for rows in groups.values():
            rng.shuffle(rows)
        quota = self.budget // max(len(tasks), 1)
        retained = []
        for key in tasks:
            used = 0
            for row in groups[key]:
                if used + row["bytes"] <= quota:
                    retained.append(row)
                    used += row["bytes"]
        if tasks and len({v["task_key"] for v in retained}) != len(tasks):
            raise ValueError("memory budget cannot retain one exact latent record per task; increase memory_bytes")
        self.entries = retained
        return retained

    @property
    def bytes(self):
        return sum(v["bytes"] for v in self.entries)

    def draw(self, current, batch_size, replay_fraction, rng):
        nold = round(batch_size * replay_fraction) if self.entries else 0
        nold = min(nold, batch_size - 1)
        return rng.choices(current, k=batch_size - nold) + (rng.choices(self.entries, k=nold) if nold else [])


def selected_similar_pairs(prototypes, fraction):
    """Intersection of the top language-similarity and vision-similarity pairs."""
    keys = sorted(prototypes)
    pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
    if not pairs:
        return set()
    count = max(1, math.ceil(len(pairs) * fraction))
    selected = []
    for modality in ("language", "visual"):
        scores = [float(F.cosine_similarity(prototypes[a][modality][None].float(),
                                           prototypes[b][modality][None].float())) for a, b in pairs]
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], pairs[i]))[:count]
        selected.append({pairs[i] for i in order})
    return selected[0] & selected[1]


def angular_margin_loss(features, task_keys, prototypes, pairs, gamma):
    losses = []
    for i, key in enumerate(task_keys):
        for a, b in sorted(pairs):
            if key not in (a, b):
                continue
            other = b if key == a else a
            pos = prototypes[key]["language"].to(features.device).float()
            neg = prototypes[other]["language"].to(features.device).float()
            def angle(x, y):
                return torch.acos(F.cosine_similarity(x[None], y[None]).clamp(-1 + 1e-6, 1 - 1e-6)).squeeze()
            losses.append(F.relu(angle(features[i], pos) - angle(features[i], neg) + gamma * angle(pos, neg)))
    return torch.stack(losses).mean() if losses else features.sum() * 0


class MLRIFA:
    def __init__(self, runtime, cfg):
        self.runtime, self.cfg = runtime, cfg
        runtime.unfreeze_action_expert()
        # The source decoder and CLIP share a width. PI0.5 uses 1024/2048;
        # this auxiliary projection makes that angular comparison well-defined.
        # It is not consulted when generating actions.
        self.feature_projection = nn.Linear(runtime.hidden_dim, runtime.prefix_dim, bias=False).to(runtime.device)
        self.prototypes = {}
        self.stages = []

    def add_prototype(self, key, entries):
        language, visual = [], []
        for row in entries:
            embedded = load_tensors(row["path"])["embedded"]
            language.append(F.normalize(embedded["language"].float(), dim=-1))
            visual.append(F.normalize(embedded["visual"].float(), dim=-1))
        self.prototypes[key] = {"language": torch.cat(language).mean(0), "visual": torch.cat(visual).mean(0)}

    def loss(self, embedded, actions, padding, task_keys):
        prefix = self.runtime.prefix(embedded)
        flow, features = self.runtime.flow_loss(prefix, actions, padding=padding, return_features=True)
        pairs = selected_similar_pairs(self.prototypes, self.cfg["similar_pair_fraction"])
        ifa = angular_margin_loss(self.feature_projection(features), task_keys, self.prototypes,
                                 pairs, self.cfg["angular_margin_scale"])
        return flow + self.cfg["ifa_weight"] * ifa, {"flow_loss": float(flow), "ifa_loss": float(ifa), "selected_pairs": len(pairs)}

    def parameters(self):
        return [p for p in self.runtime.policy.parameters() if p.requires_grad] + list(self.feature_projection.parameters())

    def state(self):
        return to_cpu({"policy": self.runtime.trainable_state(), "projection": self.feature_projection.state_dict(),
                       "prototypes": self.prototypes, "stages": self.stages})

    def restore(self, state):
        self.runtime.restore_partial(state["policy"])
        self.feature_projection.load_state_dict(state["projection"], strict=True)
        self.prototypes, self.stages = state["prototypes"], state["stages"]
