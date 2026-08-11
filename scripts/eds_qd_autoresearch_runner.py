#!/usr/bin/env python3
"""Isolated runner for the protocol-locked causal-envelope QD-1 candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import torch

SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_quality_diversity_runner as legacy
import eds_quality_diversity_audit as qd_audit
import rdt_eds_eval_runner as base
from core.qd_ed import (
    QDArchive,
    allocate_parent_slots,
    cell_ids,
    expand_bounds,
    fingerprint_action,
    freeze_bounds,
    within_cell_endpoint_sse,
)


MECHANISM_PREFLIGHT_LEVEL = "eds_qd_autoresearch_mechanism_preflight"
DEV_A_LEVEL = "eds_qd_autoresearch_dev_a"
DEV_B_LEVEL = "eds_qd_autoresearch_dev_b"
BRANCH = "exp/eds-qd-autoresearch-libero-swap-ood"
PROTOCOL_COMMIT = "1017bf0212780b2e386764517661cf9970090f8d"
REPAIR_PROTOCOL_COMMIT = "8fd3aea0b1ec063aba63fa0bffcf3829f03c006c"
EXPERIMENT_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood"
)
RUN_ROOT = EXPERIMENT_ROOT / "run_010_causal_envelope_candidate"
OUTPUT_LINK = WORKTREE_ROOT / "outputs"
ALLOWED_STORAGE_PREFIX = Path("/mnt/data/shared2/zhuoli/vla-pilot-plus-plus")
MIN_FREE_BYTES = 50 * 1024**3
PAUSE_SENTINEL = WORKTREE_ROOT / ".autoresearch/PAUSE"
ATTEMPT_CAP = 143
GPU_HOUR_CAP = 48.0
ALLOWED_GPU_INDICES = set(range(8))
RUN_MANIFEST_PATH = RUN_ROOT / "manifests/run_manifest.json"
ATTEMPT_LEDGER_PATH = RUN_ROOT / "manifests/episode_attempt_ledger.jsonl"
FAILED_OFFLINE_PREFLIGHT_V1_PATH = RUN_ROOT / "analysis/offline_preflight.json"
FAILED_OFFLINE_PREFLIGHT_V1_SHA256 = (
    "1654574975a02df00be5ac6c78b986b18baf1657bf997a808c1fcb5aa58f9a61"
)
OFFLINE_PREFLIGHT_PATH = RUN_ROOT / "analysis/offline_preflight.v2.json"
MECHANISM_AUDIT_PATH = RUN_ROOT / "analysis/mechanism_preflight_audit.json"
DEV_A_AUDIT_PATH = RUN_ROOT / "analysis/dev_a_audit.json"
MECHANISM_AUDIT_V2_PATH = RUN_ROOT / "analysis/mechanism_preflight_audit.v2.json"
DEV_A_AUDIT_V2_PATH = RUN_ROOT / "analysis/dev_a_audit.v2.json"
DEV_B_MANIFEST_PATH = RUN_ROOT / "manifests/dev_b_manifest.json"
DEV_B_AUDIT_PATH = RUN_ROOT / "analysis/dev_b_audit.json"
RUNTIME_CACHE_DIR = RUN_ROOT / "runtime_cache/cached_functions"
RUNTIME_CACHE_MANIFEST_PATH = RUN_ROOT / "runtime_cache/provenance.json"
RUNTIME_CACHE_SOURCE = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/"
    "runtime_cache/cached_functions"
)
GPU_REFERENCE_PATH = Path(
    "/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/"
    "manifests/gpu_reference_peak.json"
)
POLICY_CONFIG_PATH = WORKTREE_ROOT / "configs/policy.yaml"
ACTIVE_CHECKPOINT_ROOT = Path("/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object")
ACTIVE_CHECKPOINT_WEIGHT = ACTIVE_CHECKPOINT_ROOT / "ema/model.safetensors"
REGRESSION_TESTS = (
    "tests/test_qd_ed_archive.py",
    "tests/test_eds_quality_diversity_runner.py",
    "tests/test_eds_quality_diversity_audit.py",
    "tests/test_rdt_steer.py",
    "tests/test_eds_eval_metrics.py",
    "tests/test_eds_eval_runner.py",
    "tests/test_main_rdt_startup.py",
    "tests/test_env_adapters_imports.py",
    "tests/test_eds_qd_autoresearch_runner.py",
)
PROTECTED_UNTRACKED = (
    "docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md"
)
DEV_TASKS = [3, 5, 8, 9]
DEV_A_SEEDS = [512905, 150741, 463456, 452903]
DEV_B_SEEDS = [558482, 165717, 160148, 160312]
PREFLIGHT_TASKS = [3, 5]
PREFLIGHT_SEEDS = DEV_A_SEEDS[:2]

ORIGINAL_RUN_MANIFEST_SHA256 = (
    "cb211e2ed3fe2cfa2512f0982153295c9f23fa9964e3f623d1ef3b1eef10ae34"
)
MECHANISM_AUDIT_V2_SHA256 = (
    "c7e93f9255aee10f71e2519fa9e539cd537ca4ed89c905cebe334db5c68508ab"
)
DEV_A_AUDIT_V2_SHA256 = (
    "9c6d3ecee60d50c7e574b2a795c864483c85c812c0883a96ec81aa5d5d889fa9"
)
PRE_EPISODE_INCIDENT_GPU_HOURS = 0.023594
DEV_B_ALGORITHM_SOURCE_SHA256 = {
    "configs/config.yaml": "b20791a2792a5f7c6b3b61a2af02055462aa447059802aceb1293a7f77ecdaf8",
    "core/qd_ed.py": "1516bb75c3a5dc3894792d6b8f5daf7f777c48b7d58ea96496da47a986a970b9",
    "core/rdt_policy_steer.py": "b8806d7a28e42e6e8a9d2959b5b1d7e5b7c9b304526d4022146c3ba23c8c1ff2",
    "core/eds_eval_metrics.py": "d8fb4d04271aa801089a1202af8baf658dc270b751224bc28b4816c9a6a83429",
}

QD_CONFIG_FIELDS = (
    "qd_archive_mode",
    "qd_descriptor",
    "qd_grid_shape",
    "qd_cell_capacity",
    "qd_parent_sampling",
    "qd_sparse_exponent",
    "qd_bounds_quantiles",
    "qd_bounds_expand_fraction",
    "qd_min_axis_span_m",
    "qd_bounds_update_policy",
    "qd_overflow_policy",
    "qd_tie_break",
    "qd_metrics_observer",
)

_BASE_BUILD_MAIN_COMMAND = base.build_main_command
_BASE_STAGE_DIR = base._p2_stage_dir


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checkpoint_fingerprint() -> dict[str, Any]:
    files = [
        ACTIVE_CHECKPOINT_WEIGHT,
        ACTIVE_CHECKPOINT_ROOT / "config.json",
        POLICY_CONFIG_PATH,
    ]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise RuntimeError("active checkpoint identity is incomplete: " + ",".join(missing))
    records = [
        {
            "path": str(path.resolve(strict=True)),
            "size_bytes": int(path.stat().st_size),
            "sha256": sha256_path(path),
        }
        for path in files
    ]
    return {
        "pretrained_path": str(ACTIVE_CHECKPOINT_ROOT.resolve(strict=True)),
        "weight_variant": "ema",
        "files": records,
        "aggregate_sha256": sha256_bytes(canonical(records).encode("utf-8")),
    }


def libero_input_fingerprint() -> dict[str, Any]:
    roots = [
        base.LIBERO_PRO_ROOT / "libero/libero/bddl_files/libero_object_swap",
        base.LIBERO_PRO_ROOT / "libero/libero/init_files/libero_object_swap",
    ]
    files = sorted(path for root in roots for path in root.iterdir() if path.is_file())
    if len(files) != 20:
        raise RuntimeError(f"expected 20 LIBERO swap input files, found {len(files)}")
    records = [
        {
            "path": path.relative_to(base.LIBERO_PRO_ROOT).as_posix(),
            "size_bytes": int(path.stat().st_size),
            "sha256": sha256_path(path),
        }
        for path in files
    ]
    return {
        "suite": "libero_object_swap",
        "files": records,
        "aggregate_sha256": sha256_bytes(canonical(records).encode("utf-8")),
    }


def run_regression_tests() -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", *REGRESSION_TESTS]
    started = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=WORKTREE_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    output = process.stdout or ""
    matched = re.search(r"(\d+) passed(?:,| in)", output)
    return {
        "command": command,
        "command_sha256": sha256_bytes(canonical(command).encode("utf-8")),
        "exit_code": int(process.returncode),
        "passed_count": int(matched.group(1)) if matched else None,
        "wall_seconds": round(time.perf_counter() - started, 3),
        "output_tail": output[-4000:],
        "passed": process.returncode == 0 and matched is not None,
    }


def contains_credential(value: Any) -> bool:
    serialized = canonical(value)
    secrets = [
        os.environ.get(name, "")
        for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY")
    ]
    if any(len(secret) >= 20 and secret in serialized for secret in secrets):
        return True
    return any(
        pattern.search(serialized) is not None
        for pattern in (
            re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}"),
            re.compile(
                r"(?:api[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{20,}",
                re.IGNORECASE,
            ),
            re.compile(
                r"authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{20,}",
                re.IGNORECASE,
            ),
        )
    )


def _profile(label: str, role: str, **updates: Any) -> dict[str, Any]:
    common = {
        **legacy.COMMON_PROFILE,
        "qd_parent_sampling": "sparse_priority",
        "qd_bounds_update_policy": "fixed_initial",
    }
    # The legacy QD run pinned EGL to GPU 5.  This experiment admits any idle
    # GPU 0-7, so omitting the override makes the base runner colocate MuJoCo
    # rendering with each worker's dynamically assigned physical GPU.
    common.pop("p2_render_gpu_index", None)
    return {**common, "method": label, "label": label, "role": role, **updates}


def profiles() -> list[dict[str, Any]]:
    return [
        _profile(
            "p2_stage_on_abs_rbf_control",
            "control",
            qd_archive_mode="none",
        ),
        _profile(
            "eds_quality_diversity_sparse_primary",
            "reference",
        ),
        _profile(
            "eds_quality_diversity_sparse_causal_envelope_v1",
            "candidate",
            qd_bounds_update_policy="causal_envelope_v1",
        ),
    ]


def _bind_job(job: dict[str, Any]) -> dict[str, Any]:
    manifest_path = (
        DEV_B_MANIFEST_PATH
        if job.get("level") == DEV_B_LEVEL
        else RUN_MANIFEST_PATH
    )
    if manifest_path.is_file():
        if manifest_path.stat().st_mode & 0o222:
            raise RuntimeError("run manifest must be immutable before job binding")
        job = {
            **job,
            "manifest_path": str(manifest_path.resolve(strict=True)),
            "manifest_sha256": sha256_path(manifest_path),
        }
    with configured_base():
        return base._bind_p2_execution_context(
            job,
            real_root=EXPERIMENT_ROOT,
            cached_functions_dir=str(RUNTIME_CACHE_DIR),
            offline_vlm=False,
            storage_enforced=True,
            git_revision=base._git_head_revision(),
            code_state_sha256=base._p2_code_state_sha256(),
        )


def build_jobs(level: str, episodes: int | None = None, *, bind: bool = True, **_: Any) -> list[dict[str, Any]]:
    if level == MECHANISM_PREFLIGHT_LEVEL:
        task_ids = PREFLIGHT_TASKS
        seeds = PREFLIGHT_SEEDS
        selected = profiles()
        expected_episodes = 2
        max_chunks = 2
    elif level == DEV_A_LEVEL:
        task_ids = DEV_TASKS
        seeds = DEV_A_SEEDS
        selected = [profiles()[0], profiles()[2]]
        expected_episodes = 4
        max_chunks = None
    elif level == DEV_B_LEVEL:
        task_ids = DEV_TASKS
        seeds = DEV_B_SEEDS
        selected = [profiles()[0], profiles()[2]]
        expected_episodes = 4
        max_chunks = None
    else:
        raise ValueError(
            "phase must be mechanism_preflight, dev_a, or dev_b; formal is forbidden"
        )
    if episodes is not None and int(episodes) != expected_episodes:
        raise ValueError(f"{level} requires exactly {expected_episodes} episodes")
    jobs: list[dict[str, Any]] = []
    for profile in selected:
        formal_label = str(profile["label"])
        label = (
            f"preflight__{formal_label}"
            if level == MECHANISM_PREFLIGHT_LEVEL
            else (
                f"dev_a__{formal_label}"
                if level == DEV_A_LEVEL
                else f"dev_b__{formal_label}"
            )
        )
        job = {
            **profile,
            "formal_label": formal_label,
            "method": label,
            "label": label,
            "job_id": f"{level}_libero_object_swap_{label}",
            "level": level,
            "suite": "libero_object_swap",
            "episodes": expected_episodes,
            "task_ids_filter": list(task_ids),
            "episode_seeds": list(seeds),
            "max_chunks": max_chunks,
        }
        jobs.append(_bind_job(job) if bind else job)
    return jobs


def hydra_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(hydra_value(item) for item in value) + "]"
    if value is None:
        return "null"
    return str(value)


def _build_main_command(job: dict[str, Any], *args: Any, **kwargs: Any) -> list[str]:
    job = dict(job)
    job.setdefault("p2_output_real_root", str(EXPERIMENT_ROOT))
    with configured_base():
        command = _BASE_BUILD_MAIN_COMMAND(job, *args, **kwargs)
    command.append(
        "main.episode_seed_schedule=" + hydra_value(job["episode_seeds"])
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
        f"main.eds_config.{field}={hydra_value(job[field])}"
        for field in QD_CONFIG_FIELDS
    )
    override_keys = [
        token.split("=", 1)[0].lstrip("+") for token in command if "=" in token
    ]
    if len(override_keys) != len(set(override_keys)):
        raise RuntimeError("autoresearch command contains duplicate Hydra overrides")
    if contains_credential(command):
        raise RuntimeError("autoresearch command contains credential material")
    return command


def stage_dir(level: Any) -> str:
    if str(level) in {MECHANISM_PREFLIGHT_LEVEL, DEV_A_LEVEL}:
        return "run_010_causal_envelope_candidate"
    return _BASE_STAGE_DIR(level)


def gpu_probe(gpu: str) -> tuple[str, str]:
    index = int(gpu)
    if index not in ALLOWED_GPU_INDICES:
        return "busy", "GPU index is outside the authorized 0-7 range"
    reference = load_gpu_reference()
    device = next(
        (item for item in legacy.gpu_snapshot() if int(item["index"]) == index),
        None,
    )
    reasons = legacy._gpu_snapshot_failure(
        device,
        index=index,
        required_free=float(reference["required_free_vram_mib"]),
        allow_external_compute=False,
    )
    return ("busy", "; ".join(reasons)) if reasons else ("idle", "admitted")


def configure_base() -> None:
    base.P2_OUTPUT_ROOT = OUTPUT_LINK
    base.P2_STATUS_ROOT = OUTPUT_LINK
    base.P2_EXPECTED_OUTPUT_TARGET = EXPERIMENT_ROOT
    base.P2_ALLOWED_OUTPUT_PREFIX = ALLOWED_STORAGE_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | {
        MECHANISM_PREFLIGHT_LEVEL,
        DEV_A_LEVEL,
    }
    base.P2_ALLOWED_GPUS = {str(index) for index in ALLOWED_GPU_INDICES}
    base.P2_REQUIRED_MOUNT = Path("/mnt/data/shared2")
    base.P2_TORCH_HUB_SEED = (
        Path("/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf")
        / "runtime_cache/formal/p2_stage_on_dirnorm_rbf_global_w0_e025/xdg/torch/hub"
    )
    base.build_jobs = build_jobs
    base.build_main_command = _build_main_command
    base._p2_stage_dir = stage_dir
    base._p2_gpu_probe = gpu_probe


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


def pause_preflight(path: Path = PAUSE_SENTINEL) -> None:
    if Path(path).exists():
        raise RuntimeError(f"autoresearch is paused by sentinel: {path}")


def storage_preflight(
    *,
    experiment_root: Path = EXPERIMENT_ROOT,
    output_link: Path = OUTPUT_LINK,
    allowed_prefix: Path = ALLOWED_STORAGE_PREFIX,
    minimum_free_bytes: int = MIN_FREE_BYTES,
) -> dict[str, Any]:
    experiment_root = Path(experiment_root)
    output_link = Path(output_link)
    allowed_prefix = Path(allowed_prefix)
    if not experiment_root.is_dir() or not os.access(experiment_root, os.W_OK):
        raise RuntimeError("owned experiment root is unavailable or not writable")
    if not output_link.is_symlink() or not os.path.isabs(os.readlink(output_link)):
        raise RuntimeError("outputs must be an absolute symlink")
    target = output_link.resolve(strict=True)
    expected = experiment_root.resolve(strict=True)
    prefix = allowed_prefix.resolve(strict=True)
    if target != expected:
        raise RuntimeError(f"outputs target mismatch: {target} != {expected}")
    try:
        target.relative_to(prefix)
    except ValueError as exc:
        raise RuntimeError("owned experiment root is outside allowed shared2 prefix") from exc
    free = int(shutil.disk_usage(target).free)
    if free < int(minimum_free_bytes):
        raise RuntimeError("owned experiment root has less than 50 GiB free")
    probe = target / f".run010_storage_probe_{os.getpid()}"
    with probe.open("x", encoding="utf-8") as handle:
        handle.write("ok\n")
    probe.unlink()
    return {
        "passed": True,
        "experiment_root": str(expected),
        "outputs_link": str(output_link),
        "outputs_target": str(target),
        "free_bytes": free,
    }


def read_attempts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("record_type", "episode_attempt") == "episode_attempt":
            records.append(record)
    if [record.get("attempt_id") for record in records] != list(
        range(1, len(records) + 1)
    ):
        raise RuntimeError("attempt ledger ids are not contiguous")
    return records


def reserve_attempts(
    path: Path,
    records: list[dict[str, Any]],
    *,
    cap: int = ATTEMPT_CAP,
) -> list[dict[str, Any]]:
    existing = read_attempts(path)
    if len(existing) + len(records) > int(cap):
        raise RuntimeError(f"episode-attempt hard cap {cap} would be exceeded")
    def identity(record: dict[str, Any]) -> tuple[Any, ...]:
        return (
            record.get("phase"),
            record.get("formal_label", record.get("label")),
            record.get("task_id"),
            record.get("episode_seed"),
            record.get("config_fingerprint"),
            record.get("code_state_sha256"),
        )

    existing_identities = {identity(record) for record in existing}
    new_identities = [identity(record) for record in records]
    if len(new_identities) != len(set(new_identities)):
        raise RuntimeError("duplicate attempt identity in one reservation")
    if existing_identities & set(new_identities):
        raise RuntimeError(
            "same-cell recovery requires a protocol-audited explicit recovery command"
        )
    prepared: list[dict[str, Any]] = []
    required = {
        "phase",
        "label",
        "task_id",
        "episode_seed",
        "config_fingerprint",
        "code_state_sha256",
    }
    for offset, record in enumerate(records, start=1):
        if not required <= set(record):
            raise ValueError("attempt identity is incomplete")
        prepared_record = {
            "attempt_id": len(existing) + offset,
            "record_type": "episode_attempt",
            "started_at": now(),
            **record,
        }
        if contains_credential(prepared_record):
            raise RuntimeError("attempt identity contains credential material")
        prepared.append(prepared_record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in prepared:
            handle.write(canonical(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return prepared


def admit_gpus(
    *,
    reference_peak_vram_mib: float,
    snapshot_fn: Callable[[], list[dict[str, Any]]] = legacy.gpu_snapshot,
    wait_fn: Callable[[float], None] = time.sleep,
    wait_seconds: float = 30.0,
) -> dict[str, Any]:
    result = legacy.admit_gpus(
        reference_peak_vram_mib=reference_peak_vram_mib,
        snapshot_fn=snapshot_fn,
        wait_fn=wait_fn,
        wait_seconds=wait_seconds,
        pinned_gpu_index=None,
        allow_external_compute=False,
    )
    result["max_concurrency"] = min(8, len(result["eligible_gpu_indices"]))
    return result


def load_gpu_reference() -> dict[str, Any]:
    payload = json.loads(GPU_REFERENCE_PATH.read_text(encoding="utf-8"))
    peak = float(payload["reference_peak_vram_mib"])
    if not math.isfinite(peak) or peak <= 0:
        raise RuntimeError("GPU reference peak is invalid")
    return {
        "path": str(GPU_REFERENCE_PATH),
        "sha256": sha256_path(GPU_REFERENCE_PATH),
        "reference_peak_vram_mib": peak,
        "required_free_vram_mib": max(1.25 * peak, peak + 4096.0),
    }


def validate_credential() -> dict[str, Any]:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if not value or value.lower() == "dummy":
        raise RuntimeError("Stage credential must come from the runtime environment")
    return {"present": True, "source": "environment", "value_logged": False}


def prepare_runtime_cache() -> dict[str, Any]:
    if RUNTIME_CACHE_DIR.exists():
        return legacy.validate_runtime_cache(
            target=RUNTIME_CACHE_DIR,
            manifest_path=RUNTIME_CACHE_MANIFEST_PATH,
        )
    return legacy.prepare_runtime_cache(
        source=RUNTIME_CACHE_SOURCE,
        target=RUNTIME_CACHE_DIR,
        manifest_path=RUNTIME_CACHE_MANIFEST_PATH,
    )


def profile_fingerprint(profile: dict[str, Any]) -> str:
    excluded = {"method", "label", "role", "job_id", "level", "formal_label"}
    payload = {
        "profile": {key: value for key, value in profile.items() if key not in excluded},
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "dev_tasks": DEV_TASKS,
        "dev_a_seeds": DEV_A_SEEDS,
        "dev_b_seeds": DEV_B_SEEDS,
    }
    return sha256_bytes(canonical(payload).encode("utf-8"))


def current_provenance() -> dict[str, Any]:
    status = subprocess.check_output(
        ["git", "status", "--short"], cwd=WORKTREE_ROOT, text=True
    ).splitlines()
    unexpected = [
        line
        for line in status
        if not line.endswith(PROTECTED_UNTRACKED) and not line.endswith(" outputs")
    ]
    if unexpected:
        raise RuntimeError("worktree must be committed before manifest: " + "; ".join(unexpected))
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=WORKTREE_ROOT,
        text=True,
    ).strip()
    if branch != BRANCH:
        raise RuntimeError(f"unexpected branch: {branch}")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    return {
        "branch": branch,
        "worktree": str(WORKTREE_ROOT.resolve(strict=True)),
        "code_commit": head,
        "protocol_commit": PROTOCOL_COMMIT,
        "repair_protocol_commit": REPAIR_PROTOCOL_COMMIT,
        "code_state_sha256": base._p2_code_state_sha256(),
    }


def offline_preflight(path: Path = OFFLINE_PREFLIGHT_PATH) -> dict[str, Any]:
    pause_preflight()
    storage = storage_preflight()
    regression = run_regression_tests()
    checkpoint = checkpoint_fingerprint()
    libero_inputs = libero_input_fingerprint()
    rng_before = torch.random.get_rng_state().clone()
    initial = torch.tensor(
        [[x, y] for y in (-0.04, -0.01, 0.01, 0.04) for x in (-0.04, -0.01, 0.01, 0.04)],
        dtype=torch.float32,
    )
    bounds = freeze_bounds(
        initial,
        quantiles=(0.05, 0.95),
        expand_fraction=0.10,
        min_axis_span_m=0.08,
    )
    initial_cells, _ = cell_ids(initial, bounds, (4, 4))
    actions = torch.stack([torch.full((4, 5), float(index)) for index in range(16)])
    rewards = torch.arange(16, dtype=torch.float32)
    archive = QDArchive(grid_shape=(4, 4))
    archive.update(
        actions=actions,
        rewards=rewards,
        costs=-rewards,
        descriptors=initial,
        cell_ids=initial_cells,
        source_iter=-1,
    )
    active_bounds = bounds
    iterations: list[dict[str, Any]] = []
    evaluation_count = 16
    score_call_count = 1
    for iteration in range(10):
        allocation = allocate_parent_slots(
            archive,
            population_size=16,
            sampling="sparse_priority",
            sparse_exponent=1.0,
            run_seed=0,
            episode=0,
            global_step=0,
            iter_idx=iteration,
        )
        children = initial * float(iteration + 2)
        fixed_cells, raw_overflow = cell_ids(children, bounds, (4, 4))
        expanded, changed = expand_bounds(active_bounds, children)
        _, _, _, incumbent_descriptors, _ = archive.elite_tensors()
        rebinned_cells, _ = cell_ids(incumbent_descriptors, expanded, (4, 4))
        best_before_rebin = archive.select_global_best()[1].fingerprint
        rebin = archive.rebin(rebinned_cells)
        best_after_rebin = archive.select_global_best()[1].fingerprint
        active_bounds = expanded
        active_cells, active_overflow = cell_ids(children, active_bounds, (4, 4))
        fixed_sse = within_cell_endpoint_sse(children, fixed_cells)
        active_sse = within_cell_endpoint_sse(children, active_cells)
        resolution = 1.0 - active_sse / fixed_sse if fixed_sse > 0 else None
        child_rewards = rewards + float((iteration + 1) * 100)
        update = archive.update(
            actions=actions + float(iteration + 1),
            rewards=child_rewards,
            costs=-child_rewards,
            descriptors=children,
            cell_ids=active_cells,
            source_iter=iteration,
            parent_cell_ids=allocation.parent_cell_ids,
        )
        evaluation_count += 16
        score_call_count += 1
        iterations.append(
            {
                "iter_idx": iteration,
                "bounds_changed": changed,
                "active_bounds_checksum": active_bounds.checksum,
                "raw_overflow_count": int(raw_overflow.sum().item()),
                "post_envelope_overflow_count": int(active_overflow.sum().item()),
                "fixed_sse": fixed_sse,
                "active_sse": active_sse,
                "resolution_improvement": resolution,
                "rebin": rebin.__dict__,
                "global_best_before_rebin": best_before_rebin,
                "global_best_after_rebin": best_after_rebin,
                "parent_slot_sum": sum(allocation.slot_counts.values()),
                "update": update.__dict__,
            }
        )
    rng_unchanged = torch.equal(torch.random.get_rng_state(), rng_before)
    hard_failures = []
    if not regression["passed"]:
        hard_failures.append("frozen regression suite failed")
    if not all(item["bounds_changed"] for item in iterations):
        hard_failures.append("bounds did not expand in every synthetic iteration")
    if not all(
        item["raw_overflow_count"] > 0
        and item["post_envelope_overflow_count"] == 0
        for item in iterations
    ):
        hard_failures.append("overflow accounting mismatch")
    if not all(
        item["rebin"]["visit_sum_before"]
        == item["rebin"]["visit_sum_after"]
        for item in iterations
    ):
        hard_failures.append("visit sum was not preserved")
    if not all(
        item["global_best_before_rebin"] == item["global_best_after_rebin"]
        for item in iterations
    ):
        hard_failures.append("global best changed during rebin")
    if evaluation_count != 176 or score_call_count != 11:
        hard_failures.append("evaluation/call budget mismatch")
    if not all(item["update"]["total"] == 16 for item in iterations):
        hard_failures.append("archive accounting mismatch")
    finite_resolution = [
        float(item["resolution_improvement"])
        for item in iterations
        if isinstance(item["resolution_improvement"], (int, float))
        and math.isfinite(float(item["resolution_improvement"]))
    ]
    finite_resolution_median = median(finite_resolution)
    if finite_resolution_median is None or finite_resolution_median < 0.20:
        hard_failures.append("synthetic resolution gate failed")
    if not all(item["parent_slot_sum"] == 16 for item in iterations):
        hard_failures.append("parent allocation budget mismatch")
    if not rng_unchanged:
        hard_failures.append("global RNG state changed")
    synthetic_input = {
        "initial_descriptors": initial.tolist(),
        "actions": actions.tolist(),
        "rewards": rewards.tolist(),
    }
    payload = {
        "schema": "eds-qd-autoresearch-offline-preflight-v2",
        "created_at": now(),
        "provenance": current_provenance(),
        "storage": storage,
        "source_fingerprints": {
            path: sha256_path(WORKTREE_ROOT / path)
            for path in (
                "configs/config.yaml",
                "core/qd_ed.py",
                "core/rdt_policy_steer.py",
                "core/eds_eval_metrics.py",
                "scripts/eds_qd_autoresearch_runner.py",
            )
        },
        "checkpoint_fingerprint": checkpoint,
        "libero_input_fingerprint": libero_inputs,
        "synthetic_input_sha256": sha256_bytes(
            canonical(synthetic_input).encode("utf-8")
        ),
        "preserved_failed_v1": {
            "path": str(FAILED_OFFLINE_PREFLIGHT_V1_PATH),
            "sha256": FAILED_OFFLINE_PREFLIGHT_V1_SHA256,
        },
        "regression_test_evidence": regression,
        "candidate": "eds_quality_diversity_sparse_causal_envelope_v1",
        "profile_fingerprints": {
            profile["label"]: profile_fingerprint(profile) for profile in profiles()
        },
        "mechanism": {
            "initial_bounds_checksum": bounds.checksum,
            "final_bounds_checksum": active_bounds.checksum,
            "iterations": iterations,
            "evaluation_budget_per_full_chunk": evaluation_count,
            "score_calls_per_full_chunk": score_call_count,
            "global_rng_unchanged": rng_unchanged,
            "finite_resolution_count": len(finite_resolution),
            "finite_resolution_median": finite_resolution_median,
        },
        "hard_failures": hard_failures,
        "passed": not hard_failures,
    }
    if contains_credential(payload):
        raise RuntimeError("offline preflight contains credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    return payload


def freeze_manifest(path: Path = RUN_MANIFEST_PATH) -> dict[str, Any]:
    pause_preflight()
    storage = storage_preflight()
    offline = json.loads(OFFLINE_PREFLIGHT_PATH.read_text(encoding="utf-8"))
    if offline.get("passed") is not True:
        raise RuntimeError("offline preflight did not pass")
    if (
        not FAILED_OFFLINE_PREFLIGHT_V1_PATH.is_file()
        or sha256_path(FAILED_OFFLINE_PREFLIGHT_V1_PATH)
        != FAILED_OFFLINE_PREFLIGHT_V1_SHA256
    ):
        raise RuntimeError("preserved failed offline v1 identity mismatch")
    cache = prepare_runtime_cache()
    provenance = current_provenance()
    gpu_reference = load_gpu_reference()
    payload = {
        "schema": "eds-qd-autoresearch-run010-manifest-v1",
        "created_at": now(),
        "provenance": provenance,
        "storage": storage,
        "runtime_cache_sha256": sha256_bytes(canonical(cache).encode("utf-8")),
        "offline_preflight_sha256": sha256_path(OFFLINE_PREFLIGHT_PATH),
        "failed_offline_preflight_v1_sha256": FAILED_OFFLINE_PREFLIGHT_V1_SHA256,
        "checkpoint_fingerprint": offline["checkpoint_fingerprint"],
        "libero_input_fingerprint": offline["libero_input_fingerprint"],
        "regression_test_evidence": {
            key: offline["regression_test_evidence"][key]
            for key in ("command", "command_sha256", "exit_code", "passed_count", "passed")
        },
        "gpu_reference": gpu_reference,
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "max_episode_steps": 720,
        "stage_recognition_enabled": True,
        "gemini_grounding_enabled": False,
        "profiles": [
            {**profile, "profile_fingerprint": profile_fingerprint(profile)}
            for profile in profiles()
        ],
        "mechanism_preflight": {
            "tasks": PREFLIGHT_TASKS,
            "seeds": PREFLIGHT_SEEDS,
            "max_chunks": 2,
            "unique_cells": 6,
        },
        "dev_a": {
            "tasks": DEV_TASKS,
            "seeds": DEV_A_SEEDS,
            "profiles": [profiles()[0]["label"], profiles()[2]["label"]],
            "unique_cells": 8,
        },
        "attempt_cap": ATTEMPT_CAP,
        "gpu_hour_cap": GPU_HOUR_CAP,
        "allowed_gpu_indices": sorted(ALLOWED_GPU_INDICES),
        "formal_authorized": False,
    }
    payload["payload_sha256"] = sha256_bytes(canonical(payload).encode("utf-8"))
    if contains_credential(payload):
        raise RuntimeError("run manifest contains credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    return payload


def _require_immutable_pass_artifact(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_mode & 0o222:
        raise RuntimeError(f"immutable PASS artifact is required: {path.name}")
    if sha256_path(path) != expected_sha256:
        raise RuntimeError(f"PASS artifact identity mismatch: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("passed") is not True:
        raise RuntimeError(f"PASS artifact is not passing: {path.name}")
    return payload


def _dev_b_manifest_payload(
    *,
    provenance: dict[str, Any],
    storage: dict[str, Any],
    runtime_cache_sha256: str,
    checkpoint: dict[str, Any],
    libero_inputs: dict[str, Any],
    algorithm_source_fingerprints: dict[str, str],
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    if algorithm_source_fingerprints != DEV_B_ALGORITHM_SOURCE_SHA256:
        raise RuntimeError("Dev-B algorithm source differs from the frozen candidate")
    return {
        "schema": "eds-qd-autoresearch-run010-dev-b-manifest-v1",
        "created_at": now(),
        "provenance": provenance,
        "storage": storage,
        "runtime_cache_sha256": runtime_cache_sha256,
        "checkpoint_fingerprint": checkpoint,
        "libero_input_fingerprint": libero_inputs,
        "algorithm_source_fingerprints": algorithm_source_fingerprints,
        "parent_evidence": {
            "original_run_manifest_sha256": ORIGINAL_RUN_MANIFEST_SHA256,
            "mechanism_audit_v2_sha256": MECHANISM_AUDIT_V2_SHA256,
            "dev_a_audit_v2_sha256": DEV_A_AUDIT_V2_SHA256,
        },
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "max_episode_steps": 720,
        "profiles": [profiles()[0]["label"], profiles()[2]["label"]],
        "dev_b": {
            "tasks": DEV_TASKS,
            "seeds": DEV_B_SEEDS,
            "unique_cells": 8,
            "job_matrix_sha256": sha256_bytes(
                canonical(jobs).encode("utf-8")
            ),
        },
        "attempt_cap": ATTEMPT_CAP,
        "gpu_hour_cap": GPU_HOUR_CAP,
        "allowed_gpu_indices": sorted(ALLOWED_GPU_INDICES),
        "formal_authorized": False,
    }


def freeze_dev_b_manifest(path: Path = DEV_B_MANIFEST_PATH) -> dict[str, Any]:
    pause_preflight()
    storage = storage_preflight()
    if sha256_path(RUN_MANIFEST_PATH) != ORIGINAL_RUN_MANIFEST_SHA256:
        raise RuntimeError("original immutable run manifest identity mismatch")
    _require_immutable_pass_artifact(
        MECHANISM_AUDIT_V2_PATH, MECHANISM_AUDIT_V2_SHA256
    )
    _require_immutable_pass_artifact(DEV_A_AUDIT_V2_PATH, DEV_A_AUDIT_V2_SHA256)
    cache = legacy.validate_runtime_cache(
        target=RUNTIME_CACHE_DIR, manifest_path=RUNTIME_CACHE_MANIFEST_PATH
    )
    algorithm_sources = {
        relative: sha256_path(WORKTREE_ROOT / relative)
        for relative in DEV_B_ALGORITHM_SOURCE_SHA256
    }
    payload = _dev_b_manifest_payload(
        provenance=current_provenance(),
        storage=storage,
        runtime_cache_sha256=sha256_bytes(canonical(cache).encode("utf-8")),
        checkpoint=checkpoint_fingerprint(),
        libero_inputs=libero_input_fingerprint(),
        algorithm_source_fingerprints=algorithm_sources,
        jobs=build_jobs(DEV_B_LEVEL, bind=False),
    )
    payload["payload_sha256"] = sha256_bytes(canonical(payload).encode("utf-8"))
    if contains_credential(payload):
        raise RuntimeError("Dev-B manifest contains credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    return payload


def validate_dev_b_manifest(path: Path = DEV_B_MANIFEST_PATH) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_mode & 0o222:
        raise RuntimeError("immutable Dev-B manifest is required")
    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded_hash = payload.get("payload_sha256")
    unhashed = {key: value for key, value in payload.items() if key != "payload_sha256"}
    if recorded_hash != sha256_bytes(canonical(unhashed).encode("utf-8")):
        raise RuntimeError("Dev-B manifest payload hash mismatch")
    if payload.get("formal_authorized") is not False:
        raise RuntimeError("Dev-B manifest must forbid formal evaluation")
    if payload.get("algorithm_source_fingerprints") != DEV_B_ALGORITHM_SOURCE_SHA256:
        raise RuntimeError("Dev-B manifest algorithm identity mismatch")
    actual_sources = {
        relative: sha256_path(WORKTREE_ROOT / relative)
        for relative in DEV_B_ALGORITHM_SOURCE_SHA256
    }
    if actual_sources != DEV_B_ALGORITHM_SOURCE_SHA256:
        raise RuntimeError("current algorithm source differs from frozen Dev-B candidate")
    current_code_state = base._p2_code_state_sha256()
    if payload.get("provenance", {}).get("code_state_sha256") != current_code_state:
        raise RuntimeError("Dev-B manifest code-state mismatch")
    return payload


def _attempt_records(jobs: list[dict[str, Any]], phase: str) -> list[dict[str, Any]]:
    profile_by_label = {profile["label"]: profile for profile in profiles()}
    records: list[dict[str, Any]] = []
    for job in jobs:
        for episode, (task, seed) in enumerate(
            zip(job["task_ids_filter"], job["episode_seeds"], strict=True)
        ):
            records.append(
                {
                    "phase": phase,
                    "label": job["label"],
                    "formal_label": job["formal_label"],
                    "episode": episode,
                    "task_id": int(task),
                    "episode_seed": int(seed),
                    "config_fingerprint": profile_fingerprint(
                        profile_by_label[job["formal_label"]]
                    ),
                    "code_state_sha256": job["execution_record"]["code_state_sha256"],
                }
            )
    return records


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _select_gpus(admission: dict[str, Any], requested: str, job_count: int) -> list[str]:
    eligible = [str(index) for index in admission["eligible_gpu_indices"]]
    if requested == "auto":
        selected = eligible[: min(4, job_count)]
    else:
        selected = [item.strip() for item in requested.split(",") if item.strip()]
    if not selected or len(selected) != len(set(selected)):
        raise RuntimeError("selected GPU list must be nonempty and unique")
    if not set(selected) <= set(eligible):
        raise RuntimeError("one or more selected GPUs failed admission")
    return selected


def run_phase(level: str, *, gpus: str, timeout_seconds: int) -> int:
    pause_preflight()
    storage_preflight()
    if not RUN_MANIFEST_PATH.is_file() or RUN_MANIFEST_PATH.stat().st_mode & 0o222:
        raise RuntimeError("immutable run manifest is required")
    if json.loads(OFFLINE_PREFLIGHT_PATH.read_text(encoding="utf-8")).get("passed") is not True:
        raise RuntimeError("offline preflight did not pass")
    if level == DEV_A_LEVEL:
        _require_immutable_pass_artifact(
            MECHANISM_AUDIT_V2_PATH, MECHANISM_AUDIT_V2_SHA256
        )
    elif level == DEV_B_LEVEL:
        _require_immutable_pass_artifact(
            DEV_A_AUDIT_V2_PATH, DEV_A_AUDIT_V2_SHA256
        )
        validate_dev_b_manifest()
    legacy.validate_runtime_cache(
        target=RUNTIME_CACHE_DIR, manifest_path=RUNTIME_CACHE_MANIFEST_PATH
    )
    validate_credential()
    jobs = build_jobs(level)
    reference = load_gpu_reference()
    admission = admit_gpus(
        reference_peak_vram_mib=reference["reference_peak_vram_mib"]
    )
    selected = _select_gpus(admission, gpus, len(jobs))
    immediate = legacy.gpu_snapshot()
    immediate_by_index = {int(item["index"]): item for item in immediate}
    for selected_gpu in selected:
        reasons = legacy._gpu_snapshot_failure(
            immediate_by_index.get(int(selected_gpu)),
            index=int(selected_gpu),
            required_free=float(reference["required_free_vram_mib"]),
            allow_external_compute=False,
        )
        if reasons:
            raise RuntimeError(
                f"GPU {selected_gpu} failed immediate dispatch snapshot: {reasons}"
            )
    admission["dispatch_snapshot"] = immediate
    admission["selected_gpu_indices"] = [int(item) for item in selected]
    _write_json(
        RUN_ROOT / "manifests" / f"gpu_{level}_{int(time.time())}.json",
        admission,
    )
    attempts = reserve_attempts(
        ATTEMPT_LEDGER_PATH, _attempt_records(jobs, level), cap=ATTEMPT_CAP
    )
    legacy.append_ledger_event(
        ATTEMPT_LEDGER_PATH,
        {
            "record_type": "phase_dispatch",
            "phase": level,
            "attempt_ids": [int(item["attempt_id"]) for item in attempts],
            "selected_gpu_indices": [int(item) for item in selected],
        },
    )
    pause_preflight()
    with configured_base():
        return base.run_level(
            level,
            2 if level == MECHANISM_PREFLIGHT_LEVEL else 4,
            ",".join(selected),
            timeout_seconds,
            resume=False,
            cached_functions_dir=str(RUNTIME_CACHE_DIR),
            offline_vlm=False,
            gpu_poll_interval_s=30.0,
        )


def percentile(values: list[float], quantile: float) -> float | None:
    finite = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not finite:
        return None
    position = (len(finite) - 1) * float(quantile)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return finite[lower]
    fraction = position - lower
    return finite[lower] * (1.0 - fraction) + finite[upper] * fraction


def median(values: list[float]) -> float | None:
    return percentile(values, 0.5)


def artifact_inventory(root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")) if root.is_dir() else []:
        if path.is_symlink():
            raise RuntimeError(f"symlinked online artifact is forbidden: {path}")
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size_bytes": int(path.stat().st_size),
                    "sha256": sha256_path(path),
                }
            )
    return {
        "file_count": len(records),
        "total_bytes": sum(item["size_bytes"] for item in records),
        "aggregate_sha256": sha256_bytes(canonical(records).encode("utf-8")),
        "files": records,
    }


def credential_tree_audit(root: Path) -> dict[str, Any]:
    scanned: list[str] = []
    failures: list[str] = []
    suffixes = {".json", ".jsonl", ".txt", ".log", ".yaml", ".yml", ".csv", ".md", ".sh"}
    for path in sorted(root.rglob("*")) if root.is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        scanned.append(path.relative_to(root).as_posix())
        try:
            value = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            failures.append(f"unreadable text artifact {path.name}: {type(exc).__name__}")
            continue
        if contains_credential(value):
            failures.append(f"credential-like material in {path.relative_to(root)}")
    return {
        "passed": not failures,
        "scanned_file_count": len(scanned),
        "failures": failures,
    }


def _status_summary() -> dict[str, Any]:
    path = RUN_ROOT / "run_manifest.csv"
    if not path.is_file():
        return {"path": str(path), "rows": [], "gpu_hours": None}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    wall_seconds: list[float] = []
    for row in rows:
        try:
            value = float(row.get("wall_clock_s", ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            wall_seconds.append(value)
    return {
        "path": str(path),
        "sha256": sha256_path(path),
        "rows": rows,
        "gpu_hours": sum(wall_seconds) / 3600.0,
    }


def attempt_ledger_audit(expected_levels: set[str]) -> dict[str, Any]:
    state = legacy.attempt_ledger_state(ATTEMPT_LEDGER_PATH)
    failures: list[str] = []
    dispatched_ids = set(state["dispatched_attempt_ids"])
    dispatched = [
        row for row in state["attempts"] if int(row["attempt_id"]) in dispatched_ids
    ]
    expected_jobs = [
        job
        for level in expected_levels
        for job in build_jobs(level, bind=False)
    ]
    expected = {
        (job["level"], job["formal_label"], int(task), int(seed))
        for job in expected_jobs
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True)
    }
    actual = {
        (
            row.get("phase"),
            row.get("formal_label"),
            int(row.get("task_id")),
            int(row.get("episode_seed")),
        )
        for row in dispatched
        if row.get("phase") in expected_levels
    }
    identities = [
        (row.get("phase"), row.get("formal_label"), row.get("task_id"), row.get("episode_seed"))
        for row in dispatched
    ]
    if actual != expected:
        failures.append("dispatched cells do not match the frozen phase matrix")
    if len(identities) != len(set(identities)):
        failures.append("duplicate cell dispatch requires an audited recovery path")
    if state["dispatched_attempt_count"] > ATTEMPT_CAP:
        failures.append("global episode-attempt cap exceeded")
    if state["active_reservation_count"] != state["dispatched_attempt_count"]:
        failures.append("active reservation/dispatched count mismatch")
    return {
        "passed": not failures,
        "expected_cell_count": len(expected),
        "actual_phase_cell_count": len(actual),
        "global_dispatched_attempt_count": state["dispatched_attempt_count"],
        "global_reserved_attempt_count": state["reserved_attempt_count"],
        "failures": failures,
    }


def _metric_values(metrics: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for record in metrics:
        value = record.get(field)
        candidates = value if isinstance(value, list) else [value]
        for item in candidates:
            if isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item)):
                values.append(float(item))
    return values


def _mechanism_checks(
    evidence: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    metrics = evidence["metrics"]
    failures: list[str] = []
    if profile["qd_archive_mode"] == "grid_archive":
        legacy_gate = qd_audit.qd_mechanism_hard_gate(metrics, profile)
        failures.extend(str(item) for item in legacy_gate["failures"])
    elif not metrics or any(record.get("score_call_count") != 11 for record in metrics):
        failures.append("control reward-call budget mismatch")
    if profile["label"].endswith("causal_envelope_v1"):
        for index, record in enumerate(metrics):
            identity = f"{record.get('episode')}/{record.get('global_step', index)}"
            if record.get("qd_bounds_update_policy") != "causal_envelope_v1":
                failures.append(f"{identity}: candidate bounds policy mismatch")
            expected_lists = (
                "qd_bounds_xy_m_by_iter",
                "qd_bounds_checksum_by_iter",
                "qd_bounds_expanded_by_iter",
                "qd_archive_rebin_collisions_by_iter",
                "qd_archive_rebin_visit_sum_before_by_iter",
                "qd_archive_rebin_visit_sum_after_by_iter",
                "qd_raw_initial_bounds_overflow_count_by_iter",
                "qd_raw_initial_bounds_overflow_ratio_by_iter",
                "qd_descriptor_overflow_ratio_by_iter",
                "qd_partition_resolution_improvement_by_iter",
            )
            if any(not isinstance(record.get(field), list) or len(record[field]) != 10 for field in expected_lists):
                failures.append(f"{identity}: causal-envelope telemetry length mismatch")
                continue
            if any(
                int(before) != int(after)
                for before, after in zip(
                    record["qd_archive_rebin_visit_sum_before_by_iter"],
                    record["qd_archive_rebin_visit_sum_after_by_iter"],
                    strict=True,
                )
            ):
                failures.append(f"{identity}: cumulative visits not conserved")
            if record.get("qd_selected_action_fingerprint") != record.get(
                "qd_global_best_action_fingerprint"
            ):
                failures.append(f"{identity}: global-best fingerprint mismatch")
    return {"passed": not failures, "failures": list(dict.fromkeys(failures))}


def _read_metrics(job: dict[str, Any]) -> list[dict[str, Any]]:
    with configured_base():
        output = base._output_dir(job)
    path = output / "eds_eval/eds_metrics.jsonl"
    return base._read_jsonl(path) if path.is_file() else []


def _job_evidence(job: dict[str, Any]) -> dict[str, Any]:
    with configured_base():
        output = base._output_dir(job)
        validity = base._p2_job_validity(job)
    metrics = _read_metrics(job)
    outcomes = base._p2_episode_outcomes(output, int(job["episodes"]))
    parsed = base._parse_results_file(output / "results.txt")
    classifications = qd_audit._classify_failures(outcomes, metrics, output)
    telemetry = qd_audit._telemetry_counts(metrics)
    return {
        "formal_label": str(job["formal_label"]),
        "label": str(job["label"]),
        "output": str(output),
        "valid": validity["valid"],
        "failure_reason": validity["failure_reason"],
        "success_count": parsed.get("success"),
        "outcomes": {
            str(task): outcomes.get(episode, "unknown")
            for episode, task in enumerate(job["task_ids_filter"])
        },
        "failure_classification_by_task": {
            str(task): classifications.get(episode, "unknown")
            for episode, task in enumerate(job["task_ids_filter"])
        },
        "telemetry_counts": telemetry,
        "credential_audit": credential_tree_audit(output),
        "artifact_inventory": artifact_inventory(output),
        "metrics": metrics,
    }


def audit_mechanism_preflight(path: Path = MECHANISM_AUDIT_PATH) -> dict[str, Any]:
    jobs = build_jobs(MECHANISM_PREFLIGHT_LEVEL)
    evidence = [_job_evidence(job) for job in jobs]
    profile_by_label = {profile["label"]: profile for profile in profiles()}
    failures: list[str] = []
    for item in evidence:
        if item["valid"] is not True:
            failures.append(f"invalid job {item['formal_label']}: {item['failure_reason']}")
        if item["credential_audit"]["passed"] is not True:
            failures.append(f"credential audit failed for {item['formal_label']}")
        mechanism = _mechanism_checks(
            item, profile_by_label[item["formal_label"]]
        )
        item["mechanism_gate"] = mechanism
        failures.extend(
            f"{item['formal_label']}: {failure}"
            for failure in mechanism["failures"]
        )
    candidate = next(
        item for item in evidence if item["formal_label"].endswith("causal_envelope_v1")
    )
    reference = next(
        item for item in evidence if item["formal_label"] == profiles()[1]["label"]
    )
    candidate_metrics = candidate["metrics"]
    post_overflow_p95 = percentile(
        _metric_values(candidate_metrics, "qd_descriptor_overflow_ratio_by_iter"),
        0.95,
    )
    raw_overflow = _metric_values(
        candidate_metrics, "qd_raw_initial_bounds_overflow_ratio_by_iter"
    )
    if post_overflow_p95 is None or post_overflow_p95 > 0.25:
        failures.append("candidate post-envelope overflow P95 exceeds 0.25")
    if not raw_overflow:
        failures.append("candidate raw initial-bound overflow telemetry is missing")
    candidate_latency = percentile(
        _metric_values(candidate_metrics, "select_action_latency_s"), 0.95
    )
    reference_latency = percentile(
        _metric_values(reference["metrics"], "select_action_latency_s"), 0.95
    )
    latency_ratio = (
        candidate_latency / reference_latency
        if candidate_latency is not None
        and reference_latency is not None
        and reference_latency > 0
        else None
    )
    if latency_ratio is None or latency_ratio > 1.25:
        failures.append("candidate selection-latency P95 exceeds 1.25x sparse reference")
    disallowed_safety = {
        "qpos/execution error",
        "target pushed away",
        "target dropped after grasp",
        "basket displaced/collision",
        "clutter swept/wrong-object interaction",
    }
    candidate_safety = [
        category
        for category in candidate["failure_classification_by_task"].values()
        if category in disallowed_safety
    ]
    if candidate_safety:
        failures.append("candidate produced a disallowed plumbing/safety failure")
    status = _status_summary()
    preflight_gpu_hours = status["gpu_hours"]
    projected_gpu_hours = (
        preflight_gpu_hours * (14.0 / 6.0)
        if isinstance(preflight_gpu_hours, (int, float))
        else None
    )
    if projected_gpu_hours is None or projected_gpu_hours > GPU_HOUR_CAP:
        failures.append("projected frozen matrix exceeds the 48 GPU-hour cap")
    attempts = attempt_ledger_audit({MECHANISM_PREFLIGHT_LEVEL})
    if not attempts["passed"]:
        failures.extend(attempts["failures"])
    run_root_credential_audit = credential_tree_audit(RUN_ROOT)
    if not run_root_credential_audit["passed"]:
        failures.extend(run_root_credential_audit["failures"])
    payload = {
        "schema": "eds-qd-autoresearch-mechanism-preflight-audit-v1",
        "created_at": now(),
        "jobs": [
            {key: value for key, value in item.items() if key != "metrics"}
            for item in evidence
        ],
        "candidate_metric_records": len(candidate_metrics),
        "candidate_raw_initial_bounds_overflow_p95": percentile(raw_overflow, 0.95),
        "candidate_post_envelope_overflow_p95": post_overflow_p95,
        "candidate_selection_latency_p95_s": candidate_latency,
        "sparse_reference_selection_latency_p95_s": reference_latency,
        "candidate_to_sparse_selection_latency_ratio": latency_ratio,
        "candidate_disallowed_safety_failures": candidate_safety,
        "status": status,
        "projected_total_gpu_hours": projected_gpu_hours,
        "attempt_ledger": attempts,
        "run_root_credential_audit": run_root_credential_audit,
        "hard_failures": failures,
        "passed": not failures,
    }
    if contains_credential(payload):
        raise RuntimeError("mechanism audit contains credential material")
    _write_json(path, payload)
    return payload


def audit_dev_a(path: Path = DEV_A_AUDIT_PATH) -> dict[str, Any]:
    evidence = [_job_evidence(job) for job in build_jobs(DEV_A_LEVEL)]
    control = next(item for item in evidence if item["formal_label"] == profiles()[0]["label"])
    candidate = next(item for item in evidence if item["formal_label"] == profiles()[2]["label"])
    control_success = {int(task) for task, outcome in control["outcomes"].items() if outcome == "success"}
    candidate_success = {int(task) for task, outcome in candidate["outcomes"].items() if outcome == "success"}
    gained = sorted(candidate_success - control_success)
    retained = sorted(candidate_success & control_success)
    lost = sorted(control_success - candidate_success)
    failures: list[str] = []
    for item in evidence:
        if item["valid"] is not True:
            failures.append(
                f"invalid Dev-A job {item['formal_label']}: {item['failure_reason']}"
            )
        if item["credential_audit"]["passed"] is not True:
            failures.append(f"credential audit failed for {item['formal_label']}")
        mechanism = _mechanism_checks(
            item,
            next(
                profile
                for profile in profiles()
                if profile["label"] == item["formal_label"]
            ),
        )
        item["mechanism_gate"] = mechanism
        failures.extend(
            f"{item['formal_label']}: {failure}"
            for failure in mechanism["failures"]
        )
    if len(candidate_success) < len(control_success) + 1:
        failures.append("candidate success is not control +1")
    if lost:
        failures.append("candidate lost a control-success task")
    if len(gained) - len(lost) < 1:
        failures.append("gained-minus-lost is below one")
    resolution_by_task: dict[str, float | None] = {}
    for task in DEV_TASKS:
        values = [
            value
            for record in candidate["metrics"]
            if record.get("task_id") == task
            for value in record.get("qd_partition_resolution_improvement_by_iter", [])
            if isinstance(value, (int, float)) and math.isfinite(float(value))
        ]
        resolution_by_task[str(task)] = median([float(value) for value in values])
    mechanism_support = sum(
        value is not None and value >= 0.20 for value in resolution_by_task.values()
    )
    if mechanism_support < 3:
        failures.append("online resolution support is below 3/4 tasks")
    post_overflow_p95 = percentile(
        _metric_values(candidate["metrics"], "qd_descriptor_overflow_ratio_by_iter"),
        0.95,
    )
    raw_overflow_p95 = percentile(
        _metric_values(
            candidate["metrics"], "qd_raw_initial_bounds_overflow_ratio_by_iter"
        ),
        0.95,
    )
    if post_overflow_p95 is None or post_overflow_p95 > 0.25:
        failures.append("candidate post-envelope overflow P95 exceeds 0.25")
    if raw_overflow_p95 is None:
        failures.append("candidate raw initial-bound overflow telemetry is missing")
    control_safety = control["failure_classification_by_task"]
    candidate_safety = candidate["failure_classification_by_task"]
    collision_categories = {
        "target pushed away",
        "target dropped after grasp",
        "basket displaced/collision",
        "clutter swept/wrong-object interaction",
    }
    control_collision_count = sum(
        value in collision_categories for value in control_safety.values()
    )
    candidate_collision_count = sum(
        value in collision_categories for value in candidate_safety.values()
    )
    candidate_qpos_count = sum(
        value == "qpos/execution error" for value in candidate_safety.values()
    )
    if candidate_collision_count > control_collision_count:
        failures.append("candidate collision/push/drop/wrong-object count exceeds control")
    if candidate_qpos_count or candidate["telemetry_counts"]["execution_qpos_error_episodes"]:
        failures.append("candidate has a qpos/execution error")
    archive_by_task: dict[str, dict[str, float | None]] = {}
    for task in DEV_TASKS:
        records = [
            record
            for record in candidate["metrics"]
            if record.get("task_id") == task
        ]
        occupied_ratios: list[float] = []
        spreads: list[float] = []
        for record in records:
            occupied = record.get("qd_occupied_cells_by_iter")
            initial_occupied = record.get("qd_initial_occupied_cells")
            if (
                isinstance(occupied, list)
                and occupied
                and isinstance(occupied[-1], (int, float))
                and isinstance(initial_occupied, (int, float))
                and float(initial_occupied) > 0
            ):
                occupied_ratios.append(float(occupied[-1]) / float(initial_occupied))
            spread = record.get("qd_archive_endpoint_xy_spread_m_by_iter")
            if isinstance(spread, list) and spread and isinstance(spread[-1], (int, float)):
                spreads.append(float(spread[-1]))
        archive_by_task[str(task)] = {
            "final_occupied_mode_ratio_median": median(occupied_ratios),
            "archive_endpoint_spread_median_m": median(spreads),
        }
        if (
            archive_by_task[str(task)]["final_occupied_mode_ratio_median"] is None
            or archive_by_task[str(task)]["final_occupied_mode_ratio_median"] <= 0
            or archive_by_task[str(task)]["archive_endpoint_spread_median_m"] is None
            or archive_by_task[str(task)]["archive_endpoint_spread_median_m"] <= 0
        ):
            failures.append(f"task {task} archive mode/spread is nonfinite or collapsed")
    mechanism_audit = json.loads(MECHANISM_AUDIT_PATH.read_text(encoding="utf-8"))
    if mechanism_audit.get("passed") is not True:
        failures.append("mechanism preflight audit is not PASS")
    candidate_latency = percentile(
        _metric_values(candidate["metrics"], "select_action_latency_s"), 0.95
    )
    reference_latency = mechanism_audit.get("sparse_reference_selection_latency_p95_s")
    latency_ratio = (
        candidate_latency / float(reference_latency)
        if candidate_latency is not None
        and isinstance(reference_latency, (int, float))
        and float(reference_latency) > 0
        else None
    )
    if latency_ratio is None or latency_ratio > 1.25:
        failures.append("candidate Dev-A selection latency exceeds sparse preflight 1.25x")
    status = _status_summary()
    preflight_gpu_hours = mechanism_audit.get("status", {}).get("gpu_hours")
    total_gpu_hours = (
        float(preflight_gpu_hours) + float(status["gpu_hours"])
        if isinstance(preflight_gpu_hours, (int, float))
        and isinstance(status["gpu_hours"], (int, float))
        else None
    )
    if total_gpu_hours is None or total_gpu_hours > GPU_HOUR_CAP:
        failures.append("actual cumulative GPU-hours exceed or cannot verify 48-hour cap")
    attempts = attempt_ledger_audit({MECHANISM_PREFLIGHT_LEVEL, DEV_A_LEVEL})
    if not attempts["passed"]:
        failures.extend(attempts["failures"])
    run_root_credential_audit = credential_tree_audit(RUN_ROOT)
    if not run_root_credential_audit["passed"]:
        failures.extend(run_root_credential_audit["failures"])
    payload = {
        "schema": "eds-qd-autoresearch-dev-a-audit-v1",
        "created_at": now(),
        "jobs": [{key: value for key, value in item.items() if key != "metrics"} for item in evidence],
        "task_matrix": {
            "control_success_tasks": sorted(control_success),
            "candidate_success_tasks": sorted(candidate_success),
            "gained": gained,
            "retained": retained,
            "lost": lost,
        },
        "resolution_by_task": resolution_by_task,
        "mechanism_support_task_count": mechanism_support,
        "candidate_raw_initial_bounds_overflow_p95": raw_overflow_p95,
        "candidate_post_envelope_overflow_p95": post_overflow_p95,
        "archive_by_task": archive_by_task,
        "safety": {
            "control_failure_classification_by_task": control_safety,
            "candidate_failure_classification_by_task": candidate_safety,
            "control_collision_push_drop_wrong_object_count": control_collision_count,
            "candidate_collision_push_drop_wrong_object_count": candidate_collision_count,
            "candidate_qpos_error_count": candidate_qpos_count,
        },
        "candidate_selection_latency_p95_s": candidate_latency,
        "sparse_preflight_selection_latency_p95_s": reference_latency,
        "candidate_to_sparse_selection_latency_ratio": latency_ratio,
        "status": status,
        "cumulative_gpu_hours": total_gpu_hours,
        "attempt_ledger": attempts,
        "run_root_credential_audit": run_root_credential_audit,
        "hard_failures": failures,
        "passed": not failures,
    }
    if contains_credential(payload):
        raise RuntimeError("Dev-A audit contains credential material")
    _write_json(path, payload)
    return payload


def dev_b_target_gate(
    *,
    control_success: set[int],
    candidate_success: set[int],
    dev_a_task_matrix: dict[str, Any],
) -> dict[str, Any]:
    gained = sorted(candidate_success - control_success)
    retained = sorted(candidate_success & control_success)
    lost = sorted(control_success - candidate_success)
    pooled_gained_minus_lost = (
        len(dev_a_task_matrix.get("gained", []))
        - len(dev_a_task_matrix.get("lost", []))
        + len(gained)
        - len(lost)
    )
    failures: list[str] = []
    if len(candidate_success) < len(control_success) + 1:
        failures.append("candidate success is not control +1")
    if lost:
        failures.append("candidate lost a control-success task")
    if len(gained) - len(lost) < 1:
        failures.append("Dev-B gained-minus-lost is below one")
    if pooled_gained_minus_lost < 1:
        failures.append("pooled Dev-A plus Dev-B gained-minus-lost is below one")
    return {
        "passed": not failures,
        "gained": gained,
        "retained": retained,
        "lost": lost,
        "pooled_gained_minus_lost": pooled_gained_minus_lost,
        "failures": failures,
    }


def audit_dev_b(path: Path = DEV_B_AUDIT_PATH) -> dict[str, Any]:
    validate_dev_b_manifest()
    mechanism_audit = _require_immutable_pass_artifact(
        MECHANISM_AUDIT_V2_PATH, MECHANISM_AUDIT_V2_SHA256
    )
    dev_a_audit = _require_immutable_pass_artifact(
        DEV_A_AUDIT_V2_PATH, DEV_A_AUDIT_V2_SHA256
    )
    evidence = [_job_evidence(job) for job in build_jobs(DEV_B_LEVEL)]
    control = next(item for item in evidence if item["formal_label"] == profiles()[0]["label"])
    candidate = next(item for item in evidence if item["formal_label"] == profiles()[2]["label"])
    control_success = {
        int(task) for task, outcome in control["outcomes"].items() if outcome == "success"
    }
    candidate_success = {
        int(task) for task, outcome in candidate["outcomes"].items() if outcome == "success"
    }
    target_gate = dev_b_target_gate(
        control_success=control_success,
        candidate_success=candidate_success,
        dev_a_task_matrix=dev_a_audit["task_matrix"],
    )
    failures = list(target_gate["failures"])
    for item in evidence:
        if item["valid"] is not True:
            failures.append(
                f"invalid Dev-B job {item['formal_label']}: {item['failure_reason']}"
            )
        if item["credential_audit"]["passed"] is not True:
            failures.append(f"credential audit failed for {item['formal_label']}")
        mechanism = _mechanism_checks(
            item,
            next(
                profile
                for profile in profiles()
                if profile["label"] == item["formal_label"]
            ),
        )
        item["mechanism_gate"] = mechanism
        failures.extend(
            f"{item['formal_label']}: {failure}"
            for failure in mechanism["failures"]
        )

    resolution_by_task: dict[str, float | None] = {}
    for task in DEV_TASKS:
        values = [
            float(value)
            for record in candidate["metrics"]
            if record.get("task_id") == task
            for value in record.get("qd_partition_resolution_improvement_by_iter", [])
            if isinstance(value, (int, float)) and math.isfinite(float(value))
        ]
        resolution_by_task[str(task)] = median(values)
    mechanism_support = sum(
        value is not None and value >= 0.20 for value in resolution_by_task.values()
    )
    if mechanism_support < 3:
        failures.append("online resolution support is below 3/4 Dev-B tasks")
    post_overflow_p95 = percentile(
        _metric_values(candidate["metrics"], "qd_descriptor_overflow_ratio_by_iter"),
        0.95,
    )
    raw_overflow_p95 = percentile(
        _metric_values(
            candidate["metrics"], "qd_raw_initial_bounds_overflow_ratio_by_iter"
        ),
        0.95,
    )
    if post_overflow_p95 is None or post_overflow_p95 > 0.25:
        failures.append("candidate post-envelope overflow P95 exceeds 0.25")
    if raw_overflow_p95 is None:
        failures.append("candidate raw initial-bound overflow telemetry is missing")

    control_safety = control["failure_classification_by_task"]
    candidate_safety = candidate["failure_classification_by_task"]
    collision_categories = {
        "target pushed away",
        "target dropped after grasp",
        "basket displaced/collision",
        "clutter swept/wrong-object interaction",
    }
    control_collision_count = sum(
        value in collision_categories for value in control_safety.values()
    )
    candidate_collision_count = sum(
        value in collision_categories for value in candidate_safety.values()
    )
    candidate_qpos_count = sum(
        value == "qpos/execution error" for value in candidate_safety.values()
    )
    if candidate_collision_count > control_collision_count:
        failures.append("candidate collision/push/drop/wrong-object count exceeds control")
    if candidate_qpos_count or candidate["telemetry_counts"]["execution_qpos_error_episodes"]:
        failures.append("candidate has a qpos/execution error")

    archive_by_task: dict[str, dict[str, float | None]] = {}
    for task in DEV_TASKS:
        records = [
            record for record in candidate["metrics"] if record.get("task_id") == task
        ]
        occupied_ratios: list[float] = []
        spreads: list[float] = []
        for record in records:
            occupied = record.get("qd_occupied_cells_by_iter")
            initial_occupied = record.get("qd_initial_occupied_cells")
            if (
                isinstance(occupied, list)
                and occupied
                and isinstance(occupied[-1], (int, float))
                and isinstance(initial_occupied, (int, float))
                and float(initial_occupied) > 0
            ):
                occupied_ratios.append(float(occupied[-1]) / float(initial_occupied))
            spread = record.get("qd_archive_endpoint_xy_spread_m_by_iter")
            if isinstance(spread, list) and spread and isinstance(spread[-1], (int, float)):
                spreads.append(float(spread[-1]))
        archive_by_task[str(task)] = {
            "final_occupied_mode_ratio_median": median(occupied_ratios),
            "archive_endpoint_spread_median_m": median(spreads),
        }
        if (
            archive_by_task[str(task)]["final_occupied_mode_ratio_median"] is None
            or archive_by_task[str(task)]["final_occupied_mode_ratio_median"] <= 0
            or archive_by_task[str(task)]["archive_endpoint_spread_median_m"] is None
            or archive_by_task[str(task)]["archive_endpoint_spread_median_m"] <= 0
        ):
            failures.append(f"task {task} archive mode/spread is nonfinite or collapsed")

    candidate_latency = percentile(
        _metric_values(candidate["metrics"], "select_action_latency_s"), 0.95
    )
    reference_latency = mechanism_audit.get("sparse_reference_selection_latency_p95_s")
    latency_ratio = (
        candidate_latency / float(reference_latency)
        if candidate_latency is not None
        and isinstance(reference_latency, (int, float))
        and float(reference_latency) > 0
        else None
    )
    if latency_ratio is None or latency_ratio > 1.25:
        failures.append("candidate Dev-B selection latency exceeds sparse preflight 1.25x")

    status = _status_summary()
    component_gpu_hours = {
        "pre_episode_incident": PRE_EPISODE_INCIDENT_GPU_HOURS,
        "mechanism_preflight": mechanism_audit.get("status", {}).get("gpu_hours"),
        "dev_a": dev_a_audit.get("status", {}).get("gpu_hours"),
        "dev_b": status.get("gpu_hours"),
    }
    cumulative_gpu_hours = (
        sum(float(value) for value in component_gpu_hours.values())
        if all(isinstance(value, (int, float)) for value in component_gpu_hours.values())
        else None
    )
    if cumulative_gpu_hours is None or cumulative_gpu_hours > GPU_HOUR_CAP:
        failures.append("actual cumulative GPU-hours exceed or cannot verify 48-hour cap")
    attempts = attempt_ledger_audit(
        {MECHANISM_PREFLIGHT_LEVEL, DEV_A_LEVEL, DEV_B_LEVEL}
    )
    if not attempts["passed"]:
        failures.extend(attempts["failures"])
    run_root_credential_audit = credential_tree_audit(RUN_ROOT)
    if not run_root_credential_audit["passed"]:
        failures.extend(run_root_credential_audit["failures"])
    payload = {
        "schema": "eds-qd-autoresearch-dev-b-audit-v1",
        "created_at": now(),
        "jobs": [
            {key: value for key, value in item.items() if key != "metrics"}
            for item in evidence
        ],
        "task_matrix": {
            "control_success_tasks": sorted(control_success),
            "candidate_success_tasks": sorted(candidate_success),
            **{key: target_gate[key] for key in ("gained", "retained", "lost")},
        },
        "target_gate": target_gate,
        "dev_a_task_matrix": dev_a_audit["task_matrix"],
        "resolution_by_task": resolution_by_task,
        "mechanism_support_task_count": mechanism_support,
        "candidate_raw_initial_bounds_overflow_p95": raw_overflow_p95,
        "candidate_post_envelope_overflow_p95": post_overflow_p95,
        "archive_by_task": archive_by_task,
        "safety": {
            "control_failure_classification_by_task": control_safety,
            "candidate_failure_classification_by_task": candidate_safety,
            "control_collision_push_drop_wrong_object_count": control_collision_count,
            "candidate_collision_push_drop_wrong_object_count": candidate_collision_count,
            "candidate_qpos_error_count": candidate_qpos_count,
        },
        "candidate_selection_latency_p95_s": candidate_latency,
        "sparse_preflight_selection_latency_p95_s": reference_latency,
        "candidate_to_sparse_selection_latency_ratio": latency_ratio,
        "status": status,
        "gpu_hour_components": component_gpu_hours,
        "cumulative_gpu_hours": cumulative_gpu_hours,
        "attempt_ledger": attempts,
        "run_root_credential_audit": run_root_credential_audit,
        "hard_failures": list(dict.fromkeys(failures)),
        "passed": not failures,
    }
    if contains_credential(payload):
        raise RuntimeError("Dev-B audit contains credential material")
    _write_json(path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("storage-preflight")
    subparsers.add_parser("offline-preflight")
    subparsers.add_parser("freeze-manifest")
    subparsers.add_parser("freeze-dev-b-manifest")
    subparsers.add_parser("matrix")
    for name in ("run-mechanism-preflight", "run-dev-a", "run-dev-b"):
        command = subparsers.add_parser(name)
        command.add_argument("--gpus", default="auto")
        command.add_argument("--timeout-seconds", type=int, default=28800)
    subparsers.add_parser("audit-mechanism-preflight")
    subparsers.add_parser("audit-dev-a")
    subparsers.add_parser("audit-dev-b")
    args = parser.parse_args()
    if args.command == "storage-preflight":
        print(json.dumps(storage_preflight(), indent=2))
        return 0
    if args.command == "offline-preflight":
        result = offline_preflight()
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    if args.command == "freeze-manifest":
        print(json.dumps(freeze_manifest(), indent=2))
        return 0
    if args.command == "freeze-dev-b-manifest":
        print(json.dumps(freeze_dev_b_manifest(), indent=2))
        return 0
    if args.command == "matrix":
        print(
            json.dumps(
                {
                    "mechanism_preflight": build_jobs(MECHANISM_PREFLIGHT_LEVEL, bind=False),
                    "dev_a": build_jobs(DEV_A_LEVEL, bind=False),
                    "dev_b": build_jobs(DEV_B_LEVEL, bind=False),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "run-mechanism-preflight":
        return run_phase(
            MECHANISM_PREFLIGHT_LEVEL,
            gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "run-dev-a":
        return run_phase(
            DEV_A_LEVEL,
            gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "run-dev-b":
        return run_phase(
            DEV_B_LEVEL,
            gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "audit-mechanism-preflight":
        result = audit_mechanism_preflight()
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    if args.command == "audit-dev-a":
        result = audit_dev_a()
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    result = audit_dev_b()
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
