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
from scripts import qd_ed_n24_contract as c
from scripts import qd_ed_n24_native as n
from scripts import qd_ed_n24_prepare as prep
from scripts import qd_ed_n24_report as report
from scripts import qd_ed_n24_supervise as sup
from scripts import qd_ed_n24_bridge as bridge


def write(path,value,jsonl=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(('\n'.join(json.dumps(x) for x in value)+'\n') if jsonl else json.dumps(value))
    return c.ref(path)


def rows():
    return [dict(episode_key=f'n24_dev_t{t:02d}_{a.lower()}_20260930',iteration=c.COHORT,split='dev',seed_block='dev',
        profile=a,task_id=t,env_seed=100+t,policy_seed=200+t,init_index=0,init_row_sha256='a'*64,
        init_file_sha256='b'*64,bddl_sha256='c'*64,budget_bucket='baseline' if a=='C0' else 'development',timeout_seconds=1800)
        for t in range(10) for a in c.ARMS]


def state():
    return {'gpu_pool':[7],'max_concurrent_gpu_workers':1,'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':478,'max_gpu_hours':100.,'reserved':dict(c.CAPS['buckets']),
            'amendment':dict(r.GPU7_N23_V2_AMENDMENT),'gpu_hour_reservations':dict(c.CAPS['protected_gpu_hours'])}}


def triplet(row,aid,*,valid=True,retry=None):
    base={'attempt_id':aid,'identity':r.episode_identity(row),'episode_key':row['episode_key'],
          'budget_bucket':'recovery' if retry else row['budget_bucket'],'retry_of':retry,'output_dir':'SYNTHETIC'}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},{**base,'event':'valid','outcome_valid':valid,
        'success':False,'gpu_process_wall_seconds':10.,'required_cost_telemetry_complete':valid,'guided_chunks':1,
        'provider_logical_call_attempts':2,'provider_usage_complete_calls':2 if valid else 1,'provider_token_usage_complete':valid}]


def metric(arm,substitutions=0):
    m=EDSChunkMetrics(score_call_count=11,search_evaluation_count=176,resample_count=10,renoise_count=10,rollout_count=10,
        qd_archive_active_for_chunk=arm!='C0')
    if arm in {'N23','N24'}:
        m.qd_quality_mode='actuator_clipped_provider_v1';m.qd_descriptor='target_xy_quadrant_signed_height_v1'
        m.qd_final_selection_mode='terminal_grasp_proximity_v1'
        m.qd_actuator_quality_batches=11;m.qd_actuator_quality_candidates=176;m.qd_actuator_clipped_prefix_candidates=3
        m.qd_actuator_overhead_seconds=.01
    if arm=='N24':
        m.qd_gripper_rescue_mode=n.MODE;m.qd_gripper_rescue_checks=176;m.qd_gripper_rescue_updates=3
        m.qd_gripper_rescue_substitutions=substitutions;m.qd_gripper_rescue_overhead_seconds=.002
        m.parent_count_by_source={'qd_archive_offspring':160-substitutions,'qd_gripper_rescue_offspring':substitutions}
        m.qd_parent_slots_by_cell_by_iter=[{'0':16} for _ in range(10)]
        m.qd_gripper_rescue_actual_cells_by_iter=[[0]*16 for _ in range(10)]
    return m.to_jsonable()


def native_report(arm,substitutions=0):
    x={'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':11}}
    if arm in {'N23','N24'}:
        x['n5_grasp_timing_audit']={'checked_decisions':1,'parent_rounds_verified':10,'canonical_batches_verified':11,'canonical_candidates_verified':176}
        x['n23_actuator_clipped_quality_audit']={'score_batches_verified':11,'candidate_scores_verified':176,'clipped_prefix_candidates':3,'rank_changed_batches':1}
    if arm=='N24':x['n24_gripper_parent_rescue_audit']={'schema':'n24-native-gripper-parent-rescue-audit-v1',
        'checked_decisions':1,'parent_rounds_verified':10,'canonical_batches_verified':11,'canonical_candidates_verified':176,'cache_updates':3,'substitutions':substitutions}
    return x


@pytest.mark.parametrize('arm',c.ARMS)
def test_actual_serializer_profile_binding(arm):
    m=metric(arm);gate=native_report(arm)
    if arm in {'C0','Q0'}:assert 'qd_quality_mode' not in m and 'qd_gripper_rescue_mode' not in m
    counts,aux=n.counts(arm,[m],gate,1)
    assert counts['guided_decisions']==1
    if arm=='N24':assert counts['substitutions']==0


@pytest.mark.parametrize('fault',['all_markers','missing_mode','wrong_mode','wrong_source','original_slots','actual_cells','canonical','counter','aux','guided'])
def test_rescue_gate_rejects_missing_or_inconsistent_native(fault):
    m=metric('N24',1);gate=native_report('N24',1);guided=1
    if fault=='all_markers':
        m={k:v for k,v in m.items() if not k.startswith('qd_gripper_rescue')};gate.pop('n24_gripper_parent_rescue_audit')
    if fault=='missing_mode':m.pop('qd_quality_mode')
    if fault=='wrong_mode':m['qd_gripper_rescue_mode']='none'
    if fault=='wrong_source':m['parent_count_by_source']={'qd_archive_offspring':160}
    if fault=='original_slots':m['qd_parent_slots_by_cell_by_iter'][0]={'0':15}
    if fault=='actual_cells':m['qd_gripper_rescue_actual_cells_by_iter'][0][0]=16
    if fault=='canonical':gate['observed_counts']['canonical_candidate_batch']=10
    if fault=='counter':m['qd_gripper_rescue_updates']=4
    if fault=='aux':m['qd_gripper_rescue_overhead_seconds']=None
    if fault=='guided':guided=0
    with pytest.raises(ValueError):n.counts('N24',[m],gate,guided)


@pytest.mark.parametrize('arm',c.ARMS)
@pytest.mark.parametrize('fault',['none','canonical','canonical_bool','canonical_unknown','compute','compute_bool','terminal','terminal_bool','missing_compute'])
def test_zero_guided_absent_metrics_uses_native_and_episode_compute(tmp_path,arm,fault):
    gate={'accepted':True,'evidence_complete':True,'observed_counts':{'decision_context':90}}
    compute={'episode_id':0,'policy_counters_available':True,'guided_chunks':0}
    if fault=='canonical':gate['observed_counts']['canonical_candidate_batch']=11
    if fault=='canonical_bool':gate['observed_counts']['canonical_candidate_batch']=False
    if fault=='canonical_unknown':gate.pop('observed_counts')
    if fault=='compute_bool':compute['guided_chunks']=False
    if fault=='compute':compute['guided_chunks']=1
    if fault!='missing_compute':write(tmp_path/'eds_eval/episode_compute.jsonl',[compute],True)
    assert not (tmp_path/'eds_eval/eds_metrics.jsonl').exists()
    if fault=='none':assert n.from_output(arm,tmp_path,gate,0)[0]['guided_decisions']==0
    else:
        with pytest.raises(ValueError):n.from_output(arm,tmp_path,gate,False if fault=='terminal_bool' else 1 if fault=='terminal' else 0)


def test_routing_and_exact_profile_delta():
    plan={'candidate_profiles':{'N23':{},'N24':{}}}
    assert r.is_n24_plan(plan) and r.metered_support(plan) is c
    assert not any(f(plan) for f in (r.is_n23_plan,r.is_n23_v2_plan,r.is_n7_plan,r.is_n21_plan,r.is_n22_plan))
    assert r.is_n23_plan({'candidate_profiles':{'N7':{},'N23':{}}})
    assert r.is_n7_plan({'candidate_profiles':{'N7':{}}})
    q=r.read_json(r.ROOT/'configs/qd_ed_final/baseline_profiles.json')['profiles']['Q0']
    a=r.expand_candidate('N23',r.read_json(r.ROOT/'configs/qd_ed_final/candidate_n23.json'),q)
    b=r.expand_candidate('N24',r.read_json(r.ROOT/'configs/qd_ed_final/candidate_n24.json'),q)
    assert b['resolved_eds_config']==dict(a['resolved_eds_config'],qd_gripper_rescue_mode=n.MODE)


@pytest.fixture
def draft(tmp_path,monkeypatch):
    parent={'episodes':[{**x,'profile':('N7' if x['profile']=='N23' else 'N23' if x['profile']=='N24' else x['profile'])} for x in rows()],
        'source_commit':c.BASE,'code_files':[],'scientific_config_files':[],'n23_cohort':{'backend_proof':{'synthetic':True}},
        'runtime_manifest_path':str(tmp_path/'runtime.json'),'runtime_manifest_sha256':'runtime'}
    path=tmp_path/'source-plan.json';reference=write(path,parent)
    monkeypatch.setattr(c,'SOURCE_PLAN',path);monkeypatch.setattr(c,'SOURCE_PLAN_SHA',reference['sha256'])
    for k in ('PROTOCOL','OBSERVABILITY'):
        path=tmp_path/k;path.write_text(k);monkeypatch.setattr(c,k,path)
    return prep.build_plan(source={'commit':'synthetic','files':[],'sha256':'source'},root=r.ROOT)


def test_draft_exact_frozen_identity_mapping_is_nonexecutable(draft):
    assert draft['episodes']==rows() and not draft['frozen'] and draft['n24_cohort']['authority'] is None
    assert set(draft['candidate_profiles'])=={'N23','N24'} and 'n23_cohort' not in draft
    assert draft['phase_authorization']=={'dev':True,'validation':False,'formal':False}


@pytest.mark.parametrize('fault',['none','resource','budget','bucket','gpu','hold','adoption'])
def test_state_exact_caps_and_adoption(tmp_path,monkeypatch,fault):
    st=state();reference=write(tmp_path/'authority.json',{'source':{},'runtime':{}})
    monkeypatch.setattr(c,'AUTHORITY',Path(reference['path']));st['n24_dev_authority']=reference
    monkeypatch.setattr(c,'authority',lambda *a:reference)
    if fault=='resource':st['resource_isolation']['validation_status']='PENDING'
    if fault=='budget':st['budget']['max_episode_attempts']=479
    if fault=='bucket':st['budget']['reserved']['recovery']=21
    if fault=='gpu':st['gpu_pool']=[3]
    if fault=='hold':st['external_resource_hold']={'do_not_auto_resume':True}
    if fault=='adoption':st.pop('n24_dev_authority')
    if fault=='none':c.require_state(st,vars(r))
    else:
        with pytest.raises((ValueError,r.GateError)):c.require_state(st,vars(r))


@pytest.mark.parametrize('fault',['none','hours','protected','bucket','running','unsettled','optional'])
def test_full_remaining_budget_protects_reserves(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(bridge,'settled_backend',lambda *a:None)
    path=tmp_path/'bridge.json';write(path,{});monkeypatch.setattr(c,'BRIDGE',path)
    snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=33.;events=[]
    if fault=='hours':snap['gpu_hours_consumed']=35.
    if fault=='protected':snap['dispatched']=217
    if fault=='bucket':snap['by_bucket']['development']=158
    if fault=='running':snap['running']=1
    if fault=='unsettled':events=triplet(rows()[0],'a')[:2]
    if fault=='optional':events=[{'identity':{'iteration':c.PREFLIGHT}}]
    env=dict(vars(r),budget_snapshot=lambda *a:snap)
    if fault=='none':c.full_capacity(state(),events,[],env)
    else:
        with pytest.raises((ValueError,r.GateError)):c.full_capacity(state(),events,[],env)


@pytest.mark.parametrize('case,expected,promoted',[
 ('all_fail',24,False),('five',40,True),('equal',40,True),('inferior',40,False),('unguided',40,False),
 ('one_recovery',41,True),('two_recovery',42,True),('third_recovery',9,False),('failed_recovery',8,False),('invalid',7,False)])
def test_full_controller_terminal_reader_and_costs(tmp_path,monkeypatch,case,expected,promoted):
    write(tmp_path/'scripts/qd_ed_n24_report.py',{'synthetic_reader':True})
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
        final['success']=(row['task_id']<5 and row['profile']=='N24') if case!='all_fail' else False
        if case in {'equal','inferior'} and row['profile']!='N24':final['success']=row['task_id']<(5 if case=='equal' else 6)
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
    if case=='all_fail':assert result['audited_cells']==24 and result['decision']=='REJECT_NUMERIC_FUTILITY' and all('t06' not in k for k in calls)
    if 'recovery' in case:assert result['unknown_token_calls']>=1 and not result['all_attempt_token_usage_complete']
    with pytest.raises(ValueError):report.write_terminal(path,plan,status,tmp_path,vars(r))


@pytest.mark.parametrize('logical,complete,want',[(2,1,1),(None,None,None),(2,2,0)])
def test_unknown_tokens_independent_of_eligibility(logical,complete,want):
    item={'attempt_id':'a','profile':'C0','terminal':{'provider_logical_call_attempts':logical,'provider_usage_complete_calls':complete,'provider_token_usage_complete':False}}
    result=report.summary([],[item]);assert result['unknown_token_calls']==want and not result['all_attempt_token_usage_complete']


@pytest.mark.parametrize('fault',['after_terminal','missing_status','false_complete'])
def test_terminal_report_retains_cost_when_controller_prefix_lags(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json');write(c.BRIDGE,{})
    write(tmp_path/'scripts/qd_ed_n24_report.py',{})
    plan={'episodes':rows(),'source_commit':'synthetic'};planpath=tmp_path/'plan.json';write(planpath,plan)
    row=rows()[0];events=triplet(row,'a');events[-1]['output_dir']=str(tmp_path/'a');final=events[-1]
    for name in ('attempt-result.json','n23-worker-context.json','eds_eval/in-worker-audit-receipt.json','eds_eval/decision-evidence-audit.json'):write(tmp_path/'a'/name,{})
    monkeypatch.setattr(c,'accepted_cell',lambda *a:final);monkeypatch.setattr(c,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(n,'from_output',lambda *a:({'guided_decisions':1,'parent_rounds_verified':10},{}))
    status=tmp_path/'status.json'
    if fault!='missing_status':write(status,{'status':'completed_all_forty_audited' if fault=='false_complete' else 'failed','completed_keys':[],'dev_gate_promoted':fault=='false_complete'})
    result=report.write_terminal(planpath,plan,status,tmp_path,dict(vars(r),read_events=lambda path:events))
    assert result['decision']=='INVALID_OR_INTERRUPTED' and not result['dev_gate_promoted']
    assert result['audited_cells']==result['dispatched']==1 and not result['controller_evidence']['consistent']
    assert result['all_attempt_costs']['C0']['gpu_process_wall_seconds']['observed_total']==10


@pytest.mark.parametrize('fault',['none','alias','escape','wrong_root','provider','uuid','probe'])
def test_runtime_alias_strict_ownership_and_provider(tmp_path,monkeypatch,fault):
    root=tmp_path/'root';root.mkdir();alias=tmp_path/'alias';alias.symlink_to(root,target_is_directory=True)
    file=root/'asset';file.write_text('static');lexical=alias/'asset' if fault=='alias' else file
    if fault=='escape':
        other=tmp_path/'outside';other.write_text('x');file.unlink();file.symlink_to(other)
    runtime={'worktree':str(alias if fault=='alias' else root),'schema':'qd-ed-runtime-setup-v1','artifact_root':str(root/'artifacts'),
        'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID,'egl_device_index':4},'cuda_egl_verified':True,
        'cuda_egl_probe':{'resource_id':c.GPU7_PROOF},'stage_recovered_error_condition':r.E2_STAGE_CONDITION,
        'stage_engineering_condition':r.n4e1_support().engineering_condition(),'frozen_stage_provider':{'allow_recovered_error_events':True},
        'files':[{'path':str(lexical),'sha256':w.sha(lexical)}]}
    if fault=='wrong_root':runtime['worktree']=str(tmp_path)
    if fault=='provider':runtime['stage_recovered_error_condition']='other'
    if fault=='uuid':runtime['gpu_mapping']['uuid']='other'
    if fault=='probe':runtime['cuda_egl_probe']['resource_id']='other'
    ref=write(tmp_path/'runtime.json',runtime);monkeypatch.setattr(c,'runtime_ref',lambda:ref)
    if fault in {'none','alias'}:c.validate_runtime(runtime,root,vars(r))
    else:
        with pytest.raises((ValueError,r.GateError)):c.validate_runtime(runtime,root,vars(r))


@pytest.mark.parametrize('fault',['none','report','bucket','unsettled','fp32','negative_control','backend'])
def test_source_bridge_consumes_settled_strict_backend_json(tmp_path,fault):
    runtime={'path':'synthetic','sha256':'runtime'}
    plan={'source':{'commit':c.BASE},'runtime':runtime};planref=write(tmp_path/'backend-plan.json',plan)
    item={'candidates':16,'dtype':'torch.bfloat16','accepted':True,'mismatches':[],
          'production_helper_passed':True,'independent_passed':True,'wrong_score_rejected':True}
    proofreport={'schema':'n23-backend-preflight-proof-v2','accepted':True,'task_outcome':False,'attempt_id':'old',
        'plan':planref,'source':plan['source'],'runtime':runtime,'process':{'pid':1},'worker_wall_seconds':10,
        'batches':[copy.deepcopy(item) for _ in range(176)],'synthetic':[{**item,'candidates':4,'dtype':dtype} for dtype in ('torch.float32','torch.bfloat16')],
        'wrong_bounds_rejected':True,'errors':[],'backend':{'kind':'cuda','logical_device':'cuda:0','physical_uuid':c.GPU7_UUID,'dtype_coverage':['torch.float32','torch.bfloat16']}}
    if fault=='report':proofreport['accepted']=False
    if fault=='fp32':proofreport['synthetic'][0]['accepted']=False
    if fault=='negative_control':proofreport['batches'][0]['wrong_score_rejected']=False
    if fault=='backend':proofreport['backend']['physical_uuid']='wrong'
    proof={'attempt_id':'old','plan':planref,'report':write(tmp_path/'report.json',proofreport)}
    events=triplet(rows()[0],'old');events[-1].update(budget_bucket='recovery',backend_preflight_report=proof['report'],process={'pid':1},gpu_process_wall_seconds=16)
    if fault=='bucket':events[-1]['budget_bucket']='baseline'
    if fault=='unsettled':events.pop()
    if fault=='none':assert bridge.settled_backend({'prior_backend_proof':proof,'runtime':runtime},events,vars(r))==proof
    else:
        with pytest.raises((ValueError,r.GateError)):bridge.settled_backend({'prior_backend_proof':proof,'runtime':runtime},events,vars(r))


@pytest.fixture
def worker_job(tmp_path,monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('n24_backend_cpu_fixture',r.ROOT/'tests/test_qd_ed_n23_backend.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    monkeypatch.setattr(old,'commit',lambda *a:None)
    def source(root,paths):
        files=[{'path':p,'sha256':w.sha(Path(root)/p)} for p in sorted(paths)]
        return {'commit':'synthetic','files':files,'sha256':w.canonical_sha(files)}
    monkeypatch.setattr(w,'source_record',source)
    return old.owned_job.__wrapped__(tmp_path,monkeypatch)


@pytest.mark.parametrize('arm',c.ARMS)
@pytest.mark.parametrize('guided',[False,True])
def test_n24_same_process_worker_receipt_and_actual_serializer(worker_job,monkeypatch,arm,guided):
    import torch
    job=worker_job;job.plan.pop('n23_cohort');job.plan['n24_cohort']={'worker_audit':c.WORKER_CONTRACT};job.plan['frozen']=True
    job.plan['episodes'][0].update(iteration=c.COHORT,profile=arm);job.context['profile']=arm
    job.context['plan']=write(Path(job.plan_ref['path']),job.plan);write(job.context_path,job.context)
    write(job.output/'eds_eval/episode_compute.jsonl',[{'policy_counters_available':True,'guided_chunks':int(guided)}],True)
    if guided:write(job.output/'eds_eval/eds_metrics.jsonl',[metric(arm)],True)
    def audit(episode,compute,*,arithmetic_backend):
        job.calls.append('audit')
        if guided and arm in {'N23','N24'}:arithmetic_backend.native(torch.zeros(1,dtype=torch.bfloat16))
        report=native_report(arm) if guided else {'accepted':True,'evidence_complete':True,'observed_counts':{'decision_context':90}}
        return {**report,'n23_arithmetic_backend':arithmetic_backend.report()}
    monkeypatch.setattr(w.audit,'audit_episode',audit)
    assert w.run_worker(job.context_path,job.command[1:])==0
    assert job.calls==['identity','cuda' if arm in {'N23','N24'} else 'cpu','audit']
    job.calls.clear();assert w.verify_receipt(job.context_path,job.process)['accepted'] and not job.calls
    receipt=json.loads((job.output/'eds_eval/in-worker-audit-receipt.json').read_text())
    assert receipt['n24_metrics']['present'] is guided and receipt['n24_native_counts']['guided_decisions']==int(guided)
    if not guided:assert receipt['n24_metrics']['sha256'] is None
    # Later appearance or change must invalidate the same receipt even when scientific counters match.
    write(job.output/'eds_eval/eds_metrics.jsonl',[],True)
    with pytest.raises(ValueError):w.verify_receipt(job.context_path,job.process)


@pytest.mark.parametrize('arm',['C0','Q0','N7','N23'])
def test_old_worker_routing_unchanged(worker_job,monkeypatch,arm):
    job=worker_job;job.plan['episodes'][0]['profile']=arm;job.context['profile']=arm
    job.context['plan']=write(Path(job.plan_ref['path']),job.plan);write(job.context_path,job.context)
    assert w.run_worker(job.context_path,job.command[1:])==0
    assert job.calls==['identity','cuda' if arm=='N23' else 'cpu','audit']
    job.calls.clear();assert w.verify_receipt(job.context_path,job.process)['accepted'] and not job.calls
    receipt=json.loads((job.output/'eds_eval/in-worker-audit-receipt.json').read_text());assert 'n24_metrics' not in receipt


@pytest.mark.parametrize('fault',['none','missing','source','runtime','caps','validation','review'])
def test_external_review_and_authority_fail_closed(tmp_path,monkeypatch,fault):
    root=tmp_path/'root';(root/'experiments/qd_ed_n24').mkdir(parents=True)
    for name,content in [('PROTOCOL','protocol'),('OBSERVABILITY','observability')]:
        p=tmp_path/name;p.write_text(content);monkeypatch.setattr(c,name,p);monkeypatch.setattr(c,name+'_SHA',w.sha(p))
    (root/'experiments/qd_ed_n24/protocol-dev-v1.md').write_text('protocol')
    source={'commit':'synthetic','files':[],'sha256':'source'};runtime={'path':'runtime','sha256':'runtime'}
    for name in ('BRIDGE','FINAL_REVIEW','AUTHORITY','SOURCE_PLAN'):monkeypatch.setattr(c,name,tmp_path/(name+'.json'))
    write(c.BRIDGE,{'new_source':source});write(c.SOURCE_PLAN,{})
    monkeypatch.setattr(bridge,'verify',lambda *a:{'new_source':source})
    write(c.FINAL_REVIEW,{'schema':'n24-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
        'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'source_bridge':c.ref(c.BRIDGE),
        'native_preflight':{'required':False,'proof':None},'no_gpu_release':True})
    value={'schema':'n24-dev-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime,'protocol':c.ref(c.PROTOCOL),
        'final_review':c.ref(c.FINAL_REVIEW),'limits':c.LIMITS,'caps':copy.deepcopy(c.CAPS),'recorded_at':'synthetic',
        'authority_interpretation':'synthetic','validation_authorized':False,'formal_authorized':False}
    if fault=='source':value['source']={}
    if fault=='runtime':value['runtime']={}
    if fault=='caps':value['caps']['attempts']=479
    if fault=='validation':value['validation_authorized']=True
    if fault=='review':value['final_review']['sha256']='other'
    if fault!='missing':write(c.AUTHORITY,value)
    if fault=='none':assert c.authority(source,runtime,root)==c.ref(c.AUTHORITY)
    else:
        with pytest.raises((ValueError,OSError)):c.authority(source,runtime,root)


def test_execution_no_resume_and_exact_release(tmp_path,monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(sup,'ROOT',tmp_path)
    plan={'episodes':rows(),'source_commit':'synthetic','n24_cohort':{'authority':{'path':'synthetic','sha256':'a'}}}
    path=tmp_path/'plan.json';write(path,plan)
    release=tmp_path/'execution-release-v1.json'
    write(release,{'schema':'n24-dev-execution-release-v1','plan':c.ref(path),'source_commit':'synthetic','cohort_id':c.COHORT,
        'episode_keys':[x['episode_key'] for x in rows()],'authority':plan['n24_cohort']['authority'],'physical_gpu':7,'limits':c.LIMITS,
        'validation_authorized':False,'formal_authorized':False})
    sup.release_check(release,path,plan)
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{},{}));monkeypatch.setattr(r,'locked',lambda *a,**k:nullcontext())
    monkeypatch.setattr(c,'full_capacity',lambda *a:None);monkeypatch.setattr(r,'read_state',lambda *a:{})
    monkeypatch.setattr(r,'read_events',lambda *a:triplet(rows()[0],'a'))
    monkeypatch.setattr(sup,'execute',lambda *a:pytest.fail('must not dispatch'))
    with pytest.raises(ValueError,match='prior reservation'):sup.launch(path,release,tmp_path/'execution/supervisor-status-v1.json')
    write(tmp_path/'execution/supervisor-status-v1.json',{})
    with pytest.raises(ValueError,match='no automatic'):sup.launch(path,release,tmp_path/'execution/supervisor-status-v1.json')


@pytest.mark.parametrize('fault',['none','source','row','profile','phase','legacy_marker','runtime'])
def test_closed_contract_source_profile_matrix(draft,monkeypatch,fault):
    draft['code_files']=[{'path':'science.py','sha256':'science'}]
    source={'commit':'synthetic','files':copy.deepcopy(draft['code_files']),'sha256':'source'}
    monkeypatch.setattr(w,'source_record',lambda *a:source);monkeypatch.setattr(c,'source_paths',lambda *a:{'science.py'})
    meta=copy.deepcopy(draft['n24_cohort']);monkeypatch.setattr(c,'metadata',lambda *a:meta)
    monkeypatch.setattr(c,'expected_rows',rows);monkeypatch.setattr(c,'validate_runtime',lambda *a:None)
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(r,'read_state',lambda *a:{})
    manifest=r.read_json(r.ROOT/'configs/qd_ed_final/baseline_profiles.json')
    for arm in ('N23','N24'):manifest['profiles'][arm]=r.expand_candidate(arm,r.read_json(r.ROOT/f'configs/qd_ed_final/candidate_{arm.lower()}.json'),manifest['profiles']['Q0'])
    draft['stage_condition']=r.E2_STAGE_CONDITION
    if fault=='source':draft['code_files']=[]
    if fault=='row':draft['episodes'][1]['env_seed']+=1
    if fault=='profile':manifest['profiles']['N24']['resolved_eds_config']['qd_gripper_rescue_mode']='none'
    if fault=='phase':draft['phase_authorization']['validation']=True
    if fault=='legacy_marker':draft['n23_cohort']={}
    if fault=='runtime':draft['runtime_manifest_sha256']='wrong'
    if fault=='none':c.validate_contract(draft,manifest,{},None,r.ROOT,vars(r))
    else:
        with pytest.raises((ValueError,r.GateError)):c.validate_contract(draft,manifest,{},None,r.ROOT,vars(r))


@pytest.mark.parametrize('index,wins,accepted',[(0,0,True),(1,0,True),(23,0,True),(24,0,False),(24,1,True),(39,4,True)])
def test_admission_exact_prefix_and_only_complete_quad_futility(index,wins,accepted,monkeypatch):
    plan={'episodes':rows()};row=plan['episodes'][index]
    events=[e for i,p in enumerate(rows()[:index]) for e in triplet(p,str(i))]
    def accept(plan,prior,*a):return {'success':prior['profile']=='N24' and prior['task_id']<wins}
    monkeypatch.setattr(c,'accepted_cell',accept)
    if accepted:assert c.admission(plan,{},row,events,[],r.ROOT,vars(r))['n24_cohort_id']==c.COHORT
    else:
        with pytest.raises(ValueError,match='futility'):c.admission(plan,{},row,events,[],r.ROOT,vars(r))
    events+=triplet(rows()[-1],'future')
    with pytest.raises(ValueError,match='prefix'):c.admission(plan,{},row,events,[],r.ROOT,vars(r))


@pytest.mark.parametrize('fault',['none','plan_sha','terminal_identity','receipt','plan_content','guided','invalid'])
def test_accepted_terminal_uses_real_runner_base_schema(tmp_path,monkeypatch,fault):
    row=rows()[0];plan={'episodes':[row],'source_commit':'synthetic','profiles_sha256':'profiles',
        'runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path)}
    planref=write(tmp_path/'plan.json',plan);output=tmp_path/'output';receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
    write(output/'n23-worker-context.json',{'plan':planref})
    final=triplet(row,'primary')[-1]
    final.update(output_dir=str(output),source_commit='synthetic',plan_sha256=planref['sha256'],profile_manifest_sha256='profiles',
        runtime_manifest_sha256='runtime',runtime_inventory_sha256='inventory',physical_gpu=7,init_row_sha256=row['init_row_sha256'],n23_worker_receipt=receipt)
    assert 'init_index' not in final and 'init_file_sha256' not in final and 'bddl_sha256' not in final
    if fault=='plan_sha':final['plan_sha256']='wrong'
    if fault=='terminal_identity':final['identity']['init_index']=1
    if fault=='invalid':final['outcome_valid']=False
    if fault=='guided':final['guided_chunks']=0
    write(output/'attempt-result.json',final);events=triplet(row,'primary');events[-1]=final
    if fault=='receipt':write(output/'eds_eval/in-worker-audit-receipt.json',{'change':True})
    if fault=='plan_content':write(tmp_path/'plan.json',{})
    write(output/'eds_eval/eds_metrics.jsonl',[metric('C0')],True)
    write(output/'eds_eval/episode_compute.jsonl',[{'policy_counters_available':True,'guided_chunks':1}],True)
    monkeypatch.setattr(c,'read_worker_report',lambda *a:native_report('C0'))
    if fault=='none':assert c.accepted_cell(plan,row,events,r.ROOT,vars(r))==final
    else:
        with pytest.raises((ValueError,r.GateError)):c.accepted_cell(plan,row,events,r.ROOT,vars(r))


@pytest.mark.parametrize('fault',['none','science','worker_unrelated','controller_scope'])
def test_source_bridge_exact_unchanged_bytes_and_bounded_routes(tmp_path,monkeypatch,fault):
    # Mock Git's frozen bytes only; byte comparisons and function parsing are real.
    for name in set(bridge.UNCHANGED_BASE)|set(bridge.UNCHANGED_PHASE_A):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# frozen\n')
    old='def validate_context():\n    pass\ndef run_worker():\n    pass\ndef verify_receipt():\n    pass\ndef numerical():\n    return 1\n'
    new=old.replace('def run_worker():\n    pass','def run_worker():\n    return 1')
    if fault=='worker_unrelated':new=new.replace('def numerical():\n    return 1','def numerical():\n    return 2')
    (tmp_path/'scripts/qd_ed_n23_worker.py').write_text(new)
    if fault=='science':(tmp_path/bridge.UNCHANGED_BASE[0]).write_text('# changed\n')
    monkeypatch.setattr(bridge,'old_bytes',lambda root,commit,path:old.encode() if path=='scripts/qd_ed_n23_worker.py' else b'# frozen\n')
    monkeypatch.setattr(bridge.subprocess,'check_output',lambda *a,**k:'core/qd_ed.py\n' if fault=='controller_scope' else 'scripts/qd_ed_n23_worker.py\n')
    monkeypatch.setattr(c,'original_plan',lambda:{'source_commit':c.BASE,'n23_cohort':{'backend_proof':{'synthetic':True}}})
    monkeypatch.setattr(c,'RUN_DIR',tmp_path)
    for file in ('cpu-implementation-report-v1.md','cpu-test-results-v1.json'):(tmp_path/file).write_text('{}')
    if fault=='none':assert bridge.build({'commit':'new'}, {'runtime':'same'},tmp_path)['new_gpu_preflight'] is False
    else:
        with pytest.raises(ValueError):bridge.build({'commit':'new'},{'runtime':'same'},tmp_path)
