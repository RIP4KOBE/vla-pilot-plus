"""Synthetic conditional validation gates; no protected outcome inputs."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as dev
from scripts import qd_ed_n23_validation_contract as c
from scripts import qd_ed_n23_validation_identity as identity
from scripts import qd_ed_n23_validation_bridge as bridge
from scripts import qd_ed_n23_validation_prepare as prepare
from scripts import qd_ed_n23_validation_recovery as recovery
from scripts import qd_ed_n23_validation_report as reporting
from test_qd_ed_n23_v2 import authority as dev_authority, failing_case


@pytest.fixture(autouse=True)
def no_cuda():
    yield
    assert not torch.cuda.is_initialized()


def write(path,value,jsonl=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text((''.join(json.dumps(v)+'\n' for v in value)) if jsonl else json.dumps(value))
    return c.ref(path)


def seeds():
    blocks={}
    for i,name in enumerate(['dev','formal']+[f'validation_c{a}_b{b}' for a in range(1,5) for b in (1,2)]):
        blocks[name]=[{'task_id':t,'env_seed':1000*i+t,'policy_seed':20000+1000*i+t,'init_index':0,
            'init_row_sha256':f'{t:064x}','init_file_sha256':'a'*64,'bddl_sha256':'b'*64} for t in range(10)]
    return {'backend_task_order':list(range(10)),'blocks':blocks}


def state():
    s=dev_authority();s['n23_validation_authorization']={'schema':'n23-validation-authorization-v1',
        'cohort_id':c.COHORT,'seed_cohort':'c2','protocol_sha256':c.PROTOCOL_SHA,
        'dev_review':{'fixture':1},'source_review':{'fixture':2},'run_once':True,'physical_gpu':7}
    return s


def events_for(row,aid='fixture',*,success=False,valid=True,retry=None,bucket=None):
    base={'attempt_id':aid,'identity':r.episode_identity(row),'episode_key':row['episode_key'],
        'budget_bucket':bucket or row['budget_bucket'],'retry_of':retry}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},
        {**base,'event':'valid','outcome_valid':valid,'success':success,'gpu_process_wall_seconds':1.,
         'required_cost_telemetry_complete':valid,'provider_logical_call_attempts':2,'provider_usage_complete_calls':2 if valid else 1}]


def test_frozen_matrix_and_unchanged_dev_routes():
    rows=identity.rows_for(seeds(),'c2')
    assert [(v['seed_block'],v['task_id'],v['profile']) for v in rows]==[
        (f'validation_c2_b{b}',t,a) for b in (1,2) for t in range(10) for a in c.ARMS]
    assert len(rows)==60 and all(v['budget_bucket']==v['split']=='validation' for v in rows)
    p={'n23_validation':{},'candidate_profiles':{'N23':{}}}
    assert r.is_n23_validation_plan(p) and not r.is_n23_v2_plan(p) and not r.is_n7_plan(p)
    assert r.n23_support(p) is c
    assert r.n23_support({'n23_cohort':{'schema':'n23-clipped-quality-dev-v2'}}) is dev
    assert r.n23_support().__name__.endswith('qd_ed_n23_dev_contract')


@pytest.mark.parametrize('source',['history','registry','reserved','dispatched'])
def test_any_exposure_consumes_whole_cohort(source):
    s=seeds();pair=identity.pair(s['blocks']['validation_c1_b2'][9])
    history=[{'pair':pair}] if source=='history' else []
    registry=[{'pair':pair}] if source in {'registry','dispatched'} else []
    ledger=[{'pair':pair,'attempt_id':'old','iteration':'old','profile':'C0','split':'validation','event':source}] if source in {'reserved','dispatched'} else []
    assert identity.first_unused(s,history,registry,ledger)=='c2'
    if source=='dispatched':
        with pytest.raises(ValueError,match='reconciliation'):identity.first_unused(s,[],[],ledger)


@pytest.mark.parametrize('fault',['duplicate','task_order','policy_missing','all_used','second_candidate','own_initial','foreign_overlap'])
def test_freshness_no_substitute_or_second_cohort(fault):
    s=seeds();pair=identity.pair(s['blocks']['validation_c1_b1'][0]);history=[];registry=[];ledger=[];own=False
    if fault=='duplicate':s['blocks']['validation_c1_b2'][0]['env_seed']=pair[1]
    if fault=='task_order':s['backend_task_order'].reverse()
    if fault=='policy_missing':s['blocks']['validation_c1_b1'][0]['policy_seed']=None
    if fault=='all_used':history=[{'pair':identity.pair(s['blocks'][f'validation_c{i}_b1'][0])} for i in range(1,5)]
    if fault in {'second_candidate','own_initial','foreign_overlap'}:
        ledger=[{'pair':pair,'attempt_id':'prior','iteration':c.COHORT if fault!='second_candidate' else 'OTHER',
            'profile':'N23','split':'validation','event':'dispatched'}]
        registry=[{'pair':pair,'attempt_id':'prior','cohort_id':ledger[0]['iteration']}]
    if fault=='foreign_overlap':
        registry.append({'pair':pair,'attempt_id':'foreign','cohort_id':'OTHER'});own=True
        assert identity.first_unused(s,history,registry,ledger,allow_own=own)=='c2'
    else:
        with pytest.raises(ValueError):identity.first_unused(s,history,registry,ledger,allow_own=own)


def test_metadata_retains_identity_only(tmp_path,monkeypatch):
    seed=write(tmp_path/'seeds.json',seeds());data=tmp_path/'data'
    h=write(data/'historical-exposure-inventory.jsonl',[{'task_id':0,'episode_seed':9,'success':'PROTECTED'}],True)
    monkeypatch.setattr(identity,'HISTORY_SHA',h['sha256'])
    write(data/'exposure-registry.jsonl',[],True)
    write(data/'attempt-ledger.jsonl',[{'event':'dispatched','attempt_id':'a','identity':{
        'task_id':0,'env_seed':9,'profile':'C0','split':'validation','iteration':'OLD'},'success':'PROTECTED'},
        {'event':'valid','attempt_id':'a','success':'PROTECTED'}],True)
    value=identity.metadata(tmp_path,{'seed_plan_path':seed['path'],'seed_plan_sha256':seed['sha256']})
    assert 'PROTECTED' not in json.dumps(value) and value[-1]['protected_outcomes_read'] is False


@pytest.mark.parametrize('fault',['none','missing_auth','run_twice','wrong_gpu','budget','dev_iteration','formal','hold'])
def test_validation_separate_state_and_generic_budget_scope(fault):
    s=state();row=identity.rows_for(seeds(),'c2')[0]
    if fault=='missing_auth':s.pop('n23_validation_authorization')
    if fault=='run_twice':s['n23_validation_authorization']['run_once']=False
    if fault=='wrong_gpu':s['gpu_pool']=[3]
    if fault=='budget':s['budget']['max_episode_attempts']=479
    if fault=='dev_iteration':row['iteration']='GENERIC_VALIDATION'
    if fault=='formal':row.update(iteration='FORMAL',split='formal',budget_bucket='formal')
    if fault=='hold':s['external_resource_hold']={'do_not_auto_resume':True}
    reservation=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':32.,'formal':12.},
        'rationale':'synthetic','time_unix':1.}]
    if fault=='none':assert r.check_budget(s,[],row,[],reservation,physical_gpu=7)==1800
    else:
        with pytest.raises((ValueError,r.GateError)):r.check_budget(s,[],row,[],reservation,physical_gpu=7)


@pytest.mark.parametrize('fault',['none','hours','formal_hours','validation_slots','recovery_slots','attempts','busy','pending'])
def test_full_remaining_local_ceiling_and_formal_reserves(fault):
    s=state();snapshot=r.budget_snapshot([]);api=dict(vars(r));events=[]
    snapshot['gpu_hours_consumed']=56.
    if fault=='hours':snapshot['gpu_hours_consumed']+=.001
    if fault=='formal_hours':snapshot['gpu_hours_consumed']=70.;snapshot['gpu_hours_by_bucket']['formal']=1.
    if fault=='validation_slots':snapshot['by_bucket']['validation']=121
    if fault=='recovery_slots':snapshot['by_bucket']['recovery']=19
    if fault=='attempts':snapshot['dispatched']=377
    if fault=='busy':snapshot['running']=1
    if fault=='pending':events=[{'event':'reserved','attempt_id':'p'}]
    api['budget_snapshot']=lambda *_:snapshot
    if fault=='none':c.full_capacity(s,events,[],api)
    else:
        with pytest.raises((ValueError,r.GateError)):c.full_capacity(s,events,[],api)


def test_source_bridge_reverses_only_fixed_worker_and_runner_insertions():
    # Approved frozen Dev plan metadata only; no outcome or ledger read.
    parent=json.loads(c.DEV_PLAN.read_text())
    changed=bridge.verify_delta(r.ROOT,parent)
    assert set(changed)<=bridge.ADDITIONS|bridge.MODIFIED
    assert parent['source_commit']==bridge.DEV_COMMIT and len(parent['code_files'])==214


@pytest.mark.parametrize('path',['core/qd_actuator_clipped_quality.py','scripts/audit_decision_evidence.py',
    'scripts/qd_ed_n23_worker.py','scripts/qd_ed_final_runner.py','configs/qd_ed_final/candidate_n23.json'])
def test_bridge_rejects_other_science_or_old_routing_bytes(path,monkeypatch):
    parent=json.loads(c.DEV_PLAN.read_text());before=Path.read_bytes
    target=(r.ROOT/path).resolve()
    def read_changed(self):
        result=before(self)
        return result+b'\n# changed frozen bytes\n' if self.resolve()==target else result
    monkeypatch.setattr(Path,'read_bytes',read_changed)
    with pytest.raises(ValueError,match='changed'):bridge.verify_delta(r.ROOT,parent)


def test_scope_and_recovery_row_never_change_seed_profile_or_timeout(tmp_path):
    row=identity.rows_for(seeds(),'c2')[0];plan={'episodes':[row],'source_commit':'v'}
    with pytest.raises(ValueError):c.require_scope(plan,tmp_path,vars(r),row)
    with c.supervised_scope(plan,tmp_path,row['episode_key']):
        c.require_scope(plan,tmp_path,vars(r),row)
        assert c.effective_row(plan,row,[],tmp_path,vars(r))==row
    retry={**row,'budget_bucket':'recovery','retry_of':'first',recovery.KEY:{'synthetic':1}}
    assert c.primary_row(plan,retry)==row
    for key,value in [('env_seed',999),('profile','Q0'),('timeout_seconds',1799),('init_row_sha256','bad')]:
        with pytest.raises(ValueError):c.primary_row(plan,{**retry,key:value})


@pytest.mark.parametrize('fault',['none','valid_failure','recovery_of_recovery','third','interrupted','duplicate'])
def test_recovery_allowance_is_validation_local_and_no_recovery_retry(fault):
    row=identity.rows_for(seeds(),'c2')[0];events=events_for(row,valid=False)
    if fault=='valid_failure':events[-1]['outcome_valid']=True
    if fault=='recovery_of_recovery':
        for v in events:v['retry_of']='previous'
    if fault=='interrupted':events[-1]['event']='aborted'
    if fault=='duplicate':events+=events_for(row,aid='other',valid=False)
    if fault=='third':
        for i in range(2):events+=events_for({**row,'episode_key':str(i)},aid=str(i),retry='old',bucket='recovery')
    # Historical Dev retries must not consume these new validation-local slots.
    events=events_for({**row,'iteration':dev.COHORT},aid='devretry',retry='old',bucket='recovery')+events
    if fault=='none':assert recovery.check_cell_history(events,row,'fixture',vars(r))['outcome_valid'] is False
    else:
        with pytest.raises((ValueError,r.GateError)):recovery.check_cell_history(events,row,'fixture',vars(r))


def test_shared_timeout_diagnostic_still_enforces_real_runner_format(tmp_path,monkeypatch):
    from scripts import qd_ed_n23_v2_recovery as original
    x=failing_case(tmp_path,monkeypatch)
    # failing_case return shape is the existing schema-faithful runner fixture.
    assert original.DERIVATIVE_FAILURES=={
        'Codex token usage incomplete','Codex Stage call failure invalidates the frozen transport condition',
        'Codex Stage event lacks one measured call with complete usage'}
    assert x is not None
