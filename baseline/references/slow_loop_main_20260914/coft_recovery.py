"""Atomic, full-state checkpoints for the existing source-aware LeRobot trainer.

No training recipe changes: a restart resumes optimizer/scheduler/RNG and skips
the already consumed deterministic source draws. Only committed saves qualify.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from .io_utils import atomic_write_json, sha256_file

MARKER = "coft_checkpoint_complete.json"
STATE_FILES = ("training_step.json", "optimizer_state.safetensors",
               "optimizer_param_groups.json", "rng_state.safetensors", "scheduler_state.json")


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def checkpoint_complete(path: Path, *, source_manifest: Path | None = None,
                        expected_step: int | None = None) -> bool:
    path = Path(path)
    if not (path / MARKER).is_file():
        return False
    marker = _json(path / MARKER)
    if marker.get("schema_version") != "coft-committed-checkpoint-v1":
        raise ValueError("checkpoint marker identity mismatch")
    for name, size in marker["file_sizes"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("untrusted checkpoint member")
        member = path / relative
        if not member.is_file() or member.stat().st_size != size:
            raise ValueError(f"corrupt committed checkpoint member: {name}")
    required = {f"training_state/{name}" for name in STATE_FILES}
    required |= {"pretrained_model/train_config.json", "pretrained_model/config.json"}
    if not required <= set(marker["file_sizes"]):
        raise ValueError("committed checkpoint lacks full training state")
    if not any(name.startswith("pretrained_model/model") and name.endswith(".safetensors")
               for name in marker["file_sizes"]):
        raise ValueError("committed checkpoint lacks policy weights")
    step = int(_json(path / "training_state/training_step.json")["step"])
    if step != marker["step"] or (expected_step is not None and step != expected_step):
        raise ValueError("checkpoint step identity mismatch")
    if source_manifest is not None and sha256_file(source_manifest) != marker["source_manifest_sha256"]:
        raise ValueError("checkpoint source manifest digest mismatch")
    return True


def save_coft_checkpoint(*, save_fn, checkpoint_dir: Path, step: int, cfg, **kwargs):
    """Publish by rename only after all native checkpoint files are flushed."""
    destination = Path(checkpoint_dir)
    if kwargs.get("optimizer") is None or kwargs.get("scheduler") is None:
        raise ValueError("resumable co-FT requires optimizer and scheduler state")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError("refusing to overwrite an existing co-FT checkpoint")
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.pending-", dir=destination.parent))
    # Preserve a partial staging directory on failure; it cannot be consumed.
    save_fn(checkpoint_dir=staging, step=step, cfg=cfg, **kwargs)
    sizes = {}
    for path in staging.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
            sizes[str(path.relative_to(staging))] = path.stat().st_size
    atomic_write_json(staging / MARKER, {
        "schema_version": "coft-committed-checkpoint-v1", "step": int(step),
        "source_manifest_sha256": sha256_file(Path(cfg.source_sampler_manifest)),
        "file_sizes": sizes, "published_at": time.time(),
        "resume_state": ["policy", "optimizer", "scheduler", "rng", "source_draw_offset"],
    })
    checkpoint_complete(staging, source_manifest=Path(cfg.source_sampler_manifest), expected_step=step)
    for directory in [p for p in staging.rglob("*") if p.is_dir()] + [staging]:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    os.rename(staging, destination)
    descriptor = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    # Retain only the last two *our own committed* intermediate checkpoints.
    # Never delete an unmarked directory, symlink, or other experiment's files.
    committed = sorted(p for p in destination.parent.iterdir()
                       if p.name.isdigit() and p.is_dir() and not p.is_symlink()
                       and (p / MARKER).is_file() and p.name <= destination.name)
    for older in committed[:-2]:
        checkpoint_complete(older, source_manifest=Path(cfg.source_sampler_manifest))
        shutil.rmtree(older)


def prepare_coft_execution(command, spec):
    """Select the latest committed state without changing the immutable spec."""
    command = tuple(map(str, command))
    def argument(name):
        values = [v.split("=", 1)[1] for v in command if v.startswith(name + "=")]
        if len(values) != 1:
            raise ValueError(f"co-FT resume requires one {name}")
        return values[0]
    output = Path(argument("--output_dir")).resolve()
    expected = Path(spec["expected_checkpoint"]).resolve()
    if output.name != "training_output" or expected != output / "checkpoints/001000/pretrained_model":
        raise ValueError("co-FT resume output identity mismatch")
    source = Path(argument("--source_sampler_manifest"))
    if _json(source).get("manifest_sha256") != spec["source_manifest_sha256"]:
        raise ValueError("co-FT source manifest digest mismatch")
    complete = []
    for checkpoint in sorted((output / "checkpoints").glob("[0-9]*")):
        if checkpoint.name.isdigit() and checkpoint_complete(checkpoint, source_manifest=source):
            complete.append(checkpoint)
    if complete:
        checkpoint = complete[-1]
        cfg = _json(checkpoint / "pretrained_model/train_config.json")
        if (Path(cfg["output_dir"]).resolve() != output or int(cfg["steps"]) != int(argument("--steps"))
                or int(cfg["batch_size"]) != int(argument("--batch_size"))
                or int(cfg["gradient_accumulation_steps"]) != int(argument("--gradient_accumulation_steps"))):
            raise ValueError("checkpoint training configuration identity mismatch")
        # policy.path takes precedence over resume in native config.validate().
        resumed = [v for v in command if not v.startswith(("--policy.path=", "--config_path=", "--resume="))]
        resumed += [f"--config_path={checkpoint / 'pretrained_model/train_config.json'}", "--resume=true"]
        return tuple(resumed), {"checkpoint": str(checkpoint), "step": _json(checkpoint / MARKER)["step"],
                                "mode": "full_state_resume"}
    if output.exists():
        # A failure before the first save has no optimizer progress to recover.
        # Move the exact job output aside recoverably instead of deleting it or
        # pretending that a partial save was completed.
        archive = output.with_name(f"training_output.incomplete-{time.time_ns()}")
        os.rename(output, archive)
        return command, {"mode": "restart_before_first_committed_checkpoint", "preserved_output": str(archive)}
    return command, {"mode": "initial_start", "step": 0}
