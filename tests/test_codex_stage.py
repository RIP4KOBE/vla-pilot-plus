"""CPU-only boundary tests for managed-login Stage calls; no live API/GPU."""
import json
import hashlib
import io
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.online.codex as module
from core.online.codex import CodexStageRecognizer
from core.online.policy import discover_disabled_skill_paths, policy_sha256, public_invocation_policy
from core.gemini_grounder import GeminiStageRecognizer, create_gemini_stage_recognizer


ANSWER = "stage 2\nguidance: no\nevidence: object already grasped"
USAGE = {"input_tokens": 108, "cached_input_tokens": 20, "output_tokens": 12,
         "reasoning_output_tokens": 3}


def events(answer=ANSWER, usage=None):
    return [
        {"type": "thread.started", "thread_id": "test-thread"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": answer}},
        {"type": "turn.completed", "usage": USAGE if usage is None else usage},
    ]


def make(monkeypatch, tmp_path, event_list=None, returncode=0, timeout=False, raw=None,
         output_format="legacy_text", event_policy="strict_v1", timeout_seconds=90, stderr=b"",
         model="gpt-6-astra"):
    calls = []
    cli = tmp_path / "codex"
    cli.touch()
    template = tmp_path / "stage.txt"
    template.write_text("trigger={trigger_reason}\ninstruction={instruction}\nstages={stage_descriptions}\nkeypoints={keypoint_info}")
    event_list = events() if event_list is None else event_list

    class Process:
        pid = 12345

        def __init__(self, command, **kwargs):
            self.returncode = returncode
            self.command = command
            self.kwargs = kwargs
            paths = [command[i + 1] for i, part in enumerate(command) if part == "--image"]
            self.images = [np.array(Image.open(path)) for path in paths]
            self.schema = (json.loads(Path(command[command.index('--output-schema') + 1]).read_text())
                           if '--output-schema' in command else None)
            calls.append(self)
            data = raw if raw is not None else "\n".join(json.dumps(event) for event in event_list).encode()
            kwargs["stdout"].write(data)
            kwargs["stdout"].flush()
            kwargs["stderr"].write(stderr)
            kwargs["stderr"].flush()

        def communicate(self, input=None, timeout=None):
            self.prompt = input
            self.timeout = timeout
            if timeout is not None and make_timeout[0]:
                raise subprocess.TimeoutExpired("codex", timeout)
            return None, None

    make_timeout = [timeout]
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    recognizer = CodexStageRecognizer({
        "backend": "codex_cli", "model": model, "cli_path": str(cli),
        "stage_template_path": str(template), "disabled_skill_paths": ["/active/one"],
        "timeout_seconds": timeout_seconds,
        "output_format": output_format,
        "event_policy": event_policy,
    })
    return recognizer, calls


def identify(recognizer, initial=True):
    return recognizer.identify_stage_and_guidance(
        current_rgb=np.full((3, 4, 3), 80, dtype=np.uint8),
        init_img_with_keypoints=np.full((4, 5, 3), 12, dtype=np.uint8) if initial else None,
        instruction="put target in basket", stage_descriptions="Stage 1: pick\nStage 2: place",
        keypoint_id_to_object={0: "target", 1: "basket"}, num_stages=2,
        trigger_reason="gripper closed",
    )


def test_success_preserves_prompt_pixels_order_and_reports_observed_cost(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path)
    assert identify(recognizer) == (2, False)
    call = calls[0]
    expected = recognizer.prompt_template.format(
        trigger_reason="gripper closed", instruction="put target in basket",
        stage_descriptions="Stage 1: pick\nStage 2: place",
        keypoint_info="  Keypoint 0: target\n  Keypoint 1: basket",
    )
    assert call.prompt == expected + "\n\n**Initial Image (with keypoints):**\n\n**Current Image:**"
    assert call.images[0].shape == (4, 5, 3) and np.all(call.images[0] == 12)
    assert call.images[1].shape == (3, 4, 3) and np.all(call.images[1] == 80)
    assert not Path(call.kwargs["cwd"]).exists()  # temp files cleaned
    assert call.kwargs["start_new_session"] is False
    assert call.timeout == 90
    assert "shell" not in call.kwargs
    result = recognizer.last_result
    assert result["raw_response"] == ANSWER
    assert result["api_request_attempts"] is None
    assert result["api_sdk_retry_attempts"] is None
    assert result["api_request_counter_available"] is False
    assert result["codex_logical_call_attempts"] == 1
    assert result["codex_completed_turns"] == 1
    assert result["codex_usage_complete_calls"] == 1
    assert result["codex_failed_calls"] == 0
    assert result["codex_input_tokens"] == 108
    assert result["codex_cached_input_tokens"] == 20
    assert result["codex_reasoning_output_tokens"] == 3
    assert result["codex_call_latency_s"] >= 0


def test_online_capture_keeps_exact_prompt_and_png_order(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path)
    recognizer.capture_dir = tmp_path / "captured"
    assert identify(recognizer) == (2, False)
    folder = recognizer.capture_dir / "request_0000"
    parts = json.loads((folder / "parts.json").read_text())
    metadata = json.loads((folder / "metadata.json").read_text())
    assert (folder / "codex_prompt.txt").read_text() == calls[0].prompt
    assert [part["type"] for part in parts] == ["text", "text", "image_url", "text", "image_url"]
    assert np.array_equal(np.array(Image.open(folder / "image_01.png")), calls[0].images[0])
    assert np.array_equal(np.array(Image.open(folder / "image_02.png")), calls[0].images[1])
    assert metadata["prompt_sha256"] == recognizer.last_result["transport"]["request_fingerprint"]["prompt_sha256"]
    assert metadata["image_png_sha256"] == recognizer.last_result["transport"]["request_fingerprint"]["image_png_sha256"]


def test_incomplete_transport_reply_retries_then_keeps_complete_answer(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path, event_policy="completed_transport_cycles_v6")
    recognizer.transport_retry_count = 2
    recognizer.transport_retry_backoff_seconds = 0
    original = recognizer._request_stage_response_once
    seen = []

    def first_failure_then_success(content):
        seen.append(True)
        if len(seen) == 1:
            recognizer.api_request_counter.values["logical_call_attempts"] += 1
            recognizer._call_transport = {"completed_turns": 0, "event_types": ["thread.started", "turn.failed"]}
            recognizer._call_raw_response = None
            raise module.CodexStageError("codex_expected_one_completed_turn")
        return original(content)

    monkeypatch.setattr(recognizer, "_request_stage_response_once", first_failure_then_success)
    assert identify(recognizer) == (2, False)
    assert len(seen) == 2 and len(calls) == 1
    result = recognizer.last_result
    assert result["codex_logical_call_attempts"] == 2
    assert result["transport"]["physical_call_attempts"] == 2
    assert [item["error"] for item in result["transport"]["failed_transport_attempts"]] == [
        "codex_expected_one_completed_turn"]


def test_complete_but_invalid_answer_is_not_retried(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path, event_list=events(answer="not JSON"),
                             output_format="json_schema_v1",
                             event_policy="completed_transport_cycles_v6")
    recognizer.transport_retry_count = 4
    assert identify(recognizer) == (1, True)
    assert len(calls) == 1
    assert recognizer.last_result["error"] == "codex_invalid_structured_response"
    assert recognizer.last_result["transport"]["physical_call_attempts"] == 1


@pytest.mark.parametrize('recovers', [True, False])
def test_repeated_rate_limit_is_bounded_and_keeps_same_request(monkeypatch, tmp_path, recovers):
    recognizer, calls = make(monkeypatch, tmp_path, event_policy="completed_transport_cycles_v6")
    recognizer.transport_retry_count = 8
    recognizer.transport_retry_backoff_seconds = 30
    original = recognizer._request_stage_response_once
    requests, waits = [], []

    def rate_limit_then_maybe_recover(content):
        requests.append(content)
        if recovers and len(requests) == 9:
            return original(content)
        recognizer.api_request_counter.values["logical_call_attempts"] += 1
        recognizer._call_transport = {"completed_turns": 0,
            "error_diagnostics": [{"http_status_codes": [429], "signals": ["rate_limited"]}]}
        recognizer._call_raw_response = None
        raise module.CodexStageError("codex_expected_one_completed_turn")

    monkeypatch.setattr(recognizer, "_request_stage_response_once", rate_limit_then_maybe_recover)
    monkeypatch.setattr(module.time, "sleep", waits.append)
    assert identify(recognizer) == ((2, False) if recovers else (1, True))
    assert len(requests) == 9 and all(r == requests[0] for r in requests)
    assert waits == [30.] * 8
    assert len(calls) == int(recovers)
    result = recognizer.last_result
    assert result["codex_logical_call_attempts"] == 9
    assert result["transport"]["physical_call_attempts"] == 9
    assert len(result["transport"]["failed_transport_attempts"]) == (8 if recovers else 9)
    if not recovers:
        assert result['error'] == 'codex_expected_one_completed_turn'


def test_authentication_failure_is_not_retried(monkeypatch, tmp_path):
    recognizer, _ = make(monkeypatch, tmp_path, event_policy="completed_transport_cycles_v6")
    recognizer.transport_retry_count = 12
    seen = []

    def failed_auth(content):
        seen.append(True)
        recognizer._call_transport = {"completed_turns": 0,
            "error_diagnostics": [{"signals": ["authentication_failed"]}]}
        recognizer._call_raw_response = None
        raise module.CodexStageError("codex_expected_one_completed_turn")

    monkeypatch.setattr(recognizer, "_request_stage_response_once", failed_auth)
    assert identify(recognizer) == (1, True)
    assert len(seen) == 1
    assert recognizer.last_result["transport"]["physical_call_attempts"] == 1


def test_child_environment_uses_existing_login_without_mutating_parent(monkeypatch, tmp_path):
    for name in module._REMOVED_ENVIRONMENT:
        monkeypatch.setenv(name, "test-provider-value")
    monkeypatch.setenv("HOME", "/existing-home")
    monkeypatch.setenv("CODEX_HOME", "/existing-codex")
    recognizer, calls = make(monkeypatch, tmp_path)
    identify(recognizer)
    env = calls[0].kwargs["env"]
    assert all(name not in env for name in module._REMOVED_ENVIRONMENT)
    assert env["HOME"] == "/existing-home"
    assert env["CODEX_HOME"] == "/existing-codex"
    assert module.os.environ["OPENAI_API_KEY"] == "test-provider-value"
    assert "test-provider-value" not in json.dumps(calls[0].command)
    assert "auth.json" not in json.dumps(recognizer.public_policy)


def test_structured_output_validates_schema_preserves_raw_json_and_usage(monkeypatch, tmp_path):
    answer = json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'object grasped\nready to move'})
    recognizer, calls = make(monkeypatch, tmp_path, event_list=events(answer=answer),
                             output_format='json_schema_v1')
    assert identify(recognizer) == (2, False)
    assert calls[0].schema == recognizer.public_policy['output_schema']
    assert calls[0].schema['additionalProperties'] is False
    assert set(calls[0].schema['required']) == {'stage', 'guidance', 'evidence'}
    assert recognizer.last_result['raw_response'] == answer
    assert recognizer.last_result['evidence'] == 'object grasped ready to move'
    assert recognizer.last_result['codex_input_tokens'] == USAGE['input_tokens']
    assert recognizer.last_result['codex_failed_calls'] == 0
    assert recognizer.last_result['transport']['output_format'] == 'json_schema_v1'
    assert 'supersedes the three-line' in recognizer.public_policy['config_overrides']['developer_instructions']


@pytest.mark.parametrize('answer', [
    'Need soup lying outside Current outside basket left not visibly held. stage1 final N',
    ANSWER, 'null', '[]', '{}',
    '{"stage":1,"stage":2,"guidance":"no","evidence":"held"}',
    *[json.dumps(value) for value in [
        {'stage': 1, 'evidence': 'near'},
        {'stage': True, 'guidance': 'yes', 'evidence': 'near'},
        {'stage': 1.0, 'guidance': 'yes', 'evidence': 'near'},
        {'stage': -1, 'guidance': 'yes', 'evidence': 'near'},
        {'stage': 1, 'guidance': True, 'evidence': 'near'},
        {'stage': 1, 'guidance': 'maybe', 'evidence': 'near'},
        {'stage': 1, 'guidance': 'yes', 'evidence': ''},
        {'stage': 1, 'guidance': 'yes', 'evidence': 3},
        {'stage': 1, 'guidance': 'yes', 'evidence': 'near', 'extra': 'unapproved'},
    ]],
])
def test_structured_malformed_response_fails_without_retry_and_keeps_raw_usage(monkeypatch, tmp_path, answer):
    recognizer, calls = make(monkeypatch, tmp_path, event_list=events(answer=answer),
                             output_format='json_schema_v1')
    assert identify(recognizer) == (1, True)
    assert len(calls) == 1
    assert recognizer.last_result['error'] == 'codex_invalid_structured_response'
    assert recognizer.last_result['raw_response'] == answer
    assert recognizer.last_result['codex_failed_calls'] == 1
    assert recognizer.last_result['codex_usage_complete_calls'] == 1


def test_output_format_is_explicit_frozen_choice_and_legacy_stays_unconstrained(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path)
    identify(recognizer)
    assert '--output-schema' not in calls[0].command
    assert 'output_schema' not in recognizer.public_policy
    kwargs = dict(model='gpt-6-astra', reasoning_effort='low', timeout_seconds=90,
                  cli_path=recognizer.cli_path, disabled_skill_paths=['/active/one'])
    assert policy_sha256(public_invocation_policy(**kwargs, output_format='json_schema_v1')) != policy_sha256(recognizer.public_policy)
    with pytest.raises(ValueError, match='output format'):
        public_invocation_policy(**kwargs, output_format='json')


@pytest.mark.parametrize('notice', ['Reconnecting... 1/5', 'Reconnecting... 2/5\nstream disconnected: private detail',
                                  'Reconnecting... 1/5 (stream disconnected: private detail)'])
def test_explicit_reconnect_can_complete_once_with_cost_and_redacted_notice(monkeypatch, tmp_path, notice):
    answer = json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'})
    stream = events(answer=answer)
    stream.insert(2, {'type': 'error', 'message': notice})
    recognizer, calls = make(monkeypatch, tmp_path, event_list=stream,
                             output_format='json_schema_v1', event_policy='completed_reconnect_v1')
    assert identify(recognizer) == (2, False)
    result = recognizer.last_result
    assert len(calls) == result['codex_logical_call_attempts'] == 1
    assert result['codex_usage_complete_calls'] == 1
    assert result['codex_failed_calls'] == 0
    assert result['transport']['process_returncode'] == 0
    assert result['transport']['process_timed_out'] is False
    assert result['transport']['error_events'][0]['classification'] == 'numbered_reconnecting_notice'
    assert len(result['transport']['error_events'][0]['message_sha256']) == 64
    assert 'private detail' not in json.dumps(result)


@pytest.mark.parametrize('change', ['strict', 'unknown', 'missing_message', 'bad_count', 'before_start',
                                   'after_completion', 'after_message', 'nonzero', 'turn_failed',
                                   'missing_completion', 'invalid_json', 'timeout'])
def test_reconnect_does_not_bypass_other_failure_gates(monkeypatch, tmp_path, change):
    answer = json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'})
    stream = events(answer=answer if change != 'invalid_json' else ANSWER)
    notice = {'type': 'error', 'message': 'Reconnecting... 1/5'}
    if change == 'unknown': notice['message'] = 'unclassified private server error'
    if change == 'missing_message': notice.pop('message')
    if change == 'bad_count': notice['message'] = 'Reconnecting... 6/5'
    index = {'before_start': 0, 'after_completion': 4, 'after_message': 3}.get(change, 2)
    stream.insert(index, notice)
    if change == 'turn_failed': stream.insert(3, {'type': 'turn.failed', 'error': {'message': 'private'}})
    if change == 'missing_completion': stream.pop()
    if change == 'timeout': monkeypatch.setattr(module, '_stop_owned_process', lambda process: None)
    recognizer, calls = make(monkeypatch, tmp_path, event_list=stream,
        returncode=1 if change == 'nonzero' else 0, timeout=change == 'timeout',
        output_format='json_schema_v1',
        event_policy='strict_v1' if change == 'strict' else 'completed_reconnect_v1')
    assert identify(recognizer) == (1, True)
    assert len(calls) == 1
    assert recognizer.last_result['codex_failed_calls'] == 1
    assert 'private' not in json.dumps(recognizer.last_result)
    assert recognizer.last_result['transport']['process_returncode'] == (1 if change == 'nonzero' else 0)


def test_reconnect_policy_changes_only_local_acceptance_contract(monkeypatch, tmp_path):
    recognizer, _ = make(monkeypatch, tmp_path, output_format='json_schema_v1')
    old = recognizer.public_policy
    kwargs = dict(model='gpt-6-astra', reasoning_effort='low', timeout_seconds=90,
                  cli_path=recognizer.cli_path, disabled_skill_paths=['/active/one'], output_format='json_schema_v1')
    new = public_invocation_policy(**kwargs, event_policy='completed_reconnect_v1')
    assert policy_sha256(old) != policy_sha256(new)
    assert {k: v for k, v in new.items() if k not in {'event_policy', 'reconnect_acceptance'}} == old
    with pytest.raises(ValueError, match='event policy'):
        public_invocation_policy(**kwargs, event_policy='unknown')
    kwargs['output_format'] = 'legacy_text'
    with pytest.raises(ValueError, match='structured output'):
        public_invocation_policy(**kwargs, event_policy='completed_reconnect_v1')


def fallback_notice():
    return {'type':'item.completed', 'item':{'type':'error',
        'message':'Falling back from WebSockets to HTTPS transport. stream disconnected before completion: private detail'}}


def test_proposed_transport_fallback_accepts_only_completed_single_call_and_preserves_evidence(monkeypatch, tmp_path):
    stream = events(answer=json.dumps({'stage':2,'guidance':'no','evidence':'held'}))
    stream[2:2] = [{'type':'error','message':'Reconnecting... 5/5'}, fallback_notice()]
    recognizer, calls = make(monkeypatch,tmp_path,event_list=stream,timeout_seconds=180,
        output_format='json_schema_v1',event_policy='completed_transport_fallback_v1')
    assert identify(recognizer) == (2,False)
    result = recognizer.last_result
    assert len(calls) == result['codex_logical_call_attempts'] == result['codex_usage_complete_calls'] == 1
    assert result['codex_failed_calls'] == 0
    assert result['transport']['item_types'] == ['error','agent_message']
    assert len(result['transport']['transport_fallback_notices']) == 1
    assert result['transport']['transport_fallback_notices'][0]['classification'] == 'websocket_to_https_fallback_notice'
    assert 'private detail' not in json.dumps(result)


def test_preturn_fallback_accepts_one_complete_reply_without_relaxing_v1(monkeypatch, tmp_path):
    stream = events(answer=json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'}))
    stream.insert(1, fallback_notice())
    old, _ = make(monkeypatch, tmp_path, event_list=stream,
                  output_format='json_schema_v1', event_policy='completed_transport_fallback_v1')
    assert identify(old) == (1, True)
    assert old.last_result['error'] == 'codex_unexpected_item'
    new, calls = make(monkeypatch, tmp_path, event_list=stream,
                      output_format='json_schema_v1', event_policy='completed_transport_fallback_preturn_v2')
    assert identify(new) == (2, False)
    assert len(calls) == new.last_result['codex_usage_complete_calls'] == 1
    assert new.last_result['codex_failed_calls'] == 0
    notices = new.last_result['transport']['transport_fallback_notices']
    assert len(notices) == 1 and notices[0]['event_index'] == 1
    assert 'private detail' not in json.dumps(new.last_result)


def test_preturn_multiline_fallback_requires_new_policy_and_complete_reply(monkeypatch, tmp_path):
    stream = events(answer=json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'}))
    notice = fallback_notice()
    notice['item']['message'] += '\n  server response detail'
    stream.insert(1, notice)
    old, _ = make(monkeypatch, tmp_path, event_list=stream,
                  output_format='json_schema_v1', event_policy='completed_transport_fallback_preturn_v2')
    assert identify(old) == (1, True)
    assert old.last_result['error'] == 'codex_unexpected_item'
    new, calls = make(monkeypatch, tmp_path, event_list=stream,
                      output_format='json_schema_v1',
                      event_policy='completed_transport_fallback_preturn_multiline_v3')
    assert identify(new) == (2, False)
    assert len(calls) == new.last_result['codex_usage_complete_calls'] == 1
    assert new.last_result['transport']['error_diagnostics'][0]['contains_line_break'] is True
    assert new.last_result['transport']['error_diagnostics'][0]['known_transport_prefix'] is True
    assert 'server response detail' not in json.dumps(new.last_result)


@pytest.mark.parametrize('message', [
    'unrelated provider error',
    module.TRANSPORT_FALLBACK_PREFIX,
    module.TRANSPORT_FALLBACK_PREFIX + 'error\x00secret',
    module.TRANSPORT_FALLBACK_PREFIX + 'error\x01secret',
])
def test_preturn_multiline_rejects_unrelated_or_control_items(monkeypatch, tmp_path, message):
    stream = events(answer=json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'}))
    notice = fallback_notice()
    notice['item']['message'] = message
    stream.insert(1, notice)
    recognizer, _ = make(monkeypatch, tmp_path, event_list=stream,
        output_format='json_schema_v1', event_policy='completed_transport_fallback_preturn_multiline_v3')
    assert identify(recognizer) == (1, True)
    assert recognizer.last_result['error'] == 'codex_unexpected_item'


def test_exact_luna_metadata_warning_matches_live_hash_and_requires_v4(monkeypatch, tmp_path):
    warning = module.MODEL_METADATA_FALLBACK_TEMPLATE.format(model='gpt-6-luna')
    assert len(warning) == 122
    assert hashlib.sha256(warning.encode()).hexdigest() == (
        'c9873998fae7b5e32f26f003cc85a9dc11480871e124b8592818df89a672001b')
    stream = events(answer=json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'}))
    stream.insert(1, {'type': 'item.completed', 'item': {'type': 'error', 'message': warning}})
    old, _ = make(monkeypatch, tmp_path, event_list=stream,
        output_format='json_schema_v1', event_policy='completed_transport_fallback_preturn_multiline_v3')
    assert identify(old) == (1, True)
    assert old.last_result['error'] == 'codex_unexpected_item'
    new, calls = make(monkeypatch, tmp_path, event_list=stream, model='gpt-6-luna',
        output_format='json_schema_v1', event_policy='completed_known_startup_warnings_v4')
    assert identify(new) == (2, False)
    assert len(calls) == new.last_result['codex_usage_complete_calls'] == 1
    assert len(new.last_result['transport']['model_metadata_warning_notices']) == 1
    assert new.last_result['transport']['transport_fallback_notices'] == []
    assert new.last_result['transport']['error_diagnostics'][0]['signals'] == ['model_metadata_fallback']


def combined_warning_stream():
    stream = events(answer=json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'}))
    warning = module.MODEL_METADATA_FALLBACK_TEMPLATE.format(model='gpt-6-luna')
    stream.insert(1, {'type': 'item.completed', 'item': {'type': 'error', 'message': warning}})
    for attempt in (2, 3, 4, 5):
        stream.insert(len(stream) - 2, {'type': 'error',
            'message': f'Reconnecting... {attempt}/5 (stream disconnected)'})
    stream.insert(len(stream) - 2, fallback_notice())
    return stream


def test_combined_live_startup_warnings_require_v5(monkeypatch, tmp_path):
    stream = combined_warning_stream()
    old, _ = make(monkeypatch, tmp_path, event_list=stream, model='gpt-6-luna',
                  output_format='json_schema_v1', event_policy='completed_known_startup_warnings_v4')
    assert identify(old) == (1, True)
    new, calls = make(monkeypatch, tmp_path, event_list=stream, model='gpt-6-luna',
                      output_format='json_schema_v1', event_policy='completed_known_startup_warnings_combo_v5')
    assert identify(new) == (2, False)
    assert len(calls) == new.last_result['codex_usage_complete_calls'] == 1
    transport = new.last_result['transport']
    assert len(transport['model_metadata_warning_notices']) == 1
    assert len(transport['transport_fallback_notices']) == 1
    assert [e['attempt'] for e in transport['error_events']] == [2, 3, 4, 5]


def two_transport_phase_stream(answer):
    stream = events(answer=answer)
    notices = [
        {'type': 'error', 'message': f'Reconnecting... {attempt}/5 (stream disconnected)'}
        for attempt in (2, 3, 4, 5)
    ]
    notices.append(fallback_notice())
    notices.extend(
        {'type': 'error', 'message': f'Reconnecting... {attempt}/5 (stream disconnected)'}
        for attempt in (1, 2, 3, 4)
    )
    stream[2:2] = notices
    return stream


@pytest.mark.parametrize('output_format,answer', [
    ('json_schema_v1', json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'})),
    ('legacy_text', ANSWER),
])
def test_completed_two_transport_phases_v6_preserves_reply_and_usage(
        monkeypatch, tmp_path, output_format, answer):
    stream = two_transport_phase_stream(answer)
    recognizer, calls = make(monkeypatch, tmp_path, event_list=stream,
        output_format=output_format, event_policy='completed_transport_cycles_v6')
    assert identify(recognizer) == (2, False)
    assert len(calls) == recognizer.last_result['codex_usage_complete_calls'] == 1
    assert recognizer.last_result['raw_response'] == answer
    transport = recognizer.last_result['transport']
    assert [item['attempt'] for item in transport['error_events']] == [2, 3, 4, 5, 1, 2, 3, 4]
    assert len(transport['transport_fallback_notices']) == 1


@pytest.mark.parametrize('change', ['missing_fallback', 'duplicate_fallback', 'unknown_error',
                                    'too_many_in_phase', 'missing_reply', 'nonzero'])
def test_transport_cycle_v6_still_rejects_incomplete_or_unknown_stream(
        monkeypatch, tmp_path, change):
    stream = two_transport_phase_stream(ANSWER)
    if change == 'missing_fallback': stream.pop(6)
    if change == 'duplicate_fallback': stream.insert(7, fallback_notice())
    if change == 'unknown_error': stream[3]['message'] = 'unknown provider failure'
    if change == 'too_many_in_phase':
        stream.insert(6, {'type': 'error', 'message': 'Reconnecting... 6/6 (stream disconnected)'})
    if change == 'missing_reply': stream.pop(-2)
    recognizer, _ = make(monkeypatch, tmp_path, event_list=stream,
        returncode=1 if change == 'nonzero' else 0,
        event_policy='completed_transport_cycles_v6')
    assert identify(recognizer) == (1, True)
    assert recognizer.last_result['codex_failed_calls'] == 1


@pytest.mark.parametrize('change', ['wrong_model', 'duplicate_metadata', 'duplicate_fallback',
    'unknown_error', 'reconnect_order', 'reconnect_maximum', 'too_many_reconnects',
    'missing_usage', 'missing_reply', 'nonzero', 'extra_turn', 'tool_item'])
def test_combined_warning_v5_rejects_unapproved_streams(monkeypatch, tmp_path, change):
    stream = combined_warning_stream()
    if change == 'wrong_model': stream[1]['item']['message'] = stream[1]['item']['message'].replace('luna', 'astra')
    if change == 'duplicate_metadata': stream.insert(2, dict(stream[1]))
    if change == 'duplicate_fallback': stream.insert(-2, fallback_notice())
    if change == 'unknown_error': stream[3]['message'] = 'unknown provider failure'
    if change == 'reconnect_order': stream[4]['message'] = stream[3]['message']
    if change == 'reconnect_maximum': stream[4]['message'] = 'Reconnecting... 3/6 (stream disconnected)'
    if change == 'too_many_reconnects':
        stream.insert(-2, {'type': 'error', 'message': 'Reconnecting... 6/6 (stream disconnected)'})
    if change == 'missing_usage': stream[-1]['usage'] = {}
    if change == 'missing_reply': stream.pop(-2)
    if change == 'extra_turn': stream += events()
    if change == 'tool_item': stream.insert(-2, {'type': 'item.completed', 'item': {'type': 'command_execution'}})
    recognizer, _ = make(monkeypatch, tmp_path, event_list=stream, model='gpt-6-luna',
        returncode=1 if change == 'nonzero' else 0,
        output_format='json_schema_v1', event_policy='completed_known_startup_warnings_combo_v5')
    assert identify(recognizer) == (1, True)
    assert recognizer.last_result['codex_failed_calls'] == 1


@pytest.mark.parametrize('change', ['wrong_model', 'modified_text', 'duplicate', 'after_turn',
                                     'missing_usage', 'nonzero', 'extra_thread'])
def test_metadata_warning_v4_rejects_other_conditions(monkeypatch, tmp_path, change):
    warning = module.MODEL_METADATA_FALLBACK_TEMPLATE.format(model='gpt-6-luna')
    stream = events(answer=json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'}))
    notice = {'type': 'item.completed', 'item': {'type': 'error', 'message': warning}}
    stream.insert(2 if change == 'after_turn' else 1, notice)
    if change == 'wrong_model': notice['item']['message'] = warning.replace('gpt-6-luna', 'gpt-6-astra')
    if change == 'modified_text': notice['item']['message'] += ' '
    if change == 'duplicate': stream.insert(2, {'type': 'item.completed', 'item': {'type': 'error', 'message': warning}})
    if change == 'missing_usage': stream[-1]['usage'] = {}
    if change == 'extra_thread': stream.insert(1, {'type': 'thread.started', 'thread_id': 'extra'})
    recognizer, _ = make(monkeypatch, tmp_path, event_list=stream,
        returncode=1 if change == 'nonzero' else 0, model='gpt-6-luna',
        output_format='json_schema_v1', event_policy='completed_known_startup_warnings_v4')
    assert identify(recognizer) == (1, True)
    assert recognizer.last_result['codex_failed_calls'] == 1


@pytest.mark.parametrize('change', ['before_thread', 'duplicate', 'unknown', 'missing_usage',
                                     'missing_completion', 'nonzero', 'second_turn', 'tool_item'])
def test_preturn_fallback_still_rejects_other_error_or_incomplete_turn(monkeypatch, tmp_path, change):
    stream = events(answer=json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'}))
    stream.insert(0 if change == 'before_thread' else 1, fallback_notice())
    if change == 'duplicate': stream.insert(2, fallback_notice())
    if change == 'unknown': stream[1]['item']['message'] = 'unrelated provider error'
    if change == 'missing_usage': stream[-1]['usage'] = {}
    if change == 'missing_completion': stream.pop()
    if change == 'second_turn': stream += events()
    if change == 'tool_item': stream.insert(3, {'type':'item.completed', 'item':{'type':'command_execution'}})
    recognizer, calls = make(monkeypatch, tmp_path, event_list=stream,
        returncode=1 if change == 'nonzero' else 0,
        output_format='json_schema_v1', event_policy='completed_transport_fallback_preturn_v2')
    assert identify(recognizer) == (1, True)
    assert len(calls) == 1 and recognizer.last_result['codex_failed_calls'] == 1


@pytest.mark.parametrize('change', ['legacy','duplicate','unknown','empty_suffix','newline','nul','oversized',
    'item_updated','before_start','after_message','after_completion','nonzero','timeout','missing_usage',
    'missing_completion','turn_failed','tool_item','two_responses','two_turns','bad_json','other_error',
    'completion_before_response'])
def test_proposed_fallback_never_bypasses_nonfallback_gates(monkeypatch,tmp_path,change):
    stream = events(answer=json.dumps({'stage':2,'guidance':'no','evidence':'held'}) if change!='bad_json' else ANSWER)
    notice = fallback_notice()
    if change == 'unknown': notice['item']['message'] = 'unknown server error'
    if change == 'empty_suffix': notice['item']['message'] = module.TRANSPORT_FALLBACK_PREFIX
    if change == 'newline': notice['item']['message'] += '\n'
    if change == 'nul': notice['item']['message'] += '\x00'
    if change == 'oversized': notice['item']['message'] += 'x'*2048
    if change == 'item_updated': notice['type'] = 'item.updated'
    stream.insert({'before_start':0,'after_message':3,'after_completion':4}.get(change,2),notice)
    if change == 'duplicate': stream.insert(3,fallback_notice())
    if change == 'missing_usage': stream[-1]['usage'] = {}
    if change == 'missing_completion': stream.pop()
    if change == 'turn_failed': stream.insert(3,{'type':'turn.failed','error':{'message':'failed'}})
    if change == 'tool_item': stream.insert(3,{'type':'item.completed','item':{'type':'command_execution'}})
    if change == 'two_responses': stream.insert(3,events()[2])
    if change == 'two_turns': stream += events()
    if change == 'other_error': stream.insert(3,{'type':'error','message':'unknown error'})
    if change == 'completion_before_response': stream[3],stream[4] = stream[4],stream[3]
    if change == 'timeout': monkeypatch.setattr(module,'_stop_owned_process',lambda process:None)
    recognizer,calls = make(monkeypatch,tmp_path,event_list=stream,timeout_seconds=180,
        returncode=1 if change=='nonzero' else 0,timeout=change=='timeout',output_format='json_schema_v1',
        event_policy='completed_reconnect_v1' if change=='legacy' else 'completed_transport_fallback_v1')
    assert identify(recognizer) == (1,True)
    assert len(calls) == 1 and recognizer.last_result['codex_failed_calls'] == 1


def test_proposed_fallback_policy_changes_acceptance_hash_without_altering_cli_arguments():
    kwargs = dict(model='gpt-6-astra',reasoning_effort='low',timeout_seconds=180,
                  cli_path='/pinned/codex',output_format='json_schema_v1')
    old = public_invocation_policy(**kwargs,event_policy='completed_reconnect_v1')
    new = public_invocation_policy(**kwargs,event_policy='completed_transport_fallback_v1')
    assert policy_sha256(old) != policy_sha256(new)
    assert {k:v for k,v in old.items() if k!='event_policy'} == {
        k:v for k,v in new.items() if k not in {'event_policy','transport_fallback_acceptance'}}


def test_cli_policy_disables_tools_skills_and_preserves_builtin_system_prompt(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path)
    identify(recognizer)
    command = calls[0].command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert 'web_search="disabled"' in command
    assert 'skills.config=[{path="/active/one/SKILL.md",enabled=false}]' in command
    assert "project_doc_max_bytes=0" in command
    for feature in recognizer.public_policy["disabled_features"]:
        assert any(command[i:i + 2] == ["--disable", feature] for i in range(len(command) - 1))
    assert all("model_instructions_file" not in part for part in command)
    assert all("model_providers.openai" not in part for part in command)
    assert "skip_host_skill_discovery" not in command


@pytest.mark.parametrize("event_list", [
    [], events(answer=""), events(answer="No confident answer"),
    events() + events(),
    events()[:-1],
    events(usage={"input_tokens": 2, "output_tokens": 1}),
    events(usage={"input_tokens": 2, "cached_input_tokens": 3, "output_tokens": 1}),
    events(usage={"input_tokens": True, "cached_input_tokens": 0, "output_tokens": 1}),
    events()[:2] + [{"type": "item.completed", "item": {"type": "command_execution", "command": "forbidden"}}] + events()[2:],
    events()[:2] + [{"type": "item.completed", "item": {"type": "mcp_tool_call"}}] + events()[2:],
    events()[:2] + [{"type": "item.completed", "item": {"type": "error", "message": "private value"}}] + events()[2:],
    events()[:2] + [{"type": "error", "message": "private value"}] + events()[2:],
])
def test_invalid_calls_keep_conservative_fallback_and_count_failure(monkeypatch, tmp_path, event_list):
    recognizer, calls = make(monkeypatch, tmp_path, event_list=event_list)
    assert identify(recognizer) == (1, True)
    result = recognizer.last_result
    assert result["ok"] is False
    assert result["codex_failed_calls"] == 1
    assert result["codex_logical_call_attempts"] == 1
    assert "private value" not in result["error"]
    assert len(calls) == 1


def test_nonzero_exit_keeps_usage_but_is_failed(monkeypatch, tmp_path):
    recognizer, _ = make(monkeypatch, tmp_path, returncode=1)
    assert identify(recognizer) == (1, True)
    assert recognizer.last_result["error"] == "codex_nonzero_exit"
    assert recognizer.last_result["codex_input_tokens"] == 108
    assert recognizer.last_result["codex_usage_complete_calls"] == 1
    assert recognizer.last_result["raw_response"] == ANSWER


@pytest.mark.parametrize('timeout_seconds', [90, 180])
def test_timeout_terminates_owned_process_and_accounts_partial_events(monkeypatch, tmp_path, timeout_seconds):
    stopped = []
    monkeypatch.setattr(module, "_stop_owned_process", lambda process: stopped.append(process))
    recognizer, calls = make(monkeypatch, tmp_path, timeout=True, event_list=events()[:2],
        timeout_seconds=timeout_seconds, output_format='json_schema_v1', event_policy='completed_reconnect_v1')
    assert identify(recognizer) == (1, True)
    assert stopped == calls
    assert recognizer.last_result["error"] == "codex_timeout"
    assert recognizer.last_result["codex_usage_complete_calls"] == 0
    assert recognizer.last_result["codex_completed_turns"] == 0
    assert len(calls) == recognizer.last_result['codex_logical_call_attempts'] == 1
    assert calls[0].timeout == timeout_seconds
    assert recognizer.last_result['transport']['process_timed_out'] is True
    assert not Path(calls[0].kwargs["cwd"]).exists()


def test_180_second_call_uses_one_invocation_and_complete_usage(monkeypatch, tmp_path):
    answer = json.dumps({'stage': 2, 'guidance': 'no', 'evidence': 'held'})
    recognizer, calls = make(monkeypatch, tmp_path, event_list=events(answer=answer),
        timeout_seconds=180, output_format='json_schema_v1', event_policy='completed_reconnect_v1')
    assert identify(recognizer) == (2, False)
    assert calls[0].timeout == 180
    assert len(calls) == recognizer.last_result['codex_logical_call_attempts'] == 1
    assert recognizer.last_result['codex_usage_complete_calls'] == 1
    assert recognizer.last_result['transport']['timeout_seconds'] == 180
    assert recognizer.last_result['transport']['process_timed_out'] is False


@pytest.mark.parametrize('source', ['error_event', 'error_item', 'turn_failed'])
def test_error_diagnostics_keep_categories_without_private_payload(monkeypatch, tmp_path, source):
    secret = 'https://private.example/request?access_token=do-not-retain'
    message = f'stream disconnected: unexpected status 429 Too Many Requests {secret}'
    detail = {
        'error_event': {'type': 'error', 'message': message},
        'error_item': {'type': 'item.completed', 'item': {'type': 'error', 'message': message}},
        'turn_failed': {'type': 'turn.failed', 'error': {'message': message}},
    }[source]
    stream = events()
    stream.insert(2, detail)
    recognizer, calls = make(monkeypatch, tmp_path, event_list=stream)
    assert identify(recognizer) == (1, True)
    result = recognizer.last_result
    assert result['ok'] is False and result['codex_failed_calls'] == 1
    assert result['codex_usage_complete_calls'] == 1  # valid observed usage is retained
    diagnostic = result['transport']['error_diagnostics'][0]
    assert diagnostic['source'] == source
    assert diagnostic['http_status_codes'] == [429]
    assert diagnostic['signals'] == ['stream_disconnected', 'rate_limited']
    assert diagnostic['message_sha256'] == hashlib.sha256(message.encode()).hexdigest()
    assert secret not in json.dumps(result) and 'private.example' not in json.dumps(result)
    assert len(calls) == 1


def test_timeout_retains_bounded_stderr_and_error_item_diagnostics(monkeypatch, tmp_path):
    monkeypatch.setattr(module, '_stop_owned_process', lambda process: None)
    stream = events()[:2] + [
        {'type': 'error', 'message': 'Reconnecting... 2/5 stream disconnected'},
        {'type': 'item.completed', 'item': {'type': 'error', 'message': 'HTTP/1.1 503 Service Unavailable private-value'}},
    ]
    recognizer, calls = make(monkeypatch, tmp_path, event_list=stream, timeout=True,
        stderr=b'websocket connection reset; falling back; token=private-value',
        output_format='json_schema_v1', event_policy='completed_reconnect_v1', timeout_seconds=180)
    identify(recognizer)
    result = recognizer.last_result
    assert result['error'] == 'codex_timeout'
    assert result['codex_usage_complete_calls'] == 0
    transport = result['transport']
    assert transport['partial_event_validation_error'] == 'codex_expected_one_completed_turn'
    assert transport['error_diagnostics'][1]['http_status_codes'] == [503]
    assert transport['stderr_diagnostic']['signals'] == ['connection_reset', 'websocket']
    assert 'private-value' not in json.dumps(result)
    assert len(calls) == 1 and not Path(calls[0].kwargs['cwd']).exists()


def test_stderr_is_diagnostic_only_and_request_fingerprints_preserve_inputs(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path, stderr=b'HTTP 503 transient warning private-value')
    assert identify(recognizer) == (2, False)
    result = recognizer.last_result
    assert result['ok'] is True
    fingerprint = result['transport']['request_fingerprint']
    assert fingerprint['prompt_sha256'] == hashlib.sha256(calls[0].prompt.encode()).hexdigest()
    expected = []
    for pixels in calls[0].images:
        stream = io.BytesIO(); Image.fromarray(pixels).save(stream, format='PNG')
        expected.append(hashlib.sha256(stream.getvalue()).hexdigest())
    assert fingerprint['image_png_sha256'] == expected
    assert result['transport']['stderr_diagnostic']['http_status_codes'] == [503]
    assert 'private-value' not in json.dumps(result)


def test_stderr_capture_is_bounded_and_does_not_mask_call_on_io_error(monkeypatch, tmp_path):
    prefix = b'x' * module._MAX_DIAGNOSTIC_BYTES
    diagnostic = module._stderr_diagnostic(io.BytesIO(prefix + b' HTTP 401 private-value'))
    assert diagnostic['truncated'] is True
    assert diagnostic['bytes_examined'] == module._MAX_DIAGNOSTIC_BYTES
    assert diagnostic['sample_sha256'] == hashlib.sha256(prefix).hexdigest()
    assert diagnostic['http_status_codes'] == []
    assert 'private-value' not in json.dumps(diagnostic)
    monkeypatch.setattr(module, '_stderr_diagnostic', lambda stream: (_ for _ in ()).throw(OSError('private-value')))
    recognizer, _ = make(monkeypatch, tmp_path)
    assert identify(recognizer) == (2, False)
    assert recognizer.last_result['transport']['stderr_diagnostic'] == {'read_failed': True}


def test_malformed_stream_does_not_drop_observed_prior_usage(monkeypatch, tmp_path):
    raw = ("\n".join(json.dumps(event) for event in events()) + "\nmalformed").encode()
    recognizer, _ = make(monkeypatch, tmp_path, raw=raw)
    assert identify(recognizer) == (1, True)
    assert recognizer.last_result["error"] == "codex_invalid_event_stream"
    assert recognizer.last_result["codex_input_tokens"] == 108


def test_missing_optional_reasoning_usage_is_unknown(monkeypatch, tmp_path):
    usage = {key: value for key, value in USAGE.items() if key != "reasoning_output_tokens"}
    recognizer, _ = make(monkeypatch, tmp_path, event_list=events(usage=usage))
    assert recognizer.api_request_counter.snapshot()["reasoning_output_tokens"] == 0
    assert identify(recognizer) == (2, False)
    assert recognizer.last_result["codex_reasoning_output_tokens"] is None
    assert recognizer.api_request_counter.snapshot()["reasoning_output_tokens"] is None


def test_cumulative_counts_and_single_image(monkeypatch, tmp_path):
    recognizer, calls = make(monkeypatch, tmp_path)
    assert identify(recognizer, initial=False) == (2, False)
    assert len(calls[0].images) == 1
    assert "Initial Image" not in calls[0].prompt
    assert identify(recognizer) == (2, False)
    assert recognizer.api_request_counter.snapshot()["input_tokens"] == 216
    assert recognizer.api_request_counter.snapshot()["logical_call_attempts"] == 2
    assert recognizer.last_result["codex_input_tokens"] == 108


def test_legacy_factory_and_response_are_unchanged(monkeypatch, tmp_path):
    import core.gemini_grounder as legacy
    captured = []
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=ANSWER))])
    def create(**kwargs):
        captured.append(kwargs)
        return response
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(legacy, "_make_client", lambda config: client)
    recognizer = create_gemini_stage_recognizer({"model": "gemini-2.5-flash"})
    assert type(recognizer) is GeminiStageRecognizer
    assert identify(recognizer) == (2, False)
    assert captured[0]["temperature"] == 0.0
    assert captured[0]["max_tokens"] == 256
    assert [part["type"] for part in captured[0]["messages"][0]["content"]] == [
        "text", "text", "image_url", "text", "image_url"
    ]
    with pytest.raises(ValueError, match="Unknown"):
        create_gemini_stage_recognizer({"backend": "misspelled"})


def test_policy_hash_changes_with_any_frozen_transport_choice():
    kwargs = dict(model="model", reasoning_effort="low", timeout_seconds=90,
                  cli_path="/codex", disabled_skill_paths=["/skill"])
    first = public_invocation_policy(**kwargs)
    assert policy_sha256(first) == policy_sha256(public_invocation_policy(**kwargs))
    for key, value in (("model", "other"), ("reasoning_effort", "high"),
                       ("timeout_seconds", 80), ("cli_path", "/other"),
                       ("disabled_skill_paths", ["/other"])):
        changed = public_invocation_policy(**{**kwargs, key: value})
        assert policy_sha256(changed) != policy_sha256(first)


def test_skill_path_discovery_is_metadata_only_and_excludes_inactive_roots(tmp_path, monkeypatch):
    home = tmp_path / "home"
    codex = home / ".codex"
    names = ["skills/ordinary", "skills/.system/system", "disabled-skills/inactive",
             "skills/superpowers-inactive", "skills/disabled-skills/copy"]
    for name in names:
        folder = codex / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("DO NOT READ")
    agents = home / ".agents/skills/local"
    agents.mkdir(parents=True)
    (agents / "SKILL.md").touch()
    monkeypatch.setattr(Path, "read_text", lambda *a, **k: pytest.fail("must not read skills"))
    assert discover_disabled_skill_paths(codex, home) == sorted([
        str(codex / "skills/ordinary"), str(codex / "skills/.system/system"), str(agents)
    ])


def test_launch_errors_do_not_expose_credentials(monkeypatch, tmp_path):
    recognizer, _ = make(monkeypatch, tmp_path)
    def fail(*args, **kwargs):
        raise OSError("secret-canary-from-provider")
    monkeypatch.setattr(module.subprocess, "Popen", fail)
    assert identify(recognizer) == (1, True)
    assert recognizer.last_result["error"] == "codex_transport_failure"
    assert "secret-canary" not in json.dumps(recognizer.last_result)
    assert recognizer.last_result["codex_failed_calls"] == 1


def test_owned_timeout_cleanup_keeps_outer_group_and_stops_child_tree():
    # A real local process tree checks the cleanup boundary; no CLI/API call.
    script = (
        "import os, subprocess, sys, time; "
        "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "print(str(child.pid)+' '+str(os.getpgrp()), flush=True); time.sleep(60)"
    )
    process = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
    child_pid, group = map(int, process.stdout.readline().split())
    child = module.psutil.Process(child_pid)
    try:
        assert group == module.os.getpgrp()
        module._stop_owned_process(process)
        assert process.poll() is not None
        assert not child.is_running() or child.status() == module.psutil.STATUS_ZOMBIE
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        try:
            if child.is_running() and child.status() != module.psutil.STATUS_ZOMBIE:
                child.kill()
        except module.psutil.NoSuchProcess:
            pass
