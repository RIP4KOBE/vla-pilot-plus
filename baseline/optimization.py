"""The main experiment's optimizer contract, including real accumulation."""
import torch


def policy_optimizer(parameters, cfg):
    from lerobot.optim.schedulers import CosineDecayWithWarmupSchedulerConfig
    options = cfg["optimizer"]
    optimizer = torch.optim.AdamW(parameters, lr=cfg["learning_rate"], betas=tuple(options["betas"]),
                                  eps=options["eps"], weight_decay=options["weight_decay"])
    scheduler = CosineDecayWithWarmupSchedulerConfig(
        num_warmup_steps=options["warmup_steps"], num_decay_steps=options["decay_steps"],
        peak_lr=cfg["learning_rate"], decay_lr=options["decay_lr"], auto_scale=False,
    ).build(optimizer, cfg["steps_per_stage"])
    return optimizer, scheduler


def accumulated_step(forward, parameters, optimizer, accumulation, max_norm, scheduler=None):
    """Each forward returns a mean microbatch loss and scalar logging metrics."""
    optimizer.zero_grad(set_to_none=True)
    metrics = {}
    lr = optimizer.param_groups[0]["lr"]
    for _ in range(accumulation):
        loss, values = forward()
        if not torch.isfinite(loss):
            raise FloatingPointError("non-finite accumulated training loss")
        (loss / accumulation).backward()
        for key, value in {"loss": float(loss.detach()), **values}.items():
            metrics[key] = metrics.get(key, 0.0) + float(value) / accumulation
    norm = torch.nn.utils.clip_grad_norm_(parameters, max_norm, error_if_nonfinite=True)
    optimizer.step()
    if scheduler is not None:
        scheduler.step()
    return {**metrics, "grad_norm": float(norm), "learning_rate": lr,
            "microbatches": accumulation}
