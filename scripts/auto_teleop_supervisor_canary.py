#!/usr/bin/env python
"""Launch and stop one real managed LIBERO-PRO teleoperation service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.io_utils import atomic_write_json, sha256_file  # noqa: E402
from mode_gate.teleop_supervisor import TeleopSupervisor  # noqa: E402


DEFAULT_ROOT = Path(
    "/shared/hengyil6/vls/self_improve/canaries/auto_teleop_supervisor_v1"
)
DEFAULT_PYTHON = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ticket", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json"
        ),
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=Path("/shared/hengyil6/vls/self_improve/snapshots"),
    )
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    ticket_root = args.output / "ticket"
    ticket_root.mkdir(parents=True, exist_ok=True)
    ticket_path = ticket_root / "ticket.json"
    if ticket_path.exists():
        if sha256_file(ticket_path) != sha256_file(args.source_ticket):
            raise ValueError("canary ticket changed between runs")
    else:
        shutil.copy2(args.source_ticket, ticket_path)
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    job = SimpleNamespace(
        job_id="auto-teleop-supervisor-canary",
        ticket_id=str(ticket["ticket_id"]),
        metadata={"ticket_path": str(ticket_path), "collection_round": 1},
    )
    supervisor = TeleopSupervisor(
        repo_root=REPO_ROOT,
        python_executable=DEFAULT_PYTHON,
        protocol_manifest=args.manifest,
        snapshot_root=args.snapshot_root,
        runtime_root=args.output / "runtime",
        operator="canary",
        port=args.port,
        max_steps=3000,
        startup_timeout_seconds=180.0,
    )
    started = supervisor.ensure_running(job)
    if started.state != "ready":
        raise RuntimeError(f"managed teleoperation did not become ready: {started}")
    active = json.loads(
        (args.output / "runtime/active.json").read_text(encoding="utf-8")
    )
    stopped = supervisor.stop(job, reason="canary_complete")
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        try:
            import os

            os.kill(int(active["pid"]), 0)
        except ProcessLookupError:
            break
        time.sleep(0.25)
    process_alive_after_stop = True
    try:
        import os

        os.kill(int(active["pid"]), 0)
    except ProcessLookupError:
        process_alive_after_stop = False
    report = {
        "schema_version": "auto-teleop-supervisor-canary-v1",
        "passed": (
            started.state == "ready"
            and stopped.state == "stopped"
            and not process_alive_after_stop
        ),
        "ticket_id": ticket["ticket_id"],
        "ticket_sha256": sha256_file(ticket_path),
        "url": started.url,
        "pid": started.pid,
        "service_record_path": started.service_record_path,
        "log_path": active["log_path"],
        "process_alive_after_stop": process_alive_after_stop,
        "gpu_count_requested": 0,
    }
    atomic_write_json(args.output / "canary_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
