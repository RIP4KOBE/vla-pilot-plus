"""Observational request accounting with local mocked transports only."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
from openai import OpenAI
import pytest

from core.gemini_grounder import APIRequestCounter, GeminiStageRecognizer, observe_api_requests


ROOT = Path(__file__).resolve().parents[1]


def mock_client(handler):
    return OpenAI(api_key='unit-test-placeholder', base_url='https://mock.invalid/v1',
                  http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=2)


def response():
    return {'id': 'mock-response', 'object': 'chat.completion', 'created': 0, 'model': 'mock-model',
            'choices': [{'index': 0, 'message': {'role': 'assistant',
                'content': 'stage 2\nguidance: no\nevidence: object grasped'}, 'finish_reason': 'stop'}]}


@pytest.mark.parametrize('succeed', [True, False])
def test_stage_counts_actual_http_attempts_including_sdk_retries(monkeypatch, tmp_path, succeed):
    requests = []

    def handler(request):
        requests.append(request)
        if succeed and len(requests) == 3:
            return httpx.Response(200, json=response())
        return httpx.Response(500, json={'error': {'message': 'mock unavailable', 'type': 'server_error'}},
                              headers={'retry-after-ms': '1'})

    client = mock_client(handler)
    monkeypatch.setattr('core.gemini_grounder._make_client', lambda _: client)
    template = tmp_path / 'template.txt'
    template.write_text('{trigger_reason} {instruction} {stage_descriptions} {keypoint_info}')
    recognizer = GeminiStageRecognizer({'model': 'mock-model', 'stage_template_path': str(template)})
    result = recognizer.identify_stage_and_guidance(np.zeros((2, 2, 3), dtype=np.uint8),
        'move milk', 'stage descriptions', num_stages=2, trigger_reason='gripper closed')
    assert result == ((2, False) if succeed else (1, True))
    assert recognizer.last_result['api_request_attempts'] == 3
    assert recognizer.last_result['api_sdk_retry_attempts'] == 2
    assert recognizer.last_result['api_request_counter_available'] is True
    assert [r.headers['x-stainless-retry-count'] for r in requests] == ['0', '1', '2']
    assert all(json.loads(r.content)['model'] == 'mock-model' for r in requests)
    assert all(json.loads(r.content)['temperature'] == 0.0 for r in requests)
    assert all(json.loads(r.content)['max_tokens'] == 256 for r in requests)
    assert client.max_retries == 2
    client.close()


def test_observer_is_idempotent_and_counts_separate_caller_attempts():
    client = mock_client(lambda _: httpx.Response(200, json=response()))
    observer = observe_api_requests(client)
    assert observe_api_requests(client) is observer
    for _ in range(2):
        client.chat.completions.create(model='mock-model', messages=[{'role': 'user', 'content': 'mock'}])
    assert observer.snapshot() == {'request_attempts': 2, 'sdk_retry_attempts': 0,
                                   'observation_available': True}
    client.close()


def test_unsupported_client_does_not_pretend_requests_were_observed():
    counter = observe_api_requests(SimpleNamespace())
    assert counter.snapshot()['observation_available'] is False


def runner_methods():
    """Load only observational methods, avoiding main's simulator imports."""
    tree = ast.parse((ROOT / 'main.py').read_text())
    names = {'_api_compute_snapshot', '_perception_compute_snapshot', '_begin_episode_compute', '_append_episode_compute'}
    nodes = [n for cls in tree.body if isinstance(cls, ast.ClassDef)
             for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    cls = ast.ClassDef(name='Runner', bases=[], keywords=[], body=nodes, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    recorded = []
    namespace = {'Path': Path, '_adapter_actual_task_id': lambda adapter: adapter.task_id,
                 '_config_section_to_dict': lambda section, _: section or {},
                 'append_jsonl': lambda path, record: recorded.append((path, record))}
    exec(compile(module, '<observational-runner-methods>', 'exec'), namespace)
    return namespace['Runner'], recorded


def test_episode_summary_counts_preparation_and_failed_stage_requests_without_cross_episode_leakage(tmp_path):
    Runner, recorded = runner_methods()
    runner = Runner()
    stage, guidance = APIRequestCounter(), APIRequestCounter()
    stage.observation_available = guidance.observation_available = True
    runner.gemini_stage_recognizer = SimpleNamespace(api_request_counter=stage)
    runner.vlm_agent = SimpleNamespace(api_request_counter=guidance)
    runner.gemini_grounder = None
    dino_counts = {'dino_forward_calls': 4, 'dino_batch_rows': 4}
    runner.keypoint_detector = SimpleNamespace(get_compute_counters=lambda: dict(dino_counts))
    runner.policy = SimpleNamespace(get_episode_compute_counters=lambda: {'model_forward_calls': 7, 'reward_calls': 3})
    runner.adapter = SimpleNamespace(task_id=8)
    runner.config = {'eds_eval': {'output_dir': str(tmp_path)}}
    runner._begin_episode_compute()
    dino_counts['dino_forward_calls'] += 2
    dino_counts['dino_batch_rows'] += 2
    guidance.on_request(SimpleNamespace(headers={'x-stainless-retry-count': '0'}))
    for retry in ['0', '1', '2']:
        stage.on_request(SimpleNamespace(headers={'x-stainless-retry-count': retry}))
    runner._append_episode_compute(episode=0, episode_seed=123, outcome='execution_error')
    path, first = recorded[0]
    assert path.name == 'episode_compute.jsonl'
    assert first['schema'] == 'qd-ed-episode-compute-v1'
    assert first['provider_request_attempts'] == 4
    assert first['provider_sdk_retry_attempts'] == 2
    assert first['guidance_api_request_attempts'] == 1
    assert first['stage_api_request_attempts'] == 3
    assert first['provider_counters_available'] is True
    assert first['dino_forward_calls'] == first['dino_batch_rows'] == 2
    assert first['perception_counters_available'] is True
    assert first['perception_components'] == {'dino': 'active_observed', 'sam3': 'inactive', 'grounding': 'inactive'}
    assert first['model_forward_calls'] == 7
    assert first['outcome'] == 'execution_error'
    assert first['episode_seed'] == 123 and first['task_id'] == 8
    runner._begin_episode_compute()
    runner._append_episode_compute(episode=1, episode_seed=456, outcome='completed')
    assert recorded[1][1]['provider_request_attempts'] == 0
    assert recorded[1][1]['provider_sdk_retry_attempts'] == 0
    assert recorded[1][1]['dino_forward_calls'] == recorded[1][1]['dino_batch_rows'] == 0
    assert 'unit-test-placeholder' not in json.dumps(recorded[0][1])


def test_perception_inactive_and_active_unobserved_are_distinct():
    Runner, _ = runner_methods()
    runner = Runner()
    snapshot = runner._perception_compute_snapshot()
    assert snapshot['observation_available'] is True
    assert all(value == 'inactive' for value in snapshot['components'].values())
    runner.sam3_segmenter = SimpleNamespace()
    assert runner._perception_compute_snapshot()['observation_available'] is False
    assert runner._perception_compute_snapshot()['components']['sam3'] == 'active_unobserved'
    runner.sam3_segmenter = None
    runner.keypoint_detector = SimpleNamespace()
    assert runner._perception_compute_snapshot()['observation_available'] is False


def codex_runner(tmp_path):
    Runner, recorded = runner_methods()
    runner = Runner()
    counts = {
        'backend': 'codex_cli', 'request_attempts': None, 'sdk_retry_attempts': None,
        'observation_available': False, 'logical_call_attempts': 0, 'completed_turns': 0,
        'failed_calls': 0, 'usage_complete_calls': 0, 'input_tokens': 0,
        'cached_input_tokens': 0, 'output_tokens': 0, 'reasoning_output_tokens': 0,
        'call_latency_s': 0.0,
    }
    runner.gemini_stage_recognizer = SimpleNamespace(
        api_request_counter=SimpleNamespace(snapshot=lambda: dict(counts)),
        transport_metadata={'backend': 'codex_cli', 'model': 'gpt-6-astra', 'application_max_attempts': 1},
    )
    runner.vlm_agent = SimpleNamespace(cache_only=True)
    runner.gemini_grounder = None
    runner.policy = SimpleNamespace(get_episode_compute_counters=lambda: {'model_forward_calls': 7})
    runner.adapter = SimpleNamespace(task_id=8)
    runner.config = {'eds_eval': {'output_dir': str(tmp_path)}}
    return runner, counts, recorded


def test_codex_episode_counts_failed_calls_without_inventing_http_requests_or_tokens(tmp_path):
    runner, counts, recorded = codex_runner(tmp_path)
    runner._begin_episode_compute()
    counts.update(logical_call_attempts=3, completed_turns=2, failed_calls=2,
                  usage_complete_calls=2, input_tokens=100, cached_input_tokens=40,
                  output_tokens=9, reasoning_output_tokens=None, call_latency_s=21.5)
    runner._append_episode_compute(episode=0, episode_seed=123, outcome='completed')
    first = recorded[0][1]
    assert first['schema'] == 'qd-ed-episode-compute-v2'
    assert first['provider_counters_available'] is True
    assert first['provider_logical_counters_available'] is True
    assert first['provider_http_counters_available'] is False
    for name in ('stage_api_request_attempts', 'stage_api_sdk_retry_attempts',
                 'provider_request_attempts', 'provider_sdk_retry_attempts'):
        assert first[name] is None
    assert first['guidance_api_request_attempts'] == first['grounding_api_request_attempts'] == 0
    assert first['provider_logical_call_attempts'] == first['stage_codex_logical_call_attempts'] == 3
    assert first['provider_completed_turns'] == first['provider_failed_calls'] == 2
    assert first['provider_usage_complete_calls'] == 2
    assert first['provider_token_usage_complete'] is False
    assert first['provider_input_tokens'] == 100
    assert first['provider_cached_input_tokens'] == 40
    assert first['provider_output_tokens'] == 9
    assert first['provider_reasoning_output_tokens'] is None
    assert first['provider_call_latency_s'] == 21.5
    assert first['stage_transport']['model'] == 'gpt-6-astra'

    runner._begin_episode_compute()
    counts.update(logical_call_attempts=4, completed_turns=3, usage_complete_calls=3,
                  input_tokens=130, cached_input_tokens=50, output_tokens=12,
                  call_latency_s=31.5)
    runner._append_episode_compute(episode=1, episode_seed=456, outcome='completed')
    second = recorded[1][1]
    assert second['provider_logical_call_attempts'] == second['provider_completed_turns'] == 1
    assert second['provider_failed_calls'] == 0
    assert second['provider_input_tokens'] == 30
    assert second['provider_cached_input_tokens'] == 10
    assert second['provider_output_tokens'] == 3
    assert second['provider_call_latency_s'] == 10
    assert second['provider_token_usage_complete'] is True
    assert second['provider_reasoning_output_tokens'] is None


def test_codex_does_not_treat_unobserved_guidance_as_inactive(tmp_path):
    runner, counts, recorded = codex_runner(tmp_path)
    runner.vlm_agent = SimpleNamespace()
    runner._begin_episode_compute()
    runner._append_episode_compute(episode=0, episode_seed=123, outcome='preparation_error')
    record = recorded[0][1]
    assert record['provider_counters_available'] is False
    assert record['provider_logical_counters_available'] is False
    assert record['provider_logical_call_attempts'] is None
    assert record['provider_token_usage_complete'] is False


def test_codex_missing_counter_and_counter_reset_fail_observation(tmp_path):
    runner, counts, recorded = codex_runner(tmp_path)
    counts['logical_call_attempts'] = 3
    runner._begin_episode_compute()
    counts['logical_call_attempts'] = 0
    counts.pop('call_latency_s')
    runner._append_episode_compute(episode=0, episode_seed=123, outcome='execution_error')
    record = recorded[0][1]
    assert record['provider_counters_available'] is False
    assert record['provider_logical_call_attempts'] is None
    assert record['provider_call_latency_s'] is None
