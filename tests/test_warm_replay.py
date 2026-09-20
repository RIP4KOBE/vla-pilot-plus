from types import SimpleNamespace

import pytest

from mode_gate import offline_replay
from mode_gate.offline_replay import HgpuReplayApplication, WarmReplayApplicationPool
from mode_gate.semantic_planner import GeminiSemanticPlanner


def test_gemini_cap_can_only_increase_on_the_same_ledger(tmp_path):
    ledger = tmp_path / "provider.jsonl"
    planner = GeminiSemanticPlanner(
        client=SimpleNamespace(),
        max_provider_calls=3,
        call_ledger_path=ledger,
    )

    planner.increase_provider_call_cap(
        max_provider_calls=7,
        call_ledger_path=ledger,
    )

    assert planner._provider_budget.max_calls == 7
    assert planner._provider_budget.ledger_path == ledger.resolve()
    with pytest.raises(ValueError, match="cannot lower"):
        planner.increase_provider_call_cap(
            max_provider_calls=6,
            call_ledger_path=ledger,
        )
    with pytest.raises(ValueError, match="cannot switch"):
        planner.increase_provider_call_cap(
            max_provider_calls=8,
            call_ledger_path=tmp_path / "other.jsonl",
        )


def test_warm_pool_reuses_only_the_same_execution_identity(tmp_path, monkeypatch):
    created = []

    class FakeApplication:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.reconfigured = []
            self.closed = False
            created.append(self)

        def reconfigure_for_plan(self, **kwargs):
            self.reconfigured.append(kwargs)

        def close(self):
            self.closed = True

    monkeypatch.setattr(offline_replay, "HgpuReplayApplication", FakeApplication)
    pool = WarmReplayApplicationPool()
    common = {
        "repo_root": tmp_path / "repo",
        "runtime_suite": "libero_10_env",
        "task_ids": (5,),
        "checkpoint": tmp_path / "policy_000",
        "policy_id": "policy_000",
        "device": "cuda:6",
        "snapshot_root": tmp_path / "snapshots",
        "gemini_call_ledger_path": tmp_path / "provider.jsonl",
    }
    first = pool.acquire(
        **common,
        artifact_root=tmp_path / "artifact-a",
        gemini_max_provider_calls=1000,
    )
    second = pool.acquire(
        **common,
        artifact_root=tmp_path / "artifact-b",
        gemini_max_provider_calls=5000,
    )

    assert first is second
    assert len(created) == 1
    assert created[0].reconfigured[0]["gemini_max_provider_calls"] == 5000
    with pytest.raises(ValueError, match="incompatible"):
        pool.acquire(
            **{**common, "device": "cuda:5"},
            artifact_root=tmp_path / "artifact-c",
            gemini_max_provider_calls=5000,
        )
    pool.close()
    assert created[0].closed
    assert not pool.is_warm


def test_warm_reconfigure_updates_every_gemini_caller_without_model_reload(tmp_path):
    class Budgeted:
        def __init__(self):
            self.calls = []

        def reconfigure_provider_call_budget(self, **kwargs):
            self.calls.append(kwargs)

    planner = Budgeted()
    grounder = Budgeted()
    stage_recognizer = Budgeted()
    application = HgpuReplayApplication.__new__(HgpuReplayApplication)
    application.main = SimpleNamespace(
        mode_aware_runtime=SimpleNamespace(planner=planner),
        gemini_grounder=grounder,
        gemini_stage_recognizer=stage_recognizer,
    )
    application.reconfigure_for_plan(
        artifact_root=tmp_path / "artifact",
        gemini_max_provider_calls=5000,
        gemini_call_ledger_path=tmp_path / "counterfactual.jsonl",
    )

    assert len(planner.calls) == len(grounder.calls) == len(stage_recognizer.calls) == 1
    assert planner.calls[0]["max_provider_calls"] == 5000
    assert grounder.calls[0]["call_ledger_path"].endswith("counterfactual.jsonl")
