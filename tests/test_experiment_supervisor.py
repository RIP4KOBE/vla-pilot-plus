from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from mode_gate import experiment_supervisor as recovery
from mode_gate.coft_recovery import (MARKER, STATE_FILES, checkpoint_complete,
                                     prepare_coft_execution, save_coft_checkpoint)
from mode_gate.io_utils import AtomicJsonl, atomic_write_json
from mode_gate.slow_loop import SlowLoopState, SlowLoopStore


def experiment(tmp_path, count=40):
    root, output = tmp_path / "root", tmp_path / "run"
    output.mkdir()
    contexts = [{"context_id": f"c{i}", "task_key": f"task{i}", "runtime_suite": "libero_10_env",
                 "init_state_id": str(i), "source_split": "demo_online_pool"} for i in range(count)]
    atomic_write_json(output / "plan.json", {"task_count": count, "contexts": contexts,
                                             "gpu_index": 6, "manifest_path": str(root / "manifest.json")})
    return root, output, contexts


def complete(output, context, *, success=False, jobs=()):
    AtomicJsonl(output / "episodes.jsonl").append({
        **context, "event_id": context["context_id"], "event": "EPISODE_COMPLETED",
        "success": success, "slow_loop_jobs": list(jobs),
        "deployment": {"policy_id": "after-slow-merge", "verifier_id": "finetuned-from-initializer"},
    })


def supervisor(root, output):
    return recovery.ExperimentSupervisor(root=root, output=output, repo_root=Path.cwd(),
                                         python_executable=Path(sys.executable))


def test_complete_only_after_40_contexts_and_last_slow_loop(tmp_path):
    root, output, contexts = experiment(tmp_path)
    for context in contexts[:-1]:
        complete(output, context, success=True)
    store = SlowLoopStore(root / "slow_loop")
    job = store.create(active_policy_id="parent", input_hash="input", metadata={"task_id": "task39"})
    complete(output, contexts[-1], jobs=[job.job_id])
    progress = recovery.experiment_progress(root, output)
    assert not progress["complete"]
    preliminary = recovery.publish_experiment_results(root, output, progress)
    assert preliminary["completed_tasks"] == 40
    assert preliminary["online_success_rate"] == 39 / 40
    assert preliminary["task_results"][-1]["policy_id_after_episode"] == "after-slow-merge"
    store._append(replace(job, sequence=job.sequence + 1, state=SlowLoopState.DEPLOYED))
    assert supervisor(root, output).tick()["state"] == "COMPLETE"
    report = json.loads((output / "results.json").read_text())
    assert report["complete"] and not report["final_seal_opened"]
    assert len((output / "task_results.csv").read_text().splitlines()) == 41
    assert not (output / "stop.request").exists()  # warm main is not stopped


def test_report_pending_is_not_failed_and_native_identity_checked(tmp_path):
    root, output, contexts = experiment(tmp_path)
    complete(output, contexts[0], success=True)
    progress = recovery.experiment_progress(root, output)
    report = recovery.publish_experiment_results(root, output, progress)
    assert report["online_success_rate"] == 1
    assert report["task_results"][1]["success"] is None
    complete(output, {**contexts[1], "runtime_suite": "wrong"})
    with pytest.raises(ValueError, match="identity mismatch"):
        recovery.experiment_progress(root, output)


@pytest.mark.parametrize("message,expected", [
    ("ConnectionError: timed out", "RETRY_FROM_DURABLE_PROGRESS"),
    ("CUDA out of memory", "RETRY_FROM_DURABLE_PROGRESS"),
    ("budget exhausted after timeout", "STOP_WITH_DIAGNOSTIC"),
    ("label contract hash mismatch", "STOP_WITH_DIAGNOSTIC"),
    ("invalid api key", "STOP_WITH_DIAGNOSTIC"),
    ("unexpected coding bug", "STOP_WITH_DIAGNOSTIC"),
])
def test_failure_boundaries(message, expected):
    assert recovery.classify_failure(message) == expected


def test_retries_remain_bounded_when_traceback_timestamps_change(tmp_path, monkeypatch):
    root, output, _ = experiment(tmp_path)
    manager = supervisor(root, output)
    manager.config = recovery.RecoveryConfig(max_consecutive_retries=2)
    clock = [1000]
    monkeypatch.setattr(recovery.time, "time", lambda: clock[0])
    attempts = []
    for i in range(4):
        result = manager._retry("same-job:TRAINING", f"ConnectionError time={i}", lambda: attempts.append(i))
        clock[0] += 1000
    assert len(attempts) == 2 and result["state"] == "BLOCKED_WITH_DIAGNOSTIC"
    restored = supervisor(root, output)
    restored.config = manager.config
    assert restored._retry("same-job:TRAINING", "timeout again", lambda: pytest.fail())["state"] == "BLOCKED_WITH_DIAGNOSTIC"


def test_user_stop_and_park_never_spawn(tmp_path, monkeypatch):
    root, output, _ = experiment(tmp_path)
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *a, **k: pytest.fail("must respect user stop"))
    (output / "park.request").touch()
    assert supervisor(root, output).tick()["state"] == "USER_PAUSED"
    (output / "stop.request").touch()
    assert supervisor(root, output).tick()["state"] == "STOPPED_BY_USER"


def pause_target(tmp_path):
    root, output, contexts = experiment(tmp_path)
    context = {**contexts[1], "task_id": "drawer", "perturbation_variant": "use_environment"}
    plan = json.loads((output / "plan.json").read_text())
    plan["contexts"][1] = context
    plan["manifest_sha256"] = "manifest"
    atomic_write_json(output / "plan.json", plan)
    store = SlowLoopStore(root / "slow_loop")
    job = store.create(active_policy_id="parent", input_hash="input", metadata={
        key: context[key] for key in ("task_id", "init_state_id", "perturbation_variant")
    })
    atomic_write_json(output / "rollouts" / context["context_id"] / "attempt_001" /
                      "episode_1" / "mode_gate_expansion_request.json", {"slow_loop_job_id": job.job_id})
    return root, output, context, store, job


@pytest.mark.parametrize("state", [SlowLoopState.RAW_REGRESSION,
    SlowLoopState.NEW_POLICY_COUNTERFACTUAL, SlowLoopState.VERIFIER_TRAINING,
    SlowLoopState.VERIFIER_PENDING, SlowLoopState.READY_PAIR, SlowLoopState.RETRYABLE_ERROR])
def test_deferred_pause_does_not_interrupt_current_slow_loop(tmp_path, state):
    root, output, context, store, job = pause_target(tmp_path)
    request = recovery.request_pause_after_slow_loop(root=root, output=output,
        job_id=job.job_id, context_id=context["context_id"])
    store._append(replace(job, sequence=job.sequence + 1, state=state))
    assert recovery.apply_pause_after_slow_loop(root=root, output=output) is None
    assert not (output / "park.request").exists()
    assert not (output / "stop.request").exists()
    assert recovery.request_pause_after_slow_loop(root=root, output=output,
        job_id=job.job_id, context_id=context["context_id"]) == request


@pytest.mark.parametrize("state", [SlowLoopState.DEPLOYED, SlowLoopState.POLICY_REJECTED])
def test_deferred_pause_stops_next_task_without_inventing_results(tmp_path, state, monkeypatch):
    root, output, context, store, job = pause_target(tmp_path)
    recovery.request_pause_after_slow_loop(root=root, output=output,
        job_id=job.job_id, context_id=context["context_id"])
    store._append(replace(job, sequence=job.sequence + 1, state=state))
    result = recovery.apply_pause_after_slow_loop(root=root, output=output)
    assert result["state"] == "PAUSED_AFTER_SLOW_LOOP"
    assert result["next_fast_loop_allowed"] is False
    assert (output / "park.request").exists()
    assert not (output / "episodes.jsonl").exists()
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *a, **k: pytest.fail("paused run restarted"))
    assert supervisor(root, output).tick()["state"] == "USER_PAUSED"
    (output / "park.request").unlink()
    assert recovery.apply_pause_after_slow_loop(root=root, output=output)
    assert (output / "park.request").exists()  # recovery cannot silently resume


def test_deferred_pause_rejects_wrong_context_and_manifest(tmp_path):
    root, output, context, store, job = pause_target(tmp_path)
    with pytest.raises(ValueError, match="not bound"):
        recovery.request_pause_after_slow_loop(root=root, output=output,
            job_id=job.job_id, context_id="c0")
    request = recovery.request_pause_after_slow_loop(root=root, output=output,
        job_id=job.job_id, context_id=context["context_id"])
    atomic_write_json(output / "pause_after_slow_loop.request.json",
                      {**request, "manifest_sha256": "wrong"})
    with pytest.raises(ValueError, match="identity mismatch"):
        recovery.apply_pause_after_slow_loop(root=root, output=output)
    assert not (output / "park.request").exists()


def test_healthy_warm_main_is_not_restarted(tmp_path, monkeypatch):
    root, output, _ = experiment(tmp_path)
    atomic_write_json(output / "status.json", {"pid": 123, "state": "RUNNING"})
    monkeypatch.setattr(recovery, "process_identity", lambda pid: {"pid": pid, "command": ["python", "scripts/run_full_experiment.py"]})
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *a, **k: pytest.fail("healthy warm main restarted"))
    status = supervisor(root, output).tick()
    assert status["state"] == "RUNNING" and status["main_alive"]


def test_warm_error_retries_without_a_model_reload(tmp_path, monkeypatch):
    root, output, _ = experiment(tmp_path)
    atomic_write_json(output / "status.json", {"pid": 123, "state": "ERROR_WARM", "error": "ConnectionError", "current_context": 2})
    monkeypatch.setattr(recovery, "process_identity", lambda pid: {"pid": pid, "command": ["python", "scripts/run_full_experiment.py"]})
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *a, **k: pytest.fail("warm main restarted"))
    manager = supervisor(root, output)
    manager.tick()
    assert (output / "resume.request").is_file()
    manager.tick()
    assert len(list(manager.events.iter_valid())) == 1


@pytest.mark.skipif(not Path("/proc/self/stat").is_file(), reason="Linux process identity")
def test_orphan_adoption_does_not_launch_duplicate(tmp_path, monkeypatch):
    from mode_gate import job_runner
    command = [sys.executable, "-c", "import time; time.sleep(20)", str(tmp_path)]
    child = subprocess.Popen(command, cwd=tmp_path)
    try:
        spec = tmp_path / "gate.json"
        atomic_write_json(spec, {"schema_version": "policy-gate-job-v1", "command": command, "cwd": str(tmp_path)})
        record = job_runner.adopt_existing_execution(spec)
        assert record["pid"] == child.pid
        monkeypatch.setattr(job_runner, "_validate_command", lambda *a: None)
        monkeypatch.setattr(job_runner.subprocess, "Popen", lambda *a, **k: pytest.fail("duplicate child"))
        result = job_runner.execute_job_spec(spec)
        assert not result["launched"] and result["pid"] == child.pid
        assert recovery.same_process(record)
        assert not recovery.same_process({**record, "start_ticks": "different"})
    finally:
        child.terminate()
        child.wait(timeout=5)


@pytest.mark.skipif(not Path("/proc/self/stat").is_file(), reason="Linux process identity")
def test_adopted_orphan_still_has_bounded_execution_timeout(tmp_path, monkeypatch):
    from mode_gate import job_runner
    command = [sys.executable, "-c", "import time; time.sleep(20)", str(tmp_path)]
    child = subprocess.Popen(command, cwd=tmp_path, start_new_session=True)
    try:
        spec = tmp_path / "gate.json"
        atomic_write_json(spec, {"schema_version": "policy-gate-job-v1", "command": command, "cwd": str(tmp_path)})
        running = job_runner.adopt_existing_execution(spec)
        atomic_write_json(spec.with_name("gate.running.json"), {**running, "adopted_at": 0})
        monkeypatch.setattr(job_runner, "_validate_command", lambda *a: None)
        monkeypatch.setattr(job_runner.subprocess, "Popen", lambda *a, **k: pytest.fail("duplicate child"))
        result = job_runner.execute_job_spec(spec, timeout_seconds=1)
        assert result["timed_out"] and not result["completed"] and result["returncode"] == 124
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def checkpoint_fixture(tmp_path):
    output = tmp_path / "job/training_output"
    source = tmp_path / "source.json"
    atomic_write_json(source, {"manifest_sha256": "source"})
    cfg = SimpleNamespace(source_sampler_manifest=source, output_dir=output, steps=1000,
                          batch_size=4, gradient_accumulation_steps=8)
    def save_fn(*, checkpoint_dir, step, cfg, **kwargs):
        pretrained, state = checkpoint_dir / "pretrained_model", checkpoint_dir / "training_state"
        pretrained.mkdir()
        state.mkdir()
        atomic_write_json(pretrained / "train_config.json", {**vars(cfg), "output_dir": str(cfg.output_dir),
                                                             "source_sampler_manifest": str(cfg.source_sampler_manifest)})
        atomic_write_json(pretrained / "config.json", {})
        (pretrained / "model.safetensors").write_bytes(b"example-weights")
        for name in STATE_FILES:
            (state / name).write_bytes(b"state")
        atomic_write_json(state / "training_step.json", {"step": step})
    spec = {"expected_checkpoint": str(output / "checkpoints/001000/pretrained_model"),
            "source_manifest_sha256": "source"}
    command = ("python", "--policy.path=parent", f"--output_dir={output}", "--steps=1000", "--batch_size=4",
               "--gradient_accumulation_steps=8", f"--source_sampler_manifest={source}")
    return cfg, save_fn, spec, command


def test_checkpoint_resume_requires_complete_state_and_resumes_latest(tmp_path):
    cfg, save_fn, spec, command = checkpoint_fixture(tmp_path)
    for step in (250, 500, 750):
        path = cfg.output_dir / "checkpoints" / f"{step:06d}"
        save_coft_checkpoint(save_fn=save_fn, checkpoint_dir=path, step=step, cfg=cfg,
                             optimizer=object(), scheduler=object())
    assert not (cfg.output_dir / "checkpoints/000250").exists()
    resumed, metadata = prepare_coft_execution(command, spec)
    assert "--resume=true" in resumed and not any(v.startswith("--policy.path=") for v in resumed)
    assert metadata["step"] == 750
    path = Path(metadata["checkpoint"])
    assert checkpoint_complete(path, source_manifest=cfg.source_sampler_manifest, expected_step=750)
    (path / "training_state/optimizer_state.safetensors").write_bytes(b"truncated")
    with pytest.raises(ValueError, match="corrupt"):
        prepare_coft_execution(command, spec)


def test_partial_checkpoint_is_not_published_and_early_output_is_preserved(tmp_path):
    cfg, save_fn, spec, command = checkpoint_fixture(tmp_path)
    def broken_save(**kwargs):
        (kwargs["checkpoint_dir"] / "partial").write_bytes(b"partial")
        raise OSError("disk interruption")
    path = cfg.output_dir / "checkpoints/000250"
    with pytest.raises(OSError):
        save_coft_checkpoint(save_fn=broken_save, checkpoint_dir=path, step=250, cfg=cfg,
                             optimizer=object(), scheduler=object())
    assert not path.exists() and not checkpoint_complete(path)
    restarted, metadata = prepare_coft_execution(command, spec)
    assert restarted == command and Path(metadata["preserved_output"]).is_dir()
    assert not cfg.output_dir.exists()


def test_resume_sampler_skips_exact_draw_prefix():
    from mode_gate.training import SourceAwareSampler
    kwargs = dict(new_indices=[0, 1], old_ticket_indices={"old": [2, 3]}, replay_indices=[4, 5],
                  num_samples=320, seed=17)
    whole = list(SourceAwareSampler(**kwargs))
    resumed = SourceAwareSampler(**kwargs, start_index=96)
    assert list(resumed) == whole[96:] and len(resumed) == 224


def test_native_full_state_restore_matches_uninterrupted_cpu_update(tmp_path, monkeypatch):
    import torch
    from safetensors.torch import load_file, save_file
    from lerobot.utils.train_utils import save_checkpoint, load_training_state
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    cfg, _, _, _ = checkpoint_fixture(tmp_path)
    def save_config(path):
        atomic_write_json(path / "train_config.json", {"output_dir": str(cfg.output_dir), "steps": 1000})
    cfg.save_pretrained = save_config
    torch.manual_seed(123)
    model = torch.nn.Linear(3, 1)
    def save_policy(path):
        path.mkdir(parents=True)
        save_file(model.state_dict(), str(path / "model.safetensors"))
        atomic_write_json(path / "config.json", {"type": "cpu_checkpoint_canary"})
    model.save_pretrained = save_policy
    optimizer = torch.optim.AdamW(model.parameters(), lr=.01)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=.9)
    def update(policy, opt, schedule):
        opt.zero_grad()
        loss = policy(torch.randn(4, 3)).square().mean()
        loss.backward()
        opt.step()
        schedule.step()
        return loss.item()
    update(model, optimizer, scheduler)
    checkpoint = cfg.output_dir / "checkpoints/000001"
    save_coft_checkpoint(save_fn=save_checkpoint, checkpoint_dir=checkpoint, step=1,
                         cfg=cfg, policy=model, optimizer=optimizer, scheduler=scheduler)
    expected_loss = update(model, optimizer, scheduler)
    expected = {name: tensor.clone() for name, tensor in model.state_dict().items()}
    resumed = torch.nn.Linear(3, 1)
    resumed.load_state_dict(load_file(str(checkpoint / "pretrained_model/model.safetensors")))
    resumed_optimizer = torch.optim.AdamW(resumed.parameters(), lr=.01)
    resumed_scheduler = torch.optim.lr_scheduler.StepLR(resumed_optimizer, step_size=1, gamma=.9)
    step, resumed_optimizer, resumed_scheduler = load_training_state(checkpoint, resumed_optimizer, resumed_scheduler)
    assert step == 1
    assert update(resumed, resumed_optimizer, resumed_scheduler) == expected_loss
    assert all(torch.equal(resumed.state_dict()[name], value) for name, value in expected.items())
    assert resumed_scheduler.state_dict() == scheduler.state_dict()


@pytest.mark.parametrize("authority", ["api.openai.com:443", "generativelanguage.googleapis.com:443"])
def test_transport_allows_only_authorized_tls_apis(authority):
    from scripts.keep_experiment_transport import connect_target
    assert connect_target(authority) == (authority.split(":")[0], 443)


@pytest.mark.parametrize("authority", ["example.com:443", "api.openai.com.evil.test:443", "api.openai.com:80",
                                       "127.0.0.1:443", "user@api.openai.com:443", "api.openai.com"])
def test_transport_rejects_other_destinations(authority):
    from scripts.keep_experiment_transport import connect_target
    with pytest.raises(ValueError):
        connect_target(authority)
