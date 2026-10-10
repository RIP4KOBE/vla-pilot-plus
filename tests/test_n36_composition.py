"""Prospective composition + real CPU native audit + bounded controller tests.

All evidence is generated from small synthetic tensors, never installed runtime
attestation, model/provider execution, protected data or owning journals.
"""
import copy
from contextlib import contextmanager
from dataclasses import asdict
import datetime as dt
import json
from pathlib import Path
import pytest
import torch
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c
from scripts import qd_ed_n36_worker as worker, qd_ed_n36_supervise as supervisor
from scripts import qd_ed_n36_release as release, qd_ed_n36_report as reporting
from scripts import qd_ed_n23_worker as w
from test_rdt_steer import _patch_core_imports, stub_adapter, mock_batch, stub_steer


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return c.ref(path)


@pytest.fixture(scope='module')
def prospective_base(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('prospective')
    provider = {'backend': 'codex_cli', 'model': 'gpt-6-astra', 'auth_mode': 'chatgpt', 'reasoning_effort': 'low',
                'timeout_seconds': 180, 'cli_path': str(tmp_path / 'codex'), 'cli_version': '0.155.1',
                'cli_sha256': 'a'*64, 'disabled_skill_paths': [str(tmp_path / 'inactive')], 'allow_recovered_error_events': True}
    provider['public_config_sha256'] = b.runner.codex_public_config_sha256(provider)
    runtime = {'tasks': {}, 'files': [], 'main_overrides': ['+main.require_task_cache_identity=true'],
               'frozen_stage_provider': provider, 'stage_engineering_condition': b.runner.n4e1_support().engineering_condition(),
               'stage_recovered_error_condition': b.runner.E2_STAGE_CONDITION,
               'gpu_mapping': {'physical_gpu': 7, 'uuid': c.GPU_UUID, 'egl_device_index': 4}}
    for row in c.expected_rows()[::4]:
        t = row['task_id']
        task = {'task_id': t, 'init_index': row['init_index'], 'cache_dir': str(tmp_path / f'cache{t}'),
                'init_path': str(tmp_path / f'init{t}'), 'bddl_path': str(tmp_path / f'task{t}.bddl')}
        runtime['tasks'][str(t)] = task
        runtime['files'] += [{'path': task['init_path'], 'sha256': row['init_file_sha256']},
                             {'path': task['bddl_path'], 'sha256': row['bddl_sha256']}]
    names = set(b.RUNTIME_SOURCES) | {str(p.relative_to(b.ROOT)) for folder in ('scripts','core','utils') for p in (b.ROOT/folder).rglob('*.py')}
    files = [{'path': p, 'sha256': w.sha(b.ROOT / p)} for p in sorted(names)]
    # Synthetic-only stand-ins for unloaded pinned RDT modules; real Git closure
    # verification separately rejects missing materialized submodule source.
    files += [{'path':'third_party/rdt/'+p,'sha256':'b'*64} for p in ('scripts/maniskill_model.py','models/rdt_runner.py','models/multimodal_encoder/siglip_encoder.py','models/multimodal_encoder/t5_encoder.py','configs/state_vec.py')]
    source = {'commit': '969d5fb57c90f61dfc93331346f0ea8158f4eaf1', 'files': files, 'sha256': w.canonical_sha(files)}
    runtime_ref = write(tmp_path / 'runtime.json', runtime)
    plan = {'schema': 'n36-release-draft-v1', 'frozen': False, 'release_enabled': False,
            'worktree': str(b.ROOT), 'artifact_root': str(tmp_path / 'artifacts'), 'source': source,
            'scientific_source': copy.deepcopy(source), 'runtime': runtime_ref, 'native_build':write(tmp_path/'native-build.json',{'synthetic_only':True}),
            'runtime_closure': write(tmp_path / 'closure.json', {'synthetic_only': True}),
            'controller_semantics': write(tmp_path / 'controller.json', {'synthetic_only': True}),
            'episodes': c.expected_rows(), 'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
            'deadline': c.DEADLINE, 'stop_path': c.stop_path(), 'stop_authority': c.stop.binding(), 'root_review': None, 'protocol': None,
            'authority': None, 'execution_release': None,
            'phase_authorization': {'dev': False, 'validation': False, 'formal': False}, 'expected_manifests': {}}
    # Freeze all prospective configs BEFORE any candidate evidence exists.
    for row in plan['episodes']:
        plan['expected_manifests'][row['episode_key']] = write(tmp_path / 'expected' / (row['episode_key']+'.json'), b.manifest(plan,runtime,row))
    ref = write(tmp_path / 'plan.json', plan)
    return plan,runtime,ref


@pytest.fixture
def prospective(prospective_base, monkeypatch):
    monkeypatch.setattr(b, 'verify_sources', lambda _: None) # Separate Git fixtures exercise real source verification.
    monkeypatch.setattr(worker.closure, 'verify_runtime', lambda *_: {'modules': {}, 'required_after': []})
    return copy.deepcopy(prospective_base)



@pytest.mark.parametrize('arm',c.ARMS)
def test_four_arm_constructor_and_external_manifest(prospective,stub_steer,arm):
    plan,runtime,_=prospective
    row=next(x for x in plan['episodes'] if x['profile']==arm)
    manifest=b.verify_manifest(plan['expected_manifests'][row['episode_key']],plan,runtime,row)
    config,resolved=b.compose_launch(manifest['argv'])
    raw={**config['main']['eds_config'],'reward_mode':config['main']['eds_eval']['reward_mode'],
         'shuffle_seed':config['main']['eds_eval']['shuffle_seed'],'mechanism_pretest':config['main']['eds_mechanism_pretest']}
    assert asdict(stub_steer._resolve_eds_config_with_reference_defaults(raw))==resolved
    assert resolved['nonprogress_tangent_mode']==(b.MODE if arm=='N36' else 'off')
    assert resolved['n36_runtime_binding']==(manifest['expected_runtime']['binding'] if arm=='N36' else None)
    assert resolved['observed_jaw_approach_mode']==('observed_jaw_approach_v1' if arm in ('N34','N36') else 'off')
    original=json.loads((b.ROOT/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())
    for control in ('C0','Q0'):
        resolved_control=b.profiles()['profiles'][control]['resolved_eds_config']
        assert all(resolved_control[k]==v for k,v in original['profiles'][control]['resolved_eds_config'].items())
        assert resolved_control['closure_intent_mode']=='off' and resolved_control['n35_runtime_binding'] is None
        assert resolved_control['nonprogress_tangent_mode']=='off' and resolved_control['n36_runtime_binding'] is None
    if arm in ('N34','N36'):
        bad=copy.deepcopy(manifest);bad['expected_runtime']['binding']['run_id']='wrong'
        badref=write(Path(plan['artifact_root'])/(arm+'-bad-manifest.json'),bad)
        with pytest.raises(ValueError):b.verify_manifest(badref,plan,runtime,row)
