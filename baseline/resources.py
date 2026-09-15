"""Explicit single-GPU selection with a free-memory check and replay exclusion."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess


@contextmanager
def isolated_device(cfg):
    if not cfg["device"].startswith("cuda"):
        yield
        return
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not visible or "," in visible or cfg["device"] not in ("cuda", "cuda:0"):
        raise ValueError("set CUDA_VISIBLE_DEVICES to ONE explicit physical GPU and use --device cuda:0")
    rows = subprocess.check_output([
        "nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"
    ], text=True).splitlines()
    candidates = [tuple(x.strip() for x in row.split(",")) for row in rows]
    selected = [v for v in candidates if visible in (v[0], v[1])]
    if len(selected) != 1:
        raise ValueError("CUDA_VISIBLE_DEVICES did not resolve to one physical GPU")
    index, uuid, free_memory = selected[0]
    if int(index) in cfg["protected_gpu_indices"]:
        raise RuntimeError(f"physical GPU {index} is reserved for replay; choose another GPU")
    lock_dir = Path(__file__).resolve().parent / ".locks"
    lock_dir.mkdir(exist_ok=True)
    import fcntl
    with (lock_dir / f"{uuid}.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if int(free_memory) < cfg["gpu_min_free_mib"]:
            raise RuntimeError(f"physical GPU {index} has {free_memory} MiB free, needs at least {cfg['gpu_min_free_mib']} MiB; model not loaded")
        # CUDA ordinal order can differ from nvidia-smi order. Resolve the
        # user's physical index to its UUID before torch initializes CUDA.
        os.environ["CUDA_VISIBLE_DEVICES"] = uuid
        print(f"baseline selected physical GPU {index} ({uuid}), {free_memory} MiB free; existing jobs may share this GPU", flush=True)
        yield
