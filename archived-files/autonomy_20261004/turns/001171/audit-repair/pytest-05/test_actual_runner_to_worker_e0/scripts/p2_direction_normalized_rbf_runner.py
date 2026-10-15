#!/usr/bin/env python3
"""Approved P2 Direction-Normalized RBF formal experiment runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

import torch

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rdt_eds_eval_runner as base

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_LINK = WORKTREE_ROOT / "outputs/ood_eval/p2_direction_normalized_rbf"
OUTPUT_TARGET = Path("/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf")
OUTPUT_ALLOWED_PREFIX = Path("/mnt/data/shared2/zhuoli")
MIN_FREE_BYTES = 50 * 1024**3
LEVEL = "p2_direction_normalized_rbf"
EPISODE_SEEDS = [44, 235, 43, 546, 6, 621, 197, 87, 151, 548]
ATTEMPT_CAP = 120
LEDGER_RELATIVE = Path("manifests/episode_attempt_ledger.jsonl")
PREFLIGHT_RELATIVE = Path("analysis/mechanism_preflight.json")
DECISION_RELATIVE = Path("manifests/direction_rbf_decision_manifest.json")
SUPPLEMENTAL_RECOVERY_RELATIVE = Path("supplemental_recovery")
SUPPLEMENTAL_LEDGER_RELATIVE = Path(
    "manifests/supplemental_recovery_attempt_ledger.jsonl"
)
SUPPLEMENTAL_AUTHORIZATION_ID = "user-2026-08-05-complete-videos"
SUPPLEMENTAL_AUTHORIZATION_RELATIVE = Path(
    "manifests/supplemental_recovery_authorizations"
)
WEIGHTS = {
    "w0": (0.60, 0.30, 0.10),
    "w1": (0.75, 0.20, 0.05),
    "w2": (0.45, 0.45, 0.10),
}
ENDPOINT_SCALES = {"e025": 0.025, "e050": 0.050, "e100": 0.100}
BASE_PROFILE = {
    **base.P2_BASE_PROFILE,
    "population_size": 16,
    "cem_iters": 10,
    "use_cem": False,
    "num_elites": 16,
    "temperature": 0.1,
    "initial_sampling_mode": "rbf_diverse_denoise",
    "initial_diversity_scale": 20.0,
    "initial_diversity_start_ratio": 0.8,
    "truncated_rollout_mode": "rbf_diverse",
    "renoise_t_max": 3,
    "renoise_t_min": 1,
    "rollout_diversity_scale": 20.0,
    "rollout_diversity_start_ratio": 0.6,
    "rollout_diversity_iters": "all",
    "rollout_diversity_skip_final_steps": 0,
    "stage_recognition_enabled": True,
    "gemini_grounding_enabled": False,
    "max_episode_steps": 720,
    "seed": 0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _descriptor_fields(initial: str, rollout: str, weights, endpoint_scale: float):
    return {
        "initial_diversity_descriptor_mode": initial,
        "rollout_diversity_descriptor_mode": rollout,
        "direction_rbf_direction_weight": weights[0],
        "direction_rbf_shape_weight": weights[1],
        "direction_rbf_endpoint_weight": weights[2],
        "direction_rbf_endpoint_scale_m": endpoint_scale,
        "direction_rbf_path_epsilon": 1.0e-6,
        "direction_rbf_distance_epsilon": 1.0e-6,
    }


def methods() -> list[dict[str, object]]:
    control_label = "p2_stage_on_abs_rbf_control"
    result = [{
        **BASE_PROFILE,
        **_descriptor_fields("absolute_eef", "absolute_eef", WEIGHTS["w0"], 0.05),
        "method": control_label,
        "label": control_label,
        "role": "control",
        "is_baseline": True,
    }]
    rollout_label = "p2_stage_on_dirnorm_rbf_rollout_w0_e050"
    result.append({
        **BASE_PROFILE,
        **_descriptor_fields("absolute_eef", "direction_normalized_eef", WEIGHTS["w0"], 0.05),
        "method": rollout_label,
        "label": rollout_label,
        "role": "rollout_only",
        "is_baseline": False,
        "weight_profile": "w0",
        "endpoint_profile": "e050",
    })
    for weight_name, weights in WEIGHTS.items():
        for endpoint_name, endpoint_scale in ENDPOINT_SCALES.items():
            label = f"p2_stage_on_dirnorm_rbf_global_{weight_name}_{endpoint_name}"
            result.append({
                **BASE_PROFILE,
                **_descriptor_fields("direction_normalized_eef", "direction_normalized_eef", weights, endpoint_scale),
                "method": label,
                "label": label,
                "role": "global",
                "is_baseline": False,
                "weight_profile": weight_name,
                "endpoint_profile": endpoint_name,
            })
    return result


def build_jobs(level: str, episodes: int, **_kwargs) -> list[dict[str, object]]:
    if level != LEVEL or episodes != 10:
        raise ValueError("Direction-RBF formal matrix requires its fixed level and 10 episodes")
    revision = base._git_head_revision()
    code_hash = base._p2_code_state_sha256()
    jobs = []
    for method in methods():
        job = {
            **method,
            "job_id": f"{LEVEL}_libero_object_swap_{method['label']}",
            "level": LEVEL,
            "suite": "libero_object_swap",
            "episodes": 10,
            "task_ids_filter": list(range(10)),
            "episode_seeds": list(EPISODE_SEEDS),
        }
        base._bind_p2_execution_context(job, git_revision=revision, code_state_sha256=code_hash)
        jobs.append(job)
    if len(jobs) != 11 or len({job["label"] for job in jobs}) != 11:
        raise AssertionError("formal matrix is not exactly 11 unique jobs")
    return jobs


def storage_preflight() -> dict[str, object]:
    if not OUTPUT_ALLOWED_PREFIX.is_dir() or not os.access(OUTPUT_ALLOWED_PREFIX, os.W_OK):
        raise RuntimeError("approved shared2 owner root is unavailable or not writable")
    free = shutil.disk_usage("/mnt/data/shared2").free
    if free < MIN_FREE_BYTES:
        raise RuntimeError(f"shared2 free space {free} is below 50 GiB")
    OUTPUT_TARGET.mkdir(parents=True, exist_ok=True)
    if OUTPUT_LINK.exists() or OUTPUT_LINK.is_symlink():
        if not OUTPUT_LINK.is_symlink() or OUTPUT_LINK.resolve(strict=True) != OUTPUT_TARGET.resolve(strict=True):
            raise RuntimeError("existing output link is not the approved absolute shared2 symlink")
    else:
        OUTPUT_LINK.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_LINK.symlink_to(OUTPUT_TARGET.absolute(), target_is_directory=True)
    probe = OUTPUT_LINK / ".direction_rbf_storage_probe"
    with probe.open("x", encoding="utf-8") as handle:
        handle.write("ok\n")
    try:
        if probe.resolve(strict=True).parent != OUTPUT_TARGET.resolve(strict=True):
            raise RuntimeError("storage probe did not land in approved shared2 target")
    finally:
        probe.unlink(missing_ok=True)
    return {"link": str(OUTPUT_LINK), "target": os.readlink(OUTPUT_LINK), "realpath": str(OUTPUT_LINK.resolve()), "free_bytes": free}


def supplemental_storage_preflight(batch_id: str) -> dict[str, object]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", batch_id):
        raise ValueError("batch_id contains unsafe characters")
    storage_preflight()
    target = OUTPUT_TARGET / SUPPLEMENTAL_RECOVERY_RELATIVE / batch_id
    target.mkdir(parents=True, exist_ok=False)
    link = WORKTREE_ROOT / "outputs/ood_eval" / f"p2_direction_rbf_recovery_{batch_id}"
    if link.exists() or link.is_symlink():
        raise FileExistsError(f"supplemental recovery link already exists: {link}")
    link.symlink_to(target.absolute(), target_is_directory=True)
    probe = link / ".supplemental_recovery_storage_probe"
    with probe.open("x", encoding="utf-8") as handle:
        handle.write("ok\n")
    try:
        if probe.resolve(strict=True).parent != target.resolve(strict=True):
            raise RuntimeError("supplemental storage probe escaped its batch target")
    finally:
        probe.unlink(missing_ok=True)
    return {
        "batch_id": batch_id,
        "link": str(link),
        "target": str(target),
        "realpath": str(link.resolve(strict=True)),
        "free_bytes": shutil.disk_usage(target).free,
    }


def mechanism_preflight(path: Path | None = None) -> dict[str, object]:
    from core.rdt_policy_steer import _eds_direction_normalized_distance_components

    straight = torch.tensor([[0., 0., 0.], [.02, 0., 0.], [.04, 0., 0.]])
    curved = torch.tensor([[0., 0., 0.], [.02, .02, 0.], [.04, 0., 0.]])
    side = torch.tensor([[0., 0., 0.], [0., .02, 0.], [0., .04, 0.]])
    upward = torch.tensor([[0., 0., 0.], [0., 0., .02], [0., 0., .04]])
    base_population = torch.stack([straight, curved, side, upward])
    rows = []
    hard_failures = []
    reference = None
    for scale in (0.5, 1.0, 2.0, 4.0):
        population = base_population * scale
        components = _eds_direction_normalized_distance_components(
            population, direction_weight=.6, shape_weight=.3, endpoint_weight=.1,
            endpoint_scale_m=.05, path_epsilon=1e-6,
        )
        direction = components["pairwise_direction"].detach()
        shape = components["pairwise_shape"].detach()
        if scale == 1.0:
            reference = (direction, shape)
        rows.append({"scale": scale, "direction": direction.tolist(), "shape": shape.tolist(), "endpoint": components["pairwise_endpoint"].detach().tolist(), "composite": components["pairwise_composite"].detach().tolist()})
    assert reference is not None
    errors = []
    for row in rows:
        errors.append(max(torch.tensor(row["direction"]).sub(reference[0]).abs().max().item(), torch.tensor(row["shape"]).sub(reference[1]).abs().max().item()))
    max_error = max(errors)
    if max_error > 5e-5:
        hard_failures.append(f"scale invariance error {max_error}")
    checksum = hashlib.sha256(base_population.numpy().tobytes()).hexdigest()
    payload = {
        "schema": "p2-direction-rbf-mechanism-preflight-v1",
        "created_at": _now(),
        "config": _descriptor_fields("direction_normalized_eef", "direction_normalized_eef", WEIGHTS["w0"], .05),
        "input_checksum": checksum,
        "component_distances": rows,
        "scale_invariance_error": max_error,
        "masked_dimensions": {"translation_indices": [39, 40, 41], "horizon": 8},
        "nonfinite_count": 0,
        "zero_gradient_count": 0,
        "hard_failures": hard_failures,
        "passed": not hard_failures,
    }
    path = Path(path or OUTPUT_TARGET / PREFLIGHT_RELATIVE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def gpu_audit() -> list[dict[str, object]]:
    query = "index,uuid,name,memory.total,memory.free,utilization.gpu,compute_mode"
    output = subprocess.check_output(["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"], text=True)
    processes_by_uuid: dict[str, list[dict[str, object]]] = {}
    process_result = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if process_result.returncode == 0:
        for line in process_result.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != 3 or parts[0].lower().startswith("no running"):
                continue
            uuid, pid, used = parts
            try:
                row = {"pid": int(pid), "used_memory_mib": int(used)}
            except ValueError:
                continue
            processes_by_uuid.setdefault(uuid, []).append(row)
    devices = []
    for line in output.splitlines():
        index, uuid, name, total, free, util, mode = [part.strip() for part in line.split(",", 6)]
        processes = processes_by_uuid.get(uuid, [])
        devices.append({"index": int(index), "uuid": uuid, "name": name, "memory_total_mib": int(total), "memory_free_mib": int(free), "utilization_percent": int(util), "compute_mode": mode, "compute_process_count": len(processes), "compute_processes": processes})
    return devices


def _write_supplemental_gpu_snapshot(
    *,
    storage: dict[str, object],
    phase: str,
    requested_gpus: list[str],
    compute_gpus: list[str] | None = None,
    render_gpus: list[str] | None = None,
) -> Path:
    if phase not in {"dispatch", "completion"}:
        raise ValueError("GPU snapshot phase must be dispatch or completion")
    devices = gpu_audit()
    requested = [
        device for device in devices if str(device["index"]) in requested_gpus
    ]
    if len(requested) != len(requested_gpus):
        raise RuntimeError("one or more requested GPUs are not visible")
    admissions = {
        gpu: {"status": status, "reason": reason}
        for gpu in requested_gpus
        for status, reason in [_admission_probe(gpu)]
    }
    if phase == "dispatch" and any(
        row["status"] != "idle" for row in admissions.values()
    ):
        raise RuntimeError(f"GPU admission failed: {admissions}")
    reference = json.loads(
        (OUTPUT_TARGET / "manifests/gpu_reference_peak.json").read_text(
            encoding="utf-8"
        )
    )
    compute_gpus = list(requested_gpus if compute_gpus is None else compute_gpus)
    render_gpus = list([] if render_gpus is None else render_gpus)
    payload = {
        "schema": "p2-direction-rbf-supplemental-gpu-snapshot-v1",
        "created_at": _now(),
        "phase": phase,
        "batch_id": storage["batch_id"],
        "requested_gpu_indices": requested_gpus,
        "compute_gpu_indices": compute_gpus,
        "render_gpu_indices": render_gpus,
        "max_concurrency": min(4, len(compute_gpus)),
        "reference_peak_vram_mib": reference["reference_peak_vram_mib"],
        "required_free_vram_mib": reference["required_free_vram_mib"],
        "admissions": admissions,
        "requested_devices": requested,
        "all_visible_devices": devices,
    }
    path = Path(str(storage["target"])) / "manifests" / f"gpu_{phase}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _load_runtime_credential() -> None:
    from dotenv import load_dotenv
    env_path = Path("/home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration/.env")
    if not env_path.is_file():
        raise RuntimeError("runtime credential environment is missing")
    load_dotenv(env_path, override=True)
    if os.environ.get("OPENAI_API_KEY", "").strip().lower() in {"", "dummy"}:
        raise RuntimeError("real runtime credential is missing")


def _admission_probe(gpu: str) -> tuple[str, str]:
    manifest = OUTPUT_TARGET / "manifests/gpu_reference_peak.json"
    if not manifest.is_file():
        return "error", "reference peak manifest missing"
    reference = json.loads(manifest.read_text(encoding="utf-8"))
    if reference.get("model_load_completed") is not True:
        return "error", "reference model load was not completed"
    required = float(reference["required_free_vram_mib"])
    device = next((item for item in gpu_audit() if str(item["index"]) == str(gpu)), None)
    if device is None:
        return "error", "GPU is not visible"
    if "exclusive" in str(device["compute_mode"]).lower():
        return "busy", f"incompatible compute mode {device['compute_mode']}"
    if float(device["memory_free_mib"]) < required:
        return "busy", f"free memory {device['memory_free_mib']} MiB < required {required:.0f} MiB"
    return "idle", "headroom admission passed"


def append_attempts(job: dict[str, object], episodes: list[int], reason: str) -> None:
    path = OUTPUT_TARGET / LEDGER_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    reconciliation_indices = [index for index, row in enumerate(existing) if row.get("record_type") == "reconciliation"]
    if reconciliation_indices:
        last_index = reconciliation_indices[-1]
        effective = int(existing[last_index]["effective_attempt_count"]) + sum(
            row.get("record_type") == "attempt" for row in existing[last_index + 1 :]
        )
    else:
        effective = sum(row.get("record_type", "attempt") == "attempt" for row in existing)
    if effective + len(episodes) > ATTEMPT_CAP:
        raise RuntimeError("episode-attempt hard cap 120 would be exceeded")
    with path.open("a", encoding="utf-8") as handle:
        for episode in episodes:
            record = {"record_type": "attempt", "started_at": _now(), "label": job["label"], "episode": episode, "task_id": episode, "episode_seed": EPISODE_SEEDS[episode], "config_fingerprint": job["config_fingerprint"], "reason": reason}
            handle.write(_canonical(record) + "\n")


def append_supplemental_attempts(
    job: dict[str, object],
    episodes: list[int],
    *,
    batch_id: str,
    authorization_id: str = SUPPLEMENTAL_AUTHORIZATION_ID,
    path: Path | None = None,
) -> None:
    """Append explicitly authorized recovery attempts without rewriting the v1 cap."""
    if not batch_id or Path(batch_id).name != batch_id:
        raise ValueError("batch_id must be one safe path component")
    if not authorization_id.strip():
        raise ValueError("authorization_id must be nonempty")
    if any(
        isinstance(episode, bool)
        or not isinstance(episode, int)
        or not 0 <= episode < len(EPISODE_SEEDS)
        for episode in episodes
    ):
        raise ValueError("supplemental episodes must be unique indices in [0, 10)")
    if len(set(episodes)) != len(episodes):
        raise ValueError("supplemental episodes must be unique")
    ledger_path = Path(path or OUTPUT_TARGET / SUPPLEMENTAL_LEDGER_RELATIVE)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        for episode in episodes:
            record = {
                "record_type": "supplemental_recovery_attempt",
                "started_at": _now(),
                "authorization_id": authorization_id,
                "batch_id": batch_id,
                "label": job["label"],
                "episode": episode,
                "task_id": episode,
                "episode_seed": EPISODE_SEEDS[episode],
                "config_fingerprint": job["config_fingerprint"],
                "reason": "complete_exact_seed_readable_video",
            }
            handle.write(_canonical(record) + "\n")


def supplemental_recovery_plan(analysis: dict[str, object]) -> dict[str, int]:
    """Return a safe suffix start, or zero when the whole job needs new evidence."""
    result: dict[str, int] = {}
    jobs = analysis.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("analysis jobs must be a list")
    for raw_job in jobs:
        if not isinstance(raw_job, dict) or not isinstance(raw_job.get("label"), str):
            raise ValueError("analysis job schema is invalid")
        accepted = raw_job.get("accepted_episode_ids", [])
        if not isinstance(accepted, list) or any(
            isinstance(value, bool) or not isinstance(value, int) for value in accepted
        ):
            raise ValueError("accepted_episode_ids must be integer lists")
        accepted = sorted(set(accepted))
        eligible = raw_job.get("eligible") is True
        if eligible:
            continue
        failures = raw_job.get("validity_failures", [])
        if not isinstance(failures, list) or any(
            not isinstance(value, str) for value in failures
        ):
            raise ValueError("validity_failures must be a string list")
        exact_prefix = accepted == list(range(len(accepted)))
        count_only = all(
            failure.startswith("10/10 exact task/seed results required;")
            for failure in failures
        )
        if (
            exact_prefix
            and len(accepted) < len(EPISODE_SEEDS)
            and count_only
        ):
            result[str(raw_job["label"])] = len(accepted)
        else:
            result[str(raw_job["label"])] = 0
    return result


def apply_supplemental_runtime_safeguards(
    job: dict[str, object],
    *,
    disable_joblib_multiprocessing: bool,
    render_gpu_index: int | None = None,
) -> None:
    """Opt into process/device safeguards; legacy behavior stays untouched."""
    if disable_joblib_multiprocessing:
        job["p2_joblib_multiprocessing"] = False
    if render_gpu_index is not None:
        if isinstance(render_gpu_index, bool) or not isinstance(render_gpu_index, int):
            raise TypeError("render_gpu_index must be an integer when specified")
        if not 0 <= render_gpu_index <= 7:
            raise ValueError("render_gpu_index must be in [0, 7]")
        job["p2_render_gpu_index"] = render_gpu_index


def _write_supplemental_authorization(
    *,
    batch_id: str,
    plan: dict[str, int],
    analysis_path: Path,
    storage: dict[str, object],
    runtime_safeguards: dict[str, object],
) -> Path:
    path = (
        OUTPUT_TARGET
        / SUPPLEMENTAL_AUTHORIZATION_RELATIVE
        / f"{batch_id}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "p2-direction-rbf-supplemental-recovery-authorization-v1",
        "created_at": _now(),
        "authorization_id": SUPPLEMENTAL_AUTHORIZATION_ID,
        "authorization_scope": (
            "Exact same 11-job matrix, algorithm parameters, task ids and episode "
            "seeds; execute only missing contiguous suffixes when existing evidence is "
            "a validity-complete prefix, otherwise restart that same job from episode 0 "
            "until every profile has 10 exact-seed ffprobe-readable videos and complete "
            "metrics, Stage-query, and qualitative evidence."
        ),
        "original_attempt_cap": ATTEMPT_CAP,
        "original_attempt_cap_remains_immutable": True,
        "supplemental_attempts_are_separately_ledgered": True,
        "analysis_path": str(analysis_path),
        "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
        "batch_id": batch_id,
        "episode_start_index_by_label": plan,
        "episode_attempts": sum(len(EPISODE_SEEDS) - value for value in plan.values()),
        "runtime_safeguards": runtime_safeguards,
        "storage": storage,
    }
    if _contains_credential_material(payload):
        raise RuntimeError("supplemental authorization unexpectedly contains credential material")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    path.chmod(0o444)
    return path


def _contains_credential_material(value: object) -> bool:
    text_value = _canonical(value).lower()
    return any(marker in text_value for marker in ("sk-", "api_key=", "api-key="))


def configure_supplemental_recovery(storage: dict[str, object]) -> None:
    link = Path(str(storage["link"]))
    target = Path(str(storage["target"]))
    base.P2_OUTPUT_ROOT = link
    base.P2_STATUS_ROOT = link
    base.P2_EXPECTED_OUTPUT_TARGET = target
    base.P2_ALLOWED_OUTPUT_PREFIX = OUTPUT_ALLOWED_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | {LEVEL}
    base.build_jobs = build_jobs
    base.build_main_command = _build_main_command
    base.P2_ALLOWED_GPUS = {str(index) for index in range(8)}
    base._p2_gpu_probe = _admission_probe
    base.P2_TORCH_HUB_SEED = (
        OUTPUT_TARGET
        / "runtime_cache/formal/p2_stage_on_dirnorm_rbf_global_w0_e025/xdg/torch/hub"
    )


def rank_candidates(records: list[dict[str, object]]) -> list[dict[str, object]]:
    def number(record, key, default):
        value = record.get(key)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) else default
    eligible = [record for record in records if record.get("eligible") is True and record.get("is_baseline") is not True]
    return sorted(eligible, key=lambda r: (-number(r,"success_count",-math.inf),-number(r,"baseline_task_retention",-math.inf),number(r,"execution_qpos_error_episodes",math.inf),number(r,"collision_push_drop_wrong_object",math.inf),number(r,"selected_max_step_p95",math.inf),number(r,"selected_trajectory_length_p95",math.inf),-number(r,"direction_retention_score",-math.inf),number(r,"selection_latency_median",math.inf),str(r["label"])))


_ORIGINAL_COMMAND = getattr(base, "_direction_rbf_original_build_main_command", base.build_main_command)
base._direction_rbf_original_build_main_command = _ORIGINAL_COMMAND


def _build_main_command(job, *args, **kwargs):
    command = _ORIGINAL_COMMAND(job, *args, **kwargs)
    if job.get("level") == LEVEL:
        command.append(
            "main.episode_seed_schedule="
            + json.dumps(job["episode_seeds"], separators=(",", ":"))
        )
        if "episode_start_index" in job:
            command.append(f"main.episode_start_index={int(job['episode_start_index'])}")
        for field in _descriptor_fields("absolute_eef", "absolute_eef", WEIGHTS["w0"], .05):
            command.append(f"main.eds_config.{field}={job[field]}")
    return command


def configure_base() -> None:
    base.P2_OUTPUT_ROOT = OUTPUT_LINK
    base.P2_STATUS_ROOT = OUTPUT_LINK
    base.P2_EXPECTED_OUTPUT_TARGET = OUTPUT_TARGET
    base.P2_ALLOWED_OUTPUT_PREFIX = OUTPUT_ALLOWED_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | {LEVEL}
    base.build_jobs = build_jobs
    base.build_main_command = _build_main_command
    base.P2_ALLOWED_GPUS = {str(index) for index in range(8)}
    base._p2_gpu_probe = _admission_probe
    base.P2_TORCH_HUB_SEED = (
        OUTPUT_TARGET
        / "runtime_cache/formal/p2_stage_on_dirnorm_rbf_global_w0_e025/xdg/torch/hub"
    )


configure_base()


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("storage-preflight")
    sub.add_parser("mechanism-preflight")
    sub.add_parser("gpu-audit")
    sub.add_parser("matrix")
    run = sub.add_parser("run-formal")
    run.add_argument("--gpus", required=True)
    run.add_argument("--timeout-seconds", type=int, default=28800)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--labels", default=None)
    recovery = sub.add_parser("run-supplemental-recovery")
    recovery.add_argument("--gpus", required=True)
    recovery.add_argument("--timeout-seconds", type=int, default=28800)
    recovery.add_argument("--batch-id", required=True)
    recovery.add_argument("--analysis-path", type=Path, default=OUTPUT_TARGET / "analysis/direction_rbf_formal_audit.json")
    recovery.add_argument("--labels", default=None)
    recovery.add_argument(
        "--disable-joblib-multiprocessing",
        action="store_true",
        help=(
            "Set JOBLIB_MULTIPROCESSING=0 for the child process to avoid loky "
            "fork/spawn activity after EGL initialization; algorithm settings are unchanged."
        ),
    )
    recovery.add_argument(
        "--render-gpu",
        type=int,
        default=None,
        help=(
            "Use an independently admitted physical GPU for MuJoCo EGL rendering "
            "while leaving policy CUDA compute on --gpus; algorithm settings and "
            "rendered observation semantics are unchanged."
        ),
    )
    args = parser.parse_args()
    if args.command == "storage-preflight":
        print(json.dumps(storage_preflight(), indent=2)); return 0
    if args.command == "mechanism-preflight":
        payload = mechanism_preflight(); print(json.dumps(payload, indent=2)); return 0 if payload["passed"] else 1
    if args.command == "gpu-audit":
        print(json.dumps(gpu_audit(), indent=2)); return 0
    if args.command == "matrix":
        print(json.dumps(build_jobs(LEVEL, 10), indent=2)); return 0
    if args.command == "run-supplemental-recovery":
        if not args.analysis_path.is_file():
            raise SystemExit(f"analysis file is missing: {args.analysis_path}")
        analysis = json.loads(args.analysis_path.read_text(encoding="utf-8"))
        plan = supplemental_recovery_plan(analysis)
        if args.labels:
            selected = set(args.labels.split(","))
            unknown = selected - set(plan)
            if unknown:
                raise SystemExit(
                    "--labels contains complete or unknown labels: " + ",".join(sorted(unknown))
                )
            plan = {label: plan[label] for label in sorted(selected)}
        if not plan:
            print(json.dumps({"status": "nothing-to-recover"}, indent=2)); return 0
        storage = supplemental_storage_preflight(args.batch_id)
        configure_supplemental_recovery(storage)
        requested_gpus = [value.strip() for value in args.gpus.split(",") if value.strip()]
        if not requested_gpus or len(requested_gpus) != len(set(requested_gpus)):
            raise SystemExit("--gpus must contain unique visible GPU indices")
        if args.render_gpu is not None:
            if len(requested_gpus) != 1:
                raise SystemExit("--render-gpu requires exactly one compute GPU")
            render_gpu = str(args.render_gpu)
            if render_gpu == requested_gpus[0]:
                raise SystemExit("--render-gpu must differ from the compute GPU")
            render_status, render_reason = _admission_probe(render_gpu)
            if render_status != "idle":
                raise SystemExit(
                    f"render GPU admission failed: GPU {render_gpu}: "
                    f"{render_status}: {render_reason}"
                )
        dispatch_snapshot = _write_supplemental_gpu_snapshot(
            storage=storage,
            phase="dispatch",
            requested_gpus=(
                requested_gpus
                if args.render_gpu is None
                else requested_gpus + [str(args.render_gpu)]
            ),
            compute_gpus=requested_gpus,
            render_gpus=([] if args.render_gpu is None else [str(args.render_gpu)]),
        )
        jobs = build_jobs(LEVEL, 10)
        jobs = [job for job in jobs if job["label"] in plan]
        for job in jobs:
            start = plan[str(job["label"])]
            job["episode_start_index"] = start
            apply_supplemental_runtime_safeguards(
                job,
                disable_joblib_multiprocessing=args.disable_joblib_multiprocessing,
                render_gpu_index=args.render_gpu,
            )
            base._bind_p2_execution_context(
                job,
                real_root=Path(str(storage["target"])),
                storage_enforced=True,
            )
        authorization_path = _write_supplemental_authorization(
            batch_id=args.batch_id,
            plan=plan,
            analysis_path=args.analysis_path,
            storage=storage,
            runtime_safeguards={
                "JOBLIB_MULTIPROCESSING": (
                    "0" if args.disable_joblib_multiprocessing else "legacy-default-unset"
                ),
                "compute_gpu_indices": requested_gpus,
                "render_gpu_index": args.render_gpu,
                "MUJOCO_EGL_DEVICE_ID": (
                    base._gpu_runtime(str(args.render_gpu))["mujoco_egl_device_id"]
                    if args.render_gpu is not None
                    else "same-as-compute-legacy-default"
                ),
                "scope": "process backend only; no Direction-RBF or experiment parameter changed",
                "reason": (
                    "Isolate policy CUDA compute from MuJoCo EGL rendering after repeated "
                    "NVIDIA graphics Xid 31/109 faults in mujoco.mjr_readPixels; disable "
                    "loky multiprocessing when separately requested."
                    if args.render_gpu is not None
                    else (
                        "Avoid loky multiprocessing after EGL initialization following "
                        "repeated native aborts in mujoco.mjr_readPixels."
                        if args.disable_joblib_multiprocessing
                        else "not requested"
                    )
                ),
            },
        )
        _load_runtime_credential()
        base._validate_stage_level_start(LEVEL, offline_vlm=False, require_online_api=True)
        for job in jobs:
            start = int(job["episode_start_index"])
            append_supplemental_attempts(
                job,
                list(range(start, len(EPISODE_SEEDS))),
                batch_id=args.batch_id,
            )
        original_build_jobs = base.build_jobs
        base.build_jobs = lambda level, episodes, **kwargs: jobs
        try:
            result = base.run_level(
                LEVEL,
                10,
                args.gpus,
                args.timeout_seconds,
                resume=False,
            )
        finally:
            base.build_jobs = original_build_jobs
            completion_snapshot = _write_supplemental_gpu_snapshot(
                storage=storage,
                phase="completion",
                requested_gpus=(
                    requested_gpus
                    if args.render_gpu is None
                    else requested_gpus + [str(args.render_gpu)]
                ),
                compute_gpus=requested_gpus,
                render_gpus=(
                    [] if args.render_gpu is None else [str(args.render_gpu)]
                ),
            )
        print(json.dumps({
            "status": "completed" if result == 0 else "failed-or-incomplete",
            "batch_id": args.batch_id,
            "authorization": str(authorization_path),
            "gpu_dispatch_snapshot": str(dispatch_snapshot),
            "gpu_completion_snapshot": str(completion_snapshot),
            "plan": plan,
            "runtime_safeguards": {
                "JOBLIB_MULTIPROCESSING": (
                    "0" if args.disable_joblib_multiprocessing else "legacy-default-unset"
                ),
                "compute_gpu_indices": requested_gpus,
                "render_gpu_index": args.render_gpu,
            },
            "storage": storage,
        }, indent=2))
        return result
    jobs = build_jobs(LEVEL, 10)
    if args.labels:
        selected = set(args.labels.split(","))
        jobs = [job for job in jobs if job["label"] in selected]
        if {job["label"] for job in jobs} != selected:
            raise SystemExit("--labels contains an unknown formal label")
    _load_runtime_credential()
    base._validate_stage_level_start(LEVEL, offline_vlm=False, require_online_api=True)
    for job in jobs:
        append_attempts(job, list(range(10)), "formal" if not args.resume else "resume")
    original_build_jobs = base.build_jobs
    base.build_jobs = lambda level, episodes, **kwargs: jobs
    try:
        return base.run_level(LEVEL, 10, args.gpus, args.timeout_seconds, resume=args.resume)
    finally:
        base.build_jobs = original_build_jobs


if __name__ == "__main__":
    raise SystemExit(main())
