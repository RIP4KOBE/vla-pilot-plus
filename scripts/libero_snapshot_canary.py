#!/usr/bin/env python
"""Real hgpu1 LIBERO snapshot and deterministic PI0.5 first-action canary."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

# This canary is explicitly for hgpu1.  Set rendering before importing torch,
# MuJoCo, Robosuite, or the adapter module.
os.environ["PYOPENGL_PLATFORM"] = "egl"
os.environ["MUJOCO_GL"] = "egl"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.env_adapters import create_adapter  # noqa: E402
from mode_gate.io_utils import atomic_write_json  # noqa: E402
from mode_gate.eval_manifest import fixed_development_probe_context  # noqa: E402
from mode_gate.preflight import snapshot_canary_source_fingerprint  # noqa: E402
from mode_gate.snapshots import DecisionSnapshotStore  # noqa: E402


class _NoPolicy:
    def capture_runtime_state(self) -> dict:
        return {}

    def restore_runtime_state(self, state: dict) -> None:
        if state:
            raise ValueError("unexpected dummy policy state")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-policy", action="store_true")
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument(
        "--theta0",
        type=Path,
        default=Path("/shared/hengyil6/vls/models/pi05_libero_finetuned_v044"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("/shared/hengyil6/vls/self_improve/preflight/snapshot_canary"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json"
        ),
    )
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    context = fixed_development_probe_context(manifest)
    adapter = create_adapter(
        "libero",
        {
            "suite_name": context["runtime_suite"],
            "task_id": context["task_index"],
            "camera_name": "agentview_image, robot0_eye_in_hand_image",
            "obs_type": "pixels_agent_pos",
            "render_mode": "rgb_array",
            "render_gpu_device_id": 8,
            "observation_width": 128,
            "observation_height": 128,
            "visualization_width": 128,
            "visualization_height": 128,
            "init_states": True,
            "auto_reset": False,
            "num_steps_wait": 0,
            "max_episode_steps": 280,
            "auto_apply_perturbations": False,
            "task_ids_filter": [context["task_index"]],
            "episode_num": 1,
        },
    )
    try:
        adapter.reset(
            seed=args.seed,
            init_state_id=int(context["init_state_id"]),
        )
        runtime_context = adapter.get_context_provenance()
        _assert_runtime_context(context, runtime_context)
        store = DecisionSnapshotStore(args.output_root / "snapshots")
        simulator_result = _simulator_canary(adapter, store, args.seed)
        policy_result = None
        if args.with_policy:
            policy_result = _policy_canary(adapter, store, args.theta0, args.seed)
        result = {
            "schema_version": "libero-pro-snapshot-canary-v2",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "source_fingerprint": snapshot_canary_source_fingerprint(REPO_ROOT),
            "seed": args.seed,
            "context": context,
            "runtime_context": runtime_context,
            "simulator": simulator_result,
            "policy": policy_result,
            "passed": simulator_result["passed"]
            and (policy_result is None or policy_result["passed"]),
        }
        atomic_write_json(args.output_root / "result.json", result)
        if not result["passed"]:
            raise RuntimeError(f"snapshot canary failed: {result}")
        print(result)
    finally:
        for environment in getattr(adapter, "_env", []):
            environment.close()
    return 0


def _assert_runtime_context(expected: dict, actual: dict) -> None:
    for field in (
        "suite",
        "runtime_suite",
        "task_id",
        "perturbation_variant",
        "init_state_id",
    ):
        if str(actual.get(field)) != str(expected.get(field)):
            raise RuntimeError(
                f"LIBERO-PRO canary context mismatch for {field}: "
                f"expected {expected.get(field)!r}, got {actual.get(field)!r}"
            )


def _simulator_canary(adapter, store: DecisionSnapshotStore, seed: int) -> dict:
    policy = _NoPolicy()
    snapshot = store.capture(
        adapter=adapter,
        policy=policy,
        policy_id="simulator-only",
        controller_state={"phase": "PREFLIGHT"},
        provenance={"seed": seed, "canary": "simulator"},
        observation_image=np.asarray(adapter.get_vlm_image()),
    )
    snapshot_manifest = json.loads(
        (store.root / snapshot.snapshot_id / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    sim = adapter._get_current_robosuite_env().sim
    captured_body_pos = np.asarray(sim.model.body_pos).copy()
    action = torch.tensor([0.1, -0.1, 0.05, 0.0, 0.0, 0.0, -1.0])
    first = adapter.step(action)
    first_state = adapter.capture_simulator_state()
    first_image = np.asarray(adapter.get_vlm_image()).copy()
    # qpos/qvel mutation alone cannot detect the cross-process LIBERO-PRO bug:
    # randomized fixture placement lives on MjModel.body_pos.  Perturb it
    # explicitly so this canary blocks any snapshot implementation that omits
    # model-level state.
    sim.model.body_pos[1, 0] += 0.01
    sim.forward()
    store.restore(snapshot.snapshot_id, adapter=adapter, policy=policy, rgb_atol=0.0)
    second = adapter.step(action)
    second_state = adapter.capture_simulator_state()
    second_image = np.asarray(adapter.get_vlm_image()).copy()
    qpos_error = float(np.max(np.abs(first_state["qpos"] - second_state["qpos"])))
    qvel_error = float(np.max(np.abs(first_state["qvel"] - second_state["qvel"])))
    rgb_error = float(
        np.abs(first_image.astype(np.float32) - second_image.astype(np.float32)).mean()
    )
    model_body_pos_error = float(
        np.max(np.abs(np.asarray(sim.model.body_pos) - captured_body_pos))
    )
    reward_equal = float(first[1]) == float(second[1])
    terminal_equal = (bool(first[2]), bool(first[3])) == (
        bool(second[2]),
        bool(second[3]),
    )
    return {
        "snapshot_id": snapshot.snapshot_id,
        "qpos_max_error": qpos_error,
        "qvel_max_error": qvel_error,
        "rgb_mean_absolute_error": rgb_error,
        "model_body_pos_max_error": model_body_pos_error,
        "snapshot_schema": snapshot_manifest.get("schema_version"),
        "reward_equal": reward_equal,
        "terminal_equal": terminal_equal,
        "passed": (
            qpos_error <= 1e-10
            and qvel_error <= 1e-10
            and rgb_error <= 0.0
            and model_body_pos_error == 0.0
            and snapshot_manifest.get("schema_version") == "decision-snapshot-v2"
            and reward_equal
            and terminal_equal
        ),
    }


def _policy_canary(adapter, store: DecisionSnapshotStore, theta0: Path, seed: int) -> dict:
    from core.pi05_steer import PI05PolicySteer
    from lerobot.policies.factory import make_pre_post_processors
    from mode_gate.checkpoint_math import checkpoint_digest
    from mode_gate.scene_encoder import (
        Pi05PrefixFeatureSource,
        Theta0SceneEncoder,
        processor_artifact_digest,
    )

    policy = PI05PolicySteer.from_pretrained(str(theta0)).to("cuda:0")
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy.config,
        pretrained_path=str(theta0),
        preprocessor_overrides={
            "device_processor": {"device": "cuda:0"},
            "tokenizer_processor": {
                "tokenizer_name": "/shared/hengyil6/vls/models/paligemma-tokenizer"
            },
        },
    )
    policy.post_init(
        adapter=adapter,
        postprocessor=postprocessor,
        sample_batch_size=1,
        policy_config={"num_inference_steps": 10, "action_chunk_horizon": 10},
    )
    policy.eval()
    policy.reset()
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    snapshot = store.capture(
        adapter=adapter,
        policy=policy,
        policy_id="theta0-pi05-v044",
        controller_state={"phase": "PREFLIGHT"},
        provenance={"seed": seed, "canary": "policy_first_action"},
        observation_image=np.asarray(adapter.get_vlm_image()),
    )
    first_observation = preprocessor(adapter.get_policy_observation(sample_num=1))
    first_chunk = policy.select_action(
        first_observation,
        generate_new_chunk=True,
        use_guidance=False,
    )
    restore_result = store.restore(
        snapshot.snapshot_id,
        adapter=adapter,
        policy=policy,
        rgb_atol=2.0,
    )
    second_observation = preprocessor(adapter.get_policy_observation(sample_num=1))
    second_chunk = policy.select_action(
        second_observation,
        generate_new_chunk=True,
        use_guidance=False,
    )
    difference = float(
        (first_chunk[0, 0].float().cpu() - second_chunk[0, 0].float().cpu())
        .abs()
        .max()
    )
    instruction = adapter.get_task_description()
    image = np.asarray(adapter.get_vlm_image()).copy()

    def batch_factory(kind, _image, text):
        raw = adapter.get_policy_observation(sample_num=1)
        copied = {
            key: (value.clone() if isinstance(value, torch.Tensor) else value)
            for key, value in raw.items()
        }
        if kind == "goal":
            for key, value in copied.items():
                if str(key).startswith("observation.images.") and isinstance(
                    value, torch.Tensor
                ):
                    copied[key] = torch.zeros_like(value)
        copied["task"] = ["" if kind == "observation" else text]
        return preprocessor(copied)

    theta0_digest = checkpoint_digest(theta0)
    tokenizer_root = Path("/shared/hengyil6/vls/models/paligemma-tokenizer")
    processor_digest = processor_artifact_digest(
        theta0,
        tokenizer_root=tokenizer_root,
    )
    scene_encoder = Theta0SceneEncoder(
        Pi05PrefixFeatureSource(policy, batch_factory),
        theta0_checksum=theta0_digest,
        processor_hash=processor_digest,
        cache_dir=store.root.parent / "scene_features",
    )
    scene = scene_encoder.encode(image, instruction)
    scene_cached = scene_encoder.encode(image, instruction)
    scene_result = {
        "feature_id": scene.feature_id,
        "joint_shape": list(scene.joint_feature.shape),
        "goal_shape": list(scene.e_goal.shape),
        "observation_shape": list(scene.e_obs.shape),
        "goal_l2_norm": float(np.linalg.norm(scene.e_goal)),
        "observation_l2_norm": float(np.linalg.norm(scene.e_obs)),
        "cache_path": str(scene.cache_path),
        "cache_replay_equal": bool(
            np.array_equal(scene.joint_feature, scene_cached.joint_feature)
        ),
        "theta0_digest": theta0_digest,
        "processor_digest": processor_digest,
    }
    scene_result["passed"] = bool(
        scene_result["joint_shape"] == [2048]
        and scene_result["goal_shape"] == [2048]
        and scene_result["observation_shape"] == [2048]
        and abs(scene_result["goal_l2_norm"] - 1.0) < 1e-3
        and abs(scene_result["observation_l2_norm"] - 1.0) < 1e-3
        and scene_result["cache_replay_equal"]
    )
    return {
        "snapshot_id": snapshot.snapshot_id,
        "restore_rgb_mean_absolute_error": restore_result["rgb_mean_absolute_error"],
        "first_action_max_error": difference,
        "action_chunk_shape": list(first_chunk.shape),
        "scene_encoder": scene_result,
        "passed": (
            difference == 0.0
            and restore_result["rgb_mean_absolute_error"] <= 2.0
            and scene_result["passed"]
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
