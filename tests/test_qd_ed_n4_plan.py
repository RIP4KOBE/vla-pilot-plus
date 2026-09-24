"""Synthetic CPU-only N4 entry/identity/resource tests; never real study data."""
import copy
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module
r=load('n4_test_runner',ROOT/'scripts/qd_ed_final_runner.py')
n=load('n4_test_contract',ROOT/'scripts/qd_ed_n4_plan.py')
def baseline():return r.read_json(ROOT/'configs/qd_ed_final/baseline_profiles.json')
def candidate():return r.read_json(ROOT/n.PROFILE)


def decision(step=0,different=False):
    costs={'dtype':'torch.float32','shape':[2],'values':[-3.,-2.],'sha256':'c'*64}
    return {'global_step':step,'actual_prefix_length':8,'canonical_batches_verified':11,
        'canonical_candidates_verified':176,'parent_rounds_verified':10,'selected_index':0,
        'selected_occurrence_id':'canonical:10:0','minimum_cost_tie_indices':[0,1],
        'selected_cell':2,'selected_parent_cell':3,'selected_fingerprint':'f'*64,
        'selected_cost':-2.,'selected_raw_reward':2.,'terminal_native_costs':{'dtype':'torch.float32','shape':[16]},
        'archive_reference_index':0,'archive_reference_fingerprint':'a'*64,'archive_reference_cell':1,
        'archive_reference_raw_reward':3.,'archive_reference_cost':-3.,'archive_reference_costs':costs,
        'archive_cost_reference_sha256':costs['sha256'],'stage_raw_reward':2.,
        'canonical_sources':[{'iter_idx':i,'canonical_sequence':i*3+6,'scoring_batch_id':i*3+5} for i in range(-1,10)],
        'decoded_reference_first8_diff_positions':[[0,0]] if different else [],
        'decoded_reference_actual_prefix_diff_positions':[[0,0]] if different else []}


def native_audit(count=1,different=0):
    return {'accepted':True,'evidence_complete':True,'n4_terminal_population_audit':{
        'schema':n.NATIVE_AUDIT_SCHEMA,'checked_decisions':count,'canonical_batches_verified':count*11,
        'canonical_candidates_verified':count*176,'parent_rounds_verified':count*10,
        'decoded_reference_first8_different_decisions':different,
        'decoded_reference_actual_prefix_different_decisions':different,'actual_actions_verified':count*8,
        'decisions':[decision(i*8,i<different) for i in range(count)]}}


def metric(step=0):
    d=decision(step);t={key:d[key] for key in ('selected_index','selected_occurrence_id','minimum_cost_tie_indices',
        'selected_cell','selected_parent_cell','selected_fingerprint','selected_cost','selected_raw_reward')}
    t.update(iter_idx=9,population_size=16,canonical_event_sequence=d['canonical_sources'][-1]['canonical_sequence'],
        scoring_batch_id=d['canonical_sources'][-1]['scoring_batch_id'],cost_dtype='torch.float32')
    a={'global_best_index':0,'selected_fingerprint':'a'*64,'selected_cell':1,'selected_quality':3.,
        'selected_cost':-3.,'costs':[-3.,-2.],'cost_dtype':'torch.float32','final_selection_mismatch_count':0,
        'stage_reference_scope':'qd_archive_cost_spread','target_distance_after':None}
    return {'global_step':step,'qd_final_selection_mode':'terminal_population_v1','qd_terminal_population':t,
        'qd_archive_reference':a,'selected_idx':0,'selected_cost':-2.,'selected_reward':2.,'qd_selected_cell':2,
        'qd_selected_reward':2.,'qd_selected_action_fingerprint':'f'*64,'qd_global_best_action_fingerprint':'a'*64,
        'target_distance_after':None}


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','')
    monkeypatch.setitem(sys.modules,'qd_ed_n4_plan',n)
    root=tmp_path/'worktree';root.mkdir();artifacts=tmp_path/'artifacts';artifacts.mkdir()
    for relative in n.REQUIRED|{'configs/qd_ed_final/baseline_profiles.json'}:
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes((ROOT/relative).read_bytes() if relative in n.FROZEN_DOCS else b'synthetic source\n')
    bp=root/'configs/qd_ed_final/baseline_profiles.json';bp.write_text(json.dumps(baseline()))
    c=candidate();c['baseline_provenance']['sha256']=r.digest(bp);(root/n.PROFILE).write_text(json.dumps(c))
    observed=n.observed_profiles(baseline(),r.digest(bp));(root/n.OBSERVED).write_text(json.dumps(observed))
    manifest=copy.deepcopy(observed);manifest['profiles']['N4']=r.expand_candidate('N4',c,manifest['profiles']['Q0'])
    seeds={'blocks':{'dev':[{'task_id':t,'env_seed':t+100,'policy_seed':t+100,'init_index':0,
        'init_row_sha256':'row'+str(t),'init_file_sha256':'init'+str(t),'bddl_sha256':'bddl'+str(t)} for t in range(10)]}}
    runtime={'gpu_mapping':{'physical_gpu':3,'uuid':'GPU-test','egl_device_index':0},
        'frozen_stage_provider':{'backend':'codex_cli','public_config_sha256':'transport'},'cuda_egl_probe':{'resource_id':'prior-proof'}}
    def ref(name,value):
        path=artifacts/(name+'.json');path.write_text(json.dumps(value));return {'path':str(path),'sha256':r.digest(path)}
    evidence=ref('evidence',{})
    prereq=ref('prerequisite',{'schema':'n4-q0-transfer-complete-root-review-v1','decision':'PASS_FIXED_Q0_ACTIVITY_PREREQUISITE',
        'counts':{'cells':10,'guided':155,'Unknown':0,'conjunction':1},**dict.fromkeys(('index','provenance','status','launch_result'),evidence)})
    monkeypatch.setattr(n,'PREREQUISITE_REVIEW_SHA256',prereq['sha256'])
    resource=ref('resource',{'schema':'qd-ed-shared-current-resource-contract-v1','status':'ACTIVE_FOR_CURRENT_GPU3_N4_CONTINUATION',
        'authority_worktree':str(root),'physical_gpu':3,'gpu_uuid':'GPU-test','bucket_caps':n.ORIGINAL_CAPS,
        'global_max_attempts':240,'global_max_gpu_hours':48,'protected_gpu_hours':{'validation':14.,'formal':10.},
        'protected_original_attempts':{'validation':60,'formal':40},'N4_original_allocation':{
            k:[f't{t:02d}-{p}' for t,p in n.BUDGET_ALLOCATION[k+'_cells']] for k in ('baseline','development')},
        'eligible_recovery_cap':4,'per_cell_recovery_cap':1,'local_dispatch_cap':16,
        'local_gpu_hour_cap_including_new_health':8.5,'max_owned_GPU_workers':1,
        'amendment':{'sha256':n.FROZEN_DOCS[n.ALLOCATION]}})
    monkeypatch.setattr(n,'SHARED_RESOURCE_SHA256',resource['sha256'])
    pointer=root/n.RESOURCE_POINTER;pointer.parent.mkdir(exist_ok=True)
    pointer.write_text(json.dumps({'schema':'qd-ed-shared-resource-pointer-v1','active_contract':resource,
        'physical_gpu':3,'online_dispatch_authorized':False}))
    records=[{'path':p,'sha256':r.digest(root/p)} for p in sorted(n.REQUIRED|{'configs/qd_ed_final/baseline_profiles.json'})]
    contract={'schema':'qd-ed-n4-cohort-v1','cohort_id':n.COHORT,'limits':copy.deepcopy(n.LIMITS),
        'budget_allocation':copy.deepcopy(n.BUDGET_ALLOCATION),'health_resources':[{'resource_id':'prior-proof','scope':'reused_prior'}],
        'runtime_prerequisites':{'boot_id':n.BOOT,'reuse_scope':'prior_engineering_only_not_N4_algorithm_validation',
            'references':dict.fromkeys(n.PREREQUISITES,{}),'native_dependencies':{'path':n.DEPENDENCIES,'sha256':r.digest(root/n.DEPENDENCIES)}},
        'prerequisite_review':prereq,'shared_resource_contract':resource,
        'shared_resource_pointer':{'path':n.RESOURCE_POINTER,'sha256':r.digest(pointer)},'checkpoint_release':None}
    for key,p in [('protocol',n.PROTOCOL),('accounting_clarification',n.CLARIFICATION),('budget_allocation_amendment',n.ALLOCATION),('prerequisite_protocol',n.PREREQUISITE)]:
        contract[key]={'path':p,'sha256':r.digest(root/p)}
    plan={'worktree':str(root),'artifact_root':str(artifacts),'boot_id':n.BOOT,'source_commit':'same-source',
        'profiles_path':str(root/n.OBSERVED),'profiles_sha256':r.digest(root/n.OBSERVED),
        'runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory','seed_plan_sha256':'seeds',
        'code_files':records,'episodes':n.rows_from_dev(seeds),'phase_authorization':{'dev':True,'validation':False,'formal':False},
        'candidate_profiles':{'N4':{'path':str(root/n.PROFILE),'sha256':r.digest(root/n.PROFILE)}},'n4_cohort':contract}
    def attest(schema,**values):
        return ref(schema,{'schema':schema,'cohort_id':n.COHORT,'source_commit':plan['source_commit'],
            'protocol_sha256':contract['protocol']['sha256'],'source_files_sha256':n.source_identity(plan),
            'evidence':[evidence],**values})
    monkeypatch.setattr(r,'n4_support',lambda:n)
    resources=[{'resource_id':'prior-proof','event':'completed','gpu_process_wall_seconds':99999.}]
    return root,plan,manifest,runtime,seeds,resources,attest


def events(plan,runtime,row,attempt='a',*,terminal='valid',valid=True,seconds=1.,retry_of=None):
    output=Path(plan['artifact_root'])/attempt;(output/'eds_eval').mkdir(parents=True,exist_ok=True)
    audit=native_audit() if row['profile']=='N4' else {'accepted':True,'evidence_complete':True}
    (output/'eds_eval/decision-evidence-audit.json').write_text(json.dumps(audit))
    if row['profile']=='N4':(output/'eds_eval/eds_metrics.jsonl').write_text(json.dumps(metric())+'\n')
    base={'attempt_id':attempt,'output_dir':str(output),'identity':r.episode_identity(row),'budget_bucket':row['budget_bucket'],
        'retry_of':retry_of,'n4_cohort_id':n.COHORT,'n4_frozen_identity':n.binding(plan,runtime),'metric_chunks':1,'guided_chunks':1}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},
        {**base,'event':terminal,'outcome_valid':valid,'success':False,'gpu_process_wall_seconds':seconds,
         'retryable_infrastructure':terminal=='aborted','reason':'external GPU3 process appeared during owned attempt' if terminal=='aborted' else None}]


def release(fixture,keys,stage='first3'):
    root,plan,_,runtime,*_=fixture
    path=Path(plan['artifact_root'])/'plan.json';path.write_text(json.dumps(plan))
    value={'schema':'qd-ed-n4-execution-release-v1','status':'authorized','cohort_id':n.COHORT,
        'plan':{'path':str(path),'sha256':r.digest(path)},'frozen_identity':n.binding(plan,runtime),
        'source_commit':plan['source_commit'],'source_files_sha256':n.source_identity(plan),
        'candidate_profiles':plan['candidate_profiles'],'shared_resource_contract':plan['n4_cohort']['shared_resource_contract'],
        'limits':n.LIMITS,'budget_allocation':n.BUDGET_ALLOCATION,'phase_authorization':plan['phase_authorization'],
        'physical_gpu':3,'max_owned_GPU_workers':1,'gpu_mapping':runtime['gpu_mapping'],'episode_keys':keys,'stage':stage,
        'checkpoint_release':plan['n4_cohort']['checkpoint_release'] if stage=='remaining9' else None}
    p=Path(plan['artifact_root'])/'release.json';p.write_text(json.dumps(value))
    return path,{'path':str(p),'sha256':r.digest(p)},value


def test_exact_candidate_only_consumer_and_explicit_control_default():
    old=baseline();saved=copy.deepcopy(old);active=r.expand_candidate('N4',candidate(),old['profiles']['Q0'])
    assert old==saved and active['restored_profile']=={**old['profiles']['Q0']['restored_profile'],'qd_final_selection_mode':'terminal_population_v1'}
    observed=n.observed_profiles(old,r.digest(ROOT/'configs/qd_ed_final/baseline_profiles.json'))
    assert all(p['resolved_eds_config']['qd_final_selection_mode']=='archive_global_best' for p in observed['profiles'].values())
    for field,value in [('qd_quality_mode','executed_feedback_v1'),('population_size',32),('reward_mode','other')]:
        changed=candidate();changed['profile'][field]=value
        with pytest.raises(r.GateError,match='only qd_final_selection_mode'):r.expand_candidate('N4',changed,old['profiles']['Q0'])
    with pytest.raises(r.GateError,match='N4 contract requires N4'):r.expand_candidate('N3',candidate(),old['profiles']['Q0'])


def test_exact_twelve_six_plus_six_and_three_documents(fixture):
    root,plan,manifest,runtime,seeds,*_=fixture;n.validate_contract(plan,manifest,runtime,seeds,root,r)
    assert [(x['task_id'],x['profile']) for x in plan['episodes']]==[(t,p) for t in n.TASKS for p in ('C0','Q0','N4')]
    assert Counter(x['budget_bucket'] for x in plan['episodes'])=={'baseline':6,'development':6}
    for field,value in [('budget_bucket','development'),('env_seed',999),('task_id',5)]:
        changed=copy.deepcopy(plan);changed['episodes'][0][field]=value
        with pytest.raises(r.GateError,match='12 cells'):n.validate_contract(changed,manifest,runtime,seeds,root,r)
    changed=copy.deepcopy(plan);changed['phase_authorization']['formal']=True
    with pytest.raises(r.GateError,match='Dev-only'):n.validate_contract(changed,manifest,runtime,seeds,root,r)
    changed=copy.deepcopy(plan);changed['code_files']=[x for x in changed['code_files'] if x['path']!='core/qd_terminal_population.py']
    with pytest.raises(r.GateError,match='fingerprints'):n.validate_contract(changed,manifest,runtime,seeds,root,r)


def test_first3_valid_failures_and_zero_action_difference_do_not_stop_after_correctness(fixture):
    root,plan,_,runtime,_,resources,attest=fixture;journal=[]
    for i,row in enumerate(plan['episodes'][:3]):
        n.admission(plan,runtime,row,journal,resources,root,r);journal+=events(plan,runtime,row,str(i))
    with pytest.raises(r.GateError,match='not released'):n.admission(plan,runtime,plan['episodes'][3],journal,resources,root,r)
    plan['n4_cohort']['checkpoint_release']=attest('qd-ed-n4-checkpoint-v1',checks=dict.fromkeys(n.CHECKS,True),attempt_ids=['0','1','2'])
    n.admission(plan,runtime,plan['episodes'][3],journal,resources,root,r)
    saved=copy.deepcopy(journal);journal[2]['outcome_valid']=False
    with pytest.raises(r.GateError,match='prior valid'):n.admission(plan,runtime,plan['episodes'][3],journal,resources,root,r)
    assert saved[-1]['success'] is False


@pytest.mark.parametrize('mutation',[
    lambda p:p['n4_cohort']['prerequisite_review'].update(sha256='changed'),
    lambda p:p['n4_cohort']['shared_resource_contract'].update(sha256='changed'),
    lambda p:p['n4_cohort']['shared_resource_pointer'].update(sha256='changed'),
    lambda p:p['n4_cohort']['budget_allocation']['baseline_cells'].pop(),
    lambda p:p['n4_cohort']['limits'].update(episode_dispatches=17),
])
def test_authority_allocation_and_bounds_fail_closed(fixture,mutation):
    root,plan,manifest,runtime,seeds,*_=fixture;before=n.binding(plan,runtime);mutation(plan)
    assert n.binding(plan,runtime)!=before
    with pytest.raises(r.GateError):n.validate_contract(plan,manifest,runtime,seeds,root,r)


def test_separate_exact_release_preserves_resource_pointer_false(fixture):
    root,plan,_,runtime,*_=fixture;keys=[x['episode_key'] for x in plan['episodes'][:3]]
    path,ref,value=release(fixture,keys)
    assert n.execution_release(ref,path,plan,runtime,keys,root,r)==value
    assert r.read_json(root/n.RESOURCE_POINTER)['online_dispatch_authorized'] is False
    for field,new in [('physical_gpu',2),('stage','remaining9'),('source_commit','drift'),('status','pending')]:
        changed=copy.deepcopy(value);changed[field]=new;Path(ref['path']).write_text(json.dumps(changed));changed_ref={**ref,'sha256':r.digest(ref['path'])}
        with pytest.raises(r.GateError):n.execution_release(changed_ref,path,plan,runtime,keys,root,r)
    Path(ref['path']).write_text(json.dumps(value))
    with pytest.raises(r.GateError,match='scope'):n.execution_release(ref,path,plan,runtime,[plan['episodes'][3]['episode_key']],root,r)


def test_budget_original_caps_112_plus12_plus4_and_full_timeout(fixture):
    from test_qd_ed_final_runner import events_for,synced_state
    _,plan,*_=fixture;journal=[]
    for bucket,count in [('baseline',11),('development',94),('recovery',7)]:
        for i in range(count):journal+=events_for(bucket+str(i),bucket=bucket)
    before=copy.deepcopy(journal);caps=copy.deepcopy(r.BUCKETS)
    rows=plan['episodes']+[{**plan['episodes'][i],'budget_bucket':'recovery'} for i in range(4)]
    for i,row in enumerate(rows):
        state=synced_state(journal);state['gpu_pool']=[3];state['budget']['gpu_hour_reservations']={'validation':14.,'formal':10.}
        n.protected_budget(state,journal,[],row,r.check_budget(state,journal,row,physical_gpu=3),r)
        journal+=events_for('new'+str(i),bucket=row['budget_bucket'])
    snap=r.budget_snapshot(journal)
    assert snap['dispatched']==128 and snap['by_bucket']=={'baseline':17,'development':100,'recovery':11,'validation':0,'formal':0}
    assert journal[:len(before)]==before and caps==r.BUCKETS
    with pytest.raises(r.GateError,match='1800'):n.protected_budget(state,journal,[],rows[0],1799,r)
    state['budget']['reserved']={'baseline':11,'development':122,'validation':60,'formal':40,'recovery':7}
    with pytest.raises(r.GateError,match='caps'):n.protected_budget(state,journal,[],rows[0],1800,r)


def test_reused_health_not_recharged_new_health_and_unknown_fault_stop(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    n.admission(plan,runtime,row,[],resources,root,r)
    plan['n4_cohort']['health_resources'][0]['scope']='new_n4'
    with pytest.raises(r.GateError,match='8.5-hour'):n.admission(plan,runtime,row,[],resources,root,r)
    plan['n4_cohort']['health_resources'][0]['scope']='reused_prior'
    journal=events(plan,runtime,row,terminal='aborted',valid=False)
    retry={**row,'episode_key':'r1','retry_of':'a','budget_bucket':'recovery','n4_recovery_contract':n.binding(plan,runtime)}
    r.check_retry(journal,retry)
    for updates in [{'outcome_valid':True},{'reason':'GPU3 owned process Xid'},{'reason':'TimeoutExpired'},
                    {'reason':'GPU3 identity drift'},{'reason':'nonfinite action'}]:
        changed=copy.deepcopy(journal);changed[-1].update(updates)
        with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(changed,retry)
    journal+=events(plan,runtime,retry,'second',retry_of='a',terminal='aborted',valid=False)
    with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(journal,retry)


def test_exact_transport_preserves_original_terminal(fixture):
    _,plan,_,runtime,*_=fixture;row=plan['episodes'][0]
    outcome={'outcome_valid':False,'compute_outcome':'completed','required_cost_telemetry_complete':True,
        'stage_backend':'codex_cli','provider_failed_calls':1,'stage_failed_queries':1,'reason':n.TRANSPORT_GATE,
        'failure_class':'task_failure','task_failure':True,'retryable_infrastructure':False}
    saved=copy.deepcopy(outcome);eligible=n.transport_recovery_eligibility(r.GateError(n.TRANSPORT_GATE),outcome,plan,row,runtime,r)
    assert outcome==saved
    journal=events(plan,runtime,row,valid=False);journal[-1].update(outcome,n4_recovery_eligibility=eligible)
    retry={**row,'episode_key':'r1','retry_of':'a','budget_bucket':'recovery','n4_recovery_contract':n.binding(plan,runtime)}
    r.check_retry(journal,retry)
    assert n.transport_recovery_eligibility(r.GateError('prefix '+n.TRANSPORT_GATE),outcome,plan,row,runtime,r) is None
    assert n.transport_recovery_eligibility(r.GateError(n.TRANSPORT_GATE),outcome,{},row,runtime,r) is None


def test_multiple_predispatch_records_cannot_replace_dispatched_predecessor(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0];journal=[]
    for i in range(3):journal += [e for e in events(plan,runtime,row,'pre'+str(i),terminal='aborted',valid=False,seconds=0) if e['event']!='dispatched']
    n.admission(plan,runtime,row,journal,resources,root,r)
    journal+=events(plan,runtime,row,'real',terminal='aborted',valid=False)
    retry={**row,'episode_key':'r1','retry_of':'real','budget_bucket':'recovery','n4_recovery_contract':n.binding(plan,runtime)}
    n.admission(plan,runtime,retry,journal,resources,root,r)
    assert len(journal)==9


def test_current_whole_matrix_capacity_checked_before_any_row(fixture):
    from test_qd_ed_final_runner import events_for,synced_state
    _,plan,*_=fixture;journal=[]
    for bucket,count in [('baseline',11),('development',95),('recovery',7)]:
        for i in range(count):journal+=events_for(bucket+str(i),bucket=bucket)
    state=synced_state(journal);state['gpu_pool']=[3];state['budget']['gpu_hour_reservations']={'validation':14.,'formal':10.}
    row=plan['episodes'][0]
    assert r.check_budget(state,journal,row,physical_gpu=3)==1800
    with pytest.raises(r.GateError,match='whole-cohort bucket capacity'):
        n.protected_budget(state,journal,[],row,1800,r,plan=plan)


def test_later_release_requires_matching_reviewed_correctness(fixture):
    root,plan,_,runtime,_,_,attest=fixture;keys=[x['episode_key'] for x in plan['episodes'][3:]]
    path,ref,_=release(fixture,keys,'remaining9')
    with pytest.raises(r.GateError,match='bound correctness'):n.execution_release(ref,path,plan,runtime,keys,root,r)
    plan['n4_cohort']['checkpoint_release']=attest('qd-ed-n4-checkpoint-v1',checks=dict.fromkeys(n.CHECKS,True),attempt_ids=['a','b','c'])
    path,ref,_=release(fixture,keys,'remaining9')
    n.execution_release(ref,path,plan,runtime,keys,root,r)
    plan['n4_cohort']['checkpoint_release']=attest('qd-ed-n4-checkpoint-v1',checks={**dict.fromkeys(n.CHECKS,True),'unexpected':True})
    path,ref,_=release(fixture,keys,'remaining9')
    with pytest.raises(r.GateError,match='checkpoint failed'):n.execution_release(ref,path,plan,runtime,keys,root,r)
