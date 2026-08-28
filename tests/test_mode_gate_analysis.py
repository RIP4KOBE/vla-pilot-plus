from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from mode_gate.black_box import BlackBoxSample, OneShotSteeringBlackBox
from mode_gate.cards import ModeCardRenderer
from mode_gate.config import ModeGateConfig
from mode_gate.features import TrajectoryDescriptorEncoder
from mode_gate.gate import TrajectoryModeGate
from mode_gate.mixture import TrajectoryModeFitter
from mode_gate.projectors import CalvinTrajectoryProjector, LiberoTrajectoryProjector
from mode_gate.types import ActionChunkBatch, GateContext, TaskSpaceTrajectoryBatch


def _context() -> GateContext:
    return GateContext(
        context_id="context-1",
        observation_image=np.zeros((48, 64, 3), dtype=np.uint8),
        task_instruction="pick up the block",
        task_stage="1",
    )


def _action_batch(count: int = 40, horizon: int = 6) -> ActionChunkBatch:
    rng = np.random.default_rng(7)
    actions = rng.normal(size=(count, horizon, 7)).astype(np.float32)
    return ActionChunkBatch(
        actions=actions,
        sample_ids=[f"sample-{index}" for index in range(count)],
        context_id="context-1",
        round_id=1,
        checkpoint_id="checkpoint-1",
        action_space="delta_ee_pose",
        coordinate_frame="world",
    )


def test_one_shot_black_box_exposes_only_snapshot_and_samples():
    calls = []
    execution = object()

    def sampler(context, count):
        calls.append((context.context_id, count))
        return BlackBoxSample(
            candidates=np.zeros((count, 5, 7), dtype=np.float32),
            execution_action_chunk=execution,
        )

    black_box = OneShotSteeringBlackBox(
        40,
        sampler,
        action_space="delta_ee_pose",
        coordinate_frame="world",
    )
    snapshot = black_box.advance(_context())
    batch = black_box.sample(snapshot, _context(), 40)

    assert calls == [("context-1", 40)]
    assert snapshot.is_complete is True
    assert snapshot.execution_action_chunk is execution
    assert batch.actions.shape == (40, 5, 7)
    assert len(set(batch.sample_ids)) == 40


class _FakeAdapter:
    def __init__(self, rot_scale=0.05):
        self.rot_scale = rot_scale
        self.step_called = False

    def get_action_space_info(self):
        return {"rot_scale": self.rot_scale}

    def get_ee_pose_world(self):
        return SimpleNamespace(
            position=np.array([0.1, 0.2, 0.3]),
            quaternion=np.array([1.0, 0.0, 0.0, 0.0]),
        )

    def delta_actions_to_ee_trajectory(self, actions):
        start = self.get_ee_pose_world().position
        return np.vstack([start, start + np.cumsum(actions[:, :3] * 0.01, axis=0)])

    def step(self, action):
        self.step_called = True
        raise AssertionError("projector must never step the environment")


def test_calvin_and_libero_projectors_include_pose_and_gripper_without_rollout():
    actions = _action_batch(count=3, horizon=4)
    for projector_type in (CalvinTrajectoryProjector, LiberoTrajectoryProjector):
        adapter = _FakeAdapter()
        projected = projector_type(adapter).project(actions, _context())
        assert projected.positions.shape == (3, 5, 3)
        assert projected.orientations.shape == (3, 5, 4)
        assert projected.grippers.shape == (3, 5)
        assert adapter.step_called is False


def test_descriptor_resamples_relative_pose_and_gripper_to_eight_phases():
    count, points = 4, 11
    positions = np.zeros((count, points, 3), dtype=np.float64)
    for index in range(count):
        positions[index, :, 0] = np.linspace(0.2, 0.2 + index + 1, points)
    rotations = Rotation.from_euler(
        "z", np.linspace(0, 0.4, points)
    ).as_quat()
    orientations = np.repeat(rotations[None, :, :], count, axis=0)
    grippers = np.tile(np.linspace(-1, 1, points), (count, 1))
    trajectories = TaskSpaceTrajectoryBatch(
        positions=positions,
        orientations=orientations,
        grippers=grippers,
        sample_ids=[f"s-{index}" for index in range(count)],
    )

    encoded = TrajectoryDescriptorEncoder(phase_points=8).encode(trajectories)

    assert encoded.relative_positions.shape == (4, 8, 3)
    assert encoded.relative_rotvecs.shape == (4, 8, 3)
    assert encoded.grippers.shape == (4, 8)
    np.testing.assert_allclose(encoded.relative_positions[:, 0], 0.0)
    np.testing.assert_allclose(encoded.relative_rotvecs[:, 0], 0.0, atol=1e-8)


def test_gmm_retains_low_mass_mode_and_uses_real_unique_representatives():
    rng = np.random.default_rng(11)
    descriptors = np.concatenate(
        [
            rng.normal(0.0, 0.12, size=(36, 6)),
            rng.normal(8.0, 0.08, size=(4, 6)),
        ],
        axis=0,
    )
    fitter = TrajectoryModeFitter(max_components=4, pca_dims=6, seed=5)

    first = fitter.fit(descriptors)
    second = fitter.fit(descriptors)

    np.testing.assert_array_equal(first.labels, second.labels)
    assert len(first.modes) >= 2
    assert any(mode.weight < 0.25 for mode in first.modes)
    assert [mode.weight for mode in first.modes] == sorted(
        (mode.weight for mode in first.modes), reverse=True
    )
    for mode in first.modes:
        representatives = list(mode.representative_indices.values())
        assert len(representatives) == 3
        assert len(set(representatives)) == 3
        assert all(0 <= index < len(descriptors) for index in representatives)


def test_all_gmm_failures_degrade_to_empirical_mode(monkeypatch):
    def fail_fit(self, values):
        raise FloatingPointError("synthetic numerical failure")

    monkeypatch.setattr("mode_gate.mixture.GaussianMixture.fit", fail_fit)
    descriptors = np.arange(120, dtype=np.float64).reshape(20, 6)
    result = TrajectoryModeFitter(max_components=4, pca_dims=4).fit(descriptors)

    assert result.fit_degraded is True
    assert len(result.modes) == 1
    assert result.modes[0].weight == 1.0
    assert len(set(result.modes[0].representative_indices.values())) == 3


def test_total_fkd_ancestor_collapse_degrades_to_one_empirical_mode():
    descriptors = np.zeros((40, 79), dtype=np.float64)
    ancestors = np.zeros(40, dtype=np.int64)
    result = TrajectoryModeFitter(max_components=4, pca_dims=8).fit(
        descriptors,
        ancestor_ids=ancestors,
    )

    assert result.fit_degraded is True
    assert result.metadata["unique_ancestor_count"] == 1
    assert "insufficient unique ancestors" in result.metadata["fallback_reason"]
    assert len(result.modes) == 1
    assert result.modes[0].weight == 1.0
    assert result.modes[0].unique_ancestor_count == 1
    assert len(set(result.modes[0].representative_indices.values())) == 3


class _DirectProjector:
    def project(self, batch, context):
        del context
        positions = np.concatenate(
            [
                np.zeros((batch.sample_count, 1, 3)),
                np.cumsum(batch.actions[:, :, :3] * 0.01, axis=1),
            ],
            axis=1,
        )
        orientations = np.zeros((batch.sample_count, batch.horizon + 1, 4))
        orientations[:, :, 3] = 1.0
        grippers = np.concatenate(
            [batch.actions[:, :1, 6], batch.actions[:, :, 6]], axis=1
        )
        return TaskSpaceTrajectoryBatch(
            positions=positions,
            orientations=orientations,
            grippers=grippers,
            sample_ids=batch.sample_ids,
        )


def test_gate_writes_four_panel_fallback_mode_cards(tmp_path):
    config = ModeGateConfig(
        sample_count=8,
        max_components=2,
        pca_dims=4,
        phase_points=8,
    )

    def unavailable(points):
        raise RuntimeError("camera unavailable")

    gate = TrajectoryModeGate(
        config,
        _DirectProjector(),
        ModeCardRenderer(unavailable),
    )
    evidence = gate.analyze(_context(), _action_batch(count=8), tmp_path)

    assert evidence.modes
    assert all(mode.projection_unavailable for mode in evidence.modes)
    assert all(mode.card_path.exists() for mode in evidence.modes)
