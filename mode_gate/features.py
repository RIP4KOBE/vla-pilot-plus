"""Task-space path normalization and trajectory descriptor construction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from .types import TaskSpaceTrajectoryBatch


@dataclass(frozen=True)
class DescriptorBatch:
    descriptors: np.ndarray
    relative_positions: np.ndarray
    relative_rotvecs: np.ndarray
    grippers: np.ndarray


class TrajectoryDescriptorEncoder:
    def __init__(self, phase_points: int = 8) -> None:
        if phase_points < 2:
            raise ValueError("phase_points must be at least 2")
        self.phase_points = int(phase_points)

    def encode(self, trajectories: TaskSpaceTrajectoryBatch) -> DescriptorBatch:
        count = trajectories.positions.shape[0]
        relative_positions = np.empty((count, self.phase_points, 3), dtype=np.float64)
        relative_rotvecs = np.empty((count, self.phase_points, 3), dtype=np.float64)
        grippers = np.empty((count, self.phase_points), dtype=np.float64)
        summaries = []

        for index in range(count):
            position = _interpolate_position(
                trajectories.positions[index], self.phase_points
            )
            orientation = _interpolate_orientation(
                trajectories.orientations[index], self.phase_points
            )
            gripper = _nearest_interpolate(
                trajectories.grippers[index], self.phase_points
            )

            rel_position = position - position[0]
            rotations = Rotation.from_quat(orientation)
            rel_rotations = rotations[0].inv() * rotations
            rel_rotvec = rel_rotations.as_rotvec()

            relative_positions[index] = rel_position
            relative_rotvecs[index] = rel_rotvec
            grippers[index] = gripper
            summaries.append(_summary_features(rel_position, rel_rotvec, gripper))

        descriptor = np.concatenate(
            [
                relative_positions.reshape(count, -1),
                relative_rotvecs.reshape(count, -1),
                grippers.reshape(count, -1),
                np.asarray(summaries, dtype=np.float64),
            ],
            axis=1,
        )
        if not np.isfinite(descriptor).all():
            raise ValueError("trajectory descriptor contains non-finite values")
        return DescriptorBatch(
            descriptors=descriptor,
            relative_positions=relative_positions,
            relative_rotvecs=relative_rotvecs,
            grippers=grippers,
        )


def _interpolate_position(path: np.ndarray, points: int) -> np.ndarray:
    source = np.linspace(0.0, 1.0, len(path))
    target = np.linspace(0.0, 1.0, points)
    return np.column_stack(
        [np.interp(target, source, path[:, axis]) for axis in range(3)]
    )


def _interpolate_orientation(quaternions: np.ndarray, points: int) -> np.ndarray:
    source = np.linspace(0.0, 1.0, len(quaternions))
    target = np.linspace(0.0, 1.0, points)
    rotations = Rotation.from_quat(quaternions)
    return Slerp(source, rotations)(target).as_quat()


def _nearest_interpolate(path: np.ndarray, points: int) -> np.ndarray:
    indices = np.rint(np.linspace(0, len(path) - 1, points)).astype(int)
    return path[indices]


def _summary_features(
    relative_position: np.ndarray,
    relative_rotvec: np.ndarray,
    gripper: np.ndarray,
) -> np.ndarray:
    position_steps = np.diff(relative_position, axis=0)
    rotation_steps = np.diff(relative_rotvec, axis=0)
    binary_gripper = gripper >= 0.0
    switches = np.flatnonzero(binary_gripper[1:] != binary_gripper[:-1]) + 1
    first_switch_phase = (
        float(switches[0]) / float(max(1, len(gripper) - 1)) if len(switches) else 1.0
    )
    return np.asarray(
        [
            np.linalg.norm(position_steps, axis=1).sum(),
            np.linalg.norm(relative_position[-1]),
            np.linalg.norm(relative_position, axis=1).max(),
            np.linalg.norm(rotation_steps, axis=1).sum(),
            float(len(switches)),
            first_switch_phase,
            float(gripper[-1]),
        ],
        dtype=np.float64,
    )

