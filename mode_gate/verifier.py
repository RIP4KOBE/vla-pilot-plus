"""Decision-time-only candidate verifier. No trainable policy/backbone is owned here."""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
from typing import Sequence
import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F
from .types import ControllerRoute, RoundEvidence
from .experiment_contract import FIXED_BUDGET_50_LABEL_VERSION, require_fixed_budget_50_contract
from .io_utils import atomic_write_json, sha256_file

SCENE_DIMS = 2048
TRAJECTORY_DIMS = 15  # recorded action(7), predicted/observed xyz(3), xyzw(4), gripper(1)
HISTORY_DIMS = 15
VERIFIER_INPUT_DIMS = 128 + 128 + 64 + 2
VERIFIER_CLASSES = (ControllerRoute.RESTEER, ControllerRoute.EXPAND)
VERIFIER_HEAD_ARCHITECTURE = "all-candidate-gru-deepset-history-two-logits-v3"
VERIFIER_FEATURE_SCHEMA = "candidate-verifier-input-v3"

@dataclass(frozen=True)
class CandidateVerifierInput:
    scene_feature: np.ndarray
    candidate_trajectories: np.ndarray
    executed_history: np.ndarray
    remaining_budget: int
    retry_budget: int = 50
    candidate_ids: tuple[str, ...] = ()
    context_id: str = ""
    backbone_id: str = ""
    decision_step: int = 0

    def __post_init__(self) -> None:
        scene = np.asarray(self.scene_feature, dtype=np.float32)
        paths = np.asarray(self.candidate_trajectories, dtype=np.float32)
        history = np.asarray(self.executed_history, dtype=np.float32)
        if scene.shape != (SCENE_DIMS,):
            raise ValueError("scene feature must be the frozen v44 2048-D joint image/instruction feature")
        if paths.ndim != 3 or min(paths.shape[:2]) < 1 or paths.shape[-1] != TRAJECTORY_DIMS:
            raise ValueError("all candidate sequences must have shape (N,T,15), with no truncation of N or T")
        if history.ndim != 2 or history.shape[-1] != HISTORY_DIMS:
            raise ValueError("executed history must have shape (steps,15)")
        if not all(np.isfinite(x).all() for x in (scene, paths, history)):
            raise ValueError("non-finite verifier input")
        if self.retry_budget <= 0 or not 0 <= self.remaining_budget <= self.retry_budget:
            raise ValueError("invalid remaining budget")
        if self.decision_step < len(history):
            raise ValueError("history cannot contain steps later than the decision")
        ids = self.candidate_ids or tuple(f"candidate-{i}" for i in range(len(paths)))
        if len(ids) != len(paths) or len(set(ids)) != len(ids):
            raise ValueError("candidate IDs must preserve all samples exactly once")
        object.__setattr__(self, "scene_feature", scene)
        object.__setattr__(self, "candidate_trajectories", paths)
        object.__setattr__(self, "executed_history", history)
        object.__setattr__(self, "candidate_ids", tuple(ids))

class GroundedCapabilityVerifier(nn.Module):
    """Train the small trajectory/history encoders and head; never the v44 VLM."""
    def __init__(self) -> None:
        super().__init__()
        self.scene_projection = nn.Sequential(nn.LayerNorm(SCENE_DIMS), nn.Linear(SCENE_DIMS, 128), nn.GELU())
        self.trajectory_encoder = nn.GRU(TRAJECTORY_DIMS, 64, batch_first=True)
        self.history_encoder = nn.GRU(HISTORY_DIMS, 64, batch_first=True)
        self.empty_history = nn.Parameter(torch.zeros(64))
        self.head = nn.Sequential(nn.LayerNorm(VERIFIER_INPUT_DIMS),
                                  nn.Linear(VERIFIER_INPUT_DIMS, 128), nn.GELU(),
                                  nn.Linear(128, 2))

    def encode_one(self, item: CandidateVerifierInput, *, device=None) -> Tensor:
        device = device or next(self.parameters()).device
        # Every sequence and every time point participates in this shared trainable encoder.
        paths = torch.as_tensor(item.candidate_trajectories, device=device)
        _, states = self.trajectory_encoder(paths)
        all_candidates = states[-1]
        pooled = torch.cat((all_candidates.mean(0), all_candidates.amax(0)))
        scene = self.scene_projection(torch.as_tensor(item.scene_feature, device=device).detach())
        if len(item.executed_history):
            _, history_state = self.history_encoder(torch.as_tensor(item.executed_history, device=device)[None])
            history = history_state[-1, 0]
        else:
            history = self.empty_history
        budget = torch.tensor([item.remaining_budget / item.retry_budget, item.retry_budget / 50.0],
                              dtype=torch.float32, device=device)
        return torch.cat((scene, pooled, history, budget))

    def forward(self, items: CandidateVerifierInput | Sequence[CandidateVerifierInput]) -> Tensor:
        if isinstance(items, CandidateVerifierInput):
            items = (items,)
        return self.head(torch.stack([self.encode_one(item) for item in items]))

def build_verifier_input(*, scene_feature: np.ndarray, evidence: RoundEvidence,
                         remaining_budget: int, retry_budget: int,
                         executed_history: np.ndarray | None = None,
                         backbone_id: str = "", decision_step: int | None = None,
                         **diagnostics) -> CandidateVerifierInput:
    # Geometry/Planner scores and post-decision outcomes are deliberately NOT feature channels.
    actions = evidence.action_batch.actions
    aligned_actions = np.concatenate((np.zeros_like(actions[:, :1, :7]), actions[:, :, :7]), axis=1)
    sequences = np.concatenate((aligned_actions, evidence.trajectories.positions,
                                evidence.trajectories.orientations,
                                evidence.trajectories.grippers[..., None]), axis=-1)
    history = np.empty((0, HISTORY_DIMS), dtype=np.float32) if executed_history is None else executed_history
    return CandidateVerifierInput(scene_feature, sequences, history, remaining_budget, retry_budget,
                                  tuple(c.candidate_id for c in evidence.candidates),
                                  evidence.context_id, backbone_id,
                                  len(history) if decision_step is None else decision_step)

def ablate_verifier_input(item: CandidateVerifierInput, channel_set: str) -> CandidateVerifierInput:
    if channel_set == "full":
        return item
    if channel_set == "candidates_only":
        return replace(item, scene_feature=np.zeros_like(item.scene_feature))
    if channel_set == "scene_only":
        return replace(item, candidate_trajectories=np.zeros_like(item.candidate_trajectories),
                       executed_history=np.zeros_like(item.executed_history))
    raise ValueError(f"unsupported candidate verifier ablation: {channel_set}")

class FeatureStandardizer:
    """Normalization is learned LayerNorm inside the small head, not an old fixed feature vector."""
    def __init__(self, statistics=None):
        self.statistics = {}
    @classmethod
    def fit(cls, items):
        if not items:
            raise ValueError("training inputs are empty")
        return cls()
    def transform(self, item):
        return item
    def to_json(self):
        return {"kind": "head_layer_norm_v3"}
    @classmethod
    def from_json(cls, value):
        if value != {"kind": "head_layer_norm_v3"}:
            raise ValueError("legacy feature normalizer is incompatible; regenerate inputs")
        return cls()

def save_verifier_input(path: Path, item: CandidateVerifierInput, *, metadata: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, scene_feature=item.scene_feature,
                            candidate_trajectories=item.candidate_trajectories,
                            executed_history=item.executed_history,
                            remaining_budget=item.remaining_budget, retry_budget=item.retry_budget,
                            candidate_ids=np.asarray(item.candidate_ids), context_id=item.context_id,
                            backbone_id=item.backbone_id, decision_step=item.decision_step,
                            feature_schema=VERIFIER_FEATURE_SCHEMA)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    value = dict(metadata or {})
    value.update(schema_version=VERIFIER_FEATURE_SCHEMA, retry_budget=item.retry_budget,
                 remaining_budget=item.remaining_budget, candidate_count=len(item.candidate_ids),
                 candidate_ids=list(item.candidate_ids), backbone_id=item.backbone_id,
                 context_id=item.context_id, decision_step=item.decision_step,
                 feature_sha256=sha256_file(path), input_time_scope="at_decision")
    atomic_write_json(path.with_suffix(".json"), value)
    return path

def load_verifier_input(path: Path) -> CandidateVerifierInput:
    with np.load(Path(path), allow_pickle=False) as data:
        if str(data.get("feature_schema", "")) != VERIFIER_FEATURE_SCHEMA:
            raise ValueError("legacy verifier features are incompatible; regenerate full decision-time candidates")
        return CandidateVerifierInput(
            data["scene_feature"], data["candidate_trajectories"], data["executed_history"],
            int(data["remaining_budget"]), int(data["retry_budget"]),
            tuple(data["candidate_ids"].tolist()), str(data["context_id"]),
            str(data["backbone_id"]), int(data["decision_step"]))

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



def save_verifier_artifact(root: Path, *, model: GroundedCapabilityVerifier,
                          standardizer: FeatureStandardizer, calibrator: PlattCalibrator,
                          metadata: dict) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    require_fixed_budget_50_contract(metadata["label_config"])
    if not metadata.get("backbone_id"):
        raise ValueError("artifact must identify the frozen v44 backbone")
    temporary = root / f".head.{os.getpid()}.tmp"
    torch.save(model.state_dict(), temporary)
    os.replace(temporary, root / "head.pt")
    atomic_write_json(root / "manifest.json", {
        "schema_version": "candidate-capability-verifier-v3",
        "input_schema": VERIFIER_FEATURE_SCHEMA, "head_architecture": VERIFIER_HEAD_ARCHITECTURE,
        "output_classes": [route.value for route in VERIFIER_CLASSES],
        "decision_rule": "head_argmax", "backbone_frozen": True,
        "trainable_components": ["trajectory_encoder", "history_encoder", "scene_projection", "head", "empty_history"],
        "normalizer": standardizer.to_json(),
        "calibrator": {"slope": calibrator.slope, "intercept": calibrator.intercept},
        "head_sha256": sha256_file(root / "head.pt"), "metadata": metadata})

@dataclass(frozen=True)
class VerifierPrediction:
    route: ControllerRoute
    logits: tuple[float, float]
    p_expansion: float

class DeployedVerifierPredictor:
    def __init__(self, artifact_root: Path, *, device: str = "cpu") -> None:
        self.artifact_root = Path(artifact_root)
        manifest = json.loads((self.artifact_root / "manifest.json").read_text())
        if (manifest.get("schema_version") != "candidate-capability-verifier-v3"
                or manifest.get("head_architecture") != VERIFIER_HEAD_ARCHITECTURE
                or manifest.get("decision_rule") != "head_argmax"
                or manifest.get("output_classes") != [x.value for x in VERIFIER_CLASSES]
                or manifest.get("backbone_frozen") is not True):
            raise ValueError("incompatible verifier: train the new candidate encoder/head, do not load legacy weights")
        if sha256_file(self.artifact_root / "head.pt") != manifest["head_sha256"]:
            raise ValueError("verifier checkpoint integrity mismatch")
        self.metadata = manifest["metadata"]
        require_fixed_budget_50_contract(self.metadata["label_config"])
        self.model = GroundedCapabilityVerifier().to(device)
        self.model.load_state_dict(torch.load(self.artifact_root / "head.pt", map_location=device, weights_only=True))
        self.model.eval()
        self.standardizer = FeatureStandardizer.from_json(manifest["normalizer"])
        self.calibrator = PlattCalibrator(**manifest["calibrator"])
        self.channel_set = self.metadata.get("training_config", {}).get("channel_set", "full")
    def predict_logits(self, item: CandidateVerifierInput) -> np.ndarray:
        if item.retry_budget != 50 or item.backbone_id != self.metadata["backbone_id"]:
            raise ValueError("decision-time input budget/backbone differs from trained artifact")
        with torch.inference_mode():
            logits = self.model(ablate_verifier_input(item, self.channel_set))[0].cpu().numpy()
        return np.asarray(logits, dtype=float)
    def predict(self, item: CandidateVerifierInput) -> VerifierPrediction:
        logits = self.predict_logits(item)
        return VerifierPrediction(VERIFIER_CLASSES[int(np.argmax(logits))],
                                  tuple(map(float, logits)),
                                  float(self.calibrator.predict(logits[1] - logits[0])))
    def predict_logit_margin(self, item):
        logits = self.predict_logits(item)
        return float(logits[1] - logits[0])
    def predict_probability(self, item):
        return self.predict(item).p_expansion
    def predict_probabilities(self, items):
        return np.asarray([self.predict_probability(x) for x in items])
    def predict_routes(self, items):
        return tuple(self.predict(x).route for x in items)
