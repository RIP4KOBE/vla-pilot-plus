from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from mode_gate.black_box import BlackBoxSample, OneShotSteeringBlackBox
from mode_gate.config import ModeGateConfig
from mode_gate.gate import TrajectoryCandidateGate
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
