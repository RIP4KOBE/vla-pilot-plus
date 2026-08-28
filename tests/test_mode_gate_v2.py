import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

import h5py
import numpy as np
import pytest
import torch
from safetensors import safe_open
from safetensors.torch import save_file

from mode_gate.checkpoint_math import (
    checkpoint_digest,
    compose_policy,
    delete_verified_theta_ft,
    extract_full_delta,
    partition_counts,
    verify_full_delta_reconstruction,
)
from mode_gate.audit import (
    AuditContext,
    AuditCollectionCoordinator,
    HydraAuditEpisodeExecutor,
    audit_contexts_from_manifest,
    invalidate_audit_attempt,
)
from mode_gate.candidates import (
    DeltaLineageEntry,
    compose_expansion_candidates,
    compose_reuse_candidates,
)
from mode_gate.config import ModeGateConfig
from mode_gate.counterfactual import (
    BranchOutcome,
    CounterfactualResult,
    CounterfactualReplayWorker,
    FixedBudgetResteerExecutor,
    FreshMedoidSelection,
    NewPolicyReplayCoordinator,
)
from mode_gate.curriculum import (
    LIBERO_PRO_VARIANTS,
    balanced_libero_pro_variant_map,
)
from patches.libero_pro import (
    DEFAULT_LIBERO_PRO_SEED,
    patch_environment_seed,
)
from mode_gate.data_pipeline import (
    DemoFrame,
    DemoWriter,
    curate_and_export_ticket,
    reassess_demo_replay,
    validate_demo_replay,
)
from mode_gate.demo_matching import attach_demo_match_label
from mode_gate.deployed_evaluation import (
    DeployedDevelopmentCoordinator,
    checkpoint_identity_canary,
    deployed_dev_contexts,
)
from mode_gate.eval_manifest import (
    fixed_development_probe_context,
    generate_joint_manifest,
)
from mode_gate.evaluation import (
    EpisodeLedger,
    PolicyScore,
    adaptive_counterfactual_target,
    raw_promotion_decision,
    select_alpha_top2,
    wilson_interval,
)
from mode_gate.features import (
    ModeFeatureEncoderV1,
    TrajectoryDescriptorEncoder,
    select_task_keypoints,
)
from mode_gate.geometry import (
    AxisAlignedBox,
    GeometryContext,
    GeometryScorer,
    select_execution_medoid,
)
from mode_gate.incidents import (
    CapabilitySignatureRecord,
    IncidentMemory,
    VerifierDecisionRecord,
    VerifierLabelRecord,
)
from mode_gate.io_utils import sha256_file
from mode_gate.offline_replay import HgpuReplayApplication, validate_replay_plan
from mode_gate.progress import ProgressMonitor, canonicalize_stage_id
from mode_gate.policy_evaluator import (
    EvaluationContext,
    PolicyEvaluationSummary,
    RawEpisodeResult,
    RawPolicyEvaluator,
    contexts_from_manifest,
)
from mode_gate.promotion import (
    PolicyCandidate,
    PolicyPromotionCoordinator,
    TriggerRecheckResult,
    deploy_policy_gate,
)
from mode_gate.registry import PolicyRegistry
from mode_gate.runtime import ModeAwareRuntime, _save_round_evidence
from mode_gate.semantic_planner import GeminiSemanticPlanner
from mode_gate.scene_encoder import (
    MaskedHiddenStates,
    Theta0SceneEncoder,
    processor_artifact_digest,
)
from mode_gate.signatures import FailureMode, lookup_validated_remedies
from mode_gate.slow_loop import SlowLoopState, SlowLoopStore
from mode_gate.slow_worker import SlowLoopWorker
from mode_gate.snapshots import DecisionSnapshotStore
from mode_gate.state_machine import EpisodeChunkController
from mode_gate.training import (
    CoFTConfig,
    TrainingSmokeConfig,
    build_lerobot_coft_command,
    prepare_source_catalog,
    write_source_sampler_manifest,
)
from mode_gate.tickets import (
    CollectionSpec,
    CoverageCell,
    TICKET_PLANNER_MODEL,
    TicketCollectionPlanner,
)
from mode_gate.types import (
    ActionChunkBatch,
    ControllerPhase,
    ControllerRoute,
    DecisionSnapshot,
    FailureTrigger,
    GateContext,
    GeometryEvidence,
    ModeEvidence,
    ProgressEvidence,
    RoundEvidence,
    SamplingDiagnostics,
    SemanticModeScore,
    SemanticPlan,
    TaskSpaceTrajectoryBatch,
)
from mode_gate.verifier import (
    DeployedVerifierPredictor,
    FeatureStandardizer,
    GroundedCapabilityVerifier,
    ModeVerifierInput,
    PlattCalibrator,
    VERIFIER_INPUT_DIMS,
    ablate_verifier_input,
    binomial_cross_entropy,
    load_verifier_input,
    save_verifier_input,
)
from mode_gate.verifier_training import (
    VerifierExample,
    VerifierTrainingConfig,
    assert_group_isolation,
    build_verifier_holdout,
    train_verifier,
    verifier_channel_correlation,
    verifier_training_weights,
)
from mode_gate.verifier_refresh import verifier_refresh_status
from core.pi05_steer import PI05PolicySteer
from core.fkd_class import FKD
from core.diffusion_policy_steer import DiffusionPolicySteer


def _progress(advanced=False, success=False):
    return ProgressEvidence(
        stage_id="2" if advanced else "UNKNOWN",
        advanced=advanced,
        confidence=1.0 if advanced else 0.0,
        source="predicate" if advanced else "unknown",
        task_success=success,
    )


def _score_and_route(controller, verifier_decision=None):
    controller.begin_sampling()
    controller.mark_abstracted()
    assert controller.mark_scored(has_safe_mode=True) is None
    return controller.route_scored_batch(verifier_decision=verifier_decision)


def test_v2_controller_uses_fresh_post_failure_batches_and_four_retries():
    controller = EpisodeChunkController(ModeGateConfig(controller_mode="learned_verifier"))
    controller.start_episode(stage_id="1")
    for _ in range(3):
        route = _score_and_route(controller)
        assert route.route is ControllerRoute.EXECUTE
        controller.observe_chunk(_progress())
    assert controller.state.phase is ControllerPhase.VERIFICATION_DUE
    assert controller.state.failure_count == 1

    for retry in range(4):
        route = _score_and_route(controller, ControllerRoute.RESTEER)
        assert route.route is ControllerRoute.RESTEER
        assert route.reason == "verifier_head_argmax:RE-STEER"
        controller.observe_chunk(_progress())
        assert controller.state.verification_due
        assert controller.state.failure_count == min(4, retry + 2)
    route = _score_and_route(controller, ControllerRoute.RESTEER)
    assert route.route is ControllerRoute.EXPAND
    assert route.reason == "retry_budget_exhausted"


def test_learned_verifier_routes_directly_from_head_class_without_threshold():
    assert "expansion_threshold" not in ModeGateConfig.__dataclass_fields__
    controller = EpisodeChunkController(
        ModeGateConfig(controller_mode="learned_verifier")
    )
    controller.start_episode(stage_id="1")
    controller.state.verification_due = True
    route = _score_and_route(controller, ControllerRoute.EXPAND)
    assert route.route is ControllerRoute.EXPAND
    assert route.reason == "verifier_head_argmax:EXPANSION"
    assert route.verifier_called


def test_v2_controller_resets_counters_on_stage_advance_and_timeout_is_not_label():
    controller = EpisodeChunkController(ModeGateConfig(controller_mode="fixed_budget_4"))
    controller.start_episode(stage_id="1")
    _score_and_route(controller)
    controller.state.retry_index = 2
    decision = controller.observe_chunk(_progress(advanced=True))
    assert decision.route is ControllerRoute.EXECUTE
    assert controller.state.retry_index == 0
    _score_and_route(controller)
    timeout = controller.observe_chunk(_progress(), terminal_timeout=True)
    assert timeout.route is ControllerRoute.EXPAND
    assert timeout.label_eligible is False


def test_progress_monitor_predicate_precedence_and_gemini_confidence_gate():
    monitor = ProgressMonitor()
    monitor.reset(stage_id="1", reward=0.0)
    baseline = monitor.observe(
        task_success=False,
        gemini_stage_id="stage_1",
        gemini_confidence=0.95,
        normalized_reward=0.0,
    )
    assert not baseline.advanced
    low_confidence = monitor.observe(
        task_success=False,
        gemini_stage_id="stage_2",
        gemini_confidence=0.6,
        normalized_reward=0.0,
    )
    assert not low_confidence.advanced
    supported = monitor.observe(
        task_success=False,
        gemini_stage_id="stage_2",
        gemini_confidence=0.6,
        normalized_reward=0.03,
    )
    assert supported.advanced and supported.source == "gemini_planner"
    predicate = monitor.observe(
        task_success=False,
        predicate_stage_id="3",
        predicate_advanced=True,
        gemini_stage_id="UNKNOWN",
        normalized_reward=0.03,
    )
    assert predicate.advanced and predicate.confidence == 1.0
    assert predicate.source == "simulator_predicate"


def test_stage_identity_canonicalization_ignores_descriptive_suffixes():
    assert canonicalize_stage_id("1") == "stage_1"
    assert canonicalize_stage_id("Stage 1: Slide open the top drawer") == "stage_1"
    assert canonicalize_stage_id(
        "Stage 1: Slide open the top drawer (keypoint 11)"
    ) == "stage_1"
    monitor = ProgressMonitor()
    monitor.reset(stage_id="1", reward=0.0)
    baseline = monitor.observe(
        task_success=False,
        gemini_stage_id="Stage 1: Slide open the top drawer",
        gemini_confidence=0.95,
        normalized_reward=0.0,
    )
    alias = monitor.observe(
        task_success=False,
        gemini_stage_id="Stage 1: Slide open the top drawer (keypoint 11)",
        gemini_confidence=0.95,
        normalized_reward=0.0,
    )
    assert not baseline.advanced and not alias.advanced
    assert baseline.stage_id == alias.stage_id == "stage_1"


def test_progress_monitor_explicit_predicate_false_and_w3_boundary():
    monitor = ProgressMonitor()
    monitor.reset(stage_id="1", reward=0.0)
    controller = EpisodeChunkController(
        ModeGateConfig(controller_mode="fixed_budget_4")
    )
    controller.start_episode(stage_id="1")
    for index in range(3):
        route = _score_and_route(controller)
        assert route.route is ControllerRoute.EXECUTE
        progress = monitor.observe(
            task_success=False,
            predicate_stage_id="slide_open_top_drawer",
            predicate_advanced=False,
            normalized_reward=0.0,
        )
        assert not progress.advanced
        observed = controller.observe_chunk(progress)
        if index < 2:
            assert observed.reason == "normal_continue"
    assert controller.state.chunks_executed == 3
    assert controller.state.stagnant_chunks == 3
    assert controller.state.verification_due


def test_pi05_fkd_uses_scheduler_indices_and_performs_real_resample():
    fake_policy = SimpleNamespace(
        _action_chunk_horizon=10,
        _sample_to_trajectory_3d=lambda value: value,
    )
    reward = lambda _keypoints, trajectory: trajectory[..., 0].mean()
    fkd = PI05PolicySteer._init_fkd(
        fake_policy,
        {
            "potential_type": "rt",
            "lmbda": 100.0,
            "adaptive_resampling": False,
            "resample_frequency": 5,
        },
        4,
        10,
        0.8,
        torch.zeros(1, 3),
        reward,
        torch.device("cpu"),
    )
    assert fkd.resampling_interval.tolist()[0] == 2

    torch.manual_seed(4)
    particles = torch.zeros(4, 11, 3)
    particles[0, :, 0] = 1.0
    for scheduler_index in range(2, 11):
        particles, _ = fkd.resample(
            sampling_idx=scheduler_index,
            latents=particles,
            x0_preds=particles,
        )
    diagnostics = fkd.diagnostics()
    assert diagnostics["resample_timesteps"]
    assert 2 in diagnostics["resample_timesteps"]
    assert diagnostics["unique_ratio"] < 1.0


def test_fkd_uniform_effective_sample_size_is_bounded():
    particles = 40
    fkd = FKD(
        potential_type="rt",
        lmbda=1.0,
        num_particles=particles,
        adaptive_resampling=True,
        resample_frequency=1,
        resampling_t_start=0,
        resampling_t_end=0,
        timesteps=[0],
        reward_fn=lambda values: torch.zeros(
            values.shape[0], device=values.device, dtype=torch.float32
        ),
        device="cpu",
    )
    values = torch.zeros(particles, 2, 3)
    fkd.resample(sampling_idx=0, latents=values, x0_preds=values)

    diagnostics = fkd.diagnostics()

    assert diagnostics["ess_history"] == [pytest.approx(float(particles))]
    assert 0.0 <= diagnostics["ess_ratio"] <= 1.0
    assert diagnostics["ess_ratio"] == pytest.approx(1.0, abs=1e-12)


def test_fkd_diagnostics_rejects_material_ess_invariant_violation():
    fkd = FKD(
        potential_type="rt",
        lmbda=1.0,
        num_particles=40,
        adaptive_resampling=True,
        resample_frequency=1,
        resampling_t_start=0,
        resampling_t_end=0,
        timesteps=[0],
        reward_fn=lambda values: torch.zeros(values.shape[0]),
        device="cpu",
    )
    fkd.ess_history = [40.1]

    with pytest.raises(FloatingPointError, match="ESS ratio invariant"):
        fkd.diagnostics()


def test_pi05_fkd_projection_truncates_max_action_latent_before_postprocess():
    observed = {}

    def postprocess(value):
        observed["postprocessor_shape"] = tuple(value.shape)
        return value

    adapter = SimpleNamespace(
        delta_actions_to_ee_trajectory=lambda actions: torch.cumsum(
            actions[:, :3], dim=0
        )
    )
    policy = PI05PolicySteer.__new__(PI05PolicySteer)
    policy._adapter = adapter
    policy._postprocessor = postprocess
    policy._original_action_dim = 7
    policy._action_chunk_horizon = 10
    latent = torch.zeros(40, 10, 32)

    trajectory = PI05PolicySteer._sample_to_trajectory_3d(policy, latent)
    assert observed["postprocessor_shape"] == (40, 10, 7)
    assert trajectory.shape == (40, 10, 3)


def test_diffusion_policy_reads_public_action_chunk_horizon_key():
    policy = DiffusionPolicySteer.__new__(DiffusionPolicySteer)
    torch.nn.Module.__init__(policy)
    policy.config = SimpleNamespace(n_action_steps=0)
    policy.post_init(
        adapter=object(),
        postprocessor=lambda value: value,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 10},
    )
    assert policy.config.n_action_steps == 10
    assert policy._action_chunk_horizon == 10


def test_coft_source_manifest_and_command_freeze_training_contract(tmp_path):
    manifest = write_source_sampler_manifest(
        tmp_path / "sources.json",
        new_indices=range(0, 10),
        old_ticket_indices={"ticket-a": range(10, 20)},
        replay_indices=range(20, 50),
        dataset_size=50,
        config=CoFTConfig(),
        seed=17,
    )
    assert manifest["num_draws"] == 32_000
    assert all(
        abs(manifest["actual_source_ratios"][key] - expected) <= 0.02
        for key, expected in {"new": 0.5, "old": 0.25, "replay": 0.25}.items()
    )
    command = build_lerobot_coft_command(
        python_executable=Path("/env/bin/python"),
        parent_checkpoint=Path("/models/policy-1"),
        dataset_root=Path("/data/coft"),
        dataset_repo_id="local/coft",
        source_sampler_manifest=tmp_path / "sources.json",
        output_dir=tmp_path / "train",
        seed=17,
    )
    joined = " ".join(command)
    assert "--num_processes 1" in joined
    assert "--batch_size=4" in joined
    assert "--gradient_accumulation_steps=8" in joined
    assert "--steps=1000" in joined
    assert "--freeze_pretrained_processor_stats=true" in joined
    assert "--tokenizer_path=/shared/hengyil6/vls/models/paligemma-tokenizer" in joined
    assert "--save_final_params_only=true" in joined
    assert "--policy.scheduler_auto_scale=false" in joined
    assert "--policy.optimizer_weight_decay=1e-10" in joined
    assert "--policy.optimizer_betas=[0.9,0.95]" in joined


def test_coft_catalog_maps_three_sources_to_exact_global_indices(tmp_path):
    features = {
        "observation.state": {"dtype": "float32", "shape": [8]},
        "action": {"dtype": "float32", "shape": [7]},
    }

    def dataset(name, frames):
        root = tmp_path / "sources" / name
        (root / "meta").mkdir(parents=True)
        (root / "meta" / "info.json").write_text(
            json.dumps(
                {
                    "total_frames": frames,
                    "total_episodes": 1,
                    "fps": 20,
                    "features": features,
                }
            ),
            encoding="utf-8",
        )
        return root

    new = dataset("new", 10)
    old = dataset("old", 20)
    replay = dataset("replay", 30)
    manifest = prepare_source_catalog(
        catalog_root=tmp_path / "catalog",
        manifest_path=tmp_path / "catalog-manifest.json",
        new_datasets={"tickets/new": new},
        old_ticket_datasets={"tickets/old": old},
        replay_datasets={"libero/replay": replay},
        seed=13,
    )
    assert manifest["repo_ids"] == ["tickets/new", "tickets/old", "libero/replay"]
    assert manifest["new_indices"] == list(range(10))
    assert manifest["old_ticket_indices"]["tickets/old"] == list(range(10, 30))
    assert manifest["replay_indices"] == list(range(30, 60))
    assert (tmp_path / "catalog" / "tickets" / "new").resolve() == new.resolve()
    command = build_lerobot_coft_command(
        python_executable=Path("/env/bin/python"),
        parent_checkpoint=Path("/models/policy"),
        dataset_root=tmp_path / "catalog",
        dataset_repo_id="tickets/new",
        dataset_repo_ids=manifest["repo_ids"],
        source_sampler_manifest=tmp_path / "catalog-manifest.json",
        output_dir=tmp_path / "train",
        seed=13,
    )
    assert "--dataset.repo_ids=['tickets/new', 'tickets/old', 'libero/replay']" in command


def test_lerobot_fork_exposes_self_improve_freeze_switches():
    from lerobot.configs.train import TrainPipelineConfig
    from lerobot.optim.schedulers import CosineDecayWithWarmupSchedulerConfig

    assert "freeze_pretrained_processor_stats" in TrainPipelineConfig.__dataclass_fields__
    assert "source_sampler_manifest" in TrainPipelineConfig.__dataclass_fields__
    assert "tokenizer_path" in TrainPipelineConfig.__dataclass_fields__
    assert "save_final_params_only" in TrainPipelineConfig.__dataclass_fields__
    assert "gradient_accumulation_steps" in TrainPipelineConfig.__dataclass_fields__
    scheduler = CosineDecayWithWarmupSchedulerConfig(
        num_warmup_steps=1000,
        num_decay_steps=30_000,
        peak_lr=2.5e-5,
        decay_lr=2.5e-6,
        auto_scale=False,
    )
    parameter = torch.nn.Parameter(torch.ones(()))
    optimizer = torch.optim.AdamW([parameter], lr=2.5e-5)
    built = scheduler.build(optimizer, num_training_steps=1000)
    for _ in range(10):
        optimizer.step()
        built.step()
    # With auto scaling disabled, step 10 is still near the beginning of the
    # declared 1000-step warmup, rather than a rescaled 33-step warmup.
    assert optimizer.param_groups[0]["lr"] < 5e-7


def test_training_smoke_config_is_exactly_twenty_steps(tmp_path):
    config = TrainingSmokeConfig()
    config.validate()
    assert config.optimizer_steps == 20
    manifest = write_source_sampler_manifest(
        tmp_path / "smoke-sources.json",
        new_indices=range(0, 64),
        old_ticket_indices={"ticket": range(64, 128)},
        replay_indices=range(128, 192),
        dataset_size=192,
        config=config,
        seed=20260825,
    )
    assert manifest["actual_source_counts"] == {
        "new": 320,
        "old": 160,
        "replay": 160,
    }


def _trajectory_batch(count=4, points=11):
    positions = np.zeros((count, points, 3), dtype=np.float64)
    for index in range(count):
        positions[index, :, 0] = np.linspace(0, 0.1 + index * 0.02, points)
    orientations = np.zeros((count, points, 4), dtype=np.float64)
    orientations[:, :, 3] = 1.0
    grippers = np.ones((count, points), dtype=np.float64)
    grippers[:, points // 2 :] = -1
    return TaskSpaceTrajectoryBatch(
        positions=positions,
        orientations=orientations,
        grippers=grippers,
        sample_ids=[f"s{index}" for index in range(count)],
    )


def test_frozen_trajectory_descriptors_are_79d_and_verifier_modes_are_20d():
    trajectories = _trajectory_batch()
    keypoints = np.arange(24, dtype=np.float64).reshape(8, 3) / 100
    descriptor = TrajectoryDescriptorEncoder().encode(trajectories, keypoints)
    assert descriptor.descriptors.shape == (4, 79)
    assert descriptor.keypoint_validity.shape == (4, 8)
    mode_features = ModeFeatureEncoderV1().encode(trajectories)
    assert mode_features.shape == (4, 20)
    np.testing.assert_allclose(mode_features[:, :3], 0.0)


def test_task_keypoints_prioritize_instruction_object_then_stable_ids():
    positions = np.asarray(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
    )
    selected = select_task_keypoints(
        positions,
        instruction="pick up the red mug",
        mask_ids=[30, 10, 20],
        keypoint_to_object={0: "basket", 1: "red_mug", 2: "plate"},
    )

    np.testing.assert_array_equal(selected[0], positions[1])
    np.testing.assert_array_equal(selected[1], positions[0])
    np.testing.assert_array_equal(selected[2], positions[2])


def _round_evidence(tmp_path):
    trajectories = _trajectory_batch()
    actions = ActionChunkBatch(
        actions=np.zeros((4, 10, 7), dtype=np.float32),
        sample_ids=trajectories.sample_ids,
        context_id="ctx",
        round_id=1,
        checkpoint_id="policy-0",
        action_space="delta_ee_pose",
        coordinate_frame="world",
    )
    modes = []
    for index in range(2):
        modes.append(
            ModeEvidence(
                mode_id=f"m{index}",
                component_index=index,
                weight=0.6 if index == 0 else 0.4,
                member_indices=np.array([index, index + 2]),
                representative_indices={"medoid": index, "diverse": index + 2, "boundary": (index + 1) % 4},
                representative_sample_ids={"medoid": f"s{index}", "diverse": f"s{index+2}", "boundary": f"s{(index+1)%4}"},
                card_path=tmp_path / f"m{index}.png",
                projection_unavailable=False,
            )
        )
    return RoundEvidence(
        context_id="ctx",
        round_id=1,
        checkpoint_id="policy-0",
        action_batch=actions,
        trajectories=trajectories,
        normalized_positions=np.zeros((4, 8, 3)),
        normalized_rotvecs=np.zeros((4, 8, 3)),
        normalized_grippers=np.zeros((4, 8)),
        descriptors=np.zeros((4, 79)),
        reduced_descriptors=np.zeros((4, 2)),
        labels=np.array([0, 1, 0, 1]),
        responsibilities=np.full((4, 2), 0.5),
        modes=tuple(modes),
        fit_degraded=False,
        fit_metadata={"multiplicities": {"0": 3, "1": 1}},
        sampling_diagnostics=SamplingDiagnostics(
            ess_history=(4.0, 2.0),
            ancestor_ids=(0, 0, 0, 1),
            ess_ratio=0.5,
            unique_ratio=0.5,
            resample_indices=((0, 0, 1, 0),),
        ),
    )


def test_round_evidence_persists_sampling_diagnostics_and_hashes(tmp_path):
    evidence = _round_evidence(tmp_path)
    path = _save_round_evidence(tmp_path / "round_001", evidence)
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "mode-round-evidence-v2"
    assert metadata["sample_ids"] == ["s0", "s1", "s2", "s3"]
    assert metadata["sampling_diagnostics"]["ancestor_ids"] == [0, 0, 0, 1]
    assert metadata["sampling_diagnostics"]["ess_history"] == [4.0, 2.0]
    assert metadata["fit_metadata"]["multiplicities"] == {"0": 3, "1": 1}
    assert metadata["analysis_sha256"] == sha256_file(path)
    assert len(metadata["action_sha256"]) == 64


def test_verifier_decision_records_pre_route_remaining_budget(tmp_path):
    evidence = _round_evidence(tmp_path)

    class Gate:
        def analyze(self, context, batch, round_dir):
            assert context.context_id == batch.context_id == evidence.context_id
            return evidence

    class Renderer:
        def render(self, *, output_path, **kwargs):
            del kwargs
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"overlay")
            return SimpleNamespace(path=output_path)

    class Planner:
        def score(self, context, round_evidence, geometry, overlay_path, **kwargs):
            del context, geometry, overlay_path, kwargs
            return SemanticPlan(
                mode_scores=tuple(
                    SemanticModeScore(mode.mode_id, 0.9 - 0.1 * index, "ok")
                    for index, mode in enumerate(round_evidence.modes)
                ),
                required_trajectory_pattern="reach then grasp",
                observed_stage_id="reach_object",
                stage_confidence=0.95,
                model="gemini-robotics-er-2-preview",
                prompt_version="mode-scorer-v3",
            )

    memory = IncidentMemory(tmp_path / "incidents")
    runtime = ModeAwareRuntime(
        config=ModeGateConfig(
            sample_count=4,
            controller_mode="fixed_budget_4",
            baseline_kind="fixed_budget",
            baseline_budget=4,
            exploration_epsilon=0.0,
        ),
        gate=Gate(),
        planner=Planner(),
        combined_renderer=Renderer(),
        geometry_factory=lambda context: SimpleNamespace(
            score_round=lambda value: tuple(
                GeometryEvidence(
                    mode_id=mode.mode_id,
                    collision_risk=0.0,
                    reachability=1.0,
                    grasp_plausibility=0.8,
                    hard_safety_veto=False,
                )
                for mode in value.modes
            )
        ),
        incidents=memory,
    )
    runtime.start_episode(stage_id="1")
    runtime.controller.state.verification_due = True
    runtime.controller.state.failure_count = 1
    snapshot = DecisionSnapshot(
        snapshot_id="snapshot-1",
        policy_id="policy_000",
        simulator_state_path=tmp_path / "simulator.npz",
        controller_state=runtime.controller.state.as_dict(),
        rng_state_path=tmp_path / "runtime.pt",
        provenance={},
        snapshot_hash="a" * 64,
        observation_hash="b" * 64,
    )
    result = runtime.process_batch(
        context=GateContext(
            context_id="ctx",
            observation_image=np.zeros((16, 16, 3), dtype=np.uint8),
            task_instruction="open drawer",
            task_stage="1",
            metadata={"code_revision": "test-source"},
        ),
        batch=evidence.action_batch,
        artifact_root=tmp_path / "artifacts",
        scene_feature=np.zeros(2048, dtype=np.float32),
        scene_feature_path=tmp_path / "scene.npz",
        snapshot=snapshot,
    )
    assert result.status.value == "RE-STEER"
    assert result.route.remaining_budget == 3
    decision = list(memory.decisions.iter_valid())[0]
    assert decision["remaining_budget"] == 4
    assert decision["provenance"]["retry_index"] == 0
    assert decision["provenance"]["remaining_budget"] == 4
    feature_metadata = json.loads(
        Path(decision["verifier_feature_path"])
        .with_suffix(".json")
        .read_text(encoding="utf-8")
    )
    assert feature_metadata["remaining_budget"] == 4
    assert feature_metadata["retry_index"] == 0


def test_geometry_hard_veto_and_lexicographic_medoid_selection(tmp_path):
    evidence = _round_evidence(tmp_path)
    context = GeometryContext(
        workspace=AxisAlignedBox(np.array([-1, -1, -1]), np.array([1, 1, 1])),
        obstacles=(AxisAlignedBox(np.array([0.15, -0.1, -0.1]), np.array([0.25, 0.1, 0.1])),),
    )
    geometry = GeometryScorer(context).score_round(evidence)
    assert geometry[1].hard_safety_veto is False
    semantics = (
        SemanticModeScore("m0", 0.7, "ok"),
        SemanticModeScore("m1", 0.9, "better"),
    )
    selected = select_execution_medoid(evidence.modes, geometry, semantics)
    assert selected.mode_id == "m1"
    assert selected.sample_index == 1


def _verifier_input(order=(0, 1, 2)):
    rng = np.random.default_rng(8)
    ee = rng.normal(size=(3, 20)).astype(np.float32)
    geometry = rng.normal(size=(3, 3)).astype(np.float32)
    semantic = rng.normal(size=(3, 1)).astype(np.float32)
    weights = np.array([0.2, 0.3, 0.5], dtype=np.float32)
    order = np.asarray(order)
    return ModeVerifierInput(
        scene_feature=np.ones(2048, dtype=np.float32),
        mode_ee_features=ee[order],
        geometry_features=geometry[order],
        semantic_features=semantic[order],
        mode_weights=weights[order],
        global_features=np.zeros(7, dtype=np.float32),
    )


def test_deep_sets_is_permutation_invariant_and_binomial_target_is_soft():
    torch.manual_seed(1)
    model = GroundedCapabilityVerifier().eval()
    first = model(_verifier_input((0, 1, 2)))
    second = model(_verifier_input((2, 0, 1)))
    torch.testing.assert_close(first, second)
    encoded = model.encode_one(_verifier_input())
    assert encoded.shape == (VERIFIER_INPUT_DIMS,)
    assert first.shape == (1, 2)
    loss = binomial_cross_entropy(
        torch.tensor([[0.0, 0.0]]),
        successes=torch.tensor([4]),
        trials=torch.tensor([16]),
    )
    assert loss.item() == pytest.approx(-np.log(0.5))


def test_verifier_predecision_sidecar_roundtrip(tmp_path):
    item = _verifier_input()
    path = save_verifier_input(
        tmp_path / "sidecars/decision.npz",
        item,
        metadata={"context_id": "ctx"},
    )
    restored = load_verifier_input(path)
    np.testing.assert_allclose(restored.scene_feature, item.scene_feature, atol=1e-3)
    np.testing.assert_allclose(
        restored.mode_ee_features, item.mode_ee_features, atol=1e-3
    )
    np.testing.assert_allclose(restored.mode_weights, item.mode_weights)
    assert json.loads(path.with_suffix(".json").read_text())["context_id"] == "ctx"


def test_verifier_standardizer_excludes_explicitly_missing_channels():
    first = _verifier_input()
    second = ModeVerifierInput(
        **{
            **first.__dict__,
            "scene_feature": np.full(2048, 1e6, dtype=np.float32),
            "scene_missing": True,
            "geometry_features": np.full((3, 3), 1e6, dtype=np.float32),
            "mode_missing": np.asarray(
                [[False, True, False, False]] * 3, dtype=bool
            ),
        }
    )
    standardizer = FeatureStandardizer.fit([first, second])
    scene_mean, _ = standardizer.statistics["scene_feature"]
    geometry_mean, _ = standardizer.statistics["geometry_features"]
    np.testing.assert_allclose(scene_mean, first.scene_feature)
    np.testing.assert_allclose(geometry_mean, first.geometry_features.mean(axis=0))


def test_binomial_platt_uses_rates_not_any_success_labels():
    logits = np.asarray([-2.0, 2.0], dtype=np.float64)
    first = PlattCalibrator.fit_binomial(
        logits,
        failures=np.asarray([4, 12]),
        trials=np.asarray([16, 16]),
    )
    second = PlattCalibrator.fit_binomial(
        logits,
        failures=np.asarray([16, 48]),
        trials=np.asarray([64, 64]),
    )
    np.testing.assert_allclose(
        [first.slope, first.intercept],
        [second.slope, second.intercept],
        atol=1e-6,
    )


def test_verifier_training_pipeline_is_grouped_calibrated_and_fail_closed(tmp_path):
    examples = []
    for index in range(8):
        item = _verifier_input()
        item = ModeVerifierInput(
            **{
                **item.__dict__,
                "scene_feature": np.full(
                    2048, float(index % 2), dtype=np.float32
                ),
            }
        )
        path = tmp_path / f"feature-{index}.npz"
        save_verifier_input(path, item, metadata={"policy_id": "policy-v1"})
        split = "train" if index < 4 else "calibration" if index < 6 else "test"
        success = 16 if index % 2 == 0 else 0
        examples.append(
            VerifierExample(
                record_id=f"r{index}",
                policy_id="policy-v1",
                group_id=f"g{index}",
                split=split,
                feature_path=str(path),
                source="counterfactual_replay",
                successes=success,
                trials=16,
                weight=1.0,
                weak=False,
                behavior_propensity=1.0,
            )
        )
    config = VerifierTrainingConfig(
        max_epochs=3,
        patience=2,
        batch_size=2,
        bootstrap_samples=20,
        min_train_contexts=100,
        min_train_each_side=10,
        min_calibration_contexts=10,
        min_calibration_each_side=5,
        min_test_contexts=10,
        min_test_expansion_contexts=5,
        max_ece=1.0,
        channel_set="scene_only",
    )
    result = train_verifier(
        examples,
        policy_id="policy-v1",
        output_root=tmp_path / "artifacts",
        config=config,
    )
    assert not result.gate.passed
    assert any("train strong contexts" in reason for reason in result.gate.reasons)
    assert "classwise_ece" in result.metrics
    assert result.metrics["decision_rule"] == "head_argmax"
    predictor = DeployedVerifierPredictor(Path(result.artifact_root))
    assert predictor.channel_set == "scene_only"
    prediction = predictor.predict(_verifier_input())
    assert prediction.route in {ControllerRoute.RESTEER, ControllerRoute.EXPAND}
    assert len(prediction.logits) == 2
    assert 0.0 <= prediction.p_expansion <= 1.0
    manifest = json.loads(
        (Path(result.artifact_root) / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["decision_rule"] == "head_argmax"
    assert "threshold" not in manifest
    changed_modes = _verifier_input()
    changed_modes = ModeVerifierInput(
        **{
            **changed_modes.__dict__,
            "geometry_features": np.ones_like(changed_modes.geometry_features),
            "semantic_features": np.zeros_like(changed_modes.semantic_features),
        }
    )
    assert predictor.predict_probability(changed_modes) == pytest.approx(
        predictor.predict_probability(_verifier_input()), abs=1e-8
    )

    leaked = [
        examples[0],
        VerifierExample(
            **{**examples[1].__dict__, "group_id": "g0", "split": "test"}
        ),
    ]
    with pytest.raises(ValueError, match="group leakage"):
        assert_group_isolation(leaked)


def test_verifier_channel_ablation_and_true_holdout_contract(tmp_path):
    item = _verifier_input()
    scene_only = ablate_verifier_input(item, "scene_only")
    modes_only = ablate_verifier_input(item, "modes_only")
    assert scene_only.mode_missing.all()
    assert scene_only.global_missing.all()
    assert not scene_only.scene_missing
    assert modes_only.scene_missing
    assert not modes_only.mode_missing.all()

    examples = []
    for split in ("train", "calibration", "test"):
        for task_id in ("held", "fit"):
            path = tmp_path / f"{split}-{task_id}.npz"
            save_verifier_input(path, item, metadata={"policy_id": "policy-v1"})
            examples.append(
                VerifierExample(
                    record_id=f"{split}-{task_id}",
                    policy_id="policy-v1",
                    group_id=f"{split}-{task_id}",
                    split=split,
                    feature_path=str(path),
                    source="audit",
                    successes=8 if task_id == "fit" else 0,
                    trials=16,
                    weight=1.0,
                    weak=False,
                    behavior_propensity=1.0,
                    suite="libero",
                    task_id=task_id,
                    perturbation_variant="base",
                    origin_policy_id="origin-1",
                    recorded_at="2026-08-25T00:00:00+00:00",
                )
            )
    held_out = build_verifier_holdout(examples, kind="task", value="held")
    assert {row.task_id for row in held_out if row.split != "test"} == {"fit"}
    assert {row.task_id for row in held_out if row.split == "test"} == {"held"}
    correlation = verifier_channel_correlation(
        [row for row in examples if row.split == "test"], [item, item]
    )
    assert correlation["contexts"] == 2
    assert correlation["columns"][-1] == "p_expansion"


class _PrefixSource:
    def encode_joint(self, image, instruction):
        hidden = np.stack([np.ones(2048), np.ones(2048) * 3])
        return MaskedHiddenStates(hidden, np.array([True, False]))

    def encode_goal(self, instruction):
        hidden = np.stack([np.ones(2048) * 2, np.ones(2048) * 50])
        return MaskedHiddenStates(hidden, np.array([True, False]))

    def encode_observation(self, image):
        hidden = np.stack([np.arange(2048), np.ones(2048) * 100])
        return MaskedHiddenStates(hidden, np.array([True, False]))


def test_theta0_scene_encoder_masks_padding_and_caches_fp16(tmp_path):
    encoder = Theta0SceneEncoder(
        _PrefixSource(),
        theta0_checksum="a" * 64,
        processor_hash="b" * 64,
        cache_dir=tmp_path,
    )
    first = encoder.encode(np.zeros((8, 8, 3), dtype=np.uint8), "pick")
    second = encoder.encode(np.zeros((8, 8, 3), dtype=np.uint8), "pick")
    np.testing.assert_allclose(first.joint_feature, 1.0)
    assert np.linalg.norm(first.e_goal) == pytest.approx(1.0, abs=1e-3)
    assert np.linalg.norm(first.e_obs) == pytest.approx(1.0, abs=1e-3)
    assert second.feature_id == first.feature_id
    assert np.array_equal(first.joint_feature, second.joint_feature)
    assert np.array_equal(first.e_goal, second.e_goal)
    assert np.array_equal(first.e_obs, second.e_obs)
    assert first.cache_path is not None and first.cache_path.is_file()


def test_theta0_scene_encoder_cache_key_uses_exact_source_inputs(tmp_path):
    class FingerprintedSource(_PrefixSource):
        fingerprint = "1" * 64

        def input_fingerprint(self, image, instruction):
            return self.fingerprint

    source = FingerprintedSource()
    encoder = Theta0SceneEncoder(
        source,
        theta0_checksum="a" * 64,
        processor_hash="b" * 64,
        cache_dir=tmp_path,
    )
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    first = encoder.encode(image, "pick")
    source.fingerprint = "2" * 64
    second = encoder.encode(image, "pick")

    assert first.feature_id != second.feature_id
    assert first.metadata["input_hash"] == "1" * 64
    assert second.metadata["input_hash"] == "2" * 64


def test_processor_digest_binds_external_tokenizer(tmp_path):
    checkpoint = tmp_path / "checkpoint"
    tokenizer = tmp_path / "tokenizer"
    checkpoint.mkdir()
    tokenizer.mkdir()
    (checkpoint / "policy_preprocessor.json").write_text("{}", encoding="utf-8")
    (tokenizer / "tokenizer.json").write_text("first", encoding="utf-8")
    first = processor_artifact_digest(checkpoint, tokenizer_root=tokenizer)
    (tokenizer / "tokenizer.json").write_text("second", encoding="utf-8")
    second = processor_artifact_digest(checkpoint, tokenizer_root=tokenizer)

    assert first != second


class _PlannerModels:
    def get(self, *, model):
        assert model == "gemini-robotics-er-2-preview"


class _PlannerInteractions:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.kwargs = None

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return SimpleNamespace(
            output_text=json.dumps(self.payload),
            usage_metadata={"total_token_count": 12},
        )


def test_gemini_planner_scores_every_mode_once_and_caches(tmp_path):
    evidence = _round_evidence(tmp_path)
    card = tmp_path / "combined.png"
    card.write_bytes(b"png")
    payload = {
        "modes": [
            {"mode_id": "m0", "semantic_score": 0.2, "reason": "a", "predicted_failure_types": []},
            {"mode_id": "m1", "semantic_score": 0.8, "reason": "b", "predicted_failure_types": ["offset"]},
        ],
        "required_trajectory_pattern": "approach then grasp",
        "observed_stage_id": "stage_1",
        "stage_confidence": 0.9,
    }
    models = _PlannerModels()
    interactions = _PlannerInteractions(payload)
    planner = GeminiSemanticPlanner(
        client=SimpleNamespace(models=models, interactions=interactions),
        cache_dir=tmp_path / "cache",
    )
    context = GateContext("ctx", np.zeros((8, 8, 3), np.uint8), "pick", "1")
    geometry = tuple(
        GeometryEvidence(mode.mode_id, 0.1, 0.9, 0.8, False)
        for mode in evidence.modes
    )
    first = planner.score(context, evidence, geometry, card)
    second = planner.score(context, evidence, geometry, card)
    assert [item.mode_id for item in first.mode_scores] == ["m0", "m1"]
    assert second.raw_response["metadata"]["cache_hit"] is True
    assert interactions.calls == 1
    assert interactions.kwargs["model"] == "gemini-robotics-er-2-preview"
    assert interactions.kwargs["generation_config"] == {"thinking_level": "high"}
    assert interactions.kwargs["response_format"]["mime_type"] == "application/json"
    assert [item["type"] for item in interactions.kwargs["input"]] == ["text", "image"]


def test_gemini_planner_rejects_descriptive_stage_identity(tmp_path):
    evidence = _round_evidence(tmp_path)
    card = tmp_path / "combined.png"
    card.write_bytes(b"png")
    interactions = _PlannerInteractions(
        {
            "modes": [
                {
                    "mode_id": mode.mode_id,
                    "semantic_score": 0.5,
                    "reason": "ok",
                    "predicted_failure_types": [],
                }
                for mode in evidence.modes
            ],
            "required_trajectory_pattern": "approach",
            "observed_stage_id": "Stage 1: approach object (keypoint 11)",
            "stage_confidence": 0.95,
        }
    )
    planner = GeminiSemanticPlanner(
        client=SimpleNamespace(models=_PlannerModels(), interactions=interactions),
        max_retries=0,
    )
    context = GateContext("ctx", np.zeros((8, 8, 3), np.uint8), "pick", "stage_1")
    geometry = tuple(
        GeometryEvidence(mode.mode_id, 0.1, 0.9, 0.8, False)
        for mode in evidence.modes
    )
    with pytest.raises(Exception, match="semantic scoring failed"):
        planner.score(context, evidence, geometry, card)
    assert interactions.calls == 1


def test_gemini_planner_preflight_timeout_is_bounded():
    class BlockingModels:
        def get(self, *, model):
            time.sleep(0.25)

    planner = GeminiSemanticPlanner(
        client=SimpleNamespace(models=BlockingModels()),
        timeout_seconds=0.02,
    )
    started = time.monotonic()
    with pytest.raises(Exception, match="exceeded"):
        planner.preflight()
    assert time.monotonic() - started < 0.20


def test_gemini_planner_canary_exercises_interactions_api():
    payload = {
        "modes": [
            {
                "mode_id": "canary-m0",
                "semantic_score": 1.0,
                "reason": "provider canary",
                "predicted_failure_types": [],
            }
        ],
        "required_trajectory_pattern": "none",
        "observed_stage_id": "UNKNOWN",
        "stage_confidence": 1.0,
    }
    models = _PlannerModels()
    interactions = _PlannerInteractions(payload)
    planner = GeminiSemanticPlanner(
        client=SimpleNamespace(models=models, interactions=interactions)
    )

    planner.preflight(exercise_interactions=True)

    assert interactions.calls == 1
    assert interactions.kwargs["store"] is False


def test_incident_memory_is_append_only_idempotent_and_joins_late_labels(tmp_path):
    memory = IncidentMemory(tmp_path)
    decision = VerifierDecisionRecord(
        record_id="r1", context_id="c", policy_id="p", snapshot_id="s",
        snapshot_hash="a" * 64, scene_feature_path="", route="RE-STEER",
        verifier_decision="RE-STEER", verifier_logits=(1.0, 0.0),
        p_expansion=0.2, decision_rule="head_argmax",
        controller_mode="learned_verifier",
        failure_count=1, remaining_budget=3,
    )
    assert memory.record_decision(decision)
    assert not memory.record_decision(decision)
    label = VerifierLabelRecord(
        record_id="r1", label_version="v1", source="counterfactual_replay",
        branches=16, successes=4, p_expansion=0.75, policy_id="p",
        snapshot_hash="a" * 64,
    )
    assert memory.attach_label(label)
    assert len(memory.joined_training_rows()) == 1
    with pytest.raises(ValueError):
        VerifierLabelRecord(
            record_id="r1", label_version="v2", source="demo_match",
            branches=16, successes=1, p_expansion=15 / 16, policy_id="p",
            snapshot_hash="a" * 64, weak=False,
        )
    with pytest.raises(ValueError, match="remedy evidence"):
        VerifierLabelRecord(
            record_id="r1",
            label_version="v3",
            source="post_expansion_recheck",
            branches=1,
            successes=1,
            p_expansion=0.0,
            policy_id="p",
            snapshot_hash="a" * 64,
        )


def test_factual_retry_outcomes_close_pending_decisions_with_propensity(tmp_path):
    memory = IncidentMemory(tmp_path / "incidents")
    for index in range(2):
        memory.record_decision(
            VerifierDecisionRecord(
                record_id=f"factual-{index}",
                context_id="episode-context",
                policy_id="policy-1",
                snapshot_id=f"snapshot-{index}",
                snapshot_hash=str(index + 1) * 64,
                scene_feature_path="",
                route="RE-STEER",
                verifier_decision="EXPANSION",
                verifier_logits=(0.0, 1.0),
                p_expansion=0.95,
                decision_rule="head_argmax",
                controller_mode="learned_verifier",
                failure_count=index + 1,
                remaining_budget=3 - index,
                behavior_propensity=0.1,
            )
        )
    runtime = ModeAwareRuntime.__new__(ModeAwareRuntime)
    runtime.incidents = memory
    runtime._pending_factual = [
        {
            "record_id": f"factual-{index}",
            "policy_id": "policy-1",
            "snapshot_hash": str(index + 1) * 64,
            "behavior_propensity": 0.1,
            "data_split": "train",
        }
        for index in range(2)
    ]
    runtime._close_factual_labels(success=True)
    labels = list(memory.labels.iter_valid())
    assert len(labels) == 2
    assert all(item["source"] == "factual_online_retry" for item in labels)
    assert all(item["branches"] == item["successes"] == 1 for item in labels)
    assert all(item["behavior_propensity"] == 0.1 for item in labels)
    assert runtime._pending_factual == []
    weights = verifier_training_weights(
        [
            VerifierExample(
                record_id="explore",
                policy_id="policy-1",
                group_id="episode-context",
                split="train",
                feature_path="unused",
                source="factual_online_retry",
                successes=1,
                trials=1,
                weight=1.0,
                weak=False,
                behavior_propensity=0.1,
            ),
            VerifierExample(
                record_id="ordinary",
                policy_id="policy-1",
                group_id="episode-context",
                split="train",
                feature_path="unused",
                source="factual_online_retry",
                successes=1,
                trials=1,
                weight=1.0,
                weak=False,
                behavior_propensity=1.0,
            ),
        ],
        ipw_clip=10.0,
    )
    assert weights == {"explore": 5.0, "ordinary": 0.5}


def test_demo_match_is_weak_same_snapshot_same_target_only(tmp_path):
    analysis = tmp_path / "analysis.npz"
    positions = np.asarray(
        [[[0.0, 0.0, 0.0], [0.01, 0.0, 0.0], [0.02, 0.0, 0.0]]]
    )
    np.savez(
        analysis,
        positions=positions,
        grippers=np.asarray([[1.0, 1.0, -1.0]]),
        medoid_indices=np.asarray([0]),
    )
    feature = tmp_path / "feature.npz"
    feature.write_bytes(b"feature")
    memory = IncidentMemory(tmp_path / "incidents")
    memory.record_decision(
        VerifierDecisionRecord(
            record_id="r-demo",
            context_id="c",
            policy_id="p",
            snapshot_id="snapshot",
            snapshot_hash="b" * 64,
            scene_feature_path="",
            verifier_feature_path=str(feature),
            route="RE-STEER",
            verifier_decision="RE-STEER",
            verifier_logits=(1.0, 0.0),
            p_expansion=0.2,
            decision_rule="head_argmax",
            controller_mode="learned_verifier",
            failure_count=1,
            remaining_budget=4,
            provenance={
                "round_analysis_path": str(analysis),
                "round_analysis_sha256": sha256_file(analysis),
            },
        )
    )
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    writer = DemoWriter(
        tmp_path / "demo.h5",
        task="task",
        ticket_id="ticket",
        operator="operator",
        init_state_id="failure",
        snapshot_id="snapshot",
        hashes={"snapshot": "b" * 64},
        coverage_cell="failure",
    )
    writer.start(
        DemoFrame(image, image, np.zeros(8), np.zeros(1)),
        ee_position=positions[0, 0],
    )
    for index, gripper in enumerate((1.0, -1.0), start=1):
        action = np.zeros(7)
        action[6] = gripper
        writer.append(
            action,
            DemoFrame(image, image, np.zeros(8), np.asarray([index])),
            reward=0.0,
            done=False,
            success=False,
            ee_position=positions[0, index],
        )
    demo = writer.save()
    result = attach_demo_match_label(
        memory,
        record_id="r-demo",
        demo_path=demo,
        label_version="demo-v1",
        candidate_target_object_id="bowl",
        demo_target_object_id="bowl",
    )
    assert result.matched and result.label_attached
    label = next(memory.labels.iter_valid())
    assert label["weak"] and label["weight"] == 0.25
    assert label["data_split"] == "train"


def test_counterfactual_worker_restores_each_branch_and_resumes_idempotently(tmp_path):
    memory = IncidentMemory(tmp_path / "incidents")
    decision = VerifierDecisionRecord(
        record_id="decision-1",
        context_id="context-1",
        policy_id="policy-old",
        snapshot_id="snapshot-1",
        snapshot_hash="a" * 64,
        scene_feature_path="",
        route="RE-STEER",
        verifier_decision="RE-STEER",
        verifier_logits=(1.0, 0.0),
        p_expansion=0.2,
        decision_rule="head_argmax",
        controller_mode="learned_verifier",
        failure_count=1,
        remaining_budget=4,
    )
    memory.record_decision(decision)

    class SnapshotStore:
        def __init__(self):
            self.calls = []

        def restore(self, snapshot_id, **kwargs):
            self.calls.append((snapshot_id, kwargs["restore_policy_state"]))
            return {
                "manifest": {
                    "snapshot_hash": "a" * 64,
                    "controller_state": {"retry_index": 0},
                }
            }

    snapshots = SnapshotStore()
    executor_calls = []

    def execute(**kwargs):
        executor_calls.append(kwargs["branch_seed"])
        return BranchOutcome(
            success=True,
            chunks_executed=1,
            stage_advanced=True,
        )

    worker = CounterfactualReplayWorker(
        incidents=memory,
        snapshots=snapshots,
        adapter=object(),
        policy_loader=lambda policy_id: SimpleNamespace(reset=lambda: None),
        branch_executor=execute,
        ledger_path=tmp_path / "branches.jsonl",
    )
    new_policy_feature = tmp_path / "new-policy-feature.npz"
    new_policy_feature.write_bytes(b"feature")
    first = worker.run(
        record_id="decision-1",
        policy_id="policy-new",
        label_version="labels-v1",
        verifier_feature_path=new_policy_feature,
    )
    second = worker.run(
        record_id="decision-1",
        policy_id="policy-new",
        label_version="labels-v1",
        verifier_feature_path=new_policy_feature,
    )

    assert first.branches == 16 and first.successes == 16
    assert first.p_expansion == 0.0 and first.label_attached
    assert not second.label_attached
    assert len(executor_calls) == 16
    assert snapshots.calls == [("snapshot-1", False)] * 16


def test_new_policy_replay_coordinator_uses_frozen_plan_and_exact_feature_path(tmp_path):
    result_path = tmp_path / "result.json"
    feature_path = tmp_path / "features" / "r1.npz"
    unsigned = {
        "schema_version": "new-policy-counterfactual-plan-v2",
        "job_id": "job-1",
        "policy_id": "policy-new",
        "checkpoint_path": "/checkpoint",
        "checkpoint_digest": "a" * 64,
        "snapshot_root": "/snapshots",
        "incident_root": "/incidents",
        "retry_estimand": "retry failure",
        "adaptive_branches": [16, 32, 64],
        "decision_rule": "head_argmax",
        "max_posterior_width": 0.20,
        "contexts": [
            {
                "record_id": "r1",
                "origin_policy_id": "policy-old",
                "target_policy_id": "policy-new",
                "snapshot_id": "s1",
                "snapshot_hash": "b" * 64,
                "snapshot_manifest_path": "/snapshots/s1/manifest.json",
                "remaining_budget": 4,
                "data_split": "test",
                "fresh_feature_output_path": str(feature_path),
            }
        ],
        "result_path": str(result_path),
    }
    digest = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({**unsigned, "plan_sha256": digest}), encoding="utf-8"
    )

    class Replay:
        def __init__(self):
            self.calls = []

        def run(self, **kwargs):
            self.calls.append(kwargs)
            return CounterfactualResult(
                record_id=kwargs["record_id"],
                policy_id=kwargs["policy_id"],
                branches=16,
                successes=4,
                p_expansion=0.75,
                posterior_interval=(0.5, 0.9),
                label_attached=True,
            )

    replay = Replay()

    def feature_builder(*, context, policy_id, output_path):
        assert context["snapshot_id"] == "s1"
        assert policy_id == "policy-new"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fresh-policy-feature")
        return output_path

    value = NewPolicyReplayCoordinator(
        replay_worker=replay,
        feature_builder=feature_builder,
    ).run_plan(plan_path)
    assert value["complete"]
    assert value["contexts_completed"] == 1
    assert replay.calls[0]["data_split"] == "test"
    assert replay.calls[0]["verifier_feature_path"] == feature_path
    assert json.loads(result_path.read_text())["plan_sha256"] == digest


def test_fixed_budget_counterfactual_executes_fresh_schedule_until_progress():
    class Adapter:
        def __init__(self):
            self.steps = 0
            self.stage = "stage-1"

        def step(self, action):
            assert isinstance(action, torch.Tensor)
            assert action.dtype is torch.float32
            self.steps += 1
            if self.steps == 20:
                self.stage = "stage-2"
            return None, 0.0, False, False, {"success": False}

        def get_progress_predicate(self):
            return {"stage_id": self.stage, "advanced": False}

        def check_success(self):
            return False

    conditions = []

    def fresh_sampler(*, adapter, policy, condition):
        conditions.append(condition)
        actions = np.zeros((10, 7), dtype=np.float32)
        actions[:, 0] = condition.retry_index + 1
        return FreshMedoidSelection(
            actions=actions,
            mode_id=f"mode-{condition.retry_index}",
            sample_index=condition.retry_index,
        )

    adapter = Adapter()
    outcome = FixedBudgetResteerExecutor(fresh_sampler=fresh_sampler)(
        adapter=adapter,
        policy=object(),
        branch_seed=123,
        remaining_budget=4,
        controller_state={"retry_index": 0},
    )
    assert outcome.success and outcome.stage_advanced
    assert outcome.chunks_executed == 2 and adapter.steps == 20
    assert [item.retry_index for item in conditions] == [0, 1]
    assert [item.guide_mult for item in conditions] == [1.0, 1.15]


def test_offline_replay_loads_guidance_as_list(tmp_path, monkeypatch):
    import utils.guidance_utils as guidance_utils

    source = tmp_path / "stage1_guidance.txt"
    source.write_text("placeholder", encoding="utf-8")
    reward = lambda keypoints, trajectory: trajectory.sum()
    monkeypatch.setattr(
        guidance_utils,
        "load_functions_from_txt",
        lambda path, validate: (reward,),
    )
    application = HgpuReplayApplication.__new__(HgpuReplayApplication)
    functions = application._load_guidance(
        {
            "guidance": {
                "enabled": True,
                "stage": 1,
                "files": [
                    {
                        "path": str(source),
                        "sha256": sha256_file(source),
                    }
                ],
            }
        }
    )
    assert isinstance(functions, list)
    assert functions == [reward]


def test_fixed_budget_counterfactual_consumes_no_safe_opportunities_without_actions():
    calls = []

    def no_safe_mode(*, adapter, policy, condition):
        calls.append(condition.retry_index)
        return None

    outcome = FixedBudgetResteerExecutor(fresh_sampler=no_safe_mode)(
        adapter=object(),
        policy=object(),
        branch_seed=9,
        remaining_budget=2,
        controller_state={"retry_index": 2},
    )
    assert not outcome.success and outcome.chunks_executed == 0
    assert calls == [2, 3]
    assert all(item["no_safe_mode"] for item in outcome.metadata["attempts"])


def test_signature_lookup_requires_validated_remedy_and_headroom(tmp_path):
    goal = np.ones(4, dtype=np.float32)
    obs = np.array([1, 2, 3, 4], dtype=np.float32)
    goal_path, obs_path = tmp_path / "goal.npy", tmp_path / "obs.npy"
    np.save(goal_path, goal)
    np.save(obs_path, obs)
    record = CapabilitySignatureRecord(
        signature_id="sig", suite="libero", task_id="1", perturbation_variant="base",
        failure_mode=FailureMode.APPROACH_BLOCKED.value, e_goal_path=str(goal_path),
        e_obs_path=str(obs_path), policy_id="p1", alpha_l=0.6, validated=True,
        trigger_recheck_passed=True, regression_passed=True,
    )
    matches = lookup_validated_remedies(
        query_failure_mode=FailureMode.APPROACH_BLOCKED,
        query_e_goal=goal, query_e_obs=obs, records=[record],
    )
    assert matches[0].alpha_candidates == (0.75, 0.9, 1.0)


def test_slow_loop_rejects_invalid_transitions_and_resumes(tmp_path):
    store = SlowLoopStore(tmp_path)
    job = store.create(active_policy_id="p0", input_hash="h")
    job = store.advance(
        job.job_id, expected_state=SlowLoopState.EXPANSION_TRIGGERED,
        next_state=SlowLoopState.LOOKUP_PENDING, input_hash="h", output_hash="o",
    )
    assert store.current(job.job_id).state is SlowLoopState.LOOKUP_PENDING
    assert store.resumable_jobs()[0].job_id == job.job_id
    annotated = store.annotate(
        job.job_id,
        expected_state=SlowLoopState.LOOKUP_PENDING,
        metadata={"external_artifact": "digest"},
        output_hash="annotated",
    )
    assert annotated.metadata["external_artifact"] == "digest"
    assert store.annotate(
        job.job_id,
        expected_state=SlowLoopState.LOOKUP_PENDING,
        metadata={"external_artifact": "digest"},
    ) == annotated
    with pytest.raises(ValueError, match="immutable"):
        store.annotate(
            job.job_id,
            expected_state=SlowLoopState.LOOKUP_PENDING,
            metadata={"external_artifact": "changed"},
        )
    with pytest.raises(ValueError):
        store.advance(
            job.job_id, expected_state=SlowLoopState.LOOKUP_PENDING,
            next_state=SlowLoopState.DEPLOYED, input_hash="h", output_hash="x",
        )


def test_slow_worker_consumes_gate_and_atomically_deploys_fixed_budget(tmp_path):
    manifest = {
        "schema_version": "joint-eval-manifest-v1",
        "manifest_sha256": "manifest",
        "tasks": [
            {
                "suite": "libero_spatial",
                "task_id": "task",
                "perturbation_variant": "use_object",
                "benchmark": "LIBERO-PRO",
                "runtime_suite": "libero_spatial_object",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    parent_checkpoint = tmp_path / "parent"
    winner_checkpoint = tmp_path / "winner"
    parent_checkpoint.mkdir()
    winner_checkpoint.mkdir()
    save_file({"weight": torch.zeros(2)}, str(parent_checkpoint / "model.safetensors"))
    save_file({"weight": torch.ones(2)}, str(winner_checkpoint / "model.safetensors"))
    winner_digest = checkpoint_digest(winner_checkpoint)
    report = {
        "schema_version": "raw-policy-gate-report-v1",
        "manifest_hash": "manifest",
        "parent": {"policy_id": "p0"},
        "trigger_recheck": {"p1": {"passed": True}},
        "decision": {
            "status": "POLICY_STAGED",
            "reason": "passed",
            "winner": {
                "policy_id": "p1",
                "checkpoint_path": str(winner_checkpoint),
                "checkpoint_digest": winner_digest,
                "alpha_l": 0.6,
            },
        },
    }
    report_path = tmp_path / "policy_gate.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    feature_path = tmp_path / "signature.npz"
    np.savez(
        feature_path,
        goal=np.ones(2048, dtype=np.float16),
        observation=np.ones(2048, dtype=np.float16),
    )
    counterfactual_path = tmp_path / "counterfactual.json"
    counterfactual_path.write_text(json.dumps({"complete": True}), encoding="utf-8")
    verifier_path = tmp_path / "verifier_result.json"
    verifier_path.write_text(
        json.dumps({"gate": {"passed": False, "reasons": ["too few contexts"]}}),
        encoding="utf-8",
    )

    registry = PolicyRegistry(tmp_path / "registry")
    registry.install_artifact("policy", "p0", parent_checkpoint)
    registry.promote(
        policy_id="p0",
        verifier_id=None,
        controller_mode="fixed_budget_4",
        manifest_hash="manifest",
        expected_revision=0,
    )
    store = SlowLoopStore(tmp_path / "slow")
    job = store.create(
        active_policy_id="p0",
        input_hash="input",
        metadata={
            "signature_id": "signature-id",
            "signature_feature_path": str(feature_path),
            "failure_mode": FailureMode.APPROACH_BLOCKED.value,
            "suite": "libero_spatial",
            "task_id": "task",
            "perturbation_variant": "use_object",
        },
    )
    path = [
        SlowLoopState.LOOKUP_PENDING,
        SlowLoopState.TICKET_READY,
        SlowLoopState.AWAITING_DEMOS,
        SlowLoopState.COLLECTING,
        SlowLoopState.CURATING,
        SlowLoopState.DATASET_READY,
        SlowLoopState.TRAINING,
        SlowLoopState.DELTA_READY,
        SlowLoopState.ALPHA_SELECTING,
        SlowLoopState.RAW_REGRESSION,
    ]
    for next_state in path:
        current = store.current(job.job_id)
        store.advance(
            job.job_id,
            expected_state=current.state,
            next_state=next_state,
            input_hash=current.input_hash,
            output_hash=next_state.value,
            metadata=(
                {"policy_gate_report_path": str(report_path)}
                if next_state is SlowLoopState.RAW_REGRESSION
                else {}
            ),
        )
    worker = SlowLoopWorker(
        store=store,
        registry=registry,
        incidents=IncidentMemory(tmp_path / "incidents"),
        protocol_manifest=manifest_path,
        ticket_root=tmp_path / "tickets",
        work_root=tmp_path / "work",
    )
    assert worker.step(job.job_id).state is SlowLoopState.TRIGGER_RECHECK
    assert worker.step(job.job_id).state is SlowLoopState.POLICY_STAGED
    assert worker.step(job.job_id).state is SlowLoopState.NEW_POLICY_COUNTERFACTUAL
    store.annotate(
        job.job_id,
        expected_state=SlowLoopState.NEW_POLICY_COUNTERFACTUAL,
        metadata={"new_policy_counterfactual_manifest_path": str(counterfactual_path)},
    )
    assert worker.step(job.job_id).state is SlowLoopState.VERIFIER_TRAINING
    store.annotate(
        job.job_id,
        expected_state=SlowLoopState.VERIFIER_TRAINING,
        metadata={"verifier_result_path": str(verifier_path)},
    )
    assert worker.step(job.job_id).state is SlowLoopState.READY_FIXED_BUDGET
    deployed = worker.step(job.job_id)
    assert deployed.state is SlowLoopState.DEPLOYED
    assert registry.active().policy_id == "p1"
    assert registry.active().controller_mode == "fixed_budget_4"
    signature = next(IncidentMemory(tmp_path / "incidents").signatures.iter_valid())
    assert signature["policy_id"] == "p1" and signature["validated"]


def test_ticket_planner_uses_current_frozen_text_model_and_strict_payload():
    calls = []

    class Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "capability_gap": "drawer handle approach is unreliable",
                        "coverage_axes": [
                            {
                                "axis": "handle_approach_side",
                                "value": "centered",
                                "quota": 15,
                            }
                        ],
                        "must_demonstrate": ["grasp then pull the top drawer"],
                        "must_avoid": ["contacting the drawer face"],
                    }
                ),
                usage_metadata=None,
            )

    planner = TicketCollectionPlanner(
        client=SimpleNamespace(models=Models()),
        max_retries=0,
    )
    collection, provenance = planner.plan(
        task_instruction="open the top drawer",
        failure_mode="UNKNOWN",
        required_trajectory_pattern="grasp and pull the handle",
        semantic_failure_types=(),
    )

    assert (
        provenance["model"]
        == TICKET_PLANNER_MODEL
        == "gemini-robotics-er-2-preview"
    )
    assert calls[0]["model"] == TICKET_PLANNER_MODEL
    assert collection.coverage_axes[0].axis == "handle_approach_side"


def test_ticket_planner_rejects_unfrozen_model():
    with pytest.raises(ValueError, match="frozen to gemini-robotics-er-2-preview"):
        TicketCollectionPlanner(model="gemini-2.5-flash", client=object())


def test_ticket_planner_rejects_coverage_that_cannot_fill_demo_queue():
    class Models:
        def generate_content(self, **kwargs):
            del kwargs
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "capability_gap": "drawer pull is unreliable",
                        "coverage_axes": [
                            {"axis": "handle_type", "value": "bar", "quota": 5},
                            {"axis": "handle_type", "value": "knob", "quota": 5},
                        ],
                        "must_demonstrate": ["grasp and pull"],
                        "must_avoid": ["collision"],
                    }
                ),
                usage_metadata=None,
            )

    planner = TicketCollectionPlanner(
        client=SimpleNamespace(models=Models()),
        max_retries=0,
    )
    with pytest.raises(RuntimeError, match="quota total must equal target demos"):
        planner.plan(
            task_instruction="open the drawer",
            failure_mode="UNKNOWN",
            required_trajectory_pattern="pull outwards",
            semantic_failure_types=(),
        )


def test_slow_loop_ticket_reissue_is_append_only_and_requires_zero_demos(tmp_path):
    store = SlowLoopStore(tmp_path / "slow")
    job = store.create(active_policy_id="p0", input_hash="input")
    for state in (
        SlowLoopState.LOOKUP_PENDING,
        SlowLoopState.TICKET_READY,
        SlowLoopState.AWAITING_DEMOS,
    ):
        current = store.current(job.job_id)
        job = store.advance(
            job.job_id,
            expected_state=current.state,
            next_state=state,
            input_hash=current.input_hash,
            output_hash=state.value,
            ticket_id="ticket-old" if state is SlowLoopState.AWAITING_DEMOS else None,
        )

    with pytest.raises(ValueError, match="proof that zero demos were collected"):
        store.advance(
            job.job_id,
            expected_state=SlowLoopState.AWAITING_DEMOS,
            next_state=SlowLoopState.TICKET_READY,
            input_hash=job.input_hash,
            output_hash="invalid-correction",
            metadata={
                "superseded_ticket_id": "ticket-old",
                "ticket_reissue_reason": "invalid coverage",
                "collected_demo_count": 1,
            },
        )

    corrected = store.advance(
        job.job_id,
        expected_state=SlowLoopState.AWAITING_DEMOS,
        next_state=SlowLoopState.TICKET_READY,
        input_hash=job.input_hash,
        output_hash="valid-correction",
        metadata={
            "superseded_ticket_id": "ticket-old",
            "ticket_reissue_reason": "invalid coverage",
            "collected_demo_count": 0,
        },
    )
    reissued = store.advance(
        job.job_id,
        expected_state=SlowLoopState.TICKET_READY,
        next_state=SlowLoopState.AWAITING_DEMOS,
        input_hash=job.input_hash,
        output_hash="new-ticket",
        ticket_id="ticket-new",
    )

    assert corrected.ticket_id == "ticket-old"
    assert reissued.ticket_id == "ticket-new"
    assert reissued.metadata["ticket_reissued_from"] == "ticket-old"


def test_slow_worker_closes_lookup_and_code_owned_ticket_path(tmp_path):
    manifest = {
        "schema_version": "joint-eval-manifest-v1",
        "manifest_sha256": "manifest",
        "tasks": [
            {
                "suite": "libero_spatial",
                "task_id": "task-1",
                "perturbation_variant": "base",
                "splits": {
                    "demo_online_pool": [str(index) for index in range(10)],
                    "policy_regression": [str(index) for index in range(10, 16)],
                },
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    feature_id = "f" * 64
    feature_path = tmp_path / f"{feature_id}.npz"
    np.savez(
        feature_path,
        goal=np.ones(2048, dtype=np.float16),
        observation=np.ones(2048, dtype=np.float16),
    )

    class TicketPlanner:
        def plan(self, **kwargs):
            return (
                CollectionSpec(
                    capability_gap="blocked approach",
                    coverage_axes=[CoverageCell(axis="approach_side", value="left", quota=15)],
                    must_demonstrate=["clear obstacle then grasp"],
                    must_avoid=["contact obstacle"],
                ),
                {"model": "stub", "request_sha256": "a" * 64},
            )

    store = SlowLoopStore(tmp_path / "slow")
    registry = PolicyRegistry(tmp_path / "registry")
    incidents = IncidentMemory(tmp_path / "incidents")
    job = store.create(
        active_policy_id="p0",
        input_hash="input",
        metadata={
            "signature_id": "signature-1",
            "signature_feature_id": feature_id,
            "signature_feature_path": str(feature_path),
            "snapshot_id": "snapshot-1",
            "failure_mode": FailureMode.APPROACH_BLOCKED.value,
            "task_instruction": "pick the object",
            "required_trajectory_pattern": "go around obstacle",
            "semantic_failure_types": ["blocked"],
            "suite": "libero_spatial",
            "task_id": "task-1",
            "perturbation_variant": "base",
        },
    )
    worker = SlowLoopWorker(
        store=store,
        registry=registry,
        incidents=incidents,
        protocol_manifest=manifest_path,
        ticket_root=tmp_path / "tickets",
        work_root=tmp_path / "work",
        ticket_planner=TicketPlanner(),
    )
    result = worker.run_until_blocked(job.job_id)
    assert result.state is SlowLoopState.AWAITING_DEMOS
    assert result.ticket_id
    ticket = json.loads(Path(result.metadata["ticket_path"]).read_text())
    assert ticket["eval_split"] == "regression"
    assert set(ticket["init_state_ids"]).isdisjoint(ticket["eval_init_state_ids"])
    assert result.metadata["lookup_match_count"] == 0


def test_slow_worker_lookup_composes_reuse_grid_from_validated_delta(tmp_path):
    theta0 = tmp_path / "theta0"
    theta_ft = tmp_path / "theta_ft"
    theta0.mkdir()
    theta_ft.mkdir()
    values = {
        "model.paligemma_with_expert.paligemma.model.vision_tower.x": torch.ones(2),
        "model.paligemma_with_expert.paligemma.model.language_model.x": torch.ones(2),
        "model.action_in_proj.weight": torch.ones(2),
    }
    save_file(values, str(theta0 / "model.safetensors"))
    save_file({key: value + 0.5 for key, value in values.items()}, str(theta_ft / "model.safetensors"))
    delta = tmp_path / "delta"
    extract_full_delta(theta0, theta_ft, delta, parent_policy_id="p0")
    initial_grid = compose_expansion_candidates(
        theta0_checkpoint=theta0,
        parent_policy_id="p0",
        accepted_lineage=(),
        new_delta_id="delta-1",
        new_delta_path=delta,
        output_root=tmp_path / "initial-grid",
    )
    active_checkpoint = Path(initial_grid["candidates"][1]["checkpoint_path"])
    registry = PolicyRegistry(tmp_path / "registry")
    registry.initialize_base(
        checkpoint_path=str(theta0),
        digest=checkpoint_digest(theta0),
        metadata={},
    )
    registry.install_artifact("delta", "delta-1", delta)
    registry.install_artifact("policy", "active", active_checkpoint)
    registry.promote(
        policy_id="active",
        verifier_id=None,
        controller_mode="fixed_budget_4",
        manifest_hash="manifest",
        expected_revision=0,
    )
    tickets = tmp_path / "tickets"
    (tickets / "source-ticket").mkdir(parents=True)
    (tickets / "source-ticket" / "ticket.json").write_text("{}", encoding="utf-8")
    goal = np.ones(2048, dtype=np.float32)
    observation = np.ones(2048, dtype=np.float32)
    goal_path, obs_path = tmp_path / "goal.npy", tmp_path / "obs.npy"
    np.save(goal_path, goal)
    np.save(obs_path, observation)
    incidents = IncidentMemory(tmp_path / "incidents")
    incidents.record_signature(
        CapabilitySignatureRecord(
            signature_id="source-signature",
            suite="libero_spatial",
            task_id="task",
            perturbation_variant="base",
            failure_mode=FailureMode.APPROACH_BLOCKED.value,
            e_goal_path=str(goal_path),
            e_obs_path=str(obs_path),
            policy_id="active",
            alpha_l=0.4,
            validated=True,
            trigger_recheck_passed=True,
            regression_passed=True,
            delta_id="delta-1",
            ticket_id="source-ticket",
        )
    )
    feature_id = "f" * 64
    feature_path = tmp_path / f"{feature_id}.npz"
    np.savez(feature_path, goal=goal.astype(np.float16), observation=observation.astype(np.float16))
    manifest = {
        "schema_version": "joint-eval-manifest-v1",
        "manifest_sha256": "manifest",
        "tasks": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    store = SlowLoopStore(tmp_path / "slow")
    job = store.create(
        active_policy_id="active",
        input_hash="input",
        metadata={
            "signature_id": "query-signature",
            "signature_feature_id": feature_id,
            "signature_feature_path": str(feature_path),
            "failure_mode": FailureMode.APPROACH_BLOCKED.value,
        },
    )
    worker = SlowLoopWorker(
        store=store,
        registry=registry,
        incidents=incidents,
        protocol_manifest=manifest_path,
        ticket_root=tickets,
        work_root=tmp_path / "work",
    )
    assert worker.step(job.job_id).state is SlowLoopState.LOOKUP_PENDING
    assert worker.step(job.job_id).state is SlowLoopState.REUSE_EVALUATING
    result = worker.step(job.job_id)
    assert result.state is SlowLoopState.RAW_REGRESSION
    candidates = json.loads(Path(result.metadata["candidates_json_path"]).read_text())
    assert [item["alpha_l"] for item in candidates] == [0.55, 0.7, 0.9]
    assert result.metadata["reuse_source_delta_id"] == "delta-1"
    failed_gate = tmp_path / "failed-reuse-gate.json"
    failed_gate.write_text(
        json.dumps(
            {
                "schema_version": "raw-policy-gate-report-v1",
                "gate_kind": "REUSE",
                "manifest_hash": "manifest",
                "parent": {"policy_id": "active"},
                "decision": {"status": "NEEDS_MORE_DEMOS", "reason": "no improvement"},
            }
        ),
        encoding="utf-8",
    )
    store.annotate(
        job.job_id,
        expected_state=SlowLoopState.RAW_REGRESSION,
        metadata={"policy_gate_report_path": str(failed_gate)},
    )
    fallback = worker.step(job.job_id)
    assert fallback.state is SlowLoopState.TICKET_READY
    assert fallback.metadata["reuse_fallback_to_ticket"]


def test_joint_manifest_is_byte_stable_and_has_exact_formal_counts():
    tasks = [
        {
            "suite": f"libero_{index // 10}",
            "task_id": str(index),
            "task_index": index % 10,
            "perturbation_variant": "base",
            "init_state_ids": [str(state) for state in range(50)],
        }
        for index in range(40)
    ]
    first = generate_joint_manifest(
        tasks, dataset_hash="d", bddl_hash="b", init_state_manifest_hash="i", generator_git_sha="g"
    )
    second = generate_joint_manifest(
        tasks, dataset_hash="d", bddl_hash="b", init_state_manifest_hash="i", generator_git_sha="g"
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert sum(len(task["splits"]["policy_final_sealed"]) for task in first["tasks"]) == 500

    contexts = contexts_from_manifest(first, split="policy_alpha_selection")
    assert len(contexts) == 100
    assert len({context.episode_key for context in contexts}) == 100
    with pytest.raises(ValueError, match="cannot open final_sealed"):
        contexts_from_manifest(first, split="policy_final_sealed")


def test_raw_policy_evaluator_resumes_without_repeating_episodes(tmp_path):
    tasks = [
        {
            "suite": f"libero_{index // 10}",
            "task_id": str(index),
            "task_index": index % 10,
            "perturbation_variant": "base",
            "init_state_ids": [str(state) for state in range(50)],
        }
        for index in range(40)
    ]
    manifest = generate_joint_manifest(
        tasks,
        dataset_hash="d",
        bddl_hash="b",
        init_state_manifest_hash="i",
        generator_git_sha="g",
    )
    contexts = contexts_from_manifest(manifest, split="policy_alpha_selection")
    calls = []

    def execute(policy_id, checkpoint, context):
        calls.append((policy_id, context.episode_key))
        return RawEpisodeResult(success=int(context.init_state_id) % 2 == 0)

    evaluator = RawPolicyEvaluator(
        executor=execute,
        ledger_path=tmp_path / "episodes.jsonl",
        manifest_hash=manifest["manifest_sha256"],
        max_workers=4,
    )
    first = evaluator.evaluate(
        policy_id="candidate",
        checkpoint_path=tmp_path,
        checkpoint_digest="digest",
        contexts=contexts,
    )
    second = evaluator.evaluate(
        policy_id="candidate",
        checkpoint_path=tmp_path,
        checkpoint_digest="digest",
        contexts=contexts,
    )
    assert len(calls) == 100
    assert first.raw_vector == second.raw_vector
    assert first.episodes == 100 and len(first.per_task_sr) == 40
    with pytest.raises(ValueError, match="raw regression profile"):
        evaluator.evaluate(
            policy_id="bad-profile",
            checkpoint_path=tmp_path,
            checkpoint_digest="digest-2",
            contexts=contexts,
            raw_profile={
                "use_guidance": True,
                "mode_gate.enabled": False,
                "use_vlm_stage_recognition": False,
            },
        )


def test_raw_gate_and_adaptive_counterfactual_rules():
    scores = tuple(
        PolicyScore(f"p{index}", alpha, sr, {"t": sr})
        for index, (alpha, sr) in enumerate(zip((0.2, 0.4, 0.6, 0.8), (0.4, 0.6, 0.6, 0.5)))
    )
    assert [item.alpha_l for item in select_alpha_top2(scores)] == [0.4, 0.6]
    decision = raw_promotion_decision(
        parent_macro_sr=0.55,
        regression_scores=select_alpha_top2(scores),
        trigger_recheck_pass={"p1": False, "p2": True},
    )
    assert decision.winner.candidate_id == "p2"
    next_trials, interval = adaptive_counterfactual_target(successes=1, trials=16)
    assert next_trials in {16, 32}
    assert interval[0] <= interval[1]
    low, high = wilson_interval(0, 64)
    assert low == 0.0 and high == pytest.approx(0.0566, abs=5e-4)


def test_full_delta_compose_and_registry_cas(tmp_path):
    base = tmp_path / "base.safetensors"
    ft = tmp_path / "ft.safetensors"
    values = {
        "model.paligemma_with_expert.paligemma.model.vision_tower.x": torch.ones(2),
        "model.paligemma_with_expert.paligemma.model.language_model.x": torch.ones(2) * 2,
        "model.action_in_proj.weight": torch.ones(2) * 3,
    }
    save_file(values, base)
    save_file({key: value + 0.5 for key, value in values.items()}, ft)
    delta = tmp_path / "delta"
    extract_full_delta(base, ft, delta, parent_policy_id="p0", max_shard_bytes=64)
    merged = tmp_path / "merged"
    compose_policy(
        base,
        [(delta, {"vision": 1, "language": 1, "action": 1})],
        merged,
        max_shard_bytes=64,
    )
    assert partition_counts(merged) == {"vision": 1, "language": 1, "action": 1}
    index = json.loads((merged / "model.safetensors.index.json").read_text())
    for key, shard in index["weight_map"].items():
        with safe_open(merged / shard, framework="pt", device="cpu") as handle:
            torch.testing.assert_close(handle.get_tensor(key), values[key] + 0.5)

    registry = PolicyRegistry(tmp_path / "registry")
    registry.initialize_base(checkpoint_path=str(base), digest="a" * 64, metadata={})
    registry.install_artifact("policy", "p1", merged)
    active = registry.promote(
        policy_id="p1", verifier_id=None, controller_mode="fixed_budget_4",
        manifest_hash="m", expected_revision=0,
    )
    assert active.deployment_revision == 1
    with pytest.raises(RuntimeError):
        registry.promote(
            policy_id="p1", verifier_id=None, controller_mode="fixed_budget_4",
            manifest_hash="m", expected_revision=0,
        )


def test_full_delta_proof_allows_only_verified_theta_ft_cleanup(tmp_path):
    parent = tmp_path / "parent"
    theta_ft = tmp_path / "theta_ft"
    parent.mkdir()
    theta_ft.mkdir()
    values = {
        "model.paligemma_with_expert.paligemma.model.vision_tower.x": torch.ones(
            4, dtype=torch.bfloat16
        ),
        "model.paligemma_with_expert.paligemma.model.language_model.x": torch.ones(
            4, dtype=torch.bfloat16
        ),
        "model.action_in_proj.weight": torch.ones(4, dtype=torch.bfloat16),
    }
    save_file(values, str(parent / "model.safetensors"))
    save_file(
        {key: value + torch.tensor(0.25, dtype=value.dtype) for key, value in values.items()},
        str(theta_ft / "model.safetensors"),
    )
    delta = tmp_path / "delta"
    extract_full_delta(parent, theta_ft, delta, parent_policy_id="p0", max_shard_bytes=64)
    proof = verify_full_delta_reconstruction(parent, delta, theta_ft)
    assert proof["passed"] and proof["floating_tensors_checked"] == 3
    cleanup = delete_verified_theta_ft(
        theta_ft,
        parent_checkpoint=parent,
        delta_checkpoint=delta,
    )
    assert not theta_ft.exists()
    assert cleanup["recoverable_from_parent_and_delta"]
    with pytest.raises(ValueError, match="overlaps"):
        delete_verified_theta_ft(
            parent,
            parent_checkpoint=parent,
            delta_checkpoint=delta,
        )


def test_expansion_and_reuse_candidate_composition_preserves_full_lineage(tmp_path):
    theta0 = tmp_path / "theta0"
    ft1 = tmp_path / "ft1"
    ft2 = tmp_path / "ft2"
    theta0.mkdir()
    ft1.mkdir()
    ft2.mkdir()
    values = {
        "model.paligemma_with_expert.paligemma.model.vision_tower.x": torch.ones(2),
        "model.paligemma_with_expert.paligemma.model.language_model.x": torch.ones(2) * 2,
        "model.action_in_proj.weight": torch.ones(2) * 3,
    }
    save_file(values, str(theta0 / "model.safetensors"))
    save_file({key: value + 0.5 for key, value in values.items()}, str(ft1 / "model.safetensors"))
    save_file({key: value + 1.0 for key, value in values.items()}, str(ft2 / "model.safetensors"))
    delta1, delta2 = tmp_path / "delta1", tmp_path / "delta2"
    extract_full_delta(theta0, ft1, delta1, parent_policy_id="p0")
    extract_full_delta(theta0, ft2, delta2, parent_policy_id="p0")
    lineage = [DeltaLineageEntry("d1", str(delta1), alpha_l=0.4)]
    expansion = compose_expansion_candidates(
        theta0_checkpoint=theta0,
        parent_policy_id="p1",
        accepted_lineage=lineage,
        new_delta_id="d2",
        new_delta_path=delta2,
        output_root=tmp_path / "expansion",
    )
    assert [item["alpha_l"] for item in expansion["candidates"]] == [0.2, 0.4, 0.6, 0.8]
    candidate = Path(expansion["candidates"][0]["checkpoint_path"])
    index = json.loads((candidate / "model.safetensors.index.json").read_text())
    language_key = "model.paligemma_with_expert.paligemma.model.language_model.x"
    with safe_open(candidate / index["weight_map"][language_key], framework="pt", device="cpu") as handle:
        torch.testing.assert_close(handle.get_tensor(language_key), values[language_key] + 0.4)

    reuse = compose_reuse_candidates(
        theta0_checkpoint=theta0,
        parent_policy_id="p1",
        accepted_lineage=lineage,
        target_delta_id="d1",
        output_root=tmp_path / "reuse",
    )
    resumed = compose_reuse_candidates(
        theta0_checkpoint=theta0,
        parent_policy_id="p1",
        accepted_lineage=lineage,
        target_delta_id="d1",
        output_root=tmp_path / "reuse",
    )
    assert reuse == resumed
    assert [item["alpha_l"] for item in reuse["candidates"]] == [0.55, 0.7, 0.9]


def test_checkpoint_math_ignores_and_preserves_processor_safetensors(tmp_path):
    base = tmp_path / "base"
    ft = tmp_path / "ft"
    base.mkdir()
    ft.mkdir()
    weights = {"model.action_in_proj.weight": torch.ones(2)}
    save_file(weights, base / "model.safetensors")
    save_file({"action.count": torch.tensor([3.0])}, base / "policy_preprocessor.safetensors")
    save_file({key: value + 1 for key, value in weights.items()}, ft / "model.safetensors")
    save_file({"action.count": torch.tensor([3.0])}, ft / "policy_preprocessor.safetensors")
    (base / "config.json").write_text("{}", encoding="utf-8")

    assert partition_counts(base) == {"vision": 0, "language": 0, "action": 1}
    delta = tmp_path / "delta"
    extract_full_delta(base, ft, delta, parent_policy_id="p0", max_shard_bytes=64)
    merged = tmp_path / "merged"
    compose_policy(
        base,
        [(delta, {"vision": 1.0, "language": 1.0, "action": 1.0})],
        merged,
        max_shard_bytes=64,
    )
    assert (merged / "policy_preprocessor.safetensors").is_file()
    with safe_open(
        merged / "policy_preprocessor.safetensors", framework="pt", device="cpu"
    ) as handle:
        assert handle.get_tensor("action.count").item() == 3.0


class _SnapshotAdapter:
    def __init__(self):
        self.state = {"qpos": np.array([1.0]), "qvel": np.array([2.0])}
        self.image = np.zeros((4, 4, 3), dtype=np.uint8)
        self.cache = torch.tensor([4.0])

    def capture_simulator_state(self):
        return {key: value.copy() for key, value in self.state.items()}

    def restore_simulator_state(self, value):
        self.state = {key: np.asarray(item).copy() for key, item in value.items()}

    def get_vlm_image(self):
        return self.image

    def capture_runtime_state(self):
        return {"cache": self.cache.clone()}

    def restore_runtime_state(self, value):
        self.cache = value["cache"].clone()


class _SnapshotPolicy:
    def __init__(self):
        self.value = torch.tensor([3.0])

    def capture_runtime_state(self):
        return {"value": self.value}

    def restore_runtime_state(self, value):
        self.value = value["value"]


class _SnapshotComponent(_SnapshotPolicy):
    pass


def test_mujoco_model_state_roundtrip_and_legacy_rejection():
    from core.env_adapters.libero_adapter import (
        _capture_mujoco_model_state,
        _restore_mujoco_model_state,
    )

    model = SimpleNamespace(
        body_pos=np.asarray([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]),
        body_quat=np.asarray([[1.0, 0.0, 0.0, 0.0]] * 2),
        geom_pos=np.asarray([[0.7, 0.8, 0.9]]),
        cam_fovy=np.asarray([45.0]),
    )
    expected = {
        "body_pos": model.body_pos.copy(),
        "body_quat": model.body_quat.copy(),
        "geom_pos": model.geom_pos.copy(),
        "cam_fovy": model.cam_fovy.copy(),
    }
    state = {}
    _capture_mujoco_model_state(model, state)

    model.body_pos[:] = -1.0
    model.body_quat[:] = -1.0
    model.geom_pos[:] = -1.0
    model.cam_fovy[:] = -1.0
    _restore_mujoco_model_state(model, state)
    for name, value in expected.items():
        np.testing.assert_array_equal(getattr(model, name), value)

    with pytest.raises(ValueError, match="predates MuJoCo model-state"):
        _restore_mujoco_model_state(model, {})
    mismatched = dict(state)
    mismatched["model__body_pos"] = np.zeros((1, 3), dtype=np.float64)
    with pytest.raises(ValueError, match="field mismatch for body_pos"):
        _restore_mujoco_model_state(model, mismatched)


def test_snapshot_roundtrip_restores_simulator_policy_and_rgb(tmp_path):
    adapter, policy = _SnapshotAdapter(), _SnapshotPolicy()
    component = _SnapshotComponent()
    store = DecisionSnapshotStore(tmp_path)
    snapshot = store.capture(
        adapter=adapter, policy=policy, policy_id="p0", controller_state={"retry": 1},
        provenance={"commit": "x"}, observation_image=adapter.image,
        stateful_components={"tracker": component},
    )
    adapter.state["qpos"][0] = 9
    adapter.cache = torch.tensor([11.0])
    policy.value = torch.tensor([8.0])
    component.value = torch.tensor([10.0])
    result = store.restore(
        snapshot.snapshot_id,
        adapter=adapter,
        policy=policy,
        stateful_components={"tracker": component},
    )
    assert adapter.state["qpos"][0] == 1
    assert adapter.cache.item() == 4
    assert policy.value.item() == 3
    assert component.value.item() == 3
    assert result["rgb_mean_absolute_error"] == 0


def test_demo_writer_keeps_t_plus_one_states_and_undo(tmp_path):
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    frame = DemoFrame(image, image, np.zeros(8), np.zeros(4))
    writer = DemoWriter(
        tmp_path / "demo.h5", task="pick", ticket_id="t", operator="op",
        init_state_id="1", snapshot_id=None, hashes={"code": "x"}, coverage_cell="left",
    )
    writer.start(frame, ee_position=np.zeros(3))
    writer.append(np.zeros(7), frame, reward=0, done=False, success=False, ee_position=np.zeros(3))
    writer.undo()
    writer.append(np.zeros(7), frame, reward=1, done=True, success=True, ee_position=np.ones(3))
    writer.set_explicit_success(True)
    path = writer.save()
    with h5py.File(path, "r") as handle:
        assert handle["simulator_state"].shape[0] == handle["action"].shape[0] + 1
        assert bool(handle.attrs["explicit_success"])


def test_teleop_save_requires_fifty_steps_and_explicit_success(tmp_path):
    from mode_gate.teleop import TeleopSession

    class Writer:
        def __init__(self):
            self.actions = [np.zeros(7)] * 49
            self.successes = [True] * 49
            self.explicit_success = False
            self.metadata = {
                "init_state_id": "29",
                "coverage_cell": "approach=left",
            }
            self.saved = 0

        def save(self):
            self.saved += 1
            return tmp_path / "demo.hdf5"

        def set_explicit_success(self, value):
            self.explicit_success = bool(value)

    image = np.zeros((256, 256, 3), dtype=np.uint8)
    writer = Writer()
    session = TeleopSession(
        adapter=object(),
        writer=writer,
        observation_provider=lambda: (image, image, np.zeros(8), np.zeros(3)),
        task_success_provider=lambda: True,
    )

    assert session.handle("n")["message"] == "need_at_least_50_steps"
    writer.actions.append(np.zeros(7))
    writer.successes.append(True)
    assert session.handle("n")["message"] == "mark_success_before_save"
    assert session.handle("success")["message"] == "success_marked"
    assert session.handle("n")["message"] == "saved_queue_complete"
    assert writer.saved == 1


def test_teleop_failed_validation_keeps_one_idempotent_saved_file(tmp_path):
    from mode_gate.teleop import TeleopSession

    class Writer:
        def __init__(self):
            self.actions = [np.zeros(7)] * 50
            self.successes = [True] * 50
            self.explicit_success = False
            self.metadata = {
                "init_state_id": "29",
                "coverage_cell": "approach=left",
            }
            self.saved = 0

        def save(self):
            self.saved += 1
            return tmp_path / "demo.hdf5"

        def set_explicit_success(self, value):
            self.explicit_success = bool(value)

    attempts = 0

    def validate_once(_path):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("controller state mismatch")
        return None

    image = np.zeros((256, 256, 3), dtype=np.uint8)
    writer = Writer()
    session = TeleopSession(
        adapter=object(),
        writer=writer,
        observation_provider=lambda: (image, image, np.zeros(8), np.zeros(3)),
        task_success_provider=lambda: True,
        on_save=validate_once,
    )
    assert session.handle("success")["message"] == "success_marked"
    failed = session.handle("n")
    assert failed["message"] == "save_validation_failed"
    assert "controller state mismatch" in failed["error_detail"]
    assert failed["pending_saved_path"].endswith("demo.hdf5")
    assert writer.saved == 1
    assert session.handle("n")["message"] == "saved_queue_complete"
    assert writer.saved == 1


def test_teleop_timeout_is_invalid_and_full_reset_rebuilds_episode(tmp_path):
    from mode_gate.data_pipeline import DemoFrame, DemoWriter
    from mode_gate.teleop import TeleopSession

    image = np.zeros((256, 256, 3), dtype=np.uint8)
    frame = DemoFrame(image, image, np.zeros(8), np.zeros(4))

    class Adapter:
        device = "cpu"

        def __init__(self):
            self.value = 0
            self.last_action = None

        def capture_simulator_state(self):
            return {
                "qpos": np.asarray([self.value], dtype=np.float64),
                "qvel": np.zeros(1),
                "flattened_sim_state": np.asarray([self.value], dtype=np.float64),
            }

        def restore_simulator_state(self, state):
            self.value = int(state["qpos"][0])

        def step(self, action):
            self.last_action = action.detach().cpu().numpy()
            self.value += 1
            return {}, 0.0, False, True, {"success": False}

    adapter = Adapter()

    def new_writer(suffix):
        return DemoWriter(
            tmp_path / f"demo-{suffix}.hdf5",
            task="task",
            ticket_id="ticket",
            operator="operator",
            init_state_id="29",
            snapshot_id=None,
            hashes={"manifest": "m"},
            coverage_cell="direction=from the top-left",
        )

    resets = 0

    def reset_current():
        nonlocal resets
        resets += 1
        adapter.value = 0
        return new_writer(resets)

    session = TeleopSession(
        adapter=adapter,
        writer=new_writer("initial"),
        observation_provider=lambda: (image, image, np.zeros(8), np.zeros(3)),
        reset_current=reset_current,
        task_success_provider=lambda: False,
        max_steps=1,
    )
    session.initialize()
    terminal = session.handle("scale:4:w")
    assert terminal["message"] == "episode_timeout_reset_required"
    assert adapter.last_action[0] == pytest.approx(1.0)
    assert terminal["terminal_state"] == "invalid"
    assert session.handle("success")["message"] == "invalid_episode_reset_required"
    assert session.handle("n")["message"] == "invalid_episode_reset_required"
    assert session.handle("w")["steps"] == 1
    reset = session.handle("r")
    assert reset["message"] == "reset"
    assert reset["steps"] == 0
    assert reset["terminal_state"] is None
    assert resets == 1


def test_teleop_prefers_lightweight_step_path(tmp_path):
    from mode_gate.data_pipeline import DemoFrame, DemoWriter
    from mode_gate.teleop import TeleopSession

    image = np.zeros((256, 256, 3), dtype=np.uint8)

    class Adapter:
        device = "cpu"

        def __init__(self):
            self.value = 0.0
            self.lightweight_calls = 0

        def capture_simulator_state(self):
            return {"flattened_sim_state": np.asarray([self.value])}

        def step(self, _action):
            raise AssertionError("policy step must not be used by teleop")

        def step_teleop(self, _action):
            self.lightweight_calls += 1
            self.value += 1.0
            return {}, 0.0, False, False, {"success": False}

    writer = DemoWriter(
        tmp_path / "lightweight.hdf5",
        task="task",
        ticket_id="ticket",
        operator="operator",
        init_state_id="29",
        snapshot_id=None,
        hashes={"manifest": "m"},
        coverage_cell="direction=left",
    )
    adapter = Adapter()
    session = TeleopSession(
        adapter=adapter,
        writer=writer,
        observation_provider=lambda: (image, image, np.zeros(8), np.zeros(3)),
        task_success_provider=lambda: False,
    )
    session.initialize()
    assert session.handle("w")["message"] == "stepped"
    assert adapter.lightweight_calls == 1
    assert len(writer.actions) == 1


def test_teleop_blocks_fifth_gripper_toggle_before_recording(tmp_path):
    from mode_gate.data_pipeline import DemoWriter
    from mode_gate.teleop import TeleopSession

    image = np.zeros((256, 256, 3), dtype=np.uint8)

    class Adapter:
        device = "cpu"

        def __init__(self):
            self.value = 0.0

        def capture_simulator_state(self):
            return {"flattened_sim_state": np.asarray([self.value])}

        def step_teleop(self, _action):
            self.value += 1.0
            return {}, 0.0, False, False, {"success": False}

    writer = DemoWriter(
        tmp_path / "toggle-limit.hdf5",
        task="task",
        ticket_id="ticket",
        operator="operator",
        init_state_id="29",
        snapshot_id=None,
        hashes={"manifest": "m"},
        coverage_cell="direction=left",
    )
    adapter = Adapter()
    session = TeleopSession(
        adapter=adapter,
        writer=writer,
        observation_provider=lambda: (image, image, np.zeros(8), np.zeros(3)),
        task_success_provider=lambda: False,
    )
    session.initialize()
    assert session.handle("w")["message"] == "stepped"
    for expected in range(1, 5):
        status = session.handle(" ")
        assert status["gripper_toggles"] == expected
    before = len(writer.actions)
    blocked = session.handle(" ")
    assert blocked["message"] == "gripper_toggle_limit_reached"
    assert blocked["gripper_toggles"] == 4
    assert len(writer.actions) == before


def test_teleop_cannot_mark_success_without_simulator_predicate(tmp_path):
    from mode_gate.data_pipeline import DemoFrame, DemoWriter
    from mode_gate.teleop import TeleopSession

    image = np.zeros((256, 256, 3), dtype=np.uint8)
    writer = DemoWriter(
        tmp_path / "demo.hdf5",
        task="task",
        ticket_id="ticket",
        operator="operator",
        init_state_id="29",
        snapshot_id=None,
        hashes={"manifest": "m"},
        coverage_cell="direction=from the top-left",
    )
    frame = DemoFrame(image, image, np.zeros(8), np.zeros(4))
    writer.start(frame, ee_position=np.zeros(3))
    writer.append(
        np.zeros(7), frame, reward=0.0, done=False, success=False,
        ee_position=np.zeros(3),
    )
    session = TeleopSession(
        adapter=object(),
        writer=writer,
        observation_provider=lambda: (image, image, np.zeros(8), np.zeros(3)),
        task_success_provider=lambda: False,
    )
    assert session.handle("success")["message"] == "simulator_has_not_confirmed_success"
    assert not writer.explicit_success


def test_teleop_websocket_parameter_is_resolved_to_fastapi_type(tmp_path):
    fastapi = pytest.importorskip("fastapi")
    from mode_gate.teleop import create_teleop_app

    class Session:
        def status(self, message):
            return {"message": message}

        def handle(self, key):
            return {"message": key}

    app = create_teleop_app(Session())
    route = next(route for route in app.routes if getattr(route, "path", None) == "/ws")
    assert route.endpoint.__annotations__["websocket"] is fastapi.WebSocket


def test_teleop_page_rotates_only_human_display() -> None:
    from mode_gate.teleop import _HTML

    assert ".camera img{width:100%;border:1px solid #555;transform:rotate(180deg)}" in _HTML
    assert "保存数据仍保持冻结的 LIBERO-PRO / LeRobot 图像语义" in _HTML
    assert "按住键盘连续移动" in _HTML
    assert "onkeyup" in _HTML
    assert 'data-speed="4"' in _HTML
    assert "刷新高清画面" in _HTML
    assert "pendingHq" in _HTML


def test_teleop_guidance_reuses_last_good_signal_on_transient_failure() -> None:
    from mode_gate.teleop import TeleopSession

    image = np.zeros((256, 256, 3), dtype=np.uint8)
    calls = 0

    def guidance(_session):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"stage_title": "第 2/4 阶段", "next_action": "接近黑色碗"}
        raise TypeError("transient signal")

    writer = SimpleNamespace(
        actions=[],
        successes=[],
        metadata={
            "init_state_id": "29",
            "coverage_cell": "direction=from the top-left",
        },
    )
    session = TeleopSession(
        adapter=object(),
        writer=writer,
        observation_provider=lambda: (image, image, np.zeros(8), np.zeros(3)),
        guidance_provider=guidance,
    )
    first = session.status("connected")
    second = session.status("ignored")
    assert first["guidance"]["stage_title"] == "第 2/4 阶段"
    assert "上一次可靠提示" in second["guidance"]["stage_title"]
    assert second["guidance"]["next_action"] == "接近黑色碗"
    assert second["guidance"]["stale"] is True


def test_teleop_server_guidance_provider_returns_operator_guidance() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "teleop_server.py"
    ).read_text(encoding="utf-8")
    body = source.split("    def guidance_provider", 1)[1].split(
        "    def reset_current", 1
    )[0]
    assert "return drawer_bowl_operator_guidance(" in body


def test_teleop_guidance_tracks_drawer_bowl_stages() -> None:
    from mode_gate.teleop import drawer_bowl_operator_guidance

    base = {
        "task_success": False,
        "drawer_open_fraction": 0.1,
        "ee_to_bowl_m": 0.3,
        "bowl_lift_m": 0.0,
        "bowl_to_drawer_m": 0.4,
    }
    stage_1 = drawer_bowl_operator_guidance(
        base,
        gripper_command=-1.0,
        coverage_hint="从左上方接近。",
    )
    assert stage_1["stage_index"] == 0
    assert "最上层" in stage_1["next_action"]

    stage_2 = drawer_bowl_operator_guidance(
        base | {"drawer_open_fraction": 0.8},
        gripper_command=-1.0,
        coverage_hint="从左上方接近。",
    )
    assert stage_2["stage_index"] == 1
    assert "黑色碗" in stage_2["next_action"]

    stage_3 = drawer_bowl_operator_guidance(
        base
        | {
            "drawer_open_fraction": 0.8,
            "bowl_lift_m": 0.04,
            "bowl_to_drawer_m": 0.3,
        },
        gripper_command=1.0,
        coverage_hint="从左上方接近。",
    )
    assert stage_3["stage_index"] == 2

    stage_4 = drawer_bowl_operator_guidance(
        base
        | {
            "drawer_open_fraction": 0.8,
            "bowl_lift_m": 0.04,
            "bowl_to_drawer_m": 0.1,
        },
        gripper_command=1.0,
        coverage_hint="从左上方接近。",
    )
    assert stage_4["stage_index"] == 3

    complete = drawer_bowl_operator_guidance(
        base | {"task_success": True},
        gripper_command=-1.0,
        coverage_hint="从左上方接近。",
    )
    assert complete["stage_index"] == 4
    assert complete["task_success"]


def test_teleop_status_reuses_last_camera_frame() -> None:
    from mode_gate.teleop import TeleopSession

    calls = 0
    image = np.zeros((256, 256, 3), dtype=np.uint8)

    def observation():
        nonlocal calls
        calls += 1
        return image, image, np.zeros(8), np.zeros(3)

    writer = SimpleNamespace(
        actions=[],
        metadata={"init_state_id": "29", "coverage_cell": "direction=from the top-left"},
    )
    session = TeleopSession(
        adapter=object(),
        writer=writer,
        observation_provider=observation,
        queue_position_provider=lambda: (1, 15),
    )
    first = session.status("connected")
    second = session.status("ignored")
    assert calls == 1
    assert first["queue_total"] == second["queue_total"] == 15
    assert "左上方" in first["coverage_hint"]


def test_teleop_separates_high_resolution_preview_from_training_frame(tmp_path):
    from mode_gate.data_pipeline import DemoWriter
    from mode_gate.teleop import TeleopSession

    training = np.zeros((256, 256, 3), dtype=np.uint8)
    preview = np.zeros((512, 512, 3), dtype=np.uint8)
    writer = DemoWriter(
        tmp_path / "preview.hdf5",
        task="task",
        ticket_id="ticket",
        operator="operator",
        init_state_id="29",
        snapshot_id=None,
        hashes={"manifest": "m"},
        coverage_cell="direction=from the top-left",
    )

    class Adapter:
        def capture_simulator_state(self):
            return {"flattened_sim_state": np.zeros(4)}

    session = TeleopSession(
        adapter=Adapter(),
        writer=writer,
        observation_provider=lambda: (
            training, training, np.zeros(8), np.zeros(3)
        ),
        preview_provider=lambda: (preview, preview),
    )
    session.initialize()
    assert writer.frames[0].image.shape == (256, 256, 3)
    assert session._last_image.shape == (512, 512, 3)
    assert "data:image/jpeg" in session.status("connected")["image"]


def test_teleop_step_and_render_stay_on_websocket_thread() -> None:
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import threading

    from mode_gate.teleop import create_teleop_app

    class Session:
        def __init__(self):
            self.status_thread = None
            self.handle_thread = None

        def status(self, message):
            current = threading.get_ident()
            if self.status_thread is None:
                self.status_thread = current
            return {"message": message}

        def handle(self, key):
            self.handle_thread = threading.get_ident()
            return {"message": key}

    session = Session()
    with TestClient(create_teleop_app(session)) as client:
        with client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["message"] == "connected"
            websocket.send_json({"key": "w"})
            assert websocket.receive_json()["message"] == "w"
    assert session.handle_thread == session.status_thread


def test_demo_replay_validator_persists_exact_state_error(tmp_path):
    output = tmp_path / "demo.hdf5"
    writer = DemoWriter(
        output,
        task="task",
        ticket_id="ticket",
        operator="operator",
        init_state_id="0",
        snapshot_id=None,
        hashes={"manifest": "m"},
        coverage_cell="cell",
    )

    def frame(state):
        return DemoFrame(
            image=np.zeros((256, 256, 3), dtype=np.uint8),
            image2=np.zeros((256, 256, 3), dtype=np.uint8),
            state=np.zeros(8, dtype=np.float32),
            simulator_state=np.asarray([state], dtype=np.float64),
        )

    writer.start(frame(0.0), ee_position=np.zeros(3))
    first_action = np.zeros(7, dtype=np.float32)
    first_action[0] = 1.0
    writer.append(
        first_action,
        frame(1.0),
        reward=0.0,
        done=False,
        success=False,
        ee_position=np.zeros(3),
    )
    second_action = np.zeros(7, dtype=np.float32)
    second_action[0] = 2.0
    writer.append(
        second_action,
        frame(3.0),
        reward=1.0,
        done=True,
        success=True,
        ee_position=np.zeros(3),
    )
    writer.save()

    class ReplayAdapter:
        device = "cpu"

        def restore_flattened_simulator_state(self, value):
            self.value = float(value[0])

        def step(self, action):
            self.value += float(action[0])
            return None, 0.0, False, False, {}

        def capture_simulator_state(self):
            return {"flattened_sim_state": np.asarray([self.value])}

    assert validate_demo_replay(output, adapter=ReplayAdapter()) == 0.0
    with h5py.File(output, "r") as handle:
        assert bool(handle.attrs["replay_validated"])
        assert handle.attrs["replay_max_state_error"] == 0.0


def test_demo_replay_prepare_resets_controller_runtime(tmp_path):
    output = tmp_path / "demo.hdf5"
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    frame_0 = DemoFrame(image, image, np.zeros(8), np.asarray([0.0]))
    frame_1 = DemoFrame(image, image, np.zeros(8), np.asarray([1.0]))
    writer = DemoWriter(
        output,
        task="task",
        ticket_id="ticket",
        operator="operator",
        init_state_id="29",
        snapshot_id=None,
        hashes={"manifest": "m"},
        coverage_cell="direction=left",
    )
    writer.start(frame_0, ee_position=np.zeros(3))
    action = np.zeros(7, dtype=np.float32)
    action[0] = 1.0
    writer.append(
        action,
        frame_1,
        reward=1.0,
        done=True,
        success=True,
        ee_position=np.zeros(3),
    )
    writer.set_explicit_success(True)
    writer.save()

    class RuntimeSensitiveAdapter:
        device = "cpu"

        def __init__(self):
            self.value = 0.0
            self.controller_offset = 10.0

        def restore_flattened_simulator_state(self, value):
            self.value = float(value[0])

        def step(self, action):
            self.value += float(action[0]) + self.controller_offset
            return None, 0.0, False, False, {}

        def capture_simulator_state(self):
            return {"flattened_sim_state": np.asarray([self.value])}

    adapter = RuntimeSensitiveAdapter()
    assert validate_demo_replay(
        output,
        adapter=adapter,
        prepare_replay=lambda: setattr(adapter, "controller_offset", 0.0),
    ) == 0.0
    with h5py.File(output, "r") as handle:
        assert handle.attrs["replay_validation_version"] == "controller-reset-v1"
        assert int(handle.attrs["replay_max_state_error_index"]) == -1


def test_demo_replay_reassessment_uses_physical_component_tolerances(tmp_path):
    output = tmp_path / "demo.hdf5"
    with h5py.File(output, "w") as handle:
        handle.attrs["replay_validation_version"] = "controller-reset-v1"
        handle.attrs["replay_max_state_error"] = 2.9e-3
        handle.attrs["replay_max_qpos_error"] = 3.1e-5
        handle.attrs["replay_max_qvel_error"] = 2.9e-3
        handle.attrs["replay_success_matches"] = True
        handle.attrs["replay_validated"] = False
    assert reassess_demo_replay(
        output,
        tolerance=5e-3,
        position_tolerance=1e-4,
        velocity_tolerance=5e-3,
    )
    with h5py.File(output, "r") as handle:
        assert bool(handle.attrs["replay_validated"])
        assert handle.attrs["replay_acceptance_version"] == "physical-state-v1"


def test_teleop_queue_resumes_only_contiguous_committed_demos(tmp_path):
    from scripts.teleop_server import _commit_collected_demo, _next_queue_index

    queue = [
        {"init_state_id": "29", "coverage_cell": "direction=left"},
        {"init_state_id": "29", "coverage_cell": "direction=right"},
    ]

    def create(index, *, valid, cell):
        path = tmp_path / f"demo-{index:03d}-abcd1234.hdf5"
        with h5py.File(path, "w") as handle:
            handle.create_dataset("action", data=np.zeros((50, 7)))
            handle.create_dataset("simulator_state", data=np.zeros((51, 2)))
            handle.create_dataset("observation/state", data=np.zeros((51, 8)))
            handle.attrs["init_state_id"] = "29"
            handle.attrs["coverage_cell"] = cell
            handle.attrs["explicit_success"] = True
            handle.attrs["simulator_success"] = True
            handle.attrs["replay_validated"] = valid
        return path

    pending = create(0, valid=False, cell="direction=left")
    assert _next_queue_index(tmp_path, queue) == 0
    _commit_collected_demo(pending)
    assert _next_queue_index(tmp_path, queue) == 1


def test_teleop_refill_queue_contains_only_missing_coverage(tmp_path):
    from scripts.teleop_server import _queue

    ticket = SimpleNamespace(
        collection=SimpleNamespace(
            coverage_axes=(
                SimpleNamespace(axis="direction", value="left", quota=2),
                SimpleNamespace(axis="direction", value="right", quota=2),
            )
        ),
        init_state_ids=("10", "11"),
        demos_per_state=2,
        target_demos=4,
    )
    (tmp_path / "raw").mkdir()
    (tmp_path / "rejected").mkdir()
    for index in range(4):
        directory = "raw" if index == 2 else "rejected"
        (tmp_path / directory / f"demo-{index:03d}-abcd1234.hdf5").touch()
    (tmp_path / "curation.json").write_text(
        json.dumps(
            {
                "needs_more_demos": True,
                "coverage": {
                    "direction=left": {"accepted": 0, "quota": 2},
                    "direction=right": {"accepted": 1, "quota": 2},
                },
            }
        ),
        encoding="utf-8",
    )
    queue = _queue(ticket, source="ticket", ticket_root=tmp_path)
    assert [entry["coverage_cell"] for entry in queue] == [
        "direction=left",
        "direction=left",
        "direction=right",
    ]
    assert [entry["init_state_id"] for entry in queue] == ["10", "10", "11"]
    assert [entry["collection_index"] for entry in queue] == [4, 5, 6]


def test_ticket_curation_is_coverage_aware_exported_and_resumable(tmp_path, monkeypatch):
    ticket_root = tmp_path / "ticket"
    (ticket_root / "raw").mkdir(parents=True)
    for name in ("curated", "rejected", "exports", "attempts"):
        (ticket_root / name).mkdir()
    ticket = {
        "schema_version": "expansion-ticket-v2",
        "ticket_id": "ticket-1",
        "collection": {
            "coverage_axes": [
                {"axis": "approach_side", "value": "left", "quota": 3}
            ]
        },
    }
    ticket_path = ticket_root / "ticket.json"
    ticket_path.write_text(json.dumps(ticket), encoding="utf-8")
    for index in range(3):
        path = ticket_root / "raw" / f"demo-{index}.h5"
        with h5py.File(path, "w") as handle:
            actions = np.zeros((50, 7), dtype=np.float32)
            actions[:, 6] = 1.0
            handle.create_dataset("action", data=actions)
            observation = handle.create_group("observation")
            observation.create_dataset("state", data=np.zeros((51, 8), dtype=np.float32))
            handle.create_dataset("simulator_state", data=np.zeros((51, 2)))
            handle.create_dataset(
                "ee_position",
                data=np.column_stack(
                    [np.linspace(0, 0.1, 51), np.zeros(51), np.zeros(51)]
                ),
            )
            handle.attrs["ticket_id"] = "ticket-1"
            handle.attrs["coverage_cell"] = "approach_side=left"
            handle.attrs["explicit_success"] = True
            handle.attrs["replay_max_state_error"] = 0.0
            handle.attrs["replay_validated"] = True

    # Audit backups stay beside raw episodes but are not separate demos.
    backup = ticket_root / "raw" / "demo-0.before-recovery.h5"
    backup.write_bytes((ticket_root / "raw" / "demo-0.h5").read_bytes())

    def fake_export(paths, *, output_root, repo_id, fps=20):
        (output_root / "meta").mkdir(parents=True)
        (output_root / "meta" / "info.json").write_text(
            json.dumps({"episodes": len(paths), "repo_id": repo_id}),
            encoding="utf-8",
        )
        return output_root

    monkeypatch.setattr("mode_gate.data_pipeline.export_lerobot_v3", fake_export)
    first = curate_and_export_ticket(ticket_path=ticket_path, repo_id="vls/ticket-1")
    second = curate_and_export_ticket(ticket_path=ticket_path, repo_id="vls/ticket-1")
    assert first == second
    assert not first["needs_more_demos"]
    assert first["coverage"]["approach_side=left"]["accepted"] == 3
    assert len(first["accepted"]) == 3
    assert (ticket_root / "exports" / "lerobot_v3" / "meta" / "info.json").is_file()


def test_policy_promotion_runs_frozen_100_250_and_trigger_gate_idempotently(tmp_path):
    tasks = [
        {
            "suite": f"libero_{index // 10}",
            "task_id": str(index),
            "task_index": index % 10,
            "perturbation_variant": "base",
            "init_state_ids": [str(state) for state in range(50)],
        }
        for index in range(40)
    ]
    manifest = generate_joint_manifest(
        tasks,
        dataset_hash="d",
        bddl_hash="b",
        init_state_manifest_hash="i",
        generator_git_sha="g",
    )
    scores = {
        "parent": 0.50,
        "candidate-02": 0.45,
        "candidate-04": 0.56,
        "candidate-06": 0.60,
        "candidate-08": 0.49,
    }

    class FakeEvaluator:
        def __init__(self):
            self.calls = []

        def evaluate(self, *, policy_id, checkpoint_path, checkpoint_digest, contexts, metric_role):
            self.calls.append((policy_id, metric_role, len(contexts)))
            value = scores[policy_id]
            successes = round(value * len(contexts))
            vector = tuple(
                1 if index < successes else 0 for index in range(len(contexts))
            )
            task_ids = sorted({context.task_key for context in contexts})
            return PolicyEvaluationSummary(
                policy_id=policy_id,
                checkpoint_digest=checkpoint_digest,
                metric_role=metric_role,
                successes=successes,
                episodes=len(contexts),
                micro_sr=successes / len(contexts),
                wilson95=(0.0, 1.0),
                macro_sr=value,
                per_task_sr={task: value for task in task_ids},
                raw_vector=vector,
            )

    parent = PolicyCandidate("parent", str(tmp_path / "parent"), "p" * 64, 0.0)
    candidates = [
        PolicyCandidate(
            f"candidate-0{int(alpha * 10)}",
            str(tmp_path / f"candidate-{alpha}"),
            str(int(alpha * 10)) * 64,
            alpha,
        )
        for alpha in (0.2, 0.4, 0.6, 0.8)
    ]

    def trigger(candidate, parent_candidate):
        passed = candidate.policy_id == "candidate-06"
        return TriggerRecheckResult(
            candidate_id=candidate.policy_id,
            parent_id=parent_candidate.policy_id,
            seen_successes=8 if passed else 5,
            seen_total=10,
            unseen_successes=10 if passed else 6,
            unseen_total=12,
            parent_seen_successes=6,
            parent_seen_total=10,
            parent_unseen_successes=8,
            parent_unseen_total=12,
        )

    evaluator = FakeEvaluator()
    coordinator = PolicyPromotionCoordinator(
        evaluator=evaluator,
        manifest=manifest,
        output_root=tmp_path / "reports",
        bootstrap_draws=50,
    )
    first = coordinator.run(
        parent=parent,
        candidates=candidates,
        trigger_evaluator=trigger,
        trigger_identity={"ticket_id": "ticket"},
    )
    calls = list(evaluator.calls)
    second = coordinator.run(
        parent=parent,
        candidates=candidates,
        trigger_evaluator=trigger,
        trigger_identity={"ticket_id": "ticket"},
    )

    assert first == second
    assert evaluator.calls == calls
    assert first["alpha_selection"]["episodes"] == 100
    assert first["regression"]["episodes"] == 250
    assert first["alpha_selection"]["top2"] == ["candidate-06", "candidate-04"]
    assert first["decision"]["status"] == "POLICY_STAGED"
    assert first["decision"]["winner"]["policy_id"] == "candidate-06"


def test_deployed_dev_uses_installed_policy_fresh_seeds_and_separate_metric(tmp_path):
    manifest = generate_joint_manifest(
        [
            {
                "suite": f"libero_{index // 10}",
                "task_id": str(index),
                "task_index": index % 10,
                "perturbation_variant": "base",
                "init_state_ids": [str(state) for state in range(50)],
            }
            for index in range(40)
        ],
        dataset_hash="d",
        bddl_hash="b",
        init_state_manifest_hash="i",
        generator_git_sha="g",
    )
    contexts = deployed_dev_contexts(manifest)
    assert len(contexts) == 50
    assert len({context.task_key for context in contexts}) == 40
    final_cells = {
        (task["task_key"], str(state))
        for task in manifest["tasks"]
        for state in task["splits"]["policy_final_sealed"]
    }
    assert not {
        (context.task_key, context.init_state_id) for context in contexts
    }.intersection(final_cells)
    raw_contexts = contexts_from_manifest(manifest, split="policy_regression")
    raw_by_cell = {
        (context.task_key, context.init_state_id): context
        for context in raw_contexts
    }
    for context in contexts:
        raw = raw_by_cell[(context.task_key, context.init_state_id)]
        assert (context.env_seed, context.policy_seed) != (
            raw.env_seed,
            raw.policy_seed,
        )

    source = tmp_path / "source"
    source.mkdir()
    save_file({"weight": torch.ones(2, 2)}, str(source / "model.safetensors"))
    digest = checkpoint_digest(source)
    registry = PolicyRegistry(tmp_path / "registry")
    installed = registry.install_artifact("policy", "policy-1", source)
    active = registry.promote(
        policy_id="policy-1",
        verifier_id=None,
        controller_mode="fixed_budget_4",
        manifest_hash=manifest["manifest_sha256"],
        expected_revision=0,
    )
    assert checkpoint_identity_canary(installed, expected_digest=digest)["passed"]

    class Evaluator:
        def __init__(self):
            self.call = None

        def evaluate(self, **kwargs):
            self.call = kwargs
            values = tuple(index % 2 for index in range(len(kwargs["contexts"])))
            return PolicyEvaluationSummary(
                policy_id=kwargs["policy_id"],
                checkpoint_digest=kwargs["checkpoint_digest"],
                metric_role=kwargs["metric_role"],
                successes=sum(values),
                episodes=len(values),
                micro_sr=sum(values) / len(values),
                wilson95=(0.0, 1.0),
                macro_sr=0.5,
                per_task_sr={context.task_key: 0.5 for context in kwargs["contexts"]},
                raw_vector=values,
            )

    evaluator = Evaluator()
    report = DeployedDevelopmentCoordinator(
        registry=registry,
        manifest=manifest,
        evaluator=evaluator,
        output_path=tmp_path / "deployed_dev.json",
    ).run(
        expected_revision=active.deployment_revision,
        expected_checkpoint_digest=digest,
    )
    assert report["metric_role"] == "deployed_dev"
    assert report["context_count"] == 50
    assert report["deployment"]["policy_id"] == "policy-1"
    assert evaluator.call["checkpoint_path"] == installed
    assert evaluator.call["metric_role"] == "deployed_dev"
    assert evaluator.call["require_raw_profile"] is True


def test_offline_replay_plan_is_immutable_and_progress_is_monotonic(tmp_path):
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    save_file({"weight": torch.ones(1)}, str(checkpoint / "model.safetensors"))
    snapshots = tmp_path / "snapshots"
    snapshot = snapshots / "snapshot-1"
    snapshot.mkdir(parents=True)
    manifest = {
        "snapshot_id": "snapshot-1",
        "snapshot_hash": "a" * 64,
        "provenance": {
            "suite": "libero_object",
            "runtime_suite": "libero_object",
            "perturbation_variant": "base",
        },
    }
    manifest_path = snapshot / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    incidents = tmp_path / "incidents"
    incidents.mkdir()
    result_path = tmp_path / "result.json"
    plan = {
        "schema_version": "new-policy-counterfactual-plan-v2",
        "policy_id": "policy-2",
        "checkpoint_path": str(checkpoint),
        "checkpoint_digest": checkpoint_digest(checkpoint),
        "snapshot_root": str(snapshots),
        "incident_root": str(incidents),
        "adaptive_branches": [16, 32, 64],
        "decision_rule": "head_argmax",
        "max_posterior_width": 0.20,
        "contexts": [
            {
                "record_id": "record-1",
                "target_policy_id": "policy-2",
                "snapshot_id": "snapshot-1",
                "snapshot_hash": "a" * 64,
                "snapshot_manifest_path": str(manifest_path.resolve()),
                "data_split": "train",
                "remaining_budget": 4,
                "fresh_feature_output_path": str(tmp_path / "feature.npz"),
            }
        ],
        "result_path": str(result_path),
    }
    plan["plan_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    assert validate_replay_plan(plan_path)["policy_id"] == "policy-2"
    plan["decision_rule"] = "probability_threshold"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        validate_replay_plan(plan_path)

    progress = HgpuReplayApplication.progress_observer(
        adapter=None,
        before={"completed_count": 1},
        after={"completed_count": 2, "goal_count": 3},
        task_success=False,
    )
    assert progress.advanced
    assert progress.stage_id == "bddl-goals:2/3"
    regressed = HgpuReplayApplication.progress_observer(
        adapter=None,
        before={"completed_count": 2},
        after={"completed_count": 1, "goal_count": 3},
        task_success=False,
    )
    assert not regressed.advanced


def test_verifier_audit_uses_only_frozen_shards_and_writes_replay_job(tmp_path):
    manifest = generate_joint_manifest(
        [
            {
                "suite": f"libero_{index // 10}",
                "task_id": str(index),
                "task_index": index % 10,
                "perturbation_variant": "base",
                "init_state_ids": [str(state) for state in range(50)],
            }
            for index in range(40)
        ],
        dataset_hash="d",
        bddl_hash="b",
        init_state_manifest_hash="i",
        generator_git_sha="g",
    )
    contexts = audit_contexts_from_manifest(manifest)
    assert len(contexts) == 800
    assert {item.verifier_split for item in contexts} == {
        "train",
        "calibration",
        "test",
    }
    audit_cells = {
        (item.evaluation.task_key, item.evaluation.init_state_id)
        for item in contexts
    }
    policy_cells = {
        (task["task_key"], str(state))
        for task in manifest["tasks"]
        for split in (
            "policy_alpha_selection",
            "policy_regression",
            "policy_final_sealed",
        )
        for state in task["splits"][split]
    }
    assert not audit_cells.intersection(policy_cells)

    source = tmp_path / "source"
    source.mkdir()
    save_file({"weight": torch.ones(1)}, str(source / "model.safetensors"))
    registry = PolicyRegistry(tmp_path / "registry")
    registry.install_artifact("policy", "policy-a", source)
    registry.promote(
        policy_id="policy-a",
        verifier_id=None,
        controller_mode="fixed_budget_4",
        manifest_hash=manifest["manifest_sha256"],
        expected_revision=0,
    )

    class Executor:
        repo_root = Path(__file__).resolve().parents[1]
        python_executable = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")

        def __call__(self, policy_id, context):
            return RawEpisodeResult(
                success=False,
                output_dir=str(tmp_path / context.episode_key),
            )

    incident_root = tmp_path / "incidents"
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()
    report = AuditCollectionCoordinator(
        manifest=manifest,
        registry=registry,
        incidents=IncidentMemory(incident_root),
        snapshot_root=snapshot_root,
        executor=Executor(),
        ledger_path=tmp_path / "audit.jsonl",
        output_path=tmp_path / "collection.json",
        replay_plan_path=tmp_path / "replay" / "plan.json",
        max_workers=2,
    ).run(limit=8)
    assert report["pilot"]
    assert report["scheduled_context_count"] == 8
    assert report["verifier_opportunities"] == 0
    assert Path(report["replay_job_path"]).is_file()
    assert validate_replay_plan(report["replay_plan_path"])["contexts"] == []
    replay_job = json.loads(Path(report["replay_job_path"]).read_text())
    assert replay_job["preferred_gpu_index"] == 0
    assert replay_job["command"][-1] == "cuda:0"


def test_formal_audit_uses_single_robotics_stage_signal_and_sim_segmentation(
    tmp_path, monkeypatch
):
    captured = []

    def fake_run(command, **kwargs):
        captured.append(command)
        run_dir = Path(
            next(value.split("=", 1)[1] for value in command if value.startswith("hydra.run.dir="))
        )
        (run_dir / "results.txt").write_text("Success count: 0 / 1\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="audit-ok")

    monkeypatch.setattr("mode_gate.audit.subprocess.run", fake_run)
    executor = HydraAuditEpisodeExecutor(
        repo_root=Path(__file__).resolve().parents[1],
        python_executable=Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python"),
        registry_root=tmp_path / "registry",
        incident_root=tmp_path / "incidents",
        snapshot_root=tmp_path / "snapshots",
        slow_loop_root=tmp_path / "slow",
        output_root=tmp_path / "runs",
        use_guidance=True,
        gpu_index=4,
        code_revision="test-source-revision",
    )
    context = AuditContext(
        evaluation=EvaluationContext(
            suite="libero_10",
            task_id="task",
            task_index=2,
            perturbation_variant="use_language",
            init_state_id="28",
            env_seed=1,
            policy_seed=2,
        ),
        verifier_split="train",
    )
    first = executor("policy_000", context)
    second = executor("policy_000", context)
    assert "main.use_vlm_stage_recognition=false" in captured[0]
    assert "perception.gemini_grounding.enabled=false" in captured[0]
    assert "main.fail_on_episode_error=true" in captured[0]
    assert "mode_gate.enabled=true" in captured[0]
    assert first.output_dir.endswith("attempt_000001")
    assert second.output_dir.endswith("attempt_000002")
    assert json.loads((Path(first.output_dir) / "attempt.json").read_text())["status"] == "COMMITTED"
    assert json.loads((Path(second.output_dir) / "attempt.json").read_text())["status"] == "COMMITTED"
    correction = invalidate_audit_attempt(
        Path(first.output_dir),
        reason="test_invalid_attempt",
        evidence={"traceback": "synthetic"},
    )
    assert correction["previous_status"] == "COMMITTED"
    assert json.loads((Path(first.output_dir) / "attempt.json").read_text())["status"] == "RETRYABLE_ERROR"
    assert len(
        (Path(first.output_dir).parent.parent / "attempt_corrections.jsonl")
        .read_text()
        .splitlines()
    ) == 1


def test_formal_audit_rejects_caught_episode_errors_as_retryable(tmp_path, monkeypatch):
    def fake_run(command, **kwargs):
        run_dir = Path(
            next(value.split("=", 1)[1] for value in command if value.startswith("hydra.run.dir="))
        )
        episode_dir = run_dir / "episode_1"
        episode_dir.mkdir()
        (episode_dir / "episode_1_fail_error.txt").write_text(
            "invalid episode\n", encoding="utf-8"
        )
        (run_dir / "results.txt").write_text(
            "Success count: 0 / 1\n", encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="caught-error")

    monkeypatch.setattr("mode_gate.audit.subprocess.run", fake_run)
    executor = HydraAuditEpisodeExecutor(
        repo_root=Path(__file__).resolve().parents[1],
        python_executable=Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python"),
        registry_root=tmp_path / "registry",
        incident_root=tmp_path / "incidents",
        snapshot_root=tmp_path / "snapshots",
        slow_loop_root=tmp_path / "slow",
        output_root=tmp_path / "runs",
        gpu_index=4,
        code_revision="test-source-revision",
    )
    context = AuditContext(
        evaluation=EvaluationContext(
            suite="libero_goal",
            task_id="task",
            task_index=3,
            perturbation_variant="use_language",
            init_state_id="36",
            env_seed=1,
            policy_seed=2,
        ),
        verifier_split="train",
    )
    with pytest.raises(RuntimeError, match="invalid"):
        executor("policy_000", context)
    attempt = json.loads(
        next((tmp_path / "runs").glob("**/attempt.json")).read_text()
    )
    assert attempt["status"] == "RETRYABLE_ERROR"
    assert attempt["error"] == "invalid_episode"


def test_episode_ledger_invalidation_is_append_only_and_allows_retry(tmp_path):
    ledger = EpisodeLedger(tmp_path / "episodes.jsonl")
    episode_key = "episode-a"
    first = {
        "policy_id": "policy_000",
        "manifest_hash": "manifest",
        "output_dir": "/attempt/one",
        "success": False,
    }
    assert ledger.append(episode_key, first)
    assert ledger.completed() == {episode_key}
    assert ledger.invalidate(
        episode_key,
        reason="caught_execution_error",
        evidence={"attempt": "/attempt/one"},
    )
    assert ledger.completed() == set()
    assert ledger.append(episode_key, {**first, "output_dir": "/attempt/two"})
    assert ledger.completed() == {episode_key}
    events = ledger.events.read_all()
    assert [event["event_type"] for event in events] == [
        "EPISODE_COMPLETED",
        "EPISODE_INVALIDATED",
        "EPISODE_COMPLETED",
    ]


def test_episode_ledger_resume_is_bound_to_source_policy_and_manifest(tmp_path):
    ledger = EpisodeLedger(tmp_path / "episodes.jsonl")
    base = {
        "policy_id": "policy_000",
        "manifest_hash": "manifest-a",
        "code_revision": "source-a",
        "output_dir": "/attempt/one",
    }
    assert ledger.append("episode-a", base)
    assert ledger.completed_for(
        policy_id="policy_000",
        manifest_hash="manifest-a",
        code_revision="source-a",
    ) == {"episode-a"}
    assert ledger.completed_for(
        policy_id="policy_000",
        manifest_hash="manifest-a",
        code_revision="source-b",
    ) == set()


def test_registry_bootstrap_base_policy_is_idempotent(tmp_path):
    source = tmp_path / "theta0"
    source.mkdir()
    save_file({"weight": torch.ones(2)}, str(source / "model.safetensors"))
    digest = checkpoint_digest(source)
    registry = PolicyRegistry(tmp_path / "registry")

    first = registry.bootstrap_base_policy(
        checkpoint_path=source,
        digest=digest,
        metadata={"source": "theta0"},
        policy_id="policy_000",
        manifest_hash="manifest-a",
    )
    second = registry.bootstrap_base_policy(
        checkpoint_path=source,
        digest=digest,
        metadata={"source": "theta0"},
        policy_id="policy_000",
        manifest_hash="manifest-a",
    )

    assert first == second
    assert first.deployment_revision == 1
    assert first.controller_mode == "fixed_budget_4"
    assert checkpoint_digest(registry.root / "policies" / "policy_000") == digest
    with pytest.raises(RuntimeError, match="different deployment"):
        registry.bootstrap_base_policy(
            checkpoint_path=source,
            digest=digest,
            metadata={"source": "theta0"},
            policy_id="policy_000",
            manifest_hash="manifest-b",
        )


def test_balanced_libero_pro_variant_map_has_four_equal_axes():
    task_map = {
        suite: [f"task-{index}" for index in range(10)]
        for suite in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
    }
    task_map["libero_10"] = [
        *[f"LIVING_ROOM_SCENE{index}_task" for index in range(5)],
        *[f"KITCHEN_OR_STUDY_SCENE{index}_task" for index in range(5)],
    ]
    mapping = balanced_libero_pro_variant_map(task_map)

    assert len(mapping) == 40
    assert {
        variant: tuple(mapping.values()).count(variant)
        for variant in LIBERO_PRO_VARIANTS
    } == {variant: 10 for variant in LIBERO_PRO_VARIANTS}
    for suite in task_map:
        counts = {
            variant: sum(
                mapping[f"{suite}::{task_id}"] == variant
                for task_id in task_map[suite]
            )
            for variant in LIBERO_PRO_VARIANTS
        }
        assert set(counts.values()).issubset({2, 3})
    assert all(
        not selector.split("::", 1)[1].startswith("LIVING_ROOM_")
        for selector, variant in mapping.items()
        if selector.startswith("libero_10::") and variant == "use_environment"
    )


def test_canary_context_uses_fixed_probe_from_libero_pro_manifest():
    suffixes = {
        "use_object": "object",
        "use_swap": "swap",
        "use_language": "lan",
        "use_environment": "env",
    }
    variants = tuple(suffixes)
    tasks = []
    for suite_index in range(4):
        suite = f"libero_{suite_index}"
        for task_index in range(10):
            variant = variants[(suite_index * 10 + task_index) % len(variants)]
            tasks.append(
                {
                    "suite": suite,
                    "runtime_suite": f"{suite}_{suffixes[variant]}",
                    "benchmark": "LIBERO-PRO",
                    "task_id": f"task-{task_index}",
                    "task_index": task_index,
                    "perturbation_variant": variant,
                    "init_state_ids": [str(index) for index in range(50)],
                }
            )
    manifest = generate_joint_manifest(
        tasks,
        dataset_hash="dataset",
        bddl_hash="bddl",
        init_state_manifest_hash="init",
        generator_git_sha="revision",
    )

    context = fixed_development_probe_context(manifest)

    assert context["benchmark"] == "LIBERO-PRO"
    assert context["runtime_suite"] != context["suite"]
    assert context["split"] == "fixed_development_probe"
    assert context["init_state_id"] in next(
        task["splits"]["fixed_development_probe"]
        for task in manifest["tasks"]
        if task["task_key"]
        == "::".join(
            (context["suite"], context["task_id"], context["perturbation_variant"])
        )
    )


def test_libero_pro_environment_seed_patch_normalizes_numpy_integer():
    observed = []

    class EnvironmentReplacePerturbator:
        def perturb(self, task_suite_name, task_name, seed=None):
            observed.append(seed)
            return "ok"

    module = SimpleNamespace(
        EnvironmentReplacePerturbator=EnvironmentReplacePerturbator
    )
    patch_environment_seed(module)
    patch_environment_seed(module)

    instance = EnvironmentReplacePerturbator()
    assert instance.perturb("suite", "task", seed=np.int64(7)) == "ok"
    assert observed == [7]
    assert type(observed[0]) is int


def test_libero_pro_environment_seed_patch_repairs_upstream_int_sentinel():
    observed = []

    class EnvironmentReplacePerturbator:
        def perturb(self, task_suite_name, task_name, seed=None):
            observed.append(seed)
            return "ok"

    module = SimpleNamespace(
        EnvironmentReplacePerturbator=EnvironmentReplacePerturbator
    )
    patch_environment_seed(module)

    assert EnvironmentReplacePerturbator().perturb(
        "suite", "task", seed=int
    ) == "ok"
    assert observed == [DEFAULT_LIBERO_PRO_SEED]


def test_reuse_policy_gate_runs_every_candidate_on_regression250(tmp_path):
    manifest = generate_joint_manifest(
        [
            {
                "suite": f"libero_{index // 10}",
                "task_id": str(index),
                "task_index": index % 10,
                "perturbation_variant": "base",
                "init_state_ids": [str(state) for state in range(50)],
            }
            for index in range(40)
        ],
        dataset_hash="d",
        bddl_hash="b",
        init_state_manifest_hash="i",
        generator_git_sha="g",
    )
    scores = {"parent": 0.50, "reuse-55": 0.53, "reuse-70": 0.58, "reuse-90": 0.57}

    class Evaluator:
        def __init__(self):
            self.calls = []

        def evaluate(self, *, policy_id, checkpoint_path, checkpoint_digest, contexts, metric_role):
            self.calls.append((policy_id, metric_role, len(contexts)))
            value = scores[policy_id]
            successes = round(value * len(contexts))
            vector = tuple(index < successes for index in range(len(contexts)))
            return PolicyEvaluationSummary(
                policy_id=policy_id,
                checkpoint_digest=checkpoint_digest,
                metric_role=metric_role,
                successes=successes,
                episodes=len(contexts),
                micro_sr=successes / len(contexts),
                wilson95=(0.0, 1.0),
                macro_sr=value,
                per_task_sr={context.task_key: value for context in contexts},
                raw_vector=vector,
            )

    evaluator = Evaluator()
    coordinator = PolicyPromotionCoordinator(
        evaluator=evaluator,
        manifest=manifest,
        output_root=tmp_path / "reports",
        bootstrap_draws=10,
    )
    parent = PolicyCandidate("parent", "/parent", "p" * 64, 0.4)
    candidates = [
        PolicyCandidate(f"reuse-{int(alpha * 100):02d}", f"/{alpha}", str(index) * 64, alpha)
        for index, alpha in enumerate((0.55, 0.70, 0.90), start=1)
    ]

    def trigger(candidate, parent_candidate):
        return TriggerRecheckResult(
            candidate.policy_id,
            parent_candidate.policy_id,
            8,
            10,
            9,
            12,
            6,
            10,
            7,
            12,
        )

    report = coordinator.run_reuse(
        parent=parent,
        candidates=candidates,
        trigger_evaluator=trigger,
        trigger_identity={"ticket_id": "reuse-ticket"},
    )
    assert report["alpha_selection"]["skipped"]
    assert report["regression"]["episodes"] == 250
    assert {call[0] for call in evaluator.calls} == {
        "parent",
        "reuse-55",
        "reuse-70",
        "reuse-90",
    }
    assert report["decision"]["winner"]["policy_id"] == "reuse-70"


def test_policy_deploy_falls_back_then_switches_only_verifier(tmp_path):
    checkpoint = tmp_path / "winner"
    checkpoint.mkdir()
    save_file({"weight": torch.ones(2)}, str(checkpoint / "model.safetensors"))
    digest = checkpoint_digest(checkpoint)
    report = {
        "schema_version": "raw-policy-gate-report-v1",
        "manifest_hash": "manifest-hash",
        "decision": {
            "status": "POLICY_STAGED",
            "winner": {
                "policy_id": "policy-1",
                "checkpoint_path": str(checkpoint),
                "checkpoint_digest": digest,
                "alpha_l": 0.6,
            },
        },
    }
    registry = PolicyRegistry(tmp_path / "registry")
    first = deploy_policy_gate(
        report=report,
        registry=registry,
        expected_revision=0,
        verifier_result={"gate": {"passed": False}},
    )
    assert first.policy_id == "policy-1"
    assert first.controller_mode == "fixed_budget_4"
    assert first.verifier_id is None

    verifier = tmp_path / "verifier"
    verifier.mkdir()
    (verifier / "manifest.json").write_text(
        json.dumps({"metadata": {"policy_id": "policy-1"}}), encoding="utf-8"
    )
    (verifier / "head.pt").write_bytes(b"head")
    second = deploy_policy_gate(
        report=report,
        registry=registry,
        expected_revision=1,
        verifier_result={
            "gate": {"passed": True},
            "verifier_id": "verifier-1",
            "artifact_root": str(verifier),
        },
    )
    assert second.deployment_revision == 2
    assert second.policy_id == first.policy_id
    assert second.controller_mode == "learned_verifier"
    assert second.verifier_id == "verifier-1"


def test_verifier_refresh_requires_cold_start_or_two_hundred_new_contexts():
    assert not verifier_refresh_status(
        current_strong_contexts=1699,
        last_attempted_contexts=0,
        has_active_verifier=False,
        brier_drift=None,
    ).due
    cold = verifier_refresh_status(
        current_strong_contexts=1700,
        last_attempted_contexts=0,
        has_active_verifier=False,
        brier_drift=None,
    )
    assert cold.due and cold.reasons == ("cold_start_evidence_ready",)
    assert not verifier_refresh_status(
        current_strong_contexts=1899,
        last_attempted_contexts=1700,
        has_active_verifier=True,
        brier_drift=0.01,
    ).due
    refresh = verifier_refresh_status(
        current_strong_contexts=1900,
        last_attempted_contexts=1700,
        has_active_verifier=True,
        brier_drift=0.03,
    )
    assert refresh.due
    assert set(refresh.reasons) == {
        "at_least_200_new_labeled_contexts",
        "brier_drift_exceeded_threshold",
    }
