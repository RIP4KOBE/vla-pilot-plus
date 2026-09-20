"""Always expand with the current main slow loop, then evaluate all seen tasks.

One independent GPU and output root; fixed alpha=0.8, no online gate, planner
request, registry promotion, coefficient selection, or new demonstration work.
"""
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .config import cpu_environment, load_config
from .io import append_json, digest, read_json, write_json
from .protocol import Protocol
from .experiment import task_order
from .slow_loop_metrics import context_identity, summarize_episodes, continual_report

METHOD = "slow_loop_expansion"
REFERENCE = Path(__file__).parent / "references/slow_loop_main_20260914"
REPO = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_reference_sources():
    manifest = read_json(REFERENCE / "source_manifest.json")
    for name, expected in manifest["pinned_files"].items():
        if digest(REFERENCE / name) != expected:
            raise ValueError(f"pinned main slow-loop source changed: {name}")
    for name, expected in manifest["runtime_dependencies"].items():
        if digest(REPO / name) != expected:
            raise ValueError(f"native trainer dependency changed: {name}; preserve the frozen experiment implementation")
    return manifest


def load_settings(path):
    cfg = read_json(path)
    if cfg["schema_version"] != "baseline-slow-loop-expansion-v1" or cfg["method"] != METHOD:
        raise ValueError("wrong slow-loop baseline configuration")
    if cfg["alpha"] != 0.8 or cfg["gpu_index"] == 6 or cfg["evaluation_split"] != "fixed_development_probe":
        raise ValueError("this experiment requires alpha=0.8, a non-GPU6 device, and fixed development contexts")
    runtime = load_config(overrides=cfg["runtime"])
    if runtime["method"] != METHOD or runtime["batch_size"] != 4 or runtime["gradient_accumulation_steps"] != 8:
        raise ValueError("baseline method or batch contract mismatch")
    root = Path(runtime["output_root"]).resolve()
    if "baseline_runs" not in root.parts or "self_improve" in root.parts or "models" in root.parts:
        raise ValueError("slow-loop baseline output must be independently owned under baseline_runs")
    if cfg["gpu_index"] in runtime["protected_gpu_indices"]:
        raise ValueError("requested GPU is protected")
    cfg["runtime"] = runtime
    return cfg


def require_selected_gpu(gpu_index):
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    rows = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"], text=True)
    matches = [row.split(",")[0].strip() for row in rows.splitlines()
               if visible in [x.strip() for x in row.split(",")]]
    if matches != [str(gpu_index)] or gpu_index == 6:
        raise ValueError("worker GPU differs from its independent non-GPU6 allocation")


def configure_gpu(gpu_index):
    # Resolve nvidia-smi's physical index before importing any CUDA consumer;
    # CUDA ordinals can have a different order on this server.
    if type(gpu_index) is not int or gpu_index == 6:
        raise ValueError("an explicit non-GPU6 physical device is required")
    rows = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"], text=True)
    matches = [row.split(",")[1].strip() for row in rows.splitlines()
               if row.split(",")[0].strip() == str(gpu_index)]
    if len(matches) != 1:
        raise ValueError("physical GPU was not found")
    os.environ["CUDA_VISIBLE_DEVICES"] = matches[0]


def prepare(path):
    from .data import load_task_sources
    from .demonstration_inputs import read_conversion
    from .references.slow_loop_main_20260914.training import CoFTConfig
    cfg = load_settings(path)
    reference = verify_reference_sources()
    if cfg["training"] != asdict(CoFTConfig()):
        raise ValueError("training recipe differs from the pinned main slow loop")
    runtime = cfg["runtime"]
    protocol = Protocol(runtime["protocol"])
    order = task_order(runtime, protocol)
    if len(order) != 20 or {protocol.tasks[k]["perturbation_variant"] for k in order} != {"use_environment", "use_swap"}:
        raise ValueError("expected the existing 20 environment/position tasks")
    sources = load_task_sources(cfg["demonstrations"], protocol)
    by_key = {s["task_key"]: s for s in sources}
    if set(by_key) != set(order):
        raise ValueError("demonstrations must cover exactly the selected 20 tasks")
    for source in sources:
        read_conversion(source, runtime)
    root = Path(runtime["output_root"])
    root.mkdir(parents=True, exist_ok=True)
    contexts = protocol.contexts(cfg["evaluation_split"], runtime["seed"], order)
    if any(sum(c["task_key"] == key for c in contexts) != 2 for key in order):
        raise ValueError("this campaign expects two fixed development contexts per task")
    value = {"schema_version": "baseline-expansion-plan-v1", "method": METHOD,
             "config": cfg, "task_order": order, "protocol_sha256": protocol.digest,
             "sources": [by_key[k] for k in order], "evaluation_contexts": contexts,
             "evaluation_episodes_planned": sum(2 * (i + 1) for i in range(len(order))),
             "source_reference_sha256": content_hash(reference),
             "demonstrations_sha256": digest(cfg["demonstrations"]),
             "coefficient_selection": "fixed_uniform_0.8_no_selection",
             "stage_advancement": "always_merge_then_evaluate_no_performance_filter"}
    value["plan_sha256"] = content_hash(value)
    target = root / "plan.json"
    if target.exists() and read_json(target) != value:
        raise ValueError("immutable baseline plan changed; use a new output directory")
    write_json(target, value)
    raw_reference = read_json(Path(cfg["v44_reference"]) / "summary.json")
    rows = [json.loads(x) for x in (Path(cfg["v44_reference"]) / "episodes.jsonl").read_text().splitlines() if x.strip()]
    summary = summarize_episodes(rows, contexts)
    if (raw_reference["protocol_sha256"] != protocol.digest or
            Path(raw_reference["base"]["checkpoint"]).resolve() != Path(runtime["checkpoint"]).resolve() or
            raw_reference["base"]["files"]["model.safetensors"] != digest(Path(runtime["checkpoint"]) / "model.safetensors")):
        raise ValueError("v44 reference uses another protocol or initial checkpoint")
    write_json(root / "v44_reference.json", {**summary, "source": cfg["v44_reference"],
               "base": raw_reference["base"], "protocol_sha256": protocol.digest})
    print(json.dumps({"plan": str(target), "tasks": len(order), "demonstrations": sum(len(s["episodes"]) for s in sources),
                      "evaluation_episodes": value["evaluation_episodes_planned"], "alpha": cfg["alpha"]}), flush=True)
    return cfg, value


def prepare_stage(cfg, plan, index, parent):
    from .references.slow_loop_main_20260914.training import CoFTConfig, prepare_source_catalog, build_lerobot_coft_command
    from .references.slow_loop_main_20260914.checkpoint_math import checkpoint_digest
    root = Path(cfg["runtime"]["output_root"])
    stage = root / f"stage_{index:03d}"
    stage.mkdir(exist_ok=True)
    spec_path = stage / "training_job.json"
    if spec_path.exists():
        spec = read_json(spec_path)
        if spec["plan_sha256"] != plan["plan_sha256"] or spec["parent"] != parent:
            raise ValueError("existing task stage belongs to another parent or plan")
        return stage, spec
    sources = plan["sources"]
    source = sources[index]
    manifest_path = stage / "source_sampler.json"
    sampler = prepare_source_catalog(catalog_root=stage / "catalog", manifest_path=manifest_path,
              new_datasets={source["repo_id"]: Path(source["root"])},
              old_ticket_datasets={s["repo_id"]: Path(s["root"]) for s in sources[:index]},
              replay_datasets={k: Path(v) for k, v in cfg["replay_sources"].items()},
              seed=cfg["runtime"]["seed"], config=CoFTConfig())
    sampler.update(baseline_task_sources=sources[:index + 1], baseline_runtime=cfg["runtime"],
                   baseline_plan_sha256=plan["plan_sha256"], baseline_stage=index,
                   baseline_gpu_index=cfg["gpu_index"])
    sampler["manifest_sha256"] = content_hash({k: v for k, v in sampler.items() if k != "manifest_sha256"})
    write_json(manifest_path, sampler)
    command = build_lerobot_coft_command(python_executable=Path(sys.executable),
              parent_checkpoint=Path(parent["checkpoint_path"]), dataset_root=stage / "catalog",
              dataset_repo_id=source["repo_id"], dataset_repo_ids=sampler["repo_ids"],
              source_sampler_manifest=manifest_path, output_dir=stage / "training_output",
              seed=cfg["runtime"]["seed"], tokenizer_path=Path(cfg["runtime"]["tokenizer"]), config=CoFTConfig())
    command = ["baseline.slow_loop_train" if x == "lerobot.scripts.lerobot_train" else x for x in command]
    spec = {"schema_version": "baseline-expansion-training-job-v1", "stage": index,
            "task_key": source["task_key"], "parent": parent,
            "parent_checkpoint_digest": checkpoint_digest(Path(parent["checkpoint_path"])),
            "plan_sha256": plan["plan_sha256"], "source_manifest_sha256": sampler["manifest_sha256"],
            "command": command, "gpu_index": cfg["gpu_index"],
            "expected_checkpoint": str(stage / "training_output/checkpoints/001000/pretrained_model")}
    write_json(spec_path, spec)
    return stage, spec


def merge_stage(cfg, plan, index):
    from .references.slow_loop_main_20260914.checkpoint_math import (
        CheckpointView, parameter_group, checkpoint_digest, extract_full_delta, verify_full_delta_reconstruction)
    from .references.slow_loop_main_20260914.candidates import DeltaLineageEntry, compose_expansion_candidates
    from .references.slow_loop_main_20260914.coft_recovery import checkpoint_complete
    root = Path(cfg["runtime"]["output_root"])
    stage = root / f"stage_{index:03d}"
    spec = read_json(stage / "training_job.json")
    output = stage / "merge.json"
    if output.exists():
        merged = read_json(output)
        if merged["plan_sha256"] != plan["plan_sha256"] or checkpoint_digest(Path(merged["checkpoint_path"])) != merged["checkpoint_digest"]:
            raise ValueError("completed merge identity changed")
        return merged
    ft = Path(spec["expected_checkpoint"])
    if not checkpoint_complete(ft.parent, source_manifest=stage / "source_sampler.json", expected_step=1000):
        raise ValueError("full 1000-step committed training checkpoint required before merging")
    parent = Path(spec["parent"]["checkpoint_path"])
    if checkpoint_digest(parent) != spec["parent_checkpoint_digest"]:
        raise ValueError("parent changed during training")
    delta = stage / "delta"
    if not delta.exists():
        extract_full_delta(parent, ft, delta, parent_policy_id=spec["parent"]["policy_id"])
    reconstruction = verify_full_delta_reconstruction(parent, delta, ft)
    import torch
    changes = {group: 0 for group in ("vision", "language", "action")}
    with CheckpointView(delta) as view:
        for key in view.keys:
            tensor = view.tensor(key)
            if not torch.isfinite(tensor).all():
                raise ValueError(f"non-finite trained delta: {key}")
            changes[parameter_group(key)] += int(torch.count_nonzero(tensor))
    if not sum(changes.values()):
        raise ValueError("SFT produced no parameter change")
    lineage = [] if index == 0 else read_json(root / f"stage_{index - 1:03d}/merge.json")["lineage"]
    grid = compose_expansion_candidates(theta0_checkpoint=Path(cfg["runtime"]["checkpoint"]),
           parent_policy_id=spec["parent"]["policy_id"],
           accepted_lineage=[DeltaLineageEntry(**entry) for entry in lineage],
           new_delta_id=f"baseline_delta_{index:03d}", new_delta_path=delta,
           output_root=stage / "merged", alpha_l_values=[cfg["alpha"]])
    if len(grid["candidates"]) != 1:
        raise ValueError("fixed coefficient must produce exactly one candidate")
    candidate = grid["candidates"][0]
    details = read_json(Path(candidate["checkpoint_path"]) / "candidate.json")
    if candidate["alpha_map"] != {k: 0.8 for k in ("vision", "language", "action")}:
        raise ValueError("merge coefficient mismatch")
    # Normalizers/tokenizer settings remain those of the initial v44.
    base = Path(cfg["runtime"]["checkpoint"])
    support = {p.name: digest(p) for p in base.iterdir() if p.name.startswith(("policy_preprocessor", "policy_postprocessor"))}
    for name, value in support.items():
        if digest(Path(candidate["checkpoint_path"]) / name) != value:
            raise ValueError("merged policy changed the v44 normalization processors")
    result = {**candidate, "lineage": details["lineage"], "stage": index,
              "task_key": plan["task_order"][index], "plan_sha256": plan["plan_sha256"],
              "training_steps": 1000, "reconstruction": reconstruction,
              "changed_parameters_by_group": changes,
              "normalization_sha256": support, "merged_at": now()}
    write_json(output, result)
    return result


def evaluate_stage(cfg, plan, index):
    require_selected_gpu(cfg["gpu_index"])
    from .pi05 import Pi05Runtime
    from .rollout import episode
    from .references.slow_loop_main_20260914.checkpoint_math import checkpoint_digest
    root = Path(cfg["runtime"]["output_root"])
    stage = root / f"stage_{index:03d}"
    merged = read_json(stage / "merge.json")
    path = Path(merged["checkpoint_path"])
    if checkpoint_digest(path) != merged["checkpoint_digest"]:
        raise ValueError("evaluation checkpoint differs from the merged stage")
    output = stage / "evaluation"
    output.mkdir(exist_ok=True)
    keys = plan["task_order"][:index + 1]
    contexts = [c for c in plan["evaluation_contexts"] if c["task_key"] in keys]
    identity = {"plan_sha256": plan["plan_sha256"], "checkpoint_digest": merged["checkpoint_digest"],
                "stage": index, "contexts": contexts}
    identity_path = output / "identity.json"
    if identity_path.exists() and read_json(identity_path) != identity:
        raise ValueError("evaluation resume has another model or context plan")
    write_json(identity_path, identity)
    records = output / "episodes.jsonl"
    rows = [json.loads(x) for x in records.read_text().splitlines() if x.strip()] if records.exists() else []
    if [context_identity(x["context"]) for x in rows] != [context_identity(c) for c in contexts[:len(rows)]] or len(rows) > len(contexts):
        raise ValueError("evaluation resume is not an exact prefix of fixed contexts")
    if len(rows) < len(contexts):
        runtime = Pi05Runtime({**cfg["runtime"], "checkpoint": str(path)}, hash_weights=False)
        for context in contexts[len(rows):]:
            summary, _ = episode(runtime, cfg["runtime"], context)
            append_json(records, summary)
            rows.append(summary)
            write_json(output / "progress.json", {"stage": index, "episodes_completed": len(rows),
                       "episodes_planned": len(contexts), "successes": sum(x["success"] for x in rows),
                       "current_task": context["task_key"], "updated_at": now()})
            print(f"stage {index + 1}: evaluation {len(rows)}/{len(contexts)} success={summary['success']}", flush=True)
    summary = {**summarize_episodes(rows, contexts), "schema_version": "baseline-evaluation-v1",
               "method": METHOD, "stage": index, "tasks_learned": index + 1,
               "checkpoint_path": str(path), "checkpoint_digest": merged["checkpoint_digest"],
               "plan_sha256": plan["plan_sha256"], "protocol_sha256": plan["protocol_sha256"],
               "split": cfg["evaluation_split"], "metric_role": "development_heldout",
               "evaluation_controls_training": False, "completed_at": now()}
    write_json(output / "summary.json", summary)


def update_matrix(cfg, plan):
    root = Path(cfg["runtime"]["output_root"])
    summaries = []
    for i in range(len(plan["task_order"])):
        p = root / f"stage_{i:03d}/evaluation/summary.json"
        if not p.exists():
            break
        summaries.append(read_json(p))
    report = continual_report(plan["task_order"], summaries, read_json(root / "v44_reference.json"))
    write_json(root / "continual_metrics.json", report)
    temporary = root / "success_matrix.csv.partial"
    with temporary.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["tasks_learned", *plan["task_order"]])
        writer.writerow([0, *report["v44_reference"]])
        for i, row in enumerate(report["matrix"], 1):
            writer.writerow([i, *["" if x is None else x for x in row]])
    os.replace(temporary, root / "success_matrix.csv")
    return report


def run_command(command, root, stage, phase, status):
    log_path = stage / f"{phase}.log"
    env = dict(os.environ)
    env.update(PYTHONUNBUFFERED="1", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True",
               PYTHONPATH=str(REPO) + os.pathsep + env.get("PYTHONPATH", ""))
    with log_path.open("a") as log:
        process = subprocess.Popen(command, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
        status.update(phase=phase, worker_pid=process.pid, log=str(log_path), updated_at=now())
        write_json(root / "status.json", status)
        append_json(root / "events.jsonl", {"event": "started", "phase": phase, "stage": status["stage"], "pid": process.pid, "time": now()})
        code = process.wait()
    append_json(root / "events.jsonl", {"event": "finished", "phase": phase, "stage": status["stage"], "returncode": code, "time": now()})
    if code:
        raise RuntimeError(f"{phase} exited {code}; see {log_path}")


def run(path):
    from .resources import isolated_device
    from .references.slow_loop_main_20260914.coft_recovery import checkpoint_complete, prepare_coft_execution
    configure_gpu(load_settings(path)["gpu_index"])
    cfg, plan = prepare(path)
    root = Path(cfg["runtime"]["output_root"])
    with (root / "controller.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status = {"method": METHOD, "state": "RUNNING", "pid": os.getpid(), "gpu_index": cfg["gpu_index"],
                  "tasks_planned": 20, "tasks_completed": 0, "started_at": now(), "plan_sha256": plan["plan_sha256"]}
        # isolated_device resolves the explicit physical GPU to its UUID and
        # reserves it against other baseline controllers for this campaign.
        with isolated_device(cfg["runtime"]):
            require_selected_gpu(cfg["gpu_index"])
            parent = {"policy_id": "pi05_v44", "checkpoint_path": cfg["runtime"]["checkpoint"]}
            try:
                for index in range(20):
                    status.update(stage=index, current_task=plan["task_order"][index], updated_at=now())
                    stage, spec = prepare_stage(cfg, plan, index, parent)
                    if not (stage / "merge.json").exists():
                        final = Path(spec["expected_checkpoint"]).parent
                        if not checkpoint_complete(final, source_manifest=stage / "source_sampler.json", expected_step=1000):
                            for attempt in range(3):
                                command, recovery = prepare_coft_execution(spec["command"], spec)
                                write_json(stage / "training_recovery.json", recovery)
                                try:
                                    run_command(command, root, stage, "train", status)
                                    break
                                except RuntimeError:
                                    if attempt == 2:
                                        raise
                                    time.sleep(30)
                        run_command([sys.executable, "-u", "-m", "baseline.slow_loop_expansion", "merge", "--config", str(path), "--stage", str(index)], root, stage, "merge", status)
                    if not (stage / "evaluation/summary.json").exists():
                        for attempt in range(3):
                            try:
                                run_command([sys.executable, "-u", "-m", "baseline.slow_loop_expansion", "evaluate", "--config", str(path), "--stage", str(index)], root, stage, "evaluate", status)
                                break
                            except RuntimeError:
                                if attempt == 2:
                                    raise
                                time.sleep(30)
                    merged = read_json(stage / "merge.json")
                    parent = {key: merged[key] for key in ("policy_id", "checkpoint_path")}
                    report = update_matrix(cfg, plan)
                    status.update(tasks_completed=index + 1, phase="stage_complete", worker_pid=None,
                                  latest_metrics=report["latest"], updated_at=now())
                    write_json(root / "status.json", status)
                status.update(state="COMPLETE", phase="complete", completed_at=now(), updated_at=now())
                write_json(root / "status.json", status)
            except BaseException as exc:
                status.update(state="FAILED", error=str(exc), updated_at=now())
                write_json(root / "status.json", status)
                raise


def main():
    cpu_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "merge", "evaluate"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--stage", type=int)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.config)
    elif args.command == "run":
        run(args.config.resolve())
    else:
        cfg = load_settings(args.config)
        verify_reference_sources()
        plan = read_json(Path(cfg["runtime"]["output_root"]) / "plan.json")
        if plan["config"] != cfg or args.stage is None or not 0 <= args.stage < 20:
            raise ValueError("worker configuration or stage differs from frozen plan")
        (merge_stage if args.command == "merge" else evaluate_stage)(cfg, plan, args.stage)


if __name__ == "__main__":
    main()
