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
from scripts import qd_ed_n25_contract as c
from scripts import qd_ed_n25_native as n
from scripts import qd_ed_n25_prepare as prep
from scripts import qd_ed_n25_report as report
from scripts import qd_ed_n25_supervise as sup
from scripts import qd_ed_n25_bridge as bridge

def write(path,value,jsonl=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(('\n'.join(json.dumps(x) for x in value)+'\n') if jsonl else json.dumps(value))
    return c.ref(path)


def rows():
    return [dict(episode_key=f'n25_dev_t{t:02d}_{a.lower()}_20260930',iteration=c.COHORT,split='dev',seed_block='dev',
        profile=a,task_id=t,env_seed=100+t,policy_seed=200+t,init_index=0,init_row_sha256='a'*64,
        init_file_sha256='b'*64,bddl_sha256='c'*64,budget_bucket='baseline' if a=='C0' else 'development',timeout_seconds=1800)
        for t in range(10) for a in c.ARMS]


def state():
    return {'gpu_pool':[7],'max_concurrent_gpu_workers':1,'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':478,'max_gpu_hours':100.,'reserved':dict(c.BASE_CAPS['buckets']),
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
    if arm in {'N23','N25'}:
        m.qd_quality_mode='actuator_clipped_provider_v1';m.qd_descriptor='target_xy_quadrant_signed_height_v1'
        m.qd_final_selection_mode='terminal_grasp_proximity_v1'
        m.qd_actuator_quality_batches=11;m.qd_actuator_quality_candidates=176;m.qd_actuator_clipped_prefix_candidates=3
        m.qd_actuator_overhead_seconds=.01
    if False:
        m.qd_gripper_rescue_mode='UNUSED';m.qd_gripper_rescue_checks=176;m.qd_gripper_rescue_updates=3
        m.qd_gripper_rescue_substitutions=substitutions;m.qd_gripper_rescue_overhead_seconds=.002
        m.parent_count_by_source={'qd_archive_offspring':160-substitutions,'qd_gripper_rescue_offspring':substitutions}
        m.qd_parent_slots_by_cell_by_iter=[{'0':16} for _ in range(10)]
        m.qd_gripper_rescue_actual_cells_by_iter=[[0]*16 for _ in range(10)]
    return m.to_jsonable()


def native_report(arm,substitutions=0):
    x={'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':11}}
    if arm in {'N23','N25'}:
        x['n5_grasp_timing_audit']={'checked_decisions':1,'parent_rounds_verified':10,'canonical_batches_verified':11,'canonical_candidates_verified':176}
        x['n23_actuator_clipped_quality_audit']={'score_batches_verified':11,'candidate_scores_verified':176,'clipped_prefix_candidates':3,'rank_changed_batches':1}
    if False:x['n25_gripper_parent_rescue_audit']={'schema':'n25-native-gripper-parent-rescue-audit-v1',
        'checked_decisions':1,'parent_rounds_verified':10,'canonical_batches_verified':11,'canonical_candidates_verified':176,'cache_updates':3,'substitutions':substitutions}
    return x


@pytest.fixture
def draft(tmp_path,monkeypatch):
    parent={'episodes':[{**x,'profile':('N7' if x['profile']=='N23' else 'N23' if x['profile']=='N25' else x['profile'])} for x in rows()],
        'source_commit':c.BASE,'code_files':[],'scientific_config_files':[],'n23_cohort':{'backend_proof':{'synthetic':True}},
        'runtime_manifest_path':str(tmp_path/'runtime.json'),'runtime_manifest_sha256':'runtime'}
    path=tmp_path/'source-plan.json';reference=write(path,parent)
    monkeypatch.setattr(c,'SOURCE_PLAN',path);monkeypatch.setattr(c,'SOURCE_PLAN_SHA',reference['sha256'])
    for k in ('PROTOCOL','OBSERVABILITY'):
        path=tmp_path/k;path.write_text(k);monkeypatch.setattr(c,k,path)
    return prep.build_plan(source={'commit':'synthetic','files':[],'sha256':'source'},root=r.ROOT)


def test_draft_exact_frozen_identity_mapping_is_nonexecutable(draft):
    assert draft['episodes']==rows() and not draft['frozen'] and draft['n25_cohort']['authority'] is None
    assert set(draft['candidate_profiles'])=={'N23','N25'} and 'n23_cohort' not in draft
    assert draft['phase_authorization']=={'dev':True,'validation':False,'formal':False}


@pytest.mark.parametrize('case,expected,promoted',[
 ('all_fail',24,False),('five',40,True),('equal',40,True),('inferior',40,False),('unguided',40,False),
 ('one_recovery',41,True),('two_recovery',42,True),('third_recovery',9,False),('failed_recovery',8,False),('invalid',7,False)])
def test_full_controller_terminal_reader_and_costs(tmp_path,monkeypatch,case,expected,promoted):
    write(tmp_path/'scripts/qd_ed_n25_report.py',{'synthetic_reader':True})
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
        final['success']=(row['task_id']<5 and row['profile']=='N25') if case!='all_fail' else False
        if case in {'equal','inferior'} and row['profile']!='N25':final['success']=row['task_id']<(5 if case=='equal' else 6)
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
    write(tmp_path/'scripts/qd_ed_n25_report.py',{})
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


@pytest.mark.parametrize('fault',['none','source','row','profile','phase','legacy_marker','runtime'])
def test_closed_contract_source_profile_matrix(draft,monkeypatch,fault):
    draft['code_files']=[{'path':'science.py','sha256':'science'}]
    source={'commit':'synthetic','files':copy.deepcopy(draft['code_files']),'sha256':'source'}
    monkeypatch.setattr(w,'source_record',lambda *a:source);monkeypatch.setattr(c,'source_paths',lambda *a:{'science.py'})
    meta=copy.deepcopy(draft['n25_cohort']);monkeypatch.setattr(c,'metadata',lambda *a:meta)
    monkeypatch.setattr(c,'expected_rows',rows);monkeypatch.setattr(c,'validate_runtime',lambda *a:None)
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(r,'read_state',lambda *a:{})
    manifest=r.read_json(r.ROOT/'configs/qd_ed_final/baseline_profiles.json')
    for arm in ('N23','N25'):manifest['profiles'][arm]=r.expand_candidate(arm,r.read_json(r.ROOT/f'configs/qd_ed_final/candidate_{arm.lower()}.json'),manifest['profiles']['Q0'])
    draft['stage_condition']=r.E2_STAGE_CONDITION
    if fault=='source':draft['code_files']=[]
    if fault=='row':draft['episodes'][1]['env_seed']+=1
    if fault=='profile':manifest['profiles']['N25']['resolved_eds_config']['initial_diversity_descriptor_mode']='absolute_eef'
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
    def accept(plan,prior,*a):return {'success':prior['profile']=='N25' and prior['task_id']<wins}
    monkeypatch.setattr(c,'accepted_cell',accept)
    if accepted:assert c.admission(plan,{},row,events,[],r.ROOT,vars(r))['n25_cohort_id']==c.COHORT
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




@pytest.fixture(autouse=True)
def synthetic_classifier(monkeypatch):
    from n25_cpu_synthetic import install_classifier
    install_classifier(monkeypatch)


def test_n25_routing_and_exact_two_modes_default_controls():
    plan={'candidate_profiles':{'N23':{},'N25':{}}}
    assert r.is_n25_plan(plan) and r.metered_support(plan) is c
    assert not any(f(plan) for f in (r.is_n23_plan,r.is_n23_v2_plan,r.is_n7_plan,r.is_n24_plan,r.is_n21_plan,r.is_n22_plan))
    assert r.is_n24_plan({'candidate_profiles':{'N23':{},'N24':{}}})
    assert r.is_n23_plan({'candidate_profiles':{'N7':{},'N23':{}}})
    assert r.is_n7_plan({'candidate_profiles':{'N7':{}}})
    q=r.read_json(r.ROOT/'configs/qd_ed_final/baseline_profiles.json')['profiles']['Q0'];saved=copy.deepcopy(q)
    a=r.expand_candidate('N23',r.read_json(r.ROOT/'configs/qd_ed_final/candidate_n23.json'),q)
    b=r.expand_candidate('N25',r.read_json(r.ROOT/'configs/qd_ed_final/candidate_n25.json'),q)
    assert q==saved and b['resolved_eds_config']=={**a['resolved_eds_config'],
        'initial_diversity_descriptor_mode':n.MODE,'rollout_diversity_descriptor_mode':n.MODE}
    assert b['resolved_eds_config'].get('qd_gripper_rescue_mode','none')=='none'


@pytest.mark.parametrize('arm',c.ARMS)
@pytest.mark.parametrize('fault',['none','missing_n25_gate','canonical','compute','terminal','boolean','missing_compute'])
def test_zero_guided_real_absent_metric_compatibility(tmp_path,arm,fault):
    gate={'accepted':True,'evidence_complete':True,'observed_counts':{'decision_context':90}}
    compute={'episode_id':0,'policy_counters_available':True,'guided_chunks':0,'rbf_gradient_calls':0,'rbf_gradient_batch_rows':0}
    if arm=='N25':
        from scripts.qd_ed_audit_backend import create_backend
        gate[n.GATE]=n.audit_events('N25',[],[],compute,create_backend('cpu'))
    if fault=='missing_n25_gate':gate.pop(n.GATE,None)
    if fault=='canonical':gate['observed_counts']['canonical_candidate_batch']=11
    if fault=='compute':compute['guided_chunks']=1
    if fault=='boolean':compute['guided_chunks']=False
    if fault!='missing_compute':write(tmp_path/'eds_eval/episode_compute.jsonl',[compute],True)
    if fault=='none' or (fault=='missing_n25_gate' and arm!='N25'):
        assert n.from_output(arm,tmp_path,gate,0)[0]['guided_decisions']==0
    else:
        with pytest.raises(ValueError):n.from_output(arm,tmp_path,gate,1 if fault=='terminal' else 0)


@pytest.mark.parametrize('fault',['none','active','invalid','promoted','missing_review','source','validation_valid_reject'])
def test_predecessor_exact_valid_disposition_only(tmp_path,monkeypatch,fault):
    dev={'source_commit':'3b7afa02757eb3519d95547e4b6e6e939f7068f2','decision':'REJECT_NUMERIC_FUTILITY','dev_gate_promoted':False,'audited_cells':24}
    if fault=='active':dev['decision']='RUNNING'
    if fault=='invalid':dev['decision']='INVALID_OR_INTERRUPTED'
    if fault=='promoted':dev.update(decision='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION',dev_gate_promoted=True)
    if fault=='validation_valid_reject':dev.update(decision='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION',dev_gate_promoted=True,audited_cells=40)
    dev.update(counts={'synthetic':'aggregate'},native={'synthetic':'counts'},plan=write(tmp_path/'old-plan.json',{}),
        ledger_snapshot=write(tmp_path/'old-ledger.json',[]),controller_evidence={'consistent':True})
    dr=write(tmp_path/'dev.json',dev)
    files=[{'path':f'synthetic{i}.py','sha256':'a'*64} for i in range(230)]
    source={'commit':'other' if fault=='source' else dev['source_commit'],'files':files,'sha256':w.canonical_sha(files)}
    review={'schema':'n24-root-terminal-review-v2','result':dr,'decision':'WRONG' if fault=='missing_review' else 'ACCEPT_TERMINAL_RECONSTRUCTION',
        'source':write(tmp_path/'source.json',source),'source_files_verified':230,'cohort_disposition':dev['decision'],
        'accepted_cells':dev['audited_cells'],'counts':dev['counts'],'native':dev['native'],'plan':dev['plan'],'ledger':dev['ledger_snapshot']}
    record={'schema':'n25-predecessor-review-v1','source_commit':dev['source_commit'],'dev_result':dr,
      'dev_root_review':write(tmp_path/'review.json',review),'disposition':'VALID_DEV_REJECTION','validation_review':None,'allow_n25':True}
    if fault=='validation_valid_reject':
        record['disposition']='VALID_VALIDATION_REJECTION';record['validation_review']=write(tmp_path/'val.json',{
          'schema':'n25-predecessor-validation-aggregate-review-v1','dev_result':dr,'source_commit':dev['source_commit'],
          'all_cells_native_valid':True,'decision':'REJECT','protected_per_task_results_consulted_for_n25':False})
    path=tmp_path/'predecessor.json';reference=write(path,record);monkeypatch.setattr(c,'PREDECESSOR',path)
    if fault in {'none','validation_valid_reject'}:assert c.predecessor()==reference
    else:
        with pytest.raises(ValueError):c.predecessor()


@pytest.mark.parametrize('fault',['none','larger_finite','hour','protected_hour','recovery','val','total','negative','missing_adoption','hold','private','reservation'])
def test_finite_future_budget_requires_exact_root_record(tmp_path,monkeypatch,fault):
    predecessor=write(tmp_path/'predecessor.json',{});monkeypatch.setattr(c,'predecessor',lambda:predecessor)
    caps=copy.deepcopy(c.BASE_CAPS)
    if fault=='larger_finite':caps['buckets']['baseline']+=10;caps['buckets']['development']+=30;caps['attempts']+=40
    if fault=='hour':caps['gpu_hours']=101
    if fault=='protected_hour':caps['protected_gpu_hours']['formal']=11
    if fault=='recovery':caps['buckets']['recovery']+=1;caps['attempts']+=1
    if fault=='val':caps['buckets']['validation']-=1;caps['attempts']-=1
    if fault=='total':caps['attempts']+=1
    if fault=='negative':caps['buckets']['development']=-1
    document=tmp_path/'amendment.md';document.write_text('synthetic finite authority')
    record={'schema':'n25-finite-budget-authority-v1','cohort_id':c.COHORT,'caps':caps,'amendment':'synthetic-n25-finite',
      'amendment_document':c.ref(document),'predecessor':predecessor,'recorded_at':'synthetic','authority_interpretation':'root only'}
    path=tmp_path/'budget.json';reference=write(path,record);monkeypatch.setattr(c,'BUDGET_AUTHORITY',path)
    st=state();st['n25_budget_authority']=reference;st['budget'].update(max_episode_attempts=caps['attempts'],max_gpu_hours=caps['gpu_hours'],
        reserved=caps['buckets'],gpu_hour_reservations=caps['protected_gpu_hours'],amendment=record['amendment'])
    if fault=='missing_adoption':st.pop('n25_budget_authority')
    if fault=='hold':st['external_resource_hold']={'do_not_auto_resume':True}
    if fault=='private':st['resource_isolation']['private_budget']=False
    if fault=='reservation':st['budget']['gpu_hour_reservations']={}
    if fault in {'none','larger_finite'}:c.require_budget_state(st,vars(r))
    else:
        with pytest.raises((ValueError,r.GateError)):c.require_budget_state(st,vars(r))


@pytest.mark.parametrize('fault',['none','local','protected','bucket','missing_authority','running','missing_backend'])
def test_per_dispatch_full_1840_local_and_protected_capacity(tmp_path,monkeypatch,fault):
    from scripts import qd_ed_n25_backend as backend
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(c,'budget_authority',lambda:{'caps':c.BASE_CAPS})
    monkeypatch.setattr(bridge,'settled_backend',lambda *a:None);monkeypatch.setattr(backend,'settled_proof',lambda *a:None)
    for k in ('BRIDGE','BACKEND_PROOF','AUTHORITY'):
        path=tmp_path/k;write(path,{'local_gpu_hours':10.} if k=='AUTHORITY' else {});monkeypatch.setattr(c,k,path)
    snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=40.;events=[]
    if fault=='local':write(c.AUTHORITY,{'local_gpu_hours':.5})
    if fault=='protected':snap['gpu_hours_consumed']=47.
    if fault=='bucket':snap['by_bucket']['baseline']=42
    if fault=='missing_authority':c.AUTHORITY.unlink()
    if fault=='missing_backend':c.BACKEND_PROOF.unlink()
    if fault=='running':snap['running']=1
    env={**vars(r),'budget_snapshot':lambda *a:snap};row=rows()[0];plan={'episodes':rows()}
    if fault=='none':c.protected_budget({},events,[],row,1800,env,plan=plan)
    else:
        with pytest.raises((ValueError,OSError)):c.protected_budget({},events,[],row,1800,env,plan=plan)


@pytest.mark.parametrize('fault',['none','changed_current','changed_reverse','unrelated_function'])
def test_actual_shared_source_reverse_bridge_no_git_process(monkeypatch,tmp_path,fault):
    record=json.loads((r.ROOT/'docs/03_evidence/qd_ed_final/n25/shared-route-insertions-v1.json').read_text())
    old={}
    for item in record['files']:
        current=(r.ROOT/item['path']).read_text();lines=current.splitlines(keepends=True)
        for edit in reversed(item['edits']):lines[edit['new_start']:edit['new_end']]=edit['old'].splitlines(keepends=True)
        old[item['path']]=''.join(lines).encode()
        path=tmp_path/item['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(current)
    reverse=tmp_path/'docs/03_evidence/qd_ed_final/n25/shared-route-insertions-v1.json'
    if fault=='changed_reverse':record['files'][0]['edits'][0]['old']+='changed\n'
    write(reverse,record)
    if fault=='changed_current':(tmp_path/record['files'][0]['path']).write_text('changed')
    monkeypatch.setattr(bridge.subprocess,'check_output',lambda cmd,**k:old[cmd[2].split(':',1)[1]])
    if fault in {'none','unrelated_function'}:assert len(bridge.verify_reverse(tmp_path))==2
    else:
        with pytest.raises(ValueError):bridge.verify_reverse(tmp_path)
    if fault=='unrelated_function':
        oldfunctions=bridge.functions(old['scripts/qd_ed_n23_worker.py'].decode())
        newfunctions=bridge.functions((tmp_path/'scripts/qd_ed_n23_worker.py').read_text())
        assert oldfunctions.keys()==newfunctions.keys()
        assert all(oldfunctions[k]==newfunctions[k] for k in oldfunctions.keys()-bridge.ROUTES['scripts/qd_ed_n23_worker.py'])


@pytest.mark.parametrize('fault',['none','missing','failed','source'])
def test_dev_final_review_requires_successful_same_source_proof(tmp_path,monkeypatch,fault):
    from scripts import qd_ed_n25_backend as backend
    source={'commit':'final','files':[],'sha256':'s'};runtime={'path':'r','sha256':'r'}
    for name in ('PROTOCOL','SOURCE_PLAN','BRIDGE','PREDECESSOR','BACKEND_PROOF','ARITHMETIC_PROTOCOL','FINAL_REVIEW'):
        path=tmp_path/name;write(path,{});monkeypatch.setattr(c,name,path)
    monkeypatch.setattr(c,'require_protocols',lambda *a:None)
    monkeypatch.setattr(bridge,'verify',lambda *a:{'new_source':source})
    monkeypatch.setattr(c,'predecessor',lambda:c.ref(c.PREDECESSOR))
    def proof(*args):
        if fault=='source':raise ValueError('source differs')
        return {'accepted':fault!='failed'}
    monkeypatch.setattr(backend,'verify_proof',proof)
    write(c.FINAL_REVIEW,{'schema':'n25-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
      'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'source_bridge':c.ref(c.BRIDGE),
      'predecessor':c.predecessor(),'backend_proof':c.ref(c.BACKEND_PROOF),'arithmetic_protocol':c.ref(c.ARITHMETIC_PROTOCOL),'no_gpu_release':True})
    if fault=='missing':c.BACKEND_PROOF.unlink()
    if fault=='none':assert c.final_review(source,runtime,tmp_path)==c.ref(c.FINAL_REVIEW)
    else:
        with pytest.raises((OSError,ValueError)):c.final_review(source,runtime,tmp_path)
