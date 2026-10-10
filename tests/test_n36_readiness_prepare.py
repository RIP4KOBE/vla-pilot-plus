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
    issued = p.timestamp(prep['not_before']) + 1
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
    graph={'native_build':native_ref,'runtime_closure':put(root,'closure',closure)}
    verified=[]
    monkeypatch.setattr(p,'verify_graph',lambda *args: (verified.append(args) or graph))
    receipt_binding={'release':release_ref,'source_record':source_ref,'resource_id':prep['resource_id'],'phase':'preparation_after'}
    proof=dict(schema='n36-measured-preparation-proof-v1', release=release_ref, baseline=spec['canonical_runtime'],
        source_record=source_ref, native_receipt=put(root,'native-receipt',dict(schema='n36-loaded-native-build-v1',manifest=native_ref,libraries=libs)),
        runtime_receipt=put(root,'runtime-receipt',dict(schema='n34-runtime-receipt-v2',binding=receipt_binding,modules=closure['modules'],generated_modules={})),
        runtime_receipt_binding=receipt_binding)
    def bind():
        proof['gpu']=save_path(prep['gpu_path'],gpu)
        proof['provider']=save_path(prep['provider_path'],provider)
        events=[]
        for kind,offset in [('reserved',2),('dispatched',3),('completed',6)]:
            terminal=kind=='completed'
            events.append(dict(common,event=kind,time_unix=issued+offset,reserved_gpu_seconds=60,
                gpu_process_wall_seconds=3 if terminal else 0,provider_calls=1 if terminal else 0,
                exclusive=True,telemetry_complete=True,gpu=proof['gpu'] if terminal else None,
                provider=proof['provider'] if terminal else None))
        proof['accounting']=save_path(prep['accounting_path'],events)
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
