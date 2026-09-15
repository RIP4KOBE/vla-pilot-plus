from types import SimpleNamespace

import pytest

from baseline.io import read_json, write_json
from baseline.process_watch import ExistingWorker, verified_worker
from baseline.config import METHODS
from baseline.tests.test_campaign import frozen_config, EXPERIMENT


def fake_process(root, job, ticks=100):
    proc = root / str(job["pid"])
    proc.mkdir(exist_ok=True)
    (proc / "stat").write_text(f"{job['pid']} (python worker) " + " ".join(["S", *(["0"] * 18), str(ticks)]))
    (proc / "cmdline").write_bytes(b"\0".join(v.encode() for v in job["command"]) + b"\0")
    (proc / "environ").write_bytes(f"CUDA_VISIBLE_DEVICES={job['gpu_uuid']}\0".encode())
    return proc


def test_adoption_checks_identity_and_waits_for_actual_exit(tmp_path):
    job = {"pid": 12345, "command": ["python", "-m", "baseline", "train"], "gpu_uuid": "GPU-4"}
    proc = fake_process(tmp_path, job)
    worker = ExistingWorker(verified_worker(job, tmp_path), tmp_path / "output", tmp_path)
    write_json(tmp_path / "output/status.json", {"status": "complete"})
    assert worker.poll() is None
    (proc / "environ").write_bytes(b"CUDA_VISIBLE_DEVICES=GPU-6\0")
    with pytest.raises(RuntimeError, match="recorded baseline"):
        verified_worker(job, tmp_path)
    fake_process(tmp_path, job)
    (proc / "cmdline").write_bytes(b"unrelated_process\0")
    with pytest.raises(RuntimeError, match="recorded baseline"):
        verified_worker(job, tmp_path)
    fake_process(tmp_path, job, ticks=101)
    assert worker.poll() == 0
    write_json(tmp_path / "output/status.json", {"status": "failed"})
    assert worker.poll() == 1


def test_zombie_is_finished_and_missing_output_is_failure(tmp_path):
    job = {"pid": 23456, "command": ["python", "-m", "baseline"], "gpu_uuid": "GPU-7"}
    proc = fake_process(tmp_path, job)
    worker = ExistingWorker(verified_worker(job, tmp_path), tmp_path / "output", tmp_path)
    (proc / "stat").write_text((proc / "stat").read_text().replace(") S", ") Z"))
    assert verified_worker(job, tmp_path) is None
    assert worker.poll() == 1


def test_exit_permission_race_retries_but_persistent_denial_fails(monkeypatch):
    from baseline import process_watch
    attempts = []
    def exiting(*args):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("exiting task")
        return None
    monkeypatch.setattr(process_watch, "_read_identity", exiting)
    monkeypatch.setattr(process_watch.time, "sleep", lambda _: None)
    assert process_watch.process_identity(12345) is None and len(attempts) == 3
    def denied(*args):
        raise PermissionError("persistent denial")
    monkeypatch.setattr(process_watch, "_read_identity", denied)
    with pytest.raises(PermissionError, match="persistent denial"):
        process_watch.process_identity(12345)


def test_four_gpu_handoff_keeps_rl_workers_and_starts_only_imitation(tmp_path, monkeypatch):
    from baseline import campaign, demo_source, process_watch
    from baseline.scope import scope_identity
    experiment = tmp_path / "config"; experiment.mkdir()
    for method in METHODS:
        cfg = frozen_config()
        cfg.update(method=method, output_root=str(tmp_path / "outputs"), protocol=str(EXPERIMENT / "parent_protocol.json"))
        write_json(experiment / f"{method}.json", cfg)
    allocation = experiment / "allocation.json"
    write_json(allocation, {"method_gpu_indices": {"clare": 3, "mlr_ifa": 7, "continual_vla_rl": 5, "rl2_vla": 4}})
    methods = {m: {"state": "STAGE_TRAINED", "tasks_completed": 6, "artifact": "own_previous_stage", "evaluated": False} for m in METHODS}
    methods["v44_reference"] = {"state": "COMPLETE", "evaluated": True}
    jobs = [{"owner": owner, "method": owner, "phase": phase, "pid": pid, "gpu_index": gpu,
             "gpu_uuid": f"GPU-{gpu}", "command": ["python", "-m", "baseline", phase], "name": f"live_{owner}"}
            for owner, phase, pid, gpu in [("continual_vla_rl", "train", 1, 5), ("rl2_vla", "collect", 2, 4)]]
    for job in jobs:
        methods[job["owner"]]["state"] = "RUNNING"
    write_json(tmp_path / "outputs/queue/status.json", {"experiment_scope": scope_identity(cfg), "methods": methods,
               "collection_shards": [], "cursor": 4, "jobs": jobs})
    identities = {j["pid"]: {"pid": j["pid"], "start_ticks": 100 + j["pid"], "command": j["command"], "visible_gpu": j["gpu_uuid"]} for j in jobs}
    monkeypatch.setattr(process_watch, "process_identity", lambda pid, *a: identities.get(pid))
    monkeypatch.setattr(campaign, "cpu_environment", lambda: None)
    monkeypatch.setattr(campaign.os, "nice", lambda _: None)
    monkeypatch.setattr(campaign.signal, "signal", lambda *a: None)
    monkeypatch.setattr(demo_source, "snapshot_curated_source", lambda key, *a: {"task_key": key})
    monkeypatch.setattr(campaign.subprocess, "check_output", lambda *a, **k: "3, GPU-3, 45000\n4, GPU-4, 70000\n5, GPU-5, 60000\n7, GPU-7, 69000\n")
    created = []
    def popen(command, **kwargs):
        created.append((command, kwargs["env"]["CUDA_VISIBLE_DEVICES"]))
        return SimpleNamespace(pid=1000000 + len(created), poll=lambda: None)
    monkeypatch.setattr(campaign.subprocess, "Popen", popen)
    class EndCheck(Exception):
        pass
    monkeypatch.setattr(campaign.time, "sleep", lambda _: (_ for _ in ()).throw(EndCheck()))
    args = SimpleNamespace(experiment_dir=experiment, gpus=[3, 7, 4, 5], ticket_root=tmp_path / "tickets", collect_repeats=5,
                           resume=True, adopt_running=True, method_gpus=allocation)
    with pytest.raises(EndCheck):
        campaign.run(args)
    result = read_json(tmp_path / "outputs/queue/status.json")
    assert len(result["active_jobs"]) == 4 and len(created) == 2
    assert {gpu for _, gpu in created} == {"GPU-3", "GPU-7"}
    assert {j["owner"] for j in result["jobs"][2:]} == {"clare", "mlr_ifa"}
    assert [j["pid"] for j in result["jobs"][:2]] == [1, 2]
    assert all(result["methods"][j["owner"]]["tasks_completed"] == 6 for j in jobs)
