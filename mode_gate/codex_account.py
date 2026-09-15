"""JSON queue for a dedicated, account-authenticated Codex conversation.

The conversation itself plans. There is no API-key client, nested Codex CLI,
scheduled task, or account credential transfer. SSH carries scene/plan data.
This helper never executes a plan or changes live simulator state.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time
from uuid import uuid4


def publish_worker(root: Path, value: dict, state: str, **extra) -> None:
    """Expose the bounded account-task wait, not a fictitious background agent."""
    details = {key: value[key] for key in (
        "planner_thread_id", "experiment_output", "wait_expires_at") if key in value}
    # Liveness is disposable, unlike durable claim/response evidence. On hgpu1
    # the caller selects a private tmpfs path so idle waits cannot stall on the
    # shared disk's journal while holding the real queue lock.
    path = Path(value.get("worker_status_path") or root / "worker.json")
    write_json(path, {"worker_id": value["worker_id"],
        "updated_at": time.time(), "auth_mode": "chatgpt", "state": state,
        **details, **extra})


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with tmp.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def validate_visual_review(request: dict, value: dict) -> None:
    """Record explicit image review, not merely delivery of image filenames."""
    visuals = request.get("visual_observations") or {}
    if not visuals.get("images"):
        return  # Previously issued geometry-only requests remain compatible.
    review = value.get("visual_review") or {}
    expected = {item["image_id"] for item in visuals["images"]}
    if (review.get("manifest_sha256") != visuals.get("manifest_sha256")
            or set(review.get("viewed_image_ids", [])) != expected
            or not isinstance(review.get("assessment_zh"), str)
            or not review["assessment_zh"].strip()):
        raise ValueError("visual_review requires the current manifest hash, all viewed_image_ids and assessment_zh")


def queue_command(root: Path, operation: str, value: dict) -> dict:
    if operation == "claim":
        publish_worker(root, value, "WAITING_FOR_REQUEST")
        if not _unclaimed_requests(root):
            return {"request": None}
    root.mkdir(parents=True, exist_ok=True)
    with (root / "queue.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if operation == "claim":
            # Recheck after taking the lock; the read-only empty-queue fast
            # path above does not grant ownership or race another consumer.
            for path in _unclaimed_requests(root):
                folder = path.parent
                if (folder / "response.json").exists() or (folder / "cancelled.json").exists():
                    continue
                request = json.loads(path.read_text())
                if (request.get("planner_thread_id") is not None
                        and request["planner_thread_id"] != value.get("planner_thread_id")):
                    continue
                if request["expires_at"] <= time.time():
                    continue
                claim_path = folder / "claim.json"
                if claim_path.exists() and json.loads(claim_path.read_text())["expires_at"] > time.time():
                    continue
                claim = {"token": uuid4().hex, "worker_id": value["worker_id"],
                    "expires_at": request["expires_at"]}
                write_json(claim_path, claim)
                publish_worker(root, value, "REQUEST_CLAIMED", request_id=request["request_id"])
                return {"request": request, "claim_token": claim["token"]}
            return {"request": None}
        request_id = value.get("request_id", "")
        if not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("invalid request ID")
        folder = root / request_id
        claim = json.loads((folder / "claim.json").read_text())
        if claim["token"] != value.get("claim_token"):
            raise ValueError("response does not own request")
        if (folder / "cancelled.json").exists() or claim["expires_at"] < time.time():
            return {"accepted": False, "reason": "cancelled_or_expired"}
        if operation != "complete" or value.get("auth_mode") != "chatgpt":
            raise ValueError("only ChatGPT-account responses are accepted")
        request = json.loads((folder / "request.json").read_text())
        if request.get("schema_version") == "codex-planner-request-v1":
            from .planner_account import validate_planner_response
            validate_planner_response(request, value)
        else:
            validate_visual_review(request, value)
        if not (folder / "response.json").exists():
            write_json(folder / "response.json", value)
        return {"accepted": True}


def _unclaimed_requests(root: Path) -> list[Path]:
    """Read-only preflight: empty/expired queues do not open a writable lock."""
    ready = []
    now = time.time()
    for path in sorted(root.glob("*/request.json"), key=lambda p: p.stat().st_mtime):
        folder = path.parent
        if (folder / "response.json").exists() or (folder / "cancelled.json").exists():
            continue
        if json.loads(path.read_text())["expires_at"] <= now:
            continue
        claim = folder / "claim.json"
        if claim.exists() and json.loads(claim.read_text())["expires_at"] > now:
            continue
        ready.append(path)
    return ready


def experiment_wait_state(output: Path | None) -> str | None:
    """Only observe the explicitly selected finite run; never launch anything."""
    if output is None:
        return None
    if not output.is_dir():
        raise ValueError("the selected experiment output does not exist")
    if any((output / name).exists() for name in ("pause.request", "stop.request", "supervisor.stop.request")):
        return "STOPPED_BY_USER"
    status_path = output / "supervisor_status.json"
    status = json.loads(status_path.read_text()) if status_path.is_file() else {}
    if (status.get("collection_role") == "offline_precollection_for_future_experiments"
            and status.get("batch_state") in {"BLOCKED", "COMPLETE_WITH_BLOCKERS"}):
        # Older offline coordinators incorrectly published RUNNING/COMPLETE.
        return status["batch_state"]
    return status.get("state")


def wait_for_request(root: Path, value: dict, *, wait_seconds: float = 45,
                     experiment_output: Path | None = None) -> dict:
    """One long poll in the existing Codex turn; server data wakes that turn.

    No scheduler or external desktop IPC is involved. The account task reissues
    this bounded wait while the finite experiment is running, and must remain
    open/running. A stopped desktop task cannot be restarted by this helper.
    """
    if not 0 <= wait_seconds <= 45:
        raise ValueError("wait must be between zero and 45 seconds")
    deadline = time.monotonic() + wait_seconds
    value = {**value, "wait_expires_at": time.time() + wait_seconds}
    if experiment_output is not None:
        value["experiment_output"] = str(experiment_output)
    while True:
        state = experiment_wait_state(experiment_output)
        if state in {"COMPLETE", "COMPLETE_WITH_BLOCKERS", "BLOCKED", "INFRA_ERROR",
                     "STOPPED_BY_USER", "SUPERVISOR_STOPPED_BY_USER"}:
            publish_worker(root, value, state)
            return {"request": None, "service_state": state}
        result = queue_command(root, "claim", value)
        if result.get("request") is not None:
            return result
        if time.monotonic() >= deadline:
            return {**result, "service_state": "WAITING", "experiment_state": state}
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("claim", "complete"))
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--wait-seconds", type=float, default=0,
                        help="bounded wait for the next request; not a scheduler")
    parser.add_argument("--experiment-output", type=Path,
                        help="stop bounded account-task waits when this finite experiment ends")
    parser.add_argument("--worker-status", type=Path,
                        help="optional disposable heartbeat path (use tmpfs on hgpu1); claims stay durable")
    args = parser.parse_args()
    if not 0 <= args.wait_seconds <= 45:
        parser.error("wait must be between zero and 45 seconds")
    value = json.load(sys.stdin)
    if args.worker_status is not None:
        if not args.worker_status.is_absolute():
            parser.error("worker status path must be absolute")
        args.worker_status.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        value["worker_status_path"] = str(args.worker_status)
    result = (wait_for_request(args.queue, value, wait_seconds=args.wait_seconds,
                              experiment_output=args.experiment_output)
              if args.operation == "claim" else queue_command(args.queue, args.operation, value))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
