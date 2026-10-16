"""Shared full-episode execution and separately owned offline data collection."""
from pathlib import Path
import time

import torch

from .environment import make_environment, reset_environment, step_environment
from .io import seed_all, to_cpu, save_tensors, write_json, append_json, digest
from .protocol import TRAIN_SPLIT


def episode(runtime, cfg, context, *, method=None, record=False, on_policy=False, max_policy_steps=None):
    # Bounded integration checks must retain the configured simulator horizon:
    # LIBERO reset/settling steps also consume the simulator's step counter.
    step_budget = cfg["max_episode_steps"] if max_policy_steps is None else min(cfg["max_episode_steps"], max_policy_steps)
    if step_budget < 1:
        raise ValueError("policy step budget must be positive")
    seed_all(context["seed"])
    adapter = make_environment(cfg, context)
    records = []
    success, steps, chunks, interventions = False, 0, 0, 0
    termination_reason, final_info = None, {}
    start = time.monotonic()
    try:
        provenance = reset_environment(adapter, context)
        # Keep grouped GRPO resets identical while varying policy randomness.
        seed_all(context.get("policy_seed", context["seed"]))
        runtime.policy.reset()
        if method is not None and hasattr(method, "reset"):
            method.reset()
        while steps < step_budget:
            with torch.no_grad():
                batch = runtime.preprocess(adapter.get_policy_observation(sample_num=1))
                embedded = runtime.embed(batch)
                prefix = runtime.prefix(embedded)
                latent = runtime.latent(prefix) if record and not on_policy else None
                detail, transitions = {}, []
                if on_policy or (method is not None and cfg["method"] == "continual_vla_rl"):
                    actions, transitions = method.sample(prefix)
                elif cfg["method"] == "rl2_vla" and method is not None:
                    actions, detail = method.action(embedded)
                else:
                    actions = runtime.sample(prefix)
                physical = runtime.physical(actions)[0, :cfg["execution_horizon"]]
            discounted_reward, executed = 0.0, 0
            ended = False
            for action in physical:
                _, reward, terminated, truncated, info = step_environment(adapter, action)
                final_info = info
                discounted_reward += (cfg["rl2_vla"]["discount"] ** executed) * float(reward)
                executed += 1
                steps += 1
                success |= bool(info.get("success", info.get("is_success", False)))
                if terminated or truncated or steps >= step_budget:
                    termination_reason = ("success" if success else "simulator_horizon" if info.get("TimeLimit.truncated")
                                          else "terminated" if terminated else "policy_step_budget")
                    ended = True
                    break
            chunks += 1
            interventions += int(detail.get("steering", False))
            if record:
                item = {"actions": to_cpu(actions[:, :cfg["execution_horizon"]].reshape(-1)),
                        "reward": discounted_reward, "steps": executed, "terminal": ended}
                if on_policy:
                    item.update(embedded=to_cpu(embedded), transitions=transitions)
                else:
                    item["latent"] = to_cpu(latent[0])
                records.append(item)
            if ended:
                break
        if record and not on_policy:
            for i, row in enumerate(records):
                row["next_latent"] = records[i + 1]["latent"] if i + 1 < len(records) else torch.zeros_like(row["latent"])
                row["bootstrap_discount"] = 0.0 if row["terminal"] else cfg["rl2_vla"]["discount"] ** row["steps"]
        summary = {"context": context, "success": success, "steps": steps, "chunks": chunks,
                   "interventions": interventions, "seconds": time.monotonic() - start,
                   "environment": provenance, "termination_reason": termination_reason,
                   "simulator_timestep": final_info.get("simulator_timestep"),
                   "simulator_horizon": final_info.get("simulator_horizon")}
        return summary, records
    finally:
        # No production PID, registry, ticket, or snapshot is ever consulted.
        adapter.close()


def collection_roles(protocol, seed, task_keys=None, cfg=None):
    """Disjoint init-state groups, including across repeats of an episode."""
    from .experiment import training_contexts
    contexts = training_contexts(cfg, protocol, task_keys) if cfg else protocol.contexts(TRAIN_SPLIT, seed, task_keys)
    result = []
    for key in task_keys or protocol.order(seed):
        rows = [c for c in contexts if c["task_key"] == key]
        rows.sort(key=lambda v: v["seed"])
        if len(rows) < 5:
            raise ValueError("need at least five online states for train/calibration/validation")
        nheld = max(1, len(rows) // 5)
        for i, context in enumerate(rows):
            role = "calibration" if i < nheld else "validation" if i < 2 * nheld else "train"
            result.append((role, context))
    return result


def collection_plan(protocol, cfg, task_keys, repeats):
    result = []
    for role, context in collection_roles(protocol, cfg["seed"], task_keys, cfg):
        for repeat in range(repeats):
            repeated = {**context, "seed": (context["seed"] + repeat * 100003) % (2**32),
                        "policy_seed": (context.get("policy_seed", context["seed"]) + repeat * 100003) % (2**63 - 1)}
            result.append((role, repeated))
    return result


def collect_rollouts(runtime, cfg, protocol, output, *, repeats=5, limit=None, task_keys=None, continue_from=None):
    output = Path(output)
    (output / "episodes").mkdir()
    entries = []
    plan = collection_plan(protocol, cfg, task_keys, repeats)
    if limit is not None:
        plan = plan[:limit]
    write_json(output / "collection_plan.json", {"repeats": repeats, "episodes": len(plan), "task_keys": task_keys})
    def save_index():
        from .scope import scope_identity
        write_json(output / "rollouts.json", {
            "schema_version": "baseline-offline-rollouts-v1", "base": runtime.identity,
            "protocol_sha256": protocol.digest, "execution_horizon": cfg["execution_horizon"],
            "discount": cfg["rl2_vla"]["discount"], "entries": entries,
            "experiment_scope": scope_identity(cfg)})
    if continue_from:
        from .continuation import source_run
        from .io import read_json, load_tensors
        previous = source_run(continue_from, runtime, cfg)
        index = read_json(previous / "rollouts.json")
        if index["base"]["sha256"] != runtime.identity["sha256"] or index["protocol_sha256"] != protocol.digest:
            raise ValueError("collection source has another model/protocol")
        if len(index["entries"]) > len(plan):
            raise ValueError("collection source is longer than the requested plan")
        seen = set()
        for entry, (role, context) in zip(index["entries"], plan):
            if entry["sha256"] in seen or digest(entry["path"]) != entry["sha256"]:
                raise ValueError("duplicate or changed source episode")
            seen.add(entry["sha256"])
            data = load_tensors(entry["path"])
            if entry["role"] != role or data["summary"]["context"] != context or entry["success"] != data["summary"]["success"]:
                raise ValueError("source episode does not match the collection plan")
            entries.append(entry)
            append_json(output / "collection.jsonl", {**entry, "steps": data["summary"]["steps"], "reused": True})
        write_json(output / "continuation.json", {"source": str(previous), "episodes_reused": len(entries),
                                                  "source_index_sha256": digest(previous / "rollouts.json")})
        save_index()
        print(f"collect reused {len(entries)} validated episodes; continuing the same plan", flush=True)
    for role, context in plan[len(entries):]:
        summary, records = episode(runtime, cfg, context, record=True)
        path = output / "episodes" / f"{len(entries):06d}.pt"
        save_tensors(path, {"summary": summary, "records": records})
        entry = {"path": str(path.resolve()), "sha256": digest(path), "role": role,
                 "task_key": context["task_key"], "init_state_id": context["init_state_id"],
                 "seed": context["seed"], "success": summary["success"]}
        entries.append(entry)
        append_json(output / "collection.jsonl", {**entry, "steps": summary["steps"], "termination_reason": summary["termination_reason"]})
        print(f"collect {len(entries)}/{len(plan)} role={role} success={summary['success']} steps={summary['steps']} end={summary['termination_reason']}", flush=True)
        save_index()
    return entries
