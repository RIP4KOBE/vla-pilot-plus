#!/usr/bin/env python
"""Minimal two-rank NCCL synchronization check for hgpu1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import socket

from accelerate import Accelerator
import torch


DEFAULT_OUTPUT = Path(
    "/shared/hengyil6/vls/self_improve/preflight/nccl_canary/result.json"
)


def main() -> int:
    accelerator = Accelerator()
    rank = accelerator.process_index
    value = torch.tensor(float(rank + 1), device=accelerator.device)
    accelerator.wait_for_everyone()
    total = accelerator.reduce(value, reduction="sum")
    accelerator.wait_for_everyone()
    record = {
        "host": socket.gethostname(),
        "rank": rank,
        "local_rank": accelerator.local_process_index,
        "world_size": accelerator.num_processes,
        "device": str(accelerator.device),
        "sum": float(total.item()),
        "nccl_p2p_disable": os.environ.get("NCCL_P2P_DISABLE"),
        "nccl_ib_disable": os.environ.get("NCCL_IB_DISABLE"),
    }
    print(json.dumps(record, sort_keys=True), flush=True)
    expected_world_size = int(os.environ.get("VLS_EXPECTED_WORLD_SIZE", "2"))
    expected_sum = expected_world_size * (expected_world_size + 1) / 2
    if (
        accelerator.num_processes != expected_world_size
        or record["sum"] != expected_sum
    ):
        raise RuntimeError(f"NCCL canary failed: {record}")
    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        output = Path(os.environ.get("VLS_NCCL_RESULT", str(DEFAULT_OUTPUT)))
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.parent / f".{output.name}.{os.getpid()}.tmp"
        source_digest = hashlib.sha256()
        source_digest.update(b"scripts/nccl_canary.py\0")
        source_digest.update(Path(__file__).read_bytes())
        source_digest.update(b"\0")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": "hgpu1-nccl-canary-v1",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "host": socket.gethostname(),
                    "world_size": expected_world_size,
                    "sum": record["sum"],
                    "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                    "source_fingerprint": source_digest.hexdigest(),
                    "passed": True,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, output)
    accelerator.wait_for_everyone()
    accelerator.end_training()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
