"""Synthetic N23 v2 gate tests. Real historical evidence is forbidden by path guard."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import pytest
import torch
import yaml
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_v2_recovery as recovery
from scripts import qd_ed_n23_v2_backend as backend
from scripts import qd_ed_n23_worker as worker


def write(path,value,jsonl=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(('\n'.join(json.dumps(x) for x in value)+'\n') if jsonl else json.dumps(value))
    return c.ref(path)


@pytest.fixture(autouse=True)
def no_cuda():
    yield
    assert not torch.cuda.is_initialized()


def authority():
    return {'gpu_pool':[7],'max_concurrent_gpu_workers':1,
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':478,'max_gpu_hours':100.,'reserved':dict(runner.N23_BUCKETS),
            'amendment':dict(runner.GPU7_N23_V2_AMENDMENT),'dispatched':0,'gpu_hours_consumed':0.,'running':0,
            'gpu_hour_reservations':{'validation':32.,'formal':12.}},
        'n23_v2_gpu7_binding':{'scope':c.COHORT+'_and_backend_preflight_only','user_reply':c.AUTONOMOUS_REPLY,
            'selected_gpu':7,'addendum_path':str(c.PROTOCOL),'addendum_sha256':c.PROTOCOL_SHA}}


def test_versions_keep_legacy_routing_and_exact_static_algorithm():
    assert runner.n23_support({'n23_cohort':{'schema':'n23-clipped-quality-dev-v2'}}) is c
    assert runner.n23_support().__name__.endswith('qd_ed_n23_dev_contract')
    assert not runner.is_n7_plan({'n23_cohort':{'schema':'n23-clipped-quality-dev-v2'},'candidate_profiles':{'N7':{},'N23':{}}})
    old=runner.n23_support().expected_rows();new=c.expected_rows()
    for a,b in zip(old,new):
        assert {k:v for k,v in a.items() if k not in {'iteration','episode_key'}}=={k:v for k,v in b.items() if k not in {'iteration','episode_key'}}
    assert backend.check_batch is backend.legacy.check_batch and backend.synthetic_batches is backend.legacy.synthetic_batches
    assert backend.iter_batches is backend.legacy.iter_batches and backend.LIMITS==backend.legacy.LIMITS


@pytest.mark.parametrize('iteration',list(c.ALL_PREFLIGHTS|c.ALL_COHORTS))
@pytest.mark.parametrize('event',['reserved','dispatched','valid','aborted'])
def test_cross_version_preflight_is_one_opportunity(iteration,event):
    with pytest.raises(ValueError):c.cross_version_unused([{'identity':{'iteration':iteration},'event':event}])
    c.cross_version_unused([])


def test_full_capacity_reserves_two_recoveries_and_preflight():
    r=dict(vars(runner));snap=runner.budget_snapshot([])
    r['budget_snapshot']=lambda *_:copy.deepcopy(snap)
    c.full_capacity(authority(),[],[],r,preflight=True)
    snap['by_bucket']['recovery']=18
    with pytest.raises(ValueError,match='capacity'):c.full_capacity(authority(),[],[],r,preflight=True)
    c.full_capacity(authority(),[],[],r,preflight=False)
    snap['by_bucket']['recovery']=0;snap['gpu_hours_consumed']=34.
    c.full_capacity(authority(),[],[],r)
    with pytest.raises(ValueError,match='ceiling'):c.full_capacity(authority(),[],[],r,preflight=True)
    snap['gpu_hours_consumed']=0.;snap['dispatched']=216
    with pytest.raises(ValueError,match='protected attempts'):c.full_capacity(authority(),[],[],r,preflight=True)


def failing_case(tmp_path,monkeypatch):
    # Reuse the existing generic runner's real format builder, then execute its unchanged validator/failed_outcome.
    spec=importlib.util.spec_from_file_location('v2_real_runner_format',runner.ROOT/'tests/test_qd_ed_final_runner.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    row,profile,runtime,path,compute=helpers.codex_compute_case(tmp_path,monkeypatch,calls=2)
    r=helpers.runner;row.update(iteration=c.COHORT,profile='C0',episode_key='n23v2_dev_t08_c0_fixture',
        timeout_seconds=1800,budget_bucket='baseline',init_row_sha256='a'*64)
    frozen=runtime['frozen_stage_provider'];frozen.update(timeout_seconds=180,allow_recovered_error_events=True)
    frozen['public_config_sha256']=r.codex_public_config_sha256(frozen)
    runtime.update(stage_recovered_error_condition=r.E2_STAGE_CONDITION,
        stage_engineering_condition=r.n4e1_support().engineering_condition())
    resolved=yaml.safe_load((tmp_path/'.hydra/config.yaml').read_text())
    resolved['perception']['gemini'].update({k:frozen[k] for k in r.CODEX_CONFIG_KEYS},allow_recovered_error_events=True)
    (tmp_path/'.hydra/config.yaml').write_text(yaml.safe_dump(resolved))
    transport={**{k:frozen[k] for k in r.CODEX_CONFIG_KEYS},'auth_mode':'chatgpt','public_config_sha256':frozen['public_config_sha256'],
        'application_max_attempts':1,'internal_http_retry_observation_available':False,'internal_retry_policy':'cli_managed_unknown',
        'allow_recovered_error_events':True,'recovered_error_policy':'pre_final_only_v1'}
    compute.update(stage_transport=transport,provider_token_usage_complete=False)
    for prefix in ('stage_codex_','provider_'):
        compute.update({prefix+'failed_calls':1,prefix+'completed_turns':1,prefix+'usage_complete_calls':1,
            prefix+'input_tokens':100,prefix+'cached_input_tokens':20,prefix+'output_tokens':10,prefix+'call_latency_s':183.})
    write(path,[compute],True)
    base={'episode_id':0,'task_id':row['task_id'],'episode_seed':row['env_seed'],'api_request_attempts':None,
        'api_sdk_retry_attempts':None,'api_request_counter_available':False,
        'codex_logical_call_attempts':1,'codex_completed_turns':1,'codex_failed_calls':0,'codex_usage_complete_calls':1,
        'codex_input_tokens':100,'codex_cached_input_tokens':20,'codex_output_tokens':10,'codex_call_latency_s':2.,
        'query_ok':True,'query_status':'ok','transport':{**transport,'recoverable_error_event_count':0,
            'recoverable_error_item_count':0,'recovered_error_events_accepted':False}}
    ok={**base,'global_step':0}
    failed={**copy.deepcopy(base),'global_step':112,'query_ok':False,'query_status':'error','error':'codex_timeout','raw_response':None,
        'codex_completed_turns':0,'codex_failed_calls':1,'codex_usage_complete_calls':0,'codex_input_tokens':0,
        'codex_cached_input_tokens':0,'codex_output_tokens':0,'codex_call_latency_s':181.}
    failed['transport'].update(event_types=['thread.started','turn.started'],item_types=[],observed_usage=[],completed_turns=0,
        lifecycle={'schema':'codex-stage-lifecycle-v1','observation_complete':True,'observer_error_category':None,
            'first_completed_observed_at':None,'first_complete_usage_observed_at':None,'complete_usage_observed':False,
            'communicate_started_at':100.,'timeout_observed_at':280.1,'cleanup_started_at':280.2,
            'cleanup_returned_at':280.3,'process_exit_observed_at':280.4,
            'events':[{'kind':'thread.started'},{'kind':'turn.started'}]})
    write(tmp_path/'eds_eval/stage_events.jsonl',[ok,failed],True)
    for name in ('eds_metrics.jsonl','safety_events.jsonl'):write(tmp_path/'eds_eval'/name,[],True)
    with pytest.raises(r.GateError,match='token usage incomplete') as caught:r.validate_result(tmp_path,row,profile,runtime)
    event,outcome=r.failed_outcome(caught.value,tmp_path,row,runtime=runtime)
    final={'event':event,**outcome,'attempt_id':'fixture','identity':r.episode_identity(row),'episode_key':row['episode_key'],
        'init_row_sha256':row['init_row_sha256'],'gpu_process_wall_seconds':1717.,'output_dir':str(tmp_path),
        'source_commit':'synthetic','plan_sha256':'plan-sha','retry_of':None}
    return r,row,profile,runtime,final,[ok,failed],compute


def native_report(output):
    return {'schema':'qd-ed-decision-evidence-audit-v1','accepted':True,'evidence_complete':True,
        'episode_dir':str(output/'eds_eval/decision_evidence/episode_000'),
        'episode_compute_file':str(output/'eds_eval/episode_compute.jsonl')}


def test_real_validator_timeout_unknown_cost_is_eligible_but_never_valid(tmp_path,monkeypatch):
    r,row,profile,runtime,final,events,compute=failing_case(tmp_path,monkeypatch)
    before=copy.deepcopy(final);original_require=r.require
    d=recovery.diagnose(final,row,profile,runtime,vars(r),native_report=native_report(tmp_path))
    assert d['eligible_infrastructure_only'] and d['outcome_valid'] is False and d['unknown_token_calls']==1
    assert d['token_usage']=={'input_tokens':None,'cached_input_tokens':None,'output_tokens':None}
    assert d['observed_token_totals']=={'input_tokens':100,'cached_input_tokens':20,'output_tokens':10}
    assert r.require is original_require and final==before and final['required_cost_telemetry_complete'] is False
    assert 'candidate_evaluations' not in final and d['candidate_evaluations']==0
    with pytest.raises(r.GateError,match='token usage incomplete'):r.validate_result(tmp_path,row,profile,runtime)


@pytest.mark.parametrize('fault',['agent','completed','other_error','missing_events','incomplete_observer','early_timeout',
    'extra_failure','wrong_usage','token_imputed','native','valid','recovery','interrupted','wall_timeout','qpos','config','compute_outcome','counter_missing','scoring_postgate'])
def test_typed_timeout_rejects_every_extra_fault(tmp_path,monkeypatch,fault):
    r,row,profile,runtime,final,events,compute=failing_case(tmp_path,monkeypatch)
    bad=events[1];report=native_report(tmp_path)
    if fault=='agent':bad['transport']['item_types']=['agent_message']
    if fault=='completed':bad['transport']['event_types'].append('turn.completed')
    if fault=='other_error':bad['error']='codex_transport_failure'
    if fault=='missing_events':bad['transport'].pop('event_types')
    if fault=='incomplete_observer':bad['transport']['lifecycle']['observation_complete']=False
    if fault=='early_timeout':bad['transport']['lifecycle']['timeout_observed_at']=279.
    if fault=='extra_failure':events[0]['query_ok']=False
    if fault=='wrong_usage':events[0]['codex_usage_complete_calls']=0
    if fault=='token_imputed':final['required_cost_telemetry_complete']=True
    if fault=='native':report['accepted']=False
    if fault=='valid':final['outcome_valid']=True
    if fault=='recovery':final['retry_of']='earlier'
    if fault=='interrupted':final['event']='aborted'
    if fault=='wall_timeout':final['gpu_process_wall_seconds']=1801.
    if fault=='qpos':write(tmp_path/'eds_eval/safety_events.jsonl',[{'event':'gripper_qpos_violation','count':1}],True)
    if fault=='config':p=tmp_path/'.hydra/config.yaml';v=yaml.safe_load(p.read_text());v['seed']=-1;p.write_text(yaml.safe_dump(v))
    if fault=='compute_outcome':compute['outcome']='interrupted'
    if fault=='counter_missing':compute.pop('model_forward_calls')
    if fault=='scoring_postgate':compute['guided_chunks']=1
    write(tmp_path/'eds_eval/episode_compute.jsonl',[compute],True);write(tmp_path/'eds_eval/stage_events.jsonl',events,True)
    with pytest.raises((ValueError,r.GateError,KeyError)):
        recovery.diagnose(final,row,profile,runtime,vars(r),native_report=report)


def test_no_event_safety_absence_is_bound_without_creating_file(tmp_path,monkeypatch):
    r,row,profile,runtime,final,events,compute=failing_case(tmp_path,monkeypatch)
    path=tmp_path/'eds_eval/safety_events.jsonl';path.unlink()
    result=recovery.diagnose(final,row,profile,runtime,vars(r),native_report=native_report(tmp_path))
    assert result['evidence_files']['safety_events']=={'path':str(path),'present':False,'sha256':None}
    assert not path.exists()
    write(path,[],True)
    assert recovery.evidence_files(tmp_path)!=result['evidence_files']
    assert recovery.evidence_files(tmp_path)['safety_events']['present'] is True


@pytest.mark.parametrize('calls,complete,expected',[(3,1,2),(3,2,1),(3,3,0),(None,None,None),(3,None,None),(2,3,None)])
def test_all_attempt_unknown_tokens_do_not_depend_on_recovery_eligibility(calls,complete,expected):
    from scripts import qd_ed_n23_v2_supervise as s
    row={'episode_key':'same-cell','profile':'C0'}
    terminal={'attempt_id':'bad-primary','provider_logical_call_attempts':calls,'provider_usage_complete_calls':complete,
        'provider_token_usage_complete':False,'outcome_valid':False}
    item=s.attempt_record(terminal,row);assert item['unknown_token_calls']==expected
    report=s.summarize([], [item]);assert report['unknown_token_calls']==expected
    assert report['all_attempt_token_usage_complete'] is False
    # Failed recovery is retained with its own missing usage even though it is never eligible again.
    recovery_item=s.attempt_record(dict(terminal,attempt_id='failed-recovery',retry_of='bad-primary'),row)
    report=s.summarize([], [item,recovery_item])
    assert report['unknown_token_calls']==(None if expected is None else 2*expected)
    assert report['all_attempt_denominators']['C0']==2 and report['primary_attempt_denominators']['C0']==1
    assert report['accepted_cell_denominators']['C0']==0


# Adapted synthetic closure/accounting cases from the original N23 runtime suite.
import os
import subprocess
from types import SimpleNamespace
from scripts import qd_ed_n23_v2_prepare as prepare
from scripts import qd_ed_n23_v2_preflight_admit as admit
contract=c


@pytest.fixture(autouse=True)
def synthetic_seeds(tmp_path,monkeypatch):
    seeds={'backend_task_order':list(range(10)),'blocks':{'dev':[dict(task_id=t,env_seed=t+3,policy_seed=t+30,
        init_index=0,init_row_sha256='a'*64,init_file_sha256='b'*64,bddl_sha256='c'*64) for t in range(10)]}}
    seed=tmp_path/'seed.json';write(seed,seeds)
    plan=tmp_path/'n22-plan.json';write(plan,{'seed_plan_path':str(seed),'seed_plan_sha256':worker.sha(seed),
        'n22_cohort':{'cohort_id':'N22_HOLD_LIFT_DEV_20260930'},'code_files':[],'scientific_config_files':[],
        'runtime_manifest_path':str(c.GPU7_RUNTIME)})
    monkeypatch.setattr(c,'SOURCE_PLAN',plan);monkeypatch.setattr(c.v1,'SOURCE_PLAN',plan)


def reservations():
    return [{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':32.,'formal':12.},
        'rationale':'synthetic','time_unix':1.}]

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

@pytest.fixture
def closure(monkeypatch):
    monkeypatch.setattr(contract,'source_delta',lambda *_:[])
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
        monkeypatch.setattr(backend,'verify_preflight_proof',lambda *a:reference['report'])
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

@pytest.mark.parametrize('fault',['none','source','runtime','protocol','extra','not_reviewed'])
def test_root_final_review_binds_actual_source_runtime_and_protocols(tmp_path,monkeypatch,fault):
    source={'commit':'synthetic','files':[],'sha256':'s'};runtime={'path':'synthetic-runtime','sha256':'r'}
    review={'schema':'n23-final-source-runtime-review-v2','disposition':'accepted','source':source,'runtime':runtime,
        'dev_protocol':contract.ref(contract.PROTOCOL),'backend_protocol':contract.ref(contract.BACKEND_PROTOCOL),
        'amendment':contract.ref(contract.BUDGET_AMENDMENT),'no_gpu_release':True,'timeout_observability':contract.ref(contract.OBSERVABILITY)}
    if fault=='source':review['source']={'commit':'OTHER'}
    if fault=='runtime':review['runtime']={'path':'OTHER','sha256':'r'}
    if fault=='protocol':review['dev_protocol']['sha256']='OTHER'
    if fault=='extra':review['unbounded']=True
    if fault=='not_reviewed':review['disposition']='pending'
    path=tmp_path/'review.json';path.write_text(json.dumps(review));monkeypatch.setattr(contract,'FINAL_REVIEW',path)
    if fault=='none':assert contract.final_review(source,runtime)==contract.ref(path)
    else:
        with pytest.raises(ValueError):contract.final_review(source,runtime)


def ledger_triplet(row,aid,valid=False,**fields):
    base={'attempt_id':aid,'identity':runner.episode_identity(row),'episode_key':row['episode_key'],
        'budget_bucket':row['budget_bucket'],'retry_of':None,**fields}
    return [{**base,'event':ev,**({'outcome_valid':valid} if ev=='valid' else {})} for ev in ('reserved','dispatched','valid')]


@pytest.mark.parametrize('fault',['none','valid','incomplete','same_cell_recovery','two_recoveries','identity','another_primary'])
def test_typed_recovery_is_one_per_cell_and_two_per_cohort(fault):
    row=c.expected_rows()[0];events=ledger_triplet(row,'primary')
    if fault=='valid':events[-1]['outcome_valid']=True
    if fault=='incomplete':events.pop()
    if fault=='same_cell_recovery':events+=ledger_triplet(row,'recovery',retry_of='primary',budget_bucket='recovery')
    if fault=='two_recoveries':
        for i in (1,2):events+=ledger_triplet(c.expected_rows()[i],str(i),retry_of='old'+str(i),budget_bucket='recovery')
    if fault=='identity':events[0]['identity']['env_seed']+=1
    if fault=='another_primary':events+=ledger_triplet(row,'other-primary')
    if fault=='none':assert recovery.check_cell_history(events,row,'primary',vars(runner))==events[-1]
    else:
        with pytest.raises(ValueError):recovery.check_cell_history(events,row,'primary',vars(runner))


@pytest.mark.parametrize('arm',c.ARMS)
@pytest.mark.parametrize('scenario',['valid','missing_receipt','typed_recovery','failed_recovery'])
def test_real_run_plan_wrapper_accounting_and_recovery_identity(tmp_path,monkeypatch,arm,scenario):
    (tmp_path/'data').mkdir();state=authority();state.update(run_name='CPU',worktree=str(tmp_path),artifacts=str(tmp_path/'artifact'))
    (tmp_path/'research-state.yaml').write_text(yaml.safe_dump(state));write(tmp_path/'data/gpu-hour-reservation-ledger.jsonl',reservations(),True)
    row=next(v for v in c.expected_rows() if v['profile']==arm)
    plan={'source_commit':'synthetic','run_name':'CPU','worktree':str(tmp_path),'artifact_root':state['artifacts'],
        'candidate_profiles':{'N7':{},'N23':{}},'n23_cohort':{'schema':'n23-clipped-quality-dev-v2'},'episodes':[row],
        'phase_authorization':{'dev':True,'validation':False,'formal':False},'profiles_sha256':'p',
        'runtime_manifest_sha256':'r','runtime_manifest_path':'synthetic','runtime_inventory_sha256':'i'}
    planpath=tmp_path/'plan.json';write(planpath,plan)
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID,'egl_device_index':4},'environment':{}}
    monkeypatch.setattr(runner,'validate_plan',lambda *a,**k:(plan,{'profiles':{arm:{}}},runtime))
    monkeypatch.setattr(c,'protected_budget',lambda *a,**k:None);monkeypatch.setattr(c,'admission',lambda *a,**k:{})
    monkeypatch.setattr(runner,'gpu_admission',lambda **k:{});monkeypatch.setattr(runner,'child_environment',lambda *a:{})
    provider=[];monkeypatch.setattr(runner,'verify_provider',lambda *a,**k:provider.append(1))
    monkeypatch.setattr(worker,'build_context',lambda *a:{'synthetic':True})
    original=[str(runner.PYTHON),str(tmp_path/'main.py'),'policy.type=rdt','literal=value with spaces']
    rows=[]
    def command(p,m,rt,r,aid):rows.append(copy.deepcopy(r));return original,Path(p['artifact_root'])/'attempts'/aid
    monkeypatch.setattr(runner,'build_command',command)
    launched=[]
    def popen(argv,**kwargs):
        launched.append(argv);assert argv[1]==str(tmp_path/'scripts/qd_ed_n23_worker.py')
        assert argv[argv.index('--')+1:]==original[2:] and str(tmp_path/'main.py') in argv
        assert runner.read_events(tmp_path/'data/attempt-ledger.jsonl')[-1]['event']=='dispatched'
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(runner.subprocess,'Popen',popen)
    monkeypatch.setattr(runner,'wait_exclusively',lambda p,t,**k:(runner.require(t==1800,'whole worker timeout') or 0))
    monkeypatch.setattr(runner,'terminate_owned',lambda p:None)
    def outcome(*a):
        if scenario in {'typed_recovery','failed_recovery'} and (len(launched)==1 or scenario=='failed_recovery'):
            raise runner.GateError('Codex token usage incomplete')
        return {'success':False,'outcome_valid':True,'required_cost_telemetry_complete':True}
    monkeypatch.setattr(runner,'validate_result',outcome)
    def audit(output,r):
        if scenario=='missing_receipt':raise ValueError('missing bound receipt')
        pid=json.loads((output/'process.json').read_text());assert pid['pid']==os.getpid()
        write(output/'eds_eval/in-worker-audit-receipt.json',{})
        return {'accepted':True,'evidence_complete':True}
    monkeypatch.setattr(c,'read_worker_report',audit)
    with c.supervised_scope(plan,tmp_path,row['episode_key']):
        if scenario=='valid':runner.run_plan(planpath,split='dev',iteration=c.COHORT,root=tmp_path)
        else:
            with pytest.raises(runner.GateError):runner.run_plan(planpath,split='dev',iteration=c.COHORT,root=tmp_path)
    primary=runner.read_events(tmp_path/'data/attempt-ledger.jsonl')[-1]
    if scenario in {'typed_recovery','failed_recovery'}:
        assert primary['outcome_valid'] is False and primary['n23_worker_receipt'] and primary['process']['pid']==os.getpid()
        record={'primary_attempt_id':primary['attempt_id'],'plan':c.ref(planpath)};reference=write(tmp_path/'eligibility.json',record)
        monkeypatch.setattr(recovery,'verify_eligibility',lambda *a:record)
        with c.supervised_scope(plan,tmp_path,row['episode_key'],eligibility=reference):
            if scenario=='typed_recovery':runner.run_plan(planpath,split='dev',iteration=c.COHORT,root=tmp_path)
            else:
                with pytest.raises(runner.GateError):runner.run_plan(planpath,split='dev',iteration=c.COHORT,root=tmp_path)
        assert rows[1]==dict(row,budget_bucket='recovery',retry_of=primary['attempt_id'],n23_v2_recovery_eligibility=reference)
    events=runner.read_events(tmp_path/'data/attempt-ledger.jsonl');snap=runner.budget_snapshot(events)
    expected=2 if 'recovery' in scenario else 1
    assert snap['dispatched']==expected and snap['running']==0 and len(launched)==len(provider)==expected
    assert snap['by_bucket'][row['budget_bucket']]==1 and snap['by_bucket']['recovery']==expected-1
    assert events[-1]['outcome_valid'] is (scenario in {'valid','typed_recovery'})
    assert all(e['gpu_process_wall_seconds']>=0 for e in events if e['event'] in runner.TERMINAL)
    assert all(e['identity']==runner.episode_identity(row) for e in events)


@pytest.fixture
def predecessor_fixture(tmp_path,monkeypatch):
    from scripts import qd_ed_n23_v2_predecessor as p
    rows=[dict(v,iteration=p.N22_COHORT) for v in c.expected_rows()]
    for v in rows:v['episode_key']=v['episode_key'].replace('n23v2','n22')
    plan={'n22_cohort':{'cohort_id':p.N22_COHORT},'source_commit':p.N22_SOURCE,'worktree':str(tmp_path),'episodes':rows}
    planpath=tmp_path/'frozen-plan.json';planref=write(planpath,plan)
    monkeypatch.setattr(p,'N22_PLAN_SHA',planref['sha256']);monkeypatch.setattr(c,'SOURCE_PLAN',planpath)
    status={'status':'failed','dev_gate_promoted':False,'completed_keys':[v['episode_key'] for v in rows[:16]]}
    statuspath=tmp_path/'physical/status.json';statusref=write(statuspath,status)
    (tmp_path/'logical').symlink_to(tmp_path/'physical',target_is_directory=True)
    output=tmp_path/'output'
    for f in ['stage_events.jsonl','episode_compute.jsonl','episode_metadata.jsonl','eds_metrics.jsonl']:
        write(output/'eds_eval'/f,[],True)
    write(output/'.hydra/config.yaml',{});write(output/'results.txt',{})
    write(output/'eds_eval/decision_evidence/episode_000/status.json',{})
    (output/'eds_eval/decision_evidence/episode_000/events.jsonl').write_text('')
    auditref=write(tmp_path/'audit.json',native_report(output))
    terminal={**ledger_triplet(rows[16],p.NAMED_ATTEMPT)[-1],'source_commit':p.N22_SOURCE,'plan_sha256':planref['sha256'],
        'compute_outcome':'completed','required_cost_telemetry_complete':False,'output_dir':str(output)}
    terminalref=write(tmp_path/'terminal.json',terminal)
    evidence=recovery.evidence_files(output)
    diag={'schema':'n23-v2-timeout-diagnostic-v1','eligible_infrastructure_only':True,'outcome_valid':False,
        'attempt_id':p.NAMED_ATTEMPT,'source_commit':p.N22_SOURCE,'plan_sha256':planref['sha256'],'evidence_files':evidence,
        'global_step':112,'unknown_token_calls':1,'timeout_observability':c.ref(c.OBSERVABILITY),
        'original_required_cost_telemetry_complete':False,'all_attempt_token_usage_complete':False,
        'diagnostic_reader':c.ref(recovery.__file__)}
    diagref=write(tmp_path/'diagnostic.json',diag)
    resultrows=[];journal=[]
    for i,row in enumerate(rows[:17]):
        aid=p.NAMED_ATTEMPT if i==16 else 'prior'+str(i)
        resultrows.append(dict(attempt_id=aid,audit=auditref,outcome_valid=i<16,native_valid=i<16))
        group=ledger_triplet(row,aid,i<16,source_commit=p.N22_SOURCE,plan_sha256=planref['sha256'])
        if i==16:group[-1]=terminal
        journal+=group
    ledger=tmp_path/'data/attempt-ledger.jsonl';write(ledger,journal,True)
    closure={'schema':'n22-terminal-ledger-closure-v1','ledger':str(ledger),'snapshot_bytes':ledger.stat().st_size,
        'snapshot_sha256':c.sha(ledger),'cohort_id':p.N22_COHORT,'attempt_ids':[v['attempt_id'] for v in resultrows],
        'all_terminal':True,'dispatched':17,'unsettled':0,'owned_worker_absent':True,'source_commit':p.N22_SOURCE}
    closureref=write(tmp_path/'closure.json',closure)
    result={'schema':'n22-dev-cohort-result-v1','cohort_id':p.N22_COHORT,'source_commit':p.N22_SOURCE,'plan':planref,
        'decision':'INVALID_OR_INTERRUPTED','dev_gate_promoted':False,'dispatched':17,'audited_cells':16,'planned':40,
        'rows':resultrows,'terminal_status':{'path':str(tmp_path/'logical/status.json'),'sha256':statusref['sha256'],'content':status}}
    resultref=write(tmp_path/'result.json',result)
    proof={'schema':'n23-named-n22-timeout-proof-v2','disposition':'invalid_incomplete_not_scientific_rejection',
        'allow_n23_v2':True,'source_plan':planref,'source_commit':p.N22_SOURCE,'terminal_status':statusref,
        'terminal_result':resultref,'named_attempt':p.NAMED_ATTEMPT,'named_terminal':terminalref,
        'native_audit':auditref,'timeout_diagnostic':diagref,'evidence_files':evidence,'ledger_closure':closureref,
        'prior_cell_audits':[{'attempt_id':v['attempt_id'],'report':auditref} for v in resultrows[:16]],
        'native_evidence':worker.evidence_record(output),'owned_worker_absent':True,'n22_promoted':False,
        'timeout_observability':c.ref(c.OBSERVABILITY)}
    review={'schema':'n23-n22-prerequisite-v2','source_plan':planref,'route':'named_n22_c0_task4_timeout',
        'allow_n23_v2':True,'rationale':'synthetic exact timeout review','timeout_observability':c.ref(c.OBSERVABILITY),
        'named_failure_proof':write(tmp_path/'proof.json',proof)}
    return p,review,proof,diag,closure,result,output


@pytest.mark.parametrize('fault',['none','generic_invalid','rejected_instead','promoted','source','attempt','step','reader',
    'token_imputed','prior_missing','unsettled','status_alias_changed','evidence_changed','safety_now_present','ledger_changed'])
def test_predecessor_exact_named_closed_route_and_path_alias(predecessor_fixture,tmp_path,fault):
    p,review,proof,diag,closure,result,output=predecessor_fixture
    if fault=='generic_invalid':review['route']='invalid_resolved'
    if fault=='rejected_instead':result['decision']='REJECT'
    if fault=='promoted':proof['n22_promoted']=True
    if fault=='source':proof['source_commit']='other'
    if fault=='attempt':proof['named_attempt']='other'
    if fault=='step':diag['global_step']=113
    if fault=='reader':diag['diagnostic_reader']['sha256']='other'
    if fault=='token_imputed':diag['all_attempt_token_usage_complete']=True
    if fault=='prior_missing':proof['prior_cell_audits'].pop()
    if fault=='unsettled':closure['unsettled']=1
    if fault=='status_alias_changed':result['terminal_status']['sha256']='other'
    if fault=='evidence_changed':write(output/'eds_eval/stage_events.jsonl',[{}],True)
    if fault=='safety_now_present':write(output/'eds_eval/safety_events.jsonl',[],True)
    if fault=='ledger_changed':Path(closure['ledger']).write_text('{}\n')
    proof['timeout_diagnostic']=write(tmp_path/'diagnostic.json',diag)
    proof['ledger_closure']=write(tmp_path/'closure.json',closure)
    proof['terminal_result']=write(tmp_path/'result.json',result)
    review['named_failure_proof']=write(tmp_path/'proof.json',proof);ref=write(tmp_path/'review.json',review)
    if fault=='none':assert p.gate(ref)==review
    else:
        with pytest.raises((ValueError,KeyError)):p.gate(ref)


@pytest.mark.parametrize('fault',['none','safety_presence','source','seed','receipt','plan_bytes','valid_primary'])
def test_eligibility_rebuilds_measured_real_runner_schema(tmp_path,monkeypatch,fault):
    (tmp_path/'output').mkdir()
    r,row,profile,runtime,final,events,compute=failing_case(tmp_path/'output',monkeypatch)
    output=Path(final['output_dir']);manifest=tmp_path/'profiles.json';runtimepath=tmp_path/'runtime.json'
    write(manifest,{'profiles':{'C0':profile}});write(runtimepath,runtime)
    plan={'episodes':[row],'source_commit':'synthetic','profiles_path':str(manifest),'profiles_sha256':c.sha(manifest),
        'candidate_profiles':{},'runtime_manifest_path':str(runtimepath),'runtime_manifest_sha256':c.sha(runtimepath),
        'runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path),'worktree':str(tmp_path)}
    planpath=tmp_path/'plan.json';write(planpath,plan)
    receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
    report=native_report(output);write(output/'eds_eval/decision-evidence-audit.json',report);write(output/'process.json',{'pid':1})
    final.update(plan_sha256=c.sha(planpath),profile_manifest_sha256=plan['profiles_sha256'],
        runtime_manifest_sha256=plan['runtime_manifest_sha256'],runtime_inventory_sha256='inventory',physical_gpu=7,
        n23_worker_receipt=receipt)
    write(output/'attempt-result.json',final)
    journal=ledger_triplet(row,final['attempt_id']);journal[-1]=final
    monkeypatch.setattr(c,'read_worker_report',lambda *_:report)
    record=recovery.create_eligibility(planpath,plan,row,final,profile,runtime,journal,tmp_path,vars(r))
    reference=write(tmp_path/'eligibility.json',record)
    if fault=='safety_presence':(output/'eds_eval/safety_events.jsonl').unlink()
    if fault=='source':record['source_commit']='other';reference=write(tmp_path/'eligibility.json',record)
    if fault=='seed':row['env_seed']+=1
    if fault=='receipt':write(output/'eds_eval/in-worker-audit-receipt.json',{'changed':True})
    if fault=='plan_bytes':planpath.write_text('{}')
    if fault=='valid_primary':journal[-1]['outcome_valid']=True
    if fault=='none':
        assert recovery.verify_eligibility(reference,plan,row,journal,tmp_path,vars(r))==record
        with c.supervised_scope(plan,tmp_path,row['episode_key'],eligibility=reference):
            assert c.effective_row(plan,row,journal,tmp_path,vars(r))==dict(row,budget_bucket='recovery',
                retry_of=final['attempt_id'],n23_v2_recovery_eligibility=reference)
    else:
        with pytest.raises((ValueError,r.GateError)):recovery.verify_eligibility(reference,plan,row,journal,tmp_path,vars(r))


@pytest.mark.parametrize('case,count,status,promoted',[
    ('all_fail',24,'rejected_numeric_futility',False),('five',40,'completed_all_forty_audited',True),
    ('equal',40,'completed_all_forty_audited',True),('inferior',40,'completed_all_forty_audited',False),
    ('zero_clip',40,'completed_all_forty_audited',True),('unguided',40,'completed_all_forty_audited',False),
    ('invalid',7,'failed',False),('audit',4,'failed',False),('compute',4,'failed',False),('inactive',4,'failed',False),
    ('recovered',41,'completed_all_forty_audited',True),('failed_recovery',8,'failed',False),
    ('two_recovered',42,'completed_all_forty_audited',True),('third_recovery',9,'failed',False)])
def test_v2_supervisor_full_matrix_first_valid_and_stop_rules(tmp_path,monkeypatch,case,count,status,promoted):
    from scripts import qd_ed_n23_v2_supervise as s
    plan={'source_commit':'synthetic','artifact_root':str(tmp_path),'episodes':c.expected_rows()}
    monkeypatch.setattr(s,'ROOT',tmp_path);monkeypatch.setattr(c,'RUN_DIR',tmp_path/'variant')
    monkeypatch.setattr(runner,'validate_plan',lambda *a,**k:(plan,{'profiles':{a:{} for a in c.ARMS}},{}))
    monkeypatch.setattr(s,'release_check',lambda *a:None)
    monkeypatch.setattr(s.queue,'inventory',lambda:{7:{'uuid':c.GPU7_UUID}})
    monkeypatch.setattr(s.queue,'reservation_admission',lambda *_:None);monkeypatch.setattr(runner,'gpu_admission',lambda **_:None)
    called=[];bycell={};eligibilities=[]
    def run(planpath,actual,row,*,eligibility=None):
        called.append(row);i=len(called);task=row['task_id'];arm=row['profile'];key=row['episode_key']
        out=tmp_path/f'cell{i}';metric={'qd_archive_active_for_chunk':not(case=='inactive' and arm=='N23'),
            'qd_quality_mode':'actuator_clipped_provider_v1' if arm=='N23' else 'provider',
            'score_call_count':11,'search_evaluation_count':176,'resample_count':10,'renoise_count':10,'rollout_count':10,
            'qd_actuator_overhead_seconds':.01,'qd_actuator_quality_batches':11,'qd_actuator_quality_candidates':176,
            'qd_actuator_clipped_prefix_candidates':0 if case=='zero_clip' else 1}
        write(out/'eds_eval/eds_metrics.jsonl',[] if case=='unguided' else [metric],True)
        recovery_case=case in {'recovered','failed_recovery','two_recovered','third_recovery'}
        invalid=(case=='invalid' and i==7) or (recovery_case and eligibility is None and
            len(bycell) in ({6} if case in {'recovered','failed_recovery'} else {4,5} if case=='two_recovered' else {4,5,6}))
        invalid=invalid or (case=='failed_recovery' and eligibility is not None)
        successes=False if case=='all_fail' else task in {1,2,3,4,5} if arm=='N23' else (
            task<(6 if case=='inferior' else 5) if case in {'equal','inferior'} else False)
        result={'event':'valid','attempt_id':out.name,'episode_key':key,'output_dir':str(out),'outcome_valid':not invalid,
            'success':successes,**{k:1 for k in s.COST_FIELDS},'guided_chunks':0 if case=='unguided' else 1,
            'required_cost_telemetry_complete':not invalid,'provider_token_usage_complete':not invalid,
            'provider_logical_call_attempts':3,'provider_usage_complete_calls':1 if case=='invalid' and invalid else 2 if invalid else 3,
            'retry_of':bycell[key]['attempt_id'] if eligibility else None}
        bycell[key]=result;return result
    monkeypatch.setattr(s,'one_attempt',run)
    def eligibility(*args):
        final=args[3]
        if case=='invalid':raise ValueError('not eligible; two missing completions')
        worker.require(len(eligibilities)<2,'two recovery slots used');eligibilities.append(final['attempt_id'])
        return {'diagnostic':{'unknown_token_calls':1},'primary_attempt_id':final['attempt_id']}
    monkeypatch.setattr(recovery,'create_eligibility',eligibility)
    def accepted(plan,row,*_):
        result=bycell[row['episode_key']];worker.require(result['outcome_valid'],'failed recovery stops')
        worker.require(not(case=='audit' and row['profile']=='N23'),'bad native audit');return result
    monkeypatch.setattr(c,'accepted_cell',accepted)
    def report(*args):
        result={'accepted':True,'evidence_complete':True}
        if case!='unguided':
            result['n5_grasp_timing_audit']={'checked_decisions':1,'parent_rounds_verified':10}
            if called[-1]['profile']=='N23':result['n23_actuator_clipped_quality_audit']={
                'score_batches_verified':10 if case=='compute' else 11,'candidate_scores_verified':176,
                'clipped_prefix_candidates':0 if case=='zero_clip' else 1,'rank_changed_batches':0}
        return result
    monkeypatch.setattr(c,'read_worker_report',report)
    dst=tmp_path/'status.json';monkeypatch.setattr(sys,'argv',['test','--plan','synthetic','--release','synthetic','--status',str(dst)])
    if status=='failed':
        with pytest.raises(ValueError):s.main()
    else:s.main()
    result=json.loads(dst.read_text());assert result['status']==status and len(called)==count and result['dev_gate_promoted']==promoted
    assert set(result['native']['N7'])=={'guided_decisions','parent_rounds_verified'}
    assert sum(result['all_attempt_denominators'].values())==count
    if case in {'recovered','two_recovered'}:
        assert sum(result['accepted_cell_denominators'].values())==sum(result['primary_attempt_denominators'].values())==40
        assert result['unknown_token_calls']==count-40 and not result['all_attempt_token_usage_complete']
    if case in {'invalid','failed_recovery'}:assert result['unknown_token_calls']==2
    with pytest.raises(ValueError):s.main()


def test_supervisor_journal_exception_keeps_new_invalid_terminal(tmp_path,monkeypatch):
    from scripts import qd_ed_n23_v2_supervise as s
    monkeypatch.setattr(s,'ROOT',tmp_path)
    row=c.expected_rows()[0];plan={'episodes':[row],'source_commit':'synthetic'}
    terminal=ledger_triplet(row,'new')[-1]
    def run(*a,**k):
        write(tmp_path/'data/attempt-ledger.jsonl',[terminal],True)
        raise runner.GateError('normal runner rejects invalid terminal after journaling')
    monkeypatch.setattr(runner,'run_plan',run)
    assert s.one_attempt('synthetic',plan,row)==terminal
    # A gate failure before charging cannot masquerade as the previous terminal.
    with pytest.raises(runner.GateError):s.one_attempt('synthetic',plan,row)


def test_admission_prefix_and_futility_only_after_complete_quad(tmp_path,monkeypatch):
    rows=c.expected_rows();plan={'episodes':rows,'source_commit':'synthetic'}
    def accepted(plan,row,events,*_):
        matching=[e for e in events if e['episode_key']==row['episode_key']]
        worker.require(len(matching)==1,'previous cell missing');return matching[0]
    monkeypatch.setattr(c,'accepted_cell',accepted)
    def prefix(n):return [{'identity':runner.episode_identity(v),'episode_key':v['episode_key'],'success':False} for v in rows[:n]]
    assert c.admission(plan,{},rows[4],prefix(4),[],tmp_path,vars(runner))['n23_cohort_id']==c.COHORT
    assert c.admission(plan,{},rows[23],prefix(23),[],tmp_path,vars(runner))['n23_arm_role']=='candidate'
    for row,events in ((rows[24],prefix(24)),(rows[0],prefix(1)),(rows[4],prefix(3))):
        with pytest.raises(ValueError):c.admission(plan,{},row,events,[],tmp_path,vars(runner))
    with c.supervised_scope(plan,tmp_path,rows[0]['episode_key']):
        c.require_scope(plan,tmp_path,vars(runner),rows[0])
        with pytest.raises(ValueError):c.require_scope(plan,tmp_path,vars(runner),rows[1])
    with pytest.raises(ValueError):c.require_scope(plan,tmp_path,vars(runner))


@pytest.mark.parametrize('kind',['primary','recovery','failed_recovery','third','missing_receipt','wrong_plan','wrong_runtime','wrong_init','bad_native'])
def test_first_valid_cell_rechecks_lineage_plan_and_real_terminal_fields(tmp_path,monkeypatch,kind):
    row=c.expected_rows()[0];plan={'episodes':[row],'source_commit':'synthetic','profiles_sha256':'profile',
        'runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path)}
    planref=write(tmp_path/'plan.json',plan)
    output=tmp_path/'primary';receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
    final={**ledger_triplet(row,'primary',True)[-1],'required_cost_telemetry_complete':True,'source_commit':'synthetic',
        'plan_sha256':planref['sha256'],'profile_manifest_sha256':'profile','runtime_manifest_sha256':'runtime',
        'runtime_inventory_sha256':'inventory','init_row_sha256':row['init_row_sha256'],'physical_gpu':7,
        'output_dir':str(output),'n23_worker_receipt':receipt}
    journal=ledger_triplet(row,'primary',True);journal[-1]=final
    record={'primary_attempt_id':'primary'};eligibility=write(tmp_path/'eligibility.json',record);seen=[]
    def verify(ref,pl,r,events,*_):seen.append(events);assert len(events)==3;return record
    monkeypatch.setattr(recovery,'verify_eligibility',verify)
    if kind in {'recovery','failed_recovery','third'}:
        journal[-1]['outcome_valid']=False
        output=tmp_path/'recovered';receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
        extra=ledger_triplet(row,'recovered',kind!='failed_recovery',retry_of='primary',budget_bucket='recovery',
            n23_v2_recovery_eligibility=eligibility)
        extra[-1]={**final,**extra[-1],'output_dir':str(output),'n23_worker_receipt':receipt}
        final=extra[-1];journal+=extra
        if kind=='third':journal+=ledger_triplet(row,'third',True,retry_of='recovered',budget_bucket='recovery')
    write(output/'n23-worker-context.json',{'plan':planref})
    if kind=='missing_receipt':final.pop('n23_worker_receipt')
    if kind=='wrong_plan':final['plan_sha256']='different'
    if kind=='wrong_runtime':final['runtime_manifest_sha256']='different'
    if kind=='wrong_init':final['init_row_sha256']='different'
    monkeypatch.setattr(c,'read_worker_report',lambda *_:{'accepted':kind!='bad_native','evidence_complete':True})
    if kind in {'primary','recovery'}:
        assert c.accepted_cell(plan,row,journal,tmp_path,vars(runner))==final
        if kind=='recovery':assert seen==[journal[:3]]
    else:
        with pytest.raises(ValueError):c.accepted_cell(plan,row,journal,tmp_path,vars(runner))


@pytest.mark.parametrize('fault',['none','failed','source','unmetered','process','wrong_bucket','missing_batch','cpu','release_hash','wall'])
def test_v2_backend_proof_json_binding_without_any_cuda(tmp_path,monkeypatch,fault):
    runtime=write(tmp_path/'runtime.json',{'gpu_mapping':{'uuid':'GPU-fixture'}})
    plan={'source':{'commit':'synthetic'},'runtime':runtime,'limits':backend.LIMITS,'corpus':{}}
    planref=write(tmp_path/'plan.json',plan);release=write(tmp_path/'release.json',{});ctx=write(tmp_path/'context.json',{})
    report={'schema':'n23-backend-preflight-proof-v2','accepted':True,'task_outcome':False,'plan':planref,
        'source':plan['source'],'runtime':runtime,'limits':backend.LIMITS,'process':{'pid':1,'proc_start_ticks':'2','boot_id':'3'},
        'attempt_id':'one','release':release,'attempt_context':ctx,'worker_wall_seconds':1.,
        'backend':{'kind':'cuda','logical_device':'cuda:0','physical_uuid':'GPU-fixture','torch_version':'synthetic',
            'cuda_version':'synthetic','dtype_coverage':['torch.float32','torch.bfloat16']},
        'batches':[{'accepted':True,'candidates':16,'mismatches':[]} for _ in range(176)],
        'synthetic':[{'accepted':True,'mismatches':[]}]*2,'wrong_bounds_rejected':True}
    write(tmp_path/'n23-backend-preflight-start.json',{'schema':'n23-backend-preflight-start-v2','process':report['process'],
        'plan':planref,'attempt_id':'one','source':plan['source']})
    source=copy.deepcopy(plan['source'])
    if fault=='failed':report['accepted']=False
    if fault=='source':source['commit']='different'
    if fault=='missing_batch':report['batches'].pop()
    if fault=='cpu':report['backend']['kind']='cpu'
    if fault=='release_hash':write(tmp_path/'release.json',{'changed':True})
    if fault=='wall':report['worker_wall_seconds']=121.
    reference=write(tmp_path/'proof.json',report)
    terminal={'budget_bucket':'development' if fault=='wrong_bucket' else 'recovery','attempt_id':'one','event':'valid',
        'outcome_valid':True,'gpu_process_wall_seconds':0 if fault=='unmetered' else 2.,
        'backend_preflight_report':reference,'process':{} if fault=='process' else report['process']}
    monkeypatch.setattr(backend,'validate_plan',lambda *_:{});monkeypatch.setattr(backend,'verify_corpus_files',lambda *_:None)
    monkeypatch.setattr(backend,'create_backend',lambda *a,**k:(_ for _ in ()).throw(AssertionError('CUDA forbidden in proof reader')))
    if fault=='none':assert backend.verify_preflight_proof(planref['path'],reference['path'],terminal,source)==reference
    else:
        with pytest.raises(ValueError):backend.verify_preflight_proof(planref['path'],reference['path'],terminal,source)


@pytest.mark.parametrize('fault',['none','wrong_root','escaping_target','changed_bytes','resolved_path','link_target'])
def test_frozen_runtime_compatibility_alias_keeps_strict_file_ownership(tmp_path,fault):
    root=tmp_path/'canonical/worktree';root.mkdir(parents=True)
    alias=tmp_path/'compatibility-worktree';alias.symlink_to(root,target_is_directory=True)
    target=root/'third_party/rdt/.gitignore';target.parent.mkdir(parents=True);target.write_text('frozen bytes')
    lexical=alias/'third_party/rdt/.gitignore'
    record={'path':str(lexical),'resolved_path':str(target),'sha256':worker.sha(target),'size_bytes':target.stat().st_size}
    runtime={'schema':'qd-ed-runtime-setup-v1','worktree':str(alias),'artifact_root':str(tmp_path/'artifacts'),
        'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID,'egl_device_index':4},
        'cuda_egl_verified':True,'cuda_egl_probe':{'resource_id':c.GPU7_PROOF},
        'stage_recovered_error_condition':runner.E2_STAGE_CONDITION,'stage_engineering_condition':'synthetic',
        'frozen_stage_provider':{'allow_recovered_error_events':True},'files':[record]}
    if fault=='wrong_root':runtime['worktree']=str(tmp_path/'another-root')
    if fault=='escaping_target':
        outside=tmp_path/'outside';outside.write_text('frozen bytes');target.unlink();target.symlink_to(outside)
        record['resolved_path']=str(outside)
    if fault=='changed_bytes':target.write_text('tampered bytes')
    if fault=='resolved_path':record['resolved_path']=str(tmp_path/'different')
    if fault=='link_target':record['link_target']='missing-link-target'
    r=dict(vars(runner));r['read_json']=lambda *_:runtime
    r['n4e1_support']=lambda:SimpleNamespace(engineering_condition=lambda:'synthetic')
    original_verify=r['verify_files']
    if fault=='none':
        # The unchanged v1 gate reproduces the former lexical-prefix failure.
        with pytest.raises(runner.GateError,match='escapes owned roots'):c.v1.validate_runtime(runtime,root,r)
        c.validate_runtime(runtime,root,r)
    else:
        with pytest.raises(runner.GateError):c.validate_runtime(runtime,root,r)
    assert r['verify_files'] is original_verify
