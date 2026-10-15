"""Bounded synthetic-only test entrypoint; no production modules or loaders."""
import json
import math
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import types

HERE = Path(__file__).absolute().parent
LOG = HERE / "cpu-checks.log"
ALLOWED_NAMES = frozenset({"root-cpu-protocol-v1.md", "verified_immutable_cache.py",
    "test_verified_immutable_cache.py", "run_cpu_checks.py", "cpu-checks.log",
    "report.md", "manifest.json"})
PREFIX = "CACHE_CPU_RUN_SUMMARY "
sys.dont_write_bytecode = True
os.environ.update({"CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "2",
    "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
    "NUMEXPR_NUM_THREADS": "2", "PYTHONDONTWRITEBYTECODE": "1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
tempfile.tempdir = str(HERE)
available = sorted(os.sched_getaffinity(0))
os.sched_setaffinity(0, available[:2])


def inventory():
    files = list(HERE.iterdir())
    if any(p.is_symlink() or not p.is_file() or p.name not in ALLOWED_NAMES for p in files):
        raise RuntimeError("unexpected preparation entry; no cache/fixture directories allowed")
    if len(files) > 8 or sum(p.stat().st_size for p in files) > 1024 * 1024:
        raise RuntimeError("preparation file/byte cap exceeded")
    return {"regular_files": len(files), "bytes": sum(p.stat().st_size for p in files)}


inventory()
prior = LOG.read_text() if LOG.exists() else ""
summaries = [json.loads(line.split(PREFIX, 1)[1]) for line in prior.splitlines() if PREFIX in line]
if prior.count("CACHE_CPU_RUN_BEGIN") != len(summaries):
    raise RuntimeError("previous run lacks settled elapsed time; refuse an unmetered retry")
used = sum(row["elapsed_seconds"] for row in summaries)
remaining = 120.0 - used
if not math.isfinite(remaining) or remaining <= 0:
    raise RuntimeError("aggregate 120-second test budget exhausted")

standard_roots = tuple(Path(p).resolve() for p in {sys.prefix, sys.base_prefix})
static_metadata = {Path("/dev/null"), Path("/etc/localtime"), Path("/etc/ld.so.cache")}
denied = []


def inside(path, root):
    return path == root or root in path.parents


def deny(event, target):
    denied.append({"event": event, "target": str(target)})
    raise PermissionError(f"CPU guard refused {event}: {target}")


def audit(event, args):
    if event == "open":
        raw, mode, flags = args
        if isinstance(raw, int):
            return  # Existing stdin/stdout/stderr descriptors, no new path discovery.
        path = Path(os.fsdecode(raw)).absolute()
        writing = ((isinstance(mode, str) and any(c in mode for c in "wax+"))
                   or (isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))))
        if writing:
            if path != LOG or path.is_symlink():
                deny(event, {"path": str(path), "mode": mode, "flags": flags})
            return
        if path == HERE:  # importlib metadata may open the owned directory.
            return
        if path.parent == HERE and path.name in ALLOWED_NAMES and not path.is_symlink():
            return
        resolved = path.resolve()
        if any(inside(resolved, root) for root in standard_roots) or path in static_metadata:
            return
        deny(event, path)
    elif event in ("os.listdir", "os.scandir"):
        raw = args[0]
        if isinstance(raw, int):
            deny(event, "directory descriptor")
        path = Path(os.fsdecode(raw or ".")).absolute().resolve()
        if path != HERE and not any(inside(path, root) for root in standard_roots):
            deny(event, path)
    elif event == "os.chdir":
        if Path(os.fsdecode(args[0])).absolute() != HERE:
            deny(event, args[0])
    elif event in ("os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.link", "os.symlink",
                   "os.truncate", "os.chmod", "os.chown", "os.system", "os.fork",
                   "os.posix_spawn", "subprocess.Popen", "socket.connect", "socket.bind",
                   "socket.getaddrinfo", "socket.__new__"):
        deny(event, "operation forbidden")
    elif event == "ctypes.dlopen" and args[0] is not None:
        deny(event, args[0])
    elif event == "import" and args[0].split(".")[0] in {
            "torch", "transformers", "libero", "mujoco", "robosuite", "requests", "httpx"}:
        deny(event, args[0])


sys.addaudithook(audit)
started = time.monotonic()
print("CACHE_CPU_RUN_BEGIN", json.dumps({"prior_seconds": used, "remaining_seconds": remaining}), flush=True)


def timeout(_signum, _frame):
    raise TimeoutError("aggregate synthetic test time exhausted")


signal.signal(signal.SIGALRM, timeout)
signal.setitimer(signal.ITIMER_REAL, remaining)
exit_code = 1
error = None
try:
    import pytest
    # Compile only these owned source bytes: no bytecode-cache probe or write.
    for name in ("verified_immutable_cache", "test_verified_immutable_cache"):
        source_path = HERE / (name + ".py")
        module = types.ModuleType(name)
        module.__file__ = str(source_path)
        sys.modules[name] = module
        exec(compile(source_path.read_bytes(), str(source_path), "exec"), module.__dict__)
    exit_code = int(pytest.main(["-q", "-s", "--assert=plain", "-p", "no:cacheprovider", "--noconftest",
        "--confcutdir=" + str(HERE), "--tb=short", "--log-file=" + str(LOG),
        "--log-file-mode=a", str(HERE / "test_verified_immutable_cache.py")]))
except BaseException as exc:
    error = f"{type(exc).__name__}: {exc}"
finally:
    signal.setitimer(signal.ITIMER_REAL, 0)
    elapsed = time.monotonic() - started
    counts = inventory()
    clean = not denied and "torch" not in sys.modules
    if not clean:
        exit_code = 1
    print("\n" + PREFIX + json.dumps({"elapsed_seconds": elapsed, "aggregate_seconds": used + elapsed,
        "pytest_exit_code": exit_code, "error": error, "guard_clean": clean,
        "denied_operations": denied, "cpu_affinity_count": len(os.sched_getaffinity(0)),
        "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
        "torch_imported": "torch" in sys.modules, "inventory": counts}), flush=True)
raise SystemExit(exit_code)
