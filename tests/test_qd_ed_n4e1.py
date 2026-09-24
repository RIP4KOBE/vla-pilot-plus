"""Synthetic CPU-only E1 engineering condition; no real study records or calls."""
import copy
import json
import sys
from pathlib import Path
from collections import Counter
from types import SimpleNamespace
import pytest
from test_qd_ed_n4_plan import r,load,ROOT,fixture as old_fixture,n as old,native_audit,metric
from test_qd_ed_final_runner import codex_runtime
sys.path.insert(0,str(ROOT/'scripts'))
n=load('e1_test_contract',ROOT/'scripts/qd_ed_n4e1_plan.py')
d=load('e1_test_report',ROOT/'scripts/qd_ed_n4e1_report.py')
s=load('e1_test_supervisor',ROOT/'scripts/qd_ed_n4e1_supervise.py')


@pytest.fixture
def case(old_fixture,monkeypatch,tmp_path):
    root,base,manifest,_,seeds,resources,_=old_fixture
    monkeypatch.setitem(sys.modules,'qd_ed_n4e1_plan',n)
    monkeypatch.setattr(r,'n4e1_support',lambda:n)
    monkeypatch.setattr(n,'PREREQUISITE_REVIEW_SHA256',old.PREREQUISITE_REVIEW_SHA256)
    artifacts=Path(base['artifact_root'])
    def ref(name,value):
        p=artifacts/(name+'.json');p.write_text(json.dumps(value));return {'path':str(p),'sha256':r.digest(p)}
    parent=codex_runtime(tmp_path);parent['gpu_mapping']={'physical_gpu':3,'uuid':'GPU-test','egl_device_index':0}
    parent.update(cuda_egl_probe={'resource_id':'prior-proof'},worktree=str(root),artifact_root=str(artifacts))
    parent_ref=ref('parent-runtime',parent);runtime=n.runtime_variant(parent,r);runtime_ref=ref('runtime180',runtime)
    before_paths={x['path'] for x in base['code_files']}|{'core/codex_stage.py','core/codex_stage_policy.py'}
    paths=before_paths|n.REQUIRED|n.SOURCE_DELTA
    for rel in paths:
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
        if rel in n.FROZEN_DOCS:p.write_bytes((ROOT/rel).read_bytes())
        elif not p.exists():p.write_bytes(b'synthetic source')
    seed_path=root/'data/seeds.json';seed_path.write_text(json.dumps(seeds))
    base.update(seed_plan_path=str(seed_path),seed_plan_sha256=r.digest(seed_path))
    monkeypatch.setattr(d,'ROOT',root)
    base.update(frozen=True,run_name='owned',runtime_manifest_path=parent_ref['path'],runtime_manifest_sha256=parent_ref['sha256'],
        code_files=[{'path':p,'sha256':r.digest(root/p)} for p in sorted(before_paths)])
    base_ref=ref('parent-plan',base)
    auth=ref('authority',{'schema':'explicit-user-two-study-resource-isolation-v1','max_owned_workers_per_study':1,
        'studies':[{'study_id':'owned','artifact_root':str(artifacts),'worktree':str(root),'physical_gpu':3,'gpu_uuid':'GPU-test',
            'max_episode_attempts':240,'max_gpu_hours':48,'bucket_caps':n.ORIGINAL_CAPS}]})
    monkeypatch.setattr(n,'ISOLATION_SHA',auth['sha256'])
    migration=ref('migration',{'schema':'two-study-resource-migration-v1','authorization':auth,
        'exact_owner_partition_verified':True,'source_plan_runtime_pointer_contract_unchanged':True})
    validation=ref('validation',{'schema':'two-study-resource-isolation-root-validation-v1','status':'PASS','authorization':auth,'migration':migration})
    refs={'authorization':auth,'migration':migration,'validation':validation}
    state={'run_name':'owned','artifacts':str(artifacts),'gpu_pool':[3],'max_concurrent_gpu_workers':1,
        'budget':{'max_episode_attempts':240,'max_gpu_hours':48,'reserved':n.ORIGINAL_CAPS,'gpu_hour_reservations':{'validation':14.,'formal':10.}},
        'resource_isolation':{'status':'ACTIVE','private_budget':True,'owning_worktree_after_migration':str(root),**refs}}
    (root/'research-state.yaml').write_text(r.yaml.safe_dump(state))
    for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl','qd-ed-runner.lock','qd-ed-state.lock'):
        (root/'data'/name).touch()
    plan=copy.deepcopy(base);original=plan.pop('n4_cohort');plan['episodes']=n.rows_from_dev(seeds)
    plan.update(source_commit='new-source',runtime_manifest_path=runtime_ref['path'],runtime_manifest_sha256=runtime_ref['sha256'],
        code_files=[{'path':p,'sha256':r.digest(root/p)} for p in sorted(paths)])
    plan['n4e1_cohort']={**original,'schema':'qd-ed-n4e1-cohort-v1','cohort_id':n.COHORT,'budget_allocation':n.BUDGET_ALLOCATION,
        'protocol':{'path':n.PROTOCOL,'sha256':n.FROZEN_DOCS[n.PROTOCOL]},
        'budget_allocation_amendment':{'path':n.PROTOCOL,'sha256':n.FROZEN_DOCS[n.PROTOCOL]},
        'engineering_condition':n.engineering_condition(),'resource_authority':refs,
        'source_mapping':{'parent_plan':base_ref,'parent_source_commit':base['source_commit'],'runtime_parent':parent_ref,
            'allowed_changed_paths':sorted(n.SOURCE_DELTA),'unchanged_sources':[x for x in base['code_files'] if x['path'] not in n.SOURCE_DELTA]}}
    plan['n4e1_cohort'].pop('shared_resource_contract');plan['n4e1_cohort'].pop('shared_resource_pointer')
    plan['n4e1_cohort']['runtime_prerequisites']['reuse_scope']='prior_engineering_only_not_N4E1_algorithm_validation'
    def event(row,identifier,valid=True,reason=None):
        output=artifacts/identifier;(output/'eds_eval').mkdir(parents=True,exist_ok=True)
        audit=native_audit() if row['profile']=='N4' else {'accepted':True,'evidence_complete':True}
        (output/'eds_eval/decision-evidence-audit.json').write_text(json.dumps(audit))
        if row['profile']=='N4':(output/'eds_eval/eds_metrics.jsonl').write_text(json.dumps(metric())+'\n')
        common={'attempt_id':identifier,'episode_key':row['episode_key'],'identity':r.episode_identity(row),'output_dir':str(output),
            'retry_of':row.get('retry_of'),'budget_bucket':row['budget_bucket'],'n4e1_cohort_id':n.COHORT,
            'n4e1_frozen_identity':n.binding(plan,runtime),'metric_chunks':1,'guided_chunks':1}
        return [{**common,'event':'reserved'},{**common,'event':'dispatched'},
            {**common,'event':'valid','outcome_valid':valid,'success':False,'gpu_process_wall_seconds':1.,
                'n4e1_episode_dispatched':True,'reason':reason,'required_cost_telemetry_complete':valid}]
    return root,plan,manifest,runtime,seeds,resources,state,ref,event,parent


def test_closed_12_engineering_identity_and_unchanged_native_consumer(case):
    root,p,m,rt,seeds,*_=case;n.validate_contract(p,m,rt,seeds,root,r)
    assert Counter(x['budget_bucket'] for x in p['episodes'])=={'baseline':4,'development':8}
    assert len(set(x['episode_key'] for x in p['episodes']))==12
    assert all(x['iteration']==n.COHORT and x['episode_key'].startswith('n4e1_') for x in p['episodes'])
    assert n.native_audit_alignment(native_audit(),[metric()],require=r.require)['status']=='verified'
    assert old.rows_from_dev(seeds)[0]['iteration']!=p['episodes'][0]['iteration']


@pytest.mark.parametrize('field,value',[('task_id',5),('env_seed',42),('timeout_seconds',900),('budget_bucket','development')])
def test_original_row_and_bucket_changes_rejected(case,field,value):
    root,p,m,rt,seeds,*_=case;p['episodes'][0][field]=value
    with pytest.raises(r.GateError,match='12 cells'):n.validate_contract(p,m,rt,seeds,root,r)


@pytest.mark.parametrize('path',['core/qd_terminal_population.py','core/codex_stage_policy.py','core/rdt_libero_action_converter.py'])
def test_mapping_does_not_allow_algorithm_prompt_or_decoder_changes(case,path):
    root,p,m,rt,seeds,*_=case
    next(x for x in p['code_files'] if x['path']==path)['sha256']='f'*64
    with pytest.raises(r.GateError,match='changed algorithm'):n.validate_contract(p,m,rt,seeds,root,r)


@pytest.mark.parametrize('change',['runtime','profile','source_permission','protected'])
def test_condition_mapping_rejects_broad_changes(case,change):
    root,p,m,rt,seeds,*_=case
    if change=='runtime':rt['environment']['OMP_NUM_THREADS']='1'
    elif change=='profile':p['candidate_profiles']['N4']['sha256']='d'*64
    elif change=='source_permission':p['n4e1_cohort']['source_mapping']['allowed_changed_paths'].append('main.py')
    else:p['phase_authorization']['validation']=True
    with pytest.raises(r.GateError):n.validate_contract(p,m,rt,seeds,root,r)


def test_90_default_remains_exact_and_only_closed180_public_condition_works(case):
    *_,rt90=case
    saved=copy.deepcopy(rt90);assert r.stage_overrides(rt90)['perception.gemini.timeout_seconds']==90
    assert r.stage_condition(rt90)==r.CODEX_STAGE_CONDITION
    rt180=n.runtime_variant(rt90,r);assert rt90==saved
    assert r.stage_condition(rt180)==n.STAGE_CONDITION
    assert r.stage_overrides(rt180)['perception.gemini.timeout_seconds']==180
    assert rt90['frozen_stage_provider']['public_config_sha256']!=rt180['frozen_stage_provider']['public_config_sha256']
    bad=copy.deepcopy(rt180);bad.pop('stage_engineering_condition')
    with pytest.raises(r.GateError,match='timeout'):r.stage_overrides(bad)
    bad=copy.deepcopy(rt180);bad['stage_engineering_condition']['condition_id']='own-label'
    with pytest.raises(r.GateError,match='unrecognized'):r.stage_overrides(bad)
    for seconds in (90,181,360):
        bad=copy.deepcopy(rt180);bad['frozen_stage_provider']['timeout_seconds']=seconds
        with pytest.raises(r.GateError,match='timeout'):r.stage_overrides(bad)


def test_missing_usage_remains_unknown_and_nonretryable_stops_later_row(case):
    root,p,_,rt,_,resources,_,_,event,_=case;row=p['episodes'][0]
    events=event(row,'invalid',False,'Codex token usage incomplete');final=events[-1]
    final.update(compute_outcome='completed',stage_backend='codex_cli',provider_failed_calls=2,stage_failed_queries=2,
        provider_input_tokens=55,provider_token_usage_complete=False)
    assert n.transport_recovery_eligibility(r.GateError(final['reason']),final,p,row,rt,r) is None
    assert not n.recoverable(final,n.binding(p,rt))
    with pytest.raises(r.GateError,match='prior valid'):n.admission(p,rt,p['episodes'][1],events,resources,root,r)
    retry={**row,'episode_key':'new-name','retry_of':'invalid','budget_bucket':'recovery','n4e1_recovery_contract':n.binding(p,rt)}
    with pytest.raises(r.GateError,match='cannot be retried'):n.check_retry(events,retry,r)
    cost=d.cost_observation([final],'provider_input_tokens')
    assert cost['observed_subtotal']==55 and cost['complete_total'] is None and cost['records_with_incomplete_usage']==1


def test_only_complete_cost_exact_transport_failure_recovery(case):
    _,p,_,rt,*_=case;row=p['episodes'][0]
    f={'event':'valid','compute_outcome':'completed','outcome_valid':False,'required_cost_telemetry_complete':True,
        'stage_backend':'codex_cli','provider_failed_calls':1,'stage_failed_queries':1,'reason':n.TRANSPORT_GATE,
        'n4e1_frozen_identity':n.binding(p,rt)}
    f['n4e1_recovery_eligibility']=n.transport_recovery_eligibility(r.GateError(n.TRANSPORT_GATE),f,p,row,rt,r)
    assert n.recoverable(f,n.binding(p,rt))
    for field,value in [('outcome_valid',True),('required_cost_telemetry_complete',False),('reason','codex_timeout')]:
        changed={**f,field:value};assert not n.recoverable(changed,n.binding(p,rt))
    assert not old.recoverable(f,n.binding(p,rt))


def test_full1840_private_protected_and_whole_cohort_caps(case,monkeypatch):
    _,p,_,_,_,_,state,*_=case
    def snap(hours=11.403172863324977,base=16):return {'dispatched':80,'by_bucket':{'baseline':base,'development':58,'recovery':6,'validation':0,'formal':0},
        'gpu_hours_consumed':hours,'gpu_hours_by_bucket':dict.fromkeys(n.ORIGINAL_CAPS,0.)}
    monkeypatch.setattr(r,'budget_snapshot',lambda *a:snap())
    n.protected_budget(state,[],[],p['episodes'][0],1800,r,plan=p)
    with pytest.raises(r.GateError,match='full 1800'):n.protected_budget(state,[],[],p['episodes'][0],1799,r,plan=p)
    monkeypatch.setattr(r,'budget_snapshot',lambda *a:snap(base=17))
    with pytest.raises(r.GateError,match='bucket capacity'):n.protected_budget(state,[],[],p['episodes'][0],1800,r,plan=p)
    monkeypatch.setattr(r,'budget_snapshot',lambda *a:snap(hours=24.-1840/3600+0.0001))
    with pytest.raises(r.GateError,match='protected 24'):n.protected_budget(state,[],[],p['episodes'][0],1800,r,plan=p)


def test_private_authority_rejects_old_shared_link_and_owner_mismatch(case):
    root,p,_,rt,_,_,state,*_=case
    n.resource_authority(p,rt,root,r)
    state['resource_isolation']['private_budget']=False;(root/'research-state.yaml').write_text(r.yaml.safe_dump(state))
    with pytest.raises(r.GateError,match='ACTIVE'):n.resource_authority(p,rt,root,r)


def test_direct_run_requires_dedicated_scope_before_gpu_or_reservation(case,monkeypatch):
    from contextlib import nullcontext
    root,p,m,rt,*_=case
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(p,m,rt));monkeypatch.setattr(r,'locked',lambda *a,**k:nullcontext())
    monkeypatch.setattr(r,'gpu_admission',lambda **k:pytest.fail('GPU forbidden'))
    monkeypatch.setattr(r,'append_event',lambda *a:pytest.fail('reservation forbidden'))
    with pytest.raises(r.GateError,match='dedicated'):r.run_plan('synthetic',split='dev',iteration=n.COHORT,root=root)


def test_first3_valid_failures_are_not_success_stop_and_checkpoint_is_required(case):
    root,p,_,rt,_,resources,_,ref,event,_=case;events=[]
    for i,row in enumerate(p['episodes'][:3]):
        n.admission(p,rt,row,events,resources,root,r);events+=event(row,str(i))
    with pytest.raises(r.GateError,match='attestation'):n.admission(p,rt,p['episodes'][3],events,resources,root,r)
    evidence=ref('evidence',{})
    p['n4e1_cohort']['checkpoint_release']=ref('checkpoint',{'schema':'qd-ed-n4e1-checkpoint-v1','cohort_id':n.COHORT,
        'source_commit':p['source_commit'],'source_files_sha256':n.source_identity(p),
        'protocol_sha256':p['n4e1_cohort']['protocol']['sha256'],'evidence':[evidence],
        'checks':dict.fromkeys(n.CHECKS,True),'attempt_ids':['0','1','2']})
    n.admission(p,rt,p['episodes'][3],events,resources,root,r)


def public_attempt(plan,runtime,row,identifier,success=False,valid=True):
    t={'attempt_id':identifier,'episode_key':row['episode_key'],'identity':r.episode_identity(row),
        'n4e1_episode_dispatched':True,'physical_gpu':3,'event':'valid','outcome_valid':valid,'success':success,
        'budget_bucket':row['budget_bucket'],'retry_of':row.get('retry_of'),'time_unix':float(len(identifier)),
        'gpu_process_wall_seconds':3.,'n4e1_cohort_id':n.COHORT,'n4e1_frozen_identity':n.binding(plan,runtime),
        'source_commit':plan['source_commit'],'profile_manifest_sha256':plan['profiles_sha256'],
        'runtime_manifest_sha256':plan['runtime_manifest_sha256'],'runtime_inventory_sha256':plan['runtime_inventory_sha256'],
        'init_row_sha256':row['init_row_sha256'],'plan_sha256':'base','stage_condition':n.STAGE_CONDITION,
        'output_dir':str(Path(plan['artifact_root'])/identifier),'provider_input_tokens':123,'provider_token_usage_complete':valid}
    metrics={'finite_executed_actions':True,'observer_wall_s':1.,'observer_bytes_written':100,'qd_active_chunks':1,
        'n4':{'records':[],'native_terminal_population_alignment':{'checked_decisions':1},'actual_prefix_different_decisions':1}}
    return {'terminal':t,'status':'complete_valid' if valid else 'terminal_invalid','metrics':metrics}


def test_new_report_binds_engineering_runtime_and_never_accepts_old_row(case):
    _,p,_,rt,*_=case
    assert d.plan_contract(p)==p['episodes']
    t=public_attempt(p,rt,p['episodes'][0],'new')['terminal'];d.validate_terminal(t,p,'base')
    t['stage_condition']=r.CODEX_STAGE_CONDITION
    with pytest.raises(ValueError,match='condition'):d.validate_terminal(t,p,'base')
    t['stage_condition']=n.STAGE_CONDITION;t['identity']['iteration']=old.COHORT
    with pytest.raises(ValueError,match='identity'):d.validate_terminal(t,p,'base')


def test_full_new_12_numeric_and_activity_vs_invalid_preserves_unknown(case):
    _,p,_,rt,*_=case
    attempts=[public_attempt(p,rt,row,str(i),success=(row['profile']=='N4' and row['task_id'] in (0,3))) for i,row in enumerate(p['episodes'])]
    report=d.summarize(p,attempts)
    assert report['matrix']=='complete_valid_12' and report['protocol_numeric_dev_criterion'] is True
    assert report['protocol_execution_activity_criterion'] is True and report['engineering_condition']=='N4_E1_t180'
    # Same public numeric subtotal must never become a complete token total.
    bad=copy.deepcopy(attempts);bad[6]['status']='terminal_invalid'
    bad[6]['terminal'].update(outcome_valid=False,provider_token_usage_complete=False,reason='Codex token usage incomplete')
    report=d.summarize(p,bad)
    assert report['matrix']!='complete_valid_12' and report['protocol_numeric_dev_criterion'] is None
    cost=report['profiles']['C0']['all_attempt_cost_fields']['provider_input_tokens']
    assert cost['observed_subtotal']==4*123 and cost['complete_total'] is None
    assert report['phase_authorized'] is False


def test_exact_release_keys_condition_and_real_lease_scope_required(case):
    root,p,_,rt,_,_,_,ref,_,_=case;keys=[row['episode_key'] for row in p['episodes'][:3]]
    plan_ref=ref('plan',p)
    release={'schema':'qd-ed-n4e1-execution-release-v1','status':'authorized','cohort_id':n.COHORT,
        'plan':plan_ref,'frozen_identity':n.binding(p,rt),'source_commit':p['source_commit'],
        'source_files_sha256':n.source_identity(p),'candidate_profiles':p['candidate_profiles'],
        'resource_authority':p['n4e1_cohort']['resource_authority'],'limits':n.LIMITS,'budget_allocation':n.BUDGET_ALLOCATION,
        'phase_authorization':p['phase_authorization'],'physical_gpu':3,'max_owned_GPU_workers':1,
        'gpu_mapping':rt['gpu_mapping'],'episode_keys':keys,'stage':'first3','checkpoint_release':None}
    rr=ref('release',release)
    n.execution_release(rr,plan_ref['path'],p,rt,keys,root,r)
    with pytest.raises(r.GateError,match='dedicated'):n.require_scope(p,root,r)
    release['frozen_identity']['stage_public_config_sha256']='old'
    with pytest.raises(r.GateError,match='identity'):n.execution_release(ref('bad-release',release),plan_ref['path'],p,rt,keys,root,r)
