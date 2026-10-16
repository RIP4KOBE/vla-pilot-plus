#!/usr/bin/env python
"""Batch-validate committed LIBERO-PRO demos after the operator is finished."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time

import h5py


os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
os.environ.setdefault("MUJOCO_GL", "egl")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.data_pipeline import NATIVE_REPLAY_ACCEPTANCE, validate_demo_replay  # noqa: E402
from mode_gate.io_utils import atomic_write_json  # noqa: E402
from mode_gate.policy_evaluator import runtime_suite_name  # noqa: E402
from mode_gate.tickets import ExpansionTicket  # noqa: E402
from scripts.teleop_server import _manifest_task  # noqa: E402


_DEMO = re.compile(r"^demo-(\d{3})-[^.]+\.hdf5$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--progress-path", type=Path)
    parser.add_argument("--observation-size", type=int, default=32)
    args = parser.parse_args()
    if not 16 <= args.observation_size <= 512:
        parser.error("observation-size must be between 16 and 512")
    ticket = ExpansionTicket.model_validate_json(
        args.ticket.read_text(encoding="utf-8")
    )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task = _manifest_task(manifest, ticket)
    raw_dir = args.raw_dir or args.ticket.parent / "raw"
    paths = [
        path
        for path in sorted(raw_dir.glob("demo-*.hdf5"))
        if _DEMO.match(path.name)
    ]
    if not paths:
        raise RuntimeError(f"no committed demos found in {raw_dir}")

    from omegaconf import OmegaConf
    from rsi.core.env_adapters import create_adapter

    backend = OmegaConf.load(REPO_ROOT / "configs/backend/libero.yaml")
    config = OmegaConf.to_container(backend["libero"], resolve=True)
    config.update(
        {
            "suite_name": runtime_suite_name(
                ticket.suite, ticket.perturbation_variant
            ),
            "task_ids_filter": [int(task["task_index"])],
            "episode_num": 1,
            # RGB is not compared or rewritten by action/state validation.
            "observation_width": args.observation_size,
            "observation_height": args.observation_size,
            "camera_depths": False,
            "auto_reset": False,
            "max_episode_steps": int(args.max_steps),
        }
    )
    adapter = create_adapter("libero", config, device="cpu")
    failed = []
    errors = []
    completed = []
    progress_path = args.progress_path or args.ticket.parent / "action_replay_progress.json"
    def progress(state, current=None):
        atomic_write_json(progress_path, {"schema_version": "demo-action-replay-progress-v1",
            "state": state, "pid": os.getpid(), "total": len(paths), "completed": completed,
            "completed_count": len(completed), "current_demo": str(current) if current else None,
            "failed": failed, "errors": errors, "updated_at_unix": time.time(),
            "diagnostic_tolerances": {"state": 5e-3, "qpos": 1e-4, "qvel": 5e-3},
            "acceptance_version": NATIVE_REPLAY_ACCEPTANCE,
            "state_error_role": "diagnostic_only", "success_authority": "LIBERO-PRO native predicate",
            "validation_mode": "initial_restore_once_then_actions_only", "physics_device": "cpu",
            "observation_size": args.observation_size})
    progress("VALIDATING")
    try:
        for path in paths:
            progress("VALIDATING", path)
            match = _DEMO.match(path.name)
            assert match is not None
            with h5py.File(path, "r") as handle:
                committed = bool(handle.attrs.get("collection_committed", False))
                already_valid = bool(handle.attrs.get("replay_validated", False))
                init_state_id = int(handle.attrs["init_state_id"])
                env_seed = int(handle.attrs.get("env_seed", int(match.group(1))))
            if not committed and not already_valid:
                errors.append({"demo": str(path), "error": "not collection_committed"})
                continue
            if already_valid and not args.force:
                result = {"demo": str(path), "status": "already_valid"}
                completed.append(result)
                print(json.dumps(result), flush=True)
                continue
            try:
                error = validate_demo_replay(
                    path,
                    adapter=adapter,
                    tolerance=5e-3,
                    position_tolerance=1e-4,
                    velocity_tolerance=5e-3,
                    prepare_replay=lambda seed=env_seed, init=init_state_id: adapter.reset(
                        seed=seed, init_state_id=init
                    ),
                )
                with h5py.File(path, "r+") as handle:
                    valid = bool(handle.attrs["replay_validated"])
                    native_success = bool(handle.attrs["replay_task_success"])
                    handle.attrs["replay_status"] = "validated" if valid else "rejected"
                    handle.flush()
                result = {
                    "demo": str(path),
                    "status": "validated" if valid else "rejected",
                    "max_state_error": error,
                    "native_success": native_success,
                    "acceptance_version": NATIVE_REPLAY_ACCEPTANCE,
                }
                completed.append(result)
                print(json.dumps(result), flush=True)
                if not valid:
                    failed.append(result)
            except Exception as exc:
                with h5py.File(path, "r+") as handle:
                    handle.attrs["replay_status"] = "error"
                    handle.flush()
                errors.append(
                    {"demo": str(path), "error": f"{type(exc).__name__}: {exc}"}
                )
            progress("VALIDATING")
    finally:
        adapter.close()
    progress("ERROR" if errors else "COMPLETE")
    print(
        json.dumps(
            {
                "total": len(paths),
                "failed": failed,
                "errors": errors,
                "all_valid": not failed and not errors,
            },
            indent=2,
        )
    )
    return 1 if errors else (2 if failed else 0)


if __name__ == "__main__":
    raise SystemExit(main())
