"""Finite recovery and result publication for one existing LIBERO-PRO run.

This is part of the explicitly launched experiment, not a scheduler. It never
creates demonstrations, changes labels, loosens budgets, or advances simulator
state. The resident main process remains the sole owner of the fast loop.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any

from .io_utils import AtomicJsonl, atomic_write_json
from .slow_loop import SlowLoopStore, SlowLoopState, TERMINAL


@dataclass(frozen=True)
class RecoveryConfig:
    poll_seconds: float = 5.0
    retry_base_seconds: float = 30.0
    retry_max_seconds: float = 300.0
    max_consecutive_retries: int = 12

    def __post_init__(self):
        if min(self.poll_seconds, self.retry_base_seconds, self.retry_max_seconds,
               self.max_consecutive_retries) <= 0:
            raise ValueError("recovery limits must be positive")


def classify_failure(detail: str, returncode: int | None = None) -> str:
    value = str(detail).lower()
    # Never work around integrity, credential, scientific, or cost boundaries.
    if any(term in value for term in (
        "budget exhausted", "budget exceeded", "provider-call limit", "call limit reached",
        "maximum provider", "budgetexceeded", "insufficient_quota", "quota exhausted",
        "permission denied", "unauthorized", "invalid api key", "authenticationerror",
        "digest mismatch", "contract hash", "label contract", "group leakage",
        "non-finite", "nonfinite", "corrupt", "different policy", "identity mismatch",
        "changed after", "untrusted", "no space left on device",
    )):
        return "STOP_WITH_DIAGNOSTIC"
    if returncode in {-9, -15, 124, 137, 143} or any(term in value for term in (
        "timeout", "timed out", "connection", "network", "temporarily",
        "try again", "rate limit", "429", "502", "503", "504", "broken pipe",
        "eoferror", "out of memory", "cuda error", "egl", "nvidia-smi failed",
        "i/o error", "input/output error", "too many open files", "worker exited",
        "worker disappeared", "process exited", "connectionerror",
    )):
        return "RETRY_FROM_DURABLE_PROGRESS"
    return "STOP_WITH_DIAGNOSTIC"


def process_identity(pid: int) -> dict[str, Any] | None:
    """Bind a PID to its boot, start time, and exact command (not PID alone)."""
    try:
        proc = Path(f"/proc/{int(pid)}")
        stat = (proc / "stat").read_text().split(") ", 1)[1].split()
        if stat[0] == "Z":
            return None
        command = [p.decode() for p in (proc / "cmdline").read_bytes().split(b"\0") if p]
        if not command:
            return None
        return {"pid": int(pid), "start_ticks": stat[19], "command": command,
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    except (OSError, ValueError, IndexError, UnicodeError):
        return None


def same_process(record: dict[str, Any]) -> bool:
    observed = process_identity(record.get("pid", -1))
    return observed is not None and all(observed.get(k) == record.get(k)
                                        for k in ("pid", "start_ticks", "command", "boot_id"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.is_file() else {}


def _pause_boundary_job(root: Path, output: Path, request: dict[str, Any]):
    """Resolve a user-selected boundary without changing experiment identity."""
    if request.get("schema_version") != "pause-after-slow-loop-v1":
        raise ValueError("unsupported deferred pause request")
    plan = read_json(output / "plan.json")
    if request.get("manifest_sha256") != plan.get("manifest_sha256"):
        raise ValueError("deferred pause experiment identity mismatch")
    context_id, job_id = request.get("context_id"), request.get("slow_loop_job_id")
    context = next((c for c in plan.get("contexts", ())
                    if c["context_id"] == context_id), None)
    if context is None or not isinstance(job_id, str) or not job_id:
        raise ValueError("deferred pause must target an existing planned context")
    paths = (output / "rollouts" / context_id).glob(
        "attempt_*/episode_*/mode_gate*expansion*.json"
    )
    if not any(read_json(path).get("slow_loop_job_id") == job_id for path in paths):
        raise ValueError("deferred pause job is not bound to the selected context")
    job = SlowLoopStore(root / "slow_loop").current(job_id)
    for key in ("task_id", "init_state_id", "perturbation_variant"):
        if str(job.metadata.get(key)) != str(context.get(key)):
            raise ValueError(f"deferred pause job/context mismatch: {key}")
    return job


def request_pause_after_slow_loop(*, root: Path, output: Path, job_id: str,
                                 context_id: str) -> dict[str, Any]:
    """Arm one boundary in the existing worker; this starts no timer/process."""
    root, output = Path(root), Path(output)
    request = {
        "schema_version": "pause-after-slow-loop-v1",
        "manifest_sha256": read_json(output / "plan.json").get("manifest_sha256"),
        "slow_loop_job_id": job_id, "context_id": context_id,
        "requested_by": "user", "requested_at": datetime.now(timezone.utc).isoformat(),
        "reason": "finish the selected slow loop, then wait for explicit user resume",
    }
    _pause_boundary_job(root, output, request)
    path = output / "pause_after_slow_loop.request.json"
    existing = read_json(path)
    if existing:
        if any(existing.get(k) != request[k] for k in (
            "schema_version", "manifest_sha256", "slow_loop_job_id", "context_id"
        )):
            raise ValueError("a different deferred pause is already armed")
        return existing
    atomic_write_json(path, request)
    return request


def apply_pause_after_slow_loop(*, root: Path, output: Path) -> dict[str, Any] | None:
    """Pause only after deployment/rejection, never during evaluation or refresh.

    The main worker calls this before starting another context. The request
    remains durable across recovery; explicit resume must clear both the
    deferred request and park.request. No episode success is synthesized.
    """
    root, output = Path(root), Path(output)
    request = read_json(output / "pause_after_slow_loop.request.json")
    if not request:
        return None
    job = _pause_boundary_job(root, output, request)
    if job.state not in TERMINAL:
        return None
    parked = {
        **request, "state": "PAUSED_AFTER_SLOW_LOOP", "slow_loop_state": job.state.value,
        "boundary_reached_at": datetime.now(timezone.utc).isoformat(),
        "next_fast_loop_allowed": False,
    }
    if not (output / "park.request").exists():
        atomic_write_json(output / "park.request", parked)
    atomic_write_json(output / "pause_after_slow_loop.status.json", parked)
    return parked


def _tail(path: Path, limit: int = 32768) -> str:
    if not path.is_file():
        return ""
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - limit))
        return stream.read().decode(errors="replace")


def _publish_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def experiment_progress(root: Path, output: Path) -> dict[str, Any]:
    """Only committed, in-plan episodes count. Success is never inferred."""
    plan = read_json(output / "plan.json")
    contexts = plan.get("contexts", ())
    by_id = {str(c["context_id"]): c for c in contexts}
    if not contexts or len(by_id) != len(contexts):
        raise ValueError("experiment plan has missing or duplicate contexts")
    task_keys = {c["task_key"] for c in contexts}
    if len(task_keys) != int(plan["task_count"]):
        raise ValueError("experiment plan task breadth does not match task_count")
    completed = {}
    jobs = set()
    for row in AtomicJsonl(output / "episodes.jsonl").iter_valid():
        if row.get("event") != "EPISODE_COMPLETED":
            continue
        context_id = str(row["context_id"])
        expected = by_id.get(context_id)
        if expected is None or any(str(row.get(k)) != str(expected[k])
                                   for k in ("task_key", "runtime_suite", "init_state_id")):
            raise ValueError("completed episode identity mismatch with experiment plan")
        if not isinstance(row.get("success"), bool):
            raise ValueError("completed episode must record a native boolean success")
        if context_id in completed and completed[context_id] != row:
            raise ValueError("conflicting duplicate completed episode")
        completed[context_id] = row
        jobs.update(row.get("slow_loop_jobs", ()))
    # Include expansions whose current episode is still behind its barrier.
    for path in (output / "rollouts").glob("*/attempt_*/episode_*/mode_gate*expansion*.json"):
        value = read_json(path).get("slow_loop_job_id")
        if value:
            jobs.add(value)
    current = read_json(output / "status.json")
    if current.get("waiting_slow_loop_job_id"):
        jobs.add(current["waiting_slow_loop_job_id"])
    store = SlowLoopStore(root / "slow_loop")
    states = {job_id: store.current(job_id) for job_id in sorted(jobs) if job_id}
    pending_jobs = [job for job in states.values() if job.state not in TERMINAL]
    return {"plan": plan, "contexts": contexts, "completed": completed,
            "jobs": states, "pending_jobs": pending_jobs,
            "complete": len(completed) == len(contexts) and not pending_jobs,
            "status": current}


def publish_experiment_results(root: Path, output: Path, progress: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for context in progress["contexts"]:
        episode = progress["completed"].get(context["context_id"])
        rows.append({**context, "completed": episode is not None,
                     "success": episode["success"] if episode else None,
                     "deployment_after_episode": (episode or {}).get("deployment"),
                     "policy_id_after_episode": (episode or {}).get("deployment", {}).get("policy_id"),
                     "verifier_id_after_episode": (episode or {}).get("deployment", {}).get("verifier_id"),
                     "completed_at": (episode or {}).get("completed_at"),
                     "output_dir": (episode or {}).get("output_dir"),
                     "runtime_config_path": (str(Path(episode["output_dir"]) / "config.json")
                                             if episode and episode.get("output_dir") else None),
                     "slow_loop_jobs": (episode or {}).get("slow_loop_jobs", [])})
    successful = sum(row["success"] is True for row in rows)
    n = len(progress["completed"])
    jobs = []
    for job in progress["jobs"].values():
        metadata = job.metadata
        gate = read_json(Path(str(metadata.get("policy_gate_report_path") or "")))
        jobs.append({"job_id": job.job_id, "state": job.state.value,
                     "task_id": metadata.get("task_id"), "parent_policy_id": job.active_policy_id,
                     "deployed_policy_id": metadata.get("deployed_policy_id"),
                     "deployed_verifier_id": metadata.get("deployed_verifier_id"),
                     "gate_kind": metadata.get("gate_kind", "EXPANSION"),
                     "selection": gate.get("decision"),
                     "candidate_evaluation": gate.get("trigger_recheck"),
                     "source_artifacts": {key: value for key, value in metadata.items()
                                          if key.endswith("_path") and isinstance(value, str)}})
    provider_calls = {}
    for category in ("factual", "counterfactual"):
        path = root / "audit/incidents/fixed_budget_50" / f"{category}_gemini_provider_calls.jsonl"
        provider_calls[category] = {"ledger": str(path), "entries": sum(
            1 for _ in AtomicJsonl(path).iter_valid())}
    repo = Path(__file__).resolve().parents[1]
    configuration_files = {}
    for relative in ("configs/verifier_online.json", "configs/skill_collection.json", "configs/policy_promotion.json"):
        path = repo / relative
        if path.is_file():
            configuration_files[relative] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                             "value": read_json(path)}
    recovery_code = {}
    for relative in ("mode_gate/experiment_supervisor.py", "mode_gate/job_runner.py", "mode_gate/training.py",
                     "mode_gate/coft_recovery.py", "mode_gate/slow_worker.py", "scripts/run_full_experiment.py",
                     "scripts/keep_experiment_transport.py", "third_party/lerobot/src/lerobot/scripts/lerobot_train.py"):
        path = repo / relative
        if path.is_file():
            recovery_code[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = {
        "schema_version": "libero-pro-online-experiment-results-v1",
        "complete": progress["complete"], "updated_at": datetime.now(timezone.utc).isoformat(),
        "metric_role": "online_full_architecture_not_final_sealed",
        "final_seal_opened": False, "training_metrics_are_heldout_results": False,
        "planned_tasks": progress["plan"]["task_count"], "planned_contexts": len(rows),
        "completed_tasks": len({r["task_key"] for r in rows if r["completed"]}),
        "completed_contexts": n, "native_successes": successful,
        "online_success_rate": successful / n if n else None,
        "pending_slow_loop_jobs": [j.job_id for j in progress["pending_jobs"]],
        "task_results": rows, "slow_loop_results": jobs,
        "active_deployment": read_json(root / "registry/active.json"),
        "deployment_attribution": "ledger deployment is after episode/barrier, not necessarily the policy that acted",
        "provider_calls": provider_calls, "configuration": progress["plan"],
        "configuration_files": configuration_files, "execution_source_sha256": recovery_code,
        "recovery_log": str(output / "recovery_events.jsonl"),
    }
    atomic_write_json(output / "results.json", result)
    csv_buffer = io.StringIO()
    columns = ["task_key", "runtime_suite", "init_state_id", "completed", "success", "policy_id_after_episode", "verifier_id_after_episode", "output_dir"]
    writer = csv.DictWriter(csv_buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    _publish_text(output / "task_results.csv", csv_buffer.getvalue())
    rate = f"{successful / n:.1%}" if n else "暂无"
    _publish_text(output / "results.md", (
        "# LIBERO-PRO 全架构在线实验结果\n\n"
        f"状态：{'全部完成' if progress['complete'] else '进行中'}；任务 {result['completed_tasks']}/{result['planned_tasks']}；"
        f"context {n}/{len(rows)}。\n\n"
        f"LIBERO-PRO 原生成功：{successful}/{n}，在线成功率 {rate}。\n\n"
        "这是按实际顺序运行的在线适应结果，不是独立 held-out 或 sealed-test 成绩。"
        "训练表现、候选评估与在线任务结果分开记录。\n\n"
        "逐任务结果见 task_results.csv；配置、模型父子关系、候选评估和产物路径见 results.json。\n"
    ))
    return result


class ExperimentSupervisor:
    def __init__(self, *, root: Path, output: Path, repo_root: Path,
                 python_executable: Path, config: RecoveryConfig = RecoveryConfig()):
        self.root, self.output, self.repo_root = Path(root), Path(output), Path(repo_root)
        self.python = Path(python_executable)
        self.config = config
        self.events = AtomicJsonl(self.output / "recovery_events.jsonl")
        self.state_path = self.output / "recovery_state.json"
        self.retries = read_json(self.state_path).get("retries", {})

    def _event(self, action: str, **fields):
        value = {"action": action, "at": time.time(), **fields}
        value["event_id"] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        self.events.append(value)

    def _retry(self, key: str, detail: str, action, *, returncode=None):
        classification = classify_failure(detail, returncode)
        # Timestamps/new tracebacks must not reset the bounded retry count.
        identity = hashlib.sha256(key.encode()).hexdigest()
        state = self.retries.get(identity, {"attempts": 0, "last_at": 0})
        if classification != "RETRY_FROM_DURABLE_PROGRESS" or state["attempts"] >= self.config.max_consecutive_retries:
            return {"state": "BLOCKED_WITH_DIAGNOSTIC", "key": key, "error": detail,
                    "reason": classification, "attempts": state["attempts"]}
        delay = min(self.config.retry_max_seconds, self.config.retry_base_seconds * 2 ** min(10, state["attempts"]))
        if time.time() - state["last_at"] >= delay:
            action()
            state = {"attempts": state["attempts"] + 1, "last_at": time.time(), "key": key}
            self.retries[identity] = state
            atomic_write_json(self.state_path, {"retries": self.retries})
            self._event("AUTOMATIC_RETRY", **state)
        return {"state": "AUTOMATIC_RECOVERY", "key": key, **state}

    def _ensure_job(self, job):
        from .expansion_automation import launch_expansion_worker, _worker_process_alive
        from .job_runner import adopt_existing_execution
        record = read_json(self.root / "slow_worker_launches" / f"{job.job_id}.json")
        spec_key = {"TRAINING": "training_job_path", "RAW_REGRESSION": "policy_gate_job_path",
                    "NEW_POLICY_COUNTERFACTUAL": "new_policy_counterfactual_job_spec_path"}.get(job.state.value)
        spec_path = Path(str(job.metadata[spec_key])) if spec_key and job.metadata.get(spec_key) else None
        running = adopt_existing_execution(spec_path, coordinator_pid=record.get("pid")) if spec_path else None
        if not record or not _worker_process_alive(record):
            def launch():
                result = launch_expansion_worker(
                    job_id=job.job_id, repo_root=self.repo_root, persistent_root=self.root,
                    slow_loop_root=self.root / "slow_loop", registry_root=self.root / "registry",
                    incident_root=self.root / "incidents", snapshot_root=self.root / "snapshots",
                    python_executable=self.python, full_cycle=True,
                    gpu_index=int(read_json(self.output / "plan.json")["gpu_index"]),
                )
                self._event("SLOW_WORKER_RECOVERED", job_id=job.job_id, pid=result["pid"])
            return self._retry(f"worker:{job.job_id}", "worker disappeared", launch)
        if running:
            return {"state": "SLOW_LOOP_RUNNING", "job_id": job.job_id,
                    "slow_loop_state": job.state.value, "child_pid": running["pid"]}
        if spec_path:
            result = read_json(spec_path.with_name(spec_path.stem + ".result.json"))
            if result.get("launched") and not result.get("completed"):
                retry_path = self.root / "slow_work" / job.job_id / "retry.request"
                if retry_path.exists():
                    return {"state": "AUTOMATIC_RECOVERY_PENDING", "job_id": job.job_id}
                detail = _tail(Path(str(result.get("log_path") or "")))
                return self._retry(f"job:{job.job_id}:{job.state.value}", detail,
                    lambda: atomic_write_json(retry_path,
                                              {"reason": "automatic_transient_recovery"}),
                    returncode=result.get("returncode"))
        if job.state is SlowLoopState.RETRYABLE_ERROR:
            detail = str(job.metadata.get("last_error", ""))
            retry_path = self.root / "slow_work" / job.job_id / "retry.request"
            if retry_path.exists():
                return {"state": "AUTOMATIC_RECOVERY_PENDING", "job_id": job.job_id}
            return self._retry(f"step:{job.job_id}:{job.metadata.get('resume_state')}", detail,
                lambda: atomic_write_json(retry_path, {"reason": "automatic_transient_step_recovery"}))
        return {"state": ("WAITING_FOR_CODEX_DEMONSTRATIONS" if job.state.value in {
            "AWAITING_DEMOS", "COLLECTING", "NEEDS_MORE_DEMOS"} else "SLOW_LOOP_RUNNING"),
            "job_id": job.job_id, "slow_loop_state": job.state.value}

    def tick(self):
        progress = experiment_progress(self.root, self.output)
        if progress["complete"]:
            publish_experiment_results(self.root, self.output, progress)
            return {"state": "COMPLETE", "completed_tasks": progress["plan"]["task_count"],
                    "result_path": str(self.output / "results.json"), "main_kept_warm": True}
        status = progress["status"]
        if (self.output / "stop.request").exists():
            return {"state": "STOPPED_BY_USER"}
        if (self.output / "park.request").exists():
            return {"state": "USER_PAUSED", "main_kept_warm": True}
        actions = [self._ensure_job(job) for job in progress["pending_jobs"]]
        pid = status.get("pid")
        identity = process_identity(pid or -1)
        starting = read_json(self.output / "main_recovery_launch.json")
        if starting and same_process(starting):
            identity, pid = starting, starting["pid"]
        main_alive = identity is not None and any(
            Path(part).name == "run_full_experiment.py" for part in identity["command"]
        ) and "--supervise-existing" not in identity["command"]
        if not main_alive:
            def launch_main():
                lock_path = self.output / "worker.lock"
                with lock_path.open("a+b") as lock:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    plan = progress["plan"]
                    command = [str(self.python), "-u", str(self.repo_root / "scripts/run_full_experiment.py"),
                               "--root", str(self.root), "--output", str(self.output),
                               "--manifest", plan["manifest_path"], "--gpu-index", str(plan["gpu_index"])]
                # Supervisor singleton serializes recovery; release main's lock
                # before launch so the new main can take ownership itself.
                with (self.output / "recovered_main.log").open("ab") as log:
                    process = subprocess.Popen(command, cwd=self.repo_root, stdout=log,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                threading.Thread(target=process.wait, daemon=True).start()
                observed = process_identity(process.pid)
                if observed:
                    atomic_write_json(self.output / "main_recovery_launch.json", observed)
                self._event("MAIN_RECOVERED_AFTER_EXIT", pid=process.pid)
            detail = (str(status.get("error", "")) if status.get("state") == "STARTUP_ERROR"
                      else "worker disappeared")
            actions.append(self._retry(f"main_exit:{len(progress['completed'])}", detail, launch_main))
        elif status.get("state") == "ERROR_WARM" and pid == status.get("pid"):
            run_dir = Path(str(status.get("current_output") or ""))
            detail = str(status.get("error", "")) + "\n" + "\n".join(
                _tail(p) for p in run_dir.glob("episode_*/error.txt"))
            if not (self.output / "resume.request").exists():
                actions.append(self._retry(f"main:{status.get('current_context')}", detail,
                    lambda: atomic_write_json(self.output / "resume.request", {"automatic": True})))
        fingerprint = (len(progress["completed"]), tuple((j.job_id, j.sequence) for j in progress["jobs"].values()))
        if getattr(self, "_reported", None) != fingerprint:
            publish_experiment_results(self.root, self.output, progress)
            self._reported = fingerprint
        blocked = [a for a in actions if a["state"] == "BLOCKED_WITH_DIAGNOSTIC"]
        return {"state": "BLOCKED_WITH_DIAGNOSTIC" if blocked else "RUNNING",
                "main_pid": pid, "main_alive": main_alive,
                "completed_contexts": len(progress["completed"]),
                "planned_contexts": len(progress["contexts"]), "actions": actions}

    def run(self):
        self.output.mkdir(parents=True, exist_ok=True)
        with (self.output / "supervisor.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            while not (self.output / "supervisor.stop.request").exists():
                try:
                    status = self.tick()
                except Exception as exc:
                    status = {"state": "BLOCKED_WITH_DIAGNOSTIC", "error": f"{type(exc).__name__}: {exc}"}
                status.update(pid=os.getpid(), updated_at=time.time(), finite_experiment=True,
                              scheduled_task=False, config=asdict(self.config))
                atomic_write_json(self.output / "supervisor_status.json", status)
                if status["state"] in {"COMPLETE", "STOPPED_BY_USER"}:
                    return status
                time.sleep(self.config.poll_seconds)
        return {"state": "SUPERVISOR_STOPPED_BY_USER"}
