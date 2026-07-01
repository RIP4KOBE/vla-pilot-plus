import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlm_query.vlm_agent import VLMAgent


class _FakeCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("peer closed connection without sending complete message body (incomplete chunked read)")
        return [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="def stage1_guidance_1():\n    return 0\n")
                    )
                ]
            )
        ]


def test_vlm_guidance_stream_retries_transient_chunked_read(monkeypatch):
    completions = _FakeCompletions()
    agent = VLMAgent.__new__(VLMAgent)
    agent.config = {
        "model": "gpt-4o",
        "temperature": 1.0,
        "max_completion_tokens": 2000,
        "api_max_retries": 2,
        "api_retry_backoff_seconds": 0.01,
    }
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    sleeps = []
    monkeypatch.setattr("vlm_query.vlm_agent.time.sleep", lambda seconds: sleeps.append(seconds))

    output = agent._query_guidance_with_retry([{"role": "user", "content": "prompt"}])

    assert "stage1_guidance_1" in output
    assert completions.calls == 2
    assert sleeps == [0.01]


class _AlwaysTimeoutCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        raise APITimeoutError("handshake operation timed out")


class APITimeoutError(Exception):
    pass


def test_vlm_guidance_retry_backoff_is_capped(monkeypatch):
    completions = _AlwaysTimeoutCompletions()
    agent = VLMAgent.__new__(VLMAgent)
    agent.config = {
        "model": "gpt-4o",
        "temperature": 1.0,
        "max_completion_tokens": 2000,
        "api_max_retries": 4,
        "api_retry_backoff_seconds": 5.0,
        "api_retry_max_backoff_seconds": 8.0,
    }
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    sleeps = []
    monkeypatch.setattr("vlm_query.vlm_agent.time.sleep", lambda seconds: sleeps.append(seconds))

    try:
        agent._query_guidance_with_retry([{"role": "user", "content": "prompt"}])
    except APITimeoutError:
        pass
    else:
        raise AssertionError("expected retry exhaustion")

    assert completions.calls == 4
    assert sleeps == [5.0, 8.0, 8.0]
