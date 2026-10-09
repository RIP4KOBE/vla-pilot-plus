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
from scripts import qd_ed_n35_bridge as b, qd_ed_n35_contract as c
from scripts import qd_ed_n35_worker as worker, qd_ed_n35_supervise as supervisor
from scripts import qd_ed_n35_release as release, qd_ed_n35_report as reporting
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
    plan = {'schema': 'n35-release-draft-v1', 'frozen': False, 'release_enabled': False,
            'worktree': str(b.ROOT), 'artifact_root': str(tmp_path / 'artifacts'), 'source': source,
            'scientific_source': copy.deepcopy(source), 'runtime': runtime_ref,
            'runtime_closure': write(tmp_path / 'closure.json', {'synthetic_only': True}),
            'controller_semantics': write(tmp_path / 'controller.json', {'synthetic_only': True}),
            'episodes': c.expected_rows(), 'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
            'deadline': c.DEADLINE, 'stop_path': c.stop_path(), 'root_review': None, 'protocol': None,
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
    assert resolved['closure_intent_mode']==(b.MODE if arm=='N35' else 'off')
    assert resolved['n35_runtime_binding']==(manifest['expected_runtime']['binding'] if arm=='N35' else None)
    assert resolved['observed_jaw_approach_mode']==('observed_jaw_approach_v1' if arm in ('N34','N35') else 'off')
    original=json.loads((b.ROOT/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())
    assert all(b.profiles()['profiles'][control]==original['profiles'][control] for control in ('C0','Q0'))
    if arm in ('N34','N35'):
        bad=copy.deepcopy(manifest);bad['expected_runtime']['binding']['run_id']='wrong'
        badref=write(Path(plan['artifact_root'])/(arm+'-bad-manifest.json'),bad)
        with pytest.raises(ValueError):b.verify_manifest(badref,plan,runtime,row)

@pytest.mark.parametrize('arm',c.ARMS)
def test_same_process_mandatory_audits_and_tampered_receipts(prospective,monkeypatch,stub_adapter,mock_batch,arm):
    import test_n35_closure_intent_integration as n35_fixture
    import test_n34_observed_jaw as n34_fixture
    synthetic=n35_fixture if arm=='N35' else n34_fixture
    plan,runtime,plan_ref=prospective
    row=next(x for x in plan['episodes'] if x['profile']==arm)
    manifest=w.read_ref(plan['expected_manifests'][row['episode_key']]);out=Path(manifest['output_dir'])
    context={'plan':plan_ref,'expected_manifest':plan['expected_manifests'][row['episode_key']],
        'episode_key':row['episode_key'],'attempt_id':row['episode_key'],'main_argv':manifest['argv'][1:]}
    ref=write(out/'n35-worker-context.json',context)
    monkeypatch.setattr(worker,'validate_context',lambda _: (context,plan,runtime,row,manifest))
    monkeypatch.setattr(worker,'verify_dispatch_record',lambda *args:None)
    monkeypatch.setattr(synthetic,'runtime_cfg',lambda _:manifest['resolved_config'])
    index={x['path']:x['sha256'] for x in plan['source']['files']}
    inventory={p.removesuffix('.py').replace('/','.'): {'path':p,'sha256':h} for p,h in index.items() if p.endswith('.py')}
    for p,h in index.items():
        if p.startswith('third_party/rdt/'):
            inventory[p[len('third_party/rdt/'):].removesuffix('.py').replace('/','.')]={'path':p,'sha256':h}
    name='scripts.qd_ed_n35_worker'
    inventory[name].update(module_name=name,spec_name=name,origin=str(b.ROOT/'scripts/qd_ed_n35_worker.py'))
    monkeypatch.setattr(worker,'attest_worker_loaded',lambda *_:copy.deepcopy(inventory))
    monkeypatch.setattr(worker.closure,'attest_runtime',lambda *a,**kw:{})
    proof={'source':{},'module':'synthetic','class':'Synthetic','instance':{}}
    monkeypatch.setattr(worker.controller,'verify_semantics',lambda *_:proof)
    @contextmanager
    def observe(_):yield [proof]
    monkeypatch.setattr(worker.controller,'observe_instances',observe)
    monkeypatch.setattr(worker,'assigned_cuda_identity',lambda _:{'physical_gpu':7,'uuid':c.GPU_UUID,
        'physical_uuid':c.GPU_UUID,'actual_uuid':c.GPU_UUID,'logical_device':'cuda:0',
        'actual_uuid_type':'builtins.str','actual_uuid_bytes_hex':None})
    def main(*a,**kw):
        synthetic.episode(out,monkeypatch,stub_adapter,mock_batch,arm=arm,disk=True,
                          **({'providers_mode':'chain','target':0.} if arm=='N35' else {}))
    monkeypatch.setattr(worker.runpy,'run_path',main)
    assert worker._run_in_process(ref)==0,(out/'eds_eval/n35-worker-receipt.json').read_text()
    receipt_ref=c.ref(out/'eds_eval/n35-worker-receipt.json');receipt=w.read_ref(receipt_ref)
    report=w.read_ref(receipt['audit_report'])
    process={**receipt['process'],'attempt_id':row['episode_key']}
    assert worker.verify_receipt(ref,receipt_ref,process)==report
    for field in ('scientific_source','source','row','expected_manifest','native_counts','runtime_after','controller_instances'):
        bad=copy.deepcopy(receipt);bad[field]={}
        badref=write(out/'eds_eval/n35-worker-receipt.json',bad)
        with pytest.raises((ValueError,KeyError,TypeError)):worker.verify_receipt(ref,badref,process)
    write(out/'eds_eval/n35-worker-receipt.json',receipt)
    if arm=='N35':
        assert report[worker.n35.GATE]['lifecycle']['eligible_boundaries']==1
        bad=copy.deepcopy(report);bad.pop(worker.n35.GATE)
        with pytest.raises(ValueError):worker.native_counts(arm,out,bad,manifest['expected_runtime'])
    else:
        assert worker.n35.GATE not in report
        assert report['n35_control_absence']=={'profile':arm,'events':0,'metrics':0}
    assert not torch.cuda.is_initialized()
