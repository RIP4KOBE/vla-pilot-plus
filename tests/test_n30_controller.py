"""N30 finite protocol control tests with synthetic records, not task evidence."""
import copy,json
from pathlib import Path
import pytest
from scripts import qd_ed_final_runner as r,qd_ed_n30_contract as c,qd_ed_n30_report as report
from scripts import qd_ed_n23_worker as w


def write(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data));return {'path':str(p),'sha256':w.sha(p)}


def rows():
    return [dict(task_id=t,profile=a,episode_key=f't{t}_{a}',split='dev',seed_block='dev',iteration=c.COHORT,
        env_seed=11+t,policy_seed=22+t,init_index=0,timeout_seconds=1800,budget_bucket='baseline' if a=='C0' else 'development') for t in range(4) for a in c.ARMS]


def journal(successes=(),invalid=None,count=12):
    events=[]
    for i,row in enumerate(rows()[:count]):
        common={'attempt_id':f'a{i}','identity':dict(row),'episode_key':row['episode_key'],'budget_bucket':row['budget_bucket'],
            'source_commit':'synthetic','plan_sha256':'p','output_dir':f'/synthetic/{i}'}
        events.extend([{**common,'event':'reserved'},{**common,'event':'dispatched'}, {**common,'event':'valid',
            'outcome_valid':i!=invalid,'success':i in successes,'gpu_process_wall_seconds':10.,'required_cost_telemetry_complete':i!=invalid,
            'provider_logical_call_attempts':3,'provider_usage_complete_calls':2 if i==invalid else 3,'provider_token_usage_complete':i!=invalid}])
    return events


def accept(row,events):
    final=next(e for e in events if e['event']=='valid' and e['episode_key']==row['episode_key'])
    if final.get('outcome_valid') is not True:raise ValueError('native/transport invalid')
    return {**{k:row[k] for k in ('episode_key','task_id','profile')},'attempt_id':final['attempt_id'],'success':final['success']},{'guided_decisions':1,'parent_rounds_verified':10,'active_insertions_verified':1},{}


@pytest.mark.parametrize('count,decision',[(3,'INVALID_OR_INTERRUPTED'),(5,'INVALID_OR_INTERRUPTED'),(6,'REJECT_NUMERIC_DEV_FUTILITY')])
def test_futility_complete_triples(count,decision):
    result=report.analyze({'episodes':rows(),'source_commit':'synthetic'},journal(count=count),accept)
    assert result['decision']==decision and result['unrun_candidate_tasks']==4-count//3


def test_no_dispatch_past_first_futile_triple():
    with pytest.raises(ValueError,match='continued after numeric futility'):
        report.analyze({'episodes':rows(),'source_commit':'s'},journal(count=7),accept)


@pytest.mark.parametrize('extra,promoted',[((),True),((0,3,6,9),False)])
def test_full_three_of_four_and_controls(extra,promoted):
    result=report.analyze({'episodes':rows(),'source_commit':'s'},journal((2,5,8)+extra),accept)
    assert result['dev_gate_promoted'] is promoted and result['audited_cells']==12
    assert result['counts']['N30']['success']==3 and not result['validation_authorized']
    assert result['matched_comparisons']['Q0']['denominator']==4


def test_invalid_cost_missing_and_chronological_no_retry():
    plan={'episodes':rows(),'source_commit':'synthetic'};events=journal(invalid=2,count=3)
    result=report.analyze(plan,events,accept)
    assert result['audited_cells']==2 and result['dispatched']==3 and result['decision']=='INVALID_OR_INTERRUPTED'
    assert result['unknown_token_calls']==1 and result['all_attempt_costs']['N30']['gpu_process_wall_seconds']['observed_total']==10.
    events[-1].pop('provider_usage_complete_calls');events[-1].pop('gpu_process_wall_seconds')
    result=report.analyze(plan,events,accept)
    assert result['unknown_token_calls'] is None and result['all_attempt_costs']['N30']['gpu_process_wall_seconds']['missing_attempts']==['a2']
    for bad in (events[3:6]+events[:3]+events[6:],events+[{**e,'attempt_id':'repeat','retry_of':'a3'} for e in events[-3:]]):
        with pytest.raises(ValueError):report.analyze(plan,bad,accept)
    aborted=[{**events[0],'event':'reserved'},{**events[0],'event':'aborted','outcome_valid':False}]
    result=report.analyze(plan,aborted,lambda *a:(_ for _ in ()).throw(ValueError('not dispatched')))
    assert result['dispatched']==result['audited_cells']==0
    assert result['all_attempt_costs']['C0']['gpu_process_wall_seconds']['missing_attempts']==['a0']


def test_dedicated_route_control_route_and_mixed_marker():
    from scripts import qd_ed_n28_contract as old
    plan={'n30_cohort':{},'candidate_profiles':{'N30':{}}}
    assert r.is_n30_plan(plan) and not r.is_n28_plan(plan) and not r.is_n27_plan(plan) and not r.is_n26_plan(plan)
    assert r.metered_support(plan) is c and r.metered_support({'n28_cohort':{}}) is old
    for name in ('is_n23_plan','is_n24_plan','is_n25_plan','is_n26_plan','is_n27_plan','is_n28_plan'):
        assert not getattr(r,name)({**plan,'n'+name.split('_')[1][1:]+'_cohort':{}})
    c.check_retry([{'identity':{'iteration':'unrelated'},'episode_key':rows()[0]['episode_key']}],rows()[0],vars(r))
    for e,row in [(journal(count=1),rows()[0]),([],{**rows()[0],'retry_of':'x'}),([],{**rows()[0],'n27_recovery_eligibility':{}})]:
        with pytest.raises(ValueError):c.check_retry(e,row,vars(r))


@pytest.mark.parametrize('spent,global_hours,okay',[(6.0*3600-1840,50.,True),(6.0*3600-1840+.001,50.,False),(0.,100.-44.-1840/3600,True),(0.,100.-44.-1840/3600+.001,False)])
def test_each_episode_reserves_full_local_global_and_protected(monkeypatch,spent,global_hours,okay):
    monkeypatch.setattr(c,'full_capacity',lambda *a:None);monkeypatch.setattr(c,'local_seconds',lambda *a:spent)
    snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=global_hours
    env={**vars(r),'budget_snapshot':lambda *a:snap}
    if okay:c.protected_budget({},[],[],rows()[0],1800,env,plan={'episodes':rows()})
    else:
        with pytest.raises(c.ResourceBudgetIncomplete):c.protected_budget({},[],[],rows()[0],1800,env,plan={'episodes':rows()})


def test_supervisor_budget_closes_without_dispatch(tmp_path,monkeypatch):
    from scripts import qd_ed_n30_supervise as sup
    saved=[];term=[]
    monkeypatch.setattr(sup,'device_check',lambda:None)
    monkeypatch.setattr(sup,'one_attempt',lambda *a:(_ for _ in ()).throw(c.ResourceBudgetIncomplete('cannot reserve1840')))
    monkeypatch.setattr(sup.r,'durable_json',lambda p,data:saved.append(copy.deepcopy(data)))
    monkeypatch.setattr(c,'ref',lambda p:{'path':str(p),'sha256':'s'})
    monkeypatch.setattr(report,'write_terminal',lambda *a:term.append(True))
    sup.execute(tmp_path/'plan',{'episodes':rows(),'source_commit':'synthetic'},None,None,tmp_path/'status')
    assert saved[-1]['status']=='resource_budget_incomplete' and saved[-1]['completed_keys']==[] and term==[True]


def test_report_status_failure_preserves_valid_journal_prefix(tmp_path,monkeypatch):
    events=journal(count=3);plan={'episodes':rows(),'source_commit':'s'}
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge')
    for f in ('plan','bridge','scripts/qd_ed_n30_report.py'):write(tmp_path/f,{})
    write(tmp_path/'status',{'status':'failed','completed_keys':rows()[:2],'dev_gate_promoted':False})
    monkeypatch.setattr(report,'analyze',lambda p,e,a:{'accepted_cells':[{'episode_key':row['episode_key']} for row in rows()[:3]],'dev_gate_promoted':False,'audited_cells':3,'decision':'INVALID_OR_INTERRUPTED','failure':None})
    result=report.write_terminal(tmp_path/'plan',plan,tmp_path/'status',tmp_path,{'read_events':lambda p:events})
    assert result['decision']=='INVALID_OR_INTERRUPTED' and not result['controller_evidence']['consistent']
    assert len(result['controller_evidence']['journal_accepted_keys'])==3


@pytest.mark.parametrize('remaining_seconds',[1840.01,1839.99,1000.,39.,0.])
def test_real_check_budget_then_protected_never_truncates_n30(monkeypatch,remaining_seconds):
    snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=100.-44.-remaining_seconds/3600
    state={'gpu_pool':[7],'max_concurrent_gpu_workers':1,'budget':{'dispatched':0,'gpu_hours_consumed':snap['gpu_hours_consumed'],
        'max_episode_attempts':578,'max_gpu_hours':100.,'reserved':c.BASE_CAPS['buckets'],'gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours'],'amendment':{'prospective':'synthetic'}}}
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(r,'budget_snapshot',lambda *a:snap)
    monkeypatch.setattr(r,'authorized_gpu',lambda _:7);monkeypatch.setattr(c,'full_capacity',lambda *a:None)
    monkeypatch.setattr(c,'local_seconds',lambda *a:0.)
    reservation=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours'],'rationale':'synthetic','time_unix':1}]
    if remaining_seconds<1840:
        with pytest.raises(c.ResourceBudgetIncomplete):r.check_budget(state,[],rows()[0],[],reservation,physical_gpu=7)
    else:
        timeout=r.check_budget(state,[],rows()[0],[],reservation,physical_gpu=7);assert timeout==1800
        c.protected_budget(state,[],[],rows()[0],timeout,vars(r),plan={'episodes':rows()})


@pytest.mark.parametrize('count,allowed',[(3,True),(5,True),(6,False)])
def test_admission_cannot_bypass_completed_triple_futility(monkeypatch,count,allowed):
    plan={'episodes':rows()};events=journal(count=count)
    monkeypatch.setattr(c,'accepted_cell',lambda p,row,ev,root,env:next(e for e in ev if e['event']=='valid' and e['episode_key']==row['episode_key']))
    if allowed:c.admission(plan,{},rows()[count],events,[],Path('/synthetic'),vars(r))
    else:
        with pytest.raises(ValueError,match='futility'):c.admission(plan,{},rows()[count],events,[],Path('/synthetic'),vars(r))
