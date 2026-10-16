"""Reference QAM/SAFE optimization with the main experiment's 4 x 8 batch.

Source commits and deliberate PI0.5/LIBERO-PRO adaptations are recorded in the
experiment README. Checkpoints include optimizer and sampling RNG state.
"""
import hashlib
import json
import math
import random

import torch
from torch.nn import functional as F
from torch.nn.utils.rnn import pad_sequence

from .io import save_tensors, load_tensors, to_cpu, write_json
from .optimization import accumulated_step
from .scope import scope_identity, check_input_root


def epoch_batch_indices(count, batch_size, seed, epoch):
    """Visit every episode once per epoch; pad only the final effective batch."""
    rng = random.Random(seed + epoch)
    indices = list(range(count))
    rng.shuffle(indices)
    for start in range(0, count, batch_size):
        batch = indices[start:start + batch_size]
        yield batch + rng.choices(indices, k=batch_size - len(batch))


def safe_loss(detector, episodes, device, regularization):
    sequences = [torch.stack([r["latent"] for r in ep["records"]]).to(device).float() for ep in episodes]
    lengths = torch.tensor([len(v) for v in sequences], device=device)
    logits, _ = detector(pad_sequence(sequences, batch_first=True))
    labels = torch.tensor([not ep["summary"]["success"] for ep in episodes], device=device).float()
    per_time = F.binary_cross_entropy_with_logits(logits, labels[:, None].expand_as(logits), reduction="none")
    valid = torch.arange(logits.shape[1], device=device)[None] < lengths[:, None]
    classification = ((per_time * valid).sum(1) / lengths).mean()
    # SAFE's Adam path does NOT use the weight_decay field in its saved YAML.
    # Its explicit lambda_reg penalty excludes bias parameters.
    penalty = regularization * sum(p.square().sum() for name, p in detector.named_parameters() if "bias" not in name)
    return classification + penalty, {"classification_loss": float(classification.detach()),
                                      "regularization_loss": float(penalty.detach())}


def reference_optimizer(parameters, phase, cfg):
    options = cfg["rl2_vla"]
    return torch.optim.Adam(parameters, lr=options["safe_lr"] if phase == "safe" else options["learning_rate"],
                            betas=(0.9, 0.999), eps=1e-8,
                            weight_decay=options["safe_weight_decay"] if phase == "safe" else 0.0)


def checkpoint_contract(runtime, cfg, protocol, bank_digest):
    return {"schema_version": "baseline-rl2-optimizer-v1", "experiment_scope": scope_identity(cfg),
            "base_identity": runtime.identity["sha256"], "protocol_sha256": protocol.digest,
            "offline_bank_sha256": bank_digest,
            "config_sha256": hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def save_optimizer_checkpoint(path, method, optimizer, rng, phase, updates, contract):
    save_tensors(path, {"contract": contract, "method": method.state(), "optimizer": to_cpu(optimizer.state_dict()),
                        "phase": phase, "updates": updates, "python_rng": rng.getstate(),
                        "torch_rng": torch.get_rng_state(),
                        "cuda_rng": [v.cpu() for v in torch.cuda.get_rng_state_all()] if torch.cuda.is_initialized() else []})


def restore_optimizer_checkpoint(path, method, rng, contract, cfg):
    check_input_root(path, cfg)
    saved = load_tensors(path)
    if saved["contract"] != contract:
        raise ValueError("optimizer checkpoint has different data, configuration, base or experiment scope")
    method.restore(saved["method"])
    rng.setstate(saved["python_rng"])
    torch.set_rng_state(saved["torch_rng"])
    if saved["cuda_rng"]:
        if not torch.cuda.is_available() or len(saved["cuda_rng"]) != torch.cuda.device_count():
            raise ValueError("optimizer resume requires the same number of visible CUDA devices")
        torch.cuda.set_rng_state_all(saved["cuda_rng"])
    return saved


def fit_reference(method, runtime, cfg, protocol, output, training, bank_digest, report, optimizer_resume=None):
    options = cfg["rl2_vla"]
    rows = [(row, float(ep["summary"]["success"])) for ep in training for row in ep["records"]]
    rng = random.Random(cfg["seed"])
    contract = checkpoint_contract(runtime, cfg, protocol, bank_digest)
    saved = restore_optimizer_checkpoint(optimizer_resume, method, rng, contract, cfg) if optimizer_resume else None
    per_epoch = math.ceil(len(training) / cfg["global_batch_size"])
    budgets = {"qam": options["qam_steps"], "verifier": cfg["steps_per_stage"], "safe": options["safe_epochs"] * per_epoch}
    phases = list(budgets)
    if saved and (saved["phase"] not in phases or not 0 <= saved["updates"] <= budgets[saved["phase"]]):
        raise ValueError("invalid optimizer progress")
    start_phase = phases.index(saved["phase"]) if saved else 0
    for phase in phases[start_phase:]:
        module = {"qam": method.qam, "verifier": method.verifier, "safe": method.detector}[phase]
        parameters = [p for p in module.parameters() if p.requires_grad]
        optimizer = reference_optimizer(parameters, phase, cfg)
        start = 0
        if saved and phase == saved["phase"]:
            optimizer.load_state_dict(saved["optimizer"])
            start = saved["updates"]
        print(f"RL2 phase={phase} completed={start} target={budgets[phase]} global_batch={cfg['global_batch_size']}", flush=True)
        epoch, epoch_batches = -1, None
        for step in range(start, budgets[phase]):
            if phase == "safe":
                current_epoch = step // per_epoch
                if current_epoch != epoch:
                    epoch = current_epoch
                    epoch_batches = list(epoch_batch_indices(len(training), cfg["global_batch_size"], cfg["seed"] + 900001, epoch))
                indices = epoch_batches[step % per_epoch]
                micros = iter(indices[i:i + cfg["batch_size"]] for i in range(0, len(indices), cfg["batch_size"]))
                def forward():
                    episodes = [training[i] for i in next(micros)]
                    return safe_loss(method.detector, episodes, runtime.device, options["safe_regularization"])
            else:
                def forward():
                    sample = rng.choices(rows, k=cfg["batch_size"])
                    names = ("latent", "actions", "next_latent", "reward", "bootstrap_discount") if phase == "qam" else ("latent", "actions")
                    batch = {name: torch.stack([torch.as_tensor(row[name]) for row, _ in sample]).to(runtime.device).float() for name in names}
                    if phase == "qam":
                        return method.qam.losses(batch)
                    labels = torch.tensor([label for _, label in sample], device=runtime.device)
                    logits = method.verifier(torch.cat((batch["latent"], batch["actions"]), -1)).squeeze(-1)
                    return F.binary_cross_entropy_with_logits(logits, labels), {}
            metrics = accumulated_step(forward, parameters, optimizer, cfg["gradient_accumulation_steps"], cfg["max_grad_norm"])
            if phase == "qam":
                method.qam.update_targets()
            progress = {"phase": phase, "step": step + 1, "target_updates": budgets[phase],
                        "global_batch_size": cfg["global_batch_size"], "batch_unit": "episode" if phase == "safe" else "executed_chunk",
                        **({"epoch": epoch + 1, "target_epochs": options["safe_epochs"]} if phase == "safe" else {}), **metrics}
            report(progress)
            if (step + 1) % cfg["log_every"] == 0 or step == start:
                write_json(output / "training_progress.json", progress)
            checkpoint_every = min(options["checkpoint_every"], per_epoch * 25) if phase == "safe" else options["checkpoint_every"]
            if (step + 1) % checkpoint_every == 0 or step + 1 == budgets[phase]:
                save_optimizer_checkpoint(output / "optimizer_checkpoint.pt", method, optimizer, rng, phase, step + 1, contract)
                write_json(output / "optimizer_checkpoint.json", {**contract, "phase": phase, "updates": step + 1})
    return {"training_recipe": "paper_reference_with_main_batch", "optimizer_updates": budgets,
            "safe_epochs": options["safe_epochs"], "safe_batches_per_epoch": per_epoch,
            "safe_epoch_tail": "pad final batch to global batch size by sampling within the training set",
            "verifier_training": "separate PI0.5 latent-action MLP; main 1000-update budget",
            "gradient_clip": "main shared norm 1.0; QAM reference also uses 1.0"}
