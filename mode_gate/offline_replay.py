"""Executable hgpu1 snapshot replay for audit and staged-policy relabeling.

This is the concrete simulator integration behind
``NewPolicyReplayCoordinator``.  It recreates the original LIBERO suite,
loads theta0 only for reusable budget-independent scene features, separately fresh-loads
the target policy, restores each exact post-failure snapshot, and runs the
fixed-10 RE-STEER estimand with adaptive 16→32 branches.

No Registry deployment is read or mutated while this worker runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import gc
import hashlib
import json
import logging
from pathlib import Path
import random
import time
from typing import Any, Mapping, MutableMapping, Sequence

import numpy as np
import torch

from .black_box import as_numpy_actions
from .checkpoint_math import checkpoint_digest
from .counterfactual import (
    CounterfactualResult,
    CounterfactualReplayWorker,
    FixedBudgetResteerExecutor,
    FreshCandidateSelection,
    REPLAY_PROGRESS_CONTRACT,
)
from .evaluation import adaptive_counterfactual_target, counterfactual_posterior_status
from .experiment_contract import (
    FIXED_BUDGET_50_CONTRACT,
    label_contract_payload,
    regenerate_budget_state,
    require_fixed_budget_50_contract,
)
from .geometry import select_execution_candidate
from .incidents import IncidentMemory
from .io_utils import AtomicJsonl, atomic_write_json, sha256_file
from .policy_evaluator import runtime_suite_name
from .progress import canonicalize_stage_id, is_forward_stage_transition
from .semantic_planner import score_semantics_with_network_recovery
from .snapshots import DecisionSnapshotStore
from .types import ActionChunkBatch, GateContext, ProgressEvidence, SamplingCondition
from .verifier import build_verifier_input, load_verifier_input, save_verifier_input


LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class OfflineCandidateAnalysis:
    execution_actions: Any
    evidence: Any
    geometry: Sequence[Any]
    semantic: Any
    selected: Any | None
    context: GateContext


def validate_replay_plan(
    plan_path: Path,
    *,
    checkpoint_digest_cache: MutableMapping[Path, str] | None = None,
) -> dict[str, Any]:
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema_version") != "new-policy-counterfactual-plan-v3":
        raise ValueError("unsupported counterfactual replay plan")
    expected_hash = str(plan.get("plan_sha256") or "")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    actual_hash = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if expected_hash != actual_hash:
        raise ValueError("counterfactual replay plan checksum mismatch")
    checkpoint = Path(str(plan["checkpoint_path"])).resolve()
    actual_checkpoint_digest = (
        checkpoint_digest_cache.get(checkpoint)
        if checkpoint_digest_cache is not None
        else None
    )
    if actual_checkpoint_digest is None:
        actual_checkpoint_digest = checkpoint_digest(checkpoint)
        if checkpoint_digest_cache is not None:
            checkpoint_digest_cache[checkpoint] = actual_checkpoint_digest
    if actual_checkpoint_digest != str(plan["checkpoint_digest"]):
        raise ValueError("counterfactual target checkpoint digest changed")
    contexts = tuple(plan.get("contexts", ()))
    record_ids = [str(value["record_id"]) for value in contexts]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("counterfactual replay plan contains duplicate records")
    contract_payload = dict(plan.get("label_config") or {})
    contract = require_fixed_budget_50_contract(contract_payload)
    if str(plan.get("label_version")) != contract.label_version:
        raise ValueError("counterfactual replay label version/config mismatch")
    if tuple(map(int, plan.get("adaptive_branches", ()))) != (
        contract.counterfactual_initial_branches,
        contract.counterfactual_max_branches,
    ):
        raise ValueError("counterfactual branch schedule must be 16→32")
    if plan.get("decision_rule") != "head_argmax":
        raise ValueError("counterfactual plan must use direct head argmax")
    if plan.get("progress_contract") != REPLAY_PROGRESS_CONTRACT:
        raise ValueError(
            "counterfactual plan uses a stale or unsupported progress contract"
        )
    gemini_max_provider_calls = int(plan.get("gemini_max_provider_calls", 0))
    if not 0 < gemini_max_provider_calls <= contract.counterfactual_provider_call_limit:
        raise ValueError(
            "counterfactual Gemini provider-call cap must be in (0, 5000]"
        )
    gemini_call_ledger = str(plan.get("gemini_call_ledger_path") or "")
    if gemini_max_provider_calls > 0:
        if not gemini_call_ledger:
            raise ValueError("capped replay plan requires a Gemini call ledger")
        if not Path(gemini_call_ledger).is_absolute():
            raise ValueError("Gemini call ledger must be an absolute path")
    branch_ledger = str(plan.get("branch_ledger_path") or "")
    if branch_ledger and not Path(branch_ledger).is_absolute():
        raise ValueError("counterfactual branch ledger must be an absolute path")
    snapshot_root = Path(str(plan["snapshot_root"])).resolve()
    incident_root = Path(str(plan["incident_root"])).resolve()
    if not snapshot_root.is_dir() or not incident_root.is_dir():
        raise FileNotFoundError("counterfactual snapshot/incident roots are unavailable")
    if len(contexts) > contract.counterfactual_context_limit:
        raise ValueError(
            "counterfactual plan exceeds the conservative fixed10 context cap"
        )
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
        expected_budget_state = regenerate_budget_state(
            dict(manifest.get("controller_state") or {}), contract=contract
        )
        budget_state = dict(context.get("budget_state") or {})
        for name in (
            "retry_budget",
            "retry_index",
            "remaining_budget",
            "failure_count",
            "retry_schedule",
            "chunk_horizon",
            "max_policy_steps",
        ):
            if budget_state.get(name) != expected_budget_state.get(name):
                raise ValueError(
                    f"counterfactual context has stale fixed10 field: {name}"
                )
        if not 1 <= int(budget_state["remaining_budget"]) <= contract.retry_budget:
            raise ValueError(
                "counterfactual context has no actionable fixed10 retry budget"
            )
        if str(context.get("label_version")) != contract.label_version:
            raise ValueError("counterfactual context label version mismatch")
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
        gemini_max_provider_calls: int = 0,
        gemini_call_ledger_path: Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.runtime_suite = str(runtime_suite)
        self.task_ids = tuple(int(value) for value in task_ids)
        if not self.task_ids or len(set(self.task_ids)) != len(self.task_ids):
            raise ValueError("replay task catalog must be non-empty and unique")
        self.policy_id = str(policy_id)
        self.device = str(device)
        self.checkpoint = Path(checkpoint).resolve()
        self.gemini_max_provider_calls = int(gemini_max_provider_calls)
        self.gemini_call_ledger_path = (
            Path(gemini_call_ledger_path).resolve()
            if gemini_call_ledger_path is not None
            else None
        )
        if self.gemini_max_provider_calls < 0:
            raise ValueError("Gemini provider-call cap must be non-negative")
        if self.gemini_max_provider_calls and self.gemini_call_ledger_path is None:
            raise ValueError("capped replay requires a shared Gemini call ledger")
        self.artifact_root = Path(artifact_root).resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.snapshots = DecisionSnapshotStore(Path(snapshot_root))
        self.main = self._build_main()
        self.adapter = self.main.adapter
        self.policy, self.preprocessor = self._load_target_policy(self.checkpoint)
        self.current_context: Mapping[str, Any] | None = None
        self.current_manifest: Mapping[str, Any] | None = None
        self.current_guidance_functions: Sequence[Any] = ()
        self._prefetched_selections: dict[
            SamplingCondition, FreshCandidateSelection | None
        ] = {}

    def reconfigure_for_plan(
        self,
        *,
        artifact_root: Path,
        gemini_max_provider_calls: int,
        gemini_call_ledger_path: Path | None,
    ) -> None:
        """Apply plan-local paths/call budget without unloading warm models."""

        new_max = int(gemini_max_provider_calls)
        new_ledger = (
            Path(gemini_call_ledger_path).resolve()
            if gemini_call_ledger_path is not None
            else None
        )
        if new_max <= 0 or new_ledger is None:
            raise ValueError("warm replay requires a positive persisted Gemini cap")
        self.main.mode_aware_runtime.planner.reconfigure_provider_call_budget(
            max_provider_calls=new_max,
            call_ledger_path=new_ledger,
        )
        for name in ("gemini_grounder", "gemini_stage_recognizer"):
            component = getattr(self.main, name, None)
            if component is not None:
                component.reconfigure_provider_call_budget(
                    max_provider_calls=new_max,
                    call_ledger_path=str(new_ledger),
                )
        self.gemini_max_provider_calls = new_max
        self.gemini_call_ledger_path = new_ledger
        self.artifact_root = Path(artifact_root).resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def _build_main(self) -> Any:
        from hydra import compose, initialize_config_dir

        from rsi.main import Main

        config_dir = self.repo_root / "rsi/configs"
        run_root = self.artifact_root / "application"
        run_root.mkdir(parents=True, exist_ok=True)
        isolated = self.artifact_root / "isolated_runtime"
        overrides = [
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
            "mode_gate.controller_mode=fixed_budget_50",
            "mode_gate.retry_budget=50",
            "mode_gate.label_version=fixed_budget_50-v2",
            "mode_gate.verifier_thinking_level=medium",
            f"mode_gate.registry_root={isolated / 'registry'}",
            f"mode_gate.incident_root={isolated / 'incidents'}",
            f"mode_gate.snapshot_root={isolated / 'snapshots'}",
            f"mode_gate.slow_loop_root={isolated / 'slow_loop'}",
            f"mode_gate.planner_max_provider_calls={self.gemini_max_provider_calls}",
            f"device={self.device}",
            f"hydra.run.dir={run_root}",
        ]
        if self.gemini_call_ledger_path is not None:
            overrides.append(
                f"mode_gate.planner_call_ledger={self.gemini_call_ledger_path}"
            )
        with initialize_config_dir(
            version_base=None, config_dir=str(config_dir)
        ):
            config = compose(
                config_name="config",
                overrides=overrides,
            )
        return Main(config)

    def _load_target_policy(self, checkpoint: Path) -> tuple[Any, Any]:
        from lerobot.policies.factory import make_pre_post_processors

        from rsi.core.pi05_steer import PI05PolicySteer

        target = PI05PolicySteer.from_pretrained(str(checkpoint))
        target.to(self.device)
        # Moving a module does not mutate the device stored in its LeRobot
        # config. Keep the config authoritative for PI05's cached chunks and
        # the device processor, especially when replay runs on cuda:4/5.
        target.config.device = str(self.device)
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
        self._prefetched_selections.clear()

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
        from rsi.utils.guidance_utils import load_functions_from_txt

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
        history = (self.current_manifest.get("controller_state") or {}).get("executed_history")
        if history is None:
            history = context.get("executed_history")
        if history is None:
            raise ValueError("snapshot lacks decision-time execution history; rebuild it from recorded actions, never substitute future data")
        seed = _feature_seed(
            str(context["record_id"]), self.policy_id, str(context["snapshot_hash"])
        )
        budget_state = dict(context.get("budget_state") or {})
        retry_index = int(budget_state["retry_index"])
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
            semantics=analysis.semantic.candidate_scores,
            failure_count=int(budget_state["failure_count"]),
            remaining_budget=int(budget_state["remaining_budget"]),
            retry_budget=int(budget_state["retry_budget"]),
            ess_ratio=diagnostics.ess_ratio if diagnostics else 1.0,
            unique_ratio=diagnostics.unique_ratio if diagnostics else 1.0,
            backbone_id=self.main.theta0_scene_encoder.theta0_checksum,
            executed_history=np.asarray(history, dtype=np.float32).reshape(-1, 15),
        )
        return save_verifier_input(
            Path(output_path),
            verifier_input,
            metadata={
                "schema_version": "candidate-verifier-input-v3",
                "record_id": context["record_id"],
                "snapshot_id": context["snapshot_id"],
                "target_policy_id": self.policy_id,
                "label_version": FIXED_BUDGET_50_CONTRACT.label_version,
                "label_contract_hash": FIXED_BUDGET_50_CONTRACT.contract_hash,
                "label_config": label_contract_payload(FIXED_BUDGET_50_CONTRACT),
                "retry_budget": int(budget_state["retry_budget"]),
                "retry_index": retry_index,
                "remaining_budget": int(budget_state["remaining_budget"]),
                "failure_count": int(budget_state["failure_count"]),
                "retry_schedule": budget_state["retry_schedule"],
                "chunk_horizon": int(budget_state["chunk_horizon"]),
                "max_policy_steps": int(budget_state["max_policy_steps"]),
                "gemini_thinking_level": "medium",
                "semantic_model": analysis.semantic.model,
                "planner_provenance": getattr(analysis.semantic, "raw_response", {}).get("metadata", {}),
                "feature_seed": seed,
                "theta0_feature_id": encoded.feature_id,
                "theta0_cache_path": str(encoded.cache_path),
                "candidate_ids": [mode.candidate_id for mode in analysis.evidence.candidates],
                "captured_code_revision": self.current_manifest["provenance"][
                    "code_revision"
                ],
                "replay_code_revision": self.main.mode_gate_source_revision,
            },
        )

    def sample_candidate(
        self,
        *,
        adapter: Any,
        policy: Any,
        condition: SamplingCondition,
    ) -> FreshCandidateSelection | None:
        if adapter is not self.adapter or policy is not self.policy:
            raise ValueError("fresh sampler received another adapter/policy")
        if condition in self._prefetched_selections:
            return self._prefetched_selections.pop(condition)
        analysis = self._sample_and_analyze(condition, purpose="branch")
        return self._selection_from_analysis(analysis)

    @staticmethod
    def _selection_from_analysis(
        analysis: OfflineCandidateAnalysis,
    ) -> FreshCandidateSelection | None:
        if analysis.selected is None:
            return None
        index = int(analysis.selected.sample_index)
        actions = analysis.execution_actions[index]
        if isinstance(actions, torch.Tensor):
            actions = actions.detach().cpu().numpy()
        return FreshCandidateSelection(
            actions=np.asarray(actions),
            candidate_id=analysis.selected.candidate_id,
            sample_index=index,
            metadata={
                "sample_id": analysis.selected.sample_id,
                "semantic_model": analysis.semantic.model,
                "semantic_prompt_version": analysis.semantic.prompt_version,
                "planner_provenance": getattr(analysis.semantic, "raw_response", {}).get("metadata", {}),
                "semantic_observed_stage_id": analysis.semantic.observed_stage_id,
                "semantic_stage_confidence": analysis.semantic.stage_confidence,
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
        candidate_paths = {
            mode.candidate_id: evidence.trajectories.positions[
                mode.sample_index
            ]
            for mode in evidence.candidates
        }
        overlay = self.main.mode_aware_runtime.combined_renderer.render(
            observation_image=image,
            candidate_paths=candidate_paths,
            output_path=round_dir / "all_candidates.png",
        )
        semantic = _score_semantics_with_network_recovery(
            self.main.mode_aware_runtime.planner,
            gate_context,
            evidence,
            geometry,
            overlay.path,
            object_distances=_endpoint_object_distances(
                evidence, gate_context.metadata.get("object_positions", {})
            ),
            progress_history=gate_context.metadata.get("progress_history", ()),
        )
        selected = select_execution_candidate(
            evidence.candidates, geometry, semantic.candidate_scores, semantic.selected_candidate_id
        )
        return OfflineCandidateAnalysis(
            execution_actions=execution,
            evidence=evidence,
            geometry=geometry,
            semantic=semantic,
            selected=selected,
            context=gate_context,
        )

    def progress_observer(
        self,
        *,
        adapter: Any,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        task_success: bool,
        selection: FreshCandidateSelection | None = None,
        next_condition: SamplingCondition | None = None,
        cache_next_selection: bool = False,
        terminal: bool = False,
    ) -> ProgressEvidence:
        before_count = before.get("completed_count")
        after_count = after.get("completed_count")
        predicate_advanced = (
            before_count is not None
            and after_count is not None
            and int(after_count) > int(before_count)
        )
        success = bool(task_success or after.get("task_success", False))
        if success or predicate_advanced:
            return ProgressEvidence(
                stage_id=(
                    f"bddl-goals:{after_count}/{after.get('goal_count')}"
                    if predicate_advanced
                    else "TASK_SUCCESS"
                ),
                advanced=True,
                confidence=1.0,
                source=(
                    "task_success" if success else "bddl_goal_predicates"
                ),
                task_success=success,
            )

        # A terminal branch has no executable state to probe. Its timeout is
        # handled by FixedBudgetResteerExecutor and must never be converted
        # into semantic progress from an invalid post-terminal observation.
        if terminal:
            return ProgressEvidence(
                stage_id="UNKNOWN",
                advanced=False,
                confidence=0.0,
                source="terminal",
                task_success=False,
            )

        if selection is None or next_condition is None:
            return ProgressEvidence(
                stage_id="UNKNOWN",
                advanced=False,
                confidence=0.0,
                source="unknown",
                task_success=False,
            )

        # LIBERO-PRO BDDL commonly exposes only final goal predicates. Probe
        # the exact post-action RGB with the same fresh sampling + Gemini mode
        # scoring call that would precede the next retry. If another retry is
        # available, cache its already-scored candidate so this monitoring step
        # adds no duplicate policy/Gemini call. The final retry gets one
        # observation-only probe so progress in its last chunk is not lost.
        post_analysis = self._sample_and_analyze(
            next_condition,
            purpose="progress",
        )
        post_selection = self._selection_from_analysis(post_analysis)

        pre_stage = canonicalize_stage_id(
            str(selection.metadata.get("semantic_observed_stage_id") or "UNKNOWN")
        )
        post_stage = canonicalize_stage_id(
            str(post_analysis.semantic.observed_stage_id or "UNKNOWN")
        )
        pre_confidence = float(
            selection.metadata.get("semantic_stage_confidence", 0.0)
        )
        post_confidence = float(post_analysis.semantic.stage_confidence)
        confidence = min(pre_confidence, post_confidence)
        semantic_advanced = (
            is_forward_stage_transition(pre_stage, post_stage)
            and confidence >= 0.8
        )
        if cache_next_selection and not semantic_advanced:
            self._prefetched_selections[next_condition] = post_selection
        return ProgressEvidence(
            stage_id=post_stage,
            advanced=semantic_advanced,
            confidence=confidence,
            source="gemini_planner",
            task_success=False,
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


@dataclass(frozen=True)
class WarmReplayIdentity:
    """Immutable resources that must match before a loaded app can be reused."""

    repo_root: Path
    runtime_suite: str
    task_ids: tuple[int, ...]
    checkpoint: Path
    policy_id: str
    device: str
    snapshot_root: Path


class WarmReplayApplicationPool:
    """Retain one compatible replay application and both PI0.5 models in RAM."""

    def __init__(self) -> None:
        self._identity: WarmReplayIdentity | None = None
        self._application: HgpuReplayApplication | None = None

    @property
    def is_warm(self) -> bool:
        return self._application is not None

    @property
    def identity(self) -> WarmReplayIdentity | None:
        return self._identity

    def acquire(
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
        gemini_max_provider_calls: int,
        gemini_call_ledger_path: Path | None,
    ) -> HgpuReplayApplication:
        if int(gemini_max_provider_calls) <= 0 or gemini_call_ledger_path is None:
            raise ValueError("warm replay requires a positive persisted Gemini cap")
        identity = WarmReplayIdentity(
            repo_root=Path(repo_root).resolve(),
            runtime_suite=str(runtime_suite),
            task_ids=tuple(int(value) for value in task_ids),
            checkpoint=Path(checkpoint).resolve(),
            policy_id=str(policy_id),
            device=str(device),
            snapshot_root=Path(snapshot_root).resolve(),
        )
        if self._application is None:
            self._identity = identity
            self._application = HgpuReplayApplication(
                repo_root=identity.repo_root,
                runtime_suite=identity.runtime_suite,
                task_ids=identity.task_ids,
                checkpoint=identity.checkpoint,
                policy_id=identity.policy_id,
                device=identity.device,
                artifact_root=artifact_root,
                snapshot_root=identity.snapshot_root,
                gemini_max_provider_calls=int(gemini_max_provider_calls),
                gemini_call_ledger_path=Path(gemini_call_ledger_path).resolve(),
            )
            return self._application
        if identity != self._identity:
            raise ValueError(
                "warm replay plan is incompatible with the resident application: "
                f"resident={self._identity}, requested={identity}"
            )
        self._application.reconfigure_for_plan(
            artifact_root=artifact_root,
            gemini_max_provider_calls=int(gemini_max_provider_calls),
            gemini_call_ledger_path=Path(gemini_call_ledger_path).resolve(),
        )
        return self._application

    def close(self) -> None:
        if self._application is not None:
            self._application.close()
        self._application = None
        self._identity = None


def preload_replay_plan(
    plan_path: Path,
    *,
    repo_root: Path,
    device: str,
    application_pool: WarmReplayApplicationPool,
    checkpoint_digest_cache: MutableMapping[Path, str] | None = None,
) -> dict[str, Any]:
    """Load a plan's simulator and policies without requiring unfinished work."""

    plan = validate_replay_plan(
        plan_path,
        checkpoint_digest_cache=checkpoint_digest_cache,
    )
    groups: set[tuple[str, tuple[int, ...]]] = set()
    for context in tuple(plan.get("contexts", ())):
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
        groups.add((runtime, catalog))
    if len(groups) != 1:
        raise ValueError(
            "one warm replay worker requires exactly one runtime/task catalog, "
            f"got {sorted(groups)}"
        )
    result_path = Path(str(plan["result_path"]))
    artifact_root = (
        result_path.parent / "replay_artifacts" / str(plan["plan_sha256"])[:12]
    )
    runtime, task_ids = next(iter(groups))
    group_name = runtime + "__tasks_" + "_".join(map(str, task_ids))
    gemini_max_provider_calls = int(plan.get("gemini_max_provider_calls", 0))
    gemini_call_ledger_path = (
        Path(str(plan["gemini_call_ledger_path"]))
        if gemini_max_provider_calls > 0
        else None
    )
    application_pool.acquire(
        repo_root=repo_root,
        runtime_suite=runtime,
        task_ids=task_ids,
        checkpoint=Path(str(plan["checkpoint_path"])),
        policy_id=str(plan["policy_id"]),
        device=device,
        artifact_root=artifact_root / group_name,
        snapshot_root=Path(str(plan["snapshot_root"])),
        gemini_max_provider_calls=gemini_max_provider_calls,
        gemini_call_ledger_path=gemini_call_ledger_path,
    )
    return {
        "schema_version": "warm-replay-preload-v2",
        "plan_sha256": plan["plan_sha256"],
        "policy_id": plan["policy_id"],
        "device": device,
        "runtime_suite": runtime,
        "task_ids": list(task_ids),
        "gemini_max_provider_calls": gemini_max_provider_calls,
        "label_version": plan["label_version"],
        "label_config": plan["label_config"],
        "warm": application_pool.is_warm,
    }


def execute_replay_plan(
    plan_path: Path,
    *,
    repo_root: Path,
    device: str = "cuda:6",
    ledger_path: Path | None = None,
    application_pool: WarmReplayApplicationPool | None = None,
    checkpoint_digest_cache: MutableMapping[Path, str] | None = None,
) -> dict[str, Any]:
    """Execute one immutable plan without touching ``active.json``."""

    plan = validate_replay_plan(
        plan_path,
        checkpoint_digest_cache=checkpoint_digest_cache,
    )
    contexts = tuple(plan.get("contexts", ()))
    result_path = Path(str(plan["result_path"]))
    if result_path.is_file():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            existing.get("schema_version") == "new-policy-counterfactual-result-v2"
            and existing.get("plan_sha256") == plan["plan_sha256"]
            and existing.get("label_version") == plan["label_version"]
            and existing.get("complete") is True
        ):
            return existing
    incidents = IncidentMemory(Path(str(plan["incident_root"])))
    snapshots = DecisionSnapshotStore(Path(str(plan["snapshot_root"])))
    ledger = Path(
        ledger_path
        if ledger_path is not None
        else plan.get("branch_ledger_path")
        or result_path.parent / "branches.jsonl"
    )
    contract_payload = dict(plan["label_config"])
    contract = require_fixed_budget_50_contract(contract_payload)
    label_version = contract.label_version
    labels = tuple(incidents.labels.iter_valid())
    branch_events = tuple(AtomicJsonl(ledger).iter_valid())
    ordered_results: list[dict[str, Any] | None] = [None] * len(contexts)
    grouped: dict[
        tuple[str, tuple[int, ...]],
        list[tuple[int, Mapping[str, Any], Mapping[str, Any]]],
    ] = {}
    for index, context in enumerate(contexts):
        completed = _completed_replay_result(
            context,
            policy_id=str(plan["policy_id"]),
            label_version=label_version,
            source="counterfactual_replay",
            contract=contract,
            labels=labels,
            branch_events=branch_events,
        )
        if completed is not None:
            ordered_results[index] = asdict(completed)
            continue
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

    artifact_root = (
        result_path.parent / "replay_artifacts" / str(plan["plan_sha256"])[:12]
    )
    for runtime, task_ids in sorted(grouped):
        group_name = runtime + "__tasks_" + "_".join(map(str, task_ids))
        gemini_max_provider_calls = int(plan.get("gemini_max_provider_calls", 0))
        gemini_call_ledger_path = (
            Path(str(plan["gemini_call_ledger_path"]))
            if gemini_max_provider_calls > 0
            else None
        )
        application_kwargs = {
            "repo_root": repo_root,
            "runtime_suite": runtime,
            "task_ids": task_ids,
            "checkpoint": Path(str(plan["checkpoint_path"])),
            "policy_id": str(plan["policy_id"]),
            "device": device,
            "artifact_root": artifact_root / group_name,
            "snapshot_root": snapshots.root,
            "gemini_max_provider_calls": gemini_max_provider_calls,
            "gemini_call_ledger_path": gemini_call_ledger_path,
        }
        application = (
            application_pool.acquire(**application_kwargs)
            if application_pool is not None
            else HgpuReplayApplication(**application_kwargs)
        )
        try:
            branch_executor = FixedBudgetResteerExecutor(
                fresh_sampler=application.sample_candidate,
                retry_schedule=contract.retry_schedule,
                chunk_horizon=contract.chunk_horizon,
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
                feature = _reuse_or_build_feature(
                    application,
                    context=context,
                    policy_id=str(plan["policy_id"]),
                )
                result = replay_worker.run(
                    record_id=str(context["record_id"]),
                    policy_id=str(plan["policy_id"]),
                    label_version=label_version,
                    source="counterfactual_replay",
                    verifier_feature_path=feature,
                    data_split=str(context["data_split"]),
                    label_config=contract_payload,
                    budget_state=dict(context["budget_state"]),
                )
                ordered_results[index] = asdict(result)
        finally:
            if application_pool is None:
                application.close()
    if any(value is None for value in ordered_results):
        raise RuntimeError("counterfactual replay did not complete every context")
    value = {
        "schema_version": "new-policy-counterfactual-result-v2",
        "plan_sha256": plan["plan_sha256"],
        "policy_id": plan["policy_id"],
        "label_version": label_version,
        "label_config": contract_payload,
        "complete": True,
        "contexts_planned": len(contexts),
        "contexts_completed": len(ordered_results),
        "contexts_labeled": sum(
            value["label_status"] == "LABELED" for value in ordered_results
        ),
        "contexts_censored": sum(
            value["label_status"] != "LABELED" for value in ordered_results
        ),
        "device": device,
        "ledger_path": str(ledger.resolve()),
        "results": ordered_results,
    }
    atomic_write_json(result_path, value)
    return value


def _reuse_or_build_feature(
    application: HgpuReplayApplication,
    *,
    context: Mapping[str, Any],
    policy_id: str,
) -> Path:
    """Reuse only an exact fixed10 feature; old budget-dependent arrays are stale.

    The scene encoder still reuses its budget-independent snapshot/image cache
    internally when a new sidecar must be built.
    """

    output_path = Path(str(context["fresh_feature_output_path"])).resolve()
    metadata_path = output_path.with_suffix(".json")
    if output_path.is_file() and metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        feature_policy = str(
            metadata.get("target_policy_id") or metadata.get("policy_id") or ""
        )
        if (
            metadata.get("schema_version") == "candidate-verifier-input-v3"
            and str(metadata.get("record_id")) == str(context["record_id"])
            and str(metadata.get("snapshot_id")) == str(context["snapshot_id"])
            and feature_policy == policy_id
            and str(metadata.get("label_version"))
            == FIXED_BUDGET_50_CONTRACT.label_version
            and str(metadata.get("label_contract_hash"))
            == FIXED_BUDGET_50_CONTRACT.contract_hash
            and int(metadata.get("retry_budget", -1))
            == FIXED_BUDGET_50_CONTRACT.retry_budget
            and int(metadata.get("retry_index", -1))
            == int(context["budget_state"]["retry_index"])
            and int(metadata.get("remaining_budget", -1))
            == int(context["budget_state"]["remaining_budget"])
            and str(metadata.get("gemini_thinking_level"))
            == FIXED_BUDGET_50_CONTRACT.gemini_thinking_level
        ):
            load_verifier_input(output_path)
            return output_path
    return application.build_feature(
        context=context,
        policy_id=policy_id,
        output_path=output_path,
    )


def _score_semantics_with_network_recovery(
    planner: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Retry only transient provider/network failures inside the warm process.

    The exact planner arguments are retained across attempts, so a tunnel outage
    cannot change the sampled candidates, overlay, prompt, or cache identity.
    Structured-output/schema failures still fail closed immediately.
    """

    return score_semantics_with_network_recovery(
        planner,
        *args,
        recovery_label="offline replay",
        sleep_fn=time.sleep,
        **kwargs,
    )


def _completed_replay_result(
    context: Mapping[str, Any],
    *,
    policy_id: str,
    label_version: str,
    source: str,
    contract: Any,
    labels: Sequence[Mapping[str, Any]],
    branch_events: Sequence[Mapping[str, Any]],
) -> CounterfactualResult | None:
    """Reconstruct a completed result only from mutually consistent artifacts."""

    record_id = str(context["record_id"])
    matches = [
        item
        for item in labels
        if str(item.get("record_id")) == record_id
        and str(item.get("policy_id")) == policy_id
        and str(item.get("label_version")) == label_version
        and str(item.get("source")) == source
        and str((item.get("label_config") or {}).get("contract_hash"))
        == contract.contract_hash
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"duplicate completed replay labels for {record_id}")
    label = matches[0]
    if str(label.get("snapshot_hash")) != str(context["snapshot_hash"]):
        raise ValueError(f"completed replay snapshot hash changed for {record_id}")
    if str(label.get("data_split")) != str(context["data_split"]):
        raise ValueError(f"completed replay split changed for {record_id}")
    if bool(label.get("weak", False)) or float(label.get("weight", 1.0)) != 1.0:
        raise ValueError(f"completed counterfactual label is not full-weight for {record_id}")

    feature_path = Path(str(label.get("verifier_feature_path", ""))).resolve()
    planned_feature_path = Path(str(context["fresh_feature_output_path"])).resolve()
    if feature_path != planned_feature_path or not feature_path.is_file():
        raise ValueError(f"completed replay feature sidecar is unavailable for {record_id}")
    metadata_path = feature_path.with_suffix(".json")
    if not metadata_path.is_file():
        raise ValueError(f"completed replay feature metadata is unavailable for {record_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected_metadata = {
        "schema_version": "candidate-verifier-input-v3",
        "record_id": record_id,
        "snapshot_id": str(context["snapshot_id"]),
        "target_policy_id": policy_id,
        "label_version": label_version,
        "label_contract_hash": contract.contract_hash,
    }
    for name, expected in expected_metadata.items():
        if str(metadata.get(name)) != expected:
            raise ValueError(
                f"completed replay feature metadata mismatch for {record_id}: {name}"
            )
    required_feature_arrays = {"scene_feature", "candidate_trajectories", "executed_history",
                               "remaining_budget", "retry_budget", "backbone_id", "candidate_ids", "feature_schema"}
    with np.load(feature_path, allow_pickle=False) as values:
        if not required_feature_arrays.issubset(values.files):
            raise ValueError(f"completed replay feature schema is incomplete for {record_id}")

    try:
        branches = int(label["branches"])
        successes = int(label["successes"])
        p_expansion = float(label["p_expansion"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"completed replay label is malformed for {record_id}") from exc
    if branches not in {
        contract.counterfactual_initial_branches,
        contract.counterfactual_max_branches,
    } or not 0 <= successes <= branches:
        raise ValueError(f"completed replay branch count is invalid for {record_id}")
    expected_probability = 1.0 - successes / branches
    if abs(p_expansion - expected_probability) > 1e-9:
        raise ValueError(f"completed replay probability is invalid for {record_id}")

    indexed: dict[int, Mapping[str, Any]] = {}
    for event in branch_events:
        if (
            str(event.get("record_id")) != record_id
            or str(event.get("policy_id")) != policy_id
            or str(event.get("label_version")) != label_version
            or str(event.get("label_contract_hash")) != contract.contract_hash
        ):
            continue
        if event.get("event") != "COUNTERFACTUAL_BRANCH_COMPLETED":
            raise ValueError(f"unexpected replay ledger event for {record_id}")
        try:
            branch_index = int(event["branch_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed replay branch for {record_id}") from exc
        if branch_index in indexed:
            raise ValueError(f"duplicate replay branch {branch_index} for {record_id}")
        indexed[branch_index] = event
    if set(indexed) != set(range(branches)):
        raise ValueError(f"completed replay branches are incomplete for {record_id}")
    ledger_successes = sum(
        bool(indexed[index].get("success")) for index in range(branches)
    )
    if ledger_successes != successes:
        raise ValueError(f"completed replay success count disagrees for {record_id}")
    target, interval = adaptive_counterfactual_target(
        successes=successes,
        trials=branches,
        posterior_confidence=contract.posterior_confidence,
        decision_boundary=contract.decision_boundary,
        initial_branches=contract.counterfactual_initial_branches,
        max_branches=contract.counterfactual_max_branches,
    )
    if target != branches:
        raise ValueError(f"completed replay stopped before convergence for {record_id}")
    posterior = counterfactual_posterior_status(
        successes=successes,
        trials=branches,
        posterior_confidence=contract.posterior_confidence,
        decision_boundary=contract.decision_boundary,
    )
    if posterior["label_status"] != "LABELED":
        # Censored results deliberately have no binary label and are recovered
        # from their branch ledger by CounterfactualReplayWorker.
        return None
    return CounterfactualResult(
        record_id=record_id,
        policy_id=policy_id,
        branches=branches,
        successes=successes,
        p_expansion=p_expansion,
        posterior_interval=interval,
        posterior_side_probability=float(
            posterior["posterior_side_probability"]
        ),
        label_status="LABELED",
        censored=False,
        label_attached=False,
    )


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
        mode.candidate_id: {
            name: float(
                np.linalg.norm(
                    evidence.trajectories.positions[
                        mode.sample_index, -1
                    ]
                    - position
                )
            )
            for name, position in positions.items()
        }
        for mode in evidence.candidates
    }


__all__ = [
    "HgpuReplayApplication",
    "OfflineCandidateAnalysis",
    "WarmReplayApplicationPool",
    "WarmReplayIdentity",
    "execute_replay_plan",
    "preload_replay_plan",
    "validate_replay_plan",
]
