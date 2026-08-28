"""Executable hgpu1 snapshot replay for audit and staged-policy relabeling.

This is the concrete simulator integration behind
``NewPolicyReplayCoordinator``.  It recreates the original LIBERO suite,
loads theta0 only for frozen scene/signature features, separately fresh-loads
the target policy, restores each exact post-failure snapshot, and runs the
fixed four-level RE-STEER estimand with adaptive 16→32→64 branches.

No Registry deployment is read or mutated while this worker runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import gc
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from .black_box import as_numpy_actions
from .checkpoint_math import checkpoint_digest
from .counterfactual import (
    CounterfactualReplayWorker,
    FixedBudgetResteerExecutor,
    FreshMedoidSelection,
)
from .geometry import select_execution_medoid
from .incidents import IncidentMemory
from .io_utils import atomic_write_json, sha256_file
from .policy_evaluator import runtime_suite_name
from .snapshots import DecisionSnapshotStore
from .types import ActionChunkBatch, GateContext, ProgressEvidence, SamplingCondition
from .verifier import build_verifier_input, save_verifier_input


@dataclass(frozen=True)
class OfflineCandidateAnalysis:
    execution_actions: Any
    evidence: Any
    geometry: Sequence[Any]
    semantic: Any
    selected: Any | None
    context: GateContext


def validate_replay_plan(plan_path: Path) -> dict[str, Any]:
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema_version") != "new-policy-counterfactual-plan-v2":
        raise ValueError("unsupported counterfactual replay plan")
    expected_hash = str(plan.get("plan_sha256") or "")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    actual_hash = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if expected_hash != actual_hash:
        raise ValueError("counterfactual replay plan checksum mismatch")
    checkpoint = Path(str(plan["checkpoint_path"])).resolve()
    if checkpoint_digest(checkpoint) != str(plan["checkpoint_digest"]):
        raise ValueError("counterfactual target checkpoint digest changed")
    contexts = tuple(plan.get("contexts", ()))
    record_ids = [str(value["record_id"]) for value in contexts]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("counterfactual replay plan contains duplicate records")
    if tuple(plan.get("adaptive_branches", ())) != (16, 32, 64):
        raise ValueError("counterfactual branch schedule must be 16→32→64")
    if plan.get("decision_rule") != "head_argmax":
        raise ValueError("counterfactual plan must use direct head argmax")
    snapshot_root = Path(str(plan["snapshot_root"])).resolve()
    incident_root = Path(str(plan["incident_root"])).resolve()
    if not snapshot_root.is_dir() or not incident_root.is_dir():
        raise FileNotFoundError("counterfactual snapshot/incident roots are unavailable")
    for context in contexts:
        snapshot_id = str(context["snapshot_id"])
        manifest_path = snapshot_root / snapshot_id / "manifest.json"
        if manifest_path.resolve() != Path(
            str(context["snapshot_manifest_path"])
        ).resolve():
            raise ValueError("snapshot manifest path escaped the frozen snapshot root")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("snapshot_id") != snapshot_id
            or manifest.get("snapshot_hash") != context.get("snapshot_hash")
        ):
            raise ValueError("counterfactual context/snapshot identity mismatch")
        if str(context.get("target_policy_id")) != str(plan["policy_id"]):
            raise ValueError("counterfactual context targets another policy")
        if str(context.get("data_split")) not in {
            "train",
            "calibration",
            "test",
        }:
            raise ValueError("counterfactual context has no frozen verifier split")
    return plan


class HgpuReplayApplication:
    """One target policy plus one LIBERO runtime suite on a selected GPU."""

    def __init__(
        self,
        *,
        repo_root: Path,
        runtime_suite: str,
        task_ids: Sequence[int],
        checkpoint: Path,
        policy_id: str,
        device: str,
        artifact_root: Path,
        snapshot_root: Path,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.runtime_suite = str(runtime_suite)
        self.task_ids = tuple(int(value) for value in task_ids)
        if not self.task_ids or len(set(self.task_ids)) != len(self.task_ids):
            raise ValueError("replay task catalog must be non-empty and unique")
        self.policy_id = str(policy_id)
        self.device = str(device)
        self.artifact_root = Path(artifact_root).resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.snapshots = DecisionSnapshotStore(Path(snapshot_root))
        self.main = self._build_main()
        self.adapter = self.main.adapter
        self.policy, self.preprocessor = self._load_target_policy(Path(checkpoint))
        self.current_context: Mapping[str, Any] | None = None
        self.current_manifest: Mapping[str, Any] | None = None
        self.current_guidance_functions: Sequence[Any] = ()

    def _build_main(self) -> Any:
        from hydra import compose, initialize_config_dir

        from main import Main

        config_dir = self.repo_root / "configs"
        run_root = self.artifact_root / "application"
        run_root.mkdir(parents=True, exist_ok=True)
        isolated = self.artifact_root / "isolated_runtime"
        with initialize_config_dir(
            version_base=None, config_dir=str(config_dir)
        ):
            config = compose(
                config_name="config",
                overrides=[
                    "backend=libero",
                    f"backend.libero.suite_name={self.runtime_suite}",
                    "backend.libero.task_ids_filter=["
                    + ",".join(map(str, self.task_ids))
                    + "]",
                    f"main.episode_num={len(self.task_ids)}",
                    "main.use_guidance=false",
                    "main.use_vlm_stage_recognition=false",
                    "main.debug_draw_trajectory=false",
                    f"main.output_dir={run_root}",
                    "policy.type=pi05",
                    "mode_gate.enabled=true",
                    "mode_gate.controller_mode=fixed_budget_4",
                    f"mode_gate.registry_root={isolated / 'registry'}",
                    f"mode_gate.incident_root={isolated / 'incidents'}",
                    f"mode_gate.snapshot_root={isolated / 'snapshots'}",
                    f"mode_gate.slow_loop_root={isolated / 'slow_loop'}",
                    f"device={self.device}",
                    f"hydra.run.dir={run_root}",
                ],
            )
        return Main(config)

    def _load_target_policy(self, checkpoint: Path) -> tuple[Any, Any]:
        from lerobot.policies.factory import make_pre_post_processors

        from core.pi05_steer import PI05PolicySteer

        target = PI05PolicySteer.from_pretrained(str(checkpoint))
        target.to(self.device)
        overrides: dict[str, Any] = {
            "device_processor": {"device": str(target.config.device)}
        }
        tokenizer = self.main.policy_type_config.get("tokenizer_path", None)
        if tokenizer:
            overrides["tokenizer_processor"] = {"tokenizer_name": str(tokenizer)}
        preprocessor, postprocessor = make_pre_post_processors(
            policy_cfg=target.config,
            pretrained_path=self.main.mode_gate_config.theta0_checkpoint,
            preprocessor_overrides=overrides,
        )
        target.post_init(
            adapter=self.adapter,
            postprocessor=postprocessor,
            sample_batch_size=self.main.mode_gate_config.sample_count,
            policy_config=self.main.policy_type_config,
        )
        target.eval()
        return target, preprocessor

    def prepare_context(
        self,
        context: Mapping[str, Any],
        manifest: Mapping[str, Any],
    ) -> None:
        provenance = manifest.get("provenance", {})
        required = {
            "guidance",
            "sampling_config",
            "planner_prompt_version",
            "code_revision",
            "bddl_sha256",
            "init_states_sha256",
        }
        missing = sorted(required - set(provenance))
        if missing:
            raise ValueError(
                "snapshot predates exact replay provenance: " + ", ".join(missing)
            )
        expected_runtime = str(
            provenance.get("runtime_suite")
            or runtime_suite_name(
                str(provenance["suite"]),
                str(provenance["perturbation_variant"]),
            )
        )
        if expected_runtime != self.runtime_suite:
            raise ValueError("snapshot belongs to a different LIBERO runtime suite")
        if (
            provenance["planner_prompt_version"]
            != self.main.mode_gate_config.planner_prompt_version
        ):
            raise ValueError("snapshot Gemini prompt version is not replay-compatible")
        self.current_context = dict(context)
        self.current_manifest = dict(manifest)
        self.current_guidance_functions = self._load_guidance(provenance)

    def _load_guidance(self, provenance: Mapping[str, Any]) -> Sequence[Any]:
        guidance = provenance["guidance"]
        if not bool(guidance.get("enabled", False)):
            return ()
        files = tuple(guidance.get("files", ()))
        for value in files:
            path = Path(str(value["path"]))
            if not path.is_file() or sha256_file(path) != str(value["sha256"]):
                raise ValueError("snapshot guidance source changed or disappeared")
        stage = int(guidance["stage"])
        candidates = [
            Path(str(value["path"]))
            for value in files
            if Path(str(value["path"])).name == f"stage{stage}_guidance.txt"
        ]
        if len(candidates) != 1:
            raise ValueError("snapshot has no unique current-stage guidance source")
        from utils.guidance_utils import load_functions_from_txt

        # PI05's guidance path distinguishes a list of reward functions from a
        # single callable.  Preserve that public contract; passing a tuple is
        # interpreted as one callable and silently disables gradient guidance.
        return list(load_functions_from_txt(str(candidates[0]), validate=True))

    def restore(self) -> dict[str, Any]:
        if self.current_context is None or self.current_manifest is None:
            raise RuntimeError("prepare_context must run before snapshot restore")
        restored = self.snapshots.restore(
            str(self.current_context["snapshot_id"]),
            adapter=self.adapter,
            policy=self.policy,
            stateful_components={"keypoint_tracker": self.main.keypoint_tracker},
            restore_policy_state=False,
        )
        provenance = self.current_manifest["provenance"]
        actual = self.adapter.get_context_provenance()
        for name in (
            "runtime_suite",
            "task_id",
            "perturbation_variant",
            "init_state_id",
            "bddl_sha256",
            "init_states_sha256",
        ):
            if str(actual.get(name)) != str(provenance.get(name)):
                raise ValueError(f"restored snapshot provenance mismatch: {name}")
        return restored

    def build_feature(
        self,
        *,
        context: Mapping[str, Any],
        policy_id: str,
        output_path: Path,
    ) -> Path:
        if policy_id != self.policy_id or context is not self.current_context:
            # Mapping identity is intentionally strict inside one context loop.
            if policy_id != self.policy_id or str(context.get("record_id")) != str(
                (self.current_context or {}).get("record_id")
            ):
                raise ValueError("feature builder context/policy mismatch")
        self.restore()
        seed = _feature_seed(
            str(context["record_id"]), self.policy_id, str(context["snapshot_hash"])
        )
        retry_index = int(self.current_manifest["controller_state"]["retry_index"])
        condition = SamplingCondition(
            seed=seed,
            retry_index=retry_index,
            guide_mult=1.0,
            diversity_mult=1.0,
        )
        analysis = self._sample_and_analyze(condition, purpose="feature")
        encoded = self.main.theta0_scene_encoder.encode(
            analysis.context.observation_image,
            analysis.context.task_instruction,
        )
        diagnostics = analysis.evidence.sampling_diagnostics
        verifier_input = build_verifier_input(
            scene_feature=encoded.joint_feature,
            evidence=analysis.evidence,
            geometry=analysis.geometry,
            semantics=analysis.semantic.mode_scores,
            failure_count=int(
                self.current_manifest["controller_state"]["failure_count"]
            ),
            remaining_budget=int(context["remaining_budget"]),
            ess_ratio=diagnostics.ess_ratio if diagnostics else 1.0,
            unique_ratio=diagnostics.unique_ratio if diagnostics else 1.0,
        )
        return save_verifier_input(
            Path(output_path),
            verifier_input,
            metadata={
                "schema_version": "grounded-verifier-input-v1",
                "record_id": context["record_id"],
                "snapshot_id": context["snapshot_id"],
                "target_policy_id": self.policy_id,
                "feature_seed": seed,
                "theta0_feature_id": encoded.feature_id,
                "theta0_cache_path": str(encoded.cache_path),
                "mode_ids": [mode.mode_id for mode in analysis.evidence.modes],
                "captured_code_revision": self.current_manifest["provenance"][
                    "code_revision"
                ],
                "replay_code_revision": self.main.mode_gate_source_revision,
            },
        )

    def sample_medoid(
        self,
        *,
        adapter: Any,
        policy: Any,
        condition: SamplingCondition,
    ) -> FreshMedoidSelection | None:
        if adapter is not self.adapter or policy is not self.policy:
            raise ValueError("fresh sampler received another adapter/policy")
        analysis = self._sample_and_analyze(condition, purpose="branch")
        if analysis.selected is None:
            return None
        index = int(analysis.selected.sample_index)
        actions = analysis.execution_actions[index]
        if isinstance(actions, torch.Tensor):
            actions = actions.detach().cpu().numpy()
        return FreshMedoidSelection(
            actions=np.asarray(actions),
            mode_id=analysis.selected.mode_id,
            sample_index=index,
            metadata={
                "sample_id": analysis.selected.sample_id,
                "semantic_model": analysis.semantic.model,
                "semantic_prompt_version": analysis.semantic.prompt_version,
            },
        )

    def _sample_and_analyze(
        self, condition: SamplingCondition, *, purpose: str
    ) -> OfflineCandidateAnalysis:
        if self.current_context is None or self.current_manifest is None:
            raise RuntimeError("no replay context is active")
        provenance = self.current_manifest["provenance"]
        sampling = provenance["sampling_config"]
        random.seed(condition.seed)
        np.random.seed(condition.seed % (2**32))
        torch.manual_seed(condition.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(condition.seed)
        observation = self.adapter.get_policy_observation(
            sample_num=self.main.mode_gate_config.sample_count
        )
        processed = self.preprocessor(observation)
        keypoints = self.main.keypoint_tracker.get_keypoint_positions()
        execution = self.policy.select_action(
            processed,
            generate_new_chunk=True,
            use_guidance=bool(self.current_guidance_functions),
            keypoints=keypoints,
            guidance_fns=self.current_guidance_functions or None,
            guide_scale=float(sampling["guide_scale"]) * condition.guide_mult,
            sigmoid_k=float(sampling["sigmoid_k"]),
            sigmoid_x0=float(sampling["sigmoid_x0"]),
            start_ratio=sampling.get("start_ratio"),
            use_diversity=bool(sampling["use_diversity"]),
            diversity_scale=(
                float(sampling["diversity_scale"]) * condition.diversity_mult
            ),
            MCMC_steps=int(sampling["MCMC_steps"]),
            use_fkd=bool(sampling["use_fkd"]),
            fkd_config=sampling.get("fkd"),
            global_step=int(provenance["global_step"]),
            current_stage=int(provenance["guidance"]["stage"]),
        )
        if hasattr(self.adapter, "env_postprocessor"):
            execution = self.adapter.env_postprocessor({"action": execution})[
                "action"
            ]
        candidate_getter = getattr(
            self.policy, "get_last_visualization_action_candidates", None
        )
        candidates = candidate_getter() if callable(candidate_getter) else None
        if candidates is None:
            candidates = execution
        elif hasattr(self.adapter, "env_postprocessor"):
            candidates = self.adapter.env_postprocessor({"action": candidates})[
                "action"
            ]
        candidate_actions = as_numpy_actions(candidates)
        image = np.asarray(self.adapter.get_vlm_image())
        instruction = str(provenance["task"])
        record_id = str(self.current_context["record_id"])
        gate_context = GateContext(
            context_id=(
                f"offline-{record_id}-{purpose}-{condition.seed:016x}"
            ),
            observation_image=image,
            task_instruction=instruction,
            task_stage=str(provenance["task_stage"]),
            metadata={
                **dict(provenance),
                **self.main._build_mode_context_metadata(instruction),
                "progress_history": tuple(provenance.get("progress_history", ())),
                "workspace_bounds": self.main.config.get(
                    "workspace_bounds",
                    ((-1.0, -1.0, 0.0), (1.0, 1.0, 1.5)),
                ),
            },
        )
        metadata: dict[str, Any] = {
            "sampling_condition": asdict(condition),
        }
        if "task_keypoints" in gate_context.metadata:
            metadata["task_keypoints"] = gate_context.metadata["task_keypoints"]
        diagnostics_getter = getattr(
            self.policy, "get_last_sampling_diagnostics", None
        )
        if callable(diagnostics_getter):
            diagnostics = diagnostics_getter()
            if diagnostics is not None:
                metadata["sampling_diagnostics"] = diagnostics
        batch = ActionChunkBatch(
            actions=candidate_actions,
            sample_ids=tuple(
                f"{gate_context.context_id}-s{index:03d}"
                for index in range(len(candidate_actions))
            ),
            context_id=gate_context.context_id,
            round_id=1,
            checkpoint_id=self.policy_id,
            action_space=str(self.adapter.get_action_space_info().get("type", "environment_action")),
            coordinate_frame="world",
            metadata=metadata,
        )
        round_dir = (
            self.artifact_root
            / "contexts"
            / record_id
            / f"{purpose}_{condition.seed:016x}"
        )
        evidence = self.main.mode_aware_runtime.gate.analyze(
            gate_context, batch, round_dir
        )
        geometry = self.main.mode_aware_runtime.geometry_factory(
            gate_context
        ).score_round(evidence)
        mode_paths = {
            mode.mode_id: evidence.trajectories.positions[
                int(mode.representative_indices["medoid"])
            ]
            for mode in evidence.modes
        }
        overlay = self.main.mode_aware_runtime.combined_renderer.render(
            observation_image=image,
            mode_paths=mode_paths,
            output_path=round_dir / "combined_modes.png",
        )
        semantic = self.main.mode_aware_runtime.planner.score(
            gate_context,
            evidence,
            geometry,
            overlay.path,
            object_distances=_endpoint_object_distances(
                evidence, gate_context.metadata.get("object_positions", {})
            ),
            progress_history=gate_context.metadata.get("progress_history", ()),
        )
        selected = select_execution_medoid(
            evidence.modes, geometry, semantic.mode_scores
        )
        return OfflineCandidateAnalysis(
            execution_actions=execution,
            evidence=evidence,
            geometry=geometry,
            semantic=semantic,
            selected=selected,
            context=gate_context,
        )

    @staticmethod
    def progress_observer(
        *,
        adapter: Any,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        task_success: bool,
    ) -> ProgressEvidence:
        before_count = before.get("completed_count")
        after_count = after.get("completed_count")
        advanced = (
            before_count is not None
            and after_count is not None
            and int(after_count) > int(before_count)
        )
        success = bool(task_success or after.get("task_success", False))
        return ProgressEvidence(
            stage_id=(
                f"bddl-goals:{after_count}/{after.get('goal_count')}"
                if advanced
                else "UNKNOWN"
            ),
            advanced=advanced,
            confidence=1.0 if advanced or success else 0.0,
            source="bddl_goal_predicates" if advanced else "unknown",
            task_success=success,
        )

    def close(self) -> None:
        close = getattr(self.adapter, "close", None)
        if callable(close):
            close()
        del self.policy
        del self.main
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def execute_replay_plan(
    plan_path: Path,
    *,
    repo_root: Path,
    device: str = "cuda:0",
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Execute one immutable plan without touching ``active.json``."""

    plan = validate_replay_plan(plan_path)
    contexts = tuple(plan.get("contexts", ()))
    result_path = Path(str(plan["result_path"]))
    if result_path.is_file():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            existing.get("schema_version") == "new-policy-counterfactual-result-v1"
            and existing.get("plan_sha256") == plan["plan_sha256"]
            and existing.get("complete") is True
        ):
            return existing
    incidents = IncidentMemory(Path(str(plan["incident_root"])))
    snapshots = DecisionSnapshotStore(Path(str(plan["snapshot_root"])))
    ledger = Path(
        ledger_path
        if ledger_path is not None
        else result_path.parent / "branches.jsonl"
    )
    grouped: dict[
        tuple[str, tuple[int, ...]],
        list[tuple[int, Mapping[str, Any], Mapping[str, Any]]],
    ] = {}
    for index, context in enumerate(contexts):
        manifest = json.loads(
            Path(str(context["snapshot_manifest_path"])).read_text(encoding="utf-8")
        )
        provenance = manifest["provenance"]
        runtime = str(
            provenance.get("runtime_suite")
            or runtime_suite_name(
                str(provenance["suite"]),
                str(provenance["perturbation_variant"]),
            )
        )
        catalog = _snapshot_task_catalog(
            Path(str(plan["snapshot_root"])), str(context["snapshot_id"])
        )
        grouped.setdefault((runtime, catalog), []).append((index, context, manifest))

    ordered_results: list[dict[str, Any] | None] = [None] * len(contexts)
    artifact_root = result_path.parent / "replay_artifacts"
    for runtime, task_ids in sorted(grouped):
        group_name = runtime + "__tasks_" + "_".join(map(str, task_ids))
        application = HgpuReplayApplication(
            repo_root=repo_root,
            runtime_suite=runtime,
            task_ids=task_ids,
            checkpoint=Path(str(plan["checkpoint_path"])),
            policy_id=str(plan["policy_id"]),
            device=device,
            artifact_root=artifact_root / group_name,
            snapshot_root=snapshots.root,
        )
        try:
            branch_executor = FixedBudgetResteerExecutor(
                fresh_sampler=application.sample_medoid,
                progress_observer=application.progress_observer,
            )
            replay_worker = CounterfactualReplayWorker(
                incidents=incidents,
                snapshots=snapshots,
                adapter=application.adapter,
                policy_loader=lambda policy_id, app=application: (
                    app.policy
                    if policy_id == app.policy_id
                    else _raise_policy_mismatch(policy_id)
                ),
                branch_executor=branch_executor,
                ledger_path=ledger,
                stateful_components={
                    "keypoint_tracker": application.main.keypoint_tracker
                },
            )
            for index, context, manifest in grouped[(runtime, task_ids)]:
                application.prepare_context(context, manifest)
                feature = application.build_feature(
                    context=context,
                    policy_id=str(plan["policy_id"]),
                    output_path=Path(str(context["fresh_feature_output_path"])),
                )
                result = replay_worker.run(
                    record_id=str(context["record_id"]),
                    policy_id=str(plan["policy_id"]),
                    label_version=(
                        f"new-policy-{plan['policy_id']}-{plan['plan_sha256'][:12]}"
                    ),
                    source="counterfactual_replay",
                    max_width=float(plan["max_posterior_width"]),
                    verifier_feature_path=feature,
                    data_split=str(context["data_split"]),
                )
                ordered_results[index] = asdict(result)
        finally:
            application.close()
    if any(value is None for value in ordered_results):
        raise RuntimeError("counterfactual replay did not complete every context")
    value = {
        "schema_version": "new-policy-counterfactual-result-v1",
        "plan_sha256": plan["plan_sha256"],
        "policy_id": plan["policy_id"],
        "complete": True,
        "contexts_planned": len(contexts),
        "contexts_completed": len(ordered_results),
        "device": device,
        "ledger_path": str(ledger.resolve()),
        "results": ordered_results,
    }
    atomic_write_json(result_path, value)
    return value


def _raise_policy_mismatch(policy_id: str) -> Any:
    raise ValueError(f"replay requested an unbound policy: {policy_id}")


def _snapshot_task_catalog(snapshot_root: Path, snapshot_id: str) -> tuple[int, ...]:
    path = Path(snapshot_root) / snapshot_id / "simulator.npz"
    with np.load(path, allow_pickle=False) as values:
        if "task_id_catalog" not in values.files:
            raise ValueError("snapshot has no exact LIBERO task catalog")
        catalog = tuple(
            int(value) for value in np.asarray(values["task_id_catalog"]).reshape(-1)
        )
    if not catalog or len(set(catalog)) != len(catalog):
        raise ValueError("snapshot LIBERO task catalog is invalid")
    return catalog


def _feature_seed(record_id: str, policy_id: str, snapshot_hash: str) -> int:
    digest = hashlib.sha256(
        f"new-policy-feature-v1\0{record_id}\0{policy_id}\0{snapshot_hash}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def _endpoint_object_distances(
    evidence: Any, object_positions: Any
) -> dict[str, dict[str, float]]:
    if not isinstance(object_positions, Mapping):
        return {}
    positions = {
        str(name): np.asarray(value, dtype=np.float64)
        for name, value in object_positions.items()
        if np.asarray(value).shape == (3,) and np.isfinite(value).all()
    }
    return {
        mode.mode_id: {
            name: float(
                np.linalg.norm(
                    evidence.trajectories.positions[
                        int(mode.representative_indices["medoid"]), -1
                    ]
                    - position
                )
            )
            for name, position in positions.items()
        }
        for mode in evidence.modes
    }


__all__ = [
    "HgpuReplayApplication",
    "OfflineCandidateAnalysis",
    "execute_replay_plan",
    "validate_replay_plan",
]
