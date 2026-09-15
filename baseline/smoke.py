"""Bounded real-v44 integration checks with synthetic training targets.

These checks verify gradients and checkpoint wiring; they are NOT benchmark
results. An optional separate PRO simulator executes at most ten actions.
"""
import copy
import gc
import time

import torch

from .io import write_json, to_cpu, save_tensors, load_tensors, assert_finite_step
from .methods.clare import Clare
from .methods.mlr_ifa import MLRIFA
from .methods.continual_rl import ContinualRL
from .methods.rl2_vla import RL2VLA, conformal_threshold


def smoke(runtime, cfg, protocol, output, *, with_environment=False):
    from .optimization import policy_optimizer, accumulated_step
    size = cfg["batch_size"]
    raw = {"observation.images.image": torch.rand(size, 3, 256, 256),
           "observation.images.image2": torch.rand(size, 3, 256, 256),
           "observation.state": torch.zeros(size, 8), "action": torch.zeros(size, 50, 7),
           "task": ["put the red cup on the plate"] * size}
    batch = runtime.preprocess(raw)
    embedded = runtime.embed(batch)
    prefix = runtime.prefix(embedded)
    actions = batch["action"]
    result = {"schema_version": "baseline-real-v44-smoke-v1", "synthetic_training_targets": True,
              "base": runtime.identity, "started_unix": time.time(), "checks": {},
              "batch_size": size, "gradient_accumulation_steps": cfg["gradient_accumulation_steps"],
              "global_batch_size": cfg["global_batch_size"], "gradient_checkpointing": cfg["gradient_checkpointing"]}
    if runtime.device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(runtime.device)
        result["gpu"] = str(torch.cuda.get_device_properties(runtime.device))
    def record(name, value):
        result["checks"][name] = value
        write_json(output / "smoke.json", result)
        print(f"SMOKE {name}: {value}", flush=True)
    with torch.no_grad(), runtime.autocast():
        images, masks = runtime.policy._preprocess_images(batch)
        noise = runtime.noise(size)
        native = runtime.model.sample_actions(images, masks, batch["observation.language.tokens"],
                    batch["observation.language.attention_mask"], noise=noise.clone(), num_steps=cfg["inference_steps"])[..., :7]
        ours = runtime.sample(prefix, noise=noise.clone())
        error = float((native - ours).abs().max())
        if not torch.allclose(native, ours, atol=0.03, rtol=0.01):
            raise AssertionError(f"cached-prefix sampler changed v44 actions: {error}")
        if not torch.isfinite(runtime.physical(ours)).all():
            raise AssertionError("non-finite physical actions")
        record("base_sampling", {"shape": list(ours.shape), "max_error_vs_native": error})
    # Shared prefix extraction remains equivalent after disk serialization.
    save_tensors(output / "latent_roundtrip.pt", to_cpu(embedded))
    recovered = runtime.prefix(load_tensors(output / "latent_roundtrip.pt"))
    torch.testing.assert_close(runtime.sample(recovered, noise), runtime.sample(prefix, noise))
    record("latent_roundtrip", {"passed": True})
    expert_layers = runtime.model.paligemma_with_expert.gemma_expert.model.layers
    options = {**cfg["clare"], "bottleneck": 8, "ae_hidden": 16, "ae_latent": 8,
               "feature_batches": 2, "discriminator_steps": 2}
    method = Clare(runtime, options)
    report = method.train_stage("synthetic_smoke", lambda: runtime.flow_loss(prefix, actions),
                               steps=2, learning_rate=cfg["learning_rate"], max_norm=1, report=lambda _: None,
                               training_cfg=cfg)
    save_tensors(output / "clare_state.pt", method.state())
    expected = runtime.sample(prefix, noise)
    for layer in expert_layers:
        layer.mlp = layer.mlp.base
    restored = Clare(runtime, options)
    restored.restore(load_tensors(output / "clare_state.pt"))
    torch.testing.assert_close(expected, runtime.sample(prefix, noise))
    record("clare", {"trained_layers": len(report), "checkpoint_roundtrip": True})
    for layer in expert_layers:
        layer.mlp = layer.mlp.base
    del method, restored
    # Copy only the action expert, not the large frozen VLM.
    runtime.unfreeze_action_expert()
    base_action_state = runtime.trainable_state()
    base_action_state = {k: v.clone() for k, v in base_action_state.items()}
    method = MLRIFA(runtime, cfg["mlr_ifa"])
    method.prototypes = {"a": {"language": embedded["language"][0].cpu(), "visual": embedded["visual"][0].cpu()},
                         "b": {"language": -embedded["language"][0].cpu(), "visual": embedded["visual"][0].cpu()}}
    parameters = method.parameters()
    optimizer, scheduler = policy_optimizer(parameters, cfg)
    probe = runtime.model.paligemma_with_expert.gemma_expert.model.layers[0].self_attn.q_proj.weight
    before_update = probe.detach().clone()
    detail = accumulated_step(lambda: method.loss(embedded, actions, None, ["a"] * size),
                              parameters, optimizer, cfg["gradient_accumulation_steps"], cfg["max_grad_norm"], scheduler)
    norm = detail["grad_norm"]
    if norm <= 0:
        raise AssertionError("MLR-IFA has no policy gradient")
    changed = int((probe.detach() != before_update).sum())
    if not changed or any(p.dtype != torch.float32 for p in parameters):
        raise AssertionError("MLR-IFA must update fp32 trainable master weights")
    save_tensors(output / "mlr_state.pt", method.state())
    method.restore(load_tensors(output / "mlr_state.pt"))
    record("mlr_ifa", {"grad_norm": norm, "checkpoint_roundtrip": True, "changed_query_weights": changed, **detail})
    runtime.restore_partial(base_action_state)
    runtime.policy.requires_grad_(False)
    del method, optimizer, parameters, before_update, scheduler
    runtime.policy.zero_grad(set_to_none=True)
    gc.collect()
    torch.cuda.empty_cache()
    method = ContinualRL(runtime, {**cfg["continual_vla_rl"], "rank": 2, "alpha": 2})
    sampled, transitions = method.sample(prefix)
    parameters = method.parameters()
    optimizer = torch.optim.AdamW(parameters, lr=1e-5)
    loss = method.transition_loss(prefix, transitions[0], 1.0)
    norm = assert_finite_step(loss, parameters, optimizer)
    if norm <= 0:
        raise AssertionError("stochastic-flow GRPO has no LoRA gradient")
    save_tensors(output / "grpo_state.pt", method.state())
    method.restore(load_tensors(output / "grpo_state.pt"))
    record("continual_vla_rl", {"grad_norm": norm, "transitions": len(transitions), "checkpoint_roundtrip": True})
    expert = runtime.model.paligemma_with_expert.gemma_expert
    for name, wrapper in method.modules.items():
        parent, attr = name.rsplit(".", 1)
        setattr(expert.get_submodule(parent), attr, wrapper.base)
    del method, optimizer, loss, parameters
    runtime.policy.requires_grad_(False)
    options = {**cfg["rl2_vla"], "hidden_dim": 32, "hidden_layers": 2, "flow_steps": 3,
               "candidates": 2, "safe_hidden": 8, "trigger": "always"}
    method = RL2VLA(runtime, options)
    with torch.no_grad():
        latent = runtime.latent(prefix)[:1].expand(2, -1).float()
    training = {"latent": latent, "next_latent": latent.clone(),
                "actions": torch.randn(2, cfg["execution_horizon"] * 7, device=runtime.device),
                "reward": torch.tensor([0., 1.], device=runtime.device),
                "bootstrap_discount": torch.tensor([.9, 0.], device=runtime.device)}
    parameters = [p for p in method.qam.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(parameters, lr=1e-4)
    loss, detail = method.qam.losses(training)
    norm = assert_finite_step(loss, parameters, optimizer)
    method.qam.update_targets()
    logits, _ = method.detector(latent[:, None])
    dloss = torch.nn.functional.binary_cross_entropy_with_logits(logits, torch.tensor([[0.], [1.]], device=runtime.device))
    assert_finite_step(dloss, list(method.detector.parameters()), torch.optim.Adam(method.detector.parameters(), lr=1e-4))
    method.threshold = conformal_threshold([[.2, .3], [.1, .2], [.3, .4]], .25)
    save_tensors(output / "rl2_state.pt", method.state())
    method.restore(load_tensors(output / "rl2_state.pt"))
    samples, info = method.action({k: v[:1] for k, v in embedded.items()})
    assert torch.isfinite(samples).all() and info["steering"]
    record("rl2_vla", {"qam_grad_norm": norm, "checkpoint_roundtrip": True, **info, **detail})
    del method, optimizer, loss, parameters, base_action_state
    gc.collect()
    torch.cuda.empty_cache()
    if with_environment:
        from .rollout import episode
        from .experiment import task_order
        context = protocol.contexts("fixed_development_probe", cfg["seed"], task_order(cfg, protocol))[0]
        summary, _ = episode(runtime, cfg, context, max_policy_steps=10)
        record("libero_pro", {"executed_steps": summary["steps"], "runtime_suite": context["runtime_suite"],
                              "context_verified": True, "success_is_not_a_benchmark_result": summary["success"]})
    result["passed"] = True
    result["finished_unix"] = time.time()
    if runtime.device.type == "cuda":
        result["peak_allocated_mib"] = torch.cuda.max_memory_allocated(runtime.device) / (1024**2)
    write_json(output / "smoke.json", result)
