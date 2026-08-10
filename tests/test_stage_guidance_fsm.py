from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.stage_guidance_fsm import (
    FSMState,
    PhysicalEvidence,
    PhysicalFSMConfig,
    StageGuidanceFSM,
)


def _evidence(
    step: int,
    *,
    command: float = 1.0,
    aperture: float = 0.04,
    object_position=(0.0, 0.0, 0.0),
    eef_position=(0.0, 0.0, 0.04),
    destination_position=(0.0, 0.30, 0.0),
    success: bool = False,
) -> PhysicalEvidence:
    half = aperture / 2.0
    return PhysicalEvidence(
        step=step,
        executed_gripper_command=command,
        gripper_qpos=np.array([half, -half]),
        object_position=np.array(object_position, dtype=np.float64),
        eef_position=np.array(eef_position, dtype=np.float64),
        destination_position=np.array(destination_position, dtype=np.float64),
        success=success,
    )


def _confirmed_fsm() -> tuple[StageGuidanceFSM, int]:
    fsm = StageGuidanceFSM(PhysicalFSMConfig())
    fsm.update(_evidence(0, object_position=(0.0, 0.0, 0.0)))
    for step in range(1, 5):
        result = fsm.update(
            _evidence(
                step,
                object_position=(0.0, 0.0, 0.025),
                eef_position=(0.0, 0.0, 0.065),
            )
        )
    assert result.state_after is FSMState.TRANSPORT
    return fsm, 5


def test_empty_grasp_never_turns_guidance_off():
    fsm = StageGuidanceFSM(PhysicalFSMConfig())

    first = fsm.update(
        _evidence(
            0,
            object_position=(0.0, 0.0, 0.0),
            eef_position=(0.25, 0.0, 0.10),
        )
    )
    assert first.state_after is FSMState.GRASP_VERIFY
    for step in range(1, 8):
        result = fsm.update(
            _evidence(
                step,
                object_position=(0.0, 0.0, 0.0),
                eef_position=(0.25, 0.0, 0.10),
            )
        )

    assert result.state_after is FSMState.GRASP_VERIFY
    assert result.current_stage == 1
    assert result.use_guidance is True
    assert result.grasp_confirmed is False


def test_stable_lift_requires_four_steps_then_turns_guidance_off():
    fsm = StageGuidanceFSM(PhysicalFSMConfig())
    fsm.update(_evidence(0, object_position=(0.0, 0.0, 0.0)))

    for step in range(1, 4):
        result = fsm.update(
            _evidence(
                step,
                object_position=(0.0, 0.0, 0.025),
                eef_position=(0.0, 0.0, 0.065),
            )
        )
        assert result.state_after is FSMState.GRASP_VERIFY
        assert result.use_guidance is True

    result = fsm.update(
        _evidence(
            4,
            object_position=(0.0, 0.0, 0.025),
            eef_position=(0.0, 0.0, 0.065),
        )
    )
    assert result.state_after is FSMState.TRANSPORT
    assert result.current_stage == 2
    assert result.use_guidance is False
    assert result.grasp_confirmed is True
    assert result.transition_reason == "grasp_confirmed_4_steps"


def test_single_frame_jitter_resets_confirmation_and_does_not_switch():
    fsm = StageGuidanceFSM(PhysicalFSMConfig())
    fsm.update(_evidence(0))
    fsm.update(
        _evidence(
            1,
            object_position=(0.0, 0.0, 0.025),
            eef_position=(0.0, 0.0, 0.065),
        )
    )
    jitter = fsm.update(
        _evidence(
            2,
            object_position=(0.08, 0.0, 0.025),
            eef_position=(0.0, 0.0, 0.065),
        )
    )

    assert jitter.state_after is FSMState.GRASP_VERIFY
    assert jitter.confirmation_counters["grasp"] == 0
    assert jitter.use_guidance is True


def test_drop_recovers_guidance_and_regrasp_turns_it_off_again():
    fsm, step = _confirmed_fsm()

    for offset in range(3):
        result = fsm.update(
            _evidence(
                step + offset,
                object_position=(0.08, 0.0, 0.0),
                eef_position=(0.0, 0.0, 0.09),
            )
        )
    assert result.state_after is FSMState.RECOVERY
    assert result.use_guidance is True
    assert result.transition_reason == "drop_confirmed_3_steps"

    fsm.update(
        _evidence(
            step + 3,
            command=-1.0,
            aperture=0.08,
            object_position=(0.08, 0.0, 0.0),
            eef_position=(0.08, 0.0, 0.04),
        )
    )
    grasp_candidate = fsm.update(
        _evidence(
            step + 4,
            command=1.0,
            object_position=(0.08, 0.0, 0.0),
            eef_position=(0.08, 0.0, 0.04),
        )
    )
    assert grasp_candidate.state_after is FSMState.GRASP_VERIFY

    for offset in range(1, 5):
        result = fsm.update(
            _evidence(
                step + 4 + offset,
                object_position=(0.08, 0.0, 0.025),
                eef_position=(0.08, 0.0, 0.065),
            )
        )
    assert result.state_after is FSMState.TRANSPORT
    assert result.use_guidance is False


def test_release_inside_destination_waits_for_success_then_done():
    fsm, step = _confirmed_fsm()

    release = fsm.update(
        _evidence(
            step,
            command=-1.0,
            aperture=0.08,
            object_position=(0.0, 0.30, 0.02),
        )
    )
    assert release.state_after is FSMState.RELEASE_VERIFY
    assert release.use_guidance is False

    done = fsm.update(
        _evidence(
            step + 1,
            command=-1.0,
            aperture=0.08,
            object_position=(0.0, 0.30, 0.01),
            success=True,
        )
    )
    assert done.state_after is FSMState.DONE
    assert done.current_stage == 0
    assert done.use_guidance is False


def test_release_outside_destination_requires_three_failure_frames_for_recovery():
    fsm, step = _confirmed_fsm()

    for offset in range(2):
        result = fsm.update(
            _evidence(
                step + offset,
                command=-1.0,
                aperture=0.08,
                object_position=(0.20, 0.0, 0.0),
            )
        )
        assert result.state_after is FSMState.TRANSPORT

    result = fsm.update(
        _evidence(
            step + 2,
            command=-1.0,
            aperture=0.08,
            object_position=(0.20, 0.0, 0.0),
        )
    )
    assert result.state_after is FSMState.RECOVERY
    assert result.use_guidance is True


def test_release_verify_timeout_is_exactly_eight_steps():
    fsm, step = _confirmed_fsm()
    fsm.update(
        _evidence(
            step,
            command=-1.0,
            aperture=0.08,
            object_position=(0.0, 0.30, 0.02),
        )
    )

    for offset in range(1, 8):
        result = fsm.update(
            _evidence(
                step + offset,
                command=-1.0,
                aperture=0.08,
                object_position=(0.0, 0.30, 0.02),
            )
        )
        assert result.state_after is FSMState.RELEASE_VERIFY

    result = fsm.update(
        _evidence(
            step + 8,
            command=-1.0,
            aperture=0.08,
            object_position=(0.0, 0.30, 0.02),
        )
    )
    assert result.state_after is FSMState.RECOVERY
    assert result.transition_reason == "release_verify_timeout_8_steps"


def test_done_is_terminal_and_cannot_roll_back():
    fsm, step = _confirmed_fsm()
    fsm.update(
        _evidence(
            step,
            command=-1.0,
            aperture=0.08,
            object_position=(0.0, 0.30, 0.02),
        )
    )
    fsm.update(
        _evidence(
            step + 1,
            command=-1.0,
            aperture=0.08,
            object_position=(0.0, 0.30, 0.01),
            success=True,
        )
    )

    result = fsm.update(
        _evidence(
            step + 2,
            command=1.0,
            object_position=(0.5, 0.5, -0.5),
            eef_position=(0.0, 0.0, 0.5),
        )
    )
    assert result.state_before is FSMState.DONE
    assert result.state_after is FSMState.DONE
    assert result.state_changed is False
    assert result.transition_reason == "done_terminal_hold"


def test_invalid_or_nonfinite_physical_evidence_is_rejected():
    fsm = StageGuidanceFSM(PhysicalFSMConfig())
    with pytest.raises(ValueError, match="finite"):
        fsm.update(_evidence(0, object_position=(np.nan, 0.0, 0.0)))

