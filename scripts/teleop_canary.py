#!/usr/bin/env python
"""Real hgpu1 EGL/undo/browser-contract canary for T2 teleoperation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys

import numpy as np


os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
os.environ.setdefault("MUJOCO_GL", "egl")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.data_pipeline import DemoWriter  # noqa: E402
from mode_gate.eval_manifest import fixed_development_probe_context  # noqa: E402
from mode_gate.io_utils import atomic_write_json  # noqa: E402
from mode_gate.preflight import teleop_canary_source_fingerprint  # noqa: E402
from mode_gate.teleop import TeleopSession, create_teleop_app  # noqa: E402


DEFAULT_OUTPUT = Path(
    "/shared/hengyil6/vls/self_improve/preflight/teleop_canary/result.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json"
        ),
    )
    args = parser.parse_args()

    from omegaconf import OmegaConf
    from core.env_adapters import create_adapter

    config = OmegaConf.to_container(
        OmegaConf.load(REPO_ROOT / "configs/backend/libero.yaml")["libero"],
        resolve=True,
    )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    context = fixed_development_probe_context(manifest)
    config.update(
        {
            "suite_name": context["runtime_suite"],
            "task_ids_filter": [context["task_index"]],
            "episode_num": 1,
            "observation_width": 512,
            "observation_height": 512,
            "render_gpu_device_id": 8,
            "auto_reset": False,
            "auto_apply_perturbations": False,
            "max_episode_steps": 3000,
        }
    )
    adapter = create_adapter("libero", config)
    adapter.reset(
        seed=20260825,
        init_state_id=int(context["init_state_id"]),
    )
    runtime_context = adapter.get_context_provenance()
    _assert_runtime_context(context, runtime_context)
    robosuite_wrapper = adapter._get_current_robosuite_env()
    internal_horizon = int(
        getattr(getattr(robosuite_wrapper, "env", robosuite_wrapper), "horizon")
    )
    before = adapter.capture_simulator_state()
    image, image2, state, ee = adapter.get_teleop_observation()
    preview, preview2 = adapter.get_teleop_preview_observation()
    writer = DemoWriter(
        args.output.parent / "canary-demo.hdf5",
        task=adapter.get_task_description(),
        ticket_id="teleop-canary",
        operator="canary",
        init_state_id=context["init_state_id"],
        snapshot_id=None,
        hashes={"source": teleop_canary_source_fingerprint(REPO_ROOT)},
        coverage_cell="canary",
    )
    session = TeleopSession(
        adapter=adapter,
        writer=writer,
        observation_provider=adapter.get_teleop_observation,
        preview_provider=adapter.get_teleop_preview_observation,
        max_steps=int(config["max_episode_steps"]),
    )
    session.initialize()
    stepped = session.handle("w")
    undone = session.handle("u")
    after = adapter.capture_simulator_state()
    create_teleop_app(session)
    qpos_error = float(np.max(np.abs(before["qpos"] - after["qpos"])))
    qvel_error = float(np.max(np.abs(before["qvel"] - after["qvel"])))
    passed = bool(
        image.shape == (256, 256, 3)
        and image2.shape == (256, 256, 3)
        and preview.shape == (512, 512, 3)
        and preview2.shape == (512, 512, 3)
        and writer.frames[0].image.shape == (256, 256, 3)
        and state.shape == (8,)
        and ee.shape == (3,)
        and stepped["steps"] == 1
        and undone["steps"] == 0
        and qpos_error <= 1e-10
        and qvel_error <= 1e-10
        and internal_horizon == 3000
    )
    result = {
        "schema_version": "hgpu1-libero-pro-teleop-canary-v3",
        "source_fingerprint": teleop_canary_source_fingerprint(REPO_ROOT),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "context": context,
        "runtime_context": runtime_context,
        "image_shape": list(image.shape),
        "image2_shape": list(image2.shape),
        "preview_shape": list(preview.shape),
        "preview2_shape": list(preview2.shape),
        "state_shape": list(state.shape),
        "ee_shape": list(ee.shape),
        "qpos_restore_max_error": qpos_error,
        "qvel_restore_max_error": qvel_error,
        "undo_steps": undone["steps"],
        "internal_horizon": internal_horizon,
        "localhost_only": True,
        "passed": passed,
    }
    atomic_write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        raise RuntimeError("real T2 teleoperation canary failed")
    return 0


def _assert_runtime_context(expected: dict, actual: dict) -> None:
    for field in (
        "suite",
        "runtime_suite",
        "task_id",
        "perturbation_variant",
        "init_state_id",
    ):
        if str(actual.get(field)) != str(expected.get(field)):
            raise RuntimeError(
                f"LIBERO-PRO teleop context mismatch for {field}: "
                f"expected {expected.get(field)!r}, got {actual.get(field)!r}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
