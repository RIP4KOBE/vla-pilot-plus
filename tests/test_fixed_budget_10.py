from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mode_gate.audit import audit_contexts_from_manifest
from mode_gate.config import ModeGateConfig
from mode_gate.counterfactual import FixedBudgetResteerExecutor, FreshCandidateSelection
from mode_gate.evaluation import (
    adaptive_counterfactual_target,
    counterfactual_posterior_status,
)
from mode_gate.experiment_contract import (
    FIXED_BUDGET_50_CONTRACT,
    label_contract_payload,
    regenerate_budget_state,
)
from mode_gate.incidents import (
    IncidentMemory,
    VerifierDecisionRecord,
    VerifierLabelRecord,
)
from mode_gate.replay_budget import prepare_cost_capped_replay_plan
from mode_gate.types import ProgressEvidence
from mode_gate.verifier import CandidateVerifierInput, save_verifier_input
from mode_gate.verifier_training import (
    VerifierTrainingConfig,
    build_verifier_examples,
)


def test_fixed50_contract_and_versioned_mutability():
    config = ModeGateConfig()
    config.validate()
    assert config.retry_budget == 50 and config.controller_mode == "fixed_budget_50"
    assert len(config.retry_schedule) == 50
    assert FIXED_BUDGET_50_CONTRACT.max_policy_steps_per_branch == 500
    changed = ModeGateConfig(retry_budget=3,controller_mode="fixed_budget_3",
        label_version="experimental-budget-3-v1",retry_schedule=((1.,1.),)*3)
    changed.validate()
    assert changed.experiment_contract().retry_budget == 3


def test_budget_state_is_regenerated_without_mutating_fixed4_source() -> None:
    historical = {
        "retry_budget": 4,
        "retry_index": 3,
        "remaining_budget": 1,
        "failure_count": 3,
    }
    before = dict(historical)
    regenerated = regenerate_budget_state(historical)
    assert historical == before
    assert regenerated["retry_budget"] == 50
    assert regenerated["retry_index"] == 3
    assert regenerated["remaining_budget"] == 47
    assert regenerated["max_policy_steps"] == 470


def test_adaptive_replay_is_16_then_32_and_censors_boundary() -> None:
    assert adaptive_counterfactual_target(successes=0, trials=16)[0] == 16
    assert adaptive_counterfactual_target(successes=8, trials=16)[0] == 32
    assert adaptive_counterfactual_target(successes=16, trials=32)[0] == 32
    status = counterfactual_posterior_status(successes=16, trials=32)
    assert status["label_status"] == "AMBIGUOUS/CENSORED"
    assert status["posterior_side"] == "AMBIGUOUS"


class _Adapter:
    def __init__(self, outcome: str) -> None:
        self.outcome = outcome
        self.steps = 0

    def step(self, _action):
        self.steps += 1
        success = self.outcome == "success"
        terminal = self.outcome == "terminal"
        return None, 0.0, terminal, False, {"success": success}


def _selection(**_kwargs) -> FreshCandidateSelection:
    return FreshCandidateSelection(
        actions=np.zeros((10, 7), dtype=np.float32),
        candidate_id="m0",
        sample_index=0,
    )


def test_branch_stops_directly_on_libero_success_or_terminal() -> None:
    def forbidden_progress(**_kwargs):
        raise AssertionError("Gemini progress must not run after success/terminal")

    executor = FixedBudgetResteerExecutor(
        fresh_sampler=_selection,
        progress_observer=forbidden_progress,
    )
    state = {"retry_budget": 50, "retry_index": 0}
    success_adapter = _Adapter("success")
    success = executor(
        adapter=success_adapter,
        policy=object(),
        branch_seed=1,
        remaining_budget=50,
        controller_state=state,
    )
    assert success.task_success and success.chunks_executed == 1
    assert success_adapter.steps == 1

    terminal_adapter = _Adapter("terminal")
    terminal = executor(
        adapter=terminal_adapter,
        policy=object(),
        branch_seed=2,
        remaining_budget=50,
        controller_state=state,
    )
    assert terminal.terminal_timeout and terminal.chunks_executed == 1
    assert terminal_adapter.steps == 1


def test_branch_has_hard_10_chunk_100_step_bound() -> None:
    adapter = _Adapter("continue")
    executor = FixedBudgetResteerExecutor(
        fresh_sampler=_selection,
        progress_observer=lambda **_kwargs: ProgressEvidence(
            stage_id="UNKNOWN",
            advanced=False,
            confidence=0.0,
            source="test",
        ),
    )
    result = executor(
        adapter=adapter,
        policy=object(),
        branch_seed=3,
        remaining_budget=50,
        controller_state={"retry_budget": 50, "retry_index": 0},
    )
    assert result.chunks_executed == 50
    assert adapter.steps == 500


def _manifest() -> dict:
    tasks = []
    for index in range(40):
        tasks.append(
            {
                "task_key": f"suite-{index // 10}::task-{index}::variant",
                "suite": f"suite-{index // 10}",
                "task_id": f"task-{index}",
                "task_index": index % 10,
                "perturbation_variant": "variant",
                "splits": {
                    "verifier_audit_train": [f"train-{index}-{j}" for j in range(13)],
                    "verifier_calibration": [f"cal-{index}-{j}" for j in range(2)],
                    "verifier_test": [f"test-{index}-{j}" for j in range(5)],
                },
            }
        )
    return {
        "schema_version": "joint-eval-manifest-v1",
        "manifest_sha256": "a" * 64,
        "tasks": tasks,
    }


def test_audit_prefix_prioritizes_all_task_breadth() -> None:
    contexts = audit_contexts_from_manifest(_manifest(), limit=40)
    cells = {
        (item.evaluation.suite, item.evaluation.task_id)
        for item in contexts
    }
    assert len(contexts) == 40
    assert len(cells) == 40


def _feature() -> CandidateVerifierInput:
    return CandidateVerifierInput(scene_feature=np.zeros(2048,dtype=np.float32),
        candidate_trajectories=np.zeros((1,11,15),dtype=np.float32),executed_history=np.zeros((0,15),dtype=np.float32),
        remaining_budget=50,retry_budget=50,candidate_ids=("c0",),backbone_id="v44-sha")


def test_legacy_labels_alone_cannot_enter_planner_selected_training(tmp_path):
    memory = IncidentMemory(tmp_path / "incidents")
    with pytest.raises(ValueError, match="Planner"):
        build_verifier_examples(memory, policy_id="p1")


def test_replay_plan_migration_never_edits_historical_remaining_budget(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "snapshots"
    manifest_dir = snapshot_root / "s1"
    manifest_dir.mkdir(parents=True)
    manifest = {
        "snapshot_id": "s1",
        "snapshot_hash": "hash-s1",
        "controller_state": {
            "retry_budget": 4,
            "retry_index": 2,
            "remaining_budget": 2,
            "failure_count": 2,
        },
    }
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest))
    source = {
        "schema_version": "new-policy-counterfactual-plan-v2",
        "policy_id": "p1",
        "checkpoint_path": str(tmp_path / "checkpoint"),
        "checkpoint_digest": "d" * 64,
        "snapshot_root": str(snapshot_root),
        "incident_root": str(tmp_path / "incidents"),
        "decision_rule": "head_argmax",
        "contexts": [
            {
                "record_id": "r1",
                "snapshot_id": "s1",
                "snapshot_hash": "hash-s1",
                "remaining_budget": 2,
                "data_split": "train",
                "fresh_feature_output_path": str(tmp_path / "old.npz"),
            }
        ],
    }
    source["plan_sha256"] = hashlib.sha256(
        json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    source_path = tmp_path / "fixed4.json"
    source_path.write_text(json.dumps(source))
    historical_bytes = source_path.read_bytes()
    report = prepare_cost_capped_replay_plan(
        source_plan=source_path,
        output_dir=tmp_path / "fixed10",
        record_ids=["r1"],
        max_provider_calls=5000,
    )
    assert source_path.read_bytes() == historical_bytes
    plan = json.loads(Path(report["plan_path"]).read_text())
    assert plan["label_version"] == "fixed_budget_50-v2"
    assert plan["contexts"][0]["budget_state"]["remaining_budget"] == 48
    assert plan["contexts"][0]["fresh_feature_output_path"] != str(
        tmp_path / "old.npz"
    )


def test_training_config_has_no_mandatory_source_quotas():
    config = asdict(VerifierTrainingConfig(device="cpu"))
    assert "source_quotas" not in config and "minimum_train_contexts" not in config
    assert config["label_version"] == "fixed_budget_50-v2"


@pytest.mark.parametrize("retry_indices", [[50, 49, 0], [50], [50] * 15 + [0] * 15])
def test_staged_policy_replay_excludes_exhausted_before_sparse_selection(
    tmp_path, monkeypatch, retry_indices,
):
    from mode_gate import offline_replay, slow_worker
    from mode_gate.io_utils import atomic_write_json

    # Checkpoint loading is not needed to test replay-plan construction.
    monkeypatch.setattr(slow_worker, "checkpoint_digest", lambda _: "digest")
    monkeypatch.setattr(offline_replay, "checkpoint_digest", lambda _: "digest")
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    incidents = IncidentMemory(tmp_path / "incidents")
    decisions, originals = [], {}
    snapshots = tmp_path / "snapshots"
    for i, index in enumerate(retry_indices):
        snapshot_id, record_id = f"snapshot-{i}", f"record-{i:03d}"
        path = snapshots / snapshot_id / "manifest.json"
        atomic_write_json(path, {
            "snapshot_id": snapshot_id, "snapshot_hash": f"hash-{i}",
            "controller_state": {"retry_budget": 50, "retry_index": index,
                                 "failure_count": index, "remaining_budget": 999},
        })
        originals[path] = path.read_bytes()
        decisions.append({"record_id": record_id, "policy_id": "old-policy",
            "snapshot_id": snapshot_id, "snapshot_hash": f"hash-{i}",
            "p_expansion": 0.5,
            "provenance": {"group": {"suite": "libero_10", "task_id": f"task-{i % 2}",
                                       "perturbation_variant": "use_environment"}}})
    monkeypatch.setattr(incidents.decisions, "iter_valid", lambda: iter(decisions))
    worker = slow_worker.SlowLoopWorker.__new__(slow_worker.SlowLoopWorker)
    worker.incidents, worker.snapshot_root = incidents, snapshots
    worker._job_dir = lambda _: tmp_path / "work"
    worker._decision_verifier_split = lambda _: "train"
    job = SimpleNamespace(job_id="job", metadata={
        "staged_policy_id": "new-policy", "staged_checkpoint_path": str(checkpoint),
        "staged_checkpoint_digest": "digest"})
    transition = worker._prepare_new_policy_counterfactual(job)
    plan = offline_replay.validate_replay_plan(
        Path(transition.metadata["new_policy_counterfactual_plan_path"]))
    eligible = [i for i, index in enumerate(retry_indices) if index < 50]
    assert len(plan["contexts"]) == min(FIXED_BUDGET_50_CONTRACT.counterfactual_context_limit, len(eligible))
    assert len(plan["excluded_contexts"]) == retry_indices.count(50)
    assert all(c["budget_state"]["remaining_budget"] in range(1, 51) for c in plan["contexts"])
    assert all(c["target_policy_id"] == "new-policy" for c in plan["contexts"])
    assert all(c["reason"] == "fixed10_retry_budget_exhausted" for c in plan["excluded_contexts"])
    assert all(path.read_bytes() == before for path, before in originals.items())
    assert list(incidents.labels.iter_valid()) == []  # exclusions are not binary labels
    if len(eligible) > 14:
        assert len({c["task_key"] for c in plan["contexts"]}) == 2
    if not eligible:
        result = json.loads(Path(transition.metadata["new_policy_counterfactual_result_path"]).read_text())
        assert result["complete"] and result["contexts_planned"] == 0
        assert result["contexts_labeled"] == 0
        assert result["reason"] == "no_actionable_verifier_decision_snapshots_available"
