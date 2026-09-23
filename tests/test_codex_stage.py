"""CPU-only boundary tests for managed-login Stage calls; no live API/GPU."""
import json
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

import core.codex_stage as module
from core.codex_stage import CodexStageRecognizer
from core.codex_stage_policy import discover_disabled_skill_paths, policy_sha256, public_invocation_policy
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
         output_format="legacy_text", event_policy="strict_v1", timeout_seconds=90):
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

        def communicate(self, input=None, timeout=None):
            self.prompt = input
            self.timeout = timeout
            if timeout is not None and make_timeout[0]:
                raise subprocess.TimeoutExpired("codex", timeout)
            return None, None

    make_timeout = [timeout]
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    recognizer = CodexStageRecognizer({
        "backend": "codex_cli", "model": "gpt-6-astra", "cli_path": str(cli),
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
