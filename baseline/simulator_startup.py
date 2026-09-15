"""A bounded startup allowance for baseline-only MuJoCo scene loading."""
from contextlib import contextmanager
import signal
import threading


RL_STARTUP_SECONDS = 600.0


def startup_seconds(cfg):
    return RL_STARTUP_SECONDS if cfg.get("method") in ("continual_vla_rl", "rl2_vla") else None


@contextmanager
def startup_deadline(seconds):
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

    def expired(*_):
        raise TimeoutError(f"baseline LIBERO initialization exceeded {seconds:g}s")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
