import csv
import json
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import utils.eds_mechanism_pretest_vis as vis_module

from core.eds_mechanism_trace import (
    EDSMechanismTrace,
    EDSParticleStage,
    save_mechanism_trace,
)
from utils.eds_mechanism_pretest_vis import (
    _axis_limits,
    _initial_reference_stage,
    save_eds_rbf_diversity_artifacts,
    save_eds_rollout_rbf_diversity_artifacts,
    save_eds_mechanism_pretest_artifacts,
)


def _trace():
    stages = [
        EDSParticleStage(
            stage="initial_before_diversity",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.zeros(2, 2, 3),
            rewards=torch.tensor([0.0, 0.0]),
            costs=torch.tensor([0.0, 0.0]),
        ),
        EDSParticleStage(
            stage="initial_after_diversity_phase",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.ones(2, 2, 3),
            rewards=torch.tensor([0.0, 0.0]),
            costs=torch.tensor([0.0, 0.0]),
        ),
        EDSParticleStage(
            stage="initial_final",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.ones(2, 2, 3) * 2.0,
            rewards=torch.tensor([0.1, 0.2]),
            costs=torch.tensor([-0.1, -0.2]),
        ),
        EDSParticleStage(
            stage="initial",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.1, 0.2]),
            costs=torch.tensor([-0.1, -0.2]),
        ),
        EDSParticleStage(
            stage="rollout_before_diversity",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [0.2, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 0.2, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.2, 0.3]),
            costs=torch.tensor([-0.2, -0.3]),
        ),
        EDSParticleStage(
            stage="rollout_after_diversity_phase",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [0.8, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 0.8, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.25, 0.35]),
            costs=torch.tensor([-0.25, -0.35]),
        ),
        EDSParticleStage(
            stage="rollout_final",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [0.6, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 0.6, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.3, 0.4]),
            costs=torch.tensor([-0.3, -0.4]),
        ),
        EDSParticleStage(
            stage="after_rollout",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 1.2, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.3, 0.4]),
            costs=torch.tensor([-0.3, -0.4]),
        ),
        EDSParticleStage(
            stage="full_process_after_rollout",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 1.4, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.5, 0.6]),
            costs=torch.tensor([-0.5, -0.6]),
        ),
    ]
    return EDSMechanismTrace(
        suite="libero_object",
        task_id=1,
        episode=0,
        global_step=0,
        reward_mode="normal",
        population_size=2,
        cem_iters=1,
        use_cem=False,
        keypoints=torch.tensor(
            [
                [99.0, 99.0, 99.0],
                [1.0, 0.0, 0.0],
                [-99.0, -99.0, -99.0],
            ]
        ),
        scoring_keypoint_indices=[1],
        stages=stages,
        selected_idx=1,
        rollout_diversity_info={
            "rollout_diversity_enabled": True,
            "rollout_diversity_mode": "rbf_diverse",
            "rollout_diversity_scale": 20.0,
            "rollout_diversity_start_ratio": 0.8,
            "rollout_diversity_iters_applied": 1,
            "rollout_diversity_steps_applied": 2,
            "rollout_diversity_grad_norm_mean": 0.5,
            "rollout_diversity_grad_norm_max": 1.0,
            "rollout_diversity_fallback_used": False,
            "rollout_diversity_fallback_reason": None,
        },
    )


def test_mechanism_trace_serializes_particle_sources_and_keeps_absent_compatible(
    tmp_path,
):
    trace = _trace()
    sourced_stage = EDSParticleStage(
        stage="sourced_after_rollout",
        iter_idx=0,
        actions=torch.zeros(2, 64, 128),
        trajectories=torch.zeros(2, 2, 3),
        rewards=torch.tensor([1.0, 0.5]),
        costs=torch.tensor([-1.0, -0.5]),
        particle_sources=["elite", "weighted_offspring"],
    )
    trace.stages.append(sourced_stage)

    save_mechanism_trace(tmp_path, trace, save_tensors=True)

    csv_path = tmp_path / "single_step_inner_loop" / "single_step_particles.csv"
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    sourced_rows = [row for row in rows if row["stage"] == "sourced_after_rollout"]
    absent_rows = [row for row in rows if row["stage"] == "initial"]
    assert [row["particle_source"] for row in sourced_rows] == [
        "elite",
        "weighted_offspring",
    ]
    assert {row["particle_source"] for row in absent_rows} == {""}

    tensor_payload = torch.load(tmp_path / "tensors" / "mechanism_trace.pt")
    tensor_stages = {stage["stage"]: stage for stage in tensor_payload["stages"]}
    assert tensor_stages["sourced_after_rollout"]["particle_sources"] == [
        "elite",
        "weighted_offspring",
    ]
    assert tensor_stages["initial"]["particle_sources"] is None


def test_save_eds_mechanism_pretest_artifacts_writes_pngs_and_summary(tmp_path):
    saved = save_eds_mechanism_pretest_artifacts(tmp_path, _trace())

    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "keypoints_3d.json").exists()
    assert (tmp_path / "single_step_inner_loop" / "00_initial_population_3d.png").exists()
    assert (tmp_path / "single_step_inner_loop" / "04_after_rollout_3d.png").exists()
    assert (
        tmp_path / "single_step_inner_loop" / "rollout_before_diversity_3d.png"
    ).exists()
    assert (
        tmp_path / "single_step_inner_loop" / "rollout_after_diversity_phase_3d.png"
    ).exists()
    assert (tmp_path / "single_step_inner_loop" / "rollout_final_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "iter_000_population_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "iter_000_best_trajectory_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "final_selected_vs_initial_best_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "reward_curve.png").exists()
    assert (tmp_path / "full_eds_process" / "diversity_curve.png").exists()
    assert (tmp_path / "full_eds_process" / "distance_curve.png").exists()
    assert (tmp_path / "full_eds_process" / "per_iter_metrics.csv").exists()
    assert (tmp_path / "full_eds_process" / "full_process_summary.md").exists()
    assert any(path.endswith("reward_curve.png") for path in saved)


def test_save_eds_mechanism_pretest_artifacts_writes_initial_sampler_stage_pngs(tmp_path):
    save_eds_mechanism_pretest_artifacts(tmp_path, _trace())

    assert (
        tmp_path / "single_step_inner_loop" / "initial_before_diversity_3d.png"
    ).exists()
    assert (
        tmp_path / "single_step_inner_loop" / "initial_after_diversity_phase_3d.png"
    ).exists()
    assert (tmp_path / "single_step_inner_loop" / "initial_final_3d.png").exists()


def test_keypoints_json_contains_only_scoring_keypoint(tmp_path):
    save_eds_mechanism_pretest_artifacts(tmp_path, _trace())
    keypoints = (tmp_path / "keypoints_3d.json").read_text(encoding="utf-8")

    assert '"scoring_keypoint_indices": [\n    1\n  ]' in keypoints
    assert '"keypoints_3d": [\n    [\n      1.0,' in keypoints
    assert "99.0" not in keypoints


def test_stage_axis_limits_ignore_unscored_far_keypoints():
    trace = _trace()
    stage = trace.stages[0]

    mins, maxs = _axis_limits(trace, stage)

    assert float(maxs[0] - mins[0]) < 2.0
    assert float(maxs[1] - mins[1]) < 2.0
    assert float(maxs[2] - mins[2]) < 2.0


def test_initial_reference_stage_prefers_initial_final_when_initial_appears_first():
    trace = _trace()
    initial = next(stage for stage in trace.stages if stage.stage == "initial")
    initial_final = next(stage for stage in trace.stages if stage.stage == "initial_final")
    trace.stages = [
        initial,
        initial_final,
        *(stage for stage in trace.stages if stage.stage not in {"initial", "initial_final"}),
    ]

    assert _initial_reference_stage(trace) is initial_final


def test_summary_contains_review_protocol(tmp_path):
    save_eds_mechanism_pretest_artifacts(tmp_path, _trace())
    summary = (tmp_path / "full_eds_process" / "full_process_summary.md").read_text(
        encoding="utf-8"
    )

    assert "Qualitative Review Checklist" in summary
    assert "reward geometry" in summary
    assert "resampling pressure" in summary
    assert "rollout preservation" in summary
    assert "pass / mixed / fail" in summary


def test_save_eds_rbf_diversity_artifacts_writes_trace_metrics_and_plots(tmp_path):
    trace = _trace()
    next(
        stage for stage in trace.stages if stage.stage == "initial_after_diversity_phase"
    ).trajectories = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.0, 0.5, 0.0]],
        ],
        dtype=torch.float32,
    )
    next(stage for stage in trace.stages if stage.stage == "initial_final").trajectories = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.0, 0.4, 0.0]],
        ],
        dtype=torch.float32,
    )
    trace.initial_sampler_info = {
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_scale": 20.0,
        "initial_diversity_start_ratio": 0.8,
        "initial_diversity_steps": 4,
        "initial_diversity_fallback_used": False,
        "initial_diversity_fallback_reason": None,
    }

    saved = save_eds_rbf_diversity_artifacts(tmp_path, trace)

    rbf_dir = tmp_path / "RBF_diversity"
    assert (rbf_dir / "eef_3d_before_after_final.png").exists()
    assert (rbf_dir / "endpoint_scatter_before_after_final.png").exists()
    assert (rbf_dir / "pairwise_distance_hist_before_after_final.png").exists()
    assert (rbf_dir / "rbf_diversity_metrics.json").exists()
    assert (rbf_dir / "rbf_diversity_trace.npz").exists()
    assert str(rbf_dir / "rbf_diversity_trace.npz") in saved

    metrics = json.loads((rbf_dir / "rbf_diversity_metrics.json").read_text())
    assert metrics["initial_diversity_scale"] == 20.0
    assert metrics["initial_diversity_start_ratio"] == 0.8
    assert metrics["initial_diversity_steps"] == 4
    assert metrics["initial_diversity_fallback_used"] is False
    assert metrics["initial_eef_diversity_before_rbf"] < metrics[
        "initial_eef_diversity_after_rbf_phase"
    ]
    assert metrics["endpoint_spread_before_rbf"] < metrics[
        "endpoint_spread_after_rbf_phase"
    ]

    import numpy as np

    payload = np.load(rbf_dir / "rbf_diversity_trace.npz")
    assert payload["before_trajectories"].shape == (2, 2, 3)
    assert payload["after_rbf_phase_trajectories"].shape == (2, 2, 3)
    assert payload["final_trajectories"].shape == (2, 2, 3)


def test_save_eds_rollout_rbf_diversity_artifacts_writes_trace_metrics_and_plots(tmp_path):
    trace = _trace()

    saved = save_eds_rollout_rbf_diversity_artifacts(tmp_path, trace)

    rollout_dir = tmp_path / "Rollout_RBF_diversity"
    assert (rollout_dir / "rollout_eef_3d_before_after_final.png").exists()
    assert (rollout_dir / "rollout_endpoint_scatter_before_after_final.png").exists()
    assert (rollout_dir / "rollout_pairwise_distance_hist_before_after_final.png").exists()
    assert (rollout_dir / "rollout_rbf_diversity_metrics.json").exists()
    assert (rollout_dir / "rollout_rbf_diversity_trace.npz").exists()
    assert str(rollout_dir / "rollout_rbf_diversity_trace.npz") in saved

    metrics = json.loads(
        (rollout_dir / "rollout_rbf_diversity_metrics.json").read_text()
    )
    assert metrics["eef_diversity_before_rollout"] < metrics[
        "eef_diversity_after_rollout_rbf_phase"
    ]
    assert metrics["endpoint_spread_before_rollout"] < metrics[
        "endpoint_spread_after_rollout_rbf_phase"
    ]
    assert metrics["eef_diversity_rollout_retention_ratio"] < 1.0
    assert metrics["rollout_diversity_enabled"] is True
    assert metrics["rollout_diversity_mode"] == "rbf_diverse"
    assert metrics["rollout_diversity_scale"] == 20.0
    assert metrics["rollout_diversity_start_ratio"] == 0.8
    assert metrics["rollout_diversity_iters_applied"] == 1
    assert metrics["rollout_diversity_steps_applied"] == 2
    assert metrics["rollout_diversity_grad_norm_mean"] == 0.5
    assert metrics["rollout_diversity_grad_norm_max"] == 1.0
    assert metrics["rollout_diversity_fallback_used"] is False
    assert metrics["rollout_diversity_fallback_reason"] is None

    import numpy as np

    payload = np.load(rollout_dir / "rollout_rbf_diversity_trace.npz")
    assert payload["before_rollout_trajectories"].shape == (2, 2, 3)
    assert payload["after_rollout_rbf_phase_trajectories"].shape == (2, 2, 3)
    assert payload["final_rollout_trajectories"].shape == (2, 2, 3)


def _adaptive_evidence_trace():
    trace = _trace()
    after_rollout = next(
        stage for stage in trace.stages if stage.stage == "after_rollout"
    )
    after_rollout.parent_indices = torch.tensor([0, 1])
    after_rollout.parent_ranks = torch.tensor([1, 2])
    after_rollout.particle_sources = ["elite", "weighted_offspring"]
    after_rollout.parent_probabilities = [None, 0.35]
    after_rollout.parent_selection_kinds = [
        "deterministic_elite",
        "adaptive_ess",
    ]
    trace.selection_info = {
        "enabled": True,
        "parent_weighting_mode": "adaptive_ess",
        "parent_coverage_mode": "eef_kcenter",
        "elite_survival_to_final_count": 1,
        "initial_anchor_lineage_count": 1,
        "final_unique_anchor_lineage_survival_count": 1,
        "final_unique_anchor_lineage_survival_ratio": 1.0,
        "selected_parent_source": "elite",
        "per_iter": [
            {
                "iter_idx": 0,
                "selection_beta": 2.5,
                "selection_ess": 1.5,
                "selection_population_size": 2,
                "selection_entropy_normalized": 0.8,
                "selection_max_probability": 0.65,
                "parent_indices": [0, 1],
                "parent_ranks": [1, 2],
                "parent_sources": ["elite", "weighted_offspring"],
                "parent_probabilities": [None, 0.35],
                "parent_selection_kinds": [
                    "deterministic_elite",
                    "adaptive_ess",
                ],
                "parent_count_by_source": {
                    "elite": 1,
                    "anchor_offspring": 0,
                    "weighted_offspring": 1,
                },
            }
        ],
    }

    memory_fresh = EDSParticleStage(
        stage="memory_fresh_initial",
        iter_idx=0,
        actions=torch.zeros(2, 64, 128),
        trajectories=torch.tensor(
            [
                [[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 0.1, 0.0]],
            ]
        ),
        rewards=torch.tensor([0.1, 0.2]),
        costs=torch.tensor([-0.1, -0.2]),
        particle_sources=["fresh", "fresh"],
    )
    memory_adapted = EDSParticleStage(
        stage="memory_adapted_candidates",
        iter_idx=0,
        actions=torch.zeros(1, 64, 128),
        trajectories=torch.tensor([[[0.0, 0.0, 0.0], [0.3, 0.0, 0.0]]]),
        rewards=torch.tensor([0.3]),
        costs=torch.tensor([-0.3]),
        particle_sources=["memory"],
    )
    memory_composed = EDSParticleStage(
        stage="memory_composed_initial",
        iter_idx=0,
        actions=torch.zeros(2, 64, 128),
        trajectories=torch.tensor(
            [
                [[0.0, 0.0, 0.0], [0.3, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 0.1, 0.0]],
            ]
        ),
        rewards=torch.tensor([0.3, 0.2]),
        costs=torch.tensor([-0.3, -0.2]),
        particle_sources=["memory", "fresh"],
    )
    trace.stages.extend([memory_fresh, memory_adapted, memory_composed])
    trace.chunk_memory_info = {
        "enabled": True,
        "chunk_memory_available": True,
        "chunk_memory_used": True,
        "chunk_memory_candidate_count": 1,
        "chunk_memory_acceptance_ratio": 1.0,
        "chunk_memory_source_counts": {"memory": 1, "fresh": 1},
        "chunk_fresh_initial_best_reward": 0.2,
        "chunk_memory_initial_best_reward": 0.3,
        "chunk_fresh_initial_diversity": 0.1,
        "chunk_memory_initial_diversity": 0.3,
        "selected_chunk_population_source": "memory",
        "chunk_to_chunk_selected_trajectory_distance": 0.2,
        "accepted_positions": [0],
    }
    trace.adaptive_rollout_info = {
        "enabled": True,
        "per_iter": [
            {
                "iter_idx": 0,
                "diversity_reference": 0.4,
                "diversity_current": 0.2,
                "diversity_band_low": 0.3,
                "diversity_band_high": 0.5,
                "reward_confidence": 0.6,
                "scale_requested": 10.0,
                "scale_applied": 8.0,
                "active_particle_count": 1,
                "reason": "below_band",
                "fallback_used": False,
                "fallback_reason": None,
            }
        ],
    }
    trace.search_schedule_info = {
        "enabled": True,
        "search_schedule_mode": "adaptive",
        "eds_iters_executed": 1,
        "early_stop_used": False,
        "early_stop_reason": None,
        "reward_plateau_count": 0,
        "stable_lineage_count": 1,
        "per_iter": [
            {
                "iter_idx": 0,
                "n_trunc_steps": 3,
                "resolved_renoise_reason": "low_diversity",
                "best_reward": 0.4,
                "mean_reward": 0.3,
                "population_diversity": 0.2,
                "diversity_band_low": 0.3,
                "diversity_band_high": 0.5,
                "best_lineage_stable": True,
                "stable_lineage_count": 1,
            }
        ],
    }
    trace.execution_info = {
        "enabled": True,
        "execution_horizon_resolved": 4,
        "execution_horizon_reason": "near_target",
        "execution_horizon_stage_change": False,
        "replan_count": 2,
    }
    return trace


def test_adaptive_evidence_artifacts_match_trace_and_are_nonempty(tmp_path):
    trace = _adaptive_evidence_trace()

    save_eds_mechanism_pretest_artifacts(tmp_path, trace)

    expected = [
        "selection/parent_source_trajectories_3d.png",
        "selection/parent_rank_and_probability.csv",
        "selection/elite_anchor_survival.json",
        "memory/fresh_vs_memory_trajectories_3d.png",
        "memory/memory_acceptance.json",
        "schedule/adaptive_decisions.json",
        "schedule/reward_diversity_schedule.png",
    ]
    for relative_path in expected:
        path = tmp_path / relative_path
        assert path.exists(), relative_path
        assert path.stat().st_size > 0, relative_path

    with (tmp_path / "selection/parent_rank_and_probability.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["source"] == "elite"
    assert rows[0]["probability"] == ""
    assert rows[0]["selection_kind"] == "deterministic_elite"
    assert float(rows[1]["probability"]) == 0.35

    survival = json.loads(
        (tmp_path / "selection/elite_anchor_survival.json").read_text()
    )
    assert survival["elite_survival_to_final_count"] == 1
    assert survival["initial_anchor_lineage_count"] == 1
    assert survival["final_unique_anchor_lineage_survival_count"] == 1
    assert survival["final_unique_anchor_lineage_survival_ratio"] == 1.0
    assert survival["selected_parent_source"] == "elite"

    acceptance = json.loads((tmp_path / "memory/memory_acceptance.json").read_text())
    assert acceptance["chunk_memory_acceptance_ratio"] == 1.0
    assert acceptance["chunk_memory_source_counts"] == {"fresh": 1, "memory": 1}
    assert acceptance["accepted_positions"] == [0]
    assert len(acceptance["axis_limits"]["min"]) == 3
    assert len(acceptance["axis_limits"]["max"]) == 3

    decisions = json.loads(
        (tmp_path / "schedule/adaptive_decisions.json").read_text()
    )
    assert decisions["adaptive_rollout"]["per_iter"][0]["scale_applied"] == 8.0
    assert decisions["search_schedule"]["per_iter"][0]["n_trunc_steps"] == 3
    assert decisions["execution"]["execution_horizon_resolved"] == 4


def test_adaptive_evidence_optional_directories_are_omitted_when_modes_absent(tmp_path):
    trace = _trace()
    trace.rollout_diversity_info = {}

    save_eds_mechanism_pretest_artifacts(tmp_path, trace)

    assert not (tmp_path / "selection").exists()
    assert not (tmp_path / "memory").exists()
    assert not (tmp_path / "schedule").exists()


def test_schedule_series_builder_uses_adaptive_rbf_iterations_without_search(tmp_path):
    trace = _trace()
    trace.search_schedule_info = {}
    trace.execution_info = {}
    trace.adaptive_rollout_info = {
        "enabled": True,
        "per_iter": [
            {
                "iter_idx": 2,
                "diversity_reference": 0.4,
                "diversity_current": 0.2,
                "diversity_band_low": 0.3,
                "diversity_band_high": 0.5,
                "scale_requested": 10.0,
                "scale_applied": 8.0,
            }
        ],
    }

    builder = getattr(vis_module, "_build_adaptive_schedule_series", None)
    assert callable(builder)
    series = builder(trace)

    assert series["iter_ids"] == [2]
    assert series["diversity_current"] == [0.2]
    assert series["diversity_band_low"] == [0.3]
    assert series["diversity_band_high"] == [0.5]
    assert series["scale_requested"] == [10.0]
    assert series["scale_applied"] == [8.0]
    save_eds_mechanism_pretest_artifacts(tmp_path, trace)
    assert (tmp_path / "schedule/reward_diversity_schedule.png").stat().st_size > 0


def test_schedule_series_builder_uses_search_iterations_without_adaptive_rbf(tmp_path):
    trace = _trace()
    trace.adaptive_rollout_info = {}
    trace.execution_info = {}
    trace.search_schedule_info = {
        "enabled": True,
        "per_iter": [
            {
                "iter_idx": 1,
                "best_reward": 0.7,
                "mean_reward": 0.4,
                "population_diversity": 0.25,
                "diversity_band_low": 0.2,
                "diversity_band_high": 0.3,
                "n_trunc_steps": 3,
            }
        ],
    }

    series = vis_module._build_adaptive_schedule_series(trace)

    assert series["iter_ids"] == [1]
    assert series["best_reward"] == [0.7]
    assert series["mean_reward"] == [0.4]
    assert series["diversity_current"] == [0.25]
    assert series["renoise_steps"] == [3]
    save_eds_mechanism_pretest_artifacts(tmp_path, trace)
    assert (tmp_path / "schedule/reward_diversity_schedule.png").stat().st_size > 0


def test_schedule_series_builder_uses_execution_horizon_without_iter_series(tmp_path):
    trace = _trace()
    trace.adaptive_rollout_info = {}
    trace.search_schedule_info = {}
    trace.execution_info = {
        "enabled": True,
        "execution_horizon_resolved": 4,
        "execution_horizon_reason": "near_distance",
        "replan_count": 3,
    }

    series = vis_module._build_adaptive_schedule_series(trace)

    assert series["iter_ids"] == []
    assert series["execution_x"] == [0]
    assert series["execution_horizon"] == [4]
    assert series["execution_reason"] == ["near_distance"]
    save_eds_mechanism_pretest_artifacts(tmp_path, trace)
    assert (tmp_path / "schedule/reward_diversity_schedule.png").stat().st_size > 0


def test_disabled_adaptive_rbf_info_does_not_create_schedule_evidence(tmp_path):
    trace = _trace()
    trace.rollout_diversity_info = {}
    trace.adaptive_rollout_info = {"enabled": False, "per_iter": [{"iter_idx": 0}]}
    trace.search_schedule_info = {}
    trace.execution_info = {}

    save_eds_mechanism_pretest_artifacts(tmp_path, trace)

    assert not (tmp_path / "schedule").exists()


@pytest.mark.parametrize(
    "invalid_case",
    [
        "trajectory_nan",
        "reward_inf",
        "cost_inf",
        "empty_time_axis",
        "trajectory_wrong_last_dim",
        "reward_length_mismatch",
        "scoring_keypoint_nan",
    ],
)
def test_visualization_prevalidation_rejects_invalid_trace_without_partial_output(
    tmp_path,
    invalid_case,
):
    trace = _trace()
    stage = trace.stages[0]
    if invalid_case == "trajectory_nan":
        stage.trajectories[0, 0, 0] = float("nan")
    elif invalid_case == "reward_inf":
        stage.rewards[0] = float("inf")
    elif invalid_case == "cost_inf":
        stage.costs[0] = float("-inf")
    elif invalid_case == "empty_time_axis":
        stage.trajectories = torch.zeros(2, 0, 3)
    elif invalid_case == "trajectory_wrong_last_dim":
        stage.trajectories = torch.zeros(2, 2, 4)
    elif invalid_case == "reward_length_mismatch":
        stage.rewards = torch.zeros(1)
    else:
        trace.keypoints[1, 0] = float("nan")
    output_root = tmp_path / "artifacts"

    with pytest.raises(ValueError, match="EDS visualization trace"):
        save_eds_mechanism_pretest_artifacts(output_root, trace)

    assert not output_root.exists()


def test_singleton_trace_generates_real_visualization_artifacts(tmp_path):
    trace = _trace()
    trace.selected_idx = 0
    for stage in trace.stages:
        stage.actions = stage.actions[:1].clone()
        stage.trajectories = stage.trajectories[:1].clone()
        stage.rewards = stage.rewards[:1].clone()
        stage.costs = stage.costs[:1].clone()
        for field_name in (
            "parent_indices",
            "parent_ranks",
            "reward_before_rollout",
            "reward_after_rollout",
            "renoise_delta_norm",
            "rollout_delta_norm",
        ):
            value = getattr(stage, field_name)
            if value is not None:
                setattr(stage, field_name, value[:1].clone())
        if stage.particle_sources is not None:
            stage.particle_sources = stage.particle_sources[:1]
        if stage.parent_probabilities is not None:
            stage.parent_probabilities = stage.parent_probabilities[:1]
        if stage.parent_selection_kinds is not None:
            stage.parent_selection_kinds = stage.parent_selection_kinds[:1]
    output_root = tmp_path / "singleton"

    saved = save_eds_mechanism_pretest_artifacts(output_root, trace)

    png_paths = [Path(path) for path in saved if path.endswith(".png")]
    assert png_paths
    assert all(path.exists() and path.stat().st_size > 0 for path in png_paths)
    assert (output_root / "config.json").exists()
