import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from mode_gate.agents import PlannerAgent, VerifierAgent
from mode_gate.types import (
    ActionChunkBatch,
    GateContext,
    ModeEvidence,
    PlannerAction,
    RoundEvidence,
    TaskSpaceTrajectoryBatch,
)


def _history(tmp_path: Path):
    context = GateContext(
        context_id="agent-context",
        observation_image=np.zeros((8, 8, 3), dtype=np.uint8),
        task_instruction="move the mug to the plate",
        task_stage="1",
    )
    actions = ActionChunkBatch(
        actions=np.zeros((3, 2, 7), dtype=np.float32),
        sample_ids=("s0", "s1", "s2"),
        context_id=context.context_id,
        round_id=1,
        checkpoint_id="cp-1",
        action_space="delta_ee_pose",
        coordinate_frame="world",
    )
    card = tmp_path / "mode.png"
    card.write_bytes(b"not-a-real-png-but-valid-for-request-shape")
    mode = ModeEvidence(
        mode_id="r001-m00",
        component_index=0,
        weight=0.05,
        member_indices=np.array([0, 1, 2]),
        representative_indices={"medoid": 0, "diverse": 1, "boundary": 2},
        representative_sample_ids={"medoid": "s0", "diverse": "s1", "boundary": "s2"},
        card_path=card,
        projection_unavailable=False,
    )
    orientations = np.zeros((3, 3, 4))
    orientations[:, :, 3] = 1.0
    trajectories = TaskSpaceTrajectoryBatch(
        positions=np.zeros((3, 3, 3)),
        orientations=orientations,
        grippers=np.zeros((3, 3)),
        sample_ids=actions.sample_ids,
    )
    evidence = RoundEvidence(
        context_id=context.context_id,
        round_id=1,
        checkpoint_id="cp-1",
        action_batch=actions,
        trajectories=trajectories,
        normalized_positions=np.zeros((3, 8, 3)),
        normalized_rotvecs=np.zeros((3, 8, 3)),
        normalized_grippers=np.zeros((3, 8)),
        descriptors=np.zeros((3, 4)),
        reduced_descriptors=np.zeros((3, 2)),
        labels=np.zeros(3, dtype=int),
        responsibilities=np.ones((3, 1)),
        modes=(mode,),
        fit_degraded=False,
        fit_metadata={},
    )
    return context, evidence, mode


class _OpenAIModels:
    def __init__(self):
        self.retrieved = None

    def retrieve(self, model):
        self.retrieved = model


class _Responses:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=json.dumps(self.payload))


def test_planner_uses_exact_model_responses_images_and_strict_schema(tmp_path):
    context, evidence, _ = _history(tmp_path)
    payload = {
        "decision": "CONTINUE_STEERING",
        "required_trajectory_pattern": "move over plate then lower",
        "mode_assessments": [
            {
                "mode_id": "r001-m00",
                "behavior_interpretation": "transfer",
                "task_compatibility": "possible",
                "difficulty": "medium",
                "evidence": ["path approaches plate"],
            }
        ],
        "supporting_mode_ids": ["r001-m00"],
        "verifier_candidate_mode_ids": ["r001-m00"],
        "rationale": "pattern is plausible despite low mass",
    }
    client = SimpleNamespace(models=_OpenAIModels(), responses=_Responses(payload))
    planner = PlannerAgent(client=client)

    planner.preflight()
    decision = planner.decide(context, (evidence,))

    assert client.models.retrieved == "gpt-5.6-sol"
    assert decision.decision is PlannerAction.CONTINUE_STEERING
    request = client.responses.kwargs
    assert request["model"] == "gpt-5.6-sol"
    assert request["reasoning"] == {"effort": "high"}
    assert request["text"]["format"]["strict"] is True
    assert any(
        item["type"] == "input_image"
        for item in request["input"][0]["content"]
    )


class _GoogleModels:
    def __init__(self):
        self.model = None

    def get(self, *, model):
        self.model = model


class _Interactions:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=json.dumps(self.payload))


def test_verifier_uses_google_interactions_high_thinking_and_real_chunks(tmp_path):
    context, evidence, mode = _history(tmp_path)
    payload = {
        "mode_id": "r001-m00",
        "task_match": "NEAR_MISS",
        "missing_subpatterns": ["release"],
        "predicted_failure_types": ["keeps holding mug"],
        "candidate_reward_signals": ["mug-to-plate distance"],
        "uncertainty": 0.3,
        "evidence": ["trajectory reaches plate region"],
    }
    client = SimpleNamespace(
        models=_GoogleModels(),
        interactions=_Interactions(payload),
    )
    verifier = VerifierAgent(client=client)

    verifier.preflight()
    result = verifier.verify(context, evidence, mode)

    assert client.models.model == "gemini-robotics-er-2-preview"
    assert result.mode_id == mode.mode_id
    request = client.interactions.kwargs
    assert request["model"] == "gemini-robotics-er-2-preview"
    assert request["generation_config"] == {"thinking_level": "high"}
    assert request["response_format"]["mime_type"] == "application/json"
    assert [item["type"] for item in request["input"]] == ["text", "image"]
    assert "action_chunk" in request["input"][0]["text"]
