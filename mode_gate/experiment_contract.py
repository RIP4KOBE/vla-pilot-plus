"""Versioned experiment contract for fixed-budget verifier data.

The values in this module are defaults, not hard-coded runtime locks.  A
contract is serialized into every new replay, feature, label, training, and
evaluation artifact so an experiment can be changed by creating a new label
version instead of mutating historical evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence


FIXED_BUDGET_10_LABEL_VERSION = "fixed_budget_10-v1"
FIXED_BUDGET_50_LABEL_VERSION = "fixed_budget_50-v2"


def fixed_budget_controller_mode(retry_budget: int) -> str:
    retry_budget = int(retry_budget)
    if retry_budget <= 0:
        raise ValueError("retry_budget must be positive")
    return f"fixed_budget_{retry_budget}"


def fixed_budget_from_controller_mode(controller_mode: str) -> int | None:
    prefix = "fixed_budget_"
    value = str(controller_mode)
    if not value.startswith(prefix):
        return None
    suffix = value[len(prefix) :]
    if not suffix.isdigit() or int(suffix) <= 0:
        return None
    return int(suffix)


DEFAULT_RETRY_SCHEDULE_10: tuple[tuple[float, float], ...] = (
    (1.00, 1.00),
    (1.15, 1.10),
    (1.30, 1.25),
    (1.50, 1.40),
    (1.75, 1.50),
    (2.00, 1.60),
    (2.25, 1.70),
    (2.50, 1.80),
    (2.75, 1.90),
    (3.00, 2.00),
)
DEFAULT_RETRY_SCHEDULE_50 = ((1.0, 1.0),) * 50  # v44+VLS baseline parity at every retry


@dataclass(frozen=True)
class FixedBudgetExperimentContract:
    """Complete, serializable semantics of one verifier label generation."""

    schema_version: str = "fixed-budget-experiment-contract-v1"
    label_version: str = FIXED_BUDGET_50_LABEL_VERSION
    controller_mode: str = "fixed_budget_50"
    retry_budget: int = 50
    chunk_horizon: int = 10
    retry_schedule: tuple[tuple[float, float], ...] = DEFAULT_RETRY_SCHEDULE_50
    guide_scale_max: float = 80.0
    diversity_scale_max: float = 20.0
    counterfactual_initial_branches: int = 16
    counterfactual_max_branches: int = 32
    posterior_confidence: float = 0.95
    decision_boundary: float = 0.5
    ambiguous_status: str = "AMBIGUOUS/CENSORED"
    gemini_thinking_level: str = "medium"
    factual_provider_call_limit: int = 10_000
    counterfactual_provider_call_limit: int = 5_000
    total_provider_call_limit: int = 15_000
    suggested_train_contexts: int = 500
    suggested_calibration_contexts: int = 100
    suggested_test_contexts: int = 200
    coverage_strategy: str = (
        "all_libero_pro_tasks_breadth_first_then_minority_and_boundary"
    )

    def __post_init__(self) -> None:
        if not str(self.label_version).strip():
            raise ValueError("label_version must be non-empty")
        if self.controller_mode != fixed_budget_controller_mode(self.retry_budget):
            raise ValueError("controller_mode must encode retry_budget")
        if self.retry_budget <= 0 or self.chunk_horizon <= 0:
            raise ValueError("retry_budget and chunk_horizon must be positive")
        if len(self.retry_schedule) != self.retry_budget:
            raise ValueError("retry_schedule length must equal retry_budget")
        if not (0 < self.guide_scale_max < float("inf") and 0 < self.diversity_scale_max < float("inf")):
            raise ValueError("steering scale limits must be finite and positive")
        if any(
            len(tuple(level)) != 2
            or float(level[0]) <= 0.0
            or float(level[1]) <= 0.0
            for level in self.retry_schedule
        ):
            raise ValueError("retry_schedule entries must contain positive multipliers")
        if not (
            0 < self.counterfactual_initial_branches
            <= self.counterfactual_max_branches
        ):
            raise ValueError("invalid adaptive branch bounds")
        if not 0.5 < self.posterior_confidence < 1.0:
            raise ValueError("posterior_confidence must be in (0.5, 1)")
        if not 0.0 < self.decision_boundary < 1.0:
            raise ValueError("decision_boundary must be in (0, 1)")
        if self.gemini_thinking_level not in {"minimal", "low", "medium", "high"}:
            raise ValueError("unsupported Gemini thinking_level")
        if min(
            self.factual_provider_call_limit,
            self.counterfactual_provider_call_limit,
            self.total_provider_call_limit,
        ) <= 0:
            raise ValueError("provider-call limits must be positive")
        if (
            self.factual_provider_call_limit
            + self.counterfactual_provider_call_limit
            > self.total_provider_call_limit
        ):
            raise ValueError("category provider-call limits exceed the total limit")
        if min(
            self.suggested_train_contexts,
            self.suggested_calibration_contexts,
            self.suggested_test_contexts,
        ) <= 0:
            raise ValueError("suggested data targets must be positive")

    @property
    def max_policy_steps_per_branch(self) -> int:
        return self.retry_budget * self.chunk_horizon

    @property
    def worst_case_provider_calls_per_context(self) -> int:
        # One feature call, plus one sampling and at most one progress call for
        # each retry chunk in every branch.  This intentionally overestimates
        # cached/direct-success paths so the hard ledger cap remains safe.
        return 1 + self.counterfactual_max_branches * (self.retry_budget + 1)

    @property
    def counterfactual_context_limit(self) -> int:
        return max(
            1,
            self.counterfactual_provider_call_limit
            // self.worst_case_provider_calls_per_context,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["retry_schedule"] = [list(level) for level in self.retry_schedule]
        value["max_policy_steps_per_branch"] = self.max_policy_steps_per_branch
        value["worst_case_provider_calls_per_context"] = (
            self.worst_case_provider_calls_per_context
        )
        value["counterfactual_context_limit"] = self.counterfactual_context_limit
        return value

    @property
    def contract_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.to_dict(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> "FixedBudgetExperimentContract":
        payload = dict(value)
        for derived in (
            "max_policy_steps_per_branch",
            "worst_case_provider_calls_per_context",
            "counterfactual_context_limit",
            "contract_hash",
        ):
            payload.pop(derived, None)
        if "retry_schedule" in payload:
            payload["retry_schedule"] = tuple(
                tuple(map(float, level))
                for level in payload["retry_schedule"]
            )
        return cls(**payload)


FIXED_BUDGET_10_CONTRACT = FixedBudgetExperimentContract(
    label_version=FIXED_BUDGET_10_LABEL_VERSION, controller_mode="fixed_budget_10",
    retry_budget=10, retry_schedule=DEFAULT_RETRY_SCHEDULE_10,
)
FIXED_BUDGET_50_CONTRACT = FixedBudgetExperimentContract()


def require_fixed_budget_50_contract(value: Mapping[str, Any]) -> FixedBudgetExperimentContract:
    contract = FixedBudgetExperimentContract.from_mapping(value)
    if (contract.retry_budget, contract.chunk_horizon, contract.label_version) != (50, 10, FIXED_BUDGET_50_LABEL_VERSION):
        raise ValueError("new candidate verifier labels require fixed_budget_50-v2 (50 x 10)")
    if value.get("contract_hash") not in (None, contract.contract_hash):
        raise ValueError("label contract hash mismatch")
    return contract


def require_fixed_budget_10_contract(
    value: Mapping[str, Any],
) -> FixedBudgetExperimentContract:
    contract = FixedBudgetExperimentContract.from_mapping(value)
    if contract != FIXED_BUDGET_10_CONTRACT:
        raise ValueError(
            "artifact contract is not the current fixed_budget_10 label version"
        )
    supplied_hash = value.get("contract_hash")
    if supplied_hash is not None and str(supplied_hash) != contract.contract_hash:
        raise ValueError("fixed_budget_10 contract hash mismatch")
    return contract


def regenerate_budget_state(
    controller_state: Mapping[str, Any],
    *,
    contract: FixedBudgetExperimentContract = FIXED_BUDGET_50_CONTRACT,
) -> dict[str, Any]:
    """Derive new-budget fields without mutating a historical snapshot/label."""

    source_retry_index = int(controller_state.get("retry_index", 0))
    if not 0 <= source_retry_index <= contract.retry_budget:
        raise ValueError("snapshot retry_index is outside the requested budget")
    failure_count = min(
        contract.retry_budget,
        max(0, int(controller_state.get("failure_count", 0))),
    )
    return {
        "retry_budget": contract.retry_budget,
        "retry_index": source_retry_index,
        "remaining_budget": contract.retry_budget - source_retry_index,
        "failure_count": failure_count,
        "retry_schedule": [list(level) for level in contract.retry_schedule],
        "chunk_horizon": contract.chunk_horizon,
        "max_policy_steps": (
            contract.retry_budget - source_retry_index
        )
        * contract.chunk_horizon,
        "derived_from_snapshot_retry_index": source_retry_index,
    }


def label_contract_payload(
    contract: FixedBudgetExperimentContract = FIXED_BUDGET_50_CONTRACT,
) -> dict[str, Any]:
    value = contract.to_dict()
    value["contract_hash"] = contract.contract_hash
    return value


def validate_retry_schedule(
    schedule: Sequence[Sequence[float]], retry_budget: int
) -> tuple[tuple[float, float], ...]:
    normalized = tuple(tuple(map(float, level)) for level in schedule)
    if len(normalized) != int(retry_budget):
        raise ValueError("retry_schedule length must equal retry_budget")
    if any(len(level) != 2 or min(level) <= 0 for level in normalized):
        raise ValueError("retry_schedule multipliers must be positive pairs")
    return normalized


__all__ = [
    "DEFAULT_RETRY_SCHEDULE_50",
    "FIXED_BUDGET_50_CONTRACT",
    "FIXED_BUDGET_50_LABEL_VERSION",
    "require_fixed_budget_50_contract",
    "DEFAULT_RETRY_SCHEDULE_10",
    "FIXED_BUDGET_10_CONTRACT",
    "FIXED_BUDGET_10_LABEL_VERSION",
    "FixedBudgetExperimentContract",
    "fixed_budget_controller_mode",
    "fixed_budget_from_controller_mode",
    "label_contract_payload",
    "regenerate_budget_state",
    "require_fixed_budget_10_contract",
    "validate_retry_schedule",
]
