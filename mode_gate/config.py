"""Configuration for the opt-in trajectory mode gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ModeGateConfig:
    enabled: bool = False
    sample_count: int = 40
    max_rounds: int = 5
    phase_points: int = 8
    max_components: int = 4
    pca_dims: int = 8
    seed: int = 0
    gmm_n_init: int = 5
    gmm_reg_covar: float = 1e-5
    gmm_max_iter: int = 200
    verifier_workers: int = 4
    planner_model: str = "gpt-5.6-sol"
    planner_reasoning_effort: str = "high"
    verifier_model: str = "gemini-robotics-er-2-preview"
    verifier_thinking_level: str = "high"
    output_subdir: str = "mode_gate"

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
        if self.max_rounds < 1:
            raise ValueError("mode_gate.max_rounds must be positive")
        if self.phase_points < 2:
            raise ValueError("mode_gate.phase_points must be at least 2")
        if not 1 <= self.max_components <= self.sample_count:
            raise ValueError("mode_gate.max_components must be within the sample count")
        if self.pca_dims < 1:
            raise ValueError("mode_gate.pca_dims must be positive")
        if self.gmm_n_init < 1 or self.gmm_max_iter < 1 or self.gmm_reg_covar <= 0:
            raise ValueError("invalid GMM configuration")
        if not 1 <= self.verifier_workers <= 4:
            raise ValueError("mode_gate.verifier_workers must be between 1 and 4")
        if self.planner_model != "gpt-5.6-sol":
            raise ValueError("mode gate Planner must use the exact model gpt-5.6-sol")
        if self.verifier_model != "gemini-robotics-er-2-preview":
            raise ValueError(
                "mode gate Verifier must use the exact model "
                "gemini-robotics-er-2-preview"
            )

