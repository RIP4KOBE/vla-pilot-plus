from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "eds_qd_autoresearch_v3_dev_runner.py"
)
SPEC = importlib.util.spec_from_file_location(
    "eds_qd_autoresearch_v3_dev_runner",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_dev_a_matrix_profiles_and_budget_are_exact():
    control, candidate = runner.profiles()
    jobs = runner.build_jobs(runner.DEV_A_LEVEL, bind=False)

    assert runner.DEV_A_TASKS == [0, 1, 2, 4, 6, 7]
    assert runner.DEV_A_SEEDS == [307995, 262892, 731741, 14859, 648306, 960581]
    assert runner.EXPECTED_GLOBAL_ATTEMPT_IDS == list(range(79, 91))
    assert control["label"] == "p2_stage_on_abs_rbf_control"
    assert control["qd_archive_mode"] == "none"
    assert candidate["label"] == "eds_qd_global_quality_anchor_v1"
    assert candidate["qd_archive_mode"] == "grid_archive"
    assert candidate["qd_parent_sampling"] == "sparse_priority"
    assert candidate["qd_bounds_update_policy"] == "causal_envelope_v1"
    assert candidate["qd_global_quality_anchor_count"] == 1
    assert candidate["qd_degenerate_fallback_policy"] == "none"
    assert len(jobs) == 2
    assert all(job["episodes"] == 6 for job in jobs)


def test_candidate_command_binds_only_frozen_anchor_and_seed_schedule():
    candidate = runner.build_jobs(runner.DEV_A_LEVEL, bind=False)[1]
    command = runner.build_main_command(candidate)

    assert "main.eds_config.qd_global_quality_anchor_count=1" in command
    assert "main.eds_config.qd_degenerate_fallback_policy=none" in command
    assert "main.episode_seed_schedule=[307995,262892,731741,14859,648306,960581]" in command
    keys = [token.split("=", 1)[0].lstrip("+") for token in command if "=" in token]
    assert len(keys) == len(set(keys))
    assert runner.contains_credential(command) is False


def test_task_gate_accepts_only_target_directed_dev_a_pass():
    summary = runner.mechanism.task_success_summary(
        {"0": "success", "1": "fail", "2": "fail", "4": "fail", "6": "fail", "7": "fail"},
        {"0": "success", "1": "success", "2": "success", "4": "fail", "6": "fail", "7": "fail"},
    )
    gate = runner.dev_a_task_gate(summary)

    assert summary["candidate_success_count"] == 3
    assert summary["candidate_minus_control"] == 2
    assert summary["lost_tasks"] == []
    assert gate == {"passed": True, "failures": []}


@pytest.mark.parametrize(
    ("control", "candidate", "match"),
    [
        ({}, {"0": "success", "1": "success"}, "below 3/6"),
        (
            {"0": "success", "1": "success", "2": "success"},
            {"0": "success", "1": "success", "2": "success"},
            "below +1",
        ),
        (
            {"0": "success"},
            {"1": "success", "2": "success", "4": "success"},
            "lost one",
        ),
    ],
)
def test_task_gate_fails_closed(control, candidate, match):
    summary = runner.mechanism.task_success_summary(control, candidate)
    gate = runner.dev_a_task_gate(summary)

    assert gate["passed"] is False
    assert any(match in failure for failure in gate["failures"])


def _attempt_records():
    rows = []
    for job in runner.build_jobs(runner.DEV_A_LEVEL, bind=False):
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True):
            rows.append(
                {
                    "phase": runner.DEV_A_LEVEL,
                    "formal_label": job["formal_label"],
                    "task_id": task,
                    "episode_seed": seed,
                    "config_fingerprint": "fp",
                    "code_state_sha256": "code",
                }
            )
    return rows


def test_fresh_ledger_reserves_and_dispatches_exact_ids_79_to_90(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    reserved = runner.reserve_attempts(ledger, _attempt_records())
    assert [row["attempt_id"] for row in reserved] == list(range(79, 91))
    state = runner.append_dispatch_event(ledger, list(range(79, 91)), [0, 1])
    assert state["dispatched_attempt_ids"] == list(range(79, 91))
    with pytest.raises(RuntimeError, match="already exists"):
        runner.reserve_attempts(ledger, _attempt_records())


def test_configure_base_uses_offline_dino_and_dev_level():
    with runner.configured_base():
        assert runner.DEV_A_LEVEL in runner.base.P2_LEVELS
        assert runner.base.P2_TORCH_HUB_SEED == runner.DINOV2_TORCH_HUB_SEED
        assert (runner.base.P2_TORCH_HUB_SEED / "facebookresearch_dinov2_main/hubconf.py").is_file()


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
        runner.run_dev_a(gpus="auto", timeout_seconds=10)


def test_manifest_payload_binds_dev_a_gates_and_forbids_later_splits(monkeypatch):
    monkeypatch.setattr(runner, "current_provenance", lambda: {"code_commit": "abc"})
    monkeypatch.setattr(runner, "source_fingerprints", lambda: {"core": "hash"})
    monkeypatch.setattr(runner, "checkpoint_fingerprint", lambda: {"aggregate_sha256": "checkpoint"})
    monkeypatch.setattr(runner, "libero_input_fingerprint", lambda: {"aggregate_sha256": "libero"})
    monkeypatch.setattr(runner, "runtime_cache_fingerprint", lambda: {"aggregate_sha256": "cache"})
    monkeypatch.setattr(runner, "dinov2_seed_fingerprint", lambda: {"aggregate_sha256": "dino"})
    monkeypatch.setattr(runner, "gpu_reference", lambda: {"sha256": "gpu"})
    monkeypatch.setattr(
        runner,
        "verified_run_033",
        lambda: {"sha256": runner.RUN_033_AUDIT_SHA256, "hard_failures": []},
    )

    payload = runner.build_manifest_payload()

    assert payload["validation_authorized"] is False
    assert payload["formal_authorized"] is False
    assert payload["dev_a"]["tasks"] == runner.DEV_A_TASKS
    assert payload["dev_a"]["seeds"] == runner.DEV_A_SEEDS
    assert payload["dev_a"]["candidate_minimum_successes"] == 3
    assert payload["dev_a"]["candidate_minimum_delta_over_control"] == 1
    assert payload["dev_a"]["lost_control_success_tasks_allowed"] == 0
    assert payload["expected_global_attempt_ids"] == list(range(79, 91))
    assert runner.contains_credential(payload) is False


def test_actual_run_033_parent_is_immutable_clean_pass():
    parent = runner.verified_run_033()

    assert parent["sha256"] == runner.RUN_033_AUDIT_SHA256
    assert parent["candidate_success_tasks"] == [9]
    assert parent["hard_failures"] == []
