"""Physical-evidence stage/guidance FSM for the frozen LIBERO evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

import numpy as np


class FSMState(str, Enum):
    ACQUIRE = "ACQUIRE"
    GRASP_VERIFY = "GRASP_VERIFY"
    TRANSPORT = "TRANSPORT"
    RELEASE_VERIFY = "RELEASE_VERIFY"
    RECOVERY = "RECOVERY"
    DONE = "DONE"


_CONTROL_BY_STATE: dict[FSMState, tuple[int, bool]] = {
    FSMState.ACQUIRE: (1, True),
    FSMState.GRASP_VERIFY: (1, True),
    FSMState.TRANSPORT: (2, False),
    FSMState.RELEASE_VERIFY: (2, False),
    FSMState.RECOVERY: (1, True),
    FSMState.DONE: (0, False),
}


@dataclass(frozen=True)
class PhysicalFSMConfig:
    near_threshold_m: float = 0.08
    follow_error_max_m: float = 0.02
    lift_confirm_m: float = 0.02
    grasp_confirm_steps: int = 4
    drop_relative_drift_m: float = 0.05
    drop_fall_m: float = 0.02
    drop_confirm_steps: int = 3
    min_state_dwell_steps: int = 2
    release_verify_timeout_steps: int = 8
    destination_region_radius_m: float = 0.08
    gripper_closed_aperture_max_m: float = 0.07
    gripper_open_aperture_min_m: float = 0.075

    def __post_init__(self) -> None:
        positive_floats = (
            "near_threshold_m",
            "follow_error_max_m",
            "lift_confirm_m",
            "drop_relative_drift_m",
            "drop_fall_m",
            "destination_region_radius_m",
            "gripper_closed_aperture_max_m",
            "gripper_open_aperture_min_m",
        )
        for name in positive_floats:
            value = getattr(self, name)
            if isinstance(value, bool) or not np.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        positive_ints = (
            "grasp_confirm_steps",
            "drop_confirm_steps",
            "min_state_dwell_steps",
            "release_verify_timeout_steps",
        )
        for name in positive_ints:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.follow_error_max_m >= self.drop_relative_drift_m:
            raise ValueError("grasp follow threshold must be stricter than drop drift")
        if self.gripper_closed_aperture_max_m >= self.gripper_open_aperture_min_m:
            raise ValueError("gripper closed/open thresholds must have a hysteresis gap")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PhysicalFSMConfig":
        return cls(**({} if value is None else dict(value)))

    def as_dict(self) -> dict[str, float | int]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }


@dataclass(frozen=True)
class PhysicalEvidence:
    step: int
    executed_gripper_command: float
    gripper_qpos: np.ndarray
    object_position: np.ndarray
    eef_position: np.ndarray
    destination_position: np.ndarray
    success: bool = False

    def normalized(self) -> "PhysicalEvidence":
        if isinstance(self.step, bool) or not isinstance(self.step, int) or self.step < 0:
            raise ValueError("step must be a nonnegative integer")
        command = float(self.executed_gripper_command)
        qpos = np.asarray(self.gripper_qpos, dtype=np.float64)
        object_position = np.asarray(self.object_position, dtype=np.float64)
        eef_position = np.asarray(self.eef_position, dtype=np.float64)
        destination_position = np.asarray(self.destination_position, dtype=np.float64)
        if qpos.shape != (2,):
            raise ValueError("gripper_qpos must have shape (2,)")
        for name, value in (
            ("object_position", object_position),
            ("eef_position", eef_position),
            ("destination_position", destination_position),
        ):
            if value.shape != (3,):
                raise ValueError(f"{name} must have shape (3,)")
        if not np.isfinite(command) or not all(
            np.isfinite(value).all()
            for value in (qpos, object_position, eef_position, destination_position)
        ):
            raise ValueError("physical evidence must be finite")
        return PhysicalEvidence(
            step=int(self.step),
            executed_gripper_command=command,
            gripper_qpos=qpos.copy(),
            object_position=object_position.copy(),
            eef_position=eef_position.copy(),
            destination_position=destination_position.copy(),
            success=bool(self.success),
        )


@dataclass(frozen=True)
class FSMUpdate:
    step: int
    state_before: FSMState
    state_after: FSMState
    transition_reason: str
    state_changed: bool
    current_stage: int
    use_guidance: bool
    grasp_confirmed: bool
    confirmation_counters: dict[str, int]
    evidence: dict[str, Any]
    commit_latency_steps: int | None

    def trace_record(
        self,
        *,
        episode: int,
        task_id: int | None,
        episode_seed: int,
        chunk_id: int,
        chunk_invalidated: bool,
        vlm_advisory: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "schema": "physical-stage-guidance-fsm-trace-v1",
            "episode": int(episode),
            "task_id": task_id,
            "episode_seed": int(episode_seed),
            "global_step": int(self.step),
            "chunk_id": int(chunk_id),
            "state_before": self.state_before.value,
            "state_after": self.state_after.value,
            "transition_reason": self.transition_reason,
            "state_changed": self.state_changed,
            "current_stage": self.current_stage,
            "use_guidance": self.use_guidance,
            "grasp_confirmed": self.grasp_confirmed,
            "confirmation_counters": dict(self.confirmation_counters),
            "commit_latency_steps": self.commit_latency_steps,
            "chunk_invalidated": bool(chunk_invalidated),
            "physical_evidence": dict(self.evidence),
            "vlm_advisory": dict(
                vlm_advisory
                or {"query_status": "not_queried", "control_authority": False}
            ),
        }


class StageGuidanceFSM:
    """Reversible stage/guidance controller driven only by physical evidence."""

    def __init__(self, config: PhysicalFSMConfig | None = None):
        self.config = config or PhysicalFSMConfig()
        self.state = FSMState.ACQUIRE
        self._entered_step = -self.config.min_state_dwell_steps
        self._pre_close_object_z: float | None = None
        self._grasp_relative_window: list[np.ndarray] = []
        self._grasp_count = 0
        self._drop_count = 0
        self._release_verify_steps = 0
        self._transport_relative_anchor: np.ndarray | None = None
        self._previous_object_position: np.ndarray | None = None
        self._previous_eef_position: np.ndarray | None = None
        self._transport_peak_object_z: float | None = None
        self._release_entry_object_z: float | None = None
        self._grasp_has_been_confirmed = False

    @property
    def current_stage(self) -> int:
        return _CONTROL_BY_STATE[self.state][0]

    @property
    def use_guidance(self) -> bool:
        return _CONTROL_BY_STATE[self.state][1]

    def _dwell(self, step: int) -> int:
        return int(step - self._entered_step)

    def _can_leave(self, step: int) -> bool:
        return self._dwell(step) >= self.config.min_state_dwell_steps

    def _enter(
        self,
        state: FSMState,
        *,
        step: int,
        evidence: PhysicalEvidence,
        relative: np.ndarray,
    ) -> None:
        self.state = state
        self._entered_step = int(step)
        self._grasp_count = 0
        self._drop_count = 0
        if state is FSMState.GRASP_VERIFY:
            self._pre_close_object_z = float(evidence.object_position[2])
            self._grasp_relative_window = []
        elif state is FSMState.TRANSPORT:
            self._transport_relative_anchor = relative.copy()
            self._previous_object_position = evidence.object_position.copy()
            self._previous_eef_position = evidence.eef_position.copy()
            self._transport_peak_object_z = float(evidence.object_position[2])
            self._grasp_has_been_confirmed = True
        elif state is FSMState.RELEASE_VERIFY:
            self._release_verify_steps = 0
            self._release_entry_object_z = float(evidence.object_position[2])
        elif state is FSMState.RECOVERY:
            self._grasp_relative_window = []
            self._pre_close_object_z = None
            self._grasp_has_been_confirmed = False

    def update(self, raw_evidence: PhysicalEvidence) -> FSMUpdate:
        evidence = raw_evidence.normalized()
        cfg = self.config
        before = self.state
        relative = evidence.object_position - evidence.eef_position
        object_eef_distance = float(np.linalg.norm(relative))
        destination_distance = float(
            np.linalg.norm(evidence.object_position - evidence.destination_position)
        )
        aperture = float(abs(evidence.gripper_qpos[0] - evidence.gripper_qpos[1]))
        command_close = evidence.executed_gripper_command > 0.0
        command_open = evidence.executed_gripper_command < 0.0
        actual_closed = aperture <= cfg.gripper_closed_aperture_max_m
        actual_open = aperture >= cfg.gripper_open_aperture_min_m
        in_destination = destination_distance <= cfg.destination_region_radius_m
        lift = (
            None
            if self._pre_close_object_z is None
            else float(evidence.object_position[2] - self._pre_close_object_z)
        )
        relative_drift = (
            None
            if self._transport_relative_anchor is None
            else float(np.linalg.norm(relative - self._transport_relative_anchor))
        )
        follow_error = None
        if self._previous_object_position is not None and self._previous_eef_position is not None:
            object_delta = evidence.object_position - self._previous_object_position
            eef_delta = evidence.eef_position - self._previous_eef_position
            follow_error = float(np.linalg.norm(object_delta - eef_delta))
        fall = (
            None
            if self._transport_peak_object_z is None
            else float(self._transport_peak_object_z - evidence.object_position[2])
        )
        reason = "hold"
        commit_latency: int | None = None

        if before is FSMState.DONE:
            reason = "done_terminal_hold"
        elif before is FSMState.ACQUIRE:
            if command_close:
                self._enter(
                    FSMState.GRASP_VERIFY,
                    step=evidence.step,
                    evidence=evidence,
                    relative=relative,
                )
                reason = "close_executed_grasp_candidate"
        elif before is FSMState.GRASP_VERIFY:
            if command_open:
                self._grasp_relative_window = []
                self._grasp_count = 0
                self._pre_close_object_z = float(evidence.object_position[2])
                reason = "grasp_verify_open_hold"
            else:
                base_grasp_evidence = bool(
                    command_close
                    and actual_closed
                    and object_eef_distance <= cfg.near_threshold_m
                    and lift is not None
                    and lift >= cfg.lift_confirm_m
                )
                if base_grasp_evidence:
                    self._grasp_relative_window.append(relative.copy())
                    self._grasp_relative_window = self._grasp_relative_window[
                        -cfg.grasp_confirm_steps:
                    ]
                    window_follow_error = max(
                        float(np.linalg.norm(value - self._grasp_relative_window[0]))
                        for value in self._grasp_relative_window
                    )
                    follow_error = window_follow_error
                    if window_follow_error <= cfg.follow_error_max_m:
                        self._grasp_count = len(self._grasp_relative_window)
                    else:
                        self._grasp_relative_window = [relative.copy()]
                        self._grasp_count = 1
                else:
                    self._grasp_relative_window = []
                    self._grasp_count = 0
                if (
                    self._grasp_count >= cfg.grasp_confirm_steps
                    and self._can_leave(evidence.step)
                ):
                    self._enter(
                        FSMState.TRANSPORT,
                        step=evidence.step,
                        evidence=evidence,
                        relative=relative,
                    )
                    reason = f"grasp_confirmed_{cfg.grasp_confirm_steps}_steps"
                    commit_latency = 0
        elif before is FSMState.TRANSPORT:
            if command_open and in_destination:
                if evidence.success:
                    self._enter(
                        FSMState.DONE,
                        step=evidence.step,
                        evidence=evidence,
                        relative=relative,
                    )
                    reason = "release_success_confirmed_same_step"
                else:
                    self._enter(
                        FSMState.RELEASE_VERIFY,
                        step=evidence.step,
                        evidence=evidence,
                        relative=relative,
                    )
                    reason = "release_started_in_destination"
                commit_latency = 0
            else:
                drift_failure = bool(
                    relative_drift is not None
                    and relative_drift >= cfg.drop_relative_drift_m
                )
                fall_failure = bool(
                    fall is not None
                    and fall >= cfg.drop_fall_m
                    and follow_error is not None
                    and follow_error >= cfg.follow_error_max_m
                )
                unexpected_open = bool(actual_open and not (command_open and in_destination))
                if drift_failure or fall_failure or unexpected_open:
                    self._drop_count += 1
                else:
                    self._drop_count = 0
                if (
                    self._drop_count >= cfg.drop_confirm_steps
                    and self._can_leave(evidence.step)
                ):
                    self._enter(
                        FSMState.RECOVERY,
                        step=evidence.step,
                        evidence=evidence,
                        relative=relative,
                    )
                    reason = f"drop_confirmed_{cfg.drop_confirm_steps}_steps"
                    commit_latency = 0
                self._previous_object_position = evidence.object_position.copy()
                self._previous_eef_position = evidence.eef_position.copy()
                self._transport_peak_object_z = max(
                    float(self._transport_peak_object_z),
                    float(evidence.object_position[2]),
                )
        elif before is FSMState.RECOVERY:
            if command_close and self._can_leave(evidence.step):
                self._enter(
                    FSMState.GRASP_VERIFY,
                    step=evidence.step,
                    evidence=evidence,
                    relative=relative,
                )
                reason = "recovery_close_executed_grasp_candidate"
        elif before is FSMState.RELEASE_VERIFY:
            if evidence.success:
                self._enter(
                    FSMState.DONE,
                    step=evidence.step,
                    evidence=evidence,
                    relative=relative,
                )
                reason = "environment_success_confirmed"
                commit_latency = 0
            else:
                self._release_verify_steps += 1
                release_fall = (
                    None
                    if self._release_entry_object_z is None
                    else float(self._release_entry_object_z - evidence.object_position[2])
                )
                outside_fall = bool(
                    not in_destination
                    and release_fall is not None
                    and release_fall >= cfg.drop_fall_m
                )
                timed_out = self._release_verify_steps >= cfg.release_verify_timeout_steps
                if (outside_fall or timed_out) and self._can_leave(evidence.step):
                    self._enter(
                        FSMState.RECOVERY,
                        step=evidence.step,
                        evidence=evidence,
                        relative=relative,
                    )
                    reason = (
                        "release_outside_region_fall"
                        if outside_fall
                        else f"release_verify_timeout_{cfg.release_verify_timeout_steps}_steps"
                    )
                    commit_latency = 0

        after = self.state
        stage, guidance = _CONTROL_BY_STATE[after]
        grasp_confirmed = bool(
            self._grasp_has_been_confirmed
            and after in {FSMState.TRANSPORT, FSMState.RELEASE_VERIFY, FSMState.DONE}
        )
        physical = {
            "executed_gripper_command": evidence.executed_gripper_command,
            "actual_gripper_qpos": evidence.gripper_qpos.tolist(),
            "gripper_aperture_m": aperture,
            "actual_gripper_closed_or_holding": actual_closed,
            "actual_gripper_open": actual_open,
            "object_keypoint_position": evidence.object_position.tolist(),
            "eef_position": evidence.eef_position.tolist(),
            "destination_position": evidence.destination_position.tolist(),
            "object_eef_distance_m": object_eef_distance,
            "relative_pose_vector": relative.tolist(),
            "relative_drift_m": relative_drift,
            "follow_error_m": follow_error,
            "lift_from_pre_close_m": lift,
            "fall_from_transport_peak_m": fall,
            "destination_distance_m": destination_distance,
            "in_destination_region": in_destination,
            "environment_success": evidence.success,
            "state_dwell_steps_before_update": self._dwell(evidence.step),
        }
        return FSMUpdate(
            step=evidence.step,
            state_before=before,
            state_after=after,
            transition_reason=reason,
            state_changed=before is not after,
            current_stage=stage,
            use_guidance=guidance,
            grasp_confirmed=grasp_confirmed,
            confirmation_counters={
                "grasp": int(self._grasp_count),
                "drop": int(self._drop_count),
                "release_verify": int(self._release_verify_steps),
            },
            evidence=physical,
            commit_latency_steps=commit_latency,
        )
