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


def rank_current_task_candidates(scores: Sequence[PolicyScore]) -> tuple[PolicyScore, ...]:
    """Rank all candidates by held-out current-task SR, never old-task SR."""
    if not scores or len({item.candidate_id for item in scores}) != len(scores):
        raise ValueError("current-task ranking requires unique, non-empty candidates")
    return tuple(
        sorted(scores, key=lambda item: (-item.macro_sr, item.alpha_l, item.candidate_id))
    )


def gain_retention_tradeoffs(
    *, parent_current_sr: float, current_task_scores: Sequence[PolicyScore],
    forgetting: Mapping[str, float], forgetting_penalty: float = 1.0,
) -> dict[str, dict[str, object]]:
    """Two objectives: increase the current task and limit old-task losses."""
    ranked = rank_current_task_candidates(current_task_scores)
    if (not math.isfinite(forgetting_penalty) or forgetting_penalty < 0
            or not math.isfinite(parent_current_sr) or not 0 <= parent_current_sr <= 1):
        raise ValueError("invalid tradeoff weight or parent success rate")
    if set(forgetting) != {item.candidate_id for item in ranked}:
        raise ValueError("every candidate requires paired old-task forgetting evidence")
    values = {}
    for item in ranked:
        loss = float(forgetting[item.candidate_id])
        if (not math.isfinite(loss) or not 0 <= loss <= 1
                or not math.isfinite(item.macro_sr) or not 0 <= item.macro_sr <= 1):
            raise ValueError("success rates and forgetting must be finite probabilities")
        gain = item.macro_sr - parent_current_sr
        values[item.candidate_id] = {
            "current_task_gain": gain, "old_task_forgetting": loss,
            "score": gain - forgetting_penalty * loss,
            "current_task_improved": gain > 0,
        }
    for key, value in values.items():
        value["pareto_dominated"] = any(
            other["current_task_gain"] >= value["current_task_gain"] - 1e-12
            and other["old_task_forgetting"] <= value["old_task_forgetting"] + 1e-12
            and (other["current_task_gain"] > value["current_task_gain"] + 1e-12
                 or other["old_task_forgetting"] < value["old_task_forgetting"] - 1e-12)
            for other_key, other in values.items() if other_key != key
        )
    return values


def raw_promotion_decision(
    *, parent_current_sr: float, current_task_scores: Sequence[PolicyScore],
    forgetting: Mapping[str, float], forgetting_penalty: float = 1.0,
) -> PromotionDecision:
    values = gain_retention_tradeoffs(
        parent_current_sr=parent_current_sr, current_task_scores=current_task_scores,
        forgetting=forgetting, forgetting_penalty=forgetting_penalty,
    )
    # Compare ALL merged candidates by the same difference score. Current-task
    # ties, declines and negative combined scores are not separate rejection
    # gates. In particular, a 100% parent must not make promotion impossible.
    winner = min(current_task_scores, key=lambda item: (
        -round(values[item.candidate_id]["score"], 12),
        values[item.candidate_id]["old_task_forgetting"],
        -values[item.candidate_id]["current_task_gain"],
        item.alpha_l, item.candidate_id,
    ))
    return PromotionDecision(
        status="POLICY_STAGED", winner=winner,
        reason="best_current_task_gain_minus_old_task_forgetting",
        eligible_ids=tuple(sorted(item.candidate_id for item in current_task_scores)),
    )


def retention_metrics(*, parent: PolicyScore, candidate: PolicyScore) -> dict[str, object]:
    """Measure paired old-task losses without a zero-drop acceptance gate.

    Clip each task's loss BEFORE averaging so gains on unrelated old tasks
    cannot cancel forgetting elsewhere. Report net SR change separately.
    Finite-sample diagnostics are not proof of zero forgetting.
    """
    if not parent.per_task_sr or set(parent.per_task_sr) != set(candidate.per_task_sr):
        raise ValueError("retention task banks must be non-empty and paired")
    if any(not math.isfinite(value) or not 0 <= value <= 1
           for scores in (parent.per_task_sr, candidate.per_task_sr) for value in scores.values()):
        raise ValueError("old-task success rates must be finite probabilities")
    deltas = {task: candidate.per_task_sr[task] - parent.per_task_sr[task]
              for task in sorted(parent.per_task_sr)}
    losses = {task: max(0.0, -delta) for task, delta in deltas.items()}
    return {
        "macro_delta": candidate.macro_sr - parent.macro_sr,
        "per_task_delta": deltas, "per_task_forgetting": losses,
        "macro_forgetting": sum(losses.values()) / len(losses),
        "max_task_forgetting": max(losses.values()),
        "regressed_tasks": [task for task, loss in losses.items() if loss > 1e-12],
        "criterion": "mean_positive_per_task_success_rate_drop",
        "zero_drop_required": False, "statistical_zero_forgetting_proven": False,
    }


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
    max_width: float | None = None,
    posterior_confidence: float = 0.95,
    decision_boundary: float = 0.5,
    initial_branches: int = 16,
    max_branches: int = 32,
) -> tuple[int, tuple[float, float]]:
    """Return 16 or 32 branches under the fixed-budget-10 label rule.

    ``max_width`` is accepted only so old callers fail by semantics rather than
    by signature; interval width no longer controls collection.  At 16 trials
    we stop when at least ``posterior_confidence`` of the Beta posterior lies
    on one side of 0.5.  Otherwise we request 32.  Thirty-two is final even if
    still uncertain; the caller must censor that context instead of attaching
    a binary label.
    """

    del max_width
    if trials not in {int(initial_branches), int(max_branches)} or not 0 <= successes <= trials:
        raise ValueError("adaptive audit trials must be the configured 16 or 32")
    if not 0.5 < float(posterior_confidence) < 1.0:
        raise ValueError("posterior_confidence must be in (0.5, 1)")
    if not 0.0 < float(decision_boundary) < 1.0:
        raise ValueError("decision_boundary must be in (0, 1)")
    failures = trials - successes
    alpha = (1.0 - float(posterior_confidence)) / 2.0
    interval = (
        float(beta.ppf(alpha, failures + 1, successes + 1)),
        float(beta.ppf(1.0 - alpha, failures + 1, successes + 1)),
    )
    below = float(beta.cdf(decision_boundary, failures + 1, successes + 1))
    above = 1.0 - below
    decisive = max(below, above) >= float(posterior_confidence)
    if trials == int(initial_branches) and not decisive:
        return int(max_branches), interval
    return trials, interval


def counterfactual_posterior_status(
    *,
    successes: int,
    trials: int,
    posterior_confidence: float = 0.95,
    decision_boundary: float = 0.5,
) -> dict[str, object]:
    """Describe whether a replay label is decisive or must be censored."""

    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("invalid counterfactual counts")
    failures = trials - successes
    below = float(beta.cdf(decision_boundary, failures + 1, successes + 1))
    above = 1.0 - below
    side_probability = max(below, above)
    if side_probability >= float(posterior_confidence):
        label_status = "LABELED"
        posterior_side = "EXPANSION" if above >= below else "RE-STEER"
    else:
        label_status = "AMBIGUOUS/CENSORED"
        posterior_side = "AMBIGUOUS"
    return {
        "label_status": label_status,
        "posterior_side": posterior_side,
        "posterior_side_probability": side_probability,
        "posterior_probability_below_boundary": below,
        "posterior_probability_above_boundary": above,
        "decision_boundary": float(decision_boundary),
        "posterior_confidence_required": float(posterior_confidence),
    }


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
    "counterfactual_posterior_status",
    "assert_raw_profile",
    "paired_hierarchical_bootstrap",
    "raw_promotion_decision",
    "rank_current_task_candidates",
    "retention_metrics",
    "gain_retention_tradeoffs",
    "wilson_interval",
]
