from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import pytest

from baseline.io import digest, read_json
from baseline.vls_provider import (REFERENCE, REWARD_MODEL, SOURCE_COMMIT, STAGE_MODEL,
    VLSGeminiStageRecognizer, official_engine_factories, parse_stage)


def test_official_reference_hashes_and_models():
    import yaml
    source = read_json(REFERENCE / "source.json")
    assert source["commit"] == SOURCE_COMMIT
    for name, sha in source["files"].items():
        assert digest(REFERENCE / name) == sha
    cfg = yaml.safe_load((REFERENCE / "configs/perception.yaml").read_text())
    assert cfg["vlm_agent"]["model"] == REWARD_MODEL
    assert cfg["gemini"]["model"] == STAGE_MODEL


def test_initialization_replaces_account_factories_before_main_and_restores_on_failure():
    def account_factory(*args, **kwargs):
        pytest.fail("account/task planner must never be initialized")
    engine = SimpleNamespace(create_gemini_stage_recognizer=account_factory,
                             create_gemini_grounder=account_factory, VLMAgent=account_factory)
    with pytest.raises(RuntimeError, match="simulated init failure"):
        with official_engine_factories(engine):
            assert engine.create_gemini_stage_recognizer is VLSGeminiStageRecognizer
            assert engine.VLMAgent is not account_factory
            with pytest.raises(RuntimeError, match="native segmentation"):
                engine.create_gemini_grounder({})
            raise RuntimeError("simulated init failure")
    assert engine.create_gemini_stage_recognizer is account_factory
    assert engine.create_gemini_grounder is account_factory
    assert engine.VLMAgent is account_factory


@pytest.mark.parametrize("output,stages,expected", [
    ("stage 2\nguidance: yes\nevidence: bowl is held", 3, (2, True)),
    ("stage 0\nguidance: no", 2, (0, False)),
    ("stage 7\nguidance: yes", 3, (3, True)),
])
def test_official_stage_semantics(output, stages, expected):
    assert parse_stage(output, stages) == expected


@pytest.mark.parametrize("output", ["", "stage 1", "guidance: yes", "service unavailable"])
def test_invalid_response_cannot_become_a_scored_stage_one_guess(output):
    with pytest.raises(ValueError):
        parse_stage(output, 3)


def recognizer(tmp_path, generate):
    # Stub only the network boundary; exercise real prompt/image/ledger code.
    instance = VLSGeminiStageRecognizer.__new__(VLSGeminiStageRecognizer)
    instance.model = STAGE_MODEL
    instance.client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    instance.prompt_template = (REFERENCE / "vlm_query/stage_template.txt").read_text()
    instance.ledger = tmp_path / "calls.jsonl"
    instance.calls_root = tmp_path / "stage_api_calls"
    instance.calls_root.mkdir()
    instance.max_calls, instance.calls = 1, 0
    return instance


def test_exact_google_model_and_upstream_image_order_are_audited(tmp_path):
    captured = {}
    def generate(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text="stage 2\nguidance: yes\nevidence: transport bowl",
                               response_id="test-response", model_version=STAGE_MODEL)
    instance = recognizer(tmp_path, generate)
    current, initial = np.zeros((4, 4, 3), dtype=np.uint8), np.ones((4, 4, 3))
    result = instance.identify_stage_and_guidance(current, "put bowl in drawer", "Stage 1: grasp\nStage 2: place",
                                                initial, {0: "gripper", 1: "bowl"}, 2, "gripper closed")
    assert result == (2, True)
    assert set(captured) == {"model", "contents"}  # No different thinking/generation policy.
    assert captured["model"] == STAGE_MODEL
    assert captured["contents"][1] == "**Initial Image (with keypoints):**"
    assert captured["contents"][3] == "**Current Image:**"
    assert np.asarray(captured["contents"][2]).min() == 255
    assert np.asarray(captured["contents"][4]).max() == 0
    row = json.loads(instance.ledger.read_text())
    assert row["status"] == "complete" and row["response_model"] == STAGE_MODEL
    assert set(row["inputs"]) == {"prompt.txt", "initial.png", "current.png"}
    with pytest.raises(RuntimeError, match="budget"):
        instance.identify_stage_and_guidance(current, "task", "stage")


def test_google_permanent_failure_propagates_without_fallback(tmp_path):
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        raise ValueError("simulated invalid request")
    instance = recognizer(tmp_path, generate)
    with pytest.raises(ValueError):
        instance.identify_stage_and_guidance(np.zeros((4, 4, 3), dtype=np.uint8), "task", "stage")
    assert len(calls) == 1
    assert json.loads(instance.ledger.read_text())["status"] == "failed"


def test_google_retries_ssl_in_place_without_spending_query_budget(tmp_path, monkeypatch):
    import httpx
    import random
    from baseline import vls_retry
    waits, calls = [], []
    monkeypatch.setattr(vls_retry.time, "sleep", waits.append)
    rng = random.getstate()
    def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) <= 70:
            raise httpx.ConnectError("[SSL: UNEXPECTED_EOF_WHILE_READING]")
        return SimpleNamespace(text="stage 2\nguidance: yes", response_id="recovered", model_version=STAGE_MODEL)
    instance = recognizer(tmp_path, generate)
    assert instance.identify_stage_and_guidance(np.zeros((4, 4, 3), dtype=np.uint8), "task", "stage") == (2, True)
    assert instance.calls == 1 and len(calls) == 71
    assert all(c["model"] == STAGE_MODEL and c["contents"] is calls[0]["contents"] for c in calls)
    assert waits[:6] == [2, 4, 8, 16, 32, 60] and max(waits) == 60
    assert random.getstate() == rng
    attempts = [json.loads(line) for line in (instance.calls_root / "call_001/attempts.jsonl").read_text().splitlines()]
    assert len(attempts) == 71 and all(a["status"] == "retry_wait" for a in attempts[:-1])
    result = json.loads(instance.ledger.read_text())
    assert result["status"] == "complete" and result["attempt"] == 71
    assert result["retry_policy"]["max_attempts"] is None
    assert "error_type" not in result and "next_retry_at" not in result
    assert read_json(tmp_path / "provider_status.json")["status"] == "complete"


def test_google_regenerates_unparseable_decision_in_same_query(tmp_path, monkeypatch):
    from baseline import vls_retry
    waits, calls = [], []
    monkeypatch.setattr(vls_retry.time, "sleep", waits.append)
    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text="stage 1" if len(calls) == 1 else "stage 2\nguidance: yes",
                               response_id="test", model_version=STAGE_MODEL)
    instance = recognizer(tmp_path, generate)
    assert instance.identify_stage_and_guidance(np.zeros((4, 4, 3), dtype=np.uint8), "task", "stages") == (2, True)
    assert waits == [2] and instance.calls == 1 and len(calls) == 2
    attempts = [json.loads(line) for line in (instance.calls_root / "call_001/attempts.jsonl").read_text().splitlines()]
    assert attempts[0]["retry_reason"] == "response_format"
    assert attempts[-1]["status"] == "complete"
