from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from statistics import median
from typing import Any

import torch


def _finite_numbers(values: Any) -> list[float]:
    if not isinstance(values, (list, tuple)):
        return []
    return [
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ]


def _linear_percentile(values: list[float], quantile: float) -> float | None:
    finite = sorted(_finite_numbers(values))
    if not finite:
        return None
    position = (len(finite) - 1) * quantile
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return finite[low]
    weight = position - low
    return finite[low] * (1.0 - weight) + finite[high] * weight


def _correlation_record(left: list[float], right: list[float]) -> dict[str, Any]:
    pairs = [
        (x, y)
        for x, y in zip(left, right)
        if math.isfinite(x) and math.isfinite(y)
    ]
    count = len(pairs)
    if count < 2:
        return {
            "value": None,
            "valid_pair_count": count,
            "warning": "insufficient_valid_pairs",
        }
    xs, ys = zip(*pairs)
    x_mean = sum(xs) / count
    y_mean = sum(ys) / count
    x_centered = [value - x_mean for value in xs]
    y_centered = [value - y_mean for value in ys]
    x_ss = sum(value * value for value in x_centered)
    y_ss = sum(value * value for value in y_centered)
    if x_ss <= 0.0 or y_ss <= 0.0:
        return {
            "value": None,
            "valid_pair_count": count,
            "warning": "zero_variance",
        }
    correlation = sum(
        x_value * y_value
        for x_value, y_value in zip(x_centered, y_centered)
    ) / math.sqrt(x_ss * y_ss)
    return {
        "value": float(max(-1.0, min(1.0, correlation))),
        "valid_pair_count": count,
        "warning": None,
    }


def direction_rbf_evidence_summary(
    evidence_by_iter: list[list[dict[str, Any]]],
    *,
    weights: list[float] | tuple[float, float, float],
) -> dict[str, Any]:
    """Summarize raw Direction-RBF evidence without inventing invalid correlations."""
    if (
        not isinstance(weights, (list, tuple))
        or len(weights) != 3
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
            for value in weights
        )
    ):
        raise ValueError("Direction-RBF weights must be three finite nonnegative values")
    weight_values = [float(value) for value in weights]
    if not math.isclose(sum(weight_values), 1.0, rel_tol=0.0, abs_tol=1.0e-6):
        raise ValueError("Direction-RBF weights must sum to 1")
    if not isinstance(evidence_by_iter, list):
        raise ValueError("Direction-RBF evidence must be grouped by iteration")

    component_names = ("direction", "shape", "endpoint", "composite")
    summary: dict[str, Any] = {}
    for component in component_names:
        for statistic in ("mean", "p90", "max"):
            summary[f"direction_rbf_pairwise_{component}_{statistic}_by_iter"] = []
    summary.update(
        {
            "direction_rbf_weighted_component_fraction_by_iter": [],
            "direction_rbf_distance_path_length_delta_correlation_by_iter": [],
            "direction_rbf_distance_direction_correlation_by_iter": [],
            "direction_rbf_zero_path_descriptor_count_by_iter": [],
            "direction_rbf_grad_norm_before_normalization_by_iter": [],
            "direction_rbf_grad_norm_after_mask_by_iter": [],
            "direction_rbf_zero_gradient_count": 0,
            "direction_rbf_nonfinite_count": 0,
        }
    )

    for group_index, raw_group in enumerate(evidence_by_iter):
        if not isinstance(raw_group, list):
            raise ValueError(f"Direction-RBF evidence group {group_index} must be a list")
        group = [
            item
            for item in raw_group
            if isinstance(item, dict)
            and item.get("descriptor_mode") == "direction_normalized_eef"
        ]
        components: dict[str, list[float]] = {name: [] for name in component_names}
        path_length_deltas: list[float] = []
        grad_before: list[float] = []
        grad_after: list[float] = []
        zero_path_count = 0
        for item in group:
            item_components = {
                name: _finite_numbers(item.get(f"pairwise_{name}"))
                for name in component_names
            }
            lengths = _finite_numbers(item.get("path_lengths"))
            expected_pair_count = len(lengths) * (len(lengths) - 1) // 2
            if expected_pair_count == len(item_components["composite"]):
                path_length_deltas.extend(
                    abs(lengths[left] - lengths[right])
                    for left in range(len(lengths))
                    for right in range(left + 1, len(lengths))
                )
            for name in component_names:
                components[name].extend(item_components[name])
            before = item.get("grad_norm_before_normalization")
            after = item.get("grad_norm_after_mask")
            if isinstance(before, (int, float)) and not isinstance(before, bool) and math.isfinite(float(before)):
                grad_before.append(float(before))
            if isinstance(after, (int, float)) and not isinstance(after, bool) and math.isfinite(float(after)):
                grad_after.append(float(after))
            count = item.get("zero_path_descriptor_count", 0)
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                zero_path_count += count
            summary["direction_rbf_zero_gradient_count"] += int(item.get("zero_gradient") is True)
            nonfinite = item.get("nonfinite_count", 0)
            if isinstance(nonfinite, int) and not isinstance(nonfinite, bool) and nonfinite >= 0:
                summary["direction_rbf_nonfinite_count"] += nonfinite

        for name in component_names:
            values = components[name]
            summary[f"direction_rbf_pairwise_{name}_mean_by_iter"].append(
                sum(values) / len(values) if values else None
            )
            summary[f"direction_rbf_pairwise_{name}_p90_by_iter"].append(
                _linear_percentile(values, 0.9)
            )
            summary[f"direction_rbf_pairwise_{name}_max_by_iter"].append(
                max(values) if values else None
            )
        weighted_means = [
            weight * (sum(components[name]) / len(components[name]))
            if components[name]
            else 0.0
            for weight, name in zip(weight_values, component_names[:3])
        ]
        weighted_total = sum(weighted_means)
        summary["direction_rbf_weighted_component_fraction_by_iter"].append(
            {
                name: value / weighted_total if weighted_total > 0.0 else None
                for name, value in zip(component_names[:3], weighted_means)
            }
        )
        summary["direction_rbf_distance_path_length_delta_correlation_by_iter"].append(
            _correlation_record(components["composite"], path_length_deltas)
        )
        summary["direction_rbf_distance_direction_correlation_by_iter"].append(
            _correlation_record(components["composite"], components["direction"])
        )
        summary["direction_rbf_zero_path_descriptor_count_by_iter"].append(zero_path_count)
        summary["direction_rbf_grad_norm_before_normalization_by_iter"].append(
            sum(grad_before) / len(grad_before) if grad_before else None
        )
        summary["direction_rbf_grad_norm_after_mask_by_iter"].append(
            sum(grad_after) / len(grad_after) if grad_after else None
        )
    return summary


@dataclass
class EDSIterMetrics:
    iter_idx: int
    n_trunc_steps: int
    best_idx: int
    best_cost: float
    best_reward: float
    mean_reward: float
    reward_spread: float
    score_entropy: float
    unique_parent_ratio: float
    population_diversity: float
    selection_beta: float | None = None
    selection_ess: float | None = None
    selection_ess_ratio: float | None = None
    selection_entropy_normalized: float | None = None
    selection_max_probability: float | None = None
    selection_degenerate_reward: bool = False
    elite_count: int = 0
    anchor_count: int = 0
    anchor_min_pairwise_eef_distance: float | None = None
    diversity_reference: float | None = None
    diversity_band_low: float | None = None
    diversity_band_high: float | None = None
    diversity_current: float | None = None
    adaptive_rbf_reward_confidence: float | None = None
    adaptive_rbf_scale_requested: float | None = None
    adaptive_rbf_scale_applied: float | None = None
    adaptive_rbf_active_particle_count: int = 0
    adaptive_rbf_band_hit: bool | None = None
    adaptive_rbf_fallback_used: bool = False
    adaptive_rbf_fallback_reason: str | None = None
    adaptive_rbf_enabled: bool = False
    resolved_rollout_diversity_scale: float | None = None
    adaptive_rbf_trigger_reason: str | None = None
    resolved_renoise_reason: str | None = None
    reward_improvement: float | None = None
    diversity_band_state: str | None = None
    best_lineage_stable: bool = False
    stable_lineage_count: int = 0
    rollout_rbf_step_indices: list[int] = field(default_factory=list)
    rollout_rbf_step_flags: list[bool] = field(default_factory=list)
    rollout_rbf_step_count: int = 0
    rollout_rbf_final_step_applied: bool = False
    selected_trajectory_length: float | None = None
    population_trajectory_length_mean: float | None = None
    population_trajectory_length_p90: float | None = None
    population_trajectory_length_max: float | None = None
    selected_max_step_displacement: float | None = None
    population_max_step_mean: float | None = None
    population_max_step_p90: float | None = None
    population_max_step_max: float | None = None
    selected_trajectory_length_expansion_ratio: float | None = None
    population_trajectory_length_expansion_ratio: float | None = None
    selected_max_step_expansion_ratio: float | None = None
    population_max_step_expansion_ratio: float | None = None
    eef_direction_diversity: float | None = None
    eef_direction_valid_count: int = 0
    endpoint_direction_spread: float | None = None
    endpoint_direction_valid_count: int = 0
    direction_metric_warning: str | None = None


@dataclass
class EDSChunkMetrics:
    episode: int | None = None
    global_step: int | None = None
    task_id: int | None = None
    suite: str | None = None
    guidance_type: str = "eds"
    reward_mode: str = "normal"
    population_size: int = 0
    cem_iters: int = 0
    use_cem: bool = False
    temperature: float = 0.0
    eds_enter_count: int = 0
    score_call_count: int = 0
    search_evaluation_count: int = 0
    resample_count: int = 0
    renoise_count: int = 0
    rollout_count: int = 0
    population_size_observed: int = 0
    population_shape: list[int] = field(default_factory=list)
    score_shape: list[int] = field(default_factory=list)
    initial_sampling_mode: str = "iid"
    initial_diversity_scale: float | None = None
    initial_diversity_start_ratio: float | None = None
    initial_diversity_steps: int = 0
    initial_diversity_grad_norm_mean: float | None = None
    initial_diversity_grad_norm_max: float | None = None
    initial_diversity_grad_failure_count: int = 0
    initial_diversity_fallback_used: bool = False
    initial_diversity_fallback_reason: str | None = None
    initial_sampler_latency_s: float | None = None
    initial_best_reward: float | None = None
    final_best_reward: float | None = None
    initial_mean_reward: float | None = None
    final_mean_reward: float | None = None
    reward_spread: float | None = None
    selected_reward: float | None = None
    selected_cost: float | None = None
    selected_idx: int | None = None
    score_entropy: float | None = None
    unique_parent_ratio_mean: float | None = None
    population_diversity_initial: float | None = None
    population_diversity_final: float | None = None
    initial_eef_diversity_before_rbf: float | None = None
    initial_eef_diversity_after_rbf_phase: float | None = None
    initial_eef_diversity_final: float | None = None
    initial_eef_diversity_retention_ratio: float | None = None
    endpoint_spread_before_rbf: float | None = None
    endpoint_spread_after_rbf_phase: float | None = None
    endpoint_spread_final: float | None = None
    rollout_diversity_enabled: bool = False
    rollout_diversity_mode: str = "baseline"
    rollout_diversity_scale: float | None = None
    rollout_diversity_start_ratio: float | None = None
    rollout_diversity_iters_applied: int = 0
    rollout_diversity_steps_applied: int = 0
    rollout_diversity_grad_norm_mean: float | None = None
    rollout_diversity_grad_norm_max: float | None = None
    rollout_diversity_fallback_used: bool = False
    rollout_diversity_fallback_reason: str | None = None
    eef_diversity_before_rollout: float | None = None
    eef_diversity_after_rollout_rbf_phase: float | None = None
    eef_diversity_after_rollout_final: float | None = None
    eef_diversity_rollout_retention_ratio: float | None = None
    endpoint_spread_before_rollout: float | None = None
    endpoint_spread_after_rollout_rbf_phase: float | None = None
    endpoint_spread_after_rollout_final: float | None = None
    rollout_rbf_steps_by_iter: list[dict[str, Any]] = field(default_factory=list)
    selected_trajectory_length_by_iter: list[float | None] = field(default_factory=list)
    population_trajectory_length_mean_by_iter: list[float | None] = field(default_factory=list)
    population_trajectory_length_p90_by_iter: list[float | None] = field(default_factory=list)
    population_trajectory_length_max_by_iter: list[float | None] = field(default_factory=list)
    selected_max_step_displacement_by_iter: list[float | None] = field(default_factory=list)
    population_max_step_mean_by_iter: list[float | None] = field(default_factory=list)
    population_max_step_p90_by_iter: list[float | None] = field(default_factory=list)
    population_max_step_max_by_iter: list[float | None] = field(default_factory=list)
    trajectory_length_expansion_ratio_by_iter: list[dict[str, float | None]] = field(
        default_factory=list
    )
    max_step_expansion_ratio_by_iter: list[dict[str, float | None]] = field(
        default_factory=list
    )
    eef_direction_diversity_by_iter: list[float | None] = field(default_factory=list)
    endpoint_direction_spread_by_iter: list[float | None] = field(default_factory=list)
    direction_metric_valid_count_by_iter: list[dict[str, int]] = field(default_factory=list)
    direction_metric_warnings_by_iter: list[str | None] = field(default_factory=list)
    chunk_boundary_action_jump: float | None = None
    gripper_qpos_violation_count: int = 0
    initial_diversity_descriptor_mode: str = "absolute_eef"
    rollout_diversity_descriptor_mode: str = "absolute_eef"
    direction_rbf_weights: list[float] = field(default_factory=list)
    direction_rbf_endpoint_scale_m: float = 0.05
    initial_direction_rbf_evidence_by_step: list[dict[str, Any]] = field(default_factory=list)
    rollout_direction_rbf_evidence_by_iter: list[list[dict[str, Any]]] = field(default_factory=list)
    initial_direction_rbf_metrics: dict[str, Any] = field(default_factory=dict)
    rollout_direction_rbf_metrics: dict[str, Any] = field(default_factory=dict)
    direction_rbf_zero_gradient_count: int = 0
    direction_rbf_nonfinite_count: int = 0
    target_distance_before: float | None = None
    target_distance_after: float | None = None
    action_mask_violation_max: float = 0.0
    nonfinite_count: int = 0
    select_action_latency_s: float | None = None
    eds_loop_latency_s: float | None = None
    parent_weighting_mode: str = "legacy_temperature"
    parent_coverage_mode: str = "none"
    rollout_diversity_control_mode: str = "fixed"
    chunk_population_mode: str = "fresh"
    search_schedule_mode: str = "legacy_linear"
    selection_beta_mean: float | None = None
    selection_ess_mean: float | None = None
    selection_ess_ratio_mean: float | None = None
    selection_entropy_normalized_mean: float | None = None
    selection_max_probability_mean: float | None = None
    selection_degenerate_reward_count: int = 0
    elite_carryover_count_observed: int = 0
    anchor_count_observed: int = 0
    anchor_unique_ratio: float | None = None
    anchor_min_pairwise_eef_distance: float | None = None
    parent_mode_coverage: float | None = None
    offspring_unique_parent_ratio: float | None = None
    parent_count_by_source: dict[str, int] = field(default_factory=dict)
    elite_survival_to_final_count: int = 0
    initial_anchor_lineage_count: int = 0
    final_unique_anchor_lineage_survival_count: int = 0
    final_unique_anchor_lineage_survival_ratio: float | None = None
    selected_parent_source: str | None = None
    adaptive_rbf_reference: float | None = None
    adaptive_rbf_band_low: float | None = None
    adaptive_rbf_band_high: float | None = None
    adaptive_rbf_current_mean: float | None = None
    adaptive_rbf_active_iter_count: int = 0
    adaptive_rbf_active_iter_ratio: float | None = None
    adaptive_rbf_band_hit_ratio: float | None = None
    adaptive_rbf_scale_requested_mean: float | None = None
    adaptive_rbf_scale_applied_mean: float | None = None
    adaptive_rbf_particle_count: int = 0
    adaptive_rbf_fallback_used: bool = False
    adaptive_rbf_fallback_reason: str | None = None
    adaptive_rbf_enabled: bool = False
    chunk_memory_available: bool = False
    chunk_memory_used: bool = False
    chunk_memory_candidate_count: int = 0
    chunk_memory_fraction_observed: float | None = None
    chunk_memory_reset_reason: str | None = None
    chunk_memory_acceptance_ratio: float | None = None
    chunk_memory_source_counts: dict[str, int] = field(default_factory=dict)
    chunk_memory_initial_best_reward: float | None = None
    chunk_fresh_initial_best_reward: float | None = None
    chunk_memory_initial_mean_reward: float | None = None
    chunk_fresh_initial_mean_reward: float | None = None
    chunk_memory_initial_diversity: float | None = None
    chunk_fresh_initial_diversity: float | None = None
    selected_chunk_population_source: str | None = None
    chunk_to_chunk_selected_trajectory_distance: float | None = None
    eds_iters_executed: int = 0
    early_stop_used: bool = False
    early_stop_reason: str | None = None
    reward_plateau_count: int = 0
    stable_lineage_count: int = 0
    execution_horizon_resolved: int | None = None
    execution_horizon_reason: str | None = None
    execution_horizon_stage_change: bool = False
    replan_count: int = 0
    qd_archive_enabled: bool = False
    qd_archive_active_for_chunk: bool = False
    qd_degenerate_fallback_policy: str = "none"
    qd_degenerate_fallback_used: bool = False
    qd_degenerate_fallback_reason: str | None = None
    qd_degenerate_reward_value: float | None = None
    qd_descriptor: str = "target_relative_endpoint_xy"
    qd_grid_shape: list[int] = field(default_factory=list)
    qd_cell_capacity: int = 1
    qd_parent_sampling: str = "uniform_cells"
    qd_global_quality_anchor_count: int = 0
    qd_bounds_update_policy: str = "fixed_initial"
    qd_bounds_xy_m: list[list[float]] = field(default_factory=list)
    qd_bounds_source_initial_checksum: str | None = None
    qd_bounds_xy_m_by_iter: list[list[list[float]]] = field(default_factory=list)
    qd_bounds_checksum_by_iter: list[str] = field(default_factory=list)
    qd_bounds_expanded_by_iter: list[bool] = field(default_factory=list)
    qd_bounds_expansion_count: int = 0
    qd_archive_rebin_collisions_by_iter: list[int] = field(default_factory=list)
    qd_archive_rebin_visit_sum_before_by_iter: list[int] = field(default_factory=list)
    qd_archive_rebin_visit_sum_after_by_iter: list[int] = field(default_factory=list)
    qd_raw_initial_bounds_overflow_count_by_iter: list[int] = field(default_factory=list)
    qd_raw_initial_bounds_overflow_ratio_by_iter: list[float] = field(default_factory=list)
    qd_fixed_initial_within_cell_endpoint_sse_by_iter: list[float] = field(default_factory=list)
    qd_active_within_cell_endpoint_sse_by_iter: list[float] = field(default_factory=list)
    qd_partition_resolution_improvement_by_iter: list[float | None] = field(default_factory=list)
    qd_initial_occupied_cells: int = 0
    qd_initial_accounting: dict[str, int] = field(default_factory=dict)
    qd_initial_descriptor_overflow_count: int = 0
    qd_occupied_cells_by_iter: list[int] = field(default_factory=list)
    qd_coverage_ratio_by_iter: list[float] = field(default_factory=list)
    qd_cell_occupancy_entropy_by_iter: list[float] = field(default_factory=list)
    qd_cumulative_cell_visits_by_iter: list[list[int]] = field(default_factory=list)
    qd_descriptor_overflow_count_by_iter: list[int] = field(default_factory=list)
    qd_descriptor_overflow_ratio_by_iter: list[float] = field(default_factory=list)
    qd_archive_insertions_by_iter: list[int] = field(default_factory=list)
    qd_archive_replacements_by_iter: list[int] = field(default_factory=list)
    qd_archive_rejections_by_iter: list[int] = field(default_factory=list)
    qd_archive_turnover_ratio_by_iter: list[float] = field(default_factory=list)
    qd_per_cell_elite_reward_by_iter: list[dict[str, float]] = field(default_factory=list)
    qd_archive_best_reward_by_iter: list[float] = field(default_factory=list)
    qd_archive_mean_elite_reward_by_iter: list[float] = field(default_factory=list)
    qd_parent_slots_by_cell_by_iter: list[dict[str, int]] = field(default_factory=list)
    qd_sparse_parent_slots_by_cell_by_iter: list[dict[str, int]] = field(default_factory=list)
    qd_parent_weights_by_cell_by_iter: list[dict[str, float]] = field(default_factory=list)
    qd_parent_covered_cell_ratio_by_iter: list[float] = field(default_factory=list)
    qd_parent_cell_unique_ratio_by_iter: list[float] = field(default_factory=list)
    qd_global_quality_anchor_cell_by_iter: list[int | None] = field(default_factory=list)
    qd_global_quality_anchor_fingerprint_by_iter: list[str | None] = field(default_factory=list)
    qd_global_quality_anchor_sparse_slot_count_by_iter: list[int] = field(default_factory=list)
    qd_global_quality_anchor_rescued_by_iter: list[bool] = field(default_factory=list)
    qd_global_quality_anchor_activation_count: int = 0
    qd_global_quality_anchor_rescue_count: int = 0
    qd_selected_cell: int | None = None
    qd_selected_reward: float | None = None
    qd_selected_action_fingerprint: str | None = None
    qd_global_best_action_fingerprint: str | None = None
    qd_archive_endpoint_xy_spread_m_by_iter: list[float] = field(default_factory=list)
    qd_fallback_used: bool = False
    qd_fallback_reason: str | None = None
    qd_accounting_violation_count: int = 0
    qd_elite_monotonicity_violation_count: int = 0
    qd_final_selection_mismatch_count: int = 0
    qd_archive_update_latency_s: float = 0.0
    qd_parent_allocation_latency_s: float = 0.0
    qd_evaluation_count: int = 0
    shadow_qd_observer_enabled: bool = False
    shadow_qd_candidate_stream: list[dict[str, Any]] = field(default_factory=list)
    shadow_qd_observer_checksum: str | None = None
    per_iter: list[EDSIterMetrics] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        payload = _to_json_safe(self)
        if self.direction_rbf_weights:
            if self.initial_direction_rbf_evidence_by_step and not self.initial_direction_rbf_metrics:
                payload["initial_direction_rbf_metrics"] = direction_rbf_evidence_summary(
                    [[item] for item in self.initial_direction_rbf_evidence_by_step],
                    weights=self.direction_rbf_weights,
                )
            if self.rollout_direction_rbf_evidence_by_iter and not self.rollout_direction_rbf_metrics:
                payload["rollout_direction_rbf_metrics"] = direction_rbf_evidence_summary(
                    self.rollout_direction_rbf_evidence_by_iter,
                    weights=self.direction_rbf_weights,
                )
        return payload


def _to_json_safe(value: Any) -> Any:
    if torch.is_tensor(value):
        return _to_json_safe(value.detach().cpu().tolist())
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _to_json_safe(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if hasattr(value, "item"):
        return _to_json_safe(value.item())
    if hasattr(value, "tolist"):
        return _to_json_safe(value.tolist())
    return value


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(_to_json_safe(record), sort_keys=True, allow_nan=False) + "\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    return [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def finite_or_none(value: float | int | None) -> float | None:
    if value is None:
        return None
    value_f = float(value)
    return value_f if math.isfinite(value_f) else None


def _tensor_stat(values: torch.Tensor, kind: str) -> float | None:
    values = values.detach().float().reshape(-1)
    values = values[torch.isfinite(values)]
    if values.numel() == 0:
        return None
    if kind == "mean":
        result = values.mean()
    elif kind == "p90":
        result = torch.quantile(values, 0.9)
    elif kind == "max":
        result = values.max()
    else:
        raise ValueError(f"unsupported tensor statistic: {kind}")
    return finite_or_none(float(result.detach().cpu().item()))


def eef_population_geometry_metrics(
    trajectories: torch.Tensor,
    *,
    selected_idx: int,
    direction_epsilon: float = 1e-8,
) -> dict[str, Any]:
    """Measure EEF path magnitude and normalized direction spread for one population."""
    if not torch.is_tensor(trajectories):
        trajectories = torch.as_tensor(trajectories)
    if trajectories.ndim != 3 or trajectories.shape[-1] < 3:
        raise ValueError(
            "EEF trajectories must have shape (population, time, >=3)"
        )
    population_size = int(trajectories.shape[0])
    if population_size <= 0:
        raise ValueError("EEF trajectory population must be nonempty")
    if (
        isinstance(selected_idx, bool)
        or not isinstance(selected_idx, int)
        or not 0 <= selected_idx < population_size
    ):
        raise ValueError("selected_idx must identify a population member")
    if (
        isinstance(direction_epsilon, bool)
        or not math.isfinite(float(direction_epsilon))
        or float(direction_epsilon) <= 0.0
    ):
        raise ValueError("direction_epsilon must be finite and positive")

    xyz = trajectories[..., :3].detach().float()
    warning: str | None = None
    if not bool(torch.isfinite(xyz).all().item()):
        warning = "nonfinite_trajectory_samples"

    if xyz.shape[1] < 2:
        step_norms = torch.zeros(
            population_size, 0, dtype=xyz.dtype, device=xyz.device
        )
        lengths = torch.zeros(population_size, dtype=xyz.dtype, device=xyz.device)
        max_steps = torch.zeros_like(lengths)
    else:
        step_norms = torch.linalg.vector_norm(xyz[:, 1:] - xyz[:, :-1], dim=-1)
        lengths = step_norms.sum(dim=1)
        max_steps = step_norms.max(dim=1).values

    displacements = xyz[:, 1:] - xyz[:, :1]
    displacement_norms = torch.linalg.vector_norm(displacements, dim=-1)
    valid_steps = torch.isfinite(displacement_norms) & (
        displacement_norms > float(direction_epsilon)
    )
    valid_particles = valid_steps.any(dim=1) if valid_steps.ndim == 2 else torch.zeros(
        population_size, dtype=torch.bool, device=xyz.device
    )
    direction_valid_count = int(valid_particles.sum().detach().cpu().item())
    eef_direction_diversity: float | None = None
    if direction_valid_count >= 2:
        normalized = torch.zeros_like(displacements)
        normalized[valid_steps] = (
            displacements[valid_steps]
            / displacement_norms[valid_steps].unsqueeze(-1)
        )
        flattened = normalized[valid_particles].reshape(direction_valid_count, -1)
        pairwise = torch.pdist(flattened, p=2)
        eef_direction_diversity = _tensor_stat(pairwise, "mean")

    endpoint_displacements = xyz[:, -1] - xyz[:, 0]
    endpoint_norms = torch.linalg.vector_norm(endpoint_displacements, dim=-1)
    valid_endpoints = torch.isfinite(endpoint_norms) & (
        endpoint_norms > float(direction_epsilon)
    )
    endpoint_valid_count = int(valid_endpoints.sum().detach().cpu().item())
    endpoint_direction_spread: float | None = None
    if endpoint_valid_count >= 2:
        unit_endpoints = (
            endpoint_displacements[valid_endpoints]
            / endpoint_norms[valid_endpoints].unsqueeze(-1)
        )
        cosine = unit_endpoints @ unit_endpoints.transpose(0, 1)
        upper = torch.triu_indices(
            endpoint_valid_count,
            endpoint_valid_count,
            offset=1,
            device=cosine.device,
        )
        cosine_distance = 1.0 - cosine[upper[0], upper[1]].clamp(-1.0, 1.0)
        endpoint_direction_spread = _tensor_stat(cosine_distance, "mean")

    if direction_valid_count == 0 and endpoint_valid_count == 0:
        warning = warning or "no_valid_direction_samples"
    elif direction_valid_count < 2 or endpoint_valid_count < 2:
        warning = warning or "insufficient_pairwise_direction_samples"

    return {
        "selected_trajectory_length": finite_or_none(lengths[selected_idx].item()),
        "population_trajectory_length_mean": _tensor_stat(lengths, "mean"),
        "population_trajectory_length_p90": _tensor_stat(lengths, "p90"),
        "population_trajectory_length_max": _tensor_stat(lengths, "max"),
        "selected_max_step_displacement": finite_or_none(max_steps[selected_idx].item()),
        "population_max_step_mean": _tensor_stat(max_steps, "mean"),
        "population_max_step_p90": _tensor_stat(max_steps, "p90"),
        "population_max_step_max": _tensor_stat(max_steps, "max"),
        "eef_direction_diversity": eef_direction_diversity,
        "eef_direction_valid_count": direction_valid_count,
        "endpoint_direction_spread": endpoint_direction_spread,
        "endpoint_direction_valid_count": endpoint_valid_count,
        "direction_metric_warning": warning,
    }


def wilson_ci(success: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    phat = success / total
    denom = 1.0 + z * z / total
    center = (phat + z * z / (2.0 * total)) / denom
    margin = (
        z
        * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * total)) / total)
        / denom
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def summarize_latency(records: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = sorted(
        float(record[key])
        for record in records
        if record.get(key) is not None and math.isfinite(float(record[key]))
    )
    if not values:
        return {"p50": None, "p95": None, "mean": None}
    p95_idx = min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)
    return {
        "p50": float(median(values)),
        "p95": float(values[p95_idx]),
        "mean": float(sum(values) / len(values)),
    }
