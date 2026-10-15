import copy
from types import SimpleNamespace
import pytest
import torch
import summarize_cohort_cpu_v2 as m

def fixture(n=40, candidate_successes=5, recovery=False, phase='completed_all_forty_audited'):
    rows=[{'episode_key':f't{t}_{a}','task_id':t,'profile':a,'split':'dev','iteration':m.c.COHORT,
        'env_seed':100+t,'policy_seed':200+t,'init_index':0,
        'budget_bucket':'baseline' if a=='C0' else 'development'} for t in range(10) for a in m.c.ARMS]
    plan={'episodes':rows,'source_commit':m.SOURCE};events=[];accepted=[];attempts=[];outcomes=[]
    native={'N7':{'guided_decisions':0,'parent_rounds_verified':0},
        'N23':{'guided_decisions':0,'parent_rounds_verified':0,**{k:0 for k in m.sup.NATIVE_FIELDS}}}
    aux={k:0 for k in m.sup.AUX_FIELDS}
    def counts(row):
        if row['profile'] not in native:return {'guided_decisions':0,'parent_rounds_verified':0}
        result={'guided_decisions':1,'parent_rounds_verified':10}
        if row['profile']=='N23':result.update(score_batches_verified=11,candidate_scores_verified=176,clipped_prefix_candidates=0,rank_changed_batches=0)
        return result
    for i,row in enumerate(rows[:n]):
        base={'attempt_id':f'a{i}','episode_key':row['episode_key'],'identity':m.r.episode_identity(row),
            'source_commit':m.SOURCE,'plan_sha256':m.PLAN_SHA,'budget_bucket':row['budget_bucket']}
        success=row['profile']=='N23' and row['task_id']<candidate_successes
        finals=[]
        if recovery and i==0:
            bad={**base,**{k:1 for k in m.sup.COST_FIELDS},'event':'valid','outcome_valid':False,
                'required_cost_telemetry_complete':False,'success':False,'provider_usage_complete_calls':0,'provider_token_usage_complete':False}
            events.extend([{**base,'event':'reserved'},{**base,'event':'dispatched'},bad]);finals.append(bad)
            base={**base,'attempt_id':'a0r','retry_of':'a0','budget_bucket':'recovery'}
        final={**base,**{k:1 for k in m.sup.COST_FIELDS},'event':'valid','outcome_valid':True,
            'required_cost_telemetry_complete':True,'success':success,'provider_usage_complete_calls':1,'provider_token_usage_complete':True}
        events.extend([{**base,'event':'reserved'},{**base,'event':'dispatched'},final]);finals.append(final)
        attempts.extend(m.sup.attempt_record(v,row) for v in finals)
        accepted.append(final)
        outcomes.append({'task_id':row['task_id'],'profile':row['profile'],'success':success,'attempt_id':final['attempt_id'],'recovered':bool(final.get('retry_of'))})
        if row['profile'] in native:
            for k,v in counts(row).items():native[row['profile']][k]+=v
    successes={a:sum(v['success'] for v in outcomes if v['profile']==a) for a in m.c.ARMS}
    status={'status':phase,'completed_keys':[x['episode_key'] for x in rows[:n]],'attempts':attempts,
        'outcomes':outcomes,'successes':successes,'native':native,'auxiliary':aux,
        'dev_gate_promoted':n==40 and candidate_successes>=5 and phase=='completed_all_forty_audited',
        **m.sup.summarize(outcomes,attempts)}
    if phase=='rejected_numeric_futility':status['maximum_possible_candidate_successes']=successes['N23']+10-n//4
    def acceptor(plan,row,events):
        final=next(v for v in accepted if v['episode_key']==row['episode_key'])
        refs={k:{'path':'/synthetic/'+k,'sha256':'f'*64} for k in ('audit','worker_context','worker_receipt','attempt_result')}
        return final,refs,counts(row),aux
    return plan,status,events,acceptor

def test_full_promoted_and_all_denominators_match():
    result=m.analyze(*fixture())
    assert result['decision']=='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
    assert result['dispatched']==result['audited_cells']==40
    assert result['counts']['N23']=={'audited':10,'success':5}
    assert not torch.cuda.is_initialized()

def test_recovery_keeps_invalid_cost_and_uses_one_scientific_cell():
    result=m.analyze(*fixture(recovery=True))
    assert result['dev_gate_promoted'] and result['dispatched']==41 and result['audited_cells']==40
    assert result['accepted_cells'][0]['attempt_id']=='a0r'
    assert result['attempts'][0]['terminal']['outcome_valid'] is False
    assert result['gpu_process_wall_seconds']==41
    assert result['all_attempt_token_usage_complete'] is False
    assert result['unknown_token_calls']==1

def test_futility_only_after_full_quadruple():
    result=m.analyze(*fixture(n=24,candidate_successes=0,phase='rejected_numeric_futility'))
    assert result['decision']=='REJECT' and result['audited_cells']==24
    bad=list(fixture(n=23,candidate_successes=0,phase='rejected_numeric_futility'))
    with pytest.raises(Exception,match='futility'):m.analyze(*bad)

def test_failed_status_is_not_scientific_rejection():
    result=m.analyze(*fixture(n=4,candidate_successes=0,phase='failed'))
    assert result['decision']=='INVALID_OR_INTERRUPTED' and not result['dev_gate_promoted']

@pytest.mark.parametrize('fault',['inflight','false_promotion','changed_success','changed_source','duplicate_cell','invalid_retry'])
def test_inconsistent_reports_rejected(fault):
    plan,status,events,acceptor=fixture(recovery=fault=='invalid_retry')
    if fault=='inflight':events.pop()
    elif fault=='false_promotion':status['dev_gate_promoted']=False
    elif fault=='changed_success':status['successes']['N23']=6
    elif fault=='changed_source':events[-1]['source_commit']='bad'
    elif fault=='duplicate_cell':status['completed_keys'][-1]=status['completed_keys'][0]
    elif fault=='invalid_retry':
        for e in events:
            if e['attempt_id']=='a0r':e['retry_of']='absent'
    with pytest.raises(Exception):m.analyze(plan,status,events,acceptor)

def test_active_status_cannot_be_reported_terminal():
    plan,status,events,acceptor=fixture(n=1,phase='started')
    with pytest.raises(Exception,match='not terminal'):m.analyze(plan,status,events,acceptor)

