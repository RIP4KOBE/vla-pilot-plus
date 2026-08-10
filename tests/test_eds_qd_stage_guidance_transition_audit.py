from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path


def _load_audit():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eds_qd_stage_guidance_transition_audit.py"
    )
    spec = importlib.util.spec_from_file_location(
        "eds_qd_stage_guidance_transition_audit", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _trace(
    *,
    step=1,
    before="GRASP_VERIFY",
    after="TRANSPORT",
    reason="grasp_confirmed_4_steps",
    stage=2,
    guidance=False,
    confirmed=True,
    changed=True,
    invalidated=True,
    latency=0,
):
    return {
        "schema": "physical-stage-guidance-fsm-trace-v1",
        "episode": 0,
        "task_id": 0,
        "episode_seed": 44,
        "global_step": step,
        "chunk_id": 1,
        "state_before": before,
        "state_after": after,
        "transition_reason": reason,
        "state_changed": changed,
        "current_stage": stage,
        "use_guidance": guidance,
        "grasp_confirmed": confirmed,
        "confirmation_counters": {"grasp": 0, "drop": 0, "release_verify": 0},
        "commit_latency_steps": latency,
        "chunk_invalidated": invalidated,
        "physical_evidence": {
            "executed_gripper_command": 1.0,
            "actual_gripper_qpos": [0.02, -0.02],
            "object_keypoint_position": [0.0, 0.0, 0.03],
            "eef_position": [0.0, 0.0, 0.07],
            "relative_drift_m": 0.0,
            "follow_error_m": 0.0,
            "lift_from_pre_close_m": 0.03,
            "fall_from_transport_peak_m": 0.0,
            "destination_distance_m": 0.3,
            "in_destination_region": False,
            "environment_success": False,
        },
        "vlm_advisory": {"query_status": "ok", "control_authority": False},
    }


def test_fsm_mechanism_gate_passes_structured_physical_transition():
    audit = _load_audit()

    gate = audit.fsm_mechanism_gate([_trace()], test_evidence_passed=True)

    assert gate["passed"] is True
    assert gate["guidance_off_without_grasp_confirmed_count"] == 0
    assert gate["illegal_stage_guidance_combination_count"] == 0
    assert gate["transition_evidence_coverage"] == 1.0
    assert gate["vlm_shadow_replay"]["passed"] is True
    assert gate["drop_commit_latency"] == "N/A"
    assert gate["regrasp_commit_latency"] == "N/A"


def test_fsm_mechanism_gate_rejects_unconfirmed_off_illegal_combo_and_missing_evidence():
    audit = _load_audit()
    row = _trace(
        after="TRANSPORT",
        stage=1,
        guidance=False,
        confirmed=False,
        reason="",
        invalidated=False,
        latency=2,
    )
    row["physical_evidence"] = {}
    row["vlm_advisory"]["control_authority"] = True

    gate = audit.fsm_mechanism_gate([row], test_evidence_passed=False)

    assert gate["passed"] is False
    assert gate["guidance_off_without_grasp_confirmed_count"] == 1
    assert gate["illegal_stage_guidance_combination_count"] == 1
    assert gate["transition_evidence_coverage"] == 0.0
    assert gate["transition_without_chunk_invalidation_count"] == 1
    assert gate["vlm_shadow_replay"]["passed"] is False


def test_drop_and_regrasp_latency_are_measured_not_fabricated():
    audit = _load_audit()
    drop = _trace(
        step=10,
        before="TRANSPORT",
        after="RECOVERY",
        reason="drop_confirmed_3_steps",
        stage=1,
        guidance=True,
        confirmed=False,
        latency=1,
    )
    verify = _trace(
        step=12,
        before="RECOVERY",
        after="GRASP_VERIFY",
        reason="recovery_close_executed_grasp_candidate",
        stage=1,
        guidance=True,
        confirmed=False,
    )
    regrasp = _trace(step=16, latency=1)

    gate = audit.fsm_mechanism_gate(
        [drop, verify, regrasp], test_evidence_passed=True
    )

    assert gate["passed"] is True
    assert gate["drop_commit_latency"]["event_count"] == 1
    assert gate["drop_commit_latency"]["max_steps"] == 1
    assert gate["regrasp_commit_latency"]["event_count"] == 1
    assert gate["regrasp_commit_latency"]["max_steps"] == 1


def _job(label, round_id, mode, successes, *, valid=True, safety=True, mechanism=True):
    outcomes = {
        str(task): ("success" if task in successes else "fail")
        for task in range(10)
    }
    return {
        "label": label,
        "round": round_id,
        "transition_mode": mode,
        "valid": valid,
        "success_count": len(successes),
        "success_tasks": sorted(successes),
        "task_outcomes": outcomes,
        "safety_gate": {"passed": safety},
        "fsm_mechanism_gate": (
            {"passed": mechanism} if mode == "physical_fsm_v1" else {"passed": True, "applicable": False}
        ),
    }


def test_paired_analysis_applies_round_mean_mechanism_safety_and_adoption_gates():
    audit = _load_audit()
    jobs = [
        _job("legacy-r0", 0, "legacy_vlm", {0, 1, 2, 3}),
        _job("fsm-r0", 0, "physical_fsm_v1", {0, 1, 2, 3, 4, 5}),
        _job("legacy-r1", 1, "legacy_vlm", {0, 1, 2, 3, 4}),
        _job("fsm-r1", 1, "physical_fsm_v1", {0, 1, 2, 3, 4}),
    ]

    analysis = audit.paired_gate_analysis(jobs)

    assert analysis["rounds"]["0"]["gained_tasks"] == [4, 5]
    assert analysis["rounds"]["0"]["lost_tasks"] == []
    assert analysis["fsm_total_success_count"] == 11
    assert analysis["fsm_mean_success_rate"] == 0.55
    assert analysis["mean_gate_passed"] is True
    assert analysis["adoption_passed"] is True
    assert analysis["decision"] == "adopt_physical_fsm_v1"


def test_mean_gate_failure_is_negative_result_without_extra_experiments():
    audit = _load_audit()
    jobs = [
        _job("legacy-r0", 0, "legacy_vlm", {0, 1}),
        _job("fsm-r0", 0, "physical_fsm_v1", {0, 1, 2, 3}),
        _job("legacy-r1", 1, "legacy_vlm", {0, 1}),
        _job("fsm-r1", 1, "physical_fsm_v1", {0, 1, 2, 3}),
    ]

    analysis = audit.paired_gate_analysis(jobs)

    assert analysis["fsm_mean_success_rate"] == 0.4
    assert analysis["mean_gate_passed"] is False
    assert analysis["adoption_passed"] is False
    assert analysis["decision"] == "negative_result_keep_legacy"
    assert analysis["additional_experiments_authorized"] is False


def test_freeze_text_and_decision_manifest_are_immutable(tmp_path, monkeypatch):
    audit = _load_audit()
    report = tmp_path / "final_report.md"
    decision = tmp_path / "decision_manifest.json"
    monkeypatch.setattr(audit, "REPORT_PATH", report)
    monkeypatch.setattr(audit, "DECISION_PATH", decision)

    report_result = audit.freeze_report("# report\n")
    payload = audit.freeze_decision_manifest(
        {"decision": "negative_result_keep_legacy", "report": report_result}
    )

    assert payload["decision"] == "negative_result_keep_legacy"
    assert stat.S_IMODE(report.stat().st_mode) == 0o444
    assert stat.S_IMODE(decision.stat().st_mode) == 0o444
    assert audit.verify_decision_manifest()["decision"] == payload["decision"]
