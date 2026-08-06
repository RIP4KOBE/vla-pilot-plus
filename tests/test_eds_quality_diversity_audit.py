from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
from pathlib import Path

import pytest


def _load_audit():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eds_quality_diversity_audit.py"
    )
    spec = importlib.util.spec_from_file_location(
        "eds_quality_diversity_audit", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit = _load_audit()


def _stream() -> list[dict[str, object]]:
    initial = {
        "iter_idx": -1,
        "descriptors_xy_m": [
            [-0.04, -0.04],
            [0.04, -0.04],
            [-0.04, 0.04],
            [0.04, 0.04],
        ],
        "rewards": [1.0, 2.0, 3.0, 4.0],
        "fingerprints": ["d", "c", "b", "a"],
    }
    child = {
        "iter_idx": 0,
        "descriptors_xy_m": [
            [-0.04, -0.04],
            [-0.03, -0.03],
            [0.04, 0.04],
            [0.03, 0.03],
        ],
        "rewards": [5.0, 4.0, 4.0, 4.0],
        "fingerprints": ["z", "y", "a", "0"],
    }
    return [initial, child]


def _profile(label: str = "candidate") -> dict[str, object]:
    return {
        "label": label,
        "qd_grid_shape": [2, 2],
        "qd_bounds_quantiles": [0.0, 1.0],
        "qd_bounds_expand_fraction": 0.0,
        "qd_min_axis_span_m": 0.08,
        "qd_parent_sampling": "uniform_cells",
    }


def test_shadow_replay_is_deterministic_and_uses_stable_tie_break():
    first = audit.replay_shadow_archive(_stream(), _profile())
    permuted = [
        {
            **record,
            "descriptors_xy_m": list(reversed(record["descriptors_xy_m"])),
            "rewards": list(reversed(record["rewards"])),
            "fingerprints": list(reversed(record["fingerprints"])),
        }
        for record in _stream()
    ]
    second = audit.replay_shadow_archive(permuted, _profile())
    assert first == second
    assert first["evaluation_count"] == 8
    assert first["occupied_cells"] == 4
    assert first["best_reward"] == 5.0
    assert first["archive"]["3"]["fingerprint"] == "0"
    assert first["replacement_count"] == 2


def test_mechanism_comparison_and_frozen_gates():
    control = {
        "success_count": 5,
        "success_tasks": [0, 1, 2, 3, 4],
        "execution_qpos_error_episodes": 0,
        "collision_push_drop_wrong_object": 2,
    }
    candidate = {
        "label": "candidate",
        "valid": True,
        "success_count": 6,
        "success_tasks": [0, 1, 2, 3, 5, 6],
        "execution_qpos_error_episodes": 0,
        "collision_push_drop_wrong_object": 1,
        "nonfinite_count": 0,
        "action_mask_violation_count": 0,
        "qd_fallback_count": 0,
        "mechanism_hard": {"passed": True, "failures": []},
        "mechanism_comparison": {
            "paired_count": 4,
            "normalized_final_coverage_delta_median": 0.10,
            "endpoint_xy_spread_ratio_median": 0.95,
            "archive_best_reward_delta_median": 0.01,
            "replacement_active_chunk_ratio": 0.50,
            "descriptor_overflow_ratio_p95": 0.20,
        },
    }
    gates = audit.evaluate_candidate_gates(candidate, control)
    assert gates["task"]["passed"] is True
    assert gates["mechanism_claim"]["passed"] is True
    assert gates["safety"]["passed"] is True
    assert gates["all_passed"] is True
    assert gates["paired"]["gained_tasks"] == [5, 6]
    assert gates["paired"]["lost_tasks"] == [4]


def test_ranking_uses_all_ten_frozen_keys():
    common = {
        "valid": True,
        "success_count": 5,
        "control_task_retention": 4,
        "paired_gained_minus_lost": 0,
        "execution_qpos_error_episodes": 0,
        "collision_push_drop_wrong_object": 1,
        "normalized_coverage_gain": 0.1,
        "endpoint_xy_spread_retention": 1.0,
        "archive_best_reward_delta": 0.0,
        "selection_latency_p95_s": 1.0,
    }
    candidates = [
        {**common, "label": "z", "success_count": 6},
        {**common, "label": "a", "success_count": 6},
        {**common, "label": "b", "success_count": 5},
    ]
    ranked = audit.rank_candidates(candidates)
    assert [row["label"] for row in ranked] == ["a", "z", "b"]
    assert [row["rank"] for row in ranked] == [1, 2, 3]


def test_decision_manifest_is_exclusive_readonly_and_has_sidecar(tmp_path: Path):
    path = tmp_path / "decision.json"
    frozen = audit.freeze_decision_manifest({"decision": "keep_control"}, path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert frozen["canonical_manifest_checksum"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    assert path.with_suffix(path.suffix + ".sha256").read_text().split()[0] == expected
    assert audit.verify_decision_manifest(path)["decision"] == "keep_control"
    with pytest.raises(FileExistsError):
        audit.freeze_decision_manifest({}, path)


def test_manifest_rejects_credentials(tmp_path: Path):
    with pytest.raises(ValueError, match="credential"):
        audit.freeze_decision_manifest(
            {"value": "authorization: bearer forbidden"},
            tmp_path / "decision.json",
        )


def test_qd_metric_hard_gate_checks_accounting_and_allocations():
    metric = {
        "episode": 0,
        "global_step": 8,
        "qd_archive_enabled": True,
        "qd_evaluation_count": 176,
        "score_call_count": 11,
        "qd_initial_accounting": {
            "insertions": 4,
            "replacements": 0,
            "rejections": 12,
        },
        "qd_archive_insertions_by_iter": [0] * 10,
        "qd_archive_replacements_by_iter": [1] * 10,
        "qd_archive_rejections_by_iter": [15] * 10,
        "qd_accounting_violation_count": 0,
        "qd_elite_monotonicity_violation_count": 0,
        "qd_final_selection_mismatch_count": 0,
        "qd_fallback_used": False,
        "qd_parent_slots_by_cell_by_iter": [{"0": 4, "1": 4, "2": 4, "3": 4}] * 10,
        "qd_parent_weights_by_cell_by_iter": [{"0": 1.0, "1": 1.0, "2": 1.0, "3": 1.0}] * 10,
    }
    result = audit.qd_mechanism_hard_gate([metric], _profile())
    assert result["passed"] is True
    broken = dict(metric)
    broken["qd_archive_rejections_by_iter"] = [14] * 10
    result = audit.qd_mechanism_hard_gate([broken], _profile())
    assert result["passed"] is False
    assert any("accounting" in item for item in result["failures"])


def test_audit_attempt_ledger_requires_cap_and_unique_formal_cells(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    rows = []
    for label in ["a", "b"]:
        for task in range(2):
            rows.append(
                {
                    "attempt_id": len(rows) + 1,
                    "phase": "formal",
                    "label": label,
                    "formal_label": label,
                    "task_id": task,
                    "episode_seed": [44, 235][task],
                    "config_fingerprint": label,
                }
            )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = audit.audit_attempt_ledger(
        path,
        expected_formal={(label, task, [44, 235][task]) for label in ["a", "b"] for task in range(2)},
        expected_preflight=set(),
        cap=4,
    )
    assert result["passed"] is True
    with path.open("a") as handle:
        handle.write(json.dumps({**rows[0], "attempt_id": 5}) + "\n")
    assert audit.audit_attempt_ledger(
        path,
        expected_formal={(label, task, [44, 235][task]) for label in ["a", "b"] for task in range(2)},
        expected_preflight=set(),
        cap=4,
    )["passed"] is False


def test_report_contains_full_job_task_gate_and_mechanism_tables():
    jobs = []
    for index in range(11):
        label = "p2_stage_on_abs_rbf_control" if index == 0 else f"candidate_{index}"
        jobs.append(
            {
                "label": label,
                "valid": True,
                "success_count": index % 10,
                "success_rate": (index % 10) / 10,
                "wilson_95": [0.1, 0.9],
                "task_outcomes": {str(task): "success" if task < index % 10 else "fail" for task in range(10)},
                "failure_taxonomy_counts": {"timeout without completion": 10 - index % 10},
                "metric_summary": {"selection_latency_p95_s": 1.0},
                "mechanism_comparison": {
                    "normalized_final_coverage_delta_median": 0.1,
                    "endpoint_xy_spread_ratio_median": 0.9,
                    "archive_best_reward_delta_median": 0.0,
                    "replacement_active_chunk_ratio": 0.5,
                    "descriptor_overflow_ratio_p95": 0.1,
                },
                "gates": {"task": {"passed": True}, "mechanism_hard": {"passed": True}, "mechanism_claim": {"passed": True}, "safety": {"passed": True}, "all_passed": True},
            }
        )
    text = audit.render_report(
        {
            "jobs": jobs,
            "decision": "candidate_1",
            "ranking": [{"rank": 1, "label": "candidate_1", "all_gates_passed": True}],
            "attempt_ledger": {"attempt_count": 116, "recovery_attempts": 0, "passed": True},
            "credential_audit": {"passed": True},
            "storage_audit": {"outputs_target": "/mnt/data/shared2/test"},
        },
        provenance={"base_commit": "abc", "code_commit": "def"},
    )
    assert "11-job 完整结果" in text
    assert "Task-level paired outcome" in text
    assert "机制与三类 gates" in text
    assert "单因素主效应" in text
    assert "candidate_10" in text
