"""External, resumable slow-loop worker for hgpu1.

The rollout process only appends EXPANSION_TRIGGERED.  This worker owns all
subsequent filesystem/provider/training work and therefore never mutates a
policy object that is serving a live episode.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from .candidates import (
    DeltaLineageEntry,
    compose_expansion_candidates,
    compose_retain_expansion_candidates,
    compose_reuse_candidates,
)
from .checkpoint_math import (
    checkpoint_digest,
    delete_verified_theta_ft,
    extract_full_delta,
    partition_counts,
    verify_full_delta_reconstruction,
)
from .data_pipeline import curate_and_export_ticket
from .incidents import CapabilitySignatureRecord, IncidentMemory
from .io_utils import atomic_write_json, sha256_file
from .job_runner import SERVER_PYTHON
from .registry import PolicyRegistry
from .promotion import deploy_policy_gate
from .signatures import FailureMode, lookup_validated_remedies
from .slow_loop import ALLOWED, SlowLoopJob, SlowLoopState, SlowLoopStore
from .tickets import TicketCollectionPlanner, issue_ticket
from .training import CoFTConfig, build_lerobot_coft_command, prepare_source_catalog
from .verifier_training import (
    VerifierTrainingConfig,
    build_verifier_examples,
    train_verifier_ablations,
)


BLOCKED_STATES = frozenset(
    {
        SlowLoopState.AWAITING_DEMOS,
        SlowLoopState.COLLECTING,
        SlowLoopState.VERIFIER_PENDING,
        SlowLoopState.MANUAL_REVIEW,
        SlowLoopState.DEPLOYED,
        SlowLoopState.POLICY_REJECTED,
    }
)


@dataclass(frozen=True)
class WorkerTransition:
    next_state: SlowLoopState
    artifacts: tuple[Path, ...] = ()
    metadata: Mapping[str, Any] = None
    ticket_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", tuple(Path(path) for path in self.artifacts))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


SlowHandler = Callable[[SlowLoopJob], WorkerTransition]


class SlowLoopWorker:
    def __init__(
        self,
        *,
        store: SlowLoopStore,
        registry: PolicyRegistry,
        incidents: IncidentMemory,
        protocol_manifest: Path,
        ticket_root: Path,
        work_root: Path,
        snapshot_root: Path | None = None,
        ticket_planner: TicketCollectionPlanner | None = None,
        handlers: Mapping[SlowLoopState, SlowHandler] | None = None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.incidents = incidents
        self.protocol_manifest_path = Path(protocol_manifest)
        self.protocol_manifest = json.loads(
            self.protocol_manifest_path.read_text(encoding="utf-8")
        )
        if self.protocol_manifest.get("schema_version") != "joint-eval-manifest-v1":
            raise ValueError("slow worker requires the frozen joint eval manifest")
        self.ticket_root = Path(ticket_root)
        self.work_root = Path(work_root)
        self.snapshot_root = Path(
            snapshot_root
            if snapshot_root is not None
            else self.work_root.parent / "snapshots"
        )
        self.ticket_root.mkdir(parents=True, exist_ok=True)
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.ticket_planner = ticket_planner
        self.handlers = dict(handlers or {})

    def run_until_blocked(self, job_id: str, *, max_steps: int = 100) -> SlowLoopJob:
        for _ in range(max_steps):
            before = self.store.current(job_id)
            after = self.step(job_id)
            if after.state in BLOCKED_STATES or after == before:
                return after
        raise RuntimeError(f"slow-loop job {job_id} exceeded {max_steps} transitions")

    def step(self, job_id: str) -> SlowLoopJob:
        job = self.store.current(job_id)
        if job.state in BLOCKED_STATES:
            return job
        try:
            return self._step(job)
        except Exception as exc:
            if SlowLoopState.RETRYABLE_ERROR not in ALLOWED[job.state]:
                raise
            return self.store.advance(
                job.job_id,
                expected_state=job.state,
                next_state=SlowLoopState.RETRYABLE_ERROR,
                input_hash=job.input_hash,
                output_hash=_digest_json(
                    {
                        "state": job.state.value,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                ),
                metadata={
                    "resume_state": job.state.value,
                    "last_error_type": type(exc).__name__,
                    "last_error": str(exc),
                },
            )

    def _step(self, job: SlowLoopJob) -> SlowLoopJob:
        if job.state is SlowLoopState.RETRYABLE_ERROR:
            resume = SlowLoopState(str(job.metadata["resume_state"]))
            if resume not in ALLOWED[SlowLoopState.RETRYABLE_ERROR]:
                raise ValueError(f"invalid retry resume state {resume.value}")
            return self.store.advance(
                job.job_id,
                expected_state=job.state,
                next_state=resume,
                input_hash=job.input_hash,
                output_hash=job.output_hash,
                metadata={"retrying_state": resume.value},
            )
        if job.state is SlowLoopState.STALE_BASE:
            active = self.registry.active()
            if active is None or active.policy_id == job.active_policy_id:
                return job
            new_hash = _digest_json(
                {
                    "previous_input": job.input_hash,
                    "new_active_policy_id": active.policy_id,
                    "manifest_hash": active.manifest_hash,
                }
            )
            return self.store.advance(
                job.job_id,
                expected_state=job.state,
                next_state=SlowLoopState.LOOKUP_PENDING,
                input_hash=new_hash,
                output_hash=None,
                active_policy_id=active.policy_id,
                metadata={"rebased_from_policy_id": job.active_policy_id},
            )
        if job.state is SlowLoopState.NEEDS_MORE_DEMOS:
            return self.store.advance(
                job.job_id,
                expected_state=job.state,
                next_state=SlowLoopState.AWAITING_DEMOS,
                input_hash=job.input_hash,
                output_hash=job.output_hash,
                metadata={"demo_collection_append_only": True},
            )

        stale = self._stale_active(job)
        if stale and SlowLoopState.STALE_BASE in ALLOWED[job.state]:
            return self.store.advance(
                job.job_id,
                expected_state=job.state,
                next_state=SlowLoopState.STALE_BASE,
                input_hash=job.input_hash,
                output_hash=job.output_hash,
                metadata={"observed_active_policy_id": stale},
            )

        if job.state is SlowLoopState.EXPANSION_TRIGGERED:
            return self.store.advance(
                job.job_id,
                expected_state=job.state,
                next_state=SlowLoopState.LOOKUP_PENDING,
                input_hash=job.input_hash,
                output_hash=None,
            )
        if job.state is SlowLoopState.LOOKUP_PENDING:
            transition = self._lookup(job)
        elif job.state is SlowLoopState.TICKET_READY:
            transition = self._issue_ticket(job)
        elif job.state is SlowLoopState.REUSE_EVALUATING:
            transition = self._prepare_reuse(job)
        elif job.state is SlowLoopState.CURATING:
            transition = self._curate(job)
        elif job.state is SlowLoopState.DATASET_READY:
            transition = self._prepare_training(job)
            if transition is None:
                return job
        elif job.state is SlowLoopState.TRAINING:
            transition = self._consume_training(job)
            if transition is None:
                return job
        elif job.state is SlowLoopState.DELTA_READY:
            transition = self._extract_delta_and_candidates(job)
        elif job.state is SlowLoopState.ALPHA_SELECTING:
            transition = self._prepare_policy_gate(job)
        elif job.state is SlowLoopState.RAW_REGRESSION:
            transition = self._consume_policy_gate(job, trigger_phase=False)
            if transition is None:
                return job
        elif job.state is SlowLoopState.TRIGGER_RECHECK:
            transition = self._consume_policy_gate(job, trigger_phase=True)
            if transition is None:
                return job
        elif job.state is SlowLoopState.POLICY_STAGED:
            transition = self._prepare_new_policy_counterfactual(job)
        elif job.state is SlowLoopState.NEW_POLICY_COUNTERFACTUAL:
            path = job.metadata.get("new_policy_counterfactual_manifest_path")
            if not path:
                default_result = Path(
                    str(job.metadata["new_policy_counterfactual_result_path"])
                )
                if not default_result.is_file():
                    return job
                path = str(default_result)
            result_value = json.loads(Path(str(path)).read_text(encoding="utf-8"))
            if result_value.get("schema_version") not in {
                "new-policy-counterfactual-result-v1",
                # Backward-compatible externally produced result used before
                # the explicit job contract was introduced.
                None,
            }:
                raise ValueError("unsupported new-policy counterfactual result")
            if result_value.get("complete") is not True:
                raise ValueError("new-policy counterfactual result is incomplete")
            if result_value.get("policy_id") not in {
                None,
                job.metadata["staged_policy_id"],
            }:
                raise ValueError("counterfactual result targets a different policy")
            if result_value.get("schema_version") == "new-policy-counterfactual-result-v1":
                plan_path = Path(
                    str(job.metadata["new_policy_counterfactual_plan_path"])
                )
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                if result_value.get("plan_sha256") != plan.get("plan_sha256"):
                    raise ValueError("counterfactual result does not match its frozen plan")
                planned_ids = {
                    str(item["record_id"]) for item in plan.get("contexts", ())
                }
                if int(result_value.get("contexts_planned", -1)) != len(planned_ids):
                    raise ValueError("counterfactual result planned-context count changed")
                if int(result_value.get("contexts_completed", -1)) != len(planned_ids):
                    raise ValueError("counterfactual result did not complete every context")
                labeled_ids = {
                    str(item["record_id"])
                    for item in self.incidents.labels.iter_valid()
                    if str(item.get("policy_id"))
                    == str(job.metadata["staged_policy_id"])
                    and not bool(item.get("weak", False))
                }
                missing_labels = sorted(planned_ids - labeled_ids)
                if missing_labels:
                    raise ValueError(
                        "counterfactual result is missing attached labels: "
                        f"{missing_labels[:5]}"
                    )
            transition = WorkerTransition(
                next_state=SlowLoopState.VERIFIER_TRAINING,
                artifacts=(Path(str(path)),),
                metadata={
                    "new_policy_counterfactual_complete": True,
                    "new_policy_counterfactual_manifest_path": str(path),
                },
            )
        elif job.state is SlowLoopState.VERIFIER_TRAINING:
            path = job.metadata.get("verifier_result_path")
            if not path:
                path = str(self._train_verifier_for_staged_policy(job))
            verifier_result = json.loads(Path(str(path)).read_text(encoding="utf-8"))
            transition = WorkerTransition(
                next_state=(
                    SlowLoopState.READY_PAIR
                    if verifier_result.get("gate", {}).get("passed")
                    else SlowLoopState.READY_FIXED_BUDGET
                ),
                artifacts=(Path(str(path)),),
                metadata={
                    "verifier_gate_passed": bool(
                        verifier_result.get("gate", {}).get("passed")
                    ),
                    "verifier_gate_reasons": list(
                        verifier_result.get("gate", {}).get("reasons", ())
                    ),
                },
            )
        elif job.state in {
            SlowLoopState.READY_PAIR,
            SlowLoopState.READY_FIXED_BUDGET,
        }:
            transition = self._deploy(job)
        else:
            handler = self.handlers.get(job.state)
            if handler is None:
                return job
            transition = handler(job)
        if transition.next_state not in ALLOWED[job.state]:
            raise ValueError(
                f"handler attempted invalid transition {job.state.value}->"
                f"{transition.next_state.value}"
            )
        output_hash = _artifact_output_hash(
            job=job,
            transition=transition,
        )
        return self.store.advance(
            job.job_id,
            expected_state=job.state,
            next_state=transition.next_state,
            input_hash=job.input_hash,
            output_hash=output_hash,
            metadata=transition.metadata,
            ticket_id=transition.ticket_id,
        )

    def _curate(self, job: SlowLoopJob) -> WorkerTransition:
        ticket_path = Path(str(job.metadata["ticket_path"]))
        repo_id = str(
            job.metadata.get("lerobot_repo_id")
            or f"vls/ticket_{job.ticket_id or job.job_id}"
        )
        result = curate_and_export_ticket(
            ticket_path=ticket_path,
            repo_id=repo_id,
            replay_tolerance=float(job.metadata.get("replay_tolerance", 1e-5)),
        )
        curation_path = ticket_path.parent / "curation.json"
        if result["needs_more_demos"]:
            return WorkerTransition(
                next_state=SlowLoopState.NEEDS_MORE_DEMOS,
                artifacts=(curation_path,),
                metadata={
                    "curation_needs_more_demos": True,
                    "curation_coverage": result["coverage"],
                },
            )
        dataset_info = Path(str(result["export_root"])) / "meta/info.json"
        return WorkerTransition(
            next_state=SlowLoopState.DATASET_READY,
            artifacts=(curation_path, dataset_info),
            metadata={
                "curation_needs_more_demos": False,
                "current_ticket_dataset_path": result["export_root"],
                "current_ticket_repo_id": result["repo_id"],
            },
        )

    def _prepare_training(self, job: SlowLoopJob) -> WorkerTransition | None:
        source_spec_value = job.metadata.get("coft_source_spec_path")
        if not source_spec_value:
            # Replay and accepted-ticket sources are frozen externally once per
            # experiment.  Waiting here is intentional and hash-visible.
            return None
        source_spec_path = Path(str(source_spec_value))
        source_spec = json.loads(source_spec_path.read_text(encoding="utf-8"))
        replay = {
            str(key): Path(str(value))
            for key, value in dict(source_spec.get("replay", {})).items()
        }
        old = {
            str(key): Path(str(value))
            for key, value in dict(source_spec.get("old", {})).items()
        }
        current_repo_id = str(job.metadata["current_ticket_repo_id"])
        current_dataset = Path(str(job.metadata["current_ticket_dataset_path"]))
        root = self._job_dir(job) / "coft"
        catalog = root / "catalog"
        source_manifest_path = root / "source_sampler.json"
        seed = int(source_spec.get("seed", 20260825))
        training_config = CoFTConfig()
        source_manifest = prepare_source_catalog(
            catalog_root=catalog,
            manifest_path=source_manifest_path,
            new_datasets={current_repo_id: current_dataset},
            old_ticket_datasets=old,
            replay_datasets=replay,
            seed=seed,
            config=training_config,
        )
        parent = self.registry.root / "policies" / job.active_policy_id
        if not parent.is_dir():
            raise FileNotFoundError(f"active parent checkpoint missing: {parent}")
        training_output = root / "training_output"
        command = build_lerobot_coft_command(
            python_executable=Path(
                str(
                    source_spec.get(
                        "python_executable",
                        "/shared/hengyil6/vls/envs/vla-pilot/bin/python",
                    )
                )
            ),
            parent_checkpoint=parent,
            dataset_root=catalog,
            dataset_repo_id=current_repo_id,
            dataset_repo_ids=tuple(map(str, source_manifest["repo_ids"])),
            source_sampler_manifest=source_manifest_path,
            output_dir=training_output,
            seed=seed,
            config=training_config,
        )
        expected_checkpoint = (
            training_output / "checkpoints" / "001000" / "pretrained_model"
        )
        job_spec = {
            "schema_version": "coft-job-v1",
            "job_id": job.job_id,
            "gpu_count": training_config.gpus,
            "preferred_gpu_indices": [4, 5, 6, 7, 0, 1, 2, 3],
            "minimum_free_gib_per_gpu": 45.0,
            "command": command,
            "cwd": str(Path(__file__).resolve().parents[1]),
            "source_manifest_sha256": source_manifest["manifest_sha256"],
            "parent_policy_id": job.active_policy_id,
            "parent_checkpoint_digest": checkpoint_digest(parent),
            "expected_checkpoint": str(expected_checkpoint),
        }
        job_spec_path = root / "training_job.json"
        atomic_write_json(job_spec_path, job_spec)
        return WorkerTransition(
            next_state=SlowLoopState.TRAINING,
            artifacts=(source_spec_path, source_manifest_path, job_spec_path),
            metadata={
                "training_job_path": str(job_spec_path),
                "training_output_path": str(training_output),
                "theta_ft_checkpoint_path": str(expected_checkpoint),
                "coft_source_manifest_path": str(source_manifest_path),
            },
        )

    def _consume_training(self, job: SlowLoopJob) -> WorkerTransition | None:
        checkpoint = Path(str(job.metadata["theta_ft_checkpoint_path"]))
        if not checkpoint.is_dir():
            return None
        counts = partition_counts(checkpoint)
        if sum(counts.values()) != 812:
            raise ValueError(f"trained checkpoint is incomplete: {counts}")
        manifest = {
            "schema_version": "coft-result-v1",
            "job_id": job.job_id,
            "theta_ft_checkpoint_path": str(checkpoint.resolve()),
            "theta_ft_checkpoint_digest": checkpoint_digest(checkpoint),
            "partition_counts": counts,
            "source_manifest_path": job.metadata["coft_source_manifest_path"],
            "source_manifest_sha256": sha256_file(
                Path(str(job.metadata["coft_source_manifest_path"]))
            ),
        }
        result_path = self._job_dir(job) / "coft" / "training_result.json"
        atomic_write_json(result_path, manifest)
        return WorkerTransition(
            next_state=SlowLoopState.DELTA_READY,
            artifacts=(result_path,),
            metadata={
                "training_result_path": str(result_path),
                "theta_ft_checkpoint_digest": manifest[
                    "theta_ft_checkpoint_digest"
                ],
            },
        )

    def _extract_delta_and_candidates(self, job: SlowLoopJob) -> WorkerTransition:
        theta_ft = Path(str(job.metadata["theta_ft_checkpoint_path"]))
        parent = self.registry.root / "policies" / job.active_policy_id
        theta_ft_digest = str(job.metadata["theta_ft_checkpoint_digest"])
        if theta_ft.exists() and checkpoint_digest(theta_ft) != theta_ft_digest:
            raise ValueError("theta_ft changed after the training result was recorded")
        delta_id = "delta_" + _digest_json(
            {
                "parent_policy_id": job.active_policy_id,
                "parent_digest": checkpoint_digest(parent),
                "theta_ft_digest": theta_ft_digest,
                "source_manifest": job.metadata.get("coft_source_manifest_path"),
            }
        )[:16]
        delta_work = self._job_dir(job) / "delta" / delta_id
        if not delta_work.exists():
            if not theta_ft.exists():
                raise FileNotFoundError(
                    "theta_ft disappeared before full delta extraction completed"
                )
            extract_full_delta(
                parent,
                theta_ft,
                delta_work,
                parent_policy_id=job.active_policy_id,
            )
        if theta_ft.exists():
            reconstruction = verify_full_delta_reconstruction(
                parent, delta_work, theta_ft
            )
        else:
            proof_path = delta_work / "reconstruction.json"
            cleanup_path = delta_work / "theta_ft_cleanup.json"
            if not proof_path.is_file() or not cleanup_path.is_file():
                raise FileNotFoundError(
                    "theta_ft is absent without a complete reconstruction/cleanup proof"
                )
            reconstruction = json.loads(proof_path.read_text(encoding="utf-8"))
            cleanup_proof = json.loads(cleanup_path.read_text(encoding="utf-8"))
            if (
                not reconstruction.get("passed")
                or reconstruction.get("theta_ft_checkpoint_digest")
                != theta_ft_digest
                or cleanup_proof.get("theta_ft_checkpoint_digest")
                != theta_ft_digest
            ):
                raise ValueError("theta_ft cleanup proof does not match training result")
        cleanup = None
        if bool(job.metadata.get("cleanup_theta_ft", True)):
            if theta_ft.exists():
                cleanup = delete_verified_theta_ft(
                    theta_ft,
                    parent_checkpoint=parent,
                    delta_checkpoint=delta_work,
                )
            else:
                cleanup = json.loads(
                    (delta_work / "theta_ft_cleanup.json").read_text(encoding="utf-8")
                )
        registered_delta = self.registry.install_artifact(
            "delta", delta_id, delta_work
        )
        accepted_lineage = self._active_delta_lineage(job.active_policy_id)
        theta0_ref = json.loads(
            (self.registry.root / "base/theta_0/ref.json").read_text(encoding="utf-8")
        )
        candidate_kwargs = {
            "theta0_checkpoint": Path(str(theta0_ref["checkpoint_path"])),
            "parent_policy_id": job.active_policy_id,
            "accepted_lineage": accepted_lineage,
            "new_delta_id": delta_id,
            "new_delta_path": registered_delta,
            "output_root": self._job_dir(job) / "candidates",
        }
        if job.metadata.get("baseline_kind") == "always_expand_retain":
            grid = compose_retain_expansion_candidates(**candidate_kwargs)
            candidate_merge_method = "retain_uniform"
        else:
            grid = compose_expansion_candidates(**candidate_kwargs)
            candidate_merge_method = "v2_language_only"
        grid_path = (
            self._job_dir(job)
            / "candidates"
            / f"candidate_grid_{grid['attempt_hash'][:16]}.json"
        )
        parent_path = self._job_dir(job) / "parent_candidate.json"
        candidates_path = self._job_dir(job) / "candidates.json"
        atomic_write_json(
            parent_path,
            {
                "policy_id": job.active_policy_id,
                "checkpoint_path": str(parent.resolve()),
                "checkpoint_digest": checkpoint_digest(parent),
                "alpha_l": 0.0,
            },
        )
        atomic_write_json(candidates_path, grid["candidates"])
        artifacts = [
            delta_work / "meta.json",
            delta_work / "reconstruction.json",
            registered_delta / "registry_manifest.json",
            grid_path,
            parent_path,
            candidates_path,
        ]
        if cleanup is not None:
            artifacts.append(delta_work / "theta_ft_cleanup.json")
        return WorkerTransition(
            next_state=SlowLoopState.ALPHA_SELECTING,
            artifacts=tuple(artifacts),
            metadata={
                "delta_id": delta_id,
                "registered_delta_path": str(registered_delta),
                "delta_reconstruction": reconstruction,
                "theta_ft_deleted": cleanup is not None,
                "candidate_grid_path": str(grid_path),
                "parent_candidate_path": str(parent_path),
                "candidates_json_path": str(candidates_path),
                "candidate_merge_method": candidate_merge_method,
            },
        )

    def _prepare_policy_gate(self, job: SlowLoopJob) -> WorkerTransition:
        root = self._job_dir(job) / "policy_gate"
        report_root = root / "reports"
        command = [
            "/shared/hengyil6/vls/envs/vla-pilot/bin/python",
            str(Path(__file__).resolve().parents[1] / "scripts/self_improve.py"),
            "policy-gate",
            "--manifest",
            str(self.protocol_manifest_path),
            "--ticket",
            str(job.metadata["ticket_path"]),
            "--parent-json",
            str(job.metadata["parent_candidate_path"]),
            "--candidates-json",
            str(job.metadata["candidates_json_path"]),
            "--ledger",
            str(root / "episodes.jsonl"),
            "--output",
            str(report_root),
            "--rollout-output",
            str(root / "rollouts"),
            "--workers",
            str(int(job.metadata.get("evaluation_workers", 1))),
        ]
        spec = {
            "schema_version": "policy-gate-job-v1",
            "job_id": job.job_id,
            "command": command,
            "cwd": str(Path(__file__).resolve().parents[1]),
            "manifest_sha256": self.protocol_manifest["manifest_sha256"],
            "preferred_gpu_index": int(job.metadata.get("evaluation_gpu_index", 4)),
            "minimum_free_gib": 20.0,
            "report_root": str(report_root),
        }
        spec_path = root / "policy_gate_job.json"
        atomic_write_json(spec_path, spec)
        return WorkerTransition(
            next_state=SlowLoopState.RAW_REGRESSION,
            artifacts=(spec_path,),
            metadata={
                "policy_gate_job_path": str(spec_path),
                "policy_gate_output_root": str(report_root),
            },
        )

    def _active_delta_lineage(
        self, policy_id: str
    ) -> tuple[DeltaLineageEntry, ...]:
        candidate_path = self.registry.root / "policies" / policy_id / "candidate.json"
        if not candidate_path.is_file():
            return ()
        value = json.loads(candidate_path.read_text(encoding="utf-8"))
        result = []
        for raw in value.get("lineage", ()):
            payload = dict(raw)
            registered = self.registry.root / "deltas" / str(payload["delta_id"])
            if not registered.is_dir():
                raise FileNotFoundError(
                    f"accepted lineage delta is not registered: {registered}"
                )
            payload["path"] = str(registered)
            result.append(DeltaLineageEntry(**payload))
        return tuple(result)

    def _lookup(self, job: SlowLoopJob) -> WorkerTransition:
        metadata = job.metadata
        if metadata.get("baseline_kind") == "always_expand_retain":
            payload = {
                "schema_version": "signature-lookup-result-v1",
                "job_id": job.job_id,
                "signature_id": metadata["signature_id"],
                "failure_mode": metadata["failure_mode"],
                "active_policy_id": job.active_policy_id,
                "matches": [],
                "lookup_disabled": True,
                "reason": "always-expansion-retain-control",
            }
            path = self._job_dir(job) / "lookup.json"
            atomic_write_json(path, payload)
            return WorkerTransition(
                next_state=SlowLoopState.TICKET_READY,
                artifacts=(path,),
                metadata={
                    "lookup_result_path": str(path),
                    "lookup_match_count": 0,
                    "reuse_candidates": [],
                    "lookup_disabled": True,
                },
            )
        feature_path = Path(str(metadata["signature_feature_path"]))
        if feature_path.stem != str(metadata["signature_feature_id"]):
            raise ValueError("signature feature ID/path mismatch")
        with np.load(feature_path, allow_pickle=False) as values:
            e_goal = values["goal"].astype(np.float32)
            e_obs = values["observation"].astype(np.float32)
        failure_mode = FailureMode(str(metadata["failure_mode"]))
        records = []
        for value in self.incidents.signatures.iter_valid():
            fields = CapabilitySignatureRecord.__dataclass_fields__
            records.append(
                CapabilitySignatureRecord(
                    **{
                        name: (
                            value[name]
                            if name in value
                            else fields[name].default
                        )
                        for name in fields
                        if name != "recorded_at" or name in value
                    }
                )
            )
        matches = lookup_validated_remedies(
            query_failure_mode=failure_mode,
            query_e_goal=e_goal,
            query_e_obs=e_obs,
            records=records,
        )
        payload = {
            "schema_version": "signature-lookup-result-v1",
            "job_id": job.job_id,
            "signature_id": metadata["signature_id"],
            "failure_mode": failure_mode.value,
            "active_policy_id": job.active_policy_id,
            "matches": [
                {
                    "signature_id": item.signature.signature_id,
                    "source_policy_id": item.signature.policy_id,
                    "delta_id": item.signature.delta_id,
                    "ticket_id": item.signature.ticket_id,
                    "similarity": item.similarity,
                    "alpha_candidates": list(item.alpha_candidates),
                }
                for item in matches
            ],
        }
        path = self._job_dir(job) / "lookup.json"
        atomic_write_json(path, payload)
        return WorkerTransition(
            next_state=(
                SlowLoopState.REUSE_EVALUATING
                if matches
                else SlowLoopState.TICKET_READY
            ),
            artifacts=(path,),
            metadata={
                "lookup_result_path": str(path),
                "lookup_match_count": len(matches),
                "reuse_candidates": payload["matches"],
            },
        )

    def _prepare_reuse(self, job: SlowLoopJob) -> WorkerTransition:
        lookup_path = Path(str(job.metadata["lookup_result_path"]))
        lookup = json.loads(lookup_path.read_text(encoding="utf-8"))
        usable = [
            item
            for item in lookup.get("matches", ())
            if item.get("delta_id") and item.get("ticket_id")
        ]
        if not usable:
            return WorkerTransition(
                next_state=SlowLoopState.TICKET_READY,
                artifacts=(lookup_path,),
                metadata={"reuse_fallback_reason": "match_missing_delta_or_ticket_lineage"},
            )
        match = usable[0]
        active_root = self.registry.root / "policies" / job.active_policy_id
        candidate_metadata_path = active_root / "candidate.json"
        if not candidate_metadata_path.is_file():
            return WorkerTransition(
                next_state=SlowLoopState.TICKET_READY,
                artifacts=(lookup_path,),
                metadata={"reuse_fallback_reason": "active_policy_has_no_delta_lineage"},
            )
        candidate_metadata = json.loads(
            candidate_metadata_path.read_text(encoding="utf-8")
        )
        lineage = []
        for value in candidate_metadata.get("lineage", ()):
            payload = dict(value)
            registered = self.registry.root / "deltas" / str(payload["delta_id"])
            if registered.exists():
                payload["path"] = str(registered)
            lineage.append(DeltaLineageEntry(**payload))
        if not lineage:
            return WorkerTransition(
                next_state=SlowLoopState.TICKET_READY,
                artifacts=(lookup_path, candidate_metadata_path),
                metadata={"reuse_fallback_reason": "active_policy_lineage_is_empty"},
            )
        theta0_ref = json.loads(
            (self.registry.root / "base/theta_0/ref.json").read_text(encoding="utf-8")
        )
        source_ticket = self.ticket_root / str(match["ticket_id"]) / "ticket.json"
        if not source_ticket.is_file():
            return WorkerTransition(
                next_state=SlowLoopState.TICKET_READY,
                artifacts=(lookup_path, candidate_metadata_path),
                metadata={"reuse_fallback_reason": "validated_source_ticket_missing"},
            )
        grid = compose_reuse_candidates(
            theta0_checkpoint=Path(theta0_ref["checkpoint_path"]),
            parent_policy_id=job.active_policy_id,
            accepted_lineage=lineage,
            target_delta_id=str(match["delta_id"]),
            output_root=self._job_dir(job) / "reuse_candidates",
        )
        grid_path = (
            self._job_dir(job)
            / "reuse_candidates"
            / f"candidate_grid_{grid['attempt_hash'][:16]}.json"
        )
        target_lineage = [
            item for item in lineage if item.delta_id == str(match["delta_id"])
        ]
        if len(target_lineage) != 1:
            raise ValueError("validated REUSE delta is absent from active policy lineage")
        parent_spec = {
            "policy_id": job.active_policy_id,
            "checkpoint_path": str(active_root.resolve()),
            "checkpoint_digest": checkpoint_digest(active_root),
            "alpha_l": target_lineage[0].alpha_l,
        }
        parent_path = self._job_dir(job) / "reuse_parent.json"
        candidates_path = self._job_dir(job) / "reuse_candidates.json"
        atomic_write_json(parent_path, parent_spec)
        atomic_write_json(candidates_path, grid["candidates"])
        return WorkerTransition(
            next_state=SlowLoopState.RAW_REGRESSION,
            artifacts=(
                lookup_path,
                candidate_metadata_path,
                grid_path,
                parent_path,
                candidates_path,
                source_ticket,
            ),
            metadata={
                "gate_kind": "REUSE",
                "reuse_source_signature_id": match["signature_id"],
                "reuse_source_delta_id": match["delta_id"],
                "reuse_source_ticket_id": match["ticket_id"],
                "reuse_source_ticket_path": str(source_ticket),
                "parent_candidate_path": str(parent_path),
                "candidate_grid_path": str(grid_path),
                "candidates_json_path": str(candidates_path),
            },
        )

    def _consume_policy_gate(
        self, job: SlowLoopJob, *, trigger_phase: bool
    ) -> WorkerTransition | None:
        path_value = job.metadata.get("policy_gate_report_path")
        if not path_value:
            output_root = job.metadata.get("policy_gate_output_root")
            if not output_root:
                return None
            candidates = tuple(
                sorted(Path(str(output_root)).glob("*policy_gate_*.json"))
            )
            if not candidates:
                return None
            if len(candidates) != 1:
                raise RuntimeError(
                    f"expected one immutable policy gate report, got {candidates}"
                )
            path_value = str(candidates[0])
        path = Path(str(path_value))
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("schema_version") != "raw-policy-gate-report-v1":
            raise ValueError("slow loop received an unsupported policy gate report")
        if report.get("manifest_hash") != self.protocol_manifest["manifest_sha256"]:
            raise ValueError("policy gate report uses a different frozen manifest")
        if report.get("parent", {}).get("policy_id") != job.active_policy_id:
            raise ValueError("policy gate parent is stale")
        decision = report.get("decision", {})
        if decision.get("status") != "POLICY_STAGED":
            return WorkerTransition(
                next_state=(
                    SlowLoopState.TICKET_READY
                    if report.get("gate_kind") == "REUSE"
                    else SlowLoopState.NEEDS_MORE_DEMOS
                ),
                artifacts=(path,),
                metadata={
                    "policy_gate_report_path": str(path),
                    "policy_gate_status": decision.get("status"),
                    "policy_gate_reason": decision.get("reason"),
                    "reuse_fallback_to_ticket": report.get("gate_kind") == "REUSE",
                },
            )
        if not trigger_phase:
            return WorkerTransition(
                next_state=SlowLoopState.TRIGGER_RECHECK,
                artifacts=(path,),
                metadata={
                    "policy_gate_report_path": str(path),
                    "raw_regression_passed": True,
                },
            )
        winner = decision.get("winner") or {}
        trigger = report.get("trigger_recheck", {}).get(winner.get("policy_id"))
        if not trigger or not trigger.get("passed"):
            raise ValueError("staged policy report has no passing winner trigger recheck")
        return WorkerTransition(
            next_state=SlowLoopState.POLICY_STAGED,
            artifacts=(path,),
            metadata={
                "policy_gate_report_path": str(path),
                "trigger_recheck_passed": True,
                "staged_policy_id": winner["policy_id"],
                "staged_checkpoint_path": winner["checkpoint_path"],
                "staged_checkpoint_digest": winner["checkpoint_digest"],
                "staged_alpha_l": winner["alpha_l"],
            },
        )

    def _prepare_new_policy_counterfactual(
        self, job: SlowLoopJob
    ) -> WorkerTransition:
        """Freeze the exact historical snapshot bank for the staged policy.

        The simulator replay runs in the code-owned hgpu1 GPU worker.  This
        step freezes its immutable input and expected output locations so a
        crash can resume without a human-written list or pasted result path.
        """

        policy_id = str(job.metadata["staged_policy_id"])
        checkpoint = Path(str(job.metadata["staged_checkpoint_path"]))
        checkpoint_digest_value = str(job.metadata["staged_checkpoint_digest"])
        if checkpoint_digest(checkpoint) != checkpoint_digest_value:
            raise ValueError("staged checkpoint changed before counterfactual replay")
        root = self._job_dir(job) / "new_policy_counterfactual"
        feature_root = root / "features"
        feature_root.mkdir(parents=True, exist_ok=True)
        contexts = []
        for decision in self.incidents.decisions.iter_valid():
            split = self._decision_verifier_split(decision)
            if split is None:
                continue
            snapshot_id = str(decision.get("snapshot_id") or "")
            snapshot_manifest = self.snapshot_root / snapshot_id / "manifest.json"
            if not snapshot_manifest.is_file():
                continue
            contexts.append(
                {
                    "record_id": str(decision["record_id"]),
                    "origin_policy_id": str(decision["policy_id"]),
                    "target_policy_id": policy_id,
                    "snapshot_id": snapshot_id,
                    "snapshot_hash": str(decision["snapshot_hash"]),
                    "snapshot_manifest_path": str(snapshot_manifest.resolve()),
                    "remaining_budget": int(decision["remaining_budget"]),
                    "data_split": split,
                    "fresh_feature_output_path": str(
                        (feature_root / f"{decision['record_id']}.npz").resolve()
                    ),
                }
            )
        contexts.sort(key=lambda value: value["record_id"])
        result_path = root / "result.json"
        plan = {
            "schema_version": "new-policy-counterfactual-plan-v2",
            "job_id": job.job_id,
            "policy_id": policy_id,
            "checkpoint_path": str(checkpoint.resolve()),
            "checkpoint_digest": checkpoint_digest_value,
            "snapshot_root": str(self.snapshot_root.resolve()),
            "incident_root": str(self.incidents.root.resolve()),
            "retry_estimand": (
                "P(fail to advance/succeed under remaining fixed four-level "
                "RE-STEER schedule)"
            ),
            "adaptive_branches": [16, 32, 64],
            "decision_rule": "head_argmax",
            "max_posterior_width": 0.20,
            "contexts": contexts,
            "result_path": str(result_path.resolve()),
        }
        canonical = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
        plan["plan_sha256"] = hashlib.sha256(canonical).hexdigest()
        plan_path = root / "plan.json"
        atomic_write_json(plan_path, plan)
        repo_root = Path(__file__).resolve().parents[1]
        replay_gpu_index = int(job.metadata.get("replay_gpu_index", 0))
        if not 0 <= replay_gpu_index <= 7:
            raise ValueError("replay_gpu_index must be in [0, 7]")
        job_spec_path = root / "replay_job.json"
        atomic_write_json(
            job_spec_path,
            {
                "schema_version": "counterfactual-replay-job-v1",
                "job_id": job.job_id,
                "plan_sha256": plan["plan_sha256"],
                "preferred_gpu_index": replay_gpu_index,
                "minimum_free_gib": 45.0,
                "cwd": str(repo_root),
                "command": [
                    str(SERVER_PYTHON),
                    str(repo_root / "scripts/self_improve.py"),
                    "replay-new-policy",
                    "--plan",
                    str(plan_path),
                    "--repo-root",
                    str(repo_root),
                    "--device",
                    f"cuda:{replay_gpu_index}",
                ],
            },
        )
        artifacts: list[Path] = [plan_path, job_spec_path]
        if not contexts:
            atomic_write_json(
                result_path,
                {
                    "schema_version": "new-policy-counterfactual-result-v1",
                    "plan_sha256": plan["plan_sha256"],
                    "policy_id": policy_id,
                    "complete": True,
                    "contexts_planned": 0,
                    "contexts_completed": 0,
                    "reason": "no_frozen_verifier_decision_snapshots_available",
                },
            )
            artifacts.append(result_path)
        return WorkerTransition(
            next_state=SlowLoopState.NEW_POLICY_COUNTERFACTUAL,
            artifacts=tuple(artifacts),
            metadata={
                "policy_staged_at_gate": True,
                "new_policy_counterfactual_plan_path": str(plan_path),
                "new_policy_counterfactual_job_spec_path": str(job_spec_path),
                "new_policy_counterfactual_result_path": str(result_path),
                "new_policy_counterfactual_context_count": len(contexts),
            },
        )

    def _decision_verifier_split(self, decision: Mapping[str, Any]) -> str | None:
        provenance = decision.get("provenance", {})
        group = provenance.get("group", {}) if isinstance(provenance, Mapping) else {}
        expected = (
            str(group.get("suite") or ""),
            str(group.get("task_id") or ""),
            str(group.get("perturbation_variant") or ""),
        )
        init_state_id = str(group.get("init_state_id") or "")
        if not all(expected) or not init_state_id:
            return None
        matching = [
            task
            for task in self.protocol_manifest["tasks"]
            if (
                str(task["suite"]),
                str(task["task_id"]),
                str(task["perturbation_variant"]),
            )
            == expected
        ]
        if len(matching) != 1:
            return None
        split_map = {
            "verifier_audit_train": "train",
            "verifier_calibration": "calibration",
            "verifier_test": "test",
        }
        memberships = [
            output
            for manifest_split, output in split_map.items()
            if init_state_id
            in {str(value) for value in matching[0]["splits"][manifest_split]}
        ]
        if len(memberships) > 1:
            raise ValueError("verifier decision maps to overlapping frozen splits")
        return memberships[0] if memberships else None

    def _train_verifier_for_staged_policy(self, job: SlowLoopJob) -> Path:
        """Retrain all verifier ablations in the external slow worker process."""

        root = self._job_dir(job) / "verifier"
        result_path = root / "verifier_result.json"
        if result_path.is_file():
            return result_path
        policy_id = str(job.metadata["staged_policy_id"])
        try:
            examples = build_verifier_examples(
                self.incidents,
                policy_id=policy_id,
            )
            ablation = train_verifier_ablations(
                examples,
                policy_id=policy_id,
                output_root=root / "ablations",
                config=VerifierTrainingConfig(device="cpu"),
                metadata={
                    "slow_loop_job_id": job.job_id,
                    "protocol_manifest_hash": self.protocol_manifest[
                        "manifest_sha256"
                    ],
                },
            )
            selected_name = ablation.selected_channel_set
            if selected_name is None:
                full = ablation.results["full"]
                value = {
                    "schema_version": "verifier-training-result-v1",
                    "policy_id": policy_id,
                    "verifier_id": full.verifier_id,
                    "artifact_root": full.artifact_root,
                    "gate": {
                        "passed": False,
                        "reasons": list(full.gate.reasons),
                    },
                    "selected_channel_set": None,
                    "controller_mode": "fixed_budget_4",
                    "ablation_report_path": ablation.report_path,
                }
            else:
                selected = ablation.results[selected_name]
                value = {
                    "schema_version": "verifier-training-result-v1",
                    "policy_id": policy_id,
                    "verifier_id": selected.verifier_id,
                    "artifact_root": selected.artifact_root,
                    "gate": {
                        "passed": selected.gate.passed,
                        "reasons": list(selected.gate.reasons),
                    },
                    "selected_channel_set": selected_name,
                    "controller_mode": "learned_verifier",
                    "ablation_report_path": ablation.report_path,
                }
        except (FileNotFoundError, ValueError) as exc:
            value = {
                "schema_version": "verifier-training-result-v1",
                "policy_id": policy_id,
                "verifier_id": None,
                "artifact_root": None,
                "gate": {
                    "passed": False,
                    "reasons": [
                        f"insufficient_or_invalid_verifier_evidence: {type(exc).__name__}: {exc}"
                    ],
                },
                "selected_channel_set": None,
                "controller_mode": "fixed_budget_4",
            }
        atomic_write_json(result_path, value)
        return result_path

    def _deploy(self, job: SlowLoopJob) -> WorkerTransition:
        report_path = Path(str(job.metadata["policy_gate_report_path"]))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        verifier_result = None
        artifacts = [report_path]
        if job.state is SlowLoopState.READY_PAIR:
            verifier_path = Path(str(job.metadata["verifier_result_path"]))
            verifier_result = json.loads(verifier_path.read_text(encoding="utf-8"))
            if not verifier_result.get("gate", {}).get("passed"):
                raise ValueError("READY_PAIR requires a passing verifier result")
            artifacts.append(verifier_path)
        active = self.registry.active()
        expected_revision = 0 if active is None else active.deployment_revision
        if active is not None and active.policy_id != job.active_policy_id:
            raise RuntimeError("active policy changed before deployment")
        signature, signature_artifacts = self._materialize_validated_signature(job)
        artifacts.extend(signature_artifacts)
        deployment = deploy_policy_gate(
            report=report,
            registry=self.registry,
            expected_revision=expected_revision,
            verifier_result=verifier_result,
            incidents=self.incidents,
            signature=signature,
        )
        artifacts.extend(
            [
                self.registry.root / "active.json",
                self.registry.root
                / "attempts"
                / f"transaction_{deployment.transaction_id}.json",
            ]
        )
        return WorkerTransition(
            next_state=SlowLoopState.DEPLOYED,
            artifacts=tuple(artifacts),
            metadata={
                "deployment_revision": deployment.deployment_revision,
                "deployed_policy_id": deployment.policy_id,
                "deployed_verifier_id": deployment.verifier_id,
                "deployed_controller_mode": deployment.controller_mode,
            },
        )

    def _materialize_validated_signature(
        self, job: SlowLoopJob
    ) -> tuple[dict[str, Any], tuple[Path, ...]]:
        task = self._manifest_task(job.metadata)
        if (
            str(task.get("benchmark")) != "LIBERO-PRO"
            or str(task.get("runtime_suite")) == str(task.get("suite"))
        ):
            raise ValueError("validated remedies may only originate from LIBERO-PRO")
        source = Path(str(job.metadata["signature_feature_path"]))
        with np.load(source, allow_pickle=False) as values:
            goal = np.asarray(values["goal"], dtype=np.float16)
            observation = np.asarray(values["observation"], dtype=np.float16)
        root = self._job_dir(job) / "validated_signature"
        root.mkdir(parents=True, exist_ok=True)
        goal_path = root / "e_goal.npy"
        observation_path = root / "e_obs.npy"
        _atomic_save_array(goal_path, goal)
        _atomic_save_array(observation_path, observation)
        return (
            {
                "signature_id": job.metadata["signature_id"],
                "suite": str(task["suite"]),
                "task_id": str(task["task_id"]),
                "perturbation_variant": str(task["perturbation_variant"]),
                "failure_mode": job.metadata["failure_mode"],
                "e_goal_path": str(goal_path),
                "e_obs_path": str(observation_path),
                "delta_id": job.metadata.get("reuse_source_delta_id", ""),
                "ticket_id": job.ticket_id
                or job.metadata.get("reuse_source_ticket_id", ""),
            },
            (goal_path, observation_path),
        )

    def _issue_ticket(self, job: SlowLoopJob) -> WorkerTransition:
        if self.ticket_planner is None:
            raise RuntimeError("TicketCollectionPlanner is not configured")
        metadata = job.metadata
        task = self._manifest_task(metadata)
        collection, planner_metadata = self.ticket_planner.plan(
            task_instruction=str(metadata["task_instruction"]),
            failure_mode=str(metadata["failure_mode"]),
            required_trajectory_pattern=str(
                metadata.get("required_trajectory_pattern", "")
            ),
            semantic_failure_types=tuple(
                metadata.get("semantic_failure_types", ())
            ),
        )
        active = self.registry.active()
        registry_summary = {
            "active_policy_id": job.active_policy_id,
            "deployment_revision": active.deployment_revision if active else 0,
            "manifest_hash": active.manifest_hash if active else None,
        }
        ticket = issue_ticket(
            root=self.ticket_root,
            signature_id=str(metadata["signature_id"]),
            snapshot_id=str(metadata["snapshot_id"]),
            suite=str(task["suite"]),
            task_id=str(task["task_id"]),
            perturbation_variant=str(task["perturbation_variant"]),
            failure_mode=str(metadata["failure_mode"]),
            legal_demo_init_states=task["splits"]["demo_online_pool"],
            regression_init_states=task["splits"]["policy_regression"],
            collection=collection,
            parent_policy_id=job.active_policy_id,
            registry_summary=registry_summary,
            acceptance_criteria={
                "eval_split": "regression",
                "raw_profile": {
                    "use_guidance": False,
                    "mode_gate.enabled": False,
                    "use_vlm_stage_recognition": False,
                },
                "alpha_l": [0.2, 0.4, 0.6, 0.8],
                "trigger_recheck_required": True,
            },
            target_object_id=(
                str(metadata["target_object_id"])
                if metadata.get("target_object_id")
                else None
            ),
        )
        ticket_path = self.ticket_root / ticket.ticket_id / "ticket.json"
        return WorkerTransition(
            next_state=SlowLoopState.AWAITING_DEMOS,
            artifacts=(ticket_path,),
            ticket_id=ticket.ticket_id,
            metadata={
                "ticket_path": str(ticket_path),
                "ticket_planner": planner_metadata,
            },
        )

    def _manifest_task(self, metadata: Mapping[str, Any]) -> Mapping[str, Any]:
        expected = (
            str(metadata["suite"]),
            str(metadata["task_id"]),
            str(metadata["perturbation_variant"]),
        )
        matches = [
            task
            for task in self.protocol_manifest["tasks"]
            if (
                str(task["suite"]),
                str(task["task_id"]),
                str(task["perturbation_variant"]),
            )
            == expected
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one frozen manifest task {expected}, got {len(matches)}")
        return matches[0]

    def _stale_active(self, job: SlowLoopJob) -> str | None:
        active = self.registry.active()
        if active is not None and active.policy_id != job.active_policy_id:
            return active.policy_id
        return None

    def _job_dir(self, job: SlowLoopJob) -> Path:
        path = self.work_root / job.job_id
        path.mkdir(parents=True, exist_ok=True)
        return path


def _artifact_output_hash(*, job: SlowLoopJob, transition: WorkerTransition) -> str:
    files = {}
    for path in sorted(transition.artifacts, key=lambda value: str(value)):
        if not path.is_file():
            raise FileNotFoundError(path)
        files[str(path.resolve())] = {
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
    return _digest_json(
        {
            "job_id": job.job_id,
            "sequence": job.sequence,
            "from": job.state.value,
            "to": transition.next_state.value,
            "files": files,
            "metadata": dict(transition.metadata),
        }
    )


def _digest_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def _atomic_save_array(path: Path, value: np.ndarray) -> None:
    path = Path(path)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    with temporary.open("wb") as stream:
        np.save(stream, np.asarray(value), allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


__all__ = [
    "BLOCKED_STATES",
    "SlowLoopWorker",
    "WorkerTransition",
]
