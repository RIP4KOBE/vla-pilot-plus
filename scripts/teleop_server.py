#!/usr/bin/env python
"""Run the localhost-only hgpu1 T2 browser teleoperation queue."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from uuid import uuid4

import h5py


os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.data_pipeline import DemoWriter  # noqa: E402
from mode_gate.io_utils import sha256_file  # noqa: E402
from mode_gate.policy_evaluator import runtime_suite_name  # noqa: E402
from mode_gate.snapshots import DecisionSnapshotStore  # noqa: E402
from mode_gate.teleop import (  # noqa: E402
    TeleopSession,
    coverage_hint_zh,
    create_teleop_app,
    drawer_bowl_operator_guidance,
    libero_drawer_bowl_metrics,
)
from mode_gate.tickets import ExpansionTicket  # noqa: E402


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--ticket", type=Path, required=True)
    value.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json"
        ),
    )
    value.add_argument(
        "--snapshot-root",
        type=Path,
        default=Path("/shared/hengyil6/vls/self_improve/snapshots"),
    )
    value.add_argument("--source", choices=("ticket", "snapshot"), default="ticket")
    value.add_argument("--operator", required=True)
    value.add_argument("--output", type=Path)
    value.add_argument("--host", default="127.0.0.1")
    value.add_argument("--port", type=int, default=8765)
    value.add_argument(
        "--max-steps",
        type=int,
        default=3000,
        help="teleoperation-only episode horizon (policy evaluation remains unchanged)",
    )
    return value


def main() -> int:
    args = parser().parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("T2 teleoperation must bind to localhost")
    if args.max_steps < 1000:
        raise ValueError("teleoperation max steps must be at least 1000")
    ticket = ExpansionTicket.model_validate_json(
        args.ticket.read_text(encoding="utf-8")
    )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task = _manifest_task(manifest, ticket)
    snapshot_store = DecisionSnapshotStore(args.snapshot_root)
    snapshot_manifest = None
    task_filter = [int(task["task_index"])]
    if args.source == "snapshot":
        snapshot_manifest = json.loads(
            (args.snapshot_root / ticket.snapshot_id / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        import numpy as np

        with np.load(
            args.snapshot_root / ticket.snapshot_id / "simulator.npz",
            allow_pickle=False,
        ) as values:
            task_filter = [int(value) for value in values["task_id_catalog"]]

    from omegaconf import OmegaConf
    from core.env_adapters import create_adapter

    backend = OmegaConf.load(REPO_ROOT / "configs/backend/libero.yaml")
    env_config = OmegaConf.to_container(backend["libero"], resolve=True)
    env_config.update(
        {
            "suite_name": runtime_suite_name(
                ticket.suite, ticket.perturbation_variant
            ),
            "task_ids_filter": task_filter,
            "episode_num": len(task_filter),
            # Native 512px frames are display-only; DemoWriter still receives
            # the pinned 256px contract from get_teleop_observation().
            "observation_width": 512,
            "observation_height": 512,
            "auto_reset": False,
            # T2 stores RGB only.  Rendering two unused depth maps on every
            # keyboard step adds latency without contributing any dataset
            # field or operator feedback.
            "camera_depths": False,
            "max_episode_steps": int(args.max_steps),
        }
    )
    adapter = create_adapter("libero", env_config)
    output = args.output or args.ticket.parent / "raw"
    output.mkdir(parents=True, exist_ok=True)
    queue = _queue(ticket, source=args.source, ticket_root=args.ticket.parent)
    queue_index = _next_queue_index(output, queue)
    if queue_index >= len(queue):
        raise RuntimeError("all demonstrations in this ticket are already validated")
    guidance_state: dict[str, float | None] = {"initial_bowl_z": None}

    def reset_environment(index: int) -> None:
        entry = queue[index]
        collection_index = int(entry.get("collection_index", index))
        if entry["source"] == "snapshot":
            # Initialize all simulator objects first, then replace state exactly.
            adapter.reset(seed=0)
            snapshot_store.restore_simulator_only(
                ticket.snapshot_id,
                adapter=adapter,
            )
        else:
            adapter.current_task_idx = task_filter.index(int(task["task_index"]))
            adapter.reset(
                seed=int(entry.get("env_seed", collection_index)),
                init_state_id=entry["init_state_id"],
            )

    def start(index: int) -> DemoWriter:
        entry = queue[index]
        collection_index = int(entry.get("collection_index", index))
        reset_environment(index)
        initial_metrics = libero_drawer_bowl_metrics(
            adapter,
            initial_bowl_z=None,
        )
        guidance_state["initial_bowl_z"] = initial_metrics.get("bowl_z")
        return DemoWriter(
            output / f"demo-{collection_index:03d}-{uuid4().hex[:8]}.hdf5",
            task=ticket.task_id,
            ticket_id=ticket.ticket_id,
            operator=args.operator,
            init_state_id=entry["init_state_id"],
            snapshot_id=ticket.snapshot_id if entry["source"] == "snapshot" else None,
            coverage_cell=entry["coverage_cell"],
            target_object_id=ticket.target_object_id,
            env_seed=int(entry.get("env_seed", collection_index)),
            hashes={
                "ticket": sha256_file(args.ticket),
                "manifest": str(manifest["manifest_sha256"]),
                "snapshot": (
                    str(snapshot_manifest["snapshot_hash"])
                    if snapshot_manifest is not None
                    else ""
                ),
            },
        )

    writer = start(queue_index)

    def on_save(path: str) -> DemoWriter | None:
        nonlocal queue_index
        # Keep the operator path fast: commit the immutable T+1/T episode now,
        # then perform expensive 500+ step physical replay in the post-
        # collection validation job.  Replaying synchronously here made every
        # save appear frozen for minutes and temporarily destroyed the live
        # controller state.
        _commit_collected_demo(Path(path))
        queue_index += 1
        if queue_index >= len(queue):
            return None
        return start(queue_index)

    def guidance_provider(session: TeleopSession) -> dict:
        metrics = libero_drawer_bowl_metrics(
            adapter,
            initial_bowl_z=guidance_state["initial_bowl_z"],
        )
        return drawer_bowl_operator_guidance(
            metrics,
            gripper_command=session.gripper,
            coverage_hint=coverage_hint_zh(
                str(session.writer.metadata["coverage_cell"])
            ),
        )

    def reset_current() -> DemoWriter:
        return start(queue_index)

    def task_success() -> bool:
        return bool(adapter._get_current_robosuite_env().check_success())

    ui_context = {
        "task_id": ticket.task_id,
        "task_instruction": adapter.get_task_description(),
        "task_instruction_zh": "拉开木柜最上层抽屉，把桌面上的黑色碗放进该抽屉。",
        "must_demonstrate": list(ticket.collection.must_demonstrate),
        "must_avoid": list(ticket.collection.must_avoid),
        "must_avoid_zh": [
            "在最上层抽屉至少拉开一半前，不要松开把手。",
            "抓着碗移动时，不要碰撞柜子、炉子、盘子或其他物体。",
            "不要掉落碗，也不要把碗不稳定地卡在抽屉边缘。",
            "避免突然、连续过快或抖动式按键。",
        ],
    }

    session = TeleopSession(
        adapter=adapter,
        writer=writer,
        observation_provider=adapter.get_teleop_observation,
        on_save=on_save,
        ui_context=ui_context,
        guidance_provider=guidance_provider,
        queue_position_provider=lambda: (queue_index + 1, len(queue)),
        reset_current=reset_current,
        task_success_provider=task_success,
        preview_provider=adapter.get_teleop_preview_observation,
        max_steps=int(env_config["max_episode_steps"]),
    )
    session.initialize()
    # Pay the one-time renderer/controller cold-start cost before the operator
    # connects.  The action and every recorded field are immediately undone,
    # leaving an exact zero-step episode while avoiding an ~800 ms first key.
    warmed = session.handle("w")
    if warmed["message"] != "stepped":
        raise RuntimeError(f"teleop warm-up failed: {warmed['message']}")
    undone = session.handle("u")
    if undone["message"] != "undone" or undone["steps"] != 0:
        raise RuntimeError("teleop warm-up did not restore the zero-step episode")
    app = create_teleop_app(session)
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _manifest_task(manifest: dict, ticket: ExpansionTicket) -> dict:
    matches = [
        task
        for task in manifest["tasks"]
        if (
            str(task["suite"]),
            str(task["task_id"]),
            str(task["perturbation_variant"]),
        )
        == (ticket.suite, ticket.task_id, ticket.perturbation_variant)
    ]
    if len(matches) != 1:
        raise KeyError("ticket does not resolve to exactly one frozen manifest task")
    return matches[0]


def _queue(
    ticket: ExpansionTicket,
    *,
    source: str,
    ticket_root: Path | None = None,
) -> list[dict[str, Any]]:
    if source == "snapshot":
        return [
            {
                "source": "snapshot",
                "init_state_id": "failure_snapshot",
                "coverage_cell": "failure_snapshot",
                "collection_index": 0,
                "env_seed": 0,
            }
        ]
    cells = [
        f"{cell.axis}={cell.value}"
        for cell in ticket.collection.coverage_axes
        for _ in range(cell.quota)
    ]
    if not cells:
        raise ValueError("ticket has no coverage cells")
    entries = []
    index = 0
    for init_state_id in ticket.init_state_ids:
        for _ in range(ticket.demos_per_state):
            entries.append(
                {
                    "source": "ticket",
                    "init_state_id": init_state_id,
                    "coverage_cell": cells[index % len(cells)],
                    "collection_index": index,
                    "env_seed": index,
                }
            )
            index += 1
    if len(entries) != ticket.target_demos:
        raise RuntimeError("teleop queue length disagrees with immutable ticket")
    if ticket_root is not None:
        curation_path = Path(ticket_root) / "curation.json"
        if curation_path.is_file():
            curation = json.loads(curation_path.read_text(encoding="utf-8"))
            if curation.get("needs_more_demos") is True:
                coverage = dict(curation.get("coverage", {}))
                init_by_cell = {
                    str(entry["coverage_cell"]): str(entry["init_state_id"])
                    for entry in entries
                }
                next_index = _next_collection_index(Path(ticket_root))
                refill: list[dict[str, Any]] = []
                for raw_cell in ticket.collection.coverage_axes:
                    cell = f"{raw_cell.axis}={raw_cell.value}"
                    accepted = int(dict(coverage.get(cell, {})).get("accepted", 0))
                    missing = max(0, int(raw_cell.quota) - accepted)
                    for _ in range(missing):
                        refill.append(
                            {
                                "source": "ticket",
                                "init_state_id": init_by_cell[cell],
                                "coverage_cell": cell,
                                "collection_index": next_index,
                                "env_seed": next_index,
                            }
                        )
                        next_index += 1
                if not refill:
                    raise RuntimeError(
                        "curation requests more demos but every coverage quota is full"
                    )
                return refill
    return entries


_DEMO_INDEX = re.compile(r"^demo-(\d{3})-[^.]+\.hdf5$")


def _next_collection_index(ticket_root: Path) -> int:
    indices = []
    for directory in (Path(ticket_root) / "raw", Path(ticket_root) / "rejected"):
        for path in directory.glob("demo-*.hdf5"):
            match = _DEMO_INDEX.match(path.name)
            if match is not None:
                indices.append(int(match.group(1)))
    return max(indices, default=-1) + 1


def _commit_collected_demo(path: Path) -> None:
    """Atomically mark one structurally complete episode ready for batch replay."""

    with h5py.File(path, "r+") as handle:
        actions = int(handle["action"].shape[0])
        states = int(handle["simulator_state"].shape[0])
        observations = int(handle["observation/state"].shape[0])
        if states != actions + 1 or observations != actions + 1:
            raise RuntimeError("saved demo violates the T+1 state contract")
        if not bool(handle.attrs.get("explicit_success", False)):
            raise RuntimeError("saved demo lacks explicit operator success")
        if not bool(handle.attrs.get("simulator_success", False)):
            raise RuntimeError("saved demo lacks LIBERO-PRO success")
        handle.attrs["collection_committed"] = True
        handle.attrs["replay_status"] = "pending_batch_validation"
        handle.flush()


def _next_queue_index(output: Path, queue: list[dict[str, Any]]) -> int:
    """Resume at the first queue item without one validated demo."""

    import h5py

    position_by_collection_index = {
        int(entry.get("collection_index", position)): position
        for position, entry in enumerate(queue)
    }
    if len(position_by_collection_index) != len(queue):
        raise ValueError("teleop queue contains duplicate collection indices")
    validated: set[int] = set()
    for path in sorted(output.glob("demo-*.hdf5")):
        match = _DEMO_INDEX.match(path.name)
        if match is None:
            continue
        collection_index = int(match.group(1))
        if collection_index not in position_by_collection_index:
            continue
        position = position_by_collection_index[collection_index]
        with h5py.File(path, "r") as handle:
            expected = queue[position]
            matches_entry = (
                str(handle.attrs.get("init_state_id", ""))
                == str(expected["init_state_id"])
                and str(handle.attrs.get("coverage_cell", ""))
                == str(expected["coverage_cell"])
            )
            complete = (
                bool(handle.attrs.get("explicit_success", False))
                and bool(handle.attrs.get("simulator_success", False))
                and (
                    bool(handle.attrs.get("collection_committed", False))
                    or bool(handle.attrs.get("replay_validated", False))
                )
            )
        if matches_entry and complete:
            validated.add(position)
    index = 0
    while index in validated:
        index += 1
    if any(value > index for value in validated):
        raise RuntimeError("validated teleop demos are non-contiguous; manual review required")
    return index


if __name__ == "__main__":
    raise SystemExit(main())
