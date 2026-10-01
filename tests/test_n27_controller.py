"""Bounded synthetic controller gates; no actual outcomes, resources or dispatch."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from core.eds_eval_metrics import EDSChunkMetrics
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n27_contract as c
from scripts import qd_ed_n27_native as n
from scripts import qd_ed_n27_prepare as prep
from scripts import qd_ed_n27_report as report
from scripts import qd_ed_n27_supervise as sup
from scripts import qd_ed_n27_bridge as bridge

def write(path,value,jsonl=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(('\n'.join(json.dumps(x) for x in value)+'\n') if jsonl else json.dumps(value))
    return c.ref(path)


def rows():
    return [dict(episode_key=f'n27_dev_t{t:02d}_{a.lower()}_20260930',iteration=c.COHORT,split='dev',seed_block='dev',
        profile=a,task_id=t,env_seed=100+t,policy_seed=200+t,init_index=0,init_row_sha256='a'*64,
        init_file_sha256='b'*64,bddl_sha256='c'*64,budget_bucket='baseline' if a=='C0' else 'development',timeout_seconds=1800)
        for t in range(4) for a in c.ARMS]


def state():
    return {'gpu_pool':[7],'max_concurrent_gpu_workers':1,'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':522,'max_gpu_hours':100.,'reserved':dict(c.BASE_CAPS['buckets']),
            'amendment':dict(r.GPU7_N23_V2_AMENDMENT),'gpu_hour_reservations':dict(c.BASE_CAPS['protected_gpu_hours'])}}


def triplet(row,aid,*,valid=True,retry=None):
    base={'attempt_id':aid,'identity':r.episode_identity(row),'episode_key':row['episode_key'],
          'budget_bucket':'recovery' if retry else row['budget_bucket'],'retry_of':retry,'output_dir':'SYNTHETIC'}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},{**base,'event':'valid','outcome_valid':valid,
        'success':False,'gpu_process_wall_seconds':10.,'required_cost_telemetry_complete':valid,'guided_chunks':1,
        'provider_logical_call_attempts':2,'provider_usage_complete_calls':2 if valid else 1,'provider_token_usage_complete':valid}]


def metric(arm,substitutions=0):
    m=EDSChunkMetrics(score_call_count=11,search_evaluation_count=176,resample_count=10,renoise_count=10,rollout_count=10,
        qd_archive_active_for_chunk=arm!='C0')
    if arm in {'N26','N27'}:
        m.qd_quality_mode='actuator_clipped_provider_v1';m.qd_descriptor='target_xy_quadrant_signed_height_v1'
        m.qd_final_selection_mode='terminal_grasp_proximity_v1'
        m.qd_actuator_quality_batches=11;m.qd_actuator_quality_candidates=176;m.qd_actuator_clipped_prefix_candidates=3
        m.qd_actuator_overhead_seconds=.01
    if False:
        m.qd_gripper_rescue_mode='UNUSED';m.qd_gripper_rescue_checks=176;m.qd_gripper_rescue_updates=3
        m.qd_gripper_rescue_substitutions=substitutions;m.qd_gripper_rescue_overhead_seconds=.002
        m.parent_count_by_source={'qd_archive_offspring':160-substitutions,'qd_gripper_rescue_offspring':substitutions}
        m.qd_parent_slots_by_cell_by_iter=[{'0':16} for _ in range(4)]
        m.qd_gripper_rescue_actual_cells_by_iter=[[0]*16 for _ in range(4)]
    return m.to_jsonable()


def native_report(arm,substitutions=0):
    x={'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':11}}
    if arm in {'N26','N27'}:
        x['n5_grasp_timing_audit']={'checked_decisions':1,'parent_rounds_verified':10,'canonical_batches_verified':11,'canonical_candidates_verified':176}
        x['n23_actuator_clipped_quality_audit']={'score_batches_verified':11,'candidate_scores_verified':176,'clipped_prefix_candidates':3,'rank_changed_batches':1}
    if False:x['n27_gripper_parent_rescue_audit']={'schema':'n27-native-gripper-parent-rescue-audit-v1',
        'checked_decisions':1,'parent_rounds_verified':10,'canonical_batches_verified':11,'canonical_candidates_verified':176,'cache_updates':3,'substitutions':substitutions}
    return x


@pytest.mark.parametrize('case,expected,promoted',[
 ('all_fail',16,False),('five',16,True),('equal',16,False),('inferior',16,False),('unguided',16,False),
 ('one_recovery',17,True),('two_recovery',18,True),('third_recovery',9,False),('failed_recovery',8,False),('invalid',7,False)])
def test_full_controller_terminal_reader_and_costs(tmp_path,monkeypatch,case,expected,promoted):
    write(tmp_path/'scripts/qd_ed_n27_report.py',{'synthetic_reader':True})
    plan={'episodes':rows(),'source_commit':'synthetic'};path=tmp_path/'plan.json';write(path,plan)
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json');write(c.BRIDGE,{})
    monkeypatch.setattr(sup,'ROOT',tmp_path);monkeypatch.setattr(sup,'device_check',lambda:None)
    events=[];calls=[];recoveries=[]
    monkeypatch.setattr(r,'read_events',lambda path:copy.deepcopy(events))
    def attempt(_p,_plan,row,eligibility=None):
        i=plan['episodes'].index(row);retry=eligibility is not None
        fail=(case in {'one_recovery','two_recovery','third_recovery','failed_recovery'} and i in ({6} if case in {'one_recovery','failed_recovery'} else {2,5} if case=='two_recovery' else {2,5,6}) and (not retry or case=='failed_recovery')) or (case=='invalid' and i==6)
        aid=str(len(calls));group=triplet(row,aid,valid=not fail,retry=events[-1]['attempt_id'] if retry else None)
        final=group[-1];final['output_dir']=str(tmp_path/aid)
        final['success']=(row['task_id']<2 and row['profile']=='N27') if case!='all_fail' else False
        if case in {'equal','inferior'} and row['profile']!='N27':final['success']=row['task_id']<(2 if case=='equal' else 3)
        events.extend(group);calls.append(row['episode_key']);write(Path(final['output_dir'])/'attempt-result.json',final)
        for name in ('eds_eval/decision-evidence-audit.json','eds_eval/in-worker-audit-receipt.json','n23-worker-context.json'):write(Path(final['output_dir'])/name,{})
        return final
    monkeypatch.setattr(sup,'one_attempt',attempt)
    def eligible(*args):
        if case=='invalid' or len(recoveries)>=2:raise ValueError('noneligible or exhausted')
        recoveries.append(args[3]['attempt_id']);return {'synthetic':True}
    monkeypatch.setattr(sup.recovery,'create_eligibility',eligible)
    def accept(plan,row,events,root,env):
        final=[e for e in events if e['event']=='valid' and e['episode_key']==row['episode_key']][-1]
        if not final['outcome_valid']:raise ValueError('invalid')
        return final
    monkeypatch.setattr(c,'accepted_cell',accept);monkeypatch.setattr(c,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(n,'from_output',lambda *a:({'guided_decisions':0 if case=='unguided' else 1,'parent_rounds_verified':0 if case=='unguided' else 10,'substitutions':0},{}))
    status=tmp_path/'status.json'
    if case in {'third_recovery','failed_recovery','invalid'}:
        with pytest.raises(ValueError):sup.execute(path,plan,{'profiles':dict.fromkeys(c.ARMS,{})},{},status)
    else:sup.execute(path,plan,{'profiles':dict.fromkeys(c.ARMS,{})},{},status)
    result=json.loads((tmp_path/'result-v1.json').read_text())
    assert len(calls)==result['dispatched']==expected and result['dev_gate_promoted'] is promoted
    assert sum(v['gpu_process_wall_seconds']['observed_total'] for v in result['all_attempt_costs'].values())==10*expected
    if case=='all_fail':assert result['audited_cells']==16 and result['decision']=='REJECT_SCREEN'
    if 'recovery' in case:assert result['unknown_token_calls']>=1 and not result['all_attempt_token_usage_complete']
    with pytest.raises(ValueError):report.write_terminal(path,plan,status,tmp_path,vars(r))


@pytest.mark.parametrize('logical,complete,want',[(2,1,1),(None,None,None),(2,2,0)])
def test_unknown_tokens_independent_of_eligibility(logical,complete,want):
    item={'attempt_id':'a','profile':'C0','terminal':{'provider_logical_call_attempts':logical,'provider_usage_complete_calls':complete,'provider_token_usage_complete':False}}
    result=report.summary([],[item]);assert result['unknown_token_calls']==want and not result['all_attempt_token_usage_complete']


@pytest.mark.parametrize('fault',['after_terminal','missing_status','false_complete'])
def test_terminal_report_retains_cost_when_controller_prefix_lags(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json');write(c.BRIDGE,{})
    write(tmp_path/'scripts/qd_ed_n27_report.py',{})
    plan={'episodes':rows(),'source_commit':'synthetic'};planpath=tmp_path/'plan.json';write(planpath,plan)
    row=rows()[0];events=triplet(row,'a');events[-1]['output_dir']=str(tmp_path/'a');final=events[-1]
    for name in ('attempt-result.json','n23-worker-context.json','eds_eval/in-worker-audit-receipt.json','eds_eval/decision-evidence-audit.json'):write(tmp_path/'a'/name,{})
    monkeypatch.setattr(c,'accepted_cell',lambda *a:final);monkeypatch.setattr(c,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(n,'from_output',lambda *a:({'guided_decisions':1,'parent_rounds_verified':10},{}))
    status=tmp_path/'status.json'
    if fault!='missing_status':write(status,{'status':'completed_all_sixteen_audited' if fault=='false_complete' else 'failed','completed_keys':[],'dev_gate_promoted':fault=='false_complete'})
    result=report.write_terminal(planpath,plan,status,tmp_path,dict(vars(r),read_events=lambda path:events))
    assert result['decision']=='INVALID_OR_INTERRUPTED' and not result['dev_gate_promoted']
    assert result['audited_cells']==result['dispatched']==1 and not result['controller_evidence']['consistent']
    assert result['all_attempt_costs']['C0']['gpu_process_wall_seconds']['observed_total']==10




def test_exact_sixteen_draft_and_mixed_marker_routes(tmp_path,monkeypatch):
    parent={'episodes':[{**x,'task_id':t,'profile':a} for t in range(10) for a,x in zip(('C0','Q0','N25','N26'),rows()[:4])],
        'source_commit':c.BASE,'code_files':[],'scientific_config_files':[], 'n26_cohort':{'old':True},
        'runtime_manifest_path':str(tmp_path/'runtime.json'),'runtime_manifest_sha256':'runtime'}
    monkeypatch.setattr(c,'original_plan',lambda:copy.deepcopy(parent))
    for k in ('PROTOCOL','OBSERVABILITY','SOURCE_PLAN'):
        p=tmp_path/k;write(p,{});monkeypatch.setattr(c,k,p)
    plan=prep.build_plan(source={'commit':'synthetic','files':[],'sha256':'source'},root=r.ROOT)
    assert not plan['frozen'] and plan['n27_cohort']['authority'] is None and plan['n27_cohort']['final_review'] is None
    assert len(plan['episodes'])==16 and [(x['task_id'],x['profile']) for x in plan['episodes']]==[(t,a) for t in range(4) for a in c.ARMS]
    assert set(plan['candidate_profiles'])=={'N26','N27'} and 'n26_cohort' not in plan
    assert plan['n27_cohort']['early_stop']=='none_full_sixteen_required'
    assert r.is_n27_plan(plan) and not r.is_n26_plan(plan) and r.metered_support(plan) is c
    for marker in ('n25_cohort','n26_cohort','n25_infrastructure_continuation'):
        mixed={**plan,marker:{}}
        assert r.metered_support(mixed) is c
        with pytest.raises(ValueError):c.validate_worker_context({'profile':'N27'},[],r.ROOT,tmp_path,mixed,{})
    assert r.is_n26_plan({'candidate_profiles':{'N26':{}}}) and r.metered_support({'n26_cohort':{}}).__name__.endswith('n26_contract')


@pytest.mark.parametrize('fault',['none','wrong_cell','repeat_primary','valid_failure','aborted','second_cell_recovery','two_used'])
def test_typed_recovery_history_limits_only(fault):
    from scripts import qd_ed_n27_recovery as rec
    row=rows()[0];events=triplet(row,'a',valid=False)
    if fault=='wrong_cell':row=rows()[1]
    if fault=='repeat_primary':events+=triplet(row,'b',valid=False)
    if fault=='valid_failure':events[-1]['outcome_valid']=True
    if fault=='aborted':events[-1]['event']='aborted'
    if fault=='second_cell_recovery':events[0]['retry_of']='older'
    if fault=='two_used':
        events+=triplet(rows()[1],'r1',retry='p1')+triplet(rows()[2],'r2',retry='p2')
    if fault=='none':assert rec.check_cell_history(events,row,'a',vars(r))==events[-1]
    else:
        with pytest.raises(ValueError):rec.check_cell_history(events,row,'a',vars(r))


@pytest.mark.parametrize('spent,okay',[(9.25*3600-1840,True),(9.25*3600-1840+.001,False)])
def test_episode_full_timeout_plus_cleanup_capacity(monkeypatch,spent,okay):
    monkeypatch.setattr(c,'full_capacity',lambda *a:None);monkeypatch.setattr(c,'local_seconds',lambda *a:spent)
    row=rows()[0];plan={'episodes':rows()}
    if okay:c.protected_budget({},[],[],row,1800,vars(r),plan=plan)
    else:
        with pytest.raises(ValueError):c.protected_budget({},[],[],row,1800,vars(r),plan=plan)


def test_counter_missing_never_zero():
    result=report.summary([], [{'profile':'N27','attempt_id':'invalid','terminal':{'provider_logical_call_attempts':6,'provider_usage_complete_calls':2}}])
    assert result['unknown_token_calls']==4
    assert result['all_attempt_costs']['N27']['gpu_process_wall_seconds']['missing_attempts']==['invalid']
