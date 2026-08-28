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
        "counterfactual-replay-job-v1",
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
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
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
            if len(preference) != 8 or set(preference) != set(range(8)):
                raise ValueError("preferred_gpu_indices must be a permutation of 0..7")
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
        elif schema == "counterfactual-replay-job-v1":
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
            environment["CUDA_VISIBLE_DEVICES"] = ",".join(
                map(str, selected_gpu_indices)
            )
        started = time.monotonic()
        timed_out = False
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
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
            "gpu_memory_before": memory,
            "selected_gpu_indices": selected_gpu_indices,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(result_path, result)
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
