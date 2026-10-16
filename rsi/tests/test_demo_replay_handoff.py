from pathlib import Path
from types import SimpleNamespace
import json

import h5py
import pytest
import numpy as np

from mode_gate.data_pipeline import curate_ticket_demos, pending_demo_replays
from mode_gate.slow_worker import SlowLoopWorker


def pending_demo(tmp_path):
    path = tmp_path / "raw/demo-000-test.hdf5"
    path.parent.mkdir(parents=True)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("action", data=np.zeros((2, 7)))
        handle.create_dataset("simulator_state", data=np.zeros((3, 3)))
        handle.create_dataset("observation/state", data=np.zeros((3, 8)))
        handle.create_dataset("ee_position", data=np.zeros((3, 3)))
        handle.create_dataset("success", data=[False, True])
        handle.attrs.update(collection_committed=True, simulator_success=True,
                            explicit_success=True, replay_status="pending_batch_validation",
                            coverage_cell="cell", demonstration_source="codex_skill_controller")
    return path


@pytest.mark.parametrize("replay_status", ["pending_batch_validation", "rejected", "error", "validated"])
def test_native_collection_success_curates_regardless_of_replay(tmp_path, replay_status):
    path = pending_demo(tmp_path)
    with h5py.File(path, "r+") as handle:
        handle.attrs["replay_status"] = replay_status
        handle.attrs["replay_validated"] = replay_status == "validated"
        handle.attrs["replay_task_success"] = False
        handle.attrs["replay_max_state_error"] = 100.0
        if replay_status == "error":
            handle.attrs["replay_error"] = "unavailable simulator"
    before = path.read_bytes()
    result = curate_ticket_demos([path], required_quotas={"cell": 1}, rejected_dir=tmp_path / "rejected")
    assert result.accepted == (path,) and not result.rejected and not result.needs_more_demos
    # Acceptance must not rewrite the actual native/replay evidence or data.
    assert path.read_bytes() == before


@pytest.mark.parametrize("missing_signal", [True, False])
def test_replay_success_cannot_promote_original_native_failure(tmp_path, missing_signal):
    path = pending_demo(tmp_path)
    with h5py.File(path, "r+") as handle:
        if missing_signal:
            del handle.attrs["simulator_success"]
        else:
            handle.attrs["simulator_success"] = False
        handle.attrs["replay_validated"] = True
        handle.attrs["replay_task_success"] = True
    result = curate_ticket_demos([path], required_quotas={"cell": 1}, rejected_dir=tmp_path / "rejected")
    assert not result.accepted and len(result.rejected) == 1 and result.needs_more_demos


def worker_and_job(tmp_path):
    from mode_gate.incidents import IncidentMemory
    worker = object.__new__(SlowLoopWorker)
    worker.incidents = IncidentMemory(tmp_path / "incidents")
    worker.protocol_manifest_path = tmp_path / "manifest.json"
    worker._job_dir = lambda job: tmp_path / "job"
    job = SimpleNamespace(job_id="job", ticket_id="ticket", active_policy_id="parent",
        metadata={"ticket_path": str(tmp_path / "ticket.json"), "gpu_index": 6})
    return worker, job


def test_worker_curates_native_success_without_replay(tmp_path, monkeypatch):
    path = pending_demo(tmp_path)
    worker, job = worker_and_job(tmp_path)
    calls = []
    def curate(**kwargs):
        assert pending_demo_replays([path]) == (path,)
        calls.append("curate")
        (tmp_path / "curation.json").write_text(json.dumps({"accepted": {}, "needs_more_demos": False}))
        return {"needs_more_demos": False, "export_root": str(tmp_path / "export"), "repo_id": "vls/test"}
    monkeypatch.setattr("mode_gate.slow_worker.subprocess.run", lambda *a, **kw: pytest.fail("replay is not a training gate"))
    monkeypatch.setattr("mode_gate.slow_worker.curate_and_export_ticket", curate)
    worker._curate(job)
    assert calls == ["curate"]


@pytest.mark.parametrize("native_success,drift", [(True, 100.0), (False, 0.0)])
def test_native_success_decides_replay_and_state_error_is_diagnostic(tmp_path, native_success, drift):
    from mode_gate.data_pipeline import validate_demo_replay
    path = tmp_path / "demo.hdf5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("simulator_state", data=np.zeros((4, 3)))
        handle.create_dataset("action", data=np.zeros((3, 7), dtype=np.float32))
        handle.attrs["simulator_success"] = True

    class Adapter:
        device = "cpu"
        steps = 0
        restores = 0
        def restore_flattened_simulator_state(self, state):
            self.restores += 1
        def step(self, action):
            self.steps += 1
            return {}, 0.0, False, False, {"success": native_success and self.steps == 2}
        def capture_simulator_state(self):
            return {"flattened_sim_state": np.full(3, drift), "qpos": np.array([drift]), "qvel": np.array([drift])}

    adapter = Adapter()
    validate_demo_replay(path, adapter=adapter, tolerance=1e-12,
                         position_tolerance=1e-12, velocity_tolerance=1e-12)
    assert adapter.restores == 1
    assert adapter.steps == (2 if native_success else 3)
    with h5py.File(path, "r") as handle:
        assert bool(handle.attrs["replay_validated"]) is native_success
        assert handle.attrs["replay_max_state_error"] == drift
        assert handle.attrs["replay_state_error_role"] == "diagnostic_only"


def test_missing_native_signal_is_infrastructure_error_not_success(tmp_path):
    from mode_gate.data_pipeline import validate_demo_replay, reassess_demo_replay
    path = tmp_path / "demo.hdf5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("simulator_state", data=np.zeros((2, 1)))
        handle.create_dataset("action", data=np.zeros((1, 7), dtype=np.float32))
        handle.attrs["simulator_success"] = True
    adapter = SimpleNamespace(device="cpu", restore_flattened_simulator_state=lambda value: None,
        capture_simulator_state=lambda: {"flattened_sim_state": np.zeros(1)},
        step=lambda action: ({}, 0.0, False, False, {}))
    with pytest.raises(RuntimeError, match="native success signal missing"):
        validate_demo_replay(path, adapter=adapter)
    with pytest.raises(ValueError, match="no complete replay diagnostics"):
        reassess_demo_replay(path)


def test_refill_preserves_actual_missing_initial_state(tmp_path):
    from scripts.teleop_server import _queue
    from mode_gate.io_utils import sha256_file
    ticket = SimpleNamespace(collection=SimpleNamespace(coverage_axes=(
        SimpleNamespace(axis="approach", value="vertical", quota=5),
        SimpleNamespace(axis="approach", value="side", quota=1))),
        init_state_ids=("37", "7"), demos_per_state=3, target_demos=6)
    root = tmp_path / "curated"
    root.mkdir()
    accepted = {}
    for index, (init, cell) in enumerate([("37", "vertical"), ("37", "vertical"),
                                        ("7", "vertical"), ("7", "vertical"), ("7", "side")]):
        path = root / f"demo-{index:03d}-test.hdf5"
        with h5py.File(path, "w") as handle:
            handle.attrs.update(init_state_id=init, coverage_cell=f"approach={cell}")
        accepted[str(path)] = {"sha256": sha256_file(path)}
    (tmp_path / "curation.json").write_text(json.dumps({"needs_more_demos": True,
        "accepted": accepted, "coverage": {"approach=vertical": {"accepted": 4, "quota": 5},
                                           "approach=side": {"accepted": 1, "quota": 1}}}))
    queue = _queue(ticket, source="ticket", ticket_root=tmp_path)
    assert len(queue) == 1
    assert queue[0]["init_state_id"] == "37"
    assert queue[0]["coverage_cell"] == "approach=vertical"


def test_training_waits_for_atomic_source_publication(tmp_path):
    worker, job = worker_and_job(tmp_path)
    path = tmp_path / "coft_sources.json"
    job.metadata["coft_source_spec_path"] = str(path)
    assert worker._prepare_training(job) is None
    assert not path.exists()
    assert not (tmp_path / "job/coft").exists()
    # A published but malformed config is a real error, not an indefinite wait.
    path.write_text("{")
    with pytest.raises(json.JSONDecodeError):
        worker._prepare_training(job)


def test_training_resumes_after_source_publication(tmp_path, monkeypatch):
    worker, job = worker_and_job(tmp_path)
    path = tmp_path / "coft_sources.json"
    job.metadata.update(coft_source_spec_path=str(path),
        current_ticket_repo_id="vls/new", current_ticket_dataset_path=str(tmp_path / "new"))
    assert worker._prepare_training(job) is None
    path.write_text(json.dumps({"replay": {"libero/replay": str(tmp_path / "replay")}}))
    worker.store = SimpleNamespace(events=SimpleNamespace(iter_valid=lambda: iter(())))
    def prepare(**kwargs):
        assert kwargs["new_datasets"] == {"vls/new": tmp_path / "new"}
        assert kwargs["replay_datasets"] == {"libero/replay": tmp_path / "replay"}
        raise RuntimeError("reached training preparation")
    monkeypatch.setattr("mode_gate.slow_worker.prepare_source_catalog", prepare)
    with pytest.raises(RuntimeError, match="reached training preparation"):
        worker._prepare_training(job)


def test_full_cycle_reports_source_wait_and_continues(tmp_path, monkeypatch):
    from mode_gate.slow_loop import SlowLoopState
    worker, job = worker_and_job(tmp_path)
    source = tmp_path / "coft_sources.json"
    job.metadata["coft_source_spec_path"] = str(source)
    job.state = SlowLoopState.DATASET_READY
    worker.store = SimpleNamespace(current=lambda _: job)
    worker.teleop_supervisor = object()
    def step(_):
        if source.exists():
            job.state = SlowLoopState.DEPLOYED
        return job
    worker.step = step
    seen = []
    def publish(_):
        status = json.loads((tmp_path / "job/automation_status.json").read_text())
        assert status["state"] == "DATASET_READY" and status["error"] is None
        assert status["waiting_for"] == {"kind": "coft_replay_source", "path": str(source)}
        seen.append(status)
        source.write_text("{}")
    monkeypatch.setattr("mode_gate.slow_worker.time.sleep", publish)
    worker.run_full_cycle(job.job_id)
    assert len(seen) == 1


def test_resumed_curation_clears_stale_error_before_long_export(tmp_path):
    from mode_gate.slow_loop import SlowLoopState
    worker, job = worker_and_job(tmp_path)
    job.state = SlowLoopState.CURATING
    worker.store = SimpleNamespace(current=lambda _: job)
    worker.teleop_supervisor = object()
    status = tmp_path / "job/automation_status.json"
    status.parent.mkdir()
    status.write_text(json.dumps({"state": "RETRYABLE_ERROR", "error": "old timeout"}))
    def step(_):
        current = json.loads(status.read_text())
        assert current["state"] == "CURATING" and current["error"] is None
        job.state = SlowLoopState.DEPLOYED
        return job
    worker.step = step
    worker.run_full_cycle(job.job_id)
