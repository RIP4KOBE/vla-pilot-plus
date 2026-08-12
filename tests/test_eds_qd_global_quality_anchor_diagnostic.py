from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/eds_qd_global_quality_anchor_diagnostic.py"
)
SPEC = importlib.util.spec_from_file_location("quality_anchor_diagnostic", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
diagnostic = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = diagnostic
SPEC.loader.exec_module(diagnostic)


def _slots(rewards, visits, *, population_size, episode=0, step=8, iteration=1):
    archive = diagnostic.build_synthetic_archive(rewards, visits)
    return diagnostic.allocate_parent_slots(
        archive,
        population_size=population_size,
        sampling="sparse_priority",
        sparse_exponent=1.0,
        run_seed=0,
        episode=episode,
        global_step=step,
        iter_idx=iteration,
    ).slot_counts


def test_reconstruct_transition_exactly_replays_baseline_and_adds_anchor():
    rewards = {0: 5.0, 1: 4.0, 2: 3.0, 3: 2.0}
    visits = [100, 1, 1, 1] + [0] * 12
    observed = _slots(rewards, visits, population_size=16)

    result = diagnostic.reconstruct_transition(
        rewards=rewards,
        visits=visits,
        observed_slots=observed,
        episode=0,
        global_step=8,
        iter_idx=1,
    )

    assert result["baseline_exact_match"] is True
    assert result["baseline_global_best_slots"] == 0
    assert result["candidate_dedicated_anchor_slots"] == 1
    assert result["candidate_sparse_slot_sum"] == 15
    assert result["candidate_total_slot_sum"] == 16
    assert result["candidate_global_best_slots"] >= 1


def test_reconstruct_rejects_nonunique_maximum():
    rewards = {0: 1.0, 1: 1.0}
    visits = [1, 1] + [0] * 14
    observed = _slots(rewards, visits, population_size=16)
    with pytest.raises(ValueError, match="maximum reward is not unique"):
        diagnostic.reconstruct_transition(
            rewards=rewards,
            visits=visits,
            observed_slots=observed,
            episode=0,
            global_step=0,
            iter_idx=1,
        )


def test_analyze_uses_production_allocator_and_preserves_global_rng(tmp_path):
    rewards = {0: 5.0, 1: 4.0, 2: 3.0, 3: 2.0}
    visits = [100, 1, 1, 1] + [0] * 12
    reward_series = []
    visit_series = []
    slot_series = []
    for iteration in range(10):
        reward_series.append({str(k): v for k, v in rewards.items()})
        visit_series.append(visits)
        slot_series.append(
            {
                str(k): v
                for k, v in _slots(
                    rewards,
                    visits,
                    population_size=16,
                    iteration=iteration,
                ).items()
            }
        )
    row = {
        "task_id": 3,
        "episode": 0,
        "global_step": 8,
        "qd_per_cell_elite_reward_by_iter": reward_series,
        "qd_cumulative_cell_visits_by_iter": visit_series,
        "qd_parent_slots_by_cell_by_iter": slot_series,
    }
    metrics = tmp_path / "eds_metrics.jsonl"
    metrics.write_text(json.dumps(row) + "\n", encoding="utf-8")
    core = Path(__file__).resolve().parents[1] / "core/qd_ed.py"
    design = tmp_path / "design.md"
    design.write_text("frozen\n", encoding="utf-8")
    spec = diagnostic.InputSpec(
        metrics,
        hashlib.sha256(metrics.read_bytes()).hexdigest(),
        1,
    )

    payload = diagnostic.analyze(
        inputs=[spec],
        core_qd=core,
        core_qd_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
        design=design,
        design_sha256=hashlib.sha256(design.read_bytes()).hexdigest(),
    )

    assert payload["metrics"]["valid_transition_count"] == 9
    assert payload["metrics"]["baseline_exact_reconstruction_count"] == 9
    assert payload["metrics"]["candidate_global_best_zero_slot_count"] == 0
    assert payload["gates"]["torch_global_rng_unchanged"] is True
    assert payload["passed"] is False  # fixture intentionally misses scale gates


def test_main_rejects_output_outside_owned_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        diagnostic,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "owned_root": tmp_path / "owned",
                "output": tmp_path / "outside.json",
                "input": [],
                "core_qd": tmp_path / "core.py",
                "core_qd_sha256": "0" * 64,
                "design": tmp_path / "design.md",
                "design_sha256": "0" * 64,
            },
        )(),
    )
    with pytest.raises(ValueError, match="below the owned artifact root"):
        diagnostic.main()
