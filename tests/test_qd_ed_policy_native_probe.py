"""CPU-only orchestration tests; never import or execute a real policy/GPU."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qd_ed_policy_native_probe', ROOT / 'scripts/qd_ed_policy_native_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def evidence(resource_id, physical_gpu=6):
    return {'schema': probe.SCHEMA, 'resource_id': resource_id, **probe.SCOPE,
            'physical_gpu': physical_gpu, 'torch_logical_device': 0,
            'torch_uuid': 'GPU-test', 'cuda_visible_devices': str(physical_gpu),
            'cuda_device_order': 'PCI_BUS_ID', 'raw_prediction_shape': [1, 64, 128],
            'raw_prediction_finite': True, 'simulator_modules_present': [],
            'compute': {'model_forward_calls': 5, 'model_batch_rows': 5,
                        'vision_encoder_forward_calls': 1, 'text_encoder_forward_calls': 1,
                        'denoising_invocations': 1}}


def fixture_run(tmp_path, monkeypatch, physical_gpu=6):
    root, artifacts = tmp_path / 'worktree', tmp_path / 'artifacts'
    (root / 'data').mkdir(parents=True)
    artifacts.mkdir()
    runtime = {'gpu_mapping': {'physical_gpu': physical_gpu, 'egl_device_index': 3,
                              'uuid': 'GPU-test'}, 'environment': {}}
    runtime_path = artifacts / 'runtime.json'
    runtime_path.write_text(json.dumps(runtime))
    plan = {'run_name': 'native-test', 'source_commit': 'frozen-head', 'artifact_root': str(artifacts),
            'runtime_manifest_path': str(runtime_path), 'runtime_manifest_sha256': probe.runner.digest(runtime_path),
            'runtime_inventory_sha256': 'frozen-inventory'}
    plan_path = root / 'data/plan.json'
    plan_path.write_text(json.dumps(plan))
    state = {'gpu_pool': [physical_gpu], 'max_concurrent_gpu_workers': 1,
             'budget': {'max_episode_attempts': 240, 'max_gpu_hours': 48., 'dispatched': 0,
                        'gpu_hours_consumed': 0., 'reserved': dict(probe.runner.BUCKETS)}}
    monkeypatch.setattr(probe, 'validate_inputs', lambda path, root: (plan, runtime, {'frozen': 'config'}))
    monkeypatch.setattr(probe.runner, 'read_state', lambda path: state)
    events, admissions, cleanup = [], [], []
    monkeypatch.setattr(probe.runner, 'append_healthcheck_event', lambda root, event: events.append(event))
    def admit(**kwargs):
        admissions.append(kwargs)
        assert kwargs == {'physical_gpu': physical_gpu, 'expected_uuid': 'GPU-test'}
        return {'physical_gpu': physical_gpu}
    monkeypatch.setattr(probe.runner, 'gpu_admission', admit)
    monkeypatch.setattr(probe.runner, 'terminate_owned', lambda process: cleanup.append(process))
    return root, plan_path, runtime, state, events, admissions, cleanup


@pytest.mark.parametrize('physical_gpu', [5, 6, 7])
@pytest.mark.parametrize('exit_code', [0, -6])
def test_native_exit_preserved_and_all_dispatched_time_counted_without_episode(tmp_path, monkeypatch, physical_gpu, exit_code):
    root, plan_path, runtime, state, events, admissions, cleanup = fixture_run(tmp_path, monkeypatch, physical_gpu)
    def launch(command, **kwargs):
        env = kwargs['env']
        assert env['CUDA_VISIBLE_DEVICES'] == str(physical_gpu)
        assert env['CUDA_DEVICE_ORDER'] == 'PCI_BUS_ID'
        assert env['HF_HUB_OFFLINE'] == env['TRANSFORMERS_OFFLINE'] == env['PYTHONFAULTHANDLER'] == '1'
        assert kwargs['start_new_session'] is True
        output = Path(command[command.index('--output') + 1])
        resource_id = command[command.index('--resource-id') + 1]
        contract_path = Path(command[command.index('--contract') + 1])
        assert probe.runner.digest(contract_path) == env['QD_ED_NATIVE_CONTRACT_SHA256']
        assert json.loads(contract_path.read_text())['scope'] == probe.SCOPE
        probe.append_phase(output, '_counted_dit', 'enter', call_index=1)
        if exit_code == 0:
            (output / 'probe-evidence.json').write_text(json.dumps(evidence(resource_id, physical_gpu)))
        else:
            with (output / 'phase-boundaries.jsonl').open('a') as stream:
                stream.write('{"interrupted":')
        return SimpleNamespace(pid=99999999)
    def wait(process, timeout, **kwargs):
        assert kwargs == {'physical_gpu': physical_gpu}
        assert timeout == 600
        return exit_code
    monkeypatch.setattr(probe.subprocess, 'Popen', launch)
    monkeypatch.setattr(probe.runner, 'wait_exclusively', wait)
    result = probe.run_probe(plan_path, root=root)
    expected = 'completed' if exit_code == 0 else 'aborted'
    assert [event['event'] for event in events] == ['reserved', 'dispatched', expected]
    assert result['child_exit_code'] == exit_code
    assert result['gpu_process_wall_seconds'] >= 0
    assert all(event['kind'] == 'policy_native_diagnostic' for event in events)
    assert all(event['physical_gpu'] == physical_gpu and 'attempt_id' not in event for event in events)
    assert len(admissions) == 2 and len(cleanup) == 1
    if exit_code < 0:
        assert result['native_signal'] == 'SIGABRT'
        assert result['last_phase_boundary']['last_complete_boundary']['phase'] == '_counted_dit'
        assert result['last_phase_boundary']['incomplete_or_invalid_phase_line'] is True
    snapshot = probe.runner.budget_snapshot([], events)
    assert snapshot['dispatched'] == snapshot['completed'] == snapshot['gpu_healthcheck_inflight'] == 0
    assert snapshot['gpu_healthcheck_hours'] == pytest.approx(result['gpu_process_wall_seconds'] / 3600)
    assert snapshot['gpu_hours_by_bucket']['recovery'] == snapshot['gpu_healthcheck_hours']
    assert not (root / 'data/attempt-ledger.jsonl').exists()


def test_busy_gpu_prevents_reservation_and_dispatch(tmp_path, monkeypatch):
    root, plan_path, runtime, state, events, admissions, cleanup = fixture_run(tmp_path, monkeypatch)
    def busy(**kwargs):
        raise probe.runner.GateError('external GPU process')
    monkeypatch.setattr(probe.runner, 'gpu_admission', busy)
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('must not dispatch'))
    with pytest.raises(probe.runner.GateError, match='external'):
        probe.run_probe(plan_path, root=root)
    assert events == []


def test_wrong_authorization_and_protected_budget_gate_before_gpu(tmp_path, monkeypatch):
    root, plan_path, runtime, state, events, admissions, cleanup = fixture_run(tmp_path, monkeypatch)
    state['gpu_pool'] = [7]
    with pytest.raises(probe.runner.GateError, match='mismatch'):
        probe.run_probe(plan_path, root=root)
    state['gpu_pool'] = [6]
    state['budget']['max_gpu_hours'] = 24.
    with pytest.raises(probe.runner.GateError, match='termination grace'):
        probe.run_probe(plan_path, root=root)
    assert events == admissions == []


def test_timeout_cleanup_and_abort_still_accounted(tmp_path, monkeypatch):
    root, plan_path, runtime, state, events, admissions, cleanup = fixture_run(tmp_path, monkeypatch)
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(pid=99999999))
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('native diagnostic', 30)
    monkeypatch.setattr(probe.runner, 'wait_exclusively', timeout)
    result = probe.run_probe(plan_path, root=root, timeout_seconds=30)
    assert result['event'] == 'aborted' and result['reason'] == 'TimeoutExpired'
    assert cleanup and result['gpu_process_wall_seconds'] >= 0
    assert [event['event'] for event in events] == ['reserved', 'dispatched', 'aborted']


@pytest.mark.parametrize('timeout', [0, -1, 601, True, 1.5])
def test_timeout_is_bounded_before_reading_inputs(timeout, tmp_path):
    with pytest.raises(probe.runner.GateError, match='1..600'):
        probe.run_probe(tmp_path / 'missing.json', root=tmp_path, timeout_seconds=timeout)


def test_direct_child_cannot_import_production_without_admitted_parent(tmp_path, monkeypatch):
    monkeypatch.delenv('QD_ED_NATIVE_PARENT_PID', raising=False)
    with pytest.raises(probe.runner.GateError, match='admitted parent'):
        probe.child_probe(tmp_path / 'missing.json', tmp_path, 'unknown')


@pytest.mark.parametrize('change', [
    {'physical_gpu': 7}, {'torch_uuid': 'GPU-wrong'}, {'cuda_visible_devices': '6,7'},
    {'simulation_steps': 1}, {'action_vectors_executed': 1}, {'stage_calls': 1},
    {'raw_prediction_shape': [16, 64, 128]}, {'raw_prediction_finite': False},
    {'simulator_modules_present': ['mujoco']}, {'compute': {}},
])
def test_evidence_rejects_wrong_device_scope_or_missing_model_execution(change):
    runtime = {'gpu_mapping': {'physical_gpu': 6, 'egl_device_index': 3, 'uuid': 'GPU-test'}}
    with pytest.raises(probe.runner.GateError):
        probe.validate_evidence({**evidence('resource'), **change}, {'resource_id': 'resource'}, runtime)


def test_method_phase_wrapper_preserves_arguments_returns_and_exceptions(tmp_path):
    calls = []
    class Policy:
        def _get_lang_embed(self, task):
            calls.append(task)
            return 'real-result'
        def _counted_encode_inputs(self, *args, **kwargs):
            return args, kwargs
        def _counted_dit(self, *args, **kwargs):
            raise ValueError('example')
        def _counted_scheduler_step(self, *args, **kwargs):
            return 9
    policy = Policy()
    probe.install_phase_wrappers(policy, tmp_path)
    assert policy._get_lang_embed('task') == 'real-result'
    assert policy._counted_encode_inputs(1, flag=2) == ((1,), {'flag': 2})
    with pytest.raises(ValueError):
        policy._counted_dit(1)
    records = probe.runner.read_events(tmp_path / 'phase-boundaries.jsonl')
    assert calls == ['task']
    assert [(item['phase'], item['event']) for item in records][-2:] == [
        ('_counted_dit', 'enter'), ('_counted_dit', 'python_exception')]


@pytest.mark.parametrize('event,args', [('socket.connect', ()), ('socket.getaddrinfo', ()),
                                      ('socket.sendto', ()), ('socket.bind', ()),
                                      ('import', ('mujoco',)), ('import', ('libero.envs',))])
def test_child_audit_rejects_network_and_simulator(event, args):
    with pytest.raises(RuntimeError):
        probe.audit_no_network_or_simulator(event, args)


def test_real_type_package_imports_are_allowed_without_environment():
    probe.audit_no_network_or_simulator('import', ('gymnasium',))
    probe.audit_no_network_or_simulator('import', ('torch',))


def test_source_script_must_be_fingerprinted_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.runner, 'validate_plan', lambda *args, **kwargs: ({'code_files': []}, {}, {}))
    with pytest.raises(probe.runner.GateError, match='not included in the frozen plan'):
        probe.validate_inputs(tmp_path / 'plan.json', tmp_path)


def test_policy_config_uses_frozen_model_overrides_and_requires_arm_parity(tmp_path):
    import yaml
    (tmp_path / 'configs').mkdir()
    model_root = tmp_path / 'model'
    model_root.mkdir()
    defaults = {'pretrained_path': str(model_root), 'text_encoder': str(model_root),
                'vision_encoder': str(model_root), 'weight_variant': 'ema',
                'num_inference_steps': 5, 'control_frequency': 20,
                'fail_on_zero_language_embedding': True}
    (tmp_path / 'configs/policy.yaml').write_text(yaml.safe_dump({'rdt': defaults}))
    values = {'policy.type': 'rdt', 'device': 'cuda', 'policy.rdt.num_inference_steps': None}
    profiles = {'profiles': {name: {'static_override_values': dict(values)} for name in ('Q0', 'C0')}}
    result = probe.policy_configuration(tmp_path, profiles)
    assert result == {**defaults, 'num_inference_steps': None}
    profiles['profiles']['C0']['static_override_values']['policy.rdt.num_inference_steps'] = 7
    with pytest.raises(probe.runner.GateError, match='configurations differ'):
        probe.policy_configuration(tmp_path, profiles)


def test_validation_fingerprints_unused_codex_without_invoking_provider(tmp_path, monkeypatch):
    cli = tmp_path / 'codex'
    cli.write_bytes(b'frozen-public-executable')
    plan = {'code_files': [{'path': probe.SCRIPT_RELATIVE, 'sha256': probe.runner.digest(Path(probe.__file__))}]}
    runtime = {'frozen_stage_provider': {'backend': 'codex_cli', 'cli_path': str(cli),
                                        'cli_sha256': probe.runner.digest(cli)}}
    monkeypatch.setattr(probe.runner, 'validate_plan', lambda *args, **kwargs: (plan, {}, runtime))
    monkeypatch.setattr(probe.runner, 'stage_overrides', lambda runtime: {})
    monkeypatch.setattr(probe, 'policy_configuration', lambda *args: {'frozen': 'policy'})
    monkeypatch.setattr(probe.subprocess, 'run', lambda *args, **kwargs: pytest.fail('must not invoke provider'))
    assert probe.validate_inputs(tmp_path / 'plan.json', tmp_path) == (plan, runtime, {'frozen': 'policy'})
    cli.write_bytes(b'changed-executable')
    with pytest.raises(probe.runner.GateError, match='fingerprint changed'):
        probe.validate_inputs(tmp_path / 'plan.json', tmp_path)


def test_synthetic_images_and_state_are_deterministic():
    import numpy as np
    first, second = probe.synthetic_observation(np), probe.synthetic_observation(np)
    for name in ('agentview_image', 'robot0_eye_in_hand_image', 'robot0_joint_pos', 'robot0_gripper_qpos'):
        assert np.array_equal(first[name], second[name])
    assert first['agentview_image'].shape == (256, 256, 3)
    assert first['agentview_image'].dtype == np.uint8
    assert first['task'] == probe.SYNTHETIC_TASK
