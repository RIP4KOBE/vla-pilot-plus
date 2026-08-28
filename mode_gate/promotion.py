"""Raw policy gating, trigger recheck, and atomic deployment orchestration.

This module deliberately keeps policy promotion separate from rollout.  Every
episode is written to the resumable raw ledger before a candidate can be
staged, and deployment is a single registry CAS performed only after the raw
gate and trigger-task recheck have both passed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .checkpoint_math import checkpoint_digest
from .evaluation import (
    PolicyScore,
    paired_hierarchical_bootstrap,
    raw_promotion_decision,
    select_alpha_top2,
    trigger_score,
)
from .incidents import CapabilitySignatureRecord, IncidentMemory
from .io_utils import atomic_write_json
from .policy_evaluator import (
    EvaluationContext,
    PolicyEvaluationSummary,
    RawPolicyEvaluator,
    contexts_from_manifest,
)
from .registry import ActiveDeployment, PolicyRegistry


FROZEN_ALPHA_L = (0.2, 0.4, 0.6, 0.8)


@dataclass(frozen=True)
class PolicyCandidate:
    policy_id: str
    checkpoint_path: str
    checkpoint_digest: str
    alpha_l: float

    def __post_init__(self) -> None:
        if not self.policy_id or not self.checkpoint_digest:
            raise ValueError("policy candidate IDs and digests must be non-empty")
        if not 0.0 <= float(self.alpha_l) <= 1.0:
            raise ValueError("alpha_l must be in [0, 1]")


@dataclass(frozen=True)
class TriggerRecheckResult:
    candidate_id: str
    parent_id: str
    seen_successes: int
    seen_total: int
    unseen_successes: int
    unseen_total: int
    parent_seen_successes: int
    parent_seen_total: int
    parent_unseen_successes: int
    parent_unseen_total: int

    @property
    def candidate_score(self) -> float:
        return trigger_score(
            self.seen_successes,
            self.seen_total,
            self.unseen_successes,
            self.unseen_total,
        )

    @property
    def parent_score(self) -> float:
        return trigger_score(
            self.parent_seen_successes,
            self.parent_seen_total,
            self.parent_unseen_successes,
            self.parent_unseen_total,
        )

    @property
    def passed(self) -> bool:
        return self.candidate_score > self.parent_score

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "candidate_score": self.candidate_score,
            "parent_score": self.parent_score,
            "passed": self.passed,
        }


class TriggerEvaluator(Protocol):
    def __call__(
        self,
        candidate: PolicyCandidate,
        parent: PolicyCandidate,
    ) -> TriggerRecheckResult: ...


class TriggerTaskEvaluator:
    """Paired seen/unseen trigger evaluation over code-owned contexts."""

    def __init__(
        self,
        *,
        evaluator: RawPolicyEvaluator,
        manifest: Mapping[str, Any],
        ticket: Mapping[str, Any],
    ) -> None:
        self.evaluator = evaluator
        self.manifest = dict(manifest)
        self.ticket = dict(ticket)
        self.task = _ticket_manifest_task(self.manifest, self.ticket)
        regression = {str(value) for value in self.task["splits"]["policy_regression"]}
        if set(map(str, self.ticket["eval_init_state_ids"])) != regression:
            raise ValueError("ticket trigger unseen states differ from frozen regression shard")
        if set(map(str, self.ticket["init_state_ids"])).intersection(regression):
            raise ValueError("trigger seen and unseen states overlap")

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "schema_version": "trigger-recheck-context-v1",
            "manifest_hash": self.manifest["manifest_sha256"],
            "ticket_id": self.ticket["ticket_id"],
            "task_key": self.task["task_key"],
            "seen_init_state_ids": sorted(map(str, self.ticket["init_state_ids"])),
            "unseen_init_state_ids": sorted(
                map(str, self.ticket["eval_init_state_ids"])
            ),
            "policy_seed_repeats": 2,
        }

    def __call__(
        self,
        candidate: PolicyCandidate,
        parent: PolicyCandidate,
    ) -> TriggerRecheckResult:
        seen = _trigger_contexts(
            manifest_hash=str(self.manifest["manifest_sha256"]),
            ticket_id=str(self.ticket["ticket_id"]),
            task=self.task,
            split="seen",
            state_ids=self.ticket["init_state_ids"],
        )
        unseen = _trigger_contexts(
            manifest_hash=str(self.manifest["manifest_sha256"]),
            ticket_id=str(self.ticket["ticket_id"]),
            task=self.task,
            split="unseen",
            state_ids=self.ticket["eval_init_state_ids"],
        )
        role_prefix = f"trigger_recheck:{self.ticket['ticket_id']}"
        candidate_seen = self._evaluate(candidate, seen, f"{role_prefix}:seen")
        parent_seen = self._evaluate(parent, seen, f"{role_prefix}:seen")
        candidate_unseen = self._evaluate(candidate, unseen, f"{role_prefix}:unseen")
        parent_unseen = self._evaluate(parent, unseen, f"{role_prefix}:unseen")
        return TriggerRecheckResult(
            candidate_id=candidate.policy_id,
            parent_id=parent.policy_id,
            seen_successes=candidate_seen.successes,
            seen_total=candidate_seen.episodes,
            unseen_successes=candidate_unseen.successes,
            unseen_total=candidate_unseen.episodes,
            parent_seen_successes=parent_seen.successes,
            parent_seen_total=parent_seen.episodes,
            parent_unseen_successes=parent_unseen.successes,
            parent_unseen_total=parent_unseen.episodes,
        )

    def _evaluate(
        self,
        candidate: PolicyCandidate,
        contexts: Sequence[EvaluationContext],
        metric_role: str,
    ) -> PolicyEvaluationSummary:
        return self.evaluator.evaluate(
            policy_id=candidate.policy_id,
            checkpoint_path=Path(candidate.checkpoint_path),
            checkpoint_digest=candidate.checkpoint_digest,
            contexts=contexts,
            metric_role=metric_role,
        )


class PolicyPromotionCoordinator:
    """Run frozen 100/250 raw evaluation and the paired trigger recheck."""

    def __init__(
        self,
        *,
        evaluator: RawPolicyEvaluator,
        manifest: Mapping[str, Any],
        output_root: Path,
        bootstrap_draws: int = 10_000,
    ) -> None:
        if manifest.get("schema_version") != "joint-eval-manifest-v1":
            raise ValueError("policy promotion requires the frozen joint manifest")
        self.evaluator = evaluator
        self.manifest = dict(manifest)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.bootstrap_draws = int(bootstrap_draws)
        if self.bootstrap_draws <= 0:
            raise ValueError("bootstrap_draws must be positive")

    def run(
        self,
        *,
        parent: PolicyCandidate,
        candidates: Sequence[PolicyCandidate],
        trigger_evaluator: TriggerEvaluator,
        trigger_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidates = tuple(candidates)
        alphas = tuple(sorted(round(item.alpha_l, 8) for item in candidates))
        if len(candidates) != 4 or alphas != FROZEN_ALPHA_L:
            raise ValueError("policy gate requires alpha_l={0.2,0.4,0.6,0.8}")
        policy_ids = {parent.policy_id, *(item.policy_id for item in candidates)}
        if len(policy_ids) != 5:
            raise ValueError("parent and candidate policy IDs must be unique")
        if trigger_identity is None:
            trigger_identity = getattr(trigger_evaluator, "identity", None)
        if not isinstance(trigger_identity, Mapping) or not trigger_identity:
            raise ValueError("trigger evaluator requires a stable trigger_identity")
        input_value = {
            "schema_version": "raw-policy-gate-input-v1",
            "manifest_hash": self.manifest["manifest_sha256"],
            "parent": asdict(parent),
            "candidates": [asdict(item) for item in candidates],
            "trigger_identity": dict(trigger_identity),
        }
        input_hash = _json_digest(input_value)
        report_path = self.output_root / f"policy_gate_{input_hash[:16]}.json"
        if report_path.is_file():
            existing = json.loads(report_path.read_text(encoding="utf-8"))
            if existing.get("input_hash") != input_hash:
                raise ValueError("immutable policy gate report collision")
            return existing

        alpha_contexts = contexts_from_manifest(
            self.manifest, split="policy_alpha_selection"
        )
        alpha_summaries = {
            item.policy_id: self._evaluate(item, alpha_contexts, "promotion_raw:alpha100")
            for item in candidates
        }
        top2_scores = select_alpha_top2(
            [
                alpha_summaries[item.policy_id].policy_score(alpha_l=item.alpha_l)
                for item in candidates
            ]
        )
        by_id = {item.policy_id: item for item in candidates}
        top2 = tuple(by_id[item.candidate_id] for item in top2_scores)

        regression_contexts = contexts_from_manifest(
            self.manifest, split="policy_regression"
        )
        parent_regression = self._evaluate(
            parent, regression_contexts, "promotion_raw:regression250"
        )
        regression_summaries = {
            item.policy_id: self._evaluate(
                item, regression_contexts, "promotion_raw:regression250"
            )
            for item in top2
        }
        comparisons = {
            item.policy_id: _paired_comparison(
                contexts=regression_contexts,
                candidate=regression_summaries[item.policy_id],
                parent=parent_regression,
                draws=self.bootstrap_draws,
            )
            for item in top2
        }
        trigger_results: dict[str, TriggerRecheckResult] = {}
        for item in top2:
            if regression_summaries[item.policy_id].macro_sr > parent_regression.macro_sr:
                result = trigger_evaluator(item, parent)
                if result.candidate_id != item.policy_id or result.parent_id != parent.policy_id:
                    raise ValueError("trigger evaluator returned mismatched policy IDs")
                trigger_results[item.policy_id] = result
        regression_scores = [
            regression_summaries[item.policy_id].policy_score(alpha_l=item.alpha_l)
            for item in top2
        ]
        decision = raw_promotion_decision(
            parent_macro_sr=parent_regression.macro_sr,
            regression_scores=regression_scores,
            trigger_recheck_pass={
                policy_id: result.passed
                for policy_id, result in trigger_results.items()
            },
        )
        winner = by_id[decision.winner.candidate_id] if decision.winner else None
        report = {
            "schema_version": "raw-policy-gate-report-v1",
            "input_hash": input_hash,
            "manifest_hash": self.manifest["manifest_sha256"],
            "metric_role": "promotion_raw",
            "parent": asdict(parent),
            "alpha_selection": {
                "episodes": len(alpha_contexts),
                "summaries": {
                    key: _summary_dict(value) for key, value in alpha_summaries.items()
                },
                "top2": [item.policy_id for item in top2],
            },
            "regression": {
                "episodes": len(regression_contexts),
                "parent": _summary_dict(parent_regression),
                "candidates": {
                    key: _summary_dict(value)
                    for key, value in regression_summaries.items()
                },
                "paired_diagnostics": comparisons,
            },
            "trigger_recheck": {
                key: value.to_dict() for key, value in trigger_results.items()
            },
            "decision": {
                **asdict(decision),
                "winner": asdict(winner) if winner is not None else None,
            },
        }
        atomic_write_json(report_path, report)
        # Return the exact JSON representation so first-run and resumed calls
        # have identical container types (tuples become JSON arrays).
        return json.loads(report_path.read_text(encoding="utf-8"))

    def run_reuse(
        self,
        *,
        parent: PolicyCandidate,
        candidates: Sequence[PolicyCandidate],
        trigger_evaluator: TriggerEvaluator,
        trigger_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run every REUSE alpha through regression250 and trigger recheck."""

        candidates = tuple(sorted(candidates, key=lambda item: item.alpha_l))
        if not 1 <= len(candidates) <= 3:
            raise ValueError("REUSE gate requires one to three deduplicated candidates")
        if len({item.alpha_l for item in candidates}) != len(candidates):
            raise ValueError("REUSE candidate alpha_l values must be unique")
        policy_ids = {parent.policy_id, *(item.policy_id for item in candidates)}
        if len(policy_ids) != len(candidates) + 1:
            raise ValueError("parent and REUSE policy IDs must be unique")
        if trigger_identity is None:
            trigger_identity = getattr(trigger_evaluator, "identity", None)
        if not isinstance(trigger_identity, Mapping) or not trigger_identity:
            raise ValueError("trigger evaluator requires a stable trigger_identity")
        input_value = {
            "schema_version": "raw-policy-gate-input-v1",
            "gate_kind": "REUSE",
            "manifest_hash": self.manifest["manifest_sha256"],
            "parent": asdict(parent),
            "candidates": [asdict(item) for item in candidates],
            "trigger_identity": dict(trigger_identity),
        }
        input_hash = _json_digest(input_value)
        report_path = self.output_root / f"reuse_policy_gate_{input_hash[:16]}.json"
        if report_path.is_file():
            existing = json.loads(report_path.read_text(encoding="utf-8"))
            if existing.get("input_hash") != input_hash:
                raise ValueError("immutable REUSE policy gate report collision")
            return existing
        contexts = contexts_from_manifest(self.manifest, split="policy_regression")
        role = "promotion_raw:reuse_regression250"
        parent_summary = self._evaluate(parent, contexts, role)
        summaries = {
            item.policy_id: self._evaluate(item, contexts, role)
            for item in candidates
        }
        comparisons = {
            item.policy_id: _paired_comparison(
                contexts=contexts,
                candidate=summaries[item.policy_id],
                parent=parent_summary,
                draws=self.bootstrap_draws,
            )
            for item in candidates
        }
        trigger_results = {}
        for item in candidates:
            if summaries[item.policy_id].macro_sr > parent_summary.macro_sr:
                result = trigger_evaluator(item, parent)
                if result.candidate_id != item.policy_id or result.parent_id != parent.policy_id:
                    raise ValueError("trigger evaluator returned mismatched policy IDs")
                trigger_results[item.policy_id] = result
        decision = raw_promotion_decision(
            parent_macro_sr=parent_summary.macro_sr,
            regression_scores=[
                summaries[item.policy_id].policy_score(alpha_l=item.alpha_l)
                for item in candidates
            ],
            trigger_recheck_pass={
                policy_id: result.passed
                for policy_id, result in trigger_results.items()
            },
        )
        by_id = {item.policy_id: item for item in candidates}
        winner = by_id[decision.winner.candidate_id] if decision.winner else None
        report = {
            "schema_version": "raw-policy-gate-report-v1",
            "gate_kind": "REUSE",
            "input_hash": input_hash,
            "manifest_hash": self.manifest["manifest_sha256"],
            "metric_role": "promotion_raw",
            "parent": asdict(parent),
            "alpha_selection": {
                "skipped": True,
                "reason": "all_reuse_candidates_run_full_regression",
                "top2": [item.policy_id for item in candidates],
            },
            "regression": {
                "episodes": len(contexts),
                "parent": _summary_dict(parent_summary),
                "candidates": {
                    key: _summary_dict(value) for key, value in summaries.items()
                },
                "paired_diagnostics": comparisons,
            },
            "trigger_recheck": {
                key: value.to_dict() for key, value in trigger_results.items()
            },
            "decision": {
                **asdict(decision),
                "winner": asdict(winner) if winner is not None else None,
            },
        }
        atomic_write_json(report_path, report)
        return json.loads(report_path.read_text(encoding="utf-8"))

    def _evaluate(
        self,
        candidate: PolicyCandidate,
        contexts: Sequence[EvaluationContext],
        metric_role: str,
    ) -> PolicyEvaluationSummary:
        return self.evaluator.evaluate(
            policy_id=candidate.policy_id,
            checkpoint_path=Path(candidate.checkpoint_path),
            checkpoint_digest=candidate.checkpoint_digest,
            contexts=contexts,
            metric_role=metric_role,
        )


def deploy_policy_gate(
    *,
    report: Mapping[str, Any],
    registry: PolicyRegistry,
    expected_revision: int,
    verifier_result: Mapping[str, Any] | None = None,
    incidents: IncidentMemory | None = None,
    signature: Mapping[str, Any] | None = None,
) -> ActiveDeployment:
    """Install and deploy a staged policy, pairing a verifier only if gated."""

    if report.get("schema_version") != "raw-policy-gate-report-v1":
        raise ValueError("unsupported policy gate report")
    decision = report.get("decision", {})
    if decision.get("status") != "POLICY_STAGED" or not decision.get("winner"):
        raise RuntimeError("policy gate did not stage a deployable candidate")
    winner = PolicyCandidate(**decision["winner"])
    checkpoint = Path(winner.checkpoint_path)
    if checkpoint_digest(checkpoint) != winner.checkpoint_digest:
        raise ValueError("winning checkpoint digest changed after raw evaluation")
    registry.install_artifact("policy", winner.policy_id, checkpoint)

    verifier_id = None
    controller_mode = "fixed_budget_4"
    if verifier_result is not None and bool(verifier_result.get("gate", {}).get("passed")):
        verifier_id = str(verifier_result["verifier_id"])
        artifact_root = Path(str(verifier_result["artifact_root"]))
        manifest_path = artifact_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("metadata", {}).get("policy_id") != winner.policy_id:
            raise ValueError("verifier was not trained for the winning policy")
        registry.install_artifact("verifier", verifier_id, artifact_root)
        controller_mode = "learned_verifier"

    current = registry.active()
    if (
        current is not None
        and current.policy_id == winner.policy_id
        and current.verifier_id == verifier_id
        and current.controller_mode == controller_mode
        and current.manifest_hash == report["manifest_hash"]
    ):
        return current
    deployment = registry.promote(
        policy_id=winner.policy_id,
        verifier_id=verifier_id,
        controller_mode=controller_mode,
        manifest_hash=str(report["manifest_hash"]),
        expected_revision=expected_revision,
        reason="raw_regression_and_trigger_recheck_passed",
    )
    if incidents is not None and signature is not None:
        candidate_metadata_path = checkpoint / "candidate.json"
        candidate_metadata = (
            json.loads(candidate_metadata_path.read_text(encoding="utf-8"))
            if candidate_metadata_path.is_file()
            else {}
        )
        incidents.record_signature(
            CapabilitySignatureRecord(
                signature_id=str(signature["signature_id"]),
                suite=str(signature["suite"]),
                task_id=str(signature["task_id"]),
                perturbation_variant=str(signature["perturbation_variant"]),
                failure_mode=str(signature["failure_mode"]),
                e_goal_path=str(signature["e_goal_path"]),
                e_obs_path=str(signature["e_obs_path"]),
                policy_id=winner.policy_id,
                alpha_l=winner.alpha_l,
                validated=True,
                trigger_recheck_passed=True,
                regression_passed=True,
                delta_id=str(
                    signature.get("delta_id")
                    or candidate_metadata.get("target_delta_id", "")
                ),
                ticket_id=str(signature.get("ticket_id") or ""),
            )
        )
    return deployment


def _trigger_contexts(
    *,
    manifest_hash: str,
    ticket_id: str,
    task: Mapping[str, Any],
    split: str,
    state_ids: Sequence[str],
) -> tuple[EvaluationContext, ...]:
    contexts = []
    for state_id in sorted(map(str, state_ids)):
        for repeat in range(2):
            material = (
                f"trigger-recheck-v1\0{manifest_hash}\0{ticket_id}\0{split}\0"
                f"{task['task_key']}\0{state_id}\0{repeat}"
            )
            digest = hashlib.sha256(material.encode()).digest()
            contexts.append(
                EvaluationContext(
                    suite=str(task["suite"]),
                    task_id=str(task["task_id"]),
                    task_index=int(task["task_index"]),
                    perturbation_variant=str(task["perturbation_variant"]),
                    init_state_id=state_id,
                    env_seed=int.from_bytes(digest[:4], "big"),
                    policy_seed=int.from_bytes(digest[4:12], "big") % (2**63 - 1),
                )
            )
    return tuple(contexts)


def _ticket_manifest_task(
    manifest: Mapping[str, Any], ticket: Mapping[str, Any]
) -> Mapping[str, Any]:
    expected = (
        str(ticket["suite"]),
        str(ticket["task_id"]),
        str(ticket["perturbation_variant"]),
    )
    matches = [
        task
        for task in manifest["tasks"]
        if (
            str(task["suite"]),
            str(task["task_id"]),
            str(task["perturbation_variant"]),
        )
        == expected
    ]
    if len(matches) != 1:
        raise KeyError(f"ticket does not identify one frozen task: {expected}")
    return matches[0]


def _paired_comparison(
    *,
    contexts: Sequence[EvaluationContext],
    candidate: PolicyEvaluationSummary,
    parent: PolicyEvaluationSummary,
    draws: int,
) -> dict[str, Any]:
    if len(candidate.raw_vector) != len(parent.raw_vector) or len(contexts) != len(
        candidate.raw_vector
    ):
        raise ValueError("paired raw vectors are misaligned")
    point, lower, upper = paired_hierarchical_bootstrap(
        [item.task_key for item in contexts],
        [item.episode_key for item in contexts],
        candidate.raw_vector,
        parent.raw_vector,
        draws=draws,
    )
    return {
        "macro_delta": candidate.macro_sr - parent.macro_sr,
        "macro_retention_ratio": (
            candidate.macro_sr / parent.macro_sr
            if parent.macro_sr > 0
            else (1.0 if candidate.macro_sr == 0 else None)
        ),
        "paired_micro_delta": point,
        "paired_hierarchical_bootstrap95": [lower, upper],
    }


def _summary_dict(value: PolicyEvaluationSummary) -> dict[str, Any]:
    return {
        **asdict(value),
        "raw_vector": list(value.raw_vector),
        "wilson95": list(value.wilson95),
    }


def _json_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "FROZEN_ALPHA_L",
    "PolicyCandidate",
    "PolicyPromotionCoordinator",
    "TriggerRecheckResult",
    "TriggerTaskEvaluator",
    "deploy_policy_gate",
]
