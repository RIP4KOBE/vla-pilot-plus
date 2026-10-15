#!/usr/bin/env python3
"""Read-only H2 calibration for reward-degenerate QD selection.

The analysis never writes beside an input. Its sole output must be below the
explicit owned artifact root supplied on the command line.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import torch


SECRET_PATTERNS = (
    re.compile(r"sk-poe-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_action_fingerprint(action: torch.Tensor) -> str:
    canonical = action.detach().to(device="cpu", dtype=torch.float32).contiguous()
    array = canonical.numpy().astype("<f4", copy=False)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def final_archive_rewards(row: dict[str, Any]) -> list[float] | None:
    timeline = row.get("qd_per_cell_elite_reward_by_iter")
    if not isinstance(timeline, list) or not timeline:
        return None
    final = timeline[-1]
    if not isinstance(final, dict) or not final:
        return None
    rewards: list[float] = []
    for value in final.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        resolved = float(value)
        if not math.isfinite(resolved):
            return None
        rewards.append(resolved)
    return rewards


def is_valid_qd_row(row: dict[str, Any]) -> bool:
    if row.get("qd_archive_enabled") is not True:
        return False
    if final_archive_rewards(row) is None:
        return False
    integer_zero_fields = (
        "nonfinite_count",
        "qd_accounting_violation_count",
        "qd_elite_monotonicity_violation_count",
        "qd_final_selection_mismatch_count",
    )
    for name in integer_zero_fields:
        value = row.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            return False
    if row.get("qd_fallback_used", False) is True:
        return False
    return True


def exact_degeneracy(rewards: Iterable[float]) -> tuple[bool, str | None]:
    values = list(rewards)
    if not values or not all(math.isfinite(value) for value in values):
        return False, None
    if not all(value == values[0] for value in values[1:]):
        return False, None
    return True, "exact_zero" if values[0] == 0.0 else "equal_nonzero"


def infer_episode_outcome(metrics_path: Path, episode_index: int) -> str:
    job_root = metrics_path.parent.parent
    candidate_dirs = (
        job_root / f"episode_{episode_index + 1}",
        job_root / f"episode_{episode_index}",
    )
    names: list[str] = []
    for directory in candidate_dirs:
        if directory.is_dir():
            names.extend(path.name.lower() for path in directory.iterdir())
    if any("success" in name for name in names):
        return "success"
    if any("fail" in name or "error" in name for name in names):
        return "fail"
    return "unknown"


def _read_json_lines(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            yield value


def analyze_metric_roots(
    roots: list[tuple[str, Path]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    files: list[dict[str, Any]] = []
    degenerate_records: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    qd_rows = valid_rows = duplicate_rows = 0

    for tier, root in roots:
        for path in sorted(root.rglob("eds_metrics.jsonl")):
            file_valid = file_qd = file_degenerate = 0
            for row in _read_json_lines(path):
                if row.get("qd_archive_enabled") is not True:
                    continue
                qd_rows += 1
                file_qd += 1
                if not is_valid_qd_row(row):
                    continue
                valid_rows += 1
                file_valid += 1
                identity = canonical_json_sha256(row)
                if identity in seen_rows:
                    duplicate_rows += 1
                    continue
                seen_rows.add(identity)
                rewards = final_archive_rewards(row)
                assert rewards is not None
                is_degenerate, kind = exact_degeneracy(rewards)
                if not is_degenerate:
                    continue
                file_degenerate += 1
                episode = row.get("episode")
                outcome = (
                    infer_episode_outcome(path, episode)
                    if isinstance(episode, int) and not isinstance(episode, bool)
                    else "unknown"
                )
                degenerate_records.append(
                    {
                        "source_tier": tier,
                        "source_path": str(path.resolve()),
                        "source_row_sha256": identity,
                        "method_label": row.get("method_label"),
                        "job_id": row.get("job_id"),
                        "task_id": row.get("task_id"),
                        "episode": episode,
                        "global_step": row.get("global_step"),
                        "outcome": outcome,
                        "kind": kind,
                        "reward_value": rewards[0],
                        "occupied_cells": len(rewards),
                        "selected_reward": row.get("selected_reward"),
                        "qd_selected_reward": row.get("qd_selected_reward"),
                        "qd_selected_action_fingerprint": row.get(
                            "qd_selected_action_fingerprint"
                        ),
                        "score_call_count": row.get("score_call_count"),
                        "qd_evaluation_count": row.get("qd_evaluation_count"),
                    }
                )
            files.append(
                {
                    "tier": tier,
                    "path": str(path.resolve()),
                    "sha256": sha256_file(path),
                    "qd_rows": file_qd,
                    "valid_qd_rows": file_valid,
                    "exact_degenerate_rows_before_dedup": file_degenerate,
                }
            )

    degenerate_records.sort(
        key=lambda record: (
            str(record["source_tier"]),
            str(record["source_path"]),
            int(record["episode"] if isinstance(record["episode"], int) else -1),
            int(record["global_step"] if isinstance(record["global_step"], int) else -1),
        )
    )
    task_ids = sorted(
        {
            int(record["task_id"])
            for record in degenerate_records
            if isinstance(record["task_id"], int)
            and not isinstance(record["task_id"], bool)
        }
    )
    by_kind = Counter(str(record["kind"]) for record in degenerate_records)
    by_outcome = Counter(str(record["outcome"]) for record in degenerate_records)
    by_tier = Counter(str(record["source_tier"]) for record in degenerate_records)
    by_task = Counter(str(record["task_id"]) for record in degenerate_records)
    summary = {
        "files": files,
        "metric_file_count": len(files),
        "qd_row_count": qd_rows,
        "valid_qd_row_count": valid_rows,
        "duplicate_valid_row_count": duplicate_rows,
        "unique_valid_qd_row_count": len(seen_rows),
        "exact_degenerate_unique_count": len(degenerate_records),
        "exact_degenerate_task_ids": task_ids,
        "exact_degenerate_task_count": len(task_ids),
        "by_kind": dict(sorted(by_kind.items())),
        "by_outcome": dict(sorted(by_outcome.items())),
        "by_tier": dict(sorted(by_tier.items())),
        "by_task": dict(sorted(by_task.items(), key=lambda item: int(item[0]))),
    }
    return summary, degenerate_records


def select_archive_entry(
    archive: list[dict[str, Any]], *, reverse_fingerprint_tie: bool = False
) -> dict[str, Any]:
    if not archive:
        raise ValueError("archive must be nonempty")
    best_reward = max(float(entry["reward"]) for entry in archive)
    tied = [entry for entry in archive if float(entry["reward"]) == best_reward]
    return sorted(
        tied,
        key=lambda entry: (str(entry["fingerprint"]), int(entry["cell_id"])),
        reverse=reverse_fingerprint_tie,
    )[0]


def analyze_owned_traces(root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    qd_trace_count = selection_match_count = nondegenerate_preserved = 0
    synthetic_tie_policy_changes = input_order_invariant = 0

    for trace_path in sorted(root.rglob("mechanism_trace.pt")):
        # These are trusted, locally generated experiment artifacts.
        trace = torch.load(trace_path, map_location="cpu", weights_only=False)
        qd_info = trace.get("qd_info", {}) if isinstance(trace, dict) else {}
        if qd_info.get("qd_archive_enabled") is not True:
            continue
        timeline_path = trace_path.parent.parent / "qd_archive_timeline.json"
        if not timeline_path.is_file():
            continue
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        if not isinstance(timeline, list) or not timeline:
            continue
        final_archive = timeline[-1].get("archive")
        if not isinstance(final_archive, list) or not final_archive:
            continue
        qd_trace_count += 1

        action_fingerprints: set[str] = set()
        for stage in trace.get("stages", []):
            actions = stage.get("actions") if isinstance(stage, dict) else None
            if torch.is_tensor(actions):
                action_fingerprints.update(
                    canonical_action_fingerprint(action) for action in actions
                )
        archive_fingerprints = {str(entry["fingerprint"]) for entry in final_archive}
        binding_complete = archive_fingerprints.issubset(action_fingerprints)

        selected = select_archive_entry(final_archive)
        recorded_fingerprint = qd_info.get("qd_selected_action_fingerprint")
        selection_match = selected["fingerprint"] == recorded_fingerprint
        selection_match_count += int(selection_match)

        reward_values = [float(entry["reward"]) for entry in final_archive]
        degenerate, _ = exact_degeneracy(reward_values)
        nondegenerate_preserved += int(not degenerate and selection_match)

        equalized_archive = [dict(entry, reward=0.0) for entry in final_archive]
        ascending = select_archive_entry(equalized_archive)
        descending = select_archive_entry(
            equalized_archive, reverse_fingerprint_tie=True
        )
        reversed_input = select_archive_entry(list(reversed(equalized_archive)))
        tie_policy_changes = ascending["fingerprint"] != descending["fingerprint"]
        order_invariant = ascending["fingerprint"] == reversed_input["fingerprint"]
        synthetic_tie_policy_changes += int(tie_policy_changes)
        input_order_invariant += int(order_invariant)

        records.append(
            {
                "trace_path": str(trace_path.resolve()),
                "timeline_path": str(timeline_path.resolve()),
                "task_id": trace.get("metadata", {}).get("task_id"),
                "episode": trace.get("metadata", {}).get("episode"),
                "global_step": trace.get("metadata", {}).get("global_step"),
                "archive_size": len(final_archive),
                "archive_action_binding_complete": binding_complete,
                "recorded_selection_matches_reward_fingerprint_rule": selection_match,
                "nondegenerate": not degenerate,
                "equalized_smallest_fingerprint": ascending["fingerprint"],
                "equalized_largest_fingerprint": descending["fingerprint"],
                "equalized_tie_policy_changes_action": tie_policy_changes,
                "equalized_input_order_invariant": order_invariant,
            }
        )

    return {
        "eligible_qd_trace_count": qd_trace_count,
        "selection_match_count": selection_match_count,
        "nondegenerate_selection_preserved_count": nondegenerate_preserved,
        "equalized_tie_policy_changes_action_count": synthetic_tie_policy_changes,
        "equalized_input_order_invariant_count": input_order_invariant,
        "records": records,
    }


def stage2_is_exact_zero_function(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "stage2_guidance"
    ]
    if len(functions) != 1:
        return False
    returns = [node for node in ast.walk(functions[0]) if isinstance(node, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Call):
        return False
    call = returns[0].value
    if not (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "torch"
        and call.func.attr == "tensor"
        and call.args
    ):
        return False
    value = call.args[0]
    return (
        isinstance(value, ast.Constant)
        and isinstance(value.value, (int, float))
        and not isinstance(value.value, bool)
        and float(value.value) == 0.0
    )


def inspect_control_fallback_path(core_path: Path) -> dict[str, Any]:
    source = core_path.read_text(encoding="utf-8")
    has_qd_guard = "if qd_best_idx is not None" in source
    has_non_qd_argmin = "else int(torch.argmin(population_scores).item())" in source
    has_fixed_score_loop = "for i in range(cfg.cem_iters):" in source
    return {
        "path": str(core_path.resolve()),
        "sha256": sha256_file(core_path),
        "has_qd_selection_guard": has_qd_guard,
        "has_existing_non_qd_argmin_selection": has_non_qd_argmin,
        "has_fixed_cem_iteration_loop": has_fixed_score_loop,
        "maps_to_existing_control_branch": (
            has_qd_guard and has_non_qd_argmin and has_fixed_score_loop
        ),
        "projected_complete_chunk_evaluations": 176,
        "projected_score_calls": 11,
    }


def strict_secret_scan(value: Any) -> int:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return sum(len(pattern.findall(text)) for pattern in SECRET_PATTERNS)


def build_analysis(args: argparse.Namespace) -> dict[str, Any]:
    run_root = args.run_root.resolve()
    historical_root = args.historical_root.resolve()
    stage1_path = args.stage1_guidance.resolve()
    stage2_path = args.stage2_guidance.resolve()
    core_path = args.core_policy.resolve()

    metrics, degenerate_records = analyze_metric_roots(
        [("owned_v1", run_root), ("historical", historical_root)]
    )
    traces = analyze_owned_traces(run_root)
    guidance = {
        "stage1": {
            "path": str(stage1_path),
            "sha256": sha256_file(stage1_path),
        },
        "stage2": {
            "path": str(stage2_path),
            "sha256": sha256_file(stage2_path),
            "is_exact_zero_function": stage2_is_exact_zero_function(stage2_path),
        },
    }
    control_path = inspect_control_fallback_path(core_path)
    gates = {
        "at_least_20_exact_degenerate_chunks": (
            metrics["exact_degenerate_unique_count"] >= 20
        ),
        "at_least_5_tasks": metrics["exact_degenerate_task_count"] >= 5,
        "stage2_exact_zero_verified": guidance["stage2"]["is_exact_zero_function"],
        "fingerprint_tie_is_task_agnostic": (
            traces["eligible_qd_trace_count"] > 0
            and traces["equalized_tie_policy_changes_action_count"]
            == traces["eligible_qd_trace_count"]
            and traces["equalized_input_order_invariant_count"]
            == traces["eligible_qd_trace_count"]
        ),
        "existing_control_path_fixed_compute": control_path[
            "maps_to_existing_control_branch"
        ],
        "nondegenerate_selection_preserved": (
            traces["eligible_qd_trace_count"] > 0
            and traces["selection_match_count"] == traces["eligible_qd_trace_count"]
            and traces["nondegenerate_selection_preserved_count"]
            == traces["eligible_qd_trace_count"]
        ),
    }
    payload = {
        "schema_version": 1,
        "experiment_id": "run_020_quality_selection_calibration",
        "hypothesis_id": "H2",
        "analysis_mode": "read_only_zero_episode",
        "inputs": {
            "run_root": str(run_root),
            "historical_root": str(historical_root),
        },
        "guidance": guidance,
        "metrics": metrics,
        "degenerate_records": degenerate_records,
        "trace_replay": traces,
        "control_fallback_path": control_path,
        "online_feature_exclusions": [
            "future observations",
            "episode success",
            "environment evaluator state",
            "validation result",
            "formal result",
        ],
        "gates": gates,
        "passed": all(gates.values()),
        "online_episode_attempts": 0,
        "gpu_hours": 0.0,
    }
    payload["credential_match_count"] = strict_secret_scan(payload)
    if payload["credential_match_count"]:
        raise RuntimeError("strict credential scan failed")
    payload["analysis_sha256"] = canonical_json_sha256(payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--stage1-guidance", type=Path, required=True)
    parser.add_argument("--stage2-guidance", type=Path, required=True)
    parser.add_argument("--core-policy", type=Path, required=True)
    parser.add_argument("--owned-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    owned_root = args.owned_root.resolve()
    output = args.output.resolve()
    try:
        output.relative_to(owned_root)
    except ValueError as exc:
        raise ValueError("output must be below the owned artifact root") from exc
    payload = build_analysis(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "passed": payload["passed"],
                "analysis_sha256": payload["analysis_sha256"],
                "degenerate_chunks": payload["metrics"][
                    "exact_degenerate_unique_count"
                ],
                "task_count": payload["metrics"]["exact_degenerate_task_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
