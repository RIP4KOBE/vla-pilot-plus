"""Frozen verifier-audit collection and replay-plan orchestration on hgpu1."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Mapping, Sequence

from .checkpoint_math import checkpoint_digest
from .counterfactual import REPLAY_PROGRESS_CONTRACT
from .evaluation import EpisodeLedger
from .experiment_contract import (
    FIXED_BUDGET_50_CONTRACT,
    label_contract_payload,
    regenerate_budget_state,
)
from .incidents import IncidentMemory
from .io_utils import AtomicJsonl, atomic_write_json, sha256_file
from .policy_evaluator import EvaluationContext, RawEpisodeResult, runtime_suite_name
from .preflight import source_revision
from .registry import PolicyRegistry


LOGGER = logging.getLogger(__name__)


AUDIT_SPLITS = (
    "verifier_audit_train",
    "verifier_calibration",
    "verifier_test",
)


@dataclass(frozen=True)
class AuditContext:
    evaluation: EvaluationContext
    verifier_split: str

    @property
    def episode_key(self) -> str:
        return hashlib.sha256(
            f"audit-episode-v1\0{self.verifier_split}\0{self.evaluation.episode_key}".encode()
        ).hexdigest()


def audit_contexts_from_manifest(
    manifest: Mapping[str, Any],
    *,
    limit: int | None = None,
) -> tuple[AuditContext, ...]:
    """Materialize the available verifier banks without final-seal access."""

    if manifest.get("schema_version") != "joint-eval-manifest-v1":
        raise ValueError("audit collection requires the frozen joint manifest")
    split_names = {
        "verifier_audit_train": "train",
        "verifier_calibration": "calibration",
        "verifier_test": "test",
    }
    values_by_task: list[list[AuditContext]] = []
    for task in sorted(manifest["tasks"], key=lambda item: item["task_key"]):
        task_values: list[AuditContext] = []
        for source_split in AUDIT_SPLITS:
            for init_state in task["splits"][source_split]:
                material = (
                    f"verifier-audit-v1\0{manifest['manifest_sha256']}\0"
                    f"{source_split}\0{task['task_key']}\0{init_state}"
                )
                digest = hashlib.sha256(material.encode()).digest()
                task_values.append(
                    AuditContext(
                        evaluation=EvaluationContext(
                            suite=str(task["suite"]),
                            task_id=str(task["task_id"]),
                            task_index=int(task["task_index"]),
                            perturbation_variant=str(task["perturbation_variant"]),
                            init_state_id=str(init_state),
                            env_seed=int.from_bytes(digest[:4], "big"),
                            policy_seed=int.from_bytes(digest[4:12], "big")
                            % (2**63 - 1),
                        ),
                        verifier_split=split_names[source_split],
                    )
                )
        task_values.sort(
            key=lambda item: hashlib.sha256(
                (
                    f"audit-within-task-v2\0{manifest['manifest_sha256']}\0"
                    f"{item.episode_key}"
                ).encode()
            ).digest()
        )
        values_by_task.append(task_values)
    values = [
        task_values[index]
        for index in range(max(map(len, values_by_task), default=0))
        for task_values in values_by_task
        if index < len(task_values)
    ]
    if not values:
        raise ValueError("verifier audit manifest has no available contexts")
    # Round-robin makes every prefix of 40 cover all LIBERO-PRO tasks.  Later
    # passes add depth without making per-task significance a collection gate.
    ranked = values
    first_pass_tasks = {
        (
            item.evaluation.suite,
            item.evaluation.task_id,
            item.evaluation.perturbation_variant,
        )
        for item in ranked[:40]
    }
    if len(first_pass_tasks) != len(manifest["tasks"]):
        raise ValueError("audit breadth-first pass does not cover every task")
    if limit is not None:
        if not 1 <= int(limit) <= len(ranked):
            raise ValueError(
                f"audit collection limit must be in [1, {len(ranked)}]"
            )
        ranked = ranked[: int(limit)]
    return tuple(ranked)


class HydraAuditEpisodeExecutor:
    """One fail-closed full-controller audit episode in an isolated artifact root."""

    def __init__(
        self,
        *,
        repo_root: Path,
        python_executable: Path,
        registry_root: Path,
        incident_root: Path,
        snapshot_root: Path,
        slow_loop_root: Path,
        output_root: Path,
        use_guidance: bool = True,
        timeout_seconds: float = 3600.0,
        gpu_index: int = 6,
        code_revision: str | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_executable = Path(python_executable).resolve()
        self.registry_root = Path(registry_root).resolve()
        self.incident_root = Path(incident_root).resolve()
        self.snapshot_root = Path(snapshot_root).resolve()
        self.slow_loop_root = Path(slow_loop_root).resolve()
        self.output_root = Path(output_root).resolve()
        self.use_guidance = bool(use_guidance)
        self.timeout_seconds = float(timeout_seconds)
        self.gpu_index = int(gpu_index)
        self.code_revision = str(code_revision or source_revision(self.repo_root))
        if not 0 <= self.gpu_index <= 7:
            raise ValueError("audit GPU index must be in [0, 7]")

    def __call__(self, policy_id: str, context: AuditContext) -> RawEpisodeResult:
        evaluation = context.evaluation
        runtime_suite = runtime_suite_name(
            evaluation.suite, evaluation.perturbation_variant
        )
        context_root = self.output_root / policy_id / context.episode_key
        run_dir = _allocate_attempt_dir(context_root)
        command = [
            str(self.python_executable),
            "rsi/main.py",
            "backend=libero",
            f"backend.libero.suite_name={runtime_suite}",
            f"backend.libero.task_ids_filter=[{evaluation.task_index}]",
            "main.episode_num=1",
            f"main.init_state_id={evaluation.init_state_id}",
            f"main.env_seed={evaluation.env_seed}",
            f"main.policy_seed={evaluation.policy_seed}",
            "main.fail_on_episode_error=true",
            f"main.use_guidance={'true' if self.use_guidance else 'false'}",
            # The controller consumes observed_stage_id from the same frozen
            # Gemini Robotics semantic-planner call.  Formal audit must not
            # issue a second legacy Gemini stage-recognition request.
            "main.use_vlm_stage_recognition=false",
            # LIBERO-PRO exposes simulator instance segmentation, so the
            # legacy visual-grounding provider is neither needed nor allowed
            # in the formal protocol.
            "perception.gemini_grounding.enabled=false",
            "mode_gate.enabled=true",
            # Audit collects counterfactual labels only; it must never open a
            # human-demo ticket or launch an operator-facing service.
            "mode_gate.auto_start_expansion_worker=false",
            "mode_gate.controller_mode=fixed_budget_50",
            "mode_gate.retry_budget=50",
            "mode_gate.label_version=fixed_budget_50-v2",
            "mode_gate.baseline_kind=fixed_budget",
            "mode_gate.baseline_budget=10",
            "mode_gate.verifier_thinking_level=medium",
            "perception.gemini.thinking_level=ultra",
            "mode_gate.planner_max_provider_calls=10000",
            "mode_gate.planner_call_ledger="
            + str(
                self.incident_root
                / "fixed_budget_50"
                / "factual_gemini_provider_calls.jsonl"
            ),
            f"device=cuda:{self.gpu_index}",
            f"mode_gate.registry_root={self.registry_root}",
            f"mode_gate.incident_root={self.incident_root}",
            f"mode_gate.snapshot_root={self.snapshot_root}",
            f"mode_gate.slow_loop_root={self.slow_loop_root}",
            f"hydra.run.dir={run_dir}",
        ]
        attempt_record = {
            "schema_version": "verifier-audit-attempt-v1",
            "status": "PREPARED",
            "policy_id": policy_id,
            "episode_key": context.episode_key,
            "verifier_split": context.verifier_split,
            "evaluation": asdict(evaluation),
            "runtime_suite": runtime_suite,
            "code_revision": self.code_revision,
            "label_version": FIXED_BUDGET_50_CONTRACT.label_version,
            "label_config": label_contract_payload(FIXED_BUDGET_50_CONTRACT),
            "command": command,
        }
        atomic_write_json(run_dir / "attempt.json", attempt_record)
        environment = dict(os.environ)
        environment.update(
            {
                "PYOPENGL_PLATFORM": "egl",
                "MUJOCO_GL": "egl",
                "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            }
        )
        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            (run_dir / "executor.log").write_text(output, encoding="utf-8")
            atomic_write_json(
                run_dir / "attempt.json",
                {
                    **attempt_record,
                    "status": "RETRYABLE_ERROR",
                    "error": "episode_timeout",
                },
            )
            raise RuntimeError(f"audit episode timed out; see {run_dir}") from exc
        (run_dir / "executor.log").write_text(completed.stdout, encoding="utf-8")
        if completed.returncode:
            atomic_write_json(
                run_dir / "attempt.json",
                {
                    **attempt_record,
                    "status": "RETRYABLE_ERROR",
                    "returncode": completed.returncode,
                },
            )
            raise RuntimeError(
                f"audit episode exited {completed.returncode}; see {run_dir / 'executor.log'}"
            )
        result_path = run_dir / "results.txt"
        if not result_path.is_file():
            atomic_write_json(
                run_dir / "attempt.json",
                {
                    **attempt_record,
                    "status": "RETRYABLE_ERROR",
                    "error": "missing_results",
                },
            )
            raise RuntimeError("audit episode produced no results.txt")
        error_markers = sorted(run_dir.glob("episode_*/episode_*_fail_error.txt"))
        if error_markers:
            atomic_write_json(
                run_dir / "attempt.json",
                {
                    **attempt_record,
                    "status": "RETRYABLE_ERROR",
                    "error": "invalid_episode",
                    "error_markers": [str(path) for path in error_markers],
                },
            )
            raise RuntimeError(
                f"audit episode was invalid; see {error_markers[0]}"
            )
        matches = re.findall(
            r"Success count:\s*(\d+)\s*/\s*(\d+)",
            result_path.read_text(encoding="utf-8"),
        )
        if not matches or matches[-1][1] != "1":
            atomic_write_json(
                run_dir / "attempt.json",
                {
                    **attempt_record,
                    "status": "RETRYABLE_ERROR",
                    "error": "invalid_results",
                },
            )
            raise RuntimeError("cannot parse one-episode audit result")
        success = matches[-1][0] == "1"
        atomic_write_json(
            run_dir / "attempt.json",
            {
                **attempt_record,
                "status": "COMMITTED",
                "returncode": completed.returncode,
                "success": success,
            },
        )
        return RawEpisodeResult(
            success=success,
            output_dir=str(run_dir),
            metadata={
                "runtime_suite": runtime_suite,
                "verifier_split": context.verifier_split,
            },
        )


def _allocate_attempt_dir(context_root: Path) -> Path:
    attempts_root = Path(context_root) / "attempts"
    attempts_root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 1_000_000):
        candidate = attempts_root / f"attempt_{index:06d}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"audit attempt space exhausted: {attempts_root}")


def invalidate_audit_attempt(
    attempt_dir: Path,
    *,
    reason: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a correction and mark a previously committed invalid attempt."""

    attempt_dir = Path(attempt_dir).resolve()
    attempt_path = attempt_dir / "attempt.json"
    value = json.loads(attempt_path.read_text(encoding="utf-8"))
    if not reason:
        raise ValueError("attempt invalidation requires a reason")
    material = json.dumps(
        {
            "attempt_dir": str(attempt_dir),
            "reason": reason,
            "evidence": dict(evidence or {}),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    event = {
        "event_id": "attempt-invalidated-" + hashlib.sha256(material.encode()).hexdigest(),
        "event_type": "ATTEMPT_INVALIDATED",
        "attempt_dir": str(attempt_dir),
        "episode_key": str(value["episode_key"]),
        "previous_status": str(value.get("status", "UNKNOWN")),
        "reason": reason,
        "evidence": dict(evidence or {}),
    }
    context_root = attempt_dir.parent.parent
    AtomicJsonl(context_root / "attempt_corrections.jsonl").append(event)
    atomic_write_json(
        attempt_path,
        {
            **value,
            "status": "RETRYABLE_ERROR",
            "error": reason,
            "invalidation_event_id": event["event_id"],
        },
    )
    return event


class AuditCollectionCoordinator:
    def __init__(
        self,
        *,
        manifest: Mapping[str, Any],
        registry: PolicyRegistry,
        incidents: IncidentMemory,
        snapshot_root: Path,
        executor: HydraAuditEpisodeExecutor,
        ledger_path: Path,
        output_path: Path,
        replay_plan_path: Path,
        preflight_path: Path | None = None,
        max_workers: int = 1,
        replay_gpu_index: int = 6,
        continue_on_retryable_error: bool = False,
    ) -> None:
        self.manifest = dict(manifest)
        self.registry = registry
        self.incidents = incidents
        self.snapshot_root = Path(snapshot_root).resolve()
        self.executor = executor
        self.ledger = EpisodeLedger(Path(ledger_path))
        self.output_path = Path(output_path)
        self.replay_plan_path = Path(replay_plan_path)
        self.preflight_path = (
            Path(preflight_path).resolve() if preflight_path is not None else None
        )
        self.preflight_sha256 = (
            sha256_file(self.preflight_path) if self.preflight_path is not None else ""
        )
        self.preflight_code_revision = ""
        executor_revision = getattr(executor, "code_revision", None)
        self.code_revision = str(
            executor_revision or source_revision(Path(executor.repo_root))
        )
        self.max_workers = int(max_workers)
        self.replay_gpu_index = int(replay_gpu_index)
        self.continue_on_retryable_error = bool(continue_on_retryable_error)
        if self.max_workers <= 0:
            raise ValueError("audit max_workers must be positive")
        if not 0 <= self.replay_gpu_index <= 7:
            raise ValueError("audit replay GPU index must be in [0, 7]")

    def run(self, *, limit: int | None = None) -> dict[str, Any]:
        self._validate_preflight()
        active = self.registry.active()
        if active is None or active.manifest_hash != self.manifest["manifest_sha256"]:
            raise RuntimeError("audit requires an active policy on the frozen manifest")
        available_context_count = len(audit_contexts_from_manifest(self.manifest))
        contexts = audit_contexts_from_manifest(self.manifest, limit=limit)
        completed = self.ledger.completed_for(
            policy_id=active.policy_id,
            manifest_hash=active.manifest_hash,
            label_version=FIXED_BUDGET_50_CONTRACT.label_version,
            label_contract_hash=FIXED_BUDGET_50_CONTRACT.contract_hash,
        )
        pending = [item for item in contexts if item.episode_key not in completed]

        def execute(item: AuditContext) -> tuple[AuditContext, RawEpisodeResult]:
            return item, self.executor(active.policy_id, item)

        def commit(item: AuditContext, result: RawEpisodeResult) -> None:
            # Formal audit is a long-running, fail-closed job.  Persist every
            # valid episode before starting/awaiting the next one so a host,
            # provider, or worker interruption resumes from the exact frozen
            # context boundary instead of replaying an in-memory batch.
            self.ledger.append(
                item.episode_key,
                {
                    "policy_id": active.policy_id,
                    "manifest_hash": active.manifest_hash,
                    "code_revision": self.code_revision,
                    "label_version": FIXED_BUDGET_50_CONTRACT.label_version,
                    "label_contract_hash": FIXED_BUDGET_50_CONTRACT.contract_hash,
                    "label_config": label_contract_payload(
                        FIXED_BUDGET_50_CONTRACT
                    ),
                    "verifier_split": item.verifier_split,
                    "context": asdict(item.evaluation),
                    "success": result.success,
                    "output_dir": result.output_dir,
                    "metadata": dict(result.metadata),
                },
            )

        if self.max_workers == 1:
            retry_round = 0
            current_round = list(pending)
            while current_round:
                retryable: list[AuditContext] = []
                committed_this_round = 0
                for item in current_round:
                    try:
                        completed_item, result = execute(item)
                    except RuntimeError as exc:
                        if not self.continue_on_retryable_error:
                            raise
                        retryable.append(item)
                        LOGGER.warning(
                            "Audit context %s ended in RETRYABLE_ERROR; deferring it "
                            "until the remaining breadth-first contexts have run: %s",
                            item.episode_key,
                            exc,
                        )
                        continue
                    commit(completed_item, result)
                    committed_this_round += 1

                if not retryable:
                    break
                retry_round += 1
                if committed_this_round == 0:
                    delay = min(60.0, 10.0 * (2 ** min(retry_round - 1, 3)))
                    LOGGER.warning(
                        "All %d remaining audit contexts were retryable in round %d; "
                        "keeping the coordinator alive and retrying in %.0f seconds",
                        len(retryable),
                        retry_round,
                        delay,
                    )
                    time.sleep(delay)
                current_round = retryable
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = [pool.submit(execute, item) for item in pending]
                for future in as_completed(futures):
                    item, result = future.result()
                    commit(item, result)

        context_cells = {
            (
                item.evaluation.suite,
                item.evaluation.task_id,
                item.evaluation.perturbation_variant,
                item.evaluation.init_state_id,
            ): item.verifier_split
            for item in contexts
        }
        decisions = []
        excluded_forced_expansion = 0
        for decision in self.incidents.decisions.iter_valid():
            group = decision.get("provenance", {}).get("group", {})
            cell = (
                str(group.get("suite") or ""),
                str(group.get("task_id") or ""),
                str(group.get("perturbation_variant") or ""),
                str(group.get("init_state_id") or ""),
            )
            split = context_cells.get(cell)
            if split is None or str(decision.get("policy_id")) != active.policy_id:
                continue
            if (
                str(decision.get("label_version"))
                != FIXED_BUDGET_50_CONTRACT.label_version
                or int(decision.get("retry_budget", -1))
                != FIXED_BUDGET_50_CONTRACT.retry_budget
            ):
                continue
            snapshot_id = str(decision["snapshot_id"])
            snapshot_manifest = self.snapshot_root / snapshot_id / "manifest.json"
            if not snapshot_manifest.is_file():
                raise FileNotFoundError(snapshot_manifest)
            manifest_value = json.loads(
                snapshot_manifest.read_text(encoding="utf-8")
            )
            budget_state = regenerate_budget_state(
                dict(manifest_value.get("controller_state") or {}),
                contract=FIXED_BUDGET_50_CONTRACT,
            )
            if int(budget_state["remaining_budget"]) <= 0:
                excluded_forced_expansion += 1
                continue
            task_key = "::".join(cell[:3])
            decisions.append(
                {
                    "record_id": str(decision["record_id"]),
                    "origin_policy_id": active.policy_id,
                    "target_policy_id": active.policy_id,
                    "snapshot_id": snapshot_id,
                    "snapshot_hash": str(decision["snapshot_hash"]),
                    "snapshot_manifest_path": str(snapshot_manifest.resolve()),
                    "label_version": FIXED_BUDGET_50_CONTRACT.label_version,
                    "budget_state": budget_state,
                    "data_split": split,
                    "task_key": task_key,
                    "selection_score": decision.get("p_expansion"),
                    "observed_route": str(decision.get("route") or ""),
                    "fresh_feature_output_path": str(
                        (
                            self.replay_plan_path.parent
                            / "fixed_budget_50"
                            / "features"
                            / f"{decision['record_id']}.npz"
                        ).resolve()
                    ),
                }
            )
        all_decisions = sorted(decisions, key=lambda value: value["record_id"])
        decisions = _targeted_replay_contexts(
            all_decisions,
            limit=FIXED_BUDGET_50_CONTRACT.counterfactual_context_limit,
        )
        checkpoint = self.registry.root / "policies" / active.policy_id
        replay_result = (
            self.replay_plan_path.parent
            / "fixed_budget_50"
            / "replay_result.json"
        )
        plan = {
            "schema_version": "new-policy-counterfactual-plan-v3",
            "job_id": "verifier-audit-" + active.policy_id,
            "policy_id": active.policy_id,
            "code_revision": self.code_revision,
            "preflight_path": str(self.preflight_path or ""),
            "preflight_sha256": self.preflight_sha256,
            "preflight_code_revision": self.preflight_code_revision,
            "code_changed_since_preflight": bool(
                self.preflight_code_revision
                and self.preflight_code_revision != self.code_revision
            ),
            "checkpoint_path": str(checkpoint.resolve()),
            "checkpoint_digest": checkpoint_digest(checkpoint),
            "snapshot_root": str(self.snapshot_root),
            "incident_root": str(self.incidents.root.resolve()),
            "label_version": FIXED_BUDGET_50_CONTRACT.label_version,
            "label_config": label_contract_payload(FIXED_BUDGET_50_CONTRACT),
            "suggested_data_targets": {
                "train": FIXED_BUDGET_50_CONTRACT.suggested_train_contexts,
                "calibration": (
                    FIXED_BUDGET_50_CONTRACT.suggested_calibration_contexts
                ),
                "test": FIXED_BUDGET_50_CONTRACT.suggested_test_contexts,
                "hard_gate": False,
            },
            "retry_estimand": (
                "P(fail to advance/succeed under remaining fixed_budget_50 "
                "RE-STEER schedule)"
            ),
            "adaptive_branches": [16, 32],
            "decision_rule": "head_argmax",
            "progress_contract": REPLAY_PROGRESS_CONTRACT,
            "gemini_max_provider_calls": (
                FIXED_BUDGET_50_CONTRACT.counterfactual_provider_call_limit
            ),
            "gemini_call_ledger_path": str(
                (
                    self.incidents.root
                    / "fixed_budget_50"
                    / "counterfactual_gemini_provider_calls.jsonl"
                ).resolve()
            ),
            "branch_ledger_path": str(
                (
                    self.replay_plan_path.parent
                    / "fixed_budget_50"
                    / "branches.jsonl"
                ).resolve()
            ),
            "factual_contexts": all_decisions,
            "contexts": decisions,
            "result_path": str(replay_result.resolve()),
        }
        canonical = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
        plan["plan_sha256"] = hashlib.sha256(canonical).hexdigest()
        atomic_write_json(self.replay_plan_path, plan)
        replay_job_path = self.replay_plan_path.parent / "replay_job.json"
        atomic_write_json(
            replay_job_path,
            {
                "schema_version": "counterfactual-replay-job-v2",
                "job_id": plan["job_id"],
                "plan_sha256": plan["plan_sha256"],
                "preferred_gpu_index": self.replay_gpu_index,
                "minimum_free_gib": 45.0,
                "cwd": str(self.executor.repo_root),
                "command": [
                    str(self.executor.python_executable),
                    str(self.executor.repo_root / "scripts/self_improve.py"),
                    "replay-new-policy",
                    "--plan",
                    str(self.replay_plan_path.resolve()),
                    "--repo-root",
                    str(self.executor.repo_root),
                    "--device",
                    f"cuda:{self.replay_gpu_index}",
                ],
            },
        )
        report = {
            "schema_version": "verifier-audit-collection-v2",
            "manifest_sha256": self.manifest["manifest_sha256"],
            "policy_id": active.policy_id,
            "code_revision": self.code_revision,
            "preflight_path": str(self.preflight_path or ""),
            "preflight_sha256": self.preflight_sha256,
            "preflight_code_revision": self.preflight_code_revision,
            "code_changed_since_preflight": bool(
                self.preflight_code_revision
                and self.preflight_code_revision != self.code_revision
            ),
            "available_context_count": available_context_count,
            "scheduled_context_count": len(contexts),
            "experimental_increment": len(contexts) < available_context_count,
            "label_version": FIXED_BUDGET_50_CONTRACT.label_version,
            "label_config": label_contract_payload(FIXED_BUDGET_50_CONTRACT),
            "suggested_data_targets": {
                "train": FIXED_BUDGET_50_CONTRACT.suggested_train_contexts,
                "calibration": (
                    FIXED_BUDGET_50_CONTRACT.suggested_calibration_contexts
                ),
                "test": FIXED_BUDGET_50_CONTRACT.suggested_test_contexts,
                "hard_gate": False,
            },
            "tasks_covered": len(
                {
                    (
                        item.evaluation.suite,
                        item.evaluation.task_id,
                        item.evaluation.perturbation_variant,
                    )
                    for item in contexts
                }
            ),
            "all_libero_pro_tasks_covered": len(
                {
                    (
                        item.evaluation.suite,
                        item.evaluation.task_id,
                        item.evaluation.perturbation_variant,
                    )
                    for item in contexts
                }
            ) == len(self.manifest["tasks"]),
            "verifier_opportunities": len(all_decisions),
            "targeted_replay_contexts": len(decisions),
            "counterfactual_selection_strategy": (
                "task_breadth_then_decision_boundary"
            ),
            "excluded_forced_expansion": excluded_forced_expansion,
            "replay_plan_path": str(self.replay_plan_path.resolve()),
            "replay_plan_sha256": plan["plan_sha256"],
            "replay_job_path": str(replay_job_path.resolve()),
            "final_seal_opened": False,
        }
        atomic_write_json(self.output_path, report)
        return report

    def _validate_preflight(self) -> None:
        if self.preflight_path is None:
            return
        value = json.loads(self.preflight_path.read_text(encoding="utf-8"))
        if value.get("schema_version") != "hgpu1-preflight-v1" or not value.get(
            "passed"
        ):
            raise RuntimeError("formal audit requires a green hgpu1 preflight")
        # Source drift is provenance, not an experimental code freeze. Runtime
        # and artifact contracts still fail closed on label semantics.
        self.preflight_code_revision = str(value.get("git_revision") or "")
        protocol_checks = [
            item
            for item in value.get("checks", [])
            if item.get("name") == "joint_protocol_manifest" and item.get("passed")
        ]
        if len(protocol_checks) != 1 or str(
            protocol_checks[0].get("details", {}).get("manifest_sha256")
        ) != str(self.manifest.get("manifest_sha256")):
            raise RuntimeError("formal audit preflight manifest binding is stale")


def _targeted_replay_contexts(
    contexts: Sequence[Mapping[str, Any]], *, limit: int
) -> list[dict[str, Any]]:
    """Select replay sparsely: task breadth first, then near-boundary depth."""

    if int(limit) <= 0:
        return []

    def boundary_distance(value: Mapping[str, Any]) -> float:
        score = value.get("selection_score")
        if score is None:
            return float("inf")
        try:
            return abs(float(score) - FIXED_BUDGET_50_CONTRACT.decision_boundary)
        except (TypeError, ValueError):
            return float("inf")

    groups: dict[str, list[dict[str, Any]]] = {}
    for raw in contexts:
        value = dict(raw)
        groups.setdefault(str(value.get("task_key") or "UNKNOWN"), []).append(value)
    for values in groups.values():
        values.sort(key=lambda value: (boundary_distance(value), value["record_id"]))

    # Prefer task groups whose best available context is closest to the
    # decision boundary. Every selected group contributes one context before
    # any group contributes a second.
    task_order = sorted(
        groups,
        key=lambda task: (
            boundary_distance(groups[task][0]),
            hashlib.sha256(f"fixed10-replay-task\0{task}".encode()).digest(),
        ),
    )
    selected: list[dict[str, Any]] = []
    depth = 0
    while len(selected) < min(int(limit), len(contexts)):
        added = False
        for task in task_order:
            if depth < len(groups[task]):
                selected.append(groups[task][depth])
                added = True
                if len(selected) == int(limit):
                    break
        if not added:
            break
        depth += 1
    return selected


__all__ = [
    "AUDIT_SPLITS",
    "AuditCollectionCoordinator",
    "AuditContext",
    "HydraAuditEpisodeExecutor",
    "audit_contexts_from_manifest",
]
