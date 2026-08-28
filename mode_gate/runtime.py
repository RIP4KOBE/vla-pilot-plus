"""Fast-loop orchestration: abstract, score, select, verify only after failure."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
from .cards import CombinedModeCardRenderer
from .config import ModeGateConfig
from .gate import TrajectoryModeGate
from .geometry import GeometryScorer, select_execution_medoid
from .incidents import (
    IncidentMemory,
    VerifierDecisionRecord,
    VerifierLabelRecord,
)
from .io_utils import atomic_write_json, sha256_file
from .progress import ProgressMonitor
from .semantic_planner import GeminiSemanticPlanner
from .state_machine import EpisodeChunkController, RouteDecision
from .types import (
    ActionChunkBatch,
    ControllerRoute,
    DecisionSnapshot,
    GateContext,
    ProgressEvidence,
    SelectedExecution,
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


class ModeAwareRuntime:
    def __init__(
        self,
        *,
        config: ModeGateConfig,
        gate: TrajectoryModeGate,
        planner: GeminiSemanticPlanner,
        combined_renderer: CombinedModeCardRenderer,
        geometry_factory: Callable[[GateContext], GeometryScorer],
        incidents: IncidentMemory,
        verifier: DeployedVerifierPredictor | None = None,
    ) -> None:
        self.config = config
        self.baseline_router = build_baseline_router(
            kind=config.baseline_kind,
            budget=config.baseline_budget,
            minimum_modes=config.baseline_minimum_modes,
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
        self.progress_monitor = ProgressMonitor()
        self.progress_history: list[dict[str, Any]] = []
        self._last_semantic_stage_id: str | None = None
        self._last_semantic_confidence = 0.0
        self._round_id = 0
        self._pending_factual: list[dict[str, Any]] = []

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
        if terminal_timeout:
            self._pending_factual = []
        elif progress.task_success or progress.advanced:
            self._close_factual_labels(success=True)
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
    ) -> RuntimeDecision:
        self._round_id += 1
        was_fresh = self.controller.state.verification_due
        try:
            self.controller.begin_sampling()
            round_dir = Path(artifact_root) / context.context_id / f"round_{self._round_id:03d}"
            evidence = self.gate.analyze(context, batch, round_dir)
            analysis_path = _save_round_evidence(round_dir, evidence)
            self.controller.mark_abstracted()
            geometry = self.geometry_factory(context).score_round(evidence)
            mode_paths = {
                mode.mode_id: evidence.trajectories.positions[
                    int(mode.representative_indices["medoid"])
                ]
                for mode in evidence.modes
            }
            overlay = self.combined_renderer.render(
                observation_image=context.observation_image,
                mode_paths=mode_paths,
                output_path=round_dir / "combined_modes.png",
            )
            semantic = self.planner.score(
                context,
                evidence,
                geometry,
                overlay.path,
                object_distances=_endpoint_object_distances(
                    evidence,
                    context.metadata.get("object_positions", {}),
                ),
                progress_history=context.metadata.get("progress_history", ()),
            )
            self._last_semantic_stage_id = semantic.observed_stage_id
            self._last_semantic_confidence = semantic.stage_confidence
            semantic_failure_types = tuple(
                sorted(
                    {
                        str(value)
                        for score in semantic.mode_scores
                        for value in score.predicted_failure_types
                        if str(value).strip()
                    }
                )
            )
            selected = select_execution_medoid(
                evidence.modes, geometry, semantic.mode_scores
            )
            internal = self.controller.mark_scored(has_safe_mode=selected is not None)
            if selected is None:
                if was_fresh:
                    route = self.controller.force_expand("no_safe_mode_after_fresh_sampling")
                    self._close_factual_labels(success=False)
                    decision = RuntimeDecision(
                        RuntimeStatus.EXPAND,
                        None,
                        route,
                        self._round_id,
                        semantic_failure_types=semantic_failure_types,
                        required_trajectory_pattern=semantic.required_trajectory_pattern,
                        analysis_path=str(analysis_path),
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
                    semantics=semantic.mode_scores,
                    failure_count=self.controller.state.failure_count,
                    remaining_budget=int(opportunity_remaining_budget),
                    ess_ratio=diagnostics.ess_ratio if diagnostics else 1.0,
                    unique_ratio=diagnostics.unique_ratio if diagnostics else 1.0,
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
                        active_mode_count=len(safe_geometry),
                        max_semantic_score=max(
                            float(item.semantic_score)
                            for item in semantic.mode_scores
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
            if (
                was_fresh
                and baseline_decision is None
                and production_needs_verifier
                and verifier_decision is ControllerRoute.EXPAND
                and int(opportunity_remaining_budget) > 0
                and self.config.exploration_epsilon > 0.0
            ):
                material = (
                    f"verifier-exploration-v1\0{context.context_id}\0"
                    f"{snapshot.snapshot_id if snapshot is not None else ''}\0"
                    f"{opportunity_retry_index}\0{self.config.seed}"
                )
                draw = int.from_bytes(
                    hashlib.sha256(material.encode("utf-8")).digest()[:8], "big"
                ) / float(2**64)
                if draw < self.config.exploration_epsilon:
                    exploration_applied = True
                    exploration_override = ControllerRoute.RESTEER
                    behavior_propensity = self.config.exploration_epsilon
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
            status = {
                ControllerRoute.EXECUTE: RuntimeStatus.EXECUTE,
                ControllerRoute.RESTEER: RuntimeStatus.RESTEER,
                ControllerRoute.EXPAND: RuntimeStatus.EXPAND,
                ControllerRoute.ABORT: RuntimeStatus.ABORT,
            }[route.route]
            if status is RuntimeStatus.EXPAND:
                self._close_factual_labels(success=False)
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
                        "schema_version": "grounded-verifier-input-v1",
                        "context_id": context.context_id,
                        "policy_id": snapshot.policy_id,
                        "snapshot_id": snapshot.snapshot_id,
                        "round_id": self._round_id,
                        "mode_ids": [mode.mode_id for mode in evidence.modes],
                        "retry_index": opportunity_retry_index,
                        "remaining_budget": opportunity_remaining_budget,
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
                        behavior_propensity=float(
                            behavior_propensity
                        ),
                        provenance={
                            "round_id": self._round_id,
                            "retry_index": opportunity_retry_index,
                            "remaining_budget": opportunity_remaining_budget,
                            "semantic_model": semantic.model,
                            "semantic_prompt_version": semantic.prompt_version,
                            "code_revision": context.metadata.get("code_revision"),
                            "fit_metadata": evidence.fit_metadata,
                            "semantic_failure_types": list(semantic_failure_types),
                            "required_trajectory_pattern": semantic.required_trajectory_pattern,
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
                        }
                    )
            self._save_summary(round_dir, decision, geometry, semantic)
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

    def _close_factual_labels(self, *, success: bool) -> None:
        pending, self._pending_factual = self._pending_factual, []
        for item in pending:
            self.incidents.attach_label(
                VerifierLabelRecord(
                    record_id=str(item["record_id"]),
                    label_version="factual-online-retry-v1",
                    source="factual_online_retry",
                    branches=1,
                    successes=1 if success else 0,
                    p_expansion=0.0 if success else 1.0,
                    policy_id=str(item["policy_id"]),
                    snapshot_hash=str(item["snapshot_hash"]),
                    data_split=str(item["data_split"]),
                    weak=False,
                    weight=1.0,
                    behavior_propensity=float(item["behavior_propensity"]),
                )
            )

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
                    "mode_scores": [asdict(item) for item in semantic.mode_scores],
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
    for mode in evidence.modes:
        sample_index = int(mode.representative_indices["medoid"])
        endpoint = np.asarray(
            evidence.trajectories.positions[sample_index, -1], dtype=np.float64
        )
        result[mode.mode_id] = {
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
            normalized_positions=evidence.normalized_positions,
            normalized_rotvecs=evidence.normalized_rotvecs,
            normalized_grippers=evidence.normalized_grippers,
            descriptors=evidence.descriptors,
            reduced_descriptors=evidence.reduced_descriptors,
            labels=evidence.labels,
            responsibilities=evidence.responsibilities,
            medoid_indices=np.asarray(
                [
                    int(mode.representative_indices["medoid"])
                    for mode in evidence.modes
                ],
                dtype=np.int64,
            ),
            mode_weights=np.asarray(
                [float(mode.weight) for mode in evidence.modes], dtype=np.float64
            ),
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
                "schema_version": "mode-round-evidence-v2",
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
                "fit_degraded": bool(evidence.fit_degraded),
                "fit_metadata": evidence.fit_metadata,
                "sampling_diagnostics": diagnostics,
                "modes": [
                    {
                        "mode_id": mode.mode_id,
                        "component_index": int(mode.component_index),
                        "weight": float(mode.weight),
                        "member_indices": mode.member_indices,
                        "representative_indices": mode.representative_indices,
                        "representative_sample_ids": mode.representative_sample_ids,
                        "projection_unavailable": bool(mode.projection_unavailable),
                        "statistics": mode.statistics,
                    }
                    for mode in evidence.modes
                ],
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


__all__ = ["ModeAwareRuntime", "RuntimeDecision", "RuntimeStatus"]
