"""Real training loops; stage checkpoints resume without touching deployment."""
from pathlib import Path
import random

import torch
from torch.nn import functional as F

from .artifacts import make_method, save_stage, load_stage
from .data import load_task_sources, demo_loader, endless, normalized_batch, cache_demonstrations, latent_batch
from .io import append_json, write_json, read_json, load_tensors, digest, assert_finite_step, to_cpu, seed_all
from .protocol import TRAIN_SPLIT
from .experiment import task_order, training_contexts
from .optimization import policy_optimizer, accumulated_step


def logger(path, every):
    def report(value):
        if value.get("step", 0) % every == 0 or value.get("step") == 1:
            append_json(path, value)
            print(value, flush=True)
    return report


def train_imitation(runtime, cfg, protocol, output, task_data, resume=None, task_keys=None):
    seed_all(cfg["seed"])
    sources = load_task_sources(task_data, protocol)
    method = make_method(runtime, cfg)
    previous = load_stage(resume, runtime, protocol, method, cfg) if resume else None
    source_by_key = {v["task_key"]: v for v in sources}
    if task_keys and any(key not in source_by_key for key in task_keys):
        raise ValueError("selected task has no demonstration source")
    order = [key for key in (task_keys or task_order(cfg, protocol)) if key in source_by_key]
    write_json(output / "task_data.json", {"schema_version": "baseline-task-data-v1", "tasks": sources, "order": order})
    rng = random.Random(cfg["seed"] + len(method.stages))
    memory = None
    if cfg["method"] == "mlr_ifa":
        from .methods.mlr_ifa import ByteReplay
        memory = ByteReplay(cfg["mlr_ifa"]["memory_bytes"], cfg["seed"])
        memory.entries = previous["replay"] if previous else []
        for entry in memory.entries:
            if not Path(entry["path"]).is_file():
                raise FileNotFoundError(f"retained latent is missing: {entry['path']}")
    for key in order:
        if key in method.stages:
            continue
        index = len(method.stages)
        stage_seed = cfg["seed"] + index
        seed_all(stage_seed)
        rng = random.Random(stage_seed)
        report = logger(output / "training.jsonl", cfg["log_every"])
        source = source_by_key[key]
        if cfg["method"] == "clare":
            batches = endless(demo_loader(source, runtime, cfg["batch_size"], stage_seed))
            def forward():
                batch, actions, padding = normalized_batch(runtime, next(batches))
                return runtime.flow_loss(runtime.encode(batch), actions, padding=padding)
            metadata = method.train_stage(key, forward, steps=cfg["steps_per_stage"],
                                         learning_rate=cfg["learning_rate"], max_norm=cfg["max_grad_norm"], report=report,
                                         training_cfg=cfg)
        else:
            current = cache_demonstrations(runtime, source, output / "latent_cache" / f"stage_{index:03d}", stage_seed)
            method.add_prototype(key, current)
            parameters = method.parameters()
            optimizer, scheduler = policy_optimizer(parameters, cfg)
            for step in range(cfg["steps_per_stage"]):
                def forward():
                    selected = memory.draw(current, cfg["batch_size"], cfg["mlr_ifa"]["replay_fraction"], rng)
                    embedded, actions, padding, keys = latent_batch(selected, runtime.device, runtime.identity["sha256"])
                    return method.loss(embedded, actions, padding, keys)
                metrics = accumulated_step(forward, parameters, optimizer, cfg["gradient_accumulation_steps"],
                                           cfg["max_grad_norm"], scheduler)
                report({"stage": index, "step": step + 1, "global_batch_size": cfg["global_batch_size"], **metrics})
            prototype_bytes = sum(v.numel() * v.element_size() for p in method.prototypes.values() for v in p.values())
            memory.budget = cfg["mlr_ifa"]["memory_bytes"] - prototype_bytes
            memory.update(current)
            method.stages.append(key)
            metadata = {"retained_latent_bytes": memory.bytes, "retained_records": len(memory.entries),
                        "prototype_bytes": prototype_bytes, "working_memory_bytes": memory.bytes + prototype_bytes,
                        "current_input_cache_bytes": sum(e["bytes"] for e in current),
                        "archive_and_input_cache_excluded_from_working_memory_budget": True}
        artifact = save_stage(output, index, method, runtime, protocol, cfg, metadata=metadata,
                              replay=memory.entries if memory else None)
        print(f"saved {artifact}", flush=True)
    return method


def train_continual_rl(runtime, cfg, protocol, output, task_keys=None, resume=None, continue_from=None,
                       optimizer_resume=None):
    seed_all(cfg["seed"])
    from .rollout import episode
    from .methods.continual_rl import group_advantages
    from .continual_checkpoint import read_checkpoint, restore_random_state, save_checkpoint
    if optimizer_resume and (resume or continue_from):
        raise ValueError("GRPO optimizer recovery cannot be combined with another continuation")
    method = make_method(runtime, cfg)
    previous = load_stage(resume, runtime, protocol, method, cfg) if resume else None
    options = cfg["continual_vla_rl"]
    parameters = method.parameters()
    total_steps, updates = 0, 0
    if previous:
        total_steps = previous["metadata"].get("environment_steps", 0)
        updates = previous["metadata"].get("optimizer_updates", 0)
    first_group = 0
    recovery = None
    if optimizer_resume:
        recovery = read_checkpoint(optimizer_resume, runtime, cfg, protocol, task_keys)
        method.restore(recovery["method"])
        if task_keys is None:
            task_keys = [recovery["task_key"]]
        total_steps, updates = recovery["environment_steps"], recovery["updates"]
        write_json(Path(output) / "optimizer_continuation.json", {
            "source": str(Path(optimizer_resume).resolve()), "source_sha256": digest(optimizer_resume),
            "task_key": recovery["task_key"], "groups_completed": recovery["groups_completed"],
            "stage_updates": recovery["stage_updates"], "environment_steps": total_steps})
    if continue_from:
        if resume or task_keys:
            raise ValueError("no-update continuation cannot be combined with --resume or task selection")
        from .continuation import no_update_prefix
        first_group, total_steps = no_update_prefix(continue_from, runtime, cfg, protocol, output)
        print(f"RL reused {first_group} complete zero-advantage groups, prior environment steps={total_steps}", flush=True)
    for key in task_keys or task_order(cfg, protocol):
        if key in method.stages:
            continue
        index = len(method.stages)
        contexts = training_contexts(cfg, protocol, [key])
        optimizer, scheduler = policy_optimizer(parameters, cfg)
        stage_updates = 0
        rng = random.Random(cfg["seed"] + index)
        start_group = first_group if index == 0 else 0
        if recovery is not None:
            if key != recovery["task_key"]:
                raise ValueError("GRPO optimizer recovery task order differs")
            optimizer.load_state_dict(recovery["optimizer"])
            scheduler.load_state_dict(recovery["scheduler"])
            restore_random_state(recovery["random"], rng)
            start_group, stage_updates = recovery["groups_completed"], recovery["stage_updates"]
            print(f"RL restored {start_group} groups and {stage_updates} optimizer updates for stage {index}", flush=True)
            recovery = None

        def checkpoint(groups_completed):
            save_checkpoint(Path(output) / "continual_optimizer_checkpoint.pt", method, optimizer, scheduler,
                            rng, runtime, cfg, protocol, task_key=key, groups_completed=groups_completed,
                            stage_updates=stage_updates, updates=updates, environment_steps=total_steps)

        checkpoint(start_group)
        for group in range(start_group, options["groups_per_stage"]):
            if stage_updates >= cfg["steps_per_stage"]:
                break
            base = contexts[group % len(contexts)]
            episodes, returns = [], []
            for member in range(options["group_size"]):
                # Same task/reset state and env seed; distinct policy randomness
                # is installed after reset through a separate policy_seed field.
                context = {**base, "policy_seed": (base.get("policy_seed", base["seed"]) + group * 1009 + member) % (2**63 - 1)}
                summary, records = episode(runtime, cfg, context, method=method, record=True, on_policy=True)
                total_steps += summary["steps"]
                returns.append(float(summary["success"]))
                episodes.append(records)
                append_json(output / "rollouts.jsonl", {"stage": index, "group": group + 1, "member": member,
                                                        **summary})
                print(f"RL stage={index} group={group+1} member={member+1} success={summary['success']} steps={summary['steps']}", flush=True)
            advantages = group_advantages(returns)
            # No informative policy gradient exists in an all-equal group.
            if float(advantages.abs().sum()) > 0:
                samples = [(row["embedded"], transition, float(advantage))
                           for advantage, ep in zip(advantages, episodes) for row in ep for transition in row["transitions"]]
                for epoch in range(options["update_epochs"]):
                    rng.shuffle(samples)
                    for offset in range(0, len(samples), cfg["global_batch_size"]):
                        selected = samples[offset:offset + cfg["global_batch_size"]]
                        selected += rng.choices(samples, k=cfg["global_batch_size"] - len(selected))
                        microbatches = iter(selected[i:i + cfg["batch_size"]]
                                            for i in range(0, len(selected), cfg["batch_size"]))
                        def forward():
                            micro = next(microbatches)
                            embedded = {k: torch.cat([s[0][k] for s in micro]).to(runtime.device) for k in micro[0][0]}
                            transition = {k: torch.cat([s[1][k] for s in micro]).to(runtime.device) for k in micro[0][1]}
                            advantage = torch.tensor([s[2] for s in micro], device=runtime.device)
                            return method.transition_loss(runtime.prefix(embedded), transition, advantage), {}
                        metrics = accumulated_step(forward, parameters, optimizer, cfg["gradient_accumulation_steps"],
                                                   cfg["max_grad_norm"], scheduler)
                        updates += 1
                        stage_updates += 1
                        if stage_updates == 1 or stage_updates % cfg["log_every"] == 0:
                            value = {"stage": index, "step": stage_updates, "phase": "grpo_update",
                                     "global_batch_size": cfg["global_batch_size"], "batch_unit": "denoising_transition", **metrics}
                            append_json(output / "training.jsonl", value)
                            print(value, flush=True)
                        if stage_updates >= cfg["steps_per_stage"]:
                            break
                    if stage_updates >= cfg["steps_per_stage"]:
                        break
            report = {"stage": index, "group": group + 1, "returns": returns,
                      "informative": bool(advantages.abs().sum()), "updates": updates, "environment_steps": total_steps}
            append_json(output / "training.jsonl", report)
            print(report, flush=True)
            checkpoint(group + 1)
            if stage_updates >= cfg["steps_per_stage"]:
                break
        method.stages.append(key)
        save_stage(output, index, method, runtime, protocol, cfg,
                   metadata={"environment_steps": total_steps, "optimizer_updates": updates,
                             "stage_optimizer_updates": stage_updates, "target_optimizer_updates": cfg["steps_per_stage"],
                             "target_reached": stage_updates >= cfg["steps_per_stage"],
                             "policy_distribution": "Gaussian stochastic Euler transitions; fixed-distribution initial Gaussian"})
    return method


def read_rollout_bank(path, runtime, protocol, cfg):
    from .scope import check_input_root, check_task_keys, scope_identity
    check_input_root(path, cfg)
    value = read_json(path)
    if value.get("schema_version") != "baseline-offline-rollouts-v1":
        raise ValueError("expected rollouts.json produced by baseline collect")
    if cfg.get("experiment_id") and value.get("experiment_scope") != scope_identity(cfg):
        raise ValueError("offline bank belongs to another experiment/task selection")
    check_task_keys([e["task_key"] for e in value["entries"]], cfg, protocol)
    if value["base"]["sha256"] != runtime.identity["sha256"] or value["protocol_sha256"] != protocol.digest:
        raise ValueError("offline data belongs to a different base/protocol")
    if value["execution_horizon"] != cfg["execution_horizon"] or value["discount"] != cfg["rl2_vla"]["discount"]:
        raise ValueError("offline action horizon or reward discount differs")
    banks = {"train": [], "calibration": [], "validation": []}
    roles, episodes = {}, set()
    for entry in value["entries"]:
        check_input_root(entry["path"], cfg)
        if entry["role"] not in banks:
            raise ValueError("unknown offline data role")
        key = (entry["task_key"], str(entry["init_state_id"]))
        if key in roles and roles[key] != entry["role"]:
            raise ValueError("same initial state appears in training and held-out data")
        roles[key] = entry["role"]
        if entry["sha256"] in episodes:
            raise ValueError("duplicate offline episode; calibration count must not be inflated")
        episodes.add(entry["sha256"])
        if key[1] not in protocol.tasks[key[0]]["splits"][TRAIN_SPLIT]:
            raise ValueError("offline training data intersects evaluation shards")
        if digest(entry["path"]) != entry["sha256"]:
            raise ValueError("offline episode checksum mismatch")
        data = load_tensors(entry["path"])
        if not data["records"]:
            raise ValueError("empty offline episode")
        context = data["summary"]["context"]
        if (context["task_key"], str(context["init_state_id"])) != key or data["summary"]["success"] != entry["success"]:
            raise ValueError("offline manifest metadata does not match its episode")
        banks[entry["role"]].append(data)
    return banks


def train_rl2(runtime, cfg, protocol, output, rollouts, resume=None, optimizer_resume=None):
    seed_all(cfg["seed"])
    from .methods.rl2_vla import conformal_threshold
    banks = read_rollout_bank(rollouts, runtime, protocol, cfg)
    training = banks["train"]
    if {ep["summary"]["success"] for ep in training} != {True, False}:
        raise ValueError("failure-detector training requires successful AND failed training episodes")
    # Check calibration size before spending any optimization steps.
    conformal_threshold([[0.0] for ep in banks["calibration"] if ep["summary"]["success"]],
                        cfg["rl2_vla"]["conformal_alpha"])
    if not banks["validation"]:
        raise ValueError("offline bank requires a separate validation group")
    method = make_method(runtime, cfg)
    if resume:
        load_stage(resume, runtime, protocol, method, cfg)
    fit_metadata = {}
    if cfg["rl2_vla"]["training_recipe"] == "paper_reference":
        from .rl2_training import fit_reference
        fit_metadata = fit_reference(method, runtime, cfg, protocol, output, training, digest(rollouts),
                                     logger(output / "training.jsonl", cfg["log_every"]), optimizer_resume)
    else:
        if optimizer_resume:
            raise ValueError("optimizer resume requires the reference RL2 recipe")
        rows = [(row, float(ep["summary"]["success"])) for ep in training for row in ep["records"]]
        rng = random.Random(cfg["seed"])
        qparams = [p for p in method.qam.parameters() if p.requires_grad]
        parameters = qparams + list(method.verifier.parameters())
        optimizer, scheduler = policy_optimizer(parameters, {**cfg, "learning_rate": cfg["rl2_vla"]["learning_rate"]})
        report = logger(output / "training.jsonl", cfg["log_every"])
        for step in range(cfg["steps_per_stage"]):
            def forward():
                sample = rng.choices(rows, k=cfg["batch_size"])
                batch = {name: torch.stack([torch.as_tensor(row[name]) for row, _ in sample]).to(runtime.device).float()
                         for name in ("latent", "actions", "next_latent", "reward", "bootstrap_discount")}
                loss, detail = method.qam.losses(batch)
                labels = torch.tensor([label for _, label in sample], device=runtime.device)
                logits = method.verifier(torch.cat((batch["latent"], batch["actions"]), -1)).squeeze(-1)
                verifier_loss = F.binary_cross_entropy_with_logits(logits, labels)
                return loss + verifier_loss, {"verifier_loss": float(verifier_loss.detach()), **detail}
            metrics = accumulated_step(forward, parameters, optimizer, cfg["gradient_accumulation_steps"],
                                       cfg["max_grad_norm"], scheduler)
            method.qam.update_targets()
            report({"phase": "qam_and_verifier", "step": step + 1, "global_batch_size": cfg["global_batch_size"], **metrics})
        optimizer = torch.optim.Adam(method.detector.parameters(), lr=cfg["rl2_vla"]["safe_lr"])
        by_success = {success: [ep for ep in training if ep["summary"]["success"] == success] for success in (True, False)}
        for step in range(cfg["rl2_vla"]["safe_steps"]):
            draws = [0]
            def detector_forward():
                losses = []
                for _ in range(cfg["batch_size"]):
                    success = draws[0] % 2 == 0
                    draws[0] += 1
                    ep = rng.choice(by_success[success])
                    sequence = torch.stack([r["latent"] for r in ep["records"]]).to(runtime.device).float()[None]
                    logits, _ = method.detector(sequence)
                    losses.append(F.binary_cross_entropy_with_logits(logits, torch.full_like(logits, float(not success))))
                return torch.stack(losses).mean(), {}
            metrics = accumulated_step(detector_forward, list(method.detector.parameters()), optimizer,
                                       cfg["gradient_accumulation_steps"], cfg["max_grad_norm"])
            report({"phase": "failure_lstm", "step": step + 1, "batch_unit": "episode", **metrics})
    scores = []
    with torch.no_grad():
        for ep in banks["calibration"]:
            if ep["summary"]["success"]:
                sequence = torch.stack([r["latent"] for r in ep["records"]]).to(runtime.device).float()[None]
                scores.append(method.detector(sequence)[0].sigmoid().flatten().cpu())
    method.threshold = conformal_threshold(scores, cfg["rl2_vla"]["conformal_alpha"])
    method.stages = sorted({ep["summary"]["context"]["task_key"] for ep in training})
    validation = []
    with torch.no_grad():
        for ep in banks["validation"]:
            sequence = torch.stack([r["latent"] for r in ep["records"]]).to(runtime.device).float()[None]
            pred = float(method.detector(sequence)[0].sigmoid().max())
            validation.append({"failure": not ep["summary"]["success"], "max_failure_score": pred,
                               "triggered": pred > method.threshold})
    write_json(output / "detector_validation.json", {"threshold": method.threshold, "episodes": validation})
    save_stage(output, 0, method, runtime, protocol, cfg, metadata={
        "training_episodes": len(training), "calibration_success_episodes": len(scores),
        "offline_bank_sha256": digest(rollouts), "candidate_verifier": "independent latent-action success MLP",
        "calibration": "episode-maximum success-only split conformal", **fit_metadata})
    return method
