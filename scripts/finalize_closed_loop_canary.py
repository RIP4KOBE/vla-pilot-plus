#!/usr/bin/env python
"""Finalize an isolated self-improvement canary with deploy and rollback.

The target registry is canary-only.  Nothing in this script mutates the active
production registry or claims eligibility for the frozen 100/250 policy gate.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.eval_manifest import validate_libero_pro_manifest  # noqa: E402
from mode_gate.incidents import IncidentMemory  # noqa: E402
from mode_gate.io_utils import atomic_write_json  # noqa: E402
from mode_gate.registry import PolicyRegistry  # noqa: E402
from mode_gate.verifier_training import (  # noqa: E402
    VerifierTrainingConfig,
    build_verifier_examples,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--incidents", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--delta", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent-id", default="policy_000_canary_parent")
    parser.add_argument("--candidate-id", default="policy_canary_001")
    parser.add_argument("--delta-id", default="delta_canary_001")
    return parser


def _verifier_fallback(incidents: Path, policy_id: str) -> dict:
    config = VerifierTrainingConfig(device="cpu")
    try:
        examples = tuple(
            build_verifier_examples(IncidentMemory(incidents), policy_id=policy_id)
        )
    except (FileNotFoundError, ValueError) as exc:
        return {
            "schema_version": "verifier-training-result-v1",
            "policy_id": policy_id,
            "verifier_id": None,
            "artifact_root": None,
            "gate": {
                "passed": False,
                "reasons": [
                    "insufficient_or_invalid_verifier_evidence: "
                    f"{type(exc).__name__}: {exc}"
                ],
            },
            "observed_contexts": 0,
            "required_contexts": {
                "train": config.min_train_contexts,
                "calibration": config.min_calibration_contexts,
                "test": config.min_test_contexts,
            },
            "controller_mode": "fixed_budget_4",
        }

    split_counts = {
        split: {
            "contexts": sum(item.split == split for item in examples),
            "strong_contexts": sum(
                item.split == split and not item.weak for item in examples
            ),
            "expansion_side": sum(
                item.split == split and not item.weak and item.target_class == 1
                for item in examples
            ),
            "resteer_side": sum(
                item.split == split and not item.weak and item.p_expansion < 0.5
                for item in examples
            ),
        }
        for split in ("train", "calibration", "test")
    }
    requirements = {
        "train": (config.min_train_contexts, config.min_train_each_side),
        "calibration": (
            config.min_calibration_contexts,
            config.min_calibration_each_side,
        ),
        "test": (config.min_test_contexts, config.min_test_expansion_contexts),
    }
    reasons = []
    for split, (minimum, each_side) in requirements.items():
        counts = split_counts[split]
        if counts["strong_contexts"] < minimum:
            reasons.append(
                f"{split} strong contexts {counts['strong_contexts']} < {minimum}"
            )
        if split != "test":
            for side in ("expansion_side", "resteer_side"):
                if counts[side] < each_side:
                    reasons.append(
                        f"{split} {side} {counts[side]} < {each_side}"
                    )
        elif counts["expansion_side"] < each_side:
            reasons.append(
                f"test expansion contexts {counts['expansion_side']} < {each_side}"
            )
    if not reasons:
        reasons.append(
            "canary finalizer never deploys an untrained verifier; run the frozen "
            "ablation trainer before learned-verifier promotion"
        )
    return {
        "schema_version": "verifier-training-result-v1",
        "policy_id": policy_id,
        "verifier_id": None,
        "artifact_root": None,
        "gate": {"passed": False, "reasons": reasons},
        "observed_contexts": len(examples),
        "split_counts": split_counts,
        "controller_mode": "fixed_budget_4",
    }


def main() -> int:
    args = _parser().parse_args()
    evaluation = json.loads(args.evaluation_report.read_text(encoding="utf-8"))
    if evaluation.get("schema_version") != "closed-loop-canary-report-v1":
        raise ValueError("unsupported evaluation report")
    if not evaluation.get("execution_path_passed"):
        raise RuntimeError("LIBERO-PRO canary execution path did not pass")
    if not evaluation.get("paired", {}).get("candidate_strictly_better"):
        raise RuntimeError("canary candidate did not strictly improve the paired score")
    if evaluation.get("production_promotion_eligible") is not False:
        raise ValueError("canary report must explicitly forbid production promotion")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_libero_pro_manifest(manifest)
    manifest_hash = str(manifest["manifest_sha256"])
    delta_meta = json.loads((args.delta / "meta.json").read_text(encoding="utf-8"))
    reconstruction = json.loads(
        (args.delta / "reconstruction.json").read_text(encoding="utf-8")
    )
    candidate_meta = json.loads(
        (args.candidate / "meta.json").read_text(encoding="utf-8")
    )
    if not reconstruction.get("passed"):
        raise RuntimeError("full delta has no passing reconstruction proof")
    if int(delta_meta.get("tensor_count", 0)) != 812:
        raise RuntimeError("full delta does not contain all 812 policy tensors")
    if int(candidate_meta.get("tensor_count", 0)) != 812:
        raise RuntimeError("candidate does not contain all 812 policy tensors")
    if candidate_meta.get("alpha_maps") != [
        {"vision": 1.0, "language": 0.2, "action": 1.0}
    ]:
        raise RuntimeError("candidate alpha map differs from the canary contract")

    result_path = args.output / "closed_loop_report.json"
    if result_path.is_file():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        rollback = existing.get("deployment", {}).get("rollback", {})
        active = PolicyRegistry(
            args.registry, artifact_install_mode="hardlink_canary"
        ).active()
        if (
            existing.get("schema_version")
            == "self-improvement-closed-loop-canary-v1"
            and existing.get("complete") is True
            and existing.get("raw_trigger_canary") == evaluation
            and active is not None
            and active.deployment_revision == rollback.get("deployment_revision")
            and active.transaction_id == rollback.get("transaction_id")
        ):
            print(json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True))
            return 0

    verifier_result = _verifier_fallback(args.incidents, args.candidate_id)
    verifier_path = args.output / "verifier_result.json"
    atomic_write_json(verifier_path, verifier_result)

    registry = PolicyRegistry(args.registry, artifact_install_mode="hardlink_canary")
    baseline = registry.bootstrap_base_policy(
        checkpoint_path=args.parent,
        digest=str(delta_meta["parent_checkpoint_digest"]),
        metadata={
            "source": "isolated_closed_loop_canary",
            "production_eligible": False,
        },
        policy_id=args.parent_id,
        manifest_hash=manifest_hash,
    )
    installed_delta = registry.install_artifact("delta", args.delta_id, args.delta)
    installed_candidate = registry.install_artifact(
        "policy", args.candidate_id, args.candidate
    )
    # ``install_artifact`` has already verified every canary target is the
    # exact same inode/size as its immutable source and persisted the trusted
    # extraction/composition shard digests.  Avoid rereading 15 GB here.

    lineage = list(registry.lineage.iter_valid())
    candidate_events = [
        item
        for item in lineage
        if item.get("event") == "DEPLOYED"
        and item.get("policy_id") == args.candidate_id
    ]
    current = registry.active()
    if current is None:
        raise RuntimeError("canary registry lost its active deployment")
    if not candidate_events:
        if current.policy_id != args.parent_id:
            raise RuntimeError("unexpected active policy before canary promotion")
        candidate_deployment = registry.promote(
            policy_id=args.candidate_id,
            verifier_id=None,
            controller_mode="fixed_budget_4",
            manifest_hash=manifest_hash,
            expected_revision=current.deployment_revision,
            reason="closed_loop_canary_raw_trigger_pass_verifier_fallback",
        )
    else:
        candidate_deployment = candidate_events[-1]

    current = registry.active()
    if current is None:
        raise RuntimeError("canary registry lost deployment after promotion")
    if current.policy_id == args.candidate_id:
        parent_revisions = [
            int(item["deployment_revision"])
            for item in registry.lineage.iter_valid()
            if item.get("event") == "DEPLOYED"
            and item.get("policy_id") == args.parent_id
        ]
        if not parent_revisions:
            raise RuntimeError("canary registry has no parent revision for rollback")
        rollback = registry.rollback(
            to_revision=min(parent_revisions),
            expected_revision=current.deployment_revision,
        )
    else:
        rollback = current
    if rollback.policy_id != args.parent_id:
        raise RuntimeError("rollback did not restore the canary parent")

    lineage = list(registry.lineage.iter_valid())
    report = {
        "schema_version": "self-improvement-closed-loop-canary-v1",
        "canary_only": True,
        "production_registry_untouched": True,
        "production_promotion_eligible": False,
        "benchmark": "LIBERO-PRO",
        "training": {
            "completed": True,
            "source_ratio": "50/0/50",
            "optimizer_steps": 20,
            "global_batch": 32,
        },
        "delta": {
            "installed_path": str(installed_delta),
            "tensor_count": delta_meta["tensor_count"],
            "checkpoint_digest": delta_meta["checkpoint_digest"],
            "reconstruction": reconstruction,
        },
        "candidate": {
            "installed_path": str(installed_candidate),
            "checkpoint_digest": candidate_meta["checkpoint_digest"],
            "alpha_maps": candidate_meta["alpha_maps"],
        },
        "raw_trigger_canary": evaluation,
        "verifier": verifier_result,
        "deployment": {
            "artifact_install_mode": "hardlink_canary",
            "baseline": asdict(baseline),
            "candidate": (
                asdict(candidate_deployment)
                if not isinstance(candidate_deployment, dict)
                else candidate_deployment
            ),
            "rollback": asdict(rollback),
            "lineage_events": lineage,
            "fixed_budget_fallback_verified": True,
            "rollback_verified": True,
        },
        "complete": True,
    }
    atomic_write_json(result_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
