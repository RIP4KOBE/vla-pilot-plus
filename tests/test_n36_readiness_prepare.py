"""Explicitly SYNTHETIC CPU observations, never operational evidence/approvals.

Evidence/state validators execute normally. Only the expensive deployed all41
closure boundary is replaced in evidence-unit tests; its call is asserted.
Separate tests check that absent real graph/authority cannot reach production.
No device, provider, model, credential or owner-journal access occurs.
"""
import copy
import datetime as dt
import json
from pathlib import Path
import sys

import pytest

from scripts import qd_ed_n36_readiness_prepare as p
from scripts import qd_ed_n36_engineering_r1 as e
from test_n36_engineering import put

REAL_VERIFY_GRAPH = p.verify_graph


@pytest.fixture
def measured(tmp_path, monkeypatch):
    root = tmp_path / 'SYNTHETIC_NOT_AUTHORITY'
    root.mkdir()
    spec = e.specification()
    binding = spec['runtime_binding']
    prep = e.read(binding['preparation'])
    baseline = e.read(spec['canonical_runtime'])
    # Deliberately inert native bytes test validation plumbing, never native execution.
    inert = root / 'synthetic-runtime-input.bin'
    inert.write_bytes(b'SYNTHETIC inert input, not a model')
    baseline['artifact_root'] = str(root)
    baseline['files'] = [{'path': str(inert), 'sha256': e.w.sha(inert)}]
    baseline['tasks'] = {}
    spec['canonical_runtime'] = put(root, 'baseline', baseline)
    prep['baseline'] = spec['canonical_runtime']
    previous = e.read(prep['previous_specification'])
    previous['canonical_runtime'] = spec['canonical_runtime']
    prep['previous_specification'] = put(root, 'previous-spec', previous)
    for k in prep:
        if k.endswith('_path'):
            prep[k] = str(root / (k + '.json'))
    binding['runtime_path'] = str(root / 'ready.json')
    binding['source_record_path'] = str(root / 'source.json')
    binding['preparation'] = put(root, 'policy', prep)
    monkeypatch.setattr(e, 'SPECIFICATION', put(root, 'spec', spec))
    source = e.b.closure.source_record(e.b.ROOT, e.b.source_paths(e.b.ROOT))
    monkeypatch.setattr(e, 'SOURCE', e.b.ROOT)
    source_ref = put(root, 'source', source)
    issued = max(p.timestamp(prep['not_before']), p.timestamp(p.MEASUREMENT_CONTRACT['not_before'])) + 1
    def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()
    release = dict(schema='n36-preparation-measurement-release-v1', approved=True,
        purpose='readiness_preparation_only', specification=e.SPECIFICATION, source_record=source_ref,
        baseline=spec['canonical_runtime'], resource_id=prep['resource_id'], source_cwd=str(e.SOURCE),
        interpreter={'path': str(Path(sys.executable).resolve()), 'sha256': e.w.sha(Path(sys.executable).resolve()),
                     'version': sys.version}, issued_at=iso(issued), expires_at=iso(issued+300), gpu_seconds=60,
        provider_calls=1, episode_authorized=False, health_authorized=False, stop_authority=e.stop.binding(),
        graph={'plan': put(root, 'inert-plan', {'SYNTHETIC': True}),
               'runtime': {'path': prep['disabled_runtime_path'], 'sha256': '0'*64}})
    def save_path(path, value): return put(Path(path).parent, Path(path).stem, value)
    review = {**release, 'schema': 'n36-preparation-root-measurement-review-v1', 'decision': 'APPROVED'}
    release['root_review'] = put(root, 'synthetic-root-review', review)
    release_ref = save_path(prep['release_path'], release)
    common = {k: release[k] for k in ('source_record', 'baseline', 'resource_id', 'source_cwd', 'interpreter')}
    common['release'] = release_ref
    frame = root / 'synthetic-frame.png'
    frame.write_bytes(b'SYNTHETIC frame bytes, not a rendered image')
    mapping = baseline['gpu_mapping']
    observation = dict(schema='qd-ed-gpu-context-probe-v2', resource_id=prep['resource_id'], time_unix=issued+4,
        physical_gpu=mapping['physical_gpu'], torch_logical_device=0, cuda_visible_devices=str(mapping['physical_gpu']),
        cuda_device_order='PCI_BUS_ID', egl_cuda_ordinal_namespace='process_visible', torch_uuid=mapping['uuid'],
        nvidia_physical_gpu=mapping['physical_gpu'], nvidia_uuid=mapping['uuid'], nvidia_pci_bus_id=mapping['pci_bus_id'],
        torch_visible_device_count=1, cuda_kernel_result=2.0, display_egl_device_index=mapping['egl_device_index'],
        display_cuda_ordinal=0, cuda_associated_egl_devices=[{'egl_device_index': mapping['egl_device_index'], 'cuda_ordinal':0}],
        gl_vendor='NVIDIA SYNTHETIC', gl_renderer='SYNTHETIC', gl_version='SYNTHETIC', frame_shape=[64,64,3],
        frame_dtype='uint8', frame_nonzero_values=42, frame_std=1., simulation_steps=0, frame_png_sha256=e.w.sha(frame))
    gpu = dict(common, schema='n36-preparation-gpu-v1', observed_at=issued+4, simulation_steps=0,
               observation=observation, frame={'path':str(frame),'sha256':e.w.sha(frame)})
    provider = dict(common, schema='n36-preparation-provider-v1', observed_at=issued+5, simulation_steps=0,
        provider=baseline['frozen_stage_provider'], login_mode='current_official_chatgpt_login', calls=1, success=True,
        response=put(root, 'synthetic-response', {'schema':'n36-preparation-provider-response-v1',
            'resource_id':prep['resource_id'],'model':'gpt-6-astra','status':'completed',
            'request':put(root, 'synthetic-request-bytes', {'SYNTHETIC':'request'}),
            'response':put(root, 'synthetic-response-bytes', {'SYNTHETIC':'response'})}))
    from scripts import qd_ed_n36_build as native
    libs = []
    for name in (*native.REQUIRED, 'libcuda.so.1'):
        path=root/name; path.write_bytes(b'SYNTHETIC inert native fixture')
        libs.append({'path':str(path),'sha256':e.w.sha(path)})
    libs.sort(key=lambda x:x['path'])
    native_ref=put(root,'native',dict(schema='n36-native-build-v1',torch_version='SYNTHETIC',cuda_version='SYNTHETIC',torch_build='SYNTHETIC',libraries=libs))
    module=put(root,'synthetic-module',{'SYNTHETIC':True})
    closure={'modules':{'synthetic':module},'required_after':['synthetic']}
    graph={'native_build':native_ref,'runtime_closure':put(root,'closure',closure),
           'worktree':str(e.SOURCE), 'source':source}
    monkeypatch.setattr(e, 'owner_root', lambda plan: root)
    from scripts import qd_ed_n36_source as execution
    # Artifact-unit fixture only; real source guard gets separate negative tests.
    monkeypatch.setattr(execution, 'verify_receipt', lambda *a, **kw: None)
    (root / 'data').mkdir()
    process = {'pid': 42, 'proc_start_ticks': '100', 'boot_id': '00000000-0000-0000-0000-000000000001'}
    parent = dict(process, pid=41, proc_start_ticks='99')
    verified=[]
    monkeypatch.setattr(p,'verify_graph',lambda *args: (verified.append(args) or graph))
    receipt_binding={'release':release_ref,'source_record':source_ref,'resource_id':prep['resource_id'],'phase':'preparation_after','process':process}
    proof=dict(schema='n36-measured-preparation-proof-v2', release=release_ref, baseline=spec['canonical_runtime'],
        source_record=source_ref, native_receipt=put(root,'native-receipt',dict(schema='n36-loaded-native-build-v1',manifest=native_ref,libraries=libs)),
        runtime_receipt=put(root,'runtime-receipt',dict(schema='n34-runtime-receipt-v2',binding=receipt_binding,modules=closure['modules'],generated_modules={})),
        runtime_receipt_binding=receipt_binding)
    def bind():
        proof['gpu']=save_path(prep['gpu_path'],gpu)
        proof['provider']=save_path(prep['provider_path'],provider)
        frozen = provider['provider']
        response = e.read(provider['response'])
        output = Path(prep['proof_path']).with_suffix('.measurement')
        output.mkdir(exist_ok=True)
        launch = put(output, 'provider-launch-intent', dict(calls_reserved=1, parent=process,
            time_unix=issued+4.1, monotonic=100.1))
        provider_process = dict(process, pid=43, proc_start_ticks='101')
        handle = put(output, 'provider-process', dict(process=provider_process, parent=process,
            launch_intent=launch, time_unix=issued+4.2, monotonic=100.3))
        transport = put(root, 'synthetic-transport', dict(returncode=0, calls=1,
            process=provider_process, launch_intent=launch, process_handle=handle,
            lifecycle=dict(observation_complete=True, complete_usage_observed=True,
                clock='monotonic_seconds', spawn_started_at=100.2, spawn_returned_at=100.4,
                communicate_started_at=100.5, communicate_returned_at=100.6,
                process_exit_observed_at=100.7, observer_finished_at=100.8, returncode=0),
            preflight=dict(cli_sha256=frozen['cli_sha256'], cli_version=frozen['cli_version'],
                           login_mode='current_official_chatgpt_login'), parent=process,
            request=response['request'], response=response['response'], public_policy=e.r.codex_public_config(frozen)))
        envelope = dict(common, schema=p.MEASUREMENT_CONTRACT['schema'], process=process, parent=parent,
            started_at=issued+3.5, finished_at=issued+5.5, transport=transport,
            source_receipt=put(root, 'synthetic-source-receipt', {'SYNTHETIC':True}),
            **{k:proof[k] for k in ('gpu','provider','native_receipt','runtime_receipt','runtime_receipt_binding')})
        proof['measurement_envelope'] = put(root, 'synthetic-envelope', envelope)
        events=[]
        for kind,offset in [('reserved',2),('dispatched',3),('completed',6)]:
            terminal=kind=='completed'
            events.append(dict(common,event=kind,time_unix=issued+offset,reserved_gpu_seconds=60,
                gpu_process_wall_seconds=3 if terminal else 0,provider_calls=1 if terminal else 0,
                exclusive=True,telemetry_complete=True,gpu=proof['gpu'] if terminal else None,
                provider=proof['provider'] if terminal else None, kind='readiness_preparation',
                envelope=proof['measurement_envelope'] if terminal else None,
                process=process if terminal else None, parent=parent, **({'error':None} if terminal else {})))
        proof['accounting']=save_path(prep['accounting_path'],events)
        for name in ('readiness-preparation-ledger.jsonl','gpu-healthcheck-ledger.jsonl'):
            (root/'data'/name).write_text(''.join(json.dumps(v)+'\n' for v in events))
        return save_path(prep['proof_path'],proof)
    proof_ref=bind()
    return dict(root=root,spec=spec,prep=prep,source=source,source_ref=source_ref,proof=proof,proof_ref=proof_ref,
                gpu=gpu,provider=provider,bind=bind,save=save_path,now=issued+10,verified=verified,release=release)


def derive(m):
    return p.derive(m['spec'],m['source'],m['source_ref'],m['proof_ref'],now=m['now'])


def test_exact_measured_derivation_and_disabled_baseline(measured):
    m=measured
    before=Path(m['spec']['canonical_runtime']['path']).read_bytes()
    ready=derive(m)
    assert m['verified']
    assert ready['cuda_egl_verified'] is ready['provider_ready'] is ready['preparation']['runtime_ready'] is True
    assert ready['preparation']['release_enabled'] is False
    assert ready['preparation']['historical_readiness_is_not_current'] is True
    assert ready['preparation']['readiness_proof']==m['proof_ref']
    assert Path(m['spec']['canonical_runtime']['path']).read_bytes()==before
    assert json.loads(before)['provider_ready'] is False
    baseline=json.loads(before)
    for key in ('files','tasks','environment','frozen_stage_provider','stage_condition'):
        assert ready[key]==baseline[key]


@pytest.mark.parametrize('mutation',['stale','future','source','gpu','ordinal','egl','provider','auth','model',
    'transitions','frame','failed','calls','unlisted','native','native_incomplete','receipt','replay','sequence',
    'charge','nan','telemetry','exclusive','unapproved','expired','missing_release','health_identity','response_bytes'])
def test_bad_measured_evidence_fails_closed(measured,mutation):
    m=measured
    if mutation=='stale': m['gpu']['observed_at']=0
    elif mutation=='future': m['gpu']['observed_at']=m['now']+100
    elif mutation=='source': m['gpu']['source_record']={'path':'/wrong','sha256':'0'*64}
    elif mutation=='gpu': m['gpu']['observation']['torch_uuid']='GPU-wrong'
    elif mutation=='ordinal': m['gpu']['observation']['display_cuda_ordinal']=7
    elif mutation=='egl': m['gpu']['observation']['gl_vendor']='software'
    elif mutation=='provider': m['provider']['provider']['backend']='api'
    elif mutation=='auth': m['provider']['login_mode']='another-account'
    elif mutation=='model': m['provider']['provider']['model']='other'
    elif mutation=='transitions': m['gpu']['observation']['simulation_steps']=1
    elif mutation=='frame': m['gpu']['frame']['sha256']='0'*64
    elif mutation=='failed': m['provider']['success']=False
    elif mutation=='calls': m['provider']['calls']=2
    elif mutation=='unlisted': m['gpu']['unapproved']=True
    elif mutation=='health_identity': m['gpu']['resource_id']=e.HEALTH_ID
    elif mutation=='response_bytes':
        response=e.read(m['provider']['response'])
        Path(response['response']['path']).write_text('tampered synthetic response')
    m['proof_ref']=m['bind']()
    if mutation.startswith('native'):
        ref=m['proof']['native_receipt']; receipt=e.read(ref)
        if mutation=='native': receipt['manifest']['sha256']='0'*64
        else: receipt['libraries'].pop()
        m['proof']['native_receipt']=m['save'](ref['path'],receipt)
    elif mutation=='receipt':
        ref=m['proof']['runtime_receipt'];receipt=e.read(ref);receipt['binding']['phase']='historical'
        m['proof']['runtime_receipt']=m['save'](ref['path'],receipt)
    elif mutation in ('replay','sequence','charge','nan','telemetry','exclusive'):
        events=e.read(m['proof']['accounting'])
        if mutation=='replay': events*=2
        elif mutation=='sequence': events[-1]['event']='aborted'
        elif mutation=='charge': events[-1]['gpu_process_wall_seconds']=0
        elif mutation=='nan': events[-1]['gpu_process_wall_seconds']='NaN'
        elif mutation=='telemetry': events[-1]['telemetry_complete']=False
        else: events[-1]['exclusive']=False
        m['proof']['accounting']=m['save'](m['prep']['accounting_path'],events)
    elif mutation=='unapproved':
        m['release']['approved']=False
        m['proof']['release']=m['save'](m['prep']['release_path'],m['release'])
    elif mutation=='expired': m['now']+=1000
    elif mutation=='missing_release': Path(m['prep']['release_path']).unlink()
    m['proof_ref']=m['save'](m['prep']['proof_path'],m['proof'])
    with pytest.raises((ValueError,FileNotFoundError,e.r.GateError)):
        derive(m)


def test_external_root_acceptance_exact_and_no_episode_authority(measured):
    m=measured;ready=derive(m)
    ref=m['save'](m['spec']['runtime_binding']['runtime_path'],ready)
    with pytest.raises(FileNotFoundError):p.accepted(m['spec'],m['proof_ref'],ref)
    acceptance={'schema':'n36-preparation-root-acceptance-v1','approved':True,'specification':e.SPECIFICATION,
        'proof':m['proof_ref'],'runtime':ref,'release_enabled':False,'health_authorized':False,'episode_authorized':False}
    m['save'](m['prep']['acceptance_path'],acceptance)
    p.accepted(m['spec'],m['proof_ref'],ref)
    for key in ('release_enabled','health_authorized','episode_authorized'):
        altered=copy.deepcopy(acceptance);altered[key]=True
        m['save'](m['prep']['acceptance_path'],altered)
        with pytest.raises(ValueError):p.accepted(m['spec'],m['proof_ref'],ref)


def test_producer_requires_acceptance_and_is_write_once(measured,monkeypatch):
    m=measured
    monkeypatch.setattr(p.time,'time',lambda:m['now'])
    with pytest.raises(FileNotFoundError):p.produce(m['proof_ref'])
    path=Path(m['spec']['runtime_binding']['runtime_path']);assert not path.exists()
    ready=derive(m)
    ref={'path':str(path),'sha256':e.w.canonical_sha(ready)}
    m['save'](m['prep']['acceptance_path'],{'schema':'n36-preparation-root-acceptance-v1','approved':True,
        'specification':e.SPECIFICATION,'proof':m['proof_ref'],'runtime':ref,'release_enabled':False,
        'health_authorized':False,'episode_authorized':False})
    assert p.produce(m['proof_ref'])==ref
    assert e.read(ref)==ready
    with pytest.raises(ValueError,match='new immutable'):p.produce(m['proof_ref'])


def test_missing_real_graph_fails_without_devices(measured,monkeypatch):
    # Restore the real graph validator; the deliberately inert plan must fail.
    monkeypatch.undo()
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        p.verify_graph(measured['release'],measured['source'],e.read(measured['spec']['canonical_runtime']))


@pytest.mark.parametrize('mutation', ['valid', 'unlisted', 'boolean_only', 'gpu_mapping', 'provider', 'wrong_source'])
def test_engineering_admission_of_exact_measured_projection(measured, monkeypatch, mutation):
    m = measured
    monkeypatch.setattr(p.time, 'time', lambda: m['now'])
    runtime = derive(m)
    if mutation == 'unlisted': runtime['unapproved'] = True
    elif mutation == 'boolean_only': runtime['preparation'].pop('readiness_proof')
    elif mutation == 'gpu_mapping': runtime['gpu_mapping']['physical_gpu'] = 0
    elif mutation == 'provider': runtime['frozen_stage_provider']['model'] = 'other'
    elif mutation == 'wrong_source': runtime['preparation']['source'] = '0' * 40
    ref = m['save'](m['spec']['runtime_binding']['runtime_path'], runtime)
    m['save'](m['prep']['acceptance_path'], {'schema': 'n36-preparation-root-acceptance-v1',
        'approved': True, 'specification': e.SPECIFICATION, 'proof': m['proof_ref'], 'runtime': ref,
        'release_enabled': False, 'health_authorized': False, 'episode_authorized': False})
    plan = dict(runtime=ref, source=m['source'], scientific_source=m['source'], worktree=str(e.SOURCE))
    if mutation == 'valid':
        assert e.validate_runtime_binding(plan) == runtime
    else:
        with pytest.raises(ValueError): e.validate_runtime_binding(plan)


@pytest.mark.parametrize('field', ['release_enabled', 'frozen', 'phase_authorization'])
def test_preparation_graph_rejects_episode_authority(measured, field):
    m = measured
    plan = dict(release_enabled=False, frozen=False,
                phase_authorization=dict(engineering=False, dev=False, validation=False, formal=False))
    if field == 'phase_authorization': plan[field]['engineering'] = True
    else: plan[field] = True
    release = copy.deepcopy(m['release'])
    release['graph']['plan'] = put(m['root'], 'forbidden-enabled-plan', plan)
    with pytest.raises(ValueError, match='cannot carry episode authority'):
        REAL_VERIFY_GRAPH(release, m['source'], e.read(m['spec']['canonical_runtime']))


def test_expiry_during_closure_validation_cannot_promote(measured, monkeypatch):
    m = measured
    # Explicit clock switch at the closure boundary avoids timing-dependent tests.
    real_graph = p.verify_graph
    monkeypatch.setattr(p.time, 'time', lambda: m['now'])
    def expires(*args):
        result = real_graph(*args)
        monkeypatch.setattr(p.time, 'time', lambda: m['now'] + 1000)
        return result
    monkeypatch.setattr(p, 'verify_graph', expires)
    with pytest.raises(ValueError, match='fresh preparation release'):
        p.derive(m['spec'], m['source'], m['source_ref'], m['proof_ref'])


def synthetic_owner(tmp_path):
    import yaml
    root = tmp_path / 'SYNTHETIC_OWNER_NOT_AUTHORITY'
    (root / 'data').mkdir(parents=True)
    (root / 'research-state.yaml').write_text(yaml.safe_dump({'budget': {}}))
    return root


def resource_event(kind='reserved', identity='preparation_SYNTHETIC', charge=0):
    return dict(event=kind, resource_id=identity, kind='readiness_preparation',
                gpu_process_wall_seconds=charge, reserved_gpu_seconds=60, provider_calls=0,
                time_unix=1)


def test_durable_preparation_accounting_and_failed_overrun_retained(tmp_path):
    root = synthetic_owner(tmp_path)
    for event in (resource_event(), resource_event('dispatched'), resource_event('aborted', charge=72)):
        p.append_preparation(root, event)
    rows = p.journal_rows(root)
    assert rows == e.r.read_events(root/'data/gpu-healthcheck-ledger.jsonl')
    assert e.r.budget_snapshot([], rows)['gpu_hours_consumed'] == 72/3600
    assert e.r.read_state(root/'research-state.yaml')['budget']['gpu_hours_consumed'] == 72/3600
    with pytest.raises(e.r.GateError):
        p.append_preparation(root, resource_event())
    assert len(p.journal_rows(root)) == 3


def test_preparation_torn_reservation_blocks_global_admission(tmp_path, monkeypatch):
    root = synthetic_owner(tmp_path)
    real = p.journal_rows
    monkeypatch.setattr(p, 'journal_rows', lambda root: (_ for _ in ()).throw(OSError('synthetic crash')))
    with pytest.raises(OSError): p.append_preparation(root, resource_event())
    assert real(root) == []
    snap = e.r.budget_snapshot([], e.r.read_events(root/'data/gpu-healthcheck-ledger.jsonl'))
    assert snap['gpu_healthcheck_inflight'] == 1


def test_preparation_concurrent_identity_one_reservation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    root = synthetic_owner(tmp_path)
    def reserve():
        try:
            with e.r.locked(root/'data/qd-ed-runner.lock', nonblocking=False):
                p.append_preparation(root, resource_event())
            return True
        except e.r.GateError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: reserve(), range(2))) == [False, True]
    assert len(p.journal_rows(root)) == 1


@pytest.mark.parametrize('mutation', ['release', 'process', 'native', 'time', 'journal', 'mirror', 'telemetry', 'transport_parent', 'request'])
def test_fresh_envelope_and_durable_identity_reject_mutations(measured, mutation):
    m = measured
    ref = m['proof']['measurement_envelope']
    envelope = e.read(ref)
    if mutation == 'release': envelope['release']['sha256'] = '0'*64
    elif mutation == 'process': envelope['process']['pid'] += 1
    elif mutation == 'native': envelope['native_receipt']['sha256'] = '0'*64
    elif mutation == 'time': envelope['started_at'] = 1
    elif mutation in ('journal', 'mirror'):
        name = 'readiness-preparation-ledger.jsonl' if mutation == 'journal' else 'gpu-healthcheck-ledger.jsonl'
        (m['root']/'data'/name).write_text('')
    else:
        transport = e.read(envelope['transport'])
        if mutation == 'telemetry': transport['lifecycle']['observation_complete'] = False
        elif mutation == 'transport_parent': transport['parent']['pid'] += 1
        else: transport['request']['sha256'] = '0'*64
        envelope['transport'] = m['save'](envelope['transport']['path'], transport)
    m['proof']['measurement_envelope'] = m['save'](ref['path'], envelope)
    m['proof_ref'] = m['save'](m['prep']['proof_path'], m['proof'])
    with pytest.raises((ValueError, e.r.GateError)):
        derive(m)


@pytest.mark.parametrize('failure', ['nonzero', 'telemetry', 'timeout'])
def test_supervision_failure_paths_cpu_only(monkeypatch, failure):
    from types import SimpleNamespace
    from scripts import qd_ed_n36_runner as runner
    child = SimpleNamespace(pid=42, returncode=None)
    child.poll = lambda: child.returncode
    child.wait = lambda timeout: setattr(child, 'returncode', 1 if failure == 'nonzero' else 0)
    def monitor(*a, **kw):
        if failure == 'telemetry': raise e.r.GateError('synthetic telemetry loss')
    monkeypatch.setattr(e.r, 'check_exclusive_gpu', monitor)
    cleaned = []
    monkeypatch.setattr(runner, 'cleanup_owned', lambda *a: cleaned.append(a))
    with pytest.raises((ValueError, RuntimeError, TimeoutError)):
        p.supervise_measurement(child, {'SYNTHETIC':True}, 0 if failure == 'timeout' else 1, 7)
    assert bool(cleaned) is (failure == 'timeout')


def test_measurement_boundary_rechecks_source_and_stop(measured, monkeypatch, tmp_path):
    m = measured
    monkeypatch.setattr(p.time, 'time', lambda: m['now'])
    plan = dict(worktree=str(e.SOURCE), runtime=m['spec']['canonical_runtime'])
    calls = []
    monkeypatch.setattr(e.b.closure, 'verify_source', lambda *a: calls.append('source'))
    monkeypatch.setattr(e.b, 'attest_loaded', lambda *a: calls.append('loaded'))
    p.boundary(m['proof']['release'],m['spec'],m['source_ref'],m['source'],m['release'],plan)
    assert calls == ['source','loaded']
    stop = tmp_path/'STOP'; stop.touch()
    monkeypatch.setattr(e.stop, 'STOP_PATHS', (str(stop),))
    # Release binding itself rejects a changed STOP authority; canonical STOP
    # presence is tested with its exact authority below.
    with pytest.raises(ValueError):
        p.boundary(m['proof']['release'],m['spec'],m['source_ref'],m['source'],m['release'],plan)


@pytest.mark.parametrize('which', [0, 1])
def test_both_stop_entries_veto_without_dispatch(tmp_path, monkeypatch, which):
    paths = (tmp_path/'owner-STOP', tmp_path/'data-STOP')
    monkeypatch.setattr(e.stop, 'STOP_PATHS', tuple(map(str, paths)))
    paths[which].touch()
    with pytest.raises(ValueError, match='STOP present'): e.stop.check()


def test_write_once_receipt_rejects_overwrite(tmp_path):
    path = tmp_path/'receipt.json'
    ref = p.write_once(path, {'SYNTHETIC':True})
    with pytest.raises(FileExistsError): p.write_once(path, {'SYNTHETIC':False})
    assert e.read(ref) == {'SYNTHETIC':True}


@pytest.fixture
def runner_cpu(tmp_path, monkeypatch):
    """Real transaction/append/snapshot arithmetic; synthetic external boundaries."""
    import hashlib
    import yaml
    import subprocess
    from types import SimpleNamespace
    from scripts import qd_ed_n36_runner as runner, qd_ed_n36_source as execution
    root = synthetic_owner(tmp_path)
    prefixes = {}
    reservation = dict(event='gpu_hour_reservations_changed', gpu_hour_reservations=e.c.CAPS['protected_gpu_hours'],
                       rationale='SYNTHETIC', time_unix=1)
    (root/'data/gpu-hour-reservation-ledger.jsonl').write_text(json.dumps(reservation)+'\n')
    for name in e.JOURNALS:
        path = root/'data'/name
        if not path.exists(): path.touch()
        raw = path.read_bytes()
        prefixes[name] = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    authority = dict(caps=e.c.CAPS, ledger_prefixes=prefixes, amendment={'SYNTHETIC':True}, margin_reference={})
    authority_ref = put(root, 'authority', authority)
    snap = e.r.budget_snapshot([], [])
    state = dict(budget=dict(snap, max_episode_attempts=1800, max_gpu_hours=224,
        reserved=e.c.CAPS['buckets'], gpu_hour_reservations=e.c.CAPS['protected_gpu_hours']))
    (root/'research-state.yaml').write_text(yaml.safe_dump(state))
    source = {'commit':'SYNTHETIC'}
    source_ref = put(root, 'source', source)
    runtime = dict(gpu_mapping={'physical_gpu':7,'uuid':'SYNTHETIC'}, frozen_stage_provider={'SYNTHETIC':True})
    runtime_ref = put(root, 'runtime', runtime)
    plan = dict(worktree=str(root), authority=authority_ref, runtime=runtime_ref,
                runtime_closure=put(root,'closure',{'SYNTHETIC':True}))
    spec = dict(canonical_runtime=runtime_ref, retained_ledger_prefixes=prefixes)
    prep = {k:str(root/(k+'.json')) for k in ('proof_path','accounting_path','gpu_path','provider_path')}
    release = dict(resource_id='readiness_preparation_SYNTHETIC', gpu_seconds=60, provider_calls=1,
        source_record=source_ref, baseline=runtime_ref, source_cwd=str(root), interpreter={'SYNTHETIC':True},
        expires_at=e.stop.DEADLINE)
    ref = put(root,'release',release)
    monkeypatch.setattr(p, 'measurement_context', lambda r: (spec,source_ref,source,release,plan))
    monkeypatch.setattr(p, 'policy', lambda s: prep)
    monkeypatch.setattr(e, 'specification', lambda: spec)
    monkeypatch.setattr(e, 'owner_root', lambda plan: root)
    monkeypatch.setattr(e, 'validate_state', lambda *a: None)  # No owning adoption in fixtures.
    monkeypatch.setattr(e.accounting, 'retained_margin', lambda *a: .23357169027962)
    monkeypatch.setattr(e, 'child_environment', lambda *a: {})
    monkeypatch.setattr(e.r, 'runtime_gpu', lambda runtime: 7)
    monkeypatch.setattr(e.r, 'gpu_admission', lambda **kw: {'SYNTHETIC':True})
    monkeypatch.setattr(p, 'provider_preflight', lambda *a: {'SYNTHETIC':True})
    monkeypatch.setattr(execution, 'active', lambda: None)
    monkeypatch.setattr(execution, 'attest', lambda *a, **kw: {'SYNTHETIC':True})
    monkeypatch.setattr(runner, 'process_identity', lambda pid: dict(pid=pid,boot_id='SYNTHETIC',proc_start_ticks='1'))
    boundaries = []
    monkeypatch.setattr(p, 'boundary', lambda *a: boundaries.append(len(boundaries)))
    launches = []
    class Child:
        pid = 424242
        returncode = None
        def __init__(self, command, **kwargs): launches.append(command)
        def poll(self): return self.returncode
    monkeypatch.setattr(subprocess, 'Popen', Child)
    def supervise(child, identity, timeout, physical):
        child.returncode = 0
        output = Path(prep['proof_path']).with_suffix('.measurement')
        context = e.r.read_json(output/'context.json')
        common = {k:release[k] for k in ('source_record','baseline','resource_id','source_cwd','interpreter')}
        evidence = put(root, 'inert-evidence', {'SYNTHETIC':True})
        p.write_once(output/'envelope.json', dict(common, release=ref, process=identity, parent=context['parent'],
            **{k:evidence for k in ('gpu','provider','native_receipt','runtime_receipt','runtime_receipt_binding')}))
    monkeypatch.setattr(p, 'supervise_measurement', supervise)
    return SimpleNamespace(root=root, plan=plan, authority=authority, release=release, ref=ref,
        launches=launches, boundaries=boundaries, prep=prep, spec=spec)


def test_runner_cpu_real_reserve_dispatch_settle_and_replay(runner_cpu):
    f = runner_cpu
    before = Path(f.plan['runtime']['path']).read_bytes()
    proof = p.execute_preparation(f.ref)
    assert e.read(proof)['schema'] == 'n36-measured-preparation-proof-v2'
    rows = p.journal_rows(f.root)
    assert [x['event'] for x in rows] == ['reserved','dispatched','completed']
    assert rows == e.r.read_events(f.root/'data/gpu-healthcheck-ledger.jsonl')
    assert rows[-1]['gpu_process_wall_seconds'] > 0
    assert e.r.read_state(f.root/'research-state.yaml')['budget']['gpu_hours_consumed'] > 0
    assert len(f.launches) == 1 and '-I' in f.launches[0] and '-S' in f.launches[0]
    assert len(f.boundaries) >= 5
    assert Path(f.plan['runtime']['path']).read_bytes() == before
    with pytest.raises(ValueError, match='replay'):
        p.execute_preparation(f.ref)
    assert len(f.launches) == 1


@pytest.mark.parametrize('fault', ['failure','unknown','stop_dispatch','stop_terminal','lost_gpu'])
def test_runner_cpu_failures_keep_charges_or_inflight(runner_cpu, monkeypatch, fault):
    f = runner_cpu
    if fault in ('failure','unknown'):
        def fail(child, *args):
            if fault == 'failure': child.returncode = 1
            raise RuntimeError('SYNTHETIC child fault')
        monkeypatch.setattr(p, 'supervise_measurement', fail)
    elif fault.startswith('stop'):
        def boundary(*args):
            f.boundaries.append(1)
            if len(f.boundaries) >= (3 if fault == 'stop_dispatch' else 4):
                raise ValueError('STOP synthetic boundary')
        monkeypatch.setattr(p, 'boundary', boundary)
    else:
        count = []
        def gpu(**kwargs):
            count.append(1)
            if len(count) > 1: raise e.r.GateError('SYNTHETIC unknown GPU handles')
        monkeypatch.setattr(e.r, 'gpu_admission', gpu)
    with pytest.raises((RuntimeError, ValueError)): p.execute_preparation(f.ref)
    rows = p.journal_rows(f.root)
    if fault in ('unknown','lost_gpu'):
        assert rows[-1]['event'] == 'dispatched'
        assert e.r.budget_snapshot([], rows)['gpu_healthcheck_inflight'] == 1
    else:
        assert rows[-1]['event'] == 'aborted'
        assert rows[-1]['gpu_process_wall_seconds'] >= 0
        if fault != 'stop_dispatch': assert rows[-1]['gpu_process_wall_seconds'] > 0
    assert not Path(f.prep['proof_path']).exists()


@pytest.mark.parametrize('fault', ['inflight','replay','foreign','cap'])
def test_preparation_budget_rejects_unsettled_and_private_caps(runner_cpu, fault):
    f = runner_cpu
    if fault in ('inflight','foreign'):
        p.append_preparation(f.root, resource_event(identity='foreign-preparation'))
    elif fault == 'replay':
        for kind in ('reserved','dispatched','aborted'):
            p.append_preparation(f.root, resource_event(kind, f.release['resource_id'], 1 if kind=='aborted' else 0))
    else:
        import yaml
        state = e.r.read_state(f.root/'research-state.yaml')
        state['budget']['max_gpu_hours'] = 44
        (f.root/'research-state.yaml').write_text(yaml.safe_dump(state))
    with pytest.raises((ValueError, e.r.GateError)):
        p.preparation_budget(f.root, f.plan, f.authority, f.release)


def test_real_preparation_graph_wiring_all41_synthetic(tmp_path, monkeypatch):
    """Real verify_graph, source/closure/native/controller/input/all41 validators.

    Uses the existing inert graph and its parent schema adapter; the R1 exact
    runtime projection is covered separately. This is wiring, not deployment.
    """
    from types import SimpleNamespace
    from n36_engineering_cpu_fixture import Graph
    from scripts import qd_ed_n36_engineering as parent
    f = Graph(tmp_path, monkeypatch)
    runtime = copy.deepcopy(f.runtime)
    runtime['preparation'] = {'runtime_ready':False}
    runtime_ref = f.doc('disabled-preparation-runtime', runtime)
    closure = dict(f.closure, runtime=runtime_ref)
    closure_ref = f.doc('disabled-preparation-closure', closure)
    controller = e.read(f.controller_ref)
    controller['runtime'] = runtime_ref
    for key, ref in controller['review_evidence'].items():
        review = e.read(ref); review['runtime'] = runtime_ref
        controller['review_evidence'][key] = f.doc('disabled-review-'+key, review)
    controller_ref = f.doc('disabled-controller', controller)
    common = dict(runtime=runtime_ref, runtime_closure=closure_ref, controller_semantics=controller_ref)
    audit = dict(f.audit, **common)
    audit['expected_manifests'] = {row['episode_key']:f.doc('disabled-audit-'+str(i),
        e.b.manifest(audit,runtime,row)) for i,row in enumerate(audit['episodes'])}
    plan = dict(f.plan, **common)
    plan.update(frozen=False,release_enabled=False,phase_authorization=dict(engineering=False,dev=False,validation=False,formal=False),
                audit_plan=f.doc('disabled-audit',audit))
    plan['engineering_manifest'] = f.doc('disabled-engineering', e.b.engineering_manifest(plan,runtime,parent.row()))
    plan['expected_manifests'] = {parent.EPISODE_KEY:plan['engineering_manifest']}
    proxy = SimpleNamespace(**vars(parent))
    proxy.__file__ = str(f.source/'scripts/qd_ed_n36_engineering.py')
    def projected(plan):
        value = parent.read(plan['runtime'])
        parent.exact(value,runtime,'synthetic disabled runtime projection')
        return value
    proxy.validate_runtime_binding = projected
    monkeypatch.setattr(p,'e',proxy)
    release = {'graph':{'plan':f.doc('disabled-plan',plan),'runtime':runtime_ref}}
    assert REAL_VERIFY_GRAPH(release,f.source_record,runtime) == plan
    # Corruption at the forty-row boundary is caught by the same real wiring.
    bad = e.read(audit['expected_manifests'][audit['episodes'][-1]['episode_key']])
    bad['argv'].append('unapproved=true')
    ref = audit['expected_manifests'][audit['episodes'][-1]['episode_key']]
    Path(ref['path']).write_text(json.dumps(bad))
    with pytest.raises(ValueError): REAL_VERIFY_GRAPH(release,f.source_record,runtime)


@pytest.mark.parametrize('fault', ['none','login','version','provider','model','env','cli'])
def test_preparation_public_preflight_cpu_only(tmp_path, monkeypatch, fault):
    from types import SimpleNamespace
    cli = tmp_path/'inert-cli'; cli.write_text('SYNTHETIC NEVER EXECUTED'); cli.chmod(0o700)
    frozen = dict(backend='codex_cli',auth_mode='chatgpt',model='gpt-6-astra',reasoning_effort='low',
        timeout_seconds=90,cli_path=str(cli),cli_sha256=e.w.sha(cli),cli_version='0.155.1',disabled_skill_paths=[str(tmp_path/'inactive-fixture')])
    frozen['public_config_sha256'] = e.r.codex_public_config_sha256(frozen)
    runtime = dict(frozen_stage_provider=frozen, provider_ready=False)
    env = {'HOME':str(tmp_path)}
    monkeypatch.setattr(e.r.codex_policy_module(), 'discover_disabled_skill_paths', lambda **kw: frozen['disabled_skill_paths'])
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        value = ('codex-cli BAD' if fault=='version' else 'codex-cli 0.155.1') if argv[-1]=='--version' else (
            'Logged in using an API key' if fault=='login' else 'Logged in using ChatGPT')
        return SimpleNamespace(returncode=0,stdout=value,stderr='')
    if fault=='provider': frozen['backend']='api'
    if fault=='model': frozen['model']='other'
    if fault=='env': env['OPENAI_API_KEY']='SYNTHETIC_NOT_SECRET'
    if fault=='cli': frozen['cli_sha256']='0'*64
    if fault=='none':
        assert p.provider_preflight(runtime,env,run=run)['login_mode']=='current_official_chatgpt_login'
        assert len(calls)==2 and all('exec' not in x for x in calls)
    else:
        with pytest.raises((ValueError,e.r.GateError)): p.provider_preflight(runtime,env,run=run)


def test_real_source_boundary_rejects_wrong_commit():
    import subprocess
    source = e.b.closure.source_record(e.b.ROOT, e.b.source_paths(e.b.ROOT))
    source['commit'] = '0'*40
    with pytest.raises((ValueError, e.r.GateError, subprocess.CalledProcessError)):
        e.b.closure.verify_source(e.b.ROOT, source)


@pytest.mark.parametrize('fault', ['none','nonzero','malformed','telemetry'])
def test_preparation_transport_real_parser_retains_bytes(tmp_path, monkeypatch, fault):
    import subprocess
    from scripts import qd_ed_n36_runner as runner
    from core import codex_stage_lifecycle as lifecycle
    cli = tmp_path/'never-executed'; cli.write_text('SYNTHETIC')
    frozen = dict(backend='codex_cli',auth_mode='chatgpt',model='gpt-6-astra',reasoning_effort='low',
        timeout_seconds=90,cli_path=str(cli),cli_sha256=e.w.sha(cli),cli_version='0.155.1',disabled_skill_paths=[str(tmp_path/'inactive-fixture')])
    output = tmp_path/'output'; output.mkdir()
    frame = tmp_path/'inert.png';frame.write_bytes(b'SYNTHETIC')
    events = [dict(type='turn.started'), dict(type='item.completed',item=dict(type='agent_message',text='one\ntwo\nthree')),
              dict(type='turn.completed',usage=dict(input_tokens=3,cached_input_tokens=0,output_tokens=3))]
    raw = b'bad JSON\n' if fault=='malformed' else ''.join(json.dumps(x)+'\n' for x in events).encode()
    launches = []
    identity = dict(pid=123,proc_start_ticks='SYNTHETIC',boot_id='SYNTHETIC')
    monkeypatch.setattr(runner,'process_identity',lambda pid: dict(identity,pid=pid))
    monkeypatch.setattr(p,'provider_preflight',lambda *a: dict(cli_sha256=frozen['cli_sha256'],cli_version='0.155.1',
                                                           login_mode='current_official_chatgpt_login'))
    class Child:
        pid=123
        returncode=None
        def __init__(self,argv,**kwargs):
            launches.append(argv); self.out=kwargs['stdout']
        def communicate(self,input,timeout):
            assert input == (output/'request.txt').read_bytes()
            self.out.write(raw);self.out.flush();self.returncode=1 if fault=='nonzero' else 0
        def poll(self):return self.returncode
    monkeypatch.setattr(subprocess,'Popen',Child)
    if fault=='telemetry':
        finish = lifecycle.StageLifecycle.finish
        def lose(self, process):
            finish(self, process)
            self._data['observation_complete'] = False
        monkeypatch.setattr(lifecycle.StageLifecycle,'finish',lose)
    guards=[]
    if fault=='none':
        request,response,transport = p.measure_provider(dict(frozen_stage_provider=frozen),{},output,str(frame),lambda:guards.append(1))
        assert Path(response['path']).read_bytes()==raw
        assert e.read(transport)['calls']==1 and len(guards)==2
    else:
        with pytest.raises((ValueError,RuntimeError)):
            p.measure_provider(dict(frozen_stage_provider=frozen),{},output,str(frame),lambda:guards.append(1))
    assert len(launches)==1
    assert (output/'provider-transport.json').exists() and (output/'provider-process.json').exists()
    assert (output/'response.jsonl').read_bytes()==raw


def test_child_measurement_collects_receipts_after_observation_cpu_only(runner_cpu, monkeypatch):
    import os
    from scripts import qd_ed_n36_build as native, qd_ed_n36_source as execution
    from scripts.qd_ed_n36_runner import process_identity
    f = runner_cpu
    output = Path(f.prep['proof_path']).with_suffix('.measurement');output.mkdir()
    f.plan['native_build'] = put(f.root,'native',{'SYNTHETIC':True})
    f.plan['runtime_closure'] = put(f.root,'child-closure',{'required_after':[]})
    parent = process_identity(os.getppid())
    context = put(output,'context',dict(release=f.ref,parent=parent,output=str(output)))
    for kind in ('reserved','dispatched'):
        p.append_preparation(f.root,dict(resource_event(kind,f.release['resource_id']),release=f.ref,parent=parent))
    p.write_once(output/'child-admitted.json',process_identity(os.getpid()))
    steps = []
    def probe(manifest, dest, resource):
        steps.append('gpu')
        assert manifest == f.plan['runtime']['path'] and resource==f.release['resource_id']
        (dest/'probe-frame.png').write_bytes(b'SYNTHETIC')
        return {'time_unix':1,'simulation_steps':0}
    monkeypatch.setattr(p.probe,'child_probe',probe)
    monkeypatch.setattr(p.probe,'validate_probe_evidence',lambda *a:steps.append('validate_gpu'))
    inert = put(output,'inert',{'SYNTHETIC':True})
    def provider(*args):
        steps.append('provider');return inert,inert,inert
    monkeypatch.setattr(p,'measure_provider',provider)
    def native_after(ref,*,after):
        assert after is True;steps.append('native_after');return {'SYNTHETIC':True}
    def runtime_after(closure,ref,*,binding,after):
        assert after is True and binding['process']==process_identity(os.getpid())
        steps.append('runtime_after');return {'SYNTHETIC':True}
    def source_after(*args,**kwargs):
        assert kwargs['binding']['phase']=='preparation_after'
        steps.append('source_after');return {'SYNTHETIC':True}
    monkeypatch.setattr(native,'attest',native_after)
    monkeypatch.setattr(e.b.closure,'attest_runtime_receipt',runtime_after)
    monkeypatch.setattr(execution,'attest',source_after)
    before = Path(f.plan['runtime']['path']).read_bytes()
    ref = p.child_measure(context)
    assert steps==['gpu','validate_gpu','provider','native_after','runtime_after','source_after']
    envelope = e.read(ref)
    assert envelope['schema']==p.MEASUREMENT_CONTRACT['schema'] and envelope['parent']==parent
    assert Path(f.plan['runtime']['path']).read_bytes()==before


def test_preparation_release_has_independent_finite_reservation(measured):
    m = measured
    release = copy.deepcopy(m['release'])
    issued = p.timestamp(release['issued_at'])
    release['gpu_seconds'] = 2000  # Separate from the engineering 1900s slot.
    release['expires_at'] = dt.datetime.fromtimestamp(issued+3000,dt.timezone.utc).isoformat()
    review = {k:v for k,v in release.items() if k!='root_review'}
    review.update(schema='n36-preparation-root-measurement-review-v1',decision='APPROVED')
    release['root_review'] = put(m['root'],'independent-preparation-review',review)
    ref = m['save'](m['prep']['release_path'],release)
    assert p.validate_release(ref,m['spec'],m['source'],m['source_ref'],now=m['now'])['gpu_seconds']==2000
    release['gpu_seconds'] = 3001
    ref = m['save'](m['prep']['release_path'],release)
    with pytest.raises(ValueError,match='finite preparation caps'):
        p.validate_release(ref,m['spec'],m['source'],m['source_ref'],now=m['now'])


def test_release_predating_runner_amendment_rejected(measured):
    m = measured
    release = copy.deepcopy(m['release'])
    release['issued_at'] = dt.datetime.fromtimestamp(
        p.timestamp(p.MEASUREMENT_CONTRACT['not_before'])-1,dt.timezone.utc).isoformat()
    review = {k:v for k,v in release.items() if k!='root_review'}
    review.update(schema='n36-preparation-root-measurement-review-v1',decision='APPROVED')
    release['root_review'] = put(m['root'],'stale-amendment-review',review)
    ref = m['save'](m['prep']['release_path'],release)
    with pytest.raises(ValueError,match='fresh preparation release'):
        p.validate_release(ref,m['spec'],m['source'],m['source_ref'],now=m['now'])


def rebind_envelope(m, envelope):
    """Rebind every synthetic reference so negative tests reach semantic checks."""
    ref = m['save'](m['proof']['measurement_envelope']['path'], envelope)
    m['proof']['measurement_envelope'] = ref
    events = e.read(m['proof']['accounting'])
    events[-1]['envelope'] = ref
    m['proof']['accounting'] = m['save'](m['prep']['accounting_path'], events)
    for name in ('readiness-preparation-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl'):
        (m['root']/'data'/name).write_text(''.join(json.dumps(v)+'\n' for v in events))
    m['proof_ref'] = m['save'](m['prep']['proof_path'], m['proof'])


@pytest.mark.parametrize('fault', ['missing', 'null', 'pid_type', 'ticks_type', 'boot_type',
    'pid', 'ticks', 'boot', 'launch_parent', 'handle_parent', 'stale_launch', 'late_handle',
    'reordered_lifecycle', 'missing_exit', 'extra_transport', 'request', 'response'])
def test_provider_handle_chain_semantic_rejection(measured, fault):
    m = measured
    envelope = e.read(m['proof']['measurement_envelope'])
    transport = e.read(envelope['transport'])
    handle = e.read(transport['process_handle'])
    launch = e.read(transport['launch_intent'])
    if fault == 'missing': transport.pop('process')
    elif fault == 'null': transport['process'] = None
    elif fault == 'pid_type': transport['process']['pid'] = True
    elif fault == 'ticks_type': transport['process']['proc_start_ticks'] = []
    elif fault == 'boot_type': transport['process']['boot_id'] = 'malformed'
    elif fault == 'pid': transport['process']['pid'] += 1
    elif fault == 'ticks': transport['process']['proc_start_ticks'] = '999'
    elif fault == 'boot': transport['process']['boot_id'] = '00000000-0000-0000-0000-000000000002'
    elif fault == 'launch_parent': launch['parent']['pid'] += 1
    elif fault == 'handle_parent': handle['parent']['pid'] += 1
    elif fault == 'stale_launch': launch['time_unix'] = envelope['started_at'] - 1
    elif fault == 'late_handle': handle['time_unix'] = envelope['finished_at'] + 1
    elif fault == 'reordered_lifecycle': transport['lifecycle']['spawn_returned_at'] = 99
    elif fault == 'missing_exit': transport['lifecycle']['process_exit_observed_at'] = None
    elif fault == 'extra_transport': transport['unbound'] = True
    else: transport[fault]['sha256'] = '0'*64
    transport['launch_intent'] = m['save'](transport['launch_intent']['path'], launch)
    handle['launch_intent'] = transport['launch_intent']
    transport['process_handle'] = m['save'](transport['process_handle']['path'], handle)
    envelope['transport'] = m['save'](envelope['transport']['path'], transport)
    rebind_envelope(m, envelope)
    with pytest.raises((ValueError, e.r.GateError)):
        derive(m)


def test_constructor_interrupted_after_inert_cpu_spawn_keeps_inflight(runner_cpu, monkeypatch):
    import subprocess
    f = runner_cpu
    # No measurement command is invoked: spawn only an inert CPU sleeping child.
    real_popen = subprocess.Popen.__module__  # fixture has already replaced Popen
    assert real_popen == __name__
    import importlib
    # Save the real constructor from a fresh module without changing global state.
    import importlib.util
    spec = importlib.util.spec_from_file_location('synthetic_subprocess', subprocess.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    owned = []
    def interrupt(*args, **kwargs):
        owned.append(module.Popen([sys.executable, '-I', '-S', '-c', 'import time; time.sleep(30)']))
        raise KeyboardInterrupt('SYNTHETIC interruption after inert spawn')
    monkeypatch.setattr(subprocess, 'Popen', interrupt)
    try:
        with pytest.raises(RuntimeError, match='unknown/live'):
            p.execute_preparation(f.ref)
        assert owned[0].poll() is None
        rows = p.journal_rows(f.root)
        assert [x['event'] for x in rows] == ['reserved', 'dispatched']
        assert rows == e.r.read_events(f.root/'data/gpu-healthcheck-ledger.jsonl')
        assert e.r.budget_snapshot([], rows)['gpu_healthcheck_inflight'] == 1
        assert not Path(f.prep['proof_path']).exists()
        other = dict(f.release, resource_id='second_SYNTHETIC')
        with pytest.raises((ValueError, e.r.GateError), match='inflight'):
            p.preparation_budget(f.root, f.plan, f.authority, other)
    finally:
        for child in owned:
            child.terminate()
            child.wait(timeout=5)


@pytest.mark.parametrize('fault', ['before_intent', 'identity', 'admission_file'])
def test_launch_boundary_failure_ownership(runner_cpu, monkeypatch, fault):
    from scripts import qd_ed_n36_runner as runner, qd_ed_n36_source as execution
    f = runner_cpu
    if fault == 'before_intent':
        monkeypatch.setattr(execution, 'command', lambda *a: (_ for _ in ()).throw(RuntimeError('before launch')))
    elif fault == 'identity':
        identify = runner.process_identity
        def broken(pid):
            if pid == 424242: raise RuntimeError('unknown child identity')
            return identify(pid)
        monkeypatch.setattr(runner, 'process_identity', broken)
    else:
        write = p.write_once
        def broken(path, value):
            if Path(path).name == 'child-admitted.json': raise OSError('admission failure')
            return write(path, value)
        monkeypatch.setattr(p, 'write_once', broken)
    with pytest.raises((ValueError, RuntimeError)):
        p.execute_preparation(f.ref)
    rows = p.journal_rows(f.root)
    assert not Path(f.prep['proof_path']).exists()
    if fault == 'before_intent':
        assert not f.launches
        assert rows[-1]['event'] == 'aborted' and rows[-1]['gpu_process_wall_seconds'] == 0
    else:
        assert rows[-1]['event'] == 'dispatched'
        assert e.r.budget_snapshot([], rows)['gpu_healthcheck_inflight'] == 1


def test_preparation_actual_cost_reduces_private_headroom(runner_cpu):
    import yaml
    f = runner_cpu
    margin = .23357169027962
    protected = sum(e.c.CAPS['protected_gpu_hours'].values())
    state = e.r.read_state(f.root/'research-state.yaml')
    state['budget']['max_gpu_hours'] = protected + margin + 61/3600
    (f.root/'research-state.yaml').write_text(yaml.safe_dump(state))
    assert p.preparation_budget(f.root, f.plan, f.authority, f.release)['gpu_hours_consumed'] == 0
    # An earlier failed, distinct synthetic resource keeps the full 90-second
    # overrun. This read-only budget test does not create a release or a retry.
    for kind in ('reserved','dispatched','aborted'):
        p.append_preparation(f.root, resource_event(kind, 'prior_SYNTHETIC', 90 if kind=='aborted' else 0))
    before = (f.root/'data/gpu-healthcheck-ledger.jsonl').read_bytes()
    with pytest.raises((ValueError,e.r.GateError)):
        p.preparation_budget(f.root, f.plan, f.authority, f.release)
    assert (f.root/'data/gpu-healthcheck-ledger.jsonl').read_bytes() == before
    assert e.r.budget_snapshot([], p.journal_rows(f.root))['gpu_hours_consumed'] == 90/3600
