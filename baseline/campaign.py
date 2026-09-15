"""Durable task-stage scheduling across a small, explicitly allowed GPU set."""
import argparse
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .config import load_config, cpu_environment, METHODS
from .experiment import task_order
from .io import read_json, write_json, safe_output
from .protocol import Protocol
from .scope import scope_identity
from .offline_bank import merged_bank


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_pool(gpus, configs):
    if not gpus or len(set(gpus)) != len(gpus) or any(i < 0 for i in gpus):
        raise ValueError("GPU pool must contain distinct nonnegative physical indices")
    if any(i == 6 or any(i in c["protected_gpu_indices"] for c in configs.values()) for i in gpus):
        raise ValueError("GPU6/protected GPUs cannot run baseline jobs")


def method_placement(path, gpus, methods=METHODS):
    if path is None:
        return {}
    mapping = read_json(path)["method_gpu_indices"]
    if set(mapping) != set(methods) or any(type(gpu) is not int or gpu not in gpus for gpu in mapping.values()):
        raise ValueError("method GPU assignment must cover the selected methods inside the allowed pool")
    return {**mapping, "v44_reference": mapping.get("clare", next(iter(mapping.values())))}


def finished_job(state, job, root, task_count):
    """Commit one completed job; each method can have only one in flight."""
    output = root / job["name"]
    item = state["methods"][job["owner"]]
    phase = job["phase"]
    if job.get("stage_validation"):
        result = read_json(output / "summary.json")
        item.update(first_stage_validated=True, state="FIRST_STAGE_VALIDATED",
                    first_stage_validation={"result": str(output / "summary.json"),
                                            "episodes": result["episodes"], "success_rate": result["micro_success"]})
    elif job["owner"] == "v44_reference":
        item.update(state="COMPLETE", evaluated=True, result=str(output / "summary.json"))
    elif phase == "collect":
        state["collection_shards"].append(str(output))
        item.update(tasks_collected=len(state["collection_shards"]), state="COLLECTION_STAGE_COMPLETE")
        item.pop("collection_resume", None)
    elif phase == "train":
        item.update(tasks_completed=task_count if job["owner"] == "rl2_vla" else item["tasks_completed"] + 1,
                    artifact=read_json(output / "latest.json")["artifact"], state="STAGE_TRAINED")
        item.pop("optimizer_resume", None)
    else:
        item.update(evaluated=True, state="COMPLETE", result=str(output / "summary.json"))
    item.pop("error", None)


def recover_failed_inputs(state, root, busy_owners):
    """Select only the failed current stage; retain collected episodes and RL state."""
    for owner in ("continual_vla_rl", "rl2_vla"):
        if owner not in state["methods"]:
            continue
        item = state["methods"][owner]
        if owner in busy_owners or item["state"] == "COMPLETE":
            continue
        for job in reversed(state["jobs"]):
            if job["owner"] != owner or not job.get("returncode"):
                continue
            output = root / job["name"]
            if owner == "rl2_vla" and job["phase"] == "collect":
                if job["suffix"] == f"collect_{len(state['collection_shards']):03d}" and (output / "rollouts.json").exists():
                    item["collection_resume"] = str(output)
                    break
            elif job["phase"] == "train":
                name = "optimizer_checkpoint.pt" if owner == "rl2_vla" else "continual_optimizer_checkpoint.pt"
                if owner == "continual_vla_rl" and job["suffix"] != f"stage_{item['tasks_completed']:03d}":
                    continue
                if (output / name).exists():
                    item["optimizer_resume"] = str(output / name)
                    break


def run(args):
    cpu_environment()
    os.nice(10)
    methods = tuple(getattr(args, "methods", None) or METHODS)
    if len(set(methods)) != len(methods) or not set(methods) <= set(METHODS):
        raise ValueError("invalid selected baseline methods")
    configs = {m: load_config(args.experiment_dir / f"{m}.json") for m in methods}
    cfg = configs.get("clare", next(iter(configs.values())))
    validate_pool(args.gpus, configs)
    placement = method_placement(getattr(args, "method_gpus", None), args.gpus, methods)
    protocol = Protocol(cfg["protocol"])
    order = task_order(cfg, protocol)
    if any(c["output_root"] != cfg["output_root"] or task_order(c, protocol) != order or
           scope_identity(c) != scope_identity(cfg) for c in configs.values()):
        raise ValueError("baseline task scopes/output roots differ")
    root = Path(cfg["output_root"])
    queue = root / "queue" if args.resume else safe_output(root, "queue")
    lock = (queue / "controller.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = queue / "status.json"
    state = read_json(state_path) if args.resume else {
        "experiment_scope": scope_identity(cfg), "tasks_planned": len(order),
        "methods": {m: {"state": "QUEUED", "tasks_completed": 0, "artifact": None, "evaluated": False} for m in methods},
        "collection_shards": [], "jobs": [], "cursor": 0,
        "inputs_policy": "fresh baseline data and learned states; user-authorized completed ticket demonstrations",
        "demonstration_ticket_root": str(args.ticket_root)}
    reference_enabled = not getattr(args, "no_reference", False)
    if reference_enabled and "clare" not in methods:
        raise ValueError("a subset without CLARE must use --no-reference")
    if reference_enabled:
        state["methods"].setdefault("v44_reference", {"state": "QUEUED", "evaluated": False})
    expected_owners = set(methods) | ({"v44_reference"} if reference_enabled else set())
    if set(state["methods"]) != expected_owners:
        raise ValueError("queue resume method selection differs")
    if state["experiment_scope"] != scope_identity(cfg):
        raise ValueError("queue resume scope differs")
    adopted = {}
    busy_owners = set()
    # An explicit scheduler handoff may adopt verified workers. Training and
    # collection continue in their existing processes with all GPU state intact.
    for job in state["jobs"]:
        if job.get("returncode") is not None:
            continue
        from .process_watch import verified_worker, ExistingWorker
        identity = verified_worker(job)
        if identity is not None:
            if not getattr(args, "adopt_running", False):
                raise RuntimeError(f"previous baseline worker {job['pid']} is still active; refusing duplicate launch")
            gpu = job["gpu_index"]
            if gpu not in args.gpus or gpu in adopted or job["owner"] in busy_owners:
                raise ValueError("adopted workers exceed the GPU pool or duplicate a method")
            adopted[gpu] = (ExistingWorker(identity, root / job["name"]), job, None)
            busy_owners.add(job["owner"])
            job.update(adopted_at=now(), adopted_by=os.getpid(), process_start_ticks=identity["start_ticks"])
            state["methods"][job["owner"]].update(state="RUNNING")
            continue
        status_path = root / job["name"] / "status.json"
        if status_path.exists() and read_json(status_path).get("status") == "complete":
            finished_job(state, job, root, len(order))
            job.update(returncode=0, recovered=True)
        else:
            job.update(returncode=-1, interrupted=True)
    if args.resume:
        for method, item in state["methods"].items():
            if item["state"] == "COMPLETE" or method in busy_owners:
                continue
            item.update(state="QUEUED")
            item.pop("error", None)
        recover_failed_inputs(state, root, busy_owners)
    state.update(pid=os.getpid(), gpu_indices=args.gpus, max_simultaneous_gpu_workers=len(args.gpus),
                 method_gpu_indices={k: v for k, v in placement.items() if k in methods},
                 started_at=state.get("started_at", now()))
    running = adopted
    stopping = [False]
    signal.signal(signal.SIGTERM, lambda *_: stopping.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *_: stopping.__setitem__(0, True))

    def report(status):
        state.update(state=status, updated_at=now(), active_jobs=[v[1]["name"] for v in running.values()])
        write_json(state_path, state)

    def next_job(owner):
        item = state["methods"][owner]
        if item["state"] in ("RUNNING", "COMPLETE", "FAILED"):
            return None
        if owner == "v44_reference":
            return {"owner": owner, "method": "clare", "phase": "evaluate", "suffix": "v44_reference",
                    "extra": ["--split", "fixed_development_probe"]}
        index = item["tasks_completed"]
        if (getattr(args, "validate_first_stage", False) and owner in ("clare", "mlr_ifa")
                and index == 1 and not item.get("first_stage_validated")):
            return {"owner": owner, "method": owner, "phase": "evaluate", "suffix": "stage_000_validation",
                    "stage_validation": True,
                    "extra": ["--artifact", item["artifact"], "--split", "fixed_development_probe",
                              "--task-key", order[0], "--limit", "2"]}
        if index == len(order):
            return {"owner": owner, "method": owner, "phase": "evaluate", "suffix": "development",
                    "extra": ["--artifact", item["artifact"], "--split", "fixed_development_probe"]}
        if owner == "rl2_vla":
            index = len(state["collection_shards"])
            if index < len(order):
                item.update(current_task=order[index])
                extra = ["--task-key", order[index], "--repeats", args.collect_repeats]
                if item.get("collection_resume"):
                    extra += ["--continue-from", item["collection_resume"]]
                return {"owner": owner, "method": owner, "phase": "collect", "suffix": f"collect_{index:03d}",
                        "extra": extra}
            bank = queue / "rl2_rollouts.json"
            merged_bank(state["collection_shards"], bank, configs[owner], protocol)
            extra = ["--rollouts", bank]
            if item.get("optimizer_resume"):
                extra += ["--optimizer-resume", item["optimizer_resume"]]
            return {"owner": owner, "method": owner, "phase": "train", "suffix": "train", "extra": extra}
        key = order[index]
        item.update(current_task=key)
        extra = ["--task-key", key]
        if owner == "continual_vla_rl" and item.get("optimizer_resume"):
            extra += ["--optimizer-resume", item["optimizer_resume"]]
        elif item["artifact"]:
            extra += ["--resume", item["artifact"]]
        if owner in ("clare", "mlr_ifa"):
            # Both methods read the same frozen task snapshot even if collection
            # later appends another curation for this task.
            prepared = getattr(args, "prepared_sources", None)
            source_file = (Path(prepared) if prepared else queue) / f"demonstrations_{index:03d}.json"
            if not source_file.exists():
                if prepared:
                    item.update(state="WAITING_FOR_CONVERTED_DEMONSTRATIONS")
                    return None
                if configs[owner].get("demonstration_contract"):
                    raise ValueError("corrected imitation campaigns require --prepared-sources")
                from .demo_source import snapshot_curated_source
                source = snapshot_curated_source(key, protocol, args.ticket_root, root / "shared_demonstrations")
                if source is None:
                    item.update(state="WAITING_FOR_DEMONSTRATIONS")
                    return None
                write_json(source_file, {"schema_version": "baseline-task-data-v1", "tasks": [source]})
            extra += ["--task-data", source_file]
        return {"owner": owner, "method": owner, "phase": "train", "suffix": f"stage_{index:03d}", "extra": extra}

    owners = [m for m in ("clare", "mlr_ifa", "v44_reference", "rl2_vla", "continual_vla_rl") if m in expected_owners]
    report("SCHEDULING")
    while True:
        for gpu, (child, job, log) in list(running.items()):
            code = child.poll()
            if code is None:
                continue
            if log is not None:
                log.close()
            job.update(returncode=code, ended_at=now())
            del running[gpu]
            if code:
                state["methods"][job["owner"]].update(state="FAILED", error=f"exit {code}; {job['log']}")
            else:
                try:
                    finished_job(state, job, root, len(order))
                except Exception as exc:
                    state["methods"][job["owner"]].update(state="FAILED", error=str(exc))
            report("SCHEDULING")
        if (queue / "stop.request").exists():
            stopping[0] = True
        if stopping[0]:
            report("DRAINING" if running else "STOPPED_AT_PHASE_BOUNDARY")
            if not running:
                return
            time.sleep(5)
            continue
        if all(v["state"] == "COMPLETE" for v in state["methods"].values()):
            report("COMPLETE")
            return
        if len(running) < len(args.gpus):
            gpu_info = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"], text=True)
            rows = {int(v[0]): (v[1].strip(), int(v[2])) for line in gpu_info.splitlines() if (v := line.split(","))}
            for gpu in args.gpus:
                if gpu in running:
                    continue
                for offset in range(len(owners)):
                    cursor = (state["cursor"] + offset) % len(owners)
                    owner = owners[cursor]
                    if placement and placement[owner] != gpu:
                        continue
                    method_cfg = cfg if owner == "v44_reference" else configs[owner]
                    if rows[gpu][1] < method_cfg["gpu_min_free_mib"]:
                        continue
                    try:
                        spec = next_job(owner)
                    except Exception as exc:
                        state["methods"][owner].update(state="FAILED", error=f"input preparation: {exc}")
                        continue
                    if spec is None:
                        continue
                    name = f"{spec['method']}_{spec['suffix']}_{len(state['jobs']):04d}"
                    command = [sys.executable, "-u", "-m", "baseline", spec["phase"], "--config",
                               str(args.experiment_dir / f"{spec['method']}.json"), "--run-name", name, *map(str, spec["extra"])]
                    log_path = queue / f"{name}.log"
                    log = log_path.open("x")
                    environment = dict(os.environ, CUDA_VISIBLE_DEVICES=rows[gpu][0], OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                                       LP_NUM_THREADS="2", NUMBA_NUM_THREADS="2", PYTHONDONTWRITEBYTECODE="1")
                    child = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1], env=environment,
                                             stdout=log, stderr=subprocess.STDOUT)
                    job = {k: v for k, v in spec.items() if k != "extra"}
                    job.update(name=name, pid=child.pid, gpu_index=gpu, gpu_uuid=rows[gpu][0], command=command,
                               log=str(log_path), started_at=now())
                    state["jobs"].append(job)
                    running[gpu] = (child, job, log)
                    state["methods"][owner].update(state="RUNNING", phase=spec["phase"], current_run=name, gpu_index=gpu)
                    state["cursor"] = (cursor + 1) % len(owners)
                    report("RUNNING")
                    break
        has_errors = any(v["state"] == "FAILED" for v in state["methods"].values())
        waiting = any(v["state"] in ("WAITING_FOR_DEMONSTRATIONS", "WAITING_FOR_CONVERTED_DEMONSTRATIONS") for v in state["methods"].values())
        report("RUNNING_WITH_FAILURES" if running and has_errors else "RUNNING" if running else
               "NEEDS_ATTENTION" if has_errors else "WAITING_FOR_DEMONSTRATIONS" if waiting else "WAITING_FOR_GPU")
        time.sleep(10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--gpus", type=int, nargs="+", required=True)
    parser.add_argument("--ticket-root", type=Path, required=True)
    parser.add_argument("--collect-repeats", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--adopt-running", action="store_true", help="resume monitoring verified workers during a scheduler handoff")
    parser.add_argument("--method-gpus", type=Path, help="JSON method_gpu_indices mapping inside the allowed GPU pool")
    parser.add_argument("--methods", nargs="+", choices=METHODS, help="run only these methods in a separate queue")
    parser.add_argument("--no-reference", action="store_true", help="retain the existing v44 reference without rerunning it")
    parser.add_argument("--prepared-sources", type=Path, help="directory of validated, converted demonstration sources")
    parser.add_argument("--validate-first-stage", action="store_true", help="load and evaluate the first imitation stage before proceeding")
    args = parser.parse_args()
    args.experiment_dir = args.experiment_dir.resolve()
    if args.collect_repeats < 1:
        parser.error("collect repeats must be positive")
    if args.adopt_running and not args.resume:
        parser.error("--adopt-running requires --resume")
    run(args)


if __name__ == "__main__":
    main()
