#!/usr/bin/env python
"""Strict one-task LIBERO-PRO init-state generator for hgpu1."""

from __future__ import annotations

import argparse
import gc
import hashlib
import os
from pathlib import Path
import pickle
import random
import resource
import sys
import zipfile

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
LIBERO_PRO_ROOT = REPO_ROOT / "third_party" / "libero_pro"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(LIBERO_PRO_ROOT) not in sys.path:
    sys.path.insert(0, str(LIBERO_PRO_ROOT))


def generate_task(
    *,
    bddl_file: Path,
    output_file: Path,
    num_inits: int,
    seed: int,
    egl_device_id: int,
) -> dict[str, object]:
    """Generate exactly ``num_inits`` states or fail without publishing."""

    if os.environ.get("MUJOCO_GL", "").lower() != "egl":
        raise RuntimeError("LIBERO-PRO init worker requires MUJOCO_GL=egl")
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    target_limit = min(int(hard_limit), 65_536)
    if soft_limit < target_limit:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target_limit, hard_limit))
    from patches.robosuite_egl import apply_robosuite_egl_compat

    apply_robosuite_egl_compat()
    # Import only after applying the PyOpenGL compatibility patch.
    from libero.libero.envs import OffScreenRenderEnv

    bddl_file = bddl_file.resolve(strict=True)
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    states: list[np.ndarray] = []
    environment = None
    try:
        random.seed(int(seed))
        np.random.seed(int(seed))
        environment = OffScreenRenderEnv(
            bddl_file_name=str(bddl_file),
            camera_heights=128,
            camera_widths=128,
            render_gpu_device_id=int(egl_device_id),
            hard_reset=False,
        )
        for index in range(int(num_inits)):
            per_state_seed = (int(seed) + index) % (2**32)
            random.seed(per_state_seed)
            np.random.seed(per_state_seed)
            seed_environment = getattr(environment, "seed", None)
            if callable(seed_environment):
                seed_environment(per_state_seed)
            environment.reset()
            state = np.asarray(environment.get_sim_state()).copy()
            if not np.isfinite(state).all():
                raise RuntimeError(
                    f"non-finite simulator state at index {index}: {bddl_file}"
                )
            states.append(state)
            if (index + 1) % 10 == 0 or index + 1 == int(num_inits):
                print(
                    {
                        "task": bddl_file.stem,
                        "generated": index + 1,
                        "target": int(num_inits),
                    },
                    flush=True,
                )
    finally:
        if environment is not None:
            environment.close()
        del environment
        gc.collect()

    if len(states) != int(num_inits):
        raise RuntimeError(
            f"init-state generation incomplete: expected {num_inits}, got {len(states)}"
        )
    unique_states = {
        hashlib.sha256(np.ascontiguousarray(state).tobytes()).digest()
        for state in states
    }
    if len(unique_states) != int(num_inits):
        raise RuntimeError(
            f"init-state generation produced duplicates: "
            f"expected {num_inits}, got {len(unique_states)} unique"
        )
    payload = np.asarray(states)
    payload_sha256 = hashlib.sha256(
        np.ascontiguousarray(payload).tobytes()
    ).hexdigest()
    temporary = output_file.with_name(f".{output_file.name}.tmp-{os.getpid()}")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            members = {
                "archive/data.pkl": pickle.dumps(payload, protocol=4),
                "archive/version": b"1",
            }
            for name, content in members.items():
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
        os.replace(temporary, output_file)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "task": bddl_file.stem,
        "output": str(output_file),
        "num_inits": len(states),
        "unique_inits": len(unique_states),
        "payload_sha256": payload_sha256,
        "file_sha256": hashlib.sha256(output_file.read_bytes()).hexdigest(),
        "seed": int(seed),
        "egl_device_id": int(egl_device_id),
        "nofile_soft_limit": resource.getrlimit(resource.RLIMIT_NOFILE)[0],
    }


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--bddl-file", type=Path, required=True)
    command.add_argument("--output-file", type=Path, required=True)
    command.add_argument("--num-inits", type=int, default=50)
    command.add_argument("--seed", type=int, required=True)
    command.add_argument("--egl-device-id", type=int, default=8)
    return command


def main() -> int:
    args = parser().parse_args()
    result = generate_task(
        bddl_file=args.bddl_file,
        output_file=args.output_file,
        num_inits=args.num_inits,
        seed=args.seed,
        egl_device_id=args.egl_device_id,
    )
    print(result, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
