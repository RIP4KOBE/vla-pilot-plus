#!/usr/bin/env python3
"""Audit and report the approved P2 Direction-Normalized RBF experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from omegaconf import OmegaConf

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p2_direction_normalized_rbf_runner as runner
from core.eds_eval_metrics import direction_rbf_evidence_summary, wilson_ci

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_TARGET = runner.OUTPUT_TARGET
EPISODE_SEEDS = list(runner.EPISODE_SEEDS)
ATTEMPT_CAP = runner.ATTEMPT_CAP
REPORT_PATH = (
    WORKTREE_ROOT
    / "docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-04-p2-direction-normalized-rbf-report.md"
)
ANALYSIS_PATH = OUTPUT_TARGET / "analysis/direction_rbf_formal_audit.json"
CLASSIFICATION_PATH = OUTPUT_TARGET / "analysis/failure_classification.json"
DELIVERY_AUDIT_PATH = OUTPUT_TARGET / "analysis/delivery_audit.json"
RUNTIME_DIAGNOSTIC_PATH = (
    OUTPUT_TARGET / "analysis/runtime_diagnostics/native_egl_abort_diagnosis.json"
)
DECISION_PATH = OUTPUT_TARGET / runner.DECISION_RELATIVE

TASK_DESCRIPTIONS = [
    "pick up the alphabet soup and place it in the basket",
    "pick up the cream cheese and place it in the basket",
    "pick up the salad dressing and place it in the basket",
    "pick up the bbq sauce and place it in the basket",
    "pick up the ketchup and place it in the basket",
    "pick up the tomato sauce and place it in the basket",
    "pick up the butter and place it in the basket",
    "pick up the milk and place it in the basket",
    "pick up the chocolate pudding and place it in the basket",
    "pick up the orange juice and place it in the basket",
]
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
COLLISION_COMPOSITE_CATEGORIES = {
    "target pushed away",
    "target dropped after grasp",
    "basket displaced/collision",
    "clutter swept/wrong-object interaction",
}

# Conservative final-frame review. Every listed failure also reached the 720-step timeout;
# the primary label records the visible terminal mechanism, not an unobserved causal claim.
REVIEWED_CLASSIFICATIONS: dict[str, dict[int, str]] = {
    "p2_stage_on_abs_rbf_control": {
        0: "no target acquisition",
        1: "no target acquisition",
        2: "basket displaced/collision",
        4: "target pushed away",
        8: "placement/release failure",
        9: "no target acquisition",
    },
    "p2_stage_on_dirnorm_rbf_rollout_w0_e050": {
        1: "no target acquisition",
        2: "clutter swept/wrong-object interaction",
        3: "no target acquisition",
        4: "target pushed away",
        5: "placement/release failure",
        6: "basket displaced/collision",
        7: "no target acquisition",
        8: "no target acquisition",
        9: "no target acquisition",
    },
    "p2_stage_on_dirnorm_rbf_global_w0_e025": {
        0: "target pushed away",
        1: "no target acquisition",
        2: "clutter swept/wrong-object interaction",
        3: "clutter swept/wrong-object interaction",
        4: "target pushed away",
        5: "clutter swept/wrong-object interaction",
        6: "basket displaced/collision",
        7: "basket displaced/collision",
        8: "basket displaced/collision",
        9: "clutter swept/wrong-object interaction",
    },
    "p2_stage_on_dirnorm_rbf_global_w0_e050": {
        0: "clutter swept/wrong-object interaction",
        1: "basket displaced/collision",
        3: "basket displaced/collision",
        4: "target pushed away",
        5: "clutter swept/wrong-object interaction",
        6: "placement/release failure",
        7: "clutter swept/wrong-object interaction",
        8: "no target acquisition",
    },
    "p2_stage_on_dirnorm_rbf_global_w1_e100": {
        0: "no target acquisition",
        1: "no target acquisition",
        2: "clutter swept/wrong-object interaction",
        3: "no target acquisition",
        5: "no target acquisition",
        6: "placement/release failure",
        7: "target pushed away",
        8: "no target acquisition",
        9: "target pushed away",
    },
    "p2_stage_on_dirnorm_rbf_global_w2_e025": {
        0: "placement/release failure",
        1: "no target acquisition",
        2: "no target acquisition",
        3: "target pushed away",
        4: "target pushed away",
        5: "clutter swept/wrong-object interaction",
        7: "basket displaced/collision",
    },
}

PROFILE_AUDIT_FIELDS = (
    "population_size",
    "cem_iters",
    "use_cem",
    "num_elites",
    "temperature",
    "renoise_t_max",
    "renoise_t_min",
    "initial_sampling_mode",
    "initial_diversity_scale",
    "initial_diversity_start_ratio",
    "truncated_rollout_mode",
    "rollout_diversity_scale",
    "rollout_diversity_start_ratio",
    "rollout_diversity_iters",
    "rollout_diversity_skip_final_steps",
    "parent_weighting_mode",
    "parent_coverage_mode",
    "elite_carryover_count",
    "rollout_diversity_control_mode",
    "chunk_population_mode",
    "search_schedule_mode",
    "execution_horizon_mode",
    "execution_horizon_far",
    "execution_horizon_near",
    "execution_horizon_contact",
    "initial_diversity_descriptor_mode",
    "rollout_diversity_descriptor_mode",
    "direction_rbf_direction_weight",
    "direction_rbf_shape_weight",
    "direction_rbf_endpoint_weight",
    "direction_rbf_endpoint_scale_m",
    "direction_rbf_path_epsilon",
    "direction_rbf_distance_epsilon",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        return [], [f"missing JSONL: {path}"]
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        if not line.strip():
            failures.append(f"blank JSONL record: {path}:{line_number}")
            continue
        try:
            value = json.loads(line)
        except ValueError as exc:
            failures.append(f"invalid JSONL: {path}:{line_number}: {exc}")
            continue
        if not isinstance(value, dict):
            failures.append(f"non-object JSONL record: {path}:{line_number}")
            continue
        records.append(value)
    return records, failures


def _ffprobe_readable(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return False
    return bool(payload.get("streams"))


def select_episode_attempts(
    rows: list[dict[str, Any]],
    *,
    expected_seeds: list[int],
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    """Select one complete, exact-task/seed attempt per episode and retain rejections."""
    selected: dict[int, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    priority = {"formal": 0, "resume": 2, "archive": 3}

    def sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
        source = str(item.get("source"))
        source_priority = 1 if source.startswith("supplemental:") else priority.get(source, 9)
        return (
            int(item.get("episode", -1)),
            0 if item.get("evidence_complete") is True else 1,
            source_priority,
        )

    for row in sorted(rows, key=sort_key):
        episode = row.get("episode")
        reason: str | None = None
        if isinstance(episode, bool) or not isinstance(episode, int) or not 0 <= episode < len(expected_seeds):
            reason = "episode_identity_invalid"
        elif row.get("task_id") != episode:
            reason = f"task_id_mismatch:{row.get('task_id')}!={episode}"
        elif row.get("episode_seed") != expected_seeds[episode]:
            reason = f"episode_seed_mismatch:{row.get('episode_seed')}!={expected_seeds[episode]}"
        elif row.get("video_readable") is not True:
            reason = "video_missing_or_unreadable"
        elif episode in selected:
            reason = "duplicate_complete_episode"
        if reason is None:
            selected[episode] = row
        else:
            rejected.append({**row, "rejection_reason": reason})
    return selected, rejected


def _video_outcome(path: Path) -> str:
    name = path.name.lower()
    if "_success_" in name:
        return "success"
    if "_fail" in name:
        return "fail"
    return "unknown"


def _supplemental_attempt_directories(
    label: str, *, root: Path | None = None
) -> list[Path]:
    root = OUTPUT_TARGET if root is None else Path(root)
    return sorted(
        path
        for path in (root / "supplemental_recovery").glob(f"*/formal/{label}")
        if path.is_dir()
    )


def _attempt_rows(label: str) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    directories = [
        ("formal", OUTPUT_TARGET / "formal" / label),
        ("resume", OUTPUT_TARGET / "resume_attempts" / label),
    ]
    directories.extend(
        (f"supplemental:{directory.parents[1].name}", directory)
        for directory in _supplemental_attempt_directories(label)
    )
    for source, directory in directories:
        metadata_path = directory / "eds_eval/episode_metadata.jsonl"
        records, read_failures = _read_jsonl(metadata_path)
        if metadata_path.exists():
            failures.extend(read_failures)
        metrics, _ = _read_jsonl(directory / "eds_eval/eds_metrics.jsonl")
        stages, _ = _read_jsonl(directory / "eds_eval/stage_events.jsonl")
        metric_episodes = {
            record.get("episode")
            for record in metrics
            if isinstance(record.get("episode"), int)
            and not isinstance(record.get("episode"), bool)
        }
        successful_stage_episodes = {
            record.get("episode_id")
            for record in stages
            if isinstance(record.get("episode_id"), int)
            and not isinstance(record.get("episode_id"), bool)
            and record.get("query_ok") is True
        }
        for record in records:
            episode = record.get("episode_id")
            episode_dir = directory / f"episode_{episode + 1}" if isinstance(episode, int) and not isinstance(episode, bool) else directory / "episode_invalid"
            videos = sorted(episode_dir.glob("*.mp4")) if episode_dir.is_dir() else []
            video = videos[0] if len(videos) == 1 else None
            qualitative = (
                directory / "eds_eval/qualitative" / f"episode_{episode:03d}"
                if isinstance(episode, int) and not isinstance(episode, bool)
                else directory / "eds_eval/qualitative/episode_invalid"
            )
            qualitative_present = bool(
                qualitative.is_dir()
                and any(
                    path.is_file() and path.stat().st_size > 0
                    for path in qualitative.rglob("*")
                )
            )
            metrics_present = episode in metric_episodes
            stage_query_success = episode in successful_stage_episodes
            rows.append(
                {
                    "episode": episode,
                    "task_id": record.get("task_id"),
                    "episode_seed": record.get("episode_seed"),
                    "source": source,
                    "output_dir": str(directory),
                    "video": str(video) if video else None,
                    "video_count": len(videos),
                    "video_readable": bool(video and _ffprobe_readable(video)),
                    "outcome": _video_outcome(video) if video else None,
                    "metrics_present": metrics_present,
                    "stage_query_success": stage_query_success,
                    "qualitative_present": qualitative_present,
                    "evidence_complete": bool(
                        metrics_present
                        and stage_query_success
                        and qualitative_present
                    ),
                }
            )
    return rows, failures


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isfinite(float(actual)) and math.isclose(
            float(actual), float(expected), rel_tol=0.0, abs_tol=1.0e-9
        )
    return actual == expected


def _config_value(config: Any, path: str) -> Any:
    return OmegaConf.select(config, path, default=None)


def _config_and_manifest_failures(profile: dict[str, Any], directory: Path) -> list[str]:
    failures: list[str] = []
    config_path = directory / ".hydra/config.yaml"
    overrides_path = directory / ".hydra/overrides.yaml"
    hydra_path = directory / ".hydra/hydra.yaml"
    for path in (config_path, overrides_path, hydra_path):
        if not path.is_file() or path.is_symlink():
            failures.append(f"required Hydra artifact missing/symlinked: {path.name}")
    if config_path.is_file():
        try:
            config = OmegaConf.load(config_path)
        except Exception as exc:
            failures.append(f"Hydra config parse failure: {type(exc).__name__}: {exc}")
        else:
            fixed = {
                "backend.backend": "libero",
                "backend.libero.suite_name": "libero_object_swap",
                "backend.libero.strict_perturbations": True,
                "backend.libero.max_episode_steps": 720,
                "main.use_vlm_stage_recognition": True,
                "perception.gemini_grounding.enabled": False,
                "main.episode_num": 10,
            }
            for field, expected in fixed.items():
                actual = _config_value(config, field)
                if not _same_value(actual, expected):
                    failures.append(f"Hydra config mismatch: {field}={actual!r} expected {expected!r}")
            for field in PROFILE_AUDIT_FIELDS:
                actual = _config_value(config, f"main.eds_config.{field}")
                if field.startswith("execution_"):
                    actual = _config_value(config, f"main.{field}")
                if not _same_value(actual, profile[field]):
                    failures.append(f"Hydra profile mismatch: {field}={actual!r} expected {profile[field]!r}")

    fingerprint_path = directory / "config_fingerprint.txt"
    manifest_path = directory / "job_manifest.json"
    if not fingerprint_path.is_file():
        failures.append("config_fingerprint.txt missing")
    if not manifest_path.is_file():
        failures.append("job_manifest.json missing")
    if fingerprint_path.is_file() and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            failures.append(f"job manifest parse failure: {exc}")
        else:
            stored = fingerprint_path.read_text(encoding="utf-8").strip()
            if manifest.get("config_fingerprint") != stored:
                failures.append("stored job manifest/fingerprint mismatch")
            manifest_job = manifest.get("job")
            if not isinstance(manifest_job, dict):
                failures.append("job manifest profile missing")
            else:
                for field in ("label", "role", *PROFILE_AUDIT_FIELDS):
                    if not _same_value(manifest_job.get(field), profile.get(field)):
                        failures.append(f"job manifest profile mismatch: {field}")
            execution = manifest.get("execution_record")
            if not isinstance(execution, dict) or not execution.get("code_state_sha256"):
                failures.append("job manifest code fingerprint missing")
    return failures


def _walk_key_values(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from _walk_key_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_key_values(item)


def _percentile(values: Iterable[Any], quantile: float) -> float | None:
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


def _median(values: Iterable[Any]) -> float | None:
    finite = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ]
    return float(median(finite)) if finite else None


def _final_values(records: list[dict[str, Any]], key: str, *, nested_key: str | None = None) -> list[float]:
    values: list[float] = []
    for record in records:
        trace = record.get(key)
        if not isinstance(trace, list) or not trace:
            continue
        value: Any = trace[-1]
        if nested_key is not None:
            value = value.get(nested_key) if isinstance(value, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def _selected_records(selected: dict[int, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    metrics: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    failures: list[str] = []
    cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for episode, row in selected.items():
        directory = Path(row["output_dir"])
        for kind, relative, identity in (
            ("metrics", "eds_eval/eds_metrics.jsonl", "episode"),
            ("stages", "eds_eval/stage_events.jsonl", "episode_id"),
        ):
            key = (str(directory), kind)
            if key not in cache:
                cache[key], read_failures = _read_jsonl(directory / relative)
                failures.extend(read_failures)
            subset = [record for record in cache[key] if record.get(identity) == episode]
            if kind == "metrics":
                if not subset:
                    failures.append(f"episode {episode} metrics missing")
                metrics.extend(subset)
            else:
                if not any(record.get("query_ok") is True for record in subset):
                    failures.append(f"episode {episode} has no successful Stage query")
                stages.extend(subset)
        qualitative = directory / "eds_eval/qualitative" / f"episode_{episode:03d}"
        if not qualitative.is_dir() or not any(path.is_file() and path.stat().st_size > 0 for path in qualitative.rglob("*")):
            failures.append(f"episode {episode} qualitative evidence missing")
    return metrics, stages, failures


def _mechanism_summary(metrics: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    weights = [
        float(profile["direction_rbf_direction_weight"]),
        float(profile["direction_rbf_shape_weight"]),
        float(profile["direction_rbf_endpoint_weight"]),
    ]
    initial: list[dict[str, Any]] = []
    rollout: list[dict[str, Any]] = []
    for record in metrics:
        raw_initial = record.get("initial_direction_rbf_evidence_by_step")
        if isinstance(raw_initial, list):
            initial.extend(item for item in raw_initial if isinstance(item, dict))
        raw_rollout = record.get("rollout_direction_rbf_evidence_by_iter")
        if isinstance(raw_rollout, list):
            for group in raw_rollout:
                if isinstance(group, list):
                    rollout.extend(item for item in group if isinstance(item, dict))

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any] | None:
        directional = [item for item in items if item.get("descriptor_mode") == "direction_normalized_eef"]
        if not directional:
            return None
        full = direction_rbf_evidence_summary([directional], weights=weights)
        compact: dict[str, Any] = {}
        for key, value in full.items():
            compact[key] = value[0] if isinstance(value, list) and len(value) == 1 else value
        compact["evidence_record_count"] = len(directional)
        return compact

    return {"initial": summarize(initial), "rollout": summarize(rollout)}


def _selected_error_episode_count(selected: dict[int, dict[str, Any]]) -> int:
    episode_ids: set[int] = set()
    for episode, row in selected.items():
        root = Path(str(row["output_dir"])) / f"episode_{episode + 1}"
        if (root / "error.txt").is_file() or any(root.glob("*_fail_error_*.mp4")):
            episode_ids.add(episode)
    return len(episode_ids)


def _diagnostic_reason(label: str, accepted: int, rejected: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for path in (
        OUTPUT_TARGET / "runner_logs/formal" / f"{label}.log",
        OUTPUT_TARGET / "resume_attempts" / label / "runner.log",
        OUTPUT_TARGET / "attempt_archives/pre_bf16_fix/runner_logs" / f"{label}.log",
        *[
            directory.parents[1] / "runner_logs/formal" / f"{label}.log"
            for directory in _supplemental_attempt_directories(label)
        ],
    ):
        if path.is_file():
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
    joined = "\n".join(texts)
    details: list[str] = []
    if "cdist_cuda" in joined and "BFloat16" in joined:
        details.append("BF16 cdist execution error")
    if "Aborted" in joined or "core dumped" in joined:
        details.append("native process abort")
    if "must divide evenly" in joined:
        details.append("suffix adapter episode/task divisibility assertion")
    seed_rejections = [row["rejection_reason"] for row in rejected if str(row.get("rejection_reason", "")).startswith("episode_seed_mismatch")]
    if seed_rejections:
        details.append("resume seed mismatch (" + ", ".join(seed_rejections) + ")")
    if accepted < 10:
        details.append(f"incomplete {accepted}/10 exact-seed readable episode results")
    return "; ".join(dict.fromkeys(details)) or ("complete" if accepted == 10 else "incomplete after attempt cap")


def _stored_fingerprint(
    label: str,
    *,
    selected_sources: set[Path] | None = None,
    formal_root: Path | None = None,
) -> dict[str, Any]:
    """Report execution identity from the evidence actually selected by the audit."""
    default_source = Path(
        formal_root
        if formal_root is not None
        else OUTPUT_TARGET / "formal" / label
    )
    sources = sorted(selected_sources or {default_source}, key=lambda path: str(path))
    contexts: list[dict[str, Any]] = []
    for source in sources:
        path = source / "job_manifest.json"
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        execution = (
            payload.get("execution_record")
            if isinstance(payload.get("execution_record"), dict)
            else {}
        )
        contexts.append(
            {
                "output_dir": str(source),
                "config_fingerprint": payload.get("config_fingerprint"),
                "code_state_sha256": execution.get("code_state_sha256"),
                "git_revision": execution.get("git_revision"),
            }
        )

    def unique_value(key: str) -> Any:
        values = {context.get(key) for context in contexts}
        return next(iter(values)) if len(values) == 1 else None

    return {
        "config_fingerprint": unique_value("config_fingerprint"),
        "code_state_sha256": unique_value("code_state_sha256"),
        "git_revision": unique_value("git_revision"),
        "selected_execution_contexts": contexts,
    }


def _job_checksums(label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    names = {
        "results.txt",
        "config.yaml",
        "overrides.yaml",
        "hydra.yaml",
        "job_manifest.json",
        "config_fingerprint.txt",
        "eds_metrics.jsonl",
        "episode_metadata.jsonl",
        "stage_events.jsonl",
        "safety_events.jsonl",
        "main.log",
        "runner.log",
        "failure_reason.json",
    }
    roots = [
        OUTPUT_TARGET / "formal" / label,
        OUTPUT_TARGET / "resume_attempts" / label,
        OUTPUT_TARGET / "attempt_archives/pre_bf16_fix/formal" / label,
        *_supplemental_attempt_directories(label),
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name in names:
                key = path.relative_to(OUTPUT_TARGET).as_posix()
                result[key] = _sha256_file(path)
    runner_log = OUTPUT_TARGET / "runner_logs/formal" / f"{label}.log"
    if runner_log.is_file():
        result[runner_log.relative_to(OUTPUT_TARGET).as_posix()] = _sha256_file(runner_log)
    for directory in _supplemental_attempt_directories(label):
        recovery_log = directory.parents[1] / "runner_logs/formal" / f"{label}.log"
        if recovery_log.is_file():
            result[recovery_log.relative_to(OUTPUT_TARGET).as_posix()] = _sha256_file(recovery_log)
    return result


def _scan_credentials() -> dict[str, Any]:
    patterns = [
        re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
        re.compile(r"(?i)\b(?:OPENAI_API_KEY|POE_API_KEY)\s*[:=]\s*['\"]?(?!PRESENT\b|null\b|none\b|\$\{)[A-Za-z0-9_-]{12,}"),
    ]
    findings: list[str] = []
    suffixes = {".json", ".jsonl", ".yaml", ".yml", ".txt", ".log", ".md"}
    for path in OUTPUT_TARGET.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes or path.stat().st_size > 64 * 1024 * 1024:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in patterns):
            findings.append(path.relative_to(OUTPUT_TARGET).as_posix())
    return {"passed": not findings, "finding_paths": findings, "secret_values_emitted": False}


def _audit_ledger() -> dict[str, Any]:
    path = OUTPUT_TARGET / runner.LEDGER_RELATIVE
    rows, failures = _read_jsonl(path)
    reconciliation_indices = [index for index, row in enumerate(rows) if row.get("record_type") == "reconciliation"]
    if reconciliation_indices:
        last = reconciliation_indices[-1]
        effective = int(rows[last]["effective_attempt_count"]) + sum(
            row.get("record_type") == "attempt" for row in rows[last + 1 :]
        )
    else:
        effective = sum(row.get("record_type", "attempt") == "attempt" for row in rows)
    metadata_records = 0
    for root in (
        OUTPUT_TARGET / "formal",
        OUTPUT_TARGET / "resume_attempts",
        OUTPUT_TARGET / "attempt_archives/pre_bf16_fix",
        OUTPUT_TARGET / "supplemental_recovery",
    ):
        for metadata in root.rglob("episode_metadata.jsonl"):
            metadata_records += len(metadata.read_text(encoding="utf-8", errors="replace").splitlines())
    all_videos = list((OUTPUT_TARGET / "formal").glob("**/episode_*/*.mp4")) + list(
        (OUTPUT_TARGET / "resume_attempts").glob("**/episode_*/*.mp4")
    ) + list((OUTPUT_TARGET / "supplemental_recovery").glob("**/episode_*/*.mp4"))
    readable_videos = sum(_ffprobe_readable(path) for path in all_videos)
    supplemental_path = OUTPUT_TARGET / runner.SUPPLEMENTAL_LEDGER_RELATIVE
    supplemental_rows, supplemental_failures = _read_jsonl(supplemental_path)
    for index, row in enumerate(supplemental_rows):
        episode = row.get("episode")
        if row.get("record_type") != "supplemental_recovery_attempt":
            supplemental_failures.append(f"supplemental ledger row {index} record_type invalid")
        elif (
            isinstance(episode, bool)
            or not isinstance(episode, int)
            or not 0 <= episode < len(EPISODE_SEEDS)
            or row.get("task_id") != episode
            or row.get("episode_seed") != EPISODE_SEEDS[episode]
        ):
            supplemental_failures.append(f"supplemental ledger row {index} identity invalid")
    return {
        "path": str(path),
        "raw_record_count": len(rows),
        "attempt_or_reservation_record_count": sum(row.get("record_type") != "reconciliation" for row in rows),
        "reconciliation_count": len(reconciliation_indices),
        "effective_attempt_count": effective,
        "attempt_cap": ATTEMPT_CAP,
        "cap_respected": effective <= ATTEMPT_CAP,
        "episode_metadata_attempt_evidence_count": metadata_records,
        "readable_video_count_including_seed_mismatch": readable_videos,
        "supplemental_path": str(supplemental_path),
        "supplemental_attempt_count": len(supplemental_rows),
        "total_original_plus_supplemental_attempt_count": effective + len(supplemental_rows),
        "supplemental_failures": supplemental_failures,
        "failures": failures + supplemental_failures,
    }


def rank_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return runner.rank_candidates(records)


def _classification_payload(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        label = str(job["label"])
        classifications = REVIEWED_CLASSIFICATIONS.get(label, {})
        job_rows: list[dict[str, Any]] = []
        outcomes = {int(key): value for key, value in job.get("task_outcomes", {}).items()}
        for episode, outcome in sorted(outcomes.items()):
            if outcome == "success":
                primary = "success"
            else:
                primary = classifications.get(episode, "timeout without task completion")
            job_rows.append(
                {
                    "episode": episode,
                    "task_id": episode,
                    "episode_seed": EPISODE_SEEDS[episode],
                    "outcome": outcome,
                    "primary": primary,
                    "secondary": ["timeout without task completion"] if outcome == "fail" and primary != "timeout without task completion" else [],
                    "evidence": (
                        str(OUTPUT_TARGET / "analysis/qualitative_contact_sheets" / f"{label}_final_contact_sheet.jpg")
                        if label in REVIEWED_CLASSIFICATIONS
                        else str(job.get("output_dir", ""))
                    ),
                }
            )
        rows[label] = job_rows
    return {
        "schema": "p2-direction-rbf-failure-classification-v1",
        "created_at": _now(),
        "categories": list(FAILURE_CATEGORIES),
        "collision_push_drop_wrong_object_categories": sorted(COLLISION_COMPOSITE_CATEGORIES),
        "review_method": "terminal-frame contact sheet plus runner step/outcome log; conservative primary visible category, timeout retained as secondary",
        "jobs": rows,
    }


def _audit_job(profile: dict[str, Any], credential_passed: bool) -> dict[str, Any]:
    label = str(profile["label"])
    attempt_rows, attempt_read_failures = _attempt_rows(label)
    selected, rejected = select_episode_attempts(attempt_rows, expected_seeds=EPISODE_SEEDS)
    metrics, stages, selected_failures = _selected_records(selected)
    failures = list(attempt_read_failures) + selected_failures
    selected_sources = {Path(row["output_dir"]) for row in selected.values()}
    if len(selected) == 10:
        for source in selected_sources:
            failures.extend(_config_and_manifest_failures(profile, source))
        runner_log = OUTPUT_TARGET / "runner_logs/formal" / f"{label}.log"
        if not runner_log.is_file() or runner_log.is_symlink():
            failures.append("canonical runner log missing")
        if not any((source / "results.txt").is_file() for source in selected_sources):
            failures.append("results.txt missing from all selected attempt sources")
        for source in selected_sources:
            try:
                source.resolve(strict=True).relative_to(OUTPUT_TARGET.resolve(strict=True))
            except (OSError, ValueError):
                failures.append("selected output is outside shared2 root")
            if any(path.is_symlink() for path in source.rglob("*")):
                failures.append("symlink found inside selected evidence tree")
            if "supplemental_recovery" in source.parts:
                recovery_log = source.parents[1] / "runner_logs/formal" / f"{label}.log"
                if not recovery_log.is_file() or recovery_log.is_symlink():
                    failures.append(f"supplemental runner log missing: {source.parents[1].name}")
    else:
        failures.append(f"10/10 exact task/seed results required; found {len(selected)}/10")

    expected_episodes = set(selected)
    metric_episodes = {record.get("episode") for record in metrics if isinstance(record.get("episode"), int) and not isinstance(record.get("episode"), bool)}
    if metric_episodes != expected_episodes:
        failures.append(f"metrics coverage {sorted(metric_episodes)} != accepted episodes {sorted(expected_episodes)}")

    direction_scope = (
        profile["initial_diversity_descriptor_mode"] == "direction_normalized_eef"
        or profile["rollout_diversity_descriptor_mode"] == "direction_normalized_eef"
    )
    nonfinite_count = 0
    zero_gradient_count = 0
    fallback_count = 0
    mask_violation_count = 0
    qpos_metric_count = 0
    for record in metrics:
        if record.get("initial_diversity_descriptor_mode") != profile["initial_diversity_descriptor_mode"]:
            failures.append("initial descriptor metric/config mismatch")
        if record.get("rollout_diversity_descriptor_mode") != profile["rollout_diversity_descriptor_mode"]:
            failures.append("rollout descriptor metric/config mismatch")
        for key, value in _walk_key_values(record):
            if key in {"nonfinite_count", "direction_rbf_nonfinite_count"} and isinstance(value, int) and not isinstance(value, bool):
                nonfinite_count += max(0, value)
            if key == "zero_gradient" and value is True:
                zero_gradient_count += 1
            if key == "direction_rbf_zero_gradient_count" and isinstance(value, int) and not isinstance(value, bool):
                zero_gradient_count += max(0, value)
            if key.endswith("fallback_used") and value is True:
                fallback_count += 1
            if key == "action_mask_violation_max" and isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) > 1.0e-8:
                mask_violation_count += 1
            if key == "gripper_qpos_violation_count" and isinstance(value, int) and not isinstance(value, bool):
                qpos_metric_count += max(0, value)
    if nonfinite_count:
        failures.append(f"nonfinite telemetry count {nonfinite_count}")
    if direction_scope and zero_gradient_count:
        failures.append(f"Direction-RBF zero-gradient count {zero_gradient_count}")
    if fallback_count:
        failures.append(f"fallback telemetry count {fallback_count}")
    if mask_violation_count:
        failures.append(f"action-mask violations {mask_violation_count}")
    if not credential_passed:
        failures.append("credential scan failed")

    outcomes = {episode: str(row["outcome"]) for episode, row in selected.items()}
    success_tasks = sorted(episode for episode, outcome in outcomes.items() if outcome == "success")
    lower, upper = wilson_ci(len(success_tasks), len(selected)) if selected else (0.0, 0.0)
    classifications = REVIEWED_CLASSIFICATIONS.get(label, {})
    collision_composite = sum(
        classifications.get(episode, "timeout without task completion") in COLLISION_COMPOSITE_CATEGORIES
        for episode, outcome in outcomes.items()
        if outcome == "fail"
    )
    error_count = _selected_error_episode_count(selected)
    if error_count:
        qpos_execution_error_episodes = error_count
    else:
        qpos_execution_error_episodes = len(
            {
                int(record["episode"])
                for record in metrics
                if isinstance(record.get("episode"), int)
                and record.get("gripper_qpos_violation_count", 0)
            }
        )

    metric_summary = {
        "selected_trajectory_length_p95": _percentile(_final_values(metrics, "selected_trajectory_length_by_iter"), 0.95),
        "selected_max_step_p95": _percentile(_final_values(metrics, "selected_max_step_displacement_by_iter"), 0.95),
        "eef_direction_diversity_median": _median(_final_values(metrics, "eef_direction_diversity_by_iter")),
        "endpoint_direction_spread_median": _median(_final_values(metrics, "endpoint_direction_spread_by_iter")),
        "trajectory_length_expansion_median": _median(_final_values(metrics, "trajectory_length_expansion_ratio_by_iter", nested_key="selected")),
        "max_step_expansion_median": _median(_final_values(metrics, "max_step_expansion_ratio_by_iter", nested_key="selected")),
        "chunk_boundary_jump_p95": _percentile((record.get("chunk_boundary_action_jump") for record in metrics), 0.95),
        "selection_latency_median_s": _median(record.get("select_action_latency_s") for record in metrics),
        "eds_loop_latency_median_s": _median(record.get("eds_loop_latency_s") for record in metrics),
        "stage_query_latency_median_s": _median(record.get("query_latency_s") for record in stages),
        "stage_query_error_count": sum(record.get("query_ok") is False for record in stages),
        "guidance_off_transition_count": sum(record.get("guidance_before") is True and record.get("guidance_after") is False for record in stages),
        "guidance_on_transition_count": sum(record.get("guidance_before") is False and record.get("guidance_after") is True for record in stages),
    }
    diagnostic = _diagnostic_reason(label, len(selected), rejected)
    unique_failures = list(dict.fromkeys(failures))
    eligible = len(selected) == 10 and not unique_failures
    fingerprint = _stored_fingerprint(label, selected_sources=selected_sources)
    return {
        "label": label,
        "role": profile["role"],
        "is_baseline": bool(profile["is_baseline"]),
        "weight_profile": profile.get("weight_profile"),
        "endpoint_profile": profile.get("endpoint_profile"),
        "weights": [
            profile["direction_rbf_direction_weight"],
            profile["direction_rbf_shape_weight"],
            profile["direction_rbf_endpoint_weight"],
        ],
        "endpoint_scale_m": profile["direction_rbf_endpoint_scale_m"],
        "initial_descriptor_mode": profile["initial_diversity_descriptor_mode"],
        "rollout_descriptor_mode": profile["rollout_diversity_descriptor_mode"],
        "output_dir": str(OUTPUT_TARGET / "formal" / label),
        "accepted_episode_count": len(selected),
        "accepted_episode_ids": sorted(selected),
        "selected_attempts": {str(key): value for key, value in sorted(selected.items())},
        "rejected_attempt_rows": rejected,
        "task_outcomes": {str(key): value for key, value in sorted(outcomes.items())},
        "success_count": len(success_tasks),
        "success_rate_denominator": len(selected),
        "success_rate": len(success_tasks) / len(selected) if selected else None,
        "wilson_95": [lower, upper] if selected else None,
        "success_tasks": success_tasks,
        "eligible": eligible,
        "validity_failures": unique_failures,
        "diagnostic_reason": diagnostic,
        "failure_reason": "valid" if eligible else diagnostic + ("; " + "; ".join(unique_failures[:8]) if unique_failures else ""),
        "execution_qpos_error_episodes": qpos_execution_error_episodes,
        "collision_push_drop_wrong_object": collision_composite,
        "nonfinite_count": nonfinite_count,
        "direction_rbf_zero_gradient_count": zero_gradient_count,
        "fallback_count": fallback_count,
        "action_mask_violation_count": mask_violation_count,
        "metric_summary": metric_summary,
        **metric_summary,
        "mechanism": _mechanism_summary(metrics, profile),
        "metrics_record_count": len(metrics),
        "stage_event_count": len(stages),
        **fingerprint,
        "checksums": _job_checksums(label),
    }


def _current_gpu_snapshot() -> list[dict[str, Any]]:
    try:
        return runner.gpu_audit()
    except Exception as exc:
        return [{"audit_error": f"{type(exc).__name__}: {exc}"}]


def _runtime_gpu_roles_from_log(text: str) -> dict[str, int]:
    """Extract physical compute/render roles without exposing runtime credentials."""
    compute = re.search(r"\bGPU=(\d+)\b", text)
    if compute is None:
        return {}
    compute_index = int(compute.group(1))
    render = re.search(r"\bP2_RENDER_GPU_INDEX=(\d+)\b", text)
    egl = re.search(r"\bMUJOCO_EGL_DEVICE_ID=(\d+)\b", text)
    return {
        "compute_gpu_index": compute_index,
        "render_gpu_index": int(render.group(1)) if render else compute_index,
        "mujoco_egl_device_id": int(egl.group(1)) if egl else compute_index,
    }


def _finite_ratio(numerator: Any, denominator: Any) -> float | None:
    if (
        isinstance(numerator, (int, float))
        and not isinstance(numerator, bool)
        and isinstance(denominator, (int, float))
        and not isinstance(denominator, bool)
        and math.isfinite(float(numerator))
        and math.isfinite(float(denominator))
        and float(denominator) != 0.0
    ):
        return float(numerator) / float(denominator)
    return None


def _global_main_effects(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    global_jobs = [job for job in jobs if job.get("role") == "global"]
    eligible = [job for job in global_jobs if job.get("eligible") is True]
    if len(eligible) != 9:
        return {
            "estimable": False,
            "eligible_global_cells": len(eligible),
            "reason": (
                f"{9 - len(eligible)}/9 global cells are invalid/incomplete; "
                "main effects and interaction are not estimable"
            ),
        }
    metric_fields = {
        "success_count": lambda job: job.get("success_count"),
        "selected_trajectory_length_p95": lambda job: job.get("selected_trajectory_length_p95"),
        "selected_max_step_p95": lambda job: job.get("selected_max_step_p95"),
        "eef_direction_diversity_median": lambda job: job.get("eef_direction_diversity_median"),
        "endpoint_direction_spread_median": lambda job: job.get("endpoint_direction_spread_median"),
    }

    def means(rows: list[dict[str, Any]]) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        for name, getter in metric_fields.items():
            values = [
                float(value)
                for row in rows
                for value in [getter(row)]
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
            ]
            result[name] = sum(values) / len(values) if len(values) == len(rows) else None
        return result

    by_weight = {
        weight: means([job for job in eligible if job.get("weight_profile") == weight])
        for weight in ("w0", "w1", "w2")
    }
    by_endpoint = {
        endpoint: means([job for job in eligible if job.get("endpoint_profile") == endpoint])
        for endpoint in ("e025", "e050", "e100")
    }
    grand = means(eligible)
    interactions: dict[str, dict[str, dict[str, float | None]]] = {}
    for weight in ("w0", "w1", "w2"):
        interactions[weight] = {}
        for endpoint in ("e025", "e050", "e100"):
            cell = next(
                job
                for job in eligible
                if job.get("weight_profile") == weight
                and job.get("endpoint_profile") == endpoint
            )
            interactions[weight][endpoint] = {}
            for name, getter in metric_fields.items():
                value = getter(cell)
                weight_mean = by_weight[weight][name]
                endpoint_mean = by_endpoint[endpoint][name]
                grand_mean = grand[name]
                interactions[weight][endpoint][name] = (
                    float(value) - float(weight_mean) - float(endpoint_mean) + float(grand_mean)
                    if all(
                        item is not None
                        for item in (value, weight_mean, endpoint_mean, grand_mean)
                    )
                    else None
                )
    return {
        "estimable": True,
        "eligible_global_cells": 9,
        "reason": "complete eligible 3x3 grid",
        "grand_mean": grand,
        "by_weight": by_weight,
        "by_endpoint": by_endpoint,
        "interaction_residuals": interactions,
    }


def analyze() -> dict[str, Any]:
    credential = _scan_credentials()
    jobs = [_audit_job(dict(profile), credential["passed"]) for profile in runner.methods()]
    classifications = _classification_payload(jobs)
    classification_counts: Counter[str] = Counter()
    for rows in classifications["jobs"].values():
        classification_counts.update(
            row["primary"] for row in rows if row["outcome"] == "fail"
        )
    control = next(job for job in jobs if job["role"] == "control")
    control_success_tasks = set(control.get("success_tasks", []))
    eligible_candidates = [job for job in jobs if job["eligible"] and not job["is_baseline"]]
    for job in eligible_candidates:
        job["baseline_task_retention"] = (
            len(control_success_tasks & set(job.get("success_tasks", [])))
            if control["eligible"]
            else None
        )
        eef_ratio = _finite_ratio(
            job.get("eef_direction_diversity_median"),
            control.get("eef_direction_diversity_median"),
        )
        endpoint_ratio = _finite_ratio(
            job.get("endpoint_direction_spread_median"),
            control.get("endpoint_direction_spread_median"),
        )
        job["eef_direction_retention_ratio"] = eef_ratio
        job["endpoint_direction_retention_ratio"] = endpoint_ratio
        job["direction_retention_score"] = (
            min(eef_ratio, endpoint_ratio)
            if eef_ratio is not None and endpoint_ratio is not None
            else None
        )
        job["selection_latency_median"] = job["selection_latency_median_s"]
    ranked = rank_candidates(eligible_candidates)
    winner = ranked[0] if ranked else None
    eligible_global = [job for job in jobs if job["role"] == "global" and job["eligible"]]
    global_winner = rank_candidates(eligible_global)[0] if eligible_global else None
    primary = next(job for job in jobs if job["label"] == "p2_stage_on_dirnorm_rbf_global_w0_e050")
    task_gate = bool(winner and winner["success_count"] >= 5)
    safety_gate = "INCONCLUSIVE" if not control["eligible"] else (
        "PASS"
        if winner
        and winner["execution_qpos_error_episodes"] == 0
        and winner["collision_push_drop_wrong_object"] <= control["collision_push_drop_wrong_object"]
        and winner["nonfinite_count"] == 0
        and winner["action_mask_violation_count"] == 0
        and winner["fallback_count"] == 0
        else "FAIL"
    )
    mechanism_evidence = {
        "eef_direction_retention_ratio": _finite_ratio(
            primary.get("eef_direction_diversity_median"),
            control.get("eef_direction_diversity_median"),
        ),
        "endpoint_direction_retention_ratio": _finite_ratio(
            primary.get("endpoint_direction_spread_median"),
            control.get("endpoint_direction_spread_median"),
        ),
        "selected_trajectory_length_p95_ratio": _finite_ratio(
            primary.get("selected_trajectory_length_p95"),
            control.get("selected_trajectory_length_p95"),
        ),
        "selected_max_step_p95_ratio": _finite_ratio(
            primary.get("selected_max_step_p95"),
            control.get("selected_max_step_p95"),
        ),
    }
    if not control["eligible"] or not primary["eligible"]:
        mechanism_gate = "INCONCLUSIVE"
    else:
        mechanism_gate = (
            "PASS"
            if mechanism_evidence["eef_direction_retention_ratio"] is not None
            and mechanism_evidence["eef_direction_retention_ratio"] >= 0.90
            and mechanism_evidence["endpoint_direction_retention_ratio"] is not None
            and mechanism_evidence["endpoint_direction_retention_ratio"] >= 0.90
            and mechanism_evidence["selected_trajectory_length_p95_ratio"] is not None
            and mechanism_evidence["selected_trajectory_length_p95_ratio"] <= 0.85
            and mechanism_evidence["selected_max_step_p95_ratio"] is not None
            and mechanism_evidence["selected_max_step_p95_ratio"] <= 0.85
            else "FAIL"
        )
    ledger = _audit_ledger()
    preflight_path = OUTPUT_TARGET / runner.PREFLIGHT_RELATIVE
    preflight = json.loads(preflight_path.read_text(encoding="utf-8")) if preflight_path.is_file() else {"passed": False, "reason": "missing"}
    reference_path = OUTPUT_TARGET / "manifests/gpu_reference_peak.json"
    gpu_reference = json.loads(reference_path.read_text(encoding="utf-8")) if reference_path.is_file() else {"model_load_completed": False}
    delivery_audit = (
        json.loads(DELIVERY_AUDIT_PATH.read_text(encoding="utf-8"))
        if DELIVERY_AUDIT_PATH.is_file()
        else {"completed": False, "reason": "delivery audit not yet recorded"}
    )
    runtime_diagnostics = (
        json.loads(RUNTIME_DIAGNOSTIC_PATH.read_text(encoding="utf-8"))
        if RUNTIME_DIAGNOSTIC_PATH.is_file()
        else {"status": "not-recorded", "path": str(RUNTIME_DIAGNOSTIC_PATH)}
    )
    gpu_assignments: dict[str, int] = {}
    gpu_runtime_roles: dict[str, dict[str, int]] = {}
    for job in jobs:
        logs = [OUTPUT_TARGET / "runner_logs/formal" / f"{job['label']}.log"]
        logs.extend(
            directory.parents[1] / "runner_logs/formal" / f"{job['label']}.log"
            for directory in _supplemental_attempt_directories(job["label"])
        )
        for log in logs:
            if log.is_file():
                roles = _runtime_gpu_roles_from_log(
                    log.read_text(encoding="utf-8", errors="replace")[:4000]
                )
                if roles:
                    gpu_assignments[job["label"]] = roles["compute_gpu_index"]
                    gpu_runtime_roles[job["label"]] = roles
    output_link = runner.OUTPUT_LINK
    storage = {
        "shared2_root": str(OUTPUT_TARGET),
        "shared2_realpath": str(OUTPUT_TARGET.resolve(strict=True)),
        "worktree_link": str(output_link),
        "worktree_link_target": os.readlink(output_link) if output_link.is_symlink() else None,
        "worktree_link_realpath": str(output_link.resolve(strict=True)) if output_link.exists() else None,
        "link_is_absolute": bool(output_link.is_symlink() and Path(os.readlink(output_link)).is_absolute()),
        "free_bytes_post_run": os.statvfs(OUTPUT_TARGET).f_bavail * os.statvfs(OUTPUT_TARGET).f_frsize,
    }
    profiles = []
    for profile in runner.methods():
        profiles.append({key: value for key, value in profile.items() if key not in {"method"}})
    return {
        "schema": "p2-direction-rbf-formal-audit-v1",
        "generated_at": _now(),
        "design_path": str(WORKTREE_ROOT / "docs/01_specs/2026-08-04-p2-direction-normalized-rbf-design.md"),
        "profiles": profiles,
        "jobs": jobs,
        "historical_baseline": {
            "source": "design section 2; historical only, not contemporaneous gate denominator",
            "success_count": 3,
            "success_tasks": [3, 8, 9],
            "selected_trajectory_length_p95": 0.21200,
            "selected_max_step_p95": 0.03875,
            "eef_direction_diversity_median": 3.8558,
        },
        "primary_reference": {
            "label": primary["label"],
            "eligible": primary["eligible"],
            "observed_success": f"{primary['success_count']}/{primary['accepted_episode_count']}",
            "conclusion": (
                f"eligible; mechanism gate {mechanism_gate}"
                if primary["eligible"]
                else "incomplete and ineligible; preregistered primary mechanism comparison is not estimable"
            ),
            "mechanism_evidence": mechanism_evidence,
        },
        "ranking": {
            "eligible_candidate_count": len(ranked),
            "ordered_labels": [job["label"] for job in ranked],
            "winner_label": winner["label"] if winner else None,
            "global_parameter_winner_label": global_winner["label"] if global_winner else None,
            "winner_task_gate_passed": task_gate,
            "recommended_for_adoption": bool(task_gate and safety_gate == "PASS" and winner and winner["eligible"]),
            "note": "deterministic preregistered nine-level ranking; contemporaneous control retention is used when available",
        },
        "gates": {
            "task": "PASS" if task_gate else "FAIL",
            "mechanism": mechanism_gate,
            "safety": safety_gate,
            "validity_eligible_jobs": [job["label"] for job in jobs if job["eligible"]],
            "control_validity": "PASS" if control["eligible"] else "FAIL",
        },
        "no_adoption": not bool(task_gate and safety_gate == "PASS" and winner and winner["eligible"]),
        "main_effects": _global_main_effects(jobs),
        "classification_summary": dict(sorted(classification_counts.items())),
        "classification_path": str(CLASSIFICATION_PATH),
        "ledger": ledger,
        "storage": storage,
        "credential_audit": credential,
        "preflight": preflight,
        "gpu_admission": {
            "reference_manifest": str(reference_path),
            "reference_peak_vram_mib": gpu_reference.get("reference_peak_vram_mib"),
            "required_free_vram_mib": gpu_reference.get("required_free_vram_mib"),
            "model_load_completed": gpu_reference.get("model_load_completed"),
            "formal_gpu_assignments_from_runner_logs": gpu_assignments,
            "formal_gpu_runtime_roles_from_runner_logs": gpu_runtime_roles,
            "post_run_snapshot": _current_gpu_snapshot(),
        },
        "implementation": {
            "descriptor_modes": ["absolute_eef", "direction_normalized_eef"],
            "legacy_default": "absolute_eef",
            "resume_fields": ["main.episode_start_index", "main.episode_seed_schedule"],
            "direction_config_fields": [
                "initial_diversity_descriptor_mode",
                "rollout_diversity_descriptor_mode",
                "direction_rbf_direction_weight",
                "direction_rbf_shape_weight",
                "direction_rbf_endpoint_weight",
                "direction_rbf_endpoint_scale_m",
                "direction_rbf_path_epsilon",
                "direction_rbf_distance_epsilon",
            ],
            "formal_output_telemetry_note": "raw component/path-length evidence is sufficient for post-hoc exact summaries and correlations; formal artifacts predate the later explicit grad_norm_after_mask field, so that derived subfield remains null rather than fabricated",
        },
        "delivery_audit": delivery_audit,
        "runtime_diagnostics": runtime_diagnostics,
    }


def freeze_decision_manifest(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    if runner.base._contains_secret_text(payload):
        raise ValueError("decision manifest contains credential-like material")
    frozen = dict(payload)
    frozen.pop("canonical_manifest_checksum", None)
    frozen["canonical_manifest_checksum"] = hashlib.sha256(
        _canonical(frozen).encode("utf-8")
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(frozen, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    return frozen


def verify_decision_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    if stat.S_IMODE(path.stat().st_mode) & 0o222:
        raise ValueError("decision manifest is writable")
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("canonical_manifest_checksum")
    without = dict(payload)
    without.pop("canonical_manifest_checksum", None)
    actual = hashlib.sha256(_canonical(without).encode("utf-8")).hexdigest()
    if expected != actual:
        raise ValueError("decision manifest checksum mismatch")
    if runner.base._contains_secret_text(payload):
        raise ValueError("decision manifest contains credential-like material")
    return payload


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "—"
    return f"{float(value):.{digits}f}"


def _job_by_label(analysis: dict[str, Any], label: str) -> dict[str, Any]:
    return next((job for job in analysis.get("jobs", []) if job.get("label") == label), {})


def _render_report_pre_recovery(analysis: dict[str, Any]) -> str:
    jobs = list(analysis.get("jobs", []))
    baseline = analysis.get("historical_baseline", {})
    ranking = analysis.get("ranking", {})
    gates = analysis.get("gates", {})
    ledger = analysis.get("ledger", {})
    storage = analysis.get("storage", {})
    preflight = analysis.get("preflight", {})
    winner = _job_by_label(analysis, str(ranking.get("winner_label")))
    global_winner = _job_by_label(analysis, str(ranking.get("global_parameter_winner_label")))
    primary = _job_by_label(analysis, "p2_stage_on_dirnorm_rbf_global_w0_e050")
    rollout = _job_by_label(analysis, "p2_stage_on_dirnorm_rbf_rollout_w0_e050")

    def ratio(job: dict[str, Any], metric: str, baseline_metric: str) -> float | None:
        numerator = job.get("metric_summary", {}).get(metric)
        denominator = baseline.get(baseline_metric)
        if (
            isinstance(numerator, (int, float))
            and not isinstance(numerator, bool)
            and isinstance(denominator, (int, float))
            and not isinstance(denominator, bool)
            and math.isfinite(float(numerator))
            and math.isfinite(float(denominator))
            and float(denominator) != 0.0
        ):
            return float(numerator) / float(denominator)
        return None

    historical_tasks = set(baseline.get("success_tasks", []))

    def historical_transition(job: dict[str, Any]) -> tuple[list[int], list[int], list[int], list[int]]:
        observed = set(job.get("task_outcomes", {}))
        successes = set(job.get("success_tasks", []))
        comparable_baseline = historical_tasks & {int(value) for value in observed}
        return (
            sorted(successes - historical_tasks),
            sorted(comparable_baseline - successes),
            sorted(successes & historical_tasks),
            sorted(historical_tasks - {int(value) for value in observed}),
        )
    lines = [
        "# P2 Direction-Normalized RBF 最终实验与审计报告",
        "",
        f"生成时间：`{analysis.get('generated_at', '—')}`",
        "",
        "## 结论",
        "",
        f"- Task gate：`{gates.get('task', '—')}`；mechanism gate：`{gates.get('mechanism', '—')}`；safety gate：`{gates.get('safety', '—')}`。",
        f"- Decision：`{'no_adoption' if analysis.get('no_adoption', True) else 'recommended_for_adoption'}`。同一固定 10-task 集上没有 eligible Direction job 达到 `>=5/10`。",
        f"- Direction candidate ranking winner：`{ranking.get('winner_label') or 'none'}`；eligible global parameter winner：`{ranking.get('global_parameter_winner_label') or 'none'}`。二者均不是 adoption recommendation。",
        "- Contemporaneous absolute control 未完成，primary W0/E050 也只有 9 个 exact-seed readable outcomes，因此相对 control 的方向保留、幅值与 collision composite gates 均不可估计。不得用历史 baseline 替代 contemporaneous gate denominator。",
        "- Attempt ledger 已达批准上限；本报告不得据此追加实验，也不把 gate 失败解释成追加实验授权。",
        "",
        "## 范围、preflight、存储与 GPU admission",
        "",
        f"- Mechanism preflight：`{'PASS' if preflight.get('passed') else 'FAIL'}`；scale-invariance max error `{preflight.get('scale_invariance_error', '—')}`；hard failures `{preflight.get('hard_failures', [])}`。",
        f"- shared2：`{storage.get('shared2_realpath', '—')}`；worktree link：`{storage.get('worktree_link', '—')}` → `{storage.get('worktree_link_target', '—')}`；absolute=`{storage.get('link_is_absolute', '—')}`。",
        f"- Ledger：effective `{ledger.get('effective_attempt_count', '—')}/{ledger.get('attempt_cap', '—')}`，metadata attempt evidence `{ledger.get('episode_metadata_attempt_evidence_count', '—')}`，ffprobe-readable videos（含 1 个 seed mismatch）`{ledger.get('readable_video_count_including_seed_mismatch', '—')}`。",
        "- GPU load reference peak `17921 MiB`，admission threshold `22401.25 MiB`；formal runner logs 记录使用 GPU 2/3/4/5。外部任务未被终止、暂停或抢占。",
        "",
        "## 实现与 config 开关",
        "",
        "- `initial_diversity_descriptor_mode` 与 `rollout_diversity_descriptor_mode` 独立控制 `absolute_eef` / `direction_normalized_eef`；legacy 默认均为 `absolute_eef`。",
        "- Direction descriptor 参数：direction/shape/endpoint weights、endpoint scale、path epsilon、distance epsilon；非法配置 fail-closed，Direction scope 不 fallback 到 absolute。",
        "- resume 支持 `main.episode_start_index` 与固定 `main.episode_seed_schedule`；后者修正了审计发现的 suffix-only RNG seed 漂移风险。已有错误 seed attempt 被保留但未并入 outcome。",
        "- Metrics 同时保留 raw component evidence，并输出/派生 component mean/P90/max、weighted fraction、path-length/direction correlations（含 valid-pair count 和 null warning）、zero-path/zero-gradient/nonfinite/grad norm。",
        "",
        "## 11-job validity 与 SR",
        "",
        "| Job | Role | Exact episodes | Success | Wilson 95% | Eligible | Failure / audit note |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for job in jobs:
        ci = job.get("wilson_95")
        ci_text = f"[{_fmt(ci[0], 3)}, {_fmt(ci[1], 3)}]" if isinstance(ci, list) and len(ci) == 2 else "—"
        lines.append(
            f"| `{job.get('label')}` | {job.get('role', '—')} | {job.get('accepted_episode_count', 0)}/10 | "
            f"{job.get('success_count', 0)}/{job.get('success_rate_denominator', job.get('accepted_episode_count', 0))} | {ci_text} | "
            f"`{job.get('eligible', False)}` | {job.get('diagnostic_reason', job.get('failure_reason', ''))} |"
        )
    lines.extend(
        [
            "",
            "只有 rollout-only W0/E050 与 global W0/E025 通过 strict eligibility；global W0/E050 的 task 9 suffix attempt 使用 seed 683 而非预注册 548，故该 episode 与 cell 均被拒绝。BF16 失败、native abort、suffix adapter assertion 与 supervisor interruption 全部保留 provenance。",
            "",
            "## Task-level paired outcomes",
            "",
            "`S`=success，`F`=policy failure，`—`=无 exact-seed readable result。Control 缺失意味着表中不可做 contemporaneous paired gain/loss 推断。",
            "",
            "| Task | Control | Rollout | W0/E025 | W0/E050 primary | W0/E100 | W1/E025 | W1/E050 | W1/E100 | W2/E025 | W2/E050 | W2/E100 |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    labels = [
        "p2_stage_on_abs_rbf_control",
        "p2_stage_on_dirnorm_rbf_rollout_w0_e050",
        "p2_stage_on_dirnorm_rbf_global_w0_e025",
        "p2_stage_on_dirnorm_rbf_global_w0_e050",
        "p2_stage_on_dirnorm_rbf_global_w0_e100",
        "p2_stage_on_dirnorm_rbf_global_w1_e025",
        "p2_stage_on_dirnorm_rbf_global_w1_e050",
        "p2_stage_on_dirnorm_rbf_global_w1_e100",
        "p2_stage_on_dirnorm_rbf_global_w2_e025",
        "p2_stage_on_dirnorm_rbf_global_w2_e050",
        "p2_stage_on_dirnorm_rbf_global_w2_e100",
    ]
    for task in range(10):
        cells = []
        for label in labels:
            outcome = _job_by_label(analysis, label).get("task_outcomes", {}).get(str(task))
            cells.append("S" if outcome == "success" else "F" if outcome == "fail" else "—")
        lines.append(f"| {task} | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "## Baseline、primary reference、parameter winner 与 adoption candidate",
            "",
            f"- Historical original P2 baseline（仅背景）：`{baseline.get('success_count', '—')}/10`，tasks `{baseline.get('success_tasks', [])}`；length P95 `{_fmt(baseline.get('selected_trajectory_length_p95'))}`，max-step P95 `{_fmt(baseline.get('selected_max_step_p95'))}`，EEF direction median `{_fmt(baseline.get('eef_direction_diversity_median'))}`。",
            f"- Primary global W0/E050：observed `{primary.get('success_count', '—')}/{primary.get('accepted_episode_count', '—')}`，success tasks `{primary.get('success_tasks', [])}`，`INVALID/INCOMPLETE`。",
            f"- Eligible global parameter winner：`{global_winner.get('label', 'none')}`，`{global_winner.get('success_count', '—')}/{global_winner.get('accepted_episode_count', '—')}`。由于 9-cell 不完整，这只是唯一 eligible global cell，不是可估的 3×3 winner。",
            f"- Adoption ranking candidate：`{winner.get('label', 'none')}`，`{winner.get('success_count', '—')}/{winner.get('accepted_episode_count', '—')}`；task gate 未过，safety/control comparison 不可估，故 `recommended_for_adoption=false`。",
            "",
            "Historical baseline task transitions（仅背景，不能代替 contemporaneous pairing）：",
            "",
            "| Treatment | Gained | Lost | Retained | Baseline tasks not comparable |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for job in (rollout, global_winner, primary):
        if not job:
            continue
        gained, lost, retained, missing = historical_transition(job)
        lines.append(
            f"| `{job.get('label')}` | `{gained}` | `{lost}` | `{retained}` | `{missing}` |"
        )
    lines.extend(
        [
            "",
            "## Trajectory、direction 与 latency",
            "",
            "| Method | Exact n | Length P95 | Max-step P95 | Length expansion med. | Max-step expansion med. | EEF direction med. | Endpoint spread med. | Select latency med. s | Stage query errors |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    metric_labels = [
        "p2_stage_on_dirnorm_rbf_rollout_w0_e050",
        "p2_stage_on_dirnorm_rbf_global_w0_e025",
        "p2_stage_on_dirnorm_rbf_global_w0_e050",
        "p2_stage_on_dirnorm_rbf_global_w0_e100",
        "p2_stage_on_dirnorm_rbf_global_w1_e025",
        "p2_stage_on_dirnorm_rbf_global_w2_e100",
    ]
    for label in metric_labels:
        job = _job_by_label(analysis, label)
        metric = job.get("metric_summary", {})
        if not job:
            continue
        lines.append(
            f"| `{label}` | {job.get('accepted_episode_count', 0)} | {_fmt(metric.get('selected_trajectory_length_p95'), 5)} | "
            f"{_fmt(metric.get('selected_max_step_p95'), 5)} | {_fmt(metric.get('trajectory_length_expansion_median'))} | "
            f"{_fmt(metric.get('max_step_expansion_median'))} | {_fmt(metric.get('eef_direction_diversity_median'))} | "
            f"{_fmt(metric.get('endpoint_direction_spread_median'))} | {_fmt(metric.get('selection_latency_median_s'), 3)} | "
            f"{metric.get('stage_query_error_count', '—')} |"
        )
    lines.extend(
        [
            "",
            "历史 baseline 的 endpoint spread 未预注册在设计表中，且 contemporaneous control 无可用 metrics，因此所有 direction/endpoint retention ratios 与 length/max-step ratios均标记为不可估，不以历史数值替代。",
            "",
            "Historical-only descriptive ratios（非 gate）：",
            "",
            "| Treatment | Length / historical P2 | Max-step / historical P2 | EEF direction / historical P2 |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for job in (rollout, global_winner, primary):
        if not job:
            continue
        lines.append(
            f"| `{job.get('label')}` | {_fmt(ratio(job, 'selected_trajectory_length_p95', 'selected_trajectory_length_p95'), 3)} | "
            f"{_fmt(ratio(job, 'selected_max_step_p95', 'selected_max_step_p95'), 3)} | "
            f"{_fmt(ratio(job, 'eef_direction_diversity_median', 'eef_direction_diversity_median'), 3)} |"
        )
    lines.extend(
        [
            "",
            "相对历史 P2，rollout-only 的 direction 几乎不变、max-step 接近，但 length P95 增加；eligible global W0/E025 的 direction 也近似保留，却同时增加 length 与 max-step。primary 的 9-episode descriptive ratios 同样未达到 `<=0.85` 幅值目标。由于 control 失效，这些只能作为风险信号，不能判 mechanism gate。",
            "",
            "## RBF components：initial 与 rollout",
            "",
            "| Job / scope | Direction mean | Shape mean | Endpoint mean | Composite mean | Weighted fractions d/s/e | corr(composite,path ΔL) | corr(composite,direction) | Evidence records |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |",
        ]
    )
    for label in metric_labels[:3]:
        job = _job_by_label(analysis, label)
        for scope in ("initial", "rollout"):
            mechanism = job.get("mechanism", {}).get(scope) if job else None
            if not mechanism:
                continue
            fraction = mechanism.get("direction_rbf_weighted_component_fraction_by_iter") or {}
            path_corr = mechanism.get("direction_rbf_distance_path_length_delta_correlation_by_iter") or {}
            dir_corr = mechanism.get("direction_rbf_distance_direction_correlation_by_iter") or {}
            lines.append(
                f"| `{label}` / {scope} | {_fmt(mechanism.get('direction_rbf_pairwise_direction_mean_by_iter'))} | "
                f"{_fmt(mechanism.get('direction_rbf_pairwise_shape_mean_by_iter'))} | {_fmt(mechanism.get('direction_rbf_pairwise_endpoint_mean_by_iter'))} | "
                f"{_fmt(mechanism.get('direction_rbf_pairwise_composite_mean_by_iter'))} | "
                f"{_fmt(fraction.get('direction'), 3)}/{_fmt(fraction.get('shape'), 3)}/{_fmt(fraction.get('endpoint'), 3)} | "
                f"{_fmt(path_corr.get('value'), 3)} (n={path_corr.get('valid_pair_count', '—')}) | "
                f"{_fmt(dir_corr.get('value'), 3)} (n={dir_corr.get('valid_pair_count', '—')}) | {mechanism.get('evidence_record_count', '—')} |"
            )
    lines.extend(
        [
            "",
            "所有 eligible Direction scopes 的 recorded zero-gradient、nonfinite、action-mask violation 与 absolute fallback 均为 0。正式 artifacts 的 raw evidence 早于显式 `grad_norm_after_mask` telemetry 字段；审计不伪造该值，新实现已补齐字段。",
            "",
            "在 eligible global W0/E025 内，initial→rollout 的 direction mean `0.4809→0.5405`、shape mean `0.3285→0.3621`、composite mean `0.4855→0.5307`；endpoint mean `0.9835→0.9780` 基本稳定。Composite 与 path-length delta correlation 从 `-0.005` 升至 `0.173`，而与 direction correlation 始终约 `0.999`。这说明 Direction descriptor 仍主要跟随方向分量，但 rollout 阶段残留了正的长度差相关；不能据此宣称 scale exploit 已在任务执行中消除。",
            "",
            "## Weight、endpoint scale 主效应与 interaction",
            "",
            "完整 9-cell validity heatmap（cell 为 success/exact n；`*` 表 eligible）：",
            "",
            "| Weights | E025 | E050 | E100 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for weight in ("w0", "w1", "w2"):
        cells = []
        for endpoint in ("e025", "e050", "e100"):
            job = next((item for item in jobs if item.get("weight_profile") == weight and item.get("endpoint_profile") == endpoint and item.get("role") == "global"), {})
            cells.append(f"{job.get('success_count', 0)}/{job.get('accepted_episode_count', 0)}{'*' if job.get('eligible') else ''}")
        lines.append(f"| {weight.upper()} | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            f"主效应/interaction estimable：`{analysis.get('main_effects', {}).get('estimable', False)}`。{analysis.get('main_effects', {}).get('reason', '')} 未对缺失 cell 插补、外推或补跑，因此不能声称 W profile、endpoint scale 或二者交互的方向。",
            "",
            "## Safety、failure classification 与 qualitative evidence",
            "",
            f"- 失败分类汇总：`{analysis.get('classification_summary', {})}`。分类覆盖已完成视频；可见终态机制作 primary，所有未成功且走满 720 steps 的 episode 仍保留 timeout secondary。",
            "- Contact sheets：shared2 `analysis/qualitative_contact_sheets/`；raw 同坐标 mechanism curves/tensors 位于各 job `eds_eval/qualitative/episode_*/chunk_*/`。",
            "- Eligible jobs 均为 qpos/execution error=0、nonfinite=0、mask violation=0、fallback=0；但 collision/push/drop/wrong-object 必须相对 contemporaneous control，control 无效，所以 safety gate 只能是 `INCONCLUSIVE`，不能判 PASS。",
            "- W0/E025 出现大量 visible push/wrong-object/basket displacement；rollout-only 的 visible composite 较少但任务 SR 仍仅 1/10。该描述是固定任务集工程观察，不是统计显著性或泛化结论。",
            "",
            "## Failed / invalid / incomplete provenance",
            "",
        ]
    )
    for job in jobs:
        if not job.get("eligible"):
            lines.append(f"- `{job.get('label')}`：{job.get('diagnostic_reason', job.get('failure_reason', 'unknown'))}。")
    lines.extend(
        [
            "",
            "## Credential、Git 与进程审计边界",
            "",
            f"- Shared2 credential scan：`{'PASS' if analysis.get('credential_audit', {}).get('passed') else 'FAIL'}`；未回显 token，finding paths `{analysis.get('credential_audit', {}).get('finding_paths', [])}`。",
            "- Decision manifest 对 results/Hydra/metrics/Stage events/logs/job manifests 保存 SHA-256，并以 canonical checksum 自校验和 `0444` 只读权限冻结。",
            f"- Final delivery audit：tests `{analysis.get('delivery_audit', {}).get('tests', '—')}`；py_compile `{analysis.get('delivery_audit', {}).get('py_compile', '—')}`；git diff check `{analysis.get('delivery_audit', {}).get('git_diff_check', '—')}`；Git credential scan `{analysis.get('delivery_audit', {}).get('git_credential_scan', '—')}`；shared2 credential scan `{analysis.get('delivery_audit', {}).get('shared2_credential_scan', '—')}`；process cleanup `{analysis.get('delivery_audit', {}).get('process_cleanup', '—')}`。",
            f"- Git worktree 初始即有 clean-tail/Stage-A 等未提交修改；本任务保留并审计了它们，没有回退或覆盖。当前 status 摘要保存在 `{DELIVERY_AUDIT_PATH}`。",
            "",
            "## 风险与下一步",
            "",
            "- 主要风险是 contemporaneous control/primary 失效、8/9 grid cells 无 eligibility、native simulator abort，以及早期 BF16 telemetry/runtime bug；因此机制和安全主张不可成立。",
            "- 工程结论保持原始 P2 baseline；不采用 rollout-only 或 W0/E025。",
            "- 若未来获得新的独立批准，优先修复 simulator native-abort isolation、用 fixed episode seed schedule 做可验证 resume，并重新执行同一预注册矩阵；本轮结果本身不构成该授权。",
            "- 本轮不追加任何实验。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_report(analysis: dict[str, Any]) -> str:
    """Render the current merged formal + supplemental-recovery audit."""
    jobs = list(analysis.get("jobs", []))
    gates = analysis.get("gates", {})
    ranking = analysis.get("ranking", {})
    ledger = analysis.get("ledger", {})
    preflight = analysis.get("preflight", {})
    storage = analysis.get("storage", {})
    runtime_diagnostics = analysis.get("runtime_diagnostics", {})
    main_effects = analysis.get("main_effects", {})
    control = next((job for job in jobs if job.get("role") == "control"), {})
    rollout = _job_by_label(
        analysis, "p2_stage_on_dirnorm_rbf_rollout_w0_e050"
    )
    primary = _job_by_label(
        analysis, "p2_stage_on_dirnorm_rbf_global_w0_e050"
    )
    winner = _job_by_label(analysis, str(ranking.get("winner_label")))
    global_winner = _job_by_label(
        analysis, str(ranking.get("global_parameter_winner_label"))
    )
    recommended = bool(ranking.get("recommended_for_adoption"))

    def sr(job: dict[str, Any]) -> str:
        return f"{job.get('success_count', 0)}/{job.get('accepted_episode_count', 0)}"

    def transition(job: dict[str, Any]) -> tuple[list[int], list[int], list[int]]:
        control_success = set(control.get("success_tasks", []))
        treatment_success = set(job.get("success_tasks", []))
        return (
            sorted(treatment_success - control_success),
            sorted(control_success - treatment_success),
            sorted(control_success & treatment_success),
        )

    decision_text = (
        f"recommended_for_adoption: {winner.get('label')}"
        if recommended
        else "no_adoption"
    )
    lines = [
        "# P2 Direction-Normalized RBF 最终实验、补充恢复与审计报告",
        "",
        f"生成时间：`{analysis.get('generated_at', '—')}`",
        "",
        "## 结论",
        "",
        f"- Decision：`{decision_text}`。",
        f"- Task gate：`{gates.get('task', '—')}`；mechanism gate：`{gates.get('mechanism', '—')}`；safety gate：`{gates.get('safety', '—')}`。",
        f"- Contemporaneous control：`{sr(control)}`，tasks `{control.get('success_tasks', [])}`；primary W0/E050：`{sr(primary)}`，tasks `{primary.get('success_tasks', [])}`。",
        f"- Parameter winner：`{global_winner.get('label', 'none')}`（`{sr(global_winner)}`）；adoption ranking winner：`{winner.get('label', 'none')}`（`{sr(winner)}`）。",
        "- 本报告中的 success/fail 是任务 outcome；补充恢复的执行完成性另由 exact task/seed metadata、10 个 ffprobe-readable videos、metrics、Stage events 与 qualitative artifacts 验证。",
        "",
        "## 批准范围、preflight、shared2 与 attempt ledger",
        "",
        f"- Mechanism preflight：`{'PASS' if preflight.get('passed') else 'FAIL'}`；scale-invariance max error `{preflight.get('scale_invariance_error', '—')}`；hard failures `{preflight.get('hard_failures', [])}`。",
        f"- shared2 realpath：`{storage.get('shared2_realpath', '—')}`；worktree absolute link：`{storage.get('worktree_link', '—')}` → `{storage.get('worktree_link_target', '—')}`。",
        f"- 原批准 ledger 保持 immutable effective `{ledger.get('effective_attempt_count', '—')}/{ledger.get('attempt_cap', '—')}`；用户明确授权的 supplemental recovery attempts `{ledger.get('supplemental_attempt_count', 0)}`；合计 `{ledger.get('total_original_plus_supplemental_attempt_count', '—')}`。",
        f"- Complete video view：`{analysis.get('complete_video_view', {}).get('path', '尚未物化')}`。",
        "",
        "## 实现与恢复机制",
        "",
        "- `initial_diversity_descriptor_mode` / `rollout_diversity_descriptor_mode` 独立控制 `absolute_eef` 与 `direction_normalized_eef`；legacy 默认均为 `absolute_eef`。",
        "- Direction 参数仍为 config-controlled weights、endpoint scale、path epsilon、distance epsilon；本次补跑未改变任何算法参数、task、seed、720-step budget 或正式矩阵。",
        "- `main.episode_start_index` 保留 global episode 编号，LiberoAdapter 按 global episode 映射原 task；`main.episode_seed_schedule` 保证 suffix 使用预注册 seed。",
        "- 每个 supplemental batch 使用独立 shared2 root、只读授权 manifest、追加式 supplemental ledger、dispatch/completion GPU snapshot；DINOv2 必需 cache 从 shared2 已审计副本离线 seed。",
        f"- Native abort diagnosis：`{runtime_diagnostics.get('status', '—')}`；root cause：{runtime_diagnostics.get('root_cause', '—')}；recovery：{runtime_diagnostics.get('recovery', '—')}。",
        "",
        "## 11-job validity 与任务结果",
        "",
        "| Job | Role | Exact videos/episodes | SR | Success tasks | Eligible | Invalid reason |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for job in jobs:
        invalid_note = "; ".join(job.get("validity_failures", [])[:4])
        if not invalid_note and not job.get("eligible"):
            invalid_note = str(job.get("failure_reason", "unknown"))
        lines.append(
            f"| `{job.get('label')}` | {job.get('role')} | {job.get('accepted_episode_count', 0)}/10 | "
            f"{sr(job)} | `{job.get('success_tasks', [])}` | `{job.get('eligible', False)}` | "
            f"{invalid_note if not job.get('eligible') else '—'} |"
        )

    labels = [job["label"] for job in jobs]
    lines.extend(
        [
            "",
            "## Task-level paired outcomes",
            "",
            "`S`=success，`F`=policy failure，`—`=无 eligible exact-seed outcome。",
            "",
            "| Task | " + " | ".join(f"`{label}`" for label in labels) + " |",
            "| ---: | " + " | ".join("---" for _ in labels) + " |",
        ]
    )
    for task in range(10):
        cells = []
        for job in jobs:
            outcome = job.get("task_outcomes", {}).get(str(task))
            cells.append("S" if outcome == "success" else "F" if outcome == "fail" else "—")
        lines.append(f"| {task} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Baseline、primary、parameter winner 与 adoption candidate",
            "",
            "| Role | Label | SR | Gained vs control | Lost vs control | Retained control successes |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for role, job in (
        ("control", control),
        ("rollout attribution", rollout),
        ("primary reference", primary),
        ("parameter winner", global_winner),
        ("adoption candidate", winner),
    ):
        if not job:
            continue
        gained, lost, retained = transition(job)
        lines.append(
            f"| {role} | `{job.get('label')}` | {sr(job)} | `{gained}` | `{lost}` | `{retained}` |"
        )

    lines.extend(
        [
            "",
            "## Trajectory、max-step、direction diversity 与 latency",
            "",
            "| Job | Length P95 | Max-step P95 | Length expansion med. | Max-step expansion med. | EEF direction med. | Endpoint spread med. | Chunk jump P95 | Select latency med. s |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for job in jobs:
        metric = job.get("metric_summary", {})
        lines.append(
            f"| `{job.get('label')}` | {_fmt(metric.get('selected_trajectory_length_p95'), 5)} | "
            f"{_fmt(metric.get('selected_max_step_p95'), 5)} | {_fmt(metric.get('trajectory_length_expansion_median'))} | "
            f"{_fmt(metric.get('max_step_expansion_median'))} | {_fmt(metric.get('eef_direction_diversity_median'))} | "
            f"{_fmt(metric.get('endpoint_direction_spread_median'))} | {_fmt(metric.get('chunk_boundary_jump_p95'), 5)} | "
            f"{_fmt(metric.get('selection_latency_median_s'), 3)} |"
        )

    mechanism = analysis.get("primary_reference", {}).get("mechanism_evidence", {})
    lines.extend(
        [
            "",
            "Primary W0/E050 相对 contemporaneous control 的 mechanism ratios：",
            "",
            f"- EEF direction retention：`{_fmt(mechanism.get('eef_direction_retention_ratio'), 4)}`（gate `>=0.90`）。",
            f"- Endpoint direction retention：`{_fmt(mechanism.get('endpoint_direction_retention_ratio'), 4)}`（gate `>=0.90`）。",
            f"- Trajectory-length P95 ratio：`{_fmt(mechanism.get('selected_trajectory_length_p95_ratio'), 4)}`（gate `<=0.85`）。",
            f"- Max-step P95 ratio：`{_fmt(mechanism.get('selected_max_step_p95_ratio'), 4)}`（gate `<=0.85`）。",
            "",
            "## Direction-RBF components（initial / rollout）",
            "",
            "| Job / scope | Direction mean | Shape mean | Endpoint mean | Composite mean | Weighted d/s/e | corr(composite,path ΔL) | corr(composite,direction) | Evidence n |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |",
        ]
    )
    for job in jobs:
        for scope in ("initial", "rollout"):
            evidence = job.get("mechanism", {}).get(scope)
            if not evidence:
                continue
            fractions = evidence.get("direction_rbf_weighted_component_fraction_by_iter") or {}
            path_corr = evidence.get("direction_rbf_distance_path_length_delta_correlation_by_iter") or {}
            direction_corr = evidence.get("direction_rbf_distance_direction_correlation_by_iter") or {}
            lines.append(
                f"| `{job.get('label')}` / {scope} | {_fmt(evidence.get('direction_rbf_pairwise_direction_mean_by_iter'))} | "
                f"{_fmt(evidence.get('direction_rbf_pairwise_shape_mean_by_iter'))} | {_fmt(evidence.get('direction_rbf_pairwise_endpoint_mean_by_iter'))} | "
                f"{_fmt(evidence.get('direction_rbf_pairwise_composite_mean_by_iter'))} | "
                f"{_fmt(fractions.get('direction'), 3)}/{_fmt(fractions.get('shape'), 3)}/{_fmt(fractions.get('endpoint'), 3)} | "
                f"{_fmt(path_corr.get('value'), 3)} (n={path_corr.get('valid_pair_count', '—')}) | "
                f"{_fmt(direction_corr.get('value'), 3)} (n={direction_corr.get('valid_pair_count', '—')}) | "
                f"{evidence.get('evidence_record_count', '—')} |"
            )

    lines.extend(
        [
            "",
            "## Weight、endpoint scale 主效应与交互",
            "",
            f"Estimable：`{main_effects.get('estimable', False)}`；{main_effects.get('reason', '')}。",
            "",
            "完整 3×3 outcome grid（SR；`*` 表 eligible）：",
            "",
            "| Weight | E025 | E050 | E100 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for weight in ("w0", "w1", "w2"):
        cells = []
        for endpoint in ("e025", "e050", "e100"):
            job = next(
                (row for row in jobs if row.get("weight_profile") == weight and row.get("endpoint_profile") == endpoint),
                {},
            )
            cells.append(f"{sr(job)}{'*' if job.get('eligible') else ''}")
        lines.append(f"| {weight.upper()} | " + " | ".join(cells) + " |")
    if main_effects.get("estimable"):
        lines.extend(
            [
                "",
                "Main-effect cell means：",
                "",
                "| Factor | Level | Mean success | Mean length P95 | Mean max-step P95 | Mean EEF direction | Mean endpoint spread |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for factor, mapping in (
            ("weight", main_effects.get("by_weight", {})),
            ("endpoint", main_effects.get("by_endpoint", {})),
        ):
            for level, values in mapping.items():
                lines.append(
                    f"| {factor} | {level.upper()} | {_fmt(values.get('success_count'), 3)} | "
                    f"{_fmt(values.get('selected_trajectory_length_p95'), 5)} | {_fmt(values.get('selected_max_step_p95'), 5)} | "
                    f"{_fmt(values.get('eef_direction_diversity_median'))} | {_fmt(values.get('endpoint_direction_spread_median'))} |"
                )
        lines.extend(
            [
                "",
                "Success-count interaction residual `cell - W mean - E mean + grand mean`：",
                "",
                "| Weight | E025 | E050 | E100 |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        interactions = main_effects.get("interaction_residuals", {})
        for weight in ("w0", "w1", "w2"):
            values = [
                _fmt(interactions.get(weight, {}).get(endpoint, {}).get("success_count"), 3)
                for endpoint in ("e025", "e050", "e100")
            ]
            lines.append(f"| {weight.upper()} | " + " | ".join(values) + " |")

    lines.extend(
        [
            "",
            "## Safety、失败 attempt 与 qualitative provenance",
            "",
            f"- Safety gate：`{gates.get('safety', '—')}`；winner qpos/execution errors `{winner.get('execution_qpos_error_episodes', '—')}`，collision/push/drop/wrong-object composite `{winner.get('collision_push_drop_wrong_object', '—')}`；control composite `{control.get('collision_push_drop_wrong_object', '—')}`。",
            f"- Classification summary：`{analysis.get('classification_summary', {})}`；详情 `{analysis.get('classification_path', '—')}`。",
            f"- Final invalid/incomplete jobs：`{[job.get('label') for job in jobs if not job.get('eligible')]}`。",
            f"- Rejected historical/recovery attempts：`{sum(len(job.get('rejected_attempt_rows', [])) for job in jobs)}`；它们保留原始 BF16、native abort、wrong-seed、SSL/cache 或 interruption provenance，不进入 selected outcome。",
            "",
            "## Credential、GPU、Git 与进程审计",
            "",
            f"- Shared2 credential scan：`{'PASS' if analysis.get('credential_audit', {}).get('passed') else 'FAIL'}`；finding paths `{analysis.get('credential_audit', {}).get('finding_paths', [])}`。",
            f"- GPU reference peak `{analysis.get('gpu_admission', {}).get('reference_peak_vram_mib', '—')} MiB`；required free `{analysis.get('gpu_admission', {}).get('required_free_vram_mib', '—')} MiB`；runtime roles `{analysis.get('gpu_admission', {}).get('formal_gpu_runtime_roles_from_runner_logs', {})}`。",
            f"- Delivery audit：`{analysis.get('delivery_audit', {})}`。",
            "- Decision manifest 保存 profiles、selected attempt provenance、task outcomes、gates、metrics/mechanism、checksums、supplemental ledger 和 complete-video view，并以 canonical checksum + `0444` 冻结。",
            "",
            "## 风险与下一步",
            "",
            "- 每 cell 仅 10 个固定 tasks；结果是工程配对证据，不代表统计显著性或跨任务泛化。",
            "- 早期失败 attempts 仍揭示 native simulator、外网 cache 与长时 supervisor 风险；生产运行应继续使用离线 cache、独立 batch 与 exact-seed resume。",
            "- Gate 结论不授权改变已批准矩阵、参数或追加新 sweep。",
        ]
    )
    return "\n".join(lines) + "\n"


def _manifest_payload(analysis: dict[str, Any], report_path: Path) -> dict[str, Any]:
    return {
        "schema": "p2-direction-rbf-decision-manifest-v2",
        "created_at": _now(),
        "design_path": analysis["design_path"],
        "report_path": str(report_path),
        "profiles": analysis["profiles"],
        "matrix_completeness": [
            {
                "label": job["label"],
                "role": job["role"],
                "weight_profile": job.get("weight_profile"),
                "endpoint_profile": job.get("endpoint_profile"),
                "accepted_episode_count": job["accepted_episode_count"],
                "eligible": job["eligible"],
                "success_count": job["success_count"],
                "success_tasks": job["success_tasks"],
                "failure_reason": job["failure_reason"],
                "config_fingerprint": job["config_fingerprint"],
                "code_state_sha256": job["code_state_sha256"],
                "git_revision": job["git_revision"],
                "selected_execution_contexts": job.get(
                    "selected_execution_contexts", []
                ),
                "checksums": job["checksums"],
            }
            for job in analysis["jobs"]
        ],
        "task_level_results": {job["label"]: job["task_outcomes"] for job in analysis["jobs"]},
        "job_metrics_and_mechanism": {
            job["label"]: {
                "metric_summary": job["metric_summary"],
                "mechanism": job["mechanism"],
                "execution_qpos_error_episodes": job["execution_qpos_error_episodes"],
                "collision_push_drop_wrong_object": job["collision_push_drop_wrong_object"],
                "nonfinite_count": job["nonfinite_count"],
                "action_mask_violation_count": job["action_mask_violation_count"],
                "fallback_count": job["fallback_count"],
            }
            for job in analysis["jobs"]
        },
        "gates": analysis["gates"],
        "ranking": analysis["ranking"],
        "primary_reference": analysis["primary_reference"],
        "main_effects_and_interaction": analysis["main_effects"],
        "recommended_for_adoption": analysis["ranking"]["recommended_for_adoption"],
        "no_adoption": analysis["no_adoption"],
        "ledger": analysis["ledger"],
        "supplemental_recovery": {
            "authorization_id": runner.SUPPLEMENTAL_AUTHORIZATION_ID,
            "attempt_count": analysis["ledger"].get("supplemental_attempt_count", 0),
            "complete_video_view": analysis.get("complete_video_view"),
            "selected_attempts": {
                job["label"]: job.get("selected_attempts", {})
                for job in analysis["jobs"]
            },
        },
        "storage": analysis["storage"],
        "credential_audit": analysis["credential_audit"],
        "preflight": analysis["preflight"],
        "gpu_admission": analysis["gpu_admission"],
        "classification_path": analysis["classification_path"],
        "delivery_audit": analysis["delivery_audit"],
        "runtime_diagnostics": analysis.get("runtime_diagnostics", {}),
    }


def materialize_complete_video_views(
    analysis: dict[str, Any],
    destination: Path,
    *,
    ffprobe_fn=_ffprobe_readable,
) -> dict[str, Any]:
    """Create one hard-linked, auditable 10-video directory per formal profile."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    records: list[dict[str, Any]] = []
    jobs = analysis.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("analysis contains no jobs")
    for job in jobs:
        label = str(job.get("label", ""))
        if not label or Path(label).name != label:
            raise ValueError(f"unsafe job label: {label!r}")
        selected = job.get("selected_attempts")
        if job.get("accepted_episode_count") != 10 or not isinstance(selected, dict):
            raise ValueError(f"{label} does not have 10 selected attempts")
        if {int(value) for value in selected} != set(range(10)):
            raise ValueError(f"{label} selected episode ids are incomplete")
        for episode in range(10):
            row = selected[str(episode)]
            source = Path(str(row.get("video", "")))
            if not source.is_file() or row.get("video_readable") is not True or not ffprobe_fn(source):
                raise ValueError(f"{label} episode {episode} video is not readable")
            episode_dir = destination / label / f"episode_{episode + 1}"
            episode_dir.mkdir(parents=True, exist_ok=False)
            linked = episode_dir / source.name
            os.link(source, linked)
            if source.stat().st_ino != linked.stat().st_ino:
                raise RuntimeError(f"{label} episode {episode} was not hard-linked")
            records.append(
                {
                    "label": label,
                    "episode": episode,
                    "task_id": episode,
                    "episode_seed": EPISODE_SEEDS[episode],
                    "source": str(source),
                    "view": str(linked),
                    "sha256": _sha256_file(linked),
                    "size_bytes": linked.stat().st_size,
                    "ffprobe_readable": True,
                }
            )
    payload = {
        "schema": "p2-direction-rbf-complete-video-view-v1",
        "created_at": _now(),
        "analysis_generated_at": analysis.get("generated_at"),
        "job_count": len(jobs),
        "video_count": len(records),
        "link_type": "hardlink",
        "records": records,
    }
    manifest_path = destination / "video_view_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    manifest_path.chmod(0o444)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--analysis-path", type=Path, default=ANALYSIS_PATH)
    audit.add_argument("--classification-path", type=Path, default=CLASSIFICATION_PATH)
    audit.add_argument("--report-path", type=Path, default=REPORT_PATH)
    audit.add_argument("--manifest-path", type=Path, default=DECISION_PATH)
    audit.add_argument("--freeze-manifest", action="store_true")
    audit.add_argument("--materialize-video-view", type=Path, default=None)
    verify = sub.add_parser("verify-manifest")
    verify.add_argument("path", type=Path, nargs="?", default=DECISION_PATH)
    args = parser.parse_args()
    if args.command == "verify-manifest":
        print(json.dumps(verify_decision_manifest(args.path), indent=2, sort_keys=True))
        return 0
    result = analyze()
    if args.materialize_video_view is not None:
        video_view = materialize_complete_video_views(
            result,
            args.materialize_video_view,
        )
        result["complete_video_view"] = {
            "path": str(args.materialize_video_view),
            "job_count": video_view["job_count"],
            "video_count": video_view["video_count"],
            "manifest": str(args.materialize_video_view / "video_view_manifest.json"),
            "manifest_sha256": _sha256_file(
                args.materialize_video_view / "video_view_manifest.json"
            ),
        }
    classification = _classification_payload(result["jobs"])
    args.analysis_path.parent.mkdir(parents=True, exist_ok=True)
    args.analysis_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    args.classification_path.parent.mkdir(parents=True, exist_ok=True)
    args.classification_path.write_text(json.dumps(classification, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(render_report(result), encoding="utf-8")
    if args.freeze_manifest:
        frozen = freeze_decision_manifest(_manifest_payload(result, args.report_path), args.manifest_path)
        verify_decision_manifest(args.manifest_path)
        print(json.dumps({"analysis": str(args.analysis_path), "classification": str(args.classification_path), "report": str(args.report_path), "manifest": str(args.manifest_path), "checksum": frozen["canonical_manifest_checksum"]}, indent=2))
    else:
        print(json.dumps({"analysis": str(args.analysis_path), "classification": str(args.classification_path), "report": str(args.report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
