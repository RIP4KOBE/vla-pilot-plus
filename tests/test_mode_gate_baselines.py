from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch
from torch import nn
from safetensors import safe_open
from safetensors.torch import save_file

from mode_gate.baselines import (
    AlwaysExpandRetainRouter,
    BaselineOpportunity,
    ClareAdapter,
    ClareConfig,
    ClareExpandableFFN,
    ClareSystem,
    FixedBudgetRouter,
    GeometryGateRouter,
    MatchedRandomRouter,
    ModeCountGateRouter,
    OracleRouter,
    ResteerOnlyRouter,
    SemanticGateRouter,
    VerifierNoLookupRouter,
    build_baseline_router,
    freeze_baseline_suite,
)
from mode_gate.candidates import compose_retain_expansion_candidates
from mode_gate.config import ModeGateConfig
from mode_gate.checkpoint_math import checkpoint_digest, extract_full_delta
from mode_gate.clare_integration import (
    Pi05ClareIntegration,
    default_pi05_clare_config,
    load_clare_artifact,
    save_clare_artifact,
    train_clare_stage,
)
from mode_gate.eval_manifest import FinalSealGuard, generate_joint_manifest
from mode_gate.final_evaluation import (
    FinalEvaluationSubject,
    FinalSealedEvaluationCoordinator,
)
from mode_gate.job_runner import execute_job_spec
from mode_gate.policy_evaluator import RawEpisodeResult
from mode_gate.incidents import IncidentMemory
from mode_gate.registry import PolicyRegistry
from mode_gate.slow_loop import SlowLoopJob, SlowLoopState, SlowLoopStore
from mode_gate.slow_worker import SlowLoopWorker
from mode_gate.throughput import (
    RolloutThroughputBenchmark,
    throughput_contexts_from_manifest,
)
from mode_gate.state_machine import EpisodeChunkController
from mode_gate.types import ControllerRoute


def _opportunity(**overrides):
    values = {
        "opportunity_id": "op-1",
        "retry_index": 0,
        "active_mode_count": 3,
        "max_semantic_score": 0.8,
        "min_collision_risk": 0.1,
    }
    values.update(overrides)
    return BaselineOpportunity(**values)


def test_baseline_routes_have_frozen_and_unambiguous_semantics():
    assert FixedBudgetRouter(4).decide(_opportunity(retry_index=3)).route is ControllerRoute.RESTEER
    assert FixedBudgetRouter(4).decide(_opportunity(retry_index=4)).route is ControllerRoute.EXPAND
    always = AlwaysExpandRetainRouter().decide(_opportunity())
    assert always.route is ControllerRoute.EXPAND
    assert not always.retain_policy and not always.lookup_enabled
    assert always.merge_method == "retain_uniform"
    assert always.metadata["equation"] == "parent + alpha * (theta_ft - parent)"
    assert ResteerOnlyRouter().decide(_opportunity()).route is ControllerRoute.RESTEER
    assert ModeCountGateRouter(2).decide(
        _opportunity(active_mode_count=1)
    ).route is ControllerRoute.EXPAND
    assert SemanticGateRouter(0.5).decide(
        _opportunity(max_semantic_score=0.49)
    ).route is ControllerRoute.EXPAND
    assert GeometryGateRouter(0.5).decide(
        _opportunity(min_collision_risk=0.51)
    ).route is ControllerRoute.EXPAND
    assert VerifierNoLookupRouter().decide(
        _opportunity(
            learned_verifier_route=ControllerRoute.EXPAND,
            learned_p_expansion=0.2,
        )
    ).route is ControllerRoute.EXPAND
    assert OracleRouter().decide(
        _opportunity(oracle_should_expand=False)
    ).route is ControllerRoute.RESTEER
    with pytest.raises(ValueError, match="learned head decision"):
        VerifierNoLookupRouter().decide(_opportunity())
    with pytest.raises(ValueError, match="oracle"):
        OracleRouter().decide(_opportunity())


def test_retain_baseline_interpolates_every_parameter_group(tmp_path):
    parent = tmp_path / "parent"
    theta_ft = tmp_path / "theta_ft"
    parent.mkdir()
    theta_ft.mkdir()
    base = {
        "model.paligemma_with_expert.paligemma.model.vision_tower.x": torch.tensor([1.0]),
        "model.paligemma_with_expert.paligemma.model.language_model.x": torch.tensor([2.0]),
        "model.action_in_proj.weight": torch.tensor([3.0]),
    }
    trained = {
        key: value + increment
        for (key, value), increment in zip(base.items(), (1.0, 2.0, 3.0))
    }
    save_file(base, parent / "model.safetensors")
    save_file(trained, theta_ft / "model.safetensors")
    delta = tmp_path / "delta"
    extract_full_delta(parent, theta_ft, delta, parent_policy_id="p0")
    grid = compose_retain_expansion_candidates(
        theta0_checkpoint=parent,
        parent_policy_id="p0",
        accepted_lineage=(),
        new_delta_id="delta-1",
        new_delta_path=delta,
        output_root=tmp_path / "candidates",
    )
    first = grid["candidates"][0]
    assert first["alpha_map"] == {
        "vision": 0.2,
        "language": 0.2,
        "action": 0.2,
    }
    assert first["merge_method"] == "retain_uniform"
    checkpoint = Path(first["checkpoint_path"])
    index = json.loads((checkpoint / "model.safetensors.index.json").read_text())
    for (key, before), increment in zip(base.items(), (1.0, 2.0, 3.0)):
        with safe_open(
            checkpoint / index["weight_map"][key], framework="pt", device="cpu"
        ) as handle:
            torch.testing.assert_close(
                handle.get_tensor(key), before + 0.2 * increment
            )


def test_retain_baseline_forces_ticket_and_never_reads_signature_memory(tmp_path):
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
    worker = SlowLoopWorker(
        store=SlowLoopStore(tmp_path / "slow"),
        registry=PolicyRegistry(tmp_path / "registry"),
        incidents=IncidentMemory(tmp_path / "incidents"),
        protocol_manifest=manifest_path,
        ticket_root=tmp_path / "tickets",
        work_root=tmp_path / "work",
    )
    transition = worker._lookup(
        SlowLoopJob(
            job_id="job",
            state=SlowLoopState.LOOKUP_PENDING,
            active_policy_id="p0",
            ticket_id=None,
            input_hash="input",
            output_hash=None,
            sequence=1,
            metadata={
                "baseline_kind": "always_expand_retain",
                "signature_id": "signature",
                "failure_mode": "UNKNOWN",
            },
        )
    )
    assert transition.next_state is SlowLoopState.TICKET_READY
    assert transition.metadata["lookup_disabled"]
    assert transition.metadata["lookup_match_count"] == 0


class _ToySquareFFN(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.up_proj = nn.Linear(width, width * 2, bias=False)
        self.down_proj = nn.Linear(width * 2, width, bias=False)

    def forward(self, value):
        return self.down_proj(torch.relu(self.up_proj(value)))


class _ToyExpertLayer(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.mlp = _ToySquareFFN(width)

    def forward(self, value):
        return value + self.mlp(value)


class _ToyPi05(nn.Module):
    def __init__(self, width=4, depth=2):
        super().__init__()
        self.gemma_expert = nn.Module()
        self.gemma_expert.model = nn.Module()
        self.gemma_expert.model.layers = nn.ModuleList(
            [_ToyExpertLayer(width) for _ in range(depth)]
        )

    def forward(self, value):
        for layer in self.gemma_expert.model.layers:
            value = layer(value)
        return value


def test_pi05_clare_integration_trains_routes_and_roundtrips(tmp_path):
    torch.manual_seed(17)
    policy = _ToyPi05()
    base_state = {
        key: value.detach().clone() for key, value in policy.state_dict().items()
    }
    config = default_pi05_clare_config(
        policy,
        adapter_rank=2,
        discriminator_hidden_dim=3,
        discriminator_latent_dim=2,
    )
    assert len(config.expandable_layers) == 2
    integration = Pi05ClareIntegration(policy, ClareSystem(config))
    inputs = torch.randn(8, 3, 4)
    report = train_clare_stage(
        integration,
        stage_id="stage-1",
        feature_forwards=(lambda: policy(inputs),),
        loss_forward=lambda: policy(inputs).square().mean(),
        adapter_steps=3,
        discriminator_steps=4,
        discriminator_batch_size=4,
        seed=23,
    )
    assert report["stage_id"] == "stage-1"
    assert len(report["plan"]["expanded_layers"]) == 2
    expected = policy(inputs).detach()
    artifact = tmp_path / "clare"
    first = save_clare_artifact(
        artifact, integration.system, provenance={"base_policy": "toy"}
    )
    assert save_clare_artifact(
        artifact, integration.system, provenance={"base_policy": "toy"}
    ) == first

    restored_policy = _ToyPi05()
    restored_policy.load_state_dict(base_state)
    restored = load_clare_artifact(artifact)
    restored_integration = Pi05ClareIntegration(restored_policy, restored)
    actual = restored_policy(inputs).detach()
    torch.testing.assert_close(actual, expected)
    assert restored_integration.system.manifest() == integration.system.manifest()


def test_random_control_matches_expansion_count_exactly_and_is_order_invariant():
    ids = [f"op-{index:03d}" for index in range(100)]
    first = MatchedRandomRouter(opportunity_ids=ids, expansion_rate=0.37, seed=7)
    second = MatchedRandomRouter(
        opportunity_ids=list(reversed(ids)), expansion_rate=0.37, seed=7
    )
    expanded_first = {
        value
        for value in ids
        if first.decide(_opportunity(opportunity_id=value)).route
        is ControllerRoute.EXPAND
    }
    expanded_second = {
        value
        for value in ids
        if second.decide(_opportunity(opportunity_id=value)).route
        is ControllerRoute.EXPAND
    }
    assert len(expanded_first) == 37
    assert expanded_first == expanded_second


def test_experimental_fixed_budget_can_drive_the_real_chunk_controller_past_four():
    config = ModeGateConfig(
        enabled=True,
        baseline_kind="fixed_budget",
        baseline_budget=8,
    )
    router = build_baseline_router(
        kind=config.baseline_kind,
        budget=config.baseline_budget,
    )
    controller = EpisodeChunkController(config, retry_budget_override=8)
    controller.start_episode()
    controller.state.verification_due = True
    controller.begin_sampling()
    controller.mark_abstracted()
    controller.mark_scored(has_safe_mode=True)
    controller.state.retry_index = 4
    baseline = router.decide(_opportunity(retry_index=4))
    decision = controller.route_scored_batch(
        route_override=baseline.route,
        override_reason=baseline.reason,
    )
    assert decision.route is ControllerRoute.RESTEER
    assert controller.state.retry_budget == 8
    assert controller.state.retry_index == 5
    assert decision.remaining_budget == 3
    assert decision.verifier_called is False


def test_baseline_manifest_is_immutable_and_protocol_bound(tmp_path):
    path = tmp_path / "baselines.json"
    first = freeze_baseline_suite(path, protocol_manifest_hash="a" * 64)
    second = freeze_baseline_suite(path, protocol_manifest_hash="a" * 64)
    assert first == second == json.loads(path.read_text())
    assert first["manifest_sha256"]
    ids = {value["id"] for value in first["baselines"]}
    assert {
        "fixed_budget_1",
        "fixed_budget_2",
        "fixed_budget_4",
        "fixed_budget_8",
        "fixed_budget_16",
        "fixed_budget_32",
        "always_expansion_retain",
        "oracle_verifier",
        "resteer_only",
        "verifier_no_lookup",
        "mode_count_gate",
        "semantic_gate",
        "geometry_gate",
        "random_matched",
        "clare_minimal_faithful",
    } == ids
    with pytest.raises(ValueError, match="different contents"):
        freeze_baseline_suite(path, protocol_manifest_hash="b" * 64)


def _clare() -> ClareSystem:
    return ClareSystem(
        ClareConfig(
            expandable_layers=("encoder.block.0.ffn", "encoder.block.1.ffn"),
            feature_dims={
                "encoder.block.0.ffn": 4,
                "encoder.block.1.ffn": 4,
            },
            adapter_rank=2,
            discriminator_hidden_dim=3,
            discriminator_latent_dim=2,
            gamma=2.5,
        )
    )


def test_clare_dynamic_expansion_adds_every_discriminator_and_forces_shallowest():
    torch.manual_seed(3)
    system = _clare()
    features = {
        "encoder.block.0.ffn": torch.randn(32, 4),
        "encoder.block.1.ffn": torch.randn(32, 4),
    }
    stage1 = system.plan_stage("task-1", features)
    assert stage1.expanded_layers == (
        "encoder.block.0.ffn",
        "encoder.block.1.ffn",
    )
    system.apply_stage_plan(stage1)
    system.finalize_stage_statistics("task-1", features)

    # The exact same feature bank is in-distribution at both layers.  CLARE
    # still adds an adapter to the shallowest layer, as required by Algorithm 1.
    stage2 = system.plan_stage("task-2", features)
    assert stage2.expanded_layers == ("encoder.block.0.ffn",)
    assert stage2.layer_decisions[0].forced
    created = system.apply_stage_plan(stage2)
    assert created["encoder.block.0.ffn"]["adapter_created"] == "true"
    assert created["encoder.block.1.ffn"]["adapter_created"] == "false"
    system.finalize_stage_statistics("task-2", features)

    for layer_name in system.config.expandable_layers:
        bank = system.layer_bank(layer_name)
        assert set(bank.discriminators) == {"disc::task-1", "disc::task-2"}
        assert set(bank.links) == set(bank.discriminators)
    manifest = system.manifest()
    assert manifest["paper_contract"]["task_id_required_at_inference"] is False
    assert manifest["manifest_sha256"]


class _DistanceToCenter(nn.Module):
    def __init__(self, center: float):
        super().__init__()
        self.register_buffer("center", torch.tensor(center))

    def reconstruction_error(self, features):
        return torch.linalg.vector_norm(features - self.center, dim=-1)


def test_clare_routes_by_autoencoder_error_then_uses_surjective_link():
    system = _clare()
    features = {name: torch.zeros(8, 4) for name in system.config.expandable_layers}
    stage1 = system.plan_stage("task-1", features)
    system.apply_stage_plan(stage1)
    system.finalize_stage_statistics("task-1", features)

    bank = system.layer_bank("encoder.block.0.ffn")
    bank.add_adapter("adapter::shared")
    bank.add_discriminator("disc::near-one", linked_adapter_id="adapter::shared")
    bank.discriminators["disc::task-1"] = _DistanceToCenter(0.0)
    bank.discriminators["disc::near-one"] = _DistanceToCenter(1.0)
    assert bank.route(torch.tensor([[0.1] * 4, [0.9] * 4])) == (
        "adapter::task-1",
        "adapter::shared",
    )
    # Multiple discriminators may legally map to the same adapter.
    bank.links["disc::near-one"] = "adapter::task-1"
    assert bank.route(torch.tensor([[0.1] * 4, [0.9] * 4])) == (
        "adapter::task-1",
        "adapter::task-1",
    )


def test_clare_adapter_is_parallel_ffn_side_branch_and_freezes_base():
    torch.manual_seed(1)
    system = _clare()
    features_by_layer = {
        name: torch.randn(8, 4) for name in system.config.expandable_layers
    }
    plan = system.plan_stage("task-1", features_by_layer)
    system.apply_stage_plan(plan)
    system.finalize_stage_statistics("task-1", features_by_layer)
    bank = system.layer_bank("encoder.block.0.ffn")
    base = nn.Linear(4, 4, bias=False)
    wrapper = ClareExpandableFFN(base, bank)
    features = torch.randn(3, 4)
    expected = base(features) + bank.adapters["adapter::task-1"](features)
    assert torch.allclose(wrapper(features), expected)
    assert not any(parameter.requires_grad for parameter in base.parameters())
    assert isinstance(bank.adapters["adapter::task-1"], ClareAdapter)


def test_final_seal_opens_once_and_resumes_same_500_context_job(tmp_path, monkeypatch):
    manifest = generate_joint_manifest(
        [
            {
                "suite": f"libero_{index // 10}",
                "task_id": str(index),
                "task_index": index % 10,
                "perturbation_variant": "base",
                "init_state_ids": [str(value) for value in range(50)],
            }
            for index in range(40)
        ],
        dataset_hash="d",
        bddl_hash="b",
        init_state_manifest_hash="i",
        generator_git_sha="g",
    )
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    save_file({"weight": torch.ones(2)}, str(checkpoint / "model.safetensors"))
    subject = FinalEvaluationSubject(
        subject_id="deployed-full",
        checkpoint_path=str(checkpoint),
        checkpoint_digest=checkpoint_digest(checkpoint),
        hydra_overrides=("mode_gate.enabled=true",),
        evaluation_profile={"controller": "full", "metric_role": "deployed_final"},
    )
    monkeypatch.setenv("VLS_FINAL_SEAL_TOKEN", "one-time")
    guard = FinalSealGuard(manifest, tmp_path / "seal.json")
    opened = guard.open(
        purpose="final", authorization_token="one-time", subjects=(subject.subject_id,)
    )
    assert len(opened) == 500
    calls = []

    def executor_factory(_subject):
        def execute(policy_id, checkpoint_path, context):
            calls.append((policy_id, context.episode_key))
            return RawEpisodeResult(success=int(context.init_state_id) % 2 == 0)

        return execute

    coordinator = FinalSealedEvaluationCoordinator(
        manifest=manifest,
        seal_guard=guard,
        ledger_path=tmp_path / "episodes.jsonl",
        output_path=tmp_path / "report.json",
        executor_factory=executor_factory,
    )
    result = coordinator.run((subject,), purpose="final", resume=True)
    assert result["metric_role"] == "deployed_final"
    assert result["context_count"] == 500
    assert len(calls) == 500
    assert guard.completion_log.is_file()
    with pytest.raises(RuntimeError, match="already complete"):
        coordinator.run((subject,), purpose="final", resume=True)


def test_slow_job_runner_requires_only_two_suitable_gpus(
    tmp_path, monkeypatch
):
    import mode_gate.job_runner as runner

    repo_root = Path(__file__).resolve().parents[1]
    spec = {
        "schema_version": "coft-job-v1",
        "command": [
            "/shared/hengyil6/vls/envs/vla-pilot/bin/python",
            "-m",
            "accelerate.commands.launch",
            "--num_processes",
            "2",
            "-m",
            "lerobot.scripts.lerobot_train",
            "--batch_size=4",
            "--gradient_accumulation_steps=4",
        ],
        "cwd": str(repo_root),
        "gpu_count": 2,
        "minimum_free_gib_per_gpu": 45.0,
    }
    path = tmp_path / "training_job.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "_gpu_memory_snapshot",
        lambda: [
            {"index": index, "free_mib": 90_000 if index == 4 else 1, "used_mib": 0}
            for index in range(8)
        ],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("blocked co-FT job must not launch a subprocess")

    monkeypatch.setattr(runner.subprocess, "Popen", forbidden)
    result = execute_job_spec(path)
    assert not result["launched"] and not result["completed"]
    assert result["requested_gpu_count"] == 2
    assert result["eligible_gpu_indices"] == [4]


def test_delta_candidate_phase_resumes_after_verified_theta_ft_cleanup(tmp_path):
    theta0 = tmp_path / "theta0"
    theta_ft = tmp_path / "theta_ft"
    theta0.mkdir()
    theta_ft.mkdir()
    base = {
        "model.paligemma_with_expert.paligemma.model.vision_tower.x": torch.ones(2),
        "model.paligemma_with_expert.paligemma.model.language_model.x": torch.ones(2),
        "model.action_in_proj.weight": torch.ones(2),
    }
    save_file(base, str(theta0 / "model.safetensors"))
    save_file(
        {key: value + 0.25 for key, value in base.items()},
        str(theta_ft / "model.safetensors"),
    )
    registry = PolicyRegistry(tmp_path / "registry")
    registry.initialize_base(
        checkpoint_path=str(theta0),
        digest=checkpoint_digest(theta0),
        metadata={},
    )
    registry.install_artifact("policy", "p0", theta0)
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
    worker = SlowLoopWorker(
        store=SlowLoopStore(tmp_path / "slow"),
        registry=registry,
        incidents=IncidentMemory(tmp_path / "incidents"),
        protocol_manifest=manifest_path,
        ticket_root=tmp_path / "tickets",
        work_root=tmp_path / "work",
    )
    job = SlowLoopJob(
        job_id="job",
        state=SlowLoopState.DELTA_READY,
        active_policy_id="p0",
        ticket_id="ticket",
        input_hash="input",
        output_hash=None,
        sequence=1,
        metadata={
            "theta_ft_checkpoint_path": str(theta_ft),
            "theta_ft_checkpoint_digest": checkpoint_digest(theta_ft),
            "coft_source_manifest_path": str(tmp_path / "source.json"),
            "cleanup_theta_ft": True,
            "baseline_kind": "always_expand_retain",
        },
    )
    first = worker._extract_delta_and_candidates(job)
    assert first.next_state is SlowLoopState.ALPHA_SELECTING
    assert first.metadata["candidate_merge_method"] == "retain_uniform"
    assert first.metadata["theta_ft_deleted"]
    assert not theta_ft.exists()
    # This is the exact crash window after cleanup but before state append.
    second = worker._extract_delta_and_candidates(job)
    assert second.metadata["delta_id"] == first.metadata["delta_id"]
    assert second.metadata["candidate_grid_path"] == first.metadata["candidate_grid_path"]


def test_throughput_bank_never_uses_final_seal_and_worker_count_preserves_results(
    tmp_path,
):
    manifest = generate_joint_manifest(
        [
            {
                "suite": f"libero_{index // 10}",
                "task_id": str(index),
                "task_index": index % 10,
                "perturbation_variant": "base",
                "init_state_ids": [str(value) for value in range(50)],
            }
            for index in range(40)
        ],
        dataset_hash="d",
        bddl_hash="b",
        init_state_manifest_hash="i",
        generator_git_sha="g",
    )
    contexts = throughput_contexts_from_manifest(manifest)
    final_cells = {
        (task["task_key"], state)
        for task in manifest["tasks"]
        for state in task["splits"]["policy_final_sealed"]
    }
    assert len(contexts) == 500
    assert not any(
        (context.task_key, context.init_state_id) in final_cells for context in contexts
    )

    def execute(policy_id, checkpoint_path, context):
        success = context.policy_seed % 2 == 0
        return RawEpisodeResult(
            success=success,
            steps=10,
            metadata={"determinism_digest": context.episode_key},
        )

    result = RolloutThroughputBenchmark(
        executor=execute, sample_gpu=False
    ).run(
        policy_id="p0",
        checkpoint_path=tmp_path,
        checkpoint_digest="d" * 64,
        contexts=contexts,
        output_path=tmp_path / "throughput.json",
        worker_counts=(1, 4),
        warmup_contexts=0,
    )
    assert result["passed"]
    assert all(run["valid_episodes"] == 500 for run in result["runs"])
    assert all(
        run["seed_result_invariant_to_worker_count"] for run in result["runs"]
    )
