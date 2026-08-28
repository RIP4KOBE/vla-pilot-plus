"""Leakage-safe training, calibration, evaluation, and gating for the verifier."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import torch
from torch.nn import functional as F

from .incidents import IncidentMemory
from .verifier import (
    DeployedVerifierPredictor,
    FeatureStandardizer,
    GroundedCapabilityVerifier,
    ModeVerifierInput,
    PlattCalibrator,
    ablate_verifier_input,
    load_verifier_input,
    save_verifier_artifact,
)
from .types import ControllerRoute


VALID_SPLITS = frozenset({"train", "calibration", "test"})


@dataclass(frozen=True)
class VerifierExample:
    record_id: str
    policy_id: str
    group_id: str
    split: str
    feature_path: str
    source: str
    successes: int
    trials: int
    weight: float
    weak: bool
    behavior_propensity: float
    suite: str = ""
    task_id: str = ""
    perturbation_variant: str = ""
    init_state_id: str = ""
    episode_id: str = ""
    origin_policy_id: str = ""
    recorded_at: str = ""

    @property
    def failures(self) -> int:
        return self.trials - self.successes

    @property
    def p_expansion(self) -> float:
        return self.failures / self.trials

    @property
    def target_class(self) -> int:
        """Symmetric two-class target; exact ties default to RE-STEER."""

        return int(self.failures > self.successes)


@dataclass(frozen=True)
class VerifierTrainingConfig:
    seed: int = 20260825
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 32
    max_epochs: int = 200
    patience: int = 20
    balance_classes: bool = True
    ipw_clip: float = 10.0
    false_positive_cost: float = 30.0
    false_negative_cost: float = 2.0
    bootstrap_samples: int = 1000
    min_train_contexts: int = 1000
    min_train_each_side: int = 100
    min_calibration_contexts: int = 200
    min_calibration_each_side: int = 30
    min_test_contexts: int = 500
    min_test_expansion_contexts: int = 50
    max_ece: float = 0.05
    device: str = "cpu"
    channel_set: str = "full"

    def __post_init__(self) -> None:
        if self.channel_set not in {"full", "scene_only", "modes_only"}:
            raise ValueError("channel_set must be full, scene_only, or modes_only")
        if self.batch_size <= 0 or self.max_epochs <= 0 or self.patience <= 0:
            raise ValueError("training sizes must be positive")
        if self.bootstrap_samples <= 0:
            raise ValueError("bootstrap_samples must be positive")


@dataclass(frozen=True)
class VerifierDeploymentGate:
    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class VerifierTrainingResult:
    verifier_id: str
    artifact_root: str
    dataset_hash: str
    metrics: Mapping[str, Any]
    gate: VerifierDeploymentGate
    best_epoch: int


@dataclass(frozen=True)
class VerifierAblationResult:
    report_path: str
    dataset_hash: str
    selected_channel_set: str | None
    controller_mode: str
    results: Mapping[str, VerifierTrainingResult]
    comparisons: Mapping[str, Any]
    channel_correlation: Mapping[str, Any]


SplitResolver = Callable[[Mapping[str, Any], Mapping[str, Any]], str]


def build_verifier_examples(
    memory: IncidentMemory,
    *,
    policy_id: str,
    split_resolver: SplitResolver | Mapping[str, str] | None = None,
) -> list[VerifierExample]:
    """Join immutable decisions/labels into one row per policy/context.

    Hard evidence takes precedence over weak demo matches.  A new-policy label
    is rejected unless it names a feature sidecar computed from that same
    policy's fresh modes.
    """

    candidates: dict[tuple[str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}
    for row in memory.joined_training_rows(include_weak=True):
        decision, label = row["decision"], row["label"]
        if str(label["policy_id"]) != policy_id:
            continue
        feature_path = str(label.get("verifier_feature_path") or "")
        if not feature_path:
            if str(decision["policy_id"]) != policy_id:
                raise ValueError(
                    f"new-policy label {label['record_id']} has no policy-specific feature"
                )
            feature_path = str(decision.get("verifier_feature_path") or "")
        if not feature_path or not Path(feature_path).is_file():
            raise FileNotFoundError(feature_path or f"feature for {label['record_id']}")
        feature_metadata_path = Path(feature_path).with_suffix(".json")
        if feature_metadata_path.is_file():
            feature_metadata = json.loads(
                feature_metadata_path.read_text(encoding="utf-8")
            )
            feature_policy = feature_metadata.get("policy_id")
            if feature_policy is not None and str(feature_policy) != policy_id:
                raise ValueError(
                    f"feature policy mismatch for {label['record_id']}: "
                    f"{feature_policy!r} != {policy_id!r}"
                )
        group_id = _group_id(decision)
        split = _resolve_split(decision, label, group_id, split_resolver)
        weak = bool(label.get("weak", False))
        if weak and split != "train":
            raise ValueError("weak demo-match labels are forbidden in calibration/test")
        priority = (
            0 if weak else 1,
            _source_priority(str(label["source"])),
            int(label["branches"]),
            str(label.get("labeled_at", "")),
        )
        key = (str(label["record_id"]), policy_id)
        previous = candidates.get(key)
        if previous is None or priority > previous[0]:
            candidates[key] = (
                priority,
                {
                    "decision": decision,
                    "label": label,
                    "feature_path": feature_path,
                    "group_id": group_id,
                    "split": split,
                },
            )

    examples = []
    for _, value in sorted(candidates.values(), key=lambda item: item[1]["label"]["record_id"]):
        decision, label = value["decision"], value["label"]
        provenance = decision.get("provenance", {})
        group = provenance.get("group", {}) if isinstance(provenance, Mapping) else {}
        propensity = label.get("behavior_propensity")
        if propensity is None:
            propensity = decision.get("behavior_propensity", 1.0)
        examples.append(
            VerifierExample(
                record_id=str(label["record_id"]),
                policy_id=policy_id,
                group_id=value["group_id"],
                split=value["split"],
                feature_path=str(Path(value["feature_path"]).resolve()),
                source=str(label["source"]),
                successes=int(label["successes"]),
                trials=int(label["branches"]),
                weight=float(label.get("weight", 1.0)),
                weak=bool(label.get("weak", False)),
                behavior_propensity=float(propensity),
                suite=str(group.get("suite") or ""),
                task_id=str(group.get("task_id") or ""),
                perturbation_variant=str(
                    group.get("perturbation_variant") or ""
                ),
                init_state_id=str(group.get("init_state_id") or ""),
                episode_id=str(group.get("episode_id") or ""),
                origin_policy_id=str(decision.get("policy_id") or ""),
                recorded_at=str(decision.get("recorded_at") or ""),
            )
        )
    if not examples:
        raise ValueError(f"no verifier examples for policy {policy_id!r}")
    assert_group_isolation(examples)
    return examples


def assert_group_isolation(examples: Sequence[VerifierExample]) -> None:
    groups: dict[str, str] = {}
    for example in examples:
        if example.split not in VALID_SPLITS:
            raise ValueError(f"invalid verifier split {example.split!r}")
        previous = groups.setdefault(example.group_id, example.split)
        if previous != example.split:
            raise ValueError(
                f"verifier group leakage: {example.group_id} is in {previous} and {example.split}"
            )


def verifier_training_weights(
    examples: Sequence[VerifierExample], *, ipw_clip: float
) -> dict[str, float]:
    """Return context-normalized inverse-propensity training weights."""

    if ipw_clip <= 0:
        raise ValueError("ipw_clip must be positive")
    group_sizes: dict[str, int] = {}
    for item in examples:
        if not 0.0 < item.behavior_propensity <= 1.0:
            raise ValueError("behavior propensity must be in (0, 1]")
        group_sizes[item.group_id] = group_sizes.get(item.group_id, 0) + 1
    return {
        item.record_id: min(ipw_clip, item.weight / item.behavior_propensity)
        / group_sizes[item.group_id]
        for item in examples
    }


def verifier_dataset_hash(examples: Sequence[VerifierExample]) -> str:
    digest = hashlib.sha256()
    digest.update(b"grounded-verifier-dataset-v1\0")
    for example in sorted(examples, key=lambda item: (item.record_id, item.policy_id)):
        payload = asdict(example)
        feature = Path(example.feature_path)
        payload["feature_sha256"] = hashlib.sha256(feature.read_bytes()).hexdigest()
        digest.update(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def train_verifier(
    examples: Sequence[VerifierExample],
    *,
    policy_id: str,
    output_root: Path,
    config: VerifierTrainingConfig = VerifierTrainingConfig(),
    metadata: Mapping[str, Any] | None = None,
) -> VerifierTrainingResult:
    """Train from scratch, calibrate on natural data, gate on sealed verifier test."""

    examples = tuple(examples)
    if any(example.policy_id != policy_id for example in examples):
        raise ValueError("verifier training examples mix policy IDs")
    assert_group_isolation(examples)
    by_split = {
        split: tuple(example for example in examples if example.split == split)
        for split in VALID_SPLITS
    }
    if any(not by_split[split] for split in VALID_SPLITS):
        raise ValueError("train, calibration, and test splits must all be non-empty")
    if any(example.weak for split in ("calibration", "test") for example in by_split[split]):
        raise ValueError("calibration/test must contain natural non-weak labels only")

    inputs = {example.record_id: load_verifier_input(Path(example.feature_path)) for example in examples}
    standardizer = FeatureStandardizer.fit(
        [
            ablate_verifier_input(inputs[item.record_id], config.channel_set)
            for item in by_split["train"]
        ]
    )
    normalized = {
        record_id: standardizer.transform(
            ablate_verifier_input(item, config.channel_set)
        )
        for record_id, item in inputs.items()
    }
    model, best_epoch = _fit_head(
        by_split["train"], normalized=normalized, config=config
    )
    calibration_logits = _predict_logits(model, by_split["calibration"], normalized)
    calibration_margins = _logit_margins(calibration_logits)
    calibration_failures = np.asarray(
        [item.failures for item in by_split["calibration"]], dtype=np.float64
    )
    calibration_trials = np.asarray(
        [item.trials for item in by_split["calibration"]], dtype=np.float64
    )
    calibration_error = None
    try:
        calibrator = PlattCalibrator.fit_binomial(
            calibration_margins,
            failures=calibration_failures,
            trials=calibration_trials,
        )
    except ValueError as exc:
        calibrator = PlattCalibrator(1.0, 0.0)
        calibration_error = str(exc)

    test_logits = _predict_logits(model, by_split["test"], normalized)
    test_margins = _logit_margins(test_logits)
    test_probabilities = calibrator.predict(test_margins)
    test_classes = np.argmax(test_logits, axis=1).astype(np.int64)
    metrics = evaluate_verifier(
        by_split["test"],
        test_probabilities,
        class_predictions=test_classes,
        logit_margins=test_margins,
        config=config,
    )
    counts = {split: _split_counts(rows) for split, rows in by_split.items()}
    metrics = {
        **metrics,
        "split_counts": counts,
        "calibration_error": calibration_error,
        "channel_set": config.channel_set,
    }
    gate = deployment_gate(metrics=metrics, config=config)
    dataset_hash = verifier_dataset_hash(examples)
    config_hash = hashlib.sha256(
        json.dumps(asdict(config), sort_keys=True).encode("utf-8")
    ).hexdigest()
    verifier_id = "verifier_" + hashlib.sha256(
        f"{policy_id}\0{dataset_hash}\0{config_hash}".encode("utf-8")
    ).hexdigest()[:16]
    artifact_root = Path(output_root) / verifier_id
    if artifact_root.exists():
        manifest = json.loads((artifact_root / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("metadata", {}).get("dataset_hash") != dataset_hash:
            raise ValueError(f"immutable verifier artifact collision: {verifier_id}")
    else:
        Path(output_root).mkdir(parents=True, exist_ok=True)
        staging = Path(output_root) / f".{verifier_id}.{os.getpid()}.staging"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        artifact_metadata = {
            "policy_id": policy_id,
            "dataset_hash": dataset_hash,
            "config_hash": config_hash,
            "training_config": asdict(config),
            "best_epoch": best_epoch,
            "metrics": metrics,
            "deployment_gate": asdict(gate),
            "provenance": dict(metadata or {}),
        }
        save_verifier_artifact(
            staging,
            model=model,
            standardizer=standardizer,
            calibrator=calibrator,
            metadata=artifact_metadata,
        )
        os.replace(staging, artifact_root)
    return VerifierTrainingResult(
        verifier_id=verifier_id,
        artifact_root=str(artifact_root),
        dataset_hash=dataset_hash,
        metrics=metrics,
        gate=gate,
        best_epoch=best_epoch,
    )


def train_verifier_ablations(
    examples: Sequence[VerifierExample],
    *,
    policy_id: str,
    output_root: Path,
    config: VerifierTrainingConfig = VerifierTrainingConfig(),
    metadata: Mapping[str, Any] | None = None,
) -> VerifierAblationResult:
    """Fit scene-only, modes-only, and full heads on exactly the same splits.

    The report contains paired context-bootstrap comparisons and a correlation
    audit for geometry/semantic/weight channels.  A production verifier is
    selected only if it passes the normal deployment gate; otherwise the
    result explicitly selects the fixed-budget-4 controller.
    """

    examples = tuple(examples)
    assert_group_isolation(examples)
    dataset_hash = verifier_dataset_hash(examples)
    artifact_root = Path(output_root) / "artifacts"
    results: dict[str, VerifierTrainingResult] = {}
    for channel_set in ("scene_only", "modes_only", "full"):
        results[channel_set] = train_verifier(
            examples,
            policy_id=policy_id,
            output_root=artifact_root,
            config=replace(config, channel_set=channel_set),
            metadata={
                **dict(metadata or {}),
                "experiment_role": "verifier_channel_ablation",
                "ablation_dataset_hash": dataset_hash,
                "channel_set": channel_set,
            },
        )

    test_examples = tuple(item for item in examples if item.split == "test")
    test_inputs = [load_verifier_input(Path(item.feature_path)) for item in test_examples]
    probabilities: dict[str, np.ndarray] = {}
    decisions: dict[str, np.ndarray] = {}
    for channel_set, result in results.items():
        predictor = DeployedVerifierPredictor(Path(result.artifact_root))
        if predictor.channel_set != channel_set:
            raise RuntimeError("ablation artifact channel contract changed after save")
        probabilities[channel_set] = predictor.predict_probabilities(test_inputs)
        decisions[channel_set] = np.asarray(
            [
                int(route is ControllerRoute.EXPAND)
                for route in predictor.predict_routes(test_inputs)
            ],
            dtype=np.int64,
        )

    comparisons = {
        channel_set: _paired_ablation_comparison(
            test_examples,
            candidate=probabilities[channel_set],
            full=probabilities["full"],
            candidate_decisions=decisions[channel_set],
            full_decisions=decisions["full"],
            config=config,
        )
        for channel_set in ("scene_only", "modes_only")
    }
    selected = _select_ablation_channel(results, comparisons)
    controller_mode = "learned_verifier" if selected is not None else "fixed_budget_4"
    correlation = verifier_channel_correlation(test_examples, test_inputs)
    report = {
        "schema_version": "verifier-ablation-report-v1",
        "policy_id": policy_id,
        "dataset_hash": dataset_hash,
        "same_split_assertion": True,
        "selected_channel_set": selected,
        "controller_mode": controller_mode,
        "results": {
            name: {
                **asdict(result),
                "gate": asdict(result.gate),
            }
            for name, result in results.items()
        },
        "paired_comparisons_against_full": comparisons,
        "channel_correlation": correlation,
        "provenance": dict(metadata or {}),
    }
    report_id = hashlib.sha256(
        json.dumps(
            {
                "policy_id": policy_id,
                "dataset_hash": dataset_hash,
                "config": asdict(replace(config, channel_set="full")),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    report_path = Path(output_root) / f"ablation_{report_id}.json"
    _write_immutable_json(report_path, report)
    return VerifierAblationResult(
        report_path=str(report_path),
        dataset_hash=dataset_hash,
        selected_channel_set=selected,
        controller_mode=controller_mode,
        results=results,
        comparisons=comparisons,
        channel_correlation=correlation,
    )


def build_verifier_holdout(
    examples: Sequence[VerifierExample],
    *,
    kind: str,
    value: str,
) -> tuple[VerifierExample, ...]:
    """Create a true refit holdout without relabelling or row leakage.

    ``task``, ``axis``, and ``checkpoint`` remove the selected value from both
    train and calibration and retain only that value in test. ``temporal``
    treats ``value`` as an ISO-8601 cutoff: fitting rows must be older and test
    rows must be at or after the cutoff.
    """

    field = {
        "task": "task_id",
        "axis": "perturbation_variant",
        "checkpoint": "origin_policy_id",
    }.get(kind)
    if kind not in {"task", "axis", "checkpoint", "temporal"}:
        raise ValueError("holdout kind must be task, axis, checkpoint, or temporal")
    selected: list[VerifierExample] = []
    for item in examples:
        if kind == "temporal":
            if not item.recorded_at:
                continue
            keep = item.recorded_at < value if item.split != "test" else item.recorded_at >= value
        else:
            assert field is not None
            actual = str(getattr(item, field))
            keep = actual != value if item.split != "test" else actual == value
        if keep:
            selected.append(item)
    counts = {split: sum(item.split == split for item in selected) for split in VALID_SPLITS}
    missing = [split for split, count in counts.items() if count == 0]
    if missing:
        raise ValueError(
            f"holdout {kind}={value!r} has empty split(s): {', '.join(sorted(missing))}"
        )
    assert_group_isolation(selected)
    return tuple(selected)


def train_verifier_holdout(
    examples: Sequence[VerifierExample],
    *,
    policy_id: str,
    kind: str,
    value: str,
    output_root: Path,
    config: VerifierTrainingConfig = VerifierTrainingConfig(),
    metadata: Mapping[str, Any] | None = None,
) -> VerifierTrainingResult:
    """Refit and evaluate one preregistered temporal/checkpoint/task/axis holdout."""

    held_out = build_verifier_holdout(examples, kind=kind, value=value)
    return train_verifier(
        held_out,
        policy_id=policy_id,
        output_root=Path(output_root) / kind,
        config=config,
        metadata={
            **dict(metadata or {}),
            "experiment_role": "verifier_true_holdout",
            "holdout_kind": kind,
            "holdout_value": value,
            "fit_excludes_holdout": True,
        },
    )


def verifier_channel_correlation(
    examples: Sequence[VerifierExample],
    inputs: Sequence[ModeVerifierInput] | None = None,
) -> dict[str, Any]:
    """Correlation audit over pre-decision mode channels and soft outcome."""

    if inputs is None:
        inputs = [load_verifier_input(Path(item.feature_path)) for item in examples]
    if len(inputs) != len(examples) or not examples:
        raise ValueError("correlation inputs must be non-empty and aligned")
    names = (
        "collision_risk",
        "reachability",
        "grasp_plausibility",
        "semantic_score",
        "max_mode_weight",
        "mode_entropy",
        "p_expansion",
    )
    rows = []
    for example, item in zip(examples, inputs):
        weights = np.asarray(item.mode_weights, dtype=np.float64)
        geometry = np.asarray(item.geometry_features, dtype=np.float64)
        semantic = np.asarray(item.semantic_features[:, 0], dtype=np.float64)
        rows.append(
            [
                float(weights @ geometry[:, 0]),
                float(weights @ geometry[:, 1]),
                float(weights @ geometry[:, 2]),
                float(weights @ semantic),
                float(weights.max()),
                float(-(weights * np.log(np.clip(weights, 1e-12, 1.0))).sum()),
                float(example.p_expansion),
            ]
        )
    values = np.asarray(rows, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        matrix = np.corrcoef(values, rowvar=False)
    serialized = [
        [None if not np.isfinite(value) else float(value) for value in row]
        for row in matrix
    ]
    return {"contexts": len(examples), "columns": list(names), "pearson": serialized}


def _select_ablation_channel(
    results: Mapping[str, VerifierTrainingResult],
    comparisons: Mapping[str, Mapping[str, Any]],
) -> str | None:
    full = results["full"]
    for name in ("scene_only", "modes_only"):
        comparison = comparisons[name]
        if (
            results[name].gate.passed
            and float(comparison["average_precision_difference"]) >= 0.0
            and float(comparison["expected_cost_difference"]) <= 0.0
        ):
            return name
    return "full" if full.gate.passed else None


def _paired_ablation_comparison(
    examples: Sequence[VerifierExample],
    *,
    candidate: np.ndarray,
    full: np.ndarray,
    candidate_decisions: np.ndarray,
    full_decisions: np.ndarray,
    config: VerifierTrainingConfig,
) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score

    candidate = np.asarray(candidate, dtype=np.float64)
    full = np.asarray(full, dtype=np.float64)
    candidate_decisions = np.asarray(candidate_decisions, dtype=np.int64)
    full_decisions = np.asarray(full_decisions, dtype=np.int64)
    if candidate.shape != full.shape or candidate.shape != (len(examples),):
        raise ValueError("ablation probabilities must be aligned")
    if (
        candidate_decisions.shape != candidate.shape
        or full_decisions.shape != candidate.shape
        or not set(np.unique(candidate_decisions)).issubset({0, 1})
        or not set(np.unique(full_decisions)).issubset({0, 1})
    ):
        raise ValueError("ablation head decisions must be aligned binary classes")

    def context_cost(head_decisions: np.ndarray) -> np.ndarray:
        truth = np.asarray([item.p_expansion for item in examples], dtype=np.float64)
        expand = head_decisions.astype(bool)
        return np.where(
            expand,
            (1.0 - truth) * config.false_positive_cost,
            truth * config.false_negative_cost,
        )

    candidate_cost = context_cost(candidate_decisions)
    full_cost = context_cost(full_decisions)
    labels, candidate_trials = _expanded_trials(examples, candidate)
    _, full_trials = _expanded_trials(examples, full)
    point_ap = (
        float(average_precision_score(labels, candidate_trials))
        - float(average_precision_score(labels, full_trials))
    )
    point_cost = float(np.mean(candidate_cost - full_cost))

    groups: dict[str, list[int]] = {}
    for index, item in enumerate(examples):
        groups.setdefault(item.group_id, []).append(index)
    group_ids = sorted(groups)
    rng = np.random.default_rng(config.seed + 101)
    ap_samples: list[float] = []
    cost_samples: list[float] = []
    for _ in range(config.bootstrap_samples):
        chosen_groups = rng.choice(group_ids, size=len(group_ids), replace=True)
        indices = [index for group in chosen_groups for index in groups[str(group)]]
        chosen_examples = [examples[index] for index in indices]
        chosen_candidate = candidate[indices]
        chosen_full = full[indices]
        chosen_labels, chosen_candidate_trials = _expanded_trials(
            chosen_examples, chosen_candidate
        )
        _, chosen_full_trials = _expanded_trials(chosen_examples, chosen_full)
        if len(np.unique(chosen_labels)) == 2:
            ap_samples.append(
                float(average_precision_score(chosen_labels, chosen_candidate_trials))
                - float(average_precision_score(chosen_labels, chosen_full_trials))
            )
        cost_samples.append(float(np.mean(candidate_cost[indices] - full_cost[indices])))
    return {
        "average_precision_difference": point_ap,
        "average_precision_difference_context_bootstrap95": _finite_interval(ap_samples),
        "expected_cost_difference": point_cost,
        "expected_cost_difference_context_bootstrap95": _finite_interval(cost_samples),
        "point_noninferior_to_full": point_ap >= 0.0 and point_cost <= 0.0,
    }


def _finite_interval(values: Sequence[float]) -> list[float | None]:
    finite = np.asarray([value for value in values if np.isfinite(value)], dtype=np.float64)
    if not len(finite):
        return [None, None]
    return [float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))]


def _write_immutable_json(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise ValueError(f"immutable report collision: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def evaluate_verifier(
    examples: Sequence[VerifierExample],
    probabilities: np.ndarray,
    *,
    class_predictions: np.ndarray,
    logit_margins: np.ndarray | None,
    config: VerifierTrainingConfig,
) -> dict[str, Any]:
    probabilities = np.asarray(probabilities, dtype=np.float64)
    if probabilities.shape != (len(examples),) or np.any(~np.isfinite(probabilities)):
        raise ValueError("verifier probabilities must align with examples")
    class_predictions = np.asarray(class_predictions, dtype=np.int64)
    if class_predictions.shape != (len(examples),) or not set(
        np.unique(class_predictions)
    ).issubset({0, 1}):
        raise ValueError("direct verifier decisions must be aligned binary classes")
    labels, predictions = _expanded_trials(examples, probabilities)
    from sklearn.metrics import average_precision_score, roc_auc_score

    prevalence = float(labels.mean())
    ap = float(average_precision_score(labels, predictions))
    roc_auc = (
        float(roc_auc_score(labels, predictions))
        if len(np.unique(labels)) == 2
        else float("nan")
    )
    clipped = np.clip(predictions, 1e-7, 1.0 - 1e-7)
    brier = float(np.mean((predictions - labels) ** 2))
    log_loss = float(
        -np.mean(labels * np.log(clipped) + (1.0 - labels) * np.log(1.0 - clipped))
    )
    ece = _adaptive_ece(predictions, labels)
    classwise_ece = _classwise_ece(predictions, labels)
    reliability = _reliability_bins(predictions, labels)
    action_expand = np.concatenate(
        [
            np.full(item.trials, bool(decision), dtype=bool)
            for item, decision in zip(examples, class_predictions)
        ]
    )
    true_expand = labels == 1
    tp = int(np.sum(action_expand & true_expand))
    fp = int(np.sum(action_expand & ~true_expand))
    fn = int(np.sum(~action_expand & true_expand))
    tn = int(np.sum(~action_expand & ~true_expand))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    fpr = fp / max(1, fp + tn)
    learned_cost = float(
        np.mean(
            np.where(
                action_expand,
                (~true_expand) * config.false_positive_cost,
                true_expand * config.false_negative_cost,
            )
        )
    )
    fixed_budget_cost = float(np.mean(true_expand * config.false_negative_cost))
    ap_samples = _cluster_bootstrap_ap(
        examples,
        probabilities,
        samples=config.bootstrap_samples,
        seed=config.seed,
    )
    ap_ci = [float(np.quantile(ap_samples, 0.025)), float(np.quantile(ap_samples, 0.975))]
    calibration_slope = float("nan")
    calibration_intercept = float("nan")
    if logit_margins is not None and labels.min() != labels.max():
        try:
            diagnostic = PlattCalibrator.fit_binomial(
                np.asarray(logit_margins),
                failures=np.asarray([item.failures for item in examples]),
                trials=np.asarray([item.trials for item in examples]),
            )
            calibration_slope = diagnostic.slope
            calibration_intercept = diagnostic.intercept
        except ValueError:
            pass
    return {
        "contexts": len(examples),
        "branch_outcomes": int(len(labels)),
        "prevalence": prevalence,
        "average_precision": ap,
        "average_precision_context_bootstrap95": ap_ci,
        "roc_auc": roc_auc,
        "brier": brier,
        "log_loss": log_loss,
        "adaptive_ece": ece,
        "classwise_ece": classwise_ece,
        "reliability_bins": reliability,
        "calibration_slope": calibration_slope,
        "calibration_intercept": calibration_intercept,
        "decision_rule": "head_argmax",
        "precision": precision,
        "recall": recall,
        "false_positive_rate": fpr,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "expected_incremental_cost": learned_cost,
        "fixed_budget_4_expected_incremental_cost": fixed_budget_cost,
    }


def deployment_gate(
    *, metrics: Mapping[str, Any], config: VerifierTrainingConfig
) -> VerifierDeploymentGate:
    counts = metrics["split_counts"]
    reasons: list[str] = []
    _require_counts(
        reasons,
        "train",
        counts["train"],
        config.min_train_contexts,
        config.min_train_each_side,
    )
    _require_counts(
        reasons,
        "calibration",
        counts["calibration"],
        config.min_calibration_contexts,
        config.min_calibration_each_side,
    )
    test = counts["test"]
    if test["strong_contexts"] < config.min_test_contexts:
        reasons.append(
            f"test strong contexts {test['strong_contexts']} < {config.min_test_contexts}"
        )
    if test["expansion_side"] < config.min_test_expansion_contexts:
        reasons.append(
            "test expansion contexts "
            f"{test['expansion_side']} < {config.min_test_expansion_contexts}"
        )
    if metrics.get("calibration_error"):
        reasons.append(f"calibration unavailable: {metrics['calibration_error']}")
    ap_lower = float(metrics["average_precision_context_bootstrap95"][0])
    if not ap_lower > float(metrics["prevalence"]):
        reasons.append("PR-AUC lower confidence bound does not beat prevalence")
    worst_ece = max(
        float(metrics["adaptive_ece"]), float(metrics["classwise_ece"])
    )
    if worst_ece > config.max_ece:
        reasons.append(
            f"ECE {worst_ece:.6f} > {config.max_ece:.6f}"
        )
    if float(metrics["expected_incremental_cost"]) > float(
        metrics["fixed_budget_4_expected_incremental_cost"]
    ):
        reasons.append("expected cost is worse than fixed-budget-4")
    return VerifierDeploymentGate(passed=not reasons, reasons=tuple(reasons))


def _fit_head(
    examples: Sequence[VerifierExample],
    *,
    normalized: Mapping[str, ModeVerifierInput],
    config: VerifierTrainingConfig,
) -> tuple[GroundedCapabilityVerifier, int]:
    _seed_everything(config.seed)
    device = torch.device(config.device)
    model = GroundedCapabilityVerifier().to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    train_rows, validation_rows = _training_validation_groups(examples, config.seed)
    training_weights = verifier_training_weights(
        train_rows, ipw_clip=config.ipw_clip
    )
    target_mean = float(np.mean([item.p_expansion for item in train_rows]))
    positive_weight = (
        (1.0 - target_mean) / max(target_mean, 1e-6)
        if config.balance_classes
        else 1.0
    )
    generator = np.random.default_rng(config.seed)
    best_state = None
    best_loss = math.inf
    best_epoch = 0
    stale = 0
    for epoch in range(config.max_epochs):
        model.train()
        order = generator.permutation(len(train_rows))
        for start in range(0, len(order), config.batch_size):
            batch = [train_rows[int(index)] for index in order[start : start + config.batch_size]]
            logits = model([normalized[item.record_id] for item in batch])
            targets = torch.as_tensor(
                [item.p_expansion for item in batch], dtype=logits.dtype, device=device
            )
            base_weights = [
                training_weights[item.record_id]
                for item in batch
            ]
            weights = torch.as_tensor(base_weights, dtype=logits.dtype, device=device)
            target_distributions = torch.stack([1.0 - targets, targets], dim=1)
            class_weights = torch.as_tensor(
                [1.0, positive_weight], dtype=logits.dtype, device=device
            )
            loss_values = -(
                target_distributions
                * class_weights[None, :]
                * F.log_softmax(logits, dim=1)
            ).sum(dim=1)
            loss = (loss_values * weights).sum() / weights.sum().clamp_min(1e-12)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
        validation_loss = _validation_loss(
            model,
            validation_rows if validation_rows else train_rows,
            normalized,
            device,
        )
        if validation_loss < best_loss - 1e-7:
            best_loss = validation_loss
            best_epoch = epoch + 1
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
            stale = 0
        else:
            stale += 1
            if stale >= config.patience:
                break
    if best_state is None:
        raise RuntimeError("verifier training produced no finite checkpoint")
    model.load_state_dict(best_state, strict=True)
    model.eval()
    return model, best_epoch


def _validation_loss(
    model: GroundedCapabilityVerifier,
    examples: Sequence[VerifierExample],
    normalized: Mapping[str, ModeVerifierInput],
    device: torch.device,
) -> float:
    model.eval()
    with torch.inference_mode():
        logits = model([normalized[item.record_id] for item in examples])
        targets = torch.as_tensor(
            [item.p_expansion for item in examples], dtype=logits.dtype, device=device
        )
        target_distributions = torch.stack([1.0 - targets, targets], dim=1)
        value = -(target_distributions * F.log_softmax(logits, dim=1)).sum(dim=1).mean()
    return float(value.detach().cpu())


def _predict_logits(
    model: GroundedCapabilityVerifier,
    examples: Sequence[VerifierExample],
    normalized: Mapping[str, ModeVerifierInput],
) -> np.ndarray:
    model.eval()
    with torch.inference_mode():
        logits = model([normalized[item.record_id] for item in examples])
    return logits.detach().cpu().numpy().astype(np.float64)


def _logit_margins(logits: np.ndarray) -> np.ndarray:
    logits = np.asarray(logits, dtype=np.float64)
    if logits.ndim != 2 or logits.shape[1] != 2:
        raise ValueError("verifier logits must have shape (N, 2)")
    return logits[:, 1] - logits[:, 0]


def _training_validation_groups(
    examples: Sequence[VerifierExample], seed: int
) -> tuple[tuple[VerifierExample, ...], tuple[VerifierExample, ...]]:
    groups = sorted({item.group_id for item in examples})
    if len(groups) < 5:
        return tuple(examples), ()
    validation = {
        group
        for group in groups
        if int.from_bytes(
            hashlib.sha256(f"{seed}\0{group}".encode()).digest()[:8], "big"
        )
        % 5
        == 0
    }
    if not validation or len(validation) == len(groups):
        validation = {groups[0]}
    return (
        tuple(item for item in examples if item.group_id not in validation),
        tuple(item for item in examples if item.group_id in validation),
    )


def _expanded_trials(
    examples: Sequence[VerifierExample], probabilities: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    labels: list[int] = []
    predictions: list[float] = []
    for item, probability in zip(examples, probabilities):
        labels.extend([1] * item.failures)
        predictions.extend([float(probability)] * item.failures)
        labels.extend([0] * item.successes)
        predictions.extend([float(probability)] * item.successes)
    return np.asarray(labels, dtype=np.int64), np.asarray(predictions, dtype=np.float64)


def _adaptive_ece(probabilities: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    order = np.argsort(probabilities, kind="stable")
    groups = np.array_split(order, min(bins, len(order)))
    return float(
        sum(
            len(group)
            / len(order)
            * abs(float(probabilities[group].mean() - labels[group].mean()))
            for group in groups
            if len(group)
        )
    )


def _classwise_ece(
    probabilities: np.ndarray, labels: np.ndarray, bins: int = 15
) -> float:
    values = []
    for class_id in (0, 1):
        confidence = probabilities if class_id == 1 else 1.0 - probabilities
        target = (labels == class_id).astype(np.float64)
        values.append(_adaptive_ece(confidence, target, bins=bins))
    return float(np.mean(values))


def _reliability_bins(
    probabilities: np.ndarray, labels: np.ndarray, bins: int = 15
) -> list[dict[str, float | int]]:
    order = np.argsort(probabilities, kind="stable")
    groups = np.array_split(order, min(bins, len(order)))
    return [
        {
            "count": int(len(group)),
            "mean_probability": float(probabilities[group].mean()),
            "observed_expansion_rate": float(labels[group].mean()),
            "minimum_probability": float(probabilities[group].min()),
            "maximum_probability": float(probabilities[group].max()),
        }
        for group in groups
        if len(group)
    ]


def _cluster_bootstrap_ap(
    examples: Sequence[VerifierExample],
    probabilities: np.ndarray,
    *,
    samples: int,
    seed: int,
) -> np.ndarray:
    from sklearn.metrics import average_precision_score

    groups: dict[str, list[int]] = {}
    for index, example in enumerate(examples):
        groups.setdefault(example.group_id, []).append(index)
    group_ids = sorted(groups)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(samples):
        selected_groups = rng.choice(group_ids, size=len(group_ids), replace=True)
        selected_indices = [index for group in selected_groups for index in groups[str(group)]]
        chosen_examples = [examples[index] for index in selected_indices]
        chosen_probabilities = probabilities[selected_indices]
        labels, predictions = _expanded_trials(chosen_examples, chosen_probabilities)
        if len(np.unique(labels)) < 2:
            continue
        values.append(float(average_precision_score(labels, predictions)))
    if not values:
        return np.asarray([float("nan")])
    return np.asarray(values, dtype=np.float64)


def _split_counts(examples: Sequence[VerifierExample]) -> dict[str, int]:
    strong = [item for item in examples if not item.weak]
    return {
        "contexts": len(examples),
        "strong_contexts": len(strong),
        "expansion_side": sum(item.target_class == 1 for item in strong),
        "resteer_side": sum(item.target_class == 0 for item in strong),
        "groups": len({item.group_id for item in examples}),
    }


def _require_counts(
    reasons: list[str],
    name: str,
    counts: Mapping[str, int],
    minimum: int,
    each_side: int,
) -> None:
    if counts["strong_contexts"] < minimum:
        reasons.append(f"{name} strong contexts {counts['strong_contexts']} < {minimum}")
    for side in ("expansion_side", "resteer_side"):
        if counts[side] < each_side:
            reasons.append(f"{name} {side} {counts[side]} < {each_side}")


def _group_id(decision: Mapping[str, Any]) -> str:
    provenance = decision.get("provenance", {})
    group = provenance.get("group", {}) if isinstance(provenance, Mapping) else {}
    payload = {
        key: group.get(key)
        for key in (
            "suite",
            "task_id",
            "perturbation_variant",
            "init_state_id",
            "episode_id",
        )
    }
    if payload["episode_id"] is None:
        payload["snapshot_id"] = decision.get("snapshot_id")
    if all(value is None for value in payload.values()):
        payload["context_id"] = decision.get("context_id")
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _resolve_split(
    decision: Mapping[str, Any],
    label: Mapping[str, Any],
    group_id: str,
    resolver: SplitResolver | Mapping[str, str] | None,
) -> str:
    split = label.get("data_split")
    if split is None and resolver is not None:
        split = resolver(decision, label) if callable(resolver) else resolver.get(group_id)
    if split is None:
        provenance = decision.get("provenance", {})
        if isinstance(provenance, Mapping):
            split = provenance.get("verifier_split")
    if split not in VALID_SPLITS:
        raise ValueError(
            f"decision {decision.get('record_id')} has no frozen verifier split"
        )
    return str(split)


def _source_priority(source: str) -> int:
    return {
        "audit": 5,
        "counterfactual_replay": 4,
        "factual_online_retry": 3,
        "demo_match": 1,
    }.get(source, 2)


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


__all__ = [
    "VerifierAblationResult",
    "VerifierDeploymentGate",
    "VerifierExample",
    "VerifierTrainingConfig",
    "VerifierTrainingResult",
    "assert_group_isolation",
    "build_verifier_holdout",
    "build_verifier_examples",
    "deployment_gate",
    "evaluate_verifier",
    "train_verifier_ablations",
    "train_verifier_holdout",
    "train_verifier",
    "verifier_channel_correlation",
    "verifier_dataset_hash",
    "verifier_training_weights",
]
