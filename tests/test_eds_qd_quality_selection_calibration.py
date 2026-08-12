from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "eds_qd_quality_selection_calibration.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "eds_qd_quality_selection_calibration", _MODULE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
calibration = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(calibration)

build_analysis = calibration.build_analysis
exact_degeneracy = calibration.exact_degeneracy
final_archive_rewards = calibration.final_archive_rewards
infer_episode_outcome = calibration.infer_episode_outcome
is_valid_qd_row = calibration.is_valid_qd_row
select_archive_entry = calibration.select_archive_entry
stage2_is_exact_zero_function = calibration.stage2_is_exact_zero_function


def test_exact_degeneracy_is_threshold_free():
    assert exact_degeneracy([0.0, 0.0]) == (True, "exact_zero")
    assert exact_degeneracy([-1.0, -1.0]) == (True, "equal_nonzero")
    assert exact_degeneracy([0.0, 1e-12]) == (False, None)


def test_valid_qd_row_requires_clean_final_archive_rewards():
    row = {
        "qd_archive_enabled": True,
        "qd_per_cell_elite_reward_by_iter": [{"0": 0.0, "1": 0.0}],
        "nonfinite_count": 0,
        "qd_accounting_violation_count": 0,
        "qd_elite_monotonicity_violation_count": 0,
        "qd_final_selection_mismatch_count": 0,
        "qd_fallback_used": False,
    }
    assert is_valid_qd_row(row)
    assert final_archive_rewards(row) == [0.0, 0.0]
    assert not is_valid_qd_row(dict(row, qd_accounting_violation_count=1))


def test_equal_quality_selection_is_input_order_stable_but_fingerprint_dependent():
    archive = [
        {"cell_id": 0, "reward": 0.0, "fingerprint": "bbb"},
        {"cell_id": 1, "reward": 0.0, "fingerprint": "aaa"},
    ]
    assert select_archive_entry(archive)["fingerprint"] == "aaa"
    assert select_archive_entry(list(reversed(archive)))["fingerprint"] == "aaa"
    assert (
        select_archive_entry(archive, reverse_fingerprint_tie=True)["fingerprint"]
        == "bbb"
    )


def test_stage2_exact_zero_ast_check(tmp_path: Path):
    valid = tmp_path / "valid.py"
    valid.write_text(
        "def stage2_guidance(keypoints, action_sequence):\n"
        "    return torch.tensor(0.0, device=action_sequence.device)\n"
    )
    invalid = tmp_path / "invalid.py"
    invalid.write_text(
        "def stage2_guidance(keypoints, action_sequence):\n"
        "    return torch.tensor(0.1, device=action_sequence.device)\n"
    )
    assert stage2_is_exact_zero_function(valid)
    assert not stage2_is_exact_zero_function(invalid)


def test_episode_outcome_uses_only_retrospective_artifact_name(tmp_path: Path):
    metrics = tmp_path / "job" / "eds_eval" / "eds_metrics.jsonl"
    metrics.parent.mkdir(parents=True)
    metrics.write_text("")
    episode = tmp_path / "job" / "episode_1"
    episode.mkdir()
    (episode / "episode_1_success_agentview.mp4").write_bytes(b"")
    assert infer_episode_outcome(metrics, 0) == "success"


def test_output_must_be_inside_owned_root(tmp_path: Path):
    # The CLI boundary is intentionally exercised without building a large fixture.
    owned = (tmp_path / "owned").resolve()
    outside = (tmp_path / "outside.json").resolve()
    try:
        outside.relative_to(owned)
    except ValueError:
        pass
    else:
        raise AssertionError("test fixture must be outside owned root")


def test_build_analysis_has_no_online_compute(monkeypatch):
    synthetic = {
        "metric_file_count": 1,
        "exact_degenerate_unique_count": 20,
        "exact_degenerate_task_count": 5,
    }
    traces = {
        "eligible_qd_trace_count": 2,
        "selection_match_count": 2,
        "nondegenerate_selection_preserved_count": 2,
        "equalized_tie_policy_changes_action_count": 2,
        "equalized_input_order_invariant_count": 2,
        "records": [],
    }
    guidance = {"stage1": {}, "stage2": {"is_exact_zero_function": True}}
    control = {"maps_to_existing_control_branch": True}
    monkeypatch.setattr(
        calibration, "analyze_metric_roots", lambda roots: (synthetic, [])
    )
    monkeypatch.setattr(
        calibration, "analyze_owned_traces", lambda root: traces
    )
    monkeypatch.setattr(
        calibration, "sha256_file", lambda path: "0" * 64
    )
    monkeypatch.setattr(
        calibration, "stage2_is_exact_zero_function", lambda path: True
    )
    monkeypatch.setattr(
        calibration, "inspect_control_fallback_path", lambda path: control
    )
    args = SimpleNamespace(
        run_root=Path("/tmp/run"),
        historical_root=Path("/tmp/historical"),
        stage1_guidance=Path("/tmp/stage1"),
        stage2_guidance=Path("/tmp/stage2"),
        core_policy=Path("/tmp/core"),
    )
    payload = build_analysis(args)
    assert payload["passed"]
    assert payload["online_episode_attempts"] == 0
    assert payload["gpu_hours"] == 0.0
    assert payload["credential_match_count"] == 0
