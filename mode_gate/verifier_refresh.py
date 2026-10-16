"""Policy-stable refresh whose data selection, timing and acceptance belong to Planner."""
from dataclasses import asdict
import json
from pathlib import Path
from .experience_planner import ExperiencePlanner
from .io_utils import atomic_write_json
from .verifier_training import (VerifierTrainingConfig, continue_from_active_verifier,
                               build_verifier_examples, train_verifier, record_verifier_training_usage,
                               selected_feedback_usage)

class VerifierRefreshCoordinator:
    def __init__(self, *, registry, incidents, output_root, config=VerifierTrainingConfig(), planner=None,
                 allowed_task_keys=()):
        self.registry, self.incidents = registry, incidents
        self.output_root, self.config = Path(output_root), config
        self.planner = planner or ExperiencePlanner(incidents)
        self.allowed_task_keys = tuple(allowed_task_keys)

    def train_for_policy(self, policy_id, *, current=None, selection=None):
        from .verifier_feedback import publish_verifier_feedback
        feedback = publish_verifier_feedback(self.incidents)
        self.output_root.mkdir(parents=True, exist_ok=True)
        selection_path = self.output_root / "planner_selection.json"
        if selection is None and selection_path.is_file():
            selection = json.loads(selection_path.read_text())
        if selection is None:
            selection = self.planner.run(purpose="verifier_training", current={
                **(current or {"policy_id":policy_id}),
                "observed_verifier_feedback": {k:feedback[k] for k in ("schema_version", "ledger_path", "counts")}})
        atomic_write_json(selection_path, selection)
        request = selection.get("training_request")
        if request is None:
            return None
        config_values = asdict(continue_from_active_verifier(self.config, self.registry))
        allowed = {"learning_rate", "weight_decay", "batch_size", "max_epochs", "patience", "seed"}
        if config_values["channel_set"] != "full":
            raise ValueError("online verifier must keep scene, all candidates and history inputs")
        if set(request.get("config", {})) - allowed:
            raise ValueError("Planner may configure small-head training, not change input/budget/backbone contracts")
        config_values.update(request.get("config", {}))
        examples = build_verifier_examples(self.incidents, policy_id=policy_id, request=request,
                                          allowed_task_keys=self.allowed_task_keys)
        result = train_verifier(examples, policy_id=policy_id, output_root=self.output_root,
                                config=VerifierTrainingConfig(**config_values), reviewer=self.planner.review_head,
                                metadata={"planner_retrain_request":request,
                                          "observed_feedback":selected_feedback_usage(self.incidents, examples),
                                          "allowed_task_keys":list(self.allowed_task_keys)})
        record_verifier_training_usage(self.incidents, result, examples, request_id=request["event_id"])
        return result

    def run(self, *, current=None):
        completed = self.output_root / "refresh_result.json"
        if completed.is_file():
            return json.loads(completed.read_text())
        active = self.registry.active()
        if active is None:
            raise RuntimeError("no active policy for verifier refresh")
        result = self.train_for_policy(active.policy_id, current={"active_policy":asdict(active), **(current or {}),
            "allowed_task_keys":list(self.allowed_task_keys)})
        refreshed = bool(result and result.gate.passed)
        revision = active.deployment_revision
        if refreshed:
            self.registry.install_artifact("verifier", result.verifier_id, Path(result.artifact_root))
            deployment = self.registry.promote(policy_id=active.policy_id, verifier_id=result.verifier_id,
                controller_mode="learned_verifier", manifest_hash=active.manifest_hash,
                expected_revision=revision, reason="Planner independent-experience verifier review")
            revision = deployment.deployment_revision
        report = {"schema_version":"verifier-refresh-result-v3", "policy_id":active.policy_id,
                  "source_deployment_revision":active.deployment_revision, "deployment_revision":revision,
                  "refreshed":refreshed, "result":asdict(result) if result else None,
                  "reason":"Planner-selected retrain" if result else "Planner chose not to retrain yet"}
        atomic_write_json(self.output_root / "refresh_result.json", report)
        return report
