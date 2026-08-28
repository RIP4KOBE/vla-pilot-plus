"""Deterministic joint policy/verifier/demo split manifest and final-seal guard."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .io_utils import atomic_write_json


SPLIT_SEED = 20260825


def generate_joint_manifest(
    tasks: Sequence[Mapping[str, Any]],
    *,
    dataset_hash: str,
    bddl_hash: str,
    init_state_manifest_hash: str,
    generator_git_sha: str,
) -> dict[str, Any]:
    if len(tasks) != 40:
        raise ValueError("formal manifest requires exactly 40 task/variant entries")
    keys = [_task_key(task) for task in tasks]
    if len(set(keys)) != len(keys):
        raise ValueError("task keys must be unique")
    bonus_order = sorted(keys, key=lambda key: _hash(f"bonus\0{key}"))
    alpha_bonus = set(bonus_order[:20])
    regression_bonus = set(bonus_order[:10])
    final_bonus = set(bonus_order[20:40])

    entries = []
    for task, key in sorted(zip(tasks, keys), key=lambda item: item[1]):
        states = [str(value) for value in task["init_state_ids"]]
        if len(states) != 50 or len(set(states)) != 50:
            raise ValueError(f"{key} must expose exactly 50 unique init states")
        states.sort(key=lambda state: _hash(f"{SPLIT_SEED}\0{key}\0{state}"))
        counts = {
            "policy_alpha_selection": 2 + int(key in alpha_bonus),
            "policy_regression": 6 + int(key in regression_bonus),
            "policy_final_sealed": 12 + int(key in final_bonus),
            "verifier_audit_train": 12,
            "verifier_calibration": 4,
            "verifier_test": 4,
            "fixed_development_probe": 2,
        }
        splits: dict[str, list[str]] = {}
        cursor = 0
        for name, count in counts.items():
            splits[name] = states[cursor : cursor + count]
            cursor += count
        splits["demo_online_pool"] = states[cursor:]
        if len(splits["demo_online_pool"]) < 5:
            raise RuntimeError(f"{key} leaves fewer than five demo/online states")
        entries.append(
            {
                "suite": str(task["suite"]),
                "runtime_suite": str(
                    task.get("runtime_suite")
                    or _runtime_suite_name(
                        str(task["suite"]), str(task["perturbation_variant"])
                    )
                ),
                "benchmark": str(
                    task.get("benchmark")
                    or (
                        "LIBERO"
                        if str(task["perturbation_variant"]) == "base"
                        else "LIBERO-PRO"
                    )
                ),
                "task_id": str(task["task_id"]),
                "task_index": int(task.get("task_index", -1)),
                "perturbation_variant": str(task["perturbation_variant"]),
                "task_key": key,
                "splits": splits,
            }
        )
    manifest = {
        "schema_version": "joint-eval-manifest-v1",
        "split_seed": SPLIT_SEED,
        "dataset_hash": dataset_hash,
        "bddl_hash": bddl_hash,
        "init_state_manifest_hash": init_state_manifest_hash,
        "generator_git_sha": generator_git_sha,
        "tasks": entries,
    }
    validate_joint_manifest(manifest)
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["manifest_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return manifest


def validate_joint_manifest(manifest: Mapping[str, Any]) -> None:
    tasks = manifest["tasks"]
    indices_by_suite: dict[str, set[int]] = {}
    totals = {
        "policy_alpha_selection": 0,
        "policy_regression": 0,
        "policy_final_sealed": 0,
    }
    for task in tasks:
        task_index = int(task.get("task_index", -1))
        if not 0 <= task_index < 10:
            raise ValueError(f"invalid task_index for {task['task_key']}: {task_index}")
        suite_indices = indices_by_suite.setdefault(str(task["suite"]), set())
        if task_index in suite_indices:
            raise ValueError(f"duplicate task_index {task_index} in {task['suite']}")
        suite_indices.add(task_index)
        seen: set[str] = set()
        for split, states in task["splits"].items():
            overlap = seen.intersection(states)
            if overlap:
                raise ValueError(f"split overlap for {task['task_key']}: {sorted(overlap)}")
            seen.update(states)
            if split in totals:
                totals[split] += len(states)
        if len(seen) != 50:
            raise ValueError(f"manifest does not account for 50 states: {task['task_key']}")
        if len(task["splits"]["demo_online_pool"]) < 5:
            raise ValueError("demo/online pool too small")
    if totals != {
        "policy_alpha_selection": 100,
        "policy_regression": 250,
        "policy_final_sealed": 500,
    }:
        raise ValueError(f"formal policy split totals are wrong: {totals}")
    if any(indices != set(range(10)) for indices in indices_by_suite.values()):
        raise ValueError("each formal suite must contain task_index 0..9 exactly once")


def validate_libero_pro_manifest(manifest: Mapping[str, Any]) -> None:
    """Require the formal 40-cell protocol to be entirely LIBERO-PRO."""

    validate_joint_manifest(manifest)
    expected_variants = {
        "use_object": 10,
        "use_swap": 10,
        "use_language": 10,
        "use_environment": 10,
    }
    counts = {
        variant: sum(
            str(task.get("perturbation_variant")) == variant
            for task in manifest["tasks"]
        )
        for variant in expected_variants
    }
    if counts != expected_variants:
        raise ValueError(f"formal LIBERO-PRO variant counts are invalid: {counts}")
    for task in manifest["tasks"]:
        if str(task.get("benchmark")) != "LIBERO-PRO":
            raise ValueError(f"non-LIBERO-PRO formal task: {task.get('task_key')}")
        if str(task.get("runtime_suite")) == str(task.get("suite")):
            raise ValueError(f"unperturbed formal runtime suite: {task.get('task_key')}")


def write_joint_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    validate_libero_pro_manifest(manifest)
    atomic_write_json(path, dict(manifest))


def fixed_development_probe_context(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Select one deterministic, non-sealed LIBERO-PRO canary context."""

    validate_libero_pro_manifest(manifest)
    tasks = sorted(manifest["tasks"], key=lambda item: str(item["task_key"]))
    for task in tasks:
        states = list(task["splits"].get("fixed_development_probe", ()))
        if not states:
            continue
        suite = str(task["suite"])
        runtime_suite = str(task.get("runtime_suite", ""))
        if str(task.get("benchmark")) != "LIBERO-PRO" or runtime_suite == suite:
            continue
        return {
            "benchmark": "LIBERO-PRO",
            "manifest_sha256": str(manifest.get("manifest_sha256", "")),
            "suite": suite,
            "runtime_suite": runtime_suite,
            "task_id": str(task["task_id"]),
            "task_index": int(task["task_index"]),
            "perturbation_variant": str(task["perturbation_variant"]),
            "init_state_id": str(states[0]),
            "split": "fixed_development_probe",
        }
    raise ValueError("manifest has no non-sealed LIBERO-PRO development-probe context")


class FinalSealGuard:
    def __init__(self, manifest: Mapping[str, Any], audit_log: Path) -> None:
        self.manifest = manifest
        self.audit_log = Path(audit_log)

    @property
    def completion_log(self) -> Path:
        return self.audit_log.with_name(self.audit_log.stem + ".completion.json")

    def open(
        self,
        *,
        purpose: str,
        authorization_token: str,
        subjects: Sequence[str] = (),
    ) -> list[dict[str, str | int]]:
        expected = os.environ.get("VLS_FINAL_SEAL_TOKEN")
        if not expected or authorization_token != expected:
            raise PermissionError("final_sealed requires the explicit one-time seal token")
        if self.audit_log.exists():
            raise RuntimeError("final_sealed has already been opened")
        if self.completion_log.exists():
            raise RuntimeError("final_sealed completion exists without its open record")
        contexts = []
        for task in self.manifest["tasks"]:
            for state in task["splits"]["policy_final_sealed"]:
                contexts.append(
                    {
                        "benchmark": task.get("benchmark"),
                        "suite": task["suite"],
                        "runtime_suite": task.get("runtime_suite"),
                        "task_id": task["task_id"],
                        "task_index": int(task["task_index"]),
                        "perturbation_variant": task["perturbation_variant"],
                        "init_state_id": state,
                    }
                )
        contexts.sort(
            key=lambda value: (
                str(value["suite"]),
                str(value["task_id"]),
                str(value["perturbation_variant"]),
                str(value["init_state_id"]),
            )
        )
        context_sha256 = hashlib.sha256(
            json.dumps(contexts, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        atomic_write_json(
            self.audit_log,
            {
                "schema_version": "final-seal-open-v2",
                "manifest_sha256": self.manifest["manifest_sha256"],
                "purpose": purpose,
                "subjects": sorted(map(str, subjects)),
                "context_count": len(contexts),
                "contexts_sha256": context_sha256,
                "contexts": contexts,
            },
        )
        return contexts

    def resume(
        self, *, purpose: str, subjects: Sequence[str] = ()
    ) -> list[dict[str, str | int]]:
        """Resume the same one-time job after a crash without reopening the seal."""

        if self.completion_log.exists():
            raise RuntimeError("final_sealed job is already complete")
        if not self.audit_log.is_file():
            raise FileNotFoundError("final_sealed has not been opened")
        value = json.loads(self.audit_log.read_text(encoding="utf-8"))
        if value.get("manifest_sha256") != self.manifest.get("manifest_sha256"):
            raise ValueError("final seal manifest changed after opening")
        if value.get("purpose") != purpose:
            raise ValueError("final seal purpose changed while resuming")
        if value.get("subjects", []) != sorted(map(str, subjects)):
            raise ValueError("final seal subject bank changed while resuming")
        contexts = value.get("contexts")
        if not isinstance(contexts, list) or len(contexts) != 500:
            raise ValueError("final seal open record has an invalid context bank")
        digest = hashlib.sha256(
            json.dumps(contexts, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if digest != value.get("contexts_sha256"):
            raise ValueError("final seal context bank changed after opening")
        return contexts

    def complete(
        self,
        *,
        purpose: str,
        subjects: Sequence[str],
        result_path: Path,
        result_sha256: str,
    ) -> dict[str, Any]:
        self.resume(purpose=purpose, subjects=subjects)
        if len(result_sha256) != 64 or not Path(result_path).is_file():
            raise ValueError("final seal completion requires a checksummed result")
        value = {
            "schema_version": "final-seal-completion-v1",
            "manifest_sha256": self.manifest["manifest_sha256"],
            "purpose": purpose,
            "subjects": sorted(map(str, subjects)),
            "result_path": str(Path(result_path).resolve()),
            "result_sha256": result_sha256,
        }
        atomic_write_json(self.completion_log, value)
        return value


def _task_key(task: Mapping[str, Any]) -> str:
    return "::".join(
        [
            str(task["suite"]),
            str(task["task_id"]),
            str(task["perturbation_variant"]),
        ]
    )


def _runtime_suite_name(suite: str, variant: str) -> str:
    if variant == "base":
        return suite
    suffix = {
        "use_object": "object",
        "use_swap": "swap",
        "use_language": "lan",
        "use_task": "task",
        "use_environment": "env",
    }.get(variant)
    if suffix is None:
        return f"{suite}::{variant}"
    return f"{suite}_{suffix}"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "FinalSealGuard",
    "SPLIT_SEED",
    "fixed_development_probe_context",
    "generate_joint_manifest",
    "validate_libero_pro_manifest",
    "validate_joint_manifest",
    "write_joint_manifest",
]
