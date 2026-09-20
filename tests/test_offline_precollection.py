"""Offline collection boundaries, without creating or stepping a simulator."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pytest

from scripts import offline_precollection as op
from scripts.teleop_server import _offline_collection_context
from mode_gate.tickets import ExpansionTicket


@pytest.fixture
def batch(tmp_path):
    root = tmp_path / "batch"
    root.mkdir()
    contexts = [{"context_id": f"context-{i}", "task_key": f"task-{i}", "suite": "libero_10",
        "runtime_suite": "libero_10_env" if i < 10 else "libero_10_swap", "task_id": f"task-{i}",
        "task_index": i % 10, "perturbation_variant": "use_environment" if i < 10 else "use_swap",
        "source_split": "demo_online_pool", "legal_demo_init_state_ids": [str(j) for j in range(6)]}
        for i in range(20)]
    plan = {"schema_version": "libero-pro-offline-demo-precollection-v1", "collection_role": op.ROLE,
        "diversity_instruction": op.DIVERSITY, "tasks_planned": 20, "target_successes_per_task": 15,
        "target_init_states_per_task": 5, "target_successes_per_init_state": 3,
        "consecutive_control_failure_limit": 20, "max_parallel_collectors": 1, "gpu_index": 6,
        "protocol_manifest_sha256": "frozen", "batch_id": "test_batch", "batch_root": str(root),
        "ticket_root": str(tmp_path / "tickets"), "created_at": "2026-09-10T00:00:00Z",
        "success_authority": "LIBERO-PRO native predicate during original collection", "contexts": contexts}
    for flag in ("load_vla_model", "training_authorized", "formal_experiment_resume_authorized",
                 "create_slow_loop_jobs", "create_verifier_labels", "modify_registry", "scheduled_tasks_allowed"):
        plan[flag] = False
    manifest = {"manifest_sha256": "frozen", "tasks": [{**c, "splits": {"demo_online_pool": c["legal_demo_init_state_ids"]}} for c in contexts]}
    op.write_json(root / "plan.json", plan)
    return root, plan, manifest


def test_exact_twenty_tasks_and_legal_pool(batch):
    _, plan, manifest = batch
    op.validate_batch(plan, manifest)
    bad = copy.deepcopy(plan)
    bad["contexts"][0]["legal_demo_init_state_ids"][-1] = "999"
    with pytest.raises(ValueError, match="legal demo pool"):
        op.validate_batch(bad, manifest)


@pytest.mark.parametrize("flag", ["training_authorized", "formal_experiment_resume_authorized", "create_slow_loop_jobs", "modify_registry"])
def test_online_side_effect_flags_rejected(batch, flag):
    _, plan, manifest = batch
    plan[flag] = True
    with pytest.raises(ValueError, match="isolation flag"):
        op.validate_batch(plan, manifest)


def test_ticket_selection_idempotent_provenance_and_no_entities(batch):
    root, plan, _ = batch
    sha = op.digest(root / "plan.json")
    path = op.make_ticket(plan, plan["contexts"][0], sha)
    before = path.read_bytes()
    assert op.make_ticket(plan, plan["contexts"][0], sha) == path
    assert path.read_bytes() == before
    t = op.read_json(path)
    assert len(set(t["init_state_ids"])) == 5
    assert set(t["init_state_ids"]) <= set(plan["contexts"][0]["legal_demo_init_state_ids"])
    assert t["snapshot_id"] == "" and t["eval_init_state_ids"] == []
    assert t["failure_mode"] == "OFFLINE_PRECOLLECTION_NOT_A_FAILURE"
    assert t["parent_policy_id"] == "not_applicable_offline_precollection"
    assert t["registry_summary"]["signature_entity_created"] is False
    assert sum(c["quota"] for c in t["collection"]["coverage_axes"]) == 15
    assert op.DIVERSITY in t["collection"]["must_demonstrate"]
    assert not (root / "registry").exists() and not (root / "snapshots").exists()


def offline_args(root, path):
    return SimpleNamespace(offline_precollection_root=root, source="ticket", collection_mode="auto_skill",
        job_id=None, service_token=None, completion_file=None, ticket=path, collection_pause_file=None, output=None)


def test_teleop_isolates_pause_and_rejects_online_job(batch):
    root, plan, manifest = batch
    path = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    t = ExpansionTicket.model_validate(op.read_json(path))
    args = offline_args(root, path)
    actual_root, provenance = _offline_collection_context(args, t, manifest)
    assert actual_root == root and provenance["collection_role"] == op.ROLE
    assert args.collection_pause_file == root / "collectors" / (t.ticket_id + ".pause.request")
    args.job_id = "real-formal-job-must-not-be-used"
    with pytest.raises(ValueError, match="isolated"):
        _offline_collection_context(args, t, manifest)
    args.job_id = None
    args.collection_pause_file = root.parent / "formal_experiment/pause_after_slow_loop.request.json"
    with pytest.raises(ValueError, match="pause file"):
        _offline_collection_context(args, t, manifest)


def test_native_success_survives_replay_rejection(batch):
    root, plan, _ = batch
    path = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    t = op.read_json(path)
    for index in range(15):
        with h5py.File(path.parent / "raw" / f"demo-{index:03d}-test.hdf5", "w") as f:
            f.attrs.update(ticket_id=t["ticket_id"], task=t["task_id"], init_state_id=t["init_state_ids"][index // 3],
                simulator_success=True, explicit_success=True, collection_committed=True,
                replay_validated=False, replay_status="rejected", replay_error="diagnostic only")
            f.create_dataset("action", data=np.zeros((1, 7)))
            f.create_dataset("observation/state", data=np.zeros((2, 8)))
            f.create_dataset("success", data=np.array([True]))
    records = op.native_records(path)
    assert op.complete_counts(records)


def test_failed_raw_is_not_success(batch):
    root, plan, _ = batch
    path = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    t = op.read_json(path)
    with h5py.File(path.parent / "raw/demo-000-failed.hdf5", "w") as f:
        f.attrs.update(ticket_id=t["ticket_id"], task=t["task_id"], init_state_id=t["init_state_ids"][0],
                       simulator_success=False, explicit_success=False, collection_committed=False)
    with pytest.raises(ValueError, match="unsuccessful"):
        op.native_records(path)


def test_twenty_failures_resume_as_needs_human_without_reset(batch, monkeypatch):
    root, plan, _ = batch
    path = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    progress = path.parent / "automatic_collection/progress.json"
    op.write_json(progress, {"consecutive_failures": 20, "collection_state": "NEEDS_HUMAN"})
    original = progress.read_bytes()
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.config = {"consecutive_failure_limit": 20}
    monkeypatch.setattr(runner, "launch_or_adopt", lambda *_: pytest.fail("must not restart exhausted collector"))
    item = {}
    runner.collect(path, item)
    assert item["state"] == "NEEDS_HUMAN" and progress.read_bytes() == original


def test_stop_refuses_changed_process_identity(batch, monkeypatch):
    root, _, _ = batch
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.root = root
    monkeypatch.setattr(op, "proc_identity", lambda _: {"pid": 123, "start_ticks": "new"})
    monkeypatch.setattr(op.os, "kill", lambda *_: pytest.fail("must not signal a reused/unrelated PID"))
    runner.stop_child({"pid": 123, "start_ticks": "old"}, root / "ticket.json", "test")


def test_launch_preserves_egl_and_has_no_online_job(batch, monkeypatch):
    root, plan, _ = batch
    path = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    (root / "logs").mkdir()
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.root, runner.plan = root, plan
    runner.plan["protocol_manifest_path"] = str(root / "manifest.json")
    runner.args = SimpleNamespace(skill_config=root / "skill.json", port=8870)
    runner.config = {"max_attempt_steps": 1200}
    runner.publish = lambda **_: None
    runner.event = lambda *_, **__: None
    monkeypatch.setattr(op, "owned_collectors", lambda _: [])
    monkeypatch.setattr(op, "proc_identity", lambda _: {"pid": 123, "start_ticks": "1", "args": captured["cmd"]})
    monkeypatch.setenv("MUJOCO_EGL_DEVICE_ID", "8")
    captured = {}
    def launch(cmd, **kwargs):
        captured.update(cmd=cmd, **kwargs)
        return SimpleNamespace(pid=123)
    monkeypatch.setattr(op.subprocess, "Popen", launch)
    runner.launch_or_adopt(path, {})
    assert captured["env"]["MUJOCO_EGL_DEVICE_ID"] == "8"
    assert "--job-id" not in captured["cmd"]
    assert "--offline-precollection-root" in captured["cmd"]


def test_second_collector_never_started(batch, monkeypatch):
    root, _, _ = batch
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.root = root
    monkeypatch.setattr(op, "owned_collectors", lambda _: [{"pid": 1}, {"pid": 2}])
    with pytest.raises(RuntimeError, match="multiple offline collectors"):
        runner.launch_or_adopt(root / "ticket.json", {})


def test_explicit_retry_override_preserves_historical_plan_and_ticket(batch):
    root, plan, manifest = batch
    plan_before = (root / "plan.json").read_bytes()
    ticket_path = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    ticket_before = ticket_path.read_bytes()
    assert op.effective_failure_limit(root, plan) == 20
    control = {"schema_version": "offline-collection-control-v1", "batch_id": plan["batch_id"],
        "batch_plan_sha256": op.digest(root / "plan.json"), "requested_by": "user",
        "preserve_failure_counts": True, "consecutive_failure_limit": 50}
    op.write_json(root / "collection_control.json", control)
    assert op.effective_failure_limit(root, plan) == 50
    op.validate_batch(plan, manifest)
    assert op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json")) == ticket_path
    assert (root / "plan.json").read_bytes() == plan_before
    assert ticket_path.read_bytes() == ticket_before
    control["batch_plan_sha256"] = "another-plan"
    op.write_json(root / "collection_control.json", control)
    with pytest.raises(ValueError, match="bound to this batch"):
        op.effective_failure_limit(root, plan)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_plan_rejects_invalid_retry_limits(batch, limit):
    _, plan, manifest = batch
    plan["consecutive_control_failure_limit"] = limit
    with pytest.raises(ValueError, match="positive integer"):
        op.validate_batch(plan, manifest)


def test_new_plan_accepts_fifty_without_freezing_limit(batch):
    _, plan, manifest = batch
    plan["consecutive_control_failure_limit"] = 50
    op.validate_batch(plan, manifest)


def test_requeue_twenty_at_fifty_keeps_failure_evidence(batch):
    root, plan, _ = batch
    ticket = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    progress_path = ticket.parent / "automatic_collection/progress.json"
    op.write_json(progress_path, {"collection_state": "PAUSED", "consecutive_failures": 20,
        "failure_limit": 20, "entry_key": "same-entry", "failures": [{"error": "collision"}]})
    original = progress_path.read_bytes()
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.plan, runner.config = plan, {"consecutive_failure_limit": 50}
    events = []
    runner.event = lambda *a, **kw: events.append((a, kw))
    item = {"state": "NEEDS_HUMAN", "ticket_path": str(ticket), "native_successes": 7}
    assert runner.requeue_extended_limit(item)
    assert item["state"] == "PENDING" and item["native_successes"] == 7
    assert item["retry_limit_resume"]["preserved_consecutive_failures"] == 20
    assert item["retry_limit_resume"]["remaining_attempts"] == 30
    assert progress_path.read_bytes() == original and len(events) == 1
    item["state"] = "NEEDS_HUMAN"
    runner.config["consecutive_failure_limit"] = 20
    assert not runner.requeue_extended_limit(item)


def test_handoff_adopts_current_task_before_resumed_milk(batch, monkeypatch):
    root, plan, _ = batch
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.root, runner.plan = root, plan
    active = plan["contexts"][13]
    runner.state = {"contexts": {active["context_id"]: {"ticket_path": "/current-orange/ticket.json"}}}
    monkeypatch.setattr(op, "owned_collectors", lambda _: [{"args": ["python", "teleop_server.py",
        "--ticket", "/current-orange/ticket.json"]}])
    ordered = runner.ordered_contexts()
    assert ordered[0] == active and len(ordered) == 20
    assert len({c["context_id"] for c in ordered}) == 20
    assert plan["contexts"][12] in ordered[1:]


def test_adopted_twenty_limit_worker_restarts_at_boundary_with_fifty(batch, monkeypatch):
    root, plan, _ = batch
    ticket = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    progress_path = ticket.parent / "automatic_collection/progress.json"
    op.write_json(progress_path, {"collection_state": "NEEDS_HUMAN", "consecutive_failures": 20,
        "failure_limit": 20})
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.root, runner.plan = root, plan
    runner.config, runner.child = {"consecutive_failure_limit": 50}, None
    runner.stopped = lambda: False
    runner.event = lambda *a, **kw: None
    launched, stopped = [], []
    def launch(*_):
        identity = {"pid": len(launched) + 1}
        launched.append(identity)
        if len(launched) == 2:
            saved = op.read_json(progress_path)
            assert saved["consecutive_failures"] == 20
            op.write_json(progress_path, {"collection_state": "COMPLETE", "consecutive_failures": 0,
                "failure_limit": 50})
        return identity, 0
    runner.launch_or_adopt = launch
    runner.stop_child = lambda identity, *a: stopped.append(identity)
    item = {}
    runner.collect(ticket, item)
    assert len(launched) == len(stopped) == 2
    assert item["state"] == "COLLECTED"


def test_completed_collector_at_handoff_only_retires_matching_child(batch, monkeypatch):
    root, _, _ = batch
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.root = root
    owned = [{"pid": 1, "args": ["--ticket", "/completed/ticket.json"]},
             {"pid": 2, "args": ["--ticket", "/unrelated/ticket.json"]}]
    monkeypatch.setattr(op, "owned_collectors", lambda _: owned)
    stopped = []
    runner.stop_child = lambda identity, *args: stopped.append(identity["pid"])
    runner.finish_completed_collector(Path("/completed/ticket.json"))
    assert stopped == [1]


def test_startup_waits_for_exec_command_line(monkeypatch):
    command = ["python", "teleop_server.py", "--ticket", "/task/ticket.json"]
    expected = {"pid": 123, "start_ticks": "1", "args": command}
    snapshots = iter([None, {**expected, "args": []}, {**expected, "args": ["parent"]}, expected])
    monkeypatch.setattr(op, "proc_identity", lambda _: next(snapshots))
    sleeps = []
    monkeypatch.setattr(op.time, "sleep", sleeps.append)
    assert op.started_process_identity(SimpleNamespace(pid=123, poll=lambda: None), command) == expected
    assert sleeps == [.01] * 3


def test_startup_failure_is_bounded(monkeypatch):
    monkeypatch.setattr(op, "proc_identity", lambda _: None)
    with pytest.raises(RuntimeError, match="exited"):
        op.started_process_identity(SimpleNamespace(pid=123, poll=lambda: 1), ["python"])
    ticks = iter([0, 1])
    monkeypatch.setattr(op.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="startup deadline"):
        op.started_process_identity(SimpleNamespace(pid=123, poll=lambda: None), ["python"], timeout_seconds=.5)


def test_explicit_infrastructure_resume_keeps_successes_and_failure_history(batch):
    root, plan, _ = batch
    ticket = op.make_ticket(plan, plan["contexts"][0], op.digest(root / "plan.json"))
    progress_path = ticket.parent / "automatic_collection/progress.json"
    op.write_json(progress_path, {"consecutive_failures": 7, "collection_state": "PLANNER_ERROR",
        "entry_key": "same-entry", "failures": [{"error": "actual collision"}]})
    before = progress_path.read_bytes()
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.config = {"consecutive_failure_limit": 50}
    events = []
    runner.event = lambda *a, **kw: events.append((a, kw))
    item = {"state": "INFRA_ERROR", "ticket_path": str(ticket), "native_successes": 4,
            "last_error": "planner timeout", "infrastructure_attempt": 2}
    assert runner.requeue_infrastructure_error(item)
    assert item["state"] == "PENDING" and item["native_successes"] == 4
    assert item["infrastructure_resume_history"][0]["last_error"] == "planner timeout"
    assert progress_path.read_bytes() == before and len(events) == 1
    for terminal in ["COMPLETE", "COMPLETE_REUSED", "NEEDS_HUMAN"]:
        item["state"] = terminal
        assert not runner.requeue_infrastructure_error(item)
    item["state"] = "INFRA_ERROR"
    runner.config["consecutive_failure_limit"] = 7
    assert not runner.requeue_infrastructure_error(item)


@pytest.mark.parametrize("state", ["BLOCKED", "COMPLETE_WITH_BLOCKERS", "COMPLETE", "PAUSED", "RUNNING"])
def test_published_wait_state_does_not_mask_blocked_batch(batch, state):
    root, _, _ = batch
    runner = op.BatchRunner.__new__(op.BatchRunner)
    runner.root, runner.state_path = root, root / "status.json"
    runner.state = {"contexts": {}, "error": "old blocked error"}
    runner.publish(state)
    expected = "STOPPED_BY_USER" if state == "PAUSED" else state
    assert op.read_json(root / "supervisor_status.json")["state"] == expected
    if state != "BLOCKED":
        assert "error" not in op.read_json(root / "status.json")
