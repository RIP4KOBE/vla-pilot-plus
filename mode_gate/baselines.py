"""Reproducible controller baselines and a minimal faithful CLARE baseline.

The controller baselines share one decision contract so that they can be run
on exactly the same frozen opportunity IDs.  The CLARE implementation follows
the paper's three defining mechanisms instead of reducing it to a cosine gate:

* parallel bottleneck adapters in selected FFN layers;
* per-stage autoencoder discriminators and z-score based layer expansion;
* task-ID-free routing to the adapter linked to the lowest reconstruction
  error discriminator.

This module intentionally does not couple those mechanisms to a particular
VLA implementation.  ``ClareExpandableFFN`` is the integration boundary for
wrapping selected square FFN modules in PI0.5 or another PyTorch policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch
from torch import Tensor, nn

from .io_utils import atomic_write_json
from .types import ControllerRoute


class BaselineKind(str, Enum):
    FIXED_BUDGET = "fixed_budget"
    ALWAYS_EXPAND_RETAIN = "always_expand_retain"
    RESTEER_ONLY = "resteer_only"
    VERIFIER_NO_LOOKUP = "verifier_no_lookup"
    MODE_COUNT_GATE = "mode_count_gate"
    SEMANTIC_GATE = "semantic_gate"
    GEOMETRY_GATE = "geometry_gate"
    ORACLE = "oracle"
    RANDOM_MATCHED = "random_matched"
    CLARE = "clare"


@dataclass(frozen=True)
class BaselineOpportunity:
    """All information a baseline may use at one verifier opportunity."""

    opportunity_id: str
    retry_index: int
    active_mode_count: int
    max_semantic_score: float
    min_collision_risk: float
    learned_p_expansion: float | None = None
    learned_verifier_route: ControllerRoute | None = None
    oracle_should_expand: bool | None = None

    def __post_init__(self) -> None:
        if not self.opportunity_id:
            raise ValueError("opportunity_id is required")
        if self.retry_index < 0 or not 0 <= self.active_mode_count <= 4:
            raise ValueError("invalid retry index or active mode count")
        for name in ("max_semantic_score", "min_collision_risk"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.learned_p_expansion is not None and not 0.0 <= float(
            self.learned_p_expansion
        ) <= 1.0:
            raise ValueError("learned_p_expansion must be in [0, 1]")
        if self.learned_verifier_route not in {
            None,
            ControllerRoute.RESTEER,
            ControllerRoute.EXPAND,
        }:
            raise ValueError("learned verifier route must be RE-STEER or EXPANSION")


@dataclass(frozen=True)
class BaselineDecision:
    route: ControllerRoute
    reason: str
    retain_policy: bool = False
    lookup_enabled: bool = True
    merge_method: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "reason": self.reason,
            "retain_policy": self.retain_policy,
            "lookup_enabled": self.lookup_enabled,
            "merge_method": self.merge_method,
            "metadata": dict(self.metadata),
        }


class BaselineRouter:
    kind: BaselineKind

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        raise NotImplementedError


@dataclass(frozen=True)
class FixedBudgetRouter(BaselineRouter):
    budget: int
    kind: BaselineKind = BaselineKind.FIXED_BUDGET

    def __post_init__(self) -> None:
        if self.budget not in {1, 2, 4, 8, 16, 32}:
            raise ValueError("fixed budget must be one of 1,2,4,8,16,32")

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        if opportunity.retry_index >= self.budget:
            return BaselineDecision(
                ControllerRoute.EXPAND,
                "fixed_retry_budget_exhausted",
                metadata={"budget": self.budget},
            )
        return BaselineDecision(
            ControllerRoute.RESTEER,
            "fixed_retry_budget_available",
            metadata={"budget": self.budget},
        )


@dataclass(frozen=True)
class AlwaysExpandRetainRouter(BaselineRouter):
    kind: BaselineKind = BaselineKind.ALWAYS_EXPAND_RETAIN

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        del opportunity
        return BaselineDecision(
            ControllerRoute.EXPAND,
            "always_expand_with_retain_merge",
            lookup_enabled=False,
            merge_method="retain_uniform",
            metadata={
                "equation": "parent + alpha * (theta_ft - parent)",
                "alpha_groups": ["vision", "language", "action"],
                "alpha_grid": [0.2, 0.4, 0.6, 0.8],
            },
        )


@dataclass(frozen=True)
class ResteerOnlyRouter(BaselineRouter):
    kind: BaselineKind = BaselineKind.RESTEER_ONLY

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        del opportunity
        return BaselineDecision(
            ControllerRoute.RESTEER,
            "resteer_only_control",
            lookup_enabled=False,
        )


@dataclass(frozen=True)
class VerifierNoLookupRouter(BaselineRouter):
    kind: BaselineKind = BaselineKind.VERIFIER_NO_LOOKUP

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        if opportunity.learned_verifier_route is None:
            raise ValueError("verifier-no-lookup requires the learned head decision")
        return BaselineDecision(
            opportunity.learned_verifier_route,
            "learned_verifier_without_signature_lookup",
            lookup_enabled=False,
            metadata={
                "p_expansion": opportunity.learned_p_expansion,
                "decision_rule": "head_argmax",
            },
        )


@dataclass(frozen=True)
class ModeCountGateRouter(BaselineRouter):
    """Expand when fewer than ``minimum_modes`` viable modes remain."""

    minimum_modes: int = 2
    kind: BaselineKind = BaselineKind.MODE_COUNT_GATE

    def __post_init__(self) -> None:
        if not 1 <= self.minimum_modes <= 4:
            raise ValueError("minimum_modes must be in [1, 4]")

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        expand = opportunity.active_mode_count < self.minimum_modes
        return BaselineDecision(
            ControllerRoute.EXPAND if expand else ControllerRoute.RESTEER,
            "mode_count_threshold",
            lookup_enabled=False,
            metadata={
                "active_mode_count": opportunity.active_mode_count,
                "minimum_modes": self.minimum_modes,
            },
        )


@dataclass(frozen=True)
class SemanticGateRouter(BaselineRouter):
    """Expand when no mode reaches the pre-registered semantic threshold."""

    minimum_score: float = 0.5
    kind: BaselineKind = BaselineKind.SEMANTIC_GATE

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_score <= 1.0:
            raise ValueError("minimum_score must be in [0, 1]")

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        expand = opportunity.max_semantic_score < self.minimum_score
        return BaselineDecision(
            ControllerRoute.EXPAND if expand else ControllerRoute.RESTEER,
            "semantic_score_threshold",
            lookup_enabled=False,
            metadata={
                "max_semantic_score": opportunity.max_semantic_score,
                "minimum_score": self.minimum_score,
            },
        )


@dataclass(frozen=True)
class GeometryGateRouter(BaselineRouter):
    """Expand when even the safest viable mode exceeds a collision threshold."""

    maximum_collision_risk: float = 0.5
    kind: BaselineKind = BaselineKind.GEOMETRY_GATE

    def __post_init__(self) -> None:
        if not 0.0 <= self.maximum_collision_risk <= 1.0:
            raise ValueError("maximum_collision_risk must be in [0, 1]")

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        expand = (
            opportunity.active_mode_count == 0
            or opportunity.min_collision_risk > self.maximum_collision_risk
        )
        return BaselineDecision(
            ControllerRoute.EXPAND if expand else ControllerRoute.RESTEER,
            "geometry_risk_threshold",
            lookup_enabled=False,
            metadata={
                "min_collision_risk": opportunity.min_collision_risk,
                "maximum_collision_risk": self.maximum_collision_risk,
            },
        )


@dataclass(frozen=True)
class OracleRouter(BaselineRouter):
    kind: BaselineKind = BaselineKind.ORACLE

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        if opportunity.oracle_should_expand is None:
            raise ValueError("oracle baseline requires a counterfactual oracle label")
        return BaselineDecision(
            ControllerRoute.EXPAND
            if opportunity.oracle_should_expand
            else ControllerRoute.RESTEER,
            "counterfactual_oracle",
            lookup_enabled=False,
        )


class MatchedRandomRouter(BaselineRouter):
    """Seeded random control with an exact expansion count on a frozen bank."""

    kind = BaselineKind.RANDOM_MATCHED

    def __init__(
        self,
        *,
        opportunity_ids: Sequence[str],
        expansion_rate: float,
        seed: int,
    ) -> None:
        ids = tuple(map(str, opportunity_ids))
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("opportunity_ids must be non-empty and unique")
        if not 0.0 <= float(expansion_rate) <= 1.0:
            raise ValueError("expansion_rate must be in [0, 1]")
        self.expansion_rate = float(expansion_rate)
        self.seed = int(seed)
        ranked = sorted(
            ids,
            key=lambda value: hashlib.sha256(
                f"matched-random-v1\0{self.seed}\0{value}".encode()
            ).digest(),
        )
        count = int(round(self.expansion_rate * len(ranked)))
        self.opportunity_ids = ids
        self._expanded = frozenset(ranked[:count])

    def decide(self, opportunity: BaselineOpportunity) -> BaselineDecision:
        if opportunity.opportunity_id not in self.opportunity_ids:
            raise ValueError("opportunity is outside the frozen random bank")
        expand = opportunity.opportunity_id in self._expanded
        return BaselineDecision(
            ControllerRoute.EXPAND if expand else ControllerRoute.RESTEER,
            "matched_expansion_rate_random_control",
            lookup_enabled=False,
            metadata={"expansion_rate": self.expansion_rate, "seed": self.seed},
        )


def build_baseline_router(
    *,
    kind: str,
    budget: int = 4,
    minimum_modes: int = 2,
    threshold: float = 0.5,
    expansion_rate: float = 0.0,
    seed: int = 20260825,
    opportunity_bank: Path | None = None,
) -> BaselineRouter | None:
    """Construct one explicit experiment router; production uses ``kind=''``."""

    if not kind:
        return None
    baseline = BaselineKind(kind)
    if baseline is BaselineKind.FIXED_BUDGET:
        return FixedBudgetRouter(budget)
    if baseline is BaselineKind.ALWAYS_EXPAND_RETAIN:
        return AlwaysExpandRetainRouter()
    if baseline is BaselineKind.RESTEER_ONLY:
        return ResteerOnlyRouter()
    if baseline is BaselineKind.VERIFIER_NO_LOOKUP:
        return VerifierNoLookupRouter()
    if baseline is BaselineKind.MODE_COUNT_GATE:
        return ModeCountGateRouter(int(minimum_modes))
    if baseline is BaselineKind.SEMANTIC_GATE:
        return SemanticGateRouter(float(threshold))
    if baseline is BaselineKind.GEOMETRY_GATE:
        return GeometryGateRouter(float(threshold))
    if baseline is BaselineKind.ORACLE:
        return OracleRouter()
    if baseline is BaselineKind.RANDOM_MATCHED:
        if opportunity_bank is None or not Path(opportunity_bank).is_file():
            raise FileNotFoundError("random_matched requires a frozen opportunity bank")
        value = json.loads(Path(opportunity_bank).read_text(encoding="utf-8"))
        ids = value.get("opportunity_ids") if isinstance(value, dict) else value
        if not isinstance(ids, list):
            raise ValueError("opportunity bank must be a list or contain opportunity_ids")
        return MatchedRandomRouter(
            opportunity_ids=tuple(map(str, ids)),
            expansion_rate=expansion_rate,
            seed=seed,
        )
    raise ValueError("CLARE is a policy baseline, not a controller route baseline")


def baseline_suite_spec(
    *,
    protocol_manifest_hash: str,
    curriculum_seeds: Sequence[int] = (20260825, 20260826, 20260827),
    adversarial_order_seed: int = 20260828,
) -> dict[str, Any]:
    """Return the pre-registered baseline matrix without opening final seal."""

    if len(protocol_manifest_hash) != 64:
        raise ValueError("protocol manifest SHA256 is required")
    seeds = tuple(int(value) for value in curriculum_seeds)
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise ValueError("headline baselines require exactly three random seeds")
    value: dict[str, Any] = {
        "schema_version": "baseline-suite-v1",
        "protocol_manifest_hash": protocol_manifest_hash,
        "headline_order_seeds": list(seeds),
        "adversarial_hard_to_easy_seed": int(adversarial_order_seed),
        "baselines": [
            {
                "id": f"fixed_budget_{budget}",
                "kind": BaselineKind.FIXED_BUDGET.value,
                "budget": budget,
                "priority": 1 if budget == 4 else 2,
            }
            for budget in (1, 2, 4, 8, 16, 32)
        ]
        + [
            {
                "id": "always_expansion_retain",
                "kind": BaselineKind.ALWAYS_EXPAND_RETAIN.value,
                "priority": 1,
                "headline_seeds": True,
            },
            {
                "id": "oracle_verifier",
                "kind": BaselineKind.ORACLE.value,
                "priority": 1,
                "headline_seeds": True,
            },
            {
                "id": "resteer_only",
                "kind": BaselineKind.RESTEER_ONLY.value,
                "priority": 2,
            },
            {
                "id": "verifier_no_lookup",
                "kind": BaselineKind.VERIFIER_NO_LOOKUP.value,
                "decision_rule": "head_argmax",
                "priority": 2,
            },
            {
                "id": "mode_count_gate",
                "kind": BaselineKind.MODE_COUNT_GATE.value,
                "minimum_modes": 2,
                "priority": 2,
            },
            {
                "id": "semantic_gate",
                "kind": BaselineKind.SEMANTIC_GATE.value,
                "minimum_score": 0.5,
                "priority": 2,
            },
            {
                "id": "geometry_gate",
                "kind": BaselineKind.GEOMETRY_GATE.value,
                "maximum_collision_risk": 0.5,
                "priority": 2,
            },
            {
                "id": "random_matched",
                "kind": BaselineKind.RANDOM_MATCHED.value,
                "rate_source": "full_system_development_opportunities",
                "seed": 20260825,
                "priority": 2,
            },
            {
                "id": "clare_minimal_faithful",
                "kind": BaselineKind.CLARE.value,
                "gamma": 2.5,
                "adapter_rank": 32,
                "discriminator_hidden_dim": 256,
                "discriminator_latent_dim": 128,
                "priority": 3,
            },
        ],
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    value["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return value


def freeze_baseline_suite(
    output_path: Path,
    *,
    protocol_manifest_hash: str,
    curriculum_seeds: Sequence[int] = (20260825, 20260826, 20260827),
    adversarial_order_seed: int = 20260828,
) -> dict[str, Any]:
    value = baseline_suite_spec(
        protocol_manifest_hash=protocol_manifest_hash,
        curriculum_seeds=curriculum_seeds,
        adversarial_order_seed=adversarial_order_seed,
    )
    output_path = Path(output_path)
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        if existing != value:
            raise ValueError("baseline manifest already exists with different contents")
        return existing
    atomic_write_json(output_path, value)
    return value


# ---------------------------------------------------------------------------
# CLARE: modular adapters, autoencoder discriminators, expansion, and routing.


@dataclass(frozen=True)
class ClareConfig:
    expandable_layers: tuple[str, ...]
    feature_dims: Mapping[str, int]
    adapter_rank: int = 32
    discriminator_hidden_dim: int = 256
    discriminator_latent_dim: int = 128
    gamma: float = 2.5
    min_std: float = 1e-6

    def __post_init__(self) -> None:
        if not self.expandable_layers or len(set(self.expandable_layers)) != len(
            self.expandable_layers
        ):
            raise ValueError("expandable_layers must be ordered and unique")
        if set(self.feature_dims) != set(self.expandable_layers):
            raise ValueError("feature_dims must exactly cover expandable_layers")
        if any(int(self.feature_dims[name]) <= 0 for name in self.expandable_layers):
            raise ValueError("feature dimensions must be positive")
        if min(
            self.adapter_rank,
            self.discriminator_hidden_dim,
            self.discriminator_latent_dim,
        ) <= 0:
            raise ValueError("CLARE module dimensions must be positive")
        if self.gamma < 0 or self.min_std <= 0:
            raise ValueError("invalid CLARE expansion statistics configuration")


class ClareAdapter(nn.Module):
    """Equation (2): W_up ReLU(W_down x), used as a parallel FFN branch."""

    def __init__(self, feature_dim: int, rank: int) -> None:
        super().__init__()
        self.down = nn.Linear(feature_dim, rank, bias=False)
        self.up = nn.Linear(rank, feature_dim, bias=False)

    def forward(self, features: Tensor) -> Tensor:
        dtype = features.dtype
        work = features.to(dtype=self.down.weight.dtype)
        return self.up(torch.relu(self.down(work))).to(dtype=dtype)


class ClareAutoencoder(nn.Module):
    """Lightweight task-distribution discriminator used only for routing."""

    def __init__(self, feature_dim: int, hidden_dim: int, latent_dim: int) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, feature_dim),
        )

    def forward(self, features: Tensor) -> Tensor:
        work = features.to(dtype=self.encoder[0].weight.dtype)
        return self.decoder(self.encoder(work))

    def reconstruction_error(self, features: Tensor) -> Tensor:
        reconstruction = self(features)
        return torch.linalg.vector_norm(
            features.to(dtype=reconstruction.dtype) - reconstruction, dim=-1
        )


@dataclass(frozen=True)
class ClareDiscriminatorStats:
    mean: float
    std: float
    count: int

    def __post_init__(self) -> None:
        if self.count <= 0 or not math.isfinite(self.mean) or not math.isfinite(self.std):
            raise ValueError("invalid discriminator statistics")
        if self.std <= 0:
            raise ValueError("discriminator standard deviation must be positive")


@dataclass(frozen=True)
class ClareLayerDecision:
    layer_name: str
    expand: bool
    linked_adapter_id: str | None
    z_scores: Mapping[str, float]
    mean_errors: Mapping[str, float]
    forced: bool = False


@dataclass(frozen=True)
class ClareStagePlan:
    stage_id: str
    layer_decisions: tuple[ClareLayerDecision, ...]

    @property
    def expanded_layers(self) -> tuple[str, ...]:
        return tuple(item.layer_name for item in self.layer_decisions if item.expand)


class ClareLayerBank(nn.Module):
    """Adapters, discriminators, and the paper's surjective D->A mapping."""

    def __init__(self, layer_name: str, feature_dim: int, config: ClareConfig) -> None:
        super().__init__()
        self.layer_name = str(layer_name)
        self.feature_dim = int(feature_dim)
        self.config = config
        self.adapters = nn.ModuleDict()
        self.discriminators = nn.ModuleDict()
        self.links: dict[str, str] = {}
        self.stats: dict[str, ClareDiscriminatorStats] = {}
        self._forced_adapter_id: str | None = None

    def add_adapter(self, adapter_id: str) -> ClareAdapter:
        if adapter_id in self.adapters:
            raise ValueError(f"duplicate adapter {adapter_id}")
        adapter = ClareAdapter(self.feature_dim, self.config.adapter_rank)
        self.adapters[adapter_id] = adapter
        return adapter

    def add_discriminator(
        self, discriminator_id: str, *, linked_adapter_id: str
    ) -> ClareAutoencoder:
        if discriminator_id in self.discriminators:
            raise ValueError(f"duplicate discriminator {discriminator_id}")
        if linked_adapter_id not in self.adapters:
            raise ValueError("discriminator link references an unknown adapter")
        discriminator = ClareAutoencoder(
            self.feature_dim,
            self.config.discriminator_hidden_dim,
            self.config.discriminator_latent_dim,
        )
        self.discriminators[discriminator_id] = discriminator
        self.links[discriminator_id] = linked_adapter_id
        return discriminator

    @torch.no_grad()
    def errors(self, features: Tensor) -> dict[str, Tensor]:
        self._validate_features(features)
        return {
            discriminator_id: discriminator.reconstruction_error(features)
            for discriminator_id, discriminator in self.discriminators.items()
        }

    @torch.no_grad()
    def expansion_statistics(
        self, features: Tensor
    ) -> tuple[dict[str, float], dict[str, float]]:
        errors = self.errors(features)
        if set(errors) != set(self.stats):
            missing = sorted(set(errors) - set(self.stats))
            raise RuntimeError(f"missing frozen discriminator stats: {missing}")
        z_scores = {}
        mean_errors = {}
        for discriminator_id, values in errors.items():
            mean_error = float(values.double().mean().item())
            stats = self.stats[discriminator_id]
            normalized = (values.double() - stats.mean) / max(
                stats.std, self.config.min_std
            )
            z_scores[discriminator_id] = float(normalized.mean().item())
            mean_errors[discriminator_id] = mean_error
        return z_scores, mean_errors

    @torch.no_grad()
    def finalize_discriminator(
        self, discriminator_id: str, training_features: Tensor
    ) -> ClareDiscriminatorStats:
        self._validate_features(training_features)
        if discriminator_id not in self.discriminators:
            raise KeyError(discriminator_id)
        values = self.discriminators[discriminator_id].reconstruction_error(
            training_features
        ).double()
        stats = ClareDiscriminatorStats(
            mean=float(values.mean().item()),
            std=max(float(values.std(unbiased=False).item()), self.config.min_std),
            count=int(values.numel()),
        )
        self.stats[discriminator_id] = stats
        return stats

    @torch.no_grad()
    def route(self, features: Tensor) -> tuple[str, ...]:
        """Equation (6): argmin discriminator error, then apply B_l."""

        self._validate_features(features)
        if not self.discriminators:
            raise RuntimeError("cannot route before the first CLARE stage")
        ids = tuple(self.discriminators.keys())
        stacked = torch.stack(
            [self.discriminators[name].reconstruction_error(features) for name in ids],
            dim=-1,
        )
        winners = stacked.argmin(dim=-1).reshape(-1).tolist()
        return tuple(self.links[ids[int(index)]] for index in winners)

    def apply_routed_adapter(self, features: Tensor) -> Tensor:
        self._validate_features(features)
        if self._forced_adapter_id is not None:
            if self._forced_adapter_id not in self.adapters:
                raise RuntimeError(
                    f"forced CLARE adapter is missing: {self._forced_adapter_id}"
                )
            return self.adapters[self._forced_adapter_id](features)
        original_shape = features.shape
        flat = features.reshape(-1, self.feature_dim)
        routed = self.route(flat)
        output = torch.empty_like(flat)
        for adapter_id in sorted(set(routed)):
            indices = [index for index, value in enumerate(routed) if value == adapter_id]
            index_tensor = torch.as_tensor(indices, device=flat.device, dtype=torch.long)
            output[index_tensor] = self.adapters[adapter_id](flat[index_tensor])
        return output.reshape(original_shape)

    def force_adapter(self, adapter_id: str | None) -> None:
        """Select one adapter during stage training; ``None`` restores routing."""

        if adapter_id is not None and adapter_id not in self.adapters:
            raise KeyError(f"unknown forced adapter {adapter_id}")
        self._forced_adapter_id = adapter_id

    def _validate_features(self, features: Tensor) -> None:
        if features.ndim < 2 or features.shape[-1] != self.feature_dim:
            raise ValueError(
                f"{self.layer_name} features must end in {self.feature_dim}, "
                f"got {tuple(features.shape)}"
            )
        if not bool(torch.isfinite(features).all()):
            raise ValueError("CLARE features contain non-finite values")


class ClareExpandableFFN(nn.Module):
    """Frozen square FFN plus the one adapter selected by its layer bank."""

    def __init__(self, frozen_ffn: nn.Module, bank: ClareLayerBank) -> None:
        super().__init__()
        self.frozen_ffn = frozen_ffn
        self.bank = bank
        for parameter in self.frozen_ffn.parameters():
            parameter.requires_grad_(False)

    def forward(self, features: Tensor, *args: Any, **kwargs: Any) -> Tensor:
        base = self.frozen_ffn(features, *args, **kwargs)
        if base.shape != features.shape:
            raise ValueError(
                "faithful CLARE side branch requires a square FFN input/output"
            )
        if not self.bank.adapters:
            return base
        return base + self.bank.apply_routed_adapter(features)


class ClareSystem(nn.Module):
    """Stage planner and task-ID-free router for all expandable FFN layers."""

    def __init__(self, config: ClareConfig) -> None:
        super().__init__()
        self.config = config
        self._layer_keys = {
            name: "layer_" + hashlib.sha256(name.encode()).hexdigest()[:16]
            for name in config.expandable_layers
        }
        if len(set(self._layer_keys.values())) != len(self._layer_keys):
            raise RuntimeError("CLARE layer module-key collision")
        self.layers = nn.ModuleDict(
            {
                self._layer_keys[name]: ClareLayerBank(
                    name, int(config.feature_dims[name]), config
                )
                for name in config.expandable_layers
            }
        )
        self.stage_ids: list[str] = []

    def layer_bank(self, layer_name: str) -> ClareLayerBank:
        try:
            return self.layers[self._layer_keys[layer_name]]
        except KeyError as error:
            raise KeyError(f"unknown expandable layer {layer_name}") from error

    @torch.no_grad()
    def plan_stage(
        self, stage_id: str, features_by_layer: Mapping[str, Tensor]
    ) -> ClareStagePlan:
        if not stage_id or stage_id in self.stage_ids:
            raise ValueError("stage_id must be new and non-empty")
        if set(features_by_layer) != set(self.config.expandable_layers):
            raise ValueError("stage features must exactly cover expandable layers")
        decisions = []
        first_stage = not self.stage_ids
        for layer_name in self.config.expandable_layers:
            bank = self.layer_bank(layer_name)
            features = features_by_layer[layer_name]
            bank._validate_features(features)
            if first_stage:
                decisions.append(
                    ClareLayerDecision(layer_name, True, None, {}, {})
                )
                continue
            z_scores, mean_errors = bank.expansion_statistics(features)
            expand = all(value > self.config.gamma for value in z_scores.values())
            nearest_discriminator = min(
                mean_errors, key=lambda key: (mean_errors[key], key)
            )
            decisions.append(
                ClareLayerDecision(
                    layer_name=layer_name,
                    expand=expand,
                    linked_adapter_id=(
                        None if expand else bank.links[nearest_discriminator]
                    ),
                    z_scores=z_scores,
                    mean_errors=mean_errors,
                )
            )
        if not any(item.expand for item in decisions):
            shallowest = self.config.expandable_layers[0]
            decisions = [
                ClareLayerDecision(
                    layer_name=item.layer_name,
                    expand=item.layer_name == shallowest,
                    linked_adapter_id=(
                        None if item.layer_name == shallowest else item.linked_adapter_id
                    ),
                    z_scores=item.z_scores,
                    mean_errors=item.mean_errors,
                    forced=item.layer_name == shallowest,
                )
                for item in decisions
            ]
        return ClareStagePlan(stage_id=stage_id, layer_decisions=tuple(decisions))

    def apply_stage_plan(self, plan: ClareStagePlan) -> dict[str, dict[str, str]]:
        if plan.stage_id in self.stage_ids:
            raise ValueError("stage plan was already applied")
        if tuple(item.layer_name for item in plan.layer_decisions) != tuple(
            self.config.expandable_layers
        ):
            raise ValueError("stage plan layer order does not match CLARE config")
        created: dict[str, dict[str, str]] = {}
        for decision in plan.layer_decisions:
            bank = self.layer_bank(decision.layer_name)
            discriminator_id = f"disc::{plan.stage_id}"
            if decision.expand:
                adapter_id = f"adapter::{plan.stage_id}"
                bank.add_adapter(adapter_id)
            else:
                adapter_id = str(decision.linked_adapter_id)
            bank.add_discriminator(
                discriminator_id, linked_adapter_id=adapter_id
            )
            created[decision.layer_name] = {
                "adapter_id": adapter_id,
                "discriminator_id": discriminator_id,
                "adapter_created": str(decision.expand).lower(),
            }
        self.stage_ids.append(plan.stage_id)
        return created

    def trainable_adapter_parameters(self, stage_id: str) -> tuple[nn.Parameter, ...]:
        parameters = []
        adapter_id = f"adapter::{stage_id}"
        for bank in self.layers.values():
            for name, adapter in bank.adapters.items():
                trainable = name == adapter_id
                for parameter in adapter.parameters():
                    parameter.requires_grad_(trainable)
                    if trainable:
                        parameters.append(parameter)
            for discriminator in bank.discriminators.values():
                for parameter in discriminator.parameters():
                    parameter.requires_grad_(False)
        return tuple(parameters)

    def trainable_discriminator_parameters(
        self, stage_id: str
    ) -> tuple[nn.Parameter, ...]:
        parameters = []
        discriminator_id = f"disc::{stage_id}"
        for bank in self.layers.values():
            for adapter in bank.adapters.values():
                for parameter in adapter.parameters():
                    parameter.requires_grad_(False)
            for name, discriminator in bank.discriminators.items():
                trainable = name == discriminator_id
                for parameter in discriminator.parameters():
                    parameter.requires_grad_(trainable)
                    if trainable:
                        parameters.append(parameter)
        return tuple(parameters)

    def finalize_stage_statistics(
        self, stage_id: str, features_by_layer: Mapping[str, Tensor]
    ) -> dict[str, ClareDiscriminatorStats]:
        discriminator_id = f"disc::{stage_id}"
        return {
            layer_name: self.layer_bank(layer_name).finalize_discriminator(
                discriminator_id, features_by_layer[layer_name]
            )
            for layer_name in self.config.expandable_layers
        }

    def manifest(self) -> dict[str, Any]:
        layers = {}
        for layer_name in self.config.expandable_layers:
            bank = self.layer_bank(layer_name)
            layers[layer_name] = {
                "feature_dim": bank.feature_dim,
                "adapters": sorted(bank.adapters.keys()),
                "discriminators": sorted(bank.discriminators.keys()),
                "links": dict(sorted(bank.links.items())),
                "stats": {
                    name: asdict(value) for name, value in sorted(bank.stats.items())
                },
            }
        value = {
            "schema_version": "clare-baseline-v1",
            "paper_contract": {
                "adapter": "W_up(ReLU(W_down(x)))",
                "routing": "argmin_autoencoder_reconstruction_error",
                "expansion": "all_previous_discriminator_z_scores_gt_gamma",
                "force_shallowest_if_no_expansion": True,
                "task_id_required_at_inference": False,
            },
            "config": {
                "expandable_layers": list(self.config.expandable_layers),
                "feature_dims": dict(self.config.feature_dims),
                "adapter_rank": self.config.adapter_rank,
                "discriminator_hidden_dim": self.config.discriminator_hidden_dim,
                "discriminator_latent_dim": self.config.discriminator_latent_dim,
                "gamma": self.config.gamma,
                "min_std": self.config.min_std,
            },
            "stage_ids": list(self.stage_ids),
            "layers": layers,
        }
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        value["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
        return value


def train_clare_discriminator(
    discriminator: ClareAutoencoder,
    features: Tensor,
    *,
    steps: int = 2_000,
    batch_size: int = 32,
    learning_rate: float = 5e-4,
    seed: int = 20260825,
) -> tuple[float, ...]:
    """Paper-ordered second-stage discriminator training utility."""

    if features.ndim != 2 or len(features) == 0:
        raise ValueError("discriminator features must be a non-empty matrix")
    if min(steps, batch_size) <= 0 or learning_rate <= 0:
        raise ValueError("invalid discriminator training configuration")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    optimizer = torch.optim.Adam(discriminator.parameters(), lr=learning_rate)
    losses = []
    discriminator.train()
    for _ in range(steps):
        indices = torch.randint(
            len(features), (batch_size,), generator=generator, device="cpu"
        ).to(features.device)
        batch = features.index_select(0, indices)
        loss = discriminator.reconstruction_error(batch).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    return tuple(losses)


__all__ = [
    "AlwaysExpandRetainRouter",
    "BaselineDecision",
    "BaselineKind",
    "BaselineOpportunity",
    "BaselineRouter",
    "ClareAdapter",
    "ClareAutoencoder",
    "ClareConfig",
    "ClareDiscriminatorStats",
    "ClareExpandableFFN",
    "ClareLayerBank",
    "ClareLayerDecision",
    "ClareStagePlan",
    "ClareSystem",
    "FixedBudgetRouter",
    "GeometryGateRouter",
    "MatchedRandomRouter",
    "ModeCountGateRouter",
    "OracleRouter",
    "ResteerOnlyRouter",
    "SemanticGateRouter",
    "VerifierNoLookupRouter",
    "baseline_suite_spec",
    "build_baseline_router",
    "freeze_baseline_suite",
    "train_clare_discriminator",
]
