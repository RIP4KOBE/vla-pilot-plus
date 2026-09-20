"""Immutable stage checkpoints; the v44 base and processors are referenced."""
import os
from pathlib import Path

from .io import write_json, read_json, digest, save_tensors, load_tensors
from .scope import scope_identity, check_input_root, check_task_keys


def save_stage(run, index, method, runtime, protocol, cfg, *, metadata=None, replay=None):
    destination = Path(run) / f"stage_{index:03d}"
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_name(destination.name + ".partial")
    temporary.mkdir(exist_ok=False)
    save_tensors(temporary / "state.pt", method.state())
    manifest = {"schema_version": "pi05-pro-baseline-artifact-v1", "method": cfg["method"],
                "base": runtime.identity, "protocol_sha256": protocol.digest,
                "config": cfg, "stages": list(method.stages),
                "state_sha256": digest(temporary / "state.pt"),
                "state_bytes": (temporary / "state.pt").stat().st_size, "metadata": metadata or {},
                "replay": replay or [], "experiment_scope": scope_identity(cfg)}
    write_json(temporary / "manifest.json", manifest)
    os.replace(temporary, destination)
    write_json(Path(run) / "latest.json", {"artifact": str(destination.resolve())})
    return destination


def load_stage(path, runtime, protocol, method, cfg):
    path = Path(path)
    check_input_root(path, cfg)
    value = read_json(path / "manifest.json")
    if cfg.get("experiment_id") and value.get("experiment_scope") != scope_identity(cfg):
        raise ValueError("stage belongs to another experiment/task selection")
    check_task_keys(value.get("stages", []), cfg, protocol)
    if value.get("schema_version") != "pi05-pro-baseline-artifact-v1":
        raise ValueError("not a baseline stage checkpoint")
    if value["method"] != cfg["method"]:
        raise ValueError("baseline method mismatch")
    if cfg["method"] in ("clare", "mlr_ifa") and value["config"].get("demonstration_contract") != cfg.get("demonstration_contract"):
        raise ValueError("demonstration input contract differs from the trained policy; restart from v44")
    if value["base"]["sha256"] != runtime.identity["sha256"]:
        raise ValueError("checkpoint/normalization identity differs from training")
    if value["protocol_sha256"] != protocol.digest:
        raise ValueError("benchmark protocol differs from training")
    for key in ("execution_horizon", "inference_steps", "num_steps_wait", "observation_width", "observation_height"):
        if value["config"].get(key, cfg[key]) != cfg[key]:
            raise ValueError(f"{key} differs from the trained policy contract")
    # These explicit RL2 inference ablations do not alter parameter meanings.
    inference_options = {"trigger", "candidates", "compose_mean", "compose_std"} if cfg["method"] == "rl2_vla" else set()
    trained_options = value["config"][cfg["method"]]
    if any(v != cfg[cfg["method"]].get(k) for k, v in trained_options.items() if k not in inference_options):
        raise ValueError("algorithm settings differ from the stage checkpoint")
    if value["state_sha256"] != digest(path / "state.pt"):
        raise ValueError("stage state checksum mismatch")
    method.restore(load_tensors(path / "state.pt"))
    return value


def make_method(runtime, cfg):
    if cfg["method"] == "clare":
        from .methods.clare import Clare
        return Clare(runtime, cfg["clare"])
    if cfg["method"] == "mlr_ifa":
        from .methods.mlr_ifa import MLRIFA
        return MLRIFA(runtime, cfg["mlr_ifa"])
    if cfg["method"] == "continual_vla_rl":
        from .methods.continual_rl import ContinualRL
        return ContinualRL(runtime, cfg["continual_vla_rl"])
    if cfg["method"] == "rl2_vla":
        from .methods.rl2_vla import RL2VLA
        return RL2VLA(runtime, cfg["rl2_vla"])
    raise ValueError(cfg["method"])
