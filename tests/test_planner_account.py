import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import pytest

from mode_gate.codex_account import queue_command
from mode_gate.planner_account import CodexPlannerClient, validate_planner_response
from mode_gate.semantic_planner import SemanticPlanner, _ProviderCallBudget
from mode_gate.tickets import TicketCollectionPlanner
from core.gemini_grounder import GeminiStageRecognizer


def config(tmp_path):
    return {"model": "gpt-6-astra", "reasoning_effort": "ultra", "auth_mode": "chatgpt",
            "planner_thread_id": "top-task", "queue_root": str(tmp_path / "queue"),
            "timeout_seconds": 5}


def test_native_queue_image_json_identity_and_no_provider_fallback(tmp_path):
    client = CodexPlannerClient(config(tmp_path))
    png = BytesIO()
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(png, format="PNG")
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"stage_num": {"type": "integer", "minimum": 1}},
              "required": ["stage_num"]}
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(client.request, prompt="stage evidence", schema=schema,
                             images=[(png.getvalue(), "image/png")])
        deadline = time.monotonic() + 3
        while not list(client.queue_root.glob("*/request.json")):
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert queue_command(client.queue_root, "claim", {
            "worker_id": "wrong", "planner_thread_id": "demo-task"})["request"] is None
        claim = queue_command(client.queue_root, "claim", {
            "worker_id": "top-worker", "planner_thread_id": "top-task"})
        request = claim["request"]
        response = {key: request[key] for key in ("request_id", "request_sha256", "planner_thread_id", "model", "reasoning_effort", "auth_mode")}
        response.update(claim_token=claim["claim_token"], result={"stage_num": 1})
        with pytest.raises(ValueError, match="visual_review"):
            queue_command(client.queue_root, "complete", response)
        visuals = request["visual_observations"]
        response["visual_review"] = {"manifest_sha256": visuals["manifest_sha256"],
            "viewed_image_ids": [v["image_id"] for v in visuals["images"]], "assessment_zh": "测试观察"}
        for key in ("request_sha256", "planner_thread_id", "model", "reasoning_effort", "auth_mode"):
            with pytest.raises(ValueError):
                queue_command(client.queue_root, "complete", {**response, key: "wrong"})
        with pytest.raises(Exception):
            queue_command(client.queue_root, "complete", {**response, "result": {"stage_num": 0}})
        assert not (client.queue_root / request["request_id"] / "response.json").exists()
        assert queue_command(client.queue_root, "complete", response)["accepted"]
        result = future.result(timeout=2)
    assert json.loads(result.text) == {"stage_num": 1}
    assert result.planner_metadata["auth_mode"] == "chatgpt"
    assert result.planner_metadata["model"] == "gpt-6-astra"
    assert result.planner_metadata["reasoning_effort"] == "ultra"


def test_paused_request_is_cancelled_without_fallback(tmp_path):
    output = tmp_path / "experiment"
    output.mkdir()
    (output / "park.request").write_text("migration")
    client = CodexPlannerClient({**config(tmp_path), "experiment_output": str(output)})
    with pytest.raises(InterruptedError):
        client.request(prompt="test", schema={"type": "object"})
    assert len(list(client.queue_root.glob("*/cancelled.json"))) == 1


def test_production_clients_do_not_need_or_create_google_api_client(monkeypatch):
    for key in ("GOOGLE_API_KEY", "MODE_GATE_GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    for planner in (SemanticPlanner(), TicketCollectionPlanner(), GeminiStageRecognizer({})):
        assert isinstance(planner.client, CodexPlannerClient)
        assert planner.model == "gpt-6-astra"
        assert planner.thinking_level == "ultra"
    with pytest.raises(ValueError):
        SemanticPlanner(model="gemini-robotics-er-2-preview")


def test_historical_calls_and_account_calls_share_unchanged_cost_cap(tmp_path):
    path = tmp_path / "calls.jsonl"
    budget = _ProviderCallBudget(max_calls=2, ledger_path=path)
    args = dict(prompt_version="test", cache_key="k", attempt=1, purpose="test")
    budget.reserve(model="gemini-robotics-er-2-preview", **args)
    old = path.read_bytes()
    budget.reserve(model="gpt-6-astra", **args)
    assert path.read_bytes().startswith(old)
    events = [json.loads(v) for v in path.read_text().splitlines()]
    assert events[1]["event"] == "ACCOUNT_PLANNER_CALL_RESERVED"
    assert events[1]["auth_mode"] == "chatgpt"
    with pytest.raises(RuntimeError):
        _ProviderCallBudget(max_calls=2, ledger_path=path).reserve(model="gpt-6-astra", **args)


def test_provider_preflight_binds_account_task_and_rejects_old_gemini_evidence(monkeypatch, tmp_path):
    from mode_gate import preflight
    from mode_gate.planner_account import load_planner_account_config

    profile = load_planner_account_config()
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/planner_account.json").write_text(json.dumps(profile))
    monkeypatch.setattr(preflight, "gemini_canary_source_fingerprint", lambda root: "current")
    value = {"schema_version": "hgpu1-account-planner-canary-v1",
             "source_fingerprint": "current", "visual_input_kind": "synthetic", "passed": True,
             **{key: profile[key] for key in ("model", "reasoning_effort", "auth_mode", "planner_thread_id")},
             "gemini_api_enabled": False, "ticket_model": profile["model"],
             "interaction_exercised": True, "grounding_exercised": True,
             "stage_exercised": True, "ticket_exercised": True}
    path = tmp_path / "result.json"
    path.write_text(json.dumps(value))
    assert preflight._gemini_canary(path, tmp_path)["model"] == "gpt-6-astra"
    for key, wrong in (("schema_version", "hgpu1-gemini-canary-v3"),
                       ("planner_thread_id", "wrong-task"), ("auth_mode", "api_key"),
                       ("reasoning_effort", "medium"), ("gemini_api_enabled", True)):
        path.write_text(json.dumps({**value, key: wrong}))
        with pytest.raises(RuntimeError, match="has not passed"):
            preflight._gemini_canary(path, tmp_path)
