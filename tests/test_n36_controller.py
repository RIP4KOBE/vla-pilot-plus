"""Frozen four-arm stopping, partial denominators, dual caps and retained margin."""
import copy
import datetime as dt
from decimal import Decimal
import hashlib
import json
import pytest
from scripts import qd_ed_n36_contract as c, qd_ed_n36_supervise as s, qd_ed_n36_report as reporting
from scripts import qd_ed_n36_accounting as a, qd_ed_final_runner as r


def events_for(outcomes):
    result=[]
    for row,success in zip(c.expected_rows(),outcomes):
        base={'attempt_id':row['episode_key'],'episode_key':row['episode_key'],'identity':s.c_identity(row),
              'budget_bucket':row['budget_bucket'],'replacement':None,'retry_of':None,'recovery_of':None}
        result.extend([{**base,'event':'reserved'},{**base,'event':'dispatched'},
            {**base,'event':'valid','outcome_valid':True,'required_cost_telemetry_complete':True,'success':success}])
    return result


def reconcile(outcomes):
    return s.reconcile({'episodes':c.expected_rows(),'worktree':str(c.ROOT)},events_for(outcomes),lambda *args:None)


def test_complete_quadruple_futility_preserves_ties_and_partial_denominators():
    # Five N36 failures leave a possible 5/10: strict < must not stop a tie.
    assert reconcile([False]*20)['status']=='READY_FOR_ROOT_RELEASE'
    partial=reconcile([False]*23)
    assert partial['next_row']['profile']=='N36'
    summary=reporting.summary(partial,[])
    assert summary['valid_denominators']=={'C0':6,'Q0':6,'N34':6,'N36':5}
    assert summary['matrix'][5]['N36']=='Unknown'
    assert reconcile([False]*24)['status']=='NUMERIC_FUTILITY'
    # Controls can make the gate impossible while 5/10 remains attainable.
    outcomes=[True,False,False,False]*5+[True,False,False,True]
    assert reconcile(outcomes[:-1])['status']=='READY_FOR_ROOT_RELEASE'
    assert reconcile(outcomes)['status']=='NUMERIC_FUTILITY'
    with pytest.raises(ValueError,match='after complete-quadruple'):reconcile(outcomes+[False]*4)


def test_all40_necessary_gate_is_not_promotion():
    result=reconcile([True]*40)
    report=reporting.summary(result,[])
    assert report['prospective_dev_necessary_gate_met']
    assert report['mechanism_review_required'] and not report['validation_authorized'] and not report['target_met']
    assert report['valid_denominators']=={arm:10 for arm in c.ARMS}


def test_invalid_unknown_and_replay_stop_without_fabricated_failures():
    plan={'episodes':c.expected_rows(),'worktree':str(c.ROOT)}
    for field,value in [('success',None),('outcome_valid',False),('required_cost_telemetry_complete',False)]:
        events=events_for([True,False]);events[-1][field]=value
        result=s.reconcile(plan,events,lambda *args:None)
        assert result['status']=='INVALID_STOP' and len(result['outcomes'])==1 and result['next_row'] is None
    events=events_for([False]);events.extend(events_for([False]))
    assert s.reconcile(plan,events,lambda *args:None)['status']=='INVALID_STOP'
    events=events_for([False]);events[0]['retry_of']='old'
    with pytest.raises(ValueError):s.reconcile(plan,events,lambda *args:None)


def empty():return r.budget_snapshot([])


def test_decimal_dual_caps_and_healthcheck_bound():
    snap=empty();cohort=empty()
    snap['gpu_hours_consumed']=220.9
    with pytest.raises(ValueError,match='weekly'):a.headroom(snap,cohort,retained_margin_hours=0,protected_hours=0)
    snap['gpu_hours_consumed']=223.9
    with pytest.raises(ValueError,match='absolute'):a.headroom(snap,cohort,retained_margin_hours=0,protected_hours=0)
    snap['gpu_hours_consumed']=176.6
    with pytest.raises(ValueError,match='weekly'):a.headroom(snap,cohort,retained_margin_hours=0,protected_hours=44)
    snap=empty();cohort['gpu_healthcheck_hours']=.5
    assert a.headroom(snap,cohort,retained_margin_hours=0,protected_hours=44)['reserved_gpu_seconds']==1840
    with pytest.raises(ValueError,match='healthcheck'):a.headroom(snap,cohort,retained_margin_hours=0,protected_hours=44,healthcheck=True,need=1)
    for fault in ('running','gpu_healthcheck_inflight'):
        snap=empty();snap[fault]=1
        with pytest.raises(ValueError,match='unsettled'):a.headroom(snap,empty(),retained_margin_hours=0,protected_hours=44)
    for need in (1800,1839,1841):
        with pytest.raises(ValueError,match='full reservation'):a.headroom(empty(),empty(),retained_margin_hours=0,protected_hours=44,need=need)


def test_retained_prefix_margin_never_rewrites_or_forgets_cost(tmp_path,monkeypatch):
    (tmp_path/'data').mkdir()
    attempts=[{'attempt_id':'old','budget_bucket':'development','event':event,'gpu_process_wall_seconds':3600}
              for event in ('reserved','dispatched','valid')]
    health=[{'resource_id':'oldprobe','event':event,'gpu_process_wall_seconds':360}
            for event in ('reserved','dispatched','completed')]
    anchors={}
    for name,rows in [('attempt-ledger.jsonl',attempts),('gpu-healthcheck-ledger.jsonl',health)]:
        content=('\n'.join(json.dumps(x) for x in rows)+'\n').encode();(tmp_path/'data'/name).write_bytes(content)
        anchors[name]={'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    frozen={'ledger_prefixes':anchors,'cost_reconciliation':{'retained_admission_margin_gpu_hours':.23357169027962}}
    file=tmp_path/'accounting.json';file.write_text(json.dumps(frozen));ref=c.ref(file)
    monkeypatch.setattr(c,'ACCOUNTING_SHA',ref['sha256'])
    assert a.retained_margin(tmp_path,ref)==pytest.approx(.23357169027962)
    snap=r.budget_snapshot(attempts,health)
    result=a.headroom(snap,empty(),retained_margin_hours=a.retained_margin(tmp_path,ref),protected_hours=44)
    assert result['charged_gpu_hours']==1.1 and result['retained_margin_gpu_hours']==pytest.approx(.23357169027962)
    assert (tmp_path/'data/attempt-ledger.jsonl').read_bytes().endswith(b'\n')
    with (tmp_path/'data/attempt-ledger.jsonl').open('r+b') as stream:stream.write(b'X')
    with pytest.raises(ValueError,match='prefix differs'):a.retained_margin(tmp_path,ref)


def test_full1840_deadline_and_stop(tmp_path):
    allowance={'authority_starts_at':'2026-10-09T00:00:00Z','authority_ends_at':c.DEADLINE,
        'private_budget':True,'gpu_idle':True,'physical_gpu':7,'gpu_uuid':c.GPU_UUID,
        'live_handles':[],'unsettled_reservations':0,'global_seconds_remaining':1000000,
        'private_seconds_remaining':1000000,'cohort_seconds_remaining':75600,'protected_seconds_remaining':100,
        'bucket_attempts_remaining':{'baseline':10,'development':30},'global_attempts_remaining':100,
        'cohort_attempts_remaining':40,'protected_attempts_remaining':0}
    deadline=dt.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
    stop=tmp_path/'STOP'
    assert c.pre_dispatch(c.expected_rows()[0],allowance,now=deadline-dt.timedelta(seconds=1840),stop_path=stop)==1840
    with pytest.raises(ValueError):c.pre_dispatch(c.expected_rows()[0],allowance,now=deadline-dt.timedelta(seconds=1839),stop_path=stop)
    stop.symlink_to(tmp_path/'absent')
    with pytest.raises(ValueError,match='STOP'):c.pre_dispatch(c.expected_rows()[0],allowance,now=deadline-dt.timedelta(seconds=1900),stop_path=stop)


@pytest.mark.parametrize('failure',[IndexError('missing native row'),ArithmeticError('nonfinite arithmetic')])
def test_native_auditor_exception_stops_next_admission(failure):
    def verify(*args):raise failure
    result=s.reconcile({'episodes':c.expected_rows(),'worktree':str(c.ROOT)},events_for([True]),verify)
    assert result['status']=='INVALID_STOP' and result['next_row'] is None
