"""Chunk-boundary progress evidence with deterministic precedence rules."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .types import ProgressEvidence


_NUMBERED_STAGE = re.compile(r"^stage[\s_-]*([1-9][0-9]*)(?:\b|:)", re.IGNORECASE)


def canonicalize_stage_id(value: str | int | None) -> str:
    """Map provider/legacy spellings onto a stable stage identity.

    Human-readable suffixes and keypoint annotations remain useful planner
    diagnostics, but they must never create controller progress.  The v3
    planner emits ``stage_N`` directly; these legacy aliases keep restored
    snapshots and simulator predicates safe at the boundary.
    """

    text = str(value or "UNKNOWN").strip()
    if not text or text.upper() == "UNKNOWN":
        return "UNKNOWN"
    if text.isdigit() and int(text) > 0:
        return f"stage_{int(text)}"
    match = _NUMBERED_STAGE.match(text)
    if match:
        return f"stage_{int(match.group(1))}"
    return text


@dataclass
class ProgressMonitor:
    confidence_threshold: float = 0.8
    reward_epsilon: float = 0.02
    _last_stage_id: str = "UNKNOWN"
    _last_reward: float | None = None
    _last_predicate_stage_id: str | None = None
    _last_gemini_stage_id: str | None = None

    def reset(self, stage_id: str = "UNKNOWN", reward: float | None = None) -> None:
        self._last_stage_id = canonicalize_stage_id(stage_id)
        self._last_reward = None if reward is None else float(reward)
        # Stage identifiers from the simulator predicate, the semantic planner,
        # and the legacy controller are different namespaces. Their first
        # observation establishes a source-local baseline and must not be
        # mistaken for progress merely because, for example, ``"1"`` differs
        # from ``"slide_open_top_drawer"``.
        self._last_predicate_stage_id = None
        self._last_gemini_stage_id = None

    def observe(
        self,
        *,
        task_success: bool,
        predicate_stage_id: str | None = None,
        predicate_advanced: bool | None = None,
        gemini_stage_id: str | None = None,
        gemini_confidence: float = 0.0,
        normalized_reward: float | None = None,
        relation_improved: bool = False,
    ) -> ProgressEvidence:
        reward_improved = False
        if normalized_reward is not None and self._last_reward is not None:
            reward_improved = (
                float(normalized_reward) - self._last_reward >= self.reward_epsilon
            )

        if predicate_stage_id is not None or predicate_advanced is not None:
            stage_id = canonicalize_stage_id(
                predicate_stage_id or self._last_stage_id
            )
            if predicate_advanced is not None:
                # An explicit simulator predicate is authoritative, including
                # an explicit False. Do not turn False back into True by
                # comparing identifiers from incompatible namespaces.
                advanced = bool(predicate_advanced)
            else:
                advanced = (
                    self._last_predicate_stage_id is not None
                    and stage_id != self._last_predicate_stage_id
                )
            self._last_predicate_stage_id = stage_id
            confidence = 1.0
            source = "simulator_predicate"
        elif gemini_stage_id is not None:
            stage_id = canonicalize_stage_id(gemini_stage_id)
            confidence = float(gemini_confidence)
            supported = relation_improved or reward_improved
            qualified = confidence >= self.confidence_threshold or supported
            gemini_advanced = (
                self._last_gemini_stage_id is not None
                and stage_id not in {"", "UNKNOWN", self._last_gemini_stage_id}
            )
            advanced = gemini_advanced and qualified
            # Do not let an uncorroborated low-confidence guess become the
            # baseline. A qualified first observation establishes the
            # baseline but is not itself evidence of a transition.
            if stage_id not in {"", "UNKNOWN"} and qualified:
                self._last_gemini_stage_id = stage_id
            source = "gemini_planner"
        else:
            stage_id = "UNKNOWN"
            confidence = 0.0
            advanced = False
            source = "unknown"

        if task_success:
            advanced = True
            confidence = 1.0
            source = "task_success"
        if advanced:
            self._last_stage_id = stage_id
        if normalized_reward is not None:
            self._last_reward = float(normalized_reward)
        return ProgressEvidence(
            stage_id=stage_id,
            advanced=advanced,
            confidence=confidence,
            source=source,
            task_success=bool(task_success),
            reward_improved=reward_improved or relation_improved,
        )


__all__ = ["ProgressMonitor", "canonicalize_stage_id"]
