"""Full task-vector extraction and fp32 checkpoint composition."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Iterator, Mapping, Sequence

import torch
from safetensors import safe_open
from safetensors.torch import save_file

from .io_utils import atomic_write_json, sha256_file


GROUPS = ("vision", "language", "action")


def parameter_group(key: str) -> str:
    if ".paligemma.model.vision_tower." in key or ".paligemma.model.multi_modal_projector." in key:
        return "vision"
    if ".paligemma.model.language_model." in key or key.endswith(
        ".paligemma.lm_head.weight"
    ):
        return "language"
    return "action"


class CheckpointView:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.key_to_shard = _discover(self.path)
        self._stack: ExitStack | None = None
        self._handles: dict[Path, object] = {}

    def __enter__(self) -> "CheckpointView":
        self._stack = ExitStack()
        for shard in sorted(set(self.key_to_shard.values())):
            self._handles[shard] = self._stack.enter_context(
                safe_open(str(shard), framework="pt", device="cpu")
            )
        return self

    def __exit__(self, *args: object) -> None:
        assert self._stack is not None
        self._stack.close()
        self._handles.clear()
        self._stack = None

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.key_to_shard))

    def tensor(self, key: str) -> torch.Tensor:
        if self._stack is None:
            raise RuntimeError("CheckpointView must be used as a context manager")
        shard = self.key_to_shard[key]
        return self._handles[shard].get_tensor(key)  # type: ignore[union-attr]


class ShardedCheckpointWriter:
    def __init__(self, root: Path, *, max_shard_bytes: int = 1_800_000_000) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.max_shard_bytes = int(max_shard_bytes)
        self.buffer: dict[str, torch.Tensor] = {}
        self.buffer_bytes = 0
        self.shards: list[tuple[Path, list[str], int]] = []

    def add(self, key: str, tensor: torch.Tensor) -> None:
        tensor = tensor.detach().contiguous().cpu()
        size = tensor.numel() * tensor.element_size()
        if self.buffer and self.buffer_bytes + size > self.max_shard_bytes:
            self._flush()
        self.buffer[key] = tensor
        self.buffer_bytes += size

    def finish(self) -> dict:
        self._flush()
        total = len(self.shards)
        weight_map: dict[str, str] = {}
        shard_meta = []
        for index, (temporary, keys, size) in enumerate(self.shards, start=1):
            final = self.root / f"model-{index:05d}-of-{total:05d}.safetensors"
            os.replace(temporary, final)
            for key in keys:
                weight_map[key] = final.name
            shard_meta.append(
                {
                    "file": final.name,
                    "size": size,
                    "sha256": sha256_file(final),
                }
            )
        index_value = {
            "metadata": {"total_size": sum(item[2] for item in self.shards)},
            "weight_map": weight_map,
        }
        atomic_write_json(self.root / "model.safetensors.index.json", index_value)
        digest = checkpoint_digest(self.root)
        return {
            "tensor_count": len(weight_map),
            "total_size": index_value["metadata"]["total_size"],
            "shards": shard_meta,
            "checkpoint_digest": digest,
        }

    def _flush(self) -> None:
        if not self.buffer:
            return
        index = len(self.shards) + 1
        path = self.root / f".shard-{index:05d}.tmp"
        save_file(self.buffer, str(path))
        keys = sorted(self.buffer)
        size = sum(tensor.numel() * tensor.element_size() for tensor in self.buffer.values())
        self.shards.append((path, keys, size))
        self.buffer = {}
        self.buffer_bytes = 0


def extract_full_delta(
    parent_checkpoint: Path,
    theta_ft_checkpoint: Path,
    output_dir: Path,
    *,
    parent_policy_id: str,
    max_shard_bytes: int = 1_800_000_000,
) -> dict:
    output_dir = Path(output_dir)
    staging = output_dir.parent / f".{output_dir.name}.{os.getpid()}.staging"
    with CheckpointView(parent_checkpoint) as parent, CheckpointView(theta_ft_checkpoint) as ft:
        if parent.keys != ft.keys:
            missing = sorted(set(parent.keys) - set(ft.keys))
            extra = sorted(set(ft.keys) - set(parent.keys))
            raise ValueError(f"checkpoint key mismatch; missing={missing[:5]}, extra={extra[:5]}")
        writer = ShardedCheckpointWriter(staging, max_shard_bytes=max_shard_bytes)
        counts = {group: 0 for group in GROUPS}
        non_floating: list[str] = []
        reconstruction_max_error = 0.0
        for key in parent.keys:
            before = parent.tensor(key)
            after = ft.tensor(key)
            if before.shape != after.shape or before.dtype != after.dtype:
                raise ValueError(f"shape/dtype mismatch for {key}")
            if not before.is_floating_point():
                if not torch.equal(before, after):
                    raise ValueError(f"non-floating state changed during SFT: {key}")
                non_floating.append(key)
                continue
            delta = (after.float() - before.float()).to(before.dtype)
            reconstructed = (before.float() + delta.float()).to(before.dtype)
            error = float((reconstructed.float() - after.float()).abs().max())
            reconstruction_max_error = max(reconstruction_max_error, error)
            writer.add(key, delta)
            counts[parameter_group(key)] += 1
        write_meta = writer.finish()
    metadata = {
        "schema_version": "full-task-vector-v1",
        "parent_policy_id": parent_policy_id,
        "parent_checkpoint_digest": checkpoint_digest(parent_checkpoint),
        "theta_ft_checkpoint_digest": checkpoint_digest(theta_ft_checkpoint),
        "groups": counts,
        "non_floating_unchanged": non_floating,
        "reconstruction_max_error": reconstruction_max_error,
        **write_meta,
    }
    atomic_write_json(staging / "meta.json", metadata)
    os.replace(staging, output_dir)
    return metadata


def compose_policy(
    theta0_checkpoint: Path,
    deltas: Sequence[tuple[Path, Mapping[str, float]]],
    output_dir: Path,
    *,
    max_shard_bytes: int = 1_800_000_000,
    allow_uniform_alpha: bool = False,
) -> dict:
    output_dir = Path(output_dir)
    staging = output_dir.parent / f".{output_dir.name}.{os.getpid()}.staging"
    alpha_maps = []
    with ExitStack() as stack:
        base = stack.enter_context(CheckpointView(theta0_checkpoint))
        delta_views = [
            (
                stack.enter_context(CheckpointView(path)),
                _validate_alpha_map(
                    alpha, allow_uniform_alpha=allow_uniform_alpha
                ),
            )
            for path, alpha in deltas
        ]
        expected_float_keys = {
            key for key in base.keys if base.tensor(key).is_floating_point()
        }
        for view, _ in delta_views:
            if set(view.keys) != expected_float_keys:
                raise ValueError("full delta does not cover every floating base tensor")
        writer = ShardedCheckpointWriter(staging, max_shard_bytes=max_shard_bytes)
        group_counts = {group: 0 for group in GROUPS}
        for key in base.keys:
            base_tensor = base.tensor(key)
            if not base_tensor.is_floating_point():
                writer.add(key, base_tensor)
                continue
            group = parameter_group(key)
            accumulated = base_tensor.float()
            for view, alpha in delta_views:
                accumulated = accumulated + float(alpha[group]) * view.tensor(key).float()
            writer.add(key, accumulated.to(base_tensor.dtype))
            group_counts[group] += 1
        write_meta = writer.finish()
        _copy_support_files(Path(theta0_checkpoint), staging)
        alpha_maps = [dict(alpha) for _, alpha in delta_views]
    metadata = {
        "schema_version": "composed-policy-v1",
        "alpha_contract": (
            "v2-language-only-or-retain-uniform"
            if allow_uniform_alpha
            else "v2-language-only"
        ),
        "theta0_checkpoint_digest": checkpoint_digest(theta0_checkpoint),
        "delta_checkpoint_digests": [checkpoint_digest(path) for path, _ in deltas],
        "alpha_maps": alpha_maps,
        "groups": group_counts,
        **write_meta,
    }
    atomic_write_json(staging / "meta.json", metadata)
    os.replace(staging, output_dir)
    return metadata


def verify_full_delta_reconstruction(
    parent_checkpoint: Path,
    delta_checkpoint: Path,
    theta_ft_checkpoint: Path,
) -> dict:
    """Verify parent + full delta reconstructs every SFT tensor within one quantization."""

    maximum_error = 0.0
    maximum_tolerance = 0.0
    checked = 0
    with (
        CheckpointView(parent_checkpoint) as parent,
        CheckpointView(delta_checkpoint) as delta,
        CheckpointView(theta_ft_checkpoint) as theta_ft,
    ):
        if parent.keys != theta_ft.keys:
            raise ValueError("parent/theta_ft key sets differ during reconstruction verify")
        floating_keys = tuple(
            key for key in parent.keys if parent.tensor(key).is_floating_point()
        )
        if delta.keys != floating_keys:
            raise ValueError("full delta does not cover exactly every floating tensor")
        for key in parent.keys:
            before = parent.tensor(key)
            expected = theta_ft.tensor(key)
            if not before.is_floating_point():
                if not torch.equal(before, expected):
                    raise ValueError(f"non-floating state changed: {key}")
                continue
            reconstructed = (before.float() + delta.tensor(key).float()).to(
                expected.dtype
            )
            error = float(
                (reconstructed.float() - expected.float()).abs().max().item()
            )
            scale = max(1.0, float(expected.float().abs().max().item()))
            tolerance = float(torch.finfo(expected.dtype).eps) * scale
            if error > tolerance + 1e-12:
                raise ValueError(
                    f"delta reconstruction exceeds one dtype quantization for {key}: "
                    f"error={error}, tolerance={tolerance}"
                )
            maximum_error = max(maximum_error, error)
            maximum_tolerance = max(maximum_tolerance, tolerance)
            checked += 1
    result = {
        "schema_version": "full-delta-reconstruction-v1",
        "parent_checkpoint_digest": checkpoint_digest(parent_checkpoint),
        "delta_checkpoint_digest": checkpoint_digest(delta_checkpoint),
        "theta_ft_checkpoint_digest": checkpoint_digest(theta_ft_checkpoint),
        "floating_tensors_checked": checked,
        "maximum_absolute_error": maximum_error,
        "maximum_allowed_quantization": maximum_tolerance,
        "passed": True,
    }
    atomic_write_json(Path(delta_checkpoint) / "reconstruction.json", result)
    return result


def delete_verified_theta_ft(
    theta_ft_checkpoint: Path,
    *,
    parent_checkpoint: Path,
    delta_checkpoint: Path,
) -> dict:
    """Delete only an SFT checkpoint that has a current passing reconstruction proof."""

    theta_ft = Path(theta_ft_checkpoint).resolve()
    parent = Path(parent_checkpoint).resolve()
    delta = Path(delta_checkpoint).resolve()
    if theta_ft == parent or theta_ft == delta:
        raise ValueError("theta_ft cleanup target overlaps a retained artifact")
    if theta_ft == Path("/") or len(theta_ft.parts) < 4:
        raise ValueError(f"refusing broad theta_ft cleanup target: {theta_ft}")
    proof_path = delta / "reconstruction.json"
    if not proof_path.is_file():
        raise FileNotFoundError("delta has no reconstruction proof")
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    current_digest = checkpoint_digest(theta_ft)
    if not proof.get("passed") or proof.get("theta_ft_checkpoint_digest") != current_digest:
        raise ValueError("theta_ft digest does not match the passing reconstruction proof")
    if proof.get("parent_checkpoint_digest") != checkpoint_digest(parent):
        raise ValueError("parent digest changed after reconstruction proof")
    if proof.get("delta_checkpoint_digest") != checkpoint_digest(delta):
        raise ValueError("delta digest changed after reconstruction proof")
    deletion = {
        "schema_version": "theta-ft-cleanup-v1",
        "theta_ft_path": str(theta_ft),
        "theta_ft_checkpoint_digest": current_digest,
        "parent_checkpoint_digest": proof["parent_checkpoint_digest"],
        "delta_checkpoint_digest": proof["delta_checkpoint_digest"],
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "recoverable_from_parent_and_delta": True,
    }
    atomic_write_json(delta / "theta_ft_cleanup.json", deletion)
    if theta_ft.is_dir():
        shutil.rmtree(theta_ft)
    else:
        theta_ft.unlink()
    return deletion


def checkpoint_digest(path: Path) -> str:
    path = Path(path)
    mapping = _discover(path)
    shards = sorted(set(mapping.values()))
    digest = hashlib.sha256()
    for shard in shards:
        digest.update(shard.name.encode())
        digest.update(sha256_file(shard).encode())
    return digest.hexdigest()


def partition_counts(path: Path) -> dict[str, int]:
    mapping = _discover(Path(path))
    counts = {group: 0 for group in GROUPS}
    for key in mapping:
        counts[parameter_group(key)] += 1
    if sum(counts.values()) != len(mapping):
        raise RuntimeError("parameter partition is incomplete")
    return counts


def _validate_alpha_map(
    value: Mapping[str, float], *, allow_uniform_alpha: bool = False
) -> dict[str, float]:
    if set(value) != set(GROUPS):
        raise ValueError(f"alpha map must contain exactly {GROUPS}")
    alpha = {group: float(value[group]) for group in GROUPS}
    if any(not 0.0 <= item <= 1.0 for item in alpha.values()):
        raise ValueError("alpha values must be in [0, 1]")
    language_only = alpha["vision"] == 1.0 and alpha["action"] == 1.0
    retain_uniform = (
        allow_uniform_alpha
        and alpha["vision"] == alpha["language"] == alpha["action"]
    )
    if not (language_only or retain_uniform):
        raise ValueError(
            "alpha map must satisfy v2 language-only composition or an explicitly "
            "enabled RETAIN uniform interpolation"
        )
    return alpha


def _discover(path: Path) -> dict[str, Path]:
    if path.is_file():
        if path.suffix != ".safetensors":
            raise ValueError(f"not a safetensors checkpoint: {path}")
        with safe_open(str(path), framework="pt", device="cpu") as handle:
            return {key: path for key in handle.keys()}
    index_path = path / "model.safetensors.index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        mapping = {key: path / shard for key, shard in index["weight_map"].items()}
        if any(not shard.exists() for shard in mapping.values()):
            raise FileNotFoundError("checkpoint index references a missing shard")
        return mapping
    single_model = path / "model.safetensors"
    if single_model.exists():
        # Hugging Face policy directories also contain processor state files
        # with overlapping keys such as `action.count`.  They are support
        # artifacts, not policy parameters.
        with safe_open(str(single_model), framework="pt", device="cpu") as handle:
            return {key: single_model for key in handle.keys()}
    shards = sorted(path.glob("*.safetensors"))
    if not shards:
        raise FileNotFoundError(f"no safetensors found under {path}")
    mapping: dict[str, Path] = {}
    for shard in shards:
        with safe_open(str(shard), framework="pt", device="cpu") as handle:
            for key in handle.keys():
                if key in mapping:
                    raise ValueError(f"duplicate checkpoint key {key}")
                mapping[key] = shard
    return mapping


def _copy_support_files(source: Path, target: Path) -> None:
    if not source.is_dir():
        return
    model_files = {path.resolve() for path in set(_discover(source).values())}
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() in model_files or path.name in {
            "model.safetensors.index.json",
            "meta.json",
        }:
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


__all__ = [
    "GROUPS",
    "CheckpointView",
    "checkpoint_digest",
    "compose_policy",
    "delete_verified_theta_ft",
    "extract_full_delta",
    "parameter_group",
    "partition_counts",
    "verify_full_delta_reconstruction",
]
