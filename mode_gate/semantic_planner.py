"""Account-backed semantic mode scorer. It never selects a controller route."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .agents import AgentCallError
from .types import (
    GateContext,
    GeometryEvidence,
    RoundEvidence,
    SemanticCandidateScore,
    SemanticPlan,
)


LOGGER = logging.getLogger(__name__)

_RETRYABLE_SEMANTIC_NETWORK_MARKERS = (
    "apiconnectionerror",
    "connecterror",
    "connecttimeout",
    "connection refused",
    "connection reset",
    "readtimeout",
    "remoteprotocolerror",
    "unexpected_eof_while_reading",
    "eof occurred in violation of protocol",
    "server disconnected",
    "timed out",
    "exceeded 60.0s",
    "resource_exhausted",
    "unavailable",
    "429",
    "500 internal server error",
    "502",
    "503",
    "504",
)


def is_retryable_semantic_network_error(error: BaseException) -> bool:
    """Return whether an agent failure is a transient provider/transport error."""

    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
    message = "\n".join(parts).lower()
    return any(marker in message for marker in _RETRYABLE_SEMANTIC_NETWORK_MARKERS)


def score_semantics_with_network_recovery(
    planner: Any,
    *args: Any,
    recovery_label: str,
    sleep_fn: Callable[[float], Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Keep a warm runtime alive while a transient Gemini outage recovers.

    The same in-memory evidence, overlay, prompt inputs, and cache identity are
    reused on every attempt. Non-network and structured-output failures remain
    fail-closed rather than being retried indefinitely.
    """

    retry_index = 0
    sleeper = sleep_fn or time.sleep
    while True:
        try:
            return planner.score(*args, **kwargs)
        except AgentCallError as exc:
            if not is_retryable_semantic_network_error(exc):
                raise
            delay = min(60.0, 10.0 * (2**min(retry_index, 3)))
            retry_index += 1
            LOGGER.warning(
                "Planner transport failure during %s; keeping models "
                "loaded and retrying the same semantic request in %.0f seconds "
                "(recovery attempt %d): %s",
                recovery_label,
                delay,
                retry_index,
                exc,
            )
            sleeper(delay)


def preflight_with_network_recovery(
    planner: Any,
    *,
    exercise_interactions: bool = False,
    recovery_label: str = "planner preflight",
    sleep_fn: Callable[[float], Any] | None = None,
) -> None:
    """Keep an initialized planner alive while its connectivity check recovers."""

    retry_index = 0
    sleeper = sleep_fn or time.sleep
    while True:
        try:
            planner.preflight(exercise_interactions=exercise_interactions)
            return
        except AgentCallError as exc:
            if not is_retryable_semantic_network_error(exc):
                raise
            delay = min(60.0, 10.0 * (2**min(retry_index, 3)))
            retry_index += 1
            LOGGER.warning(
                "Gemini network/provider failure during %s; keeping models "
                "loaded and retrying preflight in %.0f seconds "
                "(recovery attempt %d): %s",
                recovery_label,
                delay,
                retry_index,
                exc,
            )
            sleeper(delay)


class GeminiCallBudgetExceeded(AgentCallError):
    """Raised before a provider request would exceed the persisted hard cap."""


class _ProviderCallBudget:
    def __init__(self, *, max_calls: int, ledger_path: Path | None) -> None:
        self.max_calls = int(max_calls)
        if self.max_calls < 0:
            raise ValueError("max_provider_calls must be non-negative")
        self.ledger_path = (
            Path(ledger_path).resolve() if ledger_path is not None else None
        )
        if self.max_calls and self.ledger_path is None:
            raise ValueError(
                "call_ledger_path is required when max_provider_calls is positive"
            )
        if self.ledger_path is not None:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def reserve(
        self,
        *,
        model: str,
        prompt_version: str,
        cache_key: str,
        attempt: int,
        purpose: str,
    ) -> int | None:
        if self.max_calls == 0:
            return None
        assert self.ledger_path is not None
        lock_path = self.ledger_path.with_suffix(self.ledger_path.suffix + ".lock")
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            events = _read_budget_events(self.ledger_path)
            used = sum(
                str(item.get("event")) in {"GEMINI_PROVIDER_CALL_RESERVED", "ACCOUNT_PLANNER_CALL_RESERVED"}
                for item in events
            )
            if used >= self.max_calls:
                raise GeminiCallBudgetExceeded(
                    "Gemini provider-call budget exhausted before request: "
                    f"used={used}, limit={self.max_calls}, ledger={self.ledger_path}"
                )
            sequence = used + 1
            event = {
                "schema_version": "gemini-provider-call-budget-v1",
                "event": ("ACCOUNT_PLANNER_CALL_RESERVED" if model == "gpt-6-astra"
                          or model.startswith("codex-account:") else "GEMINI_PROVIDER_CALL_RESERVED"),
                "auth_mode": ("chatgpt" if model == "gpt-6-astra" or model.startswith("codex-account:") else "historical_api"),
                "sequence": sequence,
                "configured_max_calls": self.max_calls,
                "model": model,
                "prompt_version": prompt_version,
                "cache_key": cache_key,
                "attempt": int(attempt),
                "purpose": purpose,
                "pid": os.getpid(),
                "reserved_at": datetime.now(timezone.utc).isoformat(),
            }
            event["event_id"] = hashlib.sha256(
                (
                    f"{self.ledger_path}\0{sequence}\0{model}\0{prompt_version}\0"
                    f"{cache_key}\0{attempt}\0{purpose}"
                ).encode()
            ).hexdigest()
            encoded = (
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            with self.ledger_path.open("ab", buffering=0) as stream:
                stream.write(encoded)
                os.fsync(stream.fileno())
            return sequence


def _read_budget_events(path: Path) -> list[dict[str, Any]]:
    if not Path(path).is_file():
        return []
    result: list[dict[str, Any]] = []
    lines = Path(path).read_bytes().splitlines(keepends=True)
    for index, raw in enumerate(lines):
        complete = raw.endswith(b"\n")
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            if index == len(lines) - 1 and not complete:
                raise ValueError(
                    f"incomplete tail in Gemini call ledger; fail closed: {path}"
                )
            raise ValueError(f"corrupt Gemini call ledger line {index + 1}: {path}")
        if event.get("schema_version") != "gemini-provider-call-budget-v1":
            raise ValueError(f"unexpected event in Gemini call ledger: {path}")
        result.append(event)
    return result


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _CandidateScore(_StrictModel):
    candidate_id: str
    semantic_score: float = Field(ge=0.0, le=1.0)
    reason: str
    predicted_failure_types: list[str]


class _SemanticPayload(_StrictModel):
    candidates: list[_CandidateScore]
    selected_candidate_id: str | None
    selection_reason: str
    required_trajectory_pattern: str
    observed_stage_id: str = Field(pattern=r"^(?:UNKNOWN|stage_[1-9][0-9]*)$")
    stage_confidence: float = Field(ge=0.0, le=1.0)


class SemanticPlanner:
    def __init__(
        self,
        *,
        model: str = "gpt-6-astra",
        prompt_version: str = "candidate-scorer-v4",
        timeout_seconds: float = 1200.0,
        max_retries: int = 2,
        cache_dir: Path | None = None,
        api_key: str | None = None,
        client: Any = None,
        max_provider_calls: int = 0,
        call_ledger_path: Path | None = None,
        thinking_level: str = "ultra",
    ) -> None:
        if model != "gpt-6-astra" and not (client is not None and model == "gemini-robotics-er-2-preview"):
            raise ValueError(
                "fixed_budget_10 semantic planner requires "
                "gpt-6-astra through the Codex account task"
            )
        self.model = model
        self.thinking_level = str(thinking_level)
        if self.thinking_level not in {"minimal", "low", "medium", "high", "ultra"}:
            raise ValueError("unsupported planner thinking_level")
        self.prompt_version = prompt_version
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._provider_budget = _ProviderCallBudget(
            max_calls=max_provider_calls,
            ledger_path=call_ledger_path,
        )
        if client is None:
            from .planner_account import CodexPlannerClient
            client = CodexPlannerClient()
            if thinking_level != "ultra":
                raise ValueError("Codex account planner requires ultra reasoning")
            self.timeout_seconds = max(self.timeout_seconds, client.timeout_seconds + 5)
        self.client = client

    def increase_provider_call_cap(
        self,
        *,
        max_provider_calls: int,
        call_ledger_path: Path,
    ) -> None:
        """Raise a capped planner's limit without recreating its warm client.

        A warm replay may only extend the existing persistent ledger.  It may
        not lower the cap, switch ledgers, or turn a capped run into an
        unbounded run while the provider client is alive.
        """

        new_max = int(max_provider_calls)
        new_ledger = Path(call_ledger_path).resolve()
        current = self._provider_budget
        if current.max_calls <= 0:
            raise ValueError("warm replay requires an existing positive provider cap")
        if new_max < current.max_calls:
            raise ValueError(
                "warm replay cannot lower the Gemini provider-call cap: "
                f"current={current.max_calls}, requested={new_max}"
            )
        if current.ledger_path != new_ledger:
            raise ValueError(
                "warm replay cannot switch Gemini provider-call ledgers: "
                f"current={current.ledger_path}, requested={new_ledger}"
            )
        if new_max == current.max_calls:
            return
        self._provider_budget = _ProviderCallBudget(
            max_calls=new_max,
            ledger_path=new_ledger,
        )

    def reconfigure_provider_call_budget(
        self, *, max_provider_calls: int, call_ledger_path: Path
    ) -> None:
        """Install a new positive run-local cap while retaining the warm client."""

        new_max = int(max_provider_calls)
        if new_max <= 0:
            raise ValueError("warm replay provider cap must be positive")
        self._provider_budget = _ProviderCallBudget(
            max_calls=new_max,
            ledger_path=Path(call_ledger_path).resolve(),
        )

    def preflight(self, *, exercise_interactions: bool = False) -> None:
        try:
            self._provider_budget.reserve(
                model=self.model,
                prompt_version=self.prompt_version,
                cache_key="preflight-model-get",
                attempt=1,
                purpose="preflight_model_get",
            )
            _run_with_timeout(
                lambda: self.client.models.get(model=self.model),
                self.timeout_seconds,
                "Account planner preflight",
            )
            if exercise_interactions:
                self._provider_budget.reserve(
                    model=self.model,
                    prompt_version=self.prompt_version,
                    cache_key="preflight-canary",
                    attempt=1,
                    purpose="preflight_canary",
                )
                response = self._call_with_timeout(
                    (
                        "This is a provider connectivity canary. Return exactly one candidate "
                        "with candidate_id='canary-m0', semantic_score=1.0, a short reason, no "
                        "predicted failures, selected_candidate_id=\'canary-m0\', selection_reason=\'canary\', required_trajectory_pattern='none', "
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
                if [item.candidate_id for item in payload.candidates] != ["canary-m0"]:
                    raise ValueError("Gemini Interactions canary returned the wrong candidate ID")
        except Exception as exc:
            raise AgentCallError(f"Account planner preflight failed: {exc}") from exc

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
        expected = {mode.candidate_id for mode in evidence.candidates}
        if not expected:
            raise ValueError("Planner requires the complete nonempty candidate set")
        if {item.candidate_id for item in geometry} != expected:
            raise ValueError("geometry must cover each candidate exactly once")
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
                    self.thinking_level.encode(),
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
                reservation = self._provider_budget.reserve(
                    model=self.model,
                    prompt_version=self.prompt_version,
                    cache_key=cache_key,
                    attempt=attempt + 1,
                    purpose="semantic_score",
                )
                response = self._call_with_timeout(prompt, image_bytes)
                output_text = getattr(response, "text", None) or getattr(
                    response, "output_text", None
                )
                if not output_text:
                    raise ValueError("Planner returned no JSON text")
                payload = _SemanticPayload.model_validate_json(output_text)
                usage = getattr(response, "usage_metadata", None) or getattr(
                    response, "usage", None
                )
                metadata = {
                    "model": self.model,
                    "prompt_version": self.prompt_version,
                    "thinking_level": self.thinking_level,
                    "latency_seconds": time.monotonic() - started,
                    "attempt": attempt + 1,
                    "cache_hit": False,
                    "cache_key": cache_key,
                    "token_usage": _usage_to_dict(usage),
                    "provider_call_sequence": reservation,
                    **dict(getattr(response, "planner_metadata", {})),
                }
                value = payload.model_dump()
                plan = self._to_plan(value, expected, metadata)
                self._write_cache(cache_key, value, metadata)
                return plan
            except GeminiCallBudgetExceeded:
                raise
            except Exception as exc:
                last_error = exc
        raise AgentCallError(
            f"Planner semantic scoring failed after {self.max_retries + 1} attempts: "
            f"{last_error}"
        ) from last_error

    def _call_with_timeout(self, prompt: str, image_bytes: bytes) -> Any:
        def call() -> Any:
            return self.client.interactions.create(
                model=self.model,
                system_instruction=(
                    "You are a robot trajectory semantic scorer. Use only the supplied "
                    "observation overlay and structured trajectory measurements. Score "
                    "every candidate exactly once, select a safe candidate ID, explain the choice, "
                    "and return strict JSON; never choose a "
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
                generation_config={"thinking_level": self.thinking_level},
                store=False,
            )

        return _run_with_timeout(
            call,
            self.timeout_seconds,
            "Account mode scoring",
        )

    def _prompt(
        self,
        context: GateContext,
        evidence: RoundEvidence,
        geometry: Sequence[GeometryEvidence],
        object_distances: Mapping[str, Mapping[str, float]],
        progress_history: Sequence[Mapping[str, Any]],
    ) -> str:
        geometry_by_id = {item.candidate_id: item for item in geometry}
        candidates = evidence.planner_candidates()
        for item in candidates:
            geo = geometry_by_id[item["candidate_id"]]
            item["geometry"] = {
                "collision_risk": geo.collision_risk,
                "reachability": geo.reachability,
                "grasp_plausibility": geo.grasp_plausibility,
                "hard_safety_veto": geo.hard_safety_veto,
            }
            item["endpoint_object_distances"] = object_distances.get(item["candidate_id"], {})
        payload = {
            "prompt_version": self.prompt_version,
            "instruction": context.task_instruction,
            "current_stage": context.task_stage,
            "context_id": context.context_id,
            "progress_history": list(progress_history),
            "candidates": candidates,
            "candidate_count": evidence.action_batch.sample_count,
            "execution_horizon": context.metadata.get("execution_horizon"),
        }
        return (
            "Read ALL complete candidate sequences (actions, positions, orientations and grippers). "
            "Choose selected_candidate_id using multimodal evidence and explain selection_reason. "
            "Do not choose a hard_safety_veto candidate. Use null only if all are vetoed. "
            "The overlay is illustrative; complete numeric candidates are authoritative predictions. "
            "Prediction sequences may be longer than execution_horizon. Only the first "
            "execution_horizon actions of the selected candidate execute before replanning; "
            "later predicted actions are context, not promised execution. Preserve and review them all. "
            "Score the semantic compatibility of every trajectory in the "
            "single supplied overlay. Return each candidate exactly once. Scores express task "
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
        returned = [item.candidate_id for item in payload.candidates]
        if len(returned) != len(set(returned)) or set(returned) != expected:
            raise AgentCallError(
                "Planner must return every candidate exactly once; "
                f"expected={sorted(expected)}, got={sorted(returned)}"
            )
        return SemanticPlan(
            selected_candidate_id=payload.selected_candidate_id,
            selection_reason=payload.selection_reason,
            candidate_scores=tuple(
                SemanticCandidateScore(
                    candidate_id=item.candidate_id,
                    semantic_score=item.semantic_score,
                    reason=item.reason,
                    predicted_failure_types=tuple(item.predicted_failure_types),
                )
                for item in payload.candidates
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


# Old artifact/test import name; there is only one implementation and no live
# Gemini client. New callers use SemanticPlanner.
GeminiSemanticPlanner = SemanticPlanner

__all__ = [
    "SemanticPlanner",
    "GeminiCallBudgetExceeded",
    "GeminiSemanticPlanner",
    "is_retryable_semantic_network_error",
    "preflight_with_network_recovery",
    "score_semantics_with_network_recovery",
]
