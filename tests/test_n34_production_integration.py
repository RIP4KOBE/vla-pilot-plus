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
from scripts import qd_ed_n34_bridge as b, qd_ed_n34_contract as c
from scripts import qd_ed_n34_worker as worker, qd_ed_n34_supervise as supervisor
from scripts import qd_ed_n34_release as release, qd_ed_n34_report as reporting
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
    for row in c.expected_rows()[::3]:
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
    source = {'commit': b.SCIENTIFIC_COMMIT, 'files': files, 'sha256': w.canonical_sha(files)}
    runtime_ref = write(tmp_path / 'runtime.json', runtime)
    plan = {'schema': 'n34-release-draft-v1', 'frozen': False, 'release_enabled': False,
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


@pytest.mark.parametrize('arm', c.ARMS)
def test_composition_and_constructor(prospective, stub_steer, arm):
    plan,runtime,_ = prospective
    row = next(r for r in plan['episodes'] if r['profile']==arm)
    m = b.verify_manifest(plan['expected_manifests'][row['episode_key']],plan,runtime,row)
    cfg,resolved = b.compose_launch(m['argv'])
    raw = {**cfg['main']['eds_config'], 'reward_mode': cfg['main']['eds_eval']['reward_mode'],
           'shuffle_seed': cfg['main']['eds_eval']['shuffle_seed'], 'mechanism_pretest': cfg['main']['eds_mechanism_pretest']}
    assert asdict(stub_steer._resolve_eds_config_with_reference_defaults(raw)) == resolved
    assert resolved['capture_dwell_proposal_mode'] == resolved['archive_eligible_capture_mode'] == 'off'
    original=json.loads((b.ROOT/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())
    for control in ('C0','Q0'):
        assert b.profiles()['profiles'][control] == original['profiles'][control]
    q0=original['profiles']['Q0']['static_override_values']
    active=b.profiles()['profiles']['N34']['static_override_values']
    assert all(active[k] == v for k,v in q0.items())
    assert any('mechanism_pretest' in arg for arg in m['argv'])
    if arm=='N34':
        assert set(m['expected_runtime']['source_hashes']) == set(b.RUNTIME_SOURCES)
        assert m['expected_runtime']['binding'] == {'task_id':row['task_id'],'run_id':row['episode_key'],'source_commit':b.SCIENTIFIC_COMMIT}
    else: assert m['expected_runtime'] is None


@pytest.mark.parametrize('fault', ['profile','config','runtime','source','binding','manifest'])
def test_prospective_mismatch_rejected(prospective, fault):
    plan,runtime,_=copy.deepcopy(prospective)
    row=plan['episodes'][2]; ref=plan['expected_manifests'][row['episode_key']]
    if fault=='profile': row['profile']='N32'
    elif fault=='config': runtime['main_overrides'].append('main.eds_config.observed_jaw_approach_mode=off')
    elif fault=='runtime': runtime['gpu_mapping']['physical_gpu']=2
    elif fault=='source': plan['scientific_source']['files'][0]['sha256']='0'*64
    elif fault=='binding': plan['scientific_source']['commit']='0'*40
    elif fault=='manifest': ref['sha256']='0'*64
    with pytest.raises((ValueError,KeyError)): b.verify_manifest(ref,plan,runtime,row)


@pytest.mark.parametrize('arm', c.ARMS)
def test_same_worker_native_audit_external_anchor(prospective, monkeypatch, stub_adapter, mock_batch, arm):
    import test_n34_observed_jaw as synthetic
    plan,runtime,plan_ref=prospective
    row=next(x for x in plan['episodes'] if x['profile']==arm)
    manifest=w.read_ref(plan['expected_manifests'][row['episode_key']]);out=Path(manifest['output_dir'])
    # This native-audit unit fixture has no release. Substitute context/dispatch
    # setup explicitly; production consumers now reject every draft context.
    context={'plan':plan_ref,'expected_manifest':plan['expected_manifests'][row['episode_key']],
             'episode_key':row['episode_key'],'attempt_id':row['episode_key'],
             'main_argv':manifest['argv'][1:]}
    ref=write(out/'n34-worker-context.json',context)
    monkeypatch.setattr(worker,'validate_context',lambda _: (context,plan,runtime,row,manifest))
    monkeypatch.setattr(worker,'verify_dispatch_record',lambda *a: None)
    monkeypatch.setattr(synthetic,'runtime_cfg',lambda _: manifest['resolved_config'])
    index={x['path']:x['sha256'] for x in plan['source']['files']}
    inventory={p.removesuffix('.py').replace('/','.'): {'path':p,'sha256':h} for p,h in index.items() if p.endswith('.py')}
    for p,h in index.items():
        if p.startswith('third_party/rdt/'):
            inventory[p[len('third_party/rdt/'):].removesuffix('.py').replace('/','.')]={'path':p,'sha256':h}
    name='scripts.qd_ed_n34_worker'
    inventory[name].update(module_name=name,spec_name=name,origin=str(b.ROOT/'scripts/qd_ed_n34_worker.py'))
    monkeypatch.setattr(worker,'attest_worker_loaded',lambda *_: copy.deepcopy(inventory))
    monkeypatch.setattr(worker.closure,'attest_runtime',lambda *a,**kw: {})
    proof={'source':{},'module':'synthetic','class':'Synthetic','instance':{}}
    monkeypatch.setattr(worker.controller,'verify_semantics',lambda *_: proof)
    @contextmanager
    def observe(_): yield [proof]
    monkeypatch.setattr(worker.controller,'observe_instances',observe)
    monkeypatch.setattr(worker,'assigned_cuda_identity',lambda _: {'physical_gpu':7,'uuid':c.GPU_UUID,
        'physical_uuid':c.GPU_UUID,'actual_uuid':c.GPU_UUID,'logical_device':'cuda:0',
        'actual_uuid_type':'builtins.str','actual_uuid_bytes_hex':None})
    def main(*a,**kw): synthetic.episode(out,monkeypatch,stub_adapter,mock_batch,arm=arm,disk=True)
    monkeypatch.setattr(worker.runpy,'run_path',main)
    assert worker._run_in_process(ref)==0,(out/'eds_eval/n34-worker-receipt.json').read_text()
    receipt=w.read_ref(c.ref(out/'eds_eval/n34-worker-receipt.json'))
    report=w.read_ref(receipt['audit_report'])
    worker.native_counts(arm,out,report,manifest['expected_runtime'],1)
    receipt_ref=c.ref(out/'eds_eval/n34-worker-receipt.json')
    process={**receipt['process'],'attempt_id':row['episode_key']}
    assert worker.verify_receipt(ref,receipt_ref,process)==report
    for field in ('scientific_source','source','row','expected_manifest','native_counts','runtime_after','controller_instances'):
        bad=copy.deepcopy(receipt)
        bad[field] = {'unfrozen':{}} if field=='runtime_after' else {}
        bad_ref=write(out/'eds_eval/n34-worker-receipt.json',bad)
        with pytest.raises((ValueError,KeyError,TypeError)):worker.verify_receipt(ref,bad_ref,process)
    receipt_ref=write(out/'eds_eval/n34-worker-receipt.json',receipt)
    with pytest.raises(ValueError,match='process/outcome'):worker.verify_receipt(ref,receipt_ref,{**process,'pid':process['pid']+1})
    assert not torch.cuda.is_initialized()
    if arm=='N34':
        assert report[worker.n34.GATE]['runtime_identity']==manifest['expected_runtime']
        for fault in ('binding','config_sha256','source_hashes'):
            expected=copy.deepcopy(manifest['expected_runtime']);expected[fault]={} if fault!='config_sha256' else '0'*64
            with pytest.raises(ValueError):worker.native_counts(arm,out,report,expected)
        bad=copy.deepcopy(report);bad.pop(worker.n34.GATE)
        with pytest.raises(ValueError):worker.native_counts(arm,out,bad,manifest['expected_runtime'])
    else:
        assert worker.n34.GATE not in report
        # A control cannot hide a candidate marker behind a valid generic receipt.
        monkeypatch.setattr(worker.generic,'load_events',lambda *_:[{'event':'n34_observation_context'}])
        with pytest.raises(ValueError,match='control N34 evidence'):
            worker.audit_native(arm,out,report,worker.create_backend('cpu'),None)
    with pytest.raises(ValueError,match='generic'):
        worker.audit_native(arm,out,{**report,'accepted':False},worker.create_backend('cpu'),manifest['expected_runtime'])
    with pytest.raises(ValueError,match='replay'):worker._run_in_process(ref)


def journal(rows, success=False):
    return [dict(event=k,identity=supervisor.c_identity(row),episode_key=row['episode_key'],attempt_id=row['episode_key'],
                 outcome_valid=True,required_cost_telemetry_complete=True,success=success,gpu_process_wall_seconds=1.)
            for row in rows for k in ('reserved','dispatched','valid')]


def test_complete_triple_futility_and_charged_invalid():
    plan={'episodes':c.expected_rows(),'worktree':str(b.ROOT)};rows=plan['episodes']
    for n in (16,17):assert supervisor.reconcile(plan,journal(rows[:n]),lambda *a:None)['next_row']==rows[n]
    assert supervisor.reconcile(plan,journal(rows[:18]),lambda *a:None)['status']=='NUMERIC_FUTILITY'
    events=journal(rows[:1]);events[-1].update(event='aborted',outcome_valid=False,success=None)
    result=supervisor.reconcile(plan,events,lambda *a:None)
    assert result['status']=='INVALID_STOP' and result['charged_events']==events
    def reject(*a):raise ValueError('wrong native/source/runtime')
    assert supervisor.reconcile(plan,journal(rows[:1]),reject)['status']=='INVALID_STOP'
    for fault in ('attempt_id','identity','retry_of'):
        bad=journal(rows[:1]);bad[0][fault]='wrong'
        with pytest.raises((ValueError,TypeError)):supervisor.reconcile(plan,bad,lambda *a:None)
    full=supervisor.reconcile(plan,journal(rows,True),lambda *a:None)
    assert reporting.summary(full,[])['prospective_dev_necessary_gate_met']
    assert not reporting.summary(supervisor.reconcile(plan,[],lambda *a:None),[])['prospective_dev_necessary_gate_met']


def allowance():
    return dict(authority_starts_at='2026-10-08T00:00:00Z',authority_ends_at=c.DEADLINE,
                private_budget=True,gpu_idle=True,physical_gpu=7,gpu_uuid=c.GPU_UUID,live_handles=[],unsettled_reservations=0,
                global_seconds_remaining=200000,private_seconds_remaining=200000,cohort_seconds_remaining=18000,
                protected_seconds_remaining=158400,bucket_attempts_remaining={'baseline':10,'development':20},
                global_attempts_remaining=250,cohort_attempts_remaining=30,protected_attempts_remaining=220)


@pytest.mark.parametrize('fault',['STOP','symlink','deadline','protected','budget','live','cohort','unknown'])
def test_admission_rejections(tmp_path,fault):
    a=allowance();stop=tmp_path/'STOP';now=dt.datetime(2026,10,8,tzinfo=dt.timezone.utc)
    assert c.pre_dispatch(c.expected_rows()[0],a,now=now,stop_path=stop)==1840
    if fault=='STOP':stop.touch()
    if fault=='symlink':stop.symlink_to(tmp_path/'missing')
    if fault=='deadline':now=dt.datetime(2026,10,11,11,tzinfo=dt.timezone.utc)
    if fault=='protected':a['private_seconds_remaining']=158400+1839
    if fault=='budget':a['global_attempts_remaining']=220
    if fault=='live':a['live_handles']=['unknown']
    if fault=='cohort':a['cohort_seconds_remaining']=1839
    if fault=='unknown':a['global_seconds_remaining']=None
    with pytest.raises(ValueError):c.pre_dispatch(c.expected_rows()[0],a,now=now,stop_path=stop)


def test_drafts_remain_unreleased(prospective):
    plan,_,ref=prospective
    c.validate_draft(plan)
    with pytest.raises(ValueError,match='released plan contract'):release.validate_release(ref,{'forged':True})
    with pytest.raises(ValueError,match='draft only'):supervisor.launch()


def test_candidates_are_fresh_unknown_and_unreleasable(tmp_path):
    from scripts.qd_ed_n34_prepare import prepare_candidates
    plan=prepare_candidates(tmp_path/'candidates')
    assert plan['episodes']==c.expected_rows() and len(plan['outcomes'])==30
    assert set(plan['outcomes'].values())=={'Unknown'} and plan['carried_control_outcomes']==[]
    assert plan['release_enabled'] is False and plan['source'] is None and plan['runtime'] is None
    assert plan['expected_manifests']=={} and plan['phase_authorization']=={'dev':False,'validation':False,'formal':False}
    protocol=w.read_ref(plan['protocol_candidate'])
    assert protocol['promotion']=={'all_valid_cells':30,'n34_min_successes':5,'at_least_both_controls':True,'matched_controls_required':True}
    with pytest.raises(ValueError,match='released plan contract'):
        release.validate_release(c.ref(tmp_path/'candidates/plan.CANDIDATE-v1.json'),{})
    with pytest.raises(ValueError,match='already exists'):prepare_candidates(tmp_path/'candidates')
