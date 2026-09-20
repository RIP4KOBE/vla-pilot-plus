"""Unit/regression tests must never send a live account Planner request."""
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def no_production_planner_queue(monkeypatch, tmp_path):
    from mode_gate.planner_account import CodexPlannerClient, load_planner_account_config
    request = CodexPlannerClient.request
    production = Path(load_planner_account_config()["queue_root"]).resolve()
    def checked(self, **kwargs):
        if self.queue_root.resolve() == production:
            pytest.fail("test must inject a Planner client; live production queue is forbidden")
        return request(self, **kwargs)
    monkeypatch.setattr(CodexPlannerClient, "request", checked)
