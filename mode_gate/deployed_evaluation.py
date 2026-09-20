"""Fresh-load development evaluation for an installed deployment.

Promotion metrics belong to the candidate checkpoint that won model
selection.  They must never be copied into a deployment report.  This module
builds a separate, deterministic 50-episode bank from the frozen regression
shard, verifies the immutable Registry copy, and evaluates that installed
copy under the distinct ``deployed_dev`` metric role.

The bank deliberately reuses regression *states* but derives new environment
and policy seeds.  It therefore checks serialization/fresh-load equivalence
without opening the final seal or manufacturing another tuning split.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .checkpoint_math import CheckpointView, checkpoint_digest
from .io_utils import atomic_write_json
from .policy_evaluator import EvaluationContext, RawPolicyEvaluator
from .registry import PolicyRegistry


DEPLOYED_DEV_CONTEXTS = 50


def deployed_dev_contexts(
    manifest: Mapping[str, Any],
) -> tuple[EvaluationContext, ...]:
    """Return the frozen 50-context post-deployment canary bank.

    Every one of the 40 tasks contributes one regression state.  Ten tasks,
    selected only by stable hash, contribute one additional state.  This
    prevents a small set of tasks from dominating while remaining exactly
    reproducible across worker counts and policy versions.
    """

    if manifest.get("schema_version") != "joint-eval-manifest-v1":
        raise ValueError("deployed_dev requires the frozen joint eval manifest")
    manifest_hash = str(manifest.get("manifest_sha256") or "")
    if len(manifest_hash) != 64:
        raise ValueError("joint manifest is missing its SHA256")
    tasks = sorted(manifest.get("tasks", ()), key=lambda value: value["task_key"])
    if len(tasks) != 40:
        raise ValueError("deployed_dev requires the frozen 40-task curriculum")

    selected: list[tuple[Mapping[str, Any], str]] = []
    remaining: list[tuple[bytes, Mapping[str, Any], str]] = []
    for task in tasks:
        states = tuple(map(str, task["splits"]["policy_regression"]))
        if len(states) < 2:
            raise ValueError("every task needs at least two regression states")
        ranked = sorted(
            states,
            key=lambda state: _rank(
                manifest_hash, str(task["task_key"]), state
            ),
        )
        selected.append((task, ranked[0]))
        remaining.extend(
            (_rank(manifest_hash, str(task["task_key"]), state), task, state)
            for state in ranked[1:]
        )
    for _, task, state in sorted(
        remaining, key=lambda value: (value[0], value[1]["task_key"], value[2])
    )[: DEPLOYED_DEV_CONTEXTS - len(selected)]:
        selected.append((task, state))

    contexts = []
    for task, state in sorted(
        selected, key=lambda value: (value[0]["task_key"], value[1])
    ):
        material = (
            f"deployed-dev-seeds-v1\0{manifest_hash}\0{task['task_key']}\0{state}"
        )
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        contexts.append(
            EvaluationContext(
                suite=str(task["suite"]),
                task_id=str(task["task_id"]),
                task_index=int(task["task_index"]),
                perturbation_variant=str(task["perturbation_variant"]),
                init_state_id=state,
                env_seed=int.from_bytes(digest[:4], "big"),
                policy_seed=int.from_bytes(digest[4:12], "big") % (2**63 - 1),
            )
        )
    if len(contexts) != DEPLOYED_DEV_CONTEXTS:
        raise RuntimeError("deployed_dev bank did not contain exactly 50 contexts")
    if len({context.task_key for context in contexts}) != 40:
        raise RuntimeError("deployed_dev bank lost 40-task coverage")
    return tuple(contexts)


def checkpoint_identity_canary(
    checkpoint: Path,
    *,
    expected_digest: str | None = None,
) -> dict[str, Any]:
    """Validate the exact installed tensor payload before launching episodes."""

    checkpoint = Path(checkpoint)
    actual_digest = checkpoint_digest(checkpoint)
    if expected_digest is not None and actual_digest != expected_digest:
        raise ValueError("installed policy digest differs from the staged winner")
    checked = []
    finite = True
    with CheckpointView(checkpoint) as view:
        keys = view.keys
        if not keys:
            raise ValueError("installed policy contains no tensors")
        indices = sorted({0, len(keys) // 3, 2 * len(keys) // 3, len(keys) - 1})
        for index in indices:
            tensor = view.tensor(keys[index])
            tensor_finite = bool(
                not tensor.is_floating_point() or tensor.isfinite().all().item()
            )
            finite = finite and tensor_finite
            checked.append(
                {
                    "key": keys[index],
                    "shape": list(tensor.shape),
                    "dtype": str(tensor.dtype),
                    "finite": tensor_finite,
                }
            )
    if not finite:
        raise ValueError("installed policy failed finite-tensor canary")
    return {
        "passed": True,
        "checkpoint_digest": actual_digest,
        "tensor_count": len(keys),
        "sampled_tensors": checked,
    }


class DeployedDevelopmentCoordinator:
    """Evaluate only the currently active, immutable Registry policy copy."""

    def __init__(
        self,
        *,
        registry: PolicyRegistry,
        manifest: Mapping[str, Any],
        evaluator: RawPolicyEvaluator,
        output_path: Path,
    ) -> None:
        self.registry = registry
        self.manifest = dict(manifest)
        self.evaluator = evaluator
        self.output_path = Path(output_path)

    def run(
        self,
        *,
        expected_revision: int | None = None,
        expected_checkpoint_digest: str | None = None,
    ) -> dict[str, Any]:
        active = self.registry.active()
        if active is None:
            raise RuntimeError("deployed_dev requires an active deployment")
        if expected_revision is not None and active.deployment_revision != int(
            expected_revision
        ):
            raise RuntimeError("active revision changed before deployed_dev")
        if active.manifest_hash != self.manifest.get("manifest_sha256"):
            raise ValueError("active deployment and eval manifest hashes differ")
        checkpoint = self.registry.root / "policies" / active.policy_id
        if not checkpoint.is_dir():
            raise FileNotFoundError(checkpoint)
        canary = checkpoint_identity_canary(
            checkpoint, expected_digest=expected_checkpoint_digest
        )
        contexts = deployed_dev_contexts(self.manifest)
        summary = self.evaluator.evaluate(
            policy_id=active.policy_id,
            checkpoint_path=checkpoint,
            checkpoint_digest=canary["checkpoint_digest"],
            contexts=contexts,
            metric_role="deployed_dev",
            require_raw_profile=True,
            evaluation_profile={
                "schema_version": "deployed-dev-profile-v1",
                "deployment_revision": active.deployment_revision,
                "controller_disabled_for_policy_identity_check": True,
                "fresh_seeds": True,
            },
        )
        result = {
            "schema_version": "deployed-dev-report-v1",
            "metric_role": "deployed_dev",
            "manifest_sha256": self.manifest["manifest_sha256"],
            "deployment": asdict(active),
            "installed_checkpoint": str(checkpoint.resolve()),
            "identity_canary": canary,
            "context_count": len(contexts),
            "context_bank_sha256": hashlib.sha256(
                json.dumps(
                    [asdict(context) for context in contexts],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "summary": asdict(summary),
        }
        atomic_write_json(self.output_path, result)
        return result


def _rank(manifest_hash: str, task_key: str, state: str) -> bytes:
    return hashlib.sha256(
        f"deployed-dev-bank-v1\0{manifest_hash}\0{task_key}\0{state}".encode(
            "utf-8"
        )
    ).digest()


__all__ = [
    "DEPLOYED_DEV_CONTEXTS",
    "DeployedDevelopmentCoordinator",
    "checkpoint_identity_canary",
    "deployed_dev_contexts",
]
