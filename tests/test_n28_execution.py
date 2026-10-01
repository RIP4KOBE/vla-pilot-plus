"""N28 new arithmetic/evidence and closed runtime gates, synthetic-only."""
import copy,json,math
from pathlib import Path
from types import SimpleNamespace
import pytest,torch
from test_rdt_steer import _patch_core_imports,stub_steer,stub_adapter,_rollout_cond,_n2_fixture_provider
from test_n25_clipped_rbf import native_adapter,input_tensor,config
from test_n26_clean_output_rbf import layout
ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('case',['strict_interior','exact_boundary','mixed_saturation','distinct_saturated','coincident_saturated','coincident_interior'])
@pytest.mark.parametrize('arrangement',['contiguous','model_slice'])
def test_parent_proof_exact_cases(dtype,case,arrangement):
    from scripts.qd_ed_n28_preflight import check_case
    from scripts.qd_ed_audit_backend import create_backend
    from scripts.qd_ed_n28_reference import CASES
    # Parameter identities must match original fixed native corpus, not silently substitute.
    assert case in CASES
    result=check_case(case,dtype,arrangement,create_backend('cpu'),ROOT)
    assert result['accepted'] and result['boundary_observer_binding_verified'] and result['rng_scope']=='cpu_only'


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_native_parent_sequence_boundary_corruption(stub_steer,stub_adapter,monkeypatch,tmp_path,dtype):
    from core.decision_evidence import DecisionEvidence
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    from scripts import qd_ed_n28_native as n
    from scripts.qd_ed_audit_backend import create_backend
    for key,value in vars(static_adapter_fixture()).items():monkeypatch.setattr(stub_adapter,key,value,raising=False)
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    stub_steer._noise_scheduler.config={'prediction_type':'sample'}
    monkeypatch.setattr(stub_steer._rdt_model.dit,'forward',lambda *a:layout(input_tensor(dtype,16),'model_slice'))
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype)
    provider=_n2_fixture_provider(index=0);rec=DecisionEvidence(tmp_path/'native',episode=0)
    rec.begin_decision(global_step=24,stage=1,use_guidance=True,keypoints=points,providers=[provider]);stub_steer._decision_evidence=rec
    monkeypatch.setattr(stub_adapter,'_decision_evidence',rec,raising=False)
    stub_steer._eds_guided_denoise_loop(x_t=input_tensor(dtype,16),cond=_rollout_cond(stub_steer),keypoints=points,
        guidance_fns=[provider],eds_config=config(stub_steer,'N28'),verbose=False,global_step=24,current_stage=1)
    metrics=stub_steer.get_last_eds_metrics();metrics['global_step']=24;events=rec._pending
    compute=stub_steer.get_episode_compute_counters();compute['guided_chunks']=1
    backend=create_backend('cpu');gate=n.audit_events('N28',[metrics],events,compute,backend)
    assert gate['all_call_summaries_verified']==14 and gate['witness_calls_verified']==11 and gate['parent_boundaries_verified']==10
    assert gate['witness_numeric_bytes']<=220*1024
    for fault in ('all_markers','boundary','allocation','prefix','operand','boundary_order','metrics_phase'):
        bad=copy.deepcopy(events);m=copy.deepcopy(metrics)
        if fault=='all_markers':bad=[e for e in bad if not e['event'].startswith('n28')]
        elif fault=='boundary':bad=[e for e in bad if e['event']!='n28_parent_renoise_input']
        elif fault=='allocation':next(e for e in bad if e['event']=='n28_rbf_witness' and e['values']['metadata']['call']['phase']=='parent')['values']['metadata']['call']['parent_allocation_sequence']+=1
        elif fault in ('prefix','boundary_order'):
            e=next(e for e in bad if e['event']=='n28_parent_renoise_input')
            if fault=='prefix':e['values']['prefix'][0,0,0]+=.125
            else:e['values']['metadata']['parent_witness_sequence']+=1
        elif fault=='operand':next(e for e in bad if e['event']=='n28_rbf_witness' and e['values']['metadata']['call']['phase']=='parent')['values']['tensors']['update_operand'][0,0,0]+=.125
        else:m['rollout_direction_rbf_evidence_by_iter'][0][0]['phase']='rollout'
        with pytest.raises(ValueError):n.audit_events('N28',[m],bad,compute,backend)
    with pytest.raises(ValueError):n.audit_events('N27',[metrics],events,compute,backend)


def test_zero_guided_gate_cannot_downgrade():
    from scripts import qd_ed_n28_native as n
    report={'accepted':True,'evidence_complete':True,'observed_counts':{}}
    with pytest.raises(ValueError):n.counts('N28',[],report,0)
    report[n.GATE]=n.audit_events('N28',[],[],{'guided_chunks':0,'rbf_gradient_calls':0,'rbf_gradient_batch_rows':0},None)
    assert n.counts('N28',[],report,0)[0]['guided_decisions']==0
    with pytest.raises(ValueError):n.counts('N27',[],report,0)


def rows():
    from scripts import qd_ed_n28_contract as c
    return [dict(task_id=t,profile=a,episode_key=f't{t}_{a}',split='dev',seed_block='dev',iteration=c.COHORT,
       env_seed=11+t,policy_seed=22+t,init_index=0,timeout_seconds=1800,budget_bucket='baseline' if a=='C0' else 'development') for t in range(4) for a in c.ARMS]


def journal(successes=(),invalid=None,count=16):
    result=[]
    for i,row in enumerate(rows()[:count]):
        base={'attempt_id':f'a{i}','identity':dict(row),'episode_key':row['episode_key'],'budget_bucket':row['budget_bucket'],
          'source_commit':'synthetic','plan_sha256':'p','output_dir':f'/synthetic/{i}'}
        result.extend([{**base,'event':'reserved'},{**base,'event':'dispatched'}, {**base,'event':'valid',
          'outcome_valid':i!=invalid,'success':i in successes,'gpu_process_wall_seconds':10.,'required_cost_telemetry_complete':i!=invalid,
          'provider_logical_call_attempts':3,'provider_usage_complete_calls':2 if i==invalid else 3,'provider_token_usage_complete':i!=invalid}])
    return result


def accept(row,events):
    finals=[e for e in events if e['episode_key']==row['episode_key'] and e['event']=='valid'];assert len(finals)==1
    final=finals[0]
    if not final['outcome_valid']:raise ValueError('native/transport incomplete')
    return {**{k:row[k] for k in ('episode_key','task_id','profile')},'attempt_id':final['attempt_id'],'success':final['success']}, {'guided_decisions':1,'parent_rounds_verified':10},{}


@pytest.mark.parametrize('wins,decision',[((), 'REJECT_SCREEN'),((3,7),'ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV'),((2,3,6,7),'REJECT_SCREEN'),((0,4,8,3,7),'REJECT_SCREEN')])
def test_complete_sixteen_screen_thresholds(wins,decision):
    from scripts import qd_ed_n28_report as report
    result=report.analyze({'episodes':rows(),'source_commit':'synthetic'},journal(wins),accept)
    assert result['audited_cells']==16 and result['decision']==decision and result['goal_status']=='TARGET_NOT_MET'
    assert result['validation_authorized'] is result['formal_authorized'] is False


def test_invalid_cost_unknown_no_retry_and_global_order():
    from scripts import qd_ed_n28_report as report
    plan={'episodes':rows(),'source_commit':'synthetic'};events=journal(invalid=3,count=4)
    result=report.analyze(plan,events,accept)
    assert result['audited_cells']==3 and result['dispatched']==4 and result['decision']=='INVALID_OR_INTERRUPTED'
    assert result['unknown_token_calls']==1 and result['all_attempt_costs']['N28']['gpu_process_wall_seconds']['observed_total']==10
    events[-1].pop('provider_usage_complete_calls');result=report.analyze(plan,events,accept)
    assert result['unknown_token_calls'] is None and result['unmeasured_token_call_attempts']==['a3']
    for bad in (events[3:6]+events[:3]+events[6:],events+[{**e,'attempt_id':'repeat','retry_of':'a3'} for e in events[-3:]]):
        with pytest.raises(ValueError):report.analyze(plan,bad,accept)
    aborted=[{**events[0],'event':'reserved'},{**events[0],'event':'aborted','outcome_valid':False,'gpu_process_wall_seconds':0.}]
    result=report.analyze(plan,aborted,lambda *x:(_ for _ in ()).throw(ValueError('no dispatch')))
    assert result['dispatched']==0 and result['audited_cells']==0 and result['decision']=='INVALID_OR_INTERRUPTED'


def test_new_marker_routing_and_no_retry():
    from scripts import qd_ed_final_runner as r,qd_ed_n28_contract as c,qd_ed_n27_contract as old
    plan={'n28_cohort':{},'candidate_profiles':{'N27':{},'N28':{}}}
    assert r.is_n28_plan(plan) and not r.is_n27_plan(plan) and not r.is_n26_plan(plan) and r.metered_support(plan) is c
    assert r.metered_support({'n27_cohort':{}}) is old
    c.check_retry([{'identity':{'iteration':'unrelated'},'episode_key':rows()[0]['episode_key']}],rows()[0],vars(r))
    for events,row in [(journal(count=1),rows()[0]),([],{**rows()[0],'retry_of':'a0'}),([],{**rows()[0],'n27_recovery_eligibility':{}})]:
        with pytest.raises(ValueError):c.check_retry(events,row,vars(r))

@pytest.mark.parametrize('arm',['C0','Q0','N27','N28'])
def test_zero_guided_missing_metrics_actual_output_shape(tmp_path,arm):
    from scripts import qd_ed_n28_native as n
    directory=tmp_path/'eds_eval';directory.mkdir()
    compute={'policy_counters_available':True,'guided_chunks':0,'rbf_gradient_calls':0,'rbf_gradient_batch_rows':0}
    (directory/'episode_compute.jsonl').write_text(json.dumps(compute)+'\n')
    report={'accepted':True,'evidence_complete':True,'observed_counts':{}}
    if arm in {'N27','N28'}:
        report[n.GATE if arm=='N28' else n.old.GATE]=n.audit_events(arm,[],[],compute,None)
    assert n.from_output(arm,tmp_path,report,0)[0]['guided_decisions']==0
    bad=copy.deepcopy(report);bad['observed_counts']={'canonical_candidate_batch':11}
    with pytest.raises(ValueError):n.from_output(arm,tmp_path,bad,0)
    if arm=='N28':
        report.pop(n.GATE)
        with pytest.raises(ValueError):n.from_output(arm,tmp_path,report,0)
