"""Append-only verifier decisions, late labels, and capability signatures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

from .io_utils import AtomicJsonl


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class VerifierDecisionRecord:
    record_id: str
    context_id: str
    policy_id: str
    snapshot_id: str
    snapshot_hash: str
    scene_feature_path: str
    route: str
    verifier_decision: str | None
    verifier_logits: tuple[float, float] | None
    p_expansion: float | None
    decision_rule: str
    controller_mode: str
    failure_count: int
    remaining_budget: int
    behavior_propensity: float = 1.0
    verifier_feature_path: str = ""
    feature_schema: str = "grounded-verifier-input-v1"
    provenance: Mapping[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.record_id or not self.context_id or not self.snapshot_id:
            raise ValueError("decision IDs must be non-empty")
        if self.p_expansion is not None and not 0.0 <= self.p_expansion <= 1.0:
            raise ValueError("p_expansion must be in [0, 1]")
        if self.verifier_decision is not None and self.verifier_decision not in {
            "RE-STEER",
            "EXPANSION",
        }:
            raise ValueError("verifier_decision must be RE-STEER or EXPANSION")
        if self.verifier_logits is not None:
            if len(self.verifier_logits) != 2 or not all(
                math.isfinite(float(value)) for value in self.verifier_logits
            ):
                raise ValueError("verifier_logits must contain two finite values")
        if self.decision_rule == "head_argmax":
            if self.verifier_decision is None or self.verifier_logits is None:
                raise ValueError("head_argmax decisions require logits and a direct class")
            expected = (
                "EXPANSION"
                if float(self.verifier_logits[1]) > float(self.verifier_logits[0])
                else "RE-STEER"
            )
            if self.verifier_decision != expected:
                raise ValueError("verifier_decision does not match head argmax")
        if not 0.0 < self.behavior_propensity <= 1.0:
            raise ValueError("behavior_propensity must be in (0, 1]")


@dataclass(frozen=True)
class VerifierLabelRecord:
    record_id: str
    label_version: str
    source: str
    branches: int
    successes: int
    p_expansion: float
    policy_id: str
    snapshot_hash: str
    # Counterfactual replay under a new policy produces a different fresh-mode
    # feature vector.  In that case the label must point at that policy-specific
    # pre-decision sidecar instead of silently reusing the old decision feature.
    verifier_feature_path: str = ""
    data_split: str | None = None
    weak: bool = False
    weight: float = 1.0
    behavior_propensity: float | None = None
    labeled_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.branches <= 0 or not 0 <= self.successes <= self.branches:
            raise ValueError("invalid counterfactual branch counts")
        expected = 1.0 - self.successes / self.branches
        if abs(self.p_expansion - expected) > 1e-9:
            raise ValueError("p_expansion must equal 1 - successes/branches")
        if self.source == "demo_match" and not self.weak:
            raise ValueError("demo_match labels must be weak")
        if self.source == "post_expansion_recheck":
            raise ValueError("post-expansion recheck is remedy evidence, not a verifier label")
        if self.weight <= 0:
            raise ValueError("label weight must be positive")
        if self.behavior_propensity is not None and not 0 < self.behavior_propensity <= 1:
            raise ValueError("behavior propensity must be in (0, 1]")
        if self.data_split is not None and self.data_split not in {
            "train",
            "calibration",
            "test",
        }:
            raise ValueError("data_split must be train, calibration, or test")


@dataclass(frozen=True)
class CapabilitySignatureRecord:
    signature_id: str
    suite: str
    task_id: str
    perturbation_variant: str
    failure_mode: str
    e_goal_path: str
    e_obs_path: str
    policy_id: str
    alpha_l: float
    validated: bool
    trigger_recheck_passed: bool
    regression_passed: bool
    delta_id: str = ""
    ticket_id: str = ""
    recorded_at: str = field(default_factory=_now)


class IncidentMemory:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.decisions = AtomicJsonl(self.root / "verifier_decisions.jsonl")
        self.labels = AtomicJsonl(self.root / "verifier_labels.jsonl")
        self.signatures = AtomicJsonl(self.root / "capability_signatures.jsonl")

    def record_decision(self, record: VerifierDecisionRecord) -> bool:
        value = {"event": "DECISION_RECORDED", **asdict(record)}
        value["event_id"] = f"decision:{record.record_id}"
        return self.decisions.append(value)

    def attach_label(self, record: VerifierLabelRecord) -> bool:
        if not any(
            item.get("record_id") == record.record_id
            for item in self.decisions.iter_valid()
        ):
            raise KeyError(f"unknown verifier decision {record.record_id}")
        value = {"event": "LABEL_ATTACHED", **asdict(record)}
        value["event_id"] = hashlib.sha256(
            f"{record.record_id}\0{record.label_version}\0{record.source}\0"
            f"{record.policy_id}\0{record.snapshot_hash}".encode()
        ).hexdigest()
        return self.labels.append(value)

    def record_signature(self, record: CapabilitySignatureRecord) -> bool:
        value = {"event": "REMEDY_VALIDATED", **asdict(record)}
        value["event_id"] = f"signature:{record.signature_id}:{record.policy_id}"
        return self.signatures.append(value)

    def joined_training_rows(self, *, include_weak: bool = True) -> list[dict[str, Any]]:
        decisions = {
            item["record_id"]: item for item in self.decisions.iter_valid()
        }
        rows = []
        seen_versions: set[tuple[str, str, str, str]] = set()
        for label in self.labels.iter_valid():
            if label.get("weak", False) and not include_weak:
                continue
            key = (
                label["record_id"],
                label["label_version"],
                label["source"],
                label["policy_id"],
            )
            if key in seen_versions:
                raise ValueError(f"duplicate logical label version: {key}")
            seen_versions.add(key)
            decision = decisions.get(label["record_id"])
            if decision is None:
                raise ValueError(f"orphan label for {label['record_id']}")
            rows.append({"decision": decision, "label": label})
        return rows

    def orphan_sidecars(self) -> list[Path]:
        referenced = {
            str(Path(value).resolve())
            for item in self.decisions.iter_valid()
            for value in (
                item.get("scene_feature_path"),
                item.get("verifier_feature_path"),
            )
            if value
        }
        sidecar_root = self.root / "sidecars"
        if not sidecar_root.exists():
            return []
        return [
            path
            for path in sidecar_root.rglob("*")
            if path.is_file() and str(path.resolve()) not in referenced
        ]


__all__ = [
    "CapabilitySignatureRecord",
    "IncidentMemory",
    "VerifierDecisionRecord",
    "VerifierLabelRecord",
]
