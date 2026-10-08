"""CPU-only runner transaction, accounting and command/release negative fixtures."""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import pytest
import yaml
from scripts import qd_ed_n32r3_contract as c, qd_ed_n32r3_release as release
from scripts import qd_ed_n32r3_runner as adapter, qd_ed_n32r3_bridge as bridge
from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from test_n32r3_continuation import fixture, write, dummy_ref

CAPS={'attempts':1800,'gpu_hours':224.,'buckets':{'baseline':400,'development':1120,'validation':180,'formal':40,'recovery':60},
      'protected_gpu_hours':{'validation':32.,'formal':12.}}
NOW=dt.datetime(2026,10,8,11,tzinfo=dt.timezone.utc)


def budget_fixture(tmp,events,resources=()):
    authority={'caps':copy.deepcopy(CAPS),'amendment':{'synthetic':True},'starts_at':'2026-10-04T00:00:00Z',
        'coordinator_ends_at':release.COORDINATOR_END,'continuation_resource_ids':[],
        'weekly_window':{'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.,'ends_at':c.DEADLINE}}
    ref=write(tmp/'authority.json',authority)
    plan={'authority':ref,'stop_path':str(tmp/'STOP')}
    state={'gpu_pool':[7],'max_concurrent_gpu_workers':1,'n32r3_budget_authority':ref,
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{**r.budget_snapshot(events,resources),'max_episode_attempts':1800,'max_gpu_hours':224.,
            'reserved':copy.deepcopy(CAPS['buckets']),'gpu_hour_reservations':copy.deepcopy(CAPS['protected_gpu_hours']),
            'amendment':authority['amendment']}}
    reservations=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':CAPS['protected_gpu_hours'],
                   'rationale':'synthetic CPU fixture','time_unix':1}]
    return plan,authority,state,reservations


@pytest.fixture
def lifecycle(fixture,tmp_path,monkeypatch):
    plan,events,mapping,parent=fixture
    root=tmp_path/'study_worktree';root.mkdir();(root/'data').mkdir()
    rows=c.expected_rows()
    monkeypatch.setattr(c,'expected_rows',lambda root=None:copy.deepcopy(rows))
    budget,authority,state,reservations=budget_fixture(root,events)
    plan.update(budget,worktree=str(root),artifact_root=str(root/'artifacts/n32r3'),run_name='synthetic',
                source={'commit':'b'*40},runtime_inventory_sha256='inventory',expected_manifests={})
    commands=[]
    for row,entry in zip(rows,mapping['proposed_cells']):
        plan['expected_manifests'][row['episode_key']]=write(root/'manifests'/(row['episode_key']+'.json'),
            {'row':row,'argv':[sys.executable,'main.py'],'output_dir':str(Path(plan['artifact_root'])/'attempts'/row['episode_key'])})
        commands.append({'new_attempt_id':row['episode_key'],'parent_expected_manifest':entry['parent_expected_manifest']})
    plan['command_candidates']=write(root/'commands.json',{'commands':commands})
    mapping['command_candidates']=plan['command_candidates']
    plan['carry_forward_map']=write(Path(plan['carry_forward_map']['path']),mapping)
    state.update(run_name='synthetic',artifacts=str(root/'artifacts'))
    runtime={'artifact_root':state['artifacts'],'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU_UUID,'egl_device_index':4},
             'frozen_stage_provider':{'backend':'codex_cli'}}
    plan['runtime']=write(root/'runtime.json',runtime)
    (root/'data/attempt-ledger.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    (root/'data/gpu-healthcheck-ledger.jsonl').write_text('')
    (root/'data/gpu-hour-reservation-ledger.jsonl').write_text(json.dumps(reservations[0])+'\n')
    (root/'research-state.yaml').write_text(yaml.safe_dump(state))
    authority['ledger_prefixes']={name:adapter.journal_prefix(root/'data'/name) for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl')}
    authority['preparation_review']=write(root/'prep.json',{'ledger_prefix':authority['ledger_prefixes']['attempt-ledger.jsonl'],
                                                         'health_prefix':authority['ledger_prefixes']['gpu-healthcheck-ledger.jsonl']})
    plan_ref=write(root/'plan.json',plan);release_ref=write(root/'release.json',{'synthetic_only':True})
    monkeypatch.setattr(release,'validate_release',lambda *args:(plan,runtime,authority))
    monkeypatch.setattr(adapter,'device_check',lambda:{'synthetic_only':True})
    monkeypatch.setattr(adapter,'check_probe',lambda *args:None)
    monkeypatch.setattr(r,'child_environment',lambda *_:{})
    monkeypatch.setattr(r,'verify_provider',lambda *args,**kwargs:None)
    monkeypatch.setattr(r,'stage_condition',lambda *_:'synthetic')
    monkeypatch.setattr(bridge,'profiles',lambda *_:{'profiles':{arm:{} for arm in c.ARMS}})
    monkeypatch.setattr(r,'validate_result',lambda *args:{'outcome_valid':True,'required_cost_telemetry_complete':True,'success':False})
    monkeypatch.setattr(adapter.worker,'verify_terminal',lambda *args:None)
    created=[]
    class FakeProcess:
        pid=90001
        def __init__(self,command,**kwargs):
            self.returncode=None;self.command=command;self.stdin=self;created.append(self)
        def write(self,data):assert data==b'G'
        def flush(self):pass
        def close(self):pass
        def poll(self):return self.returncode
    monkeypatch.setattr(adapter.subprocess,'Popen',FakeProcess)
    def identity(pid):
        if pid==123 or (created and created[-1].returncode is not None):raise FileNotFoundError('synthetic exited')
        return {'pid':pid,'proc_start_ticks':'1','boot_id':'synthetic'}
    monkeypatch.setattr(adapter,'process_identity',identity)
    def wait(process,*args):
        context=w.read_ref({'path':process.command[-3],'sha256':process.command[-1]})
        row=next(x for x in rows if x['episode_key']==context['episode_key'])
        assert context['continuation']==c.commitments(plan,row)
        output=Path(w.read_ref(plan['expected_manifests'][row['episode_key']])['output_dir'])
        record=json.loads((output/'process.json').read_text())
        assert record['release']==context['release']==release_ref
        write(output/'eds_eval/n32-worker-receipt.json',{'synthetic_only':True})
        process.returncode=0
        return 0
    monkeypatch.setattr(adapter,'wait_worker',wait)
    return root,plan,plan_ref,release_ref,events,authority


def test_full_runner_transaction_recovery_then_task5(lifecycle):
    root,plan,plan_ref,release_ref,old_events,_=lifecycle
    first=adapter.execute_one(plan_ref,release_ref)
    assert first['status']=='VALID' and first['terminal']['recovery_of']==c.OLD_INVALID
    assert first['terminal']['continuation']==c.commitments(plan,plan['episodes'][0])
    assert first['terminal']['source_commit']!=c.BASE_SOURCE
    assert adapter.execute_one(plan_ref,release_ref)['terminal']['attempt_id']==plan['episodes'][1]['episode_key']
    events=r.read_events(root/'data/attempt-ledger.jsonl')
    assert events[:len(old_events)]==old_events and len(events)==len(old_events)+6
    assert r.read_state(root/'research-state.yaml')['budget']['dispatched']==17
    assert not (root/'driver.lock').exists() and not (root/'coordinator.lease').exists()


@pytest.mark.parametrize('fault',['invalid','interrupt','stop_before','stop_after','journal','foreign_live','output_replay'])
def test_runner_fail_closed_no_retry_or_foreign_signal(lifecycle,monkeypatch,fault):
    root,plan,plan_ref,release_ref,events,_=lifecycle
    def fail(*args,**kwargs):raise ValueError('synthetic Stage/receipt invalid')
    monkeypatch.setattr(adapter,'cleanup_owned',lambda *a:pytest.fail('no timeout: never signal'))
    if fault=='invalid':monkeypatch.setattr(adapter.worker,'verify_terminal',fail)
    if fault=='interrupt':
        def interrupt(*args):raise KeyboardInterrupt('synthetic owner interruption')
        monkeypatch.setattr(adapter,'wait_worker',interrupt)
    if fault=='stop_before':
        Path(plan['stop_path']).touch()
        monkeypatch.setattr(adapter,'device_check',lambda:pytest.fail('STOP before GPU query'))
    if fault=='stop_after':
        original=r.append_event_locked
        def append(root,event):
            original(root,event)
            if event['event']=='reserved':Path(plan['stop_path']).touch()
        monkeypatch.setattr(r,'append_event_locked',append)
    if fault=='journal':
        original=adapter.snapshot;calls=[]
        def snapshot(*args):
            result=original(*args);calls.append(1)
            if len(calls)>1:result[2].append({'changed':True})
            return result
        monkeypatch.setattr(adapter,'snapshot',snapshot)
    if fault=='foreign_live':monkeypatch.setattr(adapter,'continuation_handles',lambda *a:[{'status':'LIVE'}])
    if fault=='output_replay':
        output=Path(w.read_ref(plan['expected_manifests'][plan['episodes'][0]['episode_key']])['output_dir']);output.mkdir(parents=True)
    if fault in ('stop_before','stop_after','journal'):
        with pytest.raises(ValueError):adapter.execute_one(plan_ref,release_ref)
    elif fault=='interrupt':
        with pytest.raises(KeyboardInterrupt):adapter.execute_one(plan_ref,release_ref)
        Path(plan['stop_path']).touch()
        assert adapter.execute_one(plan_ref,release_ref)['status']=='LIVE_OR_UNSETTLED'
    elif fault=='invalid':
        result=adapter.execute_one(plan_ref,release_ref)
        assert result['status']=='INVALID_STOP' and result['terminal']['gpu_process_wall_seconds']>0
        assert adapter.execute_one(plan_ref,release_ref)['status']=='INVALID_STOP'
    else:assert adapter.execute_one(plan_ref,release_ref)['status']=='LIVE_OR_UNSETTLED'
    after=r.read_events(root/'data/attempt-ledger.jsonl')
    assert after[:len(events)]==events
    if fault=='stop_after':assert [x['event'] for x in after[len(events):]]==['reserved']


@pytest.mark.parametrize('fault',['none','unknown','old_cap','recovery','baseline','development','reserves','private','workers','health','unattributed'])
def test_journal_accounting(tmp_path,fault):
    def event(key,bucket,iteration,seconds):
        base={'attempt_id':key,'identity':{'iteration':iteration},'budget_bucket':bucket}
        return [{**base,'event':kind,**({'outcome_valid':False,'gpu_process_wall_seconds':seconds} if kind=='aborted' else {})}
                for kind in ('reserved','dispatched','aborted')]
    events=event('old-invalid','development','old',1329.648039327003)
    resources=[{'resource_id':'old-health','event':kind,'cohort':'old','gpu_process_wall_seconds':100.}
               for kind in ('reserved','dispatched','completed')]
    row=c.expected_rows()[0]
    if fault in ('recovery','baseline','development'):
        count=c.LIMITS[fault]
        for i in range(count):events+=event('new'+str(i),fault,c.COHORT,1.)
        row=next(x for x in c.expected_rows() if x['budget_bucket']==fault)
    if fault=='old_cap':events+=event('new','baseline',c.COHORT,30600-1839)
    if fault=='health':resources+=[{'resource_id':'new-health','event':'reserved','cohort':c.COHORT,'kind':'n32r3_resource_preparation_v1'}]
    if fault=='unattributed':resources+=[{'resource_id':'new-health','event':kind,'cohort':c.COHORT,'kind':'n32r3_resource_preparation_v1','gpu_process_wall_seconds':1} for kind in ('reserved','dispatched','completed')]
    plan,authority,state,reservations=budget_fixture(tmp_path,events,resources)
    if fault=='unknown':events[-1]['gpu_process_wall_seconds']='Unknown'
    if fault=='reserves':reservations=[]
    if fault=='private':state['resource_isolation']['private_budget']=False
    if fault=='workers':state['max_concurrent_gpu_workers']=2
    if fault=='none':
        snap=release.admission(plan,authority,state,events,resources,reservations,row,now=NOW,gpu_idle=True)
        assert snap['gpu_hours_consumed']==pytest.approx((1329.648039327003+100)/3600)
        assert snap['by_bucket']['development']==1 and snap['gpu_healthcheck_hours']==100/3600
    else:
        with pytest.raises((ValueError,r.GateError)):release.admission(plan,authority,state,events,resources,reservations,row,now=NOW,gpu_idle=True)


@pytest.mark.parametrize('fault',['none','seed','provider','auth','model','condition','binding','unbound_output','old_digest'])
def test_bound_command_changes_only(tmp_path,monkeypatch,fault):
    row=c.expected_rows()[0]
    old_argv=['python','main.py','seed=1','perception.gemini.backend=codex_cli','perception.gemini.auth_mode=chatgpt',
              'perception.gemini.model=gpt-6-astra','condition=frozen','main.eds_config.n32_runtime_binding={source_commit:old,run_id:old}',
              'hydra.run.dir=/old']
    new_argv=old_argv[:-1]+['hydra.run.dir=/new']
    ref=write(tmp_path/'old.json',{'argv':old_argv})
    changes=[{'index':8,'old':old_argv[8],'new':new_argv[8]}]
    candidates=write(tmp_path/'commands.json',{'commands':[{'new_attempt_id':row['episode_key'],
        'parent_expected_manifest':ref,'old_argv':old_argv,'proposed_argv':new_argv,'exact_changes':changes,'proposed_output_dir':'/new'}]})
    plan={'command_candidates':candidates,'scientific_source':{'commit':c.BASE_SOURCE}}
    actual=list(new_argv)
    if fault in ('seed','provider','auth','model','condition','binding'):
        index={'seed':2,'provider':3,'auth':4,'model':5,'condition':6,'binding':7}[fault];actual[index]+='changed'
    if fault=='unbound_output':actual[-1]='hydra.run.dir=/other'
    if fault=='old_digest':Path(ref['path']).write_text('{}')
    monkeypatch.setattr(bridge.old,'command',lambda *args:(actual,Path('/new')))
    if fault=='none':assert bridge.command(plan,{},row)[0]==new_argv
    else:
        with pytest.raises(ValueError):bridge.command(plan,{},row)


@pytest.fixture
def release_chain(fixture,tmp_path,monkeypatch):
    """Exercise full detached DAG; spy expensive filesystem/runtime gates only."""
    plan,events,mapping,parent=fixture
    plan.update(frozen=True,release_enabled=True,limits=c.LIMITS,worker_contract=c.WORKER_CONTRACT,
        deadline=c.DEADLINE,stop_path=c.stop_path(),attempt_identity='episode_key',
        phase_authorization={'dev':True,'validation':False,'formal':False},source={'commit':'b'*40,'files':[]},
        expected_manifests={row['episode_key']:dummy_ref(tmp_path,row['episode_key']+'.json') for row in plan['episodes']},
        artifact_root=str(tmp_path/'new-artifacts'))
    _,authority,_,_=budget_fixture(tmp_path,events)
    # Retain the synthetic parent's own caps/window, and rebind its approved DAG.
    parent_authority={'caps':authority['caps'],'weekly_window':authority['weekly_window']}
    parent['authority']=write(Path(parent['authority']['path']),parent_authority)
    plan['parent_plan']=write(Path(plan['parent_plan']['path']),parent)
    expected_old={'schema':'n32-execution-release-v1','approved':True,'plan':plan['parent_plan'],
                  **{k:parent[k] for k in ('authority','protocol','source','runtime','limits','phase_authorization')}}
    plan['parent_review']=write(Path(plan['parent_review']['path']),{**expected_old,'schema':'n32-root-production-review-v1','decision':'APPROVED'})
    plan['parent_release']=write(Path(plan['parent_release']['path']),{**expected_old,'root_review':plan['parent_review']})
    # validate_mapping is tested independently with real digest-bound metadata.
    from scripts import qd_ed_n32r3_history as history
    monkeypatch.setattr(history,'validate_mapping',lambda *_:None)
    seen=[]
    monkeypatch.setattr(release,'verify_continuity',lambda *_:seen.append('continuity'))
    runtime={'schema':'qd-ed-runtime-setup-v1','worktree':plan['worktree'],'artifact_root':str(tmp_path),
        'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU_UUID,'egl_device_index':4},'cuda_egl_verified':True,'provider_ready':True,
        'stage_recovered_error_condition':r.E2_STAGE_CONDITION,'frozen_stage_provider':{'backend':'codex_cli'},'files':[],'tasks':{}}
    parent['runtime']=write(Path(parent['runtime']['path']),runtime)
    plan['parent_plan']=write(Path(plan['parent_plan']['path']),parent)
    plan['runtime']=write(tmp_path/'new-runtime.json',runtime)
    protocol={'schema':'n32r3-production-protocol-v1','cohort':c.COHORT,'episodes':plan['episodes'],'limits':c.LIMITS,
        'worker_contract':c.WORKER_CONTRACT,'attempt_identity':'episode_key','deadline':c.DEADLINE,'promotion':c.PROMOTION,
        'futility':'complete_valid_triples_only','validation_authorized':False,'formal_authorized':False}
    plan['protocol']=write(tmp_path/'new-protocol.json',protocol)
    authority.update(schema='n32r3-budget-authority-v1',approved=True,cohort=c.COHORT,limits=c.LIMITS,
        validation_authorized=False,formal_authorized=False,parent_authority=parent['authority'],ledger_prefixes={},
        preparation_review=plan['preparation_review'],approval_basis=dummy_ref(tmp_path,'approval.json'))
    amendment={'schema':'n32r3-adopted-accounting-v1','approved':True,'parent_authority':parent['authority'],'limits':c.LIMITS,
        'ledger_prefixes':{},'amendment':authority['amendment'],'continuation_resource_ids':[],
        'historical_charges_retained':True,'original_cohort_closed':True}
    plan['accounting_amendment']=write(tmp_path/'adopted.json',amendment)
    authority['accounting_amendment']=plan['accounting_amendment']
    plan['authority']=write(tmp_path/'new-authority.json',authority)
    plan_ref=write(tmp_path/'new-plan.json',plan)
    expected={'schema':'n32r3-execution-release-v1','approved':True,'plan':plan_ref,
        **{k:plan[k] for k in ('authority','protocol','source','runtime','limits','phase_authorization')},
        'continuation':c.commitments(plan,plan['episodes'][0])}
    review=write(tmp_path/'new-review.json',{**expected,'schema':'n32r3-root-production-review-v1','decision':'APPROVED'})
    release_ref=write(tmp_path/'new-release.json',{**expected,'root_review':review})
    monkeypatch.setattr(w,'verify_source',lambda *args:seen.append('source'))
    monkeypatch.setattr(bridge,'attest_loaded',lambda *args:seen.append('loaded'))
    monkeypatch.setattr(bridge,'source_paths',lambda *args:set())
    monkeypatch.setattr(r,'stage_overrides',lambda *args:seen.append('provider'))
    monkeypatch.setattr(r,'verify_files',lambda *args,**kwargs:seen.append('files'))
    monkeypatch.setattr(r,'validate_runtime_inputs',lambda *args:seen.append('generic-runtime'))
    monkeypatch.setattr(bridge,'verify_manifest',lambda ref,p,rt,row:seen.append(row['episode_key']))
    return plan,plan_ref,release_ref,seen


def test_release_dag_calls_every_existing_gate_and_all16(release_chain):
    plan,plan_ref,release_ref,seen=release_chain
    assert release.validate_release(plan_ref,release_ref)[0]==plan
    assert seen==['continuity','source','loaded','provider','files','generic-runtime']+[x['episode_key'] for x in plan['episodes']]


@pytest.mark.parametrize('fault',['release_hash','plan_bytes','review_bytes','review_plan','disabled','schema','source','manifest',
                                  'runtime','protocol','authority','amendment','missing_manifest','phase'])
def test_detached_release_negatives(release_chain,monkeypatch,fault):
    plan,plan_ref,ref,_=release_chain;released=w.read_ref(ref)
    if fault=='release_hash':ref['sha256']='0'*64
    elif fault=='plan_bytes':Path(plan_ref['path']).write_text('{}')
    elif fault=='review_bytes':Path(released['root_review']['path']).write_text('{}')
    elif fault=='review_plan':
        review=w.read_ref(released['root_review']);review['plan']=plan['runtime']
        released['root_review']=write(Path(released['root_review']['path']),review)
        ref=write(Path(ref['path']),released)
    elif fault=='disabled':released['approved']=False;ref=write(Path(ref['path']),released)
    elif fault in ('schema','missing_manifest','phase'):
        if fault=='schema':plan['schema']='n32-released-plan-v1'
        if fault=='missing_manifest':plan['expected_manifests'].pop(next(iter(plan['expected_manifests'])))
        if fault=='phase':plan['phase_authorization']['formal']=True
        with pytest.raises(ValueError):release.validate_plan(plan)
        return
    elif fault in ('runtime','protocol','authority','amendment'):
        key='accounting_amendment' if fault=='amendment' else fault
        Path(plan[key]['path']).write_text('{}')
    else:
        def fail(*a,**kw):raise ValueError('synthetic required gate rejected')
        monkeypatch.setattr(w if fault=='source' else bridge,'verify_source' if fault=='source' else 'verify_manifest',fail)
    with pytest.raises((ValueError,KeyError)):release.validate_release(plan_ref,ref)


@pytest.mark.parametrize('fault',['none','mapping','parent','semantic','command','manifest','no_release','attempt'])
def test_worker_context_explicit_binding(lifecycle,monkeypatch,fault):
    root,plan,plan_ref,release_ref,_,_=lifecycle
    row=plan['episodes'][0]
    context=adapter.worker.context_for(plan_ref,row,release_ref)
    monkeypatch.setattr(bridge,'verify_manifest',lambda reference,*args:w.read_ref(reference))
    if fault=='mapping':context['continuation']['carry_forward_map']=plan['parent_plan']
    if fault=='parent':context['continuation']['parent_release']=plan['parent_plan']
    if fault=='semantic':context['semantic_key']='forged'
    if fault=='command':context['main_argv']=['mutated']
    if fault=='manifest':context['expected_manifest']=plan['parent_plan']
    if fault=='no_release':context.pop('release')
    if fault=='attempt':context['attempt_id']='alias'
    ref=write(root/'context-test.json',context)
    if fault=='none':assert adapter.worker.validate_context(ref)[3]==row
    else:
        with pytest.raises(ValueError):adapter.worker.validate_context(ref)


def test_pooling_requires_operational_source_approval(fixture,monkeypatch):
    from scripts import qd_ed_n32r3_supervise as supervisor
    plan,events,_,_=fixture
    def fail(*args):raise ValueError('source review required')
    monkeypatch.setattr(release,'verify_continuity',fail)
    with pytest.raises(ValueError,match='source review required'):supervisor.reconcile(plan,events,lambda *args:None)


def test_native_success_never_repairs_generic_stage_invalid(lifecycle,monkeypatch):
    # Run a synthetic transaction, then use the actual terminal verifier, with
    # only expensive native arithmetic mocked. Generic disagreement must reject.
    import runpy
    actual=runpy.run_path(str(c.ROOT/'scripts/qd_ed_n32r3_worker.py'))['verify_terminal']
    root,plan,plan_ref,release_ref,_,_=lifecycle
    result=adapter.execute_one(plan_ref,release_ref)
    row=plan['episodes'][0];terminal=result['terminal'];terminal['guided_chunks']=1
    manifest_ref=plan['expected_manifests'][row['episode_key']]
    manifest=w.read_ref(manifest_ref);manifest['expected_runtime']=None
    # The verifier reads the new synthetic manifest and its matching plan bytes.
    plan['expected_manifests'][row['episode_key']]=write(Path(manifest_ref['path']),manifest)
    new_ref=write(Path(plan_ref['path']),plan);terminal['plan_sha256']=new_ref['sha256']
    output=Path(terminal['output_dir']);context=w.read_ref(terminal['context'])
    context['plan']=new_ref
    context_ref=write(output/'n32-worker-context.json',context);terminal['context']=context_ref
    record=json.loads((output/'process.json').read_text());record['context']=context_ref;write(output/'process.json',record)
    write(output/'command.json',{'argv':[manifest['argv'][0],'-m','scripts.qd_ed_n32r3_worker','--context',context_ref['path'],'--context-sha256',context_ref['sha256']],
          'main_argv':manifest['argv'],'context':context_ref})
    actual.__globals__['verify_receipt']=lambda *args:{'accepted':True}
    actual.__globals__['native_counts']=lambda *args:({}, {})
    monkeypatch.setattr(r,'validate_result',lambda *args:{'outcome_valid':False,'required_cost_telemetry_complete':False,'success':None})
    with pytest.raises(ValueError,match='generic result/cost telemetry'):actual(new_ref,row,terminal,release_ref)
