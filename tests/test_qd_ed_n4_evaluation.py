"""Synthetic CPU-only protected N4 contracts; never real protected payloads."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from contextlib import nullcontext
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import qd_ed_n4_evaluation as e
import qd_ed_n4_evaluate as launch
from test_qd_ed_n4_plan import fixture, r, n, ROOT


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);r.durable_json(path,value)
    return {'path':str(path),'sha256':r.digest(path)}


@pytest.fixture
def evaluation(fixture,monkeypatch):
    root,base,manifest,runtime,seeds,_,_=fixture;artifact=Path(base['artifact_root'])
    base.update(run_name='synthetic-N4',seed_plan_path=str(root/'seed.json'),seed_plan_sha256=e.SEED_SHA,
        runtime_manifest_path=str(artifact/'runtime.json'),scientific_config_files=[])
    runtime['gpu_mapping']['pci_bus_id']='0000:test';runtime['gpu_mapping']['driver_version']='synthetic'
    for i in (1,2):
        seeds['blocks']['validation_c1_b'+str(i)]=[{**x,'env_seed':x['env_seed']+i*1000,'policy_seed':x['policy_seed']+i*1000} for x in seeds['blocks']['dev']]
    seeds['blocks']['formal']=[{**x,'env_seed':x['env_seed']+4000,'policy_seed':x['policy_seed']+4000} for x in seeds['blocks']['dev']]
    save(root/'seed.json',seeds);save(artifact/'runtime.json',runtime)
    for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl',
                 'qd-ed-runner.lock','qd-ed-state.lock','exposure-registry.jsonl','historical-exposure-inventory.jsonl'):
        (root/'data'/name).touch()
    auth=save(artifact/'private-auth.json',{'schema':'explicit-user-two-study-resource-isolation-v1',
        'max_owned_workers_per_study':1,'studies':[{'study_id':base['run_name'],'worktree':str(root),
        'artifact_root':str(artifact),'physical_gpu':3,'gpu_uuid':'GPU-test','max_episode_attempts':240,
        'max_gpu_hours':48,'bucket_caps':n.ORIGINAL_CAPS}]})
    monkeypatch.setattr(e,'ISOLATION_SHA',auth['sha256'])
    migration=save(artifact/'migration.json',{'schema':'two-study-resource-migration-v1','authorization':auth,
        'exact_owner_partition_verified':True,'source_plan_runtime_pointer_contract_unchanged':True})
    valid=save(artifact/'migration-validation.json',{'schema':'two-study-resource-isolation-root-validation-v1',
        'status':'PASS','authorization':auth,'migration':migration})
    refs={'authorization':auth,'migration':migration,'validation':valid}
    state={'run_name':base['run_name'],'artifacts':str(artifact),'gpu_pool':[3],'max_concurrent_gpu_workers':1,
        'resource_isolation':{'status':'ACTIVE','private_budget':True,'owning_worktree_after_migration':str(root),**refs},
        'budget':{'max_episode_attempts':240,'max_gpu_hours':48,'dispatched':0,'gpu_hours_consumed':0.,
            'reserved':copy.deepcopy(n.ORIGINAL_CAPS),'gpu_hour_reservations':{'validation':14.,'formal':10.}}}
    import yaml
    (root/'research-state.yaml').write_text(yaml.safe_dump(state))
    for path in e.TOOLING:
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/path).read_bytes() if (ROOT/path).exists() else b'synthetic phase adapter\n')
    observed=r.read_json(root/n.OBSERVED);candidate=r.read_json(root/n.PROFILE)
    profile=e.evaluation_profiles(observed,candidate,r);save(root/e.PROFILE,profile)
    manifest=copy.deepcopy(profile);manifest['profiles']['N4']=r.expand_candidate('N4',candidate,manifest['profiles']['Q0'])
    seed_review=save(artifact/'seed-review.json',{'schema':'n4-prospective-seed-exposure-metadata-review-v1',
        'phase_authorized':False,'known_seed_intersections':[],'c1_cells':20,'all_c1_init_rows_match_formal':True,
        'inputs':[{'path':str(root/'data'/name),'sha256':r.digest(root/'data'/name)}
            for name in ('exposure-registry.jsonl','historical-exposure-inventory.jsonl')]+
            [{'path':str(root/'seed.json'),'sha256':e.SEED_SHA}]})
    monkeypatch.setattr(e,'SEED_REVIEW_SHA',seed_review['sha256'])
    base_ref=save(artifact/'base-dev.json',base)
    def make(phase):
        p=copy.deepcopy(base);previous=p.pop('n4_cohort')
        p.update(frozen=False,source_commit='same-production-new-tools',profiles_path=str(root/e.PROFILE),
            profiles_sha256=r.digest(root/e.PROFILE),episodes=e.rows(seeds,phase),
            phase_authorization={'dev':False,'validation':False,'formal':False})
        before={x['path']:x['sha256'] for x in base['code_files']}
        p['code_files']=[{'path':k,'sha256':r.digest(root/k)} for k in sorted(set(before)|e.TOOLING)]
        production=[{'path':k,'sha256':before[k]} for k in sorted(set(before)-e.TOOLING)]
        fingerprint=e.sha_json({'production_files':production,'candidate_profiles':base['candidate_profiles'],
            **{k:base[k] for k in ('runtime_manifest_sha256','runtime_inventory_sha256','seed_plan_sha256')}})
        p['n4_evaluation']={'schema':e.SCHEMA,'phase':phase,'cohort_id':e.PHASES[phase]['cohort_id'],
            'limits':copy.deepcopy(e.PHASES[phase]),'protocol':{'path':e.PROTOCOL,'sha256':e.PROTOCOL_SHA},
            'budget_clarification':{'path':e.PROTOCOL,'sha256':e.PROTOCOL_SHA},
            'dev_reporter':{'path':str(e.DEV_REPORT),'sha256':e.DEV_REPORT_SHA},'dev_plan':base_ref,
            'candidate_fingerprint':fingerprint,'promotion_certificate':None,'resource_authority':refs,'seed_exposure_review':seed_review,
            'source_mapping':{'dev_source_commit':base['source_commit'],'evaluation_source_commit':p['source_commit'],
                'allowed_tooling':sorted(e.TOOLING),'production_files':production},
            'runtime_prerequisites':previous['runtime_prerequisites'],'health_resources':previous['health_resources']}
        return p
    return root,base,manifest,runtime,seeds,make,state


@pytest.mark.parametrize('phase,count,perarm',[('validation',60,20),('formal',40,10)])
def test_closed_exact_matrices_and_seed_block_identity(evaluation,phase,count,perarm):
    root,_,manifest,runtime,seeds,make,_=evaluation;p=make(phase)
    e.validate_contract(p,manifest,runtime,seeds,root,r)
    assert len(p['episodes'])==len({e.cell(x) for x in p['episodes']})==count
    assert sum(x['profile']=='N4' for x in p['episodes'])==perarm
    assert not any(p['phase_authorization'].values())
    p['episodes'][0]['env_seed']+=1
    with pytest.raises(r.GateError,match='matrix/order'):e.validate_contract(p,manifest,runtime,seeds,root,r)


def test_ablation_exact_two_fields_and_frozen_production(evaluation):
    root,_,manifest,_,_,make,_=evaluation;p=make('formal')
    active=manifest['profiles']['N4'];off=manifest['profiles']['N4_QD_OFF']
    for name in ('restored_profile','resolved_eds_config'):
        assert {k:(v,off[name][k]) for k,v in active[name].items() if v!=off[name][k]}=={
            'qd_archive_mode':('grid_archive','none'),'qd_final_selection_mode':('terminal_population_v1','archive_global_best')}
        assert off[name].get('qd_quality_mode','provider')=='provider'
    e.scientific_mapping(p,root,r)
    next(x for x in p['code_files'] if x['path']=='core/qd_terminal_population.py')['sha256']='changed'
    with pytest.raises(r.GateError,match='production source changed'):e.scientific_mapping(p,root,r)


@pytest.mark.parametrize('field,value',[('runtime_manifest_sha256','other'),('runtime_inventory_sha256','other'),('seed_plan_sha256','other')])
def test_input_identity_drift_rejected(evaluation,field,value):
    root,*_,make,_=evaluation;p=make('validation');p[field]=value
    with pytest.raises(r.GateError,match='binding changed'):e.scientific_mapping(p,root,r)


def test_private_authority_rejects_peer_owner_and_shared_symlink(evaluation):
    root,_,_,runtime,_,make,_=evaluation;p=make('validation')
    e.resource_authority(p,runtime,root,r)
    changed=copy.deepcopy(runtime);changed['gpu_mapping']['uuid']='GPU-peer'
    with pytest.raises(r.GateError,match='budget/owner/GPU'):e.resource_authority(p,changed,root,r)
    path=root/'data/gpu-healthcheck-ledger.jsonl';path.unlink();path.symlink_to(root/'data/attempt-ledger.jsonl')
    with pytest.raises(r.GateError,match='owned local regular'):e.resource_authority(p,runtime,root,r)


def terminal(plan,row,key='a',**updates):
    value={'attempt_id':key,'episode_key':row['episode_key'],'identity':r.episode_identity(row),
        'n4_evaluation_frozen_identity':e.binding(plan),'n4_evaluation_cohort_id':plan['n4_evaluation']['cohort_id'],
        'event':'aborted','outcome_valid':False,'n4_episode_dispatched':True,'retryable_infrastructure':True,
        'reason':'external GPU3 process appeared during owned attempt','gpu_process_wall_seconds':5.,
        'retry_of':None,'budget_bucket':row['budget_bucket']}
    value.update(updates);return value


def group(t):return [{**t,'event':'reserved'},{**t,'event':'dispatched'},t]


@pytest.mark.parametrize('reason',['GPU3 UUID changed','GPU3 boot identity changed','TimeoutExpired',
    'GPU3 owned process Xid detected; see sanitized kernel monitor evidence','nonfinite action','audit failed'])
def test_unknown_faults_and_scientific_failures_never_recover(evaluation,reason):
    *_,make,_=evaluation;p=make('validation');t=terminal(p,p['episodes'][0],reason=reason)
    assert not e.recoverable(t,e.binding(p))


def test_exact_recovery_and_multiple_predispatch_records(evaluation):
    *_,make,_=evaluation;p=make('validation');row=p['episodes'][0];t=terminal(p,row)
    assert e.recoverable(t,e.binding(p))
    pre=terminal(p,row,'pre',n4_episode_dispatched=False,gpu_process_wall_seconds=0.)
    assert not e.recoverable(pre,e.binding(p))
    retry={**row,'episode_key':'retry','budget_bucket':'recovery','retry_of':'a',
        'n4_evaluation_recovery_contract':e.binding(p)}
    events=[{**pre,'event':'reserved'},pre,*group(t)]
    e.check_retry(events,retry,r)
    second=terminal(p,retry,'b',retry_of='a',event='valid',outcome_valid=True)
    with pytest.raises(r.GateError,match='one exact'):e.check_retry(events+group(second),retry,r)
    t.update(reason='GPU3 nvidia-smi monitor query timed out after 15 seconds')
    assert not e.recoverable(t,e.binding(p))
    t.update(failure_detail='gpu_monitor_timeout',gpu_monitor_timeout={'physical_gpu':3,'timeout_seconds':15})
    assert e.recoverable(t,e.binding(p))
    t.update(event='valid',reason=n.TRANSPORT_GATE,compute_outcome='completed',required_cost_telemetry_complete=True,
        stage_backend='codex_cli',provider_failed_calls=1,stage_failed_queries=1)
    snapshot=copy.deepcopy(t);t['n4_evaluation_recovery_eligibility']=e.transport_eligibility(r.GateError(n.TRANSPORT_GATE),t,p,r)
    assert e.recoverable(t,e.binding(p)) and t['event']=='valid' and snapshot['event']=='valid'
    t['outcome_valid']=True;assert not e.recoverable(t,e.binding(p))


def test_full_timeout_and_remaining_original_slots_preserved(evaluation):
    _,_,_,_,_,make,state=evaluation;p=make('validation');row=p['episodes'][0]
    e.whole_phase_budget(p,state,[],[],row,1800,r)
    with pytest.raises(r.GateError,match='no clipping'):e.whole_phase_budget(p,state,[],[],row,1799,r)
    changed=copy.deepcopy(state);changed['budget']['max_episode_attempts']=103
    with pytest.raises(r.GateError,match='remaining original'):e.whole_phase_budget(p,changed,[],[],row,1800,r)


def test_raw_recovery_uses_own_hours_only_with_verified_capability(evaluation,monkeypatch):
    from test_qd_ed_final_runner import events_for,synced_state
    root,_,_,_,_,make,_=evaluation;p=make('validation');row={**p['episodes'][0],'budget_bucket':'recovery',
        'retry_of':'eligible','n4_evaluation_recovery_contract':e.binding(p)}
    events=events_for();events[-1]['gpu_process_wall_seconds']=37.4*3600
    state=synced_state(events);state['gpu_pool']=[3]
    monkeypatch.setattr(e,'require_scope',lambda *a,**k:None)
    scope={};monkeypatch.setattr(e,'_ACTIVE_SCOPE',scope)
    permission=e._BudgetPermission(p,row,events,[],root,{})
    monkeypatch.setattr(r,'n4_evaluation_support',lambda:e)
    with pytest.raises(r.GateError,match='termination grace'):r.check_budget(state,events,row,physical_gpu=3)
    assert r.check_budget(state,events,row,physical_gpu=3,evaluation_context=permission)==1800
    changed=copy.deepcopy(row);changed['profile']='other'
    with pytest.raises(r.GateError,match='row/journal changed'):r.check_budget(state,events,changed,physical_gpu=3,evaluation_context=permission)
    with pytest.raises(r.GateError,match='unvalidated'):r.check_budget(state,events,row,physical_gpu=3,evaluation_context={})
    assert state['budget']['gpu_hours_consumed']==37.4


def test_prepare_rejects_before_seed_read(evaluation,monkeypatch):
    root,_,_,_,_,make,_=evaluation;p=make('validation');p['episodes']=[]
    def stop(*args):raise r.GateError('not promoted')
    monkeypatch.setattr(e,'reviewed_promotion',stop)
    proxy=SimpleNamespace(**r.__dict__);proxy.read_json=lambda *_:pytest.fail('must not read protected seed rows')
    with pytest.raises(r.GateError,match='not promoted'):launch.prepare(p,None,[],root,proxy)


def test_seed_exposure_recheck_and_atomic_formal_latch(evaluation):
    root,_,_,_,_,make,_=evaluation;p=make('validation');row=p['episodes'][0]
    registry=root/'data/exposure-registry.jsonl';registry.write_text(json.dumps({'task_id':row['task_id'],'episode_seed':row['env_seed']})+'\n')
    with pytest.raises(r.GateError,match='source changed|already exposed'):e.allocate(p,[],root,r)
    registry.write_text('');e.allocate(p,[],root,r);e.allocate(p,[],root,r)
    formal=make('formal');e.allocate(formal,[],root,r)
    other=copy.deepcopy(formal);other['n4_evaluation']['candidate_fingerprint']='changed'
    with pytest.raises(r.GateError,match='candidate already latched'):e.allocate(other,[],root,r)


def promotion(evaluation,monkeypatch):
    root,base,_,_,_,make,_=evaluation;p=make('validation');artifact=Path(p['artifact_root'])
    rows=base['episodes'];events=[];attempts=[]
    for i,row in enumerate(rows):
        t={'attempt_id':str(i),'event':'valid','identity':r.episode_identity(row),'n4_episode_dispatched':True,
            'outcome_valid':True,'gpu_process_wall_seconds':1.}
        events+=group(t);attempts.append({'terminal':t,'status':'complete_valid'})
    computed={'matrix':'complete_valid_12','protocol_numeric_dev_criterion':True,
        'protocol_execution_activity_criterion':True,'input_scope_complete':True,
        'profiles':{'N4':{'valid_cell_observation_summary':{'qd_active_chunks':1},'n4_consumer_summary':{'actual_prefix_different_decisions':1}}}}
    er=SimpleNamespace(recompute_dev=lambda *a:(computed,attempts,base));monkeypatch.setitem(sys.modules,'qd_ed_n4_evaluation_report',er)
    report=save(artifact/'report.json',{**computed,'input_manifest':{'synthetic':True}})
    proof=save(artifact/'proof.json',{'synthetic':True})
    review=save(artifact/'review.json',{'schema':'qd-ed-n4-evaluation-scientific-review-v1','report':report,
        'candidate_fingerprint':p['n4_evaluation']['candidate_fingerprint'],'checks':dict.fromkeys(e.CHECKS,True),
        'evidence_by_check':{k:[proof] for k in e.CHECKS}})
    cert=save(artifact/'promotion.json',{'schema':'qd-ed-n4-evaluation-promotion-v1','target_phase':'validation',
        'target_binding':e.binding(p),'protocol_sha256':e.PROTOCOL_SHA,
        'candidate_fingerprint':p['n4_evaluation']['candidate_fingerprint'],'report':report,'review':review})
    p['n4_evaluation']['promotion_certificate']=cert
    return root,p,events,computed,base,attempts


def test_promotion_full_inventory_and_reported_production_binding(evaluation,monkeypatch):
    root,p,events,_,base,attempts=promotion(evaluation,monkeypatch)
    e.reviewed_promotion(p,events,root,r)
    with pytest.raises(r.GateError,match='terminal inventory'):e.reviewed_promotion(p,events[:-3],root,r)
    pre={**events[0],'attempt_id':'pre','n4_episode_dispatched':False,'event':'aborted','gpu_process_wall_seconds':0.}
    extra=[{**pre,'event':'reserved'},pre]
    with pytest.raises(r.GateError,match='terminal inventory'):e.reviewed_promotion(p,events+extra,root,r)
    attempts.append({'terminal':pre,'status':'predispatch_rejected'})
    e.reviewed_promotion(p,events+extra,root,r)
    base['source_commit']='changed-production'
    with pytest.raises(r.GateError,match='reported Dev source'):e.reviewed_promotion(p,events+extra,root,r)


@pytest.mark.parametrize('key,value',[('matrix','incomplete'),('protocol_numeric_dev_criterion',False),
    ('protocol_execution_activity_criterion',False),('input_scope_complete',False)])
def test_partial_or_failed_dev_never_releases(evaluation,monkeypatch,key,value):
    root,p,events,computed,_,_=promotion(evaluation,monkeypatch);computed[key]=value
    with pytest.raises(r.GateError,match='recomputed|promotion incomplete'):e.reviewed_promotion(p,events,root,r)


def test_direct_runner_stops_before_gpu_and_generic_queue_is_guarded(evaluation,monkeypatch):
    root,_,manifest,runtime,_,make,_=evaluation;p=make('validation')
    p.update(frozen=True,phase_authorization={'dev':False,'validation':True,'formal':False})
    monkeypatch.setattr(r,'locked',lambda *a,**k:nullcontext())
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(p,manifest,runtime))
    monkeypatch.setattr(r,'n4_evaluation_support',lambda:e)
    monkeypatch.setattr(r,'gpu_admission',lambda *a,**k:pytest.fail('no GPU before scope'))
    with pytest.raises(r.GateError,match='dedicated owned supervisor'):
        r.run_plan('plan',split='validation',iteration=e.PHASES['validation']['cohort_id'],root=root)
    import qd_ed_available_gpu_queue as q
    monkeypatch.setattr(q,'runner',r)
    monkeypatch.setattr(r,'read_state',lambda *a:{'artifacts':p['artifact_root']})
    monkeypatch.setattr(r,'verify_provider',lambda *a,**k:pytest.fail('no provider before scope'))
    with pytest.raises(r.GateError,match='dedicated owned supervisor'):
        q.run_queue('plan',[p['episodes'][0]['episode_key']],status_path=Path(p['artifact_root'])/'direct-queue.json',root=root)
    with pytest.raises(r.GateError,match='generic bind/probe forbidden'):
        q.bind_plan('plan',p,runtime,{},p['episodes'][0],'log',root=root)


from contextlib import contextmanager
import os
import threading


def execution_release(plan,runtime,keys):
    plan.update(frozen=True,phase_authorization={'dev':False,
        'validation':plan['n4_evaluation']['phase']=='validation','formal':plan['n4_evaluation']['phase']=='formal'})
    plan['n4_evaluation']['promotion_certificate']=plan['n4_evaluation']['promotion_certificate'] or {'path':'synthetic','sha256':'fixture'}
    path=Path(plan['artifact_root'])/'phase-plan.json';save(path,plan);c=plan['n4_evaluation']
    value={'schema':'qd-ed-n4-evaluation-execution-release-v1','status':'authorized',
        'plan':{'path':str(path),'sha256':r.digest(path)},'frozen_identity':e.binding(plan),
        'source_identity':e.source_identity(plan,r),'candidate_profiles':plan['candidate_profiles'],
        'resource_authority':c['resource_authority'],'promotion_certificate':c['promotion_certificate'],
        'phase':c['phase'],'physical_gpu':3,'max_owned_GPU_workers':1,'gpu_mapping':runtime['gpu_mapping'],
        'episode_keys':list(keys),'limits':e.PHASES[c['phase']],'bucket_caps':n.ORIGINAL_CAPS,
        'timeout_seconds':1800,'cleanup_seconds':40}
    ref=save(Path(plan['artifact_root'])/'execution-release.json',value)
    return path,ref


@contextmanager
def owned_scope(root,plan,runtime,keys):
    """Actual CPU flock and unchanged supervisor wrappers, no GPU/proc probe."""
    import fcntl
    import qd_ed_n4_supervise as supervision
    support=supervision.load_support(ROOT,n.SUPPORT)
    lock=root/'data/qd-ed-runner.lock'
    monitor=SimpleNamespace(parent_pid=os.getpid(),root=root,episode_keys=frozenset(keys),require_boot=lambda:None)
    q=SimpleNamespace(pending_gate=lambda *a,**k:None,bind_plan=lambda *a,**k:None)
    path,ref=execution_release(plan,runtime,keys)
    original=r.locked
    with lock.open('a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        @contextmanager
        def reentrant(path,**kwargs):
            if Path(path)==lock:yield
            else:
                with original(path,**kwargs):yield
        r.locked=reentrant
        stat=lock.stat();status=root/'owned-status.json'
        save(status,{'status':'shared_runner_acquired','pid':os.getpid(),'owner_thread_id':threading.get_ident(),
            'boot_id':plan['boot_id'],'runner_lock_path':str(lock),'runner_lock_device':stat.st_dev,'runner_lock_inode':stat.st_ino})
        try:
            with support.supervise_calls(r,q,monitor,lambda:None),supervision.frozen_hardware(r,q):
                with e.supervised_dispatch(plan,keys,root,r,q,monitor,status,
                        release_reference=ref,plan_path=path,runtime=runtime):yield q
        finally:
            r.locked=original;fcntl.flock(stream,fcntl.LOCK_UN)


def test_real_private_lease_scope_release_and_hook_binding(evaluation):
    root,_,_,runtime,_,make,_=evaluation;p=make('validation');keys=[p['episodes'][0]['episode_key']]
    with owned_scope(root,p,runtime,keys):
        e.require_scope(p,root,r,p['episodes'][0])
        with pytest.raises(r.GateError,match='outside evaluation'):e.require_scope(p,root,r,p['episodes'][1])
        saved=r.wait_exclusively
        try:
            r.wait_exclusively=lambda *a:None
            with pytest.raises(r.GateError,match='hooks changed'):e.require_scope(p,root,r)
        finally:r.wait_exclusively=saved
    assert e._ACTIVE_SCOPE is None
    with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):pass


def test_exact_execution_release_rejects_drift_or_unreleased_phase(evaluation):
    root,_,_,runtime,_,make,_=evaluation;p=make('validation');keys=[p['episodes'][0]['episode_key']]
    path,ref=execution_release(p,runtime,keys)
    e.execution_release(ref,path,p,runtime,keys,root,r)
    changed=copy.deepcopy(p);changed['phase_authorization']['validation']=False
    with pytest.raises(r.GateError,match='remains closed'):e.execution_release(ref,path,changed,runtime,keys,root,r)
    with pytest.raises(r.GateError,match='exact binding'):e.execution_release(ref,path,p,runtime,[p['episodes'][1]['episode_key']],root,r)
    changed=copy.deepcopy(runtime);changed['gpu_mapping']['physical_gpu']=2
    with pytest.raises(r.GateError,match='exact binding'):e.execution_release(ref,path,p,changed,keys,root,r)


@pytest.mark.parametrize('phase,recoveries',[('validation',4),('formal',2)])
def test_recovery_limits_exact_original_identity_and_separate_certificate(evaluation,phase,recoveries):
    root,_,manifest,runtime,seeds,make,_=evaluation;p=make(phase)
    for i in range(recoveries):
        original=p['episodes'][i]
        p['episodes'].append({**original,'episode_key':f'retry-{i}','budget_bucket':'recovery','retry_of':f'old-{i}',
            'n4_evaluation_recovery_contract':e.binding(p),'recovery_release':{'path':'not-released','sha256':'fixture'}})
    e.validate_contract(p,manifest,runtime,seeds,root,r)
    changed=copy.deepcopy(p);changed['episodes'][-1]['policy_seed']+=1
    with pytest.raises(r.GateError,match='outside evaluation|binding differs'):e.validate_contract(changed,manifest,runtime,seeds,root,r)
    extra={**p['episodes'][recoveries],'episode_key':'too-many','budget_bucket':'recovery','retry_of':'other',
        'n4_evaluation_recovery_contract':e.binding(p),'recovery_release':{'path':'unused','sha256':'fixture'}}
    p['episodes'].append(extra)
    with pytest.raises(r.GateError,match='retry allowance'):e.validate_contract(p,manifest,runtime,seeds,root,r)


def formal_promotion(evaluation,monkeypatch,*,numeric=True):
    root,base,_,_,_,make,_=evaluation;validation=make('validation');formal=make('formal')
    attempts=[];events=[]
    for i,row in enumerate(validation['episodes']):
        t=terminal(validation,row,str(i),event='valid',outcome_valid=True)
        events+=group(t);attempts.append({'terminal':t,'status':'complete_valid'})
    computed={'complete':True,'numeric_pass':numeric,'input_scope_complete':True}
    monkeypatch.setitem(sys.modules,'qd_ed_n4_evaluation_report',SimpleNamespace(recompute=lambda *a:(computed,attempts,validation)))
    artifact=Path(formal['artifact_root']);ref=save(artifact/'validation-report.json',{**computed,'input_manifest':{'synthetic':True}})
    proof=save(artifact/'validation-proof.json',{'synthetic':True})
    review=save(artifact/'validation-review.json',{'schema':'qd-ed-n4-evaluation-scientific-review-v1','report':ref,
        'candidate_fingerprint':formal['n4_evaluation']['candidate_fingerprint'],'checks':dict.fromkeys(e.CHECKS,True),
        'evidence_by_check':dict.fromkeys(e.CHECKS,[proof])})
    formal['n4_evaluation']['promotion_certificate']=save(artifact/'formal-certificate.json',{
        'schema':'qd-ed-n4-evaluation-promotion-v1','target_phase':'formal','protocol_sha256':e.PROTOCOL_SHA,
        'target_binding':e.binding(formal),'candidate_fingerprint':formal['n4_evaluation']['candidate_fingerprint'],
        'report':ref,'review':review})
    return root,formal,events


def test_full60_numeric_fail_cannot_release_reserved_hours(evaluation,monkeypatch):
    root,p,events=formal_promotion(evaluation,monkeypatch,numeric=False)
    with pytest.raises(r.GateError,match='numeric failure'):
        e.prepare_reservation_release(p,events,[],root,r,healthcheck_inventory=None,rationale='claimed complete',time_unix=1.)


def test_reservation_release_all_costs_known_and_exact_prefix_no_mutation(evaluation,monkeypatch):
    root,p,events=formal_promotion(evaluation,monkeypatch);before=copy.deepcopy(events)
    artifact=Path(p['artifact_root'])
    health=[{'resource_id':'h','event':kind,'gpu_process_wall_seconds':7.} for kind in ('reserved','dispatched','completed')]
    inventory=save(artifact/'health.json',{'schema':'qd-ed-settled-healthcheck-inventory-v1',
        'resources':[{'resource_id':'h','terminal':save(artifact/'health-terminal.json',health[-1])}]})
    release=e.prepare_reservation_release(p,events,health,root,r,healthcheck_inventory=inventory,rationale='complete60pass',time_unix=1.)
    state=copy.deepcopy(evaluation[-1]);state['budget']['gpu_hour_reservations']={'validation':0.,'formal':10.}
    e.verify_reservation_release(p,state,events,health,[release],root,r)
    assert events==before and (root/'data/gpu-hour-reservation-ledger.jsonl').read_bytes()==b''
    with pytest.raises(r.GateError,match='unsettled healthcheck'):
        e.prepare_reservation_release(p,events,health[:-1],root,r,healthcheck_inventory=inventory,rationale='no',time_unix=1.)
    unknown=health+[{'resource_id':'new','event':kind,'gpu_process_wall_seconds':1.} for kind in ('reserved','dispatched','completed')]
    with pytest.raises(r.GateError,match='unrecognized/missing'):
        e.prepare_reservation_release(p,events,unknown,root,r,healthcheck_inventory=inventory,rationale='no',time_unix=1.)
    state['budget']['gpu_hour_reservations']['formal']=9
    with pytest.raises(r.GateError,match='state/event/phase'):e.verify_reservation_release(p,state,events,health,[release],root,r)


def test_private_ledger_alone_does_not_establish_seed_novelty(evaluation):
    root,_,_,_,_,make,_=evaluation;p=make('validation')
    (root/'data/historical-exposure-inventory.jsonl').write_text('{}\n')
    with pytest.raises(r.GateError,match='historical/rolling exposure source changed'):e.allocate(p,[],root,r)


def test_verified_recovery_permission_requires_exact_parent_and_phase(evaluation,monkeypatch):
    root,_,_,runtime,_,make,_=evaluation;p=make('validation')
    monkeypatch.setattr(e,'reviewed_promotion',lambda *a:None)  # Full certificate gates tested separately.
    e.allocate(p,[],root,r)
    original=p['episodes'][0];t=terminal(p,original);journal=group(t)
    retry={**original,'episode_key':'exact-retry','budget_bucket':'recovery','retry_of':'a',
        'n4_evaluation_recovery_contract':e.binding(p)}
    retry['recovery_release']=save(Path(p['artifact_root'])/'retry-release.json',{
        'schema':'qd-ed-n4-evaluation-recovery-v1','retry_of':'a','frozen_identity':e.binding(p),
        'original_terminal':save(Path(p['artifact_root'])/'original.json',t)})
    p['episodes'].append(retry)
    (root/'data/attempt-ledger.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in journal))
    with owned_scope(root,p,runtime,[retry['episode_key']]):
        permission=e.validated_budget_context(p,runtime,retry,journal,[],root,r)
        assert isinstance(permission,e._BudgetPermission)
        wrong={**retry,'split':'formal'}
        with pytest.raises(r.GateError,match='outside exact frozen plan'):
            e.validated_budget_context(p,runtime,wrong,journal,[],root,r)
        foreign=copy.deepcopy(journal)
        for event in foreign:event['attempt_id']='not-the-approved-parent'
        with pytest.raises(r.GateError,match='ineligible'):
            e.validated_budget_context(p,runtime,retry,foreign,[],root,r)


def test_audit_failure_retains_valid_terminal_without_retry_or_next_dispatch(evaluation,monkeypatch):
    root,_,_,_,_,make,_=evaluation;p=make('validation');row=p['episodes'][0]
    output=Path(p['artifact_root'])/'completed';(output/'eds_eval').mkdir(parents=True)
    t=terminal(p,row,event='valid',outcome_valid=True,output_dir=str(output),metric_chunks=0,guided_chunks=0)
    original=copy.deepcopy(t)
    monkeypatch.setattr(r,'run_plan',lambda *a,**k:[t])
    rejected=lambda *a:{'accepted':False,'evidence_complete':False,'errors':['synthetic_missing_bundle']}
    with launch.audited_calls(r,rejected,lambda *a:pytest.fail('C0 must use unchanged generic audit')):
        with pytest.raises(r.GateError,match='audit failed'):
            r.run_plan('unused',episode_keys=[row['episode_key']])
    assert t==original and t['event']=='valid' and t['outcome_valid'] is True
    saved=r.read_json(output/'eds_eval/decision-evidence-audit.json')
    assert saved['accepted'] is False and saved['wrapper_observation']['phase_native_alignment']['status']=='failed'


def test_unsettled_reservations_rejected_even_without_dispatch(evaluation):
    *_,make,_=evaluation;p=make('validation');row=p['episodes'][0];t=terminal(p,row)
    with pytest.raises(r.GateError,match='unsettled private episode'):
        e.require_settled([{**t,'event':'reserved'}],[],r)
    with pytest.raises(r.GateError,match='unsettled private health'):
        e.require_settled([], [{'resource_id':'h','event':'reserved'}],r)
