"""Task-space path normalization and trajectory descriptor construction."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from .types import TaskSpaceTrajectoryBatch


@dataclass(frozen=True)
class DescriptorBatch:
    descriptors: np.ndarray
    relative_positions: np.ndarray
    relative_rotvecs: np.ndarray
    grippers: np.ndarray
    keypoint_distances: np.ndarray
    keypoint_validity: np.ndarray


class TrajectoryDescriptorEncoder:
    """The frozen 79-D DPGMM descriptor from the v2 contract."""

    def __init__(self, phase_points: int = 8, keypoint_limit: int = 8) -> None:
        if phase_points < 2:
            raise ValueError("phase_points must be at least 2")
        if keypoint_limit != 8:
            raise ValueError("TrajectoryDescriptorV2 requires exactly eight keypoint slots")
        self.phase_points = int(phase_points)
        self.keypoint_limit = int(keypoint_limit)

    def encode(
        self,
        trajectories: TaskSpaceTrajectoryBatch,
        task_keypoints: np.ndarray | None = None,
    ) -> DescriptorBatch:
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

        keypoint_distances, keypoint_validity = _endpoint_keypoint_features(
            trajectories.positions[:, -1],
            task_keypoints,
            self.keypoint_limit,
        )
        descriptor = np.concatenate(
            [
                relative_positions.reshape(count, -1),
                relative_rotvecs.reshape(count, -1),
                grippers.reshape(count, -1),
                np.asarray(summaries, dtype=np.float64),
                keypoint_distances,
                keypoint_validity,
            ],
            axis=1,
        )
        expected_dims = self.phase_points * 7 + 7 + 2 * self.keypoint_limit
        if descriptor.shape[1] != expected_dims:
            raise RuntimeError(
                f"descriptor contract mismatch: expected {expected_dims}, got {descriptor.shape[1]}"
            )
        if not np.isfinite(descriptor).all():
            raise ValueError("trajectory descriptor contains non-finite values")
        return DescriptorBatch(
            descriptors=descriptor,
            relative_positions=relative_positions,
            relative_rotvecs=relative_rotvecs,
            grippers=grippers,
            keypoint_distances=keypoint_distances,
            keypoint_validity=keypoint_validity,
        )


class ModeFeatureEncoderV1:
    """Encode a trajectory into the frozen 20-D learned-verifier representation."""

    dimensions = 20

    def encode(self, trajectories: TaskSpaceTrajectoryBatch) -> np.ndarray:
        count = trajectories.positions.shape[0]
        output = np.empty((count, self.dimensions), dtype=np.float32)
        for index in range(count):
            positions = _interpolate_position(trajectories.positions[index], 5)
            positions = positions - positions[0]
            orientations = _interpolate_orientation(trajectories.orientations[index], 5)
            rotations = Rotation.from_quat(orientations)
            final_rotvec = (rotations[0].inv() * rotations[-1]).as_rotvec()
            gripper = _nearest_interpolate(trajectories.grippers[index], 5)
            binary = gripper >= 0.0
            switches = np.flatnonzero(binary[1:] != binary[:-1]) + 1
            switch_phase = float(switches[0]) / 4.0 if len(switches) else 1.0
            output[index] = np.concatenate(
                [
                    positions.reshape(-1),
                    final_rotvec,
                    np.asarray([switch_phase, float(gripper[-1])]),
                ]
            ).astype(np.float32)
        if not np.isfinite(output).all():
            raise ValueError("ModeFeatureEncoderV1 produced non-finite features")
        return output


def select_task_keypoints(
    positions: np.ndarray,
    *,
    instruction: str,
    mask_ids: Sequence[int] | np.ndarray | None = None,
    keypoint_to_object: Mapping[int, str] | None = None,
    limit: int = 8,
) -> np.ndarray:
    """Put instruction-mentioned objects first, then use stable object IDs."""

    values = np.asarray(positions, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("keypoint positions must have shape (J, 3)")
    if limit != 8:
        raise ValueError("TrajectoryDescriptorV2 keypoint limit is frozen at 8")
    ids = (
        np.arange(len(values), dtype=np.int64)
        if mask_ids is None
        else np.asarray(mask_ids, dtype=np.int64)
    )
    if ids.shape != (len(values),):
        raise ValueError("mask_ids must align with keypoint positions")
    mapping = {
        int(key): str(name) for key, name in (keypoint_to_object or {}).items()
    }
    normalized_instruction = _normalize_object_text(instruction)
    instruction_tokens = set(normalized_instruction.split())
    ranked = []
    for index, (position, segment_id) in enumerate(zip(values, ids)):
        if not np.isfinite(position).all():
            continue
        object_name = mapping.get(index, mapping.get(int(segment_id), ""))
        normalized_name = _normalize_object_text(object_name)
        object_tokens = [token for token in normalized_name.split() if len(token) > 1]
        mentioned = bool(
            normalized_name
            and (
                normalized_name in normalized_instruction
                or (object_tokens and all(token in instruction_tokens for token in object_tokens))
            )
        )
        ranked.append(
            (
                0 if mentioned else 1,
                normalized_name,
                int(segment_id),
                index,
                position,
            )
        )
    ranked.sort(key=lambda item: item[:4])
    if not ranked:
        return np.empty((0, 3), dtype=np.float64)
    return np.stack([item[4] for item in ranked[:limit]], axis=0)


def _normalize_object_text(value: str) -> str:
    return " ".join(
        re.findall(r"[a-z0-9]+", str(value).lower().replace("_", " "))
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


def _endpoint_keypoint_features(
    endpoints: np.ndarray,
    task_keypoints: np.ndarray | None,
    limit: int,
) -> tuple[np.ndarray, np.ndarray]:
    count = endpoints.shape[0]
    distances = np.zeros((count, limit), dtype=np.float64)
    validity = np.zeros((count, limit), dtype=np.float64)
    if task_keypoints is None:
        return distances, validity
    keypoints = np.asarray(task_keypoints, dtype=np.float64)
    if keypoints.ndim != 2 or keypoints.shape[1] != 3:
        raise ValueError("task_keypoints must have shape (J, 3)")
    keypoints = keypoints[:limit]
    finite = np.isfinite(keypoints).all(axis=1)
    for slot, keypoint in enumerate(keypoints):
        if not finite[slot]:
            continue
        distances[:, slot] = np.linalg.norm(endpoints - keypoint, axis=1)
        validity[:, slot] = 1.0
    return distances, validity
