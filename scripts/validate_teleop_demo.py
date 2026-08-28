#!/usr/bin/env python
"""Validate one saved LIBERO-PRO teleoperation demo in a fresh environment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

import h5py


os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.data_pipeline import validate_demo_replay  # noqa: E402
from mode_gate.policy_evaluator import runtime_suite_name  # noqa: E402
from mode_gate.tickets import ExpansionTicket  # noqa: E402
from scripts.teleop_server import _manifest_task  # noqa: E402


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--demo", type=Path, required=True)
    value.add_argument("--ticket", type=Path, required=True)
    value.add_argument("--manifest", type=Path, required=True)
    value.add_argument("--max-steps", type=int, default=3000)
    value.add_argument("--tolerance", type=float, default=5e-3)
    value.add_argument("--position-tolerance", type=float, default=1e-4)
    value.add_argument("--velocity-tolerance", type=float, default=5e-3)
    return value


def main() -> int:
    args = parser().parse_args()
    ticket = ExpansionTicket.model_validate_json(
        args.ticket.read_text(encoding="utf-8")
    )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task = _manifest_task(manifest, ticket)
    with h5py.File(args.demo, "r") as handle:
        init_state_id = int(handle.attrs["init_state_id"])
        stored_seed = handle.attrs.get("env_seed")
    if stored_seed is None:
        match = re.match(r"demo-(\d{3})-", args.demo.name)
        if match is None:
            raise ValueError("demo has no env_seed and filename has no queue index")
        env_seed = int(match.group(1))
    else:
        env_seed = int(stored_seed)

    from omegaconf import OmegaConf
    from core.env_adapters import create_adapter

    backend = OmegaConf.load(REPO_ROOT / "configs/backend/libero.yaml")
    env_config = OmegaConf.to_container(backend["libero"], resolve=True)
    env_config.update(
        {
            "suite_name": runtime_suite_name(
                ticket.suite, ticket.perturbation_variant
            ),
            "task_ids_filter": [int(task["task_index"])],
            "episode_num": 1,
            "observation_width": 256,
            "observation_height": 256,
            "auto_reset": False,
            "max_episode_steps": int(args.max_steps),
        }
    )
    adapter = create_adapter("libero", env_config)
    try:
        error = validate_demo_replay(
            args.demo,
            adapter=adapter,
            tolerance=float(args.tolerance),
            position_tolerance=float(args.position_tolerance),
            velocity_tolerance=float(args.velocity_tolerance),
            prepare_replay=lambda: adapter.reset(
                seed=env_seed, init_state_id=init_state_id
            ),
        )
        with h5py.File(args.demo, "r") as handle:
            replay_validated = bool(handle.attrs["replay_validated"])
            diagnostics = {
                key: (
                    handle.attrs[key].item()
                    if hasattr(handle.attrs[key], "item")
                    else handle.attrs[key]
                )
                for key in (
                    "replay_max_state_error_index",
                    "replay_max_state_error_dimension",
                    "replay_first_exceeds_tolerance_index",
                    "replay_max_qpos_error",
                    "replay_max_qvel_error",
                    "replay_task_success",
                    "replay_success_matches",
                )
                if key in handle.attrs
            }
    finally:
        adapter.close()
    result = {
        "demo": str(args.demo),
        "env_seed": env_seed,
        "init_state_id": init_state_id,
        "max_state_error": error,
        "tolerance": float(args.tolerance),
        "position_tolerance": float(args.position_tolerance),
        "velocity_tolerance": float(args.velocity_tolerance),
        "valid": replay_validated,
        "diagnostics": diagnostics,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
