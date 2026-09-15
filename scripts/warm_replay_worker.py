#!/usr/bin/env python3
"""Persistent single-GPU replay worker with an explicit local plan inbox.

The worker validates and preloads one immutable policy/runtime identity, keeps
the simulator plus theta0/target models resident after a plan finishes, and
accepts only compatible signed plans from its local filesystem inbox.  A cap
extension therefore resumes from the persistent branch/provider ledgers
without another Python import, checkpoint digest, or model-load cycle.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
import uuid
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with temporary.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _append_event(path: Path, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab", buffering=0) as stream:
        stream.write(encoded)
        os.fsync(stream.fileno())


def _request_payload(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != "warm-replay-request-v1":
        raise ValueError(f"unsupported warm replay request: {path}")
    plan_path = Path(str(value.get("plan_path") or ""))
    if not plan_path.is_absolute() or not plan_path.is_file():
        raise ValueError(f"warm replay request has no absolute plan: {path}")
    return value


def _checkpoint_fingerprint(path: Path) -> str:
    path = Path(path).resolve()
    if path.is_file():
        files = [path]
    else:
        index_path = path / "model.safetensors.index.json"
        single_model = path / "model.safetensors"
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
            files = [index_path] + sorted(
                {path / str(value) for value in index["weight_map"].values()}
            )
        elif single_model.is_file():
            files = [single_model]
        else:
            files = sorted(path.glob("*.safetensors"))
    if not files or any(not value.is_file() for value in files):
        raise FileNotFoundError(f"checkpoint files are unavailable: {path}")
    inventory = []
    for value in files:
        stat = value.stat()
        inventory.append(
            {
                "path": str(value.resolve()),
                "device": stat.st_dev,
                "inode": stat.st_ino,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "ctime_ns": stat.st_ctime_ns,
            }
        )
    return hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load_digest_cache(path: Path) -> dict[Path, str]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "warm-replay-checkpoint-digest-cache-v1":
        raise ValueError(f"unsupported checkpoint digest cache: {path}")
    result: dict[Path, str] = {}
    for entry in value.get("entries", ()):
        checkpoint = Path(str(entry["checkpoint_path"])).resolve()
        if _checkpoint_fingerprint(checkpoint) != str(entry["fingerprint"]):
            continue
        result[checkpoint] = str(entry["checkpoint_digest"])
    return result


def _status_value(
    *,
    state: str,
    device: str,
    active_request_id: str | None,
    active_plan_path: str | None,
    warm: bool,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "warm-replay-worker-status-v1",
        "pid": os.getpid(),
        "state": state,
        "device": device,
        "warm": bool(warm),
        "active_request_id": active_request_id,
        "active_plan_path": active_plan_path,
        "updated_at": _now(),
        "detail": detail or {},
    }


def _serve(args: argparse.Namespace) -> int:
    if float(args.poll_seconds) <= 0:
        raise ValueError("--poll-seconds must be positive")
    queue_dir = Path(args.queue_dir).resolve()
    queue_dir.mkdir(parents=True, exist_ok=True)
    status_path = queue_dir / "status.json"
    event_path = queue_dir / "events.jsonl"
    stop_path = queue_dir / "stop.request.json"
    digest_cache_path = (
        Path(args.checkpoint_digest_cache).resolve()
        if args.checkpoint_digest_cache is not None
        else queue_dir / "checkpoint_digests.json"
    )
    lock_stream = (queue_dir / "worker.lock").open("a+b")
    try:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError(f"another warm replay worker owns {queue_dir}") from exc

    from dotenv import load_dotenv

    load_dotenv(Path(args.repo_root).resolve() / ".env", override=False)
    from mode_gate.offline_replay import (
        WarmReplayApplicationPool,
        execute_replay_plan,
        preload_replay_plan,
    )

    pool = WarmReplayApplicationPool()
    digest_cache = _load_digest_cache(digest_cache_path)
    stopping = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    def run_request(request_id: str, plan_path: Path, request_file: Path | None) -> None:
        processing_path = (
            request_file.with_suffix(".processing.json")
            if request_file is not None
            else None
        )
        if request_file is not None:
            os.replace(request_file, processing_path)
        _atomic_json(
            status_path,
            _status_value(
                state="running",
                device=args.device,
                active_request_id=request_id,
                active_plan_path=str(plan_path),
                warm=pool.is_warm,
            ),
        )
        _append_event(
            event_path,
            {
                "schema_version": "warm-replay-worker-event-v1",
                "event": "REQUEST_STARTED",
                "request_id": request_id,
                "plan_path": str(plan_path),
                "at": _now(),
            },
        )
        try:
            if not pool.is_warm:
                preload = preload_replay_plan(
                    plan_path,
                    repo_root=Path(args.repo_root),
                    device=args.device,
                    application_pool=pool,
                    checkpoint_digest_cache=digest_cache,
                )
                _append_event(
                    event_path,
                    {
                        "schema_version": "warm-replay-worker-event-v1",
                        "event": "APPLICATION_WARM",
                        "request_id": request_id,
                        "at": _now(),
                        "detail": preload,
                    },
                )
            result = execute_replay_plan(
                plan_path,
                repo_root=Path(args.repo_root),
                device=args.device,
                application_pool=pool,
                checkpoint_digest_cache=digest_cache,
            )
            terminal = {
                "schema_version": "warm-replay-response-v1",
                "request_id": request_id,
                "ok": True,
                "plan_path": str(plan_path),
                "finished_at": _now(),
                "result": result,
            }
            suffix = "done"
            state = "idle"
            detail = {
                "last_request_id": request_id,
                "last_plan_sha256": result.get("plan_sha256"),
                "complete": result.get("complete"),
            }
        except Exception as exc:  # keep the resident app for a cap-extension retry
            terminal = {
                "schema_version": "warm-replay-response-v1",
                "request_id": request_id,
                "ok": False,
                "plan_path": str(plan_path),
                "finished_at": _now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            suffix = "failed"
            state = "idle_needs_request"
            detail = {
                "last_request_id": request_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        response_path = queue_dir / f"response-{request_id}.{suffix}.json"
        _atomic_json(response_path, terminal)
        if processing_path is not None and processing_path.exists():
            processing_path.unlink()
        _append_event(
            event_path,
            {
                "schema_version": "warm-replay-worker-event-v1",
                "event": "REQUEST_FINISHED",
                "request_id": request_id,
                "ok": bool(terminal["ok"]),
                "response_path": str(response_path),
                "at": _now(),
            },
        )
        _atomic_json(
            status_path,
            _status_value(
                state=state,
                device=args.device,
                active_request_id=None,
                active_plan_path=None,
                warm=pool.is_warm,
                detail=detail,
            ),
        )

    try:
        initial_plan = Path(args.initial_plan).resolve()
        run_request("initial", initial_plan, None)
        while not stopping:
            if stop_path.is_file():
                stopping = True
                break
            requests = sorted(
                path
                for path in queue_dir.glob("request-*.json")
                if ".processing." not in path.name
            )
            if not requests:
                time.sleep(float(args.poll_seconds))
                continue
            request_file = requests[0]
            payload = _request_payload(request_file)
            run_request(
                str(payload["request_id"]),
                Path(str(payload["plan_path"])).resolve(),
                request_file,
            )
    finally:
        _atomic_json(
            status_path,
            _status_value(
                state="stopping",
                device=args.device,
                active_request_id=None,
                active_plan_path=None,
                warm=pool.is_warm,
            ),
        )
        pool.close()
        if stop_path.exists():
            stop_path.unlink()
        _atomic_json(
            status_path,
            _status_value(
                state="stopped",
                device=args.device,
                active_request_id=None,
                active_plan_path=None,
                warm=False,
            ),
        )
        lock_stream.close()
    return 0


def _submit(args: argparse.Namespace) -> int:
    queue_dir = Path(args.queue_dir).resolve()
    plan_path = Path(args.plan).resolve()
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)
    request_id = uuid.uuid4().hex
    request_path = queue_dir / f"request-{request_id}.json"
    _atomic_json(
        request_path,
        {
            "schema_version": "warm-replay-request-v1",
            "request_id": request_id,
            "plan_path": str(plan_path),
            "submitted_at": _now(),
        },
    )
    print(json.dumps({"request_id": request_id, "request_path": str(request_path)}))
    return 0


def _seed_validated_digest(args: argparse.Namespace) -> int:
    """Record a digest already validated by a live one-shot replay process."""

    queue_dir = Path(args.queue_dir).resolve()
    cache_path = queue_dir / "checkpoint_digests.json"
    plan_path = Path(args.plan).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    expected_plan_hash = str(plan.get("plan_sha256") or "")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    actual_plan_hash = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual_plan_hash != expected_plan_hash:
        raise ValueError("cannot seed a digest from a plan with an invalid signature")
    pid_root = Path("/proc") / str(int(args.validated_pid))
    cmdline = (pid_root / "cmdline").read_bytes().split(b"\0")
    decoded = {value.decode(errors="replace") for value in cmdline if value}
    if str(plan_path) not in decoded or "replay-new-policy" not in decoded:
        raise ValueError("validated PID is not executing the exact replay plan")
    stdout_path = (pid_root / "fd/1").resolve()
    if "Using backend:" not in stdout_path.read_text(encoding="utf-8", errors="replace"):
        raise ValueError("validated PID has not progressed past replay-plan validation")
    checkpoint = Path(str(plan["checkpoint_path"])).resolve()
    entry = {
        "checkpoint_path": str(checkpoint),
        "checkpoint_digest": str(plan["checkpoint_digest"]),
        "fingerprint": _checkpoint_fingerprint(checkpoint),
        "source_plan_sha256": expected_plan_hash,
        "validated_pid": int(args.validated_pid),
        "validation_log": str(stdout_path),
        "seeded_at": _now(),
    }
    entries = []
    if cache_path.is_file():
        current = json.loads(cache_path.read_text(encoding="utf-8"))
        if current.get("schema_version") != "warm-replay-checkpoint-digest-cache-v1":
            raise ValueError(f"unsupported checkpoint digest cache: {cache_path}")
        entries = [
            value
            for value in current.get("entries", ())
            if str(value.get("checkpoint_path")) != str(checkpoint)
        ]
    entries.append(entry)
    _atomic_json(
        cache_path,
        {
            "schema_version": "warm-replay-checkpoint-digest-cache-v1",
            "entries": entries,
            "updated_at": _now(),
        },
    )
    print(json.dumps({"checkpoint_digest_cache": str(cache_path), "entry": entry}))
    return 0


def _status(args: argparse.Namespace) -> int:
    path = Path(args.queue_dir).resolve() / "status.json"
    if not path.is_file():
        print(json.dumps({"state": "absent", "status_path": str(path)}))
        return 1
    print(path.read_text(encoding="utf-8").strip())
    return 0


def _stop(args: argparse.Namespace) -> int:
    queue_dir = Path(args.queue_dir).resolve()
    path = queue_dir / "stop.request.json"
    _atomic_json(
        path,
        {
            "schema_version": "warm-replay-stop-v1",
            "requested_at": _now(),
        },
    )
    print(json.dumps({"stop_request_path": str(path)}))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--initial-plan", type=Path, required=True)
    serve.add_argument("--queue-dir", type=Path, required=True)
    serve.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    serve.add_argument("--device", default="cuda:6")
    serve.add_argument("--poll-seconds", type=float, default=1.0)
    serve.add_argument("--checkpoint-digest-cache", type=Path)
    submit = commands.add_parser("submit")
    submit.add_argument("--queue-dir", type=Path, required=True)
    submit.add_argument("--plan", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--queue-dir", type=Path, required=True)
    seed = commands.add_parser("seed-validated-digest")
    seed.add_argument("--queue-dir", type=Path, required=True)
    seed.add_argument("--plan", type=Path, required=True)
    seed.add_argument("--validated-pid", type=int, required=True)
    stop = commands.add_parser("stop")
    stop.add_argument("--queue-dir", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "serve":
        return _serve(args)
    if args.command == "submit":
        return _submit(args)
    if args.command == "status":
        return _status(args)
    if args.command == "seed-validated-digest":
        return _seed_validated_digest(args)
    if args.command == "stop":
        return _stop(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
