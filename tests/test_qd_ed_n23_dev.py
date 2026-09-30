"""CPU synthetic contract, dispatch and metering tests; no online calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
import torch
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_dev_contract as contract
from scripts import qd_ed_n23_dev_prepare as prepare
from scripts import qd_ed_n23_preflight_admit as admit
from scripts import qd_ed_n23_worker as worker


@pytest.fixture(autouse=True)
def synthetic_seeds(tmp_path, monkeypatch):
    seeds = {'backend_task_order': list(range(10)), 'blocks': {'dev': [dict(task_id=t,
        env_seed=t+3, policy_seed=t+30, init_index=0, init_row_sha256='a'*64,
        init_file_sha256='b'*64, bddl_sha256='c'*64) for t in range(10)]}}
    seed = tmp_path/'seed.json'; seed.write_text(json.dumps(seeds))
    plan = tmp_path/'n22-plan.json'; plan.write_text(json.dumps({'seed_plan_path': str(seed),
        'seed_plan_sha256': worker.sha(seed), 'n22_cohort': {'cohort_id': 'N22_HOLD_LIFT_DEV_20260930'},
        'code_files': [], 'scientific_config_files': [], 'runtime_manifest_path':str(contract.GPU7_RUNTIME)}))
    monkeypatch.setattr(contract,'SOURCE_PLAN',plan)
    yield
    assert not torch.cuda.is_initialized()


def authority():
    return {'gpu_pool':[7], 'max_concurrent_gpu_workers':1,
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':478,'max_gpu_hours':100.,'amendment':dict(runner.GPU7_N23_AMENDMENT),
            'reserved':dict(runner.N23_BUCKETS),'dispatched':0,'running':0,'gpu_hours_consumed':0.,
            'gpu_hour_reservations':{'validation':32.,'formal':12.}},
        'n23_gpu7_binding':{'scope':contract.COHORT+'_and_backend_preflight_only','selected_gpu':7,
            'user_reply':contract.AUTONOMOUS_REPLY,'addendum_path':str(contract.PROTOCOL),'addendum_sha256':contract.PROTOCOL_SHA}}


def reservations():
    return [{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':32.,'formal':12.},
             'rationale':'synthetic','time_unix':1.}]


def module(name,monkeypatch):
    monkeypatch.syspath_prepend(str(runner.ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location(name+'_test',runner.ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_matrix_profiles_and_legacy_routing():
    rows=contract.expected_rows()
    assert [(v['task_id'],v['profile']) for v in rows]==[(t,a) for t in range(10) for a in contract.ARMS]
    assert len({v['episode_key'] for v in rows})==40
    assert all(v['split']==v['seed_block']=='dev' and v['timeout_seconds']==1800 and 'retry_of' not in v for v in rows)
    plan={'candidate_profiles':{'N7':{},'N23':{}}}
    assert runner.is_n23_plan(plan) and not runner.is_n7_plan(plan)
    plan['n7_validation']={};plan['n7_cohort']={}
    assert not runner.is_n7_plan(plan)
    assert runner.is_n7_plan({'candidate_profiles':{'N7':{}}})
    assert runner.is_n22_plan({'candidate_profiles':{'N21':{},'N22':{}}})
    assert not runner.is_n21_plan({'candidate_profiles':{'N21':{},'N22':{}}})
    base=runner.read_json(runner.ROOT/'configs/qd_ed_final/baseline_profiles.json')['profiles']['Q0']
    a=runner.expand_candidate('N7',runner.read_json(runner.ROOT/'configs/qd_ed_final/candidate_n7.json'),base)
    b=runner.expand_candidate('N23',runner.read_json(runner.ROOT/'configs/qd_ed_final/candidate_n23.json'),base)
    assert b['resolved_eds_config']=={**a['resolved_eds_config'],'qd_quality_mode':'actuator_clipped_provider_v1'}


@pytest.mark.parametrize('fault',['none','amendment','cap','bucket','hours','reserve','gpu','cohort','private','hold'])
def test_budget_adoption_and_exact_scope(fault):
    s=authority();row=contract.expected_rows()[0]
    if fault=='amendment':s['budget']['amendment']=runner.GPU7_N22_AMENDMENT
    if fault=='cap':s['budget']['max_episode_attempts']=479
    if fault=='bucket':s['budget']['reserved']['development']=188
    if fault=='hours':s['budget']['max_gpu_hours']=101.
    if fault=='reserve':s['budget']['gpu_hour_reservations']['formal']=11.
    if fault=='gpu':s['gpu_pool']=[3]
    if fault=='cohort':row['iteration']='validation'
    if fault=='private':s['resource_isolation']['private_budget']=False
    if fault=='hold':s['external_resource_hold']={'do_not_auto_resume':True}
    if fault=='none':
        assert runner.check_budget(s,[],row,reservation_events=reservations())==1800
        assert runner.check_budget(s,[],admit.diagnostic_row(),reservation_events=reservations())==120
    else:
        with pytest.raises(runner.GateError):runner.check_budget(s,[],row,reservation_events=reservations())


def test_full_initial_ceiling_and_preflight_reserve_are_required():
    r=dict(vars(runner));s=authority()
    def snap(hours):return {**runner.budget_snapshot([]),'gpu_hours_consumed':hours}
    r['budget_snapshot']=lambda *_:snap(35.)
    contract.full_capacity(s,[],[],r)
    with pytest.raises(runner.GateError,match='full remaining'):contract.full_capacity(s,[],[],r,preflight=True)
    r['budget_snapshot']=lambda *_:snap(35.0001)
    with pytest.raises(runner.GateError):contract.full_capacity(s,[],[],r)
    r['budget_snapshot']=lambda *_:{**snap(0),'by_bucket':{**snap(0)['by_bucket'],'baseline':42}}
    with pytest.raises(runner.GateError,match='capacity'):contract.full_capacity(s,[],[],r)


def prefix(count):
    return [{'event':'valid','identity':runner.episode_identity(v),'episode_key':v['episode_key'],
             'outcome_valid':True,'success':False,'output_dir':'synthetic'} for v in contract.expected_rows()[:count]]


def test_prefix_futility_no_retry_scope(monkeypatch,tmp_path):
    rows=contract.expected_rows();plan={'episodes':rows,'source_commit':'synthetic'}
    monkeypatch.setattr(contract,'read_worker_report',lambda *_:{'accepted':True,'evidence_complete':True})
    assert contract.admission(plan,{},rows[4],prefix(4),[],tmp_path,vars(runner))['n23_cohort_id']==contract.COHORT
    assert contract.admission(plan,{},rows[2],prefix(2),[],tmp_path,vars(runner))['n23_arm_role']=='ablation_control_only'
    for row,events,match in [(rows[0],prefix(1),'retried'),(rows[24],prefix(24),'futility'),(rows[4],prefix(3),'valid')]:
        with pytest.raises(runner.GateError,match=match):contract.admission(plan,{},row,events,[],tmp_path,vars(runner))
    with contract.supervised_scope(plan,tmp_path,rows[0]['episode_key']):
        contract.require_scope(plan,tmp_path,vars(runner),rows[0])
        with pytest.raises(runner.GateError):contract.require_scope(plan,tmp_path,vars(runner),rows[1])
    with pytest.raises(runner.GateError):contract.require_scope(plan,tmp_path,vars(runner))


@pytest.mark.parametrize('case,count,status,promoted',[
 ('all_fail',24,'rejected_numeric_futility',False),('five',40,'completed_all_forty_audited',True),
 ('equal',40,'completed_all_forty_audited',True),('inferior',40,'completed_all_forty_audited',False),
 ('zero_clip',40,'completed_all_forty_audited',True),('unguided',40,'completed_all_forty_audited',False),
 ('invalid',7,'failed',False),('audit',4,'failed',False),('compute',4,'failed',False),('inactive',4,'failed',False)])
def test_supervisor_rules(tmp_path,monkeypatch,case,count,status,promoted):
    m=module('qd_ed_n23_dev_supervise',monkeypatch);r=m.runner;c=m.contract
    monkeypatch.setattr(c,'expected_rows',contract.expected_rows)
    plan={'source_commit':'synthetic','artifact_root':str(tmp_path),'episodes':contract.expected_rows()}
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{},{}));monkeypatch.setattr(m,'release_check',lambda *a:None)
    monkeypatch.setattr(m.queue,'inventory',lambda:{7:{'uuid':c.GPU7_UUID}})
    monkeypatch.setattr(m.queue,'reservation_admission',lambda *_:None);monkeypatch.setattr(r,'gpu_admission',lambda **_:None)
    monkeypatch.setattr(r,'n23_support',lambda:c);monkeypatch.setattr(c,'RUN_DIR',tmp_path/'variant')
    called=[]
    def run(*args,episode_keys,root,**kwargs):
        row=next(v for v in plan['episodes'] if v['episode_key']==episode_keys[0]);called.append(row)
        c.require_scope(plan,root,vars(r),row)
        out=tmp_path/f'cell{len(called)}';(out/'eds_eval').mkdir(parents=True)
        metric={'qd_archive_active_for_chunk':not(case=='inactive' and row['profile']=='N23'),
            'qd_quality_mode':'actuator_clipped_provider_v1' if row['profile']=='N23' else 'provider',
            'score_call_count':11,'search_evaluation_count':176,'resample_count':10,'renoise_count':10,'rollout_count':10,
            'qd_actuator_overhead_seconds':.01,'qd_actuator_quality_batches':11,
            'qd_actuator_quality_candidates':176,'qd_actuator_clipped_prefix_candidates':1}
        (out/'eds_eval/eds_metrics.jsonl').write_text('' if case=='unguided' else json.dumps(metric)+'\n')
        success=False if case=='all_fail' else row['task_id'] in {1,2,3,4,5} if row['profile']=='N23' else (
            row['task_id']<(6 if case=='inferior' else 5) if case in {'equal','inferior'} else False)
        return [{'event':'valid','outcome_valid':not(case=='invalid' and len(called)==7),'success':success,
            'output_dir':str(out),'attempt_id':out.name,**{k:1 for k in m.COST_FIELDS}}]
    monkeypatch.setattr(r,'run_plan',run)
    def report(*a):
        result={'accepted':not(case=='audit' and called[-1]['profile']=='N23'),'evidence_complete':True}
        if case!='unguided':
            result['n5_grasp_timing_audit']={'checked_decisions':1,'parent_rounds_verified':10}
            if called[-1]['profile']=='N23':result['n23_actuator_clipped_quality_audit']={
                'score_batches_verified':10 if case=='compute' else 11,'candidate_scores_verified':176,
                'clipped_prefix_candidates':0 if case=='zero_clip' else 1,'rank_changed_batches':0 if case=='zero_clip' else 1}
        return result
    monkeypatch.setattr(c,'read_worker_report',report)
    dst=tmp_path/'status.json';monkeypatch.setattr(sys,'argv',['test','--plan','synthetic','--release','synthetic','--status',str(dst)])
    if status=='failed':
        with pytest.raises(r.GateError):m.main()
    else:m.main()
    result=json.loads(dst.read_text());assert result['status']==status and len(called)==count and result['dev_gate_promoted']==promoted
    assert result['n7_role']=='ablation_control_only_no_promotion'
    with pytest.raises(r.GateError):m.main()


@pytest.fixture
def closure(monkeypatch):
    root=runner.ROOT
    paths=contract.source_paths(vars(runner));source={'commit':'synthetic','files':[{'path':p,'sha256':'a'*64} for p in sorted(paths)],'sha256':'b'*64}
    monkeypatch.setattr(worker,'source_record',lambda *_:copy.deepcopy(source))
    monkeypatch.setattr(contract,'predecessor_review',lambda:{'path':'synthetic-predecessor','sha256':'x'})
    monkeypatch.setattr(contract,'final_review',lambda *_:{'path':'synthetic-review','sha256':'y'})
    monkeypatch.setattr(contract,'backend_proof',lambda ref,*_:(runner.require(ref=={'accepted-synthetic':True},'backend proof missing') or ref))
    monkeypatch.setattr(contract,'validate_runtime',lambda *_:None)
    plan=prepare.build_plan(predecessor=contract.predecessor_review(),review=contract.final_review(),proof={'accepted-synthetic':True})
    plan['stage_condition']=runner.E2_STAGE_CONDITION
    m=runner.read_json(root/'configs/qd_ed_final/baseline_profiles.json')
    for arm in ('N7','N23'):m['profiles'][arm]=runner.expand_candidate(arm,runner.read_json(root/f'configs/qd_ed_final/candidate_{arm.lower()}.json'),m['profiles']['Q0'])
    r=dict(vars(runner));r['read_state']=lambda *_:authority()
    return plan,m,r


@pytest.mark.parametrize('fault',['none','proof','predecessor','review','matrix','seed','phase','profile','source_order','runtime','legacy','source_commit'])
def test_closed_matrix_profile_source_and_proof(closure,fault):
    plan,m,r=closure
    if fault=='proof':plan['n23_cohort']['backend_proof']=None
    if fault=='predecessor':plan['n23_cohort']['predecessor_review']=None
    if fault=='review':plan['n23_cohort']['final_review']=None
    if fault=='matrix':plan['episodes'][2]['profile']='N23'
    if fault=='seed':plan['episodes'][4]['env_seed']+=1
    if fault=='phase':plan['phase_authorization']['validation']=True
    if fault=='profile':m['profiles']['N23']['resolved_eds_config']['qd_quality_mode']='close_then_lift_v1'
    if fault=='source_order':plan['code_files'].reverse()
    if fault=='runtime':plan['runtime_manifest_sha256']='wrong'
    if fault=='legacy':plan['n7_validation']={}
    if fault=='source_commit':plan['source_commit']='other'
    if fault=='none':contract.validate_contract(plan,m,{},None,runner.ROOT,r)
    else:
        with pytest.raises((runner.GateError,ValueError)):contract.validate_contract(plan,m,{},None,runner.ROOT,r)


@pytest.mark.parametrize('fault',['accepted','missing','failed','duplicate','unmetered','wrong_review'])
def test_dev_requires_proof_from_actual_single_terminal_ledger(tmp_path,monkeypatch,fault):
    planpath=tmp_path/'preflight.json';report=tmp_path/'report.json'
    source={'commit':'synthetic'};runtime={'path':'runtime','sha256':'r'};prior={'path':'review','sha256':'v'};review={'path':'final','sha256':'z'}
    planpath.write_text(json.dumps({'runtime':runtime,'source':source,'predecessor_review':prior}));report.write_text('{}')
    reference={'plan':contract.ref(planpath),'report':contract.ref(report),'attempt_id':'one'}
    monkeypatch.setattr(contract,'GPU7_RUNTIME',tmp_path/'runtime')
    oldref=contract.ref;monkeypatch.setattr(contract,'ref',lambda p:runtime if Path(p)==tmp_path/'runtime' else oldref(p))
    monkeypatch.setattr(contract,'predecessor_review',lambda:prior);monkeypatch.setattr(contract,'final_review',lambda *_:review)
    events=[{'attempt_id':'one','identity':{'iteration':contract.PREFLIGHT},'event':e,'n23_final_review':review} for e in ('reserved','dispatched','valid')]
    if fault=='failed':events[-1]['event']='aborted'
    if fault=='duplicate':events.append({**events[0],'attempt_id':'two'})
    if fault=='wrong_review':events[-1]['n23_final_review']=None
    if fault=='unmetered':events=[]
    r=dict(vars(runner));r['read_events']=lambda *_:events
    if fault=='missing':reference=None
    if fault=='accepted':
        monkeypatch.setattr(contract.backend,'verify_preflight_proof',lambda *a:reference['report'])
        assert contract.backend_proof(reference,source,tmp_path,r)==reference
    else:
        with pytest.raises((runner.GateError,ValueError)):contract.backend_proof(reference,source,tmp_path,r)


@pytest.mark.parametrize('fault',['none','prior','adoption','reservation','invalid_retry','alternate_id','protected','review'])
def test_preflight_admission_gates(tmp_path,monkeypatch,fault):
    source={'commit':'synthetic'};runtime={'path':'runtime','sha256':'r'};prior={'path':'prior','sha256':'p'}
    plan={'source':source,'runtime':runtime,'predecessor_review':prior,'artifact_root':str(tmp_path)}
    state=authority();state.update(artifacts=str(tmp_path),worktree=str(tmp_path))
    monkeypatch.setattr(worker,'source_record',lambda *_:source);monkeypatch.setattr(contract,'ref',lambda *_:runtime)
    monkeypatch.setattr(contract,'predecessor_review',lambda:prior)
    monkeypatch.setattr(contract,'final_review',lambda *_:runner.require(fault!='review','missing root review'))
    monkeypatch.setattr(contract,'validate_runtime',lambda *_:None);monkeypatch.setattr(admit.backend,'validate_plan',lambda *_:{})
    events=[];reserve=reservations()
    if fault=='prior':plan['predecessor_review']=None
    if fault=='adoption':state['budget']['amendment']=None
    if fault=='reservation':reserve=[]
    if fault in {'invalid_retry','alternate_id'}:events=[{'attempt_id':'previous' if fault=='alternate_id' else 'one','identity':{'iteration':contract.PREFLIGHT},'event':'reserved'}]
    if fault=='protected':monkeypatch.setattr(contract,'full_capacity',lambda *a,**k:runner.require(False,'protected ceiling'))
    if fault=='none':admit.admission(plan,state,events,[],reserve,root=tmp_path)
    else:
        with pytest.raises((runner.GateError,ValueError)):admit.admission(plan,state,events,[],reserve,root=tmp_path)


@pytest.mark.parametrize('case',['success','launch_error','timeout','child_error','proof_error','interrupt','cleanup_error'])
def test_preflight_charged_before_launch_and_cleanup(tmp_path,monkeypatch,case):
    (tmp_path/'data').mkdir();state=authority();state.update(run_name='CPU',artifacts=str(tmp_path/'artifact'),worktree=str(tmp_path))
    import yaml
    (tmp_path/'research-state.yaml').write_text(yaml.safe_dump(state))
    (tmp_path/'data/gpu-hour-reservation-ledger.jsonl').write_text(json.dumps(reservations()[0])+'\n')
    plan={'source':{'commit':'synthetic'},'runtime':{'path':'synthetic','sha256':'r'},
          'predecessor_review':{'path':'synthetic','sha256':'p'},'artifact_root':state['artifacts']}
    planpath=tmp_path/'preflight.json';planpath.write_text(json.dumps(plan))
    monkeypatch.setattr(admit,'admission',lambda *a,**k:{})
    monkeypatch.setattr(admit,'gpu_gate',lambda *a,**k:{'uuid':contract.GPU7_UUID})
    monkeypatch.setattr(runner,'child_environment',lambda *_:{})
    monkeypatch.setattr(runner,'verify_provider',lambda *a,**k:(_ for _ in ()).throw(AssertionError('provider forbidden')))
    monkeypatch.setattr(contract,'FINAL_REVIEW',planpath)
    cleaned=[];outputs=[]
    def popen(command,**kwargs):
        events=runner.read_events(tmp_path/'data/attempt-ledger.jsonl');assert events[-1]['event']=='dispatched'
        assert runner.budget_snapshot(events)['by_bucket']['recovery']==1
        assert '--ownership-main' in command and str(tmp_path/'main.py') in command
        if case=='launch_error':raise OSError('synthetic')
        output=Path(events[-1]['output_dir']);outputs.append(output)
        (output/'n23-backend-preflight-report.json').write_text('{}')
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(admit.subprocess,'Popen',popen)
    def wait(*a,**k):
        if case=='timeout':raise subprocess.TimeoutExpired('synthetic',120)
        if case=='interrupt':raise KeyboardInterrupt()
        return 2 if case=='child_error' else 0
    monkeypatch.setattr(runner,'wait_exclusively',wait)
    def cleanup(p):
        cleaned.append(p)
        if case=='cleanup_error':raise RuntimeError('synthetic cleanup')
    monkeypatch.setattr(runner,'terminate_owned',cleanup)
    def proof(*a):
        if case=='proof_error':raise ValueError('synthetic missing receipt')
        return {}
    monkeypatch.setattr(admit.backend,'verify_preflight_proof',proof)
    if case=='success':admit.run(planpath,root=tmp_path)
    else:
        with pytest.raises(BaseException):admit.run(planpath,root=tmp_path)
    events=runner.read_events(tmp_path/'data/attempt-ledger.jsonl');snap=runner.budget_snapshot(events)
    assert [e['event'] for e in events[:2]]==['reserved','dispatched'] and len(events)==3
    assert snap['dispatched']==snap['by_bucket']['recovery']==1 and snap['running']==0
    assert events[-1]['outcome_valid'] is (case=='success') and events[-1]['task_outcome'] is False
    assert events[-1]['gpu_process_wall_seconds']>=0 and len(cleaned)==1
    assert events[-1]['event']==('valid' if case=='success' else 'aborted')


@pytest.mark.parametrize('arm',['C0','Q0','N7','N23'])
@pytest.mark.parametrize('receipt',['accepted','missing'])
def test_normal_runner_wraps_all_arms_and_charges_missing_receipt(tmp_path,monkeypatch,arm,receipt):
    import yaml
    (tmp_path/'data').mkdir();state=authority();state.update(run_name='CPU',artifacts=str(tmp_path/'artifact'))
    (tmp_path/'research-state.yaml').write_text(yaml.safe_dump(state))
    (tmp_path/'data/gpu-hour-reservation-ledger.jsonl').write_text(json.dumps(reservations()[0])+'\n')
    row=next(v for v in contract.expected_rows() if v['profile']==arm)
    plan={'source_commit':'synthetic','run_name':'CPU','artifact_root':state['artifacts'],'candidate_profiles':{'N7':{},'N23':{}},
        'n23_cohort':{},'episodes':[row],'phase_authorization':{'dev':True,'validation':False,'formal':False},
        'profiles_sha256':'p','runtime_manifest_sha256':'r','runtime_manifest_path':'synthetic',
        'runtime_inventory_sha256':'i'}
    planpath=tmp_path/'plan.json';planpath.write_text(json.dumps(plan))
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':contract.GPU7_UUID,'egl_device_index':4},'environment':{}}
    monkeypatch.setattr(runner,'validate_plan',lambda *a,**k:(plan,{'profiles':{arm:{}}},runtime))
    monkeypatch.setattr(runner,'n23_support',lambda:contract)
    for name in ('require_scope','protected_budget'):monkeypatch.setattr(contract,name,lambda *a,**k:None)
    monkeypatch.setattr(contract,'admission',lambda *a,**k:{})
    monkeypatch.setattr(runner,'gpu_admission',lambda **k:{})
    monkeypatch.setattr(runner,'child_environment',lambda *a:{})
    provider=[];monkeypatch.setattr(runner,'verify_provider',lambda *a,**k:provider.append(1))
    monkeypatch.setattr(worker,'build_context',lambda *a:{'synthetic':True})
    original=[str(runner.PYTHON),str(tmp_path/'main.py'),'policy.type=rdt','literal=value with spaces']
    monkeypatch.setattr(runner,'build_command',lambda p,m,rt,r,aid:(original,Path(p['artifact_root'])/'attempts'/aid))
    launched=[]
    def popen(argv,**kwargs):
        launched.append(argv);assert argv[1]==str(tmp_path/'scripts/qd_ed_n23_worker.py')
        assert argv[argv.index('--')+1:]==original[2:] and str(tmp_path/'main.py') in argv
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(runner.subprocess,'Popen',popen)
    monkeypatch.setattr(runner,'wait_exclusively',lambda p,t,**k:(runner.require(t==1800,'whole worker timeout') or 0))
    monkeypatch.setattr(runner,'terminate_owned',lambda p:None)
    monkeypatch.setattr(runner,'validate_result',lambda *a:{'success':False,'outcome_valid':True})
    def audit(output,r):
        if receipt=='missing':raise ValueError('no bound receipt')
        pid=json.loads((output/'process.json').read_text());assert pid['pid']==os.getpid()
        (output/'eds_eval').mkdir();(output/'eds_eval/in-worker-audit-receipt.json').write_text('{}')
        return {'accepted':True,'evidence_complete':True}
    monkeypatch.setattr(contract,'read_worker_report',audit)
    if receipt=='missing':
        with pytest.raises(runner.GateError):runner.run_plan(planpath,split='dev',iteration=contract.COHORT,root=tmp_path)
    else:runner.run_plan(planpath,split='dev',iteration=contract.COHORT,root=tmp_path)
    events=runner.read_events(tmp_path/'data/attempt-ledger.jsonl');snap=runner.budget_snapshot(events)
    assert snap['dispatched']==1 and snap['running']==0 and len(launched)==len(provider)==1
    assert events[-1]['outcome_valid'] is (receipt=='accepted') and events[-1]['n23_episode_dispatched'] is True
    assert events[-1]['gpu_process_wall_seconds']>=0


def test_preflight_dead_reconcile_charges_interruption_and_never_promotes(tmp_path,monkeypatch):
    import yaml
    (tmp_path/'data').mkdir();state=authority();state.update(run_name='CPU',artifacts=str(tmp_path/'artifact'))
    (tmp_path/'research-state.yaml').write_text(yaml.safe_dump(state))
    planpath=tmp_path/'plan.json';planpath.write_text(json.dumps({'artifact_root':state['artifacts']}))
    output=Path(state['artifacts'])/'attempts'/'dead';output.mkdir(parents=True)
    base={'attempt_id':'dead','identity':runner.episode_identity(admit.diagnostic_row()),'budget_bucket':'recovery',
        'output_dir':str(output),'plan_sha256':worker.sha(planpath),'n23_backend_preflight':True}
    for e,t in [('reserved',1.),('dispatched',2.)]:runner.append_event(tmp_path,{**base,'event':e,'time_unix':t})
    monkeypatch.setattr(runner,'gpu_admission',lambda **k:{})
    monkeypatch.setattr(admit.time,'time',lambda:164.)
    result=admit.reconcile(planpath,'dead',root=tmp_path)
    assert result['event']=='aborted' and result['outcome_valid'] is False and result['gpu_process_wall_seconds']==162.
    before=(tmp_path/'data/attempt-ledger.jsonl').read_bytes()
    assert admit.reconcile(planpath,'dead',root=tmp_path)==result
    assert before==(tmp_path/'data/attempt-ledger.jsonl').read_bytes()


@pytest.mark.parametrize('fault',['none','missing_gpu','uuid','busy','reservation','mapping','probe'])
def test_preflight_resource_gate_never_verifies_provider(monkeypatch,fault):
    monkeypatch.syspath_prepend(str(runner.ROOT/'scripts'))
    import qd_ed_available_gpu_queue as queue
    mapping={'physical_gpu':7,'uuid':contract.GPU7_UUID,'egl_device_index':4,'pci_bus_id':'0000:01:00.0',
             'driver_version':'synthetic','metadata_mapping_verified':True}
    devices={7:{'uuid':contract.GPU7_UUID}}
    if fault=='missing_gpu':devices={}
    if fault=='uuid':devices[7]['uuid']='OTHER'
    monkeypatch.setattr(queue,'inventory',lambda:devices)
    monkeypatch.setattr(queue,'reservation_admission',lambda *_:runner.require(fault!='reservation','reserved'))
    monkeypatch.setattr(runner,'gpu_admission',lambda **_:runner.require(fault!='busy','busy'))
    monkeypatch.setattr(queue,'current_metadata',lambda *a,**k:{**mapping,'egl_device_index':3} if fault=='mapping' else mapping)
    monkeypatch.setattr(queue,'find_probe',lambda *a,**k:None if fault=='probe' else {'resource_id':contract.GPU7_PROOF})
    monkeypatch.setattr(runner,'verify_provider',lambda *a,**k:(_ for _ in ()).throw(AssertionError('provider forbidden')))
    if fault=='none':assert admit.gpu_gate({'gpu_mapping':mapping},[])['physical_gpu']==7
    else:
        with pytest.raises(runner.GateError):admit.gpu_gate({'gpu_mapping':mapping},[])


@pytest.mark.parametrize('fault',['none','uuid','egl','worktree','stage','file'])
def test_frozen_runtime_metadata_and_bytes(tmp_path,fault):
    f=tmp_path/'static-input';f.write_text('synthetic')
    runtime={'schema':'qd-ed-runtime-setup-v1','worktree':str(tmp_path),'artifact_root':str(tmp_path),
        'gpu_mapping':{'physical_gpu':7,'uuid':contract.GPU7_UUID,'egl_device_index':4},
        'cuda_egl_verified':True,'cuda_egl_probe':{'resource_id':contract.GPU7_PROOF},
        'stage_recovered_error_condition':runner.E2_STAGE_CONDITION,'stage_engineering_condition':'synthetic',
        'frozen_stage_provider':{'allow_recovered_error_events':True},'files':[contract.ref(f)]}
    if fault=='uuid':runtime['gpu_mapping']['uuid']='OTHER'
    if fault=='egl':runtime['gpu_mapping']['egl_device_index']=3
    if fault=='worktree':runtime['worktree']=str(tmp_path/'other')
    if fault=='stage':runtime['stage_recovered_error_condition']='OTHER'
    if fault=='file':f.write_text('changed')
    r=dict(vars(runner));r['read_json']=lambda *_:runtime;r['n4e1_support']=lambda:SimpleNamespace(engineering_condition=lambda:'synthetic')
    if fault=='none':contract.validate_runtime(runtime,tmp_path,r)
    else:
        with pytest.raises(runner.GateError):contract.validate_runtime(runtime,tmp_path,r)


def test_incomplete_cohort_comparisons_do_not_claim_full_denominator(monkeypatch):
    m=module('qd_ed_n23_dev_supervise',monkeypatch)
    result=m.comparison_summary([{'task_id':0,'profile':'C0','success':False},
        {'task_id':0,'profile':'N23','success':True},{'task_id':1,'profile':'C0','success':True}])
    assert result['denominators']=={'C0':2,'Q0':0,'N7':0,'N23':1}
    assert result['matched_comparisons']['C0']=={'paired_tasks':[0],'denominator':1,'gains':1,'losses':0}
    assert result['complete_ten_task_rates'] is False


@pytest.mark.parametrize('fault',['none','source','runtime','protocol','extra','not_reviewed'])
def test_root_final_review_binds_actual_source_runtime_and_protocols(tmp_path,monkeypatch,fault):
    source={'commit':'synthetic','files':[],'sha256':'s'};runtime={'path':'synthetic-runtime','sha256':'r'}
    review={'schema':'n23-final-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
        'dev_protocol':contract.ref(contract.PROTOCOL),'backend_protocol':contract.ref(contract.BACKEND_PROTOCOL),
        'amendment':contract.ref(contract.BUDGET_AMENDMENT),'no_gpu_release':True}
    if fault=='source':review['source']={'commit':'OTHER'}
    if fault=='runtime':review['runtime']={'path':'OTHER','sha256':'r'}
    if fault=='protocol':review['dev_protocol']['sha256']='OTHER'
    if fault=='extra':review['unbounded']=True
    if fault=='not_reviewed':review['disposition']='pending'
    path=tmp_path/'review.json';path.write_text(json.dumps(review));monkeypatch.setattr(contract,'FINAL_REVIEW',path)
    if fault=='none':assert contract.final_review(source,runtime)==contract.ref(path)
    else:
        with pytest.raises(ValueError):contract.final_review(source,runtime)


def test_preflight_freeze_never_bypasses_missing_prerequisite_or_adoption(tmp_path,monkeypatch):
    from scripts import qd_ed_n23_backend_prepare as bp
    (tmp_path/'data').mkdir();(tmp_path/'research-state.yaml').write_text('{}')
    plan={'predecessor_review':None}
    def missing():raise ValueError('N22 not rejected')
    monkeypatch.setattr(contract,'predecessor_review',missing)
    with pytest.raises(ValueError):bp.freeze_plan(plan,tmp_path/'frozen.json',root=tmp_path)
    assert not (tmp_path/'frozen.json').exists()
    monkeypatch.setattr(contract,'predecessor_review',lambda:{'path':'synthetic','sha256':'p'})
    monkeypatch.setattr(admit,'admission',lambda *a,**k:runner.require(False,'not adopted'))
    with pytest.raises(runner.GateError,match='not adopted'):bp.freeze_plan(plan,tmp_path/'frozen.json',root=tmp_path)
    assert not (tmp_path/'frozen.json').exists()
    assert plan['predecessor_review'] is None
