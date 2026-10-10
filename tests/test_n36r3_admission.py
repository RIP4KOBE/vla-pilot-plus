"""CPU synthetic transactions through real release/admission/journal consumers.

Only source/runtime scientific audits and GPU/provider/process boundaries are
substituted. These fixtures are not production acceptance or G3 evidence.
"""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as release
from scripts import qd_ed_n36r3_admission as gate, qd_ed_n36_runner as runner
from scripts import qd_ed_n36_healthcheck as health, qd_ed_n36_accounting as accounting
from scripts import qd_ed_n36_supervise as supervisor, qd_ed_n36_bridge as bridge
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n36r3_preparation as preparation


@pytest.fixture
def setup(tmp_path, monkeypatch):
    source = tmp_path/'session/variants/cpu/implementation_worktree'
    owner = tmp_path/'owner/study_worktree'
    source.mkdir(parents=True); (owner/'data').mkdir(parents=True)
    (source/'configs/qd_ed_final').mkdir(parents=True)
    (source/'configs/qd_ed_final/n31_dev_task_identities.json').write_bytes(
        (c.ROOT/'configs/qd_ed_final/n31_dev_task_identities.json').read_bytes())
    (source/'scripts').mkdir()
    (source/'scripts/qd_ed_gpu_probe.py').write_bytes((c.ROOT/'scripts/qd_ed_gpu_probe.py').read_bytes())
    monkeypatch.setattr(gate, 'SOURCE', source); monkeypatch.setattr(gate, 'OWNER', owner)
    monkeypatch.setattr(bridge, 'ROOT', source)
    monkeypatch.setattr(c.stop, 'STOP_PATHS', (c.stop_path(source), str(tmp_path/'owner/STOP')))
    store = tmp_path/'refs'; store.mkdir()
    def put(name, value):
        p = store/(name+'.json'); p.write_text(json.dumps(value, sort_keys=True)); return c.ref(p)
    events = []
    for i in range(505):
        saved = gate.previous.draft.PRESERVED[i] if i < 2 else None
        key = saved['attempt_id'] if saved else 'historical_'+str(i)
        seconds = saved['gpu_seconds'] if saved else 0.
        if i == 504:
            seconds = (75.52725286641478-r.budget_snapshot(events)['gpu_hours_consumed'])*3600
        bucket = 'baseline' if i < 105 else 'development' if i < 418 else 'validation' if i < 478 else 'recovery'
        base = {'attempt_id':key, 'episode_key':key, 'budget_bucket':bucket}
        events.extend([{**base,'event':'reserved'}, {**base,'event':'dispatched'},
                       {**base,'event':'aborted','gpu_process_wall_seconds':seconds}])
    reservations = [{'event':'gpu_hour_reservations_changed', 'gpu_hour_reservations':c.CAPS['protected_gpu_hours'],
                     'rationale':'synthetic existing reserves', 'time_unix':1}]
    anchors = {}
    for name, rows in [('attempt-ledger.jsonl',events), ('gpu-healthcheck-ledger.jsonl',[]),
                       ('gpu-hour-reservation-ledger.jsonl',reservations)]:
        p = owner/'data'/name; p.write_text(''.join(json.dumps(e)+'\n' for e in rows))
        anchors[name] = {**c.ref(p), 'bytes':p.stat().st_size}
    snap = r.budget_snapshot(events, [])
    assert snap['gpu_hours_consumed'] == 75.52725286641478
    original = put('original-accounting', {'ledger_prefixes':anchors,
        'cost_reconciliation':{'retained_admission_margin_gpu_hours':.23357169027962}})
    monkeypatch.setattr(c, 'ACCOUNTING_SHA', original['sha256'])
    old_accounting = put('n36r2-accounting', {'inherited_accounting':original})
    review = put('scientific-review', {'synthetic':True})
    monkeypatch.setattr(c, 'PROTOCOL_REVIEW_SHA', review['sha256'])
    old_rows = c.expected_rows(source, cohort=c.DRAFT_RECOVERY_COHORT)
    old_protocol = put('old-protocol', {'episodes':old_rows})
    old_plan = put('old-plan', {'cohort':c.DRAFT_RECOVERY_COHORT, 'episodes':old_rows,
        'limits':c.LIMITS, 'worker_contract':c.WORKER_CONTRACT, 'protocol':old_protocol,
        'accounting':old_accounting, 'protocol_review':review})
    rows = c.expected_rows(source, cohort=c.DRAFT_N36R3_COHORT)
    terminal = put('historical-reconciliation', {'schema':'n36r3-production-closure-terminal-reconciliation-v1',
        'release_enabled':False, 'ledger_prefix':anchors['attempt-ledger.jsonl'],
        'health_ledger_prefix':anchors['gpu-healthcheck-ledger.jsonl']})
    allocation = put('allocation', {'schema':'n36r3-allocation-draft-v1', 'cohort':c.DRAFT_N36R3_COHORT,
        'episodes':rows, 'automatic_recoveries':0, 'allocation_is_not_authority':True, 'release_enabled':False})
    ledger = put('accounting', {'schema':'n36r3-accounting-draft-v1', 'cohort':c.DRAFT_N36R3_COHORT,
        'inherited_accounting':old_accounting, 'terminal_reconciliation':terminal,
        'retained_ledger_prefix':anchors['attempt-ledger.jsonl'],
        'retained_health_ledger_prefix':anchors['gpu-healthcheck-ledger.jsonl'],
        'allocation':allocation, 'all_prior_charges_retained':True, 'N36R2_status':'INVALID',
        'N36R2_charges_retained':True, 'protected_gpu_hours':c.CAPS['protected_gpu_hours'],
        'automatic_recoveries':0, 'new_budget_authority':False, 'current_headroom':None, 'release_enabled':False})
    protocol = put('protocol', {'schema':'n36r3-operational-protocol-draft-v1', 'cohort':c.DRAFT_N36R3_COHORT,
        'previous_plan':old_plan, 'inherited_protocol':old_protocol, 'inherited_protocol_review':review,
        'accounting':ledger, 'allocation':allocation, 'episodes':rows, 'automatic_recoveries':0,
        'scientific_changes':False, 'release_enabled':False})
    runtime = {'schema':'qd-ed-runtime-setup-v1', 'worktree':str(source), 'artifact_root':str(tmp_path/'artifacts'),
        'gpu_mapping':{'physical_gpu':7, 'uuid':c.GPU_UUID, 'egl_device_index':4, 'metadata_mapping_verified':True},
        'cuda_egl_verified':True, 'provider_ready':True, 'stage_recovered_error_condition':r.E2_STAGE_CONDITION,
        'frozen_stage_provider':{'backend':'codex_cli','model':'gpt-6-astra'}, 'environment':{}, 'files':[c.ref(source/'scripts/qd_ed_gpu_probe.py')], 'tasks':{}}
    source_ref = {'commit':'synthetic-exact-source', 'files':[{'path':'scripts/qd_ed_gpu_probe.py',
                   'sha256':w.sha(source/'scripts/qd_ed_gpu_probe.py')}]}
    plan = {'schema':'n36-released-plan-v1', 'frozen':True, 'release_enabled':True,
        'cohort':c.DRAFT_N36R3_COHORT, 'worktree':str(source), 'run_name':'cpu-only',
        'artifact_root':str(tmp_path/'artifacts/n36r3'), 'source':source_ref, 'scientific_source':source_ref,
        'protocol':protocol, 'protocol_review':review, 'accounting':ledger,
        'resource_routing':{'source_cwd':str(source),'owner_root':str(owner),'physical_gpu':7,'gpu_uuid':c.GPU_UUID},
        'runtime':put('runtime',runtime), 'runtime_closure':put('closure',{}),
        'controller_semantics':put('controller',{}), 'native_build':put('native',{}),
        'limits':c.LIMITS, 'worker_contract':c.WORKER_CONTRACT, 'deadline':c.DEADLINE,
        'stop_path':c.stop_path(source), 'stop_authority':c.stop.binding(), 'episodes':rows,
        'phase_authorization':{'dev':True,'validation':False,'formal':False}, 'attempt_identity':'episode_key',
        'runtime_inventory_sha256':'synthetic-inventory'}
    plan['b5_review'] = put('independent', {'schema':'n36r3-independent-b5-review-v1',
        'decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE', **{k:plan[k] for k in gate.BINDINGS},
        'worker_receipts_are_future':True, 'release_enabled':False})
    adoption = put('adoption', {'schema':'n36r3-source-adoption-v1', 'approved':True,
        'owner_root':str(owner), 'source_cwd':str(source), **{k:plan[k] for k in gate.BINDINGS},
        'independent_review':plan['b5_review']})
    amendment = put('owning-accounting', {'schema':'n36r3-owning-accounting-v1','cohort':c.DRAFT_N36R3_COHORT,
        'accounting':ledger,'source_adoption':adoption,'caps':c.CAPS,'limits':c.LIMITS,'healthchecks':gate.HEALTH,
        'automatic_recoveries':0,'ledger_prefixes':anchors,'snapshot':snap,'arithmetic':preparation.arithmetic(snap)})
    authority = {'schema':'n36-budget-authority-v1','approved':True,'cohort':c.DRAFT_N36R3_COHORT,
        'protocol':protocol,'accounting':ledger,'amendment':amendment,'ledger_prefixes':anchors,
        'source_adoption':adoption,'healthchecks':gate.HEALTH,'caps':c.CAPS,'limits':c.LIMITS,
        'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':c.DEADLINE,
        'starts_at':'2026-10-09T00:00:00Z','weekly_window':{'ends_at':c.DEADLINE,
          'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.},
        'approval_basis':put('standing',{'approved':True}),'automatic_recoveries':0}
    plan['authority'] = put('authority',authority)
    plan['expected_manifests'] = {row['episode_key']:put(row['episode_key'],
        {'row':row, 'output_dir':str(Path(plan['artifact_root'])/row['episode_key']), 'argv':['cpu-python']}) for row in rows}
    plan_ref = put('plan',plan)
    def detached(*, health_only, readiness=None):
        expected = {'schema':'n36r3-health-release-v1' if health_only else 'n36-execution-release-v1',
            'approved':True, 'plan':plan_ref, **{k:plan[k] for k in ('native_build','authority','protocol',
            'protocol_review','source','scientific_source','runtime_closure','controller_semantics','runtime',
            'limits','phase_authorization')}, **c.operational_binding(plan)}
        if health_only: expected['healthchecks'] = gate.HEALTH
        else: expected['readiness'] = readiness
        rr = put('health-review' if health_only else 'root-review', {**expected,
            'schema':'n36r3-root-health-review-v1' if health_only else 'n36-root-production-review-v1','decision':'APPROVED'})
        return put('health-release' if health_only else 'release', {**expected,'root_review':rr})
    health_ref = detached(health_only=True)
    state = {'run_name':'cpu-only','worktree':str(owner),'artifacts':runtime['artifact_root'],
        'canonical_worktree':str(owner),
        'gpu_pool':[7], 'max_concurrent_gpu_workers':1, 'n36_budget_authority':plan['authority'],
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':1800,'max_gpu_hours':224.,'reserved':c.CAPS['buckets'],
        'gpu_hour_reservations':c.CAPS['protected_gpu_hours'],'amendment':amendment,
        'dispatched':505,'gpu_hours_consumed':snap['gpu_hours_consumed']}}
    (owner/'research-state.yaml').write_text(yaml.safe_dump(state))
    seen = []
    monkeypatch.setattr(runner.source_execution, 'active', lambda: seen.append('bootstrap'))
    monkeypatch.setattr(runner.source_execution, 'attest', lambda *a, **kw: seen.append('source-only'))
    def sources(p):
        assert p['worktree'] == str(source)
        for item in p['source']['files']:
            w.require(w.sha(source/item['path']) == item['sha256'], 'synthetic source hash differs')
        seen.append('source')
    monkeypatch.setattr(bridge,'verify_sources',sources)
    monkeypatch.setattr(bridge,'attest_loaded',lambda *a: seen.append('loaded'))
    monkeypatch.setattr(bridge,'source_paths',lambda *a:{'scripts/qd_ed_gpu_probe.py'})
    monkeypatch.setattr(bridge.closure,'verify_runtime',lambda *a: seen.append('runtime') or {})
    from scripts import qd_ed_n34_controller as controller, qd_ed_n36_build as build
    monkeypatch.setattr(controller,'verify_semantics',lambda *a: seen.append('controller'))
    monkeypatch.setattr(build,'manifest',lambda *a: seen.append('native'))
    monkeypatch.setattr(r,'stage_overrides',lambda *a: None)
    monkeypatch.setattr(r,'validate_runtime_inputs',lambda *a: seen.append('inputs'))
    monkeypatch.setattr(bridge,'profiles',lambda *a:{'profiles':{'C0':{}}})
    monkeypatch.setattr(bridge,'_verify_manifest_bound',lambda ref,*a: w.read_ref(ref))
    monkeypatch.setattr(runner,'device_check',lambda: seen.append('device') or {'cpu_fixture':True})
    monkeypatch.setattr(r,'verify_provider',lambda runtime,env,root: seen.append(('provider',str(root))))
    monkeypatch.setattr(runner,'process_identity',lambda pid:{'pid':pid,'boot_id':'cpu','proc_start_ticks':'1'})
    monkeypatch.setattr(health,'wait_probe',lambda *a: 0)
    class Process:
        pid = 123
        def poll(self): return 0
    def popen(command, **kwargs):
        assert kwargs['cwd'] == source
        assert kwargs['env']['PYTHONPATH'].split(':')[0] == str(source)
        output = Path(command[command.index('--output')+1]); rid=command[-1]
        (output/'probe-frame.png').write_bytes(b'CPU synthetic frame; not a rendering')
        evidence={'schema':'qd-ed-gpu7-context-probe-v1','resource_id':rid,
            'physical_gpu':7,'torch_logical_device':0,'cuda_visible_devices':'7','cuda_device_order':'PCI_BUS_ID',
            'egl_cuda_ordinal_namespace':'process_visible','torch_uuid':c.GPU_UUID,'torch_visible_device_count':1,
            'cuda_kernel_result':2.,'display_egl_device_index':4,'display_cuda_ordinal':0,
            'cuda_associated_egl_devices':[{'egl_device_index':4,'cuda_ordinal':0}], 'gl_vendor':'NVIDIA fixture',
            'gl_renderer':'CPU fixture','gl_version':'fixture','frame_shape':[64,64,3], 'frame_dtype':'uint8',
            'frame_nonzero_values':1,'frame_std':1,'simulation_steps':0,'frame_png_sha256':w.sha(output/'probe-frame.png'),
            'time_unix':dt.datetime.now(dt.timezone.utc).timestamp()}
        (output/'probe-evidence.json').write_text(json.dumps(evidence))
        return Process()
    monkeypatch.setattr(health.subprocess,'Popen',popen)
    return SimpleNamespace(**locals())


def ready(f):
    result = health.run_healthcheck(f.plan_ref, f.health_ref, gate.PREPARATION_ID, timeout_seconds=20)
    assert result['status'] == 'VALID'
    ref = c.ref(Path(result['terminal']['output_dir'])/'healthcheck-result.json')
    return f.detached(health_only=False, readiness={'health_release':f.health_ref,'terminal':ref})


def test_positive_separate_health_then_actual_release_admission(setup):
    f=setup
    assert release.validate_health_release(f.plan_ref,f.health_ref)[0] == f.plan
    with pytest.raises((ValueError,KeyError)): release.validate_release(f.plan_ref,f.health_ref)
    rr=ready(f)
    assert release.validate_release(f.plan_ref,rr)[0] == f.plan
    state,events,resources,reservations=runner.snapshot(f.owner,f.authority)
    snap=release.admission(f.plan,f.authority,state,events,resources,reservations,f.rows[0],
        now=dt.datetime.now(dt.timezone.utc),gpu_idle=True,release_refs=(f.plan_ref,rr))
    assert snap['dispatched']==505 and snap['n36_reservation']['reserved_gpu_seconds']==1840
    assert len(resources)==3 and resources[-1]['event']=='completed'
    assert resources[0]['reserved_gpu_seconds']==60
    assert not (f.source/'data').exists()
    assert ('provider',str(f.source)) in f.seen
    assert {'source','loaded','runtime','controller','native','inputs'} <= set(x for x in f.seen if isinstance(x,str))
    with pytest.raises((ValueError,r.GateError)):
        health.run_healthcheck(f.plan_ref,f.health_ref,gate.PREPARATION_ID,timeout_seconds=20)


@pytest.mark.parametrize('fault',['source','review','authority','hash','owner','readiness','old-authority'])
def test_release_fail_closed(setup,fault):
    f=setup; rr=ready(f)
    if fault=='source': (f.source/'scripts/qd_ed_gpu_probe.py').write_text('changed')
    elif fault=='review': Path(f.plan['b5_review']['path']).write_text('{}')
    elif fault=='authority': Path(f.plan['authority']['path']).unlink()
    elif fault=='hash': rr={**rr,'sha256':'0'*64}
    elif fault=='owner': f.plan['resource_routing']['owner_root']=str(f.source); f.plan_ref=f.put('plan',f.plan)
    elif fault=='old-authority': f.authority['cohort']=c.DRAFT_RECOVERY_COHORT; f.put('authority',f.authority)
    elif fault=='readiness': rr=f.detached(health_only=False,readiness=None)
    with pytest.raises((ValueError,KeyError,TypeError,OSError)):
        release.validate_release(f.plan_ref,rr)


@pytest.mark.parametrize('fault',['stale-ledger','stale-state','STOP','deadline','bound','unknown','wrong-state','inflight'])
def test_health_reservation_negative(setup,fault,monkeypatch):
    f=setup
    if fault=='stale-ledger':
        path=f.owner/'data/gpu-hour-reservation-ledger.jsonl'
        with path.open('a') as stream: stream.write(json.dumps(f.reservations[0])+'\n')
    elif fault=='stale-state':
        f.state['budget']['dispatched']=504
        (f.owner/'research-state.yaml').write_text(yaml.safe_dump(f.state))
    elif fault=='STOP':
        path=Path(c.stop.STOP_PATHS[0]);path.parent.mkdir(parents=True);path.symlink_to(f.tmp_path/'absent')
    elif fault=='deadline': monkeypatch.setattr(c.stop,'DEADLINE','2000-01-01T00:00:00Z')
    elif fault=='wrong-state':
        f.state['n36_budget_authority']={}
        (f.owner/'research-state.yaml').write_text(yaml.safe_dump(f.state))
    elif fault=='unknown':
        path=f.owner/'data/attempt-ledger.jsonl'; path.write_text(path.read_text().replace('86.40354533703066','null'))
    elif fault=='inflight': accounting.reserve_healthcheck(f.plan_ref,f.health_ref,gate.PREPARATION_ID,timeout_seconds=20)
    with pytest.raises((ValueError,r.GateError)):
        accounting.reserve_healthcheck(f.plan_ref,f.health_ref,
            'n36_healthcheck_'+f.rows[0]['episode_key'],timeout_seconds=21 if fault=='bound' else 20)


def test_health_aggregate_and_invocation_bounds(setup):
    f=setup; rr=ready(f)
    resources=r.read_events(f.owner/'data/gpu-healthcheck-ledger.jsonl')
    local=gate.resource_events(f.plan,resources)
    assert local==resources
    snap=r.budget_snapshot(f.events,resources)
    cohort=r.budget_snapshot([],resources)
    cohort['gpu_healthcheck_hours']=1741/3600
    with pytest.raises(ValueError,match='healthcheck'):
        accounting.headroom(snap,cohort,retained_margin_hours=.23357169027962,protected_hours=44,healthcheck=True,need=60)
    bad=copy.deepcopy(resources);bad[-1]['gpu_process_wall_seconds']=61
    with pytest.raises(ValueError):gate.resource_events(f.plan,bad)
    bad=copy.deepcopy(resources);bad[-1]['release']={}
    with pytest.raises(ValueError):gate.resource_events(f.plan,bad)


def test_actual_runner_charge_once_and_durable_first_c0_pause(setup, monkeypatch):
    import io
    f=setup; rr=ready(f)
    starts=[]
    class WorkerProcess:
        pid=123
        stdin=io.BytesIO()
        def poll(self): return 0
    def start(command, **kwargs):
        starts.append(command)
        assert kwargs['cwd']==f.source
        assert kwargs['env']['PYTHONPATH'].split(':')[0]==str(f.source)
        output=Path(w.read_ref(f.plan['expected_manifests'][f.rows[0]['episode_key']])['output_dir'])
        (output/'eds_eval').mkdir()
        (output/'eds_eval/n36-worker-receipt.json').write_text('{"CPU_fixture":true}')
        return WorkerProcess()
    monkeypatch.setattr(runner.subprocess,'Popen',start)
    monkeypatch.setattr(runner,'wait_worker',lambda *a: 0)
    monkeypatch.setattr(r,'validate_result',lambda *a:{'outcome_valid':True,
        'required_cost_telemetry_complete':True,'success':False})
    # The scientific receipt verifier is unchanged in production; this test
    # isolates durable accounting/routing/pause, not scientific acceptance.
    verified=[]
    monkeypatch.setattr(runner.worker,'verify_terminal',lambda *a:verified.append(a))
    result=runner.execute_one(f.plan_ref,rr)
    assert result['status']=='PAUSED_FOR_ROOT_G3'
    before=(f.owner/'data/attempt-ledger.jsonl').read_bytes()
    # A dead fixture PID is safe to reconcile; a live handle is never killed.
    def dead(pid): raise FileNotFoundError('CPU fixture child exited')
    monkeypatch.setattr(runner,'process_identity',dead)
    for _ in range(2):
        assert runner.execute_one(f.plan_ref,rr)['status']=='PAUSED_FOR_ROOT_G3'
    assert (f.owner/'data/attempt-ledger.jsonl').read_bytes()==before
    assert len(starts)==1 and len(verified)==3
    events=r.read_events(f.owner/'data/attempt-ledger.jsonl')
    assert r.budget_snapshot(events,r.read_events(f.owner/'data/gpu-healthcheck-ledger.jsonl'))['dispatched']==506
    assert [e['event'] for e in events if e['attempt_id']==f.rows[0]['episode_key']]==['reserved','dispatched','valid']
    with pytest.raises(ValueError,match='health cannot bypass'):
        accounting.reserve_healthcheck(f.plan_ref,f.health_ref,'n36_healthcheck_'+f.rows[0]['episode_key'],timeout_seconds=20)


def test_actual_health_failed_probe_is_charged_and_no_retry(setup, monkeypatch):
    f=setup
    monkeypatch.setattr(health,'wait_probe',lambda *a: 1)
    result=health.run_healthcheck(f.plan_ref,f.health_ref,gate.PREPARATION_ID,timeout_seconds=20)
    assert result['status']=='INVALID_STOP'
    resources=r.read_events(f.owner/'data/gpu-healthcheck-ledger.jsonl')
    assert [e['event'] for e in resources]==['reserved','dispatched','aborted']
    assert resources[-1]['gpu_process_wall_seconds'] >= 0
    with pytest.raises(ValueError,match='no retry'):
        accounting.reserve_healthcheck(f.plan_ref,f.health_ref,'n36_healthcheck_'+f.rows[0]['episode_key'],timeout_seconds=20)


def test_actual_health_lost_handle_remains_unsettled(setup, monkeypatch):
    f=setup
    def interrupted(*args): raise KeyboardInterrupt()
    monkeypatch.setattr(health,'wait_probe',interrupted)
    with pytest.raises(KeyboardInterrupt):
        health.run_healthcheck(f.plan_ref,f.health_ref,gate.PREPARATION_ID,timeout_seconds=20)
    resources=r.read_events(f.owner/'data/gpu-healthcheck-ledger.jsonl')
    assert [e['event'] for e in resources]==['reserved','dispatched']
    assert r.budget_snapshot(f.events,resources)['gpu_healthcheck_inflight']==1
    with pytest.raises(r.GateError,match='unfinished GPU healthcheck'):
        accounting.reserve_healthcheck(f.plan_ref,f.health_ref,'n36_healthcheck_'+f.rows[0]['episode_key'],timeout_seconds=20)


@pytest.mark.parametrize('fault',['STOP','deadline','missing-journal','wrong-owner','state-worktree','stale-state','episode-cap'])
def test_episode_consumer_admission_gates_after_valid_readiness(setup, monkeypatch, fault):
    f=setup; rr=ready(f)
    state,events,resources,reservations=runner.snapshot(f.owner,f.authority)
    now=dt.datetime.now(dt.timezone.utc)
    if fault=='STOP':
        path=Path(c.stop.STOP_PATHS[0]);path.parent.mkdir(parents=True);path.touch()
    elif fault=='deadline': now=dt.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))-dt.timedelta(seconds=1839)
    elif fault=='missing-journal': resources=[]
    elif fault=='wrong-owner': f.plan['resource_routing']['owner_root']=str(f.source)
    elif fault=='state-worktree': state['worktree']=str(f.source)
    elif fault=='stale-state': state['budget']['gpu_hours_consumed']=0
    elif fault=='episode-cap': state['budget']['max_episode_attempts']=505
    with pytest.raises((ValueError,r.GateError)):
        release.admission(f.plan,f.authority,state,events,resources,reservations,f.rows[0],
            now=now,gpu_idle=True,release_refs=(f.plan_ref,rr))


def test_actual_health_aggregate_reservation_cannot_borrow_unused_seconds(setup):
    f=setup
    # Synthetic history fills only the health allowance. This is an arithmetic
    # boundary fixture, not a reachable continuation past the first C0 pause.
    record=accounting.reserve_healthcheck(f.plan_ref,f.health_ref,gate.PREPARATION_ID,timeout_seconds=20)
    history=[]
    for row in f.rows[1:31]:
        base={**record,'resource_id':'n36_healthcheck_'+row['episode_key']}
        history.extend([{**base,'event':'reserved'}, {**base,'event':'dispatched'},
                        {**base,'event':'completed','gpu_process_wall_seconds':60}])
    path=f.owner/'data/gpu-healthcheck-ledger.jsonl'
    path.write_text(''.join(json.dumps(e)+'\n' for e in history))
    with r.locked(f.owner/'data/qd-ed-state.lock'):
        r.sync_state_from_journal(f.owner,f.events)
    with pytest.raises(ValueError,match='healthcheck bound'):
        accounting.reserve_healthcheck(f.plan_ref,f.health_ref,gate.PREPARATION_ID,timeout_seconds=20)
    assert path.read_text()==''.join(json.dumps(e)+'\n' for e in history)


@pytest.fixture
def readiness_case(setup, monkeypatch):
    """Only temporary CPU evidence is edited; no production evidence is read."""
    f = setup
    rr = ready(f)
    record = w.read_ref(rr)
    terminal_path = Path(record['readiness']['terminal']['path'])
    terminal = r.read_json(terminal_path)
    evidence_path = terminal_path.parent/'probe-evidence.json'
    evidence = r.read_json(evidence_path)
    resources = r.read_events(f.owner/'data/gpu-healthcheck-ledger.jsonl')
    completed = terminal['time_unix']
    now = completed + 60
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(now, tz)
    monkeypatch.setattr(gate.dt, 'datetime', Clock)
    authority = copy.deepcopy(f.authority)
    validate = release.validate_health_release
    def health_release(*args):
        plan, runtime, _ = validate(*args)
        return plan, runtime, authority
    monkeypatch.setattr(release, 'validate_health_release', health_release)
    def check(*, sync_journal=True):
        evidence_path.write_text(json.dumps(evidence))
        terminal_path.write_text(json.dumps(terminal))
        record['readiness']['terminal'] = c.ref(terminal_path)
        if sync_journal:
            resources[-1] = copy.deepcopy(terminal)
        return gate.validate_readiness(f.plan_ref, record, resources=resources)
    return SimpleNamespace(**locals())


@pytest.mark.parametrize('equal', [False, True])
def test_readiness_observation_and_completion_are_distinct(readiness_case, equal):
    x = readiness_case
    assert x.evidence['time_unix'] < x.terminal['time_unix']
    x.evidence['time_unix'] = x.completed if equal else x.completed - 20
    assert x.check() == x.terminal


@pytest.mark.parametrize('field', ['probe', 'terminal'])
@pytest.mark.parametrize('bad', ['nan', 'inf', '-inf', 'future', 'before-start', 'missing', 'bool', 'string'])
def test_readiness_rejects_invalid_times(readiness_case, field, bad):
    x = readiness_case
    target = x.evidence if field == 'probe' else x.terminal
    starts = dt.datetime.fromisoformat(x.authority['starts_at'].replace('Z', '+00:00')).timestamp()
    values = {'nan':float('nan'), 'inf':float('inf'), '-inf':float('-inf'),
              'future':x.now + 1, 'before-start':starts - 1, 'bool':True, 'string':str(x.completed)}
    if bad == 'missing':
        del target['time_unix']
    else:
        target['time_unix'] = values[bad]
    with pytest.raises((ValueError, KeyError, r.GateError), match='time|nonfinite'):
        x.check()


def test_readiness_rejects_reversed_past_times(readiness_case):
    x = readiness_case
    x.evidence['time_unix'] = x.completed - 10
    x.terminal['time_unix'] = x.completed - 20
    with pytest.raises(ValueError, match='timestamps reversed'):
        x.check()


@pytest.mark.parametrize('limit', ['coordinator', 'weekly'])
def test_readiness_rejects_completion_after_authorized_end(readiness_case, limit):
    x = readiness_case
    x.evidence['time_unix'] = x.completed - 20
    end = dt.datetime.fromtimestamp(x.completed - 10, dt.timezone.utc).isoformat()
    # Isolate each window check after the real synthetic health release validation.
    if limit == 'coordinator':
        x.authority['coordinator_ends_at'] = end
    else:
        x.authority['weekly_window']['ends_at'] = end
    with pytest.raises(ValueError, match='outside authority window'):
        x.check()


@pytest.mark.parametrize('fault', ['resource', 'source', 'runtime', 'event', 'provider',
                                  'script', 'plan', 'release', 'frame', 'evidence', 'journal'])
def test_readiness_timestamp_fix_preserves_non_time_checks(readiness_case, fault):
    x = readiness_case
    if fault == 'resource': x.evidence['resource_id'] = 'foreign-resource'
    elif fault == 'source': x.terminal['source_commit'] = 'foreign-source'
    elif fault == 'runtime': x.terminal['runtime'] = {}
    elif fault == 'event': x.terminal['event'] = 'aborted'
    elif fault == 'provider': x.terminal['provider_verified'] = False
    elif fault == 'script': x.terminal['source_script_sha256'] = '0'*64
    elif fault == 'plan': x.terminal['plan'] = {}
    elif fault == 'release': x.terminal['release'] = {}
    elif fault == 'frame': (x.terminal_path.parent/'probe-frame.png').write_bytes(b'tampered')
    elif fault == 'evidence': x.evidence['gl_renderer'] = 'tampered'
    elif fault == 'journal': x.resources[-1]['time_unix'] -= 1
    with pytest.raises(ValueError):
        x.check(sync_journal=fault != 'journal')
