"""All defaults are independent of Hydra and the live replay configuration."""
from copy import deepcopy
from pathlib import Path

from .io import read_json

METHODS = ("clare", "mlr_ifa", "continual_vla_rl", "rl2_vla")
DEFAULTS = {
    "schema_version": "pi05-pro-baseline-v1",
    "method": "clare",
    "checkpoint": "/shared/hengyil6/vls/models/pi05_libero_finetuned_v044",
    "tokenizer": "/shared/hengyil6/vls/models/paligemma-tokenizer",
    "protocol": "/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json",
    "experiment_plan": None,
    "task_selection": None,
    "experiment_id": None,
    "fresh_baseline_inputs": False,
    "demonstration_contract": None,
    "output_root": "/shared/hengyil6/vls/baseline_runs",
    "device": "cuda:0",
    "gpu_min_free_mib": 32768,
    "protected_gpu_indices": [6],
    "seed": 20260825,
    "execution_horizon": 10,
    "inference_steps": 10,
    "max_episode_steps": 720,
    "num_steps_wait": 5,
    "observation_width": 128,
    "observation_height": 128,
    "render_gpu_device_id": 8,
    "steps_per_stage": 1000,
    "batch_size": 4,
    "gradient_accumulation_steps": 8,
    "global_batch_size": 32,
    "gradient_checkpointing": True,
    "learning_rate": 2.5e-5,
    "optimizer": {"betas": [0.9, 0.95], "eps": 1e-8, "weight_decay": 1e-10,
                  "warmup_steps": 1000, "decay_steps": 30000, "decay_lr": 2.5e-6},
    "max_grad_norm": 1.0,
    "log_every": 10,
    "clare": {"bottleneck": 128, "ae_hidden": 256, "ae_latent": 128,
              "expansion_threshold": 1.0, "feature_batches": 16,
              "discriminator_steps": 2000, "discriminator_lr": 5e-4},
    "mlr_ifa": {"memory_bytes": 1073741824, "replay_fraction": 0.5,
                "ifa_weight": 0.1, "angular_margin_scale": 0.72,
                "similar_pair_fraction": 0.5},
    "continual_vla_rl": {"rank": 32, "alpha": 32, "group_size": 8,
                         "groups_per_stage": 100, "update_epochs": 2,
                         "transition_std": 0.08, "clip_ratio": 0.2},
    "rl2_vla": {"hidden_dim": 512, "hidden_layers": 4, "q_ensemble": 2,
                "flow_steps": 10, "discount": 0.99, "target_tau": 0.005,
                "inverse_temperature": 0.3, "pessimism": 0.5,
                "learning_rate": 2.5e-5, "candidates": 40,
                "compose_mean": 0.5, "compose_std": 0.25,
                "trigger": "adaptive", "safe_hidden": 128,
                "safe_steps": 1000, "safe_lr": 1e-3,
                "conformal_alpha": 0.1, "action_clip": 3.0,
                "training_recipe": "main_aligned", "qam_steps": 1000,
                "safe_epochs": 0, "safe_weight_decay": 0.0,
                "safe_regularization": 0.0, "checkpoint_every": 10000},
}


def load_config(path=None, overrides=None):
    result = deepcopy(DEFAULTS)
    for incoming in (read_json(path) if path else {}, overrides or {}):
        unknown = set(incoming) - set(result)
        if unknown:
            raise ValueError(f"unknown configuration keys: {sorted(unknown)}")
        for key, value in incoming.items():
            if isinstance(result[key], dict):
                if not isinstance(value, dict) or set(value) - set(result[key]):
                    raise ValueError(f"unknown {key} options")
                result[key].update(value)
            else:
                result[key] = value
    # An unset imitation-only option must not change the serialized config/hash
    # of ongoing RL experiments or their optimizer-resume contracts.
    if result.get("demonstration_contract") is None:
        result.pop("demonstration_contract", None)
    validate_config(result)
    return result


def validate_config(cfg):
    if cfg.get("demonstration_contract") is not None:
        from .demonstration_inputs import CONTRACT
        if cfg["demonstration_contract"] != CONTRACT:
            raise ValueError("unknown demonstration input contract")
    # Standalone campaigns do not change the four-method scheduler's defaults
    # or the serialized configuration of existing experiments.
    if cfg["method"] not in (*METHODS, "slow_loop_expansion"):
        raise ValueError(f"method must be one of {METHODS}")
    if cfg["gpu_min_free_mib"] <= 0 or any(not isinstance(i, int) or i < 0 for i in cfg["protected_gpu_indices"]):
        raise ValueError("invalid GPU memory requirement or protected GPU indices")
    for key in ("batch_size", "steps_per_stage", "inference_steps", "max_episode_steps", "log_every"):
        if int(cfg[key]) <= 0:
            raise ValueError(f"{key} must be positive")
    if cfg["gradient_accumulation_steps"] < 1 or cfg["batch_size"] * cfg["gradient_accumulation_steps"] != cfg["global_batch_size"]:
        raise ValueError("global_batch_size must equal batch_size * gradient_accumulation_steps on one GPU")
    if not 1 <= int(cfg["execution_horizon"]) <= 50:
        raise ValueError("v44 execution horizon must be in [1, 50]")
    if not 0 <= cfg["mlr_ifa"]["replay_fraction"] < 1:
        raise ValueError("replay_fraction must be in [0,1)")
    if not 0 < cfg["mlr_ifa"]["similar_pair_fraction"] <= 1:
        raise ValueError("similar_pair_fraction must be in (0,1]")
    if cfg["mlr_ifa"]["memory_bytes"] <= 0:
        raise ValueError("memory_bytes must be positive")
    if cfg["continual_vla_rl"]["group_size"] < 2:
        raise ValueError("GRPO needs at least two rollouts per reset")
    if cfg["continual_vla_rl"]["transition_std"] <= 0:
        raise ValueError("GRPO requires a stochastic flow policy with positive std")
    if cfg["rl2_vla"]["trigger"] not in ("adaptive", "always", "never"):
        raise ValueError("unknown RL2 trigger")
    if cfg["rl2_vla"]["training_recipe"] not in ("main_aligned", "paper_reference"):
        raise ValueError("unknown RL2 training recipe")
    if cfg["rl2_vla"]["qam_steps"] < 1 or cfg["rl2_vla"]["safe_epochs"] < 0 or cfg["rl2_vla"]["checkpoint_every"] < 1:
        raise ValueError("invalid RL2 optimization budget")
    if cfg["rl2_vla"]["training_recipe"] == "paper_reference" and cfg["rl2_vla"]["safe_epochs"] < 1:
        raise ValueError("reference SAFE requires a positive number of full epochs")
    if cfg["rl2_vla"]["safe_weight_decay"] < 0 or cfg["rl2_vla"]["safe_regularization"] < 0:
        raise ValueError("SAFE penalties cannot be negative")
    if not 0 < cfg["rl2_vla"]["conformal_alpha"] < 1:
        raise ValueError("conformal_alpha must be in (0,1)")
    for group, keys in {
        "clare": ("bottleneck", "ae_hidden", "ae_latent", "feature_batches", "discriminator_steps", "discriminator_lr"),
        "continual_vla_rl": ("rank", "alpha", "groups_per_stage", "update_epochs", "clip_ratio"),
        "rl2_vla": ("hidden_dim", "hidden_layers", "q_ensemble", "flow_steps", "learning_rate", "candidates", "safe_hidden", "safe_steps", "safe_lr", "action_clip"),
    }.items():
        if any(cfg[group][key] <= 0 for key in keys):
            raise ValueError(f"{group} dimensions, budgets and rates must be positive")
    if not 0 <= cfg["rl2_vla"]["discount"] <= 1 or not 0 < cfg["rl2_vla"]["target_tau"] <= 1:
        raise ValueError("invalid RL2 discount or EMA coefficient")
    if cfg["rl2_vla"]["inverse_temperature"] < 0 or cfg["rl2_vla"]["compose_std"] < 0:
        raise ValueError("inverse temperature and composition std cannot be negative")
    if cfg["learning_rate"] <= 0 or cfg["max_grad_norm"] <= 0:
        raise ValueError("learning rate and gradient norm must be positive")
    for key in ("checkpoint", "tokenizer", "protocol", "output_root"):
        if not str(cfg[key]).strip():
            raise ValueError(f"missing {key}")


def cpu_environment():
    """Only affects the newly launched baseline process, never the parent shell."""
    import os
    import sys
    sys.dont_write_bytecode = True
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("MKL_NUM_THREADS", "2")
    os.environ.setdefault("LP_NUM_THREADS", "2")
    os.environ.setdefault("NUMBA_NUM_THREADS", "2")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
