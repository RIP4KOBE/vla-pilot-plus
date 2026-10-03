import copy
from pathlib import Path
import pytest
from scripts import qd_ed_final_runner as r,qd_ed_n30_r1_contract as c,qd_ed_n30_r1_bridge as b,qd_ed_n30_r1_report as report
from n30_r1_synthetic import history,new_events,accept,write

def test_fixed_rows_and_named_retry_real_route(monkeypatch):
    h=history();rr=c.expected_rows(h);monkeypatch.setattr(c,'history',lambda:h)
    assert len(rr)==10 and [x['budget_bucket'] for x in rr].count('recovery')==1
    assert [(x['task_id'],x['profile']) for x in rr]==[(0,'N30')]+[(t,a) for t in range(1,4) for a in c.ARMS]
    r.check_retry(h['events'],rr[0])
    unrelated={**h['events'][0],'identity':{**h['events'][0]['identity'],**{k:rr[1][k] for k in ('task_id','env_seed','policy_seed')},'iteration':'unrelated'}}
    r.check_retry(h['events']+[unrelated],rr[1])
    with pytest.raises(ValueError):r.check_retry(h['events']+[{**unrelated,'retry_of':b.FAILED}],rr[0])
    with pytest.raises(ValueError):r.check_retry(new_events(h,1),rr[0])
    r.check_retry(new_events(h,1),rr[1])
    with pytest.raises(ValueError):r.check_retry(new_events(h,2),rr[1])
    with pytest.raises(ValueError):r.check_retry(h['events'],{**rr[0],'retry_of':'wrong'})
    with pytest.raises(ValueError):r.check_retry(h['events'],h['plan']['episodes'][0])

@pytest.mark.parametrize('count,decision',[(0,'INVALID_OR_INTERRUPTED'),(1,'INVALID_OR_INTERRUPTED'),(3,'INVALID_OR_INTERRUPTED'),(4,'REJECT_NUMERIC_DEV_FUTILITY')])
def test_combined_triples_preserve_old_invalid(count,decision):
    h=history();out=report.analyze({'episodes':c.expected_rows(h),'source_commit':'NEW'},new_events(h,count,wins=()),h,accept)
    assert out['decision']==decision and out['audited_cells']==count+2 and out['all_dispatched']==count+3
    assert out['original_disposition']=='INVALID_OR_INTERRUPTED' and out['counts']['N30']['audited']==(count+2)//3
    total=sum(v['gpu_process_wall_seconds']['observed_total'] for v in out['all_attempt_costs'].values())
    assert total==b.OLD_SECONDS+count*10


def test_complete_gate_invalid_missing_cost_and_order():
    h=history();plan={'episodes':c.expected_rows(h),'source_commit':'NEW'}
    out=report.analyze(plan,new_events(h),h,accept)
    assert out['dev_gate_promoted'] and out['counts']['N30']=={'audited':4,'success':3} and out['all_dispatched']==13
    assert out['accepted_cells'][0]['source_commit']==b.OLD_SOURCE
    events=new_events(h,1,invalid=0);events[-1].pop('gpu_process_wall_seconds');events[-1].pop('provider_usage_complete_calls')
    out=report.analyze(plan,events,h,accept)
    assert out['decision']=='INVALID_OR_INTERRUPTED' and out['audited_cells']==2 and out['unknown_token_calls'] is None
    assert out['all_attempt_costs']['N30']['gpu_process_wall_seconds']['missing_attempts']==['new0']
    for bad in (new_events(h,5,wins=()),new_events(h,2,invalid=0),h['events']+new_events(h,2)[12:]+new_events(h,2)[9:12]):
        with pytest.raises(ValueError):report.analyze(plan,bad,h,accept)


def test_reserved_abort_no_fake_worker_or_zero_cost():
    h=history();events=new_events(h,1);events=events[:-2]+[{**events[-3],'event':'aborted','outcome_valid':False}]
    out=report.analyze({'episodes':c.expected_rows(h),'source_commit':'NEW'},events,h,lambda *a:(_ for _ in ()).throw(ValueError('never dispatched')))
    assert out['all_dispatched']==3 and out['audited_cells']==2 and out['all_attempt_costs']['N30']['gpu_process_wall_seconds']['missing_attempts']==['new0']

@pytest.mark.parametrize('remaining',[1840.01,1839.99,1000.,39.,0.])
def test_real_global_budget_route_before_truncation(monkeypatch,remaining):
    h=history();row=c.expected_rows(h)[0];snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=100.-44.-remaining/3600
    state={'gpu_pool':[7],'max_concurrent_gpu_workers':1,'budget':{'dispatched':0,'gpu_hours_consumed':snap['gpu_hours_consumed'],
        'max_episode_attempts':578,'max_gpu_hours':100.,'reserved':c.BASE_CAPS['buckets'],'gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours'],'amendment':{'synthetic':True}}}
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(r,'budget_snapshot',lambda *a:snap)
    monkeypatch.setattr(r,'authorized_gpu',lambda _:7);monkeypatch.setattr(c,'full_capacity',lambda *a:None);monkeypatch.setattr(c,'local_seconds',lambda *a:b.OLD_SECONDS)
    reservations=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours'],'rationale':'synthetic','time_unix':1}]
    if remaining<1840:
        with pytest.raises(c.ResourceBudgetIncomplete):r.check_budget(state,[],row,[],reservations,physical_gpu=7)
    else:
        timeout=r.check_budget(state,[],row,[],reservations,physical_gpu=7);assert timeout==1800
        c.protected_budget(state,[],[],row,timeout,vars(r),plan={'episodes':[row]})


def test_local_includes_history_health_unknown_and_full_reserve(monkeypatch):
    h=history();assert c.local_seconds(h['events'],[],vars(r))==b.OLD_SECONDS
    health=[{'kind':'n30_r1_resource_preparation_v1','event':'completed','gpu_process_wall_seconds':20}]
    assert c.local_seconds(h['events'],health,vars(r))==b.OLD_SECONDS+20
    with pytest.raises(ValueError):c.local_seconds(h['events'],[{**health[0],'gpu_process_wall_seconds':None}],vars(r))
    monkeypatch.setattr(c,'full_capacity',lambda *a:None);monkeypatch.setattr(c,'whole_attempt_hours',lambda *a:None)
    row=c.expected_rows(h)[0]
    monkeypatch.setattr(c,'local_seconds',lambda *a:21600-1840)
    c.protected_budget({},[],[],row,1800,vars(r),plan={'episodes':[row]})
    monkeypatch.setattr(c,'local_seconds',lambda *a:21600-1840+.001)
    with pytest.raises(c.ResourceBudgetIncomplete):c.protected_budget({},[],[],row,1800,vars(r),plan={'episodes':[row]})


def test_route_and_new_prefix_futility(monkeypatch):
    from scripts import qd_ed_n30_contract as old
    h=history();rr=c.expected_rows(h);p={'episodes':rr,'source_commit':'NEW','n30_r1_cohort':{},'candidate_profiles':{'N30':{}}}
    assert r.metered_support(p) is c and r.metered_support({'n30_cohort':{}}) is old
    assert r.typed_metered_plan(p) and not r.is_n29_plan(p)
    monkeypatch.setattr(c,'history',lambda:h)
    monkeypatch.setattr(c,'accepted_cell',lambda p,row,ev,*a:next(e for e in ev if e['event']=='valid' and e['episode_key']==row['episode_key']))
    c.admission(p,{},rr[1],new_events(h,1,wins=()),[],Path('/synthetic'),vars(r))
    with pytest.raises(ValueError,match='futility'):c.admission(p,{},rr[4],new_events(h,4,wins=()),[],Path('/synthetic'),vars(r))


def test_supervisor_resource_and_post_journal_exception(tmp_path,monkeypatch):
    from scripts import qd_ed_n30_r1_supervise as sup
    h=history();saved=[];term=[]
    monkeypatch.setattr(c,'history',lambda:h);monkeypatch.setattr(sup,'device_check',lambda:None)
    monkeypatch.setattr(sup,'one_attempt',lambda *a:(_ for _ in ()).throw(c.ResourceBudgetIncomplete('full1840')))
    monkeypatch.setattr(sup.r,'durable_json',lambda p,v:saved.append(copy.deepcopy(v)));monkeypatch.setattr(c,'ref',lambda p:{'path':str(p),'sha256':'s'})
    monkeypatch.setattr(report,'write_terminal',lambda *a:term.append(True))
    sup.execute(tmp_path/'plan',{'episodes':c.expected_rows(h),'source_commit':'NEW'},None,None,tmp_path/'status')
    assert saved[-1]['status']=='resource_budget_incomplete' and len(saved[-1]['completed_keys'])==2 and len(saved[-1]['attempts'])==3 and term==[True]


def test_status_mismatch_retains_longer_ledger_prefix(tmp_path,monkeypatch):
    h=history();events=new_events(h,1);plan={'episodes':c.expected_rows(h),'source_commit':'NEW'}
    monkeypatch.setattr(c,'history',lambda:h);monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge')
    for f in ('plan','bridge','scripts/qd_ed_n30_r1_report.py'):write(tmp_path/f,{})
    write(tmp_path/'status',{'status':'failed','completed_keys':[x['cell']['episode_key'] for x in h['imports']],'dev_gate_promoted':False})
    original=report.analyze;monkeypatch.setattr(report,'analyze',lambda p,e,hh,a:original(p,e,hh,accept))
    out=report.write_terminal(tmp_path/'plan',plan,tmp_path/'status',tmp_path,{'read_events':lambda p:events})
    assert out['decision']=='INVALID_OR_INTERRUPTED' and not out['controller_evidence']['consistent'] and out['audited_cells']==3 and out['all_dispatched']==4

@pytest.mark.parametrize('fault',['none','slots','unsettled','state','protected','old_cost'])
def test_full_remaining_capacity_without_new_budget(monkeypatch,fault):
    h=history();monkeypatch.setattr(c,'history',lambda:h);monkeypatch.setattr(c,'require_state',lambda *a:None)
    snap=r.budget_snapshot(h['events']);snap['dispatched']=398;snap['gpu_hours_consumed']=53.38686451724561
    snap['by_bucket']={'baseline':73,'development':252,'validation':60,'formal':0,'recovery':13}
    state={'budget':{'dispatched':398,'gpu_hours_consumed':snap['gpu_hours_consumed']}}
    monkeypatch.setattr(r,'budget_snapshot',lambda *a:snap)
    events=copy.deepcopy(h['events'])
    if fault=='slots':snap['by_bucket']['baseline']=74
    elif fault=='unsettled':snap['running']=1
    elif fault=='state':state['budget']['dispatched']=397
    elif fault=='protected':snap['gpu_hours_consumed']=80.;state['budget']['gpu_hours_consumed']=80.
    elif fault=='old_cost':events[-1]['gpu_process_wall_seconds']=None
    if fault=='none':c.full_capacity(state,events,[],vars(r))
    else:
        with pytest.raises((ValueError,c.ResourceBudgetIncomplete)):c.full_capacity(state,events,[],vars(r))


def test_immutable_freeze_missing_release_and_adoption(tmp_path,monkeypatch):
    from scripts import qd_ed_n30_r1_prepare as prep,qd_ed_n30_r1_supervise as sup
    monkeypatch.setattr(c,'PLAN',tmp_path/'plan');write(c.PLAN,{})
    with pytest.raises(ValueError,match='immutable'):prep.freeze(c.PLAN,root=tmp_path)
    monkeypatch.setattr(c,'AUTHORITY',tmp_path/'absent')
    with pytest.raises(OSError):c.authority({}, {}, tmp_path)
    monkeypatch.setattr(c,'RUN_DIR',tmp_path)
    with pytest.raises(OSError):sup.release_check(tmp_path/'execution-release-v1.json',c.PLAN,{'source_commit':'new'})


def test_prepare_preserves_all_scientific_fields_and_no_live_adoption(tmp_path,monkeypatch):
    from scripts import qd_ed_n30_r1_prepare as prep
    h=history();h['review']={'plan':{'path':'/original/plan','sha256':'old'}}
    h['plan'].update(n30_cohort={'old':True},scientific_config_files=['profile'],phase_authorization={'dev':True,'validation':False,'formal':False},
        runtime_manifest_path='/frozen/runtime',runtime_manifest_sha256='r',seed_plan_sha256='s',profiles_sha256='p')
    monkeypatch.setattr(c,'history',lambda:h);monkeypatch.setattr(c,'ARTIFACT_DIR',tmp_path/'artifacts');monkeypatch.setattr(c,'ref',lambda p:{'path':str(p),'sha256':'profile'})
    out=prep.build_plan(source={'commit':'NEW','files':[]},root=tmp_path)
    assert not out['frozen'] and out['n30_r1_cohort']['executable'] is False and out['n30_r1_cohort']['authority'] is None
    assert 'n30_cohort' not in out and len(out['episodes'])==10
    for k in ('scientific_config_files','phase_authorization','runtime_manifest_path','runtime_manifest_sha256','seed_plan_sha256','profiles_sha256'):assert out[k]==h['plan'][k]
