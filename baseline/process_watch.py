"""Follow an existing baseline worker without restarting its GPU process."""
from pathlib import Path
import time

from .io import read_json


def process_identity(pid, proc_root=Path("/proc")):
    # Linux can deny access to environ after releasing an exiting task's mm
    # but before changing its state to Z. Retry only this short exit race;
    # persistent access denial must still fail identity verification.
    for attempt in range(10):
        try:
            return _read_identity(pid, proc_root)
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(.01)


def _read_identity(pid, proc_root):
    root = proc_root / str(pid)
    try:
        fields = (root / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {"pid": pid, "start_ticks": int(fields[19]),
                "command": [v.decode() for v in (root / "cmdline").read_bytes().split(b"\0") if v],
                "visible_gpu": next((v.decode().split("=", 1)[1] for v in (root / "environ").read_bytes().split(b"\0")
                                     if v.startswith(b"CUDA_VISIBLE_DEVICES=")), None)}
    except (FileNotFoundError, ProcessLookupError):
        return None


def verified_worker(job, proc_root=Path("/proc")):
    identity = process_identity(job["pid"], proc_root)
    if identity is None:
        return None
    if identity["command"] != job["command"] or identity["visible_gpu"] != job["gpu_uuid"]:
        raise RuntimeError(f"PID {job['pid']} does not match the recorded baseline command/GPU")
    return identity


class ExistingWorker:
    """Popen-compatible completion check for a worker owned by the old scheduler."""
    def __init__(self, identity, output, proc_root=Path("/proc")):
        self.identity, self.output, self.proc_root = identity, Path(output), proc_root
        self.pid = identity["pid"]

    def poll(self):
        current = process_identity(self.pid, self.proc_root)
        if current is not None and current["start_ticks"] == self.identity["start_ticks"]:
            if current != self.identity:
                raise RuntimeError(f"adopted baseline worker {self.pid} changed identity")
            return None
        status = self.output / "status.json"
        return 0 if status.exists() and read_json(status).get("status") == "complete" else 1
