#!/usr/bin/env python
"""Run a small, paired LIBERO-PRO raw/trigger canary for one ticket.

This is an execution-path canary, not a substitute for the frozen 100/250
promotion protocol.  It deliberately uses one seen and one unseen context and
writes a separate resumable ledger under the caller-provided canary directory.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.checkpoint_math import checkpoint_digest  # noqa: E402
from mode_gate.eval_manifest import validate_libero_pro_manifest  # noqa: E402
from mode_gate.io_utils import atomic_write_json  # noqa: E402
from mode_gate.policy_evaluator import (  # noqa: E402
    EvaluationContext,
    HydraRawEpisodeExecutor,
    RawPolicyEvaluator,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ticket", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--parent-id", default="policy_000")
    parser.add_argument("--candidate-id", default="candidate_alpha_0_2")
    parser.add_argument("--parent-digest")
    parser.add_argument("--candidate-digest")
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-episode-steps", type=int, default=240)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    return parser


def _task_for_ticket(manifest: dict, ticket: dict) -> dict:
    identity = (
        str(ticket["suite"]),
        str(ticket["task_id"]),
        str(ticket["perturbation_variant"]),
    )
    matches = [
        task
        for task in manifest["tasks"]
        if (
            str(task["suite"]),
            str(task["task_id"]),
            str(task["perturbation_variant"]),
        )
        == identity
    ]
    if len(matches) != 1:
        raise ValueError(f"ticket identifies {len(matches)} frozen manifest tasks")
    task = dict(matches[0])
    if task.get("benchmark") != "LIBERO-PRO":
        raise ValueError("canary task is not LIBERO-PRO")
    return task


def _context(*, manifest_hash: str, ticket_id: str, task: dict, state: str, split: str) -> EvaluationContext:
    material = (
        f"closed-loop-canary-v1\0{manifest_hash}\0{ticket_id}\0{split}\0"
        f"{task['task_key']}\0{state}"
    )
    digest = hashlib.sha256(material.encode()).digest()
    return EvaluationContext(
        suite=str(task["suite"]),
        task_id=str(task["task_id"]),
        task_index=int(task["task_index"]),
        perturbation_variant=str(task["perturbation_variant"]),
        init_state_id=str(state),
        env_seed=int.from_bytes(digest[:4], "big"),
        policy_seed=int.from_bytes(digest[4:12], "big") % (2**63 - 1),
    )


def main() -> int:
    args = _parser().parse_args()
    if args.max_episode_steps <= 0:
        raise ValueError("--max-episode-steps must be positive")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    ticket = json.loads(args.ticket.read_text(encoding="utf-8"))
    validate_libero_pro_manifest(manifest)
    task = _task_for_ticket(manifest, ticket)

    seen_ids = list(map(str, ticket.get("init_state_ids", ())))
    unseen_ids = list(map(str, ticket.get("eval_init_state_ids", ())))
    if not seen_ids or not unseen_ids:
        raise ValueError("ticket requires non-empty seen and unseen state banks")
    if set(seen_ids).intersection(unseen_ids):
        raise ValueError("seen and unseen ticket states overlap")
    contexts = (
        _context(
            manifest_hash=str(manifest["manifest_sha256"]),
            ticket_id=str(ticket["ticket_id"]),
            task=task,
            state=seen_ids[0],
            split="seen",
        ),
        _context(
            manifest_hash=str(manifest["manifest_sha256"]),
            ticket_id=str(ticket["ticket_id"]),
            task=task,
            state=unseen_ids[0],
            split="unseen",
        ),
    )

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    executor = HydraRawEpisodeExecutor(
        repo_root=REPO_ROOT,
        python_executable=args.python,
        output_root=output / "rollouts",
        timeout_seconds=float(args.timeout_seconds),
        extra_overrides=(
            f"backend.libero.max_episode_steps={args.max_episode_steps}",
        ),
    )
    evaluator = RawPolicyEvaluator(
        executor=executor,
        ledger_path=output / "episodes.jsonl",
        manifest_hash=str(manifest["manifest_sha256"]),
        max_workers=1,
    )
    profile = {
        "kind": "closed_loop_canary_v1",
        "benchmark": "LIBERO-PRO",
        "ticket_id": str(ticket["ticket_id"]),
        "context_splits": ["seen", "unseen"],
        "max_episode_steps": args.max_episode_steps,
        "formal_promotion_eligible": False,
    }
    subjects = (
        (
            args.parent_id,
            args.parent,
            args.parent_digest or checkpoint_digest(args.parent),
        ),
        (
            args.candidate_id,
            args.candidate,
            args.candidate_digest or checkpoint_digest(args.candidate),
        ),
    )
    summaries = {}
    for policy_id, checkpoint, digest in subjects:
        print(
            f"[canary] evaluating {policy_id} on paired seen/unseen LIBERO-PRO contexts",
            flush=True,
        )
        summaries[policy_id] = evaluator.evaluate(
            policy_id=policy_id,
            checkpoint_path=checkpoint,
            checkpoint_digest=digest,
            contexts=contexts,
            metric_role="closed_loop_canary_raw_trigger",
            evaluation_profile=profile,
        )
        print(
            f"[canary] {policy_id}: raw_vector={list(summaries[policy_id].raw_vector)}",
            flush=True,
        )

    parent = summaries[args.parent_id]
    candidate = summaries[args.candidate_id]
    report = {
        "schema_version": "closed-loop-canary-report-v1",
        "canary_only": True,
        "production_promotion_eligible": False,
        "benchmark": "LIBERO-PRO",
        "runtime_suite": task["runtime_suite"],
        "ticket_id": ticket["ticket_id"],
        "task": {
            "suite": task["suite"],
            "task_id": task["task_id"],
            "task_index": task["task_index"],
            "perturbation_variant": task["perturbation_variant"],
        },
        "contexts": {
            "seen": asdict(contexts[0]),
            "unseen": asdict(contexts[1]),
        },
        "raw_profile": {
            "use_guidance": False,
            "mode_gate.enabled": False,
            "use_vlm_stage_recognition": False,
        },
        "evaluation_profile": profile,
        "parent": asdict(parent) | {"raw_vector": list(parent.raw_vector)},
        "candidate": asdict(candidate) | {"raw_vector": list(candidate.raw_vector)},
        "paired": {
            "parent_seen": int(parent.raw_vector[0]),
            "parent_unseen": int(parent.raw_vector[1]),
            "candidate_seen": int(candidate.raw_vector[0]),
            "candidate_unseen": int(candidate.raw_vector[1]),
            "candidate_minus_parent": candidate.macro_sr - parent.macro_sr,
            "candidate_strictly_better": candidate.macro_sr > parent.macro_sr,
        },
        "execution_path_passed": True,
        "formal_gate_required_before_production": True,
    }
    atomic_write_json(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
