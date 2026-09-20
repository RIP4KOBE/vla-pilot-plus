"""Idempotent process supervision for automatic LIBERO-PRO teleoperation.

The rollout process never hosts MuJoCo teleoperation itself.  A slow-loop
worker launches one localhost-only FastAPI/uvicorn process, records its exact
owner, and resumes the same immutable ticket after a crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener
from urllib.parse import urlparse
from uuid import uuid4

from .io_utils import AtomicJsonl, atomic_write_json, sha256_file


@dataclass(frozen=True)
class TeleopServiceResult:
    state: str
    url: str
    job_id: str
    ticket_id: str
    collection_round: int
    pid: int | None = None
    service_record_path: str | None = None
    completion_path: str | None = None
    detail: str | None = None

    @property
    def ready(self) -> bool:
        return self.state in {"ready", "complete"}

    @property
    def complete(self) -> bool:
        return self.state == "complete"

    def as_metadata(self) -> dict[str, Any]:
        return {
            "teleop_service_state": self.state,
            "teleop_url": self.url,
            "teleop_job_id": self.job_id,
            "teleop_ticket_id": self.ticket_id,
            "teleop_collection_round": int(self.collection_round),
            "teleop_pid": self.pid,
            "teleop_service_record_path": self.service_record_path,
            "teleop_completion_path": self.completion_path,
            "teleop_detail": self.detail,
        }


class TeleopSupervisor:
    """Own exactly one localhost teleoperation service on an hgpu1 port."""

    def __init__(
        self,
        *,
        repo_root: Path,
        python_executable: Path,
        protocol_manifest: Path,
        snapshot_root: Path,
        runtime_root: Path,
        operator: str = "human",
        host: str = "127.0.0.1",
        port: int = 8765,
        public_port: int | None = None,
        max_steps: int = 3000,
        startup_timeout_seconds: float = 180.0,
        collection_mode: str = "human",
        skill_config: Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_executable = Path(python_executable).resolve()
        self.protocol_manifest = Path(protocol_manifest).resolve()
        self.snapshot_root = Path(snapshot_root).resolve()
        self.runtime_root = Path(runtime_root).resolve()
        self.operator = str(operator).strip()
        self.host = str(host)
        self.port = int(port)
        self.public_port = int(public_port) if public_port is not None else None
        if self.public_port is not None and (
            not 1 <= self.public_port <= 65535 or self.public_port == self.port
        ):
            raise ValueError("portal and simulation backend need distinct valid ports")
        self.max_steps = int(max_steps)
        self.startup_timeout_seconds = float(startup_timeout_seconds)
        self.collection_mode = str(collection_mode)
        self.skill_config = Path(skill_config).resolve() if skill_config is not None else None
        if self.collection_mode not in {"human", "auto_skill"}:
            raise ValueError("unknown demonstration collection mode")
        if self.host not in {"127.0.0.1", "localhost"}:
            raise ValueError("managed teleoperation must remain localhost-only")
        if not self.operator:
            raise ValueError("teleoperation operator must be non-empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("teleoperation port must be in [1, 65535]")
        if self.max_steps < 1000:
            raise ValueError("teleoperation max_steps must be at least 1000")
        if self.startup_timeout_seconds <= 0:
            raise ValueError("teleoperation startup timeout must be positive")
        if not (self.repo_root / "scripts/teleop_server.py").is_file():
            raise FileNotFoundError("teleoperation server is missing from repo_root")
        if not self.python_executable.is_file():
            raise FileNotFoundError("pinned teleoperation Python is missing")
        if not self.protocol_manifest.is_file():
            raise FileNotFoundError("frozen protocol manifest is missing")
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.runtime_root / ".teleop.lock"
        self.active_path = self.runtime_root / "active.json"
        self.events = AtomicJsonl(self.runtime_root / "events.jsonl")

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.public_port or self.port}/"

    @property
    def health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/healthz"

    @classmethod
    def recorded_backend_port(cls, runtime_root: Path, *, default: int) -> int:
        """Keep future queues on the backend selected during an operator upgrade."""
        record = cls._read_optional_json(Path(runtime_root) / "active.json")
        if not record:
            return int(default)
        address = urlparse(str(record.get("health_url", "")))
        if (address.scheme != "http" or address.hostname != "127.0.0.1"
                or address.path != "/healthz" or not address.port):
            raise ValueError("managed teleoperation record has an invalid backend URL")
        return address.port

    def ensure_running(self, job: Any) -> TeleopServiceResult:
        identity = self._identity(job)
        if (self.runtime_root / "collection.pause").exists():
            return self._result("busy", identity, detail="collection explicitly paused by user")
        if self.collection_mode == "human":
            self.ensure_portal()
        completion = self._validated_completion(identity)
        if completion is not None:
            self._finish_owned_service(identity)
            return self._result("complete", identity, completion=completion)

        wait_for: dict[str, Any] | None = None
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            health = self._health()
            if health is not None:
                if self._health_matches(health, identity):
                    self._collection_portal(health)
                    active = self._read_optional_json(self.active_path)
                    if (
                        active is None
                        or not self._record_matches(active, identity)
                        or int(active.get("pid", -1))
                        != int(health.get("pid", -2))
                    ):
                        active = self._adopt_health_locked(identity, health)
                    return self._result(
                        "ready",
                        identity,
                        record=active,
                        detail="adopted healthy managed service",
                    )
                return self._result(
                    "busy",
                    identity,
                    detail=(
                        "teleoperation port is serving another job "
                        f"{health.get('job_id', 'unknown')}"
                    ),
                )

            active = self._read_optional_json(self.active_path)
            if active is not None and self._owned_process_alive(active):
                if active.get("health_url") != self.health_url:
                    raise RuntimeError("another live backend is recorded; an explicit handoff is required")
                if self._record_matches(active, identity):
                    wait_for = active
                else:
                    return self._result(
                        "busy",
                        identity,
                        record=active,
                        detail=(
                            "another automatic teleoperation queue currently owns "
                            f"port {self.port}"
                        ),
                    )
            else:
                if self._port_in_use():
                    raise RuntimeError(
                        f"localhost:{self.port} is occupied by a non-VLS service"
                    )
                wait_for = self._launch_locked(identity)

        assert wait_for is not None
        return self._wait_until_ready(identity, wait_for)

    def _adopt_health_locked(
        self,
        identity: Mapping[str, Any],
        health: Mapping[str, Any],
    ) -> dict[str, Any]:
        token = str(health.get("service_token", ""))
        pid = int(health.get("pid", 0))
        if not token or pid <= 0:
            raise ValueError("healthy managed teleoperation lacks process identity")
        record_path = Path(identity["service_dir"]) / f"service-{token}-adopted.json"
        record = {
            "schema_version": "vls-managed-teleop-service-v1",
            "state": "READY",
            "job_id": identity["job_id"],
            "ticket_id": identity["ticket_id"],
            "ticket_path": str(identity["ticket_path"]),
            "ticket_sha256": identity["ticket_sha256"],
            "collection_round": int(identity["collection_round"]),
            "service_token": token,
            "pid": pid,
            "command": [
                str(self.python_executable),
                str(self.repo_root / "scripts/teleop_server.py"),
                token,
            ],
            "url": self.url,
            "health_url": self.health_url,
            "log_path": None,
            "completion_path": str(identity["completion_path"]),
            "service_record_path": str(record_path),
            "adopted_at": datetime.now(timezone.utc).isoformat(),
        }
        if record_path.exists():
            existing = self._read_optional_json(record_path)
            if existing is None:
                raise ValueError("managed teleoperation adoption record is unreadable")
            record = existing
        else:
            atomic_write_json(record_path, record)
        atomic_write_json(self.active_path, record)
        self._append_event("TELEOP_ADOPTED", record)
        return record

    def poll(self, job: Any) -> TeleopServiceResult:
        self.ensure_portal()
        identity = self._identity(job)
        if (self.runtime_root / "collection.pause").exists():
            return self._result("busy", identity, detail="collection explicitly paused by user")
        completion = self._validated_completion(identity)
        if completion is not None:
            self._finish_owned_service(identity)
            return self._result("complete", identity, completion=completion)

        health = self._health()
        if health is not None and self._health_matches(health, identity):
            self._collection_portal(health)
            if bool(health.get("queue_complete", False)):
                completion = self._recover_completion(identity, health)
                self._finish_owned_service(identity)
                return self._result("complete", identity, completion=completion)
            active = self._read_optional_json(self.active_path)
            return self._result("ready", identity, record=active)

        # A crashed process is restarted from the first non-committed queue
        # item by teleop_server._next_queue_index().
        return self.ensure_running(job)

    def stop(self, job: Any, *, reason: str = "operator_stop") -> TeleopServiceResult:
        """Stop only the process whose job/ticket/token ownership is verified."""

        identity = self._identity(job)
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            active = self._read_optional_json(self.active_path)
            if active is None or not self._record_matches(active, identity):
                return self._result(
                    "stopped",
                    identity,
                    detail="no owned process was active",
                )
            self._terminate_owned(active)
            stopped = {
                **active,
                "state": "STOPPED",
                "stop_reason": str(reason),
                "stopped_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_write_json(self.active_path, stopped)
            self._append_event("TELEOP_STOPPED", stopped)
            return self._result(
                "stopped",
                identity,
                record=active,
                detail=str(reason),
            )

    def _identity(self, job: Any) -> dict[str, Any]:
        ticket_path = Path(str(job.metadata["ticket_path"])).resolve()
        if not ticket_path.is_file():
            raise FileNotFoundError(f"teleoperation ticket is missing: {ticket_path}")
        ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
        ticket_id = str(job.ticket_id or ticket.get("ticket_id", ""))
        if not ticket_id or ticket_id != str(ticket.get("ticket_id", "")):
            raise ValueError("slow-loop job and teleoperation ticket disagree")
        collection_round = int(job.metadata.get("collection_round", 1))
        if collection_round < 1:
            raise ValueError("collection_round must be positive")
        service_dir = (
            self.runtime_root
            / "services"
            / str(job.job_id)
            / f"round-{collection_round:03d}"
        )
        service_dir.mkdir(parents=True, exist_ok=True)
        return {
            "job_id": str(job.job_id),
            "ticket_id": ticket_id,
            "ticket_path": ticket_path,
            "ticket_sha256": sha256_file(ticket_path),
            "collection_round": collection_round,
            "service_dir": service_dir,
            "completion_path": service_dir / "completion.json",
            "log_path": service_dir / "teleop.log",
        }

    def _launch_locked(self, identity: Mapping[str, Any]) -> dict[str, Any]:
        token = uuid4().hex
        service_record_path = (
            Path(identity["service_dir"]) / f"service-{token}.json"
        )
        command = [
            str(self.python_executable),
            str(self.repo_root / "scripts/teleop_server.py"),
            "--ticket",
            str(identity["ticket_path"]),
            "--manifest",
            str(self.protocol_manifest),
            "--snapshot-root",
            str(self.snapshot_root),
            "--source",
            "ticket",
            "--operator",
            self.operator,
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--max-steps",
            str(self.max_steps),
            "--job-id",
            str(identity["job_id"]),
            "--service-token",
            token,
            "--collection-round",
            str(identity["collection_round"]),
            "--completion-file",
            str(identity["completion_path"]),
        ]
        if self.collection_mode == "auto_skill":
            command += ["--collection-mode", "auto_skill", "--collection-pause-file",
                        str(self.runtime_root / "collection.pause")]
            if self.skill_config is not None:
                command += ["--skill-config", str(self.skill_config)]
        environment = os.environ.copy()
        environment.update(
            {
                "PYOPENGL_PLATFORM": "egl",
                "MUJOCO_GL": "egl",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "TOKENIZERS_PARALLELISM": "false",
            }
        )
        launched_at = datetime.now(timezone.utc).isoformat()
        with Path(identity["log_path"]).open("ab", buffering=0) as log:
            process = subprocess.Popen(
                command,
                cwd=self.repo_root,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        record = {
            "schema_version": "vls-managed-teleop-service-v1",
            "state": "STARTING",
            "job_id": identity["job_id"],
            "ticket_id": identity["ticket_id"],
            "ticket_path": str(identity["ticket_path"]),
            "ticket_sha256": identity["ticket_sha256"],
            "collection_round": int(identity["collection_round"]),
            "service_token": token,
            "pid": int(process.pid),
            "command": command,
            "url": self.url,
            "health_url": self.health_url,
            "log_path": str(identity["log_path"]),
            "completion_path": str(identity["completion_path"]),
            "service_record_path": str(service_record_path),
            "launched_at": launched_at,
            "collection_mode": self.collection_mode,
        }
        atomic_write_json(service_record_path, record)
        atomic_write_json(self.active_path, record)
        self._append_event("TELEOP_LAUNCHED", record)
        return record

    def _wait_until_ready(
        self,
        identity: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> TeleopServiceResult:
        deadline = time.monotonic() + self.startup_timeout_seconds
        while time.monotonic() < deadline:
            completion = self._validated_completion(identity)
            if completion is not None:
                self._finish_owned_service(identity)
                return self._result("complete", identity, completion=completion)
            health = self._health()
            if health is not None:
                if not self._health_matches(health, identity):
                    raise RuntimeError("teleoperation health identity mismatch after launch")
                self._collection_portal(health)
                ready_record = {**dict(record), "state": "READY"}
                atomic_write_json(self.active_path, ready_record)
                self._append_event("TELEOP_READY", ready_record)
                return self._result("ready", identity, record=ready_record)
            if not self._owned_process_alive(record):
                raise RuntimeError(
                    "automatic teleoperation exited before becoming ready; "
                    f"see {record.get('log_path')}"
                )
            time.sleep(0.5)
        self._terminate_owned(record)
        raise TimeoutError(
            "automatic teleoperation did not become healthy within "
            f"{self.startup_timeout_seconds:.0f}s; see {record.get('log_path')}"
        )

    def _collection_portal(self, health: Mapping[str, Any]) -> None:
        """The public page exists only while one fallback demo is requested."""
        if self.collection_mode != "auto_skill":
            return
        if health.get("collection_mode") != "auto_skill":
            raise RuntimeError("an old manual-first backend requires an explicit service handoff")
        if health.get("collection_state") in {"PLANNER_ERROR", "CONTROLLER_ERROR"}:
            raise RuntimeError(f"automatic collection failed: {health.get('collection_error')}")
        needed = bool(health.get("needs_human"))
        request = {"needs_human": needed, "queue_index": health.get("queue_index"),
            "ticket_id": health.get("ticket_id"), "job_id": health.get("job_id"),
            "collection_round": int(health.get("collection_round", 1)),
            "consecutive_failures": health.get("consecutive_failures", 0),
            "url": self.url if needed else None,
            "message_zh": "自动控制连续失败，请人工补充当前任务的一条成功示范。" if needed else "自动采集中，无需人工操作。"}
        request_path = self.runtime_root / "human_request.json"
        previous = self._read_optional_json(request_path)
        if previous != request:
            atomic_write_json(request_path, request)
            if needed:
                self._append_event("HUMAN_FALLBACK_REQUESTED", request)
                print(f"[NEEDS_HUMAN] {request['message_zh']} {self.url}", flush=True)
        if needed:
            self.ensure_portal()
        else:
            portal = self._read_optional_json(self.runtime_root / "portal.json")
            if portal and int(portal.get("backend_port", -1)) == self.port and self._owned_process_alive(portal):
                self._terminate_owned(portal)

    def _validated_completion(
        self, identity: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        value = self._read_optional_json(Path(identity["completion_path"]))
        if value is None:
            return None
        expected = {
            "schema_version": "vls-managed-teleop-completion-v1",
            "job_id": identity["job_id"],
            "ticket_id": identity["ticket_id"],
            "ticket_sha256": identity["ticket_sha256"],
            "collection_round": int(identity["collection_round"]),
        }
        mismatches = {
            key: (value.get(key), expected_value)
            for key, expected_value in expected.items()
            if value.get(key) != expected_value
        }
        if mismatches:
            raise ValueError(f"teleoperation completion identity mismatch: {mismatches}")
        if int(value.get("queue_completed", -1)) != int(value.get("queue_total", -2)):
            raise ValueError("teleoperation completion marker is incomplete")
        return value

    def _recover_completion(
        self,
        identity: Mapping[str, Any],
        health: Mapping[str, Any],
    ) -> dict[str, Any]:
        value = {
            "schema_version": "vls-managed-teleop-completion-v1",
            "job_id": identity["job_id"],
            "service_token": health.get("service_token"),
            "collection_round": int(identity["collection_round"]),
            "ticket_id": identity["ticket_id"],
            "ticket_sha256": identity["ticket_sha256"],
            "queue_sha256": health.get("queue_sha256"),
            "queue_total": int(health.get("queue_total", 0)),
            "queue_completed": int(health.get("queue_total", 0)),
            "recovered_from_health": True,
        }
        atomic_write_json(Path(identity["completion_path"]), value)
        return value

    def _finish_owned_service(self, identity: Mapping[str, Any]) -> None:
        if self.collection_mode == "auto_skill":
            self._collection_portal({**identity, "collection_mode": "auto_skill", "needs_human": False})
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            active = self._read_optional_json(self.active_path)
            if active is None or not self._record_matches(active, identity):
                return
            self._terminate_owned(active)
            completed = {
                **active,
                "state": "COMPLETED",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_write_json(self.active_path, completed)
            self._append_event("TELEOP_COMPLETED", completed)

    def _health(self) -> dict[str, Any] | None:
        try:
            # This endpoint is strictly loopback. Provider proxies inherited
            # from .env must never intercept the local service health check.
            with build_opener(ProxyHandler({})).open(
                self.health_url, timeout=0.75
            ) as response:
                if int(response.status) != 200:
                    return None
                value = json.loads(response.read().decode("utf-8"))
        except (OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None
        if value.get("service") != "vls-teleop" or value.get("ready") is not True:
            return None
        return value

    def ensure_portal(self) -> None:
        """Keep the public page alive independently of each human queue."""
        if self.public_port is None:
            return
        health_url = self.url + "healthz"
        record_path = self.runtime_root / "portal.json"
        with (self.runtime_root / ".portal.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            record = self._read_optional_json(record_path)
            health = _local_json(health_url)
            if health is not None:
                if (
                    health.get("service") != "vls-teleop-portal"
                    or int(health.get("backend_port", -1)) != self.port
                    or not record
                    or health.get("service_token") != record.get("service_token")
                ):
                    raise RuntimeError("public teleoperation port has another owner")
                return
            if record is None or not self._owned_process_alive(record):
                with socket.socket() as probe:
                    probe.settimeout(0.25)
                    if probe.connect_ex(("127.0.0.1", self.public_port)) == 0:
                        raise RuntimeError("public teleoperation port is already occupied")
                token = uuid4().hex
                command = [
                    str(self.python_executable),
                    str(self.repo_root / "scripts/teleop_server.py"),
                    "--portal", "--port", str(self.public_port),
                    "--backend-port", str(self.port), "--service-token", token,
                    "--status-path", str(self.runtime_root.parent /
                        "fixed_budget_50/formal_experiment/status.json"),
                ]
                with (self.runtime_root / "portal.log").open("ab", buffering=0) as log:
                    process = subprocess.Popen(
                        command, cwd=self.repo_root, stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True,
                    )
                record = {"pid": process.pid, "command": command,
                          "service_token": token, "url": self.url,
                          "backend_port": self.port}
                atomic_write_json(record_path, record)
            deadline = time.monotonic() + self.startup_timeout_seconds
            while time.monotonic() < deadline:
                health = _local_json(health_url)
                if health and health.get("service_token") == record["service_token"]:
                    return
                if not self._owned_process_alive(record):
                    raise RuntimeError("teleoperation portal exited; see portal.log")
                time.sleep(0.5)
            raise TimeoutError("teleoperation portal is still starting; see portal.log")

    @staticmethod
    def _health_matches(
        health: Mapping[str, Any], identity: Mapping[str, Any]
    ) -> bool:
        return (
            health.get("schema_version") == "vls-managed-teleop-health-v1"
            and str(health.get("job_id")) == str(identity["job_id"])
            and str(health.get("ticket_id")) == str(identity["ticket_id"])
            and str(health.get("ticket_sha256")) == str(identity["ticket_sha256"])
            and int(health.get("collection_round", -1))
            == int(identity["collection_round"])
        )

    def _port_in_use(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.25)
            return probe.connect_ex(("127.0.0.1", self.port)) == 0

    @staticmethod
    def _read_optional_json(path: Path) -> dict[str, Any] | None:
        path = Path(path)
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object in {path}")
        return value

    @staticmethod
    def _record_matches(
        record: Mapping[str, Any], identity: Mapping[str, Any]
    ) -> bool:
        return (
            str(record.get("job_id")) == str(identity["job_id"])
            and str(record.get("ticket_id")) == str(identity["ticket_id"])
            and str(record.get("ticket_sha256")) == str(identity["ticket_sha256"])
            and int(record.get("collection_round", -1))
            == int(identity["collection_round"])
        )

    @staticmethod
    def _owned_process_alive(record: Mapping[str, Any]) -> bool:
        try:
            pid = int(record["pid"])
            os.kill(pid, 0)
        except (KeyError, TypeError, ValueError, ProcessLookupError, PermissionError):
            return False
        cmdline = Path(f"/proc/{pid}/cmdline")
        if not cmdline.is_file():
            # Managed deployment is hgpu1/Linux.  Refuse to claim ownership on
            # hosts where the PID command cannot be verified.
            return False
        parts = cmdline.read_bytes().split(b"\0")
        expected_script = str(Path(record["command"][1])).encode("utf-8")
        expected_token = str(record.get("service_token", "")).encode("utf-8")
        return expected_script in parts and expected_token in parts

    def _terminate_owned(self, record: Mapping[str, Any]) -> None:
        if not self._owned_process_alive(record):
            return
        pid = int(record["pid"])
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        # Reap direct children so repeated collection rounds do not leave
        # zombie uvicorn processes behind.  Adopted services are not children;
        # in that case waitpid raises and process identity polling is enough.
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            try:
                waited, _ = os.waitpid(pid, os.WNOHANG)
                if waited == pid:
                    return
            except ChildProcessError:
                if not self._pid_exists(pid):
                    return
            if not self._pid_exists(pid):
                return
            time.sleep(0.1)

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(int(pid), 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def _result(
        self,
        state: str,
        identity: Mapping[str, Any],
        *,
        record: Mapping[str, Any] | None = None,
        completion: Mapping[str, Any] | None = None,
        detail: str | None = None,
    ) -> TeleopServiceResult:
        return TeleopServiceResult(
            state=state,
            url=self.url,
            job_id=str(identity["job_id"]),
            ticket_id=str(identity["ticket_id"]),
            collection_round=int(identity["collection_round"]),
            pid=int(record["pid"]) if record and record.get("pid") else None,
            service_record_path=str(
                record.get("service_record_path", identity["completion_path"])
                if record
                else identity["completion_path"]
            ),
            completion_path=str(identity["completion_path"]),
            detail=detail,
        )

    def _append_event(self, event: str, record: Mapping[str, Any]) -> None:
        self.events.append(
            {
                "event_id": f"{event}:{record['job_id']}:"
                f"{record['collection_round']}:{record.get('service_token', '')}",
                "event": event,
                "job_id": record["job_id"],
                "ticket_id": record["ticket_id"],
                "collection_round": int(record["collection_round"]),
                "pid": record.get("pid"),
                "url": self.url,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def _local_json(url: str) -> dict[str, Any] | None:
    try:
        with build_opener(ProxyHandler({})).open(url, timeout=0.75) as response:
            value = json.loads(response.read())
            return value if isinstance(value, dict) else None
    except (OSError, ValueError, HTTPError, URLError):
        return None


def create_teleop_portal_app(*, backend_port: int, service_token: str,
                            status_path: Path | None = None):
    """Loopback-only HTTP/WS relay; never steps or resets a simulator itself."""
    import asyncio
    from fastapi import FastAPI, WebSocket
    from fastapi.responses import HTMLResponse
    from websockets.asyncio.client import connect

    app = FastAPI()
    upstream = f"http://127.0.0.1:{int(backend_port)}"

    @app.get("/healthz")
    async def health():
        return {"service": "vls-teleop-portal", "ready": True,
                "pid": os.getpid(), "service_token": service_token,
                "backend_port": int(backend_port)}

    @app.get("/status")
    async def status():
        value = {}
        if status_path is not None and status_path.is_file():
            value = json.loads(status_path.read_text())
        backend = await asyncio.to_thread(_local_json, upstream + "/healthz")
        return {"experiment": value, "backend": backend}

    @app.get("/", response_class=HTMLResponse)
    async def index():
        backend = await asyncio.to_thread(_local_json, upstream + "/healthz")
        if backend and backend.get("ready") and not backend.get("queue_complete"):
            def fetch_page():
                with build_opener(ProxyHandler({})).open(upstream + "/", timeout=5) as response:
                    return response.read().decode("utf-8")
            try:
                return await asyncio.to_thread(fetch_page)
            except (OSError, HTTPError, URLError):
                pass  # Queue ended between the health request and page request.
        return """<!doctype html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LIBERO-PRO 遥操作</title><style>body{font:18px system-ui;background:#111827;
color:#eee;max-width:800px;margin:10vh auto;padding:24px}button{font:inherit;
padding:12px 24px;cursor:pointer}pre{white-space:pre-wrap;color:#9dcaff}</style>
<h1>LIBERO-PRO 遥操作入口在线</h1><p>当前没有就绪的示范队列，或后端正在准备。
采集完成后实验会自动进入后续流程。需要新示范时，刷新此页即可继续。</p>
<button onclick="location.reload()">刷新 / 进入当前任务</button><pre id="status"></pre>
<script>fetch('/status').then(r=>r.json()).then(x=>{
document.getElementById('status').textContent='阶段：'+(x.experiment.state||'等待任务')+
'\\n任务：'+(x.experiment.current_task||'—')+
'\\nSlow loop：'+(x.experiment.waiting_slow_loop_state||'—');});</script></html>"""

    async def proxy_websocket(websocket):
        await websocket.accept()
        tasks = []
        try:
            async with connect(f"ws://127.0.0.1:{int(backend_port)}/ws",
                               proxy=None, max_size=16 * 1024 * 1024) as backend:
                async def to_backend():
                    while True:
                        await backend.send(await websocket.receive_text())

                async def to_browser():
                    async for message in backend:
                        await websocket.send_text(message)

                tasks = [asyncio.create_task(to_backend()),
                         asyncio.create_task(to_browser())]
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (OSError, RuntimeError):
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await websocket.close(code=1001)
            except RuntimeError:
                pass

    # Resolve the annotation here: FastAPI's dependency inspection cannot
    # resolve a local import through this module's postponed annotations.
    proxy_websocket.__annotations__["websocket"] = WebSocket
    app.websocket("/ws")(proxy_websocket)
    return app


def portal_main(argv: list[str]) -> int:
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="Persistent localhost teleoperation portal")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--service-token", required=True)
    parser.add_argument("--status-path", type=Path)
    args = parser.parse_args(argv)
    app = create_teleop_portal_app(backend_port=args.backend_port,
                                 service_token=args.service_token,
                                 status_path=args.status_path)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


__all__ = ["TeleopServiceResult", "TeleopSupervisor", "create_teleop_portal_app"]
