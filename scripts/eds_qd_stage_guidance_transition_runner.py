#!/usr/bin/env python3
"""Frozen paired runner for the EDS-QD stage/guidance transition study."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = Path(__file__).resolve().parents[1]
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_qd_search_budget_sweep_runner as sweep
import eds_quality_diversity_runner as legacy
import rdt_eds_eval_runner as base


FORMAL_LEVEL = "eds_qd_stage_guidance_transition"
RETRY_LEVEL = "eds_qd_stage_guidance_transition_retry"
PREFLIGHT_LEVEL = "__disabled_no_episode_preflight__"
NAMESPACE = "stage_guidance_transition_20260810"
TARGET_BRANCH = "exp/eds-qd-stage-guidance-transition"
BASE_COMMIT = "beb8d3f073857f3762a179ce8af4a3c28244b75d"
ROOT_OUTPUT_LINK = WORKTREE_ROOT / "outputs"
EXPERIMENT_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs"
) / NAMESPACE
OUTPUT_TARGET = EXPERIMENT_ROOT / "output_store"
OUTPUT_LINK = ROOT_OUTPUT_LINK / "output_store_link"
ALLOWED_STORAGE_PREFIX = Path("/mnt/data/shared2/zhuoli/vla-pilot-plus-plus")
MIN_FREE_BYTES = 50 * 1024**3
DESIGN_PATH = (
    WORKTREE_ROOT
    / "docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md"
)
RUN_MANIFEST_PATH = EXPERIMENT_ROOT / "manifests/run_manifest.json"
ATTEMPT_LEDGER_PATH = EXPERIMENT_ROOT / "manifests/episode_attempt_ledger.jsonl"
DIMENSION_PROBE_PATH = EXPERIMENT_ROOT / "analysis/dimension_probe.json"
TEST_EVIDENCE_PATH = EXPERIMENT_ROOT / "analysis/test_evidence.json"
RUNTIME_CACHE_DIR = sweep.RUNTIME_CACHE_DIR
RUNTIME_CACHE_MANIFEST_PATH = sweep.RUNTIME_CACHE_MANIFEST_PATH
GPU_REFERENCE_PATH = legacy.GPU_REFERENCE_PATH

ROUND_SEEDS = {
    0: [44, 235, 43, 546, 6, 621, 197, 87, 151, 548],
    1: [1044, 1235, 1043, 1546, 1006, 1621, 1197, 1087, 1151, 1548],
}
ROUND_ROOT_SEEDS = {0: 0, 1: 1}
ALLOWED_GPU_INDICES = tuple(range(8))
MAX_CONCURRENCY = 4
FORMAL_JOB_COUNT = 4
FORMAL_EPISODE_COUNT = 40
RETRY_ATTEMPT_LIMIT = 4
RECOVERY_ATTEMPT_LIMIT = RETRY_ATTEMPT_LIMIT
ATTEMPT_CAP = 44
EXPECTED_EVALUATIONS_PER_COMPLETE_CHUNK = 1008
REFERENCE_PEAK_VRAM_MIB = (
    sweep.HISTORICAL_REFERENCE_PEAK_VRAM_MIB * 48 / sweep.BASELINE_POPULATION_SIZE
)

FSM_THRESHOLDS = {
    "target_keypoint_index": 0,
    "destination_keypoint_index": 1,
    "near_threshold_m": 0.08,
    "follow_error_max_m": 0.02,
    "lift_confirm_m": 0.02,
    "grasp_confirm_steps": 4,
    "drop_relative_drift_m": 0.05,
    "drop_fall_m": 0.02,
    "drop_confirm_steps": 3,
    "min_state_dwell_steps": 2,
    "release_verify_timeout_steps": 8,
    "destination_region_radius_m": 0.08,
    "gripper_closed_aperture_max_m": 0.07,
    "gripper_open_aperture_min_m": 0.075,
}


def expected_evaluations(population_size: int, cem_iters: int) -> int:
    """Return the frozen QD candidate count for one complete action chunk."""
    return int(population_size) * (int(cem_iters) + 1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contains_credential(value: object) -> bool:
    return legacy._contains_credential(value)


def _profile_fingerprint(profile: dict[str, object]) -> str:
    excluded = {"label", "method", "job_id", "level", "formal_label"}
    payload = {key: value for key, value in profile.items() if key not in excluded}
    return _sha256_bytes(_canonical(payload).encode("utf-8"))


def formal_profiles() -> list[dict[str, object]]:
    base_profile = sweep._profile("uniform_expand20", 48, 20)
    profiles = []
    for round_id, suffix, transition_mode in (
        (0, "legacy", "legacy_vlm"),
        (0, "fsm_v1", "physical_fsm_v1"),
        (1, "legacy", "legacy_vlm"),
        (1, "fsm_v1", "physical_fsm_v1"),
    ):
        label = (
            "eds_qd_uniform_expand20_p48_k20_transition_"
            f"{suffix}_r{round_id}"
        )
        profile = {
            **base_profile,
            "method": label,
            "label": label,
            "role": "paired_stage_guidance_transition",
            "round": round_id,
            "transition_mode": transition_mode,
            "seed": ROUND_ROOT_SEEDS[round_id],
        }
        profile["profile_fingerprint"] = _profile_fingerprint(profile)
        profiles.append(profile)
    expected = [
        "eds_qd_uniform_expand20_p48_k20_transition_legacy_r0",
        "eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r0",
        "eds_qd_uniform_expand20_p48_k20_transition_legacy_r1",
        "eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r1",
    ]
    if [str(profile["label"]) for profile in profiles] != expected:
        raise AssertionError("formal labels changed from the frozen matrix")
    return profiles


def _stage_dir(level: object) -> str:
    if str(level) == FORMAL_LEVEL:
        return "formal"
    if str(level) == RETRY_LEVEL:
        return "retry"
    return sweep._stage_dir(level)


def _build_main_command(job, *args, **kwargs):
    with configured_base():
        command = sweep._BASE_BUILD_MAIN_COMMAND(job, *args, **kwargs)
    command.append(
        "main.episode_seed_schedule=" + legacy._hydra_value(job["episode_seeds"])
    )
    command.extend(
        [
            "main.eds_config.initial_diversity_descriptor_mode="
            + str(job["initial_diversity_descriptor_mode"]),
            "main.eds_config.rollout_diversity_descriptor_mode="
            + str(job["rollout_diversity_descriptor_mode"]),
            "main.eds_eval.max_visual_chunks_per_episode=2",
            "main.keypoint_detection_max_attempts=3",
        ]
    )
    command.extend(
        f"main.eds_config.{field}={legacy._hydra_value(job[field])}"
        for field in sweep.QD_CONFIG_FIELDS
    )
    command.append(f"main.stage_transition_mode={job['transition_mode']}")
    if job["transition_mode"] == "physical_fsm_v1":
        command.extend(
            f"main.physical_fsm.{key}={legacy._hydra_value(value)}"
            for key, value in FSM_THRESHOLDS.items()
        )
    if "episode_start_index" in job:
        command.append(f"+main.episode_start_index={int(job['episode_start_index'])}")
    if "episode_stop_index" in job:
        command.append(f"+main.episode_stop_index={int(job['episode_stop_index'])}")
    if job.get("level") == RETRY_LEVEL:
        formal_label = str(job["formal_label"])
        formal_job_id = str(job["formal_job_id"])
        command = [
            f"main.eds_eval.method_label={formal_label}"
            if token.startswith("main.eds_eval.method_label=")
            else f"main.eds_eval.job_id={formal_job_id}"
            if token.startswith("main.eds_eval.job_id=")
            else token
            for token in command
        ]
    assignments = {
        token.split("=", 1)[0].lstrip("+"): token.split("=", 1)[1]
        for token in command
        if "=" in token
    }
    expected = {
        "main.eds_config.population_size": "48",
        "main.eds_config.cem_iters": "20",
        "main.eds_config.num_elites": "16",
        "main.eds_config.use_cem": "false",
        "main.stage_transition_mode": str(job["transition_mode"]),
        "seed": str(job["seed"]),
    }
    for key, value in expected.items():
        if assignments.get(key) != value:
            raise RuntimeError(f"frozen command mismatch: {key}={value}")
    if _contains_credential(command):
        raise RuntimeError("formal command unexpectedly contains credential material")
    return command


def _bind_job(job: dict[str, object]) -> dict[str, object]:
    with configured_base():
        return base._bind_p2_execution_context(
            job,
            real_root=OUTPUT_TARGET,
            cached_functions_dir=str(RUNTIME_CACHE_DIR),
            offline_vlm=False,
            storage_enforced=True,
            git_revision=base._git_head_revision(),
            code_state_sha256=base._p2_code_state_sha256(),
        )


def build_jobs(level: str, episodes: int, **_kwargs) -> list[dict[str, object]]:
    if level != FORMAL_LEVEL or episodes != 10:
        raise ValueError("stage-guidance transition supports only its frozen 4-job matrix")
    jobs = []
    for profile in formal_profiles():
        round_id = int(profile["round"])
        job = {
            **profile,
            "job_id": f"{FORMAL_LEVEL}_libero_object_swap_{profile['label']}",
            "formal_label": profile["label"],
            "level": FORMAL_LEVEL,
            "suite": "libero_object_swap",
            "episodes": 10,
            "task_ids_filter": list(range(10)),
            "episode_seeds": list(ROUND_SEEDS[round_id]),
            "expected_evaluations_per_complete_chunk": (
                EXPECTED_EVALUATIONS_PER_COMPLETE_CHUNK
            ),
        }
        jobs.append(_bind_job(job))
    if len(jobs) != FORMAL_JOB_COUNT:
        raise AssertionError("formal matrix is not 4 jobs")
    return jobs


def initialize_storage() -> dict[str, object]:
    if not ROOT_OUTPUT_LINK.is_symlink() or not os.path.isabs(
        os.readlink(ROOT_OUTPUT_LINK)
    ):
        raise RuntimeError("worktree outputs must be the approved absolute symlink")
    if ROOT_OUTPUT_LINK.resolve(strict=True) != EXPERIMENT_ROOT.resolve(strict=True):
        raise RuntimeError("worktree outputs does not resolve to the approved namespace")
    OUTPUT_TARGET.mkdir(parents=True, exist_ok=True)
    if OUTPUT_LINK.exists() and not OUTPUT_LINK.is_symlink():
        raise RuntimeError("nested output link exists but is not a symlink")
    if not OUTPUT_LINK.exists():
        OUTPUT_LINK.symlink_to(OUTPUT_TARGET.absolute(), target_is_directory=True)
    return storage_preflight()


def storage_preflight() -> dict[str, object]:
    if not ROOT_OUTPUT_LINK.is_symlink() or not OUTPUT_LINK.is_symlink():
        raise RuntimeError("root and nested output paths must both be symlinks")
    namespace = ROOT_OUTPUT_LINK.resolve(strict=True)
    output_target = OUTPUT_LINK.resolve(strict=True)
    if namespace != EXPERIMENT_ROOT.resolve(strict=True):
        raise RuntimeError("approved namespace symlink changed")
    if output_target != OUTPUT_TARGET.resolve(strict=True):
        raise RuntimeError("output-store symlink changed")
    prefix = ALLOWED_STORAGE_PREFIX.resolve(strict=True)
    for path in (namespace, output_target):
        try:
            path.relative_to(prefix)
        except ValueError as exc:
            raise RuntimeError("storage path is outside approved shared2 prefix") from exc
    free = int(shutil.disk_usage(namespace).free)
    if free < MIN_FREE_BYTES:
        raise RuntimeError("shared2 has less than the required 50 GiB free")
    return {
        "passed": True,
        "namespace_realpath": str(namespace),
        "outputs_target": str(output_target),
        "free_bytes": free,
        "minimum_free_bytes": MIN_FREE_BYTES,
        "root_output_link": str(ROOT_OUTPUT_LINK),
        "nested_output_link": str(OUTPUT_LINK),
    }


def load_gpu_reference() -> dict[str, object]:
    historical = legacy.load_gpu_reference()
    return {
        **historical,
        "reference_peak_vram_mib": REFERENCE_PEAK_VRAM_MIB,
        "scaling": "historical_p16_peak_scaled_linearly_to_p48",
        "historical_reference_path": str(GPU_REFERENCE_PATH),
    }


def admit_gpus(
    *,
    reference_peak_vram_mib: float,
    snapshot_fn: Callable[[], list[dict[str, object]]] = legacy.gpu_snapshot,
    wait_fn: Callable[[float], None] = time.sleep,
    wait_seconds: float = 2.0,
) -> dict[str, object]:
    payload = legacy.admit_gpus(
        reference_peak_vram_mib=reference_peak_vram_mib,
        snapshot_fn=snapshot_fn,
        wait_fn=wait_fn,
        wait_seconds=wait_seconds,
        pinned_gpu_index=None,
        allow_external_compute=False,
    )
    payload["allowed_gpu_indices"] = list(ALLOWED_GPU_INDICES)
    payload["max_concurrency"] = min(
        MAX_CONCURRENCY, len(payload["eligible_gpu_indices"])
    )
    payload["strict_idle_required"] = True
    payload["external_compute_colocation_authorized"] = False
    return payload


def _selected_gpus(admission: dict[str, object], requested: str) -> list[str]:
    eligible = {int(value) for value in admission["eligible_gpu_indices"]}
    if requested != "auto":
        selected = [item.strip() for item in requested.split(",") if item.strip()]
        if not selected or len(selected) != len(set(selected)):
            raise RuntimeError("requested GPUs must be a nonempty unique list")
        if len(selected) > MAX_CONCURRENCY:
            raise RuntimeError("at most four workers are allowed")
        if not {int(value) for value in selected} <= eligible:
            raise RuntimeError("one or more requested GPUs failed strict admission")
        return selected
    latest = {
        int(item["index"]): item
        for item in admission.get("snapshots", [[], []])[-1]
        if int(item["index"]) in eligible
    }
    ranked = sorted(
        eligible,
        key=lambda index: (
            -float(latest.get(index, {}).get("memory_free_mib", -math.inf)),
            index,
        ),
    )
    return [str(index) for index in ranked[:MAX_CONCURRENCY]]


def _gpu_probe(gpu: str) -> tuple[str, str]:
    try:
        index = int(gpu)
    except ValueError:
        return "error", "GPU index is not an integer"
    if index not in ALLOWED_GPU_INDICES:
        return "error", "GPU is outside approved range 0..7"
    reference = load_gpu_reference()
    device = next(
        (row for row in legacy.gpu_snapshot() if int(row["index"]) == index),
        None,
    )
    required = max(
        float(reference["reference_peak_vram_mib"]) * 1.25,
        float(reference["reference_peak_vram_mib"]) + 4096.0,
    )
    reasons = legacy._gpu_snapshot_failure(
        device,
        index=index,
        required_free=required,
        allow_external_compute=False,
    )
    return ("busy", "; ".join(reasons)) if reasons else ("idle", "strictly idle")


def _write_gpu_admission(phase: str, payload: dict[str, object]) -> Path:
    path = EXPERIMENT_ROOT / "manifests" / f"gpu_{phase}_{time.time_ns()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def configure_base() -> None:
    base.P2_OUTPUT_ROOT = OUTPUT_LINK
    base.P2_STATUS_ROOT = OUTPUT_LINK
    base.P2_EXPECTED_OUTPUT_TARGET = OUTPUT_TARGET
    base.P2_ALLOWED_OUTPUT_PREFIX = ALLOWED_STORAGE_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | {FORMAL_LEVEL, RETRY_LEVEL}
    base.P2_ALLOWED_GPUS = {str(index) for index in ALLOWED_GPU_INDICES}
    base.P2_REQUIRED_MOUNT = Path("/mnt/data/shared2")
    base.P2_TORCH_HUB_SEED = (
        Path("/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf")
        / "runtime_cache/formal/p2_stage_on_dirnorm_rbf_global_w0_e025/xdg/torch/hub"
    )
    base.build_jobs = build_jobs
    base.build_main_command = _build_main_command
    base._p2_stage_dir = _stage_dir
    base._p2_gpu_probe = _gpu_probe


@contextmanager
def configured_base():
    names = (
        "P2_OUTPUT_ROOT",
        "P2_STATUS_ROOT",
        "P2_EXPECTED_OUTPUT_TARGET",
        "P2_ALLOWED_OUTPUT_PREFIX",
        "P2_MIN_FREE_BYTES",
        "P2_LEVELS",
        "P2_ALLOWED_GPUS",
        "P2_REQUIRED_MOUNT",
        "P2_TORCH_HUB_SEED",
        "build_jobs",
        "build_main_command",
        "_p2_stage_dir",
        "_p2_gpu_probe",
    )
    saved = {name: getattr(base, name) for name in names}
    configure_base()
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(base, name, value)


def read_attempt_ledger(path: Path = ATTEMPT_LEDGER_PATH) -> list[dict[str, object]]:
    return legacy.read_attempt_ledger(path)


def attempt_ledger_state(path: Path = ATTEMPT_LEDGER_PATH) -> dict[str, object]:
    return legacy.attempt_ledger_state(path)


def append_ledger_event(path: Path, event: dict[str, object]) -> dict[str, object]:
    return legacy.append_ledger_event(path, event)


def append_attempt_records(
    path: Path, records: list[dict[str, object]]
) -> list[dict[str, object]]:
    original_cap = legacy.ATTEMPT_CAP
    legacy.ATTEMPT_CAP = ATTEMPT_CAP
    try:
        return legacy.append_attempt_records(path, records)
    finally:
        legacy.ATTEMPT_CAP = original_cap


def _attempt_records_for_jobs(
    jobs: list[dict[str, object]], phase: str
) -> list[dict[str, object]]:
    return legacy._attempt_records_for_jobs(jobs, phase)


def select_retry_cells(cells: list[tuple[str, int]]) -> list[dict[str, object]]:
    if not cells or len(cells) != len(set(cells)):
        raise ValueError("retry cells must be a nonempty unique list")
    if len(cells) > RETRY_ATTEMPT_LIMIT:
        raise ValueError("at most four retry cells are allowed")
    jobs = {str(job["label"]): job for job in build_jobs(FORMAL_LEVEL, 10)}
    selected = []
    for label, task_id in cells:
        if label not in jobs or not 0 <= int(task_id) <= 9:
            raise ValueError("retry requires a registered formal label/task cell")
        job = jobs[label]
        task_id = int(task_id)
        selected.append(
            {
                "formal_label": label,
                "task_id": task_id,
                "episode_seed": int(job["episode_seeds"][task_id]),
                "round": int(job["round"]),
                "transition_mode": str(job["transition_mode"]),
                "profile_fingerprint": str(job["profile_fingerprint"]),
                "config_fingerprint": str(job["config_fingerprint"]),
                "code_state_sha256": str(
                    job["execution_record"]["code_state_sha256"]
                ),
            }
        )
    return selected


def _retry_jobs(
    selected: list[dict[str, object]], *, first_attempt_id: int
) -> list[dict[str, object]]:
    formal_jobs = {
        str(job["label"]): job for job in build_jobs(FORMAL_LEVEL, 10)
    }
    retry_jobs = []
    for offset, cell in enumerate(selected):
        formal = formal_jobs[str(cell["formal_label"])]
        task_id = int(cell["task_id"])
        label = (
            f"{cell['formal_label']}__retry_task{task_id}_"
            f"attempt{first_attempt_id + offset}"
        )
        job = {
            **formal,
            "label": label,
            "method": label,
            "job_id": f"{RETRY_LEVEL}_{label}",
            "formal_job_id": formal["job_id"],
            "level": RETRY_LEVEL,
            "episodes": 10,
            "episode_start_index": task_id,
            "episode_stop_index": task_id + 1,
            "retry_task_id": task_id,
            "retry_of_formal_label": cell["formal_label"],
        }
        job.pop("config_fingerprint", None)
        job.pop("execution_record", None)
        retry_jobs.append(_bind_job(job))
    return retry_jobs


def _jsonl_episode_id(record: dict[str, object]) -> int | None:
    for key in ("episode", "episode_id"):
        value = record.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return int(value)
    return None


def _merge_retry_jsonl(
    *, formal_path: Path, retry_path: Path, episode: int, archive_root: Path
) -> None:
    formal_rows = []
    if formal_path.is_file():
        formal_rows = [
            json.loads(line)
            for line in formal_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        shutil.copy2(formal_path, archive_root / formal_path.name)
    retry_rows = [
        json.loads(line)
        for line in retry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected_rows = [
        row for row in retry_rows if _jsonl_episode_id(row) == episode
    ]
    if not selected_rows:
        raise RuntimeError(
            f"retry JSONL has no episode {episode}: {retry_path}"
        )
    merged = [row for row in formal_rows if _jsonl_episode_id(row) != episode]
    merged.extend(selected_rows)
    merged.sort(
        key=lambda row: (
            _jsonl_episode_id(row) if _jsonl_episode_id(row) is not None else -1,
            int(row.get("global_step", -1))
            if isinstance(row.get("global_step"), int)
            else -1,
        )
    )
    temporary = formal_path.with_name(f".{formal_path.name}.{time.time_ns()}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        for row in merged:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, formal_path)


def _rewrite_formal_results(output_dir: Path) -> None:
    successes = 0
    for episode in range(10):
        videos = list((output_dir / f"episode_{episode + 1}").glob("*.mp4"))
        if len(videos) != 1:
            raise RuntimeError(
                f"cannot merge retry: episode {episode} video count is {len(videos)}"
            )
        if "_success_" in videos[0].name:
            successes += 1
        elif "_fail_" not in videos[0].name:
            raise RuntimeError("cannot merge retry: video outcome suffix missing")
    results = output_dir / "results.txt"
    temporary = results.with_name(f".{results.name}.{time.time_ns()}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write("Backend: libero\n")
        handle.write(f"Success count: {successes}/10\n")
        handle.write(f"Success rate: {100.0 * successes / 10:.2f}%\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, results)


def merge_retry_cell(
    *, retry_job: dict[str, object], formal_job: dict[str, object]
) -> dict[str, object]:
    """Merge one independently validated retry cell into its canonical job."""
    with configured_base():
        retry_validity = base._p2_job_validity(
            retry_job, allow_identical_overrides=True
        )
        retry_dir = base._output_dir(retry_job)
        formal_dir = base._output_dir(formal_job)
    if retry_validity.get("valid") is not True:
        raise RuntimeError(
            "retry cell is invalid and cannot replace canonical evidence: "
            + str(retry_validity.get("failure_reason"))
        )
    episode = int(retry_job["retry_task_id"])
    archive_root = (
        OUTPUT_TARGET
        / "stale/retry_cell_merges"
        / f"attempt_{retry_job['label']}"
    )
    if archive_root.exists():
        raise FileExistsError(archive_root)
    archive_root.mkdir(parents=True)
    formal_episode = formal_dir / f"episode_{episode + 1}"
    retry_episode = retry_dir / f"episode_{episode + 1}"
    if formal_episode.exists():
        shutil.move(str(formal_episode), str(archive_root / formal_episode.name))
    shutil.copytree(retry_episode, formal_episode)

    formal_qualitative = formal_dir / "eds_eval/qualitative" / f"episode_{episode:03d}"
    retry_qualitative = retry_dir / "eds_eval/qualitative" / f"episode_{episode:03d}"
    if formal_qualitative.exists():
        shutil.move(
            str(formal_qualitative),
            str(archive_root / f"qualitative_episode_{episode:03d}"),
        )
    formal_qualitative.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(retry_qualitative, formal_qualitative)

    formal_eval = formal_dir / "eds_eval"
    retry_eval = retry_dir / "eds_eval"
    for retry_path in sorted(retry_eval.glob("*.jsonl")):
        _merge_retry_jsonl(
            formal_path=formal_eval / retry_path.name,
            retry_path=retry_path,
            episode=episode,
            archive_root=archive_root,
        )
    results = formal_dir / "results.txt"
    if results.is_file():
        shutil.copy2(results, archive_root / "results.txt")
    failure_reason = formal_dir / "failure_reason.json"
    if failure_reason.is_file():
        shutil.move(str(failure_reason), str(archive_root / failure_reason.name))
    _rewrite_formal_results(formal_dir)
    payload = {
        "schema": "eds-qd-stage-guidance-retry-merge-v1",
        "created_at": _now(),
        "formal_label": formal_job["label"],
        "retry_label": retry_job["label"],
        "episode": episode,
        "task_id": int(formal_job["task_ids_filter"][episode]),
        "episode_seed": int(formal_job["episode_seeds"][episode]),
        "retry_validity": retry_validity,
        "archive_root": str(archive_root),
        "retry_output": str(retry_dir),
        "canonical_output": str(formal_dir),
    }
    manifest_path = archive_root / "merge_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path.chmod(0o444)
    return payload


def _panda_gripper_xml_path() -> Path:
    candidates = sorted(
        Path("/home/hynx/miniconda3/envs/vla-pilot/lib").rglob(
            "panda_gripper.xml"
        )
    )
    candidates = [
        path
        for path in candidates
        if "robosuite/models/assets/grippers" in path.as_posix()
    ]
    if len(candidates) != 1:
        raise RuntimeError("cannot resolve the frozen vla-pilot Panda gripper XML")
    return candidates[0]


def run_dimension_probe() -> dict[str, object]:
    if DIMENSION_PROBE_PATH.exists() or DIMENSION_PROBE_PATH.is_symlink():
        raise FileExistsError(DIMENSION_PROBE_PATH)
    xml_path = _panda_gripper_xml_path()
    root = ET.parse(xml_path).getroot()
    ranges = {}
    for name in ("finger_joint1", "finger_joint2"):
        joint = root.find(f".//joint[@name='{name}']")
        if joint is None or not joint.get("range"):
            raise RuntimeError(f"Panda gripper joint range missing: {name}")
        ranges[name] = [float(value) for value in joint.get("range").split()]
    maximum_aperture = ranges["finger_joint1"][1] - ranges["finger_joint2"][0]
    metadata_path = RUNTIME_CACHE_DIR / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    keypoint_map = {
        int(key): str(value)
        for key, value in metadata["key_points_objects_map"].items()
    }
    bddl_dir = (
        WORKTREE_ROOT
        / "third_party/libero_pro/libero/libero/bddl_files/libero_object_swap"
    )
    bddl_files = sorted(bddl_dir.glob("*.bddl"))
    bddl_checks = []
    for path in bddl_files:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"\(:obj_of_interest\s+([^\)]+)\)", text, re.DOTALL)
        objects = match.group(1).split() if match else []
        bddl_checks.append(
            {
                "file": path.name,
                "object_of_interest": objects,
                "has_basket_destination": len(objects) == 2
                and objects[1].startswith("basket_"),
                "goal_is_in_destination": "(In " in text
                and "basket_1_contain_region" in text,
            }
        )
    checks = {
        "ten_object_swap_tasks": len(bddl_checks) == 10,
        "all_tasks_have_fixed_target_and_basket": all(
            row["has_basket_destination"] and row["goal_is_in_destination"]
            for row in bddl_checks
        ),
        "cached_keypoint_zero_is_target": 0 in keypoint_map
        and "basket" not in keypoint_map[0],
        "cached_keypoint_one_is_destination": 1 in keypoint_map
        and "basket" in keypoint_map[1],
        "panda_maximum_aperture_is_0_08_m": math.isclose(
            maximum_aperture, 0.08, abs_tol=1e-9
        ),
        "closed_open_thresholds_fit_static_range": (
            0
            < FSM_THRESHOLDS["gripper_closed_aperture_max_m"]
            < FSM_THRESHOLDS["gripper_open_aperture_min_m"]
            < maximum_aperture
        ),
        "grasp_threshold_is_stricter_than_drop": (
            FSM_THRESHOLDS["follow_error_max_m"]
            < FSM_THRESHOLDS["drop_relative_drift_m"]
        ),
    }
    payload = {
        "schema": "eds-qd-stage-guidance-dimension-probe-v1",
        "created_at": _now(),
        "passed": all(checks.values()),
        "checks": checks,
        "formal_episodes_consumed": 0,
        "panda_gripper": {
            "xml_path": str(xml_path),
            "xml_sha256": _sha256_file(xml_path),
            "joint_ranges_m": ranges,
            "maximum_aperture_m": maximum_aperture,
        },
        "keypoint_resolver": {
            "source": "cached fixed task/keypoint metadata",
            "metadata_path": str(metadata_path),
            "metadata_sha256": _sha256_file(metadata_path),
            "target_keypoint_index": 0,
            "destination_keypoint_index": 1,
            "target_object": keypoint_map.get(0),
            "destination_object": keypoint_map.get(1),
        },
        "bddl_task_checks": bddl_checks,
        "frozen_thresholds": dict(FSM_THRESHOLDS),
    }
    if not payload["passed"]:
        raise RuntimeError("dimension probe failed")
    if _contains_credential(payload):
        raise RuntimeError("dimension probe contains credential material")
    DIMENSION_PROBE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DIMENSION_PROBE_PATH.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    DIMENSION_PROBE_PATH.chmod(0o444)
    return payload


def run_test_gate() -> dict[str, object]:
    """Run and freeze all preregistered test gates before formal dispatch."""
    if TEST_EVIDENCE_PATH.exists() or TEST_EVIDENCE_PATH.is_symlink():
        raise FileExistsError(TEST_EVIDENCE_PATH)
    commands = [
        [sys.executable, "-m", "pytest", "-q", "tests"],
        [
            sys.executable,
            "-m",
            "py_compile",
            "main.py",
            "core/keypoint_tracker.py",
            "core/stage_guidance_fsm.py",
            "scripts/rdt_eds_eval_runner.py",
            "scripts/eds_qd_stage_guidance_transition_runner.py",
            "scripts/eds_qd_stage_guidance_transition_audit.py",
        ],
        ["git", "diff", "--check", "HEAD"],
    ]
    results = []
    for command in commands:
        started = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=WORKTREE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        result = {
            "command": command,
            "returncode": int(completed.returncode),
            "wall_clock_s": float(time.monotonic() - started),
            "stdout_tail": completed.stdout[-12000:],
            "stderr_tail": completed.stderr[-12000:],
        }
        if _contains_credential(result):
            raise RuntimeError("test evidence unexpectedly contains credential material")
        results.append(result)
        if completed.returncode != 0:
            break
    payload = {
        "schema": "eds-qd-stage-guidance-transition-test-evidence-v1",
        "created_at": _now(),
        "passed": len(results) == len(commands)
        and all(item["returncode"] == 0 for item in results),
        "commands": results,
        "formal_episodes_consumed": 0,
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True
        ).strip(),
    }
    TEST_EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TEST_EVIDENCE_PATH.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    TEST_EVIDENCE_PATH.chmod(0o444)
    if not payload["passed"]:
        raise RuntimeError("test gate failed; formal dispatch remains forbidden")
    return payload


def current_provenance() -> dict[str, object]:
    status = subprocess.check_output(
        ["git", "status", "--short"], cwd=WORKTREE_ROOT, text=True
    ).splitlines()
    if status:
        raise RuntimeError("worktree must be committed before provenance freeze")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    if branch != TARGET_BRANCH:
        raise RuntimeError(f"unexpected branch: {branch}")
    return {
        "branch": branch,
        "worktree_realpath": str(WORKTREE_ROOT.resolve(strict=True)),
        "code_commit": head,
        "code_state_sha256": base._p2_code_state_sha256(root=WORKTREE_ROOT),
        "base_commit": BASE_COMMIT,
        "source_branch": "exp/eds-quality-diversity",
        "source_status_at_creation": "clean",
    }


def freeze_run_manifest(
    *,
    provenance: dict[str, object],
    storage: dict[str, object],
    gpu_reference: dict[str, object],
    test_evidence: dict[str, object],
) -> dict[str, object]:
    if RUN_MANIFEST_PATH.exists() or RUN_MANIFEST_PATH.is_symlink():
        raise FileExistsError(RUN_MANIFEST_PATH)
    if not DIMENSION_PROBE_PATH.is_file():
        raise RuntimeError("dimension probe is missing")
    probe = json.loads(DIMENSION_PROBE_PATH.read_text(encoding="utf-8"))
    if probe.get("passed") is not True or test_evidence.get("passed") is not True:
        raise RuntimeError("tests and dimension probe must pass before manifest freeze")
    profiles = formal_profiles()
    payload = {
        "schema": "eds-qd-stage-guidance-transition-run-manifest-v1",
        "created_at": _now(),
        "design_path": str(DESIGN_PATH),
        "design_sha256": _sha256_file(DESIGN_PATH),
        "design_status": "Approved for execution",
        "provenance": provenance,
        "storage": storage,
        "gpu_reference": gpu_reference,
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "task_ids": list(range(10)),
        "round_seeds": {
            "0": list(ROUND_SEEDS[0]),
            "1": list(ROUND_SEEDS[1]),
        },
        "round_root_seeds": {
            "0": ROUND_ROOT_SEEDS[0],
            "1": ROUND_ROOT_SEEDS[1],
        },
        "max_episode_steps": 720,
        "render_video": True,
        "formal_profiles": profiles,
        "formal_job_count": FORMAL_JOB_COUNT,
        "formal_episode_count": FORMAL_EPISODE_COUNT,
        "preflight_episode_count": 0,
        "retry_attempt_limit": RETRY_ATTEMPT_LIMIT,
        "attempt_cap": ATTEMPT_CAP,
        "allowed_gpu_indices": list(ALLOWED_GPU_INDICES),
        "max_concurrency": MAX_CONCURRENCY,
        "external_compute_colocation_authorized": False,
        "fsm_thresholds": dict(FSM_THRESHOLDS),
        "gates": {
            "per_round_success_count": 5,
            "mean_total_success_count": 10,
            "qd_evaluations_per_complete_chunk": 1008,
            "zero_nonfinite": True,
            "zero_action_mask_violation": True,
            "zero_qd_fallback": True,
            "zero_qpos_execution_error": True,
        },
        "dimension_probe": {
            "path": str(DIMENSION_PROBE_PATH),
            "sha256": _sha256_file(DIMENSION_PROBE_PATH),
        },
        "test_evidence": test_evidence,
        "no_additional_experiment_jobs": True,
        "gates_frozen_by_design": True,
    }
    payload["manifest_payload_sha256"] = _sha256_bytes(
        _canonical(payload).encode("utf-8")
    )
    if _contains_credential(payload):
        raise RuntimeError("run manifest contains credential material")
    RUN_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUN_MANIFEST_PATH.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    RUN_MANIFEST_PATH.chmod(0o444)
    return payload


def _run_formal(*, requested_gpus: str, timeout_seconds: int) -> int:
    if not RUN_MANIFEST_PATH.is_file() or RUN_MANIFEST_PATH.stat().st_mode & 0o222:
        raise RuntimeError("immutable run manifest must exist before formal attempts")
    storage_preflight()
    sweep.legacy.validate_runtime_cache()
    legacy.validate_runtime_credential()
    if not base._poe_healthcheck():
        raise RuntimeError("Poe stage-recognition health check failed")
    reference = load_gpu_reference()
    admission = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"])
    )
    selected = _selected_gpus(admission, requested_gpus)
    if not selected:
        raise RuntimeError("no GPU in 0..7 passed strict idle admission")
    admission["selected_gpu_indices"] = [int(value) for value in selected]
    _write_gpu_admission("formal_dispatch", admission)
    jobs = build_jobs(FORMAL_LEVEL, 10)
    if attempt_ledger_state(ATTEMPT_LEDGER_PATH)["attempts"]:
        raise RuntimeError("formal ledger is nonempty; duplicate dispatch is forbidden")
    reservations = append_attempt_records(
        ATTEMPT_LEDGER_PATH, _attempt_records_for_jobs(jobs, "formal")
    )
    attempt_ids = [int(row["attempt_id"]) for row in reservations]
    if len(attempt_ids) != FORMAL_EPISODE_COUNT:
        raise RuntimeError("formal reservation count is not 40")
    append_ledger_event(
        ATTEMPT_LEDGER_PATH,
        {
            "record_type": "phase_dispatch",
            "phase": "formal",
            "attempt_ids": attempt_ids,
            "selected_gpu_indices": [int(value) for value in selected],
        },
    )
    with configured_base():
        original_healthcheck = base._poe_healthcheck
        base._poe_healthcheck = lambda: True
        try:
            result = base.run_level(
                FORMAL_LEVEL,
                10,
                ",".join(selected),
                timeout_seconds,
                resume=False,
                cached_functions_dir=str(RUNTIME_CACHE_DIR),
                offline_vlm=False,
                gpu_poll_interval_s=30.0,
            )
        finally:
            base._poe_healthcheck = original_healthcheck
    completion = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"]),
        wait_seconds=0.0,
    )
    completion["selected_gpu_indices"] = [int(value) for value in selected]
    completion["runner_exit_code"] = int(result)
    _write_gpu_admission("formal_completion", completion)
    return int(result)


def _run_retry(
    *, cells: list[tuple[str, int]], requested_gpus: str, timeout_seconds: int
) -> int:
    if not RUN_MANIFEST_PATH.is_file() or RUN_MANIFEST_PATH.stat().st_mode & 0o222:
        raise RuntimeError("immutable run manifest must exist before retry")
    manifest = json.loads(RUN_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("provenance") != current_provenance():
        raise RuntimeError("retry code provenance differs from frozen formal run")
    storage_preflight()
    sweep.legacy.validate_runtime_cache()
    legacy.validate_runtime_credential()
    if not base._poe_healthcheck():
        raise RuntimeError("Poe stage-recognition health check failed")
    selected = select_retry_cells(cells)
    state = attempt_ledger_state(ATTEMPT_LEDGER_PATH)
    if int(state["dispatched_attempt_count"]) < FORMAL_EPISODE_COUNT:
        raise RuntimeError("all 40 formal attempts must be dispatched before retry")
    retry_used = int(state["dispatched_attempt_count"]) - FORMAL_EPISODE_COUNT
    if retry_used < 0 or retry_used + len(selected) > RETRY_ATTEMPT_LIMIT:
        raise RuntimeError("retry would exceed the frozen four-attempt allowance")

    formal_jobs = {
        str(job["label"]): job for job in build_jobs(FORMAL_LEVEL, 10)
    }
    with configured_base():
        valid_labels = sorted(
            {
                str(cell["formal_label"])
                for cell in selected
                if base._p2_job_validity(
                    formal_jobs[str(cell["formal_label"])],
                    allow_identical_overrides=True,
                ).get("valid")
                is True
            }
        )
    if valid_labels:
        raise RuntimeError(
            "outcome-driven retry is forbidden for valid jobs: "
            + ",".join(valid_labels)
        )

    next_id = int(state["reserved_attempt_count"]) + 1
    retry_jobs = _retry_jobs(selected, first_attempt_id=next_id)
    reference = load_gpu_reference()
    admission = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"])
    )
    gpu_indices = _selected_gpus(admission, requested_gpus)
    gpu_indices = gpu_indices[: min(len(gpu_indices), len(retry_jobs))]
    if not gpu_indices:
        raise RuntimeError("no GPU in 0..7 passed strict retry admission")
    admission["selected_gpu_indices"] = [int(value) for value in gpu_indices]
    admission["retry_cells"] = selected
    _write_gpu_admission("retry_dispatch", admission)

    prior_by_cell: dict[tuple[str, int, int], int] = {}
    dispatched_ids = set(state["dispatched_attempt_ids"])
    for row in state["active_attempts"]:
        if int(row["attempt_id"]) not in dispatched_ids:
            continue
        key = (
            str(row.get("formal_label", row.get("label"))),
            int(row["task_id"]),
            int(row["episode_seed"]),
        )
        prior_by_cell[key] = int(row["attempt_id"])
    records = []
    for cell in selected:
        key = (
            str(cell["formal_label"]),
            int(cell["task_id"]),
            int(cell["episode_seed"]),
        )
        if key not in prior_by_cell:
            raise RuntimeError("retry cell has no prior dispatched formal attempt")
        formal = formal_jobs[key[0]]
        records.append(
            {
                "phase": "formal",
                "label": key[0],
                "formal_label": key[0],
                "task_id": key[1],
                "episode_seed": key[2],
                "profile_fingerprint": formal["profile_fingerprint"],
                "config_fingerprint": formal["config_fingerprint"],
                "code_state_sha256": formal["execution_record"][
                    "code_state_sha256"
                ],
                "recovery_of_attempt_id": prior_by_cell[key],
            }
        )
    reservations = append_attempt_records(ATTEMPT_LEDGER_PATH, records)
    attempt_ids = [int(row["attempt_id"]) for row in reservations]
    append_ledger_event(
        ATTEMPT_LEDGER_PATH,
        {
            "record_type": "phase_dispatch",
            "phase": "retry",
            "attempt_ids": attempt_ids,
            "selected_gpu_indices": [int(value) for value in gpu_indices],
            "retry_cells": selected,
        },
    )

    def retry_builder(level: str, episodes: int, **_kwargs):
        if level != RETRY_LEVEL or episodes != 10:
            raise ValueError("retry matrix changed unexpectedly")
        return [dict(job) for job in retry_jobs]

    with configured_base():
        original_builder = base.build_jobs
        original_healthcheck = base._poe_healthcheck
        base.build_jobs = retry_builder
        base._poe_healthcheck = lambda: True
        try:
            result = base.run_level(
                RETRY_LEVEL,
                10,
                ",".join(gpu_indices),
                timeout_seconds,
                resume=False,
                cached_functions_dir=str(RUNTIME_CACHE_DIR),
                offline_vlm=False,
                gpu_poll_interval_s=30.0,
            )
        finally:
            base.build_jobs = original_builder
            base._poe_healthcheck = original_healthcheck

    merge_results = []
    for retry_job, cell in zip(retry_jobs, selected):
        formal = formal_jobs[str(cell["formal_label"])]
        try:
            merge_results.append(
                merge_retry_cell(retry_job=retry_job, formal_job=formal)
            )
        except (OSError, ValueError, RuntimeError) as exc:
            merge_results.append(
                {
                    "retry_label": retry_job["label"],
                    "formal_label": formal["label"],
                    "episode": cell["task_id"],
                    "merged": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    completion = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"]),
        wait_seconds=0.0,
    )
    completion["selected_gpu_indices"] = [int(value) for value in gpu_indices]
    completion["runner_exit_code"] = int(result)
    completion["retry_cells"] = selected
    completion["merge_results"] = merge_results
    _write_gpu_admission("retry_completion", completion)
    all_merged = all(item.get("merged", True) is not False for item in merge_results)
    return 0 if int(result) == 0 and all_merged else 1


def _parse_cells(value: str) -> list[tuple[str, int]]:
    cells = []
    for raw in value.split(","):
        label, separator, task = raw.strip().rpartition(":")
        if not separator:
            raise ValueError("retry cells must use label:task syntax")
        cells.append((label, int(task)))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("matrix")
    subparsers.add_parser("initialize-storage")
    subparsers.add_parser("storage-preflight")
    subparsers.add_parser("dimension-probe")
    subparsers.add_parser("test-gate")
    subparsers.add_parser("gpu-admission")
    subparsers.add_parser("freeze-manifest")
    run = subparsers.add_parser("run-formal")
    run.add_argument("--gpus", default="auto")
    run.add_argument("--timeout-seconds", type=int, default=28800)
    retry = subparsers.add_parser("retry-cells")
    retry.add_argument("--cells", required=True)
    retry.add_argument("--gpus", default="auto")
    retry.add_argument("--timeout-seconds", type=int, default=28800)
    args = parser.parse_args()

    if args.command == "matrix":
        print(json.dumps(build_jobs(FORMAL_LEVEL, 10), indent=2))
        return 0
    if args.command == "initialize-storage":
        print(json.dumps(initialize_storage(), indent=2))
        return 0
    if args.command == "storage-preflight":
        print(json.dumps(storage_preflight(), indent=2))
        return 0
    if args.command == "dimension-probe":
        print(json.dumps(run_dimension_probe(), indent=2))
        return 0
    if args.command == "test-gate":
        print(json.dumps(run_test_gate(), indent=2))
        return 0
    if args.command == "gpu-admission":
        print(
            json.dumps(
                admit_gpus(reference_peak_vram_mib=REFERENCE_PEAK_VRAM_MIB),
                indent=2,
            )
        )
        return 0
    if args.command == "freeze-manifest":
        test_evidence = json.loads(TEST_EVIDENCE_PATH.read_text(encoding="utf-8"))
        payload = freeze_run_manifest(
            provenance=current_provenance(),
            storage=storage_preflight(),
            gpu_reference=load_gpu_reference(),
            test_evidence=test_evidence,
        )
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "retry-cells":
        return _run_retry(
            cells=_parse_cells(args.cells),
            requested_gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
        )
    return _run_formal(
        requested_gpus=args.gpus,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
