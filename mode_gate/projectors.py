"""CALVIN and LIBERO task-space projectors.

These classes only use public environment-adapter calls and never step the
simulator.  They intentionally live outside the statistical gate so that the
gate contains no backend conditionals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from .types import ActionChunkBatch, GateContext, TaskSpaceTrajectoryBatch


class EnvAdapterTrajectoryProjector(ABC):
    def __init__(self, adapter: Any, *, rotation_scale: float) -> None:
        self.adapter = adapter
        self.rotation_scale = float(rotation_scale)

    def project(
        self,
        batch: ActionChunkBatch,
        context: GateContext,
    ) -> TaskSpaceTrajectoryBatch:
        del context
        positions = []
        orientations = []
        grippers = []
        for actions in batch.actions:
            trajectory = self.adapter.delta_actions_to_ee_trajectory(actions)
            if hasattr(trajectory, "detach"):
                trajectory = trajectory.detach()
            if hasattr(trajectory, "cpu"):
                trajectory = trajectory.cpu()
            if hasattr(trajectory, "numpy"):
                trajectory = trajectory.numpy()
            position_path = np.asarray(trajectory, dtype=np.float64)
            if position_path.ndim != 2 or position_path.shape[1] < 3:
                raise ValueError(
                    "adapter.delta_actions_to_ee_trajectory must return (T+1, 3+)"
                )
            position_path = position_path[:, :3]
            expected_points = actions.shape[0] + 1
            if position_path.shape[0] != expected_points:
                raise ValueError(
                    f"projected position path has {position_path.shape[0]} points; "
                    f"expected {expected_points}"
                )
            positions.append(position_path)
            orientations.append(self._orientation_path(actions))
            # Duplicate the first command at t=0.  This keeps the gripper channel
            # in command space instead of mixing it with physical finger width.
            grippers.append(np.concatenate(([actions[0, 6]], actions[:, 6])))

        return TaskSpaceTrajectoryBatch(
            positions=np.stack(positions),
            orientations=np.stack(orientations),
            grippers=np.stack(grippers),
            sample_ids=batch.sample_ids,
            frame="world",
        )

    def _start_rotation(self) -> Rotation:
        pose = self.adapter.get_ee_pose_world()
        quat_wxyz = np.asarray(pose.quaternion, dtype=np.float64)
        return Rotation.from_quat(
            [quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]]
        )

    @abstractmethod
    def _orientation_path(self, actions: np.ndarray) -> np.ndarray:
        pass


class CalvinTrajectoryProjector(EnvAdapterTrajectoryProjector):
    def __init__(self, adapter: Any) -> None:
        info = adapter.get_action_space_info()
        super().__init__(adapter, rotation_scale=float(info.get("rot_scale", 0.05)))

    def _orientation_path(self, actions: np.ndarray) -> np.ndarray:
        start = self._start_rotation()
        start_euler = start.as_euler("xyz")
        cumulative = np.vstack(
            [np.zeros(3), np.cumsum(actions[:, 3:6] * self.rotation_scale, axis=0)]
        )
        return Rotation.from_euler("xyz", start_euler + cumulative).as_quat()


class LiberoTrajectoryProjector(EnvAdapterTrajectoryProjector):
    def __init__(self, adapter: Any, *, rotation_scale: float = 0.05) -> None:
        super().__init__(adapter, rotation_scale=rotation_scale)

    def _orientation_path(self, actions: np.ndarray) -> np.ndarray:
        current = self._start_rotation()
        path = [current.as_quat()]
        for delta in actions[:, 3:6]:
            current = current * Rotation.from_rotvec(delta * self.rotation_scale)
            path.append(current.as_quat())
        return np.stack(path)

