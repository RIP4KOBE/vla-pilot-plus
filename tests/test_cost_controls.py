"""Fast tests for API-cost controls and zero-call label reconstruction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mode_gate.factual_reconstruction import reconstruct_factual_labels
from mode_gate.experiment_contract import (
    FIXED_BUDGET_10_CONTRACT,
    label_contract_payload,
    regenerate_budget_state,
)
from mode_gate.incidents import IncidentMemory, VerifierDecisionRecord
from mode_gate.io_utils import AtomicJsonl, atomic_write_json
from mode_gate.offline_replay import _reuse_or_build_feature
from mode_gate.replay_budget import prepare_cost_capped_replay_plan
from mode_gate.semantic_planner import (
    GeminiCallBudgetExceeded,
    GeminiSemanticPlanner,
)
from mode_gate.verifier import CandidateVerifierInput, save_verifier_input
from mode_gate.types import (
    ActionChunkBatch,
    GateContext,
    GeometryEvidence,
    CandidateEvidence,
    RoundEvidence,
    SamplingDiagnostics,
    TaskSpaceTrajectoryBatch,
)


class _Interactions:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(output_text=json.dumps(self.payload))


def _evidence() -> RoundEvidence:
    actions = ActionChunkBatch(np.zeros((1,10,7),dtype=np.float32),("s0",),"ctx",1,"policy","OSC","world")
    trajectories = TaskSpaceTrajectoryBatch(np.zeros((1,11,3)),np.tile([0,0,0,1],(1,11,1)),np.ones((1,11)),("s0",))
    return RoundEvidence("ctx",1,"policy",actions,trajectories,(CandidateEvidence("m0",0,"s0"),),
        SamplingDiagnostics((1.,),(0,),1.,1.))


def test_provider_call_cap_persists_and_cache_hits_do_not_consume(tmp_path):
    evidence = _evidence()
    payload = {
        "selected_candidate_id": "m0", "selection_reason": "全部候选中可行",
        "candidates": [
            {
                "candidate_id": "m0",
                "semantic_score": 0.5,
                "reason": "ok",
                "predicted_failure_types": [],
            }
        ],
        "required_trajectory_pattern": "approach",
        "observed_stage_id": "stage_1",
        "stage_confidence": 0.9,
    }
    card = tmp_path / "card.png"
    card.write_bytes(b"png")
    ledger = tmp_path / "calls.jsonl"
    interactions = _Interactions(payload)
    planner = GeminiSemanticPlanner(
        client=SimpleNamespace(interactions=interactions),
        cache_dir=tmp_path / "cache",
        max_provider_calls=1,
        call_ledger_path=ledger,
    )
    geometry = (GeometryEvidence("m0", 0.1, 0.9, 0.8, False),)
    context = GateContext("a", np.zeros((8, 8, 3), np.uint8), "pick", "stage_1")
    planner.score(context, evidence, geometry, card)
    assert planner.score(context, evidence, geometry, card).raw_response[
        "metadata"
    ]["cache_hit"]
    assert interactions.calls == 1

    restarted_calls = _Interactions(payload)
    restarted = GeminiSemanticPlanner(
        client=SimpleNamespace(interactions=restarted_calls),
        cache_dir=tmp_path / "cache",
        max_provider_calls=1,
        call_ledger_path=ledger,
    )
    with pytest.raises(GeminiCallBudgetExceeded):
        restarted.score(
            GateContext("b", np.zeros((8, 8, 3), np.uint8), "pick", "stage_1"),
            evidence,
            geometry,
            card,
        )
    assert restarted_calls.calls == 0




def test_cost_capped_subset_is_signed_and_reuses_only_fixed10_feature(tmp_path):
    snapshot_root = tmp_path / "snapshots"
    snapshot_manifest = snapshot_root / "snapshot-1" / "manifest.json"
    snapshot_manifest.parent.mkdir(parents=True)
    atomic_write_json(
        snapshot_manifest,
        {
            "snapshot_id": "snapshot-1",
            "snapshot_hash": "a" * 64,
            "controller_state": {
                "retry_budget": 4,
                "retry_index": 0,
                "remaining_budget": 4,
                "failure_count": 1,
            },
        },
    )
    source = {
        "schema_version": "new-policy-counterfactual-plan-v2",
        "job_id": "source",
        "policy_id": "policy-0",
        "checkpoint_path": str(tmp_path / "checkpoint"),
        "checkpoint_digest": "d" * 64,
        "snapshot_root": str(snapshot_root),
        "incident_root": str(tmp_path / "incidents"),
        "decision_rule": "head_argmax",
        "progress_contract": "bddl-then-post-action-gemini-stage-v1",
        "contexts": [
            {
                "record_id": "record-1",
                "target_policy_id": "policy-0",
                "snapshot_id": "snapshot-1",
                "snapshot_hash": "a" * 64,
                "remaining_budget": 4,
                "data_split": "train",
                "fresh_feature_output_path": str(tmp_path / "feature.npz"),
            }
        ],
        "result_path": str(tmp_path / "source-result.json"),
    }
    source["plan_sha256"] = hashlib.sha256(
        json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    report = prepare_cost_capped_replay_plan(
        source_plan=source_path,
        output_dir=tmp_path / "capped",
        record_ids=("record-1",),
        max_provider_calls=17,
        branch_ledger_path=tmp_path / "existing-branches.jsonl",
    )
    plan = json.loads(Path(report["plan_path"]).read_text(encoding="utf-8"))
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    assert plan["plan_sha256"] == hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert plan["gemini_max_provider_calls"] == 17
    assert plan["label_version"] == "fixed_budget_50-v2"
    assert plan["contexts"][0]["record_id"] == "record-1"
    assert plan["contexts"][0]["budget_state"]["remaining_budget"] == 50
    assert prepare_cost_capped_replay_plan(
        source_plan=source_path,
        output_dir=tmp_path / "capped",
        record_ids=("record-1",),
        max_provider_calls=17,
        branch_ledger_path=tmp_path / "existing-branches.jsonl",
    )["plan_sha256"] == plan["plan_sha256"]

    feature_path = Path(plan["contexts"][0]["fresh_feature_output_path"])
    save_verifier_input(
        feature_path,
        CandidateVerifierInput(
            scene_feature=np.zeros(2048, dtype=np.float32),
            candidate_trajectories=np.zeros((1,11,15),dtype=np.float32),
            executed_history=np.zeros((0,15),dtype=np.float32),
            remaining_budget=50,retry_budget=50,candidate_ids=("m0",),backbone_id="v44-sha",
        ),
        metadata={
            "schema_version": "candidate-verifier-input-v3",
            "record_id": "record-1",
            "snapshot_id": "snapshot-1",
            "target_policy_id": "policy-0",
            "label_version": "fixed_budget_50-v2",
            "label_contract_hash": plan["label_config"]["contract_hash"],
            "retry_budget": 50,
            "retry_index": 0,
            "remaining_budget": 50,
            "gemini_thinking_level": "medium",
        },
    )

    class Application:
        def build_feature(self, **kwargs):
            raise AssertionError("valid existing feature should be reused")

    assert _reuse_or_build_feature(
        Application(), context=plan["contexts"][0], policy_id="policy-0"
    ) == feature_path.resolve()
