"""Discover the pinned LIBERO-40 catalog and bind it to source hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
from typing import Mapping

import torch

from .eval_manifest import generate_joint_manifest, write_joint_manifest
from .io_utils import atomic_write_json, sha256_file


FORMAL_SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_10")
LIBERO_PRO_VARIANTS = (
    "use_object",
    "use_swap",
    "use_language",
    "use_environment",
)
BALANCED_PRO_VARIANT = "balanced_pro_v2"
_VARIANT_SUFFIX = {
    "use_object": "object",
    "use_swap": "swap",
    "use_language": "lan",
    "use_environment": "env",
}


def balanced_libero_pro_variant_map(
    task_map: Mapping[str, list[str] | tuple[str, ...]],
) -> dict[str, str]:
    """Assign 40 task cells to four LIBERO-PRO axes, ten cells per axis."""

    result: dict[str, str] = {}
    for suite_index, suite in enumerate(FORMAL_SUITES):
        task_ids = list(task_map.get(suite, ()))
        if len(task_ids) != 10:
            raise ValueError(f"{suite} must expose exactly ten formal tasks")
        quotas = (3, 3, 2, 2) if suite_index % 2 == 0 else (2, 2, 3, 3)
        quota_by_variant = dict(zip(LIBERO_PRO_VARIANTS, quotas))
        remaining = set(task_ids)
        # The pinned environment perturbator maps to living_room_table, so a
        # LIBERO-10 task already in that scene would be a false PRO cell.
        # Reserve this axis first from tasks where the perturbation is real.
        if suite == "libero_10":
            eligible = [
                task_id
                for task_id in task_ids
                if not task_id.startswith("LIVING_ROOM_")
            ]
            ranked_environment = sorted(
                eligible,
                key=lambda task_id: hashlib.sha256(
                    f"libero-pro-balanced-v2\0{suite}\0use_environment\0{task_id}".encode()
                ).digest(),
            )
            selected = ranked_environment[
                : quota_by_variant["use_environment"]
            ]
            if len(selected) != quota_by_variant["use_environment"]:
                raise RuntimeError("LIBERO-10 has too few nontrivial environment tasks")
            for task_id in selected:
                result[f"{suite}::{task_id}"] = "use_environment"
                remaining.remove(task_id)

        ranked = sorted(
            remaining,
            key=lambda task_id: hashlib.sha256(
                f"libero-pro-balanced-v2\0{suite}\0{task_id}".encode()
            ).digest(),
        )
        cursor = 0
        for variant in LIBERO_PRO_VARIANTS:
            if suite == "libero_10" and variant == "use_environment":
                continue
            quota = quota_by_variant[variant]
            for task_id in ranked[cursor : cursor + quota]:
                result[f"{suite}::{task_id}"] = variant
            cursor += quota
    counts = {variant: tuple(result.values()).count(variant) for variant in LIBERO_PRO_VARIANTS}
    if counts != {variant: 10 for variant in LIBERO_PRO_VARIANTS}:
        raise RuntimeError(f"unbalanced LIBERO-PRO assignment: {counts}")
    return result


def runtime_suite_name(suite: str, variant: str) -> str:
    try:
        suffix = _VARIANT_SUFFIX[variant]
    except KeyError as exc:
        raise ValueError(f"unsupported formal LIBERO-PRO variant: {variant!r}") from exc
    return f"{suite}_{suffix}"


def discover_libero40(
    repo_root: Path,
    *,
    default_variant: str = BALANCED_PRO_VARIANT,
    variant_by_task: Mapping[str, str] | None = None,
) -> dict:
    """Resolve 40 balanced LIBERO-PRO task/variant cells and their real resources."""

    repo_root = Path(repo_root).resolve()
    libero_root = repo_root / "third_party/libero_pro/libero/libero"
    task_map_path = libero_root / "libero_suite_task_map.py"
    namespace = runpy.run_path(str(task_map_path))
    task_map = namespace["libero_task_map"]
    if variant_by_task is None and default_variant == BALANCED_PRO_VARIANT:
        requested_variants = balanced_libero_pro_variant_map(task_map)
    else:
        requested_variants = dict(variant_by_task or {})
    entries = []
    for suite in FORMAL_SUITES:
        task_ids = list(task_map.get(suite, ()))
        if len(task_ids) != 10:
            raise ValueError(f"{suite} must expose exactly ten formal tasks")
        for task_index, task_id in enumerate(task_ids):
            selector = f"{suite}::{task_id}"
            fallback = None if default_variant == BALANCED_PRO_VARIANT else default_variant
            variant = requested_variants.pop(selector, fallback)
            if variant not in LIBERO_PRO_VARIANTS:
                raise ValueError(
                    f"formal cell {selector} must use one of {LIBERO_PRO_VARIANTS}, "
                    f"got {variant!r}"
                )
            runtime_suite = runtime_suite_name(suite, str(variant))
            init_path = (
                libero_root / "init_files" / runtime_suite / f"{task_id}.pruned_init"
            )
            bddl_path = libero_root / "bddl_files" / runtime_suite / f"{task_id}.bddl"
            base_bddl_path = libero_root / "bddl_files" / suite / f"{task_id}.bddl"
            if not init_path.is_file() or not bddl_path.is_file():
                raise FileNotFoundError(
                    f"formal task resources missing for {selector}: {init_path}, {bddl_path}"
                )
            if not base_bddl_path.is_file() or sha256_file(base_bddl_path) == sha256_file(
                bddl_path
            ):
                raise ValueError(
                    f"formal LIBERO-PRO cell has no BDDL perturbation: {selector}"
                )
            states = torch.load(init_path, map_location="cpu", weights_only=False)  # nosec B614
            if len(states) != 50:
                raise ValueError(f"{selector} exposes {len(states)} init states, expected 50")
            entries.append(
                {
                    "suite": suite,
                    "runtime_suite": runtime_suite,
                    "benchmark": "LIBERO-PRO",
                    "task_id": task_id,
                    "task_index": task_index,
                    "perturbation_variant": str(variant),
                    "init_state_ids": [str(index) for index in range(50)],
                    "init_state_file": str(init_path.relative_to(repo_root)),
                    "init_state_sha256": sha256_file(init_path),
                    "init_state_shape": list(getattr(states, "shape", (len(states),))),
                    "bddl_file": str(bddl_path.relative_to(repo_root)),
                    "bddl_sha256": sha256_file(bddl_path),
                }
            )
    if requested_variants:
        raise ValueError(
            f"variant map contains unknown task selectors: {sorted(requested_variants)}"
        )
    if len(entries) != 40:
        raise RuntimeError("LIBERO formal catalog must contain exactly 40 tasks")
    return {
        "schema_version": "libero40-curriculum-v1",
        "benchmark": "LIBERO-PRO",
        "default_variant": default_variant,
        "variant_counts": {
            variant: sum(
                item["perturbation_variant"] == variant for item in entries
            )
            for variant in LIBERO_PRO_VARIANTS
        },
        "task_map_file": str(task_map_path.relative_to(repo_root)),
        "task_map_sha256": sha256_file(task_map_path),
        "tasks": entries,
    }


def freeze_protocol(
    repo_root: Path,
    output_root: Path,
    *,
    default_variant: str = BALANCED_PRO_VARIANT,
    variant_by_task: Mapping[str, str] | None = None,
    generator_revision: str,
) -> tuple[dict, dict]:
    """Atomically write the curriculum source manifest and joint split manifest."""

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    curriculum = discover_libero40(
        repo_root,
        default_variant=default_variant,
        variant_by_task=variant_by_task,
    )
    curriculum_canonical = json.dumps(
        curriculum, sort_keys=True, separators=(",", ":")
    )
    curriculum["manifest_sha256"] = hashlib.sha256(
        curriculum_canonical.encode()
    ).hexdigest()
    init_manifest_hash = _field_digest(curriculum["tasks"], "init_state_sha256")
    bddl_hash = _field_digest(curriculum["tasks"], "bddl_sha256")
    joint = generate_joint_manifest(
        curriculum["tasks"],
        dataset_hash=curriculum["manifest_sha256"],
        bddl_hash=bddl_hash,
        init_state_manifest_hash=init_manifest_hash,
        generator_git_sha=generator_revision,
    )
    atomic_write_json(output_root / "curriculum.json", curriculum)
    write_joint_manifest(output_root / "joint_eval_manifest.json", joint)
    # Regenerate in memory to assert determinism before declaring the seal frozen.
    regenerated = generate_joint_manifest(
        curriculum["tasks"],
        dataset_hash=curriculum["manifest_sha256"],
        bddl_hash=bddl_hash,
        init_state_manifest_hash=init_manifest_hash,
        generator_git_sha=generator_revision,
    )
    if json.dumps(joint, sort_keys=True) != json.dumps(regenerated, sort_keys=True):
        raise RuntimeError("joint manifest regeneration is not byte-deterministic")
    return curriculum, joint


def prepare_libero_pro_resources() -> dict:
    """Materialize every single-axis LIBERO-PRO suite before freezing manifests."""

    from core.env_adapters.libero_adapter import _apply_perturbations

    prepared = []
    for suite in FORMAL_SUITES:
        for variant in LIBERO_PRO_VARIANTS:
            requested = runtime_suite_name(suite, variant)
            actual, read_language = _apply_perturbations(requested)
            if actual != requested:
                raise RuntimeError(
                    f"LIBERO-PRO resource preparation changed {requested} to {actual}"
                )
            prepared.append(
                {
                    "suite": suite,
                    "variant": variant,
                    "runtime_suite": actual,
                    "read_language_from_bddl": bool(read_language),
                }
            )
    return {
        "schema_version": "libero-pro-resource-preparation-v1",
        "prepared": prepared,
    }


def _field_digest(entries: list[dict], field: str) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda value: (value["suite"], value["task_id"])):
        digest.update(entry["suite"].encode())
        digest.update(b"\0")
        digest.update(entry["task_id"].encode())
        digest.update(b"\0")
        digest.update(entry[field].encode())
        digest.update(b"\n")
    return digest.hexdigest()


__all__ = [
    "BALANCED_PRO_VARIANT",
    "FORMAL_SUITES",
    "LIBERO_PRO_VARIANTS",
    "balanced_libero_pro_variant_map",
    "discover_libero40",
    "freeze_protocol",
    "prepare_libero_pro_resources",
    "runtime_suite_name",
]
