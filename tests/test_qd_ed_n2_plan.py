"""CPU-only N2 contract gates; no model/provider, GPU, real state or journal writes."""
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


r=load('n2_test_runner',ROOT/'scripts/qd_ed_final_runner.py')
n=load('n2_test_contract',ROOT/'scripts/qd_ed_n2_plan.py')


def baseline(): return r.read_json(ROOT/'configs/qd_ed_final/baseline_profiles.json')
def candidate(): return r.read_json(ROOT/n.PROFILE)


def test_closed_N2_delta_leaves_both_original_controls_unchanged():
    base=baseline(); original=copy.deepcopy(base)
    active=r.expand_candidate('N2',candidate(),base['profiles']['Q0'])
    assert base==original
    assert active['restored_profile']=={**base['profiles']['Q0']['restored_profile'],'qd_quality_mode':'executed_prefix_v1'}
    assert active['resolved_eds_config']['qd_quality_mode']=='executed_prefix_v1'
    assert 'qd_quality_mode' not in base['profiles']['Q0']['resolved_eds_config']
    old=candidate();old['profile']['population_size']=32
    with pytest.raises(r.GateError,match='only qd_quality_mode'):r.expand_candidate('N2',old,base['profiles']['Q0'])
    old=candidate();old['profile']['qd_quality_mode']='anything_else'
    with pytest.raises(r.GateError,match='only qd_quality_mode'):r.expand_candidate('N2',old,base['profiles']['Q0'])
    old=candidate();old['algorithm_contract']='future_arbitrary_delta'
    with pytest.raises(r.GateError,match='unknown candidate'):r.expand_candidate('N2',old,base['profiles']['Q0'])


@pytest.fixture
def fixture(tmp_path):
    root=tmp_path/'worktree';root.mkdir();artifacts=tmp_path/'artifacts';artifacts.mkdir()
    for relative in n.REQUIRED|{'configs/qd_ed_final/baseline_profiles.json'}:
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic source\n')
    bp=root/'configs/qd_ed_final/baseline_profiles.json';bp.write_text(json.dumps(baseline()))
    c=candidate();c['baseline_provenance']['sha256']=r.digest(bp)
    (root/n.PROFILE).write_text(json.dumps(c))
    observed=n.observed_profiles(baseline(),r.digest(bp));(root/n.OBSERVED).write_text(json.dumps(observed))
    manifest=copy.deepcopy(observed);manifest['profiles']['N2']=r.expand_candidate('N2',c,manifest['profiles']['Q0'])
    seeds={'blocks':{'dev':[{'task_id':task,'env_seed':task+100,'policy_seed':task+100,'init_index':0,
             'init_row_sha256':'row'+str(task),'init_file_sha256':'init'+str(task),'bddl_sha256':'bddl'+str(task)} for task in range(10)]}}
    runtime={'gpu_mapping':{'physical_gpu':3,'uuid':'GPU-test','egl_device_index':0},
             'frozen_stage_provider':{'backend':'codex_cli','public_config_sha256':'transport'},
             'cuda_egl_probe':{'resource_id':'prior-proof'}}
    records=[{'path':relative,'sha256':r.digest(root/relative)} for relative in n.REQUIRED|{'configs/qd_ed_final/baseline_profiles.json'}]
    plan={'artifact_root':str(artifacts),'boot_id':n.BOOT,'source_commit':'same-source','profiles_path':str(root/n.OBSERVED),
          'profiles_sha256':r.digest(root/n.OBSERVED),'runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory',
          'seed_plan_sha256':'seedtable','code_files':records,'episodes':n.rows_from_dev(seeds),
          'phase_authorization':{'dev':True,'validation':False,'formal':False},
          'candidate_profiles':{'N2':{'path':str(root/n.PROFILE),'sha256':r.digest(root/n.PROFILE)}},
          'n2_cohort':{'schema':'qd-ed-n2-cohort-v1','cohort_id':n.COHORT,'limits':copy.deepcopy(n.LIMITS),
              'protocol':{'path':n.PROTOCOL,'sha256':r.digest(root/n.PROTOCOL)},
              'accounting_clarification':{'path':n.CLARIFICATION,'sha256':r.digest(root/n.CLARIFICATION)},
              'health_resources':[{'resource_id':'prior-proof','scope':'reused_prior'}],
              'recorded_candidate_review':None,'checkpoint_release':None,
              'runtime_prerequisites':{'boot_id':n.BOOT,'reuse_scope':'prior_engineering_only_not_N2_algorithm_validation',
                 'references':{key:{} for key in n.PREREQUISITES},
                 'native_dependencies':{'path':n.DEPENDENCIES,'sha256':r.digest(root/n.DEPENDENCIES)}}}}
    evidence=artifacts/'evidence.json';evidence.write_text('{}\n')
    def attest(schema,**values):
        value={'schema':schema,'cohort_id':n.COHORT,'source_commit':plan['source_commit'],
            'protocol_sha256':plan['n2_cohort']['protocol']['sha256'],
            'evidence':[{'path':str(evidence),'sha256':r.digest(evidence)}],**values}
        path=artifacts/(schema+'.json');path.write_text(json.dumps(value))
        return {'path':str(path),'sha256':r.digest(path)}
    plan['n2_cohort']['recorded_candidate_review']=attest('qd-ed-n2-recorded-check-v1',passed=True,changed_recorded_choice=True)
    resources=[{'resource_id':'prior-proof','event':'completed','gpu_process_wall_seconds':99999.}]
    return root,plan,manifest,runtime,seeds,resources,attest


def events(plan,runtime,row,attempt='a',*,terminal='valid',valid=True,seconds=1.,retry_of=None):
    output=Path(plan['artifact_root'])/attempt
    (output/'eds_eval').mkdir(parents=True,exist_ok=True)
    (output/'eds_eval/decision-evidence-audit.json').write_text(json.dumps({'accepted':True,'evidence_complete':True}))
    base={'attempt_id':attempt,'output_dir':str(output),'identity':r.episode_identity(row),'budget_bucket':row['budget_bucket'],
          'retry_of':retry_of,'n2_cohort_id':n.COHORT,'n2_frozen_identity':n.binding(plan,runtime)}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},
            {**base,'event':terminal,'outcome_valid':valid,'success':False,'gpu_process_wall_seconds':seconds,
             'retryable_infrastructure':terminal=='aborted'}]


def test_exact_30_rows_common_observer_and_protocol_freeze(fixture):
    root,plan,manifest,runtime,seeds,_,_=fixture
    n.validate_contract(plan,manifest,runtime,seeds,root,r)
    assert [(x['task_id'],x['profile']) for x in plan['episodes']]==[(t,p) for t in range(10) for p in ('C0','Q0','N2')]
    assert all(x['timeout_seconds']==1800 and x['budget_bucket']=='development' for x in plan['episodes'])
    assert all(manifest['profiles'][p]['static_override_values']['main.decision_evidence.enabled'] is True for p in ('C0','Q0','N2'))
    for mutation,message in [(lambda p:p['episodes'].reverse(),'30 cells'),
        (lambda p:p['episodes'][0].update(env_seed=999),'30 cells'),
        (lambda p:p['phase_authorization'].update(validation=True),'Dev-only'),
        (lambda p:p['n2_cohort']['limits'].update(recoveries=5),'limits')]:
        changed=copy.deepcopy(plan);mutation(changed)
        with pytest.raises(r.GateError,match=message):n.validate_contract(changed,manifest,runtime,seeds,root,r)


def test_fixed_order_and_checkpoint_ignore_success_but_require_valid_and_activation(fixture):
    root,plan,_,runtime,_,resources,attest=fixture
    rows=plan['episodes'];journal=[]
    for i in range(3):
        n.admission(plan,runtime,rows[i],journal,resources,root,r)
        journal+=events(plan,runtime,rows[i],str(i))  # All valid task failures: allowed.
    with pytest.raises(r.GateError,match='not released'):n.admission(plan,runtime,rows[3],journal,resources,root,r)
    plan['n2_cohort']['checkpoint_release']=attest('qd-ed-n2-checkpoint-v1',checks={k:True for k in n.CHECKS},attempt_ids=['0','1','2'])
    n.admission(plan,runtime,rows[3],journal,resources,root,r)
    changed=copy.deepcopy(journal);changed[2]['outcome_valid']=False
    with pytest.raises(r.GateError,match='prior valid'):n.admission(plan,runtime,rows[3],changed,resources,root,r)
    plan['n2_cohort']['checkpoint_release']=attest('qd-ed-n2-checkpoint-v1',checks={k:k!='substantive_qd_activation' for k in n.CHECKS},attempt_ids=['0','1','2'])
    with pytest.raises(r.GateError,match='checkpoint'):n.admission(plan,runtime,rows[3],journal,resources,root,r)


def test_bounded_recorded_choice_required_before_first_dispatch(fixture):
    root,plan,_,runtime,_,resources,attest=fixture
    plan['n2_cohort']['recorded_candidate_review']=attest('qd-ed-n2-recorded-check-v1',passed=True,changed_recorded_choice=False)
    with pytest.raises(r.GateError,match='mechanism prerequisite'):n.admission(plan,runtime,plan['episodes'][0],[],resources,root,r)


def test_local_18h_new_resources_and_34_dispatches_fail_closed(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    n.admission(plan,runtime,row,[],resources,root,r)  # Prior proof cost is not recharged.
    plan['n2_cohort']['health_resources'][0]['scope']='new_n2'
    with pytest.raises(r.GateError,match='18-hour'):n.admission(plan,runtime,row,[],resources,root,r)
    plan['n2_cohort']['health_resources'][0]['scope']='reused_prior'
    journal=[]
    for i in range(34):journal+=events(plan,runtime,plan['episodes'][i%30],str(i))
    with pytest.raises(r.GateError,match='allowance exhausted'):n.admission(plan,runtime,row,journal,resources,root,r)


def test_once_per_cell_and_four_recoveries_are_hard_limits(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    journal=events(plan,runtime,row,'a',terminal='aborted',valid=False)+events(plan,runtime,row,'b',terminal='aborted',valid=False,retry_of='a')
    retry={**row,'episode_key':'r2','retry_of':'b','budget_bucket':'recovery','n2_recovery_contract':n.binding(plan,runtime)}
    with pytest.raises(r.GateError,match='cell dispatch'):n.admission(plan,runtime,retry,journal,resources,root,r)
    journal=[]
    for i in range(4):journal+=events(plan,runtime,plan['episodes'][i],str(i),retry_of='original'+str(i))
    original=plan['episodes'][4];journal+=events(plan,runtime,original,'last',terminal='aborted',valid=False)
    retry={**original,'episode_key':'retry','retry_of':'last','budget_bucket':'recovery','n2_recovery_contract':n.binding(plan,runtime)}
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
    journal[-1].update(outcome,n2_recovery_eligibility=eligible)
    retry={**row,'episode_key':'retry','retry_of':'a','budget_bucket':'recovery','n2_recovery_contract':n.binding(plan,runtime)}
    r.check_retry(journal,retry)
    for field,value in [('outcome_valid',True),('reason','other failure '+n.TRANSPORT_GATE),('compute_outcome','execution_error')]:
        changed=copy.deepcopy(journal);changed[-1][field]=value
        with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(changed,retry)
    changed=copy.deepcopy(journal)
    for event in changed:event.pop('n2_cohort_id',None);event.pop('n2_frozen_identity',None)
    with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(changed,retry)
    drift=copy.deepcopy(retry);drift['n2_recovery_contract']['source_commit']='changed'
    with pytest.raises(r.GateError,match='cannot be retried'):r.check_retry(journal,drift)
    assert n.transport_recovery_eligibility(r.GateError('prefix '+n.TRANSPORT_GATE),outcome,plan,row,runtime,r) is None
    assert n.transport_recovery_eligibility(TimeoutError(),outcome,plan,row,runtime,r) is None
    assert n.transport_recovery_eligibility(r.GateError(n.TRANSPORT_GATE),outcome,{},row,runtime,r) is None


def test_no_second_recovery_and_full_identity_needed_for_infrastructure_abort(fixture):
    root,plan,_,runtime,_,resources,_=fixture;row=plan['episodes'][0]
    journal=events(plan,runtime,row,terminal='aborted',valid=False)
    retry={**row,'episode_key':'r1','retry_of':'a','budget_bucket':'recovery','n2_recovery_contract':n.binding(plan,runtime)}
    r.check_retry(journal,retry);n.admission(plan,runtime,retry,journal,resources,root,r)
    drift=copy.deepcopy(journal);drift[0]['n2_frozen_identity']['runtime_manifest_sha256']='changed'
    with pytest.raises(r.GateError,match='frozen identity'):n.admission(plan,runtime,retry,drift,resources,root,r)


def test_new_declared_dependency_cannot_be_missing_from_source_freeze(fixture):
    root,plan,manifest,runtime,seeds,_,_=fixture
    plan['code_files']=[x for x in plan['code_files'] if x['path']!='core/qd_executed_quality.py']
    with pytest.raises(r.GateError,match='source fingerprints'):n.validate_contract(plan,manifest,runtime,seeds,root,r)
