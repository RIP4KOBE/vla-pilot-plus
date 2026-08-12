from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "eds_qd_autoresearch_v3_runner.py"
)
SPEC = importlib.util.spec_from_file_location(
    "eds_qd_autoresearch_v3_runner",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_online_matrix_profiles_and_budget_are_exact():
    control, candidate = runner.profiles()
    jobs = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)

    assert runner.MECHANISM_TASKS == [3, 8, 9]
    assert runner.MECHANISM_SEEDS == [955865, 522754, 845886]
    assert runner.INITIAL_GLOBAL_ATTEMPT_IDS == list(range(67, 73))
    assert runner.EXPECTED_GLOBAL_ATTEMPT_IDS == list(range(73, 79))
    assert control["label"] == "p2_stage_on_abs_rbf_control"
    assert control["qd_archive_mode"] == "none"
    assert candidate["label"] == "eds_qd_global_quality_anchor_v1"
    assert candidate["qd_archive_mode"] == "grid_archive"
    assert candidate["qd_parent_sampling"] == "sparse_priority"
    assert candidate["qd_bounds_update_policy"] == "causal_envelope_v1"
    assert candidate["qd_global_quality_anchor_count"] == 1
    assert candidate["qd_degenerate_fallback_policy"] == "none"
    assert len(jobs) == 2
    assert all(job["episodes"] == 3 and job["max_chunks"] == 16 for job in jobs)


def test_candidate_command_binds_anchor_once_and_contains_no_secret():
    candidate = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)[1]
    command = runner.build_main_command(candidate)

    anchor = [
        token
        for token in command
        if token.startswith("main.eds_config.qd_global_quality_anchor_count=")
    ]
    fallback = [
        token
        for token in command
        if token.startswith("main.eds_config.qd_degenerate_fallback_policy=")
    ]
    assert anchor == ["main.eds_config.qd_global_quality_anchor_count=1"]
    assert fallback == ["main.eds_config.qd_degenerate_fallback_policy=none"]
    keys = [token.split("=", 1)[0].lstrip("+") for token in command if "=" in token]
    assert len(keys) == len(set(keys))
    assert runner.contains_credential(command) is False


def _candidate_metric(*, rescued: bool = True, **updates):
    sparse = {"0": 0 if rescued else 2, "1": 15 if rescued else 13}
    total = {"0": 1 if rescued else 3, "1": 15 if rescued else 13}
    return {
        "task_id": 3,
        "qd_archive_enabled": True,
        "qd_archive_active_for_chunk": True,
        "qd_degenerate_fallback_policy": "none",
        "qd_degenerate_fallback_used": False,
        "qd_global_quality_anchor_count": 1,
        "qd_global_quality_anchor_activation_count": 10,
        "qd_global_quality_anchor_rescue_count": 10 if rescued else 0,
        "qd_global_quality_anchor_cell_by_iter": [0] * 10,
        "qd_global_quality_anchor_fingerprint_by_iter": ["abc"] * 10,
        "qd_global_quality_anchor_rescued_by_iter": [rescued] * 10,
        "qd_sparse_parent_slots_by_cell_by_iter": [sparse] * 10,
        "qd_parent_slots_by_cell_by_iter": [total] * 10,
        "parent_count_by_source": {
            "elite": 0,
            "anchor_offspring": 0,
            "weighted_offspring": 0,
            "qd_global_quality_anchor_offspring": 10,
            "qd_archive_offspring": 150,
        },
        "search_evaluation_count": 176,
        "qd_evaluation_count": 176,
        "score_call_count": 11,
        "selected_chunk_population_source": "qd_archive",
        "qd_selected_action_fingerprint": "final",
        "qd_global_best_action_fingerprint": "final",
        "qd_accounting_violation_count": 0,
        "qd_elite_monotonicity_violation_count": 0,
        "qd_final_selection_mismatch_count": 0,
        "nonfinite_count": 0,
        "action_mask_violation_max": 0.0,
        "gripper_qpos_violation_count": 0,
        **updates,
    }


def test_candidate_metric_gate_accepts_complete_anchor_and_real_rescue():
    result = runner.candidate_metric_gate([_candidate_metric()])

    assert result["passed"] is True
    assert result["activation_count"] == 10
    assert result["rescue_count"] == 10
    assert result["failures"] == []


@pytest.mark.parametrize(
    ("updates", "match"),
    [
        ({"qd_global_quality_anchor_count": 0}, "configured count"),
        ({"qd_global_quality_anchor_activation_count": 9}, "activation"),
        ({"search_evaluation_count": 175}, "search/call"),
        ({"qd_degenerate_fallback_used": True}, "fallback"),
        ({"qd_parent_slots_by_cell_by_iter": [{"0": 1}] * 10}, "total slots"),
    ],
)
def test_candidate_metric_gate_fails_closed(updates, match):
    result = runner.candidate_metric_gate([_candidate_metric(**updates)])

    assert result["passed"] is False
    assert any(match in failure for failure in result["failures"])


def test_candidate_metric_gate_requires_at_least_one_rescue():
    result = runner.candidate_metric_gate([_candidate_metric(rescued=False)])

    assert result["passed"] is False
    assert any("no real rescue" in failure for failure in result["failures"])


def test_control_metric_gate_preserves_qd_off_contract():
    valid = {
        "qd_archive_enabled": False,
        "qd_archive_active_for_chunk": False,
        "qd_degenerate_fallback_used": False,
        "search_evaluation_count": 176,
        "score_call_count": 11,
        "qd_evaluation_count": 0,
        "qd_selected_action_fingerprint": None,
        "nonfinite_count": 0,
        "action_mask_violation_max": 0.0,
        "gripper_qpos_violation_count": 0,
    }
    assert runner.control_metric_gate([valid])["passed"] is True
    assert runner.control_metric_gate([dict(valid, qd_archive_enabled=True)])["passed"] is False


def test_fresh_attempt_ledger_reserves_exact_ids_67_to_72(tmp_path):
    jobs = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)
    records = []
    for job in jobs:
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True):
            records.append(
                {
                    "phase": runner.MECHANISM_LEVEL,
                    "formal_label": job["formal_label"],
                    "task_id": task,
                    "episode_seed": seed,
                    "config_fingerprint": "fp",
                    "code_state_sha256": "code",
                }
            )
    ledger = tmp_path / "ledger.jsonl"
    reserved = runner.reserve_attempts(ledger, records)
    assert [row["attempt_id"] for row in reserved] == list(range(67, 73))
    state = runner.append_dispatch_event(ledger, [67, 68, 69, 70, 71, 72], [0, 1])
    assert state["dispatched_attempt_ids"] == list(range(67, 73))
    with pytest.raises(RuntimeError, match="already contains"):
        runner.reserve_attempts(ledger, records)


def test_exact_cell_recovery_aborts_initial_dispatch_and_reserves_73_to_78(
    tmp_path, monkeypatch
):
    jobs = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)
    records = []
    for job in jobs:
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True):
            records.append(
                {
                    "phase": runner.MECHANISM_LEVEL,
                    "formal_label": job["formal_label"],
                    "task_id": task,
                    "episode_seed": seed,
                    "config_fingerprint": "fp",
                    "code_state_sha256": "initial",
                }
            )
    ledger = tmp_path / "ledger.jsonl"
    runner.reserve_attempts(ledger, records)
    runner.append_dispatch_event(ledger, list(range(67, 73)), [0, 1])
    monkeypatch.setattr(runner, "INITIAL_LEDGER_SHA256", runner.sha256_path(ledger))

    state = runner.prepare_recovery_ledger(ledger)
    assert state["aborted_attempt_ids"] == list(range(67, 73))
    assert state["active_dispatched_attempt_ids"] == []

    recovery = [dict(row, code_state_sha256="repaired") for row in records]
    reserved = runner.reserve_attempts(
        ledger,
        recovery,
        recovery_of_attempt_ids=list(range(67, 73)),
    )
    assert [row["attempt_id"] for row in reserved] == list(range(73, 79))
    assert [row["recovery_of_attempt_id"] for row in reserved] == list(range(67, 73))
    state = runner.append_dispatch_event(ledger, list(range(73, 79)), [2, 3])
    assert state["active_dispatched_attempt_ids"] == list(range(73, 79))
    with pytest.raises(RuntimeError, match="already been reserved"):
        runner.reserve_attempts(
            ledger,
            recovery,
            recovery_of_attempt_ids=list(range(67, 73)),
        )


def test_configure_base_uses_audited_offline_dinov2_seed():
    with runner.configured_base():
        assert runner.base.P2_TORCH_HUB_SEED == runner.DINOV2_TORCH_HUB_SEED
        assert (runner.base.P2_TORCH_HUB_SEED / "facebookresearch_dinov2_main/hubconf.py").is_file()
        assert (runner.base.P2_TORCH_HUB_SEED / "checkpoints/dinov2_vitb14_pretrain.pth").is_file()


def test_task_retention_reports_gained_lost_and_gap():
    summary = runner.task_success_summary(
        {"3": "success", "8": "fail", "9": "fail"},
        {"3": "success", "8": "success", "9": "fail"},
    )
    assert summary["control_success_tasks"] == [3]
    assert summary["candidate_success_tasks"] == [3, 8]
    assert summary["gained_tasks"] == [8]
    assert summary["lost_tasks"] == []
    assert summary["candidate_success_count"] == 2
    assert summary["gap_to_five"] == 3


def test_run_stops_at_manifest_before_credential_or_admission(monkeypatch):
    monkeypatch.setattr(
        runner,
        "validate_manifest",
        lambda: (_ for _ in ()).throw(RuntimeError("manifest blocked")),
    )
    monkeypatch.setattr(
        runner,
        "validate_credential",
        lambda: pytest.fail("credential checked before manifest"),
    )
    monkeypatch.setattr(
        runner,
        "admit_gpus",
        lambda **kwargs: pytest.fail("GPU admission before manifest"),
    )
    with pytest.raises(RuntimeError, match="manifest blocked"):
        runner.run_mechanism(gpus="auto", timeout_seconds=10)


def test_manifest_payload_binds_anchor_matrix_budget_and_forbids_formal(monkeypatch):
    monkeypatch.setattr(runner, "current_provenance", lambda: {"code_commit": "abc"})
    monkeypatch.setattr(runner, "source_fingerprints", lambda: {"core": "hash"})
    monkeypatch.setattr(
        runner, "checkpoint_fingerprint", lambda: {"aggregate_sha256": "checkpoint"}
    )
    monkeypatch.setattr(
        runner, "libero_input_fingerprint", lambda: {"aggregate_sha256": "libero"}
    )
    monkeypatch.setattr(
        runner, "runtime_cache_fingerprint", lambda: {"aggregate_sha256": "cache"}
    )
    monkeypatch.setattr(runner, "gpu_reference", lambda: {"sha256": "gpu"})
    monkeypatch.setattr(
        runner,
        "verified_run_032",
        lambda: {
            "sha256": runner.RUN_032_ARTIFACT_SHA256,
            "scientific_payload_sha256": runner.RUN_032_PAYLOAD_SHA256,
        },
    )
    monkeypatch.setattr(
        runner,
        "verified_incident_evidence",
        lambda: {
            "classification": "pre_episode_dinov2_cache_infrastructure",
            "initial_attempt_ids": list(range(67, 73)),
        },
    )

    payload = runner.build_manifest_payload()

    assert payload["formal_authorized"] is False
    assert payload["mechanism"]["tasks"] == [3, 8, 9]
    assert payload["mechanism"]["seeds"] == [955865, 522754, 845886]
    assert payload["mechanism"]["unique_cells"] == 6
    assert payload["initial_aborted_attempt_ids"] == list(range(67, 73))
    assert payload["expected_global_attempt_ids"] == list(range(73, 79))
    assert payload["prior_global_reservations"] == 66
    assert payload["recovery_reserve"] == 19
    assert payload["recovery_slots_consumed"] == 6
    assert payload["credential_material_present"] is False
    assert runner.contains_credential(payload) is False
