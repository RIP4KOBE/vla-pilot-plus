"""Deterministic 8→16→32→64 rollout throughput benchmark."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .io_utils import atomic_write_json
from .policy_evaluator import EvaluationContext, RawEpisodeResult


def throughput_contexts_from_manifest(
    manifest: Mapping[str, Any], *, total: int = 500
) -> tuple[EvaluationContext, ...]:
    """Build a development-only load bank without touching final_sealed."""

    base = []
    for task in sorted(manifest["tasks"], key=lambda value: value["task_key"]):
        for init_state_id in task["splits"]["fixed_development_probe"]:
            base.append((task, str(init_state_id)))
    if len(base) != 80 or total <= 0:
        raise ValueError("throughput bank requires 40 tasks × 2 fixed probe states")
    contexts = []
    repeat = 0
    while len(contexts) < total:
        for task, init_state_id in base:
            material = (
                f"throughput-v1\0{manifest['manifest_sha256']}\0{task['task_key']}\0"
                f"{init_state_id}\0{repeat}"
            )
            digest = hashlib.sha256(material.encode()).digest()
            contexts.append(
                EvaluationContext(
                    suite=str(task["suite"]),
                    task_id=str(task["task_id"]),
                    task_index=int(task["task_index"]),
                    perturbation_variant=str(task["perturbation_variant"]),
                    init_state_id=init_state_id,
                    env_seed=int.from_bytes(digest[:4], "big"),
                    policy_seed=int.from_bytes(digest[4:12], "big") % (2**63 - 1),
                )
            )
            if len(contexts) == total:
                break
        repeat += 1
    if len({item.episode_key for item in contexts}) != total:
        raise RuntimeError("throughput context seeds are not isolated")
    return tuple(contexts)


class RolloutThroughputBenchmark:
    def __init__(
        self,
        *,
        executor: Callable[[str, Path, EvaluationContext], RawEpisodeResult | bool],
        sample_gpu: bool = True,
    ) -> None:
        self.executor = executor
        self.sample_gpu = bool(sample_gpu)

    def run(
        self,
        *,
        policy_id: str,
        checkpoint_path: Path,
        checkpoint_digest: str,
        contexts: Sequence[EvaluationContext],
        output_path: Path,
        worker_counts: Sequence[int] = (8, 16, 32, 64),
        warmup_contexts: int = 8,
        target_episodes_per_minute: float = 50.0,
    ) -> dict[str, Any]:
        contexts = tuple(contexts)
        if len(contexts) != 500:
            raise ValueError("formal throughput benchmark requires exactly 500 contexts")
        counts = tuple(map(int, worker_counts))
        if not counts or any(value <= 0 for value in counts) or len(set(counts)) != len(counts):
            raise ValueError("worker counts must be unique positive integers")
        if not 0 <= warmup_contexts < len(contexts):
            raise ValueError("invalid warmup context count")
        reference_signatures = None
        runs = []
        for workers in counts:
            for context in contexts[:warmup_contexts]:
                self.executor(policy_id, Path(checkpoint_path), context)
            sampler = _GpuSampler(enabled=self.sample_gpu)
            sampler.start()
            started = time.monotonic()
            rows: dict[str, dict[str, Any]] = {}

            def execute(context: EvaluationContext) -> tuple[str, dict[str, Any]]:
                item_started = time.monotonic()
                try:
                    value = self.executor(policy_id, Path(checkpoint_path), context)
                    if isinstance(value, bool):
                        value = RawEpisodeResult(value)
                    row = {
                        "valid": True,
                        "success": bool(value.success),
                        "steps": value.steps,
                        "duration_seconds": time.monotonic() - item_started,
                        "determinism_digest": dict(value.metadata).get(
                            "determinism_digest"
                        ),
                    }
                except Exception as exc:
                    row = {
                        "valid": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "duration_seconds": time.monotonic() - item_started,
                    }
                return context.episode_key, row

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(execute, context) for context in contexts]
                for future in as_completed(futures):
                    key, row = future.result()
                    rows[key] = row
            elapsed = time.monotonic() - started
            gpu_samples = sampler.stop()
            ordered = [rows[item.episode_key] for item in contexts]
            valid = [item for item in ordered if item["valid"]]
            invalid = len(ordered) - len(valid)
            durations = np.asarray(
                [item["duration_seconds"] for item in valid], dtype=np.float64
            )
            steps = [int(item["steps"]) for item in valid if item.get("steps") is not None]
            signatures = [
                (
                    item.get("success"),
                    item.get("steps"),
                    item.get("determinism_digest"),
                )
                if item["valid"]
                else ("INVALID", item.get("error_type"), item.get("error"))
                for item in ordered
            ]
            deterministic = (
                True
                if reference_signatures is None
                else signatures == reference_signatures
            )
            if reference_signatures is None:
                reference_signatures = signatures
            episodes_per_minute = len(valid) / max(elapsed, 1e-9) * 60.0
            runs.append(
                {
                    "workers": workers,
                    "attempted_episodes": len(ordered),
                    "valid_episodes": len(valid),
                    "invalid_or_crashed": invalid,
                    "invalid_crash_rate": invalid / len(ordered),
                    "elapsed_seconds": elapsed,
                    "completed_episodes_per_minute": episodes_per_minute,
                    "target_50_ep_min_met": episodes_per_minute
                    >= target_episodes_per_minute,
                    "environment_steps_per_second": (
                        sum(steps) / elapsed if len(steps) == len(valid) else None
                    ),
                    "episode_latency_p50_seconds": (
                        float(np.quantile(durations, 0.50)) if len(durations) else None
                    ),
                    "episode_latency_p95_seconds": (
                        float(np.quantile(durations, 0.95)) if len(durations) else None
                    ),
                    "seed_result_invariant_to_worker_count": deterministic,
                    "gpu": _summarize_gpu(gpu_samples),
                }
            )
        result = {
            "schema_version": "rollout-throughput-v1",
            "policy_id": policy_id,
            "checkpoint_path": str(Path(checkpoint_path).resolve()),
            "checkpoint_digest": checkpoint_digest,
            "context_count": len(contexts),
            "warmup_contexts_excluded_per_run": warmup_contexts,
            "process_isolation": "one Hydra subprocess per episode",
            "performance_target_is_not_a_functional_gate": True,
            "runs": runs,
            "passed": all(
                item["invalid_crash_rate"] < 0.01
                and item["seed_result_invariant_to_worker_count"]
                for item in runs
            ),
        }
        atomic_write_json(Path(output_path), result)
        return result


class _GpuSampler:
    def __init__(self, *, enabled: bool) -> None:
        self.enabled = enabled
        self.stop_event = threading.Event()
        self.samples: list[list[dict[str, int]]] = []
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled:
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> list[list[dict[str, int]]]:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
        return self.samples

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.samples.append(_gpu_snapshot())
            except Exception:
                pass
            self.stop_event.wait(1.0)


def _gpu_snapshot() -> list[dict[str, int]]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip())
    rows = []
    for line in completed.stdout.splitlines():
        index, utilization, used, total = [int(value.strip()) for value in line.split(",")]
        rows.append(
            {
                "index": index,
                "utilization_percent": utilization,
                "memory_used_mib": used,
                "memory_total_mib": total,
            }
        )
    return rows


def _summarize_gpu(samples: Sequence[Sequence[Mapping[str, int]]]) -> dict[str, Any]:
    by_gpu: dict[int, list[Mapping[str, int]]] = {}
    for sample in samples:
        for row in sample:
            by_gpu.setdefault(int(row["index"]), []).append(row)
    return {
        str(index): {
            "mean_utilization_percent": float(
                np.mean([row["utilization_percent"] for row in rows])
            ),
            "max_memory_used_mib": max(row["memory_used_mib"] for row in rows),
            "memory_total_mib": rows[0]["memory_total_mib"],
        }
        for index, rows in sorted(by_gpu.items())
    }


__all__ = ["RolloutThroughputBenchmark", "throughput_contexts_from_manifest"]
