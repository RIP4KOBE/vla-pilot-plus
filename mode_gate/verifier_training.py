"""Planner-selected candidate-verifier training with decision-time inputs and independent experience checks."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence
import numpy as np
import torch
from torch.nn import functional as F
from .incidents import IncidentMemory
from .io_utils import atomic_write_json, sha256_file
from .experiment_contract import FIXED_BUDGET_50_LABEL_VERSION, FIXED_BUDGET_50_CONTRACT, label_contract_payload
from .verifier import (CandidateVerifierInput, GroundedCapabilityVerifier, DeployedVerifierPredictor,
    FeatureStandardizer, PlattCalibrator, ablate_verifier_input, load_verifier_input,
    save_verifier_artifact, expected_calibration_error)

@dataclass(frozen=True)
class VerifierExample:
    record_id: str
    policy_id: str
    group_id: str
    split: str
    feature_path: str
    source: str
    target_class: int
    annotation_id: str
    feature_sha256: str
    weight: float = 1.0
    episode_id: str = ""
    snapshot_hash: str = ""
    label_version: str = FIXED_BUDGET_50_LABEL_VERSION
    evidence_refs: tuple = ()

@dataclass(frozen=True)
class VerifierTrainingConfig:
    seed: int = 20260914
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 32
    max_epochs: int = 100
    patience: int = 20
    device: str = "cuda:6"
    channel_set: str = "full"
    training_mode: str = "planner_selected"
    warm_start_artifact: str | None = None
    label_version: str = FIXED_BUDGET_50_LABEL_VERSION
    def __post_init__(self):
        if min(self.batch_size, self.max_epochs, self.patience) <= 0 or self.learning_rate <= 0:
            raise ValueError("invalid training hyperparameters")
        if self.label_version != FIXED_BUDGET_50_LABEL_VERSION:
            raise ValueError("train a new fixed_budget_50-v2 label version")
        if self.channel_set not in {"full", "scene_only", "candidates_only"}:
            raise ValueError("unsupported channel ablation")
        if self.training_mode not in {"planner_selected", "initialization_all_data", "online_finetune", "heldout"}:
            raise ValueError("unsupported training mode")

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

def continue_from_active_verifier(config, registry):
    active = registry.active()
    if active and active.verifier_id:
        path = registry.root / "verifiers" / active.verifier_id
        manifest = json.loads((path / "manifest.json").read_text())
        if manifest.get("schema_version") == "candidate-capability-verifier-v3":
            return replace(config, warm_start_artifact=str(path))
    # Old weights are structurally incompatible, not a warm start for this head.
    return replace(config, warm_start_artifact=None)

def build_verifier_examples(memory, *, policy_id, split_resolver=None,
                           label_version=FIXED_BUDGET_50_LABEL_VERSION,
                           excluded_record_ids=(), request=None, allowed_task_keys=()):
    if label_version != FIXED_BUDGET_50_LABEL_VERSION:
        raise ValueError("old-budget labels cannot enter new candidate-verifier training")
    if request is None:
        requests = list(memory.experiences.training_requests.iter_valid())
        if not requests:
            raise ValueError("Planner has not selected a retrain dataset")
        request = requests[-1]
    train = set(request["train_annotation_ids"])
    independent = set(request["independent_annotation_ids"])
    if train & independent:
        raise ValueError("training and independent selections overlap")
    annotations = {v["annotation_id"]: v for v in memory.experiences.latest_annotations().values()}
    decisions = {v["record_id"]: v for v in memory.decisions.iter_valid()}
    from .verifier_feedback import derive_verifier_feedback, validate_feedback_annotation
    feedback_ids = [annotations[aid]["record_id"] for aid in train | independent
                    if aid in annotations and annotations[aid].get("feedback_id")]
    feedback = derive_verifier_feedback(memory, record_ids=feedback_ids) if feedback_ids else []
    result = []
    for aid in sorted(train | independent):
        label = annotations.get(aid)
        if not label or not label.get("use_for_training") or label["label_version"] != label_version:
            raise ValueError("stale/withdrawn Planner annotation")
        observed_feedback = validate_feedback_annotation(memory, label, assessments=feedback)
        decision = decisions[label["record_id"]]
        group = decision.get("provenance", {}).get("group", {})
        if allowed_task_keys:
            task_key = '::'.join(str(group.get(key, '')) for key in ('suite','task_id','perturbation_variant'))
            if task_key not in allowed_task_keys:
                raise ValueError('initialization training data is outside the user-selected two-task scope')
        if label["record_id"] in excluded_record_ids:
            continue
        path = Path(decision["verifier_feature_path"])
        meta = json.loads(path.with_suffix(".json").read_text())
        item = load_verifier_input(path)
        if (meta.get("feature_sha256") != sha256_file(path) or meta.get("input_time_scope") != "at_decision"
                or item.retry_budget != 50 or not item.backbone_id
                or item.remaining_budget != decision["remaining_budget"]
                or (observed_feedback is not None and item.decision_step != observed_feedback["decision_step"])
                or meta.get("policy_id", meta.get("target_policy_id")) != decision["policy_id"]
                or meta.get("snapshot_id") != decision["snapshot_id"]):
            raise ValueError("feature provenance/time boundary does not match its original decision")
        episode_id = str(label.get("episode_id") or group.get("episode_id") or "")
        group_id = episode_id or decision["snapshot_hash"]
        if aid in independent:
            for run in memory.experiences.training_usage.iter_valid():
                for used in run.get("examples", []):
                    if used.get("split") == "train" and (used.get("group_id") == group_id
                            or used.get("snapshot_hash") == decision["snapshot_hash"]):
                        raise ValueError("independent experience was used by an earlier verifier training run")
        if not group_id:
            raise ValueError("independence requires episode/snapshot identity")
        result.append(VerifierExample(
            label["record_id"], decision["policy_id"], group_id,
            "train" if aid in train else "test", str(path), str(label.get("source", "planner")),
            int(label["label"] == "EXPANSION"), aid, sha256_file(path),
            float(label.get("weight", 1.0)), episode_id, decision["snapshot_hash"], label_version,
            tuple(label["evidence_refs"])))
    validate_independent_groups(result)
    return result

def validate_independent_groups(examples):
    seen = {}
    for row in examples:
        if row.target_class not in (0, 1) or not math.isfinite(row.weight) or row.weight <= 0:
            raise ValueError("invalid binary target/weight")
        for identity in (("record", row.record_id), ("episode", row.group_id),
                         ("snapshot", row.snapshot_hash), ("feature", row.feature_sha256)):
            if not identity[1]:
                continue
            role = "train" if row.split == "train" else "independent"
            if identity in seen and seen[identity] != role:
                raise ValueError(f"independent experience leakage: {identity}")
            seen[identity] = role

def record_verifier_training_usage(memory, result, examples, *, request_id=None):
    """Record every training entry point, including manual/ablation runs, idempotently."""
    examples = list(examples)
    if request_id is None:
        train = {x.annotation_id for x in examples if x.split == "train"}
        independent = {x.annotation_id for x in examples if x.split != "train"}
        for request in memory.experiences.training_requests.iter_valid():
            if (set(request["train_annotation_ids"]) == train
                    and set(request["independent_annotation_ids"]) == independent):
                request_id = request["event_id"]
    memory.experiences.training_usage.append({
        "event_id": result.verifier_id, "schema_version": "verifier-training-usage-v3",
        "verifier_id": result.verifier_id, "dataset_hash": result.dataset_hash,
        "request_id": request_id, "examples": [asdict(x) for x in examples],
        "observed_feedback": selected_feedback_usage(memory, examples),
        "artifact_root": result.artifact_root})

def selected_feedback_usage(memory, examples):
    """Keep rewards/provenance in receipts, never in decision-time features."""
    annotations = {x["annotation_id"]: x for x in memory.experiences.interpretations.iter_valid()}
    return [{"record_id": row.record_id, "annotation_id": row.annotation_id,
             "feedback_id": annotations[row.annotation_id]["feedback_id"],
             "decision_reward": annotations[row.annotation_id]["decision_reward"],
             "corrected_target": row.target_class, "weight": row.weight, "split": row.split}
            for row in examples if annotations.get(row.annotation_id, {}).get("feedback_id")]

def _metrics(model, rows, inputs, device):
    if not rows:
        return {"contexts": 0}
    with torch.inference_mode():
        logits = model([inputs[x.record_id] for x in rows])
        targets = torch.tensor([x.target_class for x in rows], device=device)
        p = logits.softmax(-1)[:, 1].cpu().numpy()
        accuracy = float((logits.argmax(-1) == targets).float().mean())
        loss = float(F.cross_entropy(logits, targets))
    y = np.array([x.target_class for x in rows])
    return {"contexts": len(rows), "accuracy": accuracy, "cross_entropy": loss,
            "brier": float(np.mean((p-y)**2)), "ece": expected_calibration_error(p, y),
            "predictions": [{"record_id": x.record_id, "target": int(y[i]),
                             "p_expansion_diagnostic": float(p[i])} for i,x in enumerate(rows)]}

def train_verifier(examples, *, policy_id, output_root, config=VerifierTrainingConfig(),
                   metadata=None, reviewer=None):
    examples = list(examples)
    validate_independent_groups(examples)
    if len({x.record_id for x in examples}) != len(examples):
        raise ValueError("training dataset contains repeated decision contexts")
    train = [x for x in examples if x.split == "train"]
    independent = [x for x in examples if x.split != "train"]
    if not train:
        raise ValueError("Planner selected no training experiences")
    if any(x.label_version != config.label_version for x in examples):
        raise ValueError("mixed label versions")
    dataset_hash = hashlib.sha256(json.dumps([asdict(x) for x in examples], sort_keys=True).encode()).hexdigest()
    run_hash = hashlib.sha256(json.dumps({"dataset":dataset_hash,"config":asdict(config),"policy":policy_id}, sort_keys=True).encode()).hexdigest()
    verifier_id = "candidate-verifier-" + run_hash[:20]
    root = Path(output_root) / verifier_id
    if (root / "training_result.json").is_file():
        saved = json.loads((root / "training_result.json").read_text())
        if saved.get("dataset_hash") != dataset_hash or saved.get("policy_id") != policy_id:
            raise ValueError("completed training result identity mismatch")
        for row in examples:
            if sha256_file(Path(row.feature_path)) != row.feature_sha256:
                raise ValueError("selected training input changed")
        DeployedVerifierPredictor(root)
        return VerifierTrainingResult(saved["verifier_id"],saved["artifact_root"],saved["dataset_hash"],
            saved["metrics"],VerifierDeploymentGate(**saved["gate"]),saved["best_epoch"])
    if root.exists():
        raise FileExistsError("incomplete training artifact requires recovery, not silent overwrite")
    torch.manual_seed(config.seed)
    rng = np.random.default_rng(config.seed)
    device = torch.device(config.device)
    inputs = {}
    for row in examples:
        if sha256_file(Path(row.feature_path)) != row.feature_sha256:
            raise ValueError("training input was changed after selection")
        inputs[row.record_id] = ablate_verifier_input(load_verifier_input(Path(row.feature_path)), config.channel_set)
    backbone_ids = {x.backbone_id for x in inputs.values()}
    if len(backbone_ids) != 1 or not next(iter(backbone_ids)):
        raise ValueError("all inputs must come from the same frozen v44 backbone")
    model = GroundedCapabilityVerifier().to(device)
    incumbent = None
    if config.warm_start_artifact:
        incumbent = DeployedVerifierPredictor(Path(config.warm_start_artifact), device=str(device))
        if incumbent.metadata["backbone_id"] != next(iter(backbone_ids)):
            raise ValueError("warm-start backbone mismatch")
        prior = incumbent.metadata.get("selected_examples", [])
        for row in independent:
            if any(old.get("split") == "train" and (
                    old.get("feature_sha256") == row.feature_sha256
                    or old.get("group_id") == row.group_id
                    or (row.snapshot_hash and old.get("snapshot_hash") == row.snapshot_hash)
                    or (row.episode_id and old.get("episode_id") == row.episode_id)) for old in prior):
                raise ValueError("independent experience leakage from warm-start training")
        model.load_state_dict(incumbent.model.state_dict(), strict=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    # All trainable parameters live in this small module; no policy/VLM is loaded by training.
    parameter_names = [n for n,p in model.named_parameters() if p.requires_grad]
    best, best_epoch, best_state, stale = float("inf"), 0, None, 0
    for epoch in range(config.max_epochs):
        model.train()
        losses = []
        order = rng.permutation(len(train))
        for start in range(0, len(order), config.batch_size):
            rows = [train[i] for i in order[start:start+config.batch_size]]
            logits = model([inputs[x.record_id] for x in rows])
            target = torch.tensor([x.target_class for x in rows], device=device)
            weight = torch.tensor([x.weight for x in rows], device=device)
            loss = (F.cross_entropy(logits, target, reduction="none") * weight).sum() / weight.sum()
            if not torch.isfinite(loss):
                raise ValueError("non-finite verifier loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach()))
        mean = float(np.mean(losses))
        if mean < best:
            best, best_epoch, stale = mean, epoch+1, 0
            best_state = {k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        else:
            stale += 1
        if stale >= config.patience:
            break
    model.load_state_dict(best_state)
    model.eval()
    metrics = {"train": _metrics(model, train, inputs, device),
               "independent": _metrics(model, independent, inputs, device),
               "incumbent_independent": _metrics(incumbent.model, independent, inputs, device) if incumbent else None,
               "input_time_scope": "at_decision", "independent_not_used_for_gradient_or_checkpoint_selection": True}
    review = reviewer(metrics) if reviewer and independent else {"accept": False, "reason": "independent Planner review pending"}
    passed = bool(independent and review.get("accept") is True and
                  review.get("planner_provenance", {}).get("planner_thread_id") ==
                  "01a0893c-15b0-7203-881c-de3c5bcee058")
    gate = VerifierDeploymentGate(passed, (str(review.get("reason", "Planner review")),))
    meta = {**(metadata or {}), "policy_id":policy_id, "label_version":config.label_version,
            "label_config": label_contract_payload(), "backbone_id":next(iter(backbone_ids)),
            "dataset_hash":dataset_hash, "training_config":asdict(config), "metrics":metrics,
            "selected_examples":[asdict(x) for x in examples], "trainable_parameters":parameter_names,
            "planner_deployment_review":review, "warm_start_artifact":config.warm_start_artifact,
            "backbone_frozen":True}
    save_verifier_artifact(root, model=model, standardizer=FeatureStandardizer.fit([inputs[x.record_id] for x in train]),
                          calibrator=PlattCalibrator(1.0, 0.0), metadata=meta)
    result = VerifierTrainingResult(verifier_id, str(root), dataset_hash, metrics, gate, best_epoch)
    atomic_write_json(root / "training_result.json", {**asdict(result), "policy_id":policy_id})
    return result

def verifier_deployment_allowed(result):
    path = Path(str(result.get("artifact_root") or "")) / "manifest.json"
    if not path.is_file():
        return False
    manifest = json.loads(path.read_text())
    meta = manifest.get("metadata", {})
    review = meta.get("planner_deployment_review", {})
    return bool(manifest.get("schema_version") == "candidate-capability-verifier-v3"
                and result.get("gate", {}).get("passed") is True and review.get("accept") is True
                and review.get("planner_provenance", {}).get("planner_thread_id") == "01a0893c-15b0-7203-881c-de3c5bcee058"
                and meta.get("metrics", {}).get("independent", {}).get("contexts", 0))

def train_verifier_ablations(examples, *, policy_id, output_root, config=VerifierTrainingConfig(),
                            metadata=None, reviewer=None, channel_sets=None):
    # The Planner chooses whether to request ablations; there is no mandatory three-run protocol.
    results = {name: train_verifier(examples, policy_id=policy_id, output_root=Path(output_root)/name,
                                   config=replace(config, channel_set=name), metadata=metadata, reviewer=reviewer)
               for name in (channel_sets or (config.channel_set,))}
    selected = next((name for name,row in results.items() if row.gate.passed), None)
    path = Path(output_root) / "comparison.json"
    value = VerifierAblationResult(str(path), next(iter(results.values())).dataset_hash, selected,
                                  "learned_verifier" if selected else "fixed_budget_50", results, {}, {})
    atomic_write_json(path, asdict(value))
    return value

def train_verifier_holdout(examples, *, policy_id, output_root, config=VerifierTrainingConfig(), metadata=None, **kwargs):
    if kwargs:
        raise ValueError("fixed source/task holdout selection was removed; use Planner-selected independent annotations")
    return train_verifier(examples, policy_id=policy_id, output_root=output_root, config=config, metadata=metadata)
