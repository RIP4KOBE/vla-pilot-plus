"""Independent multimodal Planner and Verifier clients."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .types import (
    GateContext,
    ModeEvidence,
    PlannerAction,
    PlannerDecision,
    PlannerModeAssessment,
    RoundEvidence,
    VerifierEvidence,
)


class AgentCallError(RuntimeError):
    pass


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _PlannerModeAssessment(_StrictModel):
    mode_id: str
    behavior_interpretation: str
    task_compatibility: str
    difficulty: str
    evidence: list[str]


class _PlannerPayload(_StrictModel):
    decision: Literal["CONTINUE_STEERING", "REQUEST_EXPANSION"]
    required_trajectory_pattern: str
    mode_assessments: list[_PlannerModeAssessment]
    supporting_mode_ids: list[str]
    verifier_candidate_mode_ids: list[str]
    rationale: str


class _VerifierPayload(_StrictModel):
    mode_id: str
    task_match: Literal["POSSIBLE", "NEAR_MISS", "UNLIKELY"]
    missing_subpatterns: list[str]
    predicted_failure_types: list[str]
    candidate_reward_signals: list[str]
    uncertainty: float = Field(ge=0.0, le=1.0)
    evidence: list[str]


class PlannerAgent:
    """GPT-5.6 Sol Planner using Responses API structured outputs."""

    def __init__(
        self,
        *,
        model: str = "gpt-5.6-sol",
        reasoning_effort: str = "high",
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        if model != "gpt-5.6-sol":
            raise ValueError("Planner model substitution is not allowed")
        self.model = model
        self.reasoning_effort = reasoning_effort
        if client is None:
            key = api_key or os.environ.get("MODE_GATE_OPENAI_API_KEY")
            if not key:
                raise AgentCallError("MODE_GATE_OPENAI_API_KEY is required")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise AgentCallError("the openai package is required for Planner") from exc
            client = OpenAI(api_key=key)
        self.client = client

    def preflight(self) -> None:
        try:
            self.client.models.retrieve(self.model)
        except Exception as exc:
            raise AgentCallError(
                f"Planner model preflight failed for exact model {self.model}: {exc}"
            ) from exc

    def decide(
        self,
        context: GateContext,
        history: Sequence[RoundEvidence],
    ) -> PlannerDecision:
        prompt, card_paths = _planner_prompt(context, history)
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for card_path in card_paths:
            content.append(
                {
                    "type": "input_image",
                    "image_url": _data_url(card_path),
                    "detail": "high",
                }
            )
        request_summary = {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "prompt": prompt,
            "mode_card_paths": [str(path) for path in card_paths],
        }
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=(
                    "You are the top-level robot trajectory-mode Planner. Judge whether "
                    "any sampled trajectory MODE could satisfy the task. Exact pointwise "
                    "trajectory equality is not required. Mixture weight is statistical "
                    "context only and must never be used as a hard feasibility threshold. "
                    "Return only the required strict JSON decision."
                ),
                reasoning={"effort": self.reasoning_effort},
                input=[{"role": "user", "content": content}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "trajectory_mode_planner_decision",
                        "strict": True,
                        "schema": _PlannerPayload.model_json_schema(),
                    }
                },
                store=False,
            )
            output_text = getattr(response, "output_text", None)
            if not output_text:
                raise ValueError("Planner returned no output_text")
            parsed = _PlannerPayload.model_validate_json(output_text)
        except Exception as exc:
            raise AgentCallError(f"Planner call or structured-output validation failed: {exc}") from exc

        known_modes = {mode.mode_id for round_item in history for mode in round_item.modes}
        referenced = set(parsed.supporting_mode_ids) | set(parsed.verifier_candidate_mode_ids)
        unknown = referenced - known_modes
        if unknown:
            raise AgentCallError(f"Planner referenced unknown mode IDs: {sorted(unknown)}")
        assessed = {item.mode_id for item in parsed.mode_assessments}
        if assessed != known_modes:
            raise AgentCallError(
                "Planner must assess every historical mode exactly once; "
                f"expected {sorted(known_modes)}, got {sorted(assessed)}"
            )

        response_dict = parsed.model_dump()
        return PlannerDecision(
            decision=PlannerAction(parsed.decision),
            required_trajectory_pattern=parsed.required_trajectory_pattern,
            mode_assessments=tuple(
                PlannerModeAssessment(
                    mode_id=item.mode_id,
                    behavior_interpretation=item.behavior_interpretation,
                    task_compatibility=item.task_compatibility,
                    difficulty=item.difficulty,
                    evidence=tuple(item.evidence),
                )
                for item in parsed.mode_assessments
            ),
            supporting_mode_ids=tuple(parsed.supporting_mode_ids),
            verifier_candidate_mode_ids=tuple(parsed.verifier_candidate_mode_ids),
            rationale=parsed.rationale,
            raw_response={"request": request_summary, "response": response_dict},
        )


class VerifierAgent:
    """Gemini Robotics-ER Verifier using the official Interactions API."""

    def __init__(
        self,
        *,
        model: str = "gemini-robotics-er-2-preview",
        thinking_level: str = "high",
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        if model != "gemini-robotics-er-2-preview":
            raise ValueError("Verifier model substitution is not allowed")
        self.model = model
        self.thinking_level = thinking_level
        if client is None:
            key = api_key or os.environ.get("MODE_GATE_GEMINI_API_KEY")
            if not key:
                raise AgentCallError("MODE_GATE_GEMINI_API_KEY is required")
            try:
                from google import genai
            except ImportError as exc:
                raise AgentCallError("google-genai==2.17.0 is required for Verifier") from exc
            client = genai.Client(api_key=key)
        if not hasattr(client, "interactions"):
            raise AgentCallError("installed google-genai does not expose Interactions API")
        self.client = client

    def preflight(self) -> None:
        try:
            self.client.models.get(model=self.model)
        except Exception as exc:
            raise AgentCallError(
                f"Verifier model preflight failed for exact model {self.model}: {exc}"
            ) from exc

    def verify(
        self,
        context: GateContext,
        round_evidence: RoundEvidence,
        mode: ModeEvidence,
    ) -> VerifierEvidence:
        prompt = _verifier_prompt(context, round_evidence, mode)
        request_summary = {
            "model": self.model,
            "thinking_level": self.thinking_level,
            "prompt": prompt,
            "mode_card_path": str(mode.card_path),
        }
        try:
            interaction = self.client.interactions.create(
                model=self.model,
                system_instruction=(
                    "You are an offline robot trajectory verifier. Use only the supplied "
                    "observation, Mode Card, real action chunks, and statistics. Do not "
                    "claim simulator or real-world execution. Return strict JSON."
                ),
                input=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "data": _base64_file(mode.card_path),
                        "mime_type": "image/png",
                    },
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _VerifierPayload.model_json_schema(),
                },
                generation_config={"thinking_level": self.thinking_level},
                store=False,
            )
            output_text = getattr(interaction, "output_text", None)
            if not output_text:
                raise ValueError("Verifier returned no output_text")
            parsed = _VerifierPayload.model_validate_json(output_text)
        except Exception as exc:
            raise AgentCallError(f"Verifier call or structured-output validation failed: {exc}") from exc
        if parsed.mode_id != mode.mode_id:
            raise AgentCallError(
                f"Verifier returned mode_id={parsed.mode_id}, expected {mode.mode_id}"
            )
        response_dict = parsed.model_dump()
        return VerifierEvidence(
            mode_id=parsed.mode_id,
            task_match=parsed.task_match,
            missing_subpatterns=tuple(parsed.missing_subpatterns),
            predicted_failure_types=tuple(parsed.predicted_failure_types),
            candidate_reward_signals=tuple(parsed.candidate_reward_signals),
            uncertainty=parsed.uncertainty,
            evidence=tuple(parsed.evidence),
            raw_response={"request": request_summary, "response": response_dict},
        )


def _planner_prompt(
    context: GateContext,
    history: Sequence[RoundEvidence],
) -> tuple[str, list[Path]]:
    rounds = []
    card_paths: list[Path] = []
    for round_item in history:
        modes = []
        for mode in round_item.modes:
            card_paths.append(mode.card_path)
            modes.append(
                {
                    "mode_id": mode.mode_id,
                    "mixture_weight": mode.weight,
                    "statistics": dict(mode.statistics),
                    "representative_sample_ids": dict(mode.representative_sample_ids),
                    "projection_unavailable": mode.projection_unavailable,
                }
            )
        rounds.append(
            {
                "round_id": round_item.round_id,
                "checkpoint_id": round_item.checkpoint_id,
                "fit_degraded": round_item.fit_degraded,
                "modes": modes,
            }
        )
    prompt = (
        "Decide whether at least one trajectory pattern could plausibly accomplish the "
        "task. Judge pattern semantics, not exact numerical equality. Select possible or "
        "near-miss modes for offline verification. If no mode is viable or all require a "
        "difficult missing behavior, request expansion.\n\n"
        f"Task: {context.task_instruction}\n"
        f"Task stage: {context.task_stage}\n"
        f"Context ID: {context.context_id}\n"
        f"Round/mode metadata: {json.dumps(rounds, ensure_ascii=False)}"
    )
    return prompt, card_paths


def _verifier_prompt(
    context: GateContext,
    round_evidence: RoundEvidence,
    mode: ModeEvidence,
) -> str:
    representatives = {
        role: {
            "sample_id": round_evidence.action_batch.sample_ids[index],
            "action_chunk": round_evidence.action_batch.actions[index].tolist(),
        }
        for role, index in mode.representative_indices.items()
    }
    payload = {
        "task": context.task_instruction,
        "task_stage": context.task_stage,
        "context_id": context.context_id,
        "round_id": round_evidence.round_id,
        "mode_id": mode.mode_id,
        "mixture_weight": mode.weight,
        "mode_statistics": dict(mode.statistics),
        "representatives": representatives,
        "action_space": round_evidence.action_batch.action_space,
        "coordinate_frame": round_evidence.action_batch.coordinate_frame,
    }
    return (
        "Assess whether this trajectory MODE is possible, a near miss, or unlikely for "
        "the task. Identify missing sub-patterns and predicted failures, and propose "
        "observable reward signals that an expansion mechanism could use. Do not assert "
        "that the actions were executed.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _base64_file(path: Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _data_url(path: Path) -> str:
    return f"data:image/png;base64,{_base64_file(path)}"

