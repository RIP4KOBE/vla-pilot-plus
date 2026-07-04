from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


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
    target_distance_before: float | None = None
    target_distance_after: float | None = None
    action_mask_violation_max: float = 0.0
    nonfinite_count: int = 0
    select_action_latency_s: float | None = None
    eds_loop_latency_s: float | None = None
    per_iter: list[EDSIterMetrics] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


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
