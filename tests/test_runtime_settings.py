import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mode_gate.config import ModeGateConfig
from mode_gate.experiment_contract import DEFAULT_RETRY_SCHEDULE_50
from mode_gate.runtime_settings import apply_runtime_steering_settings, install_warm_steering_hook


def make_runner():
    old_schedule = ((1., 1.), (1.15, 1.1), (1.3, 1.25)) + ((1.5, 1.4),) * 47
    old = ModeGateConfig(retry_schedule=old_schedule)
    runtime = SimpleNamespace(config=old, _pending_factual=[],
        controller=SimpleNamespace(config=old, state=SimpleNamespace(phase=SimpleNamespace(value='EXPAND'))),
        gate=SimpleNamespace(config=old))
    return SimpleNamespace(mode_gate_config=old, mode_aware_runtime=runtime,
        policy=SimpleNamespace(select_action=lambda batch=None, guide_scale=1.0, diversity_scale=1.0: (guide_scale, diversity_scale)),
        adapter=object(), cfg=SimpleNamespace(mode_gate=SimpleNamespace(retry_schedule=[])),
        _reload_active_deployment=lambda: 'original reload')


def write_request(tmp_path):
    from mode_gate.io_utils import atomic_write_json
    path = tmp_path / 'runtime_steering_settings.json'
    atomic_write_json(path, {'schema_version': 'vls-runtime-steering-v1',
        'guide_multiplier_upper_bound': 1.0,
        'guide_scale_max': 80.0, 'diversity_scale_max': 20.0,
        'retry_schedule': [list(pair) for pair in DEFAULT_RETRY_SCHEDULE_50]})
    return path


def test_expansion_boundary_changes_schedule_without_model_reload_or_label_rewrite(tmp_path):
    runner = make_runner()
    old = runner.mode_gate_config
    policy, adapter = runner.policy, runner.adapter
    before = old.experiment_contract().contract_hash
    request = write_request(tmp_path)
    result = apply_runtime_steering_settings(runner, request_path=request)
    assert max(pair[0] for pair in runner.mode_gate_config.retry_schedule) == 1.0
    assert runner.policy is policy and runner.adapter is adapter
    assert max(pair[0] for pair in old.retry_schedule) == 1.5
    assert result['old_contract_hash'] == before
    assert result['label_contract_hash'] != before
    assert result['existing_labels_modified'] is False
    assert runner.mode_gate_config.retry_budget == 50
    assert runner.mode_gate_config.chunk_horizon == 10
    assert runner.mode_gate_config.retry_schedule[-1][1] == 1.0
    assert runner.policy.select_action(guide_scale=120, diversity_scale=25) == (80, 20)
    assert apply_runtime_steering_settings(runner, request_path=request) is None
    assert len(request.with_suffix('.events.jsonl').read_text().splitlines()) == 1


def test_runtime_update_rejects_mid_chunk_or_unclosed_factual_labels(tmp_path):
    runner = make_runner()
    old = runner.mode_gate_config
    path = write_request(tmp_path)
    runner.mode_aware_runtime.controller.state.phase.value = 'EXECUTE'
    with pytest.raises(RuntimeError, match='boundary'):
        apply_runtime_steering_settings(runner, request_path=path)
    runner.mode_aware_runtime._pending_factual = [{}]
    with pytest.raises(RuntimeError, match='unfinished factual'):
        apply_runtime_steering_settings(runner, request_path=path, at_episode_boundary=True)
    assert runner.mode_gate_config is old


def test_hook_reuses_existing_deployment_callback_and_is_idempotent(tmp_path):
    runner = make_runner()
    path = write_request(tmp_path)
    install_warm_steering_hook(runner, request_path=path)
    hook = runner._reload_active_deployment
    install_warm_steering_hook(runner, request_path=path)
    assert runner._reload_active_deployment is hook
    assert runner._reload_active_deployment() == 'original reload'
    assert max(pair[0] for pair in runner.mode_gate_config.retry_schedule) == 1.0


def test_hot_deployment_replacement_inherits_caps_without_reapplying_request(tmp_path):
    runner = make_runner()
    replacement = make_runner().policy
    path = write_request(tmp_path)
    apply_runtime_steering_settings(runner, request_path=path)

    def deploy():
        runner.policy = replacement
        return 'deployed'

    runner._reload_active_deployment = deploy
    install_warm_steering_hook(runner, request_path=path)
    assert runner._reload_active_deployment() == 'deployed'
    assert runner.policy is replacement
    assert replacement.select_action(guide_scale=240, diversity_scale=40) == (80, 20)
    assert len(path.with_suffix('.events.jsonl').read_text().splitlines()) == 1


@pytest.mark.parametrize('guide,diversity,expected', [
    (40, 10, (40, 10)), (40 * 3, 10 * 2, (80, 20)),
    (80 * 3, 20 * 2, (80, 20)), (0, 0, (0, 0)),
])
def test_absolute_caps_apply_after_retry_multipliers(guide, diversity, expected):
    from core.steering_limits import bounded_steering_scales
    policy = SimpleNamespace()
    assert bounded_steering_scales(policy, guide, diversity) == expected
    assert policy._last_steering_limits_report['requested_guide_scale'] == guide


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf')])
def test_invalid_steering_values_fail_before_sampling(value):
    from core.steering_limits import bounded_steering_scales
    with pytest.raises(ValueError, match='finite, nonnegative'):
        bounded_steering_scales(SimpleNamespace(), value, 10)


def test_full_experiment_enables_guidance_and_stage_recognition_for_each_context(tmp_path):
    from scripts.run_full_experiment import make_config

    for init_state in (21, 22):
        cfg = make_config({'runtime_suite': 'libero_10_lan', 'task_index': 2,
            'init_state_id': init_state, 'env_seed': 1, 'policy_seed': 2},
            tmp_path / f'run-{init_state}', tmp_path / 'data', 6)
        assert cfg.main.use_guidance is True
        assert cfg.main.use_vlm_stage_recognition is True
        assert cfg.perception.gemini.thinking_level == 'ultra'
        assert cfg.perception.gemini.model == 'gpt-6-astra'
        assert cfg.mode_gate.planner_model == 'gpt-6-astra'
        assert cfg.mode_gate.planner_reasoning_effort == 'ultra'
        assert cfg.perception.gemini.max_provider_calls == 10000
        assert cfg.perception.gemini.call_ledger_path == cfg.mode_gate.planner_call_ledger
        assert cfg.device == 'cuda:6'
