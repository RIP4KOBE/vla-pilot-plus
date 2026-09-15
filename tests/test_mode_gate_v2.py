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
    compose_selected_remedy,
)
from mode_gate.config import ModeGateConfig
from mode_gate.counterfactual import (
    BranchOutcome,
    CounterfactualResult,
    CounterfactualReplayWorker,
    FixedBudgetResteerExecutor,
    FreshCandidateSelection,
    NewPolicyReplayCoordinator,
    REPLAY_PROGRESS_CONTRACT,
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
    rank_current_task_candidates,
    wilson_interval,
)
from mode_gate.experiment_contract import (
    FIXED_BUDGET_50_CONTRACT,
    FIXED_BUDGET_50_LABEL_VERSION,
    label_contract_payload,
    regenerate_budget_state,
)
from mode_gate.features import select_task_keypoints
from mode_gate.factual_reconstruction import reconstruct_factual_labels
from mode_gate.geometry import (
    AxisAlignedBox,
    GeometryContext,
    GeometryScorer,
    select_execution_candidate,
)
from mode_gate.incidents import (
    CapabilitySignatureRecord,
    IncidentMemory,
    VerifierDecisionRecord,
    VerifierLabelRecord,
)
from mode_gate.io_utils import AtomicJsonl, atomic_write_json, sha256_file
from mode_gate.offline_replay import (
    HgpuReplayApplication,
    _completed_replay_result,
    _score_semantics_with_network_recovery,
    validate_replay_plan,
)
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
from mode_gate.runtime import CandidateRuntime, _save_round_evidence
from mode_gate.semantic_planner import (
    GeminiCallBudgetExceeded,
    GeminiSemanticPlanner,
    preflight_with_network_recovery,
    score_semantics_with_network_recovery,
)
from mode_gate.scene_encoder import (
    MaskedHiddenStates,
    Theta0SceneEncoder,
    processor_artifact_digest,
)
from mode_gate.signatures import FailureMode
from mode_gate.slow_loop import SlowLoopState, SlowLoopStore
from mode_gate.slow_worker import SlowLoopWorker
from mode_gate.teleop_supervisor import TeleopServiceResult
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
    CandidateEvidence,
    ProgressEvidence,
    RoundEvidence,
    SamplingCondition,
    SamplingDiagnostics,
    SemanticCandidateScore,
    SemanticPlan,
    TaskSpaceTrajectoryBatch,
)
from mode_gate.verifier import (
    DeployedVerifierPredictor,
    FeatureStandardizer,
    GroundedCapabilityVerifier,
    CandidateVerifierInput,
    PlattCalibrator,
    VERIFIER_HEAD_ARCHITECTURE,
    VERIFIER_INPUT_DIMS,
    ablate_verifier_input,
    binomial_cross_entropy,
    load_verifier_input,
    save_verifier_input,
)
from mode_gate.verifier_training import VerifierExample, VerifierTrainingConfig, train_verifier
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
    assert controller.mark_scored(has_safe_candidate=True) is None
    return controller.route_scored_batch(verifier_decision=verifier_decision)


def test_v2_controller_uses_fresh_post_failure_batches_and_ten_retries():
    controller = EpisodeChunkController(ModeGateConfig(controller_mode="learned_verifier"))
    controller.start_episode(stage_id="1")
    for _ in range(3):
        route = _score_and_route(controller)
        assert route.route is ControllerRoute.EXECUTE
        controller.observe_chunk(_progress())
    assert controller.state.phase is ControllerPhase.VERIFICATION_DUE
    assert controller.state.failure_count == 1

    for retry in range(50):
        route = _score_and_route(controller, ControllerRoute.RESTEER)
        assert route.route is ControllerRoute.RESTEER
        assert route.reason == "verifier_head_argmax:RE-STEER"
        controller.observe_chunk(_progress())
        assert controller.state.verification_due
        assert controller.state.failure_count == min(50, retry + 2)
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
    controller = EpisodeChunkController(ModeGateConfig(controller_mode="fixed_budget_50"))
    controller.start_episode(stage_id="1")
    _score_and_route(controller)
    controller.state.retry_index = 2
    decision = controller.observe_chunk(_progress(advanced=True))
    assert decision.route is ControllerRoute.EXECUTE
    assert controller.state.retry_index == 2
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
    regressed = monitor.observe(
        task_success=False,
        gemini_stage_id="stage_1",
        gemini_confidence=0.95,
        normalized_reward=0.03,
    )
    assert not regressed.advanced
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
        ModeGateConfig(controller_mode="fixed_budget_50")
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
    assert "--save_final_params_only=false" in joined
    assert "--save_freq=250" in joined
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
        actions=np.zeros((4, trajectories.positions.shape[1]-1, 7), dtype=np.float32),
        sample_ids=trajectories.sample_ids, context_id="ctx", round_id=1,
        checkpoint_id="policy-0", action_space="delta_ee_pose", coordinate_frame="world")
    return RoundEvidence("ctx",1,"policy-0",actions,trajectories,
        tuple(CandidateEvidence(f"m{i}",i,f"s{i}") for i in range(4)),
        SamplingDiagnostics((4.0,2.0),(0,0,0,1),.5,.5,((0,0,1,0),)))


def test_round_evidence_persists_sampling_diagnostics_and_hashes(tmp_path):
    evidence = _round_evidence(tmp_path)
    path = _save_round_evidence(tmp_path / "round_001", evidence)
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "candidate-round-evidence-v3"
    assert metadata["sample_ids"] == ["s0", "s1", "s2", "s3"]
    assert metadata["sampling_diagnostics"]["ancestor_ids"] == [0, 0, 0, 1]
    assert metadata["sampling_diagnostics"]["ess_history"] == [4.0, 2.0]
    assert "fit_metadata" not in metadata and len(metadata["candidates"]) == 4
    assert metadata["analysis_sha256"] == sha256_file(path)
    assert len(metadata["action_sha256"]) == 64




def test_geometry_hard_veto_and_lexicographic_medoid_selection(tmp_path):
    evidence = _round_evidence(tmp_path)
    context = GeometryContext(
        workspace=AxisAlignedBox(np.array([-1, -1, -1]), np.array([1, 1, 1])),
        obstacles=(AxisAlignedBox(np.array([0.15, -0.1, -0.1]), np.array([0.25, 0.1, 0.1])),),
    )
    geometry = GeometryScorer(context).score_round(evidence)
    assert geometry[1].hard_safety_veto is False
    semantics = (
        SemanticCandidateScore("m0", 0.7, "ok"),
        SemanticCandidateScore("m1", 0.9, "better"),
        SemanticCandidateScore("m2", 0.7, "ok"),
        SemanticCandidateScore("m3", 0.7, "ok"),
    )
    selected = select_execution_candidate(evidence.candidates, geometry, semantics, "m1")
    assert selected.candidate_id == "m1"
    assert selected.sample_index == 1


def _verifier_input(order=(0, 1, 2)):
    rng = np.random.default_rng(8)
    candidates = rng.normal(size=(3,11,15)).astype(np.float32)
    return CandidateVerifierInput(scene_feature=np.ones(2048,dtype=np.float32),
        candidate_trajectories=candidates[np.asarray(order)],executed_history=np.zeros((0,15),dtype=np.float32),
        remaining_budget=50,retry_budget=50,candidate_ids=tuple(f"m{i}" for i in order),backbone_id="v44-sha",context_id="ctx")


def test_deep_sets_is_permutation_invariant_and_binomial_target_is_soft():
    torch.manual_seed(1)
    model = GroundedCapabilityVerifier().eval()
    first = model(_verifier_input((0, 1, 2)))
    second = model(_verifier_input((2, 0, 1)))
    torch.testing.assert_close(first, second)
    encoded = model.encode_one(_verifier_input())
    assert encoded.shape == (VERIFIER_INPUT_DIMS,)
    assert first.shape == (1, 2)
    assert isinstance(model.head[-1], torch.nn.Linear)
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
        restored.candidate_trajectories, item.candidate_trajectories, atol=1e-3
    )
    assert restored.candidate_ids == item.candidate_ids
    assert json.loads(path.with_suffix(".json").read_text())["context_id"] == "ctx"




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








def test_reuse_gate_handoff_refuses_to_skip_current_task_demonstrations(tmp_path):
    store = SlowLoopStore(tmp_path / "slow")
    job = store.create(active_policy_id="round-one-merged", input_hash="input", metadata={
        "gate_kind": "REUSE", "suite": "libero_10", "task_id": "black-bowl",
        "perturbation_variant": "env", "reuse_source_ticket_id": "stove-source",
        "parent_candidate_path": str(tmp_path / "parent.json"),
        "candidates_json_path": str(tmp_path / "candidates.json"),
    })
    for state in (SlowLoopState.LOOKUP_PENDING, SlowLoopState.REUSE_EVALUATING,
                  SlowLoopState.RAW_REGRESSION):
        job = store.advance(job.job_id, expected_state=job.state, next_state=state,
                            input_hash=job.input_hash, output_hash=None)
    worker = SlowLoopWorker.__new__(SlowLoopWorker)
    worker.store, worker.work_root = store, tmp_path / "work"
    worker.registry = SimpleNamespace(active=lambda: None)
    worker.protocol_manifest_path = tmp_path / "manifest.json"
    worker.protocol_manifest = {"manifest_sha256": "hash", "tasks": [{
        "suite": "libero_10", "task_id": "black-bowl", "perturbation_variant": "env",
        "splits": {"demo_online_pool": [37], "policy_regression": [1, 2]},
    }]}
    with pytest.raises(ValueError, match="Planner evidence"):
        worker._step(job)






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
        assert model == "gpt-6-astra"


class _PlannerInteractions:
    def __init__(self, payload):
        self.payload = json.loads(json.dumps(payload))
        candidates = self.payload.get("candidates", [])
        if [x["candidate_id"] for x in candidates] == ["m0", "m1"]:
            candidates.extend([{**candidates[0], "candidate_id": f"m{i}"} for i in (2, 3)])
        if candidates:
            self.payload.setdefault("selected_candidate_id", candidates[0]["candidate_id"])
            self.payload.setdefault("selection_reason", "explicit test candidate selection")
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
        "candidates": [
            {"candidate_id": "m0", "semantic_score": 0.2, "reason": "a", "predicted_failure_types": []},
            {"candidate_id": "m1", "semantic_score": 0.8, "reason": "b", "predicted_failure_types": ["offset"]},
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
        GeometryEvidence(mode.candidate_id, 0.1, 0.9, 0.8, False)
        for mode in evidence.candidates
    )
    first = planner.score(context, evidence, geometry, card)
    second = planner.score(context, evidence, geometry, card)
    assert [item.candidate_id for item in first.candidate_scores] == ["m0", "m1", "m2", "m3"]
    assert second.raw_response["metadata"]["cache_hit"] is True
    assert interactions.calls == 1
    assert interactions.kwargs["model"] == "gpt-6-astra"
    assert interactions.kwargs["generation_config"] == {"thinking_level": "ultra"}
    assert interactions.kwargs["response_format"]["mime_type"] == "application/json"
    assert [item["type"] for item in interactions.kwargs["input"]] == ["text", "image"]


def test_gemini_provider_call_budget_is_persistent_and_cache_hits_are_free(tmp_path):
    evidence = _round_evidence(tmp_path)
    card = tmp_path / "combined.png"
    card.write_bytes(b"png")
    payload = {
        "candidates": [
            {
                "candidate_id": mode.candidate_id,
                "semantic_score": 0.5,
                "reason": "ok",
                "predicted_failure_types": [],
            }
            for mode in evidence.candidates
        ],
        "required_trajectory_pattern": "approach",
        "observed_stage_id": "stage_1",
        "stage_confidence": 0.9,
    }
    ledger = tmp_path / "provider_calls.jsonl"
    cache = tmp_path / "cache"
    first_interactions = _PlannerInteractions(payload)
    first = GeminiSemanticPlanner(
        client=SimpleNamespace(
            models=_PlannerModels(), interactions=first_interactions
        ),
        cache_dir=cache,
        max_provider_calls=1,
        call_ledger_path=ledger,
    )
    geometry = tuple(
        GeometryEvidence(mode.candidate_id, 0.1, 0.9, 0.8, False)
        for mode in evidence.candidates
    )
    context = GateContext("ctx-a", np.zeros((8, 8, 3), np.uint8), "pick", "1")
    first.score(context, evidence, geometry, card)
    cached = first.score(context, evidence, geometry, card)
    assert cached.raw_response["metadata"]["cache_hit"] is True
    assert first_interactions.calls == 1
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1

    second_interactions = _PlannerInteractions(payload)
    restarted = GeminiSemanticPlanner(
        client=SimpleNamespace(
            models=_PlannerModels(), interactions=second_interactions
        ),
        cache_dir=cache,
        max_provider_calls=1,
        call_ledger_path=ledger,
    )
    new_context = GateContext(
        "ctx-b", np.zeros((8, 8, 3), np.uint8), "pick", "1"
    )
    with pytest.raises(GeminiCallBudgetExceeded, match="budget exhausted"):
        restarted.score(new_context, evidence, geometry, card)
    assert second_interactions.calls == 0
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_gemini_provider_retries_each_consume_one_reserved_call(tmp_path):
    evidence = _round_evidence(tmp_path)
    card = tmp_path / "combined.png"
    card.write_bytes(b"png")
    payload = {
        "candidates": [
            {
                "candidate_id": mode.candidate_id,
                "semantic_score": 0.5,
                "reason": "ok",
                "predicted_failure_types": [],
            }
            for mode in evidence.candidates
        ],
        "required_trajectory_pattern": "approach",
        "observed_stage_id": "stage_1",
        "stage_confidence": 0.9,
    }

    class FlakyInteractions(_PlannerInteractions):
        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient")
            self.kwargs = kwargs
            return SimpleNamespace(output_text=json.dumps(self.payload))

    interactions = FlakyInteractions(payload)
    ledger = tmp_path / "provider_calls.jsonl"
    planner = GeminiSemanticPlanner(
        client=SimpleNamespace(models=_PlannerModels(), interactions=interactions),
        max_retries=1,
        max_provider_calls=2,
        call_ledger_path=ledger,
    )
    geometry = tuple(
        GeometryEvidence(mode.candidate_id, 0.1, 0.9, 0.8, False)
        for mode in evidence.candidates
    )
    context = GateContext("ctx", np.zeros((8, 8, 3), np.uint8), "pick", "1")
    result = planner.score(context, evidence, geometry, card)
    assert result.observed_stage_id == "stage_1"
    assert interactions.calls == 2
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [item["sequence"] for item in events] == [1, 2]
    assert [item["attempt"] for item in events] == [1, 2]


def test_gemini_planner_rejects_descriptive_stage_identity(tmp_path):
    evidence = _round_evidence(tmp_path)
    card = tmp_path / "combined.png"
    card.write_bytes(b"png")
    interactions = _PlannerInteractions(
        {
            "candidates": [
                {
                    "candidate_id": mode.candidate_id,
                    "semantic_score": 0.5,
                    "reason": "ok",
                    "predicted_failure_types": [],
                }
                for mode in evidence.candidates
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
        GeometryEvidence(mode.candidate_id, 0.1, 0.9, 0.8, False)
        for mode in evidence.candidates
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
        "candidates": [
            {
                "candidate_id": "canary-m0",
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
        failure_count=1, remaining_budget=3, retry_index=47,
    )
    assert memory.record_decision(decision)
    assert not memory.record_decision(decision)
    label = VerifierLabelRecord(
        record_id="r1", label_version=FIXED_BUDGET_50_LABEL_VERSION,
        source="counterfactual_replay",
        branches=16, successes=4, p_expansion=0.75, policy_id="p",
        snapshot_hash="a" * 64,
        label_config=label_contract_payload(),
    )
    assert memory.attach_label(label)
    assert len(memory.joined_training_rows()) == 1
    assert len(list(memory.experiences.facts.iter_valid())) == 1
    assert not list(memory.experiences.interpretations.iter_valid())




def test_atomic_label_batch_is_idempotent_and_validates_before_writing(tmp_path):
    ledger = AtomicJsonl(tmp_path / "labels.jsonl")
    events = [{"event_id": "a", "value": 1}, {"event_id": "b", "value": 2}]
    assert ledger.append_many(events + events[:1]) == [True, True, False]
    original = ledger.path.read_bytes()
    assert ledger.append_many(events) == [False, False]
    assert ledger.path.read_bytes() == original
    with pytest.raises(ValueError, match="event requires"):
        ledger.append_many([{"event_id": "c"}, {}])
    assert ledger.path.read_bytes() == original
    assert ledger.read_all() == events






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
        remaining_budget=50,
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
            task_success=True,
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
        label_version=FIXED_BUDGET_50_LABEL_VERSION,
        verifier_feature_path=new_policy_feature,
    )
    second = worker.run(
        record_id="decision-1",
        policy_id="policy-new",
        label_version=FIXED_BUDGET_50_LABEL_VERSION,
        verifier_feature_path=new_policy_feature,
    )

    assert first.branches == 16 and first.successes == 16
    assert first.p_expansion == 0.0 and first.label_attached
    assert not second.label_attached
    assert len(executor_calls) == 16
    assert snapshots.calls == [("snapshot-1", False)] * 16


def test_new_policy_replay_coordinator_uses_versioned_plan_and_exact_feature_path(tmp_path):
    result_path = tmp_path / "result.json"
    feature_path = tmp_path / "features" / "r1.npz"
    unsigned = {
        "schema_version": "new-policy-counterfactual-plan-v3",
        "job_id": "job-1",
        "policy_id": "policy-new",
        "checkpoint_path": "/checkpoint",
        "checkpoint_digest": "a" * 64,
        "snapshot_root": "/snapshots",
        "incident_root": "/incidents",
        "retry_estimand": "retry failure",
        "adaptive_branches": [16, 32],
        "decision_rule": "head_argmax",
        "progress_contract": REPLAY_PROGRESS_CONTRACT,
        "label_version": FIXED_BUDGET_50_LABEL_VERSION,
        "label_config": label_contract_payload(),
        "contexts": [
            {
                "record_id": "r1",
                "origin_policy_id": "policy-old",
                "target_policy_id": "policy-new",
                "snapshot_id": "s1",
                "snapshot_hash": "b" * 64,
                "snapshot_manifest_path": "/snapshots/s1/manifest.json",
                "budget_state": regenerate_budget_state({"retry_index": 0}),
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
                posterior_side_probability=0.99,
                label_status="LABELED",
                censored=False,
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
        return FreshCandidateSelection(
            actions=actions,
            candidate_id=f"mode-{condition.retry_index}",
            sample_index=condition.retry_index,
        )

    adapter = Adapter()
    outcome = FixedBudgetResteerExecutor(fresh_sampler=fresh_sampler)(
        adapter=adapter,
        policy=object(),
        branch_seed=123,
        remaining_budget=10,
        controller_state={"retry_index": 0},
    )
    assert not outcome.success and not outcome.task_success
    assert outcome.chunks_executed == 10 and adapter.steps == 100
    assert [item.retry_index for item in conditions] == list(range(10))
    assert [item.guide_mult for item in conditions] == [1.0] * 10


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


def test_offline_replay_aligns_policy_config_and_processor_device(
    tmp_path, monkeypatch
):
    import core.pi05_steer as pi05_steer
    import lerobot.policies.factory as policy_factory

    calls = {}

    class FakeTarget:
        def __init__(self):
            self.config = SimpleNamespace(device="cuda:0")

        @classmethod
        def from_pretrained(cls, path):
            calls["checkpoint"] = path
            return cls()

        def to(self, device):
            calls["module_device"] = device
            return self

        def post_init(self, **kwargs):
            calls["post_init"] = kwargs

        def eval(self):
            calls["eval"] = True

    def fake_processors(*, policy_cfg, pretrained_path, preprocessor_overrides):
        calls["config_device"] = policy_cfg.device
        calls["processor_device"] = preprocessor_overrides["device_processor"][
            "device"
        ]
        return object(), object()

    monkeypatch.setattr(pi05_steer, "PI05PolicySteer", FakeTarget)
    monkeypatch.setattr(
        policy_factory, "make_pre_post_processors", fake_processors
    )
    application = HgpuReplayApplication.__new__(HgpuReplayApplication)
    application.device = "cuda:4"
    application.adapter = object()
    application.main = SimpleNamespace(
        mode_gate_config=SimpleNamespace(
            theta0_checkpoint=tmp_path / "theta0", sample_count=40
        ),
        policy_type_config={},
    )

    target, _ = application._load_target_policy(tmp_path / "policy")

    assert calls["module_device"] == "cuda:4"
    assert calls["config_device"] == "cuda:4"
    assert calls["processor_device"] == "cuda:4"
    assert target.config.device == "cuda:4"
    assert calls["eval"] is True


def test_offline_replay_keeps_warm_process_during_gemini_network_outage(
    monkeypatch,
):
    from mode_gate.agents import AgentCallError

    calls = []
    sleeps = []

    class Planner:
        def score(self, *args, **kwargs):
            calls.append((args, kwargs))
            if len(calls) < 3:
                raise AgentCallError(
                    "Gemini semantic scoring failed: "
                    "SSL UNEXPECTED_EOF_WHILE_READING"
                )
            return "semantic-plan"

    monkeypatch.setattr("mode_gate.offline_replay.time.sleep", sleeps.append)

    result = _score_semantics_with_network_recovery(
        Planner(), "context", frozen_prompt="same"
    )

    assert result == "semantic-plan"
    assert len(calls) == 3
    assert all(call == (("context",), {"frozen_prompt": "same"}) for call in calls)
    assert sleeps == [10.0, 20.0]


def test_offline_replay_does_not_retry_gemini_schema_failure(monkeypatch):
    from mode_gate.agents import AgentCallError

    class Planner:
        def score(self):
            raise AgentCallError("duplicate or missing mode ID")

    monkeypatch.setattr(
        "mode_gate.offline_replay.time.sleep",
        lambda delay: pytest.fail(f"unexpected retry sleep: {delay}"),
    )

    with pytest.raises(AgentCallError, match="duplicate or missing"):
        _score_semantics_with_network_recovery(Planner())


def test_online_semantic_scoring_keeps_warm_runtime_during_tunnel_reconnect():
    from mode_gate.agents import AgentCallError

    calls = []
    sleeps = []

    class Planner:
        def score(self, *args, **kwargs):
            calls.append((args, kwargs))
            if len(calls) == 1:
                raise AgentCallError(
                    "Gemini semantic scoring failed after 3 attempts: "
                    "[Errno 111] Connection refused"
                )
            if len(calls) == 2:
                raise AgentCallError(
                    "Gemini semantic scoring failed after 3 attempts: "
                    "SSL UNEXPECTED_EOF_WHILE_READING"
                )
            return "semantic-plan"

    result = score_semantics_with_network_recovery(
        Planner(),
        "same-evidence",
        recovery_label="online mode-aware runtime",
        sleep_fn=sleeps.append,
        frozen_prompt="same",
    )

    assert result == "semantic-plan"
    assert len(calls) == 3
    assert all(
        call == (("same-evidence",), {"frozen_prompt": "same"})
        for call in calls
    )
    assert sleeps == [10.0, 20.0]


def test_planner_preflight_keeps_warm_runtime_during_tunnel_reconnect():
    from mode_gate.agents import AgentCallError

    calls = []
    sleeps = []

    class Planner:
        def preflight(self, *, exercise_interactions=False):
            calls.append(exercise_interactions)
            if len(calls) == 1:
                raise AgentCallError(
                    "Gemini planner preflight failed: "
                    "Gemini planner preflight exceeded 60.0s"
                )

    preflight_with_network_recovery(
        Planner(),
        exercise_interactions=True,
        recovery_label="test startup",
        sleep_fn=sleeps.append,
    )

    assert calls == [True, True]
    assert sleeps == [10.0]


def test_offline_replay_reconstructs_and_skips_completed_context(tmp_path):
    feature = tmp_path / "feature.npz"
    save_verifier_input(feature, _verifier_input(), metadata={
                "schema_version": "candidate-verifier-input-v3",
                "record_id": "record-1",
                "snapshot_id": "snapshot-1",
                "target_policy_id": "policy-1",
                "label_version": FIXED_BUDGET_50_LABEL_VERSION,
                "label_contract_hash": FIXED_BUDGET_50_CONTRACT.contract_hash,
            })
    context = {
        "record_id": "record-1",
        "snapshot_id": "snapshot-1",
        "snapshot_hash": "snapshot-hash",
        "data_split": "train",
        "fresh_feature_output_path": str(feature),
    }
    label = {
        "record_id": "record-1",
        "policy_id": "policy-1",
        "label_version": FIXED_BUDGET_50_LABEL_VERSION,
        "source": "counterfactual_replay",
        "snapshot_hash": "snapshot-hash",
        "data_split": "train",
        "verifier_feature_path": str(feature),
        "branches": 16,
        "successes": 0,
        "p_expansion": 1.0,
        "weak": False,
        "weight": 1.0,
        "label_config": label_contract_payload(),
    }
    branches = [
        {
            "event": "COUNTERFACTUAL_BRANCH_COMPLETED",
            "record_id": "record-1",
            "policy_id": "policy-1",
            "branch_index": index,
            "success": False,
            "label_version": FIXED_BUDGET_50_LABEL_VERSION,
            "label_contract_hash": FIXED_BUDGET_50_CONTRACT.contract_hash,
        }
        for index in range(16)
    ]

    result = _completed_replay_result(
        context,
        policy_id="policy-1",
        label_version=FIXED_BUDGET_50_LABEL_VERSION,
        source="counterfactual_replay",
        contract=FIXED_BUDGET_50_CONTRACT,
        labels=[label],
        branch_events=branches,
    )

    assert result is not None
    assert result.branches == 16
    assert result.successes == 0
    assert result.p_expansion == 1.0
    assert result.label_attached is False
    assert (
        _completed_replay_result(
            context,
            policy_id="policy-1",
            label_version=FIXED_BUDGET_50_LABEL_VERSION,
            source="counterfactual_replay",
            contract=FIXED_BUDGET_50_CONTRACT,
            labels=[],
            branch_events=branches,
        )
        is None
    )
    with pytest.raises(ValueError, match="branches are incomplete"):
        _completed_replay_result(
            context,
            policy_id="policy-1",
            label_version=FIXED_BUDGET_50_LABEL_VERSION,
            source="counterfactual_replay",
            contract=FIXED_BUDGET_50_CONTRACT,
            labels=[label],
            branch_events=branches[:-1],
        )


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
        controller_mode="fixed_budget_50",
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
    # This test isolates atomic deployment; prerequisite integrity is exercised
    # by test_mandatory_demos against real ticket/training artifacts.
    worker._require_current_task_training = lambda current: {}
    store.annotate(job.job_id, expected_state=SlowLoopState.RAW_REGRESSION,
                   metadata={"current_task_training_evidence": {}, "registered_delta_path":str(winner_checkpoint)})
    assert worker.step(job.job_id).state is SlowLoopState.TRIGGER_RECHECK
    assert worker.step(job.job_id).state is SlowLoopState.POLICY_STAGED
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
    assert registry.active().controller_mode == "fixed_budget_50"
    signatures = list(IncidentMemory(tmp_path / "incidents").signatures.iter_valid())
    assert len(signatures) == 1
    signature = signatures[0]
    assert signature["event"] == "CAPABILITY_SIGNATURE_RECORDED"
    assert signature["policy_id"] == "p1"
    assert not signature["validated"]
    assert not signature["trigger_recheck_passed"]
    assert signature["metadata"]["current_task_evaluation"]["passed"]
    assert signature["metadata"]["use_status"] == "evidence_only_requires_current_policy_validation"
    assert signature["metadata"]["signature_reuse_enabled"]
    assert np.load(signature["e_goal_path"], allow_pickle=False).shape == (2048,)
    # Retrying a committed deployment finishes the label append without a new
    # registry revision or duplicate label.
    worker._deploy(store.current(job.job_id))
    assert registry.active().deployment_revision == 2
    assert len(list(IncidentMemory(tmp_path / "incidents").signatures.iter_valid())) == 1


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
                                "operator_instruction_zh": "从把手正中央接近并抓取。",
                            }
                        ],
                        "must_demonstrate": ["抓住把手后拉开上层抽屉。"],
                        "must_avoid": ["不要碰撞抽屉面板。"],
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
        == "gpt-6-astra"
    )
    assert calls[0]["model"] == TICKET_PLANNER_MODEL
    assert collection.coverage_axes[0].axis == "handle_approach_side"


def test_ticket_planner_rejects_noncontract_model():
    with pytest.raises(ValueError, match="requires gpt-6-astra"):
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
                            {"axis": "handle_type", "value": "bar", "quota": 5, "operator_instruction_zh": "横向把手"},
                            {"axis": "handle_type", "value": "knob", "quota": 5, "operator_instruction_zh": "旋钮把手"},
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


def test_slow_worker_closes_lookup_and_code_owned_ticket_path(tmp_path, monkeypatch):
    monkeypatch.setattr(SlowLoopWorker, '_select_precollected_demonstrations',
        lambda *args: ({'precollected_demonstrations':True}, ()))
    monkeypatch.setattr("mode_gate.experience_planner.ExperiencePlanner.run",
        lambda *args, **kwargs: {"remedy":None,"reason":"没有合适的历史 remedy"})
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
    assert result.state is SlowLoopState.DATASET_READY
    assert result.ticket_id
    ticket = json.loads(Path(result.metadata["ticket_path"]).read_text())
    assert ticket["eval_split"] == "regression"
    assert set(ticket["init_state_ids"]).isdisjoint(ticket["eval_init_state_ids"])
    assert result.metadata["lookup_match_count"] == 0


def test_slow_worker_automatically_starts_and_completes_teleop(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "joint-eval-manifest-v1",
                "manifest_sha256": "manifest",
                "tasks": [],
            }
        ),
        encoding="utf-8",
    )
    ticket_path = tmp_path / "tickets/ticket-1/ticket.json"
    ticket_path.parent.mkdir(parents=True)
    ticket_path.write_text(json.dumps({"ticket_id": "ticket-1"}), encoding="utf-8")
    service_record = tmp_path / "service.json"
    service_record.write_text("{}", encoding="utf-8")
    completion = tmp_path / "completion.json"
    completion.write_text("{}", encoding="utf-8")

    class Supervisor:
        def ensure_running(self, job):
            assert job.state is SlowLoopState.AWAITING_DEMOS
            return TeleopServiceResult(
                state="ready",
                url="http://127.0.0.1:8765/",
                job_id=job.job_id,
                ticket_id="ticket-1",
                collection_round=1,
                pid=123,
                service_record_path=str(service_record),
                completion_path=str(completion),
            )

        def poll(self, job):
            assert job.state is SlowLoopState.COLLECTING
            return TeleopServiceResult(
                state="complete",
                url="http://127.0.0.1:8765/",
                job_id=job.job_id,
                ticket_id="ticket-1",
                collection_round=1,
                service_record_path=str(service_record),
                completion_path=str(completion),
            )

    store = SlowLoopStore(tmp_path / "slow")
    job = store.create(
        active_policy_id="p0",
        input_hash="input",
        metadata={"ticket_path": str(ticket_path), "collection_round": 1},
    )
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
            ticket_id="ticket-1" if state is SlowLoopState.AWAITING_DEMOS else None,
        )
    worker = SlowLoopWorker(
        store=store,
        registry=PolicyRegistry(tmp_path / "registry"),
        incidents=IncidentMemory(tmp_path / "incidents"),
        protocol_manifest=manifest_path,
        ticket_root=tmp_path / "tickets",
        work_root=tmp_path / "work",
        teleop_supervisor=Supervisor(),
    )
    collecting = worker.step(job.job_id)
    assert collecting.state is SlowLoopState.COLLECTING
    assert collecting.metadata["teleop_auto_started"] is True
    assert collecting.metadata["teleop_url"] == "http://127.0.0.1:8765/"
    curating = worker.step(job.job_id)
    assert curating.state is SlowLoopState.CURATING
    assert curating.metadata["teleop_collection_complete"] is True


def test_teleop_health_bypasses_provider_proxy(monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from mode_gate.teleop_supervisor import TeleopSupervisor

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/healthz"
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"service":"vls-teleop","ready":true}')

        def log_message(self, *args):
            pass

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(key, "http://127.0.0.1:1")
    for key in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        supervisor = TeleopSupervisor.__new__(TeleopSupervisor)
        supervisor.port = server.server_address[1]
        assert supervisor._health() == {"service": "vls-teleop", "ready": True}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("state", [
    SlowLoopState.EXPANSION_TRIGGERED, SlowLoopState.AWAITING_DEMOS,
    SlowLoopState.COLLECTING, SlowLoopState.CURATING,
    SlowLoopState.NEEDS_MORE_DEMOS, SlowLoopState.RETRYABLE_ERROR,
])
def test_expansion_demo_barrier_rejects_incomplete_collection(tmp_path, state):
    from mode_gate.expansion_automation import expansion_demonstrations_ready

    info = tmp_path / "dataset/meta/info.json"
    info.parent.mkdir(parents=True)
    info.write_text('{"total_episodes":15}')
    job = SimpleNamespace(state=state, metadata={
        "teleop_auto_started": True, "teleop_collection_complete": True,
        "curation_needs_more_demos": False,
        "current_ticket_dataset_path": str(info.parent.parent),
    })
    assert not expansion_demonstrations_ready(job)


def test_expansion_demo_barrier_waits_before_fast_loop_continues(tmp_path, monkeypatch):
    from mode_gate import expansion_automation

    info = tmp_path / "dataset/meta/info.json"
    info.parent.mkdir(parents=True)
    info.write_text('{"total_episodes":1}')
    job = SimpleNamespace(
        state=SlowLoopState.AWAITING_DEMOS, sequence=0, ticket_id="ticket-current",
        metadata={"task_id": "current-task", "collection_round": 1},
    )
    events = []

    class Store:
        def current(self, job_id):
            assert job_id == "job-current"
            return job

    def collect(_):
        assert events[-1]["state"] == "WAITING_FOR_DEMONSTRATIONS"
        job.sequence += 1
        if job.sequence == 1:
            job.state = SlowLoopState.CURATING
            job.metadata["teleop_collection_complete"] = True
        else:
            job.state = SlowLoopState.DATASET_READY
            job.metadata.update(
                curation_needs_more_demos=False,
                current_ticket_dataset_path=str(info.parent.parent),
            )

    monkeypatch.setattr(expansion_automation.time, "sleep", collect)
    expansion_automation.wait_for_expansion_demonstrations(
        store=Store(), job_id="job-current", on_update=events.append,
    )
    assert [x["state"] for x in events] == [
        "WAITING_FOR_DEMONSTRATIONS", "WAITING_FOR_DEMONSTRATIONS",
        "DEMONSTRATIONS_READY",
    ]
    assert job.state is SlowLoopState.DATASET_READY


def test_expansion_demo_barrier_does_not_accept_empty_or_missing_dataset(tmp_path):
    from mode_gate.expansion_automation import expansion_demonstrations_ready

    job = SimpleNamespace(state=SlowLoopState.DATASET_READY, metadata={
        "curation_needs_more_demos": False,
        "current_ticket_dataset_path": str(tmp_path / "dataset"),
    })
    assert not expansion_demonstrations_ready(job)
    info = tmp_path / "dataset/meta/info.json"
    info.parent.mkdir(parents=True)
    info.write_text('{"total_episodes":0}')
    assert not expansion_demonstrations_ready(job)
    info.write_text('{"total_episodes":1}')
    assert expansion_demonstrations_ready(job)


def test_expansion_worker_launcher_detaches_managed_collection(tmp_path, monkeypatch):
    from mode_gate import expansion_automation

    python = tmp_path / "python"
    python.touch()
    calls = []

    class Process:
        pid = 424242

        def wait(self):
            return 0

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return Process()

    monkeypatch.setattr(expansion_automation.subprocess, "Popen", popen)
    repo_root = Path(__file__).resolve().parents[1]
    record = expansion_automation.launch_expansion_worker(
        job_id="job-1",
        repo_root=repo_root,
        persistent_root=tmp_path / "persistent",
        slow_loop_root=tmp_path / "persistent/slow_loop",
        registry_root=tmp_path / "persistent/registry",
        incident_root=tmp_path / "persistent/incidents",
        snapshot_root=tmp_path / "persistent/snapshots",
        python_executable=python,
        operator="operator",
    )
    command, kwargs = calls[0]
    assert record["launch_status"] == "launched"
    assert record["teleop_url"] == "http://127.0.0.1:8765/"
    assert "--auto-teleop" in command
    assert "--watch-collection" in command
    assert command[command.index("--job-id") + 1] == "job-1"
    assert kwargs["start_new_session"] is True


def test_expansion_full_cycle_barrier_waits_through_training(tmp_path, monkeypatch):
    from mode_gate import expansion_automation
    info = tmp_path / "dataset/meta/info.json"
    info.parent.mkdir(parents=True)
    info.write_text('{"total_episodes":1}')
    job = SimpleNamespace(state=SlowLoopState.TRAINING, sequence=0, ticket_id="t",
                          metadata={"curation_needs_more_demos": False,
                                    "current_ticket_dataset_path": str(info.parent.parent)})
    seen = []

    def complete(_):
        assert seen[-1]["state"] == "WAITING_FOR_SLOW_LOOP"
        job.state = SlowLoopState.DEPLOYED
        job.sequence += 1

    monkeypatch.setattr(expansion_automation.time, "sleep", complete)
    expansion_automation.wait_for_expansion_demonstrations(
        store=SimpleNamespace(current=lambda _: job), job_id="job",
        wait_for_completion=True, on_update=seen.append)
    assert seen[-1]["state"] == "SLOW_LOOP_COMPLETE"


def test_teleop_portal_survives_queue_backend_and_proxies_websocket(monkeypatch):
    import socket
    import threading
    import uvicorn
    from fastapi import FastAPI, WebSocket
    from fastapi.responses import HTMLResponse
    from fastapi.testclient import TestClient
    from mode_gate.teleop_supervisor import create_teleop_portal_app

    backend = FastAPI()
    queue = {"active": False}

    @backend.get("/healthz")
    def health():
        return {"service": "vls-teleop", "ready": True,
                "queue_complete": not queue["active"]}

    @backend.get("/", response_class=HTMLResponse)
    def index():
        return "<h1>Current task</h1>"

    @backend.websocket("/ws")
    async def echo(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("initial-frame")
        await websocket.send_text(await websocket.receive_text())
        await websocket.close()

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(backend, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)
    try:
        app = create_teleop_portal_app(backend_port=port, service_token="test")
        with TestClient(app) as client:
            assert "入口在线" in client.get("/").text
            queue["active"] = True
            assert "Current task" in client.get("/").text
            with client.websocket_connect("/ws") as websocket:
                assert websocket.receive_text() == "initial-frame"
                websocket.send_text("test-only-no-simulator")
                assert websocket.receive_text() == "test-only-no-simulator"
            queue["active"] = False
            assert "入口在线" in client.get("/").text
            server.should_exit = True
            thread.join(timeout=5)
            assert client.get("/healthz").json()["ready"] is True
            assert "入口在线" in client.get("/").text
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


def test_full_cycle_executes_generated_jobs_in_order(tmp_path, monkeypatch):
    from dataclasses import replace
    from mode_gate import slow_worker as module

    store = SlowLoopStore(tmp_path / "slow")
    job = store.create(active_policy_id="p", input_hash="input")
    current = [replace(job, state=SlowLoopState.TRAINING, metadata={
        "training_job_path": "training.json", "policy_gate_job_path": "gate.json",
        "new_policy_counterfactual_job_spec_path": "replay.json"})]
    monkeypatch.setattr(store, "current", lambda _: current[0])
    completed = []
    states = {SlowLoopState.TRAINING: ("training.json", SlowLoopState.RAW_REGRESSION),
              SlowLoopState.RAW_REGRESSION: ("gate.json", SlowLoopState.NEW_POLICY_COUNTERFACTUAL),
              SlowLoopState.NEW_POLICY_COUNTERFACTUAL: ("replay.json", SlowLoopState.DEPLOYED)}

    def step(_):
        name, next_state = states[current[0].state]
        if name in completed:
            current[0] = replace(current[0], state=next_state, sequence=current[0].sequence + 1)
        return current[0]

    def execute(path):
        completed.append(str(path))
        return {"launched": True, "completed": True}

    worker = module.SlowLoopWorker.__new__(module.SlowLoopWorker)
    worker.store = store
    worker.work_root = tmp_path / "work"
    worker.teleop_supervisor = object()
    monkeypatch.setattr(worker, "step", step)
    monkeypatch.setattr(module, "execute_job_spec", execute)
    result = worker.run_full_cycle(job.job_id)
    assert result.state is SlowLoopState.DEPLOYED
    assert completed == ["training.json", "gate.json", "replay.json"]


def test_coft_preserves_native_fps_and_ignores_display_names(tmp_path):
    sources = []
    for name, fps in (("new", 20), ("replay", 10)):
        root = tmp_path / name
        (root / "meta").mkdir(parents=True)
        (root / "meta/info.json").write_text(json.dumps({
            "fps": fps, "total_frames": 5, "total_episodes": 1,
            "features": {"action": {"dtype": "float32", "shape": [7],
                                       "names": [name], "fps": fps}},
        }))
        sources.append(root)
    hashes = [sha256_file(root / "meta/info.json") for root in sources]
    value = prepare_source_catalog(
        catalog_root=tmp_path / "catalog", manifest_path=tmp_path / "sources.json",
        new_datasets={"vls/new": sources[0]}, old_ticket_datasets={},
        replay_datasets={"libero/replay": sources[1]}, seed=17)
    assert value["fps_by_repo"] == {"vls/new": 20, "libero/replay": 10}
    assert hashes == [sha256_file(root / "meta/info.json") for root in sources]
    assert value["datasets"]["libero/replay"]["temporal_alignment"] == "native_policy_step_indices_no_resampling"


def test_raw_gate_reuses_warm_model_across_contexts(tmp_path, monkeypatch):
    import sys
    from mode_gate.policy_evaluator import HydraRawEpisodeExecutor, EvaluationContext

    constructed = []
    runs = []

    class Adapter:
        def __init__(self, env=None, config=None, device=None):
            self.current_task_idx = 0
            self.episode_step = 7
            self._env = [SimpleNamespace(num_steps_wait=5, _env=SimpleNamespace(
                env=SimpleNamespace(done=False, timestep=12, horizon=720)))]

        def close(self):
            pass

        def get_context_provenance(self):
            return {"runtime_suite": "libero_10_lan", "task_id": "task",
                    "init_state_id": str(runs[-1])}

    class Runner:
        def __init__(self, cfg):
            constructed.append(True)
            self.cfg, self.config = cfg, cfg.main
            self.adapter, self.device = Adapter(), "cuda:6"

        def run(self):
            runs.append(self.config.init_state_id)
            self.success_count = 1

    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(Main=Runner))
    executor = HydraRawEpisodeExecutor(
        repo_root=Path(__file__).resolve().parents[1], python_executable=Path(sys.executable),
        output_root=tmp_path, extra_overrides=("device=cuda:6",), keep_warm=True)
    for state in (21, 22):
        context = EvaluationContext(suite="libero_10", task_id="task", task_index=2,
            perturbation_variant="use_language", init_state_id=str(state), env_seed=1, policy_seed=1)
        assert executor("policy", tmp_path / "checkpoint", context).success
    assert len(constructed) == 1
    assert list(map(str, runs)) == ["21", "22"]




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
    assert [item.alpha_l for item in rank_current_task_candidates(scores)] == [0.4, 0.6, 0.8, 0.2]
    decision = raw_promotion_decision(
        parent_current_sr=0.55,
        current_task_scores=scores,
        forgetting={"p0": 0.0, "p1": 0.04, "p2": 0.01, "p3": 0.0},
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
        policy_id="p1", verifier_id=None, controller_mode="fixed_budget_50",
        manifest_hash="m", expected_revision=0,
    )
    assert active.deployment_revision == 1
    with pytest.raises(RuntimeError):
        registry.promote(
            policy_id="p1", verifier_id=None, controller_mode="fixed_budget_50",
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
    lineage = [DeltaLineageEntry("d1", str(delta1), alpha_v=0.4, alpha_l=0.4, alpha_a=0.4)]
    expansion = compose_expansion_candidates(
        theta0_checkpoint=theta0,
        parent_policy_id="p1",
        accepted_lineage=lineage,
        new_delta_id="d2",
        new_delta_path=delta2,
        output_root=tmp_path / "expansion",
        alpha_l_values=[0.2, 0.4, 0.6, 0.8],
    )
    assert [item["alpha_l"] for item in expansion["candidates"]] == [0.2, 0.4, 0.6, 0.8]
    candidate = Path(expansion["candidates"][0]["checkpoint_path"])
    index = json.loads((candidate / "model.safetensors.index.json").read_text())
    language_key = "model.paligemma_with_expert.paligemma.model.language_model.x"
    with safe_open(candidate / index["weight_map"][language_key], framework="pt", device="cpu") as handle:
        torch.testing.assert_close(handle.get_tensor(language_key), values[language_key] + 0.4)

    reuse = compose_selected_remedy(
        theta0_checkpoint=theta0,
        parent_policy_id="p1",
        accepted_lineage=lineage,
        target_delta_id="d1",
        target_delta_path=delta1, alpha_l_values=[0.1, 0.6, 0.95],
        output_root=tmp_path / "reuse",
    )
    resumed = compose_selected_remedy(
        theta0_checkpoint=theta0,
        parent_policy_id="p1",
        accepted_lineage=lineage,
        target_delta_id="d1",
        target_delta_path=delta1, alpha_l_values=[0.1, 0.6, 0.95],
        output_root=tmp_path / "reuse",
    )
    assert reuse == resumed
    assert [item["alpha_l"] for item in reuse["candidates"]] == [0.1, 0.6, 0.95]
    external = compose_selected_remedy(theta0_checkpoint=theta0,parent_policy_id="p1",
        accepted_lineage=lineage,target_delta_id="d2",target_delta_path=delta2,
        alpha_l_values=[0.3],output_root=tmp_path/"external_remedy")
    restored = Path(external["candidates"][0]["checkpoint_path"])
    merge_index = json.loads((restored/"model.safetensors.index.json").read_text())
    with safe_open(restored/merge_index["weight_map"][language_key],framework="pt",device="cpu") as handle:
        torch.testing.assert_close(handle.get_tensor(language_key),values[language_key]+0.5)


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


def test_snapshot_restore_discards_a_bounded_stale_egl_frame(tmp_path):
    class StaleFirstFrameAdapter(_SnapshotAdapter):
        def __init__(self):
            super().__init__()
            self.rendered_frames = 0

        def get_vlm_image(self):
            self.rendered_frames += 1
            if self.rendered_frames == 1:
                return np.full_like(self.image, 255)
            return self.image

    adapter, policy = StaleFirstFrameAdapter(), _SnapshotPolicy()
    store = DecisionSnapshotStore(tmp_path)
    snapshot = store.capture(
        adapter=adapter,
        policy=policy,
        policy_id="p0",
        controller_state={},
        provenance={},
        observation_image=adapter.image,
    )

    result = store.restore(snapshot.snapshot_id, adapter=adapter, policy=policy)

    assert result["rgb_mean_absolute_error"] == 0
    assert adapter.rendered_frames == 2


def test_snapshot_restore_still_fails_closed_after_stale_frame_retries(tmp_path):
    class AlwaysWrongFrameAdapter(_SnapshotAdapter):
        def __init__(self):
            super().__init__()
            self.rendered_frames = 0

        def get_vlm_image(self):
            self.rendered_frames += 1
            return np.full_like(self.image, 255)

    adapter, policy = AlwaysWrongFrameAdapter(), _SnapshotPolicy()
    store = DecisionSnapshotStore(tmp_path)
    snapshot = store.capture(
        adapter=adapter,
        policy=policy,
        policy_id="p0",
        controller_state={},
        provenance={},
        observation_image=adapter.image,
    )

    with pytest.raises(ValueError, match="after 3 renders"):
        store.restore(snapshot.snapshot_id, adapter=adapter, policy=policy)
    assert adapter.rendered_frames == 3


def test_snapshot_restore_refreshes_stale_offscreen_context_once(tmp_path):
    class StaleRendererAdapter(_SnapshotAdapter):
        def __init__(self):
            super().__init__()
            self.rendered_frames = 0
            self.refreshes = 0
            self.stale = True

        def get_vlm_image(self):
            self.rendered_frames += 1
            return np.full_like(self.image, 255) if self.stale else self.image

        def refresh_offscreen_render_context(self):
            self.refreshes += 1
            self.stale = False

    adapter, policy = StaleRendererAdapter(), _SnapshotPolicy()
    store = DecisionSnapshotStore(tmp_path)
    snapshot = store.capture(
        adapter=adapter,
        policy=policy,
        policy_id="p0",
        controller_state={},
        provenance={},
        observation_image=adapter.image,
    )

    result = store.restore(snapshot.snapshot_id, adapter=adapter, policy=policy)

    assert result["rgb_mean_absolute_error"] == 0
    assert adapter.refreshes == 1
    assert adapter.rendered_frames == 4


def test_libero_renderer_refresh_rebuilds_only_gpu_context():
    from core.env_adapters.libero_adapter import LiberoAdapter

    class Call:
        def __init__(self):
            self.count = 0

        def __call__(self):
            self.count += 1

    make_current = Call()
    free = Call()
    rebuild = Call()
    forward = Call()
    context = SimpleNamespace(
        gl_ctx=SimpleNamespace(make_current=make_current),
        con=SimpleNamespace(free=free),
        _set_mujoco_context_and_buffers=rebuild,
    )
    sim = SimpleNamespace(_render_context_offscreen=context, forward=forward)
    adapter = LiberoAdapter.__new__(LiberoAdapter)
    adapter._get_current_robosuite_env = lambda: SimpleNamespace(sim=sim)

    adapter.refresh_offscreen_render_context()

    assert make_current.count == 1
    assert free.count == 1
    assert rebuild.count == 1
    assert forward.count == 1


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
    assert "return task_guidance.status(" in body
    assert "drawer_bowl_task" not in source


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


def test_teleop_health_endpoint_is_render_free_and_identified() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from mode_gate.teleop import create_teleop_app

    class Session:
        def service_status(self):
            return {
                "schema_version": "vls-teleop-session-health-v1",
                "ticket_id": "ticket-1",
                "queue_complete": False,
            }

        def status(self, _message):
            raise AssertionError("health checks must not render a camera frame")

    app = create_teleop_app(
        Session(),
        service_metadata={
            "schema_version": "vls-managed-teleop-health-v1",
            "job_id": "job-1",
            "service_token": "token",
            "collection_round": 1,
            "ticket_id": "ticket-1",
            "ticket_sha256": "a" * 64,
        },
    )
    with TestClient(app) as client:
        payload = client.get("/healthz").json()
    assert payload["ready"] is True
    assert payload["service"] == "vls-teleop"
    assert payload["job_id"] == "job-1"
    assert payload["queue_complete"] is False


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
            return None, 0.0, False, False, {"success": self.value >= 3.0}

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
            return None, 0.0, False, False, {"success": self.value == 1.0}

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


def test_demo_replay_reassessment_uses_native_success_not_state_tolerances(tmp_path):
    output = tmp_path / "demo.hdf5"
    with h5py.File(output, "w") as handle:
        handle.attrs["replay_validation_version"] = "controller-reset-v1"
        handle.attrs["replay_max_state_error"] = 2.9e-3
        handle.attrs["replay_max_qpos_error"] = 3.1e-5
        handle.attrs["replay_max_qvel_error"] = 2.9e-3
        handle.attrs["replay_success_matches"] = True
        handle.attrs["replay_validated"] = False
        handle.attrs["simulator_success"] = True
        handle.attrs["replay_task_success"] = True
        handle.attrs["replay_acceptance_version"] = "physical-state-v1"
    assert reassess_demo_replay(
        output,
        tolerance=1e-15,
        position_tolerance=1e-15,
        velocity_tolerance=1e-15,
    )
    with h5py.File(output, "r") as handle:
        assert bool(handle.attrs["replay_validated"])
        assert handle.attrs["replay_acceptance_version"] == "libero-native-success-v1"
        assert handle.attrs["replay_state_error_role"] == "diagnostic_only"
        assert json.loads(handle.attrs["replay_prior_acceptance_json"])["replay_validated"] is False
        assert handle.attrs["replay_max_state_error"] == 2.9e-3


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
            handle.attrs["simulator_success"] = True
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


def test_policy_promotion_current_task_tradeoff_is_idempotent(tmp_path):
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
        retention_history={"schema_version": "policy-retention-history-v1",
                           "manifest_hash": manifest["manifest_sha256"],
                           "task_keys": [t["task_key"] for t in manifest["tasks"]]},
    )
    first = coordinator.run(
        parent=parent,
        candidates=candidates,
        trigger_evaluator=trigger,
        trigger_identity={"ticket_id": "ticket", "task_key": manifest["tasks"][0]["task_key"]},
    )
    calls = list(evaluator.calls)
    second = coordinator.run(
        parent=parent,
        candidates=candidates,
        trigger_evaluator=trigger,
        trigger_identity={"ticket_id": "ticket", "task_key": manifest["tasks"][0]["task_key"]},
    )

    assert first == second
    assert evaluator.calls == calls
    assert first["alpha_selection"]["episodes"] == 12
    assert first["alpha_selection"]["global_alpha_selection_skipped"]
    assert first["regression"]["episodes"] == 100 - len(manifest["tasks"][0]["splits"]["policy_alpha_selection"])
    assert len(first["regression"]["candidates"]) == 4
    assert first["alpha_selection"]["ranking"][0] == "candidate-06"
    assert not first["tradeoff"]["zero_drop_required"]
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
        controller_mode="fixed_budget_50",
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
        "controller_state": {"retry_index": 0, "failure_count": 1},
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
        "schema_version": "new-policy-counterfactual-plan-v3",
        "policy_id": "policy-2",
        "checkpoint_path": str(checkpoint),
        "checkpoint_digest": checkpoint_digest(checkpoint),
        "snapshot_root": str(snapshots),
        "incident_root": str(incidents),
        "adaptive_branches": [16, 32],
        "decision_rule": "head_argmax",
        "progress_contract": REPLAY_PROGRESS_CONTRACT,
        "label_version": FIXED_BUDGET_50_LABEL_VERSION,
        "label_config": label_contract_payload(),
        "gemini_max_provider_calls": 5000,
        "gemini_call_ledger_path": str((tmp_path / "gemini.jsonl").resolve()),
        "branch_ledger_path": str((tmp_path / "branches.jsonl").resolve()),
        "contexts": [
            {
                "record_id": "record-1",
                "target_policy_id": "policy-2",
                "snapshot_id": "snapshot-1",
                "snapshot_hash": "a" * 64,
                "snapshot_manifest_path": str(manifest_path.resolve()),
                "data_split": "train",
                "label_version": FIXED_BUDGET_50_LABEL_VERSION,
                "budget_state": regenerate_budget_state(
                    {"retry_index": 0, "failure_count": 1}
                ),
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

    application = HgpuReplayApplication.__new__(HgpuReplayApplication)
    progress = application.progress_observer(
        adapter=None,
        before={"completed_count": 1},
        after={"completed_count": 2, "goal_count": 3},
        task_success=False,
    )
    assert progress.advanced
    assert progress.stage_id == "bddl-goals:2/3"
    regressed = application.progress_observer(
        adapter=None,
        before={"completed_count": 2},
        after={"completed_count": 1, "goal_count": 3},
        task_success=False,
    )
    assert not regressed.advanced


def test_offline_progress_uses_post_action_gemini_stage_and_prefetches_next_mode():
    application = HgpuReplayApplication.__new__(HgpuReplayApplication)
    application._prefetched_selections = {}
    post_semantic = SimpleNamespace(
        observed_stage_id="stage_2",
        stage_confidence=0.95,
        model="gemini-robotics-er-2-preview",
        prompt_version="mode-scorer-v3",
    )
    post_selected = SimpleNamespace(
        sample_index=0,
        candidate_id="mode-post",
        sample_id="sample-post",
    )
    post_analysis = SimpleNamespace(
        selected=post_selected,
        execution_actions=np.zeros((1, 10, 7), dtype=np.float32),
        semantic=post_semantic,
    )
    application._sample_and_analyze = lambda condition, purpose: post_analysis
    current = FreshCandidateSelection(
        actions=np.zeros((10, 7), dtype=np.float32),
        candidate_id="mode-pre",
        sample_index=0,
        metadata={
            "semantic_observed_stage_id": "stage_1",
            "semantic_stage_confidence": 0.98,
        },
    )
    next_condition = SamplingCondition(seed=11, retry_index=1)
    progress = application.progress_observer(
        adapter=None,
        before={"completed_count": 0},
        after={"completed_count": 0, "goal_count": 1},
        task_success=False,
        selection=current,
        next_condition=next_condition,
        cache_next_selection=True,
    )
    assert progress.advanced
    assert progress.stage_id == "stage_2"
    assert progress.source == "gemini_planner"
    assert next_condition not in application._prefetched_selections

    post_semantic.observed_stage_id = "stage_1"
    no_progress = application.progress_observer(
        adapter=None,
        before={"completed_count": 0},
        after={"completed_count": 0, "goal_count": 1},
        task_success=False,
        selection=current,
        next_condition=next_condition,
        cache_next_selection=True,
    )
    assert not no_progress.advanced
    assert application._prefetched_selections[next_condition].candidate_id == "mode-post"

    application._prefetched_selections.clear()
    current = FreshCandidateSelection(
        actions=np.zeros((10, 7), dtype=np.float32),
        candidate_id="mode-pre",
        sample_index=0,
        metadata={
            "semantic_observed_stage_id": "stage_2",
            "semantic_stage_confidence": 0.98,
        },
    )
    regressed = application.progress_observer(
        adapter=None,
        before={"completed_count": 0},
        after={"completed_count": 0, "goal_count": 1},
        task_success=False,
        selection=current,
        next_condition=next_condition,
        cache_next_selection=True,
    )
    assert not regressed.advanced


def test_counterfactual_replay_rejects_forced_expansion_without_retry_budget():
    with pytest.raises(ValueError, match="actionable remaining budget"):
        FixedBudgetResteerExecutor(
            fresh_sampler=lambda **kwargs: None,
        )(
            adapter=object(),
            policy=object(),
            branch_seed=1,
            remaining_budget=0,
            controller_state={"retry_index": 4},
        )


def test_verifier_audit_uses_only_versioned_shards_and_writes_replay_job(tmp_path):
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
        controller_mode="fixed_budget_50",
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
    assert report["experimental_increment"]
    assert report["scheduled_context_count"] == 8
    assert report["verifier_opportunities"] == 0
    assert Path(report["replay_job_path"]).is_file()
    assert validate_replay_plan(report["replay_plan_path"])["contexts"] == []
    replay_job = json.loads(Path(report["replay_job_path"]).read_text())
    assert replay_job["preferred_gpu_index"] == 6
    assert replay_job["command"][-1] == "cuda:6"


def test_verifier_audit_excludes_forced_expansion_without_retry_choice(tmp_path):
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
    source = tmp_path / "source"
    source.mkdir()
    save_file({"weight": torch.ones(1)}, str(source / "model.safetensors"))
    registry = PolicyRegistry(tmp_path / "registry")
    registry.install_artifact("policy", "policy-a", source)
    registry.promote(
        policy_id="policy-a",
        verifier_id=None,
        controller_mode="fixed_budget_50",
        manifest_hash=manifest["manifest_sha256"],
        expected_revision=0,
    )

    context = audit_contexts_from_manifest(manifest, limit=1)[0]
    group = {
        "suite": context.evaluation.suite,
        "task_id": context.evaluation.task_id,
        "perturbation_variant": context.evaluation.perturbation_variant,
        "init_state_id": context.evaluation.init_state_id,
    }
    incidents = IncidentMemory(tmp_path / "incidents")
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()
    for record_id, snapshot_id, budget, route in (
        ("actionable", "snapshot-actionable", 10, "RE-STEER"),
        ("forced", "snapshot-forced", 0, "EXPANSION"),
    ):
        directory = snapshot_root / snapshot_id
        directory.mkdir()
        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    "snapshot_id": snapshot_id,
                    "snapshot_hash": "a" * 64,
                    "controller_state": {
                        "retry_index": 50 - budget,
                        "failure_count": 1,
                    },
                }
            ),
            encoding="utf-8",
        )
        incidents.record_decision(
            VerifierDecisionRecord(
                record_id=record_id,
                context_id=record_id,
                policy_id="policy-a",
                snapshot_id=snapshot_id,
                snapshot_hash="a" * 64,
                scene_feature_path="",
                route=route,
                verifier_decision=None,
                verifier_logits=None,
                p_expansion=None,
                decision_rule="fixed_budget_50",
                controller_mode="fixed_budget_50",
                failure_count=1,
                remaining_budget=budget,
                retry_index=50 - budget,
                provenance={"group": group, "code_revision": "audit-filter-v1"},
            )
        )

    class Executor:
        repo_root = Path(__file__).resolve().parents[1]
        python_executable = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")
        code_revision = "audit-filter-v1"

        def __call__(self, policy_id, audit_context):
            return RawEpisodeResult(success=False, output_dir=str(tmp_path / "episode"))

    report = AuditCollectionCoordinator(
        manifest=manifest,
        registry=registry,
        incidents=incidents,
        snapshot_root=snapshot_root,
        executor=Executor(),
        ledger_path=tmp_path / "audit.jsonl",
        output_path=tmp_path / "collection.json",
        replay_plan_path=tmp_path / "replay" / "plan.json",
    ).run(limit=1)
    plan = validate_replay_plan(Path(report["replay_plan_path"]))
    assert [item["record_id"] for item in plan["contexts"]] == ["actionable"]
    assert report["excluded_forced_expansion"] == 1
    assert plan["progress_contract"] == REPLAY_PROGRESS_CONTRACT


def test_verifier_audit_commits_each_episode_before_later_failure(tmp_path):
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
    source = tmp_path / "source"
    source.mkdir()
    save_file({"weight": torch.ones(1)}, str(source / "model.safetensors"))
    registry = PolicyRegistry(tmp_path / "registry")
    registry.install_artifact("policy", "policy-a", source)
    registry.promote(
        policy_id="policy-a",
        verifier_id=None,
        controller_mode="fixed_budget_50",
        manifest_hash=manifest["manifest_sha256"],
        expected_revision=0,
    )

    class Executor:
        repo_root = Path(__file__).resolve().parents[1]
        python_executable = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")
        code_revision = "audit-streaming-test"

        def __init__(self):
            self.calls = 0

        def __call__(self, policy_id, context):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("injected interruption")
            return RawEpisodeResult(
                success=False,
                output_dir=str(tmp_path / context.episode_key),
            )

    executor = Executor()
    ledger_path = tmp_path / "audit.jsonl"
    coordinator = AuditCollectionCoordinator(
        manifest=manifest,
        registry=registry,
        incidents=IncidentMemory(tmp_path / "incidents"),
        snapshot_root=tmp_path / "snapshots",
        executor=executor,
        ledger_path=ledger_path,
        output_path=tmp_path / "collection.json",
        replay_plan_path=tmp_path / "replay" / "plan.json",
        max_workers=1,
    )
    with pytest.raises(RuntimeError, match="injected interruption"):
        coordinator.run(limit=2)

    completed = EpisodeLedger(ledger_path).completed_for(
        policy_id="policy-a",
        manifest_hash=manifest["manifest_sha256"],
        code_revision=executor.code_revision,
    )
    assert len(completed) == 1


def test_verifier_audit_defers_retryable_context_and_keeps_collecting(tmp_path):
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
    source = tmp_path / "source"
    source.mkdir()
    save_file({"weight": torch.ones(1)}, str(source / "model.safetensors"))
    registry = PolicyRegistry(tmp_path / "registry")
    registry.install_artifact("policy", "policy-a", source)
    registry.promote(
        policy_id="policy-a",
        verifier_id=None,
        controller_mode="fixed_budget_50",
        manifest_hash=manifest["manifest_sha256"],
        expected_revision=0,
    )

    expected = audit_contexts_from_manifest(manifest, limit=2)

    class Executor:
        repo_root = Path(__file__).resolve().parents[1]
        python_executable = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")
        code_revision = "audit-keep-going-test"

        def __init__(self):
            self.calls = []

        def __call__(self, policy_id, context):
            self.calls.append(context.episode_key)
            if context == expected[0] and self.calls.count(context.episode_key) == 1:
                raise RuntimeError("transient provider timeout")
            return RawEpisodeResult(
                success=False,
                output_dir=str(tmp_path / context.episode_key),
            )

    executor = Executor()
    AuditCollectionCoordinator(
        manifest=manifest,
        registry=registry,
        incidents=IncidentMemory(tmp_path / "incidents"),
        snapshot_root=tmp_path / "snapshots",
        executor=executor,
        ledger_path=tmp_path / "audit.jsonl",
        output_path=tmp_path / "collection.json",
        replay_plan_path=tmp_path / "replay" / "plan.json",
        max_workers=1,
        continue_on_retryable_error=True,
    ).run(limit=2)

    assert executor.calls == [
        expected[0].episode_key,
        expected[1].episode_key,
        expected[0].episode_key,
    ]
    assert len(EpisodeLedger(tmp_path / "audit.jsonl").completed()) == 2


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
    assert first.controller_mode == "fixed_budget_50"
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


def test_reuse_policy_gate_scores_current_task_and_forgetting_for_every_candidate(tmp_path):
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
        retention_history={"schema_version": "policy-retention-history-v1",
                           "manifest_hash": manifest["manifest_sha256"],
                           "task_keys": [t["task_key"] for t in manifest["tasks"]]},
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
        parent=parent, candidates=candidates, trigger_evaluator=trigger,
        trigger_identity={"ticket_id":"reuse-ticket","task_key":manifest["tasks"][0]["task_key"]})
    assert report["gate_kind"] == "REUSE" and len(report["trigger_recheck"]) == len(candidates)


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
    assert first.controller_mode == "fixed_budget_50"
    assert first.verifier_id is None

    verifier = tmp_path / "verifier"
    from mode_gate.verifier import save_verifier_artifact
    save_verifier_artifact(verifier, model=GroundedCapabilityVerifier(),standardizer=FeatureStandardizer(),
        calibrator=PlattCalibrator(1.,0.),metadata={"policy_id":"policy-1",
            "label_version":FIXED_BUDGET_50_LABEL_VERSION,"label_config":label_contract_payload(),
            "backbone_id":"v44-test", "metrics":{"independent":{"contexts":1}},
            "planner_deployment_review":{"accept":True,"planner_provenance":{
                "planner_thread_id":"01a0893c-15b0-7203-881c-de3c5bcee058"}}})
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
