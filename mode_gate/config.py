"""Configuration for the opt-in trajectory mode gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ModeGateConfig:
    enabled: bool = False
    schema_version: str = "mode-gate-v2"
    sample_count: int = 40
    chunk_horizon: int = 10
    stagnation_window: int = 3
    retry_budget: int = 4
    exploration_epsilon: float = 0.10
    controller_mode: str = "learned_verifier"
    # Experimental route controls are never written to active.json.  They are
    # explicit Hydra-only baselines over an otherwise fixed deployed policy.
    baseline_kind: str = ""
    baseline_budget: int = 4
    baseline_minimum_modes: int = 2
    baseline_threshold: float = 0.5
    baseline_expansion_rate: float = 0.0
    baseline_seed: int = 20260825
    baseline_opportunity_bank: str = ""
    # Kept for legacy fixed-context callers.  The v2 runtime uses retry_budget.
    max_rounds: int = 5
    phase_points: int = 8
    keypoint_limit: int = 8
    max_components: int = 4
    pca_dims: int = 8
    seed: int = 0
    gmm_n_init: int = 5
    gmm_reg_covar: float = 1e-5
    gmm_max_iter: int = 500
    min_mode_mass: float = 0.05
    min_unique_ancestors: int = 2
    verifier_workers: int = 4
    planner_model: str = "gemini-robotics-er-2-preview"
    planner_timeout_seconds: float = 60.0
    planner_max_retries: int = 2
    planner_prompt_version: str = "mode-scorer-v3"
    # Legacy provider fields remain readable so old artifacts/configs migrate.
    planner_reasoning_effort: str = "high"
    verifier_model: str = "learned-binary-v1"
    verifier_thinking_level: str = "high"
    output_subdir: str = "mode_gate"
    theta0_checkpoint: str = "/shared/hengyil6/vls/models/pi05_libero_finetuned_v044"
    registry_root: str = "/shared/hengyil6/vls/self_improve/registry"
    incident_root: str = "/shared/hengyil6/vls/self_improve/incidents"
    snapshot_root: str = "/shared/hengyil6/vls/self_improve/snapshots"
    slow_loop_root: str = "/shared/hengyil6/vls/self_improve/slow_loop"
    retry_schedule: tuple[tuple[float, float], ...] = (
        (1.00, 1.00),
        (1.15, 1.10),
        (1.30, 1.25),
        (1.50, 1.40),
    )

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
        if self.sample_count < 3:
            raise ValueError("mode_gate.sample_count must be at least 3")
        if self.chunk_horizon != 10:
            raise ValueError("mode_gate.chunk_horizon is frozen at 10")
        if self.stagnation_window < 1 or self.retry_budget != 4:
            raise ValueError("stagnation_window must be positive and retry_budget frozen at 4")
        if not 0.0 <= self.exploration_epsilon < 1.0:
            raise ValueError("exploration_epsilon must be in [0, 1)")
        if self.controller_mode not in {"learned_verifier", "fixed_budget_4"}:
            raise ValueError("unsupported controller_mode")
        allowed_baselines = {
            "",
            "fixed_budget",
            "always_expand_retain",
            "resteer_only",
            "verifier_no_lookup",
            "mode_count_gate",
            "semantic_gate",
            "geometry_gate",
            "oracle",
            "random_matched",
        }
        if self.baseline_kind not in allowed_baselines:
            raise ValueError("unsupported experimental baseline_kind")
        if self.baseline_budget not in {1, 2, 4, 8, 16, 32}:
            raise ValueError("baseline_budget must be one of 1,2,4,8,16,32")
        if not 1 <= self.baseline_minimum_modes <= 4:
            raise ValueError("baseline_minimum_modes must be in [1, 4]")
        if not 0.0 <= self.baseline_threshold <= 1.0:
            raise ValueError("baseline_threshold must be in [0, 1]")
        if not 0.0 <= self.baseline_expansion_rate <= 1.0:
            raise ValueError("baseline_expansion_rate must be in [0, 1]")
        if self.baseline_kind == "random_matched" and not self.baseline_opportunity_bank:
            raise ValueError("random_matched requires a frozen opportunity bank")
        if self.max_rounds < 1:
            raise ValueError("mode_gate.max_rounds must be positive")
        if self.phase_points < 2:
            raise ValueError("mode_gate.phase_points must be at least 2")
        if not 1 <= self.max_components <= self.sample_count:
            raise ValueError("mode_gate.max_components must be within the sample count")
        if self.pca_dims < 1:
            raise ValueError("mode_gate.pca_dims must be positive")
        if self.keypoint_limit != 8:
            raise ValueError("mode_gate.keypoint_limit is frozen at 8")
        if self.gmm_n_init < 1 or self.gmm_max_iter < 1 or self.gmm_reg_covar <= 0:
            raise ValueError("invalid GMM configuration")
        if not 0.0 < self.min_mode_mass < 1.0 or self.min_unique_ancestors < 1:
            raise ValueError("invalid active-mode thresholds")
        if not 1 <= self.verifier_workers <= 4:
            raise ValueError("mode_gate.verifier_workers must be between 1 and 4")
        if self.planner_model != "gemini-robotics-er-2-preview":
            raise ValueError(
                "v2 mode scorer must use gemini-robotics-er-2-preview"
            )
        if self.verifier_model != "learned-binary-v1":
            raise ValueError("v2 verifier is the learned binary head")
        if len(self.retry_schedule) != self.retry_budget:
            raise ValueError("retry_schedule must contain exactly four entries")
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
