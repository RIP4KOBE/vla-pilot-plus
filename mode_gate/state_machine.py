"""Deterministic episode/chunk controller for the mode-aware v2 runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .config import ModeGateConfig
from .types import (
    ControllerPhase,
    ControllerRoute,
    FailureTrigger,
    ProgressEvidence,
    SamplingCondition,
)


@dataclass(frozen=True)
class RouteDecision:
    route: ControllerRoute
    reason: str
    phase: ControllerPhase
    remaining_budget: int
    verifier_called: bool = False
    label_eligible: bool = True


@dataclass
class EpisodeControllerState:
    phase: ControllerPhase = ControllerPhase.NORMAL_SAMPLE
    stagnant_chunks: int = 0
    failure_count: int = 0
    retry_index: int = 0
    verification_due: bool = False
    retry_active: bool = False
    last_stage_id: str = "UNKNOWN"
    chunks_executed: int = 0
    terminal: bool = False
    retry_budget: int = 4
    trace: list[str] = field(default_factory=list)

    @property
    def remaining_budget(self) -> int:
        return max(0, self.retry_budget - self.retry_index)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["phase"] = self.phase.value
        return value


class EpisodeChunkController:
    """Own the route state; provider/model code cannot directly choose routes."""

    def __init__(
        self, config: ModeGateConfig, *, retry_budget_override: int | None = None
    ) -> None:
        config.validate()
        self.config = config
        self.retry_budget = int(
            config.retry_budget
            if retry_budget_override is None
            else retry_budget_override
        )
        if self.retry_budget <= 0:
            raise ValueError("controller retry budget must be positive")
        self.state = EpisodeControllerState(retry_budget=self.retry_budget)

    def start_episode(self, *, stage_id: str = "UNKNOWN") -> None:
        self.state = EpisodeControllerState(
            last_stage_id=str(stage_id), retry_budget=self.retry_budget
        )
        self._transition(ControllerPhase.NORMAL_SAMPLE)

    def begin_sampling(self) -> ControllerPhase:
        self._require_live()
        phase = (
            ControllerPhase.FRESH_SAMPLE
            if self.state.verification_due
            else ControllerPhase.NORMAL_SAMPLE
        )
        self._transition(phase)
        return phase

    def mark_abstracted(self) -> None:
        if self.state.phase not in {
            ControllerPhase.NORMAL_SAMPLE,
            ControllerPhase.FRESH_SAMPLE,
        }:
            raise RuntimeError(f"cannot abstract from {self.state.phase.value}")
        self._transition(ControllerPhase.ABSTRACT)

    def mark_scored(self, *, has_safe_mode: bool) -> RouteDecision | None:
        if self.state.phase is not ControllerPhase.ABSTRACT:
            raise RuntimeError(f"cannot score from {self.state.phase.value}")
        self._transition(ControllerPhase.SCORE)
        if has_safe_mode:
            return None
        self.state.verification_due = True
        self.state.failure_count = min(4, self.state.failure_count + 1)
        self._transition(ControllerPhase.VERIFICATION_DUE)
        return RouteDecision(
            route=ControllerRoute.EXECUTE,
            reason=FailureTrigger.NO_SAFE_MODE.value,
            phase=self.state.phase,
            remaining_budget=self.state.remaining_budget,
            verifier_called=False,
        )

    def route_scored_batch(
        self,
        *,
        verifier_decision: ControllerRoute | None = None,
        route_override: ControllerRoute | None = None,
        override_reason: str = "",
        override_verifier_called: bool = False,
    ) -> RouteDecision:
        """Route a scored batch.

        On a normal batch, the verifier is never consulted.  On a fresh
        post-failure batch, the learned head must directly return RE-STEER or
        EXPANSION.  No controller probability threshold is applied.
        """

        if self.state.phase is not ControllerPhase.SCORE:
            raise RuntimeError(f"cannot route from {self.state.phase.value}")
        if not self.state.verification_due:
            self._transition(ControllerPhase.EXECUTE)
            return RouteDecision(
                route=ControllerRoute.EXECUTE,
                reason="safe_semantic_medoid",
                phase=self.state.phase,
                remaining_budget=self.state.remaining_budget,
                verifier_called=False,
            )

        self._transition(ControllerPhase.VERIFY)
        if route_override is not None:
            if route_override is ControllerRoute.EXPAND:
                return self._expand(
                    override_reason or "experimental_baseline_expand",
                    verifier_called=override_verifier_called,
                )
            if route_override is not ControllerRoute.RESTEER:
                raise ValueError(
                    "post-failure route override must be RE-STEER or EXPANSION"
                )
            schedule_index = self.state.retry_index
            self.state.retry_index += 1
            self.state.verification_due = False
            self.state.retry_active = True
            self._transition(ControllerPhase.RESTEER_EXECUTE)
            return RouteDecision(
                route=ControllerRoute.RESTEER,
                reason=override_reason or f"experimental_retry_{schedule_index}",
                phase=self.state.phase,
                remaining_budget=self.state.remaining_budget,
                verifier_called=override_verifier_called,
            )
        if self.state.remaining_budget == 0:
            return self._expand("retry_budget_exhausted", verifier_called=False)

        if self.config.controller_mode == "learned_verifier":
            if verifier_decision not in {
                ControllerRoute.RESTEER,
                ControllerRoute.EXPAND,
            }:
                raise ValueError(
                    "learned verifier must directly decide RE-STEER or EXPANSION"
                )
            if verifier_decision is ControllerRoute.EXPAND:
                return self._expand(
                    "verifier_head_argmax:EXPANSION",
                    verifier_called=True,
                )

        schedule_index = self.state.retry_index
        self.state.retry_index += 1
        self.state.verification_due = False
        self.state.retry_active = True
        self._transition(ControllerPhase.RESTEER_EXECUTE)
        return RouteDecision(
            route=ControllerRoute.RESTEER,
            reason=(
                "verifier_head_argmax:RE-STEER"
                if self.config.controller_mode == "learned_verifier"
                else f"retry_schedule_{schedule_index}"
            ),
            phase=self.state.phase,
            remaining_budget=self.state.remaining_budget,
            verifier_called=self.config.controller_mode == "learned_verifier",
        )

    def observe_chunk(
        self,
        progress: ProgressEvidence,
        *,
        failure_trigger: FailureTrigger | None = None,
        terminal_timeout: bool = False,
    ) -> RouteDecision:
        if self.state.phase not in {
            ControllerPhase.EXECUTE,
            ControllerPhase.RESTEER_EXECUTE,
        }:
            raise RuntimeError(f"cannot observe from {self.state.phase.value}")
        self._transition(ControllerPhase.OBSERVE)
        self.state.chunks_executed += 1

        if progress.task_success or progress.advanced:
            self.state.stagnant_chunks = 0
            self.state.failure_count = 0
            self.state.retry_index = 0
            self.state.verification_due = False
            self.state.retry_active = False
            self.state.last_stage_id = progress.stage_id
            self._transition(ControllerPhase.NORMAL_CONTINUE)
            return RouteDecision(
                route=ControllerRoute.EXECUTE,
                reason="task_success" if progress.task_success else "stage_advanced",
                phase=self.state.phase,
                remaining_budget=self.state.remaining_budget,
                label_eligible=False,
            )

        if terminal_timeout or failure_trigger is FailureTrigger.TIMEOUT:
            # No executable horizon remains, so this is a ticket-only event and
            # must not become a verifier training label.
            return self._expand(
                FailureTrigger.TIMEOUT.value,
                verifier_called=False,
                label_eligible=False,
            )

        immediate = failure_trigger in {
            FailureTrigger.CONTACT,
            FailureTrigger.NO_SAFE_MODE,
        }
        if self.state.retry_active or immediate:
            self.state.stagnant_chunks = self.config.stagnation_window
        else:
            unknown_without_support = (
                progress.stage_id.upper() == "UNKNOWN"
                and not progress.reward_improved
            )
            confident_no_progress = progress.confidence >= 0.8 and not progress.advanced
            if confident_no_progress or unknown_without_support:
                self.state.stagnant_chunks += 1

        if self.state.stagnant_chunks >= self.config.stagnation_window:
            # Count observed failed execution opportunities, not routing
            # decisions.  This value is consumed by the verifier before it
            # decides whether the next fresh batch should be executed.
            self.state.failure_count = min(4, self.state.failure_count + 1)
            self.state.verification_due = True
            self.state.retry_active = False
            self._transition(ControllerPhase.VERIFICATION_DUE)
            return RouteDecision(
                route=ControllerRoute.EXECUTE,
                reason=(failure_trigger or FailureTrigger.STAGNATION).value,
                phase=self.state.phase,
                remaining_budget=self.state.remaining_budget,
                verifier_called=False,
            )

        self._transition(ControllerPhase.NORMAL_CONTINUE)
        return RouteDecision(
            route=ControllerRoute.EXECUTE,
            reason="normal_continue",
            phase=self.state.phase,
            remaining_budget=self.state.remaining_budget,
            verifier_called=False,
            label_eligible=False,
        )

    def sampling_condition(self, seed: int) -> SamplingCondition:
        index = min(self.state.retry_index, len(self.config.retry_schedule) - 1)
        guide, diversity = self.config.retry_schedule[index]
        return SamplingCondition(
            seed=int(seed),
            retry_index=self.state.retry_index,
            guide_mult=float(guide),
            diversity_mult=float(diversity),
        )

    def abort(self, error: Exception | str) -> RouteDecision:
        self.state.terminal = True
        self._transition(ControllerPhase.ABORT)
        return RouteDecision(
            route=ControllerRoute.ABORT,
            reason=str(error),
            phase=self.state.phase,
            remaining_budget=self.state.remaining_budget,
            verifier_called=False,
            label_eligible=False,
        )

    def force_expand(
        self,
        reason: str,
        *,
        label_eligible: bool = True,
    ) -> RouteDecision:
        self._require_live()
        return self._expand(
            reason,
            verifier_called=False,
            label_eligible=label_eligible,
        )

    def _expand(
        self,
        reason: str,
        *,
        verifier_called: bool,
        label_eligible: bool = True,
    ) -> RouteDecision:
        self.state.terminal = True
        self._transition(ControllerPhase.EXPAND)
        return RouteDecision(
            route=ControllerRoute.EXPAND,
            reason=reason,
            phase=self.state.phase,
            remaining_budget=self.state.remaining_budget,
            verifier_called=verifier_called,
            label_eligible=label_eligible,
        )

    def _transition(self, phase: ControllerPhase) -> None:
        self.state.phase = phase
        self.state.trace.append(phase.value)

    def _require_live(self) -> None:
        if self.state.terminal:
            raise RuntimeError("episode controller is terminal")


__all__ = ["EpisodeChunkController", "EpisodeControllerState", "RouteDecision"]
