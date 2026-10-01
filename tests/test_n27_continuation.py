import copy
import hashlib
import json
from pathlib import Path
import pytest
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n27_contract as old
from scripts import qd_ed_n27_cont_contract as c,qd_ed_n27_cont_history as h,qd_ed_n27_cont_prepare as prep
from scripts import qd_ed_n27_cont_report as report,qd_ed_n27_cont_supervise as sup,qd_ed_n27_cont_bridge as bridge
from n27_cont_fixtures import seal,write,group,snapshot

@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'RUN_DIR',tmp_path/'controller');monkeypatch.setattr(c,'SEAL',tmp_path/'seal.json')
    monkeypatch.setattr(c,'AUTHORITY',tmp_path/'authority.json');write(c.AUTHORITY,{})
    monkeypatch.setattr(c,'PLAN',tmp_path/'plan.json');monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json')
    s=seal(tmp_path);write(c.SEAL,s);write(c.BRIDGE,{})
    monkeypatch.setattr(c,'history',lambda:s)
    return s

def test_rows_and_unchanged_plan(fixture):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});rr=p['episodes']
    assert len(rr)==13 and [(x['task_id'],x['profile']) for x in rr]==[(0,'N27')]+[(t,a) for t in (1,2,3) for a in c.ARMS]
    assert sum(x['budget_bucket']=='recovery' for x in rr)==1
    assert {b:sum(x['budget_bucket']==b for x in rr) for b in ('baseline','development')}=={'baseline':3,'development':9}
    assert rr[0]['retry_of']==h.FAILED and all(not x.get('retry_of') for x in rr[1:]) and p['frozen'] is False
    assert p['n27_cohort']['worker_audit']==old.WORKER_CONTRACT and not p['n27_hydra_continuation']['executable']
    for i,row in enumerate(rr,3):
        oldrow=fixture['original_plan_content']['episodes'][i]
        assert all(row[k]==oldrow[k] for k in oldrow if k not in {'iteration','episode_key','budget_bucket'})

@pytest.mark.parametrize('field',['source','rows','named','cost','valid','prefix','resource','unknown'])
def test_history_negative(fixture,field):
    x=copy.deepcopy(fixture)
    if field=='source':x['original_source']['commit']='x'
    elif field=='rows':x['original_plan_content']['episodes'].reverse()
    elif field=='named':x['old_events'][-1]['attempt_id']='wrong'
    elif field=='cost':x['old_events'][-1].pop('gpu_process_wall_seconds')
    elif field=='valid':x['old_events'][-1]['outcome_valid']=True
    elif field=='prefix':x['accepted_prefix'][0]['cell']['source_commit']='new';x['accepted_prefix'][0]['cell']['attempt_id']='new'
    elif field=='resource':x['old_resource_events'][-1]['event']='aborted'
    else:x['historical_unknowns']=[]
    with pytest.raises((ValueError,KeyError)):h.verify(x)

def test_history_positive_and_unrelated_append(fixture):
    assert h.verify(fixture)==fixture
    h.current_subset(fixture,fixture['old_events']+[{'identity':{'iteration':'UNRELATED'}}],fixture['old_resource_events']+[{'kind':'unrelated'}])
    with pytest.raises(ValueError):h.current_subset(fixture,fixture['old_events']+[fixture['old_events'][0]],fixture['old_resource_events'])

@pytest.mark.parametrize('case',['named','unrelated','duplicate','wrong_named','valid_repeat','mixed'])
def test_retry_exact_scope(fixture,case):
    rr=c.rows(fixture);row=rr[0] if case in {'named','wrong_named','mixed'} else rr[1];events=copy.deepcopy(fixture['old_events'])
    if case=='unrelated':
        other=copy.deepcopy(row);other['iteration']='N26_PREVIOUS';events+=group(other,'unrelated')
    elif case in {'duplicate','valid_repeat'}:events+=group(row,'already')
    elif case=='wrong_named':row={**row,'retry_of':'wrong'}
    elif case=='mixed':row={**row,'n27_recovery_eligibility':{}}
    if case in {'named','unrelated'}:c.check_retry(events,row,vars(r))
    else:
        with pytest.raises(ValueError):c.check_retry(events,row,vars(r))

@pytest.mark.parametrize('fault',[None,'baseline','development','recovery','hours','protected','local','unsettled','state','missingcost'])
def test_capacity(fixture,monkeypatch,fault):
    snap=snapshot();events=copy.deepcopy(fixture['old_events']);resources=fixture['old_resource_events']
    if fault in {'baseline','development','recovery'}:snap['by_bucket'][fault]=c.CAPS['buckets'][fault]
    if fault=='hours':snap['gpu_hours_consumed']=99.
    if fault=='protected':snap['gpu_hours_by_bucket']['validation']=0.;snap['gpu_hours_consumed']=70.
    if fault=='local':fixture['old_gpu_seconds']=9.25*3600-100.;monkeypatch.setattr(h,'current_subset',lambda *a:None)
    if fault=='unsettled':snap['running']=1
    if fault=='missingcost':
        g=group(c.rows(fixture)[0],'new');g[-1].pop('gpu_process_wall_seconds');events+=g
    state={'budget':{'dispatched':snap['dispatched'],'gpu_hours_consumed':snap['gpu_hours_consumed']}}
    if fault=='state':state['budget']['dispatched']-=1
    env={**vars(r),'budget_snapshot':lambda *a:snap}
    if fault is None:assert c.budget_check(state,events,resources,env,dispatch=True)['remaining']=={'baseline':3,'development':9,'recovery':1}
    else:
        with pytest.raises(ValueError):c.budget_check(state,events,resources,env,dispatch=True)

def test_capacity_exact_boundary(fixture,monkeypatch):
    snap=snapshot();seconds=13*1840;reserved=34.;snap['gpu_hours_consumed']=100-reserved-seconds/3600
    state={'budget':{'dispatched':342,'gpu_hours_consumed':snap['gpu_hours_consumed']}}
    env={**vars(r),'budget_snapshot':lambda *a:snap};c.budget_check(state,fixture['old_events'],fixture['old_resource_events'],env,dispatch=True)
    snap['gpu_hours_consumed']+=.001;state['budget']['gpu_hours_consumed']=snap['gpu_hours_consumed']
    with pytest.raises(ValueError):c.budget_check(state,fixture['old_events'],fixture['old_resource_events'],env,dispatch=True)

def test_router_old_and_new(fixture):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});assert r.is_n27_plan(p) and r.metered_support(p) is c
    assert r.metered_support(fixture['original_plan_content']) is old
    assert not r.is_n26_plan(p) and r.metered_plan(p)

def test_closed_scope(fixture):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});row=p['episodes'][0]
    with pytest.raises(ValueError):c.require_scope(p,c.ROOT,vars(r),row)
    with c.supervised_scope(p,c.ROOT,row['episode_key']):
        assert c.effective_row(p,row,[],c.ROOT,vars(r))==row
        with pytest.raises(ValueError):c.require_scope(p,c.ROOT,vars(r),p['episodes'][1])
        with pytest.raises(ValueError):
            with c.supervised_scope(p,c.ROOT,row['episode_key']):pass

def test_freeze_existing_blocks_before_io(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'PLAN',tmp_path/'p.json');write(c.PLAN,{})
    monkeypatch.setattr(c,'history',lambda:pytest.fail('must not read history'))
    with pytest.raises(ValueError):prep.freeze(c.PLAN,root=tmp_path)

def run_report(fixture,*,wins=2,control=0,invalid=None,stop=13,substantive=True):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});ev=[]
    for i,row in enumerate(p['episodes'][:stop]):
        success=row['task_id']<(wins if row['profile']=='N27' else control)
        ev+=group(row,'new'+str(i),source='new',valid=i!=invalid,success=success)
    def accept(row,events):
        f=next(x for x in events if x['event']=='valid' and x['episode_key']==row['episode_key'])
        w.require(f['outcome_valid'],'invalid');return {k:row[k] for k in ('episode_key','task_id','profile')}|{'attempt_id':f['attempt_id'],'success':f['success']},{'guided_decisions':int(substantive),'parent_rounds_verified':10*int(substantive)},{}
    return report.analyze(p,fixture,ev,accept),p,ev,accept

@pytest.mark.parametrize('wins,control,substantive,expected',[(0,0,True,'REJECT_SCREEN'),(1,0,True,'REJECT_SCREEN'),(2,0,True,'ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV'),(2,3,True,'REJECT_SCREEN'),(4,0,False,'REJECT_SCREEN')])
def test_all_sixteen_thresholds_and_costs(fixture,wins,control,substantive,expected):
    result,_,_,_=run_report(fixture,wins=wins,control=control,substantive=substantive)
    assert result['decision']==expected and result['audited_cells']==16 and result['dispatched']==17
    assert result['original_disposition']=='INVALID_OR_INTERRUPTED' and result['unknown_token_calls'] is None
    assert result['unmeasured_token_call_attempts']==[h.FAILED]
    assert result['all_attempt_denominators']=={'C0':4,'Q0':4,'N26':4,'N27':5}
    assert all(x['source_commit']==h.BASE for x in result['accepted_cells'][:3])

@pytest.mark.parametrize('stop,invalid',[(0,None),(1,0),(4,3),(13,12),(5,None)])
def test_incomplete_never_promotes(fixture,stop,invalid):
    result,_,_,_=run_report(fixture,stop=stop,invalid=invalid)
    assert result['decision']=='INVALID_OR_INTERRUPTED' and not result['dev_gate_promoted']
    assert len(result['attempts'])==4+stop

def test_reordered_skipped_postinvalid_rejected(fixture):
    result,p,ev,accept=run_report(fixture)
    for bad in (ev[3:6]+ev[:3]+ev[6:],ev[:1]+ev[3:6]+ev[1:3]+ev[6:]):
        with pytest.raises(ValueError):report.analyze(p,fixture,bad,accept)
    with pytest.raises(ValueError):run_report(fixture,invalid=2)

@pytest.mark.parametrize('profile',['C0','Q0','N26','N27'])
def test_worker_route_real_shape(fixture,tmp_path,monkeypatch,profile):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});p['frozen']=True
    p['n27_hydra_continuation'].update(cohort_id=c.COHORT,protocol={'path':'synthetic','sha256':c.PROTOCOL_SHA})
    row=next(x for x in p['episodes'] if x['profile']==profile);out=Path(p['artifact_root'])/'attempts'/'new'
    context={'schema':'n23-metered-worker-context-v1','attempt_id':'new','episode_key':row['episode_key'],'profile':profile,'output_dir':str(out),
        'worktree':str(tmp_path),'main_argv':[str(tmp_path/'main.py'),'unchanged=1'],'plan':{},'runtime':{'path':p['runtime_manifest_path'],'sha256':p['runtime_manifest_sha256']},
        'source':{'commit':'new','files':[],'sha256':'x'}}
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':old.GPU7_UUID}}
    monkeypatch.setattr(w,'ROOT',tmp_path);monkeypatch.setattr(w,'read_ref',lambda ref:p if ref==context['plan'] else runtime);monkeypatch.setattr(w,'verify_source',lambda *a:None)
    assert w.validate_context(context,context['main_argv'])==(tmp_path,out,runtime)
    p['n27_cohort']['worker_audit']={}
    with pytest.raises(ValueError):w.validate_context(context,context['main_argv'])

def test_native_zero_guided_gate_is_not_optional(tmp_path):
    report={'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':0}}
    # Actual immutable profile-bound counter routine must reject erased N27 markers, including zero work.
    with pytest.raises(ValueError):c.native.counts('N27',[],report,0)
    report['n27_feasible_ray_rbf_audit']={'schema':'n27-native-rbf-audit-v1','accepted':True,'guided_decisions':0,
        'all_call_summaries_verified':0,'witness_calls_verified':0,'zero_gradient_calls':0,'clipped_components':0,'limited_rows':0,'realized_nonzero_delta_components':0}
    assert c.native.counts('N27',[],report,0)[0]['guided_decisions']==0
    # Specific accepted schema is checked by the existing native function; no implementation changes here.
    assert c.native.counts('C0',[],{'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':0}},0)[0]['guided_decisions']==0
