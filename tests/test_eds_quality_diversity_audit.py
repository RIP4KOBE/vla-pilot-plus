from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
from pathlib import Path

import pytest
import torch


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
QDArchive = audit.QDArchive
allocate_parent_slots = audit.allocate_parent_slots
cell_ids = audit.cell_ids
freeze_bounds = audit.freeze_bounds


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


def test_ranking_excludes_invalid_candidates():
    ranked = audit.rank_candidates(
        [
            {"label": "invalid", "valid": False, "success_count": 10},
            {"label": "valid", "valid": True, "success_count": 1},
        ]
    )
    assert [row["label"] for row in ranked] == ["valid"]


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


def test_final_report_is_exclusive_readonly_and_has_sidecar(tmp_path: Path):
    path = tmp_path / "report.md"
    result = audit.freeze_report("final evidence\n", path)

    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    assert stat.S_IMODE(path.with_suffix(path.suffix + ".sha256").stat().st_mode) == 0o444
    assert path.with_suffix(path.suffix + ".sha256").read_text().split()[0] == result["sha256"]
    with pytest.raises(FileExistsError):
        audit.freeze_report("replacement\n", path)


def test_manifest_rejects_credentials(tmp_path: Path):
    with pytest.raises(ValueError, match="credential"):
        audit.freeze_decision_manifest(
            {"value": "authorization: bearer forbidden"},
            tmp_path / "decision.json",
        )


def test_credential_guard_does_not_treat_task_level_as_an_api_key():
    assert audit._contains_credential("Task-level paired outcome") is False
    assert audit._contains_credential("sk-" + "x" * 24) is True


def test_audit_reuses_frozen_dispatch_identity(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "job"
    output_dir.mkdir()
    frozen_record = {
        "git_revision": "a" * 40,
        "code_state_sha256": "b" * 64,
    }
    (output_dir / "job_manifest.json").write_text(
        json.dumps(
            {
                "execution_record": frozen_record,
                "config_fingerprint": "c" * 64,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(audit.runner.base, "_output_dir", lambda job: output_dir)
    job = {"label": "candidate", "execution_record": {"current": True}}

    audit._bind_frozen_job_identity_for_audit(job)

    assert job["execution_record"] == frozen_record
    assert job["config_fingerprint"] == "c" * 64


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


def test_parent_allocation_replay_validates_fixed_bounds_visits_and_exact_slots():
    profile = _profile()
    descriptors = [
        [-0.04, -0.04],
        [0.04, -0.04],
        [-0.04, 0.04],
        [0.04, 0.04],
    ] * 4
    stream = []
    for iteration in range(-1, 10):
        stream.append(
            {
                "iter_idx": iteration,
                "descriptors_xy_m": descriptors,
                "rewards": [float(index + 100 * (iteration + 1)) for index in range(16)],
                "fingerprints": [f"{iteration + 1:02x}{index:02x}" for index in range(16)],
            }
        )
    bounds = freeze_bounds(
        torch.tensor(descriptors),
        quantiles=profile["qd_bounds_quantiles"],
        expand_fraction=profile["qd_bounds_expand_fraction"],
        min_axis_span_m=profile["qd_min_axis_span_m"],
    )
    archive = QDArchive(grid_shape=profile["qd_grid_shape"])

    def update(source_iter):
        group = stream[source_iter + 1]
        values = torch.tensor(group["descriptors_xy_m"])
        cells, _ = cell_ids(values, bounds, profile["qd_grid_shape"])
        rewards = torch.tensor(group["rewards"])
        actions = torch.arange(32, dtype=torch.float32).reshape(16, 2) + 1000 * (source_iter + 1)
        archive.update(
            actions=actions,
            rewards=rewards,
            costs=-rewards,
            descriptors=values,
            cell_ids=cells,
            source_iter=source_iter,
        )

    update(-1)
    slots = []
    weights = []
    for iteration in range(10):
        allocation = allocate_parent_slots(
            archive,
            population_size=16,
            sampling="uniform_cells",
            sparse_exponent=1.0,
            run_seed=0,
            episode=0,
            global_step=8,
            iter_idx=iteration,
        )
        slots.append({str(key): value for key, value in allocation.slot_counts.items()})
        weights.append({str(key): value for key, value in allocation.weights.items()})
        update(iteration)
    record = {
        "episode": 0,
        "global_step": 8,
        "qd_bounds_xy_m": [bounds.lo.tolist(), bounds.hi.tolist()],
        "qd_bounds_source_initial_checksum": bounds.checksum,
        "qd_parent_slots_by_cell_by_iter": slots,
        "qd_parent_weights_by_cell_by_iter": weights,
        "shadow_qd_candidate_stream": stream,
        "shadow_qd_observer_checksum": hashlib.sha256(
            json.dumps(stream, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    result = audit.validate_parent_allocation_replay(record, profile)
    assert result["passed"] is True
    record["qd_parent_slots_by_cell_by_iter"][0]["0"] += 1
    assert audit.validate_parent_allocation_replay(record, profile)["passed"] is False


def test_contact_sheets_use_same_time_and_include_every_job(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    jobs = []
    for index, label in enumerate(("control", "uniform", "sparse")):
        output = tmp_path / label
        video = output / "episode_1" / "episode_1_fail_agentview.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(f"video-{label}".encode())
        jobs.append(
            {
                "label": label,
                "output_dir": str(output),
                "task_outcomes": {"0": "fail"},
                "failure_taxonomy": {"0": "timeout without completion"},
            }
        )
    calls = []

    def frame(video: Path, time_s: float):
        calls.append((video, time_s))
        return Image.new("RGB", (80, 60), color=(20, 40, 60))

    result = audit.generate_contact_sheets(
        {"jobs": jobs},
        output_root=tmp_path / "sheets",
        tasks=[0],
        times_s=[5.0],
        frame_fn=frame,
    )
    assert result["passed"] is True
    assert len(calls) == 3
    assert {time for _, time in calls} == {5.0}
    assert Path(result["sheets"][0]["path"]).is_file()


def test_failure_taxonomy_does_not_treat_zero_valued_key_names_as_evidence(tmp_path: Path):
    result = audit._classify_failures(
        {0: "fail", 1: "fail"},
        [
            {"episode": 0, "gripper_qpos_violation_count": 0, "collision_count": 0},
            {"episode": 1, "gripper_qpos_violation_count": 2},
        ],
        tmp_path,
    )
    assert result[0] == "timeout without completion"
    assert result[1] == "qpos/execution error"


def test_failure_taxonomy_uses_episode_error_traceback_as_execution_evidence(
    tmp_path: Path,
):
    error = tmp_path / "episode_5" / "error.txt"
    error.parent.mkdir(parents=True)
    error.write_text(
        "Traceback (most recent call last):\n"
        "ValueError: Expected robot0_gripper_qpos values within raw qpos range\n",
        encoding="utf-8",
    )

    result = audit._classify_failures({}, [], tmp_path)

    assert result == {4: "qpos/execution error"}


def test_execution_error_count_includes_failure_taxonomy_evidence():
    assert audit._execution_error_episode_count(
        {"execution_qpos_error_episodes": 0},
        {4: "qpos/execution error", 5: "timeout without completion"},
    ) == 1


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
    with path.open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "ledger_event_id": 1,
                    "record_type": "phase_dispatch",
                    "phase": "formal",
                    "attempt_ids": [1, 2, 3, 4],
                }
            )
            + "\n"
        )
    result = audit.audit_attempt_ledger(
        path,
        expected_formal={(label, task, [44, 235][task]) for label in ["a", "b"] for task in range(2)},
        expected_preflight=set(),
        cap=4,
    )
    assert result["passed"] is True
    assert result["actual_episode_attempt_count"] == 4
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
            "completion": {
                "status": "complete",
                "preflight_passed": True,
                "formal_completed_episodes": 110,
                "formal_dispatch_status": "completed",
                "blocker": None,
            },
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
    assert "mechanism preflight：`PASS`；formal：`110/110`" in text
    assert "formal 未 dispatch" not in text
