"""Policy-stable verifier refresh after 200 new labels or calibration drift."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .incidents import IncidentMemory
from .io_utils import atomic_write_json
from .registry import ActiveDeployment, PolicyRegistry
from .verifier import DeployedVerifierPredictor, load_verifier_input
from .verifier_training import (
    VerifierExample,
    VerifierTrainingConfig,
    build_verifier_examples,
    train_verifier_ablations,
)


@dataclass(frozen=True)
class VerifierRefreshStatus:
    due: bool
    reasons: tuple[str, ...]
    current_strong_contexts: int
    last_attempted_contexts: int
    brier_drift: float | None


def verifier_refresh_status(
    *,
    current_strong_contexts: int,
    last_attempted_contexts: int,
    has_active_verifier: bool,
    brier_drift: float | None,
    minimum_cold_start_contexts: int = 1700,
    increment: int = 200,
    brier_drift_threshold: float = 0.02,
) -> VerifierRefreshStatus:
    if min(current_strong_contexts, last_attempted_contexts) < 0:
        raise ValueError("verifier context counts must be non-negative")
    if increment <= 0 or minimum_cold_start_contexts <= 0:
        raise ValueError("verifier refresh thresholds must be positive")
    reasons = []
    if not has_active_verifier:
        if (
            current_strong_contexts >= minimum_cold_start_contexts
            and current_strong_contexts - last_attempted_contexts >= increment
        ):
            reasons.append("cold_start_evidence_ready")
    elif current_strong_contexts - last_attempted_contexts >= increment:
        reasons.append("at_least_200_new_labeled_contexts")
    if brier_drift is not None and brier_drift > brier_drift_threshold:
        reasons.append("brier_drift_exceeded_threshold")
    return VerifierRefreshStatus(
        due=bool(reasons),
        reasons=tuple(reasons),
        current_strong_contexts=int(current_strong_contexts),
        last_attempted_contexts=int(last_attempted_contexts),
        brier_drift=None if brier_drift is None else float(brier_drift),
    )


class VerifierRefreshCoordinator:
    """Retrain a verifier without rerunning the already-passed policy gate."""

    def __init__(
        self,
        *,
        registry: PolicyRegistry,
        incidents: IncidentMemory,
        output_root: Path,
        config: VerifierTrainingConfig = VerifierTrainingConfig(device="cpu"),
        brier_drift_threshold: float = 0.02,
    ) -> None:
        self.registry = registry
        self.incidents = incidents
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.brier_drift_threshold = float(brier_drift_threshold)

    @property
    def state_path(self) -> Path:
        return self.output_root / "refresh_state.json"

    def run(self) -> dict[str, Any]:
        active = self.registry.active()
        if active is None:
            raise RuntimeError("cannot refresh verifier before a policy is active")
        try:
            examples = tuple(
                build_verifier_examples(
                    self.incidents,
                    policy_id=active.policy_id,
                )
            )
        except ValueError as exc:
            return {
                "schema_version": "verifier-refresh-result-v1",
                "policy_id": active.policy_id,
                "deployment_revision": active.deployment_revision,
                "refreshed": False,
                "status": {
                    "due": False,
                    "reasons": [f"no_refreshable_evidence: {exc}"],
                    "current_strong_contexts": 0,
                    "last_attempted_contexts": 0,
                    "brier_drift": None,
                },
            }
        strong_count = len({item.record_id for item in examples if not item.weak})
        state = self._state(active)
        drift = self._brier_drift(active, examples)
        status = verifier_refresh_status(
            current_strong_contexts=strong_count,
            last_attempted_contexts=int(state.get("last_attempted_contexts", 0)),
            has_active_verifier=active.verifier_id is not None,
            brier_drift=drift,
            brier_drift_threshold=self.brier_drift_threshold,
        )
        if not status.due:
            return {
                "schema_version": "verifier-refresh-result-v1",
                "policy_id": active.policy_id,
                "deployment_revision": active.deployment_revision,
                "refreshed": False,
                "status": asdict(status),
            }

        ablation = train_verifier_ablations(
            examples,
            policy_id=active.policy_id,
            output_root=self.output_root / "ablations",
            config=self.config,
            metadata={
                "experiment_role": "policy_stable_verifier_refresh",
                "source_deployment_revision": active.deployment_revision,
                "refresh_reasons": list(status.reasons),
            },
        )
        selected_name = ablation.selected_channel_set
        next_deployment = active
        if selected_name is not None:
            selected = ablation.results[selected_name]
            self.registry.install_artifact(
                "verifier", selected.verifier_id, Path(selected.artifact_root)
            )
            next_deployment = self.registry.promote(
                policy_id=active.policy_id,
                verifier_id=selected.verifier_id,
                controller_mode="learned_verifier",
                manifest_hash=active.manifest_hash,
                expected_revision=active.deployment_revision,
                reason="verifier_refresh_without_policy_regression_rerun",
            )
        next_state = {
            "schema_version": "verifier-refresh-state-v1",
            "policy_id": active.policy_id,
            "last_attempted_contexts": strong_count,
            "last_dataset_hash": ablation.dataset_hash,
            "last_ablation_report_path": ablation.report_path,
            "selected_channel_set": selected_name,
            "deployment_revision": next_deployment.deployment_revision,
        }
        atomic_write_json(self.state_path, next_state)
        result = {
            "schema_version": "verifier-refresh-result-v1",
            "policy_id": active.policy_id,
            "source_deployment_revision": active.deployment_revision,
            "deployment_revision": next_deployment.deployment_revision,
            "refreshed": selected_name is not None,
            "status": asdict(status),
            "selected_channel_set": selected_name,
            "controller_mode": next_deployment.controller_mode,
            "verifier_id": next_deployment.verifier_id,
            "ablation_report_path": ablation.report_path,
        }
        report_id = hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        atomic_write_json(self.output_root / f"refresh_{report_id}.json", result)
        return result

    def _state(self, active: ActiveDeployment) -> Mapping[str, Any]:
        if not self.state_path.is_file():
            trained_count = self._active_trained_count(active)
            return {
                "policy_id": active.policy_id,
                "last_attempted_contexts": trained_count,
            }
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if value.get("policy_id") != active.policy_id:
            return {"policy_id": active.policy_id, "last_attempted_contexts": 0}
        return value

    def _active_trained_count(self, active: ActiveDeployment) -> int:
        if active.verifier_id is None:
            return 0
        manifest = self._active_verifier_manifest(active)
        counts = manifest.get("metadata", {}).get("metrics", {}).get(
            "split_counts", {}
        )
        return int(
            sum(
                int(counts.get(split, {}).get("strong_contexts", 0))
                for split in ("train", "calibration", "test")
            )
        )

    def _active_verifier_manifest(self, active: ActiveDeployment) -> Mapping[str, Any]:
        if active.verifier_id is None:
            raise ValueError("active deployment has no verifier")
        path = self.registry.root / "verifiers" / active.verifier_id / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _brier_drift(
        self,
        active: ActiveDeployment,
        examples: Sequence[VerifierExample],
    ) -> float | None:
        if active.verifier_id is None:
            return None
        test = tuple(item for item in examples if item.split == "test" and not item.weak)
        if not test:
            return None
        artifact = self.registry.root / "verifiers" / active.verifier_id
        predictor = DeployedVerifierPredictor(artifact)
        probabilities = predictor.predict_probabilities(
            [load_verifier_input(Path(item.feature_path)) for item in test]
        )
        squared_error = 0.0
        outcomes = 0
        for item, probability in zip(test, probabilities):
            squared_error += item.failures * (1.0 - float(probability)) ** 2
            squared_error += item.successes * float(probability) ** 2
            outcomes += item.trials
        current_brier = squared_error / outcomes
        reference = self._active_verifier_manifest(active).get("metadata", {}).get(
            "metrics", {}
        )
        if "brier" not in reference:
            return None
        return float(current_brier) - float(reference["brier"])


__all__ = [
    "VerifierRefreshCoordinator",
    "VerifierRefreshStatus",
    "verifier_refresh_status",
]
