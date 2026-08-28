"""Runnable PI0.5 integration for the CLARE continual-learning baseline.

The algorithmic primitives live in :mod:`mode_gate.baselines`.  This module
binds them to the real PI0.5 action-expert FFNs, implements the paper-ordered
adapter/discriminator training phases, and stores an immutable artifact that
can be reloaded without a task ID at inference time.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Iterator, Mapping, Sequence

import torch
from safetensors.torch import load_file, save_file
from torch import Tensor, nn

from .baselines import (
    ClareConfig,
    ClareDiscriminatorStats,
    ClareExpandableFFN,
    ClareStagePlan,
    ClareSystem,
)
from .io_utils import atomic_write_json, sha256_file


_ACTION_EXPERT_MLP = re.compile(
    r"(?:^|\.)gemma_expert\.model\.layers\.(\d+)\.mlp$"
)


def default_pi05_clare_config(
    policy: nn.Module,
    *,
    adapter_rank: int = 32,
    discriminator_hidden_dim: int = 256,
    discriminator_latent_dim: int = 128,
    gamma: float = 2.5,
) -> ClareConfig:
    """Pre-register every PI0.5 action-expert FFN as expandable.

    Restricting the baseline to the action expert keeps it lightweight while
    still applying CLARE at every layer that directly produces robot actions.
    Layer names are taken from the live model, so architecture drift fails
    before training rather than silently changing the baseline.
    """

    discovered: list[tuple[int, str, int]] = []
    for name, module in policy.named_modules():
        match = _ACTION_EXPERT_MLP.search(name)
        if match is None:
            continue
        up_proj = getattr(module, "up_proj", None)
        feature_dim = getattr(up_proj, "in_features", None)
        if not isinstance(feature_dim, int) or feature_dim <= 0:
            raise ValueError(f"cannot infer square FFN width for {name}")
        discovered.append((int(match.group(1)), name, feature_dim))
    discovered.sort()
    indices = [item[0] for item in discovered]
    if not discovered or indices != list(range(len(discovered))):
        raise ValueError(
            "PI0.5 CLARE requires a contiguous action-expert layer stack"
        )
    return ClareConfig(
        expandable_layers=tuple(item[1] for item in discovered),
        feature_dims={item[1]: item[2] for item in discovered},
        adapter_rank=adapter_rank,
        discriminator_hidden_dim=discriminator_hidden_dim,
        discriminator_latent_dim=discriminator_latent_dim,
        gamma=gamma,
    )


class Pi05ClareIntegration:
    """Inject CLARE side branches into an already loaded PI0.5 policy."""

    def __init__(self, policy: nn.Module, system: ClareSystem) -> None:
        self.policy = policy
        self.system = system
        self.wrappers: dict[str, ClareExpandableFFN] = {}
        self._inject()

    @classmethod
    def create(cls, policy: nn.Module, **config_overrides: Any) -> "Pi05ClareIntegration":
        config = default_pi05_clare_config(policy, **config_overrides)
        return cls(policy, ClareSystem(config))

    def _inject(self) -> None:
        for parameter in self.policy.parameters():
            parameter.requires_grad_(False)
        device: torch.device | None = None
        for layer_name in self.system.config.expandable_layers:
            module = _resolve_module(self.policy, layer_name)
            if isinstance(module, ClareExpandableFFN):
                raise ValueError(f"CLARE already injected at {layer_name}")
            first_parameter = next(module.parameters(), None)
            if first_parameter is not None:
                if device is None:
                    device = first_parameter.device
                elif first_parameter.device != device:
                    raise ValueError("CLARE expandable layers span multiple devices")
            wrapper = ClareExpandableFFN(
                module, self.system.layer_bank(layer_name)
            )
            _replace_module(self.policy, layer_name, wrapper)
            self.wrappers[layer_name] = wrapper
        if device is not None:
            self.system.to(device=device)

    @contextmanager
    def capture(self, *, max_rows_per_layer: int = 4096) -> Iterator[dict[str, list[Tensor]]]:
        if max_rows_per_layer <= 0:
            raise ValueError("max_rows_per_layer must be positive")
        captured: dict[str, list[Tensor]] = {
            name: [] for name in self.system.config.expandable_layers
        }
        counts = {name: 0 for name in captured}
        handles = []

        def hook_for(layer_name: str):
            def hook(_module: nn.Module, inputs: tuple[Any, ...]) -> None:
                if not inputs or not isinstance(inputs[0], Tensor):
                    raise ValueError(f"{layer_name} did not receive tensor features")
                values = inputs[0].detach().float().reshape(
                    -1, self.system.config.feature_dims[layer_name]
                )
                remaining = max_rows_per_layer - counts[layer_name]
                if remaining <= 0:
                    return
                values = values[:remaining]
                if len(values):
                    captured[layer_name].append(values)
                    counts[layer_name] += len(values)

            return hook

        try:
            for layer_name, wrapper in self.wrappers.items():
                handles.append(wrapper.register_forward_pre_hook(hook_for(layer_name)))
            yield captured
        finally:
            for handle in handles:
                handle.remove()

    @torch.no_grad()
    def collect_features(
        self,
        forward_calls: Sequence[Callable[[], Any]],
        *,
        max_rows_per_layer: int = 4096,
    ) -> dict[str, Tensor]:
        if not forward_calls:
            raise ValueError("feature collection requires at least one forward call")
        with self.capture(max_rows_per_layer=max_rows_per_layer) as captured:
            for forward in forward_calls:
                forward()
        result = {}
        for layer_name, chunks in captured.items():
            if not chunks:
                raise RuntimeError(f"no CLARE features captured for {layer_name}")
            result[layer_name] = torch.cat(chunks, dim=0)
        return result

    def apply_stage_plan(self, plan: ClareStagePlan) -> dict[str, dict[str, str]]:
        created = self.system.apply_stage_plan(plan)
        for layer_name, wrapper in self.wrappers.items():
            parameter = next(wrapper.frozen_ffn.parameters(), None)
            if parameter is not None:
                self.system.layer_bank(layer_name).to(device=parameter.device)
        return created

    def force_stage(self, plan: ClareStagePlan) -> None:
        for decision in plan.layer_decisions:
            adapter_id = (
                f"adapter::{plan.stage_id}"
                if decision.expand
                else decision.linked_adapter_id
            )
            if adapter_id is None:
                raise RuntimeError("CLARE stage plan has no adapter assignment")
            self.system.layer_bank(decision.layer_name).force_adapter(adapter_id)

    def clear_forced_routing(self) -> None:
        for layer_name in self.system.config.expandable_layers:
            self.system.layer_bank(layer_name).force_adapter(None)


def train_clare_stage(
    integration: Pi05ClareIntegration,
    *,
    stage_id: str,
    feature_forwards: Sequence[Callable[[], Any]],
    loss_forward: Callable[[], Tensor],
    adapter_steps: int = 1_000,
    discriminator_steps: int = 2_000,
    adapter_learning_rate: float = 2.5e-5,
    discriminator_learning_rate: float = 5e-4,
    discriminator_batch_size: int = 32,
    seed: int = 20260825,
) -> dict[str, Any]:
    """Run CLARE's adapter phase followed by its discriminator phase."""

    if min(adapter_steps, discriminator_steps, discriminator_batch_size) <= 0:
        raise ValueError("CLARE training counts must be positive")
    if min(adapter_learning_rate, discriminator_learning_rate) <= 0:
        raise ValueError("CLARE learning rates must be positive")
    torch.manual_seed(seed)
    initial_features = integration.collect_features(feature_forwards)
    plan = integration.system.plan_stage(stage_id, initial_features)
    topology = integration.apply_stage_plan(plan)
    integration.force_stage(plan)
    adapter_parameters = integration.system.trainable_adapter_parameters(stage_id)
    if not adapter_parameters:
        raise RuntimeError("CLARE stage did not create a trainable adapter")
    adapter_optimizer = torch.optim.AdamW(
        adapter_parameters, lr=adapter_learning_rate
    )
    adapter_losses = []
    integration.policy.train()
    for _ in range(adapter_steps):
        loss = loss_forward()
        if loss.ndim:
            loss = loss.mean()
        if not bool(torch.isfinite(loss.detach())):
            raise FloatingPointError("non-finite CLARE adapter loss")
        adapter_optimizer.zero_grad(set_to_none=True)
        loss.backward()
        adapter_optimizer.step()
        adapter_losses.append(float(loss.detach().cpu()))

    integration.policy.eval()
    stage_features = integration.collect_features(feature_forwards)
    discriminator_parameters = integration.system.trainable_discriminator_parameters(
        stage_id
    )
    discriminator_optimizer = torch.optim.Adam(
        discriminator_parameters, lr=discriminator_learning_rate
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    discriminator_losses = []
    for _ in range(discriminator_steps):
        losses = []
        for layer_name, values in stage_features.items():
            indices = torch.randint(
                len(values),
                (discriminator_batch_size,),
                generator=generator,
                device="cpu",
            ).to(values.device)
            batch = values.index_select(0, indices)
            discriminator = integration.system.layer_bank(layer_name).discriminators[
                f"disc::{stage_id}"
            ]
            losses.append(discriminator.reconstruction_error(batch).mean())
        loss = torch.stack(losses).mean()
        if not bool(torch.isfinite(loss.detach())):
            raise FloatingPointError("non-finite CLARE discriminator loss")
        discriminator_optimizer.zero_grad(set_to_none=True)
        loss.backward()
        discriminator_optimizer.step()
        discriminator_losses.append(float(loss.detach().cpu()))
    stats = integration.system.finalize_stage_statistics(stage_id, stage_features)
    integration.clear_forced_routing()
    return {
        "schema_version": "clare-stage-training-v1",
        "stage_id": stage_id,
        "plan": {
            "expanded_layers": list(plan.expanded_layers),
            "decisions": [asdict(item) for item in plan.layer_decisions],
        },
        "topology": topology,
        "adapter_steps": adapter_steps,
        "adapter_loss_first": adapter_losses[0],
        "adapter_loss_last": adapter_losses[-1],
        "discriminator_steps": discriminator_steps,
        "discriminator_loss_first": discriminator_losses[0],
        "discriminator_loss_last": discriminator_losses[-1],
        "statistics": {name: asdict(value) for name, value in stats.items()},
    }


def save_clare_artifact(
    output_dir: Path,
    system: ClareSystem,
    *,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically save CLARE topology, routing statistics, and weights."""

    output_dir = Path(output_dir)
    staging = output_dir.parent / f".{output_dir.name}.{os.getpid()}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    weights = {
        key: value.detach().contiguous().cpu()
        for key, value in system.state_dict().items()
    }
    weights_path = staging / "clare.safetensors"
    save_file(weights, weights_path)
    value = {
        "schema_version": "pi05-clare-artifact-v1",
        "system": system.manifest(),
        "weights_sha256": sha256_file(weights_path),
        "provenance": dict(provenance),
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    value["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()
    atomic_write_json(staging / "manifest.json", value)
    if output_dir.exists():
        existing = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        if existing != value or sha256_file(output_dir / "clare.safetensors") != value[
            "weights_sha256"
        ]:
            raise ValueError("immutable CLARE artifact collision")
        shutil.rmtree(staging)
        return existing
    os.replace(staging, output_dir)
    return value


def load_clare_artifact(path: Path) -> ClareSystem:
    """Strictly restore a CLARE system before injecting it into PI0.5."""

    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "pi05-clare-artifact-v1":
        raise ValueError("unsupported CLARE artifact schema")
    weights_path = path / "clare.safetensors"
    if sha256_file(weights_path) != manifest.get("weights_sha256"):
        raise ValueError("CLARE artifact weights digest mismatch")
    stored_digest = manifest.get("artifact_sha256")
    unsigned = {key: value for key, value in manifest.items() if key != "artifact_sha256"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != stored_digest:
        raise ValueError("CLARE artifact manifest digest mismatch")
    system_value = manifest["system"]
    config_value = system_value["config"]
    config = ClareConfig(
        expandable_layers=tuple(config_value["expandable_layers"]),
        feature_dims={
            str(key): int(value) for key, value in config_value["feature_dims"].items()
        },
        adapter_rank=int(config_value["adapter_rank"]),
        discriminator_hidden_dim=int(config_value["discriminator_hidden_dim"]),
        discriminator_latent_dim=int(config_value["discriminator_latent_dim"]),
        gamma=float(config_value["gamma"]),
        min_std=float(config_value["min_std"]),
    )
    system = ClareSystem(config)
    for layer_name in config.expandable_layers:
        layer_value = system_value["layers"][layer_name]
        bank = system.layer_bank(layer_name)
        for adapter_id in layer_value["adapters"]:
            bank.add_adapter(str(adapter_id))
        for discriminator_id, adapter_id in layer_value["links"].items():
            bank.add_discriminator(
                str(discriminator_id), linked_adapter_id=str(adapter_id)
            )
        bank.stats = {
            str(name): ClareDiscriminatorStats(**raw)
            for name, raw in layer_value["stats"].items()
        }
    system.stage_ids = [str(value) for value in system_value["stage_ids"]]
    state = load_file(weights_path, device="cpu")
    missing, unexpected = system.load_state_dict(state, strict=False)
    if missing or unexpected:
        raise ValueError(
            f"CLARE artifact state mismatch; missing={missing}, unexpected={unexpected}"
        )
    if system.manifest() != system_value:
        raise ValueError("CLARE artifact topology changed during restore")
    return system


def _resolve_module(root: nn.Module, path: str) -> nn.Module:
    current: Any = root
    for part in path.split("."):
        current = current[int(part)] if part.isdigit() else getattr(current, part)
    if not isinstance(current, nn.Module):
        raise TypeError(f"{path} does not resolve to a torch module")
    return current


def _replace_module(root: nn.Module, path: str, replacement: nn.Module) -> None:
    parts = path.split(".")
    parent = _resolve_module(root, ".".join(parts[:-1])) if len(parts) > 1 else root
    leaf = parts[-1]
    if leaf.isdigit():
        parent[int(leaf)] = replacement  # type: ignore[index]
    else:
        setattr(parent, leaf, replacement)


__all__ = [
    "Pi05ClareIntegration",
    "default_pi05_clare_config",
    "load_clare_artifact",
    "save_clare_artifact",
    "train_clare_stage",
]
