import json
import math
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.eds_eval_metrics import (
    EDSChunkMetrics,
    EDSIterMetrics,
    append_jsonl,
    read_jsonl,
    summarize_latency,
    wilson_ci,
)


def test_eds_chunk_metrics_serializes_nested_iter_metrics():
    metrics = EDSChunkMetrics(
        population_size=16,
        cem_iters=10,
        eds_enter_count=1,
        per_iter=[
            EDSIterMetrics(
                iter_idx=0,
                n_trunc_steps=5,
                best_idx=3,
                best_cost=0.2,
                best_reward=-0.2,
                mean_reward=-0.5,
                reward_spread=0.3,
                score_entropy=2.1,
                unique_parent_ratio=0.5,
                population_diversity=0.01,
            )
        ],
    )

    payload = metrics.to_jsonable()

    assert payload["population_size"] == 16
    assert payload["per_iter"][0]["iter_idx"] == 0
    assert payload["adaptive_rbf_enabled"] is False
    assert payload["per_iter"][0]["adaptive_rbf_enabled"] is False
    assert payload["initial_anchor_lineage_count"] == 0
    assert payload["final_unique_anchor_lineage_survival_count"] == 0
    assert payload["final_unique_anchor_lineage_survival_ratio"] is None
    json.dumps(payload)


def test_eds_chunk_metrics_serializes_initial_sampler_fields():
    metrics = EDSChunkMetrics(
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=1.0,
        initial_diversity_start_ratio=0.5,
        initial_diversity_steps=3,
        initial_diversity_grad_norm_mean=0.5,
        initial_diversity_grad_norm_max=1.0,
        initial_diversity_grad_failure_count=2,
        initial_diversity_fallback_used=True,
        initial_diversity_fallback_reason="missing_gradient",
        initial_sampler_latency_s=0.25,
    )

    payload = metrics.to_jsonable()

    assert payload["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert payload["initial_diversity_scale"] == 1.0
    assert payload["initial_diversity_start_ratio"] == 0.5
    assert payload["initial_diversity_steps"] == 3
    assert payload["initial_diversity_grad_norm_mean"] == 0.5
    assert payload["initial_diversity_grad_norm_max"] == 1.0
    assert payload["initial_diversity_grad_failure_count"] == 2
    assert payload["initial_diversity_fallback_used"] is True
    assert payload["initial_diversity_fallback_reason"] == "missing_gradient"
    assert payload["initial_sampler_latency_s"] == 0.25


def test_eds_chunk_metrics_serializes_initial_eef_diversity_fields():
    metrics = EDSChunkMetrics(
        initial_eef_diversity_before_rbf=0.1,
        initial_eef_diversity_after_rbf_phase=0.4,
        initial_eef_diversity_final=0.2,
        initial_eef_diversity_retention_ratio=0.5,
        endpoint_spread_before_rbf=0.01,
        endpoint_spread_after_rbf_phase=0.03,
        endpoint_spread_final=0.02,
    )

    payload = metrics.to_jsonable()

    assert payload["initial_eef_diversity_before_rbf"] == 0.1
    assert payload["initial_eef_diversity_after_rbf_phase"] == 0.4
    assert payload["initial_eef_diversity_final"] == 0.2
    assert payload["initial_eef_diversity_retention_ratio"] == 0.5
    assert payload["endpoint_spread_before_rbf"] == 0.01
    assert payload["endpoint_spread_after_rbf_phase"] == 0.03
    assert payload["endpoint_spread_final"] == 0.02


def test_eds_chunk_metrics_serializes_rollout_diversity_fields():
    metrics = EDSChunkMetrics(
        rollout_diversity_enabled=True,
        rollout_diversity_mode="rbf_diverse",
        rollout_diversity_scale=10.0,
        rollout_diversity_start_ratio=0.8,
        rollout_diversity_iters_applied=3,
        rollout_diversity_steps_applied=6,
        rollout_diversity_grad_norm_mean=0.5,
        rollout_diversity_grad_norm_max=1.0,
        rollout_diversity_fallback_used=True,
        rollout_diversity_fallback_reason="diversity_gradient_none",
        eef_diversity_before_rollout=0.1,
        eef_diversity_after_rollout_rbf_phase=0.3,
        eef_diversity_after_rollout_final=0.2,
        eef_diversity_rollout_retention_ratio=0.666,
        endpoint_spread_before_rollout=0.01,
        endpoint_spread_after_rollout_rbf_phase=0.03,
        endpoint_spread_after_rollout_final=0.02,
    )

    payload = metrics.to_jsonable()

    assert payload["rollout_diversity_enabled"] is True
    assert payload["rollout_diversity_mode"] == "rbf_diverse"
    assert payload["rollout_diversity_scale"] == 10.0
    assert payload["rollout_diversity_start_ratio"] == 0.8
    assert payload["rollout_diversity_iters_applied"] == 3
    assert payload["rollout_diversity_steps_applied"] == 6
    assert payload["rollout_diversity_grad_norm_mean"] == 0.5
    assert payload["rollout_diversity_grad_norm_max"] == 1.0
    assert payload["rollout_diversity_fallback_used"] is True
    assert payload["rollout_diversity_fallback_reason"] == "diversity_gradient_none"
    assert payload["eef_diversity_before_rollout"] == 0.1
    assert payload["eef_diversity_after_rollout_rbf_phase"] == 0.3
    assert payload["eef_diversity_after_rollout_final"] == 0.2
    assert payload["eef_diversity_rollout_retention_ratio"] == 0.666
    assert payload["endpoint_spread_before_rollout"] == 0.01
    assert payload["endpoint_spread_after_rollout_rbf_phase"] == 0.03
    assert payload["endpoint_spread_after_rollout_final"] == 0.02


def test_eds_adaptive_metrics_round_trip_preserves_json_safe_values(tmp_path):
    metrics = EDSChunkMetrics(
        parent_weighting_mode="adaptive_ess",
        parent_coverage_mode="eef_kcenter",
        rollout_diversity_control_mode="adaptive_band",
        chunk_population_mode="warm_start_mix",
        search_schedule_mode="adaptive",
        selection_beta_mean=3.5,
        selection_ess_mean=8.0,
        selection_ess_ratio_mean=0.5,
        selection_entropy_normalized_mean=0.7,
        selection_max_probability_mean=0.25,
        selection_degenerate_reward_count=1,
        elite_carryover_count_observed=2,
        anchor_count_observed=4,
        anchor_unique_ratio=1.0,
        anchor_min_pairwise_eef_distance=0.04,
        parent_mode_coverage=0.75,
        offspring_unique_parent_ratio=0.625,
        parent_count_by_source={
            "elite": 2,
            "anchor_offspring": 4,
            "weighted_offspring": torch.tensor(10),
        },
        elite_survival_to_final_count=1,
        initial_anchor_lineage_count=4,
        final_unique_anchor_lineage_survival_count=3,
        final_unique_anchor_lineage_survival_ratio=0.75,
        selected_parent_source="anchor_offspring",
        adaptive_rbf_reference=0.5,
        adaptive_rbf_band_low=0.4,
        adaptive_rbf_band_high=0.6,
        adaptive_rbf_current_mean=float("nan"),
        adaptive_rbf_active_iter_count=3,
        adaptive_rbf_active_iter_ratio=0.375,
        adaptive_rbf_band_hit_ratio=0.5,
        adaptive_rbf_scale_requested_mean=4.0,
        adaptive_rbf_scale_applied_mean=3.0,
        adaptive_rbf_particle_count=14,
        adaptive_rbf_fallback_used=True,
        adaptive_rbf_fallback_reason="nonfinite_reference",
        adaptive_rbf_enabled=True,
        chunk_memory_available=True,
        chunk_memory_used=True,
        chunk_memory_candidate_count=4,
        chunk_memory_fraction_observed=0.25,
        chunk_memory_reset_reason=None,
        chunk_memory_acceptance_ratio=0.75,
        chunk_memory_source_counts={"memory": 3, "fresh": 13},
        chunk_memory_initial_best_reward=-0.1,
        chunk_fresh_initial_best_reward=-0.2,
        chunk_memory_initial_mean_reward=-0.4,
        chunk_fresh_initial_mean_reward=-0.5,
        chunk_memory_initial_diversity=0.2,
        chunk_fresh_initial_diversity=0.1,
        selected_chunk_population_source="memory",
        chunk_to_chunk_selected_trajectory_distance=0.03,
        eds_iters_executed=8,
        early_stop_used=True,
        early_stop_reason="reward_plateau",
        reward_plateau_count=2,
        execution_horizon_resolved=4,
        execution_horizon_reason="near_target",
        execution_horizon_stage_change=True,
        replan_count=6,
        per_iter=[
            EDSIterMetrics(
                iter_idx=0,
                n_trunc_steps=3,
                best_idx=1,
                best_cost=0.1,
                best_reward=-0.1,
                mean_reward=-0.4,
                reward_spread=0.3,
                score_entropy=1.5,
                unique_parent_ratio=0.75,
                population_diversity=0.2,
                selection_beta=3.0,
                selection_ess=8.0,
                selection_ess_ratio=0.5,
                selection_entropy_normalized=0.7,
                selection_max_probability=0.25,
                selection_degenerate_reward=False,
                elite_count=2,
                anchor_count=4,
                anchor_min_pairwise_eef_distance=0.04,
                diversity_reference=0.5,
                diversity_band_low=0.4,
                diversity_band_high=0.6,
                diversity_current=0.2,
                adaptive_rbf_reward_confidence=0.25,
                adaptive_rbf_scale_requested=4.0,
                adaptive_rbf_scale_applied=3.0,
                adaptive_rbf_active_particle_count=14,
                adaptive_rbf_band_hit=False,
                adaptive_rbf_fallback_used=False,
                adaptive_rbf_fallback_reason=None,
                adaptive_rbf_enabled=True,
                resolved_rollout_diversity_scale=3.0,
                adaptive_rbf_trigger_reason="below_band",
                resolved_renoise_reason="low_diversity",
                reward_improvement=0.01,
                diversity_band_state="below_band",
                best_lineage_stable=True,
                stable_lineage_count=2,
            )
        ],
        stable_lineage_count=2,
    )

    payload = metrics.to_jsonable()
    path = tmp_path / "adaptive_eds_metrics.jsonl"
    append_jsonl(path, payload)
    restored = read_jsonl(path)[0]

    def assert_json_safe(value):
        assert not torch.is_tensor(value)
        if isinstance(value, dict):
            for item in value.values():
                assert_json_safe(item)
        elif isinstance(value, list):
            for item in value:
                assert_json_safe(item)
        elif isinstance(value, float):
            assert math.isfinite(value)

    assert_json_safe(payload)
    assert_json_safe(restored)
    assert restored["parent_weighting_mode"] == "adaptive_ess"
    assert type(restored["selection_degenerate_reward_count"]) is int
    assert type(restored["chunk_memory_available"]) is bool
    assert type(restored["selection_beta_mean"]) is float
    assert restored["parent_count_by_source"]["weighted_offspring"] == 10
    assert type(restored["parent_count_by_source"]["weighted_offspring"]) is int
    assert restored["adaptive_rbf_current_mean"] is None
    assert restored["per_iter"][0]["selection_ess_ratio"] == 0.5
    assert restored["per_iter"][0]["selection_degenerate_reward"] is False
    assert restored["per_iter"][0]["diversity_reference"] == 0.5
    assert restored["per_iter"][0]["adaptive_rbf_scale_applied"] == 3.0
    assert restored["per_iter"][0]["adaptive_rbf_active_particle_count"] == 14
    assert restored["per_iter"][0]["adaptive_rbf_band_hit"] is False
    assert restored["per_iter"][0]["adaptive_rbf_fallback_used"] is False
    assert restored["per_iter"][0]["adaptive_rbf_enabled"] is True
    assert restored["per_iter"][0]["reward_improvement"] == 0.01
    assert restored["per_iter"][0]["diversity_band_state"] == "below_band"
    assert restored["per_iter"][0]["best_lineage_stable"] is True
    assert restored["per_iter"][0]["stable_lineage_count"] == 2
    assert restored["execution_horizon_resolved"] == 4
    assert restored["replan_count"] == 6
    assert restored["stable_lineage_count"] == 2
    assert restored["adaptive_rbf_enabled"] is True
    assert restored["initial_anchor_lineage_count"] == 4
    assert restored["final_unique_anchor_lineage_survival_count"] == 3
    assert restored["final_unique_anchor_lineage_survival_ratio"] == 0.75


def test_eds_metrics_serializes_nested_nonleaf_tensor_without_deepcopy(tmp_path):
    leaf = torch.tensor([1.5, -2.0], requires_grad=True)
    nonleaf = leaf * 2.0
    metrics = EDSChunkMetrics()
    metrics.parent_count_by_source = {
        "nested": [
            {
                "tensor": nonleaf,
                "nan": float("nan"),
                "positive_inf": float("inf"),
                "negative_inf": -float("inf"),
            }
        ]
    }

    payload = metrics.to_jsonable()
    path = tmp_path / "nonleaf_tensor_metrics.jsonl"
    append_jsonl(path, payload)
    restored = read_jsonl(path)[0]

    nested = restored["parent_count_by_source"]["nested"][0]
    assert nested["tensor"] == [3.0, -4.0]
    assert all(type(value) is float for value in nested["tensor"])
    assert nested["nan"] is None
    assert nested["positive_inf"] is None
    assert nested["negative_inf"] is None
    json.dumps(restored, allow_nan=False)


def test_append_and_read_jsonl_round_trip(tmp_path):
    path = tmp_path / "eds_metrics.jsonl"

    append_jsonl(path, {"episode": 1, "selected_idx": 2})
    append_jsonl(path, {"episode": 2, "selected_idx": 0})

    assert read_jsonl(path) == [
        {"episode": 1, "selected_idx": 2},
        {"episode": 2, "selected_idx": 0},
    ]


def test_wilson_ci_has_reasonable_bounds():
    low, high = wilson_ci(success=8, total=10)

    assert 0.0 <= low < 0.8 < high <= 1.0


def test_summarize_latency_reports_p50_p95_mean():
    summary = summarize_latency(
        [
            {"select_action_latency_s": 1.0},
            {"select_action_latency_s": 2.0},
            {"select_action_latency_s": 3.0},
        ],
        "select_action_latency_s",
    )

    assert summary["p50"] == 2.0
    assert summary["p95"] == 3.0
    assert summary["mean"] == 2.0
