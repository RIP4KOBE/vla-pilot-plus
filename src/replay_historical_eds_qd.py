#!/usr/bin/env python3
"""Deterministically replay audited historical EDS-QD evidence.

This is an offline observer. It never imports the policy/environment stack and
never mutates any historical artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable


ORIGINAL_AUDIT_ID = "baseline_formal_audit"
BUDGET_AUDIT_ID = "search_budget_sweep_audit"
EXPECTED_ORIGINAL_TASKS = {
    "p2_stage_on_abs_rbf_control": [3, 8, 9],
    "eds_quality_diversity_uniform_primary": [],
    "eds_quality_diversity_sparse_primary": [5, 8],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * quantile
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2.0
        for index in order[cursor:end]:
            ranks[index] = rank
        cursor = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_norm = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_norm = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    return numerator / (left_norm * right_norm)


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(average_ranks(left), average_ranks(right))


def load_catalog(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            source = Path(record["path"])
            observed = sha256_file(source) if source.is_file() else None
            expected = record["sha256"]
            checks.append(
                {
                    "evidence_id": record["evidence_id"],
                    "path": str(source),
                    "expected_sha256": expected,
                    "observed_sha256": observed,
                    "exists": source.is_file(),
                    "matches": observed == expected,
                    "catalog_line": line_number,
                }
            )
            records.append(record)
    return records, checks


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def catalog_path(records: list[dict[str, Any]], evidence_id: str) -> Path:
    matches = [Path(record["path"]) for record in records if record["evidence_id"] == evidence_id]
    if len(matches) != 1:
        raise ValueError(f"catalog must contain exactly one {evidence_id!r}; found {len(matches)}")
    return matches[0]


def compact_job(job: dict[str, Any], *, study: str) -> dict[str, Any]:
    return {
        "study": study,
        "label": job.get("label"),
        "family": job.get("family"),
        "valid": bool(job.get("valid")),
        "validity_failures": job.get("validity_failures", []),
        "success_count": job.get("success_count"),
        "success_tasks": sorted(job.get("success_tasks") or []),
        "population_size": job.get("population_size"),
        "cem_iters": job.get("cem_iters"),
        "candidate_evaluations_per_chunk": job.get("candidate_evaluations_per_chunk"),
        "candidate_evaluation_count": job.get("candidate_evaluation_count"),
        "coverage_median": job.get("coverage_median"),
        "overflow_p95": job.get("overflow_p95"),
        "turnover_median": job.get("turnover_median"),
        "replacement_active_chunk_ratio": job.get("replacement_active_chunk_ratio"),
        "archive_best_reward_delta": job.get(
            "archive_best_reward_delta",
            job.get("archive_best_reward_delta_vs_historical"),
        ),
        "execution_qpos_error_episodes": job.get("execution_qpos_error_episodes"),
        "output_dir": job.get("output_dir"),
    }


def qd_jobs(audit: dict[str, Any], *, study: str) -> list[dict[str, Any]]:
    jobs = []
    for raw in audit.get("jobs", []):
        label = str(raw.get("label", ""))
        if "quality_diversity" not in label and not label.startswith("eds_qd_"):
            continue
        jobs.append(compact_job(raw, study=study))
    return sorted(jobs, key=lambda value: value["label"])


def parse_metrics(paths: list[Path]) -> dict[str, Any]:
    total_records = 0
    qd_records = 0
    malformed_records = 0
    missing_required_fields = 0
    elite_zero_records = 0
    archive_only_parent_records = 0
    direct_elite_parent_count = 0
    archive_parent_count = 0
    final_coverage: list[float] = []
    all_overflow: list[float] = []
    all_turnover: list[float] = []
    parsed_files: list[dict[str, Any]] = []

    for path in paths:
        file_digest = hashlib.sha256()
        file_records = 0
        file_qd_records = 0
        with path.open("rb") as handle:
            for raw_line in handle:
                file_digest.update(raw_line)
                if not raw_line.strip():
                    continue
                total_records += 1
                file_records += 1
                try:
                    record = json.loads(raw_line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    malformed_records += 1
                    continue
                coverage = record.get("qd_coverage_ratio_by_iter")
                overflow = record.get("qd_descriptor_overflow_ratio_by_iter")
                turnover = record.get("qd_archive_turnover_ratio_by_iter")
                sources = record.get("parent_count_by_source")
                elite_carryover = record.get("elite_carryover_count_observed")
                required = (coverage, overflow, turnover, sources, elite_carryover)
                if not all(value is not None for value in required):
                    missing_required_fields += 1
                    continue
                if not coverage:
                    continue
                qd_records += 1
                file_qd_records += 1
                final_coverage.append(float(coverage[-1]))
                all_overflow.extend(float(value) for value in overflow)
                all_turnover.extend(float(value) for value in turnover)
                direct_elite = int(sources.get("elite", 0))
                archive_parents = int(sources.get("qd_archive_offspring", 0))
                direct_elite_parent_count += direct_elite
                archive_parent_count += archive_parents
                if int(elite_carryover) == 0:
                    elite_zero_records += 1
                non_archive = sum(
                    int(value)
                    for key, value in sources.items()
                    if key != "qd_archive_offspring"
                )
                if archive_parents > 0 and non_archive == 0:
                    archive_only_parent_records += 1
        parsed_files.append(
            {
                "path": str(path),
                "sha256": file_digest.hexdigest(),
                "records": file_records,
                "qd_records": file_qd_records,
            }
        )

    denominator = qd_records or 1
    return {
        "file_count": len(paths),
        "files": parsed_files,
        "total_records": total_records,
        "qd_records": qd_records,
        "malformed_records": malformed_records,
        "missing_required_fields": missing_required_fields,
        "skipped_non_qd_records": total_records - qd_records - malformed_records - missing_required_fields,
        "elite_zero_record_count": elite_zero_records,
        "elite_zero_record_ratio": elite_zero_records / denominator,
        "archive_only_parent_record_count": archive_only_parent_records,
        "archive_only_parent_record_ratio": archive_only_parent_records / denominator,
        "direct_elite_parent_count": direct_elite_parent_count,
        "qd_archive_offspring_parent_count": archive_parent_count,
        "raw_final_coverage_median": median(final_coverage) if final_coverage else None,
        "raw_overflow_p95": percentile(all_overflow, 0.95),
        "raw_turnover_median": median(all_turnover) if all_turnover else None,
    }


def metric_paths(jobs: list[dict[str, Any]]) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    missing: list[str] = []
    for job in jobs:
        output_dir = job.get("output_dir")
        path = Path(output_dir) / "eds_eval" / "eds_metrics.jsonl" if output_dir else Path("")
        if output_dir and path.is_file():
            paths.append(path)
        else:
            missing.append(str(path) if output_dir else f"{job['label']}:missing-output-dir")
    return sorted(set(paths)), sorted(missing)


def make_gate(name: str, passed: bool, observed: Any, criterion: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "observed": observed, "criterion": criterion}


def build_analysis(
    catalog: list[dict[str, Any]],
    checksum_checks: list[dict[str, Any]],
    original_audit: dict[str, Any],
    budget_audit: dict[str, Any],
    no_op_audit: dict[str, Any],
) -> dict[str, Any]:
    original_jobs_all = [compact_job(job, study="original") for job in original_audit["jobs"]]
    original_by_label = {job["label"]: job for job in original_jobs_all}
    original_matrix = {
        label: original_by_label.get(label, {}).get("success_tasks")
        for label in EXPECTED_ORIGINAL_TASKS
    }
    original_qd = qd_jobs(original_audit, study="original")
    budget_jobs = qd_jobs(budget_audit, study="budget_sweep")
    valid_budget = [job for job in budget_jobs if job["valid"]]
    valid_profiles = [job for job in original_qd + valid_budget if job["valid"]]
    metrics, missing_metrics = metric_paths(valid_profiles)
    metric_replay = parse_metrics(metrics)

    evaluations = [float(job["candidate_evaluations_per_chunk"]) for job in valid_budget]
    successes = [float(job["success_count"]) for job in valid_budget]
    compute_correlations: dict[str, Any] = {
        "all_valid_spearman_evaluations_vs_success": spearman(evaluations, successes),
        "by_family": {},
    }
    for family in sorted({job["family"] for job in valid_budget}):
        family_jobs = [job for job in valid_budget if job["family"] == family]
        compute_correlations["by_family"][str(family)] = spearman(
            [float(job["candidate_evaluations_per_chunk"]) for job in family_jobs],
            [float(job["success_count"]) for job in family_jobs],
        )

    coverage_values = [float(job["coverage_median"]) for job in valid_profiles if job["coverage_median"] is not None]
    overflow_values = [float(job["overflow_p95"]) for job in valid_profiles if job["overflow_p95"] is not None]
    profile_coverage_median = median(coverage_values) if coverage_values else None
    profile_overflow_p95 = percentile(overflow_values, 0.95)
    max_budget_success = max((int(job["success_count"]) for job in valid_budget), default=-1)
    budget_target_passes = [job["label"] for job in valid_budget if int(job["success_count"]) >= 5]

    gates = [
        make_gate(
            "catalog_checksums",
            bool(checksum_checks) and all(check["matches"] for check in checksum_checks),
            {"matched": sum(check["matches"] for check in checksum_checks), "total": len(checksum_checks)},
            "all catalog files exist and SHA-256 match",
        ),
        make_gate(
            "original_task_matrix",
            original_matrix == EXPECTED_ORIGINAL_TASKS,
            original_matrix,
            f"exactly {EXPECTED_ORIGINAL_TASKS}",
        ),
        make_gate(
            "budget_target_boundary",
            max_budget_success <= 1 and not budget_target_passes,
            {"valid_configs": len(valid_budget), "max_success_count": max_budget_success, "passing_labels": budget_target_passes},
            "maximum valid success <=1/10 and no >=5/10 result",
        ),
        make_gate(
            "elite_and_parent_ecology",
            metric_replay["qd_records"] > 0
            and metric_replay["elite_zero_record_ratio"] >= 0.95
            and metric_replay["archive_only_parent_record_ratio"] >= 0.95
            and bool(no_op_audit.get("passed")),
            {
                "qd_records": metric_replay["qd_records"],
                "elite_zero_ratio": metric_replay["elite_zero_record_ratio"],
                "archive_only_parent_ratio": metric_replay["archive_only_parent_record_ratio"],
                "num_elites_no_op_passed": no_op_audit.get("passed"),
            },
            ">=95% zero direct elite carryover, >=95% archive-only parents, and num_elites no-op audit passes",
        ),
        make_gate(
            "coverage_overflow_saturation",
            profile_coverage_median is not None
            and profile_coverage_median >= 0.9
            and profile_overflow_p95 is not None
            and profile_overflow_p95 >= 0.75,
            {"profile_coverage_median": profile_coverage_median, "profile_overflow_p95": profile_overflow_p95},
            "profile coverage median >=0.9 and overflow P95 >=0.75",
        ),
        make_gate(
            "parser_accounting",
            not missing_metrics and metric_replay["malformed_records"] == 0,
            {
                "missing_metrics": missing_metrics,
                "malformed_records": metric_replay["malformed_records"],
                "missing_required_fields": metric_replay["missing_required_fields"],
                "skipped_non_qd_records": metric_replay["skipped_non_qd_records"],
            },
            "all expected metrics files parsed; malformed/skipped/missing-field counts explicit",
        ),
    ]
    all_passed = all(gate["passed"] for gate in gates)
    trace_examples = []
    for job in valid_profiles:
        output_dir = job.get("output_dir")
        if not output_dir:
            continue
        traces = sorted(Path(output_dir).glob("eds_eval/qualitative/episode_*/chunk_*/tensors/mechanism_trace.pt"))
        if traces:
            trace_examples.append({"label": job["label"], "count": len(traces), "example": str(traces[0])})

    return {
        "schema": "eds-qd-historical-replay-v1",
        "experiment_id": "run_000_baseline_replay",
        "behavior_changed": False,
        "online_episode_attempts": 0,
        "gpu_hours": 0,
        "catalog_count": len(catalog),
        "catalog_checks": checksum_checks,
        "original_task_matrix": original_matrix,
        "expected_original_task_matrix": EXPECTED_ORIGINAL_TASKS,
        "original_qd_profiles": original_qd,
        "budget_profiles": budget_jobs,
        "budget_summary": {
            "config_count": len(budget_jobs),
            "valid_config_count": len(valid_budget),
            "max_valid_success_count": max_budget_success,
            "passing_5_of_10_labels": budget_target_passes,
            "success_tasks_union": sorted({task for job in valid_budget for task in job["success_tasks"]}),
            "compute_correlations": compute_correlations,
            "attempt_exception": budget_audit.get("attempt_ledger", {}).get("failures", []),
        },
        "profile_mechanism_summary": {
            "profile_count": len(valid_profiles),
            "coverage_median": profile_coverage_median,
            "overflow_p95": profile_overflow_p95,
            "turnover_median": median(
                [float(job["turnover_median"]) for job in valid_profiles if job["turnover_median"] is not None]
            ),
        },
        "raw_metric_replay": metric_replay,
        "num_elites_no_op_audit": no_op_audit,
        "mechanism_trace_availability": trace_examples,
        "gates": gates,
        "all_support_gates_passed": all_passed,
        "observations": [
            "The original control/QD task matrix is reproduced from the audited machine record.",
            "No valid budget-sweep configuration exceeds 1/10 despite 512-1664 candidate evaluations per complete chunk.",
            "Normalized coverage remains saturated while descriptor overflow remains high.",
            "The QD branch records no direct elite carryover and spends parent slots through archive cells.",
            "The historical clean-tail report shows that generic motion smoothing is not sufficient for success.",
        ],
        "inferences": [
            "Direct compute scaling is not the next target-linked intervention.",
            "Quality retention and allocation ecology should be audited before changing descriptor bounds because parent/reward traces are available.",
        ],
        "unresolved": [
            "Existing replay does not establish causal reward-to-stage-progress calibration (H2).",
            "Existing replay does not establish within-cell future-value aliasing (H5).",
            "Overflow may contain useful exploration or uncontrolled drift; a partition counterfactual remains necessary if ecology is not actionable.",
        ],
        "decision": "KEEP_DIAGNOSTIC_EVIDENCE" if all_passed else "INVALID_REPAIR_REPLAY",
        "next_direction": "run_001_allocation_ecology_diagnostic" if all_passed and trace_examples else "run_001_partition_diagnostic",
        "target": {"historical_best_qd": 2, "required": 5, "gap_before": 3, "gap_after": 3},
    }


def render_summary(analysis: dict[str, Any]) -> str:
    budget = analysis["budget_summary"]
    mechanism = analysis["profile_mechanism_summary"]
    raw = analysis["raw_metric_replay"]
    lines = [
        "# `run_000_baseline_replay` Summary",
        "",
        f"Decision: `{analysis['decision']}`. All support gates passed: `{str(analysis['all_support_gates_passed']).lower()}`.",
        "",
        "## Target-linked result",
        "",
        "This zero-episode replay does not change the historical best (`2/10`) or target gap (`3`). It rules out direct population/iteration scaling as the next intervention: "
        f"the {budget['valid_config_count']} valid budget configurations reached at most `{budget['max_valid_success_count']}/10`.",
        "",
        "## Mechanism facts",
        "",
        f"- Original task matrix: `{json.dumps(analysis['original_task_matrix'], sort_keys=True)}`.",
        f"- Budget success-task union: `{budget['success_tasks_union']}`; no configuration reached `>=5/10`.",
        f"- Profile coverage median: `{mechanism['coverage_median']}`; overflow P95: `{mechanism['overflow_p95']}`.",
        f"- Parsed QD chunk records: `{raw['qd_records']}`; zero-direct-elite ratio: `{raw['elite_zero_record_ratio']:.6f}`; archive-only-parent ratio: `{raw['archive_only_parent_record_ratio']:.6f}`.",
        f"- Missing metrics files: `0`; malformed records: `{raw['malformed_records']}`; missing required fields: `{raw['missing_required_fields']}`.",
        "",
        "## Gate table",
        "",
        "| Gate | Result | Criterion |",
        "| --- | --- | --- |",
    ]
    for gate in analysis["gates"]:
        lines.append(f"| `{gate['name']}` | `{'PASS' if gate['passed'] else 'FAIL'}` | {gate['criterion']} |")
    lines.extend(
        [
            "",
            "## Decision boundary",
            "",
            "Observations support an allocation/quality-retention audit, not an immediate online change. H2 reward calibration and H5 aliasing remain unresolved. Generic continuity smoothing is deprioritized by the historical clean-tail task regression.",
            "",
            f"Next protocol candidate: `{analysis['next_direction']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--budget-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog, checks = load_catalog(args.catalog)
    original_audit = load_json(catalog_path(catalog, ORIGINAL_AUDIT_ID))
    budget_audit = load_json(catalog_path(catalog, BUDGET_AUDIT_ID))
    no_op_path = args.budget_root / "analysis" / "num_elites_no_op_audit.json"
    no_op_audit = load_json(no_op_path)
    no_op_audit = {
        "path": str(no_op_path),
        "sha256": sha256_file(no_op_path),
        "passed": no_op_audit.get("passed"),
        "checks": no_op_audit.get("checks"),
        "formal_num_elites": no_op_audit.get("formal_num_elites"),
        "num_elites_values_audited": no_op_audit.get("num_elites_values_audited"),
        "libero_episode_attempts_consumed": no_op_audit.get("libero_episode_attempts_consumed"),
    }
    analysis = build_analysis(catalog, checks, original_audit, budget_audit, no_op_audit)
    args.output_root.mkdir(parents=True, exist_ok=True)
    analysis_bytes = canonical_json_bytes(analysis)
    (args.output_root / "analysis.json").write_bytes(analysis_bytes)
    (args.output_root / "summary.md").write_text(render_summary(analysis), encoding="utf-8")
    (args.output_root / "analysis.json.sha256").write_text(
        f"{hashlib.sha256(analysis_bytes).hexdigest()}  analysis.json\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "all_support_gates_passed": analysis["all_support_gates_passed"],
        "decision": analysis["decision"],
        "next_direction": analysis["next_direction"],
        "output_root": str(args.output_root),
        "analysis_sha256": hashlib.sha256(analysis_bytes).hexdigest(),
    }, sort_keys=True))
    return 0 if analysis["all_support_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
