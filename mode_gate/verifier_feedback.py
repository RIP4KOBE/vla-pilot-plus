"""Observed correctness feedback for the binary head, never synthetic outcomes.

This is an evidence compiler, not a rollout/replay scheduler or a labeler. Planner
still selects/revises labels and positive loss weights. Signed decision rewards
describe the *original proposal*; training uses the corrected binary target.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math

from .experiment_contract import FIXED_BUDGET_50_CONTRACT, FIXED_BUDGET_50_LABEL_VERSION
from .io_utils import AtomicJsonl


FEEDBACK_SCHEMA = "observed-verifier-action-feedback-v1"
FEEDBACK_FILE = "verifier_action_feedback.jsonl"
BINARY = {"RE-STEER", "EXPANSION"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _physical_step(payload):
    return (type(payload.get("native_success")) is bool
            and all(isinstance(payload.get(key), list) and len(payload[key]) == 7
                    and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                            and math.isfinite(x) for x in payload[key])
                    for key in ("action_osc", "observed_pose")))


def _assess(decision, facts):
    """Use only an uninterrupted continuation of this decision, on this policy.

    Reset/replay/other-policy outcomes need their own explicit lineage and Planner
    analysis. They are never inferred from matching task text or a later success.
    """
    record_id = decision["record_id"]
    episode_id = decision.get("provenance", {}).get("episode_id", "")
    base = {"record_id": record_id, "episode_id": episode_id,
            "status": "CENSORED", "decision_reward": None, "target_label": None}

    def unresolved(reason, *, pending=False):
        return {**base, "status": "PENDING" if pending else "CENSORED", "reason": reason}

    if any(x["kind"] == "formal_attempt_excluded_by_protocol_update" for x in facts):
        return unresolved("episode_explicitly_excluded")
    remaining, retry_index = decision.get("remaining_budget"), decision.get("retry_index")
    contract = FIXED_BUDGET_50_CONTRACT
    if (decision.get("label_version") != FIXED_BUDGET_50_LABEL_VERSION
            or decision.get("feature_schema") != "candidate-verifier-input-v3"
            or decision.get("retry_budget") != contract.retry_budget
            or not _integer(remaining) or not _integer(retry_index)
            or not 0 < remaining <= contract.retry_budget
            or retry_index != contract.retry_budget - remaining):
        return unresolved("incompatible_or_empty_decision_budget")
    starts = [(i, x) for i, x in enumerate(facts)
              if x["kind"] == "decision_context" and x["context_id"] == record_id]
    if not episode_id or len(starts) != 1:
        return unresolved("missing_or_ambiguous_decision_fact")
    start_index, start = starts[0]
    p = start["payload"]
    start_step = p.get("step")
    if (not _integer(start_step) or start_step < 0 or p.get("policy_id") != decision["policy_id"]
            or p.get("retry_index") != retry_index or p.get("remaining_budget") != remaining
            or p.get("verifier_proposal") != decision["verifier_decision"]
            or p.get("route") != decision["route"]):
        return unresolved("decision_fact_provenance_mismatch")
    # Ordinary EXECUTE does not consume retry_index. Bound success credit by
    # actual executed steps too, or 700 EXECUTE steps would look like zero retry.
    horizon = remaining * contract.chunk_horizon
    active = start
    active_count = 0
    last_retry = retry_index
    trace, sources, routes = [], [start], []
    all_retry_steps = True

    def observed(target, reason):
        reward = 1 if decision["verifier_decision"] == target else -1
        result = {**base, "schema_version": FEEDBACK_SCHEMA, "status": "OBSERVED",
            "reason": reason, "target_label": target, "decision_reward": reward,
            "proposal": decision["verifier_decision"], "actual_initial_route": decision["route"],
            "policy_id": decision["policy_id"], "verifier_id": p.get("verifier_id"),
            "snapshot_hash": decision["snapshot_hash"], "label_version": decision["label_version"],
            "retry_budget": contract.retry_budget, "retry_index": retry_index,
            "remaining_budget": remaining, "chunk_horizon": contract.chunk_horizon,
            "maximum_continuation_steps": horizon, "continuation_steps": len(trace),
            "decision_step": start_step, "outcome_step": trace[-1]["payload"]["step"],
            "native_success": target == "RE-STEER", "executed_routes": sorted(set(routes)),
            "evidence_scope": "observed_same_policy_continuation_not_proof_of_impossibility",
            "input_time_scope": "original_decision_only",
            "training_semantics": "Planner_selected_corrected_target_with_positive_weight_not_signed_loss",
            "decision_sha256": _digest(decision), "continuation_sha256": _digest(sources),
            "evidence_refs": [{"event_id": start["event_id"]}, {"event_id": trace[-1]["event_id"]}]}
        result["feedback_id"] = result["event_id"] = "verifier-feedback:" + _digest(result)
        return result

    if active["payload"].get("route") not in {"EXECUTE", "RE-STEER"}:
        return unresolved("no_actual_continuation_after_proposal")
    for fact in facts[start_index + 1:]:
        kind, payload = fact["kind"], fact["payload"]
        if kind == "decision_context":
            if not trace:
                return unresolved("original_decision_was_not_executed")
            if payload.get("policy_id") != decision["policy_id"]:
                return unresolved("policy_changed_before_outcome")
            if payload.get("step") != start_step + len(trace):
                return unresolved("reset_or_discontinuous_decision")
            if payload.get("route") not in {"EXECUTE", "RE-STEER"}:
                return unresolved("continuation_stopped_before_observed_outcome")
            active, active_count = fact, 0
            sources.append(fact)
        elif kind == "executed_step":
            if payload.get("policy_id") != decision["policy_id"]:
                return unresolved("policy_changed_before_outcome")
            if (payload.get("step") != start_step + len(trace) + 1
                    or fact["context_id"] != active["context_id"]
                    or not _physical_step(payload)):
                return unresolved("missing_reset_or_mismatched_physical_execution")
            index = payload.get("retry_index")
            route = active["payload"]["route"]
            expected_index = last_retry + int(route == "RE-STEER" and active_count == 0)
            if (not _integer(index) or index != expected_index or index > contract.retry_budget
                    or active_count >= contract.chunk_horizon):
                return unresolved("invalid_retry_schedule_or_chunk_length")
            active_count += 1
            last_retry = index
            trace.append(fact)
            sources.append(fact)
            routes.append(route)
            all_retry_steps &= (route == "RE-STEER"
                and index == retry_index + (len(trace) - 1) // contract.chunk_horizon + 1)
            if payload["native_success"]:
                return observed("RE-STEER", "native_success_within_remaining_horizon")
            if len(trace) == horizon:
                if all_retry_steps:
                    return observed("EXPANSION", "observed_remaining_retry_chunks_exhausted")
                return unresolved("continuation_horizon_observed_but_not_all_retry_chunks_exhausted")
        elif kind in {"rollout_completed", "episode_reset", "snapshot_restored", "policy_changed"}:
            return unresolved("rollout_or_execution_boundary_without_observed_budget_outcome")
        elif kind == "retry_outcome" and payload.get("censored"):
            return unresolved("early_stopped_continuation_is_censored")
    return unresolved("awaiting_observed_continuation", pending=True)


def derive_verifier_feedback(memory, *, record_ids=None):
    """Pure derivation: no labels, model updates, simulator actions or file writes."""
    episodes = defaultdict(list)
    for fact in memory.experiences.facts.iter_valid():
        episodes[fact["episode_id"]].append(fact)
    selected = set(record_ids) if record_ids is not None else None
    result = []
    for row in memory.decisions.iter_valid():
        if (row.get("decision_rule") != "head_argmax" or row.get("verifier_decision") not in BINARY
                or (selected is not None and row["record_id"] not in selected)):
            continue
        result.append(_assess(row, episodes[row.get("provenance", {}).get("episode_id", "")]))
    return result


def publish_verifier_feedback(memory):
    """Append reproducible evidence only. Planner remains the label/retrain owner."""
    assessments = derive_verifier_feedback(memory)
    observed = [x for x in assessments if x["status"] == "OBSERVED"]
    ledger = AtomicJsonl(memory.root / FEEDBACK_FILE)
    inserted = ledger.append_many(observed)
    return {"schema_version": FEEDBACK_SCHEMA, "ledger_path": str(ledger.path),
            "counts": dict(Counter(x["status"] for x in assessments)),
            "new_observed": sum(inserted), "observed": observed,
            "unresolved": [x for x in assessments if x["status"] != "OBSERVED"]}


def validate_feedback_annotation(memory, annotation, *, assessments=None):
    """Recompute immutable sources; a claimed reward is not trusted supervision."""
    if not annotation.get("feedback_id"):
        if annotation.get("decision_reward") is not None:
            raise ValueError("decision_reward requires validated observed feedback_id")
        return None
    if assessments is None:
        assessments = derive_verifier_feedback(memory, record_ids=[annotation["record_id"]])
    found = [x for x in assessments if x.get("feedback_id") == annotation["feedback_id"]
             and x["record_id"] == annotation["record_id"] and x["status"] == "OBSERVED"]
    if len(found) != 1:
        raise ValueError("feedback is unknown, censored or invalidated by newer evidence")
    feedback = found[0]
    if (annotation.get("label") != feedback["target_label"]
            or annotation.get("episode_id") != feedback["episode_id"]
            or type(annotation.get("decision_reward")) is not int
            or annotation.get("decision_reward") != feedback["decision_reward"]
            or annotation.get("label_version") != feedback["label_version"]):
        raise ValueError("feedback correction label/reward/provenance mismatch")
    cited = {x.get("event_id") for x in annotation.get("evidence_refs", [])}
    if not {x["event_id"] for x in feedback["evidence_refs"]} <= cited:
        raise ValueError("feedback annotation must cite its decision and actual outcome facts")
    weight = float(annotation.get("weight", 1.0))
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError("signed decision reward is not a loss weight; weight must be finite and positive")
    return feedback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incidents", required=True)
    parser.add_argument("--publish", action="store_true", help="append evidence, never auto-label or retrain")
    args = parser.parse_args()
    from .incidents import IncidentMemory
    memory = IncidentMemory(args.incidents)
    result = publish_verifier_feedback(memory) if args.publish else derive_verifier_feedback(memory)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
