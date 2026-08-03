from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from statistics import median
from typing import Any

import torch


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
    per_iter: list[EDSIterMetrics] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return _to_json_safe(self)


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
