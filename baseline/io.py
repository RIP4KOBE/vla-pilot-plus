"""Small atomic artifacts, explicit output ownership, and reproducibility."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        temporary = stream.name
    os.replace(temporary, path)


def append_json(path, value):
    with Path(path).open("a") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def safe_output(root, name, *, inputs=()):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", name):
        raise ValueError("run name must be a simple filename, without directory separators")
    root = Path(root).expanduser().resolve()
    if "self_improve" in root.parts or "models" in root.parts:
        raise ValueError("baseline outputs may not enter production artifacts or model directories")
    for source in inputs:
        source = Path(source).expanduser().resolve()
        if root == source or source in root.parents:
            raise ValueError(f"output root overlaps read-only input: {source}")
    output = root / name
    output.mkdir(parents=True, exist_ok=False)
    return output


def save_tensors(path, value):
    import torch
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    torch.save(value, temporary)
    os.replace(temporary, path)


def load_tensors(path, device="cpu"):
    import torch
    return torch.load(path, map_location=device, weights_only=True)


def to_cpu(value):
    import torch
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        return {k: to_cpu(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(to_cpu(v) for v in value)
    return value


def seed_all(seed):
    import random
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)


def assert_finite_step(loss, parameters, optimizer, max_norm=1.0):
    import torch
    if not torch.isfinite(loss):
        raise FloatingPointError("non-finite training loss")
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(parameters, max_norm, error_if_nonfinite=True)
    optimizer.step()
    return float(norm)
