#!/usr/bin/env python3
"""Analyze QD parent-quality inheritance from immutable mechanism traces."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Callable

import numpy as np
import torch


EXPECTED_PROFILE_COUNT = 27
EXPECTED_TRACE_COUNT = 540
EXPECTED_STAGE_COUNT = 9000
HISTORICAL_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity"
)


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def family_for(profile: dict[str, Any]) -> str:
    family = profile.get("family")
    if family:
        return "sparse" if "sparse" in str(family) else "uniform"
    return "sparse" if "sparse" in str(profile["label"]) else "uniform"


def valid_profiles(replay: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = [
        profile
        for profile in replay["original_qd_profiles"] + replay["budget_profiles"]
        if profile["valid"]
    ]
    profiles.sort(key=lambda value: value["label"])
    return profiles


def trace_paths(profile: dict[str, Any]) -> list[Path]:
    output_dir = Path(profile["output_dir"])
    return sorted(
        output_dir.glob(
            "eds_eval/qualitative/episode_*/chunk_*/tensors/mechanism_trace.pt"
        )
    )


def finite_float_list(tensor: torch.Tensor) -> list[float]:
    values = tensor.detach().to(device="cpu", dtype=torch.float32).tolist()
    return [float(value) for value in values]


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty list")
    return sum(values) / len(values)


def bootstrap_mean_ci(
    values: list[float],
    *,
    seed: int,
    resamples: int,
) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "ci95_low": None, "ci95_high": None}
    array = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    for start in range(0, resamples, 1000):
        width = min(1000, resamples - start)
        indices = rng.integers(0, len(array), size=(width, len(array)))
        draws[start : start + width] = array[indices].mean(axis=1)
    return {
        "count": len(values),
        "mean": float(array.mean()),
        "ci95_low": float(np.quantile(draws, 0.025)),
        "ci95_high": float(np.quantile(draws, 0.975)),
    }


def summarize_traces(
    records: list[dict[str, Any]],
    *,
    seed: int,
    resamples: int,
) -> dict[str, Any]:
    margins = [float(record["top_bottom_margin"]) for record in records]
    rank1 = [float(record["rank1_bottom_margin"]) for record in records]
    top_slots = [float(record["top_slot_share"]) for record in records]
    return {
        "trace_count": len(records),
        "top_bottom_margin_mean": mean(margins) if margins else None,
        "top_bottom_margin_median": median(margins) if margins else None,
        "top_bottom_margin_positive_ratio": (
            sum(value > 0.0 for value in margins) / len(margins) if margins else None
        ),
        "top_bottom_margin_bootstrap": bootstrap_mean_ci(
            margins, seed=seed, resamples=resamples
        ),
        "rank1_bottom_margin_mean": mean(rank1) if rank1 else None,
        "rank1_bottom_margin_median": median(rank1) if rank1 else None,
        "top_slot_share_mean": mean(top_slots) if top_slots else None,
        "top_slot_share_median": median(top_slots) if top_slots else None,
        "saturated_iteration_count": sum(
            int(record["saturated_iteration_count"]) for record in records
        ),
    }


def subgroup_summaries(
    records: list[dict[str, Any]],
    *,
    seed: int,
    resamples: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    groups: dict[str, Callable[[dict[str, Any]], bool]] = {
        "uniform": lambda record: record["family"] == "uniform",
        "sparse": lambda record: record["family"] == "sparse",
        "historical_success_episode": lambda record: record["historical_success"],
        "historical_failure_episode": lambda record: not record["historical_success"],
    }
    for task_id in (3, 5, 8, 9):
        groups[f"task_{task_id}"] = lambda record, task_id=task_id: record["task_id"] == task_id
    for offset, (name, predicate) in enumerate(groups.items(), start=1):
        selected = [record for record in records if predicate(record)]
        output[name] = summarize_traces(
            selected,
            seed=seed + offset,
            resamples=resamples,
        )
    return output


def gate(name: str, passed: bool, observed: Any, criterion: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "observed": observed,
        "criterion": criterion,
    }


def analyze_trace(
    path: Path,
    *,
    profile: dict[str, Any],
    source_sha256: str,
) -> tuple[dict[str, Any] | None, list[str], int, int]:
    failures: list[str] = []
    try:
        trace = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as error:  # noqa: BLE001 - surfaced as validity evidence
        return None, [f"unsafe_or_failed_load:{type(error).__name__}:{error}"], 0, 0
    if not isinstance(trace, dict):
        return None, ["trace_not_dict"], 0, 0

    metadata = trace.get("metadata") or {}
    qd_info = trace.get("qd_info") or {}
    stages = [
        stage
        for stage in trace.get("stages", [])
        if stage.get("stage") == "full_process_after_rollout"
    ]
    expected_iters = int(metadata.get("cem_iters", -1))
    population_size = int(metadata.get("population_size", -1))
    coverage = qd_info.get("qd_coverage_ratio_by_iter") or []
    slots_by_iter = qd_info.get("qd_parent_slots_by_cell_by_iter") or []
    if len(stages) != expected_iters:
        failures.append(f"stage_count:{len(stages)}!={expected_iters}")
    if len(coverage) != expected_iters:
        failures.append(f"coverage_count:{len(coverage)}!={expected_iters}")
    if len(slots_by_iter) != expected_iters:
        failures.append(f"slot_map_count:{len(slots_by_iter)}!={expected_iters}")

    saturated_margins: list[float] = []
    saturated_rank1_margins: list[float] = []
    saturated_slot_shares: list[float] = []
    child_count = 0
    for stage in stages:
        iter_idx = int(stage.get("iter_idx", -1))
        ranks_tensor = stage.get("parent_ranks")
        rewards_tensor = stage.get("rewards")
        if not isinstance(ranks_tensor, torch.Tensor):
            failures.append(f"iter_{iter_idx}:missing_parent_ranks")
            continue
        if not isinstance(rewards_tensor, torch.Tensor):
            failures.append(f"iter_{iter_idx}:missing_rewards")
            continue
        ranks = [int(value) for value in ranks_tensor.detach().cpu().tolist()]
        rewards = finite_float_list(rewards_tensor)
        if len(ranks) != population_size or len(rewards) != population_size:
            failures.append(
                f"iter_{iter_idx}:population_mismatch:{len(ranks)}:{len(rewards)}:{population_size}"
            )
            continue
        if any(not math.isfinite(value) for value in rewards):
            failures.append(f"iter_{iter_idx}:nonfinite_reward")
            continue
        if sorted(ranks) != list(range(1, population_size + 1)):
            failures.append(f"iter_{iter_idx}:occurrence_ranks_not_permutation")
            continue
        child_count += len(rewards)
        if iter_idx >= len(slots_by_iter) or not isinstance(slots_by_iter[iter_idx], dict):
            failures.append(f"iter_{iter_idx}:missing_slot_map")
            continue
        slot_map = {
            int(cell): int(count)
            for cell, count in slots_by_iter[iter_idx].items()
        }
        parent_cells = [
            cell
            for cell in sorted(slot_map)
            for _ in range(slot_map[cell])
        ]
        if len(parent_cells) != population_size:
            failures.append(
                f"iter_{iter_idx}:slot_population_mismatch:{len(parent_cells)}:{population_size}"
            )
            continue
        if any(count <= 0 for count in slot_map.values()):
            failures.append(f"iter_{iter_idx}:nonpositive_slot_count")
            continue
        if len(slot_map) != 16:
            continue
        cell_rank_scores = {
            cell: mean(
                [
                    float(rank)
                    for parent_cell, rank in zip(parent_cells, ranks)
                    if parent_cell == cell
                ]
            )
            for cell in slot_map
        }
        quality_order = sorted(
            slot_map,
            key=lambda cell: (cell_rank_scores[cell], cell),
        )
        top_cells = set(quality_order[:4])
        bottom_cells = set(quality_order[-4:])
        best_cell = quality_order[0]
        top = [
            reward
            for cell, reward in zip(parent_cells, rewards)
            if cell in top_cells
        ]
        bottom = [
            reward
            for cell, reward in zip(parent_cells, rewards)
            if cell in bottom_cells
        ]
        rank1 = [
            reward
            for cell, reward in zip(parent_cells, rewards)
            if cell == best_cell
        ]
        if not top or not bottom or not rank1:
            failures.append(f"iter_{iter_idx}:missing_saturated_rank_group")
            continue
        saturated_margins.append(mean(top) - mean(bottom))
        saturated_rank1_margins.append(mean(rank1) - mean(bottom))
        saturated_slot_shares.append(len(top) / population_size)

    task_id = int(metadata.get("task_id", -1))
    episode = int(metadata.get("episode", -1))
    record = None
    if saturated_margins:
        record = {
            "path": str(path),
            "source_sha256": source_sha256,
            "profile": profile["label"],
            "study": profile["study"],
            "family": family_for(profile),
            "task_id": task_id,
            "episode": episode,
            "global_step": int(metadata.get("global_step", -1)),
            "historical_success": task_id in profile["success_tasks"],
            "population_size": population_size,
            "cem_iters": expected_iters,
            "stage_count": len(stages),
            "saturated_iteration_count": len(saturated_margins),
            "top_bottom_margin": mean(saturated_margins),
            "rank1_bottom_margin": mean(saturated_rank1_margins),
            "top_slot_share": mean(saturated_slot_shares),
        }
    del trace
    return record, failures, len(stages), child_count


def build_analysis(
    replay: dict[str, Any],
    *,
    replay_path: Path,
    bootstrap_seed: int,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    profiles = valid_profiles(replay)
    inventory: list[tuple[dict[str, Any], Path]] = []
    profile_trace_counts: dict[str, int] = {}
    root_failures: list[str] = []
    for profile in profiles:
        paths = trace_paths(profile)
        profile_trace_counts[profile["label"]] = len(paths)
        for path in paths:
            if not is_relative_to(path, HISTORICAL_ROOT):
                root_failures.append(str(path))
            inventory.append((profile, path))
    inventory.sort(key=lambda item: str(item[1]))

    records: list[dict[str, Any]] = []
    trace_failures: list[dict[str, Any]] = []
    source_inventory: list[dict[str, Any]] = []
    total_stages = 0
    total_children = 0
    for index, (profile, path) in enumerate(inventory, start=1):
        checksum = sha256_file(path)
        source_inventory.append(
            {"path": str(path), "size_bytes": path.stat().st_size, "sha256": checksum}
        )
        record, failures, stage_count, child_count = analyze_trace(
            path,
            profile=profile,
            source_sha256=checksum,
        )
        total_stages += stage_count
        total_children += child_count
        if record is not None:
            records.append(record)
        if failures:
            trace_failures.append({"path": str(path), "failures": failures})
        if index % 20 == 0:
            gc.collect()

    overall = summarize_traces(
        records,
        seed=bootstrap_seed,
        resamples=bootstrap_resamples,
    )
    subgroups = subgroup_summaries(
        records,
        seed=bootstrap_seed,
        resamples=bootstrap_resamples,
    )
    uniform = subgroups["uniform"]
    sparse = subgroups["sparse"]
    bootstrap = overall["top_bottom_margin_bootstrap"]
    validity_gates = [
        gate(
            "profile_accounting",
            len(profiles) == EXPECTED_PROFILE_COUNT,
            len(profiles),
            f"exactly {EXPECTED_PROFILE_COUNT} valid profiles",
        ),
        gate(
            "trace_accounting",
            len(inventory) == EXPECTED_TRACE_COUNT
            and total_stages == EXPECTED_STAGE_COUNT
            and not trace_failures,
            {
                "trace_count": len(inventory),
                "stage_count": total_stages,
                "trace_failures": len(trace_failures),
                "per_profile_trace_counts": profile_trace_counts,
            },
            f"exactly {EXPECTED_TRACE_COUNT} traces and {EXPECTED_STAGE_COUNT} metadata-matched stages with no trace failures",
        ),
        gate(
            "source_roots",
            not root_failures,
            root_failures,
            f"all traces under immutable {HISTORICAL_ROOT}",
        ),
    ]
    h4_gates = [
        gate(
            "saturated_iteration_support",
            int(overall["saturated_iteration_count"]) >= 2700,
            overall["saturated_iteration_count"],
            ">=2700 saturated trace-iterations",
        ),
        gate(
            "quality_blind_slot_share",
            uniform["top_slot_share_mean"] is not None
            and sparse["top_slot_share_mean"] is not None
            and float(uniform["top_slot_share_mean"]) <= 0.35
            and float(sparse["top_slot_share_mean"]) <= 0.35,
            {
                "uniform": uniform["top_slot_share_mean"],
                "sparse": sparse["top_slot_share_mean"],
            },
            "mean top-quartile slot share <=0.35 in both families",
        ),
        gate(
            "overall_inheritance_bootstrap",
            bootstrap["ci95_low"] is not None and float(bootstrap["ci95_low"]) > 0.0,
            bootstrap,
            "trace-cluster bootstrap 95% CI lower bound >0",
        ),
        gate(
            "family_inheritance",
            uniform["top_bottom_margin_median"] is not None
            and sparse["top_bottom_margin_median"] is not None
            and float(uniform["top_bottom_margin_median"]) > 0.0
            and float(sparse["top_bottom_margin_median"]) > 0.0,
            {
                "uniform_median": uniform["top_bottom_margin_median"],
                "sparse_median": sparse["top_bottom_margin_median"],
            },
            "median per-trace top-minus-bottom margin >0 in both families",
        ),
        gate(
            "rank1_inheritance",
            overall["rank1_bottom_margin_median"] is not None
            and float(overall["rank1_bottom_margin_median"]) > 0.0,
            overall["rank1_bottom_margin_median"],
            "overall median per-trace rank1-minus-bottom margin >0",
        ),
    ]
    validity_passed = all(item["passed"] for item in validity_gates)
    h4_supported = validity_passed and all(item["passed"] for item in h4_gates)
    if not validity_passed:
        decision = "INVALID_REPAIR_ANALYZER"
        next_direction = "repair_run_001_under_versioned_protocol"
    elif h4_supported:
        decision = "KEEP_DIAGNOSTIC_EVIDENCE"
        next_direction = "run_010_quality_reserve_candidate"
    else:
        decision = "REJECT_H4_ALLOCATION_CANDIDATE"
        next_direction = "run_002_partition_diagnostic"

    inventory_digest = hashlib.sha256()
    for item in source_inventory:
        inventory_digest.update(canonical_json_bytes(item))
    prospective_margin = overall["top_bottom_margin_mean"]
    return {
        "schema": "eds-qd-allocation-ecology-diagnostic-v1",
        "experiment_id": "run_001_allocation_ecology_diagnostic",
        "protocol_v1_commit": "dcf234b6999165de0a5bca4a8e44332896cc61dc",
        "protocol_v2_commit": "91ddd34f64d129549147f42c64244b552398a624",
        "protocol_v3_commit": "f6d7bc9a1d579fcbb55e36905beafd1a2ba8264c",
        "protocol_v4_commit": "3d320f6a143a74cbc31625f2f12ccdd77995c7f4",
        "behavior_changed": False,
        "online_episode_attempts": 0,
        "gpu_hours": 0,
        "replay_analysis_path": str(replay_path),
        "replay_analysis_sha256": sha256_file(replay_path),
        "bootstrap_seed": bootstrap_seed,
        "bootstrap_resamples": bootstrap_resamples,
        "profile_count": len(profiles),
        "trace_count": len(inventory),
        "stage_count": total_stages,
        "child_record_count": total_children,
        "saturated_trace_count": len(records),
        "source_inventory_sha256": inventory_digest.hexdigest(),
        "source_inventory": source_inventory,
        "trace_failures": trace_failures,
        "root_failures": root_failures,
        "overall": overall,
        "subgroups": subgroups,
        "prospective_4_of_16_estimate": {
            "assumption": "four bottom-quartile draws are replaced by draws from the observed top-quartile child-yield distribution",
            "observed_top_minus_bottom_child_reward": prospective_margin,
            "estimated_population_reward_sum_delta": (
                4.0 * float(prospective_margin) if prospective_margin is not None else None
            ),
            "estimated_population_mean_reward_delta": (
                0.25 * float(prospective_margin) if prospective_margin is not None else None
            ),
            "limitation": "saved offspring do not contain the additional children; this is an expectation estimate, not an executed counterfactual",
        },
        "validity_gates": validity_gates,
        "h4_support_gates": h4_gates,
        "validity_passed": validity_passed,
        "h4_supported": h4_supported,
        "decision": decision,
        "next_direction": next_direction,
        "target": {"best_qd": 2, "required": 5, "gap_before": 3, "gap_after": 3},
        "observations": [
            "Slot shares and child rewards are measured only when the pre-update parent slot map contains all 16 cells with positive counts.",
            "Each trace contributes one aggregate value regardless of population size or iteration count.",
            "Historical success labels are descriptive strata and do not convert this replay into new task evidence.",
        ],
    }


def render_summary(analysis: dict[str, Any]) -> str:
    overall = analysis["overall"]
    uniform = analysis["subgroups"]["uniform"]
    sparse = analysis["subgroups"]["sparse"]
    bootstrap = overall["top_bottom_margin_bootstrap"]
    lines = [
        "# `run_001_allocation_ecology_diagnostic` Summary",
        "",
        f"Decision: `{analysis['decision']}`. H4 supported: `{str(analysis['h4_supported']).lower()}`.",
        "",
        "This is a zero-episode saved-trace diagnostic. The best remains `2/10`; target gap remains `3`.",
        "",
        "## Accounting",
        "",
        f"- Profiles/traces/stages: `{analysis['profile_count']}` / `{analysis['trace_count']}` / `{analysis['stage_count']}`.",
        f"- Saturated trace-iterations: `{overall['saturated_iteration_count']}`.",
        f"- Child records: `{analysis['child_record_count']}`.",
        f"- Trace failures / root failures: `{len(analysis['trace_failures'])}` / `{len(analysis['root_failures'])}`.",
        "",
        "## Primary result",
        "",
        f"- Overall top-minus-bottom margin: mean `{overall['top_bottom_margin_mean']}`, median `{overall['top_bottom_margin_median']}`.",
        f"- Trace-cluster bootstrap 95% CI: `[{bootstrap['ci95_low']}, {bootstrap['ci95_high']}]`.",
        f"- Top-quartile slot share: uniform `{uniform['top_slot_share_mean']}`, sparse `{sparse['top_slot_share_mean']}`.",
        f"- Family median margins: uniform `{uniform['top_bottom_margin_median']}`, sparse `{sparse['top_bottom_margin_median']}`.",
        f"- Rank-1-minus-bottom overall median: `{overall['rank1_bottom_margin_median']}`.",
        "",
        "## Gates",
        "",
        "| Gate | Result | Criterion |",
        "| --- | --- | --- |",
    ]
    for item in analysis["validity_gates"] + analysis["h4_support_gates"]:
        lines.append(
            f"| `{item['name']}` | `{'PASS' if item['passed'] else 'FAIL'}` | {item['criterion']} |"
        )
    lines.extend(
        [
            "",
            "Historical success/failure and task 3/5/8/9 strata are descriptive only; see `analysis.json`.",
            "",
            f"Next direction: `{analysis['next_direction']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-analysis", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--bootstrap-seed", type=int, required=True)
    parser.add_argument("--bootstrap-resamples", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    torch.set_num_threads(1)
    replay = load_json(args.replay_analysis)
    analysis = build_analysis(
        replay,
        replay_path=args.replay_analysis,
        bootstrap_seed=args.bootstrap_seed,
        bootstrap_resamples=args.bootstrap_resamples,
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(analysis)
    (args.output_root / "analysis.json").write_bytes(payload)
    (args.output_root / "summary.md").write_text(render_summary(analysis), encoding="utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    (args.output_root / "analysis.json.sha256").write_text(
        f"{digest}  analysis.json\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "analysis_sha256": digest,
                "decision": analysis["decision"],
                "h4_supported": analysis["h4_supported"],
                "next_direction": analysis["next_direction"],
                "output_root": str(args.output_root),
                "validity_passed": analysis["validity_passed"],
            },
            sort_keys=True,
        )
    )
    return 0 if analysis["validity_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
