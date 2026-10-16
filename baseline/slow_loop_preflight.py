"""Bounded real-data/model checks for the independent expansion campaign."""
import argparse
from pathlib import Path
from types import SimpleNamespace

from .config import cpu_environment
from .io import read_json, write_json, seed_all
from .slow_loop_expansion import prepare, prepare_stage, require_selected_gpu, configure_gpu


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    cpu_environment()
    configure_gpu(read_json(args.config)["gpu_index"])
    import torch
    from torch.utils.data import default_collate
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.policies.pi05.configuration_pi05 import PI05Config  # register the pi05 config choice
    from lerobot.datasets.factory import make_dataset
    from .slow_loop_train import adapt_dataset
    from .references.slow_loop_main_20260914.training import SourceAwareSampler
    from .references.slow_loop_main_20260914.checkpoint_math import CheckpointView, compose_policy
    from .resources import isolated_device
    from .pi05 import Pi05Runtime
    from .rollout import episode
    from .protocol import Protocol

    cfg, plan = prepare(args.config)
    runtime_cfg = cfg["runtime"]
    root = Path(runtime_cfg["output_root"])
    output = root / "preflight"
    output.mkdir(exist_ok=True)
    stage, spec = prepare_stage(cfg, plan, 0, {"policy_id": "pi05_v44", "checkpoint_path": runtime_cfg["checkpoint"]})
    source = read_json(stage / "source_sampler.json")
    policy_cfg = PreTrainedConfig.from_pretrained(runtime_cfg["checkpoint"], local_files_only=True)
    dcfg = SimpleNamespace(policy=policy_cfg, dataset=SimpleNamespace(
        repo_ids=source["repo_ids"], root=stage / "catalog", revision=None, episodes=None,
        image_transforms=SimpleNamespace(enable=False), video_backend="pyav", use_imagenet_stats=False))
    dataset, checks = adapt_dataset(make_dataset(dcfg), source)
    result = {"validation_only": True, "training_initialization": "original_v44_after_preflight",
              "mixed_input_checks": checks, "source_ratios": source["actual_source_ratios"],
              "plan_sha256": plan["plan_sha256"], "checks": {}}
    def record(name, value):
        result["checks"][name] = value
        write_json(output / "validation.json", result)
        print(name, value, flush=True)
    sampler = SourceAwareSampler(new_indices=source["new_indices"], old_ticket_indices=source["old_ticket_indices"],
               replay_indices=source["replay_indices"], num_samples=source["num_draws"], seed=runtime_cfg["seed"])
    chosen = list(sampler)[:4]
    raw = default_collate([dataset[i] for i in chosen])
    record("mixed_batch", {"batch_size": len(raw["action"]), "action_shape": list(raw["action"].shape),
                           "camera_shape": list(raw["observation.images.image"].shape), "dataset_indices": chosen})
    # Produce a genuinely sharded, zero-delta copy to test the loader that all
    # post-merge evaluations will use, without consuming a training checkpoint.
    sharded = output / "v44_sharded"
    if not sharded.exists():
        compose_policy(Path(runtime_cfg["checkpoint"]), [], sharded)
    checked = 0
    with CheckpointView(Path(runtime_cfg["checkpoint"])) as base, CheckpointView(sharded) as copy:
        if base.keys != copy.keys:
            raise ValueError("sharded v44 changed its parameter keys")
        for key in base.keys:
            if not torch.equal(base.tensor(key), copy.tensor(key)):
                raise ValueError(f"zero-delta checkpoint changed {key}")
            checked += 1
    record("sharded_checkpoint", {"tensors_checked": checked, "bitwise_equal_to_v44": True})
    with isolated_device(runtime_cfg):
        require_selected_gpu(cfg["gpu_index"])
        seed_all(runtime_cfg["seed"])
        runtime = Pi05Runtime({**runtime_cfg, "checkpoint": str(sharded)}, hash_weights=False)
        batch = runtime.preprocess(raw)
        prefix = runtime.encode(batch)
        noise = runtime.noise(4)
        with torch.no_grad(), runtime.autocast():
            images, masks = runtime.policy._preprocess_images(batch)
            native = runtime.model.sample_actions(images, masks, batch["observation.language.tokens"],
                 batch["observation.language.attention_mask"], noise=noise.clone(), num_steps=10)[..., :7]
            sampled = runtime.sample(prefix, noise.clone())
            error = float((native - sampled).abs().max())
            if not torch.allclose(native, sampled, atol=.03, rtol=.01) or not torch.isfinite(runtime.physical(sampled)).all():
                raise ValueError("sharded/native PI05 inference differs or is non-finite")
        record("native_inference", {"max_abs_error": error, "physical_actions_finite": True})
        protocol = Protocol(runtime_cfg["protocol"])
        context = protocol.contexts("demo_online_pool", runtime_cfg["seed"], [plan["task_order"][0]])[0]
        summary, _ = episode(runtime, runtime_cfg, context, max_policy_steps=10)
        if not 1 <= summary["steps"] <= 10:
            raise ValueError("bounded LIBERO-PRO execution did not complete")
        record("libero_pro_execution", {"steps": summary["steps"], "runtime_suite": context["runtime_suite"],
                                         "perturbation_variant": context["perturbation_variant"],
                                         "not_a_success_rate_measurement": True})
    result["passed"] = True
    write_json(output / "validation.json", result)


if __name__ == "__main__":
    main()
