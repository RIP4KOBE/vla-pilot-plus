"""CPU-only runner contracts: initialization, import origin, and cohort validity."""
from __future__ import annotations

from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml

from scripts import audit_steering, steering_runtime, steering_worker


ROOT = Path(__file__).resolve().parents[1]


def machine():
    return dict(gpu=2, egl_device_id=1, allocator_limit_gib=48,
                rdt_checkpoint='/assets/rdt', text_encoder='/assets/text/snapshot',
                vision_encoder='/assets/vision/snapshot',
                libero_root=str(ROOT / 'third_party/libero_pro'),
                libero_config='/assets/libero_config', torch_home='/assets/torch')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


def test_subset_keeps_task_seed_identity_and_initialization_contract(tmp_path):
    cfg = steering_runtime.load_config(machine(), method='eds',
                                       output_dir=tmp_path / 'output', tasks=[9, 1])
    assert cfg['backend']['libero']['task_ids_filter'] == [1, 9]
    assert cfg['main']['episode_seed_schedule'] == [235, 548]
    assert cfg['main']['episode_num'] == 2
    assert cfg['main']['episode_start_index'] == 0
    assert cfg['main']['episode_policy_rng_mode'] == 'continuous'
    fixture = Path(cfg['main']['episode_rng_fixture_manifest'])
    assert steering_runtime.digest(fixture) == cfg['main']['episode_rng_fixture_manifest_sha256']
    assert cfg['hydra']['job']['chdir'] is False
    assert cfg['main']['cached_functions_dir'] is None
    assert cfg['policy']['rdt']['num_inference_steps'] is None
    assert cfg['policy']['rdt']['action_chunk_horizon'] == 8
    assert cfg['backend']['libero']['max_episode_steps'] == 720
    assert cfg['main']['eds_config']['population_size'] == 16
    assert cfg['main']['eds_config']['cem_iters'] == 10
    assert cfg['main']['eds_config']['temperature'] == .1
    assert cfg['main']['eds_config']['initial_sampling_mode'] == 'rbf_diverse_denoise'
    assert cfg['main']['eds_config']['truncated_rollout_mode'] == 'rbf_diverse'
    assert cfg['main']['eds_config']['qd_archive_mode'] == 'none'


@pytest.mark.parametrize('tasks', [[], [0, 0], [-1], [10]])
def test_invalid_task_windows_are_rejected(tmp_path, tasks):
    with pytest.raises(ValueError, match='Tasks must'):
        steering_runtime.load_config(machine(), method='eds', output_dir=tmp_path, tasks=tasks)


@pytest.mark.parametrize('method', ['vls', 'eds_qd'])
def test_unreleased_algorithms_cannot_enter_eds_migration_cohort(tmp_path, method):
    with pytest.raises(ValueError, match='not yet released'):
        steering_runtime.load_config(machine(), method=method, output_dir=tmp_path)


def test_runtime_import_search_resolves_owned_vendor_trees():
    env = steering_runtime.runtime_environment(machine(), base={**os.environ,
        'PYTHONPATH': '/unrelated/research/checkout', 'CUDA_VISIBLE_DEVICES': ''})
    # find_spec reads module origins without importing Torch, models, or a simulator.
    code = """import importlib.util, json, sys
names = ['lerobot', 'libero', 'scripts.maniskill_model']
result = {}
for name in names:
    spec = importlib.util.find_spec(name)
    result[name] = [spec.origin] if spec.origin else list(spec.submodule_search_locations)
assert 'torch' not in sys.modules
print(json.dumps(result))
"""
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                            text=True, capture_output=True, check=True, timeout=20)
    origins = json.loads(result.stdout)
    expected = {'lerobot': ROOT / 'third_party/lerobot/src',
                'libero': ROOT / 'third_party/libero_pro',
                'scripts.maniskill_model': ROOT / 'third_party/rdt'}
    for name, paths in origins.items():
        assert paths and all(Path(path).resolve().is_relative_to(expected[name]) for path in paths)


def worker_fixture(tmp_path, monkeypatch, *, cuda=True, hydra_args=()):
    config = tmp_path / 'resolved-config.yaml'
    config.write_text('{}\n')
    write_json(tmp_path / 'manifest.json',
               dict(config_sha256=steering_runtime.digest(config), source_sha256={'main.py': 'test'}))
    calls = []
    monkeypatch.setenv('VLA_CODEX_ONLY', '1')
    monkeypatch.setenv('VLA_STEERING_ALLOCATOR_GIB', '48')
    monkeypatch.setattr(sys, 'argv', ['worker', str(config), *hydra_args])
    monkeypatch.setattr(steering_runtime, 'source_unchanged',
                        lambda _: calls.append('source') or True)
    fake_cuda = SimpleNamespace(
        is_available=lambda: calls.append('cuda') or cuda,
        get_device_properties=lambda _: SimpleNamespace(total_memory=80 * 1024**3),
        set_per_process_memory_fraction=lambda value, device: calls.append(('memory', value, device)))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=fake_cuda))
    target = lambda: calls.append('entry')
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(main=SimpleNamespace(__wrapped__=target)))
    def decorate(**kwargs):
        calls.append(('hydra', kwargs))
        return lambda function: function
    monkeypatch.setitem(sys.modules, 'hydra', SimpleNamespace(main=decorate))
    from core import episode_rng_hooks
    monkeypatch.setattr(episode_rng_hooks, 'install', lambda module: calls.append('rng_hooks'))
    return config, calls


def test_worker_installs_two_phase_hooks_before_entering_hydra(tmp_path, monkeypatch):
    config, calls = worker_fixture(tmp_path, monkeypatch)
    steering_worker.main()
    assert calls[:4] == ['source', 'cuda', ('memory', .6, 0), 'rng_hooks']
    assert calls[4] == ('hydra', dict(version_base=None, config_path=str(tmp_path),
                                    config_name='resolved-config'))
    assert calls[5] == 'entry'
    assert sys.argv == [str(ROOT / 'main.py')]


def test_worker_refuses_cpu_substitution_before_importing_main(tmp_path, monkeypatch):
    _, calls = worker_fixture(tmp_path, monkeypatch, cuda=False)
    with pytest.raises(RuntimeError, match='CUDA is unavailable'):
        steering_worker.main()
    assert calls == ['source', 'cuda']


def test_worker_rejects_changed_config_before_cuda_or_hooks(tmp_path, monkeypatch):
    config, calls = worker_fixture(tmp_path, monkeypatch)
    config.write_text('changed: true\n')
    with pytest.raises(RuntimeError, match='Frozen config'):
        steering_worker.main()
    assert calls == []


def test_worker_config_print_does_not_touch_cuda(tmp_path, monkeypatch):
    _, calls = worker_fixture(tmp_path, monkeypatch, cuda=False, hydra_args=['--cfg', 'job'])
    steering_worker.main()
    assert 'cuda' not in calls and 'source' not in calls
    assert calls[0] == 'rng_hooks'
    assert sys.argv[-2:] == ['--cfg', 'job']


@pytest.fixture
def cohort(tmp_path):
    folder = tmp_path / 'cohort'
    output = folder / 'output'
    config = steering_runtime.load_config(machine(), method='eds', output_dir=output, tasks=[0, 1])
    folder.mkdir()
    config_path = folder / 'resolved-config.yaml'
    config_path.write_text(yaml.safe_dump(config))
    source = folder / 'source/main.py'
    source.parent.mkdir()
    source.write_text('# source snapshot\n')
    write_json(folder / 'manifest.json', dict(method='eds', tasks=[0, 1], seeds=[44, 235],
        config_sha256=steering_runtime.digest(config_path),
        source_sha256={'main.py': steering_runtime.digest(source)}))
    write_json(folder / 'status.json', dict(state='finished', exit_code=0, source_unchanged=True))
    fixture = json.loads((ROOT / 'tests/fixtures/steering_rng/fixture-manifest.json').read_text())
    records = {name: [] for name in ['stage_events', 'episode_metadata', 'episode_compute',
                                     'eds_metrics', 'episode_rng_events']}
    for episode, (task, seed) in enumerate([(0, 44), (1, 235)]):
        identity = dict(episode_id=episode, task_id=task, episode_seed=seed)
        records['episode_metadata'].append(identity)
        records['episode_compute'].append(dict(identity, outcome='completed'))
        records['stage_events'].append(dict(identity, global_step=0,
            query_status='ok', query_ok=True, guidance_after=True,
            reward_capability={'available': True}, reward_reference_reset=False,
            stage_before=1, stage_after=1, completion_confirmed=False,
            visual_hold=False, contact_phase='approach', contact_until=None,
            fused_hold_enabled=True, fused_hold_established=False, fused_hold_source=None,
            failed_contact_recheck=dict(enabled=True, armed=False, seed_step=None,
                                       confirmed=False, confirmation=None)))
        records['eds_metrics'].append(dict(episode=episode, task_id=task, global_step=0,
            guidance_type='eds', population_size=16, population_size_observed=16,
            eds_iters_executed=10, cem_iters=10, qd_archive_enabled=False,
            qd_archive_active_for_chunk=False, initial_sampling_mode='rbf_diverse_denoise',
            initial_diversity_steps=4, initial_diversity_fallback_used=False,
            rollout_diversity_mode='rbf_diverse', rollout_diversity_fallback_used=False,
            rollout_diversity_iters_applied=10,
            rollout_rbf_steps_by_iter=[2, 2, 2, 2, 2, 1, 1, 1, 1, 1],
            execution_horizon_resolved=8, score_call_count=11, search_evaluation_count=176))
        for phase in ['prepare', 'rollout']:
            entry = fixture['fixtures'][f'{task}:{phase}']
            records['episode_rng_events'].append({name: deepcopy(entry[name])
                for name in ['metadata', 'sha256', 'state_signature']})
        ep = output / f'episode_{episode + 1}'
        ep.mkdir(parents=True)
        (ep / f'episode_{episode + 1}_fail_agentview.mp4').write_bytes(b'test-video-marker')
        write_json(ep / 'vlm_agent/target_distance_reward.json',
                   dict(valid=True, contract='target_distance'))
    for name, entries in records.items():
        write_rows(output / f'eds_eval/{name}.jsonl', entries)
    (output / 'results.txt').write_text('Success count: 0/2\n')
    return folder, records


def test_valid_zero_success_cohort_is_separate_from_performance_acceptance(cohort):
    result = audit_steering.audit(cohort[0])
    assert result['valid'] is True, result['checks']
    assert result['successes'] == 0 and result['completed'] == result['planned'] == 2


@pytest.mark.parametrize('corruption', [
    'worker_exit', 'source_changed', 'config_changed', 'bad_json', 'missing_task_queries',
    'episode_exception', 'wrong_compute_identity', 'rng_changed', 'snapshot_changed',
    'missing_metadata', 'error_video', 'no_candidate_search'])
def test_invalid_cohort_cannot_be_reported_as_valid_zero_success(cohort, corruption):
    folder, records = cohort
    if corruption in ['worker_exit', 'source_changed']:
        status = json.loads((folder / 'status.json').read_text())
        status['exit_code' if corruption == 'worker_exit' else 'source_unchanged'] = (
            1 if corruption == 'worker_exit' else False)
        write_json(folder / 'status.json', status)
    elif corruption == 'config_changed':
        (folder / 'resolved-config.yaml').write_text('modified: true\n')
    elif corruption == 'bad_json':
        with (folder / 'output/eds_eval/stage_events.jsonl').open('a') as stream:
            stream.write('{truncated\n')
    elif corruption == 'snapshot_changed':
        (folder / 'source/main.py').write_text('# changed\n')
    elif corruption == 'error_video':
        episode = folder / 'output/episode_2'
        (episode / 'episode_2_fail_agentview.mp4').rename(episode / 'episode_2_error_agentview.mp4')
    else:
        if corruption == 'missing_task_queries':
            records['stage_events'].pop()
            records['eds_metrics'].pop()
        elif corruption == 'episode_exception':
            records['episode_compute'][1]['outcome'] = 'execution_error'
        elif corruption == 'wrong_compute_identity':
            records['episode_compute'][1]['task_id'] = 0
        elif corruption == 'rng_changed':
            records['episode_rng_events'][2]['state_signature'] = 'wrong'
        elif corruption == 'missing_metadata':
            records['episode_metadata'].pop()
        elif corruption == 'no_candidate_search':
            records['eds_metrics'].clear()
        for name, entries in records.items():
            write_rows(folder / f'output/eds_eval/{name}.jsonl', entries)
    result = audit_steering.audit(folder)
    assert result['valid'] is False, (corruption, result['checks'])


def test_exit_code_override_cannot_erase_worker_failure(cohort):
    folder, _ = cohort
    write_json(folder / 'status.json', dict(state='finished', exit_code=1, source_unchanged=True))
    assert audit_steering.audit(folder, exit_code=0)['valid'] is False
