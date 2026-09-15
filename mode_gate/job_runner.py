"""Fail-closed executor for immutable slow-loop GPU/evaluation job specs."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any

from .io_utils import atomic_write_json


SERVER_PYTHON = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")


def adopt_existing_execution(spec_path: Path, *, coordinator_pid=None) -> dict | None:
    """Find an exact in-flight job, including an orphan of a dead coordinator.

    Attaching records identity only: it never signals, restarts, or waits on the
    child. A replacement coordinator must consume its artifacts before retrying.
    """
    from .experiment_supervisor import process_identity, read_json, same_process
    spec_path = Path(spec_path).resolve()
    spec = read_json(spec_path)
    command = list(map(str, spec["command"]))
    digest = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    running_path = spec_path.with_name(spec_path.stem + ".running.json")
    record = read_json(running_path)
    if record and record.get("spec_sha256") != digest:
        raise ValueError("job spec changed after a running execution was recorded")
    if record and same_process(record):
        return record
    candidates = [command]
    if record.get("actual_command"):
        candidates.append(record["actual_command"])
    matches = []
    for proc in Path("/proc").glob("[0-9]*"):
        observed = process_identity(int(proc.name))
        if not observed:
            continue
        actual = observed["command"]
        # Python symlinks are equivalent; every job argument must still match.
        matched = any(actual[1:] == expected[1:] and actual and
                      Path(actual[0]).resolve() == Path(expected[0]).resolve()
                      for expected in candidates)
        # Accelerate's Python trainer may outlive its launcher. Match its full
        # module argument tail, not a generic Python/GPU process name.
        module = "lerobot.scripts.lerobot_train"
        if spec["schema_version"] == "coft-job-v1" and module in actual:
            matched |= any(module in expected and
                           actual[actual.index(module):] == expected[expected.index(module):]
                           for expected in candidates)
        if matched:
            try:
                if (proc / "cwd").resolve() == Path(spec["cwd"]).resolve():
                    matches.append(observed)
            except OSError:
                continue
    if not matches:
        return None
    observed = matches[0]
    record = {**observed, "spec_sha256": digest, "actual_command": observed["command"],
              "coordinator_pid": coordinator_pid, "adopted_at": time.time(),
              "related_pids": [item["pid"] for item in matches]}
    atomic_write_json(running_path, record)
    return record


def execute_job_spec(
    spec_path: Path,
    *,
    timeout_seconds: float = 86_400.0,
) -> dict[str, Any]:
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    schema = str(spec.get("schema_version", ""))
    if schema not in {
        "coft-job-v1",
        "policy-gate-job-v1",
        "counterfactual-replay-job-v2",
    }:
        raise ValueError(f"unsupported executable job schema: {schema}")
    command = tuple(map(str, spec.get("command", ())))
    cwd = Path(str(spec.get("cwd", ""))).resolve()
    _validate_command(schema, command, cwd)
    spec_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    result_path = spec_path.with_name(spec_path.stem + ".result.json")
    if result_path.is_file():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("spec_sha256") != spec_hash:
            raise ValueError("job spec changed after an execution result was recorded")
        if existing.get("completed"):
            return existing

    lock_path = spec_path.with_suffix(spec_path.suffix + ".execution.lock")
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"launched": False, "completed": False, "blocked_reason": "job_already_owned"}
        running = adopt_existing_execution(spec_path, coordinator_pid=os.getpid())
        if running:
            # An adopted orphan no longer has its original parent enforcing
            # process.wait(timeout). Preserve that bound after handoff too.
            from .experiment_supervisor import same_process
            began = float(running.get("started_at", running.get("adopted_at", time.time())))
            if time.time() - began >= timeout_seconds and same_process(running):
                pid = int(running["pid"])
                if os.getpgid(pid) == pid:
                    os.killpg(pid, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline and same_process(running):
                    time.sleep(.2)
                if same_process(running):
                    # Only this verified process group belongs to the job.
                    if os.getpgid(pid) == pid:
                        os.killpg(pid, signal.SIGKILL)
                    else:
                        os.kill(pid, signal.SIGKILL)
                result = {"schema_version": "slow-job-result-v1", "spec_sha256": spec_hash,
                          "job_schema": schema, "launched": True, "completed": False,
                          "returncode": 124, "timed_out": True, "adopted_execution": True,
                          "log_path": str(spec_path.with_name(spec_path.stem + ".log")),
                          "recorded_at": datetime.now(timezone.utc).isoformat()}
                atomic_write_json(result_path, result)
                return result
            return {"launched": False, "completed": False,
                    "blocked_reason": "existing_execution_still_running", "pid": running["pid"]}
        selected_gpu_indices: list[int] | None = None
        if schema == "coft-job-v1":
            memory = _gpu_memory_snapshot()
            minimum = float(spec.get("minimum_free_gib_per_gpu", 45.0)) * 1024
            requested = _coft_process_count(command)
            if int(spec.get("gpu_count", requested)) != requested:
                raise ValueError("co-FT GPU count differs from launcher process count")
            preference = list(
                map(
                    int,
                    spec.get("preferred_gpu_indices", [4, 5, 6, 7, 0, 1, 2, 3]),
                )
            )
            if not preference or len(set(preference)) != len(preference) or any(
                index < 0 or index >= len(memory) for index in preference
            ):
                raise ValueError("preferred_gpu_indices must be unique valid physical GPUs")
            eligible = [
                index
                for index in preference
                if memory[index]["free_mib"] >= minimum
            ]
            selected_gpu_indices = eligible[:requested]
            if len(selected_gpu_indices) != requested:
                result = {
                    "schema_version": "slow-job-result-v1",
                    "spec_sha256": spec_hash,
                    "job_schema": schema,
                    "completed": False,
                    "launched": False,
                    "blocked_reason": "insufficient_free_gpu_memory_for_bounded_coft",
                    "requested_gpu_count": requested,
                    "eligible_gpu_indices": eligible,
                    "gpu_memory_before": memory,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
                atomic_write_json(result_path, result)
                return result
        elif schema == "counterfactual-replay-job-v2":
            memory = _gpu_memory_snapshot()
            index = int(spec.get("preferred_gpu_index", -1))
            if not 0 <= index < len(memory):
                raise ValueError("counterfactual replay requires GPU index 0..7")
            device_position = command.index("--device") + 1
            if device_position >= len(command) or command[device_position] != f"cuda:{index}":
                raise ValueError("counterfactual replay GPU spec/command mismatch")
            minimum = float(spec.get("minimum_free_gib", 45.0)) * 1024
            if memory[index]["free_mib"] < minimum:
                result = {
                    "schema_version": "slow-job-result-v1",
                    "spec_sha256": spec_hash,
                    "job_schema": schema,
                    "completed": False,
                    "launched": False,
                    "blocked_reason": "insufficient_free_gpu_memory_before_replay",
                    "blocked_gpus": [index],
                    "gpu_memory_before": memory,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
                atomic_write_json(result_path, result)
                return result
        elif schema == "policy-gate-job-v1":
            memory = _gpu_memory_snapshot()
            index = int(spec.get("preferred_gpu_index", -1))
            if not 0 <= index < len(memory):
                raise ValueError("policy gate requires a physical GPU index 0..7")
            minimum = float(spec.get("minimum_free_gib", 20.0)) * 1024
            if memory[index]["free_mib"] < minimum:
                result = {
                    "schema_version": "slow-job-result-v1",
                    "spec_sha256": spec_hash,
                    "job_schema": schema,
                    "completed": False,
                    "launched": False,
                    "blocked_reason": "insufficient_free_gpu_memory_before_policy_gate",
                    "blocked_gpus": [index],
                    "gpu_memory_before": memory,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
                atomic_write_json(result_path, result)
                return result
            selected_gpu_indices = [index]
        else:
            memory = None

        log_path = spec_path.with_name(spec_path.stem + ".log")
        environment = os.environ.copy()
        environment.update(
            {
                "PYOPENGL_PLATFORM": "egl",
                "MUJOCO_GL": "egl",
                "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
                "TOKENIZERS_PARALLELISM": "false",
            }
        )
        if selected_gpu_indices is not None:
            if len(selected_gpu_indices) != 1:
                raise ValueError("this experiment supports one physical GPU without remapping")
            physical_device = f"cuda:{selected_gpu_indices[0]}"
            if schema == "coft-job-v1":
                if spec.get("physical_device", physical_device) != physical_device:
                    raise ValueError("co-FT physical device differs from selected GPU")
                environment["ACCELERATE_TORCH_DEVICE"] = physical_device
            elif schema == "policy-gate-job-v1":
                if "--device" not in command or command[command.index("--device") + 1] != physical_device:
                    raise ValueError("policy gate must use its explicit physical CUDA device")
        if environment.get("CUDA_VISIBLE_DEVICES"):
            raise ValueError("remove CUDA_VISIBLE_DEVICES: physical GPU numbering must stay unchanged")
        resume = None
        if schema == "coft-job-v1" and spec.get("resumable_checkpoints"):
            from .coft_recovery import prepare_coft_execution
            command, resume = prepare_coft_execution(command, spec)
        started = time.monotonic()
        timed_out = False
        with log_path.open("a", encoding="utf-8") as log:
            log_start_offset = log.tell()
            log.write(f"\n=== execution attempt {datetime.now(timezone.utc).isoformat()} ===\n")
            log.flush()
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            from .experiment_supervisor import process_identity
            identity = process_identity(process.pid)
            if identity:
                atomic_write_json(spec_path.with_name(spec_path.stem + ".running.json"), {
                    **identity, "actual_command": list(command), "spec_sha256": spec_hash,
                    "coordinator_pid": os.getpid(), "started_at": time.time(),
                    "log_start_offset": log_start_offset, "resume": resume,
                })
            try:
                returncode = process.wait(timeout=float(timeout_seconds))
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    returncode = process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=30)
                    returncode = 124
            log.flush()
            os.fsync(log.fileno())
        accepted_returncodes = {0, 3} if schema == "policy-gate-job-v1" else {0}
        result = {
            "schema_version": "slow-job-result-v1",
            "spec_sha256": spec_hash,
            "job_schema": schema,
            "completed": returncode in accepted_returncodes and not timed_out,
            "launched": True,
            "returncode": returncode,
            "timed_out": timed_out,
            "elapsed_seconds": time.monotonic() - started,
            "log_path": str(log_path),
            "log_start_offset": log_start_offset,
            "resume": resume,
            "gpu_memory_before": memory,
            "selected_gpu_indices": selected_gpu_indices,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(result_path, result)
        from .io_utils import AtomicJsonl
        AtomicJsonl(spec_path.with_name(spec_path.stem + ".attempts.jsonl")).append({
            **result, "event_id": hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
        })
        return result


def _validate_command(schema: str, command: tuple[str, ...], cwd: Path) -> None:
    if not cwd.is_dir() or not (cwd / "scripts/self_improve.py").is_file():
        raise ValueError("slow job cwd is not the vla-pilot-plus repository")
    if len(command) < 3 or Path(command[0]).resolve() != SERVER_PYTHON.resolve():
        raise ValueError("slow job must use the pinned hgpu1 Python")
    if schema == "coft-job-v1":
        required = ("-m", "accelerate.commands.launch", "--num_processes")
        if tuple(command[1:4]) != required:
            raise ValueError("co-FT job is not the pinned Accelerate launcher")
        processes = _coft_process_count(command)
        batch_size = _equals_argument(command, "--batch_size")
        accumulation = _equals_argument(command, "--gradient_accumulation_steps")
        if not 1 <= processes <= 2:
            raise ValueError("co-FT launcher may use only one or two processes")
        if processes * batch_size * accumulation != 32:
            raise ValueError("co-FT effective global batch must remain 32")
        if "lerobot.scripts.lerobot_train" not in command:
            raise ValueError("co-FT job does not invoke the pinned LeRobot trainer")
    elif schema == "policy-gate-job-v1":
        script = Path(command[1]).resolve()
        if script != (cwd / "scripts/self_improve.py").resolve():
            raise ValueError("policy gate job invokes an untrusted script")
        if command[2] != "policy-gate":
            raise ValueError("policy gate job invokes an unexpected command")
    else:
        script = Path(command[1]).resolve()
        if script != (cwd / "scripts/self_improve.py").resolve():
            raise ValueError("counterfactual replay invokes an untrusted script")
        if command[2] != "replay-new-policy":
            raise ValueError("counterfactual replay invokes an unexpected command")
        if "--device" not in command:
            raise ValueError("counterfactual replay must pin an explicit GPU")


def _coft_process_count(command: tuple[str, ...]) -> int:
    try:
        index = command.index("--num_processes")
        return int(command[index + 1])
    except (ValueError, IndexError) as exc:
        raise ValueError("co-FT command has no valid --num_processes") from exc


def _equals_argument(command: tuple[str, ...], name: str) -> int:
    prefix = name + "="
    values = [value[len(prefix) :] for value in command if value.startswith(prefix)]
    if len(values) != 1:
        raise ValueError(f"co-FT command requires exactly one {name}=...")
    try:
        return int(values[0])
    except ValueError as exc:
        raise ValueError(f"co-FT command has invalid {name}") from exc


def _gpu_memory_snapshot() -> list[dict[str, int]]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,memory.free,memory.used",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "nvidia-smi failed")
    rows = []
    for line in completed.stdout.splitlines():
        fields = [value.strip() for value in line.split(",")]
        if len(fields) != 3:
            raise ValueError(f"unexpected nvidia-smi row: {line!r}")
        rows.append(
            {
                "index": int(fields[0]),
                "free_mib": int(fields[1]),
                "used_mib": int(fields[2]),
            }
        )
    if [item["index"] for item in rows] != list(range(8)):
        raise RuntimeError("job runner requires exactly GPUs 0..7")
    return rows


__all__ = ["execute_job_spec"]
