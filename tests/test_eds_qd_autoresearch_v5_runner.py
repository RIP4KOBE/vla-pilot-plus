from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "eds_qd_autoresearch_v5_runner.py"
)
SPEC = importlib.util.spec_from_file_location(
    "eds_qd_autoresearch_v5_runner", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_matrix_profiles_and_budget_are_exact():
    control, candidate = runner.profiles()
    jobs = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)

    assert runner.MECHANISM_TASKS == [7, 5]
    assert runner.MECHANISM_SEEDS == [87603, 666847]
    assert runner.EXPECTED_GLOBAL_ATTEMPT_IDS == list(range(91, 95))
    assert control["label"] == "p2_stage_on_abs_rbf_control"
    assert control["qd_archive_mode"] == "none"
    assert control["qd_secondary_lane_mode"] == "none"
    assert candidate["label"] == "eds_qd_protected_quality_secondary_v1"
    assert candidate["qd_archive_mode"] == "grid_archive"
    assert candidate["qd_parent_sampling"] == "sparse_priority"
    assert candidate["qd_bounds_update_policy"] == "causal_envelope_v1"
    assert candidate["qd_global_quality_anchor_count"] == 1
    assert candidate["qd_degenerate_fallback_policy"] == "none"
    assert candidate["qd_secondary_lane_mode"] == "protected_reward_v1"
    assert len(jobs) == 2
    assert all(job["episodes"] == 2 for job in jobs)


def test_candidate_command_binds_secondary_mode_and_seed_schedule():
    candidate = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)[1]
    command = runner.build_main_command(candidate)

    assert "main.eds_config.qd_secondary_lane_mode=protected_reward_v1" in command
    assert "main.eds_config.qd_global_quality_anchor_count=1" in command
    assert runner.frozen_task_seed_pairs() == [(7, 87603), (5, 666847)]
    assert runner.backend_execution_pairs() == [(5, 666847), (7, 87603)]
    assert "main.episode_seed_schedule=[666847,87603]" in command
    keys = [token.split("=", 1)[0].lstrip("+") for token in command if "=" in token]
    assert len(keys) == len(set(keys))
    assert runner.contains_credential(command) is False


def test_task_gate_requires_noninferiority_and_retention():
    passed = runner.mechanism_task_gate(
        runner.mechanism.task_success_summary(
            {"7": "fail", "5": "success"}, {"7": "success", "5": "success"}
        )
    )
    lost = runner.mechanism_task_gate(
        runner.mechanism.task_success_summary(
            {"7": "success", "5": "fail"}, {"7": "fail", "5": "success"}
        )
    )
    below = runner.mechanism_task_gate(
        runner.mechanism.task_success_summary(
            {"7": "success", "5": "fail"}, {"7": "fail", "5": "fail"}
        )
    )

    assert passed == {"passed": True, "failures": []}
    assert lost["passed"] is False
    assert below["passed"] is False


def _candidate_record(task_id=7):
    secondary_counts = [7] * 10
    secondary_slots = [{"0": 7} for _ in range(10)]
    return {
        "episode": 0,
        "task_id": task_id,
        "global_step": 0,
        "search_evaluation_count": 176,
        "score_call_count": 11,
        "nonfinite_count": 0,
        "action_mask_violation_max": 0.0,
        "gripper_qpos_violation_count": 0,
        "qd_archive_enabled": True,
        "qd_archive_active_for_chunk": True,
        "qd_secondary_lane_mode": "protected_reward_v1",
        "qd_degenerate_fallback_policy": "none",
        "qd_degenerate_fallback_used": False,
        "qd_global_quality_anchor_count": 1,
        "qd_global_quality_anchor_activation_count": 10,
        "qd_sparse_parent_slots_by_cell_by_iter": [{"0": 15} for _ in range(10)],
        "qd_parent_slots_by_cell_by_iter": [{"0": 16} for _ in range(10)],
        "qd_secondary_parent_slots_by_cell_by_iter": secondary_slots,
        "qd_secondary_parent_count_by_iter": secondary_counts,
        "qd_secondary_parent_ratio_by_iter": [7 / 16] * 10,
        "qd_secondary_parent_fingerprints_by_iter": [[f"fp-{i}-{j}" for j in range(7)] for i in range(10)],
        "qd_secondary_occupied_cells_by_iter": [4] * 10,
        "qd_secondary_parent_activation_count": 70,
        "qd_evaluation_count": 176,
        "selected_chunk_population_source": "qd_archive",
        "qd_selected_action_fingerprint": "best",
        "qd_global_best_action_fingerprint": "best",
        "parent_count_by_source": {
            "elite": 0,
            "anchor_offspring": 0,
            "weighted_offspring": 0,
            "qd_global_quality_anchor_offspring": 10,
            "qd_archive_offspring": 80,
            "qd_secondary_lane_offspring": 70,
        },
        "qd_accounting_violation_count": 0,
        "qd_elite_monotonicity_violation_count": 0,
        "qd_secondary_invariant_violation_count": 0,
        "qd_final_selection_mismatch_count": 0,
    }


def test_candidate_metric_gate_requires_secondary_activation_on_both_tasks():
    result = runner.candidate_metric_gate([_candidate_record(7), _candidate_record(5)])
    assert result["passed"] is True
    assert result["secondary_parent_activation_count"] == 140

    broken = _candidate_record(5)
    broken["qd_secondary_parent_count_by_iter"] = [0] * 10
    assert runner.candidate_metric_gate([_candidate_record(7), broken])["passed"] is False


def _attempt_records():
    rows = []
    for job in runner.build_jobs(runner.MECHANISM_LEVEL, bind=False):
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True):
            rows.append(
                {
                    "phase": runner.MECHANISM_LEVEL,
                    "formal_label": job["formal_label"],
                    "task_id": task,
                    "episode_seed": seed,
                    "config_fingerprint": "fp",
                    "code_state_sha256": "code",
                }
            )
    return rows


def test_fresh_ledger_reserves_and_dispatches_exact_ids_91_to_94(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    reserved = runner.reserve_attempts(ledger, _attempt_records())
    assert [row["attempt_id"] for row in reserved] == list(range(91, 95))
    state = runner.append_dispatch_event(ledger, list(range(91, 95)), [0, 1])
    assert state["dispatched_attempt_ids"] == list(range(91, 95))
    state = runner.append_identity_abort_event(ledger)
    assert state["aborted_attempt_ids"] == list(range(91, 95))
    assert state["active_dispatched_attempt_ids"] == []
    assert runner.append_identity_abort_event(ledger) == state
    with pytest.raises(RuntimeError, match="already exists"):
        runner.reserve_attempts(ledger, _attempt_records())


def test_configure_base_uses_offline_dino_and_v5_level():
    with runner.configured_base():
        assert runner.MECHANISM_LEVEL in runner.base.P2_LEVELS
        assert runner.base.P2_TORCH_HUB_SEED == runner.DINOV2_TORCH_HUB_SEED
        assert (
            runner.base.P2_TORCH_HUB_SEED
            / "facebookresearch_dinov2_main/hubconf.py"
        ).is_file()


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


def test_manifest_payload_binds_online_gates_and_forbids_later_splits(monkeypatch):
    monkeypatch.setattr(runner, "current_provenance", lambda: {"code_commit": "abc"})
    monkeypatch.setattr(runner, "source_fingerprints", lambda: {"core": "hash"})
    monkeypatch.setattr(runner, "checkpoint_fingerprint", lambda: {"aggregate_sha256": "checkpoint"})
    monkeypatch.setattr(runner, "libero_input_fingerprint", lambda: {"aggregate_sha256": "libero"})
    monkeypatch.setattr(runner, "runtime_cache_fingerprint", lambda: {"aggregate_sha256": "cache"})
    monkeypatch.setattr(runner, "dinov2_seed_fingerprint", lambda: {"aggregate_sha256": "dino"})
    monkeypatch.setattr(runner, "gpu_reference", lambda: {"sha256": "gpu"})
    monkeypatch.setattr(runner, "verified_run_043", lambda: {"sha256": runner.RUN_043_ARTIFACT_SHA256})

    payload = runner.build_manifest_payload()

    assert payload["dev_a_authorized"] is False
    assert payload["validation_authorized"] is False
    assert payload["formal_authorized"] is False
    assert payload["mechanism"]["tasks"] == runner.MECHANISM_TASKS
    assert payload["mechanism"]["seeds"] == runner.MECHANISM_SEEDS
    assert payload["mechanism"]["candidate_minimum_delta_over_control"] == 0
    assert payload["mechanism"]["secondary_activation_required_per_task"] is True
    assert payload["expected_global_attempt_ids"] == list(range(91, 95))
    assert runner.contains_credential(payload) is False


def test_actual_run_043_parent_is_immutable_clean_pass():
    parent = runner.verified_run_043()
    assert parent["sha256"] == runner.RUN_043_ARTIFACT_SHA256
    assert parent["scientific_payload_sha256"] == runner.RUN_043_PAYLOAD_SHA256
