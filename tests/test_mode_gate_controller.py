from pathlib import Path

import numpy as np

from mode_gate.config import ModeGateConfig
from mode_gate.controller import ModeGateController
from mode_gate.types import (
    ActionChunkBatch,
    ControllerStatus,
    GateContext,
    ModeEvidence,
    PlannerAction,
    PlannerDecision,
    PlannerModeAssessment,
    RoundEvidence,
    SteeringSnapshot,
    TaskSpaceTrajectoryBatch,
    VerifierEvidence,
)


def _context(context_id="controller-context", stage="1"):
    return GateContext(
        context_id=context_id,
        observation_image=np.zeros((16, 16, 3), dtype=np.uint8),
        task_instruction="open the drawer",
        task_stage=stage,
    )


class _BlackBox:
    def __init__(self, complete_round=None):
        self.complete_round = complete_round
        self.round = 0

    def advance(self, context):
        self.round += 1
        return SteeringSnapshot(
            checkpoint_id=f"checkpoint-{self.round}",
            is_complete=self.complete_round == self.round,
            execution_action_chunk=f"execute-{self.round}",
        )

    def sample(self, snapshot, context, count):
        return ActionChunkBatch(
            actions=np.zeros((count, 4, 7), dtype=np.float32),
            sample_ids=[f"r{self.round}-s{index}" for index in range(count)],
            context_id=context.context_id,
            round_id=self.round,
            checkpoint_id=snapshot.checkpoint_id,
            action_space="delta_ee_pose",
            coordinate_frame="world",
        )


class _Gate:
    def analyze(self, context, batch, round_dir):
        card_path = round_dir / f"mode_card_r{batch.round_id:03d}-m00.png"
        card_path.write_bytes(b"png")
        mode_id = f"r{batch.round_id:03d}-m00"
        mode = ModeEvidence(
            mode_id=mode_id,
            component_index=0,
            weight=1.0,
            member_indices=np.arange(batch.sample_count),
            representative_indices={"medoid": 0, "diverse": 1, "boundary": 2},
            representative_sample_ids={
                "medoid": batch.sample_ids[0],
                "diverse": batch.sample_ids[1],
                "boundary": batch.sample_ids[2],
            },
            card_path=card_path,
            projection_unavailable=False,
        )
        positions = np.zeros((batch.sample_count, 5, 3))
        orientations = np.zeros((batch.sample_count, 5, 4))
        orientations[:, :, 3] = 1.0
        grippers = np.zeros((batch.sample_count, 5))
        trajectories = TaskSpaceTrajectoryBatch(
            positions=positions,
            orientations=orientations,
            grippers=grippers,
            sample_ids=batch.sample_ids,
        )
        return RoundEvidence(
            context_id=context.context_id,
            round_id=batch.round_id,
            checkpoint_id=batch.checkpoint_id,
            action_batch=batch,
            trajectories=trajectories,
            normalized_positions=np.zeros((batch.sample_count, 8, 3)),
            normalized_rotvecs=np.zeros((batch.sample_count, 8, 3)),
            normalized_grippers=np.zeros((batch.sample_count, 8)),
            descriptors=np.zeros((batch.sample_count, 10)),
            reduced_descriptors=np.zeros((batch.sample_count, 2)),
            labels=np.zeros(batch.sample_count, dtype=int),
            responsibilities=np.ones((batch.sample_count, 1)),
            modes=(mode,),
            fit_degraded=False,
            fit_metadata={"selected_components": 1},
        )


class _Planner:
    def __init__(self, action, select_verifier=True):
        self.action = action
        self.select_verifier = select_verifier
        self.calls = 0

    def decide(self, context, history):
        self.calls += 1
        current_mode = history[-1].modes[0].mode_id
        return PlannerDecision(
            decision=self.action,
            required_trajectory_pattern="reach then pull",
            mode_assessments=(
                PlannerModeAssessment(
                    mode_id=current_mode,
                    behavior_interpretation="pulling motion",
                    task_compatibility="possible",
                    difficulty="medium",
                    evidence=("moves outward",),
                ),
            ),
            supporting_mode_ids=(current_mode,),
            verifier_candidate_mode_ids=(current_mode,) if self.select_verifier else (),
            rationale="test",
        )


class _Verifier:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def verify(self, context, round_evidence, mode):
        self.calls.append((round_evidence.round_id, mode.mode_id))
        if self.fail:
            raise RuntimeError("verifier failed")
        return VerifierEvidence(
            mode_id=mode.mode_id,
            task_match="NEAR_MISS",
            missing_subpatterns=("grasp",),
            predicted_failure_types=("slip",),
            candidate_reward_signals=("drawer displacement",),
            uncertainty=0.2,
            evidence=("offline evidence",),
        )


def _controller(planner, verifier, max_rounds=5):
    config = ModeGateConfig(sample_count=6, max_rounds=max_rounds)
    return ModeGateController(config, _Gate(), planner, verifier)


def test_complete_snapshot_returns_original_execution_chunk_without_waiting(tmp_path):
    planner = _Planner(PlannerAction.CONTINUE_STEERING)
    controller = _controller(planner, _Verifier())

    result = controller.run(_context(), _BlackBox(complete_round=1), tmp_path)

    assert result.status is ControllerStatus.STEERING_COMPLETE
    assert result.execution_action_chunk == "execute-1"
    assert result.rounds == 1


def test_planner_expansion_overrides_complete_and_waits_for_verifier(tmp_path):
    verifier = _Verifier()
    controller = _controller(
        _Planner(PlannerAction.REQUEST_EXPANSION), verifier
    )

    result = controller.run(_context(), _BlackBox(complete_round=1), tmp_path)

    assert result.status is ControllerStatus.REQUEST_EXPANSION
    assert result.expansion_request.trigger_reason == "planner_requested_expansion"
    assert result.expansion_request.missing_or_hard_pattern == "grasp"
    assert verifier.calls == [(1, "r001-m00")]


def test_fifth_incomplete_round_forces_expansion(tmp_path):
    black_box = _BlackBox(complete_round=None)
    planner = _Planner(PlannerAction.CONTINUE_STEERING, select_verifier=False)
    controller = _controller(planner, _Verifier(), max_rounds=5)

    result = controller.run(_context(), black_box, tmp_path)

    assert result.status is ControllerStatus.REQUEST_EXPANSION
    assert result.expansion_request.trigger_reason == "max_steering_rounds_reached"
    assert black_box.round == 5
    assert planner.calls == 5


def test_active_verifier_failure_aborts_instead_of_triggering_expansion(tmp_path):
    controller = _controller(
        _Planner(PlannerAction.REQUEST_EXPANSION),
        _Verifier(fail=True),
    )

    result = controller.run(_context(), _BlackBox(complete_round=1), tmp_path)

    assert result.status is ControllerStatus.ABORTED
    assert "verifier failed" in result.error


def test_new_context_starts_a_fresh_round_history(tmp_path):
    class RecordingPlanner(_Planner):
        def __init__(self):
            super().__init__(PlannerAction.CONTINUE_STEERING, select_verifier=False)
            self.histories = []

        def decide(self, context, history):
            self.histories.append((context.context_id, len(history), history[0].round_id))
            return super().decide(context, history)

    planner = RecordingPlanner()
    controller = _controller(planner, _Verifier())

    first = controller.run(
        _context("context-a", "1"), _BlackBox(complete_round=1), tmp_path
    )
    second = controller.run(
        _context("context-b", "2"), _BlackBox(complete_round=1), tmp_path
    )

    assert first.status is ControllerStatus.STEERING_COMPLETE
    assert second.status is ControllerStatus.STEERING_COMPLETE
    assert planner.histories == [
        ("context-a", 1, 1),
        ("context-b", 1, 1),
    ]


def test_planner_failure_aborts_session(tmp_path):
    class FailingPlanner:
        def decide(self, context, history):
            raise RuntimeError("planner failed")

    controller = _controller(FailingPlanner(), _Verifier())
    result = controller.run(_context(), _BlackBox(complete_round=1), tmp_path)

    assert result.status is ControllerStatus.ABORTED
    assert "planner failed" in result.error
