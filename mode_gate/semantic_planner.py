"""Gemini semantic mode scorer.  It never selects a controller route."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import time
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .agents import AgentCallError
from .types import (
    GateContext,
    GeometryEvidence,
    RoundEvidence,
    SemanticModeScore,
    SemanticPlan,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ModeScore(_StrictModel):
    mode_id: str
    semantic_score: float = Field(ge=0.0, le=1.0)
    reason: str
    predicted_failure_types: list[str]


class _SemanticPayload(_StrictModel):
    modes: list[_ModeScore]
    required_trajectory_pattern: str
    observed_stage_id: str = Field(pattern=r"^(?:UNKNOWN|stage_[1-9][0-9]*)$")
    stage_confidence: float = Field(ge=0.0, le=1.0)


class GeminiSemanticPlanner:
    def __init__(
        self,
        *,
        model: str = "gemini-robotics-er-2-preview",
        prompt_version: str = "mode-scorer-v3",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        cache_dir: Path | None = None,
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        if model != "gemini-robotics-er-2-preview":
            raise ValueError(
                "v2 semantic planner is frozen to gemini-robotics-er-2-preview"
            )
        self.model = model
        self.prompt_version = prompt_version
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        if client is None:
            key = (
                api_key
                or os.environ.get("MODE_GATE_GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
            )
            if not key:
                raise AgentCallError(
                    "MODE_GATE_GEMINI_API_KEY or GOOGLE_API_KEY is required "
                    "for Gemini mode scoring"
                )
            try:
                from google import genai
                from google.genai import types
            except ImportError as exc:
                raise AgentCallError("google-genai is required for Gemini mode scoring") from exc
            client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    timeout=max(1, int(self.timeout_seconds * 1000))
                ),
            )
        self.client = client

    def preflight(self, *, exercise_interactions: bool = False) -> None:
        try:
            _run_with_timeout(
                lambda: self.client.models.get(model=self.model),
                self.timeout_seconds,
                "Gemini planner preflight",
            )
            if exercise_interactions:
                response = self._call_with_timeout(
                    (
                        "This is a provider connectivity canary. Return exactly one mode "
                        "with mode_id='canary-m0', semantic_score=1.0, a short reason, no "
                        "predicted failures, required_trajectory_pattern='none', "
                        "observed_stage_id='UNKNOWN', and stage_confidence=1.0."
                    ),
                    base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAHnOcQAAAAABJRU5ErkJggg=="
                    ),
                )
                output_text = getattr(response, "output_text", None) or getattr(
                    response, "text", None
                )
                if not output_text:
                    raise ValueError("Gemini Interactions canary returned no JSON text")
                payload = _SemanticPayload.model_validate_json(output_text)
                if [item.mode_id for item in payload.modes] != ["canary-m0"]:
                    raise ValueError("Gemini Interactions canary returned the wrong mode ID")
        except Exception as exc:
            raise AgentCallError(f"Gemini planner preflight failed: {exc}") from exc

    def score(
        self,
        context: GateContext,
        evidence: RoundEvidence,
        geometry: Sequence[GeometryEvidence],
        combined_card_path: Path,
        *,
        object_distances: Mapping[str, Mapping[str, float]] | None = None,
        progress_history: Sequence[Mapping[str, Any]] = (),
    ) -> SemanticPlan:
        expected = {mode.mode_id for mode in evidence.modes}
        if not 1 <= len(expected) <= 4:
            raise ValueError("Gemini planner expects K in [1, 4]")
        if {item.mode_id for item in geometry} != expected:
            raise ValueError("geometry must cover each mode exactly once")
        prompt = self._prompt(
            context,
            evidence,
            geometry,
            object_distances or {},
            progress_history,
        )
        image_bytes = Path(combined_card_path).read_bytes()
        cache_key = hashlib.sha256(
            b"\0".join(
                [
                    self.model.encode(),
                    self.prompt_version.encode(),
                    prompt.encode("utf-8"),
                    image_bytes,
                ]
            )
        ).hexdigest()
        cached = self._read_cache(cache_key)
        if cached is not None:
            return self._to_plan(cached["payload"], expected, {
                **cached.get("metadata", {}),
                "cache_hit": True,
                "cache_key": cache_key,
            })

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                response = self._call_with_timeout(prompt, image_bytes)
                output_text = getattr(response, "text", None) or getattr(
                    response, "output_text", None
                )
                if not output_text:
                    raise ValueError("Gemini returned no JSON text")
                payload = _SemanticPayload.model_validate_json(output_text)
                usage = getattr(response, "usage_metadata", None) or getattr(
                    response, "usage", None
                )
                metadata = {
                    "model": self.model,
                    "prompt_version": self.prompt_version,
                    "latency_seconds": time.monotonic() - started,
                    "attempt": attempt + 1,
                    "cache_hit": False,
                    "cache_key": cache_key,
                    "token_usage": _usage_to_dict(usage),
                }
                value = payload.model_dump()
                plan = self._to_plan(value, expected, metadata)
                self._write_cache(cache_key, value, metadata)
                return plan
            except Exception as exc:
                last_error = exc
        raise AgentCallError(
            f"Gemini semantic scoring failed after {self.max_retries + 1} attempts: "
            f"{last_error}"
        ) from last_error

    def _call_with_timeout(self, prompt: str, image_bytes: bytes) -> Any:
        def call() -> Any:
            return self.client.interactions.create(
                model=self.model,
                system_instruction=(
                    "You are a robot trajectory semantic scorer. Use only the supplied "
                    "observation overlay and structured trajectory measurements. Score "
                    "every mode exactly once and return strict JSON; never choose a "
                    "controller route. observed_stage_id must be exactly UNKNOWN or "
                    "stage_N, where N is a positive integer; never include descriptions, "
                    "object names, keypoint IDs, or parenthetical suffixes in that field."
                ),
                input=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                        "mime_type": "image/png",
                    },
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _SemanticPayload.model_json_schema(),
                },
                generation_config={"thinking_level": "high"},
                store=False,
            )

        return _run_with_timeout(
            call,
            self.timeout_seconds,
            "Gemini mode scoring",
        )

    def _prompt(
        self,
        context: GateContext,
        evidence: RoundEvidence,
        geometry: Sequence[GeometryEvidence],
        object_distances: Mapping[str, Mapping[str, float]],
        progress_history: Sequence[Mapping[str, Any]],
    ) -> str:
        geometry_by_id = {item.mode_id: item for item in geometry}
        modes = []
        for mode in evidence.modes:
            index = int(mode.representative_indices["medoid"])
            gripper = evidence.normalized_grippers[index]
            switches = [
                int(value)
                for value in (
                    (gripper[1:] >= 0.0) != (gripper[:-1] >= 0.0)
                ).nonzero()[0]
            ]
            modes.append(
                {
                    "mode_id": mode.mode_id,
                    "weight": mode.weight,
                    "geometry": {
                        "collision_risk": geometry_by_id[mode.mode_id].collision_risk,
                        "reachability": geometry_by_id[mode.mode_id].reachability,
                        "grasp_plausibility": geometry_by_id[mode.mode_id].grasp_plausibility,
                        "hard_safety_veto": geometry_by_id[mode.mode_id].hard_safety_veto,
                    },
                    "endpoint_object_distances": object_distances.get(mode.mode_id, {}),
                    "gripper_switch_phases": switches,
                }
            )
        payload = {
            "prompt_version": self.prompt_version,
            "instruction": context.task_instruction,
            "current_stage": context.task_stage,
            "context_id": context.context_id,
            "progress_history": list(progress_history),
            "modes": modes,
        }
        return (
            "Score the semantic compatibility of every colored trajectory mode in the "
            "single supplied overlay. Return each mode exactly once. Scores express task "
            "compatibility only; do not choose EXECUTE, RE-STEER, or EXPANSION. Infer the "
            "observed task stage and the required trajectory pattern. observed_stage_id "
            "MUST be exactly UNKNOWN or stage_N (for example stage_1); keep all natural-"
            "language descriptions and keypoint references out of that identity field. "
            "Return strict JSON.\n\n"
            + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )

    def _to_plan(
        self,
        payload_value: Mapping[str, Any],
        expected: set[str],
        metadata: Mapping[str, Any],
    ) -> SemanticPlan:
        payload = _SemanticPayload.model_validate(payload_value)
        returned = [item.mode_id for item in payload.modes]
        if len(returned) != len(set(returned)) or set(returned) != expected:
            raise AgentCallError(
                "Gemini must return every mode exactly once; "
                f"expected={sorted(expected)}, got={sorted(returned)}"
            )
        return SemanticPlan(
            mode_scores=tuple(
                SemanticModeScore(
                    mode_id=item.mode_id,
                    semantic_score=item.semantic_score,
                    reason=item.reason,
                    predicted_failure_types=tuple(item.predicted_failure_types),
                )
                for item in payload.modes
            ),
            required_trajectory_pattern=payload.required_trajectory_pattern,
            observed_stage_id=payload.observed_stage_id,
            stage_confidence=payload.stage_confidence,
            model=self.model,
            prompt_version=self.prompt_version,
            raw_response={"metadata": dict(metadata), "payload": payload.model_dump()},
        )

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(
        self,
        key: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> None:
        if self.cache_dir is None:
            return
        target = self.cache_dir / f"{key}.json"
        temporary = self.cache_dir / f".{key}.{os.getpid()}.tmp"
        temporary.write_text(
            json.dumps(
                {"payload": payload, "metadata": metadata},
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, target)


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return dict(usage.model_dump())
    if isinstance(usage, Mapping):
        return dict(usage)
    result = {}
    for name in (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
    ):
        if hasattr(usage, name):
            result[name] = getattr(usage, name)
    return result


def _run_with_timeout(call: Any, timeout_seconds: float, label: str) -> Any:
    """Run a provider call with a true caller-side deadline.

    The SDK-level HTTP timeout handles real network calls.  The daemon thread
    additionally protects mocked/custom clients and, unlike a context-managed
    ThreadPoolExecutor, does not wait forever during shutdown after timeout.
    """

    result_queue: "queue.Queue[tuple[bool, Any]]" = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            result_queue.put((True, call()))
        except BaseException as exc:  # Preserve provider exception type/cause.
            result_queue.put((False, exc))

    worker = threading.Thread(target=invoke, name="gemini-provider-call", daemon=True)
    worker.start()
    try:
        succeeded, value = result_queue.get(timeout=float(timeout_seconds))
    except queue.Empty as exc:
        raise AgentCallError(f"{label} exceeded {timeout_seconds:.1f}s") from exc
    if not succeeded:
        raise value
    return value


__all__ = ["GeminiSemanticPlanner"]
