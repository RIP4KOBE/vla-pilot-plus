#!/usr/bin/env python
"""Batch-validate committed LIBERO-PRO demos after the operator is finished."""

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

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.data_pipeline import validate_demo_replay  # noqa: E402
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
    args = parser.parse_args()
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
    from core.env_adapters import create_adapter

    backend = OmegaConf.load(REPO_ROOT / "configs/backend/libero.yaml")
    config = OmegaConf.to_container(backend["libero"], resolve=True)
    config.update(
        {
            "suite_name": runtime_suite_name(
                ticket.suite, ticket.perturbation_variant
            ),
            "task_ids_filter": [int(task["task_index"])],
            "episode_num": 1,
            "observation_width": 256,
            "observation_height": 256,
            "camera_depths": False,
            "auto_reset": False,
            "max_episode_steps": int(args.max_steps),
        }
    )
    adapter = create_adapter("libero", config)
    failed = []
    try:
        for path in paths:
            match = _DEMO.match(path.name)
            assert match is not None
            with h5py.File(path, "r") as handle:
                committed = bool(handle.attrs.get("collection_committed", False))
                already_valid = bool(handle.attrs.get("replay_validated", False))
                init_state_id = int(handle.attrs["init_state_id"])
                env_seed = int(handle.attrs.get("env_seed", int(match.group(1))))
            if not committed and not already_valid:
                failed.append({"demo": str(path), "error": "not collection_committed"})
                continue
            if already_valid and not args.force:
                print(json.dumps({"demo": str(path), "status": "already_valid"}))
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
                    handle.attrs["replay_status"] = "validated" if valid else "rejected"
                    handle.flush()
                result = {
                    "demo": str(path),
                    "status": "validated" if valid else "rejected",
                    "max_state_error": error,
                }
                print(json.dumps(result))
                if not valid:
                    failed.append(result)
            except Exception as exc:
                with h5py.File(path, "r+") as handle:
                    handle.attrs["replay_status"] = "error"
                    handle.flush()
                failed.append(
                    {"demo": str(path), "error": f"{type(exc).__name__}: {exc}"}
                )
    finally:
        adapter.close()
    print(
        json.dumps(
            {
                "total": len(paths),
                "failed": failed,
                "all_valid": not failed,
            },
            indent=2,
        )
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
