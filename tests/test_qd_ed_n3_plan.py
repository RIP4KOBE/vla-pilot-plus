"""CPU-only N3 contract gates; no model/provider, GPU, real state or journal writes."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


r=load('n3_test_runner',ROOT/'scripts/qd_ed_final_runner.py')
n=load('n3_test_contract',ROOT/'scripts/qd_ed_n3_plan.py')


def baseline(): return r.read_json(ROOT/'configs/qd_ed_final/baseline_profiles.json')
def candidate(): return r.read_json(ROOT/n.PROFILE)


def test_closed_N3_delta_leaves_both_original_controls_unchanged():
    base=baseline(); original=copy.deepcopy(base)
    active=r.expand_candidate('N3',candidate(),base['profiles']['Q0'])
    assert base==original
    assert active['restored_profile']=={**base['profiles']['Q0']['restored_profile'],'qd_quality_mode':'executed_feedback_v1'}
    assert active['resolved_eds_config']['qd_quality_mode']=='executed_feedback_v1'
    assert 'qd_quality_mode' not in base['profiles']['Q0']['resolved_eds_config']
    old=candidate();old['profile']['population_size']=32
    with pytest.raises(r.GateError,match='only qd_quality_mode'):r.expand_candidate('N3',old,base['profiles']['Q0'])
    old=candidate();old['profile']['qd_quality_mode']='anything_else'
    with pytest.raises(r.GateError,match='only qd_quality_mode'):r.expand_candidate('N3',old,base['profiles']['Q0'])
    old=candidate();old['algorithm_contract']='future_arbitrary_delta'
    with pytest.raises(r.GateError,match='unknown candidate'):r.expand_candidate('N3',old,base['profiles']['Q0'])


@pytest.fixture
def fixture(tmp_path):
    root=tmp_path/'worktree';root.mkdir();artifacts=tmp_path/'artifacts';artifacts.mkdir()
    for relative in n.REQUIRED|{'configs/qd_ed_final/baseline_profiles.json'}:
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic source\n')
    bp=root/'configs/qd_ed_final/baseline_profiles.json';bp.write_text(json.dumps(baseline()))
    c=candidate();c['baseline_provenance']['sha256']=r.digest(bp)
    (root/n.PROFILE).write_text(json.dumps(c))
    observed=n.observed_profiles(baseline(),r.digest(bp));(root/n.OBSERVED).write_text(json.dumps(observed))
    manifest=copy.deepcopy(observed);manifest['profiles']['N3']=r.expand_candidate('N3',c,manifest['profiles']['Q0'])
    seeds={'blocks':{'dev':[{'task_id':task,'env_seed':task+100,'policy_seed':task+100,'init_index':0,
             'init_row_sha256':'row'+str(task),'init_file_sha256':'init'+str(task),'bddl_sha256':'bddl'+str(task)} for task in range(10)]}}
    runtime={'gpu_mapping':{'physical_gpu':3,'uuid':'GPU-test','egl_device_index':0},
             'frozen_stage_provider':{'backend':'codex_cli','public_config_sha256':'transport'},
             'cuda_egl_probe':{'resource_id':'prior-proof'}}
    records=[{'path':relative,'sha256':r.digest(root/relative)} for relative in n.REQUIRED|{'configs/qd_ed_final/baseline_profiles.json'}]
    plan={'worktree':str(root),'artifact_root':str(artifacts),'boot_id':n.BOOT,'source_commit':'same-source','profiles_path':str(root/n.OBSERVED),
          'profiles_sha256':r.digest(root/n.OBSERVED),'runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory',
          'seed_plan_sha256':'seedtable','code_files':records,'episodes':n.rows_from_dev(seeds),
          'phase_authorization':{'dev':True,'validation':False,'formal':False},
          'candidate_profiles':{'N3':{'path':str(root/n.PROFILE),'sha256':r.digest(root/n.PROFILE)}},
          'n3_cohort':{'schema':'qd-ed-n3-cohort-v1','cohort_id':n.COHORT,'limits':copy.deepcopy(n.LIMITS),
              'protocol':{'path':n.PROTOCOL,'sha256':r.digest(root/n.PROTOCOL)},
              'accounting_clarification':{'path':n.CLARIFICATION,'sha256':r.digest(root/n.CLARIFICATION)},
              'budget_allocation':copy.deepcopy(n.BUDGET_ALLOCATION),
              'budget_allocation_amendment':{'path':n.ALLOCATION,'sha256':r.digest(root/n.ALLOCATION)},
              'health_resources':[{'resource_id':'prior-proof','scope':'reused_prior'}],
              'recorded_candidate_review':None,'checkpoint_release':None,
              'runtime_prerequisites':{'boot_id':n.BOOT,'reuse_scope':'prior_engineering_only_not_N3_algorithm_validation',
                 'references':{key:{} for key in n.PREREQUISITES},
                 'native_dependencies':{'path':n.DEPENDENCIES,'sha256':r.digest(root/n.DEPENDENCIES)}}}}
    evidence=artifacts/'evidence.json';evidence.write_text('{}\n')
    def attest(schema,**values):
        value={'schema':schema,'cohort_id':n.COHORT,'source_commit':plan['source_commit'],
            'protocol_sha256':plan['n3_cohort']['protocol']['sha256'],'source_files_sha256':n.source_identity(plan),
            'evidence':[{'path':str(evidence),'sha256':r.digest(evidence)}],
            'scope':'conditional_recorded_final_pool_only','historical_tracking_validity':'Unknown',
            'runtime_tracking_validity':'known_valid',**values}
        path=artifacts/(schema+'.json');path.write_text(json.dumps(value))
        return {'path':str(path),'sha256':r.digest(path)}
    plan['n3_cohort']['recorded_candidate_review']=attest('qd-ed-n3-recorded-check-v1',passed=True,changed_recorded_choice=True)
    resources=[{'resource_id':'prior-proof','event':'completed','gpu_process_wall_seconds':99999.}]
    return root,plan,manifest,runtime,seeds,resources,attest


def native_audit(checked=2,active=1):
    return {'accepted':True,'evidence_complete':True,'n3_feedback_audit':{
        'schema':'n3-native-feedback-audit-v1','scope':n.NATIVE_AUDIT_SCOPE,
        'checked_decisions':checked,'active_previous_ack_verified':active,'inactive_decisions':checked-active,
        'uncommitted_clears':0,'inactive_ack_clears_unknown':0,'complete_nonterminal_prefixes':checked}}


def events(plan,runtime,row,attempt='a',*,terminal='valid',valid=True,seconds=1.,retry_of=None):
    output=Path(plan['artifact_root'])/attempt
    (output/'eds_eval').mkdir(parents=True,exist_ok=True)
    audit=native_audit(1,1) if row['profile']=='N3' else {'accepted':True,'evidence_complete':True}
    (output/'eds_eval/decision-evidence-audit.json').write_text(json.dumps(audit))
    if row['profile']=='N3':
        metric={'qd_quality_mode':'executed_feedback_v1','qd_quality_applicable':True,'qd_feedback_active':True}
        (output/'eds_eval/eds_metrics.jsonl').write_text(json.dumps(metric)+'\n')
    base={'attempt_id':attempt,'output_dir':str(output),'identity':r.episode_identity(row),'budget_bucket':row['budget_bucket'],
          'retry_of':retry_of,'n3_cohort_id':n.COHORT,'n3_frozen_identity':n.binding(plan,runtime),'metric_chunks':1}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},
            {**base,'event':terminal,'outcome_valid':valid,'success':False,'gpu_process_wall_seconds':seconds,
             'retryable_infrastructure':terminal=='aborted',
             'reason':'external GPU3 process appeared during owned attempt' if terminal=='aborted' else None}]


def test_exact_30_rows_common_observer_and_protocol_freeze(fixture):
    root,plan,manifest,runtime,seeds,_,_=fixture
    n.validate_contract(plan,manifest,runtime,seeds,root,r)
    assert [(x['task_id'],x['profile']) for x in plan['episodes']]==[(t,p) for t in range(10) for p in ('C0','Q0','N3')]
    assert all(x['timeout_seconds']==1800 and x['budget_bucket']==n.BUDGET_ALLOCATION['original_by_profile'][x['profile']] for x in plan['episodes'])
    assert all(manifest['profiles'][p]['static_override_values']['main.decision_evidence.enabled'] is True for p in ('C0','Q0','N3'))
    for mutation,message in [(lambda p:p['episodes'].reverse(),'30 cells'),
        (lambda p:p['episodes'][0].update(env_seed=999),'30 cells'),
        (lambda p:p['phase_authorization'].update(validation=True),'Dev-only'),
        (lambda p:p['n3_cohort']['limits'].update(recoveries=5),'limits')]:
        changed=copy.deepcopy(plan);mutation(changed)
        with pytest.raises(r.GateError,match=message):n.validate_contract(changed,manifest,runtime,seeds,root,r)


def test_fixed_order_and_checkpoint_ignore_success_but_require_valid_and_activation(fixture):
    root,plan,_,runtime,_,resources,attest=fixture
    rows=plan['episodes'];journal=[]
    for i in range(3):
        n.admission(plan,runtime,rows[i],journal,resources,root,r)
        journal+=events(plan,runtime,rows[i],str(i))  # All valid task failures: allowed.
    with pytest.raises(r.GateError,match='not released'):n.admission(plan,runtime,rows[3],journal,resources,root,r)
    plan['n3_cohort']['checkpoint_release']=attest('qd-ed-n3-checkpoint-v1',checks={k:True for k in n.CHECKS},attempt_ids=['0','1','2'])
    n.admission(plan,runtime,rows[3],journal,resources,root,r)
    changed=copy.deepcopy(journal);changed[2]['outcome_valid']=False
    with pytest.raises(r.GateError,match='prior valid'):n.admission(plan,runtime,rows[3],changed,resources,root,r)
    plan['n3_cohort']['checkpoint_release']=attest('qd-ed-n3-checkpoint-v1',checks={k:k!='substantive_qd_activation' for k in n.CHECKS},attempt_ids=['0','1','2'])
    with pytest.raises(r.GateError,match='checkpoint'):n.admission(plan,runtime,rows[3],journal,resources,root,r)


def test_prospective_arm_mapping_preserves_science_and_binds_amendment(fixture):
    root,plan,manifest,runtime,seeds,*_=fixture
    from collections import Counter
    assert Counter(x['budget_bucket'] for x in plan['episodes'])=={'baseline':10,'development':20}
    for row in plan['episodes']:
        legacy={**row,'budget_bucket':'development'}
        assert r.episode_identity(row)==r.episode_identity(legacy)
    saved=n.binding(plan,runtime)
    drift=copy.deepcopy(plan);drift['n3_cohort']['budget_allocation']['original_by_profile']['Q0']='baseline'
    assert n.binding(drift,runtime)!=saved
    with pytest.raises(r.GateError,match='budget allocation differs'):
        n.validate_contract(drift,manifest,runtime,seeds,root,r)
    drift=copy.deepcopy(plan);drift['episodes'][0]['budget_bucket']='development'
    with pytest.raises(r.GateError,match='original 30 cells'):
        n.validate_contract(drift,manifest,runtime,seeds,root,r)
    drift=copy.deepcopy(plan);drift['n3_cohort']['budget_allocation_amendment']['sha256']='drift'
    assert n.binding(drift,runtime)!=saved
    with pytest.raises(r.GateError,match='clarification differs'):
        n.validate_contract(drift,manifest,runtime,seeds,root,r)


def test_actual_budget_checker_accepts_30_and_four_recoveries_without_changing_caps_or_history(fixture):
    from test_qd_ed_final_runner import events_for, synced_state
    _,plan,*_=fixture
    journal=[]
    for bucket,count in [('baseline',1),('development',72),('recovery',6)]:
        for i in range(count):journal+=events_for(bucket+str(i),bucket=bucket)
    original=copy.deepcopy(journal);caps=copy.deepcopy(r.BUCKETS)
    rows=copy.deepcopy(plan['episodes'])+[{**plan['episodes'][i],'budget_bucket':'recovery'} for i in range(4)]
    for i,row in enumerate(rows):
        state=synced_state(journal);state['gpu_pool']=[3];before=copy.deepcopy(state)
        timeout=r.check_budget(state,journal,row,physical_gpu=3)
        n.protected_budget(state,journal,[],row,timeout,r)
        assert timeout==1800 and state==before
        journal+=events_for('new'+str(i),bucket=row['budget_bucket'],identity=r.episode_identity(row))
    snap=r.budget_snapshot(journal)
    assert snap['dispatched']==113 and snap['by_bucket']=={'baseline':11,'development':92,'recovery':10,'validation':0,'formal':0}
    assert journal[:len(original)]==original and r.BUCKETS==caps
    exhausted=journal+sum((events_for('more'+str(i),bucket='development') for i in range(8)),[])
    state=synced_state(exhausted);state['gpu_pool']=[3]
    with pytest.raises(r.GateError,match='development reserve exhausted'):
        r.check_budget(state,exhausted,plan['episodes'][1],physical_gpu=3)



@pytest.mark.parametrize('kind',['missing','unrecognized','no_history'])
def test_accepted_generic_audit_or_no_actual_feedback_cannot_release_checkpoint(fixture,kind):
    root,plan,_,runtime,_,resources,attest=fixture;rows=plan['episodes'];journal=[]
    for i in range(3):journal+=events(plan,runtime,rows[i],str(i))
    plan['n3_cohort']['checkpoint_release']=attest('qd-ed-n3-checkpoint-v1',checks={k:True for k in n.CHECKS},attempt_ids=['0','1','2'])
    output=Path(journal[-1]['output_dir'])/'eds_eval'
    if kind=='missing':
        audit={'accepted':True,'evidence_complete':True}
    else:
        recognized=kind=='no_history'
        metric={'qd_quality_mode':'executed_feedback_v1','qd_quality_applicable':recognized,'qd_feedback_active':False}
        (output/'eds_metrics.jsonl').write_text(json.dumps(metric)+'\n')
        audit=native_audit(1,0) if recognized else {'accepted':True,'evidence_complete':True}
    r.durable_json(output/'decision-evidence-audit.json',audit)
    with pytest.raises(r.GateError,match='native feedback audit|lacks actual native-audited'):
        n.admission(plan,runtime,rows[3],journal,resources,root,r)


def test_bounded_recorded_choice_required_before_first_dispatch(fixture):
    root,plan,_,runtime,_,resources,attest=fixture
    plan['n3_cohort']['recorded_candidate_review']=attest('qd-ed-n3-recorded-check-v1',passed=True,changed_recorded_choice=False)
    with pytest.raises(r.GateError,match='mechanism prerequisite'):n.admission(plan,runtime,plan['episodes'][0],[],resources,root,r)


def test_local_8h_new_resources_and_34_dispatches_fail_closed(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    n.admission(plan,runtime,row,[],resources,root,r)  # Prior proof cost is not recharged.
    plan['n3_cohort']['health_resources'][0]['scope']='new_n3'
    with pytest.raises(r.GateError,match='8-hour'):n.admission(plan,runtime,row,[],resources,root,r)
    plan['n3_cohort']['health_resources'][0]['scope']='reused_prior'
    journal=[]
    for i in range(34):journal+=events(plan,runtime,plan['episodes'][i%30],str(i))
    with pytest.raises(r.GateError,match='cannot be retried|allowance exhausted'):n.admission(plan,runtime,row,journal,resources,root,r)


def test_once_per_cell_and_four_recoveries_are_hard_limits(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    journal=events(plan,runtime,row,'a',terminal='aborted',valid=False)+events(plan,runtime,row,'b',terminal='aborted',valid=False,retry_of='a')
    retry={**row,'episode_key':'r2','retry_of':'b','budget_bucket':'recovery','n3_recovery_contract':n.binding(plan,runtime)}
    with pytest.raises(r.GateError,match='cannot be retried'):n.admission(plan,runtime,retry,journal,resources,root,r)
    journal=[]
    for i in range(4):journal+=events(plan,runtime,plan['episodes'][i],str(i),retry_of='original'+str(i))
    original=plan['episodes'][4];journal+=events(plan,runtime,original,'last',terminal='aborted',valid=False)
    retry={**original,'episode_key':'retry','retry_of':'last','budget_bucket':'recovery','n3_recovery_contract':n.binding(plan,runtime)}
    with pytest.raises(r.GateError,match='recovery allowance'):n.admission(plan,runtime,retry,journal,resources,root,r)


def test_exact_transport_exception_keeps_terminal_and_rejects_old_or_drifted_records(fixture):
    _,plan,_,runtime,_,_,_=fixture;row=plan['episodes'][0]
    outcome={'reason':n.TRANSPORT_GATE,'task_failure':True,'failure_class':'task_failure','outcome_valid':False,
        'compute_outcome':'completed','required_cost_telemetry_complete':True,'stage_backend':'codex_cli',
        'provider_failed_calls':1,'stage_failed_queries':1,'retryable_infrastructure':False}
    original=copy.deepcopy(outcome)
    eligible=n.transport_recovery_eligibility(r.GateError(n.TRANSPORT_GATE),outcome,plan,row,runtime,r)
    assert outcome==original and eligible is not None
    journal=events(plan,runtime,row,valid=False)
    journal[-1].update(outcome,n3_recovery_eligibility=eligible)
    retry={**row,'episode_key':'retry','retry_of':'a','budget_bucket':'recovery','n3_recovery_contract':n.binding(plan,runtime)}
    r.check_retry(journal,retry)
    for field,value in [('outcome_valid',True),('reason','other failure '+n.TRANSPORT_GATE),('compute_outcome','execution_error')]:
        changed=copy.deepcopy(journal);changed[-1][field]=value
        with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(changed,retry)
    changed=copy.deepcopy(journal)
    for event in changed:event.pop('n3_cohort_id',None);event.pop('n3_frozen_identity',None)
    with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(changed,retry)
    drift=copy.deepcopy(retry);drift['n3_recovery_contract']['source_commit']='changed'
    with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(journal,drift)
    assert n.transport_recovery_eligibility(r.GateError('prefix '+n.TRANSPORT_GATE),outcome,plan,row,runtime,r) is None
    assert n.transport_recovery_eligibility(TimeoutError(),outcome,plan,row,runtime,r) is None
    assert n.transport_recovery_eligibility(r.GateError(n.TRANSPORT_GATE),outcome,{},row,runtime,r) is None


def test_no_second_recovery_and_full_identity_needed_for_infrastructure_abort(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    journal=events(plan,runtime,row,terminal='aborted',valid=False)
    retry={**row,'episode_key':'r1','retry_of':'a','budget_bucket':'recovery','n3_recovery_contract':n.binding(plan,runtime)}
    r.check_retry(journal,retry);n.admission(plan,runtime,retry,journal,resources,root,r)
    drift=copy.deepcopy(journal);drift[0]['n3_frozen_identity']['runtime_manifest_sha256']='changed'
    with pytest.raises(r.GateError,match='cannot be retried|frozen identity'):n.admission(plan,runtime,retry,drift,resources,root,r)


def test_new_declared_dependency_cannot_be_missing_from_source_freeze(fixture):
    root,plan,manifest,runtime,seeds,_,_=fixture
    plan['code_files']=[x for x in plan['code_files'] if x['path']!='core/qd_executed_quality.py']
    with pytest.raises(r.GateError,match='source fingerprints'):n.validate_contract(plan,manifest,runtime,seeds,root,r)


@pytest.mark.parametrize('updates',[
    {'reason':'GPU3 source identity changed'},
    {'reason':'GPU3 owned process Xid detected; see sanitized kernel monitor evidence'},
    {'reason':'TimeoutExpired'},
    {'reason':'nonfinite action'},
    {'outcome_valid':True},
    {'reason':'GPU3 nvidia-smi monitor query timed out after 15 seconds'},
])
def test_unknown_native_identity_timeout_or_valid_failure_never_retry(fixture,updates):
    _,plan,_,runtime,_,_,_=fixture
    row=plan['episodes'][0];journal=events(plan,runtime,row,terminal='aborted',valid=False)
    journal[-1].update(updates)
    retry={**row,'episode_key':'r1','retry_of':'a','budget_bucket':'recovery','n3_recovery_contract':n.binding(plan,runtime)}
    with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(journal,retry)


def test_exact_monitor_timeout_retry_remains_raw_infrastructure(fixture):
    _,plan,_,runtime,_,_,_=fixture;row=plan['episodes'][0]
    journal=events(plan,runtime,row,terminal='aborted',valid=False)
    journal[-1].update(reason='GPU3 nvidia-smi monitor query timed out after 15 seconds',
        failure_detail='gpu_monitor_timeout',gpu_monitor_timeout={'physical_gpu':3,'timeout_seconds':15})
    retry={**row,'episode_key':'r1','retry_of':'a','budget_bucket':'recovery','n3_recovery_contract':n.binding(plan,runtime)}
    saved=copy.deepcopy(journal);r.check_retry(journal,retry);assert saved==journal


def test_N2_contract_cannot_be_used_for_N3_and_original_provider_unchanged():
    old=load('original_n2',ROOT/'scripts/qd_ed_n2_plan.py')
    assert old.COHORT!=n.COHORT and old.LIMITS['new_gpu_hours']==18
    with pytest.raises(r.GateError,match='N3 contract requires N3'):
        r.expand_candidate('N2',candidate(),baseline()['profiles']['Q0'])
    n2_profile=r.read_json(ROOT/'configs/qd_ed_final/candidate_n2.json')
    with pytest.raises(r.GateError,match='N2 contract requires N2'):
        r.expand_candidate('N3',n2_profile,baseline()['profiles']['Q0'])


def test_source_drift_breaks_attestation_and_runtime_binding(fixture):
    root,plan,_,runtime,_,resources,_=fixture
    before=n.binding(plan,runtime)
    plan['code_files'][0]['sha256']='changed'
    assert n.binding(plan,runtime)!=before
    with pytest.raises(r.GateError,match='attestation identity'):
        n.admission(plan,runtime,plan['episodes'][0],[],resources,root,r)


def test_historical_witness_does_not_certify_online_tracking(fixture):
    root,plan,_,runtime,_,resources,attest=fixture
    plan['n3_cohort']['recorded_candidate_review']=attest('qd-ed-n3-recorded-check-v1',passed=True,
        quality_dependent_ranking_witness=True,changed_recorded_choice=False)
    n.admission(plan,runtime,plan['episodes'][0],[],resources,root,r)
    journal=sum((events(plan,runtime,row,str(i)) for i,row in enumerate(plan['episodes'][:3])),[])
    plan['n3_cohort']['checkpoint_release']=attest('qd-ed-n3-checkpoint-v1',
        checks=dict.fromkeys(n.CHECKS,True),attempt_ids=['0','1','2'],runtime_tracking_validity='Unknown')
    with pytest.raises(r.GateError,match='checkpoint'):
        n.admission(plan,runtime,plan['episodes'][3],journal,resources,root,r)


def test_global_protected_hours_attempts_and_full_timeout(fixture):
    from test_qd_ed_final_runner import synced_state,events_for
    _,plan,_,_,_,_,_=fixture;row=plan['episodes'][0]
    # Even an explicit generic reallocation cannot silently borrow N3's protected24h.
    journal=events_for('old');journal[-1]['gpu_process_wall_seconds']=24*3600
    state=synced_state(journal);state['gpu_pool']=[3]
    state['budget']['gpu_hour_reservations']={}
    with pytest.raises(r.GateError,match='protected 24'):
        n.protected_budget(state,journal,[],row,1800,r)
    state=synced_state([]);state['gpu_pool']=[3]
    n.protected_budget(state,[],[],row,1800,r)
    with pytest.raises(r.GateError,match='1800\\+40'):n.protected_budget(state,[],[],row,1799,r)
    journal=[]
    for i in range(140):journal+=events_for(str(i))
    state=synced_state(journal);state['gpu_pool']=[3]
    with pytest.raises(r.GateError,match='protected 100'):
        n.protected_budget(state,journal,[],row,1800,r)


def test_contract_rejects_another_gpu_or_cohort(fixture):
    root,plan,manifest,runtime,seeds,*_=fixture
    wrong=copy.deepcopy(runtime);wrong['gpu_mapping']['physical_gpu']=2
    with pytest.raises(r.GateError,match='GPU3'):
        n.validate_contract(plan,manifest,wrong,seeds,root,r)
    mixed=copy.deepcopy(plan);mixed['n2_cohort']={}
    with pytest.raises(r.GateError,match='another cohort'):
        n.validate_contract(mixed,manifest,runtime,seeds,root,r)


def test_resource_cost_attribution_cannot_change_after_first_dispatch(fixture):
    root,plan,_,runtime,_,resources,_=fixture
    journal=events(plan,runtime,plan['episodes'][0])
    plan['n3_cohort']['health_resources'][0]['scope']='new_n3'
    with pytest.raises(r.GateError,match='frozen identity'):
        n.admission(plan,runtime,plan['episodes'][1],journal,resources,root,r)


def test_predispatch_rejections_do_not_consume_original_or_one_retry(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    pre=events(plan,runtime,row,'pre',terminal='aborted',valid=False,seconds=0.)
    pre=[e for e in pre if e['event']!='dispatched']
    r.check_retry(pre,row);n.admission(plan,runtime,row,pre,resources,root,r)
    original=events(plan,runtime,row,'actual',terminal='aborted',valid=False)
    retry={**row,'episode_key':'r1','retry_of':'actual','budget_bucket':'recovery','n3_recovery_contract':n.binding(plan,runtime)}
    rejected=events(plan,runtime,retry,'retry-pre',terminal='aborted',valid=False,seconds=0.,retry_of='actual')
    rejected=[e for e in rejected if e['event']!='dispatched']
    journal=pre+original+rejected
    r.check_retry(journal,retry);n.admission(plan,runtime,retry,journal,resources,root,r)
    journal+=events(plan,runtime,retry,'actual-retry',terminal='aborted',valid=False,retry_of='actual')
    with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(journal,retry)
