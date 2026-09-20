import json
import time

import pytest

from mode_gate import codex_account as account


def request(root, request_id="a" * 32, **fields):
    value = {"request_id": request_id, "expires_at": time.time() + 60, **fields}
    account.write_json(root / request_id / "request.json", value)
    return value


def test_fresh_server_request_wakes_existing_account_worker(tmp_path):
    req = request(tmp_path)
    result = account.wait_for_request(tmp_path, {
        "worker_id": "dedicated-worker", "planner_thread_id": "existing-thread"}, wait_seconds=0)
    assert result["request"] == req
    worker = json.loads((tmp_path / "worker.json").read_text())
    assert worker["state"] == "REQUEST_CLAIMED"
    assert worker["planner_thread_id"] == "existing-thread"
    assert worker["request_id"] == req["request_id"]
    assert account.wait_for_request(tmp_path, {"worker_id": "same-worker"}, wait_seconds=0)["request"] is None


def test_wait_returns_when_request_arrives_without_new_thread(tmp_path, monkeypatch):
    sleeps = []

    def arrived(_seconds):
        sleeps.append(True)
        request(tmp_path)

    monkeypatch.setattr(account.time, "sleep", arrived)
    result = account.wait_for_request(tmp_path, {"worker_id": "same-thread"}, wait_seconds=45)
    assert result["request"]["request_id"] == "a" * 32
    assert len(sleeps) == 1


@pytest.mark.parametrize("terminal", ["COMPLETE", "COMPLETE_WITH_BLOCKERS", "BLOCKED", "INFRA_ERROR",
                                      "STOPPED_BY_USER", "SUPERVISOR_STOPPED_BY_USER"])
def test_experiment_terminal_does_not_claim_pending_request(tmp_path, terminal):
    queue, output = tmp_path / "queue", tmp_path / "experiment"
    req = request(queue)
    account.write_json(output / "supervisor_status.json", {"state": terminal})
    result = account.wait_for_request(queue, {"worker_id": "worker"},
                                      wait_seconds=45, experiment_output=output)
    assert result == {"request": None, "service_state": terminal}
    assert not (queue / req["request_id"] / "claim.json").exists()


@pytest.mark.parametrize("stop_file", ["pause.request", "stop.request", "supervisor.stop.request"])
def test_user_stop_wakes_idle_wait(tmp_path, monkeypatch, stop_file):
    output = tmp_path / "experiment"
    output.mkdir()
    monkeypatch.setattr(account.time, "sleep", lambda _: (output / stop_file).touch())
    result = account.wait_for_request(tmp_path / "queue", {"worker_id": "worker"},
                                      experiment_output=output)
    assert result["service_state"] == "STOPPED_BY_USER"


def test_finished_cancelled_expired_and_claimed_requests_do_not_wake(tmp_path):
    for letter, marker in (("a", "response.json"), ("b", "cancelled.json"), ("c", "claim.json")):
        req = request(tmp_path, letter * 32)
        account.write_json(tmp_path / req["request_id"] / marker, {"expires_at": time.time() + 60})
    request(tmp_path, "d" * 32, expires_at=time.time() - 1)
    result = account.wait_for_request(tmp_path, {"worker_id": "worker"}, wait_seconds=0)
    assert result["request"] is None and result["service_state"] == "WAITING"


def test_active_experiment_is_not_collection_and_does_not_launch_anything(tmp_path):
    output = tmp_path / "experiment"
    account.write_json(output / "supervisor_status.json", {
        "state": "RUNNING", "completed_contexts": 1, "planned_contexts": 40})
    result = account.wait_for_request(tmp_path / "queue", {"worker_id": "worker"},
                                      wait_seconds=0, experiment_output=output)
    assert result == {"request": None, "service_state": "WAITING", "experiment_state": "RUNNING"}


@pytest.mark.parametrize("seconds", [-1, 46, float("nan")])
def test_wait_is_bounded(tmp_path, seconds):
    with pytest.raises(ValueError, match="zero and 45"):
        account.wait_for_request(tmp_path, {"worker_id": "worker"}, wait_seconds=seconds)


def test_wrong_experiment_path_fails_without_claim(tmp_path):
    req = request(tmp_path / "queue")
    with pytest.raises(ValueError, match="does not exist"):
        account.wait_for_request(tmp_path / "queue", {"worker_id": "worker"},
                                 experiment_output=tmp_path / "missing")
    assert not (tmp_path / "queue" / req["request_id"] / "claim.json").exists()


def test_idle_volatile_heartbeat_does_not_write_or_lock_shared_queue(tmp_path, monkeypatch):
    queue, heartbeat = tmp_path / "shared_queue", tmp_path / "ram/worker.json"
    req = request(queue)
    account.write_json(queue / req["request_id"] / "cancelled.json", {})
    before = {p: p.read_bytes() for p in queue.rglob("*") if p.is_file()}
    monkeypatch.setattr(account.fcntl, "flock", lambda *_: pytest.fail("idle wait locked shared queue"))
    result = account.wait_for_request(queue, {
        "worker_id": "worker", "worker_status_path": str(heartbeat)}, wait_seconds=0)
    assert result["service_state"] == "WAITING"
    assert json.loads(heartbeat.read_text())["state"] == "WAITING_FOR_REQUEST"
    assert {p: p.read_bytes() for p in queue.rglob("*") if p.is_file()} == before


def test_volatile_heartbeat_keeps_real_claim_and_response_durable(tmp_path):
    queue, heartbeat = tmp_path / "shared_queue", tmp_path / "ram/worker.json"
    req = request(queue)
    value = {"worker_id": "worker", "worker_status_path": str(heartbeat)}
    result = account.wait_for_request(queue, value, wait_seconds=0)
    assert result["request"] == req
    assert (queue / req["request_id"] / "claim.json").is_file()
    assert not (queue / "worker.json").exists()
    assert json.loads(heartbeat.read_text())["state"] == "REQUEST_CLAIMED"
    assert account.queue_command(queue, "claim", value) == {"request": None}
    assert account.queue_command(queue, "complete", {
        "request_id": req["request_id"], "claim_token": result["claim_token"],
        "auth_mode": "chatgpt", "plan": {}})["accepted"]
    assert (queue / req["request_id"] / "response.json").is_file()


def test_read_only_preflight_is_rechecked_under_queue_lock(tmp_path, monkeypatch):
    req = request(tmp_path)
    original = account.fcntl.flock

    def cancelled_during_lock_acquisition(*args):
        original(*args)
        account.write_json(tmp_path / req["request_id"] / "cancelled.json", {})

    monkeypatch.setattr(account.fcntl, "flock", cancelled_during_lock_acquisition)
    assert account.queue_command(tmp_path, "claim", {"worker_id": "worker"}) == {"request": None}
    assert not (tmp_path / req["request_id"] / "claim.json").exists()


@pytest.mark.parametrize("blocked", ["BLOCKED", "COMPLETE_WITH_BLOCKERS"])
def test_legacy_offline_wait_reports_actual_blocked_state(tmp_path, blocked):
    queue, output = tmp_path / "queue", tmp_path / "offline"
    req = request(queue)
    account.write_json(output / "supervisor_status.json", {"state": "RUNNING", "batch_state": blocked,
        "collection_role": "offline_precollection_for_future_experiments"})
    result = account.wait_for_request(queue, {"worker_id": "worker"}, wait_seconds=45, experiment_output=output)
    assert result == {"request": None, "service_state": blocked}
    assert not (queue / req["request_id"] / "claim.json").exists()
