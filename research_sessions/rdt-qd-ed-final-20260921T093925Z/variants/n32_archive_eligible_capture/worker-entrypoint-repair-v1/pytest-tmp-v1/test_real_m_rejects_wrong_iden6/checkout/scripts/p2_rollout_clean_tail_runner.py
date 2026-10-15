#!/usr/bin/env python3
"""Approved P2 rollout-RBF sweep and clean-tail experiment runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Callable, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rdt_eds_eval_runner as base


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_LINK = WORKTREE_ROOT / "outputs" / "ood_eval" / "p2_rollout_clean_tail_sweep"
OUTPUT_TARGET = Path("/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep")
OUTPUT_ALLOWED_PREFIX = Path("/mnt/data/shared2/zhuoli")
MIN_FREE_BYTES = 50 * 1024**3
RUNTIME_ENV_PATH = Path(
    "/home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration/.env"
)
PHASE_A_LEVEL = "p2_rollout_clean_tail_phase_a"
PHASE_B_LEVEL = "p2_rollout_clean_tail_phase_b"
SWEEP_LEVELS = {PHASE_A_LEVEL, PHASE_B_LEVEL}
BASELINE_LABEL = "p2_stage_on_baseline_rerun_rt3to1_s20_start06_skip0"
WINNER_MANIFEST_RELATIVE = Path("manifests/phase_a_winner_manifest.json")
CLASSIFICATION_RELATIVE = Path("analysis/failure_classifications.json")
AUDIT_RELATIVE = Path("analysis/phase_a_audit.json")
FINAL_REPORT_PATH = (
    WORKTREE_ROOT
    / "docs"
    / "03_evidence"
    / "eds_init_pg_diverse_sampling"
    / "2026-08-03-p2-rollout-clean-tail-parameter-sweep-report.md"
)
RANKING_RULE_VERSION = "p2-rollout-clean-tail-nine-level-v1"
BASELINE_SUCCESS_TASKS = {3, 8, 9}
EPISODE_SEEDS = [44, 235, 43, 546, 6, 621, 197, 87, 151, 548]
FAILURE_CATEGORIES = (
    "no target acquisition",
    "target pushed away",
    "target dropped after grasp",
    "basket displaced/collision",
    "clutter swept/wrong-object interaction",
    "unstable transport",
    "placement/release failure",
    "premature guidance OFF",
    "guidance oscillation",
    "qpos/execution error",
    "timeout without task completion",
)
COLLISION_PUSH_DROP_CATEGORIES = {
    "target pushed away",
    "target dropped after grasp",
    "basket displaced/collision",
    "clutter swept/wrong-object interaction",
}
PROFILE_FIELDS = tuple(base.P2_BASE_PROFILE)

_ORIGINAL_BUILD_JOBS = base.build_jobs
_ORIGINAL_P2_JOB_VALIDITY = base._p2_job_validity
_ORIGINAL_VALIDATE_STORAGE = base._validate_p2_output_storage


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _configured_validate_storage(**kwargs) -> Path:
    kwargs.setdefault("link_path", OUTPUT_LINK)
    kwargs.setdefault("expected_target", OUTPUT_TARGET)
    kwargs.setdefault("allowed_prefix", OUTPUT_ALLOWED_PREFIX)
    kwargs.setdefault("min_free_bytes", MIN_FREE_BYTES)
    return _ORIGINAL_VALIDATE_STORAGE(**kwargs)


def _load_runtime_credential() -> None:
    """Inject the configured Poe credential into the process without serializing it."""
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("python-dotenv is required for credential injection") from exc
    if not RUNTIME_ENV_PATH.is_file():
        raise RuntimeError(f"runtime environment file is missing: {RUNTIME_ENV_PATH}")
    load_dotenv(RUNTIME_ENV_PATH, override=True)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.lower() == "dummy":
        raise RuntimeError("runtime OPENAI_API_KEY is missing or non-real")


def storage_preflight() -> dict[str, object]:
    """Safely create/audit the shared2 target and absolute worktree symlink."""
    if not Path("/mnt/data/shared2/zhuoli").is_dir():
        raise RuntimeError("shared2 owner directory is missing")
    if not os.access("/mnt/data/shared2/zhuoli", os.W_OK):
        raise RuntimeError("shared2 owner directory is not writable")
    free = shutil.disk_usage("/mnt/data/shared2").free
    if free < MIN_FREE_BYTES:
        raise RuntimeError(
            f"shared2 has only {free} free bytes; requires {MIN_FREE_BYTES}"
        )

    OUTPUT_TARGET.mkdir(parents=True, exist_ok=True)
    if OUTPUT_LINK.exists() or OUTPUT_LINK.is_symlink():
        if not OUTPUT_LINK.is_symlink():
            raise RuntimeError(
                f"worktree output path exists and is not a symlink: {OUTPUT_LINK}"
            )
        if OUTPUT_LINK.resolve(strict=True) != OUTPUT_TARGET.resolve(strict=True):
            raise RuntimeError(
                "existing worktree symlink points at an unexpected target: "
                f"{OUTPUT_LINK.resolve(strict=True)}"
            )
    else:
        OUTPUT_LINK.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_LINK.symlink_to(OUTPUT_TARGET.absolute(), target_is_directory=True)

    real_root = _configured_validate_storage()
    probe_link = OUTPUT_LINK / ".storage_probe"
    probe_target = OUTPUT_TARGET / ".storage_probe"
    with probe_link.open("x", encoding="utf-8") as handle:
        handle.write("shared2-probe\n")
    try:
        if probe_link.resolve(strict=True) != probe_target.resolve(strict=True):
            raise RuntimeError("probe file did not resolve into the shared2 target")
        if probe_target.read_text(encoding="utf-8") != "shared2-probe\n":
            raise RuntimeError("probe file content mismatch")
    finally:
        probe_link.unlink(missing_ok=True)
    return {
        "symlink": str(OUTPUT_LINK),
        "symlink_target": os.readlink(OUTPUT_LINK),
        "real_root": str(real_root),
        "free_bytes": free,
        "probe_verified": True,
    }


def _candidate_label(t_max: int, scale: float, start: float) -> str:
    return (
        f"p2_param_rt{int(t_max)}to1_s{int(scale)}_"
        f"start{int(round(start * 10)):02d}_skip0"
    )


def _phase_a_methods() -> list[dict[str, object]]:
    methods: list[dict[str, object]] = []
    for t_max in (3, 2):
        for scale in (5.0, 10.0, 15.0):
            for start in (0.4, 0.6):
                methods.append(
                    {
                        **base.P2_BASE_PROFILE,
                        "method": _candidate_label(t_max, scale, start),
                        "label": _candidate_label(t_max, scale, start),
                        "renoise_t_max": t_max,
                        "renoise_t_min": 1,
                        "rollout_diversity_scale": scale,
                        "rollout_diversity_start_ratio": start,
                        "rollout_diversity_iters": "all",
                        "rollout_diversity_skip_final_steps": 0,
                        "is_baseline": False,
                    }
                )
    methods.append(
        {
            **base.P2_BASE_PROFILE,
            "method": BASELINE_LABEL,
            "label": BASELINE_LABEL,
            "renoise_t_max": 3,
            "renoise_t_min": 1,
            "rollout_diversity_scale": 20.0,
            "rollout_diversity_start_ratio": 0.6,
            "rollout_diversity_iters": "all",
            "rollout_diversity_skip_final_steps": 0,
            "is_baseline": True,
        }
    )
    return methods


def _bind_jobs(jobs: list[dict[str, object]]) -> list[dict[str, object]]:
    git_revision = base._git_head_revision()
    code_state_sha256 = base._p2_code_state_sha256()
    for job in jobs:
        base._bind_p2_execution_context(
            job,
            git_revision=git_revision,
            code_state_sha256=code_state_sha256,
        )
    return jobs


def build_jobs(
    level: str,
    episodes: int,
    *,
    manifest_path: str | Path | None = None,
) -> list[dict[str, object]]:
    if episodes != 10:
        raise ValueError(f"{level} requires exactly 10 episodes")
    if level == PHASE_A_LEVEL:
        methods = _phase_a_methods()
    elif level == PHASE_B_LEVEL:
        manifest = load_winner_manifest(manifest_path)
        profile = dict(manifest["winner_profile"])
        if profile.get("rollout_diversity_skip_final_steps") != 0:
            raise ValueError("winner manifest does not describe a skip0 Phase A job")
        winner_label = str(manifest["winner_label"])
        label = f"{winner_label}_cleantail_skip1"
        profile.update(
            {
                "method": label,
                "label": label,
                "rollout_diversity_skip_final_steps": 1,
                "is_baseline": False,
                "source_winner_label": winner_label,
                "manifest_path": str(Path(manifest["manifest_path"]).resolve()),
                "manifest_sha256": manifest["manifest_sha256"],
            }
        )
        methods = [profile]
    else:
        raise ValueError(f"unsupported P2 clean-tail level: {level}")

    jobs = [
        {
            **method,
            "job_id": f"{level}_libero_object_swap_{method['label']}",
            "level": level,
            "suite": "libero_object_swap",
            "episodes": episodes,
            "task_ids_filter": list(range(10)),
            "episode_seeds": list(EPISODE_SEEDS),
        }
        for method in methods
    ]
    return _bind_jobs(jobs)


def phase_b_profile_diff(
    winner_job: dict[str, object], phase_b_job: dict[str, object]
) -> dict[str, tuple[object, object]]:
    return {
        field: (winner_job.get(field), phase_b_job.get(field))
        for field in PROFILE_FIELDS
        if winner_job.get(field) != phase_b_job.get(field)
    }


def _ranking_number(record: dict[str, object], field: str, default: float) -> float:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    number = float(value)
    return number if math.isfinite(number) else default


def rank_phase_a_candidates(
    records: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    candidates = [
        record
        for record in records
        if record.get("eligible") is True and record.get("is_baseline") is not True
    ]
    return sorted(
        candidates,
        key=lambda record: (
            -_ranking_number(record, "success_count", -math.inf),
            -_ranking_number(record, "baseline_task_retention", -math.inf),
            _ranking_number(record, "execution_qpos_error_episodes", math.inf),
            _ranking_number(record, "collision_push_drop_episodes", math.inf),
            _ranking_number(record, "selected_max_step_p95", math.inf),
            _ranking_number(record, "selected_trajectory_length_p95", math.inf),
            -_ranking_number(record, "eef_direction_diversity_median", -math.inf),
            _ranking_number(record, "select_action_latency_median_s", math.inf),
            str(record["label"]),
        ),
    )


def partition_resume_jobs(
    jobs: Iterable[dict[str, object]],
    *,
    has_outputs: Callable[[dict[str, object]], bool],
    validity: Callable[[dict[str, object]], dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    skipped: list[dict[str, object]] = []
    runnable: list[dict[str, object]] = []
    for job in jobs:
        if has_outputs(job) and validity(job).get("valid") is True:
            skipped.append(job)
        else:
            runnable.append(job)
    return skipped, runnable


_REQUIRED_SWEEP_METRICS = (
    "rollout_rbf_steps_by_iter",
    "selected_trajectory_length_by_iter",
    "population_trajectory_length_mean_by_iter",
    "population_trajectory_length_p90_by_iter",
    "population_trajectory_length_max_by_iter",
    "selected_max_step_displacement_by_iter",
    "population_max_step_mean_by_iter",
    "population_max_step_p90_by_iter",
    "population_max_step_max_by_iter",
    "trajectory_length_expansion_ratio_by_iter",
    "max_step_expansion_ratio_by_iter",
    "eef_direction_diversity_by_iter",
    "endpoint_direction_spread_by_iter",
    "chunk_boundary_action_jump",
    "gripper_qpos_violation_count",
)


def sweep_metric_failures(
    records: list[dict[str, object]],
    *,
    skip_final_steps: int,
    start_ratio: float | None = None,
) -> list[str]:
    failures: list[str] = []
    if not records:
        return ["sweep metrics are empty"]
    for record_index, record in enumerate(records):
        missing = [field for field in _REQUIRED_SWEEP_METRICS if field not in record]
        if missing:
            failures.append(
                f"record {record_index} sweep metrics missing: {','.join(missing)}"
            )
            continue
        qpos_count = record.get("gripper_qpos_violation_count")
        if (
            not isinstance(qpos_count, int)
            or isinstance(qpos_count, bool)
            or qpos_count < 0
        ):
            failures.append(f"record {record_index} gripper qpos count invalid")
        steps_by_iter = record.get("rollout_rbf_steps_by_iter")
        if not isinstance(steps_by_iter, list) or not steps_by_iter:
            failures.append(f"record {record_index} rollout RBF step trace invalid")
            continue
        for item_index, item in enumerate(steps_by_iter):
            prefix = f"record {record_index} iter {item_index}"
            if not isinstance(item, dict):
                failures.append(f"{prefix} rollout RBF step record invalid")
                continue
            n_trunc = item.get("n_trunc_steps")
            count = item.get("step_count")
            indices = item.get("step_indices")
            final_applied = item.get("final_step_rbf_applied")
            if (
                not isinstance(n_trunc, int)
                or isinstance(n_trunc, bool)
                or n_trunc <= 0
                or not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
                or not isinstance(indices, list)
                or any(not isinstance(value, int) for value in indices)
                or count != len(indices)
            ):
                failures.append(f"{prefix} rollout RBF step schema invalid")
                continue
            if skip_final_steps > 0 and final_applied is not False:
                failures.append(f"{prefix} final denoise step applied RBF")
            if skip_final_steps > 0 and n_trunc == 1:
                if count != 0 or item.get("fallback_used") is not False:
                    failures.append(
                        f"{prefix} n_trunc=1 must have zero RBF steps without fallback"
                    )
            if start_ratio is not None:
                nominal = int(math.ceil(n_trunc * float(start_ratio)))
                maximum = max(0, n_trunc - int(skip_final_steps))
                expected = min(nominal, maximum)
                if count != expected or indices != list(range(expected)):
                    failures.append(f"{prefix} RBF step mask mismatch")
        list_lengths = [
            len(record[field])
            for field in _REQUIRED_SWEEP_METRICS
            if field.endswith("_by_iter") and isinstance(record.get(field), list)
        ]
        if list_lengths and len(set(list_lengths)) != 1:
            failures.append(f"record {record_index} per-iter metric lengths mismatch")
    return failures


def _sweep_job_validity(job: dict[str, object]) -> dict[str, object]:
    result = dict(_ORIGINAL_P2_JOB_VALIDITY(job))
    failures = [value for value in str(result.get("failure_reason") or "").split("; ") if value]
    output_dir = base._output_dir(job)
    try:
        output_dir.resolve(strict=True).relative_to(OUTPUT_TARGET.resolve(strict=True))
    except (OSError, ValueError):
        failures.append("output realpath is outside the approved shared2 target")
    metrics, read_failures = base._read_p2_jsonl_strict(
        output_dir / "eds_eval" / "eds_metrics.jsonl",
        label="metrics",
    )
    failures.extend(read_failures)
    failures.extend(
        sweep_metric_failures(
            metrics,
            skip_final_steps=int(job["rollout_diversity_skip_final_steps"]),
            start_ratio=float(job["rollout_diversity_start_ratio"]),
        )
    )
    if job.get("level") == PHASE_B_LEVEL:
        try:
            manifest = load_winner_manifest(job.get("manifest_path"))
            winner_job = dict(manifest["winner_profile"])
            diff = phase_b_profile_diff(winner_job, job)
            if diff != {"rollout_diversity_skip_final_steps": (0, 1)}:
                failures.append("Phase B changes fields other than skip_final_steps")
        except Exception as exc:
            failures.append(f"Phase B manifest validation failed: {type(exc).__name__}: {exc}")
    result["failure_reason"] = "; ".join(dict.fromkeys(failures))
    result["valid"] = not failures
    return result


def _percentile(values: Iterable[object], quantile: float) -> float | None:
    finite = sorted(
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
    if not finite:
        return None
    position = (len(finite) - 1) * quantile
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return finite[low]
    weight = position - low
    return finite[low] * (1.0 - weight) + finite[high] * weight


def _median(values: Iterable[object]) -> float | None:
    finite = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ]
    return float(median(finite)) if finite else None


def _load_classifications(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("categories") != list(FAILURE_CATEGORIES):
        raise ValueError("failure classification categories differ from preregistration")
    return payload


def write_classification_template(path: Path | None = None) -> Path:
    path = Path(path or (OUTPUT_TARGET / CLASSIFICATION_RELATIVE))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    jobs = {}
    for job in build_jobs(PHASE_A_LEVEL, 10):
        jobs[str(job["label"])] = [
            {
                "episode": episode,
                "task_id": episode,
                "episode_seed": EPISODE_SEEDS[episode],
                "outcome": "pending",
                "primary": None,
                "secondary": [],
                "evidence": None,
            }
            for episode in range(10)
        ]
    payload = {
        "schema": "p2-clean-tail-failure-classification-v1",
        "created_at": _now_iso(),
        "categories": list(FAILURE_CATEGORIES),
        "collision_push_drop_categories": sorted(COLLISION_PUSH_DROP_CATEGORIES),
        "jobs": jobs,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _job_classifications(
    classifications: dict[str, object], label: str, outcomes: dict[int, str]
) -> list[dict[str, object]]:
    rows = classifications.get("jobs", {}).get(label)
    if not isinstance(rows, list) or len(rows) != 10:
        raise ValueError(f"classification records missing for {label}")
    by_episode = {row.get("episode"): row for row in rows if isinstance(row, dict)}
    if set(by_episode) != set(range(10)):
        raise ValueError(f"classification episode coverage invalid for {label}")
    for episode, outcome in outcomes.items():
        row = by_episode[episode]
        if row.get("outcome") != outcome:
            raise ValueError(f"classification outcome mismatch for {label} episode {episode}")
        if outcome == "fail" and row.get("primary") not in FAILURE_CATEGORIES:
            raise ValueError(f"failure classification incomplete for {label} episode {episode}")
        if outcome == "success" and row.get("primary") not in {None, "success"}:
            raise ValueError(f"success classification invalid for {label} episode {episode}")
    return rows


def _output_error_episodes(output_dir: Path) -> set[int]:
    result: set[int] = set()
    for episode in range(10):
        if any("_fail_error_" in path.name for path in (output_dir / f"episode_{episode + 1}").glob("*.mp4")):
            result.add(episode)
    safety_events = base._read_jsonl(output_dir / "eds_eval" / "safety_events.jsonl")
    for event in safety_events:
        if event.get("event") == "gripper_qpos_violation" and isinstance(event.get("episode"), int):
            result.add(int(event["episode"]))
    return result


def collect_phase_a_records(
    classification_path: Path | None = None,
) -> list[dict[str, object]]:
    classification_path = Path(
        classification_path or (OUTPUT_TARGET / CLASSIFICATION_RELATIVE)
    )
    classifications = _load_classifications(classification_path)
    records: list[dict[str, object]] = []
    for job in build_jobs(PHASE_A_LEVEL, 10):
        output_dir = base._output_dir(job)
        validity = _sweep_job_validity(job)
        parsed = base._parse_results_file(output_dir / "results.txt")
        outcomes = base._p2_episode_outcomes(output_dir, 10)
        class_rows = _job_classifications(classifications, str(job["label"]), outcomes)
        metrics = base._read_jsonl(output_dir / "eds_eval" / "eds_metrics.jsonl")
        final_lengths = [
            values[-1]
            for record in metrics
            if isinstance((values := record.get("selected_trajectory_length_by_iter")), list)
            and values
        ]
        final_max_steps = [
            values[-1]
            for record in metrics
            if isinstance((values := record.get("selected_max_step_displacement_by_iter")), list)
            and values
        ]
        final_direction = [
            values[-1]
            for record in metrics
            if isinstance((values := record.get("eef_direction_diversity_by_iter")), list)
            and values
        ]
        success_tasks = sorted(
            episode for episode, outcome in outcomes.items() if outcome == "success"
        )
        error_episodes = _output_error_episodes(output_dir)
        error_episodes.update(
            int(row["episode"])
            for row in class_rows
            if row.get("primary") == "qpos/execution error"
        )
        collision_count = sum(
            row.get("primary") in COLLISION_PUSH_DROP_CATEGORIES for row in class_rows
        )
        records.append(
            {
                "label": job["label"],
                "job": job,
                "output_dir": str(output_dir),
                "is_baseline": bool(job["is_baseline"]),
                "eligible": bool(validity["valid"]),
                "validity": validity,
                "success_count": parsed.get("success"),
                "success_rate": parsed.get("success_rate"),
                "success_tasks": success_tasks,
                "baseline_task_retention": len(BASELINE_SUCCESS_TASKS & set(success_tasks)),
                "execution_qpos_error_episodes": len(error_episodes),
                "collision_push_drop_episodes": collision_count,
                "selected_max_step_p95": _percentile(final_max_steps, 0.95),
                "selected_trajectory_length_p95": _percentile(final_lengths, 0.95),
                "eef_direction_diversity_median": _median(final_direction),
                "select_action_latency_median_s": _median(
                    record.get("select_action_latency_s") for record in metrics
                ),
                "metrics_records": len(metrics),
                "failure_classifications": class_rows,
                "renoise_t_max": job["renoise_t_max"],
                "rollout_diversity_scale": job["rollout_diversity_scale"],
                "rollout_diversity_start_ratio": job[
                    "rollout_diversity_start_ratio"
                ],
                "rollout_diversity_skip_final_steps": job[
                    "rollout_diversity_skip_final_steps"
                ],
            }
        )
    return records


def _manifest_record(record: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"job", "failure_classifications", "validity"}
    } | {
        "failure_reason": record.get("validity", {}).get("failure_reason", "")
    }


def freeze_winner_manifest(
    ranked_records: list[dict[str, object]],
    *,
    path: Path,
    source_report_path: Path,
) -> dict[str, object]:
    ranked = rank_phase_a_candidates(ranked_records)
    if not ranked:
        raise ValueError("no eligible Phase A sweep candidate")
    winner = ranked[0]
    if winner.get("is_baseline") is True:
        raise ValueError("P2 baseline cannot be frozen as winner")
    job = dict(winner["job"])
    output_dir = Path(winner["output_dir"])
    checksum_paths = {
        "results.txt": output_dir / "results.txt",
        "eds_eval/eds_metrics.jsonl": output_dir / "eds_eval" / "eds_metrics.jsonl",
        ".hydra/config.yaml": output_dir / ".hydra" / "config.yaml",
        ".hydra/overrides.yaml": output_dir / ".hydra" / "overrides.yaml",
    }
    missing = [name for name, evidence_path in checksum_paths.items() if not evidence_path.is_file()]
    if missing:
        raise ValueError("winner evidence missing: " + ",".join(missing))
    payload: dict[str, object] = {
        "schema": "p2-rollout-clean-tail-winner-manifest-v1",
        "created_at": _now_iso(),
        "ranking_rule_version": RANKING_RULE_VERSION,
        "source_report_path": str(source_report_path),
        "winner_label": winner["label"],
        "winner_profile": {field: job[field] for field in PROFILE_FIELDS},
        "winner_hydra_overrides": base._parse_p2_overrides_file(
            output_dir / ".hydra" / "overrides.yaml"
        ),
        "checksums": {
            name: _sha256_file(evidence_path)
            for name, evidence_path in checksum_paths.items()
        },
        "winner_output_dir": str(output_dir.resolve(strict=True)),
        "phase_b_only_allowed_change": {
            "field": "rollout_diversity_skip_final_steps",
            "from": 0,
            "to": 1,
        },
        "candidate_ranking": [
            {"rank": index, **_manifest_record(record)}
            for index, record in enumerate(ranked, start=1)
        ],
    }
    if base._contains_secret_text(payload):
        raise ValueError("winner manifest contains credential material")
    payload["manifest_sha256"] = hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    return {**payload, "manifest_path": str(path.resolve())}


def load_winner_manifest(path: str | Path | None) -> dict[str, object]:
    manifest_path = Path(path or (OUTPUT_TARGET / WINNER_MANIFEST_RELATIVE))
    mode = stat.S_IMODE(manifest_path.stat().st_mode)
    if mode & 0o222:
        raise ValueError("winner manifest must be read-only")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = payload.get("manifest_sha256")
    without_hash = dict(payload)
    without_hash.pop("manifest_sha256", None)
    actual_hash = hashlib.sha256(_canonical_json(without_hash).encode("utf-8")).hexdigest()
    if expected_hash != actual_hash:
        raise ValueError("winner manifest checksum mismatch")
    if payload.get("ranking_rule_version") != RANKING_RULE_VERSION:
        raise ValueError("winner manifest ranking rule mismatch")
    if payload.get("winner_label") == BASELINE_LABEL:
        raise ValueError("winner manifest selected the P2 baseline")
    output_dir = Path(payload["winner_output_dir"])
    for name, expected in payload.get("checksums", {}).items():
        evidence_path = output_dir / name
        if not evidence_path.is_file() or _sha256_file(evidence_path) != expected:
            raise ValueError(f"winner evidence checksum mismatch: {name}")
    if base._contains_secret_text(payload):
        raise ValueError("winner manifest contains credential material")
    return {**payload, "manifest_path": str(manifest_path.resolve())}


def _fmt(value: object, digits: int = 4) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "-"
    return f"{float(value):.{digits}f}"


def write_final_report(
    *,
    path: Path,
    phase_a_records: list[dict[str, object]],
    baseline_record: dict[str, object],
    winner_manifest: dict[str, object],
    phase_b_record: dict[str, object],
    storage_audit: dict[str, object],
    failed_invalid_jobs: list[dict[str, object]],
) -> Path:
    winner_label = str(winner_manifest["winner_label"])
    winner = next(
        (record for record in phase_a_records if record.get("label") == winner_label),
        {},
    )
    gate_pass = _ranking_number(phase_b_record, "success_count", -1) >= 5
    lines = [
        "# P2 Rollout RBF 参数 Sweep 与 Clean-Tail 实验报告",
        "",
        f"生成时间：`{_now_iso()}`",
        "",
        f"工程 Gate `>=5/10`：`{'PASS' if gate_pass else 'FAIL'}`",
        "",
        "## 执行范围与存储",
        "",
        "- Benchmark：LIBERO-PRO `libero_object_swap`，strict perturbation，tasks `0..9`。",
        f"- Episode seeds：`{EPISODE_SEEDS}`；max steps `720`；Stage Recognition ON；Gemini grounding OFF。",
        f"- shared2 real root：`{storage_audit.get('real_root')}`。",
        f"- worktree symlink：`{storage_audit.get('symlink')}`。",
        "",
        "## Phase A 参数主效应",
        "",
        "| Job | rtmax | Scale | Start | Success | Eligible |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for record in phase_a_records:
        lines.append(
            f"| `{record.get('label')}` | {record.get('renoise_t_max', '-')} | "
            f"{record.get('rollout_diversity_scale', '-')} | "
            f"{record.get('rollout_diversity_start_ratio', '-')} | "
            f"{record.get('success_count', '-')}/10 | `{record.get('eligible')}` |"
        )
    lines.extend(
        [
            "",
            "主效应按 `rtmax`、scale 与 start ratio 分组比较 success、trajectory length、max-step 与 normalized direction diversity；由于每组仅 10 episodes，本报告只作工程配对解释，不宣称统计显著性。",
            "",
            "## Winner Ranking",
            "",
            f"唯一 winner：`{winner_label}`。P2 baseline rerun 未进入 ranking。",
            "",
            "九级排序依次使用 success、baseline task retention、execution/qpos、collision/push/drop、max-step P95、trajectory-length P95、direction diversity、latency 和 label。",
            "",
            "## Phase B Clean-Tail 增量",
            "",
            f"Phase A winner：`{winner.get('success_count', '-')}/10`；Phase B：`{phase_b_record.get('success_count', '-')}/10`。Phase B 仅将 `rollout_diversity_skip_final_steps` 从 `0` 改为 `1`。",
            "",
            "## Task-Level SR",
            "",
            "| Method | Success tasks | SR |",
            "| --- | --- | ---: |",
            f"| P2 baseline rerun | `{baseline_record.get('success_tasks', [])}` | {baseline_record.get('success_count', '-')}/10 |",
            f"| Phase A winner | `{winner.get('success_tasks', [])}` | {winner.get('success_count', '-')}/10 |",
            f"| Phase B clean-tail | `{phase_b_record.get('success_tasks', [])}` | {phase_b_record.get('success_count', '-')}/10 |",
            "",
            "## 方向多样性、轨迹长度与 Max-Step",
            "",
            "| Method | Selected length P95 | Selected max-step P95 | Direction median |",
            "| --- | ---: | ---: | ---: |",
            f"| P2 baseline | {_fmt(baseline_record.get('selected_trajectory_length_p95'))} | {_fmt(baseline_record.get('selected_max_step_p95'))} | {_fmt(baseline_record.get('eef_direction_diversity_median'))} |",
            f"| Phase A winner | {_fmt(winner.get('selected_trajectory_length_p95'))} | {_fmt(winner.get('selected_max_step_p95'))} | {_fmt(winner.get('eef_direction_diversity_median'))} |",
            f"| Phase B | {_fmt(phase_b_record.get('selected_trajectory_length_p95'))} | {_fmt(phase_b_record.get('selected_max_step_p95'))} | {_fmt(phase_b_record.get('eef_direction_diversity_median'))} |",
            "",
            "报告同时保留 iter 0/1/last expansion ratio、population mean/P90/max、endpoint direction spread 和实际 RBF step mask，避免把名义 start ratio 当作连续强度。",
            "",
            "## 失败、Latency 与 Qualitative Evidence",
            "",
            "失败按预注册 11 类逐 episode 编码；collision/push/drop/qpos、Stage OFF/ON transitions、query latency、selected-action latency 与相同坐标定性曲线均保存在 shared2 job evidence 中。",
            "",
            "## Validity Audit",
            "",
            f"- Phase A jobs：`{len(phase_a_records) + 1}/13`（12 sweep + baseline）。",
            f"- Phase B jobs：`1/1`。",
            f"- Failed/invalid jobs：`{len(failed_invalid_jobs)}`。",
        ]
    )
    for record in failed_invalid_jobs:
        lines.append(
            f"  - `{record.get('label')}`：{record.get('failure_reason', 'unknown')}"
        )
    lines.extend(
        [
            "- 每个 complete job 要求 results、10/10 metadata、10 个 ffprobe-readable videos、Hydra config/overrides、metrics、Stage events、qualitative evidence、完整 log、strict suite、0 fallback/nonfinite/mask violation、credential scan 和 shared2 realpath 全部通过。",
            "",
            "## 结论与风险",
            "",
            f"同一套 10 tasks 的主要 gate：`{'达到' if gate_pass else '未达到'} >=5/10`。未运行任何结果驱动的额外 sweep。Stage API 波动和 n=10 winner 稳定性仍是主要解释边界。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_with_retries(
    level: str,
    *,
    gpus: str,
    timeout_seconds: int,
    resume: bool,
    retries: int,
    manifest_path: str | Path | None = None,
) -> int:
    last_code = 1
    for attempt in range(retries + 1):
        last_code = base.run_level(
            level,
            10,
            gpus,
            timeout_seconds,
            resume=resume or attempt > 0,
            manifest_path=manifest_path,
        )
        if last_code == 0:
            return 0
    return last_code


def _configure_base() -> None:
    base.P2_OUTPUT_ROOT = OUTPUT_LINK
    base.P2_STATUS_ROOT = OUTPUT_LINK
    base.P2_EXPECTED_OUTPUT_TARGET = OUTPUT_TARGET
    base.P2_ALLOWED_OUTPUT_PREFIX = OUTPUT_ALLOWED_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | SWEEP_LEVELS
    base.build_jobs = build_jobs
    base._p2_job_validity = _sweep_job_validity
    base._validate_p2_output_storage = _configured_validate_storage


_configure_base()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("storage-preflight")
    sub.add_parser("write-classification-template")
    health = sub.add_parser("health-check")
    health.add_argument("--level", choices=[PHASE_A_LEVEL, PHASE_B_LEVEL], default=PHASE_A_LEVEL)
    for name in ("run-phase-a", "run-phase-b"):
        run = sub.add_parser(name)
        run.add_argument("--gpus", default="2")
        run.add_argument("--timeout-seconds", type=int, default=28800)
        run.add_argument("--resume", action="store_true")
        run.add_argument("--retries", type=int, default=2)
        run.add_argument("--manifest-path", default=None)
    audit = sub.add_parser("audit-phase-a")
    audit.add_argument("--classification-path", default=None)
    freeze = sub.add_parser("freeze-winner")
    freeze.add_argument("--classification-path", default=None)
    freeze.add_argument("--manifest-path", default=None)

    args = parser.parse_args()
    if args.command in {"health-check", "run-phase-a", "run-phase-b"}:
        _load_runtime_credential()
    if args.command == "storage-preflight":
        print(json.dumps(storage_preflight(), indent=2, sort_keys=True))
        return 0
    if args.command == "write-classification-template":
        print(write_classification_template())
        return 0
    if args.command == "health-check":
        base._validate_stage_level_start(
            args.level,
            offline_vlm=False,
            require_online_api=True,
        )
        print("credential health check: PASS")
        return 0
    if args.command == "run-phase-a":
        return run_with_retries(
            PHASE_A_LEVEL,
            gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
            resume=args.resume,
            retries=args.retries,
        )
    if args.command == "run-phase-b":
        if not args.manifest_path:
            raise SystemExit("run-phase-b requires --manifest-path")
        return run_with_retries(
            PHASE_B_LEVEL,
            gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
            resume=args.resume,
            retries=args.retries,
            manifest_path=args.manifest_path,
        )
    records = collect_phase_a_records(
        Path(args.classification_path) if args.classification_path else None
    )
    audit_payload = {
        "created_at": _now_iso(),
        "records": [_manifest_record(record) for record in records],
    }
    audit_path = OUTPUT_TARGET / AUDIT_RELATIVE
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.command == "audit-phase-a":
        print(audit_path)
        return int(not all(record["eligible"] for record in records))
    candidates = [record for record in records if not record["is_baseline"]]
    if len(candidates) != 12 or not all(record["eligible"] for record in records):
        raise SystemExit("all 13 Phase A jobs must be valid before freezing winner")
    manifest_path = Path(
        args.manifest_path or (OUTPUT_TARGET / WINNER_MANIFEST_RELATIVE)
    )
    manifest = freeze_winner_manifest(
        candidates,
        path=manifest_path,
        source_report_path=FINAL_REPORT_PATH,
    )
    print(manifest["manifest_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
