"""Raw policy promotion, statistical reporting, and adaptive replay utilities."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import beta

from .io_utils import AtomicJsonl


RAW_PROFILE = {
    "use_guidance": False,
    "mode_gate.enabled": False,
    "use_vlm_stage_recognition": False,
}


def assert_raw_profile(config: Mapping[str, object]) -> None:
    mismatches = {
        key: (config.get(key), expected)
        for key, expected in RAW_PROFILE.items()
        if config.get(key) is not expected
    }
    if mismatches:
        raise ValueError(f"raw regression profile violated: {mismatches}")


@dataclass(frozen=True)
class PolicyScore:
    candidate_id: str
    alpha_l: float
    macro_sr: float
    per_task_sr: Mapping[str, float]


@dataclass(frozen=True)
class PromotionDecision:
    status: str
    winner: PolicyScore | None
    reason: str
    eligible_ids: tuple[str, ...]


def select_alpha_top2(scores: Sequence[PolicyScore]) -> tuple[PolicyScore, ...]:
    if len(scores) != 4 or {round(item.alpha_l, 8) for item in scores} != {
        0.2,
        0.4,
        0.6,
        0.8,
    }:
        raise ValueError("alpha selection requires the frozen four candidates")
    return tuple(
        sorted(scores, key=lambda item: (-item.macro_sr, item.alpha_l, item.candidate_id))[:2]
    )


def raw_promotion_decision(
    *,
    parent_macro_sr: float,
    regression_scores: Sequence[PolicyScore],
    trigger_recheck_pass: Mapping[str, bool],
) -> PromotionDecision:
    raw_improved = [
        item for item in regression_scores if item.macro_sr > parent_macro_sr
    ]
    eligible = [
        item for item in raw_improved if trigger_recheck_pass.get(item.candidate_id, False)
    ]
    if not eligible:
        return PromotionDecision(
            status="NEEDS_MORE_DEMOS",
            winner=None,
            reason=(
                "no_candidate_strictly_improved_raw_macro"
                if not raw_improved
                else "all_raw_improved_candidates_failed_trigger_recheck"
            ),
            eligible_ids=(),
        )
    winner = min(
        eligible,
        key=lambda item: (-item.macro_sr, item.alpha_l, item.candidate_id),
    )
    return PromotionDecision(
        status="POLICY_STAGED",
        winner=winner,
        reason="highest_raw_macro_among_trigger_recheck_passes",
        eligible_ids=tuple(sorted(item.candidate_id for item in eligible)),
    )


def trigger_score(seen_successes: int, seen_total: int, unseen_successes: int, unseen_total: int) -> float:
    if min(seen_total, unseen_total) <= 0:
        raise ValueError("seen and unseen trigger recheck both require episodes")
    return 0.5 * seen_successes / seen_total + 0.5 * unseen_successes / unseen_total


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("invalid binomial count")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = z / denominator * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == total else min(1.0, center + radius)
    return lower, upper


def paired_hierarchical_bootstrap(
    task_ids: Sequence[str],
    context_ids: Sequence[str],
    candidate: Sequence[float],
    parent: Sequence[float],
    *,
    draws: int = 10_000,
    seed: int = 20260825,
) -> tuple[float, float, float]:
    task_ids = np.asarray(task_ids)
    context_ids = np.asarray(context_ids)
    candidate = np.asarray(candidate, dtype=np.float64)
    parent = np.asarray(parent, dtype=np.float64)
    if not (
        len(task_ids) == len(context_ids) == len(candidate) == len(parent)
    ):
        raise ValueError("paired bootstrap inputs are misaligned")
    tasks = np.unique(task_ids)
    rng = np.random.default_rng(seed)
    samples = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        sampled_tasks = rng.choice(tasks, size=len(tasks), replace=True)
        task_deltas = []
        for task in sampled_tasks:
            task_mask = task_ids == task
            contexts = np.unique(context_ids[task_mask])
            sampled_contexts = rng.choice(contexts, size=len(contexts), replace=True)
            context_deltas = []
            for context in sampled_contexts:
                mask = task_mask & (context_ids == context)
                indices = np.flatnonzero(mask)
                selected = rng.choice(indices, size=len(indices), replace=True)
                context_deltas.append(float((candidate[selected] - parent[selected]).mean()))
            task_deltas.append(float(np.mean(context_deltas)))
        samples[draw] = float(np.mean(task_deltas))
    point = float(np.mean(candidate - parent))
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return point, float(lower), float(upper)


def adaptive_counterfactual_target(
    *,
    successes: int,
    trials: int,
    max_width: float = 0.20,
) -> tuple[int, tuple[float, float]]:
    if trials not in {16, 32, 64} or not 0 <= successes <= trials:
        raise ValueError("adaptive audit trials must be 16, 32, or 64")
    failures = trials - successes
    interval = (
        float(beta.ppf(0.025, failures + 1, successes + 1)),
        float(beta.ppf(0.975, failures + 1, successes + 1)),
    )
    # The verifier is a direct symmetric two-class head.  More branches are
    # requested only when the posterior cannot distinguish which outcome is
    # the majority; there is no configurable cost-derived routing threshold.
    uncertain = interval[0] <= 0.5 <= interval[1] or interval[1] - interval[0] > max_width
    if trials < 64 and uncertain:
        return trials * 2, interval
    return trials, interval


class EpisodeLedger:
    def __init__(self, path: Path) -> None:
        self.events = AtomicJsonl(path)

    def append(self, episode_key: str, result: Mapping[str, object]) -> bool:
        value = dict(result)
        identity = json.dumps(
            {
                "episode_key": episode_key,
                "output_dir": value.get("output_dir"),
                "policy_id": value.get("policy_id"),
                "manifest_hash": value.get("manifest_hash"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return self.events.append(
            {
                "event_id": "complete-" + hashlib.sha256(identity.encode()).hexdigest(),
                "event_type": "EPISODE_COMPLETED",
                "episode_key": episode_key,
                **value,
            }
        )

    def invalidate(
        self,
        episode_key: str,
        *,
        reason: str,
        evidence: Mapping[str, object] | None = None,
    ) -> bool:
        if not reason:
            raise ValueError("episode invalidation requires a reason")
        value = {
            "episode_key": episode_key,
            "reason": reason,
            "evidence": dict(evidence or {}),
        }
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return self.events.append(
            {
                "event_id": "invalidate-" + hashlib.sha256(encoded.encode()).hexdigest(),
                "event_type": "EPISODE_INVALIDATED",
                **value,
            }
        )

    def completed(self) -> set[str]:
        status: dict[str, bool] = {}
        for item in self.events.iter_valid():
            episode_key = str(item["episode_key"])
            event_type = str(item.get("event_type", "EPISODE_COMPLETED"))
            if event_type == "EPISODE_COMPLETED":
                status[episode_key] = True
            elif event_type == "EPISODE_INVALIDATED":
                status[episode_key] = False
            else:
                raise ValueError(f"unknown episode ledger event type: {event_type}")
        return {episode_key for episode_key, active in status.items() if active}

    def completed_for(self, **required: object) -> set[str]:
        """Return effective completions for one immutable experiment generation.

        Older ledger rows intentionally do not satisfy newly introduced
        generation fields.  This makes a source, policy, or manifest change
        resume into fresh attempts while preserving every historical event.
        """

        if not required or any(value is None for value in required.values()):
            raise ValueError("completed_for requires non-null generation fields")
        status: dict[str, bool] = {}
        for item in self.events.iter_valid():
            episode_key = str(item["episode_key"])
            event_type = str(item.get("event_type", "EPISODE_COMPLETED"))
            if event_type == "EPISODE_COMPLETED":
                if all(item.get(key) == value for key, value in required.items()):
                    status[episode_key] = True
            elif event_type == "EPISODE_INVALIDATED":
                status[episode_key] = False
            else:
                raise ValueError(f"unknown episode ledger event type: {event_type}")
        return {episode_key for episode_key, active in status.items() if active}


__all__ = [
    "EpisodeLedger",
    "PolicyScore",
    "PromotionDecision",
    "adaptive_counterfactual_target",
    "assert_raw_profile",
    "paired_hierarchical_bootstrap",
    "raw_promotion_decision",
    "select_alpha_top2",
    "trigger_score",
    "wilson_interval",
]
