"""Fast-loop orchestration: abstract, score, select, verify only after failure."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import numpy as np

from .baselines import (
    BaselineKind,
    BaselineOpportunity,
    build_baseline_router,
)
from .cards import CandidateCardRenderer
from .config import ModeGateConfig
from .experiment_contract import label_contract_payload
from .gate import TrajectoryCandidateGate
from .geometry import GeometryScorer, select_execution_candidate
from .incidents import (
    IncidentMemory,
    VerifierDecisionRecord,
    VerifierLabelRecord,
)
from .io_utils import atomic_write_json, sha256_file
from .progress import ProgressMonitor
from .semantic_planner import (
    GeminiSemanticPlanner,
    score_semantics_with_network_recovery,
)
from .state_machine import EpisodeChunkController, RouteDecision
from .types import (
    ActionChunkBatch,
    ControllerRoute,
    DecisionSnapshot,
    GateContext,
    ProgressEvidence,
    SelectedExecution,
    SemanticPlan,
    SemanticCandidateScore,
)
from .verifier import (
    DeployedVerifierPredictor,
    build_verifier_input,
    save_verifier_input,
)


class RuntimeStatus(str, Enum):
    INTERNAL_RESAMPLE = "INTERNAL_RESAMPLE"
    EXECUTE = "EXECUTE"
    RESTEER = "RE-STEER"
    EXPAND = "EXPANSION"
    ABORT = "ABORT"


@dataclass(frozen=True)
class RuntimeDecision:
    status: RuntimeStatus
    selected: SelectedExecution | None
    route: RouteDecision | None
    round_id: int
    verifier_decision: ControllerRoute | None = None
    verifier_logits: tuple[float, float] | None = None
    p_expansion: float | None = None
    error: str | None = None
    record_id: str | None = None
    semantic_failure_types: tuple[str, ...] = ()
    required_trajectory_pattern: str = ""
    analysis_path: str = ""
    evidence_path: str = ""


class CandidateRuntime:
    def __init__(
        self,
        *,
        config: ModeGateConfig,
        gate: TrajectoryCandidateGate,
        planner: GeminiSemanticPlanner,
        combined_renderer: CandidateCardRenderer,
        geometry_factory: Callable[[GateContext], GeometryScorer],
        incidents: IncidentMemory,
        verifier: DeployedVerifierPredictor | None = None,
        backbone_id: str = "",
    ) -> None:
        self.config = config
        self.baseline_router = build_baseline_router(
            kind=config.baseline_kind,
            budget=config.baseline_budget,
            minimum_candidates=config.baseline_minimum_candidates,
            threshold=config.baseline_threshold,
            expansion_rate=config.baseline_expansion_rate,
            seed=config.baseline_seed,
            opportunity_bank=(
                Path(config.baseline_opportunity_bank)
                if config.baseline_opportunity_bank
                else None
            ),
        )
        retry_budget_override = (
            config.baseline_budget
            if config.baseline_kind == BaselineKind.FIXED_BUDGET.value
            else None
        )
        self.controller = EpisodeChunkController(
            config, retry_budget_override=retry_budget_override
        )
        self.gate = gate
        self.planner = planner
        self.combined_renderer = combined_renderer
        self.geometry_factory = geometry_factory
        self.incidents = incidents
        self.verifier = verifier
        self.backbone_id = backbone_id
        self.progress_monitor = ProgressMonitor()
        self.progress_history: list[dict[str, Any]] = []
        self._last_semantic_stage_id: str | None = None
        self._last_semantic_confidence = 0.0
        self._round_id = 0
        self._pending_factual: list[dict[str, Any]] = []
        self.executed_history: list[list[float]] = []
        self.episode_id = uuid4().hex
        self._execution_context = None
        self.last_analysis_path = None
        self.last_evidence_path = None

    def start_episode(self, *, stage_id: str = "UNKNOWN") -> None:
        self.controller.start_episode(stage_id=stage_id)
        self.progress_monitor.reset(stage_id=stage_id, reward=0.0)
        self.progress_history = []
        self._last_semantic_stage_id = None
        self._last_semantic_confidence = 0.0
        self._round_id = 0
        # Any opportunity left open by a provider/runtime crash is censored,
        # never converted into a capability failure label.
        self._pending_factual = []
        self.executed_history = []
        self.episode_id = uuid4().hex
        self._execution_context = None
        self.last_analysis_path = None
        self.last_evidence_path = None

    @property
    def verification_due(self) -> bool:
        return self.controller.state.verification_due

    @property
    def next_round_id(self) -> int:
        return self._round_id + 1

    def observe_chunk(
        self,
        progress: ProgressEvidence,
        **kwargs: Any,
    ) -> RouteDecision:
        terminal_timeout = bool(kwargs.get("terminal_timeout", False))
        decision = self.controller.observe_chunk(progress, **kwargs)
        if progress.task_success:
            self._close_factual_labels(success=True, reason="native_success")
        elif terminal_timeout:
            self._close_factual_labels(success=False, censored=True, reason="terminal")
        self.progress_history.append(
            {
                "stage_id": progress.stage_id,
                "advanced": progress.advanced,
                "confidence": progress.confidence,
                "source": progress.source,
                "task_success": progress.task_success,
                "reward_improved": progress.reward_improved,
                "route_reason": decision.reason,
            }
        )
        return decision

    def assess_progress(
        self,
        *,
        task_success: bool,
        predicate_stage_id: str | None = None,
        predicate_advanced: bool | None = None,
        gemini_stage_id: str | None = None,
        gemini_confidence: float | None = None,
        normalized_reward: float | None = None,
        relation_improved: bool = False,
    ) -> ProgressEvidence:
        return self.progress_monitor.observe(
            task_success=task_success,
            predicate_stage_id=predicate_stage_id,
            predicate_advanced=predicate_advanced,
            gemini_stage_id=(
                gemini_stage_id
                if gemini_stage_id is not None
                else self._last_semantic_stage_id
            ),
            gemini_confidence=(
                float(gemini_confidence)
                if gemini_confidence is not None
                else self._last_semantic_confidence
            ),
            normalized_reward=normalized_reward,
            relation_improved=relation_improved,
        )

    def process_batch(
        self,
        *,
        context: GateContext,
        batch: ActionChunkBatch,
        artifact_root: Path,
        scene_feature: np.ndarray | None = None,
        scene_feature_path: Path | None = None,
        snapshot: DecisionSnapshot | None = None,
        camera_images: dict | None = None,
    ) -> RuntimeDecision:
        self._round_id += 1
        was_fresh = self.controller.state.verification_due
        try:
            self.controller.begin_sampling()
            round_dir = Path(artifact_root) / context.context_id / f"round_{self._round_id:03d}"
            evidence = self.gate.analyze(context, batch, round_dir)
            analysis_path = _save_round_evidence(round_dir, evidence)
            self.last_analysis_path = analysis_path
            from .ticket_visuals import build_decision_evidence
            evidence_path = build_decision_evidence(
                directory=round_dir / "visuals", context=context, analysis_path=analysis_path,
                executed_history=self.executed_history, images=camera_images or {},
                project_points=self.combined_renderer._project_points,
                library=self.incidents.experiences, episode_id=self.episode_id)
            self.last_evidence_path = evidence_path
            self.controller.mark_abstracted()
            geometry = self.geometry_factory(context).score_round(evidence)
            candidate_paths = {
                mode.candidate_id: evidence.trajectories.positions[
                    mode.sample_index
                ]
                for mode in evidence.candidates
            }
            overlay = self.combined_renderer.render(
                observation_image=context.observation_image,
                candidate_paths=candidate_paths,
                output_path=round_dir / "all_candidates.png",
            )
            posthoc_only = bool(context.metadata.get('initialization_posthoc_only', False))
            planner_enabled = bool(context.metadata.get('planner_steering_enabled', True)) and not posthoc_only
            if not planner_enabled:
                # VLS/FK already produced these particles. Preserve its order
                # and take the first non-vetoed particle; no semantic ranking,
                # stage judgment or online Planner request. This does NOT
                # change the learned verifier or the formal retry protocol.
                safe = {item.candidate_id for item in geometry if not item.hard_safety_veto}
                selected_id = next((item.candidate_id for item in evidence.candidates
                                    if item.candidate_id in safe), None)
                phase = 'initialization' if posthoc_only else 'formal_online_planner_disabled'
                reason = f'{phase}: original VLS particle order, hard safety veto only; not an LLM judgment'
                semantic = SemanticPlan(
                    tuple(SemanticCandidateScore(item.candidate_id,0.,reason) for item in evidence.candidates),
                    '', 'UNKNOWN', 0., 'local_vls_particle_order', 'local-vls-selection-v1',
                    raw_response={'metadata':{'provider':'local_policy','planner_called':False,
                                             'planner_steering_enabled':False, 'phase':phase,
                                             'semantic_scores_are_placeholders':True}},
                    selected_candidate_id=selected_id, selection_reason=reason)
            else:
                semantic = score_semantics_with_network_recovery(
                    self.planner,
                    context,
                    evidence,
                    geometry,
                    overlay.path,
                    recovery_label="online mode-aware runtime",
                    object_distances=_endpoint_object_distances(
                        evidence,
                        context.metadata.get("object_positions", {}),
                    ),
                    progress_history=context.metadata.get("progress_history", ()),
                )
            self._last_semantic_stage_id = (
                None if not planner_enabled
                else semantic.observed_stage_id)
            self._last_semantic_confidence = semantic.stage_confidence
            semantic_failure_types = tuple(
                sorted(
                    {
                        str(value)
                        for score in semantic.candidate_scores
                        for value in score.predicted_failure_types
                        if str(value).strip()
                    }
                )
            )
            selected = select_execution_candidate(
                evidence.candidates, geometry, semantic.candidate_scores, semantic.selected_candidate_id
            )
            internal = self.controller.mark_scored(has_safe_candidate=selected is not None)
            if selected is None:
                self.incidents.record_fact(episode_id=self.episode_id,
                    context_id=f"{context.context_id}:round:{self._round_id}", kind="safety_veto",
                    payload={"task":context.task_instruction, "policy_id":batch.checkpoint_id,
                             "candidate_count":len(evidence.candidates), "geometry":[asdict(x) for x in geometry],
                             "multimodal_evidence":{"path":str(evidence_path),"sha256":sha256_file(evidence_path),"kind":"historical_evidence"},
                             "remaining_budget":self.controller.state.remaining_budget,
                             "label_status":"CENSORED_NOT_A_CAPABILITY_LABEL"})
                if was_fresh:
                    route = self.controller.force_expand("no_safe_mode_after_fresh_sampling")
                    if route.route is ControllerRoute.ABORT:
                        self._close_factual_labels(success=False, censored=True, reason="safety_abort")
                        decision = RuntimeDecision(RuntimeStatus.ABORT, None, route, self._round_id,
                                                   error=route.reason)
                        self._save_summary(round_dir, decision, geometry, semantic)
                        return decision
                    self._close_factual_labels(success=False, censored=self.controller.state.remaining_budget > 0, reason="expansion")
                    decision = RuntimeDecision(
                        RuntimeStatus.EXPAND,
                        None,
                        route,
                        self._round_id,
                        semantic_failure_types=semantic_failure_types,
                        required_trajectory_pattern=semantic.required_trajectory_pattern,
                        analysis_path=str(analysis_path),
                        evidence_path=str(evidence_path),
                    )
                else:
                    decision = RuntimeDecision(
                        RuntimeStatus.INTERNAL_RESAMPLE,
                        None,
                        internal,
                        self._round_id,
                        semantic_failure_types=semantic_failure_types,
                        required_trajectory_pattern=semantic.required_trajectory_pattern,
                        analysis_path=str(analysis_path),
                        evidence_path=str(evidence_path),
                    )
                self._save_summary(round_dir, decision, geometry, semantic)
                return decision

            verifier_prediction = None
            verifier_decision = None
            verifier_logits = None
            p_expansion = None
            verifier_input = None
            opportunity_retry_index = (
                int(self.controller.state.retry_index) if was_fresh else None
            )
            opportunity_remaining_budget = (
                int(self.controller.state.remaining_budget) if was_fresh else None
            )
            if was_fresh:
                if scene_feature is None:
                    raise RuntimeError(
                        "post-failure decisions require the immutable theta0 scene feature"
                    )
                diagnostics = evidence.sampling_diagnostics
                verifier_input = build_verifier_input(
                    scene_feature=scene_feature,
                    evidence=evidence,
                    geometry=geometry,
                    semantics=semantic.candidate_scores,
                    failure_count=self.controller.state.failure_count,
                    remaining_budget=int(opportunity_remaining_budget),
                    retry_budget=int(self.controller.retry_budget),
                    ess_ratio=diagnostics.ess_ratio if diagnostics else 1.0,
                    unique_ratio=diagnostics.unique_ratio if diagnostics else 1.0,
                    executed_history=np.asarray(self.executed_history, dtype=np.float32).reshape(-1, 15),
                    backbone_id=self.backbone_id,
                    decision_step=len(self.executed_history),
                )
            baseline_needs_verifier = (
                self.config.baseline_kind
                == BaselineKind.VERIFIER_NO_LOOKUP.value
            )
            production_needs_verifier = (
                not self.config.baseline_kind
                and self.config.controller_mode == "learned_verifier"
            )
            if was_fresh and (baseline_needs_verifier or production_needs_verifier):
                if self.verifier is None:
                    raise RuntimeError(
                        "learned verifier mode requires a deployed verifier and theta0 scene feature"
                    )
                assert verifier_input is not None
                verifier_prediction = self.verifier.predict(verifier_input)
                verifier_decision = verifier_prediction.route
                verifier_logits = verifier_prediction.logits
                p_expansion = verifier_prediction.p_expansion
            baseline_decision = None
            if was_fresh and self.baseline_router is not None:
                safe_geometry = [
                    item for item in geometry if not item.hard_safety_veto
                ]
                opportunity_id = str(
                    context.metadata.get("opportunity_id")
                    or (snapshot.snapshot_id if snapshot is not None else "")
                    or f"{context.context_id}:round:{self._round_id}"
                )
                baseline_decision = self.baseline_router.decide(
                    BaselineOpportunity(
                        opportunity_id=opportunity_id,
                        retry_index=int(opportunity_retry_index),
                        active_candidate_count=len(safe_geometry),
                        max_semantic_score=max(
                            float(item.semantic_score)
                            for item in semantic.candidate_scores
                        ),
                        min_collision_risk=(
                            min(float(item.collision_risk) for item in safe_geometry)
                            if safe_geometry
                            else 1.0
                        ),
                        learned_p_expansion=p_expansion,
                        learned_verifier_route=verifier_decision,
                        oracle_should_expand=context.metadata.get(
                            "oracle_should_expand"
                        ),
                    )
                )
            behavior_propensity = float(
                context.metadata.get("behavior_propensity", 1.0)
            )
            exploration_applied = False
            exploration_override = None
            route = self.controller.route_scored_batch(
                verifier_decision=verifier_decision,
                route_override=(
                    baseline_decision.route
                    if baseline_decision is not None
                    else exploration_override
                ),
                override_reason=(
                    baseline_decision.reason
                    if baseline_decision is not None
                    else (
                        "epsilon_factual_retry_exploration"
                        if exploration_applied
                        else ""
                    )
                ),
                override_verifier_called=(
                    baseline_needs_verifier or exploration_applied
                ),
            )
            if not planner_enabled and route.reason == 'planner_selected_safe_candidate':
                route = replace(route,reason=('initialization_vls_policy_particle' if posthoc_only
                                              else 'local_vls_policy_particle'))
            status = {
                ControllerRoute.EXECUTE: RuntimeStatus.EXECUTE,
                ControllerRoute.RESTEER: RuntimeStatus.RESTEER,
                ControllerRoute.EXPAND: RuntimeStatus.EXPAND,
                ControllerRoute.ABORT: RuntimeStatus.ABORT,
            }[route.route]
            if status is RuntimeStatus.EXPAND:
                self._close_factual_labels(success=False, censored=self.controller.state.remaining_budget > 0, reason="expansion")
            record_id = uuid4().hex if was_fresh else None
            decision = RuntimeDecision(
                status=status,
                selected=selected if status in {RuntimeStatus.EXECUTE, RuntimeStatus.RESTEER} else None,
                route=route,
                round_id=self._round_id,
                verifier_decision=verifier_decision,
                verifier_logits=verifier_logits,
                p_expansion=p_expansion,
                record_id=record_id,
                semantic_failure_types=semantic_failure_types,
                required_trajectory_pattern=semantic.required_trajectory_pattern,
                analysis_path=str(analysis_path),
                        evidence_path=str(evidence_path),
            )
            if was_fresh:
                if snapshot is None:
                    raise RuntimeError("post-failure verifier opportunity requires a decision snapshot")
                assert verifier_input is not None
                assert record_id is not None
                verifier_feature_path = save_verifier_input(
                    self.incidents.root / "sidecars" / f"{record_id}.npz",
                    verifier_input,
                    metadata={
                        "schema_version": "candidate-verifier-input-v3",
                        "context_id": context.context_id,
                        "policy_id": snapshot.policy_id,
                        "snapshot_id": snapshot.snapshot_id,
                        "round_id": self._round_id,
                        "candidate_ids": [mode.candidate_id for mode in evidence.candidates],
                        "retry_index": opportunity_retry_index,
                        "retry_budget": self.controller.retry_budget,
                        "remaining_budget": opportunity_remaining_budget,
                        "failure_count": self.controller.state.failure_count,
                        "retry_schedule": [
                            list(level) for level in self.config.retry_schedule
                        ],
                        "chunk_horizon": self.config.chunk_horizon,
                        "max_policy_steps": (
                            int(opportunity_remaining_budget)
                            * self.config.chunk_horizon
                        ),
                        "label_version": self.config.label_version,
                        "label_contract_hash": (
                            self.config.experiment_contract().contract_hash
                        ),
                        "gemini_thinking_level": (
                            self.config.verifier_thinking_level
                        ),
                        "semantic_model": semantic.model,
                        "planner_provenance": semantic.raw_response.get("metadata", {}),
                        "label_config": label_contract_payload(
                            self.config.experiment_contract()
                        ),
                    },
                )
                self.incidents.record_decision(
                    VerifierDecisionRecord(
                        record_id=record_id,
                        context_id=context.context_id,
                        policy_id=snapshot.policy_id,
                        snapshot_id=snapshot.snapshot_id,
                        snapshot_hash=snapshot.snapshot_hash,
                        scene_feature_path=str(scene_feature_path or ""),
                        verifier_feature_path=str(verifier_feature_path),
                        route=route.route.value,
                        verifier_decision=(
                            verifier_decision.value
                            if verifier_decision is not None
                            else None
                        ),
                        verifier_logits=verifier_logits,
                        p_expansion=p_expansion,
                        decision_rule=(
                            "head_argmax"
                            if verifier_decision is not None
                            else (
                                f"baseline:{self.config.baseline_kind}"
                                if self.config.baseline_kind
                                else self.config.controller_mode
                            )
                        ),
                        controller_mode=(
                            f"baseline:{self.config.baseline_kind}"
                            if self.config.baseline_kind
                            else self.config.controller_mode
                        ),
                        failure_count=self.controller.state.failure_count,
                        remaining_budget=int(opportunity_remaining_budget),
                        retry_budget=int(self.controller.retry_budget),
                        retry_index=int(opportunity_retry_index),
                        label_version=self.config.label_version,
                        behavior_propensity=float(
                            behavior_propensity
                        ),
                        provenance={
                            "round_id": self._round_id,
                            "retry_index": opportunity_retry_index,
                            "retry_budget": self.controller.retry_budget,
                            "remaining_budget": opportunity_remaining_budget,
                            "label_version": self.config.label_version,
                            "label_config": label_contract_payload(
                                self.config.experiment_contract()
                            ),
                            "semantic_model": semantic.model,
                            "semantic_prompt_version": semantic.prompt_version,
                            "planner_provenance": semantic.raw_response.get("metadata", {}),
                            "code_revision": context.metadata.get("code_revision"),
                            "candidate_count": len(evidence.candidates),
                            "semantic_failure_types": list(semantic_failure_types),
                            "required_trajectory_pattern": semantic.required_trajectory_pattern,
                            "episode_id": self.episode_id,
                            "route_reason": route.reason,
                            "label_eligible": route.label_eligible,
                            "rollout_complete": self.controller.state.rollout_complete,
                            "require_complete_rollout_before_expansion": self.config.require_complete_rollout_before_expansion,
                            "multimodal_evidence_path": str(evidence_path),
                            "round_analysis_path": str(analysis_path),
                            "round_analysis_sha256": sha256_file(analysis_path),
                            "round_metadata_path": str(analysis_path.with_suffix(".json")),
                            "round_metadata_sha256": sha256_file(
                                analysis_path.with_suffix(".json")
                            ),
                            "target_object_id": context.metadata.get("target_object_id"),
                            "baseline": (
                                baseline_decision.to_json()
                                if baseline_decision is not None
                                else None
                            ),
                            "epsilon_exploration": exploration_applied,
                            "group": {
                                key: (
                                    context.metadata.get("base_suite")
                                    if key == "suite"
                                    and context.metadata.get("base_suite")
                                    else context.metadata.get(key)
                                )
                                for key in (
                                    "suite",
                                    "task_id",
                                    "perturbation_variant",
                                    "init_state_id",
                                    "episode_id",
                                )
                            },
                        },
                    )
                )
                if (
                    status is RuntimeStatus.RESTEER
                    and not self.config.baseline_kind
                ):
                    data_split = str(
                        context.metadata.get("verifier_split", "train")
                    )
                    if data_split not in {"train", "calibration", "test"}:
                        raise ValueError("invalid verifier_split for factual label")
                    self._pending_factual.append(
                        {
                            "record_id": record_id,
                            "policy_id": snapshot.policy_id,
                            "snapshot_hash": snapshot.snapshot_hash,
                            "behavior_propensity": behavior_propensity,
                            "data_split": data_split,
                            "label_config": label_contract_payload(
                                self.config.experiment_contract()
                            ),
                        }
                    )
            self._execution_context = record_id or f"{context.context_id}:round:{self._round_id}"
            self._execution_policy = batch.checkpoint_id
            self._selected_candidate_id = selected.candidate_id
            self.incidents.record_fact(
                episode_id=self.episode_id, context_id=self._execution_context, kind="decision_context",
                payload={"task": context.task_instruction, "analysis_path": str(analysis_path),
                         "multimodal_evidence": {"path": str(evidence_path), "sha256": sha256_file(evidence_path), "kind": "historical_evidence"},
                         "candidate_count": batch.sample_count, "selected_candidate_id": selected.candidate_id,
                         "route": route.route.value, "policy_id": batch.checkpoint_id,
                         "verifier_proposal": verifier_decision.value if verifier_decision else None,
                         "route_reason": route.reason, "label_eligible": route.label_eligible,
                         "rollout_complete": self.controller.state.rollout_complete,
                         "verifier_id": self.verifier.artifact_root.name if self.verifier else None,
                         "step": len(self.executed_history), "retry_index": opportunity_retry_index,
                         "remaining_budget": opportunity_remaining_budget,
                         "image_path": str(overlay.path), "image_kind": "real_observation_with_predicted_overlay",
                         "semantic": semantic.raw_response})
            self._save_summary(round_dir, decision, geometry, semantic)
            if status is RuntimeStatus.EXPAND:
                self.incidents.record_fact(episode_id=self.episode_id, context_id=self._execution_context,
                    kind="retry_outcome", payload={"native_success":False,
                        "censored":self.controller.state.remaining_budget > 0,
                        "stop_reason":"expansion", "retry_chunks_executed":self.controller.state.retry_index,
                        "remaining_budget":self.controller.state.remaining_budget,
                        "policy_id":batch.checkpoint_id, "retry_budget":self.controller.retry_budget})
            return decision
        except Exception as exc:
            self._pending_factual = []
            route = self.controller.abort(f"{type(exc).__name__}: {exc}")
            return RuntimeDecision(
                status=RuntimeStatus.ABORT,
                selected=None,
                route=route,
                round_id=self._round_id,
                error=route.reason,
            )

    def _close_factual_labels(self, *, success: bool, censored: bool = False, reason: str = "") -> None:
        pending, self._pending_factual = self._pending_factual, []
        for item in pending:
            self.incidents.record_fact(
                episode_id=self.episode_id, context_id=str(item["record_id"]),
                kind="retry_outcome", payload={
                    **item, "native_success": bool(success), "censored": bool(censored),
                    "stop_reason": reason, "retry_chunks_executed": self.controller.state.retry_index,
                    "remaining_budget": self.controller.state.remaining_budget,
                    "retry_budget": self.controller.retry_budget,
                    "interpretation": "observation_only_not_a_training_label",
                })

    def record_execution_step(self, action, pose, *, native_success: bool, images=None):
        action = np.asarray(action, dtype=np.float32).reshape(-1)[:7]
        position = np.asarray(pose.position, dtype=np.float32)
        orientation = np.asarray(pose.quaternion, dtype=np.float32)[[1, 2, 3, 0]]
        row = np.concatenate((action, position, orientation, [action[-1]]))
        if row.shape != (15,) or not np.isfinite(row).all():
            raise ValueError("history must contain physical OSC actions and observed poses")
        self.executed_history.append(row.tolist())
        self.incidents.record_fact(
            episode_id=self.episode_id, context_id=str(self._execution_context or ""),
            kind="executed_step", payload={"step": len(self.executed_history),
                "action_osc": action.tolist(), "observed_pose": row[7:14].tolist(),
                "native_success": bool(native_success), "policy_id": getattr(self, "_execution_policy", ""),
                "candidate_id": getattr(self, "_selected_candidate_id", None),
                "retry_index": self.controller.state.retry_index})
        if images:
            self.incidents.record_video_frame(self.episode_id, images,
                                             context_id=str(self._execution_context or ""),
                                             step=len(self.executed_history))

    @staticmethod
    def _save_summary(round_dir: Path, decision: RuntimeDecision, geometry: Any, semantic: Any) -> None:
        atomic_write_json(
            round_dir / "runtime_decision.json",
            {
                "status": decision.status.value,
                "selected": asdict(decision.selected) if decision.selected else None,
                "route": (
                    {
                        "route": decision.route.route.value,
                        "reason": decision.route.reason,
                        "phase": decision.route.phase.value,
                        "remaining_budget": decision.route.remaining_budget,
                        "verifier_called": decision.route.verifier_called,
                        "label_eligible": decision.route.label_eligible,
                    }
                    if decision.route
                    else None
                ),
                "round_id": decision.round_id,
                "verifier_decision": (
                    decision.verifier_decision.value
                    if decision.verifier_decision is not None
                    else None
                ),
                "verifier_logits": decision.verifier_logits,
                "p_expansion": decision.p_expansion,
                "record_id": decision.record_id,
                "semantic_failure_types": list(decision.semantic_failure_types),
                "required_trajectory_pattern": decision.required_trajectory_pattern,
                "analysis_path": decision.analysis_path,
                "evidence_path": decision.evidence_path,
                "analysis_sha256": (
                    sha256_file(Path(decision.analysis_path))
                    if decision.analysis_path
                    else None
                ),
                "analysis_metadata_path": (
                    str(Path(decision.analysis_path).with_suffix(".json"))
                    if decision.analysis_path
                    else None
                ),
                "analysis_metadata_sha256": (
                    sha256_file(Path(decision.analysis_path).with_suffix(".json"))
                    if decision.analysis_path
                    else None
                ),
                "geometry": [asdict(item) for item in geometry],
                "semantic": {
                    "candidate_scores": [asdict(item) for item in semantic.candidate_scores],
                    "required_trajectory_pattern": semantic.required_trajectory_pattern,
                    "observed_stage_id": semantic.observed_stage_id,
                    "stage_confidence": semantic.stage_confidence,
                    "model": semantic.model,
                    "prompt_version": semantic.prompt_version,
                },
            },
        )


def _endpoint_object_distances(
    evidence: Any,
    object_positions: Any,
) -> dict[str, dict[str, float]]:
    if not isinstance(object_positions, dict):
        return {}
    positions = {}
    for name, raw in object_positions.items():
        value = np.asarray(raw, dtype=np.float64)
        if value.shape == (3,) and np.isfinite(value).all():
            positions[str(name)] = value
    result: dict[str, dict[str, float]] = {}
    for mode in evidence.candidates:
        sample_index = mode.sample_index
        endpoint = np.asarray(
            evidence.trajectories.positions[sample_index, -1], dtype=np.float64
        )
        result[mode.candidate_id] = {
            name: float(np.linalg.norm(endpoint - object_position))
            for name, object_position in positions.items()
        }
    return result


def _save_round_evidence(round_dir: Path, evidence: Any) -> Path:
    """Persist the exact candidate support used by a verifier opportunity."""

    import os

    path = Path(round_dir) / "analysis.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            actions=evidence.action_batch.actions,
            positions=evidence.trajectories.positions,
            orientations=evidence.trajectories.orientations,
            grippers=evidence.trajectories.grippers,
            candidate_ids=np.asarray([c.candidate_id for c in evidence.candidates]),
        )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    diagnostics = (
        asdict(evidence.sampling_diagnostics)
        if evidence.sampling_diagnostics is not None
        else None
    )
    actions = np.ascontiguousarray(evidence.action_batch.actions)
    atomic_write_json(
        path.with_suffix(".json"),
        _round_metadata_jsonable(
            {
                "schema_version": "candidate-round-evidence-v3",
                "context_id": evidence.context_id,
                "round_id": int(evidence.round_id),
                "checkpoint_id": evidence.checkpoint_id,
                "sample_ids": list(evidence.action_batch.sample_ids),
                "action_space": evidence.action_batch.action_space,
                "coordinate_frame": evidence.action_batch.coordinate_frame,
                "action_shape": list(actions.shape),
                "action_dtype": str(actions.dtype),
                "action_sha256": hashlib.sha256(actions.tobytes()).hexdigest(),
                "analysis_sha256": sha256_file(path),
                "sampling_diagnostics": diagnostics,
                "candidates": [asdict(candidate) for candidate in evidence.candidates],
                "evidence_kind": "predicted_candidates_not_executed_actions",
            }
        ),
    )
    return path


def _round_metadata_jsonable(value: Any) -> Any:
    """Convert numerical audit metadata without silently dropping channels."""

    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _round_metadata_jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_round_metadata_jsonable(item) for item in value]
    return value


__all__ = ["CandidateRuntime", "RuntimeDecision", "RuntimeStatus"]
