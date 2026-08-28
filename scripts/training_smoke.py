#!/usr/bin/env python
"""Create a deterministic LIBERO v3 dataset and run the bounded-GPU trainer canary."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.checkpoint_math import partition_counts  # noqa: E402
from mode_gate.io_utils import atomic_write_json, sha256_file  # noqa: E402
from mode_gate.preflight import training_smoke_source_fingerprint  # noqa: E402
from mode_gate.training import (  # noqa: E402
    TrainingSmokeConfig,
    build_lerobot_coft_command,
    write_source_sampler_manifest,
)


DEFAULT_ROOT = Path("/shared/hengyil6/vls/self_improve/preflight/training_smoke")
DEFAULT_THETA0 = Path("/shared/hengyil6/vls/models/pi05_libero_finetuned_v044")
DEFAULT_PYTHON = Path("/shared/hengyil6/vls/envs/vla-pilot/bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--theta0", type=Path, default=DEFAULT_THETA0)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--minimum-free-gib", type=float, default=45.0)
    parser.add_argument(
        "--gpu-index",
        type=int,
        action="append",
        help="Preferred physical GPU (repeat twice); defaults to free GPUs in 4,5,6,7,0,1,2,3 order.",
    )
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    args.root.mkdir(parents=True, exist_ok=True)
    dataset_root = args.root / "dataset-v1"
    _prepare_dataset(dataset_root, seed=args.seed)
    config = TrainingSmokeConfig()
    source_manifest_path = args.root / "source_sampler.json"
    source_manifest = write_source_sampler_manifest(
        source_manifest_path,
        new_indices=range(0, 64),
        old_ticket_indices={"accepted-smoke-ticket": range(64, 128)},
        replay_indices=range(128, 192),
        dataset_size=192,
        config=config,
        seed=args.seed,
    )
    if args.prepare_only:
        print(
            json.dumps(
                {
                    "dataset_root": str(dataset_root),
                    "source_manifest": source_manifest,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    gpu_memory_before = _gpu_memory_snapshot()
    preference = args.gpu_index or [4, 5, 6, 7, 0, 1, 2, 3]
    if len(preference) != len(set(preference)) or any(
        not 0 <= index <= 7 for index in preference
    ):
        raise ValueError("--gpu-index values must be unique physical indices 0..7")
    eligible = [
        index
        for index in preference
        if gpu_memory_before[index]["free_mib"] >= args.minimum_free_gib * 1024
    ]
    selected_gpu_indices = eligible[: config.gpus]
    if len(selected_gpu_indices) != config.gpus:
        result = {
            "schema_version": "hgpu1-training-smoke-v1",
            "source_fingerprint": training_smoke_source_fingerprint(REPO_ROOT),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "dataset_root": str(dataset_root),
            "dataset_info_sha256": sha256_file(dataset_root / "meta/info.json"),
            "source_manifest_sha256": source_manifest["manifest_sha256"],
            "gpu_memory_before": gpu_memory_before,
            "minimum_free_gib": args.minimum_free_gib,
            "blocked_reason": "insufficient_free_gpu_memory_for_bounded_smoke",
            "requested_gpu_count": config.gpus,
            "eligible_gpu_indices": eligible,
            "passed": False,
        }
        atomic_write_json(args.root / "result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        raise RuntimeError(
            "bounded-GPU training smoke not launched because suitable GPUs are unavailable"
        )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.root / "runs" / run_id
    log_path = args.root / "logs" / f"{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = build_lerobot_coft_command(
        python_executable=args.python,
        parent_checkpoint=args.theta0,
        dataset_root=dataset_root,
        dataset_repo_id="vls/preflight_smoke",
        source_sampler_manifest=source_manifest_path,
        output_dir=output_dir,
        seed=args.seed,
        config=config,
    )
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TORCHDYNAMO_DISABLE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
    )
    environment["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, selected_gpu_indices))
    started = time.monotonic()
    timed_out = False
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            returncode = process.wait(timeout=args.timeout_seconds)
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
    elapsed = time.monotonic() - started
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    losses = [float(value) for value in re.findall(r"loss:\s*([0-9.eE+-]+)", log_text)]
    checkpoint = output_dir / "checkpoints" / "000020" / "pretrained_model"
    counts = partition_counts(checkpoint) if checkpoint.is_dir() else {}
    passed = bool(
        returncode == 0
        and checkpoint.is_dir()
        and sum(counts.values()) == 812
        and losses
        and np.isfinite(losses).all()
    )
    result = {
        "schema_version": "hgpu1-training-smoke-v1",
        "source_fingerprint": training_smoke_source_fingerprint(REPO_ROOT),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "command": command,
        "gpu_memory_before": gpu_memory_before,
        "selected_gpu_indices": selected_gpu_indices,
        "requested_gpu_count": config.gpus,
        "per_device_batch_size": config.per_device_batch_size,
        "gradient_accumulation_steps": config.gradient_accumulation_steps,
        "effective_global_batch_size": config.global_batch_size,
        "minimum_free_gib": args.minimum_free_gib,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_seconds": args.timeout_seconds,
        "elapsed_seconds": elapsed,
        "dataset_root": str(dataset_root),
        "dataset_info_sha256": sha256_file(dataset_root / "meta/info.json"),
        "source_manifest_sha256": source_manifest["manifest_sha256"],
        "output_dir": str(output_dir),
        "checkpoint": str(checkpoint),
        "partition_counts": counts,
        "logged_losses": losses,
        "log_path": str(log_path),
        "passed": passed,
    }
    atomic_write_json(args.root / "result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        raise RuntimeError(
            f"bounded-GPU training smoke failed; inspect {log_path} (exit={returncode})"
        )
    return 0


def _gpu_memory_snapshot() -> list[dict[str, int]]:
    process = subprocess.run(
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
    if process.returncode != 0:
        raise RuntimeError(f"cannot query GPU memory: {process.stderr.strip()}")
    values = []
    for line in process.stdout.splitlines():
        fields = [item.strip() for item in line.split(",")]
        if len(fields) != 3:
            raise RuntimeError(f"unexpected nvidia-smi memory row: {line!r}")
        values.append(
            {
                "index": int(fields[0]),
                "free_mib": int(fields[1]),
                "used_mib": int(fields[2]),
            }
        )
    if [item["index"] for item in values] != list(range(8)):
        raise RuntimeError(f"expected memory data for GPUs 0..7, got {values}")
    return values


def _prepare_dataset(root: Path, *, seed: int) -> None:
    info_path = root / "meta/info.json"
    if info_path.is_file():
        info = json.loads(info_path.read_text(encoding="utf-8"))
        if info.get("total_frames") != 192 or info.get("total_episodes") != 3:
            raise RuntimeError(f"existing smoke dataset has the wrong shape: {info}")
        return
    if root.exists() and any(root.iterdir()):
        raise RuntimeError(f"refusing to overwrite incomplete dataset directory: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    features = {
        "observation.images.image": {
            "dtype": "image",
            "shape": (256, 256, 3),
            "names": ["height", "width", "channels"],
        },
        "observation.images.image2": {
            "dtype": "image",
            "shape": (256, 256, 3),
            "names": ["height", "width", "channels"],
        },
        "observation.state": {
            "dtype": "float32",
            "shape": (8,),
            "names": ["state"],
        },
        "action": {
            "dtype": "float32",
            "shape": (7,),
            "names": ["action"],
        },
    }
    dataset = LeRobotDataset.create(
        repo_id="vls/preflight_smoke",
        fps=20,
        features=features,
        root=root,
        robot_type="libero",
        use_videos=False,
    )
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:256, 0:256]
    for episode in range(3):
        for frame_index in range(64):
            phase = (episode * 64 + frame_index) / 191.0
            image = np.stack(
                [
                    (grid_x + frame_index * 3) % 256,
                    (grid_y + episode * 47) % 256,
                    ((grid_x // 2 + grid_y // 2) + frame_index) % 256,
                ],
                axis=-1,
            ).astype(np.uint8)
            image2 = np.roll(image, shift=episode + 1, axis=1)
            state = np.asarray(
                [
                    np.sin(phase * np.pi * (axis + 1))
                    + rng.normal(0.0, 1e-3)
                    for axis in range(8)
                ],
                dtype=np.float32,
            )
            action = np.asarray(
                [
                    np.cos(phase * np.pi * (axis + 1)) * 0.2
                    for axis in range(6)
                ]
                + [1.0 if frame_index < 32 else -1.0],
                dtype=np.float32,
            )
            dataset.add_frame(
                {
                    "observation.images.image": image,
                    "observation.images.image2": image2,
                    "observation.state": state,
                    "action": action,
                    "task": "pick the alphabet soup and place it in the basket",
                }
            )
        dataset.save_episode(parallel_encoding=False)


if __name__ == "__main__":
    raise SystemExit(main())
