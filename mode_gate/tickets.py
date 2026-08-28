"""Strict expansion ticket schema with code-owned IDs and split guards."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .io_utils import atomic_write_json
from .semantic_planner import _run_with_timeout, _usage_to_dict


TICKET_PLANNER_MODEL = "gemini-robotics-er-2-preview"
TICKET_ID_VERSION = "operational-coverage-v1"
DEFAULT_TARGET_DEMOS = 15


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoverageCell(_StrictModel):
    axis: str
    value: str
    quota: int = Field(ge=1)


class CollectionSpec(_StrictModel):
    capability_gap: str
    coverage_axes: list[CoverageCell]
    must_demonstrate: list[str]
    must_avoid: list[str]


class _TicketPlanPayload(_StrictModel):
    capability_gap: str
    coverage_axes: list[CoverageCell]
    must_demonstrate: list[str]
    must_avoid: list[str]


class TicketCollectionPlanner:
    """Strict Gemini planner that may describe demos but never invent IDs."""

    def __init__(
        self,
        *,
        model: str = TICKET_PLANNER_MODEL,
        prompt_version: str = "ticket-collection-v2",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        if model != TICKET_PLANNER_MODEL:
            raise ValueError(
                f"ticket planner is frozen to {TICKET_PLANNER_MODEL}"
            )
        self.model = model
        self.prompt_version = prompt_version
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        if client is None:
            key = api_key or os.environ.get("GOOGLE_API_KEY")
            if not key:
                raise RuntimeError("GOOGLE_API_KEY is required for ticket planning")
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    timeout=max(1, int(self.timeout_seconds * 1000))
                ),
            )
        self.client = client

    def plan(
        self,
        *,
        task_instruction: str,
        failure_mode: str,
        required_trajectory_pattern: str,
        semantic_failure_types: Sequence[str],
    ) -> tuple[CollectionSpec, dict[str, Any]]:
        request = {
            "prompt_version": self.prompt_version,
            "task_instruction": task_instruction,
            "failure_mode": failure_mode,
            "required_trajectory_pattern": required_trajectory_pattern,
            "semantic_failure_types": list(semantic_failure_types),
            "constraints": {
                "target_demos": DEFAULT_TARGET_DEMOS,
                "init_states": 5,
                "demos_per_state": 3,
                "planner_must_not_generate_ids": True,
                "coverage_is_one_mutually_exclusive_partition": True,
                "coverage_axis_count": 1,
                "coverage_quota_total": DEFAULT_TARGET_DEMOS,
                "coverage_must_be_operator_controllable_in_fixed_scene": True,
                "forbid_object_identity_geometry_or_task_variants": True,
            },
        }
        prompt = (
            "Describe the capability gap and a concrete, coverage-aware human "
            "demonstration collection specification. Include measurable coverage "
            "axes, must-demonstrate items, and must-avoid items. Never generate "
            "ticket IDs, snapshot IDs, init-state IDs, eval splits, checkpoint IDs, "
            "or acceptance thresholds. Coverage cells must all use one axis, "
            "must form one mutually exclusive partition of exactly 15 demos, and "
            "their quotas must sum to exactly 15. Every coverage value must be "
            "controllable by the operator inside this fixed simulator task; never "
            "invent alternate object identities, handle types, scene geometry, or "
            "task variants. Return strict JSON.\n\n"
            + json.dumps(request, ensure_ascii=False, sort_keys=True)
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                response = _run_with_timeout(
                    lambda: self._call(prompt),
                    self.timeout_seconds,
                    "Gemini ticket planning",
                )
                text = getattr(response, "text", None) or getattr(
                    response, "output_text", None
                )
                if not text:
                    raise ValueError("Gemini returned no ticket JSON")
                payload = _TicketPlanPayload.model_validate_json(text)
                collection = CollectionSpec(**payload.model_dump())
                # The issue_ticket validator repeats these checks; rejecting
                # here makes provider failures retryable before any artifact.
                if (
                    not collection.coverage_axes
                    or not collection.must_demonstrate
                    or not collection.must_avoid
                ):
                    raise ValueError("ticket collection lists must be non-empty")
                _validate_coverage_partition(
                    collection.coverage_axes,
                    target_demos=DEFAULT_TARGET_DEMOS,
                )
                return collection, {
                    "model": self.model,
                    "prompt_version": self.prompt_version,
                    "attempt": attempt + 1,
                    "latency_seconds": time.monotonic() - started,
                    "token_usage": _usage_to_dict(
                        getattr(response, "usage_metadata", None)
                    ),
                    "request_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                }
            except Exception as exc:
                last_error = exc
        raise RuntimeError(
            f"ticket planning failed after {self.max_retries + 1} attempts: {last_error}"
        ) from last_error

    def _call(self, prompt: str) -> Any:
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=_TicketPlanPayload.model_json_schema(),
                temperature=0.0,
            )
        except ImportError:
            config = {
                "response_mime_type": "application/json",
                "response_json_schema": _TicketPlanPayload.model_json_schema(),
                "temperature": 0.0,
            }
        return self.client.models.generate_content(
            model=self.model,
            contents=[prompt],
            config=config,
        )


class ExpansionTicket(_StrictModel):
    schema_version: Literal["expansion-ticket-v2"] = "expansion-ticket-v2"
    ticket_id: str
    signature_id: str
    snapshot_id: str
    suite: str
    task_id: str
    perturbation_variant: str
    failure_mode: str
    target_object_id: str | None = None
    init_state_ids: list[str]
    demos_per_state: int = Field(default=3, ge=1)
    target_demos: int = Field(default=15, ge=8, le=24)
    eval_split: Literal["regression"] = "regression"
    eval_init_state_ids: list[str]
    collection: CollectionSpec
    parent_policy_id: str
    registry_summary: dict[str, Any]
    acceptance_criteria: dict[str, Any]
    created_at: str

    @model_validator(mode="after")
    def validate_ticket(self) -> "ExpansionTicket":
        if len(self.init_state_ids) != 5 or len(set(self.init_state_ids)) != 5:
            raise ValueError("ticket requires five unique demo init states")
        if len(set(self.eval_init_state_ids)) != len(self.eval_init_state_ids):
            raise ValueError("eval init states must be unique")
        if set(self.init_state_ids).intersection(self.eval_init_state_ids):
            raise ValueError("demo and regression init states must be disjoint")
        if self.target_demos != len(self.init_state_ids) * self.demos_per_state:
            raise ValueError("target demo count is inconsistent with per-state quota")
        if not self.collection.coverage_axes:
            raise ValueError("ticket must define coverage axes")
        _validate_coverage_partition(
            self.collection.coverage_axes,
            target_demos=self.target_demos,
        )
        if not self.collection.must_demonstrate or not self.collection.must_avoid:
            raise ValueError("ticket must define must-demonstrate and must-avoid")
        return self


def issue_ticket(
    *,
    root: Path,
    signature_id: str,
    snapshot_id: str,
    suite: str,
    task_id: str,
    perturbation_variant: str,
    failure_mode: str,
    legal_demo_init_states: Sequence[str],
    regression_init_states: Sequence[str],
    collection: CollectionSpec,
    parent_policy_id: str,
    registry_summary: dict[str, Any],
    acceptance_criteria: dict[str, Any],
    target_object_id: str | None = None,
) -> ExpansionTicket:
    legal = [str(value) for value in legal_demo_init_states]
    if len(legal) < 5:
        raise ValueError("demo pool contains fewer than five legal init states")
    # Stable code-owned selection; the planner cannot fabricate init IDs.
    ordered = sorted(
        legal,
        key=lambda value: hashlib.sha256(
            f"{signature_id}\0{value}".encode("utf-8")
        ).hexdigest(),
    )
    demo_states = ordered[:5]
    ticket_id = "ticket-" + hashlib.sha256(
        (
            f"{TICKET_ID_VERSION}\0{signature_id}\0{snapshot_id}\0"
            f"{parent_policy_id}"
        ).encode()
    ).hexdigest()[:16]
    directory = Path(root) / ticket_id
    target = directory / "ticket.json"
    existing = (
        ExpansionTicket.model_validate_json(target.read_text(encoding="utf-8"))
        if target.exists()
        else None
    )
    ticket = ExpansionTicket(
        ticket_id=ticket_id,
        signature_id=signature_id,
        snapshot_id=snapshot_id,
        suite=suite,
        task_id=task_id,
        perturbation_variant=perturbation_variant,
        failure_mode=failure_mode,
        target_object_id=target_object_id,
        init_state_ids=demo_states,
        demos_per_state=3,
        target_demos=15,
        eval_init_state_ids=[str(value) for value in regression_init_states],
        collection=collection,
        parent_policy_id=parent_policy_id,
        registry_summary=registry_summary,
        acceptance_criteria=acceptance_criteria,
        created_at=(
            existing.created_at
            if existing is not None
            else datetime.now(timezone.utc).isoformat()
        ),
    )
    directory.mkdir(parents=True, exist_ok=True)
    if existing is not None:
        if existing != ticket:
            raise ValueError("ticket ID collision with different immutable content")
    else:
        atomic_write_json(target, ticket.model_dump())
    for subdir in ("raw", "curated", "rejected", "exports", "attempts"):
        (directory / subdir).mkdir(exist_ok=True)
    return ticket


def _validate_coverage_partition(
    coverage_axes: Sequence[CoverageCell], *, target_demos: int
) -> None:
    cells = tuple(coverage_axes)
    keys = [(cell.axis.strip(), cell.value.strip()) for cell in cells]
    if not cells or any(not axis or not value for axis, value in keys):
        raise ValueError("coverage cells must have non-empty axis/value")
    if len(keys) != len(set(keys)):
        raise ValueError("coverage cells must be unique")
    axes = {axis for axis, _ in keys}
    if len(axes) != 1:
        raise ValueError("coverage cells must form one operational axis")
    quota_total = sum(int(cell.quota) for cell in cells)
    if quota_total != int(target_demos):
        raise ValueError(
            "coverage quota total must equal target demos: "
            f"quota_total={quota_total}, target_demos={target_demos}"
        )


__all__ = [
    "CollectionSpec",
    "CoverageCell",
    "ExpansionTicket",
    "DEFAULT_TARGET_DEMOS",
    "TICKET_ID_VERSION",
    "TICKET_PLANNER_MODEL",
    "TicketCollectionPlanner",
    "issue_ticket",
]
