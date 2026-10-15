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


@pytest.mark.parametrize('method', ['vls', 'eds', 'eds_qd'])
def test_modes_share_online_contract_and_route_mechanism(tmp_path, method):
    cfg = steering_runtime.load_config(machine(), method=method,
                                       output_dir=tmp_path / 'output', tasks=[9, 1])
    assert cfg['steering']['method'] == method
    assert cfg['main']['guidance_type'] == ('vls' if method == 'vls' else 'eds')
    assert cfg['main']['eds_config']['qd_archive_mode'] == ('grid_archive' if method == 'eds_qd' else 'none')
    assert cfg['main']['cached_functions_dir'] is None
    assert cfg['perception']['gemini']['backend'] == 'codex_cli'
    assert cfg['perception']['gemini']['model'] == 'gpt-6-astra'
    assert cfg['perception']['gemini']['reasoning_effort'] == 'ultra'
    assert cfg['perception']['vlm_agent']['reasoning_effort'] == 'ultra'
    for role in ('gemini', 'vlm_agent'):
        assert cfg['perception'][role]['transport_retry_count'] == 8
        assert cfg['perception'][role]['transport_retry_backoff_seconds'] == 30.0
    assert cfg['main']['episode_seed_schedule'] == [235, 548]
    assert cfg['main']['eds_eval']['job_id'] == tmp_path.name
    assert cfg['main']['eds_eval']['method_label'] == method
    if method == 'vls':
        assert cfg['backend']['libero']['task_guide_scales'] == [80., 80.]
        assert cfg['main']['vls_config']['sample_batch_size'] == 20
        assert cfg['main']['vls_config']['guide_scale'] == 80.
    if method == 'eds_qd':
        assert cfg['main']['eds_config']['qd_parent_sampling'] == 'sparse_priority'


def test_unknown_mode_and_misspelled_profile_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='Unknown steering method'):
        steering_runtime.load_config(machine(), method='edz', output_dir=tmp_path)
    with pytest.raises(ValueError, match='Unknown steering profile setting'):
        steering_runtime._merge_profile({'main': {}}, {'main': {'populaton_size': 16}})


def test_source_freeze_detects_new_runtime_files(tmp_path, monkeypatch):
    monkeypatch.setattr(steering_runtime, 'ROOT', tmp_path)
    (tmp_path / 'main.py').write_text('# main\n')
    (tmp_path / 'core').mkdir()
    frozen = steering_runtime.source_manifest()
    assert steering_runtime.source_unchanged(frozen)
    (tmp_path / 'core/injected.py').write_text('# another import\n')
    assert not steering_runtime.source_unchanged(frozen)


def test_evaluation_directory_cannot_escape_cohort(tmp_path):
    cohort = tmp_path / 'cohort'
    cohort.mkdir()
    (cohort / 'link').symlink_to(tmp_path, target_is_directory=True)
    for value in ['../outside', str(tmp_path), 'link/outside']:
        with pytest.raises(ValueError, match='relative|escapes'):
            steering_runtime.evaluation_directory(cohort, {'evaluation_directory': value})


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


# The following are offline wrapper unit fixtures. Provider/contract details are
# tested independently by tests/steering_audit; no fixture attests a real cohort.
def prepare_v2_cohort(cohort, monkeypatch, method='eds'):
    import shutil
    folder, records = cohort
    (folder / 'output/eds_eval').rename(folder / 'output/evaluation')
    cfg = steering_runtime.load_config(machine(), method=method, output_dir=folder/'output', tasks=[0,1])
    cfgpath=folder/'resolved-config.yaml';cfgpath.write_text(yaml.safe_dump(cfg))
    required=['configs/evaluation/libero_object_swap.yaml',f'configs/steering/{method}.yaml',
        'scripts/steering_runtime.py','scripts/steering_worker.py','scripts/run_steering.py',
        'scripts/steering_model_assets.py','scripts/steering_model_assets_manifest.json',
        'scripts/steering_assets_manifest.json','scripts/prepare_steering_assets.py','core/episode_rng_hooks.py','core/rdt_policy_steer.py','core/qd_ed.py','core/fkd_class.py']
    required.extend(['scripts/steering_dependency_compat.py',
        'scripts/dependency_patches/robosuite-1.4.0.json',
        'scripts/dependency_patches/robosuite-binding.patch',
        'scripts/dependency_patches/robosuite-egl.patch'])
    for name in required:
        target=folder/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    source={name:steering_runtime.digest(folder/'source'/name) for name in required}
    identity=json.loads((ROOT/'scripts/steering_model_assets_manifest.json').read_text())
    assets=dict(schema='steering_model_verification_v1',valid=True,files=[{k:r[k] for k in ('root','path','bytes','sha256')} for r in identity['files']],
        files_checked=len(identity['files']),bytes_hashed=sum(r['bytes'] for r in identity['files']),
        expected_manifest_sha256=source['scripts/steering_model_assets_manifest.json'],
        verifier_sha256=source['scripts/steering_model_assets.py'],
        selected=dict(rdt_weight='/assets/rdt/ema/model.safetensors',rdt_config='/assets/rdt/config.json',
            text_encoder_weight='/assets/text/snapshot/pytorch_model.bin',vision_encoder_weight='/assets/vision/snapshot/model.safetensors'),
        normalization_checked=True,normalization_files=identity['repository_contract']['normalization_files'])
    # Synthetic preflight attestations test binding, not actual asset availability.
    env=dict(model_assets=assets,submodules={k:dict(commit=v,dirty=False) for k,v in audit_steering.SUBMODULE_PINS.items()},
        imported_packages={name:dict(module_version='synthetic-test',file='/synthetic/'+name+'.py',sha256='0'*64) for name in audit_steering.IMPORTED_MODULES},
        libero=dict(valid=True,root=machine()['libero_root'],manifest_sha256=source['scripts/steering_assets_manifest.json']),
        libero_paths=dict(valid=True,config_path='/assets/libero_config/config.yaml',config_sha256='0'*64,
            bindings={k:str(Path(machine()['libero_root'])/'libero/libero'/v) for k,v in
                (('benchmark_root',''),('assets','assets'),('bddl_files','bddl_files'),('init_states','init_files'))}),
        rng=dict(valid=True,fixture_count=20,sha256=cfg['main']['episode_rng_fixture_manifest_sha256']))
    compat=json.loads((ROOT/'scripts/dependency_patches/robosuite-1.4.0.json').read_text())
    env['runtime_compatibility']=dict(valid=True,distribution='robosuite',version='1.4.0',
        root='/synthetic/robosuite',manifest_sha256=source['scripts/dependency_patches/robosuite-1.4.0.json'],
        files={name:row['patched_sha256'] for name,row in compat['files'].items()})
    write_json(folder/'environment.json',env)
    (folder/'local-config.yaml').write_text(yaml.safe_dump(machine()))
    manifest=dict(schema='steering_cohort_v2',method=method,tasks=[0,1],seeds=[44,235],
        evaluation_directory='output/evaluation',code_root=str(ROOT),source_sha256=source,
        local_config_sha256=steering_runtime.digest(folder/'local-config.yaml'),physical_gpu=2,egl_device_id=1,
        config_sha256=steering_runtime.digest(cfgpath),environment_sha256=steering_runtime.digest(folder/'environment.json'),
        provider='codex_cli',model='gpt-6-astra',reasoning_effort=cfg['perception']['gemini']['reasoning_effort'],online_stage=True,fresh_reward=True)
    write_json(folder/'manifest.json',manifest)
    if method=='eds':
        m=json.loads((ROOT/'tests/fixtures/steering_qd/eds-control-firstchunk.json').read_text())
    elif method=='eds_qd':
        spec=importlib.util.spec_from_file_location('qd_wrapper_fixture',ROOT/'tests/steering_audit/test_audit_qd_mechanism.py')
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture);m,_=fixture.synthetic()
    else:
        m=synthetic_vls_profile_metric(cfg)
    if method=='eds_qd':
        m.update(initial_sampling_mode='rbf_diverse_denoise',initial_diversity_steps=4,initial_diversity_fallback_used=False,
            rollout_diversity_mode='rbf_diverse',rollout_diversity_fallback_used=False,rollout_diversity_iters_applied=10,
            rollout_rbf_steps_by_iter=json.loads((ROOT/'tests/fixtures/steering_qd/eds-control-firstchunk.json').read_text())['rollout_rbf_steps_by_iter'])
    records['eds_metrics' if method!='vls' else 'vls_metrics']=[dict(deepcopy(m),episode=i,task_id=i,episode_seed=seed,global_step=0,
        suite='libero_object_swap',method_label=method,job_id=folder.name) for i,seed in enumerate([44,235])]
    if method=='vls':
        records['eds_metrics']=[]
        for event in records['stage_events']:event.update(guidance_before=True,normalized_reward_diagnostic=0.)
    for row in records['episode_compute']:row.update(guided_chunks=1,unguided_chunks=0)
    for name,rows in records.items():write_rows(folder/f'output/evaluation/{name}.jsonl',rows)
    monkeypatch.setattr(audit_steering,'audit_task_contract',lambda *a,**kw:dict(task_contract_valid=True,task_evidence_complete=True,summary={'pass':1,'fail':0,'pending':0}))
    return folder,records,cfg


def synthetic_vls_profile_metric(cfg):
    """Explicit synthetic public-profile record; not a production execution result."""
    m=json.loads((ROOT/'tests/fixtures/steering_vls/cpu-small-model-metrics.json').read_text())
    c=cfg['main']['vls_config'];b=c['sample_batch_size']
    m.update(sample_batch_size_observed=b,guide_scale=c['guide_scale'],diversity_scale=c['diversity_scale'],
             start_ratio=c['start_ratio'],sigmoid_k=c['sigmoid_k'],sigmoid_x0=c['sigmoid_x0'],resolved_start_timestep=799)
    ge=deepcopy(m['gradient']['events'][0]);ge.update(scale=1.)
    m['gradient'].update(attempted=4,applied=4,events=[dict(ge,timestep=t) for t in [799,599,400,200]])
    re=deepcopy(m['rbf']['events'][0]);re.update(timestep=999,scale=c['diversity_scale'])
    m['rbf'].update(attempted=1,applied=1,events=[re])
    events=[dict(timestep=t,scored=(i==0),resampled=False,ess=(float(b) if i==0 else None),
        parent_indices=None,terminal_sort_indices=None,terminal=False,reason=('ess_sufficient' if i==0 else 'not_scheduled')) for i,t in enumerate([799,599,400])]
    m['fkd'].update(config=deepcopy(c['fkd']),diagnostics=dict(calls=3,score_opportunities=1,actual_resamples=0,ess_skips=1,events=events))
    m['compute_delta'].update(model_batch_rows=b*5,denoising_step_batch_rows=b*5,model_forward_batch_sizes=[b]*5,rbf_gradient_calls=1,rbf_gradient_batch_rows=b)
    return m


@pytest.mark.parametrize('method',['eds','eds_qd','vls'])
def test_v2_valid_recorded_method_and_zero_success_are_valid(cohort,monkeypatch,method):
    folder,_,_=prepare_v2_cohort(cohort,monkeypatch,method)
    result=audit_steering.audit(folder)
    assert result['valid'],{k:v for k,v in result['checks'].items() if not v}
    assert result['scope']=='full_v2_contract_and_recorded_method_evidence'
    assert result['full_audit_performed'] and result['successes']==0
    detail=result['method_audit'];assert detail['chunks']==2 and detail['failed_chunks']==0
    assert steering_runtime.digest(Path(detail['path']))==detail['sha256']
    for task in result['tasks']:
        assert task['extended_contract']['valid']
        assert steering_runtime.digest(Path(task['extended_contract']['path']))==task['extended_contract']['sha256']


def test_legacy_scope_and_read_only_audit_preserve_old_result(cohort):
    folder,_=cohort;old=folder/'audit.json';old.write_bytes(b'immutable old acceptance\n')
    result=audit_steering.audit(folder,write=False)
    assert result['valid'] and result['scope']=='legacy_basic_only' and not result['full_audit_performed']
    assert old.read_bytes()==b'immutable old acceptance\n'
    alternate=folder/'recheck.json';audit_steering.audit(folder,output_path=alternate)
    assert alternate.exists() and old.read_bytes()==b'immutable old acceptance\n'


@pytest.mark.parametrize('case', ['ultra', 'historical_low', 'manifest_mismatch',
                                  'reward_mismatch', 'stage_mismatch', 'unsupported'])
def test_v2_reasoning_effort_bound_to_both_clients_and_frozen_protocol(cohort, monkeypatch, case):
    folder, _, cfg = prepare_v2_cohort(cohort, monkeypatch)
    manifest = json.loads((folder/'manifest.json').read_text())
    frozen_path = folder/'source/configs/evaluation/libero_object_swap.yaml'
    frozen = yaml.safe_load(frozen_path.read_text())
    if case in ('historical_low', 'unsupported'):
        effort = 'low' if case == 'historical_low' else 'unapproved_effort'
        for role in ('gemini', 'vlm_agent'):
            cfg['perception'][role]['reasoning_effort'] = effort
            frozen['perception'][role]['reasoning_effort'] = effort
        manifest['reasoning_effort'] = effort
    elif case == 'manifest_mismatch':
        manifest['reasoning_effort'] = 'low'
    elif case in ('reward_mismatch', 'stage_mismatch'):
        role = 'vlm_agent' if case == 'reward_mismatch' else 'gemini'
        cfg['perception'][role]['reasoning_effort'] = 'low'
        frozen['perception'][role]['reasoning_effort'] = 'low'
    frozen_path.write_text(yaml.safe_dump(frozen))
    manifest['source_sha256'][str(frozen_path.relative_to(folder/'source'))] = steering_runtime.digest(frozen_path)
    config_path = folder/'resolved-config.yaml'; config_path.write_text(yaml.safe_dump(cfg))
    manifest['config_sha256'] = steering_runtime.digest(config_path)
    write_json(folder/'manifest.json', manifest)
    result = audit_steering.audit(folder, write=False)
    assert result['checks']['fixed_protocol_config']
    assert result['checks']['provider_manifest'] == (case in ('ultra', 'historical_low'))
    assert result['valid'] == (case in ('ultra', 'historical_low'))


@pytest.mark.parametrize('case',['missing_metric','duplicate_metric','extra_metric','wrong_seed','wrong_task','corrupt_chunk','bad_json','missing_new_directory','bad_identity_shape','bad_method_label','bad_job','sampler_fallback'])
def test_v2_failed_or_missing_chunks_are_never_silently_dropped(cohort,monkeypatch,case):
    folder,records,_=prepare_v2_cohort(cohort,monkeypatch)
    rows=records['eds_metrics']
    if case=='missing_metric':rows.pop()
    elif case=='duplicate_metric':rows.append(deepcopy(rows[0]))
    elif case=='extra_metric':rows.append(dict(deepcopy(rows[0]),global_step=1000))
    elif case=='wrong_seed':rows[0]['episode_seed']=999
    elif case=='wrong_task':rows[0]['task_id']=9
    elif case=='corrupt_chunk':rows[0]['score_call_count']=12
    elif case=='bad_identity_shape':rows[0]['task_id']=[0]
    elif case=='bad_method_label':rows[0]['method_label']='wrong'
    elif case=='bad_job':rows[0]['job_id']='other_run'
    elif case=='sampler_fallback':rows[0]['initial_diversity_fallback_used']=True
    write_rows(folder/'output/evaluation/eds_metrics.jsonl',rows)
    if case=='bad_json':
        with (folder/'output/evaluation/eds_metrics.jsonl').open('a') as f:f.write('{bad\n')
    if case=='missing_new_directory':(folder/'output/evaluation').rename(folder/'output/eds_eval')
    result=audit_steering.audit(folder)
    assert not result['valid'],case
    detail=json.loads(Path(result['method_audit']['path']).read_text())
    assert len(detail['chunks'])==(len(rows)+(case=='bad_json') if case!='missing_new_directory' else 0)
    if case in ('corrupt_chunk','bad_json'):assert result['method_audit']['failed_chunks']>=1


@pytest.mark.parametrize('case',['raised','pending','failed'])
def test_v2_task_contract_errors_are_persisted_fail_closed(cohort,monkeypatch,case):
    folder,_,_=prepare_v2_cohort(cohort,monkeypatch)
    def contract(*args,**kwargs):
        if case=='raised':raise ValueError('Malformed input')
        return dict(task_contract_valid=case=='pending',task_evidence_complete=case!='pending',summary={case:1})
    monkeypatch.setattr(audit_steering,'audit_task_contract',contract)
    result=audit_steering.audit(folder)
    assert not result['valid'] and not result['checks']['extended_task_contracts']
    for row in result['tasks']:
        report=json.loads(Path(row['extended_contract']['path']).read_text())
        assert not row['extended_contract']['valid']
        if case=='raised':assert report['checks']['evidence_structure']['status']=='fail'


@pytest.mark.parametrize('case',['asset_valid','asset_hash','asset_manifest','asset_loader','normalization','dependency_missing','dependency_hash','dirty_vendor','vendor_pin','libero','rng','environment_hash','profile','profile_seed','provider','source_omitted'])
def test_v2_source_asset_protocol_corruption_is_rejected(cohort,monkeypatch,case):
    folder,records,cfg=prepare_v2_cohort(cohort,monkeypatch)
    env=json.loads((folder/'environment.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
    if case=='asset_valid':env['model_assets']['valid']=False
    elif case=='asset_hash':env['model_assets']['files'][0]['sha256']='f'*64
    elif case=='asset_manifest':env['model_assets']['expected_manifest_sha256']='f'*64
    elif case=='asset_loader':env['model_assets']['selected']['rdt_weight']='/wrong/model'
    elif case=='normalization':env['model_assets']['normalization_files'][0]['sha256']='f'*64
    elif case=='dependency_missing':env['imported_packages'].pop('numpy')
    elif case=='dependency_hash':env['imported_packages']['numpy']['sha256']='missing'
    elif case=='dirty_vendor':env['submodules']['rdt']['dirty']=True
    elif case=='vendor_pin':env['submodules']['lerobot']['commit']='f'*40
    elif case=='libero':env['libero']['valid']=False
    elif case=='rng':env['rng']['fixture_count']=19
    elif case=='profile':cfg['main']['eds_config']['temperature']=.2
    elif case=='profile_seed':
        manifest['seeds'][0]=cfg['main']['episode_seed_schedule'][0]=1000
        for name in ('stage_events','episode_metadata','episode_compute'):records[name][0]['episode_seed']=1000
        for name,rows in records.items():write_rows(folder/f'output/evaluation/{name}.jsonl',rows)
    elif case=='provider':manifest['model']='other'
    elif case=='source_omitted':manifest['source_sha256'].pop('core/qd_ed.py')
    write_json(folder/'environment.json',env)
    if case!='environment_hash':manifest['environment_sha256']=steering_runtime.digest(folder/'environment.json')
    else:manifest['environment_sha256']='f'*64
    (folder/'resolved-config.yaml').write_text(yaml.safe_dump(cfg));manifest['config_sha256']=steering_runtime.digest(folder/'resolved-config.yaml')
    write_json(folder/'manifest.json',manifest)
    assert not audit_steering.audit(folder)['valid'],case


def vls_cpu_example():
    m=json.loads((ROOT/'tests/fixtures/steering_vls/cpu-small-model-metrics.json').read_text())
    cfg={'main':{'vls_config':dict(sample_batch_size=4,guide_scale=1.,use_diversity=True,diversity_scale=1.,
        start_ratio=.4,sigmoid_k=12.,sigmoid_x0=.7,use_fkd=True,fkd=deepcopy(m['fkd']['config']))},
        'policy':{'rdt':{'num_inference_steps':5,'action_chunk_horizon':8}}}
    return m,cfg


def test_real_cpu_vls_telemetry_fixture_matches_schema():
    m,cfg=vls_cpu_example();r=audit_steering.audit_vls_chunk(m,cfg)
    assert r['recorded_mechanism_valid'],r['checks']


@pytest.mark.parametrize('case',['nan_norm','infinite_raw','negative_masknorm','missing_norm','duplicate_timestep','wrong_partition','wrong_start','bad_range','missing_step','wrong_scale','fake_zero','unscheduled_score','fake_terminal','bad_parent','fake_ess_skip','wrong_score_source','fkd_terminal','wrong_budget','bad_progress'])
def test_vls_numeric_schedule_and_lineage_corruption_rejected(case):
    m,cfg=vls_cpu_example()
    if case=='nan_norm':m['gradient']['events'][0]['norm']=float('nan')
    elif case=='infinite_raw':m['gradient']['events'][0]['raw_reward']=float('inf')
    elif case=='negative_masknorm':m['rbf']['events'][0]['masked_norm']=-1
    elif case=='missing_norm':m['rbf']['events'][0].pop('norm')
    elif case=='duplicate_timestep':m['gradient']['events'][0]['timestep']=1
    elif case=='wrong_partition':m['rbf']['events'][1]['timestep']=2
    elif case=='wrong_start':m['resolved_start_timestep']=1
    elif case=='bad_range':m['rbf']['events'][0]['timestep']=1000
    elif case=='missing_step':m['gradient']['events'].pop();m['gradient'].update(attempted=2,applied=2)
    elif case=='wrong_scale':m['gradient']['events'][0]['scale']=float('nan')
    elif case=='fake_zero':m['gradient']['events'][0]['status']='zero';m['gradient']['zero']=1
    elif case=='unscheduled_score':m['fkd']['config']['resample_frequency']=cfg['main']['vls_config']['fkd']['resample_frequency']=5
    elif case=='fake_terminal':m['fkd']['diagnostics']['events'][0]['terminal']=True
    elif case=='bad_parent':m['fkd']['diagnostics']['events'][0]['parent_indices'][0]=4
    elif case=='fake_ess_skip':m['fkd']['diagnostics']['events'][0]['reason']='ess_sufficient'
    elif case=='wrong_score_source':m['selection']['score_source']='extra_selected_score'
    elif case=='fkd_terminal':m['selection']['source']='fkd_terminal'
    elif case=='wrong_budget':m['compute_delta']['model_forward_calls']=6
    elif case=='bad_progress':m['outer_reward']['progress']=.5
    assert not audit_steering.audit_vls_chunk(m,cfg)['recorded_mechanism_valid'],case


def test_vls_legal_zero_gradient_and_finite_tiny_norm():
    m,cfg=vls_cpu_example();m['gradient']['zero']=1
    m['gradient']['events'][0].update(status='zero',norm=1e-9,masked_norm=0.)
    assert audit_steering.audit_vls_chunk(m,cfg)['recorded_mechanism_valid']


@pytest.mark.parametrize('case',['stable','changed_reference','unguided_stage_reset','missed_stage_reset','arbitrary_first_reference','wrong_diagnostic','stale_unguided_diagnostic','unguided_same_stage'])
def test_vls_reference_continuity_obeys_stage_changes_including_unguided(case):
    events=[dict(episode_id=0,task_id=0,global_step=i*8,reward_reference_reset=False,guidance_before=True,guidance_after=True,
        normalized_reward_diagnostic=[0.,0.,.5][i]) for i in range(3)]
    metrics=[dict(episode=0,task_id=0,global_step=i*8,selection={'raw_score':raw},outer_reward={'reference':-10.,'progress':[0.,.5,.6][i]}) for i,raw in enumerate([-10.,-5.,-4.])]
    if case=='changed_reference':metrics[1]['outer_reward']['reference']=-5.
    elif case=='arbitrary_first_reference':metrics[0]['outer_reward']['reference']=-20.
    elif case=='wrong_diagnostic':events[1]['normalized_reward_diagnostic']=.42
    elif case in ('unguided_stage_reset','missed_stage_reset','stale_unguided_diagnostic','unguided_same_stage'):
        events[1].update(guidance_after=False,reward_reference_reset=case!='unguided_same_stage');metrics.pop(1)
        events[2].update(guidance_before=False,normalized_reward_diagnostic=None)
        if case in ('unguided_stage_reset','stale_unguided_diagnostic'):metrics[1]['outer_reward'].update(reference=-4.,progress=0.)
        if case=='stale_unguided_diagnostic':events[2]['normalized_reward_diagnostic']=.5
    assert audit_steering.vls_reference_continuity(events,metrics) is (case in ('stable','unguided_stage_reset','unguided_same_stage'))


@pytest.mark.parametrize('case',['snapshot_hash','gpu','egl','libero_config','libero_asset_root','libero_binding','libero_valid','local_model'])
def test_v2_machine_and_libero_loading_receipts_bind_local_snapshot(cohort,monkeypatch,case):
    folder,_,_=prepare_v2_cohort(cohort,monkeypatch)
    env=json.loads((folder/'environment.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
    local=yaml.safe_load((folder/'local-config.yaml').read_text())
    if case=='snapshot_hash':local['allocator_limit_gib']=40
    elif case=='gpu':manifest['physical_gpu']=4
    elif case=='egl':manifest['egl_device_id']=3
    elif case=='libero_config':env['libero_paths']['config_path']='/wrong/config.yaml'
    elif case=='libero_asset_root':env['libero']['root']='/other/libero'
    elif case=='libero_binding':env['libero_paths']['bindings']['assets']='/other/assets'
    elif case=='libero_valid':env['libero_paths']['valid']=False
    elif case=='local_model':local['rdt_checkpoint']='/different/checkpoint'
    (folder/'local-config.yaml').write_text(yaml.safe_dump(local))
    if case!='snapshot_hash':manifest['local_config_sha256']=steering_runtime.digest(folder/'local-config.yaml')
    write_json(folder/'environment.json',env);manifest['environment_sha256']=steering_runtime.digest(folder/'environment.json')
    write_json(folder/'manifest.json',manifest)
    assert not audit_steering.audit(folder)['valid'],case


def test_v2_other_gpu_binding_and_no_write_are_supported(cohort,monkeypatch):
    folder,_,_=prepare_v2_cohort(cohort,monkeypatch)
    local=yaml.safe_load((folder/'local-config.yaml').read_text());local.update(gpu=4,egl_device_id=4)
    (folder/'local-config.yaml').write_text(yaml.safe_dump(local))
    manifest=json.loads((folder/'manifest.json').read_text());manifest.update(physical_gpu=4,egl_device_id=4,
        local_config_sha256=steering_runtime.digest(folder/'local-config.yaml'))
    write_json(folder/'manifest.json',manifest)
    old=folder/'audit.json';old.write_bytes(b'immutable\n')
    result=audit_steering.audit(folder,write=False)
    assert result['valid'],result['checks']
    assert old.read_bytes()==b'immutable\n' and not (folder/'audit-details').exists()
    assert result['method_audit']['path'] is None and not result['method_audit']['written']


def test_unserializable_task_report_is_preserved_as_failed_contract(cohort,monkeypatch):
    folder,_,_=prepare_v2_cohort(cohort,monkeypatch)
    monkeypatch.setattr(audit_steering,'audit_task_contract',lambda *a,**kw:dict(
        task_contract_valid=True,task_evidence_complete=True,facts={'bad':float('nan')}))
    result=audit_steering.audit(folder)
    assert not result['valid'] and len(result['tasks'])==2
    for row in result['tasks']:
        report=json.loads(Path(row['extended_contract']['path']).read_text())
        assert report['checks']['evidence_structure']['error_type']=='ValueError'


def test_vls_wrapper_rejects_stage_consuming_wrong_progress(cohort,monkeypatch):
    folder,records,_=prepare_v2_cohort(cohort,monkeypatch,'vls')
    records['stage_events'][0]['normalized_reward_diagnostic']=.42
    write_rows(folder/'output/evaluation/stage_events.jsonl',records['stage_events'])
    result=audit_steering.audit(folder)
    assert not result['valid'] and not result['checks']['vls_stage_reference_continuity']
