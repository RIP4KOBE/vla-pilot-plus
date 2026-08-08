from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_audit():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eds_qd_search_budget_sweep_audit.py"
    )
    spec = importlib.util.spec_from_file_location(
        "eds_qd_search_budget_sweep_audit", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _metric(population_size: int, cem_iters: int):
    return {
        "episode": 0,
        "global_step": 8,
        "qd_archive_enabled": True,
        "qd_evaluation_count": population_size * (cem_iters + 1),
        "score_call_count": cem_iters + 1,
        "qd_initial_accounting": {
            "insertions": 16,
            "replacements": 0,
            "rejections": population_size - 16,
        },
        "qd_archive_insertions_by_iter": [0] * cem_iters,
        "qd_archive_replacements_by_iter": [1] * cem_iters,
        "qd_archive_rejections_by_iter": [population_size - 1] * cem_iters,
        "qd_accounting_violation_count": 0,
        "qd_elite_monotonicity_violation_count": 0,
        "qd_final_selection_mismatch_count": 0,
        "qd_fallback_used": False,
        "qd_parent_slots_by_cell_by_iter": [
            {"0": population_size // 2, "1": population_size // 2}
        ]
        * cem_iters,
        "qd_parent_weights_by_cell_by_iter": [{"0": 1.0, "1": 1.0}]
        * cem_iters,
    }


def test_dynamic_mechanism_gate_uses_each_jobs_budget():
    audit = _load_audit()
    profile = {
        "population_size": 32,
        "cem_iters": 15,
        "qd_parent_sampling": "uniform_cells",
    }
    assert audit.qd_mechanism_hard_gate([_metric(32, 15)], profile)["passed"]
    broken = _metric(32, 15)
    broken["qd_evaluation_count"] = 176
    result = audit.qd_mechanism_hard_gate([broken], profile)
    assert result["passed"] is False
    assert any("512" in failure for failure in result["failures"])


def test_ranking_only_includes_valid_task_and_safety_gate_passers():
    audit = _load_audit()
    eligible = {
        "label": "eligible",
        "valid": True,
        "success_count": 5,
        "historical_paired_gained_minus_lost": 1,
        "candidates_per_success": 100.0,
        "selection_latency_p95_s": 2.0,
        "replacement_active_chunk_ratio": 0.5,
        "archive_best_reward_delta_vs_historical": 0.1,
        "gates": {"task": {"passed": True}, "safety": {"passed": True}},
    }
    higher_success = {
        **eligible,
        "label": "higher",
        "success_count": 6,
        "candidates_per_success": 120.0,
    }
    excluded = {
        **eligible,
        "label": "excluded",
        "success_count": 10,
        "gates": {"task": {"passed": True}, "safety": {"passed": False}},
    }
    ranked = audit.rank_candidates([eligible, excluded, higher_success])
    assert [row["label"] for row in ranked] == ["higher", "eligible"]
    assert [row["rank"] for row in ranked] == [1, 2]


def test_main_effects_require_complete_family_grids():
    audit = _load_audit()
    jobs = []
    for family in audit.runner.FAMILIES:
        for population_size in audit.runner.POPULATION_SIZES:
            for cem_iters in audit.runner.CEM_ITERS:
                jobs.append(
                    {
                        "family": family,
                        "population_size": population_size,
                        "cem_iters": cem_iters,
                        "valid": True,
                        "success_count": population_size // 16 + cem_iters // 5,
                        "metric_summary": {"global_best_reward_median": 1.0},
                    }
                )
    result = audit.parameter_effects(jobs)
    assert result["estimable"] is True
    assert set(result["families"]) == set(audit.runner.FAMILIES)
    assert len(result["equal_budget_pairs"]) == 6
    assert audit.parameter_effects(jobs[:-1])["estimable"] is False


def test_expected_attempt_cells_are_exactly_180_formal_and_zero_preflight():
    audit = _load_audit()
    formal, preflight = audit.expected_attempt_cells()
    assert len(formal) == 180
    assert preflight == set()


def test_execution_exception_reports_physical_attempt_overrun(tmp_path):
    audit = _load_audit()
    path = tmp_path / "interruption_provenance.json"
    path.write_text(
        json.dumps(
            {
                "schema": "eds-qd-recovery-tool-timeout-v1",
                "affected_label": "eds_qd_uniform_expand20_p48_k20",
                "continuation_completed": True,
                "algorithm_or_config_change": False,
                "ledger_reserved_attempts": audit.runner.ATTEMPT_CAP,
                "soft_cap_exception_attempts": 1,
                "actual_attempts_after_continuation": (
                    audit.runner.ATTEMPT_CAP + 1
                ),
                "canonical_merged_result": "1/10",
                "interruption": "outer tool timeout",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = audit.execution_exception_audit(path)
    assert result["passed"] is True
    assert result["physical_episode_attempt_count"] == 201
    assert result["hard_cap_passed"] is False
    assert result["user_soft_cap_override_applied"] is True
