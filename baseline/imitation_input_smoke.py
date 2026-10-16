"""Bounded real-demonstration validation; outputs never enter the campaign."""
import argparse
import gc
from pathlib import Path

from .config import cpu_environment, load_config
from .io import read_json, write_json, safe_output, save_tensors, load_tensors, seed_all, to_cpu


def run(runtime, cfg, protocol, source, output):
    import torch
    from .data import demo_loader, normalized_batch
    from .methods.clare import Clare
    from .methods.mlr_ifa import MLRIFA
    from .optimization import policy_optimizer, accumulated_step
    from .rollout import episode
    seed_all(cfg["seed"])
    raw = next(iter(demo_loader(source, runtime, cfg["batch_size"], cfg["seed"])))
    batch, actions, padding = normalized_batch(runtime, raw)
    embedded = runtime.embed(batch)
    prefix = runtime.prefix(embedded)
    noise = runtime.noise(cfg["batch_size"])
    result = {"validation_only": True, "campaign_will_restart_from_v44": True,
              "base": runtime.identity, "source_conversion": source["policy_input"],
              "task_key": source["task_key"], "batch_size": cfg["batch_size"],
              "gradient_accumulation_steps": cfg["gradient_accumulation_steps"],
              "global_batch_size": cfg["global_batch_size"], "optimizer_updates_per_method": 2,
              "checks": {}}
    def record(key, value):
        result["checks"][key] = value
        write_json(output / "validation.json", result)
        print(f"INPUT_SMOKE {key}: {value}", flush=True)
    with torch.no_grad(), runtime.autocast():
        images, masks = runtime.policy._preprocess_images(batch)
        native = runtime.model.sample_actions(images, masks, batch["observation.language.tokens"],
            batch["observation.language.attention_mask"], noise=noise.clone(), num_steps=cfg["inference_steps"])[..., :7]
        sampled = runtime.sample(prefix, noise.clone())
        error = float((native - sampled).abs().max())
        if not torch.allclose(native, sampled, atol=.03, rtol=.01) or not torch.isfinite(runtime.physical(sampled)).all():
            raise AssertionError("native and baseline v44 inference differ on corrected demonstration inputs")
        record("v44_native_inference", {"max_abs_error": error, "physical_actions_finite": True})
    save_tensors(output / "embedded.pt", to_cpu(embedded))
    reloaded = load_tensors(output / "embedded.pt")
    torch.testing.assert_close(runtime.sample(runtime.prefix(reloaded), noise), sampled)
    record("converted_feature_cache_roundtrip", {"passed": True})
    # Only the validation loop lengths are bounded. Adapter dimensions and the
    # common optimizer, accumulation and normalizers match the experiment.
    options = {**cfg["clare"], "feature_batches": 2, "discriminator_steps": 2}
    clare = Clare(runtime, options)
    metrics = []
    clare.train_stage(source["task_key"], lambda: runtime.flow_loss(prefix, actions, padding=padding), steps=2,
                      learning_rate=cfg["learning_rate"], max_norm=cfg["max_grad_norm"],
                      report=metrics.append, training_cfg=cfg)
    if not any(v["phase"] == "adapter" and v["grad_norm"] > 0 for v in metrics):
        raise AssertionError("CLARE has no gradient on corrected demonstrations")
    save_tensors(output / "clare.pt", clare.state())
    expected = runtime.sample(prefix, noise)
    layers = runtime.model.paligemma_with_expert.gemma_expert.model.layers
    for layer in layers:
        layer.mlp = layer.mlp.base
    restored = Clare(runtime, options)
    restored.restore(load_tensors(output / "clare.pt"))
    torch.testing.assert_close(runtime.sample(prefix, noise), expected)
    record("clare", {"training": metrics, "checkpoint_roundtrip": True})
    for layer in layers:
        layer.mlp = layer.mlp.base
    del clare, restored
    gc.collect()
    method = MLRIFA(runtime, cfg["mlr_ifa"])
    method.add_prototype(source["task_key"], save_prototype(output, embedded))
    parameters = method.parameters()
    optimizer, scheduler = policy_optimizer(parameters, cfg)
    probe = runtime.model.paligemma_with_expert.gemma_expert.model.layers[0].self_attn.q_proj.weight
    before = probe.detach().clone()
    metrics = [accumulated_step(lambda: method.loss(embedded, actions, padding, [source["task_key"]] * len(actions)),
                parameters, optimizer, cfg["gradient_accumulation_steps"], cfg["max_grad_norm"], scheduler) for _ in range(2)]
    changed = int((probe.detach() != before).sum())
    if not changed or not any(v["grad_norm"] > 0 for v in metrics):
        raise AssertionError("MLR-IFA did not update its action expert")
    method.stages.append(source["task_key"])
    save_tensors(output / "mlr_ifa.pt", method.state())
    expected = runtime.sample(prefix, noise)
    with torch.no_grad():
        probe[0, 0] += .1
    method.restore(load_tensors(output / "mlr_ifa.pt"))
    torch.testing.assert_close(runtime.sample(prefix, noise), expected)
    record("mlr_ifa", {"training": metrics, "changed_query_weights": changed, "checkpoint_roundtrip": True})
    context = next(c for c in protocol.contexts("demo_online_pool", cfg["seed"], [source["task_key"]])
                   if str(c["init_state_id"]) in source["init_state_ids"])
    summary, _ = episode(runtime, {**cfg, "method": "mlr_ifa"}, context, method=method, max_policy_steps=20)
    if not 1 <= summary["steps"] <= 20:
        raise AssertionError("bounded environment execution did not complete")
    record("libero_pro_execution", {"steps": summary["steps"], "runtime_suite": context["runtime_suite"],
                                   "perturbation_variant": context["perturbation_variant"],
                                   "validation_only": True, "not_a_success_rate_measurement": True})
    result["passed"] = True
    write_json(output / "validation.json", result)


def save_prototype(output, embedded):
    path = output / "embedded_prototype.pt"
    save_tensors(path, {"embedded": to_cpu(embedded)})
    return [{"path": str(path)}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--task-data", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args()
    cpu_environment()
    cfg = load_config(args.config)
    from .protocol import Protocol
    from .resources import isolated_device
    from .pi05 import Pi05Runtime
    from .scope import check_input_root
    check_input_root(args.task_data, cfg)
    source = read_json(args.task_data)["tasks"][0]
    protocol = Protocol(cfg["protocol"])
    protocol.validate_training_source(source)
    with isolated_device(cfg):
        output = safe_output(cfg["output_root"], args.run_name)
        write_json(output / "config.json", cfg)
        try:
            run(Pi05Runtime(cfg), cfg, protocol, source, output)
            write_json(output / "status.json", {"status": "complete", "validation_only": True})
        except Exception as exc:
            write_json(output / "status.json", {"status": "failed", "error": str(exc), "validation_only": True})
            raise


if __name__ == "__main__":
    main()
