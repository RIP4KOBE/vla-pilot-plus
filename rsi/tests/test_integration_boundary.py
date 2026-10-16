"""Keep the accepted runtime separate from the experimental PR runtime."""
import hashlib
import json
from pathlib import Path

from mode_gate.planner_account import load_planner_account_config

ROOT = Path(__file__).resolve().parents[2]


def test_accepted_main_runtime_is_preserved():
    identity = json.loads((ROOT / "rsi/integration.json").read_text())
    for path, expected in identity["protected_main_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


def test_planner_profile_can_be_local_without_rewriting_historical_config(tmp_path, monkeypatch):
    original = (ROOT / "configs/planner_account.json").read_bytes()
    profile = json.loads(original)
    profile.update(planner_thread_id="test-local-worker", queue_root=str(tmp_path / "queue"))
    local = tmp_path / "planner.json"
    local.write_text(json.dumps(profile))
    monkeypatch.setenv("VLA_RSI_PLANNER_CONFIG", str(local))
    assert load_planner_account_config()["planner_thread_id"] == "test-local-worker"
    assert (ROOT / "configs/planner_account.json").read_bytes() == original


def test_cold_and_warm_evaluators_use_rsi_runtime_and_config():
    # Both execution modes must select the same experimental control path.
    source = (ROOT / "mode_gate/policy_evaluator.py").read_text()
    assert '"rsi/main.py"' in source
    assert "from rsi.main import Main" in source
    assert 'self.repo_root / "rsi/configs"' in source
