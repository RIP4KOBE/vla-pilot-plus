"""Transport recovery must not mutate prompts or resample semantic failures."""
import importlib.util
import json
from pathlib import Path

import httpx


def module():
    path = Path(__file__).resolve().parents[1] / "scripts/c0_poe_resilient_worker.py"
    spec = importlib.util.spec_from_file_location("c0_transport_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def response(text):
    return {"id": "test", "object": "chat.completion", "created": 1,
            "model": "gemini-3-flash", "choices": [{"index": 0, "finish_reason": "stop",
              "message": {"role": "assistant", "content": text}}]}


def test_connect_timeout_retries_identical_payload():
    requests = []
    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ConnectTimeout("test connect timeout", request=request)
        return httpx.Response(200, json=response("stage 1\nguidance: yes"))
    mod = module()
    with mod.make_client(api_key="test", base_url="https://example.invalid/v1",
                         http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        result = client.chat.completions.create(model="gemini-3-flash", messages=[{"role": "user", "content": "fixed prompt"}], max_tokens=256, temperature=0.0)
    assert result.choices[0].message.content == "stage 1\nguidance: yes"
    assert len(requests) == 2
    expected = {"model": "gemini-3-flash", "messages": [{"role": "user", "content": "fixed prompt"}], "max_tokens": 256, "temperature": 0.0}
    assert all(json.loads(r.content) == expected for r in requests)
    assert requests[0].extensions["timeout"]["connect"] == 30.0


def test_complete_unparsable_reply_is_not_retried():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response("stage 0\nguidance:"))
    mod = module()
    with mod.make_client(api_key="test", base_url="https://example.invalid/v1",
                         http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        result = client.chat.completions.create(model="gemini-3-flash", messages=[{"role": "user", "content": "fixed prompt"}], max_tokens=256, temperature=0.0)
    assert result.choices[0].message.content == "stage 0\nguidance:"
    assert len(requests) == 1
