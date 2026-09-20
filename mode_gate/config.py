"""Configuration for the opt-in trajectory mode gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .experiment_contract import (
    DEFAULT_RETRY_SCHEDULE_50,
    FIXED_BUDGET_50_LABEL_VERSION,
    FixedBudgetExperimentContract,
    fixed_budget_controller_mode,
    fixed_budget_from_controller_mode,
    require_fixed_budget_50_contract,
    label_contract_payload,
)


@dataclass(frozen=True)
class ModeGateConfig:
    enabled: bool = False
    schema_version: str = "candidate-gate-v3"
    sample_count: int = 40
    chunk_horizon: int = 10
    stagnation_window: int = 3
    retry_budget: int = 50
    exploration_epsilon: float = 0.0
    controller_mode: str = "fixed_budget_50"
    # Formal runs must never silently fall back to initialization collection.
    require_learned_verifier: bool = False
    require_complete_rollout_before_expansion: bool = False
    label_version: str = FIXED_BUDGET_50_LABEL_VERSION
    # Experimental route controls are never written to active.json.  They are
    # explicit Hydra-only baselines over an otherwise fixed deployed policy.
    baseline_kind: str = ""
    baseline_budget: int = 50
    baseline_minimum_candidates: int = 2
    baseline_threshold: float = 0.5
    baseline_expansion_rate: float = 0.0
    baseline_seed: int = 20260825
    baseline_opportunity_bank: str = ""
    # Kept for legacy fixed-context callers and aligned with fixed_budget_50.
    max_rounds: int = 50
    seed: int = 0
    verifier_workers: int = 4
    planner_model: str = "gpt-6-astra"
    planner_timeout_seconds: float = 1205.0
    planner_max_retries: int = 2
    # Zero means unlimited for backward-compatible plans.  Formal replay jobs
    # set a positive signed limit plus one shared absolute ledger path.
    planner_max_provider_calls: int = 10_000
    planner_call_ledger: str = (
        "/shared/hengyil6/vls/self_improve/fixed_budget_50/"
        "factual_planner_calls.jsonl"
    )
    planner_prompt_version: str = "candidate-scorer-v4"
    # Legacy provider fields remain readable so old artifacts/configs migrate.
    planner_reasoning_effort: str = "ultra"
    verifier_model: str = "candidate-binary-v3"
    verifier_thinking_level: str = "medium"
    factual_provider_call_limit: int = 10_000
    counterfactual_provider_call_limit: int = 5_000
    total_provider_call_limit: int = 15_000
    counterfactual_initial_branches: int = 16
    counterfactual_max_branches: int = 32
    posterior_confidence: float = 0.95
    decision_boundary: float = 0.5
    suggested_train_contexts: int = 500
    suggested_calibration_contexts: int = 100
    suggested_test_contexts: int = 200
    output_subdir: str = "mode_gate"
    theta0_checkpoint: str = "/shared/hengyil6/vls/models/pi05_libero_finetuned_v044"
    registry_root: str = "/shared/hengyil6/vls/self_improve/registry"
    incident_root: str = "/shared/hengyil6/vls/self_improve/incidents"
    snapshot_root: str = "/shared/hengyil6/vls/self_improve/snapshots"
    slow_loop_root: str = "/shared/hengyil6/vls/self_improve/slow_loop"
    # Never launch a background worker without an explicit run command.
    auto_start_expansion_worker: bool = False
    teleop_operator: str = "human"
    teleop_port: int = 8765
    teleop_max_steps: int = 3000
    retry_schedule: tuple[tuple[float, float], ...] = DEFAULT_RETRY_SCHEDULE_50

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "ModeGateConfig":
        if value is None:
            return cls()
        known = {field_name for field_name in cls.__dataclass_fields__}
        kwargs = {key: raw for key, raw in dict(value).items() if key in known}
        config = cls(**kwargs)
        config.validate()
        return config

    def validate(self) -> None:
        if self.sample_count < 1:
            raise ValueError("mode_gate.sample_count must be positive")
        if self.chunk_horizon < 1:
            raise ValueError("mode_gate.chunk_horizon must be positive")
        if self.stagnation_window < 1 or self.retry_budget < 1:
            raise ValueError("stagnation_window and retry_budget must be positive")
        if not 0.0 <= self.exploration_epsilon < 1.0:
            raise ValueError("exploration_epsilon must be in [0, 1)")
        if self.exploration_epsilon != 0:
            raise ValueError("production candidate verifier uses argmax without exploration overrides")
        fixed_budget = fixed_budget_from_controller_mode(self.controller_mode)
        if self.controller_mode != "learned_verifier" and fixed_budget is None:
            raise ValueError("unsupported controller_mode")
        if self.require_learned_verifier and (
            self.controller_mode != "learned_verifier" or self.baseline_kind
        ):
            raise ValueError("formal execution requires the learned verifier; fixed-budget routing is forbidden")
        if self.require_complete_rollout_before_expansion and not self.require_learned_verifier:
            raise ValueError("the complete-rollout prerequisite belongs to formal learned-verifier execution")
        if fixed_budget is not None and fixed_budget != self.retry_budget:
            raise ValueError("fixed-budget controller mode must match retry_budget")
        allowed_baselines = {
            "",
            "fixed_budget",
            "always_expand_retain",
            "resteer_only",
            "verifier_no_lookup",
            "candidate_count_gate",
            "semantic_gate",
            "geometry_gate",
            "oracle",
            "random_matched",
        }
        if self.baseline_kind not in allowed_baselines:
            raise ValueError("unsupported experimental baseline_kind")
        if self.baseline_budget < 1:
            raise ValueError("baseline_budget must be positive")
        if (
            self.baseline_kind == "fixed_budget"
            and self.baseline_budget != self.retry_budget
        ):
            raise ValueError(
                "fixed-budget evaluation must use the experiment retry_budget"
            )
        if self.baseline_minimum_candidates < 1:
            raise ValueError("baseline_minimum_candidates must be in [1, 4]")
        if not 0.0 <= self.baseline_threshold <= 1.0:
            raise ValueError("baseline_threshold must be in [0, 1]")
        if not 0.0 <= self.baseline_expansion_rate <= 1.0:
            raise ValueError("baseline_expansion_rate must be in [0, 1]")
        if self.baseline_kind == "random_matched" and not self.baseline_opportunity_bank:
            raise ValueError("random_matched requires a frozen opportunity bank")
        if self.max_rounds < 1:
            raise ValueError("mode_gate.max_rounds must be positive")
        if not 1 <= self.verifier_workers <= 4:
            raise ValueError("mode_gate.verifier_workers must be between 1 and 4")
        if self.planner_model != "gpt-6-astra" or self.planner_reasoning_effort != "ultra":
            raise ValueError(
                "v2 mode scorer must use gpt-6-astra / ultra through the Codex account"
            )
        if int(self.planner_max_provider_calls) < 0:
            raise ValueError("mode_gate.planner_max_provider_calls must be non-negative")
        if int(self.planner_max_provider_calls) > int(
            self.factual_provider_call_limit
        ):
            raise ValueError("planner_max_provider_calls exceeds the factual call cap")
        if self.verifier_model != "candidate-binary-v3":
            raise ValueError("v2 verifier is the learned binary head")
        if len(self.retry_schedule) != self.retry_budget:
            raise ValueError("retry_schedule length must equal retry_budget")
        contract = self.experiment_contract()
        if self.label_version == FIXED_BUDGET_50_LABEL_VERSION:
            require_fixed_budget_50_contract(label_contract_payload(contract))
        if not all(
            str(value)
            for value in (
                self.theta0_checkpoint,
                self.registry_root,
                self.incident_root,
                self.snapshot_root,
                self.slow_loop_root,
            )
        ):
            raise ValueError("persistent v2 paths must be configured")
        if not str(self.teleop_operator).strip():
            raise ValueError("mode_gate.teleop_operator must be non-empty")
        if not 1 <= int(self.teleop_port) <= 65535:
            raise ValueError("mode_gate.teleop_port must be in [1, 65535]")
        if int(self.teleop_max_steps) < 1000:
            raise ValueError("mode_gate.teleop_max_steps must be at least 1000")

    def experiment_contract(self) -> FixedBudgetExperimentContract:
        """Return the serialized label semantics for this runtime configuration."""

        return FixedBudgetExperimentContract(
            label_version=self.label_version,
            controller_mode=fixed_budget_controller_mode(self.retry_budget),
            retry_budget=int(self.retry_budget),
            chunk_horizon=int(self.chunk_horizon),
            retry_schedule=tuple(
                tuple(map(float, level)) for level in self.retry_schedule
            ),
            counterfactual_initial_branches=int(
                self.counterfactual_initial_branches
            ),
            counterfactual_max_branches=int(self.counterfactual_max_branches),
            posterior_confidence=float(self.posterior_confidence),
            decision_boundary=float(self.decision_boundary),
            gemini_thinking_level=str(self.verifier_thinking_level),
            factual_provider_call_limit=int(self.factual_provider_call_limit),
            counterfactual_provider_call_limit=int(
                self.counterfactual_provider_call_limit
            ),
            total_provider_call_limit=int(self.total_provider_call_limit),
            suggested_train_contexts=int(self.suggested_train_contexts),
            suggested_calibration_contexts=int(
                self.suggested_calibration_contexts
            ),
            suggested_test_contexts=int(self.suggested_test_contexts),
        )
