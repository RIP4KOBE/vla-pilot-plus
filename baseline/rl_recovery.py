"""Recover Continual RL simulator startup failures without changing training."""
import os
from pathlib import Path
import signal
import time

from .io import read_json
from .process_watch import verified_worker
from .simulator_startup import RL_STARTUP_SECONDS


TIMEOUT = "simulator_initialization_timeout"
WATCHDOG_GRACE_SECONDS = 120
EXIT_GRACE_SECONDS = 30
MAX_RETRIES_WITHOUT_PROGRESS = 3


def eligible(job):
    return job["owner"] == "continual_vla_rl" and job["phase"] == "train"


def timeout_failure(job, output, now=None):
    """Never use general training inactivity as a reason to kill a worker."""
    if not eligible(job):
        return None
    if job.get("infrastructure_failure"):
        return job["infrastructure_failure"]
    for filename in ("status.json", "simulator_activity.json"):
        path = Path(output) / filename
        if not path.exists():
            continue
        value = read_json(path)
        if filename == "simulator_activity.json" and value.get("pid") != job["pid"]:
            continue
        if value.get("retryable_infrastructure_failure") == TIMEOUT:
            return {"kind": TIMEOUT, "source": filename, "details": value}
        # A C/GL call can prevent Python's SIGALRM handler from ever executing.
        # Check the explicitly recorded initialization/reset scope externally.
        timestamp = time.time() if now is None else now
        if (filename == "simulator_activity.json" and value.get("state") == "running"
                and value.get("operation") in ("initialize", "reset")
                and value.get("timeout_seconds") == RL_STARTUP_SECONDS
                and timestamp - value["started_at"] > RL_STARTUP_SECONDS + WATCHDOG_GRACE_SECONDS):
            return {"kind": TIMEOUT, "source": "external_startup_watchdog", "details": value}
    return None


def stop_timed_out_worker(job, output, protected_gpus, now=None):
    """Signal only the recorded baseline PID after checking command, GPU, birth."""
    failure = timeout_failure(job, output, now)
    if failure is None:
        return False
    if job["gpu_index"] == 6 or job["gpu_index"] in protected_gpus:
        raise RuntimeError("refusing to stop a worker on a protected GPU")
    identity = verified_worker(job)
    if identity is None:
        return False
    expected = job.get("process_start_ticks")
    if expected is not None and expected != identity["start_ticks"]:
        raise RuntimeError("baseline worker PID was reused")
    job["process_start_ticks"] = identity["start_ticks"]
    timestamp = time.time() if now is None else now
    job["infrastructure_failure"] = failure
    if "watchdog_term_at" not in job:
        sig = signal.SIGTERM
        job["watchdog_term_at"] = timestamp
    elif timestamp - job["watchdog_term_at"] >= EXIT_GRACE_SECONDS and "watchdog_kill_at" not in job:
        sig = signal.SIGKILL
        job["watchdog_kill_at"] = timestamp
    else:
        return False
    try:
        os.kill(job["pid"], sig)
    except ProcessLookupError:
        pass
    return True


def retry_failed_startup(state, job, root):
    """Requeue at a committed group; never commit a partial failed GRPO group."""
    output = Path(root) / job["name"]
    failure = timeout_failure(job, output)
    if failure is None:
        return False
    item = state["methods"][job["owner"]]
    if job["suffix"] != f"stage_{item['tasks_completed']:03d}":
        return False
    checkpoint = output / "continual_optimizer_checkpoint.pt"
    progress_path = checkpoint.with_suffix(".progress.json")
    if not checkpoint.is_file() or not progress_path.is_file():
        return False
    progress = read_json(progress_path)
    info = checkpoint.stat()
    if (progress.get("task_key") != item["current_task"]
            or progress.get("checkpoint_size") != info.st_size
            or progress.get("checkpoint_mtime_ns") != info.st_mtime_ns):
        return False
    previous = item.get("simulator_recovery", {})
    advanced = (previous.get("stage") != job["suffix"]
                or progress["groups_completed"] > previous.get("groups_completed", -1))
    retries = 1 if advanced else previous["retries_without_progress"] + 1
    recovery = {"stage": job["suffix"], "groups_completed": progress["groups_completed"],
                "retries_without_progress": retries, "total_retries": previous.get("total_retries", 0) + 1,
                "source_run": job["name"], "failure": failure}
    item["simulator_recovery"] = recovery
    job["simulator_recovery"] = recovery
    if retries > MAX_RETRIES_WITHOUT_PROGRESS:
        item["error"] += "; simulator retry budget exhausted without checkpoint progress"
        return False
    item.update(state="QUEUED", optimizer_resume=str(checkpoint))
    item.pop("error", None)
    return True


def prepare_resume(state, busy_owners, selected=None):
    """An explicit repair can resume one owner without reviving retired runs."""
    if selected is not None and not set(selected) <= set(state["methods"]):
        raise ValueError("resume selection contains an unknown queue owner")
    for method, item in state["methods"].items():
        if selected is not None and method not in selected:
            continue
        if item["state"] == "COMPLETE" or method in busy_owners:
            continue
        item.update(state="QUEUED")
        item.pop("error", None)
