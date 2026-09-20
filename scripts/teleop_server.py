#!/usr/bin/env python
"""Run the localhost-only hgpu1 T2 browser teleoperation queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from uuid import uuid4

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The persistent page has no model/simulator dependency and survives the
# lifecycle of each per-ticket backend.
if __name__ == "__main__" and "--portal" in sys.argv:
    from mode_gate.teleop_supervisor import portal_main
    raise SystemExit(portal_main([arg for arg in sys.argv[1:] if arg != "--portal"]))

import h5py

from mode_gate.data_pipeline import DemoWriter  # noqa: E402
from mode_gate.demo_videos import start_success_video_export  # noqa: E402
from mode_gate.io_utils import atomic_write_json, sha256_file  # noqa: E402
from mode_gate.policy_evaluator import runtime_suite_name  # noqa: E402
from mode_gate.snapshots import DecisionSnapshotStore  # noqa: E402
from mode_gate.teleop import (  # noqa: E402
    TeleopSession,
    coverage_hint_zh,
    create_teleop_app,
)
from mode_gate.teleop_guidance import LiberoTaskGuidance  # noqa: E402
from mode_gate.tickets import ExpansionTicket, TicketCollectionPlanner, operator_collection_zh  # noqa: E402


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
    value.add_argument("--collection-mode", choices=("human", "auto_skill"), default="human")
    value.add_argument("--skill-config", type=Path)
    value.add_argument("--collection-pause-file", type=Path)
    value.add_argument("--offline-precollection-root", type=Path,
                       help="explicit isolated finite batch; never an online EXPANSION/job")
    value.add_argument("--output", type=Path)
    value.add_argument("--host", default="127.0.0.1")
    value.add_argument("--port", type=int, default=8765)
    value.add_argument("--job-id")
    value.add_argument("--service-token")
    value.add_argument("--collection-round", type=int, default=1)
    value.add_argument("--completion-file", type=Path)
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
    managed_values = (args.job_id, args.service_token, args.completion_file)
    if any(value is not None for value in managed_values) and not all(
        value is not None for value in managed_values
    ):
        raise ValueError(
            "managed teleoperation requires job-id, service-token, and completion-file"
        )
    if args.collection_round < 1:
        raise ValueError("collection-round must be positive")
    ticket = ExpansionTicket.model_validate_json(
        args.ticket.read_text(encoding="utf-8")
    )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task = _manifest_task(manifest, ticket)
    offline_root, offline_provenance = _offline_collection_context(args, ticket, manifest)
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
            "observation_width": 256 if args.collection_mode == "auto_skill" else 512,
            "observation_height": 256 if args.collection_mode == "auto_skill" else 512,
            "auto_reset": False,
            # T2 stores RGB only.  Rendering two unused depth maps on every
            # keyboard step adds latency without contributing any dataset
            # field or operator feedback.
            "camera_depths": False,
            "max_episode_steps": int(args.max_steps),
        }
    )
    adapter = create_adapter("libero", env_config, device="cuda:6")
    from mode_gate.collection_initialization import activate_collection_revision
    initialization_revision = activate_collection_revision(adapter, ticket=ticket,
        ticket_path=args.ticket, manifest=manifest, offline_root=offline_root)
    output = args.output or args.ticket.parent / "raw"
    output.mkdir(parents=True, exist_ok=True)
    queue = _queue(ticket, source=args.source, ticket_root=args.ticket.parent)
    queue_sha256 = hashlib.sha256(
        json.dumps(
            queue,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    queue_index = _next_queue_index(output, queue)
    if queue_index >= len(queue):
        if args.completion_file is not None:
            _write_managed_completion(
                args.completion_file,
                job_id=str(args.job_id),
                service_token=str(args.service_token),
                collection_round=int(args.collection_round),
                ticket=ticket,
                ticket_path=args.ticket,
                queue_sha256=queue_sha256,
                queue_total=len(queue),
            )
            return 0
        raise RuntimeError("all demonstrations in this ticket are already validated")
    task_guidance: LiberoTaskGuidance | None = None

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
        nonlocal task_guidance
        entry = queue[index]
        collection_index = int(entry.get("collection_index", index))
        reset_environment(index)
        initialization = (initialization_revision.validate(adapter, entry["init_state_id"])
                          if initialization_revision is not None else None)
        task_guidance = LiberoTaskGuidance(adapter, task_id=ticket.task_id)
        writer = DemoWriter(
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

        # Preserve the task ID for matching, but train on the PRO instruction.
        writer.metadata["task_instruction"] = adapter.get_task_description()
        if initialization is not None:
            writer.metadata["initialization_revision"] = initialization["revision"]
            writer.metadata["initialization_provenance"] = json.dumps(initialization, ensure_ascii=False, sort_keys=True)
        if offline_provenance is not None:
            writer.metadata.update(collection_role=offline_provenance["collection_role"],
                offline_precollection_batch_id=offline_provenance["batch_id"],
                offline_precollection_provenance=json.dumps(offline_provenance, ensure_ascii=False, sort_keys=True))
        return writer

    writer = start(queue_index)

    def on_save(path: str) -> DemoWriter | None:
        nonlocal queue_index
        # Keep the operator path fast: commit the immutable T+1/T episode now,
        # then perform expensive 500+ step physical replay in the post-
        # collection validation job.  Replaying synchronously here made every
        # save appear frozen for minutes and temporarily destroyed the live
        # controller state.
        _commit_collected_demo(Path(path))
        # Finite, CPU-only viewing-copy export for every task and both human
        # and automatic successes. No simulator replay or scheduler is involved.
        start_success_video_export(args.ticket.parent)
        queue_index += 1
        if queue_index >= len(queue):
            if args.completion_file is not None:
                _write_managed_completion(
                    args.completion_file,
                    job_id=str(args.job_id),
                    service_token=str(args.service_token),
                    collection_round=int(args.collection_round),
                    ticket=ticket,
                    ticket_path=args.ticket,
                    queue_sha256=queue_sha256,
                    queue_total=len(queue),
                )
            return None
        return start(queue_index)

    def guidance_provider(session: TeleopSession) -> dict:
        assert task_guidance is not None
        return task_guidance.status(coverage_hint=coverage_hint_zh(
            str(session.writer.metadata["coverage_cell"])))

    def reset_current() -> DemoWriter:
        return start(queue_index)

    def task_success() -> bool:
        return bool(adapter._get_current_robosuite_env().check_success())

    task_instruction = adapter.get_task_description()
    assert task_guidance is not None
    localized = operator_collection_zh(
        ticket.collection,
        cache_path=args.ticket.parent / "operator_guide_zh.json",
        task_instruction=task_instruction,
        simulator_goals_zh=task_guidance.task_instruction_zh,
        mechanics_zh=task_guidance.mechanics_zh,
        planner_factory=lambda: TicketCollectionPlanner(
            max_provider_calls=10000,
            call_ledger_path=args.snapshot_root.parent / "audit/incidents/fixed_budget_50/factual_gemini_provider_calls.jsonl",
            thinking_level="medium",
        ),
    )
    ui_context = {
        "task_id": ticket.task_id,
        "task_instruction": task_instruction,
        "task_instruction_zh": task_guidance.task_instruction_zh,
        "must_demonstrate": list(ticket.collection.must_demonstrate),
        "must_avoid": list(ticket.collection.must_avoid),
        "must_demonstrate_zh": list(localized.must_demonstrate),
        "must_avoid_zh": list(localized.must_avoid),
        "coverage_hints_zh": {f"{cell.axis}={cell.value}": cell.operator_instruction_zh
                              for cell in localized.coverage_axes},
        "guidance_note_zh": "步骤状态来自模拟器；抓取与抬升是辅助提示，整项成功以 LIBERO-PRO 判定为准。",
        "multimodal_evidence": ticket.multimodal_evidence,
        "visual_guidance": ticket.collection.visual_guidance,
        "suggested_path": (json.loads((args.ticket.parent / "suggested_path_evidence.json").read_text())
                           if (args.ticket.parent / "suggested_path_evidence.json").is_file() else None),
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
        preview_provider=adapter.get_teleop_preview_observation if args.collection_mode == "human" else None,
        max_steps=int(env_config["max_episode_steps"]),
    )
    session.initialize()
    # Pay the one-time renderer/controller cold-start cost before the operator
    # connects.  The action and every recorded field are immediately undone,
    # leaving an exact zero-step episode while avoiding an ~800 ms first key.
    if args.collection_mode == "human":
        warmed = session.handle("w")
        if warmed["message"] != "stepped":
            raise RuntimeError(f"teleop warm-up failed: {warmed['message']}")
        undone = session.handle("u")
        if undone["message"] != "undone" or undone["steps"] != 0:
            raise RuntimeError("teleop warm-up did not restore the zero-step episode")
    else:
        from dotenv import load_dotenv
        from mode_gate.skill_collection import AutomaticCollection, CodexSkillPlanner, SkillCollectionConfig
        from mode_gate.libero_skill_controller import LiberoSkillController

        load_dotenv(REPO_ROOT / ".env", override=False)
        config = SkillCollectionConfig(**(json.loads(args.skill_config.read_text()) if args.skill_config else {}))
        if offline_root is not None:
            from scripts.offline_precollection import effective_failure_limit
            batch_plan = json.loads((offline_root / "plan.json").read_text())
            if (config.consecutive_failure_limit != effective_failure_limit(offline_root, batch_plan)
                    or not config.use_visual_observations):
                raise ValueError("offline collector failure limit and visual inputs must match its runtime control")
        planner = CodexSkillPlanner(config=config,
            ledger_path=(offline_root / "audit/account_calls.jsonl" if offline_root is not None else
                         args.snapshot_root.parent / "audit/incidents/fixed_budget_50/factual_gemini_provider_calls.jsonl"),
            queue_root=(offline_root / "codex_account_queue" if offline_root is not None else
                        args.snapshot_root.parent / "teleop_runtime/codex_account_queue"),
            pause_path=args.collection_pause_file)
        AutomaticCollection(session=session, controller_factory=LiberoSkillController, planner=planner,
            ticket=ticket.model_dump(mode="json"), output_root=args.ticket.parent / "automatic_collection",
            config=config, pause_path=args.collection_pause_file)
    app = create_teleop_app(
        session,
        service_metadata={
            "schema_version": "vls-managed-teleop-health-v1",
            "job_id": None if offline_root is not None else str(args.job_id or "manual"),
            "collection_role": "offline_precollection_for_future_experiments" if offline_root is not None else "online_or_manual",
            "offline_precollection_batch_id": offline_provenance["batch_id"] if offline_root is not None else None,
            "pid": os.getpid(),
            "service_token": str(args.service_token or "manual"),
            "collection_round": int(args.collection_round),
            "ticket_id": ticket.ticket_id,
            "ticket_sha256": sha256_file(args.ticket),
            "queue_sha256": queue_sha256,
        },
    )
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _offline_collection_context(args, ticket, manifest):
    offline_root = args.offline_precollection_root
    offline_provenance = None
    if offline_root is not None:
        from scripts.offline_precollection import validate_batch, digest
        from mode_gate.tickets import _validate_operator_chinese
        offline_root = offline_root.resolve()
        batch = json.loads((offline_root / "plan.json").read_text())
        validate_batch(batch, manifest)
        if (args.source != "ticket" or args.collection_mode != "auto_skill"
                or any(value is not None for value in (args.job_id, args.service_token, args.completion_file))
                or Path(batch["batch_root"]).resolve() != offline_root):
            raise ValueError("offline collection requires its isolated auto_skill/ticket lifecycle")
        offline_provenance = ticket.registry_summary
        context = offline_provenance.get("source_context", {})
        if (offline_provenance.get("collection_role") != batch["collection_role"]
                or offline_provenance.get("batch_id") != batch["batch_id"]
                or offline_provenance.get("batch_plan_sha256") != digest(offline_root / "plan.json")
                or context not in batch["contexts"]
                or context.get("reuse_ticket_path")
                or (ticket.suite, ticket.task_id, ticket.perturbation_variant)
                    != (context.get("suite"), context.get("task_id"), context.get("perturbation_variant"))
                or not set(ticket.init_state_ids).issubset(context["legal_demo_init_state_ids"])
                or ticket.snapshot_id != "" or ticket.eval_init_state_ids
                or ticket.failure_mode != "OFFLINE_PRECOLLECTION_NOT_A_FAILURE"
                or ticket.parent_policy_id != "not_applicable_offline_precollection"
                or args.ticket.resolve() != Path(batch["ticket_root"]).resolve() / ticket.ticket_id / "ticket.json"):
            raise ValueError("offline ticket provenance or legal initial states mismatch")
        expected_pause = offline_root / "collectors" / (ticket.ticket_id + ".pause.request")
        if args.collection_pause_file is not None and args.collection_pause_file.resolve() != expected_pause:
            raise ValueError("offline collector cannot use another lifecycle's pause file")
        args.collection_pause_file = expected_pause
        if args.output is not None and args.output.resolve() != args.ticket.resolve().parent / "raw":
            raise ValueError("offline raw output must retain the existing ticket layout")
        # A new offline ticket must never spawn a second account localization
        # request or an API client; instructions are authored in Chinese already.
        _validate_operator_chinese(ticket.collection)
    return offline_root, offline_provenance


def _write_managed_completion(
    path: Path,
    *,
    job_id: str,
    service_token: str,
    collection_round: int,
    ticket: ExpansionTicket,
    ticket_path: Path,
    queue_sha256: str,
    queue_total: int,
) -> None:
    atomic_write_json(
        path,
        {
            "schema_version": "vls-managed-teleop-completion-v1",
            "job_id": job_id,
            "service_token": service_token,
            "collection_round": int(collection_round),
            "ticket_id": ticket.ticket_id,
            "ticket_sha256": sha256_file(ticket_path),
            "queue_sha256": queue_sha256,
            "queue_total": int(queue_total),
            "queue_completed": int(queue_total),
        },
    )


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
                # Refill the actual missing initial-state slots, not the last
                # initial state appearing in each coverage category.
                from collections import Counter, defaultdict
                accepted_slots = Counter()
                for source, evidence in curation.get("accepted", {}).items():
                    path = Path(source)
                    if sha256_file(path) != evidence["sha256"]:
                        raise ValueError("accepted demonstration changed before refill planning")
                    with h5py.File(path, "r") as handle:
                        accepted_slots[(str(handle.attrs["init_state_id"]),
                                        str(handle.attrs["coverage_cell"]))] += 1
                missing_slots = defaultdict(list)
                if "accepted" in curation:
                    for entry in entries:
                        slot = (str(entry["init_state_id"]), str(entry["coverage_cell"]))
                        if accepted_slots[slot]:
                            accepted_slots[slot] -= 1
                        else:
                            missing_slots[slot[1]].append(slot[0])
                next_index = _next_collection_index(Path(ticket_root))
                refill: list[dict[str, Any]] = []
                for raw_cell in ticket.collection.coverage_axes:
                    cell = f"{raw_cell.axis}={raw_cell.value}"
                    accepted = int(dict(coverage.get(cell, {})).get("accepted", 0))
                    missing = max(0, int(raw_cell.quota) - accepted)
                    for missing_index in range(missing):
                        slots = missing_slots[cell]
                        init = slots[missing_index] if missing_index < len(slots) else init_by_cell[cell]
                        refill.append(
                            {
                                "source": "ticket",
                                "init_state_id": init,
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
    """Mark a complete, native-success episode ready for curation."""

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
        if "replay_status" not in handle.attrs:
            handle.attrs["replay_status"] = "not_requested_diagnostic_only"
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
