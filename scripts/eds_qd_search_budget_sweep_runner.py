#!/usr/bin/env python3
"""Frozen 18-job EDS-QD search-budget sweep runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = Path(__file__).resolve().parents[1]
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_quality_diversity_runner as legacy
import rdt_eds_eval_runner as base


FORMAL_LEVEL = "eds_qd_search_budget_sweep"
PREFLIGHT_LEVEL = "__disabled_no_preflight__"
NAMESPACE = "search_budget_sweep_20260808"
ROOT_OUTPUT_LINK = WORKTREE_ROOT / "outputs"
LEGACY_OUTPUT_TARGET = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs"
)
EXPERIMENT_ROOT = LEGACY_OUTPUT_TARGET / NAMESPACE
OUTPUT_LINK = ROOT_OUTPUT_LINK / NAMESPACE / "outputs"
OUTPUT_TARGET = EXPERIMENT_ROOT / "output_store"
ALLOWED_STORAGE_PREFIX = Path("/mnt/data/shared2/zhuoli/vla-pilot-plus-plus")
MIN_FREE_BYTES = 50 * 1024**3

DESIGN_PATH = (
    WORKTREE_ROOT
    / "docs/01_specs/2026-08-08-eds-qd-search-budget-parameter-sweep-design.md"
)
RUN_MANIFEST_PATH = EXPERIMENT_ROOT / "manifests/run_manifest.json"
ATTEMPT_LEDGER_PATH = EXPERIMENT_ROOT / "manifests/episode_attempt_ledger.jsonl"
NO_OP_AUDIT_PATH = EXPERIMENT_ROOT / "analysis/num_elites_no_op_audit.json"
GPU_REFERENCE_PATH = legacy.GPU_REFERENCE_PATH
RUNTIME_CACHE_DIR = legacy.RUNTIME_CACHE_DIR
RUNTIME_CACHE_MANIFEST_PATH = legacy.RUNTIME_CACHE_MANIFEST_PATH

EPISODE_SEEDS = list(legacy.EPISODE_SEEDS)
FAMILIES = ("uniform_expand20", "sparse_primary")
POPULATION_SIZES = (32, 48, 64)
CEM_ITERS = (15, 20, 25)
NUM_ELITES = 16
FORMAL_JOB_COUNT = 18
FORMAL_EPISODE_COUNT = 180
RECOVERY_ATTEMPT_LIMIT = 20
ATTEMPT_CAP = 200
MAX_CONCURRENCY = 4
ALLOWED_GPU_INDICES = tuple(range(8))
BASELINE_POPULATION_SIZE = 16
MAX_POPULATION_SIZE = max(POPULATION_SIZES)
HISTORICAL_REFERENCE_PEAK_VRAM_MIB = 17921.0
SCALED_REFERENCE_PEAK_VRAM_MIB = (
    HISTORICAL_REFERENCE_PEAK_VRAM_MIB
    * MAX_POPULATION_SIZE
    / BASELINE_POPULATION_SIZE
)

QD_CONFIG_FIELDS = tuple(legacy.QD_CONFIG_FIELDS)
_BASE_BUILD_MAIN_COMMAND = legacy._BASE_BUILD_MAIN_COMMAND
_BASE_STAGE_DIR = legacy._BASE_STAGE_DIR


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


def expected_evaluations(population_size: int, cem_iters: int) -> int:
    if (
        isinstance(population_size, bool)
        or not isinstance(population_size, int)
        or population_size <= 0
    ):
        raise ValueError("population_size must be a positive integer")
    if isinstance(cem_iters, bool) or not isinstance(cem_iters, int) or cem_iters <= 0:
        raise ValueError("cem_iters must be a positive integer")
    return population_size * (cem_iters + 1)


def _profile(
    family: str, population_size: int, cem_iters: int
) -> dict[str, object]:
    if family not in FAMILIES:
        raise ValueError(f"unsupported family: {family}")
    profile = dict(legacy.COMMON_PROFILE)
    profile.pop("p2_render_gpu_index", None)
    label = f"eds_qd_{family}_p{population_size}_k{cem_iters}"
    profile.update(
        {
            "method": label,
            "label": label,
            "role": "search_budget_sweep",
            "family": family,
            "population_size": population_size,
            "cem_iters": cem_iters,
            "num_elites": NUM_ELITES,
            "use_cem": False,
        }
    )
    if family == "uniform_expand20":
        profile.update(
            {
                "qd_parent_sampling": "uniform_cells",
                "qd_bounds_expand_fraction": 0.20,
            }
        )
    else:
        profile.update(
            {
                "qd_parent_sampling": "sparse_priority",
                "qd_sparse_exponent": 1.0,
                "qd_bounds_expand_fraction": 0.10,
            }
        )
    return profile


def formal_profiles() -> list[dict[str, object]]:
    profiles = [
        _profile(family, population_size, cem_iters)
        for family in FAMILIES
        for population_size in POPULATION_SIZES
        for cem_iters in CEM_ITERS
    ]
    identities = {
        (
            str(profile["family"]),
            int(profile["population_size"]),
            int(profile["cem_iters"]),
        )
        for profile in profiles
    }
    expected = {
        (family, population_size, cem_iters)
        for family in FAMILIES
        for population_size in POPULATION_SIZES
        for cem_iters in CEM_ITERS
    }
    if len(profiles) != FORMAL_JOB_COUNT or identities != expected:
        raise AssertionError("formal matrix is not the frozen 2x3x3 sweep")
    if len({str(profile["label"]) for profile in profiles}) != FORMAL_JOB_COUNT:
        raise AssertionError("formal sweep labels are not unique")
    if any(
        profile["num_elites"] != NUM_ELITES or profile["use_cem"] is not False
        for profile in profiles
    ):
        raise AssertionError("num_elites/use_cem changed outside the frozen design")
    return profiles


def _stage_dir(level: object) -> str:
    if str(level) == FORMAL_LEVEL:
        return "formal"
    return _BASE_STAGE_DIR(level)


def _build_main_command(job, *args, **kwargs):
    with configured_base():
        command = _BASE_BUILD_MAIN_COMMAND(job, *args, **kwargs)
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
        for field in QD_CONFIG_FIELDS
    )
    expected = {
        "main.eds_config.population_size": str(job["population_size"]),
        "main.eds_config.cem_iters": str(job["cem_iters"]),
        "main.eds_config.num_elites": str(NUM_ELITES),
        "main.eds_config.use_cem": "false",
    }
    assignments = {
        token.split("=", 1)[0].lstrip("+"): token.split("=", 1)[1]
        for token in command
        if "=" in token
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
        raise ValueError("search-budget sweep supports only its frozen 18-job formal matrix")
    jobs = []
    for profile in formal_profiles():
        job = {
            **profile,
            "job_id": f"{FORMAL_LEVEL}_libero_object_swap_{profile['label']}",
            "level": FORMAL_LEVEL,
            "suite": "libero_object_swap",
            "episodes": 10,
            "task_ids_filter": list(range(10)),
            "episode_seeds": list(EPISODE_SEEDS),
            "expected_evaluations_per_complete_chunk": expected_evaluations(
                int(profile["population_size"]), int(profile["cem_iters"])
            ),
        }
        jobs.append(_bind_job(job))
    if len(jobs) != FORMAL_JOB_COUNT:
        raise AssertionError("formal job count changed")
    return jobs


def initialize_storage() -> dict[str, object]:
    if not ROOT_OUTPUT_LINK.is_symlink() or not os.path.isabs(
        os.readlink(ROOT_OUTPUT_LINK)
    ):
        raise RuntimeError("worktree outputs must remain the approved absolute symlink")
    try:
        root_target = ROOT_OUTPUT_LINK.resolve(strict=True)
        expected_root = LEGACY_OUTPUT_TARGET.resolve(strict=True)
        prefix = ALLOWED_STORAGE_PREFIX.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"shared2 output root is invalid: {exc}") from exc
    if root_target != expected_root:
        raise RuntimeError(f"worktree outputs target mismatch: {root_target} != {expected_root}")
    try:
        root_target.relative_to(prefix)
    except ValueError as exc:
        raise RuntimeError("output root is outside the approved shared2 prefix") from exc
    EXPERIMENT_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_TARGET.mkdir(parents=True, exist_ok=True)
    if OUTPUT_LINK.exists() and not OUTPUT_LINK.is_symlink():
        raise RuntimeError("sweep output link exists but is not a symlink")
    if not OUTPUT_LINK.exists():
        OUTPUT_LINK.symlink_to(OUTPUT_TARGET.absolute(), target_is_directory=True)
    return storage_preflight()


def storage_preflight() -> dict[str, object]:
    if not ROOT_OUTPUT_LINK.is_symlink() or not OUTPUT_LINK.is_symlink():
        raise RuntimeError("root and namespace outputs must both be symlinks")
    try:
        root_target = ROOT_OUTPUT_LINK.resolve(strict=True)
        output_target = OUTPUT_LINK.resolve(strict=True)
        expected_root = LEGACY_OUTPUT_TARGET.resolve(strict=True)
        expected_output = OUTPUT_TARGET.resolve(strict=True)
        prefix = ALLOWED_STORAGE_PREFIX.resolve(strict=True)
        namespace = EXPERIMENT_ROOT.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"sweep storage is invalid: {exc}") from exc
    if root_target != expected_root or output_target != expected_output:
        raise RuntimeError("sweep storage symlink target mismatch")
    for path in (namespace, output_target):
        try:
            path.relative_to(prefix)
        except ValueError as exc:
            raise RuntimeError("sweep storage is outside shared2") from exc
    if shutil.disk_usage(namespace).free < MIN_FREE_BYTES:
        raise RuntimeError("shared2 has less than the required 50 GiB free")
    probe = OUTPUT_LINK / f".storage_probe_{os.getpid()}"
    with probe.open("x", encoding="utf-8") as handle:
        handle.write("ok\n")
    try:
        probe.resolve(strict=True).relative_to(output_target)
    finally:
        probe.unlink(missing_ok=True)
    return {
        "namespace": NAMESPACE,
        "namespace_realpath": str(namespace),
        "root_outputs_link": str(ROOT_OUTPUT_LINK),
        "root_outputs_link_value": os.readlink(ROOT_OUTPUT_LINK),
        "outputs_link": str(OUTPUT_LINK),
        "outputs_link_value": os.readlink(OUTPUT_LINK),
        "outputs_target": str(output_target),
    }


def load_gpu_reference() -> dict[str, object]:
    payload = legacy.load_gpu_reference()
    historical = float(payload["reference_peak_vram_mib"])
    scaled = historical * MAX_POPULATION_SIZE / BASELINE_POPULATION_SIZE
    required = max(scaled * 1.25, scaled + 4096.0)
    return {
        **payload,
        "historical_reference_peak_vram_mib": historical,
        "population_scaling_factor": MAX_POPULATION_SIZE
        / BASELINE_POPULATION_SIZE,
        "reference_peak_vram_mib": scaled,
        "required_free_vram_mib": required,
        "conservative_linear_population_scaling": True,
    }


def admit_gpus(
    *,
    reference_peak_vram_mib: float,
    snapshot_fn: Callable[[], list[dict[str, object]]] = legacy.gpu_snapshot,
    wait_fn: Callable[[float], None] = time.sleep,
    wait_seconds: float = 2.0,
) -> dict[str, object]:
    result = legacy.admit_gpus(
        reference_peak_vram_mib=reference_peak_vram_mib,
        snapshot_fn=snapshot_fn,
        wait_fn=wait_fn,
        wait_seconds=wait_seconds,
        pinned_gpu_index=None,
        allow_external_compute=True,
    )
    result["max_concurrency"] = min(
        MAX_CONCURRENCY, len(result["eligible_gpu_indices"])
    )
    result["allowed_gpu_indices"] = list(ALLOWED_GPU_INDICES)
    return result


def _selected_gpus(admission: dict[str, object], requested: str) -> list[str]:
    eligible = {int(value) for value in admission["eligible_gpu_indices"]}
    if requested != "auto":
        selected = [item.strip() for item in requested.split(",") if item.strip()]
        if not selected or len(selected) != len(set(selected)):
            raise RuntimeError("requested GPUs must be a nonempty unique list")
        if len(selected) > MAX_CONCURRENCY:
            raise RuntimeError(f"at most {MAX_CONCURRENCY} sweep workers are allowed")
        if not {int(item) for item in selected} <= eligible:
            raise RuntimeError("one or more requested GPUs failed admission")
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
            float(latest.get(index, {}).get("utilization_percent", math.inf)),
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
        (item for item in legacy.gpu_snapshot() if int(item["index"]) == index),
        None,
    )
    reasons = legacy._gpu_snapshot_failure(
        device,
        index=index,
        required_free=float(reference["required_free_vram_mib"]),
        allow_external_compute=True,
    )
    return ("busy", "; ".join(reasons)) if reasons else ("idle", "admitted")


def _write_gpu_admission(phase: str, payload: dict[str, object]) -> Path:
    path = EXPERIMENT_ROOT / "manifests" / f"gpu_{phase}_{int(time.time())}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def configure_base() -> None:
    base.P2_OUTPUT_ROOT = OUTPUT_LINK
    base.P2_STATUS_ROOT = OUTPUT_LINK
    base.P2_EXPECTED_OUTPUT_TARGET = OUTPUT_TARGET
    base.P2_ALLOWED_OUTPUT_PREFIX = ALLOWED_STORAGE_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | {FORMAL_LEVEL}
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
    jobs: list[dict[str, object]], phase: str = "formal"
) -> list[dict[str, object]]:
    return legacy._attempt_records_for_jobs(jobs, phase)


def _profile_fingerprint(profile: dict[str, object]) -> str:
    excluded = {"method", "role", "job_id", "level", "formal_label"}
    payload = {
        "profile": {
            key: value for key, value in profile.items() if key not in excluded
        },
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "tasks": list(range(10)),
        "episode_seeds": EPISODE_SEEDS,
    }
    return _sha256_bytes(_canonical(payload).encode("utf-8"))


def num_elites_no_op_audit(path: Path = NO_OP_AUDIT_PATH) -> dict[str, object]:
    source_path = WORKTREE_ROOT / "core/rdt_policy_steer.py"
    source = source_path.read_text(encoding="utf-8")
    profiles = formal_profiles()
    checks = {
        "all_profiles_use_cem_false": all(
            profile["use_cem"] is False for profile in profiles
        ),
        "all_profiles_enable_qd_archive": all(
            profile["qd_archive_mode"] == "grid_archive" for profile in profiles
        ),
        "all_profiles_fix_num_elites_16": all(
            profile["num_elites"] == NUM_ELITES for profile in profiles
        ),
        "qd_branch_uses_empty_elite_indices": (
            "if qd_archive is not None:" in source
            and "elite_indices=torch.empty(" in source
        ),
        "num_elites_is_guarded_by_use_cem": (
            "if cfg.use_cem:" in source
            and "cem_elites = torch.argsort(costs)[: cfg.num_elites]" in source
        ),
    }
    payload = {
        "schema": "eds-qd-num-elites-no-op-audit-v1",
        "created_at": _now(),
        "passed": all(checks.values()),
        "checks": checks,
        "behavioral_test": (
            "tests/test_rdt_steer.py::"
            "test_qd_loop_num_elites_is_bitwise_no_op_when_cem_is_disabled"
        ),
        "source_path": str(source_path),
        "source_sha256": _sha256_file(source_path),
        "num_elites_values_audited": [16, 32],
        "formal_num_elites": NUM_ELITES,
        "libero_episode_attempts_consumed": 0,
    }
    if not payload["passed"]:
        raise RuntimeError("num_elites no-op static audit failed")
    if _contains_credential(payload):
        raise RuntimeError("num_elites audit contains credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return payload


def current_provenance() -> dict[str, object]:
    status = subprocess.check_output(
        ["git", "status", "--short"], cwd=WORKTREE_ROOT, text=True
    ).splitlines()
    if status:
        raise RuntimeError(
            "sweep worktree must be committed before manifest freeze: "
            + "; ".join(status)
        )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=WORKTREE_ROOT,
        text=True,
    ).strip()
    if branch != "exp/eds-quality-diversity":
        raise RuntimeError(f"unexpected branch: {branch}")
    return {
        "branch": branch,
        "worktree_realpath": str(WORKTREE_ROOT.resolve(strict=True)),
        "code_commit": head,
        "code_state_sha256": base._p2_code_state_sha256(),
        "prior_qd_commit": "5b0898e53d5b9e16200c17479a74746071215787",
    }


def freeze_run_manifest(
    *,
    provenance: dict[str, object],
    storage: dict[str, object],
    gpu_reference: dict[str, object],
) -> dict[str, object]:
    if RUN_MANIFEST_PATH.exists() or RUN_MANIFEST_PATH.is_symlink():
        raise FileExistsError(RUN_MANIFEST_PATH)
    no_op = json.loads(NO_OP_AUDIT_PATH.read_text(encoding="utf-8"))
    if no_op.get("passed") is not True:
        raise RuntimeError("num_elites no-op audit has not passed")
    profiles = formal_profiles()
    payload = {
        "schema": "eds-qd-search-budget-sweep-run-manifest-v1",
        "created_at": _now(),
        "design_path": str(DESIGN_PATH),
        "design_sha256": _sha256_file(DESIGN_PATH),
        "design_status": "Approved design",
        "provenance": provenance,
        "storage": storage,
        "gpu_reference": gpu_reference,
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "task_ids": list(range(10)),
        "episode_seeds": list(EPISODE_SEEDS),
        "root_seed": 0,
        "max_episode_steps": 720,
        "stage_recognition": True,
        "gemini_grounding": False,
        "formal_profiles": [
            {**profile, "profile_fingerprint": _profile_fingerprint(profile)}
            for profile in profiles
        ],
        "formal_job_count": FORMAL_JOB_COUNT,
        "formal_episode_count": FORMAL_EPISODE_COUNT,
        "preflight_episode_count": 0,
        "recovery_attempt_limit": RECOVERY_ATTEMPT_LIMIT,
        "attempt_cap": ATTEMPT_CAP,
        "allowed_gpu_indices": list(ALLOWED_GPU_INDICES),
        "max_concurrency": MAX_CONCURRENCY,
        "external_compute_colocation_authorized": True,
        "num_elites_no_op_audit": {
            "path": str(NO_OP_AUDIT_PATH),
            "sha256": _sha256_file(NO_OP_AUDIT_PATH),
        },
        "ranking_order": [
            "success_count_desc",
            "historical_family_paired_gained_minus_lost_desc",
            "candidates_per_success_asc",
            "selection_latency_p95_asc",
            "replacement_active_ratio_desc",
            "archive_best_reward_delta_desc",
            "job_label_lexical",
        ],
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
    legacy.validate_runtime_cache()
    legacy.validate_runtime_credential()
    if not base._poe_healthcheck():
        raise RuntimeError("Poe Stage Recognition health check failed")
    reference = load_gpu_reference()
    admission = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"])
    )
    selected = _selected_gpus(admission, requested_gpus)
    if not selected:
        raise RuntimeError("no GPU in 0..7 passed sweep admission")
    admission["selected_gpu_indices"] = [int(item) for item in selected]
    _write_gpu_admission("formal_dispatch", admission)

    jobs = build_jobs(FORMAL_LEVEL, 10)
    if attempt_ledger_state(ATTEMPT_LEDGER_PATH)["attempts"]:
        raise RuntimeError("formal ledger is nonempty; duplicate dispatch is forbidden")
    reservations = append_attempt_records(
        ATTEMPT_LEDGER_PATH, _attempt_records_for_jobs(jobs, "formal")
    )
    attempt_ids = [int(row["attempt_id"]) for row in reservations]
    if len(attempt_ids) != FORMAL_EPISODE_COUNT:
        raise RuntimeError("formal reservation count is not 180")
    append_ledger_event(
        ATTEMPT_LEDGER_PATH,
        {
            "record_type": "phase_dispatch",
            "phase": "formal",
            "attempt_ids": attempt_ids,
            "selected_gpu_indices": [int(item) for item in selected],
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
    completion["selected_gpu_indices"] = [int(item) for item in selected]
    completion["runner_exit_code"] = int(result)
    _write_gpu_admission("formal_completion", completion)
    return int(result)


def select_recovery_jobs(labels: list[str]) -> list[dict[str, object]]:
    if not labels or len(labels) != len(set(labels)):
        raise ValueError("recovery labels must be a nonempty unique list")
    if len(labels) > RECOVERY_ATTEMPT_LIMIT // 10:
        raise ValueError("at most two full formal jobs may use recovery attempts")
    by_label = {
        str(job["label"]): job for job in build_jobs(FORMAL_LEVEL, 10)
    }
    if any(label not in by_label for label in labels):
        raise ValueError("recovery requires a registered formal label")
    return [by_label[label] for label in labels]


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RuntimeError(f"recovery artifact tree contains a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def archive_formal_recovery_artifacts(
    jobs: list[dict[str, object]],
) -> dict[str, object]:
    """Preserve failed/incomplete artifacts before exact full-job recovery."""
    if not jobs or len(jobs) > 2:
        raise RuntimeError("formal recovery archive requires one or two jobs")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive_root = base._p2_safe_child_path(
        OUTPUT_TARGET, "stale", "formal", f"recovery_predispatch_{stamp}"
    )
    archive_root.mkdir(parents=True, exist_ok=False)
    jobs_root = base._p2_safe_child_path(archive_root, "jobs")
    jobs_root.mkdir()
    moves: list[tuple[Path, Path]] = []
    status_path = base._p2_safe_child_path(
        OUTPUT_TARGET, "formal", "run_manifest.csv"
    )
    try:
        if status_path.exists():
            if not status_path.is_file() or status_path.is_symlink():
                raise RuntimeError("formal recovery status path is unsafe")
            archived_status = base._p2_safe_child_path(
                archive_root, "prior_run_manifest.csv"
            )
            shutil.move(str(status_path), str(archived_status))
            moves.append((archived_status, status_path))
        evidence = []
        for job in jobs:
            label = str(job["label"])
            output_dir = base._p2_safe_child_path(
                OUTPUT_TARGET, "formal", label
            )
            log_path = base._p2_safe_child_path(
                OUTPUT_TARGET, "runner_logs", "formal", f"{label}.log"
            )
            failure_path = base._p2_safe_child_path(
                OUTPUT_TARGET, "failures", "formal", f"{label}.json"
            )
            if not any(path.exists() for path in (output_dir, log_path, failure_path)):
                raise RuntimeError(f"no failed recovery artifacts exist for {label}")
            if output_dir.exists():
                if not output_dir.is_dir() or output_dir.is_symlink():
                    raise RuntimeError(f"unsafe recovery output: {label}")
                identity_path = output_dir / "job_manifest.json"
                if not identity_path.is_file() or identity_path.is_symlink():
                    raise RuntimeError(f"recovery identity is missing: {label}")
                identity = json.loads(identity_path.read_text(encoding="utf-8"))
                if identity.get("config_fingerprint") != job["config_fingerprint"]:
                    raise RuntimeError(f"recovery config fingerprint mismatch: {label}")
            job_root = base._p2_safe_child_path(jobs_root, label)
            job_root.mkdir()
            for source, name in (
                (output_dir, "output"),
                (log_path, "runner.log"),
                (failure_path, "failure.json"),
            ):
                if not source.exists():
                    continue
                if source.is_symlink():
                    raise RuntimeError(f"unsafe recovery artifact symlink: {source}")
                destination = base._p2_safe_child_path(job_root, name)
                shutil.move(str(source), str(destination))
                moves.append((destination, source))
            evidence.append(
                {
                    "label": label,
                    "config_fingerprint": job["config_fingerprint"],
                    "code_state_sha256": job["execution_record"][
                        "code_state_sha256"
                    ],
                    "archive_tree_sha256": _tree_sha256(job_root),
                }
            )
        base._redact_secrets_in_text_tree(archive_root)
        for row in evidence:
            row["archive_tree_sha256"] = _tree_sha256(
                base._p2_safe_child_path(jobs_root, row["label"])
            )
        payload = {
            "schema": "eds-qd-search-budget-formal-recovery-archive-v1",
            "created_at": _now(),
            "reason": "failed or incomplete exact-config full-job recovery",
            "archive_root": str(archive_root),
            "jobs": evidence,
        }
        payload["payload_sha256"] = _sha256_bytes(
            _canonical(payload).encode("utf-8")
        )
        if _contains_credential(payload):
            raise RuntimeError("formal recovery archive contains credential material")
        manifest_path = base._p2_safe_child_path(
            archive_root, "archive_manifest.json"
        )
        with manifest_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return {
            "archive_root": str(archive_root),
            "archive_manifest": str(manifest_path),
            "archive_manifest_sha256": _sha256_file(manifest_path),
            "archived_job_count": len(jobs),
        }
    except Exception:
        for destination, source in reversed(moves):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        shutil.rmtree(archive_root, ignore_errors=True)
        raise


def _run_formal_recovery(
    *, labels: list[str], requested_gpus: str, timeout_seconds: int
) -> int:
    if not RUN_MANIFEST_PATH.is_file() or RUN_MANIFEST_PATH.stat().st_mode & 0o222:
        raise RuntimeError("immutable run manifest must exist before recovery")
    storage_preflight()
    legacy.validate_runtime_cache()
    legacy.validate_runtime_credential()
    if not base._poe_healthcheck():
        raise RuntimeError("Poe Stage Recognition health check failed")
    manifest = json.loads(RUN_MANIFEST_PATH.read_text(encoding="utf-8"))
    provenance = current_provenance()
    if manifest.get("provenance") != provenance:
        raise RuntimeError("recovery code provenance differs from frozen formal run")
    jobs = select_recovery_jobs(labels)
    with configured_base():
        validity = {
            str(job["label"]): base._p2_job_validity(
                job, allow_identical_overrides=True
            )
            for job in jobs
        }
    valid_labels = [
        label for label, result in validity.items() if result.get("valid") is True
    ]
    if valid_labels:
        raise RuntimeError(
            "outcome-driven retry is forbidden for valid jobs: "
            + ",".join(valid_labels)
        )
    state = attempt_ledger_state(ATTEMPT_LEDGER_PATH)
    requested_attempts = len(jobs) * 10
    recovery_used = int(state["dispatched_attempt_count"]) - FORMAL_EPISODE_COUNT
    if recovery_used < 0 or recovery_used + requested_attempts > RECOVERY_ATTEMPT_LIMIT:
        raise RuntimeError("formal recovery would exceed the 20-attempt allowance")
    reference = load_gpu_reference()
    admission = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"])
    )
    selected = _selected_gpus(admission, requested_gpus)
    selected = selected[: min(len(selected), len(jobs))]
    if not selected:
        raise RuntimeError("no GPU in 0..7 passed recovery admission")
    admission["selected_gpu_indices"] = [int(item) for item in selected]
    admission["recovery_labels"] = labels
    _write_gpu_admission("formal_recovery_dispatch", admission)
    archive = archive_formal_recovery_artifacts(jobs)
    prior_by_cell = {}
    dispatched_ids = set(state["dispatched_attempt_ids"])
    for row in state["active_attempts"]:
        if int(row["attempt_id"]) not in dispatched_ids or row.get("phase") != "formal":
            continue
        prior_by_cell[
            (
                str(row.get("formal_label", row.get("label"))),
                int(row["task_id"]),
                int(row["episode_seed"]),
            )
        ] = int(row["attempt_id"])
    records = _attempt_records_for_jobs(jobs, "formal")
    for record in records:
        cell = (
            str(record.get("formal_label", record.get("label"))),
            int(record["task_id"]),
            int(record["episode_seed"]),
        )
        if cell not in prior_by_cell:
            raise RuntimeError("formal recovery cell has no prior dispatched attempt")
        record["recovery_of_attempt_id"] = prior_by_cell[cell]
    reservations = append_attempt_records(ATTEMPT_LEDGER_PATH, records)
    attempt_ids = [int(row["attempt_id"]) for row in reservations]
    append_ledger_event(
        ATTEMPT_LEDGER_PATH,
        {
            "record_type": "phase_dispatch",
            "phase": "formal",
            "attempt_ids": attempt_ids,
            "selected_gpu_indices": [int(item) for item in selected],
            "recovery_archive": archive,
        },
    )

    def recovery_builder(level: str, episodes: int, **_kwargs):
        if level != FORMAL_LEVEL or episodes != 10:
            raise ValueError("formal recovery matrix changed unexpectedly")
        return [dict(job) for job in jobs]

    with configured_base():
        original_builder = base.build_jobs
        original_healthcheck = base._poe_healthcheck
        base.build_jobs = recovery_builder
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
            base.build_jobs = original_builder
            base._poe_healthcheck = original_healthcheck
    completion = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"]),
        wait_seconds=0.0,
    )
    completion["selected_gpu_indices"] = [int(item) for item in selected]
    completion["recovery_labels"] = labels
    completion["runner_exit_code"] = int(result)
    _write_gpu_admission("formal_recovery_completion", completion)
    return int(result)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("matrix")
    subparsers.add_parser("initialize-storage")
    subparsers.add_parser("storage-preflight")
    subparsers.add_parser("num-elites-no-op-audit")
    subparsers.add_parser("gpu-admission")
    subparsers.add_parser("freeze-manifest")
    run = subparsers.add_parser("run-formal")
    run.add_argument("--gpus", default="auto")
    run.add_argument("--timeout-seconds", type=int, default=28800)
    recovery = subparsers.add_parser("retry-formal")
    recovery.add_argument("--labels", required=True)
    recovery.add_argument("--gpus", default="auto")
    recovery.add_argument("--timeout-seconds", type=int, default=28800)
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
    if args.command == "num-elites-no-op-audit":
        print(json.dumps(num_elites_no_op_audit(), indent=2))
        return 0
    if args.command == "gpu-admission":
        reference = load_gpu_reference()
        print(
            json.dumps(
                admit_gpus(
                    reference_peak_vram_mib=float(
                        reference["reference_peak_vram_mib"]
                    )
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "freeze-manifest":
        payload = freeze_run_manifest(
            provenance=current_provenance(),
            storage=storage_preflight(),
            gpu_reference=load_gpu_reference(),
        )
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "run-formal":
        return _run_formal(
            requested_gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
        )
    labels = [item.strip() for item in args.labels.split(",") if item.strip()]
    return _run_formal_recovery(
        labels=labels,
        requested_gpus=args.gpus,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
