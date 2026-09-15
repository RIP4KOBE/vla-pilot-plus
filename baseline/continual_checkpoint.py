"""Atomic GRPO group-boundary recovery, including optimizer and random states."""
import random
from pathlib import Path

import numpy as np
import torch

from .io import load_tensors, save_tensors, to_cpu
from .scope import check_input_root


def contract(runtime, cfg, protocol):
    execution = {"output_root", "device", "gpu_min_free_mib", "protected_gpu_indices"}
    return {"base_sha256": runtime.identity["sha256"], "protocol_sha256": protocol.digest,
            "config": {k: v for k, v in cfg.items() if k not in execution}}


def random_state(rng):
    numpy_state = np.random.get_state()
    return {"shuffle": rng.getstate(), "python": random.getstate(),
            "numpy": [numpy_state[0], numpy_state[1].tolist(), *numpy_state[2:]],
            "torch": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}


def restore_random_state(state, rng):
    rng.setstate(state["shuffle"])
    random.setstate(state["python"])
    values = state["numpy"]
    np.random.set_state((values[0], np.asarray(values[1], dtype=np.uint32), *values[2:]))
    torch.set_rng_state(state["torch"])
    if state["cuda"]:
        if not torch.cuda.is_available() or len(state["cuda"]) != torch.cuda.device_count():
            raise ValueError("GRPO recovery CUDA device count differs")
        torch.cuda.set_rng_state_all(state["cuda"])


def save_checkpoint(path, method, optimizer, scheduler, rng, runtime, cfg, protocol,
                    *, task_key, groups_completed, stage_updates, updates, environment_steps):
    save_tensors(path, {"schema_version": "baseline-continual-optimizer-v1",
        "contract": contract(runtime, cfg, protocol), "task_key": task_key,
        "method": method.state(), "optimizer": to_cpu(optimizer.state_dict()),
        "scheduler": scheduler.state_dict(), "random": random_state(rng),
        "groups_completed": groups_completed, "stage_updates": stage_updates,
        "updates": updates, "environment_steps": environment_steps})


def read_checkpoint(path, runtime, cfg, protocol, task_keys=None):
    check_input_root(path, cfg)
    value = load_tensors(Path(path))
    if (value.get("schema_version") != "baseline-continual-optimizer-v1"
            or value["contract"] != contract(runtime, cfg, protocol)):
        raise ValueError("GRPO checkpoint has different configuration, base or protocol")
    if task_keys is not None and list(task_keys) != [value["task_key"]]:
        raise ValueError("GRPO checkpoint belongs to another task")
    if (not 0 <= value["groups_completed"] <= cfg["continual_vla_rl"]["groups_per_stage"]
            or not 0 <= value["stage_updates"] <= cfg["steps_per_stage"]
            or value["task_key"] in value["method"]["stages"]):
        raise ValueError("invalid GRPO checkpoint progress")
    return value
