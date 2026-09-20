#!/usr/bin/env python
"""Measure the hgpu1 teleoperation hot path without touching a live session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

import numpy as np
import torch


os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
os.environ.setdefault("MUJOCO_GL", "egl")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.policy_evaluator import runtime_suite_name  # noqa: E402
from mode_gate.teleop import _jpeg_data_url  # noqa: E402
from mode_gate.tickets import ExpansionTicket  # noqa: E402
from scripts.teleop_server import _manifest_task  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--resolution", type=int, default=512)
    args = parser.parse_args()
    ticket = ExpansionTicket.model_validate_json(
        args.ticket.read_text(encoding="utf-8")
    )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task = _manifest_task(manifest, ticket)

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
            "observation_width": int(args.resolution),
            "observation_height": int(args.resolution),
            "auto_reset": False,
            "camera_depths": False,
            "max_episode_steps": 3000,
        }
    )
    adapter = create_adapter("libero", config)
    try:
        adapter.reset(seed=0, init_state_id=int(ticket.init_state_ids[0]))
        action = torch.tensor(
            [0.25, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0],
            device=adapter.device,
        )
        rows = []
        step = getattr(adapter, "step_teleop", adapter.step)
        for _ in range(int(args.steps)):
            started = time.perf_counter()
            step(action)
            stepped = time.perf_counter()
            state = adapter.capture_simulator_state()
            captured = time.perf_counter()
            adapter.get_teleop_observation()
            observed = time.perf_counter()
            images = adapter.get_teleop_preview_observation()
            previewed = time.perf_counter()
            encoded = [_jpeg_data_url(image) for image in images]
            finished = time.perf_counter()
            rows.append(
                {
                    "step_ms": 1000.0 * (stepped - started),
                    "full_snapshot_ms": 1000.0 * (captured - stepped),
                    "training_frame_ms": 1000.0 * (observed - captured),
                    "preview_ms": 1000.0 * (previewed - observed),
                    "jpeg_ms": 1000.0 * (finished - previewed),
                    "total_ms": 1000.0 * (finished - started),
                    "snapshot_mib": sum(
                        np.asarray(value).nbytes for value in state.values()
                    )
                    / (1024 * 1024),
                    "wire_kib": sum(len(value) for value in encoded) / 1024,
                }
            )
        result = {
            "resolution": int(args.resolution),
            "steps": len(rows),
            "median": {
                key: round(statistics.median(row[key] for row in rows), 3)
                for key in rows[0]
            },
            "p95_total_ms": round(
                float(np.percentile([row["total_ms"] for row in rows], 95)), 3
            ),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        adapter.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
