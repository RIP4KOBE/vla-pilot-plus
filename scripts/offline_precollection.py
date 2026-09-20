#!/usr/bin/env python
"""Finite, serial native-account collection, isolated from online experiments.

This entry point owns only offline tickets and its own collector children. It
does not import a policy, create incidents/jobs, run replay, or start training.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DIVERSITY = "确保采集动作的多样性，不要每个示范都一样，起码包含2-3种"
ROLE = "offline_precollection_for_future_experiments"
TERMINAL = {"COMPLETE", "COMPLETE_REUSED", "NEEDS_HUMAN", "INFRA_ERROR"}


def read_json(path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def effective_failure_limit(root, plan):
    """Explicit runtime control; historical plans, tickets and traces stay intact."""
    root = Path(root)
    control = read_json(root / "collection_control.json")
    limit = plan["consecutive_control_failure_limit"]
    if control is not None:
        if (control.get("schema_version") != "offline-collection-control-v1"
                or control.get("batch_id") != plan["batch_id"]
                or control.get("batch_plan_sha256") != digest(root / "plan.json")
                or control.get("requested_by") != "user"
                or control.get("preserve_failure_counts") is not True):
            raise ValueError("retry control must be an explicit request bound to this batch")
        limit = control["consecutive_failure_limit"]
    if type(limit) is not int or limit < 1:
        raise ValueError("consecutive failure limit must be a positive integer")
    return limit


def write_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{uuid4().hex}.tmp")
    with tmp.open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def validate_batch(plan, manifest):
    if plan.get("schema_version") != "libero-pro-offline-demo-precollection-v1":
        raise ValueError("unsupported offline plan")
    if plan.get("collection_role") != ROLE or plan.get("diversity_instruction") != DIVERSITY:
        raise ValueError("missing offline provenance or exact diversity instruction")
    for flag in ("load_vla_model", "training_authorized", "formal_experiment_resume_authorized",
                 "create_slow_loop_jobs", "create_verifier_labels", "modify_registry", "scheduled_tasks_allowed"):
        if plan.get(flag) is not False:
            raise ValueError(f"offline isolation flag must be false: {flag}")
    if (plan.get("tasks_planned"), plan.get("target_successes_per_task"),
            plan.get("target_init_states_per_task"), plan.get("target_successes_per_init_state"),
            plan.get("max_parallel_collectors"), plan.get("gpu_index")) != (20, 15, 5, 3, 1, 6):
        raise ValueError("unexpected finite collection specification")
    if type(plan.get("consecutive_control_failure_limit")) is not int or plan["consecutive_control_failure_limit"] < 1:
        raise ValueError("consecutive failure limit must be a positive integer")
    if manifest.get("manifest_sha256") != plan["protocol_manifest_sha256"]:
        raise ValueError("frozen manifest hash mismatch")
    contexts = plan["contexts"]
    if len(contexts) != 20 or len({c["context_id"] for c in contexts}) != 20:
        raise ValueError("requires exactly 20 unique contexts")
    if len({c["task_key"] for c in contexts}) != 20:
        raise ValueError("duplicate task/perturbation")
    if Counter(c["perturbation_variant"] for c in contexts) != {"use_environment": 10, "use_swap": 10}:
        raise ValueError("requires ten contexts of each selected perturbation")
    for c in contexts:
        matches = [t for t in manifest["tasks"] if t["task_key"] == c["task_key"]]
        if len(matches) != 1:
            raise ValueError("context does not resolve uniquely to frozen manifest")
        t = matches[0]
        if any(c[k] != t[k] for k in ("suite", "task_id", "task_index", "runtime_suite", "perturbation_variant")):
            raise ValueError("context task metadata differs from manifest")
        legal = [str(x) for x in t["splits"]["demo_online_pool"]]
        if c["source_split"] != "demo_online_pool" or c["legal_demo_init_state_ids"] != legal or len(set(legal)) < 5:
            raise ValueError("collection init states must be the exact legal demo pool")


def make_ticket(plan, context, plan_sha):
    """Code chooses IDs and initial states; no signature or snapshot is issued."""
    from mode_gate.tickets import ExpansionTicket
    identity = f"offline-precollection-v1\0{plan['batch_id']}\0{context['task_key']}\0{plan['protocol_manifest_sha256']}"
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:16]
    ticket_id = "ticket-" + suffix
    signature_id = "offline-precollection-" + suffix
    legal = context["legal_demo_init_state_ids"]
    states = sorted(legal, key=lambda x: hashlib.sha256(f"{signature_id}\0{x}".encode()).hexdigest())[:5]
    provenance = {"collection_role": ROLE, "batch_id": plan["batch_id"], "batch_plan_sha256": plan_sha,
        "manifest_sha256": plan["protocol_manifest_sha256"], "source_context": context,
        "source_context_seeds_role": "formal provenance only; each new demo records its actual queue env_seed",
        "training_authorized": False, "registry_modified": False, "verifier_labels_created": False,
        "slow_loop_job_created": False, "snapshot_created": False, "signature_entity_created": False}
    # These are feasible-route families, not a task-specific action template.
    # The account chooses concrete mechanics from each fresh scene and history.
    cells = [
        ("direct_clear_route", "在当前几何允许的清晰走廊采用直接接近与转运策略；根据真实接触和成功路径规划。"),
        ("alternative_approach_route", "采用有实质差异的可行接近方向或避障走廊；不能仅微调或抖动路径。"),
        ("alternative_transfer_or_contact", "结合已有成功选择另一种可行抓取朝向、转运高度/路径或独立子任务顺序；不强行改变机械约束。"),
    ]
    payload = {"ticket_id": ticket_id, "signature_id": signature_id, "snapshot_id": "",
        "suite": context["suite"], "task_id": context["task_id"],
        "perturbation_variant": context["perturbation_variant"],
        "failure_mode": "OFFLINE_PRECOLLECTION_NOT_A_FAILURE", "target_object_id": None,
        "init_state_ids": states, "demos_per_state": 3, "target_demos": 15,
        "eval_init_state_ids": [], "parent_policy_id": "not_applicable_offline_precollection",
        "registry_summary": provenance,
        "acceptance_criteria": {**provenance, "success_authority": plan["success_authority"],
            "replay_role": "diagnostic_only", "diversity_role": "planning_requirement_not_success_gate"},
        "created_at": plan["created_at"],
        "collection": {"capability_gap": "独立离线预采集：为当前既定任务及扰动收集原生成功示范，不代表线上失败或能力标签。",
            "coverage_axes": [{"axis": "motion_strategy", "value": value, "quota": 5,
                "operator_instruction_zh": zh} for value, zh in cells],
            "must_demonstrate": [DIVERSITY, "完整达成当前LIBERO-PRO原生任务目标。", "所有连续动作经有界7维OSC物理控制并完整记录。"],
            "must_avoid": ["不得瞬移、写实时物体/关节状态、修改物理或成功谓词。", "不得使用heldout/sealed初态或把失败轨迹写为成功。", "不得使用无意义抖动充当多样性。"]}}
    ticket = ExpansionTicket.model_validate(payload)
    path = Path(plan["ticket_root"]) / ticket_id / "ticket.json"
    canonical = ticket.model_dump(mode="json")
    if path.exists():
        if read_json(path) != canonical:
            raise ValueError("immutable offline ticket collision")
    else:
        write_json(path, canonical)
    sidecar = path.parent / "offline_precollection.json"
    if sidecar.exists() and read_json(sidecar) != provenance:
        raise ValueError("offline provenance collision")
    if not sidecar.exists():
        write_json(sidecar, provenance)
    for name in ("raw", "curated", "rejected", "exports", "automatic_collection", "videos", "attempts"):
        (path.parent / name).mkdir(exist_ok=True)
    return path


def native_records(ticket_path):
    """Read original success and structural identity, never replay acceptance."""
    import h5py
    ticket = read_json(ticket_path)
    records = []
    for p in sorted((Path(ticket_path).parent / "raw").glob("demo-*.hdf5")):
        if p.name.count(".") != 1:
            continue
        with h5py.File(p, "r") as f:
            if str(f.attrs.get("ticket_id")) != ticket["ticket_id"] or str(f.attrs.get("task")) != ticket["task_id"]:
                raise ValueError(f"raw demonstration identity mismatch: {p}")
            initial = str(f.attrs["init_state_id"])
            if initial not in ticket["init_state_ids"]:
                raise ValueError("raw demonstration initial state is outside ticket")
            if not (bool(f.attrs.get("simulator_success")) and bool(f.attrs.get("explicit_success"))
                    and bool(f.attrs.get("collection_committed"))):
                raise ValueError(f"uncommitted/unsuccessful file in raw: {p}")
            n = len(f["action"])
            if n < 1 or len(f["success"]) != n or not bool(f["success"][-1]) or len(f["observation/state"]) != n + 1:
                raise ValueError("raw action/native-success alignment is invalid")
            records.append({"path": str(p), "init_state_id": initial, "steps": n})
    return records


def complete_counts(records):
    return len(records) == 15 and sorted(Counter(r["init_state_id"] for r in records).values()) == [3] * 5


def proc_identity(pid):
    try:
        p = Path("/proc") / str(pid)
        args = (p / "cmdline").read_bytes().split(b"\0")
        fields = (p / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {"pid": int(pid), "start_ticks": fields[19], "args": [a.decode() for a in args if a]}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def owned_collectors(root):
    found = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        item = proc_identity(int(path.name))
        if item and "--offline-precollection-root" in item["args"]:
            a = item["args"]
            if a[a.index("--offline-precollection-root") + 1] == str(root):
                found.append(item)
    return found


def started_process_identity(child, command, *, timeout_seconds=5):
    """Wait for exec, not an empty/transient /proc cmdline after Popen."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        identity = proc_identity(child.pid)
        if identity is not None and identity["args"] == command:
            return identity
        if child.poll() is not None:
            raise RuntimeError("collector exited before process identity was recorded")
        if time.monotonic() >= deadline:
            raise RuntimeError("collector command line did not become ready before startup deadline")
        time.sleep(0.01)


class BatchRunner:
    def __init__(self, args):
        self.args = args
        self.root = args.plan.resolve().parent
        self.plan = read_json(args.plan)
        self.plan_sha = digest(args.plan)
        if Path(self.plan["batch_root"]).resolve() != self.root:
            raise ValueError("plan root and selected lifecycle directory disagree")
        manifest = read_json(self.plan["protocol_manifest_path"])
        validate_batch(self.plan, manifest)
        self.state_path = self.root / "status.json"
        self.state = read_json(self.state_path, {"schema_version": "offline-precollection-status-v1", "contexts": {}})
        if self.state.get("plan_sha256", self.plan_sha) != self.plan_sha:
            raise ValueError("cannot resume against a changed batch plan")
        self.state.update(plan_sha256=self.plan_sha, batch_id=self.plan["batch_id"], collection_role=ROLE,
            runner_pid=os.getpid(), tasks_planned=20, queue_root=str(self.root / "codex_account_queue"))
        self.interrupted = False
        self.child = None
        for name in ("logs", "collectors", "codex_account_queue", "audit"):
            (self.root / name).mkdir(exist_ok=True)
        from mode_gate.skill_collection import SkillCollectionConfig
        config = read_json(args.skill_config)
        if config["consecutive_failure_limit"] != effective_failure_limit(self.root, self.plan) or not config["use_visual_observations"]:
            raise ValueError("collector failure limit or visual requirement differs from batch")
        SkillCollectionConfig(**config)
        self.config = config
        control_path = self.root / "collection_control.json"
        self.state.update(effective_consecutive_failure_limit=config["consecutive_failure_limit"],
            historical_plan_failure_limit=self.plan["consecutive_control_failure_limit"],
            skill_config_sha256=digest(args.skill_config),
            collection_control_path=str(control_path) if control_path.exists() else None,
            collection_control_sha256=digest(control_path) if control_path.exists() else None)
        for item in self.state["contexts"].values():
            self.requeue_extended_limit(item)
            if getattr(args, "retry_infrastructure_errors", False):
                self.requeue_infrastructure_error(item)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "interrupted", True))

    def requeue_extended_limit(self, item):
        if item.get("state") != "NEEDS_HUMAN":
            return False
        progress = read_json(Path(item["ticket_path"]).parent / "automatic_collection/progress.json", {})
        failures = int(progress.get("consecutive_failures", 0))
        old_limit = int(progress.get("failure_limit", self.plan["consecutive_control_failure_limit"]))
        new_limit = self.config["consecutive_failure_limit"]
        if not old_limit <= failures < new_limit:
            return False
        evidence = {"old_limit": old_limit, "new_limit": new_limit,
                    "preserved_consecutive_failures": failures, "remaining_attempts": new_limit - failures}
        item.update(state="PENDING", retry_limit_resume=evidence)
        self.event("RETRY_LIMIT_INCREASE_REQUEUED", ticket_path=item["ticket_path"], **evidence)
        return True

    def ordered_contexts(self):
        """Adopt a live collector first; do not interrupt it to revisit a ticket."""
        collectors = owned_collectors(self.root)
        if not collectors:
            return list(self.plan["contexts"])
        if len(collectors) != 1:
            raise RuntimeError("multiple offline collectors found during resume")
        args = collectors[0]["args"]
        ticket_path = args[args.index("--ticket") + 1]
        active = [c for c in self.plan["contexts"]
                  if self.state["contexts"].get(c["context_id"], {}).get("ticket_path") == ticket_path]
        if len(active) != 1:
            raise RuntimeError("live collector does not match a single recorded batch context")
        return active + [c for c in self.plan["contexts"] if c["context_id"] != active[0]["context_id"]]

    def requeue_infrastructure_error(self, item):
        """An explicit resume retries infrastructure, never erases physical evidence."""
        if item.get("state") != "INFRA_ERROR":
            return False
        progress = read_json(Path(item["ticket_path"]).parent / "automatic_collection/progress.json", {})
        if int(progress.get("consecutive_failures", 0)) >= self.config["consecutive_failure_limit"]:
            return False
        previous = {key: item.get(key) for key in ("state", "last_error", "infrastructure_attempt")}
        item.setdefault("infrastructure_resume_history", []).append({"time": time.time(), **previous})
        item["state"] = "PENDING"
        self.event("EXPLICIT_INFRASTRUCTURE_RESUME", ticket_path=item["ticket_path"],
                   preserved_consecutive_failures=int(progress.get("consecutive_failures", 0)), **previous)
        return True

    def finish_completed_collector(self, ticket_path):
        # A live collector can commit its last success during a coordinator
        # handoff. Retire only that completed ticket's child before exporting.
        for identity in owned_collectors(self.root):
            args = identity["args"]
            if args[args.index("--ticket") + 1] == str(ticket_path):
                self.stop_child(identity, ticket_path, "native_collection_complete")

    def stopped(self):
        return self.interrupted or any((self.root / n).exists() for n in ("pause.request", "stop.request", "supervisor.stop.request"))

    def publish(self, state="RUNNING", **extra):
        values = list(self.state["contexts"].values())
        if state != "BLOCKED":
            self.state.pop("error", None)
        self.state.update(state=state, updated_at=datetime.now(timezone.utc).isoformat(),
            completed_tasks=sum(v.get("state") in {"COMPLETE", "COMPLETE_REUSED"} for v in values),
            processed_tasks=sum(v.get("state") in TERMINAL for v in values),
            native_successes=sum(v.get("native_successes", 0) for v in values), **extra)
        write_json(self.state_path, self.state)
        # This is the offline lifecycle adapter consumed by codex_account.
        wait_state = "STOPPED_BY_USER" if state == "PAUSED" else state
        write_json(self.root / "supervisor_status.json", {"state": wait_state, "collection_role": ROLE,
            "batch_state": state, "runner_pid": os.getpid(), "updated_at": time.time(),
            "planned_contexts": 20, "completed_contexts": self.state["completed_tasks"]})

    def event(self, event, **fields):
        with (self.root / "events.jsonl").open("a") as f:
            f.write(json.dumps({"time": time.time(), "event": event, **fields}, ensure_ascii=False) + "\n")
            f.flush()

    def child_pause(self, ticket_path):
        return self.root / "collectors" / (ticket_path.parent.name + ".pause.request")

    def stop_child(self, identity, ticket_path, reason):
        current = proc_identity(identity["pid"])
        if not current or current != identity:
            return
        write_json(self.child_pause(ticket_path), {"owner": "offline_precollection_runner", "reason": reason})
        os.kill(identity["pid"], signal.SIGTERM)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.child is not None:
                self.child.poll()
            if proc_identity(identity["pid"]) != identity:
                return
            time.sleep(0.2)
        raise RuntimeError("owned collector did not exit; no second collector will be started")

    def launch_or_adopt(self, ticket_path, item):
        existing = owned_collectors(self.root)
        if len(existing) > 1:
            raise RuntimeError("multiple offline collectors found; refusing another collector")
        if existing:
            identity = existing[0]
            a = identity["args"]
            if a[a.index("--ticket") + 1] != str(ticket_path):
                raise RuntimeError("another batch ticket still owns a collector")
            self.event("COLLECTOR_ADOPTED", **identity)
            return identity, float(item.get("collector_started_at", 0))
        pause = self.child_pause(ticket_path)
        if pause.exists():
            if read_json(pause).get("owner") != "offline_precollection_runner":
                raise RuntimeError("collector pause belongs to user; not clearing it")
            pause.unlink()
        cmd = [sys.executable, str(REPO / "scripts/teleop_server.py"), "--ticket", str(ticket_path),
            "--manifest", self.plan["protocol_manifest_path"], "--source", "ticket", "--collection-mode", "auto_skill",
            "--operator", "codex-offline-precollection", "--skill-config", str(self.args.skill_config.resolve()),
            "--collection-pause-file", str(pause), "--offline-precollection-root", str(self.root),
            "--port", str(self.args.port), "--max-steps", str(max(3000, self.config["max_attempt_steps"]))]
        # CUDA and EGL indices are distinct. Preserve the working renderer
        # selection from the adapter configuration / inherited environment.
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
            HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        log = self.root / "logs" / f"{ticket_path.parent.name}.collector.log"
        started = time.time()
        with log.open("ab") as f:
            self.child = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        identity = started_process_identity(self.child, cmd)
        item.update(collector=identity, collector_started_at=started, log_path=str(log))
        self.publish(active_ticket_id=ticket_path.parent.name)
        self.event("COLLECTOR_STARTED", ticket_id=ticket_path.parent.name, pid=identity["pid"], log_path=str(log))
        return identity, started

    def collect(self, ticket_path, item):
        progress_path = ticket_path.parent / "automatic_collection/progress.json"
        old = read_json(progress_path, {})
        if int(old.get("consecutive_failures", 0)) >= self.config["consecutive_failure_limit"]:
            item.update(state="NEEDS_HUMAN", progress=old)
            return
        identity, started = self.launch_or_adopt(ticket_path, item)
        while True:
            if self.stopped():
                self.stop_child(identity, ticket_path, "batch_pause")
                item["state"] = "PAUSED"
                return
            if self.child is not None:
                self.child.poll()
            progress = read_json(progress_path, {})
            fresh = progress_path.exists() and progress_path.stat().st_mtime >= started
            if fresh:
                item.update(progress=progress, state=progress.get("collection_state", "COLLECTING"))
                if progress.get("collection_state") in {"COMPLETE", "NEEDS_HUMAN", "PLANNER_ERROR", "CONTROLLER_ERROR", "PAUSED"}:
                    self.stop_child(identity, ticket_path, progress["collection_state"])
                    if (progress["collection_state"] == "NEEDS_HUMAN"
                            and int(progress.get("failure_limit", self.config["consecutive_failure_limit"]))
                            <= int(progress.get("consecutive_failures", 0)) < self.config["consecutive_failure_limit"]):
                        # The adopted worker still has the old ceiling. Its
                        # attempt is already saved; resume from the same streak.
                        self.event("LEGACY_COLLECTOR_LIMIT_EXTENDED", ticket_id=ticket_path.parent.name,
                            preserved_consecutive_failures=int(progress["consecutive_failures"]),
                            new_limit=self.config["consecutive_failure_limit"])
                        identity, started = self.launch_or_adopt(ticket_path, item)
                        continue
                    item["state"] = "COLLECTED" if progress["collection_state"] == "COMPLETE" else progress["collection_state"]
                    return
            item["native_successes"] = len(native_records(ticket_path))
            self.publish(active_ticket_id=ticket_path.parent.name)
            if proc_identity(identity["pid"]) != identity:
                raise RuntimeError(f"collector exited unexpectedly; inspect {item.get('log_path')}")
            time.sleep(self.args.poll_seconds)

    def finish_ticket(self, ticket_path, item):
        records = native_records(ticket_path)
        item["native_successes"] = len(records)
        from mode_gate.demo_videos import export_ticket_videos
        item["video_count"] = len(export_ticket_videos(ticket_path.parent))
        if not complete_counts(records):
            if item.get("state") != "NEEDS_HUMAN":
                raise RuntimeError("collection ended without fifteen original native successes across five states")
            return
        # Never restart collection to repair a curation/export infrastructure error.
        export_root = ticket_path.parent / "exports/lerobot_v3"
        if export_root.exists() and not (export_root / "meta/info.json").exists():
            backup = export_root.with_name("lerobot_v3.incomplete-" + uuid4().hex[:8])
            export_root.rename(backup)
            self.event("INCOMPLETE_EXPORT_PRESERVED", path=str(backup))
        item["state"] = "EXPORTING"
        self.publish()
        from mode_gate.data_pipeline import curate_and_export_ticket
        result = curate_and_export_ticket(ticket_path=ticket_path, repo_id="offline-precollection/" + ticket_path.parent.name)
        if result["needs_more_demos"] or len(result["accepted"]) != 15:
            raise RuntimeError("curation did not retain all native successes; do not recollect automatically")
        meta = read_json(export_root / "meta/info.json")
        if meta["total_episodes"] != 15 or meta["total_frames"] != sum(r["steps"] for r in records):
            raise RuntimeError("LeRobot export count mismatch")
        item.update(state="COMPLETE", export_root=str(export_root), total_frames=meta["total_frames"],
            curation_sha256=result["curation_sha256"])

    def run(self):
        self.publish()
        for context in self.ordered_contexts():
            if self.stopped():
                self.publish("PAUSED")
                return 0
            item = self.state["contexts"].setdefault(context["context_id"], {"task_key": context["task_key"], "state": "PENDING"})
            if item["state"] in TERMINAL:
                continue
            if context.get("reuse_ticket_path"):
                # Root task owns immutable reuse verification; no curation, export,
                # attribute edits or collector are applied to these original files.
                audit = self.plan["existing_reuse_audit"]
                if audit["ticket_id"] != context["reuse_ticket_id"] or audit["native_success_count"] != 15:
                    raise ValueError("missing verified reuse evidence")
                records = native_records(Path(context["reuse_ticket_path"]))
                if not complete_counts(records):
                    raise ValueError("verified reused native successes no longer complete")
                item.update(state="COMPLETE_REUSED", ticket_path=context["reuse_ticket_path"], native_successes=15,
                    reuse_evidence="plan.existing_reuse_audit", video_count=15)
                self.publish()
                continue
            ticket_path = make_ticket(self.plan, context, self.plan_sha)
            item["ticket_path"] = str(ticket_path)
            for retry in range(self.args.max_infrastructure_attempts):
                if self.stopped():
                    break
                item["infrastructure_attempt"] = retry + 1
                try:
                    if complete_counts(native_records(ticket_path)):
                        self.finish_completed_collector(ticket_path)
                        item["state"] = "COLLECTED"
                    else:
                        self.collect(ticket_path, item)
                    if item["state"] in {"COLLECTED", "NEEDS_HUMAN"}:
                        self.finish_ticket(ticket_path, item)
                        break
                    if item["state"] == "PAUSED":
                        self.publish("PAUSED")
                        return 0
                    raise RuntimeError(f"collection infrastructure state: {item['state']}")
                except Exception as exc:
                    item["last_error"] = f"{type(exc).__name__}: {exc}"
                    self.event("INFRASTRUCTURE_ERROR", ticket_id=ticket_path.parent.name, error=item["last_error"],
                        physical_failure_count_unchanged=True)
                    if owned_collectors(self.root):
                        # A hung process must never result in a second simulator.
                        self.publish("BLOCKED", error=item["last_error"])
                        return 2
                    if retry + 1 >= self.args.max_infrastructure_attempts:
                        item["state"] = "INFRA_ERROR"
                    else:
                        time.sleep(2)
            self.publish()
            self.event("TASK_TERMINAL", **item)
        if self.stopped():
            self.publish("PAUSED")
            return 0
        blockers = [v for v in self.state["contexts"].values() if v["state"] not in {"COMPLETE", "COMPLETE_REUSED"}]
        self.publish("COMPLETE_WITH_BLOCKERS" if blockers else "COMPLETE")
        write_json(self.root / "completion.json", self.state)
        return 2 if blockers else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--skill-config", type=Path, default=REPO / "configs/skill_collection.json")
    p.add_argument("--port", type=int, default=8870)
    p.add_argument("--poll-seconds", type=float, default=2)
    p.add_argument("--max-infrastructure-attempts", type=int, default=2)
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--retry-infrastructure-errors", action="store_true",
                   help="explicit resume of failed infrastructure; keep successes and physical failure history")
    args = p.parse_args()
    if not 1 <= args.max_infrastructure_attempts <= 3 or not 0.5 <= args.poll_seconds <= 10:
        p.error("bounded infrastructure attempts and polling required")
    root = args.plan.resolve().parent
    with (root / "runner.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.validate_only:
            plan = read_json(args.plan)
            validate_batch(plan, read_json(plan["protocol_manifest_path"]))
            print(json.dumps({"valid": True, "tasks": len(plan["contexts"]), "plan_sha256": digest(args.plan)}))
            return 0
        return BatchRunner(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
