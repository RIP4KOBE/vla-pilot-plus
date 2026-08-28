"""Persistent, hash-addressed slow-loop state machine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import fcntl

from .io_utils import AtomicJsonl


class SlowLoopState(str, Enum):
    EXPANSION_TRIGGERED = "EXPANSION_TRIGGERED"
    LOOKUP_PENDING = "LOOKUP_PENDING"
    REUSE_EVALUATING = "REUSE_EVALUATING"
    TICKET_READY = "TICKET_READY"
    AWAITING_DEMOS = "AWAITING_DEMOS"
    COLLECTING = "COLLECTING"
    CURATING = "CURATING"
    DATASET_READY = "DATASET_READY"
    TRAINING = "TRAINING"
    DELTA_READY = "DELTA_READY"
    ALPHA_SELECTING = "ALPHA_SELECTING"
    RAW_REGRESSION = "RAW_REGRESSION"
    TRIGGER_RECHECK = "TRIGGER_RECHECK"
    POLICY_STAGED = "POLICY_STAGED"
    NEW_POLICY_COUNTERFACTUAL = "NEW_POLICY_COUNTERFACTUAL"
    VERIFIER_TRAINING = "VERIFIER_TRAINING"
    READY_PAIR = "READY_PAIR"
    READY_FIXED_BUDGET = "READY_FIXED_BUDGET"
    DEPLOYED = "DEPLOYED"
    NEEDS_MORE_DEMOS = "NEEDS_MORE_DEMOS"
    RETRYABLE_ERROR = "RETRYABLE_ERROR"
    STALE_BASE = "STALE_BASE"
    POLICY_REJECTED = "POLICY_REJECTED"
    VERIFIER_PENDING = "VERIFIER_PENDING"
    MANUAL_REVIEW = "MANUAL_REVIEW"


TERMINAL = {SlowLoopState.DEPLOYED, SlowLoopState.POLICY_REJECTED}
MUTATING = {
    SlowLoopState.TRAINING,
    SlowLoopState.DELTA_READY,
    SlowLoopState.ALPHA_SELECTING,
    SlowLoopState.RAW_REGRESSION,
    SlowLoopState.TRIGGER_RECHECK,
    SlowLoopState.POLICY_STAGED,
    SlowLoopState.NEW_POLICY_COUNTERFACTUAL,
    SlowLoopState.VERIFIER_TRAINING,
    SlowLoopState.READY_PAIR,
    SlowLoopState.READY_FIXED_BUDGET,
}


ALLOWED: dict[SlowLoopState, set[SlowLoopState]] = {
    SlowLoopState.EXPANSION_TRIGGERED: {
        SlowLoopState.LOOKUP_PENDING,
        SlowLoopState.RETRYABLE_ERROR,
    },
    SlowLoopState.LOOKUP_PENDING: {
        SlowLoopState.REUSE_EVALUATING,
        SlowLoopState.TICKET_READY,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.REUSE_EVALUATING: {
        SlowLoopState.RAW_REGRESSION,
        SlowLoopState.TICKET_READY,
        SlowLoopState.STALE_BASE,
        SlowLoopState.RETRYABLE_ERROR,
    },
    SlowLoopState.TICKET_READY: {
        SlowLoopState.AWAITING_DEMOS,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.AWAITING_DEMOS: {
        SlowLoopState.COLLECTING,
        # Append-only correction path for a ticket that fails an operational
        # integrity check before any demonstration is collected.
        SlowLoopState.TICKET_READY,
    },
    SlowLoopState.COLLECTING: {SlowLoopState.CURATING, SlowLoopState.RETRYABLE_ERROR},
    SlowLoopState.CURATING: {
        SlowLoopState.DATASET_READY,
        SlowLoopState.NEEDS_MORE_DEMOS,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.NEEDS_MORE_DEMOS: {SlowLoopState.AWAITING_DEMOS},
    SlowLoopState.DATASET_READY: {
        SlowLoopState.TRAINING,
        SlowLoopState.STALE_BASE,
        SlowLoopState.RETRYABLE_ERROR,
    },
    SlowLoopState.TRAINING: {SlowLoopState.DELTA_READY, SlowLoopState.RETRYABLE_ERROR},
    SlowLoopState.DELTA_READY: {
        SlowLoopState.ALPHA_SELECTING,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.ALPHA_SELECTING: {
        SlowLoopState.RAW_REGRESSION,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.RAW_REGRESSION: {
        SlowLoopState.TRIGGER_RECHECK,
        SlowLoopState.TICKET_READY,
        SlowLoopState.NEEDS_MORE_DEMOS,
        SlowLoopState.POLICY_REJECTED,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.TRIGGER_RECHECK: {
        SlowLoopState.POLICY_STAGED,
        SlowLoopState.NEEDS_MORE_DEMOS,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.POLICY_STAGED: {
        SlowLoopState.NEW_POLICY_COUNTERFACTUAL,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.NEW_POLICY_COUNTERFACTUAL: {
        SlowLoopState.VERIFIER_TRAINING,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.VERIFIER_TRAINING: {
        SlowLoopState.READY_PAIR,
        SlowLoopState.READY_FIXED_BUDGET,
        SlowLoopState.VERIFIER_PENDING,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.VERIFIER_PENDING: {
        SlowLoopState.VERIFIER_TRAINING,
        SlowLoopState.READY_FIXED_BUDGET,
    },
    SlowLoopState.READY_PAIR: {
        SlowLoopState.DEPLOYED,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.READY_FIXED_BUDGET: {
        SlowLoopState.DEPLOYED,
        SlowLoopState.RETRYABLE_ERROR,
        SlowLoopState.STALE_BASE,
    },
    SlowLoopState.RETRYABLE_ERROR: {
        SlowLoopState.COLLECTING,
        SlowLoopState.TRAINING,
        SlowLoopState.VERIFIER_TRAINING,
        SlowLoopState.MANUAL_REVIEW,
        SlowLoopState.LOOKUP_PENDING,
        SlowLoopState.REUSE_EVALUATING,
        SlowLoopState.TICKET_READY,
        SlowLoopState.CURATING,
        SlowLoopState.DATASET_READY,
        SlowLoopState.DELTA_READY,
        SlowLoopState.ALPHA_SELECTING,
        SlowLoopState.RAW_REGRESSION,
        SlowLoopState.TRIGGER_RECHECK,
        SlowLoopState.POLICY_STAGED,
        SlowLoopState.NEW_POLICY_COUNTERFACTUAL,
        SlowLoopState.READY_PAIR,
        SlowLoopState.READY_FIXED_BUDGET,
    },
    SlowLoopState.STALE_BASE: {SlowLoopState.LOOKUP_PENDING},
    SlowLoopState.MANUAL_REVIEW: set(),
    SlowLoopState.DEPLOYED: set(),
    SlowLoopState.POLICY_REJECTED: set(),
}


@dataclass(frozen=True)
class SlowLoopJob:
    job_id: str
    state: SlowLoopState
    active_policy_id: str
    ticket_id: str | None
    input_hash: str
    output_hash: str | None
    sequence: int
    metadata: dict[str, Any]


class SlowLoopStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = AtomicJsonl(self.root / "slow_loop_events.jsonl")
        self.lock_path = self.root / ".policy_mutation.lock"

    def create(
        self,
        *,
        active_policy_id: str,
        input_hash: str,
        ticket_id: str | None = None,
        metadata: Mapping[str, Any] = {},
    ) -> SlowLoopJob:
        job = SlowLoopJob(
            job_id=uuid4().hex,
            state=SlowLoopState.EXPANSION_TRIGGERED,
            active_policy_id=active_policy_id,
            ticket_id=ticket_id,
            input_hash=input_hash,
            output_hash=None,
            sequence=0,
            metadata=dict(metadata),
        )
        self._append(job)
        return job

    def current(self, job_id: str) -> SlowLoopJob:
        events = [item for item in self.events.iter_valid() if item["job_id"] == job_id]
        if not events:
            raise KeyError(job_id)
        value = max(events, key=lambda item: int(item["sequence"]))
        return _job_from_event(value)

    def advance(
        self,
        job_id: str,
        *,
        expected_state: SlowLoopState,
        next_state: SlowLoopState,
        input_hash: str,
        output_hash: str | None,
        metadata: Mapping[str, Any] = {},
        ticket_id: str | None = None,
        active_policy_id: str | None = None,
    ) -> SlowLoopJob:
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.current(job_id)
            if current.state is not expected_state:
                raise RuntimeError(
                    f"job state changed: expected {expected_state.value}, got {current.state.value}"
                )
            if next_state not in ALLOWED[current.state]:
                raise ValueError(
                    f"invalid slow-loop transition {current.state.value}->{next_state.value}"
                )
            if (
                current.state is SlowLoopState.AWAITING_DEMOS
                and next_state is SlowLoopState.TICKET_READY
            ):
                if (
                    metadata.get("superseded_ticket_id") != current.ticket_id
                    or not metadata.get("ticket_reissue_reason")
                    or int(metadata.get("collected_demo_count", -1)) != 0
                ):
                    raise ValueError(
                        "ticket reissue requires the exact superseded ticket, "
                        "a reason, and proof that zero demos were collected"
                    )
            if current.state in MUTATING and input_hash != current.input_hash:
                raise RuntimeError("policy-mutating job input hash changed")
            if next_state in MUTATING:
                self._ensure_only_mutating_job(job_id)
            replacing_ticket = (
                ticket_id is not None
                and current.ticket_id not in {None, ticket_id}
            )
            if replacing_ticket:
                replacement_is_authorized = (
                    current.state is SlowLoopState.TICKET_READY
                    and current.metadata.get("superseded_ticket_id")
                    == current.ticket_id
                    and bool(current.metadata.get("ticket_reissue_reason"))
                )
                if not replacement_is_authorized:
                    raise RuntimeError(
                        "slow-loop ticket ID is immutable once assigned"
                    )
            if active_policy_id is not None and current.state is not SlowLoopState.STALE_BASE:
                raise RuntimeError("active base can only change while restarting STALE_BASE")
            job = SlowLoopJob(
                job_id=current.job_id,
                state=next_state,
                active_policy_id=active_policy_id or current.active_policy_id,
                ticket_id=ticket_id or current.ticket_id,
                input_hash=input_hash,
                output_hash=output_hash,
                sequence=current.sequence + 1,
                metadata={
                    **current.metadata,
                    **(
                        {"ticket_reissued_from": current.ticket_id}
                        if replacing_ticket
                        else {}
                    ),
                    **dict(metadata),
                },
            )
            self._append(job)
            return job

    def resumable_jobs(self) -> list[SlowLoopJob]:
        latest: dict[str, SlowLoopJob] = {}
        for event in self.events.iter_valid():
            job = _job_from_event(event)
            if job.sequence >= latest.get(job.job_id, job).sequence:
                latest[job.job_id] = job
        return [job for job in latest.values() if job.state not in TERMINAL]

    def annotate(
        self,
        job_id: str,
        *,
        expected_state: SlowLoopState,
        metadata: Mapping[str, Any],
        output_hash: str | None = None,
    ) -> SlowLoopJob:
        """Attach immutable external-worker artifacts without changing state."""

        if not metadata:
            raise ValueError("slow-loop annotation must not be empty")
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.current(job_id)
            if current.state is not expected_state:
                raise RuntimeError(
                    f"job state changed: expected {expected_state.value}, "
                    f"got {current.state.value}"
                )
            conflicts = {
                key: (current.metadata[key], value)
                for key, value in metadata.items()
                if key in current.metadata and current.metadata[key] != value
            }
            if conflicts:
                raise ValueError(f"slow-loop annotation is immutable: {conflicts}")
            if all(current.metadata.get(key) == value for key, value in metadata.items()):
                return current
            job = SlowLoopJob(
                job_id=current.job_id,
                state=current.state,
                active_policy_id=current.active_policy_id,
                ticket_id=current.ticket_id,
                input_hash=current.input_hash,
                output_hash=output_hash or current.output_hash,
                sequence=current.sequence + 1,
                metadata={**current.metadata, **dict(metadata)},
            )
            self._append(job)
            return job

    def _ensure_only_mutating_job(self, job_id: str) -> None:
        conflicts = [
            job.job_id
            for job in self.resumable_jobs()
            if job.job_id != job_id and job.state in MUTATING
        ]
        if conflicts:
            raise RuntimeError(f"another policy-mutating job is active: {conflicts}")

    def _append(self, job: SlowLoopJob) -> None:
        event = {
            "event_id": f"{job.job_id}:{job.sequence}",
            "event": "SLOW_LOOP_STATE",
            "job_id": job.job_id,
            "state": job.state.value,
            "active_policy_id": job.active_policy_id,
            "ticket_id": job.ticket_id,
            "input_hash": job.input_hash,
            "output_hash": job.output_hash,
            "sequence": job.sequence,
            "metadata": job.metadata,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(event)


def _job_from_event(value: Mapping[str, Any]) -> SlowLoopJob:
    return SlowLoopJob(
        job_id=str(value["job_id"]),
        state=SlowLoopState(value["state"]),
        active_policy_id=str(value["active_policy_id"]),
        ticket_id=value.get("ticket_id"),
        input_hash=str(value["input_hash"]),
        output_hash=value.get("output_hash"),
        sequence=int(value["sequence"]),
        metadata=dict(value.get("metadata", {})),
    )


__all__ = ["SlowLoopJob", "SlowLoopState", "SlowLoopStore"]
