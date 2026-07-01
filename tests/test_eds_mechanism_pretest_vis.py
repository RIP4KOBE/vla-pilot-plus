import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.eds_mechanism_trace import EDSMechanismTrace, EDSParticleStage
from utils.eds_mechanism_pretest_vis import _axis_limits, save_eds_mechanism_pretest_artifacts


def _trace():
    stages = [
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
    )


def test_save_eds_mechanism_pretest_artifacts_writes_pngs_and_summary(tmp_path):
    saved = save_eds_mechanism_pretest_artifacts(tmp_path, _trace())

    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "keypoints_3d.json").exists()
    assert (tmp_path / "single_step_inner_loop" / "00_initial_population_3d.png").exists()
    assert (tmp_path / "single_step_inner_loop" / "04_after_rollout_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "iter_000_population_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "iter_000_best_trajectory_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "final_selected_vs_initial_best_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "reward_curve.png").exists()
    assert (tmp_path / "full_eds_process" / "diversity_curve.png").exists()
    assert (tmp_path / "full_eds_process" / "distance_curve.png").exists()
    assert (tmp_path / "full_eds_process" / "per_iter_metrics.csv").exists()
    assert (tmp_path / "full_eds_process" / "full_process_summary.md").exists()
    assert any(path.endswith("reward_curve.png") for path in saved)


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
