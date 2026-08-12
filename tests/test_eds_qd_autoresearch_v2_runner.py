from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "eds_qd_autoresearch_v2_runner.py"
)
SPEC = importlib.util.spec_from_file_location(
    "eds_qd_autoresearch_v2_runner",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_mechanism_matrix_and_profiles_are_exact_and_no_formal():
    profiles = runner.profiles()
    jobs = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)

    assert runner.MECHANISM_TASKS == [2, 3, 9]
    assert runner.MECHANISM_SEEDS == [932032, 615132, 718536]
    assert len(profiles) == 2
    assert profiles[0]["label"] == "p2_stage_on_abs_rbf_control"
    assert profiles[0]["qd_archive_mode"] == "none"
    assert profiles[0]["qd_degenerate_fallback_policy"] == "none"
    assert profiles[1]["label"] == "eds_qd_reward_degenerate_control_fallback_v1"
    assert profiles[1]["qd_archive_mode"] == "grid_archive"
    assert profiles[1]["qd_parent_sampling"] == "sparse_priority"
    assert profiles[1]["qd_bounds_update_policy"] == "causal_envelope_v1"
    assert profiles[1]["qd_degenerate_fallback_policy"] == "control_v1"
    assert len(jobs) == 2
    assert all(job["episodes"] == 3 for job in jobs)
    assert all(job["task_ids_filter"] == [2, 3, 9] for job in jobs)
    assert all(job["episode_seeds"] == [932032, 615132, 718536] for job in jobs)
    assert all(job["max_chunks"] == 16 for job in jobs)
    assert not hasattr(runner, "FORMAL_LEVEL")
    assert runner.MANIFEST_V1_PATH.name == "mechanism_manifest.json"
    assert runner.MANIFEST_V2_PATH.name == "mechanism_manifest.v2.json"
    assert runner.MANIFEST_PATH.name == "mechanism_manifest.v3.json"


def test_command_contains_candidate_guard_once_and_is_secret_free():
    candidate = runner.build_jobs(runner.MECHANISM_LEVEL, bind=False)[1]
    command = runner.build_main_command(candidate)

    guard = [
        token
        for token in command
        if token.startswith("main.eds_config.qd_degenerate_fallback_policy=")
    ]
    assert guard == ["main.eds_config.qd_degenerate_fallback_policy=control_v1"]
    keys = [token.split("=", 1)[0].lstrip("+") for token in command if "=" in token]
    assert len(keys) == len(set(keys))
    assert runner.contains_credential(command) is False


def test_profile_fingerprints_bind_mechanism_matrix():
    control, candidate = runner.profiles()

    assert runner.profile_fingerprint(control) != runner.profile_fingerprint(candidate)
    assert runner.profile_fingerprint(control) == runner.profile_fingerprint(
        dict(control)
    )


def _base_metric(**updates):
    return {
        "qd_archive_enabled": True,
        "qd_archive_active_for_chunk": True,
        "qd_degenerate_fallback_policy": "control_v1",
        "qd_degenerate_fallback_used": False,
        "qd_degenerate_fallback_reason": None,
        "qd_degenerate_reward_value": None,
        "search_evaluation_count": 176,
        "score_call_count": 11,
        "qd_evaluation_count": 176,
        "selected_chunk_population_source": "qd_archive",
        "qd_selected_action_fingerprint": "abc",
        "qd_global_best_action_fingerprint": "abc",
        "qd_accounting_violation_count": 0,
        "qd_elite_monotonicity_violation_count": 0,
        "qd_final_selection_mismatch_count": 0,
        "nonfinite_count": 0,
        "action_mask_violation_max": 0.0,
        "gripper_qpos_violation_count": 0,
        **updates,
    }


def test_candidate_metric_semantics_accept_fallback_and_active_records():
    active = _base_metric()
    fallback = _base_metric(
        qd_archive_active_for_chunk=False,
        qd_degenerate_fallback_used=True,
        qd_degenerate_fallback_reason="initial_rewards_exactly_equal",
        qd_degenerate_reward_value=0.0,
        qd_evaluation_count=0,
        selected_chunk_population_source="fresh",
        qd_selected_action_fingerprint=None,
        qd_global_best_action_fingerprint=None,
    )

    result = runner.candidate_metric_gate([fallback, active])

    assert result["passed"] is True
    assert result["fallback_record_count"] == 1
    assert result["active_qd_record_count"] == 1
    assert result["failures"] == []


@pytest.mark.parametrize(
    "update,match",
    [
        ({"search_evaluation_count": 175}, "search/call"),
        ({"qd_degenerate_fallback_policy": "none"}, "policy"),
        (
            {
                "qd_degenerate_fallback_used": True,
                "qd_archive_active_for_chunk": True,
            },
            "fallback archive",
        ),
        ({"qd_selected_action_fingerprint": None}, "active QD fingerprint"),
    ],
)
def test_candidate_metric_semantics_fail_closed(update, match):
    result = runner.candidate_metric_gate([_base_metric(**update)])

    assert result["passed"] is False
    assert any(match in failure for failure in result["failures"])


def test_control_metric_semantics_require_qd_off_and_176_11():
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
    invalid = dict(valid, qd_archive_enabled=True)
    assert runner.control_metric_gate([invalid])["passed"] is False


def test_global_attempt_reservation_starts_at_55_and_caps_globally(tmp_path):
    records = [
        {
            "phase": runner.MECHANISM_LEVEL,
            "label": f"job-{index}",
            "formal_label": f"profile-{index // 3}",
            "task_id": [2, 3, 9][index % 3],
            "episode_seed": [932032, 615132, 718536][index % 3],
            "config_fingerprint": f"fingerprint-{index // 3}",
            "code_state_sha256": "code",
        }
        for index in range(6)
    ]

    ledger = tmp_path / "ledger.jsonl"
    initial = [
        {"attempt_id": 55 + index, "record_type": "episode_attempt", **record}
        for index, record in enumerate(records)
    ]
    ledger.write_text(
        "".join(runner.canonical(record) + "\n" for record in initial),
        encoding="utf-8",
    )
    state = runner.prepare_recovery_ledger(ledger)
    assert state["void_attempt_ids"] == list(range(55, 61))

    reserved = runner.reserve_attempts(
        ledger,
        records,
        recovery_of_attempt_ids=list(range(55, 61)),
    )

    assert [record["attempt_id"] for record in reserved] == list(range(61, 67))
    assert [record["recovery_of_attempt_id"] for record in reserved] == list(
        range(55, 61)
    )
    dispatched = runner.append_global_ledger_event(
        ledger,
        {
            "record_type": "phase_dispatch",
            "attempt_ids": list(range(61, 67)),
        },
    )
    assert dispatched["dispatched_attempt_ids"] == list(range(61, 67))


def test_run_stops_at_manifest_gate_before_credential_or_admission(monkeypatch):
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
        lambda **kwargs: pytest.fail("GPU admission ran before manifest"),
    )

    with pytest.raises(RuntimeError, match="manifest blocked"):
        runner.run_mechanism(gpus="auto", timeout_seconds=10)


def test_manifest_payload_forbids_formal_and_binds_six_cells(monkeypatch):
    monkeypatch.setattr(
        runner,
        "current_provenance",
        lambda: {
            "code_commit": "abc",
            "recovery_protocol_commit": runner.RECOVERY_PROTOCOL_COMMIT,
        },
    )
    monkeypatch.setattr(runner, "source_fingerprints", lambda: {"core": "hash"})
    monkeypatch.setattr(runner, "checkpoint_fingerprint", lambda: {"aggregate_sha256": "c"})
    monkeypatch.setattr(runner, "libero_input_fingerprint", lambda: {"aggregate_sha256": "l"})
    monkeypatch.setattr(runner, "runtime_cache_fingerprint", lambda: {"aggregate_sha256": "r"})
    monkeypatch.setattr(runner, "gpu_reference", lambda: {"sha256": "g"})
    monkeypatch.setattr(
        runner,
        "_verified_parent_manifest",
        lambda: {
            "path": "/owned/mechanism_manifest.json",
            "sha256": runner.MANIFEST_V1_SHA256,
            "payload_sha256": "parent-payload",
        },
    )
    monkeypatch.setattr(
        runner,
        "_verified_parent_manifest_v2",
        lambda: {
            "path": "/owned/mechanism_manifest.v2.json",
            "sha256": runner.MANIFEST_V2_SHA256,
            "payload_sha256": "parent-v2-payload",
        },
    )

    payload = runner.build_manifest_payload()

    assert payload["formal_authorized"] is False
    assert payload["schema"] == "eds-qd-autoresearch-v2-mechanism-manifest-v3"
    assert payload["parent_manifest_v1"]["sha256"] == runner.MANIFEST_V1_SHA256
    assert payload["parent_manifest_v2"]["sha256"] == runner.MANIFEST_V2_SHA256
    assert payload["provenance"]["recovery_protocol_commit"] == (
        runner.RECOVERY_PROTOCOL_COMMIT
    )
    assert payload["mechanism"]["unique_cells"] == 6
    assert payload["mechanism"]["tasks"] == [2, 3, 9]
    assert payload["expected_global_attempt_ids"] == list(range(61, 67))
    assert payload["void_pre_dispatch_attempt_ids"] == list(range(55, 61))
    assert payload["prior_global_reservations"] == 54
    assert payload["global_reservation_cap"] == 143
    assert payload["payload_sha256"]


def test_parent_manifest_v1_is_immutable_and_exact(monkeypatch, tmp_path):
    parent = tmp_path / "mechanism_manifest.json"
    parent.write_text(
        '{"schema":"eds-qd-autoresearch-v2-mechanism-manifest-v1",'
        '"formal_authorized":false,"payload_sha256":"parent"}\n',
        encoding="utf-8",
    )
    parent.chmod(0o444)
    monkeypatch.setattr(runner, "MANIFEST_V1_PATH", parent)
    monkeypatch.setattr(runner, "MANIFEST_V1_SHA256", runner.sha256_path(parent))

    verified = runner._verified_parent_manifest()

    assert verified["sha256"] == runner.sha256_path(parent)
    assert verified["payload_sha256"] == "parent"
    parent.chmod(0o644)
    with pytest.raises(RuntimeError, match="v1 identity"):
        runner._verified_parent_manifest()
