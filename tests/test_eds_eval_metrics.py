import json
import sys
from pathlib import Path

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
