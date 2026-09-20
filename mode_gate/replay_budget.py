"""Prepare independent, call-capped ``fixed_budget_50`` replay plans.

Historical fixed-4 plans and labels are migration inputs only. This module
never edits them: it re-derives every budget-dependent field from the immutable
snapshot and writes a new label-version namespace.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from .counterfactual import REPLAY_PROGRESS_CONTRACT
from .experiment_contract import (
    FIXED_BUDGET_50_CONTRACT,
    label_contract_payload,
    regenerate_budget_state,
)
from .io_utils import atomic_write_json, sha256_file


def prepare_cost_capped_replay_plan(
    *,
    source_plan: Path,
    output_dir: Path,
    record_ids: Sequence[str],
    max_provider_calls: int,
    branch_ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Create a signed fixed10 subset without mutating its source plan."""

    contract = FIXED_BUDGET_50_CONTRACT
    source_path = Path(source_plan).resolve()
    source = _load_signed_plan(source_path)
    selected_ids = tuple(dict.fromkeys(str(value) for value in record_ids))
    if not selected_ids or any(not value for value in selected_ids):
        raise ValueError("at least one non-empty replay record ID is required")
    if len(selected_ids) != len(tuple(record_ids)):
        raise ValueError("cost-capped replay record IDs must be unique")
    if not 0 < int(max_provider_calls) <= contract.counterfactual_provider_call_limit:
        raise ValueError("counterfactual max_provider_calls must be in (0, 5000]")
    if len(selected_ids) > contract.counterfactual_context_limit:
        raise ValueError(
            "selection exceeds the conservative fixed10 context limit "
            f"({contract.counterfactual_context_limit})"
        )

    by_id = {str(value["record_id"]): dict(value) for value in source["contexts"]}
    unknown = sorted(set(selected_ids) - set(by_id))
    if unknown:
        raise KeyError(f"record IDs are absent from the source plan: {unknown}")

    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    feature_root = root / "features"
    feature_root.mkdir(parents=True, exist_ok=True)
    snapshot_root = Path(str(source["snapshot_root"])).resolve()
    contexts: list[dict[str, Any]] = []
    for record_id in selected_ids:
        historical = by_id[record_id]
        snapshot_id = str(historical["snapshot_id"])
        manifest_path = snapshot_root / snapshot_id / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            str(manifest.get("snapshot_id")) != snapshot_id
            or str(manifest.get("snapshot_hash"))
            != str(historical["snapshot_hash"])
        ):
            raise ValueError(f"snapshot identity changed for {record_id}")
        budget_state = regenerate_budget_state(
            dict(manifest.get("controller_state") or {}), contract=contract
        )
        if int(budget_state["remaining_budget"]) <= 0:
            raise ValueError(
                f"selected record has no fixed10 RE-STEER budget: {record_id}"
            )
        contexts.append(
            {
                "record_id": record_id,
                "origin_policy_id": str(historical.get("origin_policy_id") or ""),
                "target_policy_id": str(source["policy_id"]),
                "snapshot_id": snapshot_id,
                "snapshot_hash": str(historical["snapshot_hash"]),
                "snapshot_manifest_path": str(manifest_path.resolve()),
                "data_split": str(historical["data_split"]),
                "label_version": contract.label_version,
                "budget_state": budget_state,
                "fresh_feature_output_path": str(
                    (feature_root / f"{record_id}.npz").resolve()
                ),
                "reusable_budget_independent_source": {
                    "snapshot_id": snapshot_id,
                    "historical_feature_path": str(
                        historical.get("fresh_feature_output_path") or ""
                    ),
                },
            }
        )
    contexts.sort(key=lambda value: str(value["record_id"]))

    branch_ledger = Path(
        branch_ledger_path
        if branch_ledger_path is not None
        else root / "branches.jsonl"
    ).resolve()
    incident_root = Path(str(source["incident_root"])).resolve()
    call_ledger = (
        incident_root
        / "fixed_budget_50"
        / "counterfactual_gemini_provider_calls.jsonl"
    ).resolve()
    result_path = (root / "replay_result.json").resolve()
    subset_material = "\0".join(sorted(selected_ids))
    plan: dict[str, Any] = {
        "schema_version": "new-policy-counterfactual-plan-v3",
        "job_id": (
            "fixed10-"
            + str(source.get("policy_id"))
            + "-"
            + hashlib.sha256(subset_material.encode()).hexdigest()[:12]
        ),
        "policy_id": str(source["policy_id"]),
        "checkpoint_path": str(source["checkpoint_path"]),
        "checkpoint_digest": str(source["checkpoint_digest"]),
        "snapshot_root": str(snapshot_root),
        "incident_root": str(incident_root),
        "label_version": contract.label_version,
        "label_config": label_contract_payload(contract),
        "retry_estimand": (
            "P(fail to advance/succeed under remaining fixed_budget_50 "
            "RE-STEER schedule)"
        ),
        "adaptive_branches": [
            contract.counterfactual_initial_branches,
            contract.counterfactual_max_branches,
        ],
        "decision_rule": "head_argmax",
        "progress_contract": REPLAY_PROGRESS_CONTRACT,
        "parent_plan_path": str(source_path),
        "parent_plan_sha256": str(source["plan_sha256"]),
        "selection": {
            "kind": "explicit_targeted_record_subset",
            "record_ids": sorted(selected_ids),
            "source_context_count": len(tuple(source.get("contexts", ()))),
            "strategy": contract.coverage_strategy,
        },
        "contexts": contexts,
        "gemini_max_provider_calls": int(max_provider_calls),
        "gemini_call_ledger_path": str(call_ledger),
        "branch_ledger_path": str(branch_ledger),
        "result_path": str(result_path),
    }
    for key in ("code_revision", "preflight_path", "preflight_sha256"):
        if key in source:
            plan[key] = source[key]
    plan["plan_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    plan_path = root / "replay_plan.json"
    if plan_path.is_file():
        existing = json.loads(plan_path.read_text(encoding="utf-8"))
        if existing != plan:
            raise ValueError(f"independent fixed10 plan collision: {plan_path}")
    else:
        atomic_write_json(plan_path, plan)
    report = {
        "schema_version": "fixed-budget-10-replay-preparation-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_plan_path": str(source_path),
        "source_plan_file_sha256": sha256_file(source_path),
        "source_plan_sha256": str(source["plan_sha256"]),
        "source_artifacts_mutated": False,
        "plan_path": str(plan_path),
        "plan_sha256": str(plan["plan_sha256"]),
        "label_version": contract.label_version,
        "label_config": label_contract_payload(contract),
        "record_ids": sorted(selected_ids),
        "context_count": len(contexts),
        "max_provider_calls": int(max_provider_calls),
        "call_ledger_path": str(call_ledger),
        "branch_ledger_path": str(branch_ledger),
        "result_path": str(result_path),
    }
    atomic_write_json(root / "preparation_report.json", report)
    return report


def _load_signed_plan(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") not in {
        "new-policy-counterfactual-plan-v2",
        "new-policy-counterfactual-plan-v3",
    }:
        raise ValueError("unsupported counterfactual replay plan")
    expected = str(value.get("plan_sha256") or "")
    unsigned = {key: item for key, item in value.items() if key != "plan_sha256"}
    actual = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual != expected:
        raise ValueError("source replay plan checksum mismatch")
    if value.get("decision_rule") != "head_argmax":
        raise ValueError("source replay plan does not use direct head argmax")
    return value


__all__ = ["prepare_cost_capped_replay_plan"]
