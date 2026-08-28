"""Frozen-backbone Deep Sets verifier and calibration utilities."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

from .features import ModeFeatureEncoderV1
from .types import ControllerRoute, GeometryEvidence, RoundEvidence, SemanticModeScore


SCENE_DIMS = 2048
MODE_EE_DIMS = 20
MODE_EMBED_DIMS = 37
POOLED_MODE_DIMS = 74
GLOBAL_DIMS = 7
VERIFIER_INPUT_DIMS = SCENE_DIMS + POOLED_MODE_DIMS + GLOBAL_DIMS
VERIFIER_CLASSES = (ControllerRoute.RESTEER, ControllerRoute.EXPAND)


@dataclass(frozen=True)
class ModeVerifierInput:
    scene_feature: np.ndarray
    mode_ee_features: np.ndarray
    geometry_features: np.ndarray
    semantic_features: np.ndarray
    mode_weights: np.ndarray
    global_features: np.ndarray
    scene_missing: bool = False
    # Columns: EE, geometry, semantic, weight.
    mode_missing: np.ndarray | None = None
    global_missing: np.ndarray | None = None
    mode_weight_features: np.ndarray | None = None

    def __post_init__(self) -> None:
        scene = np.asarray(self.scene_feature, dtype=np.float32)
        ee = np.asarray(self.mode_ee_features, dtype=np.float32)
        geometry = np.asarray(self.geometry_features, dtype=np.float32)
        semantic = np.asarray(self.semantic_features, dtype=np.float32)
        weights = np.asarray(self.mode_weights, dtype=np.float32)
        global_features = np.asarray(self.global_features, dtype=np.float32)
        if scene.shape != (SCENE_DIMS,):
            raise ValueError(f"scene_feature must have shape ({SCENE_DIMS},)")
        if ee.ndim != 2 or ee.shape[1] != MODE_EE_DIMS or not 1 <= len(ee) <= 4:
            raise ValueError("mode_ee_features must have shape (K, 20), K in [1, 4]")
        count = len(ee)
        if geometry.shape != (count, 3) or semantic.shape != (count, 1):
            raise ValueError("geometry/semantic feature shapes do not match K")
        if weights.shape != (count,) or np.any(weights < 0) or float(weights.sum()) <= 0:
            raise ValueError("mode_weights must be a positive simplex vector")
        weights = weights / weights.sum()
        if global_features.shape != (GLOBAL_DIMS,):
            raise ValueError("global_features must have shape (7,)")
        mode_missing = (
            np.zeros((count, 4), dtype=bool)
            if self.mode_missing is None
            else np.asarray(self.mode_missing, dtype=bool)
        )
        global_missing = (
            np.zeros(GLOBAL_DIMS, dtype=bool)
            if self.global_missing is None
            else np.asarray(self.global_missing, dtype=bool)
        )
        weight_features = (
            weights[:, None]
            if self.mode_weight_features is None
            else np.asarray(self.mode_weight_features, dtype=np.float32)
        )
        if mode_missing.shape != (count, 4):
            raise ValueError("mode_missing must have shape (K, 4)")
        if global_missing.shape != (GLOBAL_DIMS,):
            raise ValueError("global_missing must have shape (7,)")
        if weight_features.shape != (count, 1):
            raise ValueError("mode_weight_features must have shape (K, 1)")
        for value in (scene, ee, geometry, semantic, weights, global_features, weight_features):
            if not np.isfinite(value).all():
                raise ValueError("verifier input contains non-finite values")
        object.__setattr__(self, "scene_feature", scene)
        object.__setattr__(self, "mode_ee_features", ee)
        object.__setattr__(self, "geometry_features", geometry)
        object.__setattr__(self, "semantic_features", semantic)
        object.__setattr__(self, "mode_weights", weights)
        object.__setattr__(self, "global_features", global_features)
        object.__setattr__(self, "mode_missing", mode_missing)
        object.__setattr__(self, "global_missing", global_missing)
        object.__setattr__(self, "mode_weight_features", weight_features)


def ablate_verifier_input(
    item: ModeVerifierInput, channel_set: str
) -> ModeVerifierInput:
    """Apply the exact channel contract used by an ablation artifact.

    Missing channels are represented through the model's learned missing-value
    embeddings.  The same transformation is used during fitting and deployed
    inference so an ablation can never silently consume channels it did not
    train on.
    """

    if channel_set == "full":
        return item
    if channel_set == "modes_only":
        return ModeVerifierInput(**{**item.__dict__, "scene_missing": True})
    if channel_set == "scene_only":
        return ModeVerifierInput(
            **{
                **item.__dict__,
                "mode_missing": np.ones_like(item.mode_missing, dtype=bool),
                "global_missing": np.ones_like(item.global_missing, dtype=bool),
            }
        )
    raise ValueError(f"unknown verifier channel set: {channel_set!r}")


class GroundedCapabilityVerifier(nn.Module):
    """2129-D two-class head; scene extraction is external and permanently frozen."""

    def __init__(self) -> None:
        super().__init__()
        self.ee_mlp = nn.Sequential(
            nn.Linear(MODE_EE_DIMS, 32),
            nn.ReLU(),
        )
        self.ee_missing = nn.Parameter(torch.zeros(32))
        self.geometry_missing = nn.Parameter(torch.zeros(3))
        self.semantic_missing = nn.Parameter(torch.zeros(1))
        self.weight_missing = nn.Parameter(torch.zeros(1))
        self.scene_missing = nn.Parameter(torch.zeros(SCENE_DIMS))
        self.global_missing = nn.Parameter(torch.zeros(GLOBAL_DIMS))
        self.head = nn.Sequential(
            nn.Linear(VERIFIER_INPUT_DIMS, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Linear(64, len(VERIFIER_CLASSES)),
        )

    def encode_one(self, item: ModeVerifierInput, *, device: torch.device | None = None) -> Tensor:
        if device is None:
            device = next(self.parameters()).device
        scene = torch.as_tensor(item.scene_feature, device=device)
        if item.scene_missing:
            scene = self.scene_missing
        ee = torch.as_tensor(item.mode_ee_features, device=device)
        geometry = torch.as_tensor(item.geometry_features, device=device)
        semantic = torch.as_tensor(item.semantic_features, device=device)
        weight_feature = torch.as_tensor(item.mode_weight_features, device=device)
        missing = torch.as_tensor(item.mode_missing, device=device)
        ee_embedded = self.ee_mlp(ee)
        ee_embedded = torch.where(missing[:, 0:1], self.ee_missing[None, :], ee_embedded)
        geometry = torch.where(
            missing[:, 1:2], self.geometry_missing[None, :], geometry
        )
        semantic = torch.where(
            missing[:, 2:3], self.semantic_missing[None, :], semantic
        )
        weight_feature = torch.where(
            missing[:, 3:4], self.weight_missing[None, :], weight_feature
        )
        per_mode = torch.cat([ee_embedded, geometry, semantic, weight_feature], dim=1)
        if per_mode.shape[1] != MODE_EMBED_DIMS:
            raise RuntimeError("per-mode verifier embedding must be 37-D")
        pool_weights = torch.as_tensor(item.mode_weights, device=device)
        weighted_mean = (pool_weights[:, None] * per_mode).sum(dim=0)
        elementwise_max = per_mode.max(dim=0).values
        pooled = torch.cat([weighted_mean, elementwise_max], dim=0)
        global_features = torch.as_tensor(item.global_features, device=device)
        global_missing = torch.as_tensor(item.global_missing, device=device)
        global_features = torch.where(
            global_missing, self.global_missing, global_features
        )
        encoded = torch.cat([scene, pooled, global_features], dim=0)
        if encoded.shape != (VERIFIER_INPUT_DIMS,):
            raise RuntimeError(
                f"verifier input must be {VERIFIER_INPUT_DIMS}-D, got {tuple(encoded.shape)}"
            )
        return encoded

    def forward(self, items: ModeVerifierInput | Sequence[ModeVerifierInput]) -> Tensor:
        if isinstance(items, ModeVerifierInput):
            items = (items,)
        encoded = torch.stack([self.encode_one(item) for item in items], dim=0)
        return self.head(encoded)


def build_verifier_input(
    *,
    scene_feature: np.ndarray,
    evidence: RoundEvidence,
    geometry: Sequence[GeometryEvidence],
    semantics: Sequence[SemanticModeScore],
    failure_count: int,
    remaining_budget: int,
    ess_ratio: float,
    unique_ratio: float,
) -> ModeVerifierInput:
    mode_ids = [mode.mode_id for mode in evidence.modes]
    geometry_by_id = {item.mode_id: item for item in geometry}
    semantic_by_id = {item.mode_id: item for item in semantics}
    if set(geometry_by_id) != set(mode_ids) or set(semantic_by_id) != set(mode_ids):
        raise ValueError("verifier channels must cover every mode")
    all_features = ModeFeatureEncoderV1().encode(evidence.trajectories)
    medoid_features = np.stack(
        [
            all_features[int(mode.representative_indices["medoid"])]
            for mode in evidence.modes
        ]
    )
    geometry_features = np.asarray(
        [
            [
                geometry_by_id[mode_id].collision_risk,
                geometry_by_id[mode_id].reachability,
                geometry_by_id[mode_id].grasp_plausibility,
            ]
            for mode_id in mode_ids
        ],
        dtype=np.float32,
    )
    semantic_features = np.asarray(
        [[semantic_by_id[mode_id].semantic_score] for mode_id in mode_ids],
        dtype=np.float32,
    )
    weights = np.asarray([mode.weight for mode in evidence.modes], dtype=np.float32)
    weights /= weights.sum()
    entropy = float(-(weights * np.log(np.clip(weights, 1e-12, 1.0))).sum())
    globals_ = np.asarray(
        [
            min(4, max(0, failure_count)) / 4.0,
            min(4, max(0, remaining_budget)) / 4.0,
            len(mode_ids) / 4.0,
            float(weights.max()),
            entropy / math.log(4.0),
            float(np.clip(ess_ratio, 0.0, 1.0)),
            float(np.clip(unique_ratio, 0.0, 1.0)),
        ],
        dtype=np.float32,
    )
    return ModeVerifierInput(
        scene_feature=scene_feature,
        mode_ee_features=medoid_features,
        geometry_features=geometry_features,
        semantic_features=semantic_features,
        mode_weights=weights,
        global_features=globals_,
    )


class FeatureStandardizer:
    """Train-split-only channel normalizer with a serializable contract."""

    _channels = (
        "scene_feature",
        "mode_ee_features",
        "geometry_features",
        "semantic_features",
        "mode_weight_features",
        "global_features",
    )

    def __init__(self, statistics: dict[str, tuple[np.ndarray, np.ndarray]]) -> None:
        self.statistics = statistics

    @classmethod
    def fit(cls, items: Sequence[ModeVerifierInput]) -> "FeatureStandardizer":
        if not items:
            raise ValueError("cannot fit standardizer on an empty train split")
        values_and_missing = {
            "scene_feature": (
                np.stack([item.scene_feature for item in items]),
                np.stack(
                    [
                        np.full(SCENE_DIMS, item.scene_missing, dtype=bool)
                        for item in items
                    ]
                ),
            ),
            "mode_ee_features": (
                np.concatenate([item.mode_ee_features for item in items]),
                np.concatenate(
                    [
                        np.broadcast_to(
                            item.mode_missing[:, 0:1], item.mode_ee_features.shape
                        )
                        for item in items
                    ]
                ),
            ),
            "geometry_features": (
                np.concatenate([item.geometry_features for item in items]),
                np.concatenate(
                    [
                        np.broadcast_to(
                            item.mode_missing[:, 1:2], item.geometry_features.shape
                        )
                        for item in items
                    ]
                ),
            ),
            "semantic_features": (
                np.concatenate([item.semantic_features for item in items]),
                np.concatenate(
                    [
                        np.broadcast_to(
                            item.mode_missing[:, 2:3], item.semantic_features.shape
                        )
                        for item in items
                    ]
                ),
            ),
            "mode_weight_features": (
                np.concatenate([item.mode_weights[:, None] for item in items]),
                np.concatenate([item.mode_missing[:, 3:4] for item in items]),
            ),
            "global_features": (
                np.stack([item.global_features for item in items]),
                np.stack([item.global_missing for item in items]),
            ),
        }
        stats = {}
        for name, (array, missing) in values_and_missing.items():
            valid = ~missing
            count = valid.sum(axis=0)
            safe_count = np.maximum(count, 1)
            mean = ((array * valid).sum(axis=0) / safe_count).astype(np.float32)
            centered = np.where(valid, array - mean, 0.0)
            scale = np.sqrt((centered * centered).sum(axis=0) / safe_count).astype(
                np.float32
            )
            mean[count == 0] = 0.0
            scale[scale < 1e-6] = 1.0
            stats[name] = (mean, scale)
        return cls(stats)

    def transform(self, item: ModeVerifierInput) -> ModeVerifierInput:
        def norm(name: str, value: np.ndarray) -> np.ndarray:
            mean, scale = self.statistics[name]
            return (value - mean) / scale

        return ModeVerifierInput(
            scene_feature=norm("scene_feature", item.scene_feature),
            mode_ee_features=norm("mode_ee_features", item.mode_ee_features),
            geometry_features=norm("geometry_features", item.geometry_features),
            semantic_features=norm("semantic_features", item.semantic_features),
            mode_weights=item.mode_weights,
            mode_weight_features=norm(
                "mode_weight_features", item.mode_weights[:, None]
            ),
            global_features=norm("global_features", item.global_features),
            scene_missing=item.scene_missing,
            mode_missing=item.mode_missing,
            global_missing=item.global_missing,
        )

    def to_json(self) -> dict[str, dict[str, list[float]]]:
        return {
            name: {"mean": mean.tolist(), "scale": scale.tolist()}
            for name, (mean, scale) in self.statistics.items()
        }

    @classmethod
    def from_json(cls, value: dict[str, dict[str, list[float]]]) -> "FeatureStandardizer":
        return cls(
            {
                name: (
                    np.asarray(item["mean"], dtype=np.float32),
                    np.asarray(item["scale"], dtype=np.float32),
                )
                for name, item in value.items()
            }
        )


def save_verifier_input(
    path: Path,
    item: ModeVerifierInput,
    *,
    metadata: dict | None = None,
) -> Path:
    """Atomically persist all pre-decision channels before logging a route."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            scene_feature=item.scene_feature.astype(np.float16),
            mode_ee_features=item.mode_ee_features.astype(np.float16),
            geometry_features=item.geometry_features.astype(np.float16),
            semantic_features=item.semantic_features.astype(np.float16),
            mode_weights=item.mode_weights.astype(np.float32),
            mode_weight_features=item.mode_weight_features.astype(np.float16),
            global_features=item.global_features.astype(np.float32),
            scene_missing=np.asarray([item.scene_missing], dtype=bool),
            mode_missing=item.mode_missing.astype(bool),
            global_missing=item.global_missing.astype(bool),
        )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    metadata_path = path.with_suffix(".json")
    metadata_tmp = metadata_path.parent / f".{metadata_path.name}.{os.getpid()}.tmp"
    metadata_tmp.write_text(
        json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(metadata_tmp, metadata_path)
    return path


def load_verifier_input(path: Path) -> ModeVerifierInput:
    with np.load(Path(path), allow_pickle=False) as data:
        return ModeVerifierInput(
            scene_feature=data["scene_feature"].astype(np.float32),
            mode_ee_features=data["mode_ee_features"].astype(np.float32),
            geometry_features=data["geometry_features"].astype(np.float32),
            semantic_features=data["semantic_features"].astype(np.float32),
            mode_weights=data["mode_weights"].astype(np.float32),
            mode_weight_features=data["mode_weight_features"].astype(np.float32),
            global_features=data["global_features"].astype(np.float32),
            scene_missing=bool(data["scene_missing"][0]),
            mode_missing=data["mode_missing"].astype(bool),
            global_missing=data["global_missing"].astype(bool),
        )


def binomial_cross_entropy(
    logits: Tensor,
    *,
    successes: Tensor,
    trials: Tensor,
    context_weights: Tensor | None = None,
) -> Tensor:
    """Soft two-class cross entropy from aggregate retry outcomes.

    Class 0 is RE-STEER and class 1 is EXPANSION.  The aggregate branch
    outcomes remain a soft target distribution, while deployed routing is the
    output head's direct argmax and never a hand-set probability threshold.
    """

    if torch.any(trials <= 0) or torch.any(successes < 0) or torch.any(successes > trials):
        raise ValueError("invalid binomial counts")
    if logits.ndim != 2 or logits.shape[1] != len(VERIFIER_CLASSES):
        raise ValueError("verifier logits must have shape (N, 2)")
    p_resteer = successes.to(logits.dtype) / trials.to(logits.dtype)
    targets = torch.stack([p_resteer, 1.0 - p_resteer], dim=-1)
    losses = -(targets * F.log_softmax(logits, dim=-1)).sum(dim=-1)
    if context_weights is not None:
        weights = context_weights.to(losses.dtype)
        return (losses * weights).sum() / weights.sum().clamp_min(1e-12)
    return losses.mean()


@dataclass(frozen=True)
class PlattCalibrator:
    slope: float
    intercept: float

    @classmethod
    def fit(cls, logits: np.ndarray, labels: np.ndarray) -> "PlattCalibrator":
        from sklearn.linear_model import LogisticRegression

        logits = np.asarray(logits, dtype=np.float64).reshape(-1, 1)
        labels = np.asarray(labels, dtype=np.int64)
        if len(logits) != len(labels) or set(np.unique(labels)) != {0, 1}:
            raise ValueError("Platt calibration requires aligned natural binary labels")
        model = LogisticRegression(C=1e6, solver="lbfgs")
        model.fit(logits, labels)
        return cls(float(model.coef_[0, 0]), float(model.intercept_[0]))

    @classmethod
    def fit_binomial(
        cls,
        logits: np.ndarray,
        *,
        failures: np.ndarray,
        trials: np.ndarray,
        max_iter: int = 100,
    ) -> "PlattCalibrator":
        """Fit Platt scaling to natural aggregate Bernoulli outcomes.

        Each row remains one decision context; ``failures/trials`` is never
        collapsed to an "any success" hard label.  Newton updates operate on
        the exact aggregate binomial likelihood.
        """

        x = np.asarray(logits, dtype=np.float64).reshape(-1)
        failures = np.asarray(failures, dtype=np.float64).reshape(-1)
        trials = np.asarray(trials, dtype=np.float64).reshape(-1)
        if not (len(x) == len(failures) == len(trials)) or len(x) == 0:
            raise ValueError("binomial Platt inputs must be non-empty aligned vectors")
        if (
            np.any(~np.isfinite(x))
            or np.any(trials <= 0)
            or np.any(failures < 0)
            or np.any(failures > trials)
        ):
            raise ValueError("invalid binomial Platt inputs")
        if failures.sum() <= 0 or (trials - failures).sum() <= 0:
            raise ValueError("binomial Platt calibration requires both outcomes")
        design = np.stack([x, np.ones_like(x)], axis=1)
        parameters = np.asarray([1.0, 0.0], dtype=np.float64)
        ridge = np.diag([1e-8, 1e-8])
        for _ in range(max_iter):
            linear = np.clip(design @ parameters, -50.0, 50.0)
            probability = 1.0 / (1.0 + np.exp(-linear))
            gradient = design.T @ (trials * probability - failures)
            curvature = trials * probability * (1.0 - probability)
            hessian = design.T @ (curvature[:, None] * design) + ridge
            step = np.linalg.solve(hessian, gradient)
            parameters -= step
            if float(np.max(np.abs(step))) < 1e-8:
                break
        if not np.isfinite(parameters).all():
            raise RuntimeError("binomial Platt calibration did not converge")
        return cls(float(parameters[0]), float(parameters[1]))

    def predict(self, logits: np.ndarray | float) -> np.ndarray:
        value = self.slope * np.asarray(logits, dtype=np.float64) + self.intercept
        return 1.0 / (1.0 + np.exp(-np.clip(value, -50.0, 50.0)))


def expected_calibration_error(
    probabilities: np.ndarray,
    labels: np.ndarray,
    *,
    bins: int = 15,
) -> float:
    probabilities = np.asarray(probabilities, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    if probabilities.shape != labels.shape or probabilities.ndim != 1:
        raise ValueError("probabilities and labels must be aligned vectors")
    order = np.argsort(probabilities, kind="stable")
    groups = np.array_split(order, min(bins, len(order)))
    total = max(1, len(order))
    return float(
        sum(
            len(group)
            / total
            * abs(float(probabilities[group].mean() - labels[group].mean()))
            for group in groups
            if len(group)
        )
    )


def save_verifier_artifact(
    root: Path,
    *,
    model: GroundedCapabilityVerifier,
    standardizer: FeatureStandardizer,
    calibrator: PlattCalibrator,
    metadata: dict,
) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / f".head.{os.getpid()}.tmp"
    torch.save(model.state_dict(), temporary)
    os.replace(temporary, root / "head.pt")
    manifest = {
        "schema_version": "grounded-capability-verifier-v2",
        "input_dims": VERIFIER_INPUT_DIMS,
        "output_classes": [route.value for route in VERIFIER_CLASSES],
        "decision_rule": "head_argmax",
        "normalizer": standardizer.to_json(),
        "calibrator": {
            "slope": calibrator.slope,
            "intercept": calibrator.intercept,
        },
        "metadata": metadata,
    }
    temporary_json = root / f".manifest.{os.getpid()}.tmp"
    temporary_json.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary_json, root / "manifest.json")


@dataclass(frozen=True)
class VerifierPrediction:
    route: ControllerRoute
    logits: tuple[float, float]
    p_expansion: float


class DeployedVerifierPredictor:
    def __init__(self, artifact_root: Path, *, device: str = "cpu") -> None:
        self.artifact_root = Path(artifact_root)
        manifest = json.loads(
            (self.artifact_root / "manifest.json").read_text(encoding="utf-8")
        )
        if manifest.get("schema_version") != "grounded-capability-verifier-v2":
            raise ValueError("unsupported verifier artifact schema")
        if int(manifest.get("input_dims", -1)) != VERIFIER_INPUT_DIMS:
            raise ValueError("verifier artifact input dimension mismatch")
        if tuple(manifest.get("output_classes", ())) != tuple(
            route.value for route in VERIFIER_CLASSES
        ):
            raise ValueError("verifier artifact class order mismatch")
        if manifest.get("decision_rule") != "head_argmax":
            raise ValueError("verifier artifact must use direct head argmax")
        self.model = GroundedCapabilityVerifier().to(device)
        state = torch.load(
            self.artifact_root / "head.pt", map_location=device, weights_only=True
        )
        self.model.load_state_dict(state, strict=True)
        self.model.eval()
        self.standardizer = FeatureStandardizer.from_json(manifest["normalizer"])
        self.calibrator = PlattCalibrator(
            float(manifest["calibrator"]["slope"]),
            float(manifest["calibrator"]["intercept"]),
        )
        self.metadata = manifest.get("metadata", {})

        training_config = self.metadata.get("training_config", {})
        self.channel_set = str(training_config.get("channel_set", "full"))
        if self.channel_set not in {"full", "scene_only", "modes_only"}:
            raise ValueError(
                f"unsupported verifier artifact channel set {self.channel_set!r}"
            )

    def predict_logits(self, item: ModeVerifierInput) -> np.ndarray:
        item = ablate_verifier_input(item, self.channel_set)
        normalized = self.standardizer.transform(item)
        with torch.inference_mode():
            logits = self.model(normalized)[0].detach().cpu().numpy()
        return np.asarray(logits, dtype=np.float64)

    def predict_logit_margin(self, item: ModeVerifierInput) -> float:
        logits = self.predict_logits(item)
        return float(logits[1] - logits[0])

    def predict_probability(self, item: ModeVerifierInput) -> float:
        """Diagnostic calibrated probability; never used to choose the route."""

        return float(self.calibrator.predict(self.predict_logit_margin(item)))

    def predict(self, item: ModeVerifierInput) -> VerifierPrediction:
        logits = self.predict_logits(item)
        route = VERIFIER_CLASSES[int(np.argmax(logits))]
        margin = float(logits[1] - logits[0])
        return VerifierPrediction(
            route=route,
            logits=(float(logits[0]), float(logits[1])),
            p_expansion=float(self.calibrator.predict(margin)),
        )

    def predict_probabilities(self, items: Sequence[ModeVerifierInput]) -> np.ndarray:
        return np.asarray(
            [self.predict_probability(item) for item in items], dtype=np.float64
        )

    def predict_routes(self, items: Sequence[ModeVerifierInput]) -> tuple[ControllerRoute, ...]:
        return tuple(self.predict(item).route for item in items)


__all__ = [
    "FeatureStandardizer",
    "DeployedVerifierPredictor",
    "GroundedCapabilityVerifier",
    "ModeVerifierInput",
    "PlattCalibrator",
    "VerifierPrediction",
    "VERIFIER_CLASSES",
    "VERIFIER_INPUT_DIMS",
    "ablate_verifier_input",
    "binomial_cross_entropy",
    "build_verifier_input",
    "expected_calibration_error",
    "load_verifier_input",
    "save_verifier_input",
    "save_verifier_artifact",
]
