"""Source-aware co-FT sampling contract and fixed training configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import torch
from torch.utils.data import Sampler

from .io_utils import atomic_write_json, sha256_file


@dataclass(frozen=True)
class CoFTConfig:
    gpus: int = 1
    per_device_batch_size: int = 4
    gradient_accumulation_steps: int = 8
    global_batch_size: int = 32
    optimizer_steps: int = 1000
    optimizer: str = "AdamW"
    peak_lr: float = 2.5e-5
    warmup_steps: int = 1000
    decay_steps: int = 30000
    decay_lr: float = 2.5e-6
    beta1: float = 0.9
    beta2: float = 0.95
    eps: float = 1e-8
    weight_decay: float = 1e-10
    grad_clip: float = 1.0
    gradient_checkpointing: bool = True
    auto_scale_schedule: bool = False
    save_final_params_only: bool = True

    def validate(self) -> None:
        if not 1 <= self.gpus <= 2:
            raise ValueError("co-FT may use only one or two GPUs")
        if (
            self.gpus
            * self.per_device_batch_size
            * self.gradient_accumulation_steps
            != self.global_batch_size
        ):
            raise ValueError(
                "global batch must equal GPUs × per-device batch × accumulation"
            )
        if self.optimizer_steps != 1000 or self.auto_scale_schedule:
            raise ValueError("v2 co-FT schedule is frozen")


@dataclass(frozen=True)
class TrainingSmokeConfig(CoFTConfig):
    """Twenty-step schedule used only for the blocking trainer canary."""

    optimizer_steps: int = 20

    def validate(self) -> None:
        if not 1 <= self.gpus <= 2:
            raise ValueError("training smoke may use only one or two GPUs")
        if (
            self.gpus
            * self.per_device_batch_size
            * self.gradient_accumulation_steps
            != self.global_batch_size
        ):
            raise ValueError(
                "global batch must equal GPUs × per-device batch × accumulation"
            )
        if self.optimizer_steps != 20 or self.auto_scale_schedule:
            raise ValueError("training smoke is frozen to 20 unscaled steps")


class SourceAwareSampler(Sampler[int]):
    """Deterministic transition sampler with 50/25/25 source mass."""

    def __init__(
        self,
        *,
        new_indices: Sequence[int],
        old_ticket_indices: Mapping[str, Sequence[int]],
        replay_indices: Sequence[int],
        num_samples: int,
        seed: int,
    ) -> None:
        self.num_samples = int(num_samples)
        self.seed = int(seed)
        if not new_indices or not replay_indices:
            raise ValueError("new demos and replay transitions are both required")
        all_indices: list[int] = []
        all_weights: list[float] = []
        new_mass = 0.50
        old_mass = 0.25 if old_ticket_indices else 0.0
        replay_mass = 0.25 if old_ticket_indices else 0.50
        for index in new_indices:
            all_indices.append(int(index))
            all_weights.append(new_mass / len(new_indices))
        if old_ticket_indices:
            per_ticket = old_mass / len(old_ticket_indices)
            for ticket in sorted(old_ticket_indices):
                values = old_ticket_indices[ticket]
                if not values:
                    raise ValueError(f"accepted ticket {ticket} has no transitions")
                for index in values:
                    all_indices.append(int(index))
                    all_weights.append(per_ticket / len(values))
        for index in replay_indices:
            all_indices.append(int(index))
            all_weights.append(replay_mass / len(replay_indices))
        self.indices = torch.tensor(all_indices, dtype=torch.long)
        self.weights = torch.tensor(all_weights, dtype=torch.double)
        self._new_indices = torch.tensor(list(map(int, new_indices)), dtype=torch.long)
        self._old_ticket_indices = {
            str(ticket): torch.tensor(list(map(int, values)), dtype=torch.long)
            for ticket, values in sorted(old_ticket_indices.items())
        }
        self._replay_indices = torch.tensor(
            list(map(int, replay_indices)), dtype=torch.long
        )
        self.source_masses = {
            "new": new_mass,
            "old": old_mass,
            "replay": replay_mass,
        }

    def __iter__(self):
        generator = torch.Generator().manual_seed(self.seed)
        names = ("new", "old", "replay")
        exact = {
            name: self.source_masses[name] * self.num_samples for name in names
        }
        counts = {name: int(np.floor(exact[name])) for name in names}
        remaining = self.num_samples - sum(counts.values())
        for name in sorted(names, key=lambda item: (-(exact[item] - counts[item]), item))[
            :remaining
        ]:
            counts[name] += 1

        draws: list[torch.Tensor] = []
        draws.append(
            self._new_indices[
                torch.randint(
                    len(self._new_indices),
                    (counts["new"],),
                    generator=generator,
                )
            ]
        )
        if counts["old"]:
            tickets = tuple(sorted(self._old_ticket_indices))
            ticket_choices = torch.randint(
                len(tickets),
                (counts["old"],),
                generator=generator,
            )
            old_draws = []
            for ticket_index in ticket_choices.tolist():
                values = self._old_ticket_indices[tickets[ticket_index]]
                offset = int(
                    torch.randint(len(values), (1,), generator=generator).item()
                )
                old_draws.append(int(values[offset]))
            draws.append(torch.tensor(old_draws, dtype=torch.long))
        draws.append(
            self._replay_indices[
                torch.randint(
                    len(self._replay_indices),
                    (counts["replay"],),
                    generator=generator,
                )
            ]
        )
        sampled = torch.cat(draws)
        sampled = sampled[torch.randperm(len(sampled), generator=generator)]
        return iter(sampled.tolist())

    def __len__(self) -> int:
        return self.num_samples


def write_training_manifest(
    path: Path,
    *,
    config: CoFTConfig,
    dataset_manifests: Mapping[str, str],
    actual_source_counts: Mapping[str, int],
    theta0_processor_hash: str,
) -> dict:
    config.validate()
    total = sum(actual_source_counts.values())
    if total <= 0:
        raise ValueError("training source counts are empty")
    expected = {
        "new": 0.50,
        "old": 0.25 if actual_source_counts.get("old", 0) else 0.0,
        "replay": 0.25 if actual_source_counts.get("old", 0) else 0.50,
    }
    observed = {key: actual_source_counts.get(key, 0) / total for key in expected}
    if any(abs(observed[key] - expected[key]) > 0.02 for key in expected):
        raise ValueError(f"actual source ratio exceeds ±2%: {observed}")
    value = {
        "schema_version": "coft-training-manifest-v1",
        "config": asdict(config),
        "dataset_manifests": dict(dataset_manifests),
        "actual_source_counts": dict(actual_source_counts),
        "actual_source_ratios": observed,
        "theta0_processor_hash": theta0_processor_hash,
        "processor_stats_frozen": True,
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    value["manifest_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    atomic_write_json(path, value)
    return value


def write_source_sampler_manifest(
    path: Path,
    *,
    new_indices: Sequence[int],
    old_ticket_indices: Mapping[str, Sequence[int]],
    replay_indices: Sequence[int],
    dataset_size: int,
    config: CoFTConfig = CoFTConfig(),
    seed: int,
) -> dict:
    """Freeze transition identities and the exact 50/25/25 draw vector."""

    config.validate()
    groups = {
        "new": [int(value) for value in new_indices],
        "replay": [int(value) for value in replay_indices],
    }
    old = {
        str(ticket): [int(value) for value in values]
        for ticket, values in sorted(old_ticket_indices.items())
    }
    flat = groups["new"] + groups["replay"] + [
        value for values in old.values() for value in values
    ]
    if len(flat) != len(set(flat)):
        raise ValueError("source sampler index groups must be disjoint")
    if not flat or min(flat) < 0 or max(flat) >= int(dataset_size):
        raise ValueError("source sampler contains an out-of-range dataset index")
    draws = config.optimizer_steps * config.global_batch_size
    sampler = SourceAwareSampler(
        new_indices=groups["new"],
        old_ticket_indices=old,
        replay_indices=groups["replay"],
        num_samples=draws,
        seed=seed,
    )
    index_to_source = {value: "new" for value in groups["new"]}
    index_to_source.update({value: "replay" for value in groups["replay"]})
    for values in old.values():
        index_to_source.update({value: "old" for value in values})
    actual = {"new": 0, "old": 0, "replay": 0}
    draw_digest = hashlib.sha256()
    for value in sampler:
        actual[index_to_source[int(value)]] += 1
        draw_digest.update(int(value).to_bytes(8, "little", signed=False))
    total = sum(actual.values())
    expected = sampler.source_masses
    observed = {name: count / total for name, count in actual.items()}
    if any(abs(observed[name] - expected[name]) > 0.02 for name in expected):
        raise RuntimeError(f"deterministic source draw exceeds ±2%: {observed}")
    value = {
        "schema_version": "coft-source-sampler-v1",
        "new_indices": groups["new"],
        "old_ticket_indices": old,
        "replay_indices": groups["replay"],
        "dataset_size": int(dataset_size),
        "num_draws": draws,
        "seed": int(seed),
        "actual_source_counts": actual,
        "actual_source_ratios": observed,
        "draw_vector_sha256": draw_digest.hexdigest(),
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    value["manifest_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    atomic_write_json(path, value)
    return value


def prepare_source_catalog(
    *,
    catalog_root: Path,
    manifest_path: Path,
    new_datasets: Mapping[str, Path],
    old_ticket_datasets: Mapping[str, Path],
    replay_datasets: Mapping[str, Path],
    seed: int,
    config: CoFTConfig = CoFTConfig(),
) -> dict:
    """Create an immutable symlink catalog and exact global transition ranges."""

    if not new_datasets or not replay_datasets:
        raise ValueError("co-FT catalog requires current-ticket and replay datasets")
    roles = {
        "new": {str(key): Path(value).resolve() for key, value in new_datasets.items()},
        "old": {
            str(key): Path(value).resolve()
            for key, value in old_ticket_datasets.items()
        },
        "replay": {
            str(key): Path(value).resolve() for key, value in replay_datasets.items()
        },
    }
    repo_ids = [
        repo_id
        for role in ("new", "old", "replay")
        for repo_id in sorted(roles[role])
    ]
    if len(repo_ids) != len(set(repo_ids)):
        raise ValueError("dataset repo IDs must be unique across source roles")
    catalog_root = Path(catalog_root)
    catalog_root.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, object]] = {}
    feature_contract = None
    fps = None
    offset = 0
    new_indices: list[int] = []
    old_indices: dict[str, list[int]] = {}
    replay_indices: list[int] = []
    for role in ("new", "old", "replay"):
        for repo_id, source in sorted(roles[role].items()):
            info_path = source / "meta" / "info.json"
            if not info_path.is_file():
                raise FileNotFoundError(info_path)
            info = json.loads(info_path.read_text(encoding="utf-8"))
            frames = int(info.get("total_frames", 0))
            if frames <= 0:
                raise ValueError(f"dataset {repo_id} has no transitions")
            current_features = json.dumps(
                info.get("features", {}), sort_keys=True, separators=(",", ":")
            )
            current_fps = int(info.get("fps", 0))
            if feature_contract is None:
                feature_contract, fps = current_features, current_fps
            if current_features != feature_contract or current_fps != fps:
                raise ValueError("co-FT source datasets have incompatible features/fps")
            target = catalog_root / repo_id
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                if target.resolve() != source:
                    raise ValueError(f"immutable dataset catalog collision: {target}")
            elif target.exists():
                if target.resolve() != source:
                    raise ValueError(f"catalog path already exists and is not the source: {target}")
            else:
                os.symlink(source, target, target_is_directory=True)
            indices = list(range(offset, offset + frames))
            if role == "new":
                new_indices.extend(indices)
            elif role == "old":
                old_indices[repo_id] = indices
            else:
                replay_indices.extend(indices)
            records[repo_id] = {
                "role": role,
                "source": str(source),
                "info_sha256": sha256_file(info_path),
                "frames": frames,
                "global_from_index": offset,
                "global_to_index": offset + frames,
            }
            offset += frames
    value = write_source_sampler_manifest(
        manifest_path,
        new_indices=new_indices,
        old_ticket_indices=old_indices,
        replay_indices=replay_indices,
        dataset_size=offset,
        config=config,
        seed=seed,
    )
    value.update(
        {
            "catalog_root": str(catalog_root.resolve()),
            "repo_ids": repo_ids,
            "datasets": records,
            "feature_contract_sha256": hashlib.sha256(
                str(feature_contract).encode()
            ).hexdigest(),
            "fps": fps,
        }
    )
    canonical = json.dumps(
        {key: item for key, item in value.items() if key != "manifest_sha256"},
        sort_keys=True,
        separators=(",", ":"),
    )
    value["manifest_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    atomic_write_json(manifest_path, value)
    return value


def build_lerobot_coft_command(
    *,
    python_executable: Path,
    parent_checkpoint: Path,
    dataset_root: Path,
    dataset_repo_id: str,
    dataset_repo_ids: Sequence[str] | None = None,
    source_sampler_manifest: Path,
    output_dir: Path,
    seed: int,
    tokenizer_path: Path = Path("/shared/hengyil6/vls/models/paligemma-tokenizer"),
    config: CoFTConfig = CoFTConfig(),
) -> list[str]:
    """Return the pinned 1–2 GPU LeRobot command used by the slow worker."""

    config.validate()
    dataset_arguments = (
        [f"--dataset.repo_ids={list(map(str, dataset_repo_ids))}"]
        if dataset_repo_ids
        else [f"--dataset.repo_id={dataset_repo_id}"]
    )
    return [
        str(python_executable),
        "-m",
        "accelerate.commands.launch",
        "--num_processes",
        str(config.gpus),
        "--mixed_precision",
        "bf16",
        "-m",
        "lerobot.scripts.lerobot_train",
        *dataset_arguments,
        f"--dataset.root={dataset_root}",
        f"--policy.path={parent_checkpoint}",
        f"--output_dir={output_dir}",
        "--job_name=mode_aware_coft",
        f"--seed={int(seed)}",
        f"--batch_size={config.per_device_batch_size}",
        f"--gradient_accumulation_steps={config.gradient_accumulation_steps}",
        f"--steps={config.optimizer_steps}",
        "--num_workers=4",
        "--eval_freq=0",
        "--log_freq=20",
        f"--save_freq={config.optimizer_steps}",
        "--save_checkpoint=true",
        f"--save_final_params_only={str(config.save_final_params_only).lower()}",
        "--wandb.enable=false",
        "--freeze_pretrained_processor_stats=true",
        f"--tokenizer_path={tokenizer_path}",
        f"--source_sampler_manifest={source_sampler_manifest}",
        f"--policy.gradient_checkpointing={str(config.gradient_checkpointing).lower()}",
        f"--policy.optimizer_lr={config.peak_lr}",
        f"--policy.optimizer_betas=[{config.beta1},{config.beta2}]",
        f"--policy.optimizer_eps={config.eps}",
        f"--policy.optimizer_weight_decay={config.weight_decay}",
        f"--policy.optimizer_grad_clip_norm={config.grad_clip}",
        f"--policy.scheduler_warmup_steps={config.warmup_steps}",
        f"--policy.scheduler_decay_steps={config.decay_steps}",
        f"--policy.scheduler_decay_lr={config.decay_lr}",
        f"--policy.scheduler_auto_scale={str(config.auto_scale_schedule).lower()}",
        "--policy.push_to_hub=false",
    ]


__all__ = [
    "CoFTConfig",
    "SourceAwareSampler",
    "TrainingSmokeConfig",
    "build_lerobot_coft_command",
    "prepare_source_catalog",
    "write_source_sampler_manifest",
    "write_training_manifest",
]
