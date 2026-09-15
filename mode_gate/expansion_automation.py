"""Detach the slow-loop worker as soon as a rollout requests EXPANSION."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Callable

from .io_utils import AtomicJsonl, atomic_write_json


SERVER_PYTHON = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")


def expansion_demonstrations_ready(job: Any) -> bool:
    """Only the current ticket's curated, nonempty dataset releases fast loop.

    Launching a UI, accepting a ticket, or finishing an unsuccessful recording
    is not sufficient. A new collection round also invalidates an older ready
    dataset until that round has passed curation.
    """
    ready_states = {
        "DATASET_READY", "TRAINING", "DELTA_READY", "ALPHA_SELECTING",
        "RAW_REGRESSION", "TRIGGER_RECHECK", "POLICY_STAGED",
        "NEW_POLICY_COUNTERFACTUAL", "VERIFIER_TRAINING", "VERIFIER_PENDING",
        "READY_PAIR", "READY_FIXED_BUDGET", "DEPLOYED", "POLICY_REJECTED",
    }
    if job.state.value not in ready_states:
        return False
    metadata = job.metadata
    if metadata.get("curation_needs_more_demos") is not False:
        return False
    dataset = metadata.get("current_ticket_dataset_path")
    if not dataset:
        return False
    info = _read_optional_json(Path(str(dataset)) / "meta/info.json")
    return info is not None and int(info.get("total_episodes", 0)) > 0


def wait_for_expansion_demonstrations(
    *,
    store: Any,
    job_id: str,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
    poll_seconds: float = 2.0,
    wait_for_completion: bool = False,
) -> None:
    """Synchronous demo barrier; no rollout/model reset or scheduled task."""
    if poll_seconds <= 0:
        raise ValueError("demonstration poll interval must be positive")
    previous = None
    while True:
        if stop_requested is not None and stop_requested():
            raise InterruptedError("experiment stopped while awaiting demonstrations")
        job = store.current(job_id)
        demos_ready = expansion_demonstrations_ready(job)
        ready = (job.state.value in {"DEPLOYED", "POLICY_REJECTED", "CANCELLED"}
                 if wait_for_completion else demos_ready)
        if job.state.value == "CANCELLED":
            ready = True
        identity = (job.sequence, ready)
        if identity != previous and on_update is not None:
            on_update({
                "state": (("SLOW_LOOP_COMPLETE" if wait_for_completion else "DEMONSTRATIONS_READY")
                          if ready else ("WAITING_FOR_SLOW_LOOP" if demos_ready
                                         else "WAITING_FOR_DEMONSTRATIONS")),
                "slow_loop_job_id": job_id,
                "slow_loop_state": job.state.value,
                "task_id": job.metadata.get("task_id"),
                "ticket_id": job.ticket_id,
                "collection_round": job.metadata.get("collection_round", 1),
                "teleop_url": job.metadata.get("teleop_url"),
                "error": job.metadata.get("last_error"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        previous = identity
        if ready:
            return
        time.sleep(poll_seconds)


def launch_expansion_worker(
    *,
    job_id: str,
    repo_root: Path,
    persistent_root: Path,
    slow_loop_root: Path,
    registry_root: Path,
    incident_root: Path,
    snapshot_root: Path,
    operator: str = "human",
    teleop_port: int = 8765,
    teleop_max_steps: int = 3000,
    python_executable: Path = SERVER_PYTHON,
    full_cycle: bool = False,
    gpu_index: int = 6,
) -> dict[str, Any]:
    """Start one idempotent background worker and return its launch record."""

    job_id = str(job_id).strip()
    if not job_id:
        raise ValueError("automatic slow-loop launch requires a job_id")
    repo_root = Path(repo_root).resolve()
    persistent_root = Path(persistent_root).resolve()
    python_executable = Path(python_executable).resolve()
    if not (repo_root / "scripts/self_improve.py").is_file():
        raise FileNotFoundError("self_improve.py is missing from repo_root")
    if not python_executable.is_file():
        raise FileNotFoundError("pinned hgpu1 Python is missing")
    if not str(operator).strip():
        raise ValueError("teleoperation operator must be non-empty")

    launch_root = persistent_root / "slow_worker_launches"
    launch_root.mkdir(parents=True, exist_ok=True)
    record_path = launch_root / f"{job_id}.json"
    lock_path = launch_root / f"{job_id}.lock"
    events = AtomicJsonl(launch_root / "events.jsonl")
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        existing = _read_optional_json(record_path)
        if existing is not None and _worker_process_alive(existing):
            return {**existing, "launch_status": "already_running"}

        attempts = int(existing.get("attempt", 0)) + 1 if existing else 1
        log_path = launch_root / f"{job_id}.attempt-{attempts:03d}.log"
        protocol_manifest = persistent_root / "protocol/joint_eval_manifest.json"
        tickets = persistent_root / "tickets"
        work = persistent_root / "slow_work"
        teleop_runtime = persistent_root / "teleop_runtime"
        command = [
            str(python_executable),
            str(repo_root / "scripts/self_improve.py"),
            "run-job",
            "--job-id",
            job_id,
            "--root",
            str(Path(slow_loop_root).resolve()),
            "--registry",
            str(Path(registry_root).resolve()),
            "--incidents",
            str(Path(incident_root).resolve()),
            "--snapshots",
            str(Path(snapshot_root).resolve()),
            "--protocol-manifest",
            str(protocol_manifest),
            "--tickets",
            str(tickets),
            "--work",
            str(work),
            "--auto-teleop",
            "--watch-collection",
            "--teleop-runtime",
            str(teleop_runtime),
            "--teleop-operator",
            str(operator).strip(),
            "--teleop-port",
            str(int(teleop_port)),
            "--teleop-max-steps",
            str(int(teleop_max_steps)),
        ]
        from .campaign import configuration
        precollected_only = persistent_root == Path(configuration()['root']).resolve()
        if precollected_only:
            command.remove('--auto-teleop')
        if full_cycle:
            command += ["--full-cycle", "--gpu-index", str(int(gpu_index)),
                        "--coft-source-spec", str(persistent_root / "coft_sources.json")]
        environment = os.environ.copy()
        environment.update(
            {
                "PYOPENGL_PLATFORM": "egl",
                "MUJOCO_GL": "egl",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "TOKENIZERS_PARALLELISM": "false",
            }
        )
        with log_path.open("ab", buffering=0) as log:
            process = subprocess.Popen(
                command,
                cwd=repo_root,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        threading.Thread(
            target=process.wait,
            name=f"slow-worker-reaper-{job_id[:8]}",
            daemon=True,
        ).start()
        record = {
            "schema_version": "vls-expansion-worker-launch-v1",
            "launch_status": "launched",
            "job_id": job_id,
            "pid": int(process.pid),
            "attempt": attempts,
            "command": command,
            "log_path": str(log_path),
            "teleop_url": None if precollected_only else f"http://127.0.0.1:{int(teleop_port)}/",
            "demonstration_policy": "precollected_only" if precollected_only else "collection_enabled",
            "launched_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(record_path, record)
        events.append(
            {
                "event_id": f"EXPANSION_WORKER_LAUNCHED:{job_id}:{attempts}",
                "event": "EXPANSION_WORKER_LAUNCHED",
                "job_id": job_id,
                "pid": int(process.pid),
                "attempt": attempts,
                "log_path": str(log_path),
                "recorded_at": record["launched_at"],
            }
        )
        return record


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not Path(path).is_file():
        return None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _worker_process_alive(record: dict[str, Any]) -> bool:
    try:
        pid = int(record["pid"])
        os.kill(pid, 0)
    except (KeyError, TypeError, ValueError, ProcessLookupError, PermissionError):
        return False
    cmdline = Path(f"/proc/{pid}/cmdline")
    if not cmdline.is_file():
        return False
    parts = cmdline.read_bytes().split(b"\0")
    command = list(map(str, record.get("command", ())))
    if len(command) < 4:
        return False
    return (
        str(Path(command[1])).encode("utf-8") in parts
        and b"run-job" in parts
        and str(record.get("job_id", "")).encode("utf-8") in parts
        and b"--watch-collection" in parts
    )


__all__ = [
    "SERVER_PYTHON", "launch_expansion_worker",
    "expansion_demonstrations_ready", "wait_for_expansion_demonstrations",
]
