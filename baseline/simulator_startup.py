"""A bounded startup allowance for baseline-only MuJoCo scene loading."""
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import threading
import time

from .io import write_json


RL_STARTUP_SECONDS = 600.0
ACTIVITY_PATH = "BASELINE_SIMULATOR_ACTIVITY_PATH"


def failure_details(exc):
    """Robosuite wraps a camera timeout in ValueError; retain its real cause."""
    chain, pending, seen = [], [exc], set()
    timed_out = False
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        chain.append({"error_type": type(error).__name__, "error": str(error)})
        timed_out |= isinstance(error, TimeoutError) and str(error).startswith("baseline LIBERO initialization exceeded ")
        pending.extend(e for e in (error.__context__, error.__cause__) if e is not None)
    return {"error_type": type(exc).__name__, "error": str(exc), "error_chain": chain,
            "retryable_infrastructure_failure": "simulator_initialization_timeout" if timed_out else None}


@contextmanager
def monitor_startup(output):
    """Expose only this worker's bounded simulator operations to its scheduler."""
    previous = os.environ.pop(ACTIVITY_PATH, None)
    if output is not None:
        os.environ[ACTIVITY_PATH] = str(Path(output).resolve() / "simulator_activity.json")
    try:
        yield
    finally:
        os.environ.pop(ACTIVITY_PATH, None)
        if previous is not None:
            os.environ[ACTIVITY_PATH] = previous


def startup_seconds(cfg):
    return RL_STARTUP_SECONDS if cfg.get("method") in ("continual_vla_rl", "rl2_vla") else None


@contextmanager
def startup_deadline(seconds, operation="initialize"):
    """The native adapter preserves this outer timer instead of installing 120s.

    This scope ends before any policy action. It never alters the simulator
    horizon, reset state, success predicate, or a pre-existing caller's alarm.
    """
    if seconds is None:
        yield
        return
    if seconds <= 0:
        raise ValueError("simulator startup allowance must be positive")
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
        raise RuntimeError("bounded simulator startup requires a POSIX main thread")
    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)
    path = os.environ.get(ACTIVITY_PATH)
    activity = {"pid": os.getpid(), "operation": operation, "state": "running",
                "started_at": time.time(), "timeout_seconds": seconds}
    if path:
        write_json(path, activity)

    def expired(*_):
        raise TimeoutError(f"baseline LIBERO initialization exceeded {seconds:g}s")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    except BaseException as exc:
        activity.update(state="failed", **failure_details(exc))
        raise
    else:
        activity.update(state="complete")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if path:
            write_json(path, {**activity, "ended_at": time.time()})
