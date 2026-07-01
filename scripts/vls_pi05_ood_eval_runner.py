#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Iterable


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))

EVIDENCE_ROOT = WORKTREE_ROOT / "docs" / "03_evidence" / "eds_steering"
RUN_ROOT = WORKTREE_ROOT / "outputs" / "ood_eval"
EVAL_ROOT = EVIDENCE_ROOT / "vls_pi05_ood_eval"
LOG_ROOT = EVAL_ROOT / "logs"
MARKER_ROOT = EVAL_ROOT / "markers"
STATUS_CSV = EVAL_ROOT / "job_status.csv"
REPORT_PATH = EVIDENCE_ROOT / "level_4_vls_pi05_libero_pro_ood.md"
EDS_LEVEL4_REPORT = EVIDENCE_ROOT / "level_4_libero_pro_ood.md"
EDS_RUN_ROOT = WORKTREE_ROOT / "outputs" / "rdt_eds_eval"
LIBERO_PRO_ROOT = WORKTREE_ROOT / "third_party" / "libero_pro"
LIBERO_CONFIG_PATH = WORKTREE_ROOT / ".libero_config"

EPISODES_DEFAULT = 10
MAX_EPISODE_STEPS = 240
OOD_SUITES = [
    "libero_object_object",
    "libero_object_swap",
    "libero_object_lan",
    "libero_object_task",
    "libero_object_env",
    "libero_object_temp",
]

RDT_VLS_BEST_SOURCE = (
    "/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-gt-rollout-reintegration/"
    "outputs/libero/rdt_full_sbs50_divs1_gs20_temp0"
)
RDT_VLS_BEST_SOURCE_RESULTS = Path(RDT_VLS_BEST_SOURCE) / "results.txt"
RDT_VLS_BEST_SOURCE_OVERRIDES = Path(RDT_VLS_BEST_SOURCE) / ".hydra" / "overrides.yaml"


@dataclass(frozen=True)
class MethodSpec:
    method: str
    label: str
    policy_type: str
    use_guidance: bool
    guidance_type: str = "vls"


METHODS = [
    MethodSpec(
        method="rdt_vls",
        label="RDT+VLS",
        policy_type="rdt",
        use_guidance=True,
    ),
    MethodSpec(
        method="pi05_vls",
        label="PI05+VLS",
        policy_type="pi05",
        use_guidance=True,
    ),
    MethodSpec(
        method="pi05_unguided",
        label="PI05 unguided",
        policy_type="pi05",
        use_guidance=False,
    ),
]

STATUS_FIELDS = [
    "job_id",
    "suite",
    "method",
    "label",
    "policy_type",
    "status",
    "episodes",
    "output_dir",
    "log_file",
    "gpu",
    "exit_code",
    "wall_clock_s",
    "success_count",
    "success_rate",
    "videos",
    "vls_debug_artifacts",
    "strict_perturbations",
    "failure_reason",
    "start_time",
    "end_time",
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_dirs() -> None:
    for path in [EVIDENCE_ROOT, RUN_ROOT, EVAL_ROOT, LOG_ROOT, MARKER_ROOT]:
        path.mkdir(parents=True, exist_ok=True)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKTREE_ROOT))
    except ValueError:
        return str(path)


def build_jobs(episodes: int) -> list[dict[str, object]]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    jobs: list[dict[str, object]] = []
    for suite in OOD_SUITES:
        for method in METHODS:
            job_id = f"level4_{suite}_{method.method}"
            jobs.append(
                {
                    "job_id": job_id,
                    "suite": suite,
                    "method": method.method,
                    "label": method.label,
                    "policy_type": method.policy_type,
                    "use_guidance": method.use_guidance,
                    "guidance_type": method.guidance_type,
                    "episodes": episodes,
                }
            )
    return jobs


def _gpu_runtime(gpu: str) -> dict[str, str]:
    """Return CUDA/EGL settings for a physical nvidia-smi GPU index.

    On this host, EGL device order is not the same as nvidia-smi/CUDA order:
    EGL index 1 maps to physical GPU3, and EGL index 2 maps to physical GPU2.
    robosuite's default import-time assertion was too strict for this host
    because CUDA ordinal and EGL ordinal differ. The local vla-pilot conda
    environment is patched to allow MUJOCO_EGL_DEVICE_ID to be an EGL index
    that differs from CUDA_VISIBLE_DEVICES.
    """
    gpu = str(gpu).strip()
    if gpu == "2":
        return {
            "cuda_visible_devices": "2",
            "mujoco_egl_device_id": "2",
            "hydra_device": "cuda:0",
        }
    if gpu == "3":
        return {
            "cuda_visible_devices": "3",
            "mujoco_egl_device_id": "1",
            "hydra_device": "cuda:0",
        }
    return {
        "cuda_visible_devices": gpu,
        "mujoco_egl_device_id": gpu.split(",", 1)[0],
        "hydra_device": "cuda:0",
    }


def build_main_command(job: dict[str, object], gpu: str) -> list[str]:
    output_dir = RUN_ROOT / str(job["job_id"])
    runtime = _gpu_runtime(gpu)
    command = [
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "python",
        "main.py",
        f"device={runtime['hydra_device']}",
        "backend=libero",
        f"policy.type={job['policy_type']}",
        f"backend.libero.suite_name={job['suite']}",
        f"main.episode_num={job['episodes']}",
        f"backend.libero.max_episode_steps={MAX_EPISODE_STEPS}",
        "backend.libero.strict_perturbations=true",
        "main.render=true",
        "main.visualize_trajectory=true",
        "main.debug_draw_trajectory=true",
        "perception.gemini_grounding.enabled=true",
        "perception.vlm_agent.api_max_retries=8",
        "perception.vlm_agent.api_retry_backoff_seconds=5.0",
        "perception.vlm_agent.api_retry_max_backoff_seconds=30.0",
        f"hydra.run.dir={output_dir}",
    ]

    if bool(job["use_guidance"]):
        command.extend(
            [
                "main.use_guidance=true",
                f"main.guidance_type={job['guidance_type']}",
            ]
        )
    else:
        command.append("main.use_guidance=false")

    if job["method"] == "rdt_vls":
        # Highest documented RDT+VLS base-libero_object ablation with an unambiguous
        # current-config mapping: 6/10 from rdt_full_sbs50_divs1_gs20_temp0.
        command.extend(
            [
                "main.use_vlm_stage_recognition=false",
                "main.vls_config.sample_batch_size=50",
                "main.vls_config.guide_scale=20.0",
                "main.vls_config.use_diversity=true",
                "main.vls_config.diversity_scale=1.0",
                "main.vls_config.use_fkd=true",
                "perception.vlm_agent.temperature=0.0",
            ]
        )
    elif job["method"] == "pi05_vls":
        command.extend(
            [
                "main.use_vlm_stage_recognition=true",
                "perception.vlm_agent.temperature=0.0",
            ]
        )
    elif job["method"] == "pi05_unguided":
        command.extend(
            [
                "main.use_vlm_stage_recognition=true",
            ]
        )
    else:
        raise ValueError(f"Unsupported method: {job['method']}")

    return command


def _results_path(job: dict[str, object]) -> Path:
    return RUN_ROOT / str(job["job_id"]) / "results.txt"


def _output_dir(job: dict[str, object]) -> Path:
    return RUN_ROOT / str(job["job_id"])


def _log_file(job: dict[str, object]) -> Path:
    return LOG_ROOT / f"{job['job_id']}.log"


def _parse_results_file(path: Path) -> dict[str, object]:
    parsed: dict[str, object] = {
        "success": None,
        "total": None,
        "success_rate": None,
    }
    if not path.exists():
        return parsed
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Success count:"):
            value = line.split(":", 1)[1].strip()
            if "/" in value:
                left, right = value.split("/", 1)
                try:
                    parsed["success"] = int(left.strip())
                    parsed["total"] = int(right.strip())
                except ValueError:
                    pass
        elif line.startswith("Success rate:"):
            value = line.split(":", 1)[1].strip().rstrip("%")
            try:
                parsed["success_rate"] = float(value)
            except ValueError:
                pass
    return parsed


def _artifact_counts(output_dir: Path) -> dict[str, int]:
    return {
        "videos": len(list(output_dir.glob("episode_*/*.mp4"))),
        "vls_debug_artifacts": len(
            [
                path
                for path in output_dir.glob("episode_*/vlm_agent/**/*")
                if path.is_file()
            ]
        )
        + len(list(output_dir.glob("episode_*/*trajectory*.png"))),
        "episode_errors": len(list(output_dir.glob("episode_*/error.txt")))
        + len(list(output_dir.glob("episode_*/*fail_error.txt"))),
    }


def _hydra_text(output_dir: Path) -> str:
    pieces = []
    for rel in [".hydra/overrides.yaml", ".hydra/config.yaml"]:
        path = output_dir / rel
        if path.exists():
            pieces.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(pieces)


def _strict_perturbation_recorded(output_dir: Path) -> bool:
    text = _hydra_text(output_dir)
    return (
        "backend.libero.strict_perturbations=true" in text
        or "strict_perturbations: true" in text
    )


def _classify_failure(job: dict[str, object], exit_code: int | None = None) -> str:
    output_dir = _output_dir(job)
    log_path = _log_file(job)
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    if "Timed out after" in log_text or exit_code == 124:
        return "timeout"
    if "Failed to apply required LIBERO-PRO perturbations" in log_text:
        return "perturbation loading failure"
    if "invalid literal for int() with base 10" in log_text and "MUJOCO_EGL_DEVICE_ID" in log_text:
        return "EGL/render device failure"
    if "Cannot initialize a EGL device display" in log_text:
        return "EGL/render device failure"
    if "strict_perturbations" in log_text and "Traceback" in log_text:
        return "perturbation loading failure"
    if "OPENAI" in log_text or "GEMINI" in log_text or "Google" in log_text or "Poe" in log_text:
        if "Error" in log_text or "Exception" in log_text or "timeout" in log_text.lower():
            return "VLM/API failure"
    if "Loading" in log_text and ("checkpoint" in log_text.lower() or "pretrained" in log_text.lower()):
        if "No such file" in log_text or "not found" in log_text.lower():
            return "policy loading/checkpoint failure"
    artifacts = _artifact_counts(output_dir)
    if artifacts["episode_errors"] > 0:
        return "episode execution/preparation error"
    if not _results_path(job).exists():
        return "missing results.txt"
    if _parse_results_file(_results_path(job))["success"] is None:
        return "success parsing failure"
    if artifacts["videos"] < int(job["episodes"]):
        return "missing episode videos"
    if not _strict_perturbation_recorded(output_dir):
        return "strict perturbation config missing"
    parsed = _parse_results_file(_results_path(job))
    if parsed["success"] == 0:
        return "task execution failure; inspect videos for grasp/wrong-object/language binding"
    return ""


def _job_has_complete_outputs(job: dict[str, object]) -> bool:
    output_dir = _output_dir(job)
    parsed = _parse_results_file(_results_path(job))
    artifacts = _artifact_counts(output_dir)
    if parsed["success"] is None or parsed["total"] != int(job["episodes"]):
        return False
    if artifacts["videos"] < int(job["episodes"]):
        return False
    if artifacts["episode_errors"] > 0:
        return False
    if not _strict_perturbation_recorded(output_dir):
        return False
    return True


def _status_row(
    job: dict[str, object],
    status: str,
    *,
    gpu: str = "",
    exit_code: int | str = "",
    wall_clock_s: float | str = "",
    failure_reason: str = "",
) -> dict[str, object]:
    output_dir = _output_dir(job)
    parsed = _parse_results_file(_results_path(job))
    artifacts = _artifact_counts(output_dir)
    success_count = ""
    if parsed["success"] is not None and parsed["total"] is not None:
        success_count = f"{parsed['success']}/{parsed['total']}"
    success_rate = ""
    if parsed["success_rate"] is not None:
        success_rate = f"{parsed['success_rate']:.2f}"
    return {
        **job,
        "status": status,
        "output_dir": str(output_dir),
        "log_file": str(_log_file(job)),
        "gpu": gpu,
        "exit_code": exit_code,
        "wall_clock_s": f"{wall_clock_s:.3f}" if isinstance(wall_clock_s, float) else wall_clock_s,
        "success_count": success_count,
        "success_rate": success_rate,
        "videos": artifacts["videos"],
        "vls_debug_artifacts": artifacts["vls_debug_artifacts"],
        "strict_perturbations": _strict_perturbation_recorded(output_dir),
        "failure_reason": failure_reason,
        "start_time": "",
        "end_time": now_iso(),
    }


def write_status(rows: Iterable[dict[str, object]]) -> None:
    ensure_dirs()
    with STATUS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in STATUS_FIELDS})


def _write_marker(job: dict[str, object], marker_type: str, reason: str = "") -> None:
    for path in MARKER_ROOT.glob(f"{job['job_id']}.*.marker"):
        path.unlink()
    marker = MARKER_ROOT / f"{job['job_id']}.{marker_type}.marker"
    marker.write_text(
        "\n".join(
            [
                f"job_id: {job['job_id']}",
                f"suite: {job['suite']}",
                f"method: {job['method']}",
                f"timestamp: {now_iso()}",
                f"reason: {reason}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def init(episodes: int) -> int:
    jobs = build_jobs(episodes)
    write_status([_status_row(job, "pending") for job in jobs])
    print(STATUS_CSV)
    return 0


def _prepare_env(gpu: str) -> dict[str, str]:
    env = os.environ.copy()
    runtime = _gpu_runtime(gpu)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    env["CUDA_VISIBLE_DEVICES"] = runtime["cuda_visible_devices"]
    env["MUJOCO_EGL_DEVICE_ID"] = runtime["mujoco_egl_device_id"]
    env["PYTHONUNBUFFERED"] = "1"
    env["LIBERO_CONFIG_PATH"] = str(LIBERO_CONFIG_PATH)
    env.setdefault("OPENAI_BASE_URL", "https://api.poe.com/v1")
    pythonpath_parts = [str(LIBERO_PRO_ROOT)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def run_job(job: dict[str, object], gpu: str, timeout_seconds: int) -> dict[str, object]:
    ensure_dirs()
    output_dir = _output_dir(job)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = _log_file(job)
    command = build_main_command(job, gpu)
    env = _prepare_env(gpu)
    start = now_iso()
    start_perf = time.perf_counter()
    return_code = 1
    timed_out = False
    with log_file.open("a", encoding="utf-8", buffering=1) as handle:
        handle.write(f"===== START {job['job_id']} {start} GPU={gpu} =====\n")
        handle.write("Command: " + shlex.join(command) + "\n")
        try:
            process = subprocess.run(
                command,
                cwd=WORKTREE_ROOT,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
            )
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            return_code = 124
            handle.write(f"Timed out after {timeout_seconds} seconds.\n")
        handle.write(f"===== END {job['job_id']} {now_iso()} exit={return_code} =====\n")

    wall_clock = time.perf_counter() - start_perf
    complete = _job_has_complete_outputs(job)
    if timed_out:
        status = "timeout"
    elif complete:
        status = "done"
    elif return_code == 0:
        status = "invalid"
    else:
        status = "failed"
    failure_reason = "" if status == "done" else _classify_failure(job, return_code)
    _write_marker(job, "done" if status == "done" else status, failure_reason)
    row = _status_row(
        job,
        status,
        gpu=gpu,
        exit_code=return_code,
        wall_clock_s=wall_clock,
        failure_reason=failure_reason,
    )
    row["start_time"] = start
    row["end_time"] = now_iso()
    return row


def run_all(episodes: int, gpus: str, timeout_seconds: int, resume: bool) -> int:
    ensure_dirs()
    gpu_list = [gpu.strip() for gpu in gpus.split(",") if gpu.strip()]
    if not gpu_list:
        raise SystemExit("No GPUs specified")
    jobs = build_jobs(episodes)
    rows_by_id: dict[str, dict[str, object]] = {}
    runnable_jobs: list[dict[str, object]] = []
    for job in jobs:
        job_id = str(job["job_id"])
        if resume and _job_has_complete_outputs(job):
            rows_by_id[job_id] = _status_row(job, "done", wall_clock_s="resume-skip")
            _write_marker(job, "done", "resume-skip")
        else:
            rows_by_id[job_id] = _status_row(job, "pending")
            runnable_jobs.append(job)
    write_status(rows_by_id.values())

    queue: Queue[dict[str, object]] = Queue()
    for job in runnable_jobs:
        queue.put(job)

    lock = Lock()

    def worker(gpu: str) -> None:
        while True:
            try:
                job = queue.get_nowait()
            except Empty:
                return
            job_id = str(job["job_id"])
            try:
                with lock:
                    rows_by_id[job_id] = _status_row(job, "running", gpu=gpu)
                    write_status(rows_by_id.values())
                row = run_job(job, gpu=gpu, timeout_seconds=timeout_seconds)
                with lock:
                    rows_by_id[job_id] = row
                    write_status(rows_by_id.values())
            finally:
                queue.task_done()

    threads = [Thread(target=worker, args=(gpu,), daemon=False) for gpu in gpu_list]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    report = write_report(episodes)
    print(report)
    failures = [
        row for row in rows_by_id.values() if str(row.get("status")) not in {"done"}
    ]
    return 1 if failures else 0


def preflight() -> int:
    ensure_dirs()
    failures: list[str] = []
    checks: list[str] = []
    required = [
        WORKTREE_ROOT / "main.py",
        WORKTREE_ROOT / "configs" / "config.yaml",
        WORKTREE_ROOT / "configs" / "policy.yaml",
        WORKTREE_ROOT / "core" / "rdt_policy_steer.py",
        WORKTREE_ROOT / "core" / "pi05_steer.py",
        LIBERO_CONFIG_PATH / "config.yaml",
        LIBERO_PRO_ROOT / "perturbation.py",
        LIBERO_PRO_ROOT / "evaluation_config.yaml",
        LIBERO_PRO_ROOT / "libero_ood" / "ood_environment.yaml",
        LIBERO_PRO_ROOT / "libero_ood" / "ood_spatial_relation.yaml",
        LIBERO_PRO_ROOT / "libero_ood" / "ood_object.yaml",
        LIBERO_PRO_ROOT / "libero_ood" / "ood_language.yaml",
        LIBERO_PRO_ROOT / "libero_ood" / "ood_task.yaml",
    ]
    for path in required:
        if not path.exists():
            failures.append(f"missing required path: `{_rel(path)}`")
    if not RDT_VLS_BEST_SOURCE_RESULTS.exists():
        failures.append(f"missing RDT+VLS best-source results: `{RDT_VLS_BEST_SOURCE_RESULTS}`")
    if not RDT_VLS_BEST_SOURCE_OVERRIDES.exists():
        failures.append(f"missing RDT+VLS best-source overrides: `{RDT_VLS_BEST_SOURCE_OVERRIDES}`")

    try:
        if str(LIBERO_PRO_ROOT) not in sys.path:
            sys.path.insert(0, str(LIBERO_PRO_ROOT))
        os.environ["LIBERO_CONFIG_PATH"] = str(LIBERO_CONFIG_PATH)
        from libero.libero import benchmark, get_libero_path
        from core.env_adapters import libero_adapter

        available = benchmark.get_benchmark_dict()
        missing = [suite for suite in OOD_SUITES if suite not in available]
        if missing:
            failures.append(f"LIBERO-PRO suites not registered: {missing}")
        for key in ["bddl_files", "init_states", "assets"]:
            resolved = Path(get_libero_path(key)).resolve()
            if LIBERO_PRO_ROOT.resolve() not in resolved.parents:
                failures.append(
                    f"LIBERO `{key}` path does not point to worktree LIBERO-PRO: `{resolved}`"
                )
        for suite in OOD_SUITES:
            actual_suite, read_language = libero_adapter._apply_perturbations(suite)
            if actual_suite == "libero_object":
                failures.append(f"`{suite}` fell back to base `libero_object`")
                continue
            bddl_dir = Path(get_libero_path("bddl_files")) / actual_suite
            init_dir = Path(get_libero_path("init_states")) / actual_suite
            bddl_files = sorted(bddl_dir.glob("*.bddl"))
            init_files = sorted(init_dir.glob("*.pruned_init"))
            if not bddl_files or not init_files:
                failures.append(
                    f"`{suite}` generated empty artifacts: {len(bddl_files)} BDDL, "
                    f"{len(init_files)} init files"
                )
            else:
                checks.append(
                    f"`{suite}` -> `{actual_suite}` "
                    f"({len(bddl_files)} BDDL / {len(init_files)} init, "
                    f"read_language_from_bddl={read_language})"
                )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"failed LIBERO-PRO import/apply preflight: {exc}")

    lines = [
        "# VLS/PI05 LIBERO-PRO OOD Preflight",
        "",
        f"Timestamp: `{now_iso()}`",
        f"Status: `{'blocked' if failures else 'pass'}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {item}" for item in checks) if checks else lines.append("- No successful checks recorded.")
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    preflight_path = EVAL_ROOT / "preflight.md"
    preflight_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(preflight_path)
    return 2 if failures else 0


def _read_status_rows() -> list[dict[str, str]]:
    if not STATUS_CSV.exists():
        return []
    with STATUS_CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _success_cell(parsed: dict[str, object]) -> str:
    if parsed["success"] is None or parsed["total"] is None:
        return "-"
    return f"{parsed['success']}/{parsed['total']}"


def _sr_cell(parsed: dict[str, object]) -> str:
    if parsed["success_rate"] is None:
        return "-"
    return f"{float(parsed['success_rate']):.2f}"


def _existing_eds_rows() -> list[dict[str, object]]:
    mapping = {
        "unguided": "RDT unguided",
        "eds_softmax_strong_weak_renoise": "RDT+EDS softmax",
        "eds_cem_resample_weak_renoise": "RDT+EDS CEM",
    }
    rows: list[dict[str, object]] = []
    for suite in OOD_SUITES:
        for suffix, label in mapping.items():
            output_dir = EDS_RUN_ROOT / f"level4_{suite}_{suffix}"
            parsed = _parse_results_file(output_dir / "results.txt")
            rows.append(
                {
                    "suite": suite,
                    "method": label,
                    "success": parsed["success"],
                    "total": parsed["total"],
                    "success_rate": parsed["success_rate"],
                    "output_dir": output_dir,
                }
            )
    return rows


def _new_result_rows(episodes: int) -> list[dict[str, object]]:
    status_by_job = {row["job_id"]: row for row in _read_status_rows()}
    rows = []
    for job in build_jobs(episodes):
        output_dir = _output_dir(job)
        parsed = _parse_results_file(output_dir / "results.txt")
        artifacts = _artifact_counts(output_dir)
        status_row = status_by_job.get(str(job["job_id"]), {})
        complete = _job_has_complete_outputs(job)
        failure_reason = "" if complete else _classify_failure(job)
        wall_clock = status_row.get("wall_clock_s", "")
        rows.append(
            {
                **job,
                "complete": complete,
                "status": status_row.get("status", "missing"),
                "success": parsed["success"],
                "total": parsed["total"],
                "success_rate": parsed["success_rate"],
                "wall_clock_s": wall_clock,
                "videos": artifacts["videos"],
                "vls_debug_artifacts": artifacts["vls_debug_artifacts"],
                "failure_reason": failure_reason or status_row.get("failure_reason", ""),
                "output_dir": output_dir,
                "log_file": _log_file(job),
            }
        )
    return rows


def _perturbation_description(suite: str) -> str:
    return {
        "libero_object_object": "object/visual instance replacement",
        "libero_object_swap": "target-distractor initial-position swap",
        "libero_object_lan": "language paraphrase with unchanged physical task",
        "libero_object_task": "task/goal/object-of-interest remapping",
        "libero_object_env": "environment/support-surface replacement",
        "libero_object_temp": "temp generation under active evaluation_config flags",
    }[suite]


def _suite_analysis(suite: str, rows: list[dict[str, object]], eds_rows: list[dict[str, object]]) -> str:
    combined = [row for row in eds_rows if row["suite"] == suite] + [
        row for row in rows if row["suite"] == suite
    ]
    scored = [
        (str(row["method"] if "method" in row else row["label"]), row.get("success_rate"))
        for row in combined
        if isinstance(row.get("success_rate"), (int, float))
    ]
    if not scored:
        return "No valid result is available yet."
    best = max(scored, key=lambda item: float(item[1]))
    zero_count = sum(1 for _name, sr in scored if float(sr) == 0.0)
    if zero_count == len(scored):
        return (
            f"All compared methods are at 0%; this suite remains unsolved in the current "
            f"10-episode setting."
        )
    return (
        f"Best observed method is `{best[0]}` at {float(best[1]):.2f}%. "
        f"{zero_count}/{len(scored)} compared method results are zero."
    )


def _report_param_source_lines() -> list[str]:
    lines = [
        "## Parameter Sources",
        "",
        "### RDT+VLS",
        "",
        (
            f"- Source selected: `{RDT_VLS_BEST_SOURCE}`. This historical RDT+VLS "
            "base-`libero_object` ablation reports `6/10` and is tied for best among "
            "the documented VLS ablations found locally."
        ),
        (
            f"- Source results: `{RDT_VLS_BEST_SOURCE_RESULTS}`; source overrides: "
            f"`{RDT_VLS_BEST_SOURCE_OVERRIDES}`."
        ),
        "- Current-config mapping used for this run: `main.vls_config.sample_batch_size=50`, `main.vls_config.guide_scale=20.0`, `main.vls_config.use_diversity=true`, `main.vls_config.diversity_scale=1.0`, `main.vls_config.use_fkd=true`, `main.use_vlm_stage_recognition=false`, `perception.vlm_agent.temperature=0.0`.",
        "- Selection rationale: it is the best documented RDT+VLS setting with no ambiguous deprecated key mapping; the tied `start_step=70` result was not selected because current config uses grouped `main.vls_config.start_ratio` semantics.",
        "",
        "### PI05+VLS",
        "",
        "- Policy: `policy.type=pi05` using default `configs/policy.yaml` PI05 settings.",
        "- Guidance: `main.use_guidance=true`, `main.guidance_type=vls`; VLS parameters are the default grouped `main.vls_config` from `configs/config.yaml`.",
        "- No PI05-specific VLS tuning was applied.",
        "",
        "### PI05 Unguided",
        "",
        "- Policy: `policy.type=pi05` using default `configs/policy.yaml` PI05 settings.",
        "- Guidance is disabled via `main.use_guidance=false`.",
    ]
    return lines


def write_report(episodes: int) -> Path:
    ensure_dirs()
    rows = _new_result_rows(episodes)
    eds_rows = _existing_eds_rows()
    complete_count = sum(1 for row in rows if row["complete"])
    lines = [
        "# Level 4 VLS/PI05 LIBERO-PRO OOD Evaluation",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        "## Experiment Overview",
        "",
        "- Benchmark: LIBERO-PRO OOD evaluation on `libero_object`.",
        "- Suites: `libero_object_object`, `libero_object_swap`, `libero_object_lan`, `libero_object_task`, `libero_object_env`, `libero_object_temp`.",
        "- New methods: `RDT+VLS`, `PI05+VLS`, `PI05 unguided`.",
        f"- Episodes per job: `{episodes}`.",
        f"- Strict perturbation mode: `backend.libero.strict_perturbations=true`.",
        "- GPU allocation: runner configured for physical GPU2/GPU3. This host's EGL order differs from CUDA order, so GPU2 uses `CUDA_VISIBLE_DEVICES=2`, `MUJOCO_EGL_DEVICE_ID=2`, `device=cuda:0`; GPU3 uses `CUDA_VISIBLE_DEVICES=3`, `MUJOCO_EGL_DEVICE_ID=1`, `device=cuda:0`. The local `vla-pilot` robosuite import-time EGL assertion was patched to permit this CUDA/EGL split.",
        f"- New job completion: `{complete_count}/18`.",
        f"- Existing RDT+EDS comparison report: `{_rel(EDS_LEVEL4_REPORT)}`.",
        "",
    ]
    lines.extend(_report_param_source_lines())
    lines.extend(
        [
            "",
            "## Complete Result Table",
            "",
            "| Suite | Method | Complete | Status | Success | SR % | Wall-clock s | Videos | VLS/debug artifacts | Log | Output | Failure reason |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in rows:
        success = "-"
        if row["success"] is not None and row["total"] is not None:
            success = f"{row['success']}/{row['total']}"
        sr = "-" if row["success_rate"] is None else f"{float(row['success_rate']):.2f}"
        lines.append(
            f"| `{row['suite']}` | `{row['label']}` | `{row['complete']}` | "
            f"`{row['status']}` | {success} | {sr} | {row['wall_clock_s'] or '-'} | "
            f"{row['videos']} | {row['vls_debug_artifacts']} | "
            f"`{_rel(Path(row['log_file']))}` | `{_rel(Path(row['output_dir']))}` | "
            f"{row['failure_reason'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Comparison With Existing RDT+EDS Level 4",
            "",
            "| Suite | RDT unguided | RDT+EDS softmax | RDT+EDS CEM | RDT+VLS | PI05 unguided | PI05+VLS |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for suite in OOD_SUITES:
        eds_for_suite = {row["method"]: row for row in eds_rows if row["suite"] == suite}
        new_for_suite = {row["method"]: row for row in rows if row["suite"] == suite}
        def sr_from(row: dict[str, object] | None) -> str:
            if not row or row.get("success_rate") is None:
                return "-"
            return f"{float(row['success_rate']):.2f}"

        lines.append(
            f"| `{suite}` | {sr_from(eds_for_suite.get('RDT unguided'))} | "
            f"{sr_from(eds_for_suite.get('RDT+EDS softmax'))} | "
            f"{sr_from(eds_for_suite.get('RDT+EDS CEM'))} | "
            f"{sr_from(new_for_suite.get('rdt_vls'))} | "
            f"{sr_from(new_for_suite.get('pi05_unguided'))} | "
            f"{sr_from(new_for_suite.get('pi05_vls'))} |"
        )

    lines.extend(["", "## Perturbation-Wise Analysis", ""])
    for suite in OOD_SUITES:
        lines.extend(
            [
                f"### `{suite}`",
                "",
                f"- OOD type: {_perturbation_description(suite)}.",
                f"- Result summary: {_suite_analysis(suite, rows, eds_rows)}",
                "",
            ]
        )

    failures = [row for row in rows if not row["complete"] or row["failure_reason"]]
    zero_rows = [row for row in rows if row["success"] == 0 and row["complete"]]
    lines.extend(
        [
            "## Failure Taxonomy",
            "",
            "| Category | Jobs / evidence |",
            "| --- | --- |",
        ]
    )
    categories = [
        "timeout",
        "grasp failure",
        "wrong object / wrong target",
        "language/goal binding failure",
        "perturbation loading failure",
        "VLM/API failure",
        "policy loading/checkpoint failure",
        "EGL/render device failure",
        "task execution failure; inspect videos for grasp/wrong-object/language binding",
        "missing episode videos",
        "success parsing failure",
    ]
    for category in categories:
        matching = [
            f"`{row['job_id']}`"
            for row in failures
            if category in str(row.get("failure_reason", ""))
        ]
        if category in {"grasp failure", "wrong object / wrong target", "language/goal binding failure"}:
            matching = [
                f"`{row['job_id']}`"
                for row in zero_rows
                if "task execution failure" in str(row.get("failure_reason", ""))
            ]
        lines.append(f"| {category} | {', '.join(matching) if matching else '-'} |")
    if not failures and not zero_rows:
        lines.append("| no automatic failures detected | All new jobs complete with nonzero SR. |")

    rdt_vls_better = []
    pi05_vls_better = []
    pi05_better_rdt = []
    for suite in OOD_SUITES:
        eds_for_suite = {row["method"]: row for row in eds_rows if row["suite"] == suite}
        new_for_suite = {row["method"]: row for row in rows if row["suite"] == suite}
        rdt_unguided = eds_for_suite.get("RDT unguided", {}).get("success_rate")
        rdt_vls = new_for_suite.get("rdt_vls", {}).get("success_rate")
        pi05_unguided = new_for_suite.get("pi05_unguided", {}).get("success_rate")
        pi05_vls = new_for_suite.get("pi05_vls", {}).get("success_rate")
        if isinstance(rdt_vls, (int, float)) and isinstance(rdt_unguided, (int, float)):
            if float(rdt_vls) > float(rdt_unguided):
                rdt_vls_better.append(suite)
        if isinstance(pi05_vls, (int, float)) and isinstance(pi05_unguided, (int, float)):
            if float(pi05_vls) > float(pi05_unguided):
                pi05_vls_better.append(suite)
        if isinstance(pi05_unguided, (int, float)) and isinstance(rdt_unguided, (int, float)):
            if float(pi05_unguided) > float(rdt_unguided):
                pi05_better_rdt.append(suite)

    lines.extend(
        [
            "",
            "## Gate And Conclusions",
            "",
            f"- RDT+VLS beats RDT unguided on suites: {', '.join(f'`{s}`' for s in rdt_vls_better) if rdt_vls_better else '`none yet`'}.",
            f"- PI05 unguided beats RDT unguided on suites: {', '.join(f'`{s}`' for s in pi05_better_rdt) if pi05_better_rdt else '`none yet`'}.",
            f"- PI05+VLS beats PI05 unguided on suites: {', '.join(f'`{s}`' for s in pi05_vls_better) if pi05_vls_better else '`none yet`'}.",
            "- VLS stability should be judged per perturbation suite; aggregate SR alone hides whether gains come from language, object, or geometry shifts.",
            "- Remaining zero-SR suites should be debugged by inspecting saved episode videos, VLM outputs under `episode_*/vlm_agent`, and hydra overrides to separate policy failures from perturbation/API failures.",
        ]
    )

    incomplete = [row for row in rows if not row["complete"]]
    lines.extend(
        [
            "",
            "## Completion Audit",
            "",
            f"- Jobs with complete valid outputs: `{complete_count}/18`.",
            f"- Status CSV: `{_rel(STATUS_CSV)}`.",
            f"- Markers: `{_rel(MARKER_ROOT)}`.",
        ]
    )
    if incomplete:
        lines.append("- Incomplete or invalid jobs:")
        lines.extend(
            f"  - `{row['job_id']}`: {row['failure_reason'] or row['status']}"
            for row in incomplete
        )
    else:
        lines.append("- All 18 jobs have `results.txt`, 10 videos, strict perturbation config, and parseable success metrics.")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_PATH


def audit(episodes: int) -> int:
    ensure_dirs()
    rows = _new_result_rows(episodes)
    invalid = [row for row in rows if not row["complete"]]
    for row in rows:
        status = "OK" if row["complete"] else "INVALID"
        print(
            f"{status} {row['job_id']} success={row['success']}/{row['total']} "
            f"videos={row['videos']} reason={row['failure_reason']}"
        )
    print(write_report(episodes))
    return 1 if invalid else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Level-4 VLS/PI05 LIBERO-PRO OOD runner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preflight")
    init_parser = sub.add_parser("init")
    init_parser.add_argument("--episodes", type=int, default=EPISODES_DEFAULT)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--episodes", type=int, default=EPISODES_DEFAULT)
    run_parser.add_argument("--gpus", default="2,3")
    run_parser.add_argument("--timeout-seconds", type=int, default=21600)
    run_parser.add_argument("--resume", action="store_true")
    report_parser = sub.add_parser("write-report")
    report_parser.add_argument("--episodes", type=int, default=EPISODES_DEFAULT)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--episodes", type=int, default=EPISODES_DEFAULT)
    args = parser.parse_args()

    if args.cmd == "preflight":
        return preflight()
    if args.cmd == "init":
        return init(args.episodes)
    if args.cmd == "run":
        return run_all(args.episodes, args.gpus, args.timeout_seconds, args.resume)
    if args.cmd == "write-report":
        print(write_report(args.episodes))
        return 0
    if args.cmd == "audit":
        return audit(args.episodes)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
