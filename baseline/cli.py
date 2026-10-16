"""Single entry point; help and config inspection do not import torch."""
import argparse
import json
from pathlib import Path

from .config import load_config, cpu_environment, METHODS
from .io import read_json, write_json, safe_output
from .protocol import Protocol, EVAL_SPLITS


def parser():
    root = argparse.ArgumentParser(description="Independent PI0.5 v44 / LIBERO-PRO baselines")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("plan", "train", "evaluate", "collect", "smoke"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path)
        command.add_argument("--method", choices=METHODS)
        command.add_argument("--checkpoint")
        command.add_argument("--tokenizer")
        command.add_argument("--protocol")
        command.add_argument("--experiment-plan")
        command.add_argument("--output-root")
        command.add_argument("--device")
        command.add_argument("--seed", type=int)
        if name != "smoke":
            command.add_argument("--task-key", action="append", help="repeat to select a subset of protocol task keys")
        if name != "plan":
            command.add_argument("--run-name", required=True)
        if name in ("train", "collect"):
            command.add_argument("--continue-from", type=Path, help="prior collection run, or zero-update GRPO prefix; creates a new run")
        if name == "train":
            command.add_argument("--task-data", type=Path)
            command.add_argument("--rollouts", type=Path)
            command.add_argument("--resume", type=Path, help="completed stage artifact to continue from")
            command.add_argument("--optimizer-resume", type=Path, help="RL2 or Continual RL optimizer checkpoint from this experiment")
        if name == "evaluate":
            command.add_argument("--artifact", type=Path, help="omit to evaluate unchanged v44")
            command.add_argument("--split", choices=(*EVAL_SPLITS, "main_online"), default="fixed_development_probe")
            command.add_argument("--limit", type=int)
        if name == "collect":
            command.add_argument("--repeats", type=int, default=5)
            command.add_argument("--limit", type=int)
        if name == "smoke":
            command.add_argument("--with-environment", action="store_true")
    metrics = commands.add_parser("metrics")
    metrics.add_argument("matrix", type=Path, help="JSON square success matrix (values in [0,1])")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    cpu_environment()
    if args.command == "metrics":
        from .evaluation import continual_metrics
        print(json.dumps(continual_metrics(read_json(args.matrix)), indent=2))
        return
    # Evaluation uses the artifact's original algorithm settings by default.
    config_path = args.config
    cfg = load_config(config_path)
    if args.command == "evaluate" and args.artifact and config_path is None:
        cfg = load_config(overrides=read_json(args.artifact / "manifest.json")["config"])
    for key in ("method", "checkpoint", "tokenizer", "protocol", "experiment_plan", "output_root", "device", "seed"):
        value = getattr(args, key)
        if value is not None:
            cfg[key] = value
    from .config import validate_config
    validate_config(cfg)
    if getattr(args, "limit", None) is not None and args.limit <= 0:
        raise ValueError("limit must be positive")
    if getattr(args, "repeats", 1) <= 0:
        raise ValueError("repeats must be positive")
    if args.command == "plan":
        value = {"config": cfg, "available_paths": {key: Path(cfg[key]).exists() for key in ("checkpoint", "tokenizer", "protocol")}}
        if Path(cfg["protocol"]).is_file():
            protocol = Protocol(cfg["protocol"])
            from .experiment import task_order
            from .scope import check_task_keys
            keys = args.task_key or task_order(cfg, protocol)
            check_task_keys(keys, cfg, protocol)
            value.update(protocol_sha256=protocol.digest, task_order=keys,
                         development_episodes=len(protocol.contexts("fixed_development_probe", cfg["seed"], keys)))
            value["training_tasks"] = [{"task_key": key, "runtime_suite": protocol.tasks[key]["runtime_suite"],
                                        "demo_init_state_ids": protocol.tasks[key]["splits"]["demo_online_pool"]}
                                       for key in value["task_order"]]
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    protocol = Protocol(cfg["protocol"])
    from .experiment import task_order
    from .scope import check_task_keys, check_input_root
    task_keys = getattr(args, "task_key", None)
    if task_keys and (any(k not in protocol.tasks for k in task_keys) or len(set(task_keys)) != len(task_keys)):
        raise ValueError("unknown --task-key")
    if task_keys:
        check_task_keys(task_keys, cfg, protocol)
    for key in ("artifact", "resume", "rollouts", "continue_from", "optimizer_resume", "task_data"):
        path = getattr(args, key, None)
        if path is not None:
            check_input_root(path, cfg)
    if args.command in ("collect", "evaluate") and not task_keys:
        args.task_key = task_order(cfg, protocol)
    if args.command == "train":
        if args.optimizer_resume and (cfg["method"] not in ("rl2_vla", "continual_vla_rl") or args.resume or args.continue_from):
            raise ValueError("--optimizer-resume requires an RL method and cannot be combined with another continuation")
        if args.continue_from and cfg["method"] != "continual_vla_rl":
            raise ValueError("--continue-from train is only for a zero-update GRPO prefix; other methods use --resume")
        if cfg["method"] in ("clare", "mlr_ifa") and not args.task_data:
            raise ValueError("CLARE/MLR-IFA require --task-data; see configs/task_data.example.json")
        if cfg["method"] == "rl2_vla" and not args.rollouts:
            raise ValueError("RL2 needs --rollouts from the separate baseline collect command")
        if cfg["method"] == "rl2_vla" and task_keys:
            raise ValueError("select RL2 tasks during collect; training uses the complete supplied rollout bank")
    from .resources import isolated_device
    from .simulator_startup import monitor_startup
    with isolated_device(cfg):
        from .io import seed_all
        from .pi05 import Pi05Runtime
        seed_all(cfg["seed"])
        output = safe_output(cfg["output_root"], args.run_name, inputs=(cfg["checkpoint"], cfg["tokenizer"]))
        write_json(output / "config.json", cfg)
        with monitor_startup(output if cfg["method"] == "continual_vla_rl" else None):
            _run_command(args, cfg, protocol, output, Pi05Runtime)


def _run_command(args, cfg, protocol, output, runtime_type):
    from .simulator_startup import failure_details
    try:
        runtime = runtime_type(cfg)
        write_json(output / "base_identity.json", runtime.identity)
        if args.command == "train":
            from .train import train_imitation, train_continual_rl, train_rl2
            if cfg["method"] in ("clare", "mlr_ifa"):
                train_imitation(runtime, cfg, protocol, output, args.task_data, args.resume, args.task_key)
            elif cfg["method"] == "continual_vla_rl":
                train_continual_rl(runtime, cfg, protocol, output, args.task_key, args.resume, args.continue_from,
                                   args.optimizer_resume)
            else:
                train_rl2(runtime, cfg, protocol, output, args.rollouts, args.resume, args.optimizer_resume)
        elif args.command == "evaluate":
            from .evaluation import evaluate
            evaluate(runtime, cfg, protocol, output, artifact=args.artifact, split=args.split,
                     limit=args.limit, task_keys=args.task_key)
        elif args.command == "collect":
            from .rollout import collect_rollouts
            collect_rollouts(runtime, cfg, protocol, output, repeats=args.repeats, limit=args.limit, task_keys=args.task_key,
                             continue_from=args.continue_from)
        elif args.command == "smoke":
            from .smoke import smoke
            smoke(runtime, cfg, protocol, output, with_environment=args.with_environment)
        write_json(output / "status.json", {"status": "complete", "command": args.command})
    except Exception as exc:
        write_json(output / "status.json", {"status": "failed", **failure_details(exc)})
        raise
