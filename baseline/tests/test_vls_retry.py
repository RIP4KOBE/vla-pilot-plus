import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from baseline import vls_retry
from baseline.io import read_json
from baseline.vls_provider import REWARD_MODEL, create_reward_agent


@pytest.mark.parametrize("code,retry", [(400, False), (401, False), (403, False), (404, False),
    (408, True), (409, True), (429, True), (500, True), (502, True), (503, True), (504, True)])
def test_google_sdk_status_classification(code, retry):
    from google.genai.errors import APIError
    assert vls_retry.transient_error(APIError(code, {"error": {"code": code, "message": "test"}})) is retry


def test_sdk_transport_exceptions_and_request_errors():
    from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError
    request = httpx.Request("POST", "https://example.invalid/test")
    for exc in (httpx.ReadError("test"), httpx.ReadTimeout("test"), APIConnectionError(request=request),
                APITimeoutError(request=request), TimeoutError(), ConnectionResetError(),
                RateLimitError("test", response=httpx.Response(429, request=request), body=None)):
        assert vls_retry.transient_error(exc)
    assert not vls_retry.transient_error(AuthenticationError("test", response=httpx.Response(401, request=request), body=None))
    assert not vls_retry.transient_error(ValueError("bad stage output"))
    assert not vls_retry.transient_error(OSError("disk problem"))


def reward_agent(tmp_path, monkeypatch, create):
    def fake_agent(config, **kwargs):
        return SimpleNamespace(config=config, generate_guidance=lambda *a, **kw: None, prompt_template="official", client=SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setitem(sys.modules, "baseline.references.vls.vlm_query.vlm_agent", SimpleNamespace(VLMAgent=fake_agent))
    return create_reward_agent({"model": REWARD_MODEL, "timeout_ms": 180000}, base_dir=tmp_path)


def chunk(text, finish=None):
    return SimpleNamespace(id="test", model=REWARD_MODEL, choices=[SimpleNamespace(
        delta=SimpleNamespace(content=text), finish_reason=finish)])


class Stream:
    def __init__(self, chunks, error=None):
        self.chunks, self.error, self.closed = chunks, error, False

    def __iter__(self):
        yield from self.chunks
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


@pytest.mark.parametrize("error", [httpx.ReadError("simulated mid-stream disconnect"), None])
def test_reward_stream_discards_partial_attempt_before_retry(tmp_path, monkeypatch, error):
    waits, calls = [], []
    monkeypatch.setattr(vls_retry.time, "sleep", waits.append)
    failed = Stream([chunk("INCOMPLETE OLD FUNCTION")], error)
    recovered = Stream([chunk("def new_reward():\n"), chunk("    return 1\n", "stop")])
    def create(**kwargs):
        calls.append(kwargs)
        return failed if len(calls) == 1 else recovered
    agent = reward_agent(tmp_path, monkeypatch, create)
    request = {"model": REWARD_MODEL, "messages": [{"role": "user", "content": "same image and instruction"}],
               "temperature": 1, "max_completion_tokens": 2000, "stream": True}
    result = agent.client.chat.completions.create(**request)
    assert "".join(c.choices[0].delta.content for c in result) == "def new_reward():\n    return 1\n"
    assert failed.closed and recovered.closed and calls == [request, request] and waits == [2]
    row = read_json(tmp_path / "reward_api_calls/call_001/status.json")
    assert row["status"] == "complete" and row["attempt"] == 2 and row["finish_reason"] == "stop"
    assert len((tmp_path / "reward_provider_calls.jsonl").read_text().splitlines()) == 1


def test_reward_retries_request_timeout_and_preserves_nonstream_response(tmp_path, monkeypatch):
    waits, calls = [], []
    monkeypatch.setattr(vls_retry.time, "sleep", waits.append)
    response = SimpleNamespace(id="test", model=REWARD_MODEL)
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise httpx.ConnectTimeout("test")
        return response
    agent = reward_agent(tmp_path, monkeypatch, create)
    assert agent.client.chat.completions.create(model=REWARD_MODEL) is response
    assert waits == [2, 4] and len(calls) == 3


def test_token_limit_is_not_misclassified_as_network_eof(tmp_path, monkeypatch):
    def unexpected_wait(delay):
        pytest.fail("non-network model output error must not be retried")
    monkeypatch.setattr(vls_retry.time, "sleep", unexpected_wait)
    response = Stream([chunk("truncated", "length")])
    agent = reward_agent(tmp_path, monkeypatch, lambda **kw: response)
    with pytest.raises(RuntimeError, match="finish normally"):
        agent.client.chat.completions.create(model=REWARD_MODEL, stream=True)
    assert response.closed
    assert read_json(tmp_path / "reward_api_calls/call_001/status.json")["status"] == "failed"


def test_operator_interrupt_can_stop_retry_wait(tmp_path, monkeypatch):
    def interrupt(delay):
        raise KeyboardInterrupt()
    monkeypatch.setattr(vls_retry.time, "sleep", interrupt)
    def request(record):
        raise httpx.ConnectError("test")
    with pytest.raises(KeyboardInterrupt):
        vls_retry.retry_provider_call(request, {"model": REWARD_MODEL},
            attempts_path=tmp_path / "attempts.jsonl", status_path=tmp_path / "status.json",
            activity_path=tmp_path / "provider_status.json")
    assert len((tmp_path / "attempts.jsonl").read_text().splitlines()) == 1
