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
import math
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .checkpoint_math import checkpoint_digest
from .evaluation import (
    PolicyScore,
    paired_hierarchical_bootstrap,
    raw_promotion_decision,
    rank_current_task_candidates,
    retention_metrics,
    gain_retention_tradeoffs,
)
from .incidents import CapabilitySignatureRecord, IncidentMemory
from .io_utils import AtomicJsonl, atomic_write_json, sha256_file
from .policy_evaluator import (
    EvaluationContext,
    PolicyEvaluationSummary,
    RawPolicyEvaluator,
    contexts_from_manifest,
)
from .registry import ActiveDeployment, PolicyRegistry
from .experiment_contract import (
    FIXED_BUDGET_50_LABEL_VERSION,
    require_fixed_budget_50_contract,
)


PROMOTION_PROTOCOL = "current-task-retention-tradeoff-v2"


@dataclass
class PromotionConfig:
    schema_version: str = PROMOTION_PROTOCOL
    current_task_splits: tuple[str, ...] = ("policy_alpha_selection", "policy_regression")
    current_policy_seed_repeats: int = 2
    retention_split: str = "policy_alpha_selection"
    retention_scope: str = "completed_formal_tasks"
    forgetting_penalty: float = 1.0

    def __post_init__(self) -> None:
        self.current_task_splits = tuple(self.current_task_splits)
        allowed = {"policy_alpha_selection", "policy_regression"}
        if self.schema_version != PROMOTION_PROTOCOL:
            raise ValueError("unsupported promotion protocol")
        if self.retention_scope != "completed_formal_tasks":
            raise ValueError("old-task retention must use previously completed formal tasks")
        if (not self.current_task_splits or len(set(self.current_task_splits)) != len(self.current_task_splits)
                or not set(self.current_task_splits) <= allowed or self.retention_split not in allowed):
            raise ValueError("promotion may use only development policy banks, never demos or final seal")
        if (isinstance(self.current_policy_seed_repeats, bool)
                or not isinstance(self.current_policy_seed_repeats, int)
                or self.current_policy_seed_repeats <= 0):
            raise ValueError("current-policy seed repeats must be a positive integer")
        if not math.isfinite(self.forgetting_penalty) or self.forgetting_penalty < 0:
            raise ValueError("forgetting penalty must be finite and non-negative")

    @classmethod
    def load(cls, path: Path) -> "PromotionConfig":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def load_retention_history(
    *, experiment_output: Path, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve prior tasks from this experiment, not unvisited PRO tasks.

    The main loop records a completed context only after its slow loop ends.
    Consequently its earlier completed tasks are the causal retention history
    for the current ticket. The first task has an explicitly empty history.
    Original LIBERO pretraining retention is a separate optional diagnostic.
    """
    root = Path(experiment_output)
    plan_path, ledger_path = root / "plan.json", root / "episodes.jsonl"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (plan.get("manifest_sha256") != manifest["manifest_sha256"]
            or plan.get("experiment_role") != "full_architecture_online"):
        raise ValueError("retention history is not from this formal experiment")
    planned = {c["context_id"]: c for c in plan["contexts"]}
    tasks = {t["task_key"] for t in manifest["tasks"]}
    completed = {}
    if not ledger_path.exists():
        status = json.loads((root / "status.json").read_text(encoding="utf-8"))
        if status.get("contexts_completed") != 0:
            raise ValueError("missing completed-context history is not an empty history")
    for row in AtomicJsonl(ledger_path).iter_valid():
        if row.get("event") != "EPISODE_COMPLETED":
            continue
        context_id = row["context_id"]
        task_key = row["task_key"]
        if (context_id not in planned or task_key not in tasks
                or planned[context_id]["task_key"] != task_key):
            raise ValueError("completed context does not belong to the formal plan")
        completed[context_id] = task_key
    return {
        "schema_version": "policy-retention-history-v1",
        "manifest_hash": manifest["manifest_sha256"],
        "task_keys": sorted(set(completed.values())),
        "completed_context_ids": sorted(completed),
        "sources": {
            "plan_path": str(plan_path), "plan_sha256": sha256_file(plan_path),
            "episode_ledger_path": str(ledger_path),
            "episode_ledger_sha256": sha256_file(ledger_path) if ledger_path.is_file() else None,
        },
        "basis": "previously_completed_formal_tasks_only",
        "pretraining_retention_included": False,
    }


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
        if self.unseen_total <= 0:
            raise ValueError("current-task selection requires held-out episodes")
        return self.unseen_successes / self.unseen_total

    @property
    def parent_score(self) -> float:
        if self.parent_unseen_total <= 0:
            raise ValueError("current-task selection requires held-out parent episodes")
        return self.parent_unseen_successes / self.parent_unseen_total

    @property
    def comparison_complete(self) -> bool:
        return (self.unseen_total > 0 and self.unseen_total == self.parent_unseen_total
                and 0 <= self.unseen_successes <= self.unseen_total
                and 0 <= self.parent_unseen_successes <= self.parent_unseen_total)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "candidate_score": self.candidate_score,
            "parent_score": self.parent_score,
            "comparison_complete": self.comparison_complete,
            "current_task_improved": self.candidate_score > self.parent_score,
            "current_task_delta": self.candidate_score - self.parent_score,
            "score_basis": "held_out_current_task_only",
            "seen_evaluated": self.seen_total > 0,
        }


class TriggerEvaluator(Protocol):
    def __call__(
        self,
        candidate: PolicyCandidate,
        parent: PolicyCandidate,
    ) -> TriggerRecheckResult: ...


class TriggerTaskEvaluator:
    """Current ticket's held-out task evaluation, paired with its parent."""

    def __init__(
        self,
        *,
        evaluator: RawPolicyEvaluator,
        manifest: Mapping[str, Any],
        ticket: Mapping[str, Any],
        config: PromotionConfig | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.manifest = dict(manifest)
        self.ticket = dict(ticket)
        self.config = config or PromotionConfig()
        self.task = _ticket_manifest_task(self.manifest, self.ticket)
        regression = {str(value) for value in self.task["splits"]["policy_regression"]}
        if set(map(str, self.ticket["eval_init_state_ids"])) != regression:
            raise ValueError("ticket trigger unseen states differ from frozen regression shard")
        if set(map(str, self.ticket["init_state_ids"])).intersection(regression):
            raise ValueError("trigger seen and unseen states overlap")
        self.current_contexts = tuple(
            context
            for split in self.config.current_task_splits
            for context in contexts_from_manifest(
                self.manifest, split=split,
                policy_seed_repeats=self.config.current_policy_seed_repeats,
            )
            if context.task_key == self.task["task_key"]
        )
        if not self.current_contexts or {c.init_state_id for c in self.current_contexts}.intersection(
            map(str, self.ticket["init_state_ids"])
        ):
            raise ValueError("current-task evaluation must be non-empty and independent of training demos")

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "schema_version": "current-task-held-out-context-v1",
            "manifest_hash": self.manifest["manifest_sha256"],
            "ticket_id": self.ticket["ticket_id"],
            "task_key": self.task["task_key"],
            "excluded_demo_init_state_ids": sorted(map(str, self.ticket["init_state_ids"])),
            "unseen_init_state_ids": sorted({c.init_state_id for c in self.current_contexts}),
            "policy_seed_repeats": self.config.current_policy_seed_repeats,
            "contexts": [asdict(c) for c in self.current_contexts],
            "promotion_config": asdict(self.config),
        }

    def __call__(
        self,
        candidate: PolicyCandidate,
        parent: PolicyCandidate,
    ) -> TriggerRecheckResult:
        role = f"promotion_raw:current_task:{self.ticket['ticket_id']}"
        # Parent runs once; subsequent candidates reuse its ledger without
        # switching the resident model back to the parent each time.
        parent_unseen = self._evaluate(parent, self.current_contexts, role)
        candidate_unseen = self._evaluate(candidate, self.current_contexts, role)
        return TriggerRecheckResult(
            candidate_id=candidate.policy_id,
            parent_id=parent.policy_id,
            seen_successes=0,
            seen_total=0,
            unseen_successes=candidate_unseen.successes,
            unseen_total=candidate_unseen.episodes,
            parent_seen_successes=0,
            parent_seen_total=0,
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
    """Select merged policies by current-task gain versus paired forgetting."""

    def __init__(
        self, *, evaluator: RawPolicyEvaluator, manifest: Mapping[str, Any],
        output_root: Path, bootstrap_draws: int = 10_000,
        config: PromotionConfig | None = None,
        retention_history: Mapping[str, Any] | None = None,
    ) -> None:
        if manifest.get("schema_version") != "joint-eval-manifest-v1":
            raise ValueError("policy promotion requires a joint manifest")
        self.evaluator = evaluator
        self.manifest = dict(manifest)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.bootstrap_draws = int(bootstrap_draws)
        self.config = config or PromotionConfig()
        self.retention_history = dict(retention_history) if retention_history is not None else None
        if self.bootstrap_draws <= 0:
            raise ValueError("bootstrap_draws must be positive")

    def run(
        self, *, parent: PolicyCandidate, candidates: Sequence[PolicyCandidate],
        trigger_evaluator: TriggerEvaluator,
        trigger_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._run(parent=parent, candidates=candidates,
                         trigger_evaluator=trigger_evaluator,
                         trigger_identity=trigger_identity, gate_kind="EXPANSION")

    def run_reuse(
        self, *, parent: PolicyCandidate, candidates: Sequence[PolicyCandidate],
        trigger_evaluator: TriggerEvaluator,
        trigger_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._run(parent=parent, candidates=candidates, trigger_evaluator=trigger_evaluator,
                         trigger_identity=trigger_identity, gate_kind="REUSE")

    def _run(
        self, *, parent: PolicyCandidate, candidates: Sequence[PolicyCandidate],
        trigger_evaluator: TriggerEvaluator,
        trigger_identity: Mapping[str, Any] | None, gate_kind: str,
    ) -> dict[str, Any]:
        if gate_kind not in {"EXPANSION", "REUSE"}:
            raise ValueError("unknown policy gate kind")
        candidates = tuple(sorted(candidates, key=lambda item: (item.alpha_l, item.policy_id)))
        if (not candidates or len({item.policy_id for item in candidates}) != len(candidates)
                or parent.policy_id in {item.policy_id for item in candidates}
                or len({item.alpha_l for item in candidates}) != len(candidates)):
            raise ValueError("parent and candidate identities/alphas must be unique")
        if trigger_identity is None:
            trigger_identity = getattr(trigger_evaluator, "identity", None)
        if not isinstance(trigger_identity, Mapping) or not trigger_identity.get("task_key"):
            raise ValueError("current-task evaluation requires an explicit trigger task identity")
        task_key = str(trigger_identity["task_key"])
        if sum(task["task_key"] == task_key for task in self.manifest["tasks"]) != 1:
            raise ValueError("trigger task is not a unique manifest task")
        history = self.retention_history
        if (history is None or history.get("schema_version") != "policy-retention-history-v1"
                or history.get("manifest_hash") != self.manifest["manifest_sha256"]
                or not isinstance(history.get("task_keys"), list)):
            raise ValueError("promotion requires explicit manifest-bound prior-task history")
        old_task_keys = set(history["task_keys"]) - {task_key}
        if not old_task_keys <= {task["task_key"] for task in self.manifest["tasks"]}:
            raise ValueError("retention history contains a task outside this manifest")
        config_value = json.loads(json.dumps(asdict(self.config)))
        trigger_config = trigger_identity.get("promotion_config")
        if trigger_config is not None and json.loads(json.dumps(trigger_config)) != config_value:
            raise ValueError("current-task evaluator and coordinator promotion configs differ")
        input_value = {
            "schema_version": "raw-policy-gate-input-v2",
            "selection_protocol": PROMOTION_PROTOCOL, "promotion_config": config_value,
            "gate_kind": gate_kind, "manifest_hash": self.manifest["manifest_sha256"],
            "parent": asdict(parent), "candidates": [asdict(item) for item in candidates],
            "trigger_identity": dict(trigger_identity),
            "retention_history": history,
            "bootstrap_draws": self.bootstrap_draws,
        }
        input_hash = _json_digest(input_value)
        prefix = "reuse_policy_gate" if gate_kind == "REUSE" else "policy_gate"
        report_path = self.output_root / f"{prefix}_{input_hash[:16]}.json"
        if report_path.is_file():
            existing = json.loads(report_path.read_text(encoding="utf-8"))
            if (existing.get("input_hash") != input_hash
                    or existing.get("selection_protocol") != PROMOTION_PROTOCOL):
                raise ValueError("policy gate report identity mismatch")
            return existing

        progress = {**input_value, "input_hash": input_hash,
                    "current_task_results": {}, "retention_checks": {}}

        def publish(state: str, **values: Any) -> None:
            progress.update(state=state, **values)
            atomic_write_json(self.output_root / "progress.json", progress)

        # Evaluate EVERY candidate on the task being learned before filtering.
        # The trigger executor caches the paired parent and uses no demo states.
        current: dict[str, TriggerRecheckResult] = {}
        parent_score = None
        parent_total = None
        for candidate in candidates:
            publish("CURRENT_TASK_EVALUATION", current_policy_id=candidate.policy_id)
            result = trigger_evaluator(candidate, parent)
            if result.candidate_id != candidate.policy_id or result.parent_id != parent.policy_id:
                raise ValueError("trigger evaluator returned mismatched policy IDs")
            if (result.unseen_total != result.parent_unseen_total
                    or not 0 <= result.unseen_successes <= result.unseen_total
                    or not 0 <= result.parent_unseen_successes <= result.parent_unseen_total):
                raise ValueError("current-task candidate and parent episodes must be paired")
            if parent_score is not None and (parent_score != result.parent_score
                                            or parent_total != result.parent_unseen_total):
                raise ValueError("current-task candidates must share the same parent baseline")
            parent_score, parent_total = result.parent_score, result.parent_unseen_total
            current[candidate.policy_id] = result
            progress["current_task_results"][candidate.policy_id] = result.to_dict()
            publish("CURRENT_TASK_EVALUATION")

        scores = [PolicyScore(item.policy_id, item.alpha_l, current[item.policy_id].candidate_score,
                              {task_key: current[item.policy_id].candidate_score})
                  for item in candidates]
        ranked = rank_current_task_candidates(scores)
        by_id = {item.policy_id: item for item in candidates}
        # Only tasks already completed in this experiment are "old". Future
        # tasks are generalization probes, not evidence of continual forgetting.
        retention_contexts = tuple(
            context for context in contexts_from_manifest(self.manifest, split=self.config.retention_split)
            if context.task_key in old_task_keys
        )
        parent_retention = None
        retention_summaries = {}
        checks = {}
        comparisons = {}
        role = f"promotion_raw:retention:{trigger_identity.get('ticket_id', task_key)}"
        publish("CURRENT_TASK_RANKED", ranking=[score.candidate_id for score in ranked])
        if retention_contexts:
            publish("RETENTION_BASELINE", current_policy_id=parent.policy_id)
            parent_retention = self._evaluate(parent, retention_contexts, role)
            # All merged candidates receive the same old-task bank: neither
            # global macro top-two pruning nor a zero-drop gate is applied.
            for score in ranked:
                candidate = by_id[score.candidate_id]
                publish("RETENTION_CHECK", current_policy_id=candidate.policy_id)
                summary = self._evaluate(candidate, retention_contexts, role)
                retention_summaries[candidate.policy_id] = summary
                check = retention_metrics(
                    parent=parent_retention.policy_score(alpha_l=parent.alpha_l),
                    candidate=summary.policy_score(alpha_l=candidate.alpha_l),
                )
                checks[candidate.policy_id] = check
                comparisons[candidate.policy_id] = _paired_comparison(
                    contexts=retention_contexts, candidate=summary, parent=parent_retention,
                    draws=self.bootstrap_draws,
                )
                progress["retention_checks"][candidate.policy_id] = check
                publish("RETENTION_CHECK_COMPLETE")
        else:
            publish("RETENTION_SKIPPED", skip_reason="no_prior_completed_tasks")

        # Zero here means "not applicable", not measured zero forgetting.
        forgetting = {item.policy_id: float(checks[item.policy_id]["macro_forgetting"])
                      if retention_contexts else 0.0 for item in candidates}
        tradeoffs = gain_retention_tradeoffs(
            parent_current_sr=parent_score, current_task_scores=scores,
            forgetting=forgetting, forgetting_penalty=self.config.forgetting_penalty,
        )
        decision = raw_promotion_decision(
            parent_current_sr=parent_score, current_task_scores=scores,
            forgetting=forgetting, forgetting_penalty=self.config.forgetting_penalty,
        )
        tradeoff_ranking = sorted(by_id, key=lambda key: (
            -round(tradeoffs[key]["score"], 12), tradeoffs[key]["old_task_forgetting"],
            -tradeoffs[key]["current_task_gain"], by_id[key].alpha_l, key,
        ))
        winner = by_id[decision.winner.candidate_id] if decision.winner else None
        report = {
            # Preserve the outer envelope consumed by the resident slow worker;
            # selection identity/config are explicitly versioned in input_hash.
            "schema_version": "raw-policy-gate-report-v1",
            "selection_protocol": PROMOTION_PROTOCOL, "promotion_config": config_value,
            "input_hash": input_hash, "gate_kind": gate_kind,
            "manifest_hash": self.manifest["manifest_sha256"], "metric_role": "promotion_raw",
            "parent": asdict(parent),
            "current_task": {
                "task_key": task_key, "episodes_per_policy": parent_total,
                "parent_score": parent_score, "score_basis": "held_out_current_task_only",
                "ranking": [score.candidate_id for score in ranked],
                "summaries": {key: value.to_dict() for key, value in current.items()},
                "tie_break": "smaller_language_alpha_then_policy_id",
            },
            "alpha_selection": {
                "global_alpha_selection_skipped": True, "episodes": parent_total,
                "ranking": tradeoff_ranking,
                "criterion": "current_task_gain_minus_weighted_old_task_forgetting",
            },
            "regression": {
                "purpose": "measure_forgetting_tradeoff", "current_task_excluded": True,
                "source_split": self.config.retention_split,
                "scope": self.config.retention_scope,
                "history": history, "old_task_keys": sorted(old_task_keys),
                "evaluated": bool(retention_contexts),
                "skip_reason": None if retention_contexts else "no_prior_completed_tasks",
                "episodes": len(retention_contexts),
                "contexts": [asdict(c) for c in retention_contexts],
                "parent": _summary_dict(parent_retention) if parent_retention else None,
                "candidates": {key: _summary_dict(value) for key, value in retention_summaries.items()},
                "checks": checks, "paired_diagnostics": comparisons,
                "not_evaluated": [item.policy_id for item in candidates if item.policy_id not in checks],
                "statistical_zero_forgetting_proven": False,
            },
            "trigger_recheck": {
                key: {**value.to_dict(),
                      "passed": winner is not None and key == winner.policy_id,
                      "capability_resolution_validated": False,
                      "criterion": "selected_by_difference_score_no_strict_improvement_gate"}
                for key, value in current.items()
            },
            "tradeoff": {
                "formula": "current_task_gain - forgetting_penalty * macro_forgetting",
                "forgetting_penalty": self.config.forgetting_penalty,
                "candidates": tradeoffs,
                "ranking": tradeoff_ranking,
                "zero_drop_required": False,
                "strict_current_task_improvement_required": False,
                "old_task_forgetting_applicable": bool(retention_contexts),
                "first_task_rule": "maximize_current_task_success_rate_among_merged_candidates",
                "positive_tradeoff_score_required": False,
                "tie_break": "less_forgetting_then_more_current_gain_then_smaller_alpha",
            },
            "decision": {**asdict(decision), "winner": asdict(winner) if winner else None},
        }
        atomic_write_json(report_path, report)
        publish("COMPLETE", decision=report["decision"], report_path=str(report_path))
        return json.loads(report_path.read_text(encoding="utf-8"))

    def _evaluate(
        self, candidate: PolicyCandidate, contexts: Sequence[EvaluationContext], metric_role: str,
    ) -> PolicyEvaluationSummary:
        return self.evaluator.evaluate(
            policy_id=candidate.policy_id, checkpoint_path=Path(candidate.checkpoint_path),
            checkpoint_digest=candidate.checkpoint_digest, contexts=contexts, metric_role=metric_role,
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
    """Pair a gated verifier or an explicitly authorized experimental update."""

    from .verifier_training import verifier_deployment_allowed

    if report.get("schema_version") != "raw-policy-gate-report-v1":
        raise ValueError("unsupported policy gate report")
    if report.get("gate_kind", "EXPANSION") not in {"EXPANSION", "REUSE"}:
        raise ValueError("unsupported measured policy gate kind")
    decision = report.get("decision", {})
    if decision.get("status") != "POLICY_STAGED" or not decision.get("winner"):
        raise RuntimeError("policy gate did not stage a deployable candidate")
    winner = PolicyCandidate(**decision["winner"])
    if report.get("gate_kind") == "REUSE":
        check = report.get("trigger_recheck", {}).get(winner.policy_id, {})
        if report.get("selection_protocol") != PROMOTION_PROTOCOL or not check.get("comparison_complete"):
            raise ValueError("REUSE requires measured current-task and retention comparison")
    checkpoint = Path(winner.checkpoint_path)
    if checkpoint_digest(checkpoint) != winner.checkpoint_digest:
        raise ValueError("winning checkpoint digest changed after raw evaluation")
    current = registry.active()
    if (current is not None and current.controller_mode == "learned_verifier"
            and (verifier_result is None or not verifier_deployment_allowed(verifier_result))):
        raise RuntimeError(
            "Formal promotion must retain an approved verifier; fixed-budget fallback is forbidden"
        )
    registry.install_artifact("policy", winner.policy_id, checkpoint)

    verifier_id = None
    controller_mode = "fixed_budget_50"
    if verifier_result is not None and verifier_deployment_allowed(verifier_result):
        verifier_id = str(verifier_result["verifier_id"])
        artifact_root = Path(str(verifier_result["artifact_root"]))
        manifest_path = artifact_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        current = registry.active()
        retained = (verifier_result.get("retained_existing_verifier") is True
                    and current is not None and current.verifier_id == verifier_id)
        if manifest.get("metadata", {}).get("policy_id") != winner.policy_id and not retained:
            raise ValueError("verifier was not trained for the winning policy")
        verifier_metadata = manifest.get("metadata", {})
        if verifier_metadata.get("label_version") != FIXED_BUDGET_50_LABEL_VERSION:
            raise ValueError("verifier was not trained on fixed_budget_50 labels")
        require_fixed_budget_50_contract(
            dict(verifier_metadata.get("label_config") or {})
        )
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
        deployment = current
    else:
        deployment = registry.promote(
            policy_id=winner.policy_id,
            verifier_id=verifier_id,
            controller_mode=controller_mode,
            manifest_hash=str(report["manifest_hash"]),
            expected_revision=expected_revision,
            reason="raw_regression_and_trigger_recheck_passed",
        )
    # Keep measured evidence searchable. Being the best merge is not proof of
    # transferability: any later reuse must be reconstructed and measured anew.
    # Also finish this append on an idempotent retry after the registry commit.
    if incidents is not None and signature is not None:
        trigger = report.get("trigger_recheck", {}).get(winner.policy_id, {})
        regression = report.get("regression", {})
        incidents.record_signature(CapabilitySignatureRecord(
            **{key: value for key, value in signature.items() if key != "metadata"},
            policy_id=winner.policy_id, alpha_l=winner.alpha_l,
            validated=False, trigger_recheck_passed=bool(
                trigger.get("capability_resolution_validated", False)),
            regression_passed=bool(
                regression.get("checks", {}).get(winner.policy_id, {}).get("passed", False)),
            metadata={**dict(signature.get("metadata") or {}),
                "use_status": "evidence_only_requires_current_policy_validation", "signature_reuse_enabled": True,
                "deployment_revision": deployment.deployment_revision,
                "selection_protocol": report.get("selection_protocol"),
                "promotion_config": report.get("promotion_config", {}),
                "current_task_evaluation": trigger,
                "retention_evaluation": regression,
                "tradeoff": report.get("tradeoff", {}),
                "validation_note": "merge selection is not transferable capability validation",
            },
        ))
    return deployment


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
    "PROMOTION_PROTOCOL",
    "PromotionConfig",
    "load_retention_history",
    "PolicyCandidate",
    "PolicyPromotionCoordinator",
    "TriggerRecheckResult",
    "TriggerTaskEvaluator",
    "deploy_policy_gate",
]
