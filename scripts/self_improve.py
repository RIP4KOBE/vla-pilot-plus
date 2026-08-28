#!/usr/bin/env python
"""Operational CLI for the hgpu1 self-improvement artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.checkpoint_math import (  # noqa: E402
    checkpoint_digest,
    compose_policy,
    delete_verified_theta_ft,
    extract_full_delta,
    verify_full_delta_reconstruction,
)
from mode_gate.baselines import freeze_baseline_suite  # noqa: E402
from mode_gate.audit import (  # noqa: E402
    AuditCollectionCoordinator,
    HydraAuditEpisodeExecutor,
)
from mode_gate.candidates import (  # noqa: E402
    DeltaLineageEntry,
    compose_expansion_candidates,
    compose_retain_expansion_candidates,
    compose_reuse_candidates,
)
from mode_gate.curriculum import (  # noqa: E402
    BALANCED_PRO_VARIANT,
    freeze_protocol,
    prepare_libero_pro_resources,
)
from mode_gate.data_pipeline import curate_and_export_ticket  # noqa: E402
from mode_gate.deployed_evaluation import (  # noqa: E402
    DeployedDevelopmentCoordinator,
)
from mode_gate.eval_manifest import (  # noqa: E402
    FinalSealGuard,
    validate_libero_pro_manifest,
)
from mode_gate.final_evaluation import (  # noqa: E402
    FinalEvaluationSubject,
    FinalSealedEvaluationCoordinator,
    make_hydra_executor_factory,
)
from mode_gate.incidents import IncidentMemory  # noqa: E402
from mode_gate.io_utils import sha256_file  # noqa: E402
from mode_gate.job_runner import execute_job_spec  # noqa: E402
from mode_gate.offline_replay import execute_replay_plan  # noqa: E402
from mode_gate.preflight import run_preflight  # noqa: E402
from mode_gate.policy_evaluator import (  # noqa: E402
    HydraRawEpisodeExecutor,
    RawPolicyEvaluator,
    contexts_from_manifest,
)
from mode_gate.promotion import (  # noqa: E402
    PolicyCandidate,
    PolicyPromotionCoordinator,
    TriggerTaskEvaluator,
    deploy_policy_gate,
)
from mode_gate.registry import PolicyRegistry  # noqa: E402
from mode_gate.slow_loop import SlowLoopState, SlowLoopStore  # noqa: E402
from mode_gate.slow_worker import SlowLoopWorker  # noqa: E402
from mode_gate.tickets import TicketCollectionPlanner  # noqa: E402
from mode_gate.throughput import (  # noqa: E402
    RolloutThroughputBenchmark,
    throughput_contexts_from_manifest,
)
from mode_gate.training import (  # noqa: E402
    build_lerobot_coft_command,
    prepare_source_catalog,
)
from mode_gate.verifier_training import (  # noqa: E402
    VerifierTrainingConfig,
    build_verifier_examples,
    train_verifier,
    train_verifier_ablations,
    train_verifier_holdout,
)
from mode_gate.verifier_refresh import VerifierRefreshCoordinator  # noqa: E402


DEFAULT_ROOT = Path("/shared/hengyil6/vls/self_improve")
DEFAULT_PYTHON = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")


def _load_formal_manifest(path: Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_libero_pro_manifest(value)
    return value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    freeze = commands.add_parser("freeze-protocol")
    freeze.add_argument("--output-root", type=Path, default=DEFAULT_ROOT / "protocol")
    freeze.add_argument("--default-variant", default=BALANCED_PRO_VARIANT)
    freeze.add_argument("--variant-map", type=Path)

    commands.add_parser("prepare-libero-pro")

    baselines = commands.add_parser("freeze-baselines")
    baselines.add_argument(
        "--protocol-manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    baselines.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ROOT / "protocol/baseline_manifest.json",
    )

    preflight = commands.add_parser("preflight")
    preflight.add_argument("--output", type=Path, default=DEFAULT_ROOT / "preflight/preflight.json")
    preflight.add_argument(
        "--curriculum-manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/curriculum.json",
    )
    preflight.add_argument(
        "--protocol-manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    preflight.add_argument(
        "--snapshot-canary-result",
        type=Path,
        default=DEFAULT_ROOT / "preflight/snapshot_canary/result.json",
    )
    preflight.add_argument(
        "--nccl-canary-result",
        type=Path,
        default=DEFAULT_ROOT / "preflight/nccl_canary/result.json",
    )
    preflight.add_argument(
        "--training-smoke-result",
        type=Path,
        default=DEFAULT_ROOT / "preflight/training_smoke/result.json",
    )
    preflight.add_argument(
        "--gemini-canary-result",
        type=Path,
        default=DEFAULT_ROOT / "preflight/gemini_canary/result.json",
    )
    preflight.add_argument(
        "--teleop-canary-result",
        type=Path,
        default=DEFAULT_ROOT / "preflight/teleop_canary/result.json",
    )
    preflight.add_argument(
        "--baseline-manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/baseline_manifest.json",
    )
    preflight.add_argument("--skip-tests", action="store_true")

    init = commands.add_parser("registry-init")
    init.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    init.add_argument(
        "--theta0",
        type=Path,
        default=Path("/shared/hengyil6/vls/models/pi05_libero_finetuned_v044"),
    )

    bootstrap = commands.add_parser("registry-bootstrap")
    bootstrap.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    bootstrap.add_argument(
        "--theta0",
        type=Path,
        default=Path("/shared/hengyil6/vls/models/pi05_libero_finetuned_v044"),
    )
    bootstrap.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    bootstrap.add_argument("--policy-id", default="policy_000")

    delta = commands.add_parser("extract-delta")
    delta.add_argument("--parent", type=Path, required=True)
    delta.add_argument("--theta-ft", type=Path, required=True)
    delta.add_argument("--output", type=Path, required=True)
    delta.add_argument("--parent-policy-id", required=True)
    delta.add_argument("--delete-theta-ft", action="store_true")

    compose = commands.add_parser("compose")
    compose.add_argument("--theta0", type=Path, required=True)
    compose.add_argument("--delta", type=Path, action="append", required=True)
    compose.add_argument("--alpha-l", type=float, action="append", required=True)
    compose.add_argument("--output", type=Path, required=True)

    compose_candidates = commands.add_parser("compose-candidates")
    compose_candidates.add_argument("--spec-json", type=Path, required=True)
    compose_candidates.add_argument("--output", type=Path, required=True)

    promote = commands.add_parser("promote")
    promote.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    promote.add_argument("--policy-id", required=True)
    promote.add_argument("--verifier-id")
    promote.add_argument(
        "--controller-mode",
        choices=("learned_verifier", "fixed_budget_4"),
        required=True,
    )
    promote.add_argument("--manifest-hash", required=True)
    promote.add_argument("--expected-revision", type=int, required=True)

    rollback = commands.add_parser("rollback")
    rollback.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    rollback.add_argument("--to-revision", type=int, required=True)
    rollback.add_argument("--expected-revision", type=int, required=True)

    jobs = commands.add_parser("list-jobs")
    jobs.add_argument("--root", type=Path, default=DEFAULT_ROOT / "slow_loop")

    annotate_job = commands.add_parser("annotate-job")
    annotate_job.add_argument("--job-id", required=True)
    annotate_job.add_argument("--root", type=Path, default=DEFAULT_ROOT / "slow_loop")
    annotate_job.add_argument(
        "--expected-state", choices=tuple(item.value for item in SlowLoopState), required=True
    )
    annotate_job.add_argument("--metadata-json", type=Path, required=True)

    advance_job = commands.add_parser("advance-job")
    advance_job.add_argument("--job-id", required=True)
    advance_job.add_argument("--root", type=Path, default=DEFAULT_ROOT / "slow_loop")
    advance_job.add_argument(
        "--expected-state", choices=tuple(item.value for item in SlowLoopState), required=True
    )
    advance_job.add_argument(
        "--next-state", choices=tuple(item.value for item in SlowLoopState), required=True
    )
    advance_job.add_argument("--metadata-json", type=Path)
    advance_job.add_argument("--artifact", type=Path, action="append", default=[])

    coft = commands.add_parser("coft-command")
    coft.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    coft.add_argument("--parent", type=Path, required=True)
    coft.add_argument("--dataset-root", type=Path, required=True)
    coft.add_argument("--dataset-repo-id")
    coft.add_argument("--source-manifest", type=Path, required=True)
    coft.add_argument("--output", type=Path, required=True)
    coft.add_argument("--seed", type=int, required=True)
    coft.add_argument("--run", action="store_true")

    sources = commands.add_parser("prepare-sources")
    sources.add_argument("--spec-json", type=Path, required=True)
    sources.add_argument("--catalog", type=Path, required=True)
    sources.add_argument("--manifest", type=Path, required=True)
    sources.add_argument("--seed", type=int, required=True)

    curate = commands.add_parser("curate-ticket")
    curate.add_argument("--ticket", type=Path, required=True)
    curate.add_argument("--repo-id", required=True)
    curate.add_argument("--replay-tolerance", type=float, default=1e-5)

    verifier = commands.add_parser("train-verifier")
    verifier.add_argument(
        "--incidents", type=Path, default=DEFAULT_ROOT / "incidents"
    )
    verifier.add_argument("--policy-id", required=True)
    verifier.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "verifier_attempts"
    )
    verifier.add_argument("--config-json", type=Path)
    verifier.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    verifier.add_argument("--install", action="store_true")
    verifier.add_argument("--require-gate", action="store_true")

    verifier_ablations = commands.add_parser("train-verifier-ablations")
    verifier_ablations.add_argument(
        "--incidents", type=Path, default=DEFAULT_ROOT / "incidents"
    )
    verifier_ablations.add_argument("--policy-id", required=True)
    verifier_ablations.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "verifier_ablations"
    )
    verifier_ablations.add_argument("--config-json", type=Path)
    verifier_ablations.add_argument(
        "--registry", type=Path, default=DEFAULT_ROOT / "registry"
    )
    verifier_ablations.add_argument("--install-selected", action="store_true")

    verifier_holdout = commands.add_parser("train-verifier-holdout")
    verifier_holdout.add_argument(
        "--incidents", type=Path, default=DEFAULT_ROOT / "incidents"
    )
    verifier_holdout.add_argument("--policy-id", required=True)
    verifier_holdout.add_argument(
        "--kind", choices=("task", "axis", "checkpoint", "temporal"), required=True
    )
    verifier_holdout.add_argument("--value", required=True)
    verifier_holdout.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "verifier_holdouts"
    )
    verifier_holdout.add_argument("--config-json", type=Path)

    verifier_refresh = commands.add_parser("refresh-verifier")
    verifier_refresh.add_argument(
        "--incidents", type=Path, default=DEFAULT_ROOT / "incidents"
    )
    verifier_refresh.add_argument(
        "--registry", type=Path, default=DEFAULT_ROOT / "registry"
    )
    verifier_refresh.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "verifier_refresh"
    )
    verifier_refresh.add_argument("--config-json", type=Path)
    verifier_refresh.add_argument("--brier-drift-threshold", type=float, default=0.02)

    run_job = commands.add_parser("run-job")
    run_job.add_argument("--job-id", required=True)
    run_job.add_argument("--root", type=Path, default=DEFAULT_ROOT / "slow_loop")
    run_job.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    run_job.add_argument("--incidents", type=Path, default=DEFAULT_ROOT / "incidents")
    run_job.add_argument("--snapshots", type=Path, default=DEFAULT_ROOT / "snapshots")
    run_job.add_argument(
        "--protocol-manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    run_job.add_argument("--tickets", type=Path, default=DEFAULT_ROOT / "tickets")
    run_job.add_argument("--work", type=Path, default=DEFAULT_ROOT / "slow_work")
    run_job.add_argument("--once", action="store_true")

    execute_job = commands.add_parser("execute-job-spec")
    execute_job.add_argument("--spec", type=Path, required=True)
    execute_job.add_argument("--timeout-seconds", type=float, default=86_400.0)

    raw_eval = commands.add_parser("raw-evaluate")
    raw_eval.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    raw_eval.add_argument(
        "--split",
        choices=("policy_alpha_selection", "policy_regression"),
        required=True,
    )
    raw_eval.add_argument("--policy-id", required=True)
    raw_eval.add_argument("--checkpoint", type=Path, required=True)
    raw_eval.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    raw_eval.add_argument("--ledger", type=Path, required=True)
    raw_eval.add_argument("--output", type=Path, required=True)
    raw_eval.add_argument("--workers", type=int, default=1)

    policy_gate = commands.add_parser("policy-gate")
    policy_gate.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    policy_gate.add_argument("--ticket", type=Path, required=True)
    policy_gate.add_argument("--parent-json", type=Path, required=True)
    policy_gate.add_argument("--candidates-json", type=Path, required=True)
    policy_gate.add_argument("--ledger", type=Path, required=True)
    policy_gate.add_argument("--output", type=Path, required=True)
    policy_gate.add_argument("--rollout-output", type=Path, required=True)
    policy_gate.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    policy_gate.add_argument("--workers", type=int, default=1)
    policy_gate.add_argument("--bootstrap-draws", type=int, default=10_000)
    policy_gate.add_argument("--reuse", action="store_true")

    deploy_gate = commands.add_parser("deploy-gate")
    deploy_gate.add_argument("--report", type=Path, required=True)
    deploy_gate.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    deploy_gate.add_argument("--expected-revision", type=int, required=True)
    deploy_gate.add_argument("--verifier-result", type=Path)
    deploy_gate.add_argument("--signature", type=Path)
    deploy_gate.add_argument(
        "--incidents", type=Path, default=DEFAULT_ROOT / "incidents"
    )

    deployed_dev = commands.add_parser("deployed-dev-evaluate")
    deployed_dev.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    deployed_dev.add_argument(
        "--registry", type=Path, default=DEFAULT_ROOT / "registry"
    )
    deployed_dev.add_argument(
        "--ledger", type=Path, default=DEFAULT_ROOT / "deployed_dev/episodes.jsonl"
    )
    deployed_dev.add_argument(
        "--rollout-output",
        type=Path,
        default=DEFAULT_ROOT / "deployed_dev/rollouts",
    )
    deployed_dev.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "deployed_dev/report.json"
    )
    deployed_dev.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    deployed_dev.add_argument("--workers", type=int, default=1)
    deployed_dev.add_argument("--expected-revision", type=int)
    deployed_dev.add_argument("--expected-checkpoint-digest")

    replay = commands.add_parser("replay-new-policy")
    replay.add_argument("--plan", type=Path, required=True)
    replay.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    replay.add_argument("--device", default="cuda:0")
    replay.add_argument("--ledger", type=Path)

    audit = commands.add_parser("collect-verifier-audit")
    audit.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    audit.add_argument("--registry", type=Path, default=DEFAULT_ROOT / "registry")
    audit.add_argument(
        "--incident-root", type=Path, default=DEFAULT_ROOT / "audit/incidents"
    )
    audit.add_argument(
        "--snapshot-root", type=Path, default=DEFAULT_ROOT / "audit/snapshots"
    )
    audit.add_argument(
        "--slow-loop-root", type=Path, default=DEFAULT_ROOT / "audit/slow_loop"
    )
    audit.add_argument(
        "--ledger", type=Path, default=DEFAULT_ROOT / "audit/episodes.jsonl"
    )
    audit.add_argument(
        "--rollout-output", type=Path, default=DEFAULT_ROOT / "audit/rollouts"
    )
    audit.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "audit/collection.json"
    )
    audit.add_argument(
        "--replay-plan", type=Path, default=DEFAULT_ROOT / "audit/replay_plan.json"
    )
    audit.add_argument(
        "--preflight",
        type=Path,
        default=DEFAULT_ROOT / "preflight/preflight.json",
    )
    audit.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    audit.add_argument("--workers", type=int, default=1)
    audit.add_argument("--gpu-index", type=int, default=0)
    audit.add_argument("--limit", type=int)
    audit.add_argument(
        "--use-guidance",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    audit.add_argument("--episode-timeout", type=float, default=3600.0)

    final_eval = commands.add_parser("final-evaluate")
    final_eval.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    final_eval.add_argument("--subjects-json", type=Path, required=True)
    final_eval.add_argument(
        "--seal-audit",
        type=Path,
        default=DEFAULT_ROOT / "final/final_seal_open.json",
    )
    final_eval.add_argument(
        "--ledger", type=Path, default=DEFAULT_ROOT / "final/episodes.jsonl"
    )
    final_eval.add_argument(
        "--rollout-output", type=Path, default=DEFAULT_ROOT / "final/rollouts"
    )
    final_eval.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "final/report.json"
    )
    final_eval.add_argument(
        "--purpose", default="final_deployed_and_preregistered_baselines"
    )
    final_eval.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    final_eval.add_argument("--workers", type=int, default=1)
    final_eval.add_argument("--resume", action="store_true")

    throughput = commands.add_parser("throughput-benchmark")
    throughput.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "protocol/joint_eval_manifest.json",
    )
    throughput.add_argument("--policy-id", required=True)
    throughput.add_argument("--checkpoint", type=Path, required=True)
    throughput.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ROOT / "benchmarks/throughput.json",
    )
    throughput.add_argument(
        "--rollout-output",
        type=Path,
        default=DEFAULT_ROOT / "benchmarks/throughput_rollouts",
    )
    throughput.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    throughput.add_argument("--worker", type=int, action="append")
    throughput.add_argument("--warmup-contexts", type=int, default=8)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "freeze-protocol":
        variant_map = None
        if args.variant_map:
            variant_map = json.loads(args.variant_map.read_text(encoding="utf-8"))
        revision = _working_revision()
        curriculum, joint = freeze_protocol(
            REPO_ROOT,
            args.output_root,
            default_variant=args.default_variant,
            variant_by_task=variant_map,
            generator_revision=revision,
        )
        _print({"curriculum": curriculum["manifest_sha256"], "joint": joint["manifest_sha256"]})
    elif args.command == "prepare-libero-pro":
        _print(prepare_libero_pro_resources())
    elif args.command == "freeze-baselines":
        protocol = _load_formal_manifest(args.protocol_manifest)
        result = freeze_baseline_suite(
            args.output,
            protocol_manifest_hash=str(protocol["manifest_sha256"]),
        )
        _print(result)
    elif args.command == "preflight":
        result = run_preflight(
            repo_root=REPO_ROOT,
            output_path=args.output,
            curriculum_manifest=args.curriculum_manifest,
            protocol_manifest=args.protocol_manifest,
            snapshot_canary_result=args.snapshot_canary_result,
            nccl_canary_result=args.nccl_canary_result,
            training_smoke_result=args.training_smoke_result,
            gemini_canary_result=args.gemini_canary_result,
            teleop_canary_result=args.teleop_canary_result,
            baseline_manifest=args.baseline_manifest,
            run_tests=not args.skip_tests,
            require_hgpu1_layout=True,
        )
        _print(result)
    elif args.command == "registry-init":
        registry = PolicyRegistry(args.registry)
        digest = checkpoint_digest(args.theta0)
        registry.initialize_base(
            checkpoint_path=str(args.theta0),
            digest=digest,
            metadata={"source": "lerobot/pi05_libero_finetuned_v044"},
        )
        _print({"registry": str(args.registry), "theta0_digest": digest})
    elif args.command == "registry-bootstrap":
        manifest = _load_formal_manifest(args.manifest)
        digest = checkpoint_digest(args.theta0)
        deployment = PolicyRegistry(args.registry).bootstrap_base_policy(
            checkpoint_path=args.theta0,
            digest=digest,
            metadata={"source": "lerobot/pi05_libero_finetuned_v044"},
            policy_id=args.policy_id,
            manifest_hash=str(manifest["manifest_sha256"]),
        )
        _print(deployment.__dict__ | {"theta0_digest": digest})
    elif args.command == "extract-delta":
        cleanup_path = args.output / "theta_ft_cleanup.json"
        if not args.theta_ft.exists() and cleanup_path.is_file():
            extraction = json.loads(
                (args.output / "meta.json").read_text(encoding="utf-8")
            )
            reconstruction = json.loads(
                (args.output / "reconstruction.json").read_text(encoding="utf-8")
            )
            cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
            if reconstruction.get("parent_checkpoint_digest") != checkpoint_digest(args.parent):
                raise ValueError("parent changed after theta_ft cleanup")
            if reconstruction.get("delta_checkpoint_digest") != checkpoint_digest(args.output):
                raise ValueError("delta changed after theta_ft cleanup")
            _print(
                {
                    "extraction": extraction,
                    "reconstruction": reconstruction,
                    "theta_ft_cleanup": cleanup,
                }
            )
            return 0
        if args.output.exists():
            extraction = json.loads(
                (args.output / "meta.json").read_text(encoding="utf-8")
            )
            if extraction.get("parent_checkpoint_digest") != checkpoint_digest(args.parent):
                raise ValueError("existing delta was extracted from a different parent")
            if extraction.get("theta_ft_checkpoint_digest") != checkpoint_digest(args.theta_ft):
                raise ValueError("existing delta was extracted from a different theta_ft")
        else:
            extraction = extract_full_delta(
                args.parent,
                args.theta_ft,
                args.output,
                parent_policy_id=args.parent_policy_id,
            )
        reconstruction = verify_full_delta_reconstruction(
            args.parent, args.output, args.theta_ft
        )
        cleanup = None
        if args.delete_theta_ft:
            cleanup = delete_verified_theta_ft(
                args.theta_ft,
                parent_checkpoint=args.parent,
                delta_checkpoint=args.output,
            )
        _print(
            {
                "extraction": extraction,
                "reconstruction": reconstruction,
                "theta_ft_cleanup": cleanup,
            }
        )
    elif args.command == "compose":
        if len(args.delta) != len(args.alpha_l):
            raise ValueError("--delta and --alpha-l counts must match")
        deltas = [
            (path, {"vision": 1.0, "language": alpha, "action": 1.0})
            for path, alpha in zip(args.delta, args.alpha_l)
        ]
        _print(compose_policy(args.theta0, deltas, args.output))
    elif args.command == "compose-candidates":
        spec = json.loads(args.spec_json.read_text(encoding="utf-8"))
        lineage = tuple(
            DeltaLineageEntry(**value) for value in spec.get("accepted_lineage", ())
        )
        common = {
            "theta0_checkpoint": Path(spec["theta0_checkpoint"]),
            "parent_policy_id": str(spec["parent_policy_id"]),
            "accepted_lineage": lineage,
            "output_root": args.output,
        }
        if spec.get("mode") == "EXPANSION":
            result = compose_expansion_candidates(
                **common,
                new_delta_id=str(spec["new_delta_id"]),
                new_delta_path=Path(spec["new_delta_path"]),
            )
        elif spec.get("mode") == "RETAIN_EXPANSION":
            result = compose_retain_expansion_candidates(
                **common,
                new_delta_id=str(spec["new_delta_id"]),
                new_delta_path=Path(spec["new_delta_path"]),
            )
        elif spec.get("mode") == "REUSE":
            result = compose_reuse_candidates(
                **common,
                target_delta_id=str(spec["target_delta_id"]),
            )
        else:
            raise ValueError(
                "candidate spec mode must be EXPANSION, RETAIN_EXPANSION, or REUSE"
            )
        _print(result)
    elif args.command == "promote":
        deployment = PolicyRegistry(args.registry).promote(
            policy_id=args.policy_id,
            verifier_id=args.verifier_id,
            controller_mode=args.controller_mode,
            manifest_hash=args.manifest_hash,
            expected_revision=args.expected_revision,
        )
        _print(deployment.__dict__)
    elif args.command == "rollback":
        deployment = PolicyRegistry(args.registry).rollback(
            to_revision=args.to_revision,
            expected_revision=args.expected_revision,
        )
        _print(deployment.__dict__)
    elif args.command == "list-jobs":
        _print([job.__dict__ | {"state": job.state.value} for job in SlowLoopStore(args.root).resumable_jobs()])
    elif args.command == "annotate-job":
        metadata = _artifact_metadata(
            json.loads(args.metadata_json.read_text(encoding="utf-8"))
        )
        output_hash = _json_hash(metadata)
        job = SlowLoopStore(args.root).annotate(
            args.job_id,
            expected_state=SlowLoopState(args.expected_state),
            metadata=metadata,
            output_hash=output_hash,
        )
        _print(job.__dict__ | {"state": job.state.value})
    elif args.command == "advance-job":
        store = SlowLoopStore(args.root)
        current = store.current(args.job_id)
        metadata = {}
        if args.metadata_json:
            metadata = _artifact_metadata(
                json.loads(args.metadata_json.read_text(encoding="utf-8"))
            )
        artifacts = {}
        for path in args.artifact:
            path = path.resolve()
            if not path.is_file():
                raise FileNotFoundError(path)
            artifacts[str(path)] = sha256_file(path)
        output_hash = _json_hash(
            {
                "job_id": args.job_id,
                "from": args.expected_state,
                "to": args.next_state,
                "metadata": metadata,
                "artifacts": artifacts,
            }
        )
        job = store.advance(
            args.job_id,
            expected_state=SlowLoopState(args.expected_state),
            next_state=SlowLoopState(args.next_state),
            input_hash=current.input_hash,
            output_hash=output_hash,
            metadata=metadata,
        )
        _print(job.__dict__ | {"state": job.state.value})
    elif args.command == "coft-command":
        source_value = json.loads(args.source_manifest.read_text(encoding="utf-8"))
        repo_ids = source_value.get("repo_ids")
        if repo_ids and Path(source_value["catalog_root"]).resolve() != args.dataset_root.resolve():
            raise ValueError("--dataset-root differs from the frozen source catalog")
        dataset_repo_id = args.dataset_repo_id or (
            str(repo_ids[0]) if repo_ids else None
        )
        if not dataset_repo_id:
            raise ValueError(
                "--dataset-repo-id is required for a legacy single-dataset manifest"
            )
        command = build_lerobot_coft_command(
            python_executable=args.python,
            parent_checkpoint=args.parent,
            dataset_root=args.dataset_root,
            dataset_repo_id=dataset_repo_id,
            dataset_repo_ids=tuple(map(str, repo_ids)) if repo_ids else None,
            source_sampler_manifest=args.source_manifest,
            output_dir=args.output,
            seed=args.seed,
        )
        print(shlex.join(command))
        if args.run:
            subprocess.run(command, cwd=REPO_ROOT, check=True)
    elif args.command == "prepare-sources":
        spec = json.loads(args.spec_json.read_text(encoding="utf-8"))
        result = prepare_source_catalog(
            catalog_root=args.catalog,
            manifest_path=args.manifest,
            new_datasets=spec.get("new", {}),
            old_ticket_datasets=spec.get("old", {}),
            replay_datasets=spec.get("replay", {}),
            seed=args.seed,
        )
        _print(result)
    elif args.command == "curate-ticket":
        result = curate_and_export_ticket(
            ticket_path=args.ticket,
            repo_id=args.repo_id,
            replay_tolerance=args.replay_tolerance,
        )
        _print(result)
        if result["needs_more_demos"]:
            return 3
    elif args.command == "train-verifier":
        overrides = {}
        if args.config_json:
            overrides = json.loads(args.config_json.read_text(encoding="utf-8"))
        config = VerifierTrainingConfig(**overrides)
        examples = build_verifier_examples(
            IncidentMemory(args.incidents), policy_id=args.policy_id
        )
        result = train_verifier(
            examples,
            policy_id=args.policy_id,
            output_root=args.output,
            config=config,
            metadata={"working_revision": _working_revision()},
        )
        installed = None
        if args.install:
            if not result.gate.passed:
                raise RuntimeError(
                    "verifier failed its deployment gate and cannot be installed: "
                    + "; ".join(result.gate.reasons)
                )
            installed = PolicyRegistry(args.registry).install_artifact(
                "verifier", result.verifier_id, Path(result.artifact_root)
            )
        _print(
            {
                **result.__dict__,
                "gate": result.gate.__dict__,
                "installed": str(installed) if installed else None,
            }
        )
        if args.require_gate and not result.gate.passed:
            return 2
    elif args.command == "train-verifier-ablations":
        overrides = (
            json.loads(args.config_json.read_text(encoding="utf-8"))
            if args.config_json
            else {}
        )
        config = VerifierTrainingConfig(**overrides)
        examples = build_verifier_examples(
            IncidentMemory(args.incidents), policy_id=args.policy_id
        )
        result = train_verifier_ablations(
            examples,
            policy_id=args.policy_id,
            output_root=args.output,
            config=config,
            metadata={"working_revision": _working_revision()},
        )
        installed = None
        if args.install_selected:
            if result.selected_channel_set is None:
                raise RuntimeError(
                    "no ablation passed the deployment gate; keep fixed-budget-4"
                )
            selected = result.results[result.selected_channel_set]
            installed = PolicyRegistry(args.registry).install_artifact(
                "verifier", selected.verifier_id, Path(selected.artifact_root)
            )
        _print(
            {
                "report_path": result.report_path,
                "dataset_hash": result.dataset_hash,
                "selected_channel_set": result.selected_channel_set,
                "controller_mode": result.controller_mode,
                "installed": str(installed) if installed else None,
            }
        )
        if result.selected_channel_set is None:
            return 2
    elif args.command == "train-verifier-holdout":
        overrides = (
            json.loads(args.config_json.read_text(encoding="utf-8"))
            if args.config_json
            else {}
        )
        examples = build_verifier_examples(
            IncidentMemory(args.incidents), policy_id=args.policy_id
        )
        result = train_verifier_holdout(
            examples,
            policy_id=args.policy_id,
            kind=args.kind,
            value=args.value,
            output_root=args.output,
            config=VerifierTrainingConfig(**overrides),
            metadata={"working_revision": _working_revision()},
        )
        _print({**result.__dict__, "gate": result.gate.__dict__})
    elif args.command == "refresh-verifier":
        overrides = (
            json.loads(args.config_json.read_text(encoding="utf-8"))
            if args.config_json
            else {}
        )
        result = VerifierRefreshCoordinator(
            registry=PolicyRegistry(args.registry),
            incidents=IncidentMemory(args.incidents),
            output_root=args.output,
            config=VerifierTrainingConfig(**overrides),
            brier_drift_threshold=args.brier_drift_threshold,
        ).run()
        _print(result)
        if not result["refreshed"] and result.get("status", {}).get("due"):
            return 2
    elif args.command == "run-job":
        _load_formal_manifest(args.protocol_manifest)
        load_dotenv(REPO_ROOT / ".env", override=False)
        planner = None
        if os.environ.get("GOOGLE_API_KEY"):
            planner = TicketCollectionPlanner()
        store = SlowLoopStore(args.root)
        worker = SlowLoopWorker(
            store=store,
            registry=PolicyRegistry(args.registry),
            incidents=IncidentMemory(args.incidents),
            protocol_manifest=args.protocol_manifest,
            ticket_root=args.tickets,
            work_root=args.work,
            snapshot_root=args.snapshots,
            ticket_planner=planner,
        )
        job = worker.step(args.job_id) if args.once else worker.run_until_blocked(args.job_id)
        _print(job.__dict__ | {"state": job.state.value})
        if job.state.value == "RETRYABLE_ERROR":
            return 2
    elif args.command == "execute-job-spec":
        result = execute_job_spec(
            args.spec, timeout_seconds=args.timeout_seconds
        )
        _print(result)
        if not result.get("completed"):
            return 4 if not result.get("launched") else 2
    elif args.command == "raw-evaluate":
        manifest = _load_formal_manifest(args.manifest)
        contexts = contexts_from_manifest(manifest, split=args.split)
        executor = HydraRawEpisodeExecutor(
            repo_root=REPO_ROOT,
            python_executable=args.python,
            output_root=args.output,
        )
        evaluator = RawPolicyEvaluator(
            executor=executor,
            ledger_path=args.ledger,
            manifest_hash=manifest["manifest_sha256"],
            max_workers=args.workers,
        )
        summary = evaluator.evaluate(
            policy_id=args.policy_id,
            checkpoint_path=args.checkpoint,
            checkpoint_digest=checkpoint_digest(args.checkpoint),
            contexts=contexts,
        )
        _print(summary.__dict__)
    elif args.command == "policy-gate":
        manifest = _load_formal_manifest(args.manifest)
        ticket = json.loads(args.ticket.read_text(encoding="utf-8"))
        parent = _policy_candidate(
            json.loads(args.parent_json.read_text(encoding="utf-8"))
        )
        candidate_values = json.loads(
            args.candidates_json.read_text(encoding="utf-8")
        )
        if not isinstance(candidate_values, list):
            raise ValueError("--candidates-json must contain a JSON array")
        candidates = tuple(_policy_candidate(value) for value in candidate_values)
        evaluator = RawPolicyEvaluator(
            executor=HydraRawEpisodeExecutor(
                repo_root=REPO_ROOT,
                python_executable=args.python,
                output_root=args.rollout_output,
            ),
            ledger_path=args.ledger,
            manifest_hash=manifest["manifest_sha256"],
            max_workers=args.workers,
        )
        coordinator = PolicyPromotionCoordinator(
            evaluator=evaluator,
            manifest=manifest,
            output_root=args.output,
            bootstrap_draws=args.bootstrap_draws,
        )
        trigger = TriggerTaskEvaluator(
            evaluator=evaluator,
            manifest=manifest,
            ticket=ticket,
        )
        gate_fn = coordinator.run_reuse if args.reuse else coordinator.run
        report = gate_fn(
            parent=parent,
            candidates=candidates,
            trigger_evaluator=trigger,
        )
        _print(report)
        if report["decision"]["status"] != "POLICY_STAGED":
            return 3
    elif args.command == "deploy-gate":
        report = json.loads(args.report.read_text(encoding="utf-8"))
        verifier_result = (
            json.loads(args.verifier_result.read_text(encoding="utf-8"))
            if args.verifier_result
            else None
        )
        signature = (
            json.loads(args.signature.read_text(encoding="utf-8"))
            if args.signature
            else None
        )
        deployment = deploy_policy_gate(
            report=report,
            registry=PolicyRegistry(args.registry),
            expected_revision=args.expected_revision,
            verifier_result=verifier_result,
            incidents=IncidentMemory(args.incidents) if signature else None,
            signature=signature,
        )
        _print(deployment.__dict__)
    elif args.command == "deployed-dev-evaluate":
        manifest = _load_formal_manifest(args.manifest)
        evaluator = RawPolicyEvaluator(
            executor=HydraRawEpisodeExecutor(
                repo_root=REPO_ROOT,
                python_executable=args.python,
                output_root=args.rollout_output,
            ),
            ledger_path=args.ledger,
            manifest_hash=manifest["manifest_sha256"],
            max_workers=args.workers,
        )
        result = DeployedDevelopmentCoordinator(
            registry=PolicyRegistry(args.registry),
            manifest=manifest,
            evaluator=evaluator,
            output_path=args.output,
        ).run(
            expected_revision=args.expected_revision,
            expected_checkpoint_digest=args.expected_checkpoint_digest,
        )
        _print(result)
    elif args.command == "replay-new-policy":
        result = execute_replay_plan(
            args.plan,
            repo_root=args.repo_root,
            device=args.device,
            ledger_path=args.ledger,
        )
        _print(result)
    elif args.command == "collect-verifier-audit":
        manifest = _load_formal_manifest(args.manifest)
        incidents = IncidentMemory(args.incident_root)
        executor = HydraAuditEpisodeExecutor(
            repo_root=REPO_ROOT,
            python_executable=args.python,
            registry_root=args.registry,
            incident_root=args.incident_root,
            snapshot_root=args.snapshot_root,
            slow_loop_root=args.slow_loop_root,
            output_root=args.rollout_output,
            use_guidance=args.use_guidance,
            timeout_seconds=args.episode_timeout,
            gpu_index=args.gpu_index,
        )
        result = AuditCollectionCoordinator(
            manifest=manifest,
            registry=PolicyRegistry(args.registry),
            incidents=incidents,
            snapshot_root=args.snapshot_root,
            executor=executor,
            ledger_path=args.ledger,
            output_path=args.output,
            replay_plan_path=args.replay_plan,
            preflight_path=args.preflight,
            max_workers=args.workers,
            replay_gpu_index=args.gpu_index,
        ).run(limit=args.limit)
        _print(result)
    elif args.command == "final-evaluate":
        manifest = _load_formal_manifest(args.manifest)
        values = json.loads(args.subjects_json.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError("--subjects-json must contain a JSON array")
        subjects = tuple(
            FinalEvaluationSubject.from_mapping(value) for value in values
        )
        coordinator = FinalSealedEvaluationCoordinator(
            manifest=manifest,
            seal_guard=FinalSealGuard(manifest, args.seal_audit),
            ledger_path=args.ledger,
            output_path=args.output,
            executor_factory=make_hydra_executor_factory(
                repo_root=REPO_ROOT,
                python_executable=args.python,
                rollout_root=args.rollout_output,
            ),
            max_workers=args.workers,
        )
        token = None if args.resume else os.environ.get("VLS_FINAL_SEAL_TOKEN")
        result = coordinator.run(
            subjects,
            purpose=args.purpose,
            authorization_token=token,
            resume=args.resume,
        )
        _print(result)
    elif args.command == "throughput-benchmark":
        manifest = _load_formal_manifest(args.manifest)
        contexts = throughput_contexts_from_manifest(manifest)
        benchmark = RolloutThroughputBenchmark(
            executor=HydraRawEpisodeExecutor(
                repo_root=REPO_ROOT,
                python_executable=args.python,
                output_root=args.rollout_output,
            )
        )
        result = benchmark.run(
            policy_id=args.policy_id,
            checkpoint_path=args.checkpoint,
            checkpoint_digest=checkpoint_digest(args.checkpoint),
            contexts=contexts,
            output_path=args.output,
            worker_counts=tuple(args.worker or (8, 16, 32, 64)),
            warmup_contexts=args.warmup_contexts,
        )
        _print(result)
        if not result["passed"]:
            return 2
    return 0


def _working_revision() -> str:
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    diff = subprocess.check_output(
        ["git", "diff", "--binary", "HEAD"], cwd=REPO_ROOT
    )
    import hashlib

    return f"{head}+worktree:{hashlib.sha256(diff).hexdigest()}"


def _policy_candidate(value: object) -> PolicyCandidate:
    if not isinstance(value, dict):
        raise ValueError("policy candidate must be a JSON object")
    payload = dict(value)
    checkpoint = Path(str(payload["checkpoint_path"]))
    digest = payload.get("checkpoint_digest") or checkpoint_digest(checkpoint)
    return PolicyCandidate(
        policy_id=str(payload["policy_id"]),
        checkpoint_path=str(checkpoint),
        checkpoint_digest=str(digest),
        alpha_l=float(payload["alpha_l"]),
    )


def _artifact_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not value:
        raise ValueError("job metadata must be a non-empty JSON object")
    result = dict(value)
    for key, raw in list(result.items()):
        if not key.endswith("_path") or raw is None:
            continue
        path = Path(str(raw)).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        result[key] = str(path)
        result[f"{key}_sha256"] = sha256_file(path)
    return result


def _json_hash(value: object) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
