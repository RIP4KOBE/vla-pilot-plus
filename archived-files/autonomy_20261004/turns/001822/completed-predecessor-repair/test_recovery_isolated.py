import copy, hashlib, json
from pathlib import Path
import pytest
RECOVERY_CPU_SOURCE = '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree/scripts/qd_ed_n36_engineering_r1.py'
@pytest.fixture
def recovery_cpu(tmp_path):
    """AST-isolated CPU fixture: no production/native/provider module imports.

    Actual recovery and lifecycle function bodies run against temporary bytes.
    Detached release/proof/acceptance boundaries are synthetic stand-ins; this
    suite asserts those boundaries are reached, never claims graph validation.
    """
    import ast
    import datetime
    import math
    import types
    source = Path(__file__).resolve().parents[1] / 'scripts/qd_ed_n36_engineering_r1.py'
    source = Path(globals().get('RECOVERY_CPU_SOURCE', source))
    module = ast.parse(source.read_text())
    names = {'exact', 'reference', 'read', 'specification', 'preparation_health_suffix', 'resource_events'}
    nodes = [n for n in module.body if isinstance(n, ast.FunctionDef) and (n.name in names or n.name.startswith('_recovery_'))]
    for node in nodes:
        node.body = [n for n in node.body if not isinstance(n, ast.ImportFrom)]

    def require(ok, label):
        if not ok:
            raise ValueError(label)

    def sha(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

    def read_ref(ref):
        path = Path(ref['path'])
        require(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'file reference hash')
        return json.loads(path.read_bytes())
    w = types.SimpleNamespace(require=require, canonical_sha=sha, read_ref=read_ref)
    env = dict(w=w, json=json, hashlib=hashlib, Path=Path, time=types.SimpleNamespace(time=lambda: 1000), HEALTH_ID='health', HEALTH_KIND='engineering_health', EPISODE_KEY='episode', JOURNALS=('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), env)
    e = types.SimpleNamespace(**env)
    data = tmp_path / 'data'
    data.mkdir()

    def put_doc(name, value):
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(value, sort_keys=True, allow_nan=False))
        return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def raw(rows):
        return b''.join((json.dumps(row, sort_keys=True, allow_nan=False).encode() + b'\n' for row in rows))
    baseline = {name: [{'event': 'historical', 'journal': name}] for name in env['JOURNALS']}
    baseline[env['JOURNALS'][0]] = [dict(attempt_id='historical-attempt', event=event, budget_bucket='baseline', gpu_process_wall_seconds=7 if event == 'valid' else 0) for event in ('reserved', 'dispatched', 'valid')]
    baseline[env['JOURNALS'][1]] = [dict(resource_id='historical-health', kind='historical', event=event, gpu_process_wall_seconds=9 if event == 'completed' else 0) for event in ('reserved', 'dispatched', 'completed')]
    original = {}
    for name, rows in baseline.items():
        payload = raw(rows)
        (data / name).write_bytes(payload)
        original[name] = dict(path=str(data / name), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    old = [dict(resource_id='old', kind='readiness_preparation', event=event, telemetry_complete=False if event == 'aborted' else True, gpu_process_wall_seconds=162.0 if event == 'aborted' else 0, provider_calls=1 if event == 'aborted' else 0) for event in ('reserved', 'dispatched', 'aborted')]
    retained_raw = raw(old)
    retained_path = tmp_path / 'retained.jsonl'
    retained_path.write_bytes(retained_raw)
    raw_ref = dict(path=str(retained_path), sha256=hashlib.sha256(retained_raw).hexdigest())
    own_path = data / 'readiness-preparation-ledger.jsonl'
    own_path.write_bytes(retained_raw)
    (data / env['JOURNALS'][1]).write_bytes(raw(baseline[env['JOURNALS'][1]]) + retained_raw)
    observed = {}
    for name in env['JOURNALS']:
        payload = (data / name).read_bytes()
        observed[name] = dict(path=str(data / name), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), prior_prefix_preserved=True)
    offset = original[env['JOURNALS'][1]]['bytes']
    segments = []
    cursor = 0
    for line, row in zip(retained_raw.splitlines(keepends=True), old):
        segments.append(dict(bytes=len(line), event=row['event'], global_start_inclusive=offset + cursor, global_end_exclusive=offset + cursor + len(line), own_start_inclusive=cursor, own_end_exclusive=cursor + len(line), sha256=hashlib.sha256(line).hexdigest()))
        cursor += len(line)
    segment = lambda path, start: dict(path=str(path), start_inclusive=start, end_exclusive=start + len(retained_raw), sha256=raw_ref['sha256'])
    amendment = put_doc('amendment', {'SYNTHETIC': True, 'ledger_prefixes': original})
    snapshot = put_doc('snapshot', {'SYNTHETIC': True})
    identity = put_doc('identity', dict(resource_id='new', recovery_of='old', retained_charge_gpu_hours=162.0 / 3600, source={'commit': 'historical-not-current'}))
    review = put_doc('review', {'SYNTHETIC': True})
    reconciliation = dict(schema='n36-recovery-binding-review-terminal-reconciliation-v1', review=review, live_handles=[], root_accepts_blocking_findings=True, ledger_prefixes=observed)
    contract = dict(schema='n36-failed-readiness-recovery-prefix-contract-v1', accepted_review=review, amendment=amendment, drafting_authority=review, full_ledgers_required_for_budget_snapshots=True, gpu_authorized=False, identity=identity, original_ledger_prefixes=original, own_journal_at_draft=dict(path=str(own_path), bytes=len(retained_raw), sha256=raw_ref['sha256']), predecessor=dict(consumed=True, events=['reserved', 'dispatched', 'aborted'], global_health_segment=segment(data / env['JOURNALS'][1], offset), kind='readiness_preparation', own_journal=segment(own_path, 0), provider_calls_retained=1, raw_bytes=len(retained_raw), raw_sequence=raw_ref, resource_id='old', retained_charge_gpu_hours=162.0 / 3600, retained_charge_gpu_seconds=162.0, row_segments=segments, rows=old, telemetry_complete=False), production_authority=False, provider_measurement_authorized=False, read_semantics=[], release_enabled=False, retained_snapshot_reference=snapshot, root_observed_ledger_prefixes=observed, root_terminal_reconciliation=put_doc('reconciliation', reconciliation), scientific_success=False, status='SYNTHETIC', successor=dict(automatic_retry=False, kind='readiness_preparation', occurrences_in_complete_ledgers={n: 0 for n in (*env['JOURNALS'], 'readiness-preparation-ledger.jsonl')}, resource_id='new', unconsumed_at_draft=True))
    source_doc = {'commit': 'current'}
    source_ref = put_doc('source', source_doc)
    release = dict(source_record=source_ref, baseline=amendment, resource_id='new', source_cwd=str(tmp_path), interpreter={'SYNTHETIC': True}, issued_at='1970-01-01T00:00:10+00:00', expires_at='1970-01-01T00:08:20+00:00', gpu_seconds=600)
    release_ref = put_doc('release', release)
    common = {k: release[k] for k in ('source_record', 'baseline', 'resource_id', 'source_cwd', 'interpreter')}
    common.update(release=release_ref, parent={'pid': 123}, kind='readiness_preparation')
    current = [dict(common, event=event, time_unix=20 + i, reserved_gpu_seconds=600, gpu_process_wall_seconds=2 if i == 2 else 0, provider_calls=1 if i == 2 else 0, exclusive=True, telemetry_complete=True, gpu=None, provider=None, envelope=None, process=None, **{'error': None} if i == 2 else {}) for i, event in enumerate(('reserved', 'dispatched', 'completed'))]
    proof = dict(accounting=put_doc('accounting', current), release=release_ref)
    proof_ref = put_doc('proof', proof)
    runtime = {'preparation': {'readiness_proof': proof_ref}}
    runtime_ref = put_doc('runtime', runtime)
    plan = dict(source=source_doc, runtime=runtime_ref)
    plan_ref = put_doc('plan', plan)
    health = [dict(resource_id='health', kind='engineering_health', event=event, time_unix=30 + i, timeout_seconds=20, cleanup_seconds=40, reserved_gpu_seconds=60, physical_gpu=7, gpu_uuid='synthetic', source_commit='current', runtime=runtime_ref, plan=plan_ref, release=release_ref, accounting_admission={'reserved_gpu_seconds': 60}, gpu_process_wall_seconds=1 if i == 2 else 0) for i, event in enumerate(('reserved', 'dispatched', 'completed'))]
    policy = dict(resource_id='new', proof_path=proof_ref['path'])
    spec = dict(prospective_amendment=amendment, readiness_recovery=identity, retained_ledger_prefixes=original, retained_snapshot_reference=snapshot, runtime_binding={'source_record_path': source_ref['path'], 'preparation': put_doc('policy', policy)}, recovery_prefix_contract=put_doc('contract', contract))
    calls = []

    def number(value, label):
        require(type(value) in (int, float) and math.isfinite(value) and (value >= 0), label)
        return value

    def closed(value, keys, label):
        require(set(value) == set(keys), label)

    def accepted(*args):
        calls.append('accepted')

    def derive(*args):
        calls.append('derive')
        return runtime
    preparation = types.SimpleNamespace(policy=lambda spec: policy, journal_rows=lambda root: e._recovery_rows(own_path.read_bytes()), validate_release=lambda *args, **kwargs: release, owned_identity=lambda value: value, timestamp=lambda value: datetime.datetime.fromisoformat(value).timestamp(), number=number, closed=closed, pinned=lambda ref, path: read_ref(ref), derive=derive, accepted=accepted)
    env.update(AMENDMENT=amendment, SPECIFICATION=put_doc('spec', spec), preparation=preparation, terminal_parent_prefix=lambda: copy.deepcopy(baseline), owner_root=lambda plan: tmp_path, operational_binding=lambda plan: {}, c=types.SimpleNamespace(GPU_UUID='synthetic', finite=number))
    runner_tree = ast.parse((source.parent / 'qd_ed_final_runner.py').read_text())
    budget_env = dict(require=require, math=math, TERMINAL={'valid', 'aborted'}, BUCKETS={'baseline': 20, 'development': 100, 'validation': 60, 'formal': 40, 'recovery': 20})
    exec(compile(ast.Module(body=[n for n in runner_tree.body if isinstance(n, ast.FunctionDef) and n.name in {'event_groups', 'budget_snapshot'}], type_ignores=[]), str(source.parent / 'qd_ed_final_runner.py'), 'exec'), budget_env)
    e.r = types.SimpleNamespace(budget_snapshot=budget_env['budget_snapshot'], read_events=lambda path: e._recovery_rows(Path(path).read_bytes()))
    prepare_tree = ast.parse((source.parent / 'qd_ed_n36_readiness_prepare.py').read_text())
    own_node = next((n for n in prepare_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'journal_rows'))
    own_env = dict(e=e, Path=Path, MEASUREMENT_CONTRACT={'journal': 'readiness-preparation-ledger.jsonl'})
    exec(compile(ast.Module(body=[own_node], type_ignores=[]), str(source.parent / 'qd_ed_n36_readiness_prepare.py'), 'exec'), own_env)
    preparation.journal_rows = own_env['journal_rows']
    resources = []

    def sync():
        resources[:] = copy.deepcopy(baseline[env['JOURNALS'][1]]) + copy.deepcopy(old) + copy.deepcopy(current) + copy.deepcopy(health)
        own_path.write_bytes(retained_raw + raw(current))
        (data / env['JOURNALS'][1]).write_bytes(raw(baseline[env['JOURNALS'][1]]) + retained_raw + raw(current) + raw(health))

    def repin():
        spec['recovery_prefix_contract'] = put_doc('contract', contract)
        env['SPECIFICATION'] = put_doc('spec', spec)
        env['HISTORICAL_SPECIFICATION'] = env['SPECIFICATION']
    env['HISTORICAL_SPECIFICATION'] = env['SPECIFICATION']
    sync()
    return types.SimpleNamespace(e=e, env=env, root=tmp_path, data=data, baseline=baseline, resources=resources, contract=contract, spec=spec, old=old, current=current, health=health, own=own_path, raw=raw, retained_raw=retained_raw, plan=plan, calls=calls, sync=sync, repin=repin, put=put_doc, preparation=preparation)

def test_recovery_cpu_positive_and_initial_use(recovery_cpu):
    f = recovery_cpu
    before = copy.deepcopy((f.resources, f.baseline))
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == f.health
    assert f.calls == ['derive', 'accepted']
    assert (f.resources, f.baseline) == before
    assert f.resources[len(f.baseline[f.env['JOURNALS'][1]]) + 2]['telemetry_complete'] is False
    assert f.resources[len(f.baseline[f.env['JOURNALS'][1]]) + 2]['gpu_process_wall_seconds'] == 162.0
    f.current.clear()
    f.health.clear()
    f.sync()
    assert f.e.specification() == f.spec
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == []

@pytest.mark.parametrize('fault', ['spacing', 'value', 'missing', 'torn', 'reordered', 'replayed', 'unfinished', 'unknown', 'foreign', 'old_reuse', 'duplicate_successor', 'partial_mirror', 'current_spacing', 'health_before', 'contract_hash', 'reconciliation_hash', 'review_hash', 'extra_contract_key', 'null_contract', 'parsed_resources', 'baseline', 'offset', 'row_hash', 'symlink', 'duplicate_key', 'nonfinite', 'successor_attempt', 'successor_reservation'])
def test_recovery_cpu_rejects_prefix_and_binding_faults(recovery_cpu, fault):
    f = recovery_cpu
    global_path = f.data / f.env['JOURNALS'][1]
    if fault in ('spacing', 'value', 'missing', 'torn', 'reordered', 'replayed', 'unfinished', 'unknown'):
        payload = f.retained_raw
        if fault == 'spacing':
            payload = payload.replace(b': ', b':', 1)
        elif fault == 'value':
            payload = payload.replace(b'162.0', b'163.0')
        elif fault == 'missing':
            payload = b''
        elif fault == 'torn':
            payload = payload[:-1]
        elif fault == 'reordered':
            payload = b''.join(reversed(payload.splitlines(keepends=True)))
        elif fault == 'replayed':
            payload += payload
        elif fault == 'unfinished':
            payload = b''.join(payload.splitlines(keepends=True)[:2])
        elif fault == 'unknown':
            payload = payload.replace(b'aborted', b'unknown')
        f.own.write_bytes(payload + f.raw(f.current))
        global_path.write_bytes(f.raw(f.baseline[f.env['JOURNALS'][1]]) + payload + f.raw(f.current) + f.raw(f.health))
    elif fault in ('foreign', 'old_reuse'):
        f.current[0]['resource_id'] = 'foreign' if fault == 'foreign' else 'old'
        f.sync()
    elif fault == 'duplicate_successor':
        f.current.extend(copy.deepcopy(f.current))
        f.sync()
    elif fault == 'partial_mirror':
        f.own.write_bytes(f.retained_raw + f.raw(f.current[:-1]))
    elif fault == 'current_spacing':
        f.own.write_bytes(f.retained_raw + f.raw(f.current).replace(b': ', b':', 1))
    elif fault == 'health_before':
        f.health[0]['time_unix'] = 21
        f.sync()
    elif fault == 'contract_hash':
        Path(f.spec['recovery_prefix_contract']['path']).write_text('{}')
    elif fault == 'reconciliation_hash':
        Path(f.contract['root_terminal_reconciliation']['path']).write_text('{}')
    elif fault == 'review_hash':
        Path(f.contract['accepted_review']['path']).write_text('{}')
    elif fault == 'extra_contract_key':
        f.contract['unknown'] = True
        f.repin()
    elif fault == 'null_contract':
        f.spec['recovery_prefix_contract'] = None
        f.env['SPECIFICATION'] = f.put('spec', f.spec)
    elif fault == 'parsed_resources':
        f.resources.pop()
    elif fault == 'baseline':
        f.baseline[f.env['JOURNALS'][1]][0]['event'] = 'changed'
    elif fault == 'offset':
        f.contract['predecessor']['global_health_segment']['start_inclusive'] += 1
        f.repin()
    elif fault == 'row_hash':
        f.contract['predecessor']['row_segments'][0]['sha256'] = '0' * 64
        f.repin()
    elif fault == 'symlink':
        target = f.root / 'own-copy'
        target.write_bytes(f.own.read_bytes())
        f.own.unlink()
        f.own.symlink_to(target)
    elif fault in ('duplicate_key', 'nonfinite'):
        extra = b'{"x":1,"x":2}\n' if fault == 'duplicate_key' else b'{"x":1e999}\n'
        global_path.write_bytes(global_path.read_bytes() + extra)
    elif fault in ('successor_attempt', 'successor_reservation'):
        name = f.env['JOURNALS'][0 if fault == 'successor_attempt' else 2]
        path = f.data / name
        path.write_bytes(path.read_bytes() + f.raw([{'resource_id': 'new'}]))
    with pytest.raises((ValueError, KeyError, TypeError)):
        f.e.preparation_health_suffix(f.plan, f.baseline, f.resources)

@pytest.mark.parametrize('fault', ['pending', 'unknown', 'aborted', 'overrun', 'reorder', 'release', 'source', 'baseline', 'parent', 'extra_key', 'reservation', 'timestamp', 'expired', 'preterminal_charge', 'provider_calls', 'admission_telemetry', 'accounting', 'acceptance', 'health_replay'])
def test_recovery_cpu_preserves_current_lifecycle_rejections(recovery_cpu, fault):
    f = recovery_cpu
    if fault == 'pending':
        f.current.pop()
    elif fault == 'unknown':
        f.current[-1]['event'] = 'unknown'
    elif fault in ('aborted', 'overrun'):
        f.current[-1].update(event='aborted', gpu_process_wall_seconds=900 if fault == 'overrun' else 2, telemetry_complete=False, exclusive=False)
    elif fault == 'reorder':
        f.current[0], f.current[1] = (f.current[1], f.current[0])
    elif fault in ('release', 'source', 'baseline'):
        key = 'source_record' if fault == 'source' else fault
        f.current[-1][key] = {'path': '/SYNTHETIC', 'sha256': '0' * 64}
    elif fault == 'parent':
        f.current[-1]['parent'] = {'pid': 456}
    elif fault == 'extra_key':
        f.current[-1]['unknown'] = True
    elif fault == 'reservation':
        f.current[-1]['reserved_gpu_seconds'] = 601
    elif fault == 'timestamp':
        f.current[-1]['time_unix'] = 19
    elif fault == 'expired':
        f.current[-1]['time_unix'] = 600
    elif fault == 'preterminal_charge':
        f.current[0]['gpu_process_wall_seconds'] = 1
    elif fault == 'provider_calls':
        f.current[-1]['provider_calls'] = True
    elif fault == 'admission_telemetry':
        f.current[0]['telemetry_complete'] = False
    elif fault == 'accounting':
        f.current[-1]['gpu_process_wall_seconds'] = 3
    elif fault == 'acceptance':

        def reject(*args):
            raise ValueError('synthetic detached acceptance rejected')
        f.preparation.accepted = reject
    elif fault == 'health_replay':
        f.health.extend(copy.deepcopy(f.health))
    f.sync()
    reason = {'pending': 'unsettled/unknown/replayed', 'unknown': 'unknown GPU healthcheck event', 'aborted': 'failed preparation requires', 'overrun': 'failed preparation requires', 'reorder': 'illegal attempt transition', 'release': 'immutable preparation release', 'source': 'immutable preparation release', 'baseline': 'immutable preparation release', 'parent': 'immutable preparation parent', 'extra_key': 'strict preparation event', 'reservation': 'preparation finite reservation', 'timestamp': 'ordered preparation timestamps', 'expired': 'preparation release event expiry', 'preterminal_charge': 'preparation preterminal evidence', 'provider_calls': 'preparation one provider call', 'admission_telemetry': 'preparation admission telemetry', 'accounting': 'accepted proof exact preparation accounting', 'acceptance': 'synthetic detached acceptance rejected', 'health_replay': 'engineering one-use health lifecycle'}[fault]
    with pytest.raises(ValueError, match=reason):
        f.e.preparation_health_suffix(f.plan, f.baseline, f.resources)

def test_recovery_cpu_absence_keeps_old_behavior(recovery_cpu):
    f = recovery_cpu
    del f.spec['recovery_prefix_contract']
    f.env['SPECIFICATION'] = f.put('spec', f.spec)
    f.env['HISTORICAL_SPECIFICATION'] = f.env['SPECIFICATION']
    with pytest.raises(ValueError, match='foreign resource'):
        f.e.preparation_health_suffix(f.plan, f.baseline, f.resources)
    f.resources[:] = f.baseline[f.env['JOURNALS'][1]] + f.current + f.health
    f.own.write_bytes(f.raw(f.current))
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == f.health

def test_recovery_cpu_complete_budget_and_initial_replay(recovery_cpu):
    """Execute real pure budget/admission bodies, with synthetic authority gates."""
    import ast
    import math
    import types
    f = recovery_cpu
    source = Path(globals().get('RECOVERY_CPU_SOURCE', Path(__file__).resolve().parents[1] / 'scripts/qd_ed_n36_engineering_r1.py'))
    runner = ast.parse((source.parent / 'qd_ed_final_runner.py').read_text())
    names = {'budget_snapshot', 'event_groups'}
    budget_env = dict(require=f.env['w'].require, math=math, TERMINAL={'valid', 'aborted'}, BUCKETS={'baseline': 20, 'development': 100, 'validation': 60, 'formal': 40, 'recovery': 20})
    exec(compile(ast.Module(body=[n for n in runner.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[]), str(source.parent / 'qd_ed_final_runner.py'), 'exec'), budget_env)
    snapshot = budget_env['budget_snapshot']
    retained_seconds = sum((x['gpu_process_wall_seconds'] for x in f.old))
    full = snapshot(f.baseline[f.env['JOURNALS'][0]], f.resources)
    assert full['gpu_hours_consumed'] == pytest.approx((7 + 9 + retained_seconds + 2 + 1) / 3600)
    assert full['gpu_hours_by_bucket']['recovery'] == pytest.approx((9 + retained_seconds + 2 + 1) / 3600)
    assert snapshot([], f.health)['gpu_hours_consumed'] == pytest.approx(1 / 3600)
    before = copy.deepcopy(f.resources)
    f.e.preparation_health_suffix(f.plan, f.baseline, f.resources)
    assert f.resources == before
    assert snapshot(f.baseline[f.env['JOURNALS'][0]], f.resources) == full
    preparation_path = source.parent / 'qd_ed_n36_readiness_prepare.py'
    tree = ast.parse(preparation_path.read_text())
    body = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'preparation_budget'))
    body.body = [n for n in body.body if not isinstance(n, ast.ImportFrom)]
    authority = dict(ledger_prefixes=f.spec['retained_ledger_prefixes'], retained_snapshot=snapshot(*(f.baseline[n] for n in f.env['JOURNALS'][:2])), caps={'buckets': {}, 'protected_gpu_hours': {}}, amendment={}, margin_reference={})
    release = dict(accounting_authority={}, expires_at='SYNTHETIC', gpu_seconds=600, resource_id='new')

    def state_snapshot(root, auth):
        rows = [f.e._recovery_rows((f.data / name).read_bytes()) for name in f.env['JOURNALS']]
        return ({'budget': dict(snapshot(*rows[:2]), max_gpu_hours=100)}, *rows)
    f.e.JOURNALS = f.env['JOURNALS']
    f.e.stop = types.SimpleNamespace(check=lambda **kwargs: None)
    f.e.accounting = types.SimpleNamespace(ABSOLUTE_HOURS=100, WEEKLY_HOURS=100, retained_margin=lambda *args: 0)
    f.e.r = types.SimpleNamespace(**{name: budget_env[name] for name in names}, TERMINAL={'valid', 'aborted'}, check_budget_limits=lambda *args, **kwargs: 1000, read_events=lambda path: f.e._recovery_rows(Path(path).read_bytes()))
    initial_env = dict(e=f.e, Path=Path, json=json, owner=types.SimpleNamespace(snapshot=state_snapshot), validate_preparation_authority=lambda *args: authority, validate_preparation_state=lambda *args: None, journal_rows=f.preparation.journal_rows, number=f.preparation.number, MEASUREMENT_CONTRACT={'cleanup_seconds': 40})
    exec(compile(ast.Module(body=[body], type_ignores=[]), str(preparation_path), 'exec'), initial_env)
    with pytest.raises(ValueError, match='global preparation identity replay'):
        initial_env['preparation_budget'](f.root, f.plan, authority, release)
    f.current.clear()
    f.health.clear()
    f.sync()
    initial = initial_env['preparation_budget'](f.root, f.plan, authority, release)
    assert initial['gpu_hours_consumed'] == pytest.approx((7 + 9 + retained_seconds) / 3600)
    for name in (*f.env['JOURNALS'], 'readiness-preparation-ledger.jsonl'):
        path = f.data / name
        saved = path.read_bytes()
        path.write_bytes(saved + f.raw([{'resource_id': 'new', 'kind': 'readiness_preparation', 'event': 'reserved'}]))
        with pytest.raises(ValueError):
            initial_env['preparation_budget'](f.root, f.plan, authority, release)
        path.write_bytes(saved)

@pytest.fixture
def recovery_multi_cpu(recovery_cpu):
    """Two charged aborted lifecycles, immutable bytes, no real evidence reads."""
    f = recovery_cpu
    first = copy.deepcopy(f.contract.pop('predecessor'))
    second = copy.deepcopy(first)
    second['resource_id'] = 'old-two'
    for row in second['rows']:
        row['resource_id'] = 'old-two'
    second['rows'][-1].update(gpu_process_wall_seconds=81.0, provider_calls=None)
    second.update(retained_charge_gpu_seconds=81.0, retained_charge_gpu_hours=81.0 / 3600, provider_calls_retained=None)
    payload = f.raw(second['rows'])
    path = f.root / 'second-retained.jsonl'
    path.write_bytes(payload)
    second['raw_sequence'] = dict(path=str(path), sha256=hashlib.sha256(payload).hexdigest())
    second['raw_bytes'] = len(payload)
    start = len(f.retained_raw)
    offset = f.contract['original_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes']
    for key, begin in [('own_journal', start), ('global_health_segment', offset + start)]:
        second[key].update(start_inclusive=begin, end_exclusive=begin + len(payload), sha256=second['raw_sequence']['sha256'])
    second['row_segments'] = []
    cursor = start
    for row, line in zip(second['rows'], payload.splitlines(keepends=True)):
        second['row_segments'].append(dict(bytes=len(line), event=row['event'], global_start_inclusive=offset + cursor, global_end_exclusive=offset + cursor + len(line), own_start_inclusive=cursor, own_end_exclusive=cursor + len(line), sha256=hashlib.sha256(line).hexdigest()))
        cursor += len(line)
    f.contract.update(schema='n36-failed-readiness-recovery-prefix-contract-v2', predecessors=[first, second])
    identity = f.e.read(f.contract['identity'])
    identity.update(recovery_of=['old', 'old-two'], retained_charge_gpu_hours=162.0 / 3600 + 81.0 / 3600)
    f.contract['identity'] = f.spec['readiness_recovery'] = f.put('multi-identity', identity)
    f.retained_raw += payload
    f.old.extend(second['rows'])
    f.contract['own_journal_at_draft'].update(bytes=len(f.retained_raw), sha256=hashlib.sha256(f.retained_raw).hexdigest())
    observed = f.contract['root_observed_ledger_prefixes']
    prefix = f.raw(f.baseline[f.env['JOURNALS'][1]]) + f.retained_raw
    observed[f.env['JOURNALS'][1]].update(bytes=len(prefix), sha256=hashlib.sha256(prefix).hexdigest())
    reconciliation = f.e.read(f.contract['root_terminal_reconciliation'])
    reconciliation['ledger_prefixes'] = observed
    f.contract['root_terminal_reconciliation'] = f.put('multi-reconciliation', reconciliation)

    def sync():
        f.resources[:] = copy.deepcopy(f.baseline[f.env['JOURNALS'][1]] + f.old + f.current + f.health)
        f.own.write_bytes(f.retained_raw + f.raw(f.current))
        (f.data / f.env['JOURNALS'][1]).write_bytes(prefix + f.raw(f.current) + f.raw(f.health))
    f.sync = sync
    f.sync()
    f.repin()
    return f

def test_recovery_multi_cpu_preserves_both_costs_and_unknowns(recovery_multi_cpu):
    f = recovery_multi_cpu
    before = {p: p.read_bytes() for p in f.data.iterdir()}
    assert f.e.specification() == f.spec
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == f.health
    snap = f.e.r.budget_snapshot(f.baseline[f.env['JOURNALS'][0]], f.resources)
    assert snap['gpu_hours_consumed'] == pytest.approx((7 + 9 + 162 + 81 + 2 + 1) / 3600)
    assert f.old[-1]['provider_calls'] is None
    assert f.old[-1]['telemetry_complete'] is False
    assert {p: p.read_bytes() for p in f.data.iterdir()} == before
    test_recovery_cpu_complete_budget_and_initial_replay(f)

@pytest.mark.parametrize('fault', ['missing_first', 'missing_second', 'reverse', 'duplicate', 'second_bytes', 'second_own_offset', 'second_global_offset', 'second_row_offset', 'second_row_hash', 'second_charge', 'aggregate_charge', 'telemetry', 'provider_unknown', 'consumed_successor', 'foreign', 'first_replay', 'second_replay', 'truncated_own', 'original_offset', 'observed_offset', 'identity_order', 'raw_hash'])
def test_recovery_multi_cpu_rejects_faults(recovery_multi_cpu, fault):
    f = recovery_multi_cpu
    predecessors = f.contract['predecessors']
    second = predecessors[1]
    if fault == 'missing_first':
        predecessors.pop(0)
    elif fault == 'missing_second':
        predecessors.pop()
    elif fault == 'reverse':
        predecessors.reverse()
    elif fault == 'duplicate':
        predecessors.append(copy.deepcopy(second))
    elif fault == 'second_bytes':
        f.own.write_bytes(f.own.read_bytes().replace(b'81.0', b'82.0'))
    elif fault == 'second_own_offset':
        second['own_journal']['start_inclusive'] = 0
    elif fault == 'second_global_offset':
        second['global_health_segment']['start_inclusive'] += 1
    elif fault == 'second_row_offset':
        second['row_segments'][0]['own_start_inclusive'] = 0
    elif fault == 'second_row_hash':
        second['row_segments'][0]['sha256'] = '0' * 64
    elif fault == 'second_charge':
        second['retained_charge_gpu_seconds'] = 0
    elif fault in ('aggregate_charge', 'identity_order'):
        identity = f.e.read(f.contract['identity'])
        if fault == 'aggregate_charge':
            identity['retained_charge_gpu_hours'] = 81.0 / 3600
        else:
            identity['recovery_of'].reverse()
        f.spec['readiness_recovery'] = f.contract['identity'] = f.put('multi-identity', identity)
    elif fault == 'telemetry':
        second['telemetry_complete'] = True
    elif fault == 'provider_unknown':
        second['provider_calls_retained'] = 0
    elif fault == 'consumed_successor':
        f.contract['successor']['resource_id'] = 'old-two'
    elif fault in ('foreign', 'first_replay', 'second_replay'):
        f.current[0]['resource_id'] = {'foreign': 'foreign', 'first_replay': 'old', 'second_replay': 'old-two'}[fault]
        f.sync()
    elif fault == 'truncated_own':
        f.own.write_bytes(f.own.read_bytes()[:len(f.retained_raw) - 1])
    elif fault == 'original_offset':
        f.contract['original_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes'] += 1
    elif fault == 'observed_offset':
        f.contract['root_observed_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes'] -= 1
    elif fault == 'raw_hash':
        second['raw_sequence']['sha256'] = '0' * 64
    f.repin()
    with pytest.raises((ValueError, KeyError, TypeError)):
        f.e.preparation_health_suffix(f.plan, f.baseline, f.resources)

@pytest.mark.parametrize('fault', [None, 'science', 'limits', 'amendment', 'old_identity', 'lineage', 'spec_hash', 'policy_hash', 'old_path', 'extra_key', 'v1'])
def test_recovery_prospective_cpu_specification(recovery_multi_cpu, fault):
    f = recovery_multi_cpu
    historical = copy.deepcopy(f.spec)
    historical['scope'] = {'threshold': 0.7}
    historical['runtime_binding'].update(runtime_path='/synthetic/old-runtime', source_record_path='/synthetic/old-source')
    historical['runtime_binding']['preparation'] = f.put('historical-policy', {'resource_id': 'old-two', 'proof_path': '/synthetic/old-proof', 'previous_specification': {}, 'deadline': 'unchanged'})
    historical['readiness_recovery'] = f.put('historical-identity', {'resource_id': 'old-two'})
    historical['recovery_prefix_contract'] = f.put('historical-contract', {'historical': True})
    historical_ref = f.put('historical-spec', historical)
    f.spec['scope'] = historical['scope'].copy()
    f.spec['runtime_binding']['runtime_path'] = '/synthetic/new-runtime'
    policy = f.e.read(f.spec['runtime_binding']['preparation'])
    policy['previous_specification'] = historical_ref
    policy['deadline'] = 'unchanged'
    if fault == 'science':
        f.spec['scope']['threshold'] = 0.8
    elif fault == 'limits':
        f.spec['runtime_binding']['measurement_contract'] = {'cleanup_seconds': 0}
    elif fault == 'amendment':
        f.spec['prospective_amendment'] = f.put('foreign-amendment', {})
    elif fault == 'old_identity':
        policy['resource_id'] = 'old-two'
    elif fault == 'lineage':
        policy['previous_specification'] = f.put('foreign-spec', {})
    elif fault == 'extra_key':
        f.spec['approval'] = True
    elif fault == 'v1':
        f.contract['schema'] = 'n36-failed-readiness-recovery-prefix-contract-v1'
        f.contract['predecessor'] = f.contract.pop('predecessors')[0]
    f.spec['runtime_binding']['preparation'] = f.put('fresh-policy', policy)
    f.repin()
    f.env['HISTORICAL_SPECIFICATION'] = historical_ref
    if fault == 'spec_hash':
        f.env['SPECIFICATION']['sha256'] = '0' * 64
    elif fault == 'policy_hash':
        Path(f.spec['runtime_binding']['preparation']['path']).write_text('{}')
    elif fault == 'old_path':
        f.env['SPECIFICATION']['path'] = historical_ref['path']
    if fault is None:
        before = Path(historical_ref['path']).read_bytes()
        assert f.e.specification() == f.spec
        assert Path(historical_ref['path']).read_bytes() == before
    else:
        with pytest.raises((ValueError, KeyError, TypeError)):
            f.e.specification()

def test_recovery_prospective_cpu_process_selection(recovery_cpu):
    import ast
    import types
    f = recovery_cpu
    source = Path(globals().get('RECOVERY_CPU_SOURCE', Path(__file__).resolve().parents[1] / 'scripts/qd_ed_n36_engineering_r1.py'))
    tree = ast.parse(source.read_text())
    assignment = next((n for n in tree.body if isinstance(n, ast.Assign) and any((isinstance(t, ast.Name) and t.id == 'SPECIFICATION' for t in n.targets))))
    historical = f.env['SPECIFICATION']
    selected = {'path': '/synthetic/fresh.json', 'sha256': '1' * 64}
    for environ, expected in [({}, historical), ({'QD_ED_N36_R1_SPECIFICATION': json.dumps(selected)}, selected)]:
        env = dict(os=types.SimpleNamespace(environ=environ), json=json, HISTORICAL_SPECIFICATION=historical)
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(source), 'exec'), env)
        assert env['SPECIFICATION'] == expected
    child = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'child_environment'))
    env = dict(owner_root=lambda plan: None, r=types.SimpleNamespace(child_environment=lambda rt: {'QD_ED_N36_R1_SPECIFICATION': 'foreign environment mutation'}), SOURCE=f.root, SPECIFICATION=selected, reference=f.e.reference, json=json)
    exec(compile(ast.Module(body=[child], type_ignores=[]), str(source), 'exec'), env)
    assert json.loads(env['child_environment']({}, {})['QD_ED_N36_R1_SPECIFICATION']) == selected

def repin_terminal_partition(f):
    """Build authenticated SYNTHETIC bytes, including deliberately invalid rows."""
    offset = f.contract['original_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes']
    retained = b''
    f.old.clear()
    for i, predecessor in enumerate(f.contract['predecessors']):
        payload = f.raw(predecessor['rows'])
        path = f.root / f'terminal-retained-{i}.jsonl'
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        predecessor.update(raw_bytes=len(payload), raw_sequence=dict(path=str(path), sha256=digest))
        start = len(retained)
        for key, begin in [('own_journal', start), ('global_health_segment', offset + start)]:
            predecessor[key].update(start_inclusive=begin, end_exclusive=begin + len(payload), sha256=digest)
        predecessor['row_segments'] = []
        cursor = start
        for row, line in zip(predecessor['rows'], payload.splitlines(keepends=True)):
            predecessor['row_segments'].append(dict(bytes=len(line), event=row['event'], global_start_inclusive=offset + cursor, global_end_exclusive=offset + cursor + len(line), own_start_inclusive=cursor, own_end_exclusive=cursor + len(line), sha256=hashlib.sha256(line).hexdigest()))
            cursor += len(line)
        retained += payload
        f.old.extend(predecessor['rows'])
    f.retained_raw = retained
    f.contract['own_journal_at_draft'].update(bytes=len(retained), sha256=hashlib.sha256(retained).hexdigest())
    prefix = f.raw(f.baseline[f.env['JOURNALS'][1]]) + retained
    observed = f.contract['root_observed_ledger_prefixes']
    observed[f.env['JOURNALS'][1]].update(bytes=len(prefix), sha256=hashlib.sha256(prefix).hexdigest())
    reconciliation = f.e.read(f.contract['root_terminal_reconciliation'])
    reconciliation['ledger_prefixes'] = observed
    f.contract['root_terminal_reconciliation'] = f.put('terminal-reconciliation', reconciliation)
    identity = f.e.read(f.contract['identity'])
    identity.update(recovery_of=[p['resource_id'] for p in f.contract['predecessors']], retained_charge_gpu_hours=sum((p['retained_charge_gpu_hours'] for p in f.contract['predecessors'])))
    f.contract['identity'] = f.spec['readiness_recovery'] = f.put('terminal-identity', identity)

    def sync():
        f.resources[:] = copy.deepcopy(f.baseline[f.env['JOURNALS'][1]] + f.old + f.current + f.health)
        f.own.write_bytes(f.retained_raw + f.raw(f.current))
        (f.data / f.env['JOURNALS'][1]).write_bytes(prefix + f.raw(f.current) + f.raw(f.health))
    f.sync = sync
    f.sync()
    f.repin()

@pytest.fixture
def recovery_terminal_cpu(recovery_multi_cpu):
    """Two aborted/incomplete and one completed/complete, with all costs retained."""
    f = recovery_multi_cpu
    f.contract['schema'] = 'n36-readiness-recovery-prefix-contract-v3'
    for p in f.contract['predecessors']:
        p['terminal_status'] = 'aborted'
    completed = copy.deepcopy(f.contract['predecessors'][-1])
    completed.update(resource_id='old-three', terminal_status='completed', events=['reserved', 'dispatched', 'completed'], telemetry_complete=True, provider_calls_retained=1, retained_charge_gpu_seconds=234.72371816635132, retained_charge_gpu_hours=234.72371816635132 / 3600)
    for row in completed['rows']:
        row['resource_id'] = completed['resource_id']
    completed['rows'][-1].update(event='completed', telemetry_complete=True, provider_calls=1, gpu_process_wall_seconds=completed['retained_charge_gpu_seconds'])
    f.contract['predecessors'].append(completed)
    repin_terminal_partition(f)
    return f

def test_recovery_terminal_cpu_partition_and_budget(recovery_terminal_cpu):
    f = recovery_terminal_cpu
    before = {p: p.read_bytes() for p in f.data.iterdir()}
    assert f.e.specification() == f.spec
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == f.health
    assert f.calls == ['derive', 'accepted']
    terminals = f.old[2::3]
    assert [r['event'] for r in terminals] == ['aborted', 'aborted', 'completed']
    assert [r['telemetry_complete'] for r in terminals] == [False, False, True]
    assert terminals[1]['provider_calls'] is None
    assert {p: p.read_bytes() for p in f.data.iterdir()} == before
    test_recovery_cpu_complete_budget_and_initial_replay(f)

@pytest.mark.parametrize('fault', ['missing_status', 'unknown_status', 'false_status', 'false_events', 'false_telemetry', 'bool_as_int', 'abort_complete', 'raw_status', 'raw_telemetry', 'raw_bool_as_int', 'unknown_provider', 'bool_provider', 'uncharged', 'negative_charge', 'false_charge', 'duplicate_identity', 'missing_raw_row', 'reordered_raw_rows', 'extra_raw_row', 'legacy_v2', 'unknown_schema'])
def test_recovery_terminal_cpu_semantics(recovery_terminal_cpu, fault):
    f = recovery_terminal_cpu
    completed = f.contract['predecessors'][-1]
    terminal = completed['rows'][-1]
    rebuild = False
    if fault == 'missing_status':
        completed.pop('terminal_status')
    elif fault == 'unknown_status':
        completed['terminal_status'] = 'valid'
    elif fault == 'false_status':
        completed['terminal_status'] = 'aborted'
    elif fault == 'false_events':
        completed['events'][-1] = 'aborted'
    elif fault == 'false_telemetry':
        completed['telemetry_complete'] = False
    elif fault == 'bool_as_int':
        completed['telemetry_complete'] = 1
    elif fault == 'abort_complete':
        f.contract['predecessors'][0]['telemetry_complete'] = True
    elif fault == 'raw_status':
        terminal['event'] = 'aborted'
        rebuild = True
    elif fault == 'raw_telemetry':
        terminal['telemetry_complete'] = False
        rebuild = True
    elif fault == 'raw_bool_as_int':
        terminal['telemetry_complete'] = 1
        rebuild = True
    elif fault in ('unknown_provider', 'bool_provider'):
        terminal['provider_calls'] = completed['provider_calls_retained'] = None if fault == 'unknown_provider' else True
        rebuild = True
    elif fault in ('uncharged', 'negative_charge'):
        charge = 0.0 if fault == 'uncharged' else -1.0
        terminal['gpu_process_wall_seconds'] = completed['retained_charge_gpu_seconds'] = charge
        completed['retained_charge_gpu_hours'] = charge / 3600
        rebuild = True
    elif fault == 'false_charge':
        completed['retained_charge_gpu_seconds'] = 0.0
    elif fault == 'duplicate_identity':
        completed['resource_id'] = 'old'
    elif fault == 'missing_raw_row':
        completed['rows'].pop(1)
        rebuild = True
    elif fault == 'reordered_raw_rows':
        completed['rows'].reverse()
        rebuild = True
    elif fault == 'extra_raw_row':
        completed['rows'].append(copy.deepcopy(terminal))
        rebuild = True
    elif fault == 'legacy_v2':
        f.contract['schema'] = 'n36-failed-readiness-recovery-prefix-contract-v2'
        for p in f.contract['predecessors']:
            p.pop('terminal_status')
    elif fault == 'unknown_schema':
        f.contract['schema'] = 'n36-readiness-recovery-prefix-contract-v4'
    if rebuild:
        repin_terminal_partition(f)
    else:
        f.repin()
    with pytest.raises(ValueError):
        f.e.specification()

@pytest.mark.parametrize('fault', ['missing_first', 'missing_second', 'reverse', 'duplicate', 'second_bytes', 'second_own_offset', 'second_global_offset', 'second_row_offset', 'second_row_hash', 'second_charge', 'aggregate_charge', 'telemetry', 'provider_unknown', 'consumed_successor', 'foreign', 'first_replay', 'second_replay', 'truncated_own', 'original_offset', 'observed_offset', 'identity_order', 'raw_hash'])
def test_recovery_terminal_cpu_partition_faults(recovery_terminal_cpu, fault):
    test_recovery_multi_cpu_rejects_faults(recovery_terminal_cpu, fault)

@pytest.mark.parametrize('fault', ['pending', 'aborted', 'reorder', 'release', 'source', 'reservation', 'preterminal_charge', 'provider_calls', 'admission_telemetry', 'accounting', 'acceptance', 'health_replay'])
def test_recovery_terminal_cpu_successor_gates(recovery_terminal_cpu, fault):
    test_recovery_cpu_preserves_current_lifecycle_rejections(recovery_terminal_cpu, fault)

@pytest.mark.parametrize('fault', ['partial_mirror', 'current_spacing', 'health_before', 'successor_attempt', 'successor_reservation', 'duplicate_successor'])
def test_recovery_terminal_cpu_mirror_gates(recovery_terminal_cpu, fault):
    test_recovery_cpu_rejects_prefix_and_binding_faults(recovery_terminal_cpu, fault)

@pytest.mark.parametrize('fault', [None, 'science', 'limits', 'amendment', 'old_identity', 'lineage', 'spec_hash', 'policy_hash', 'old_path', 'extra_key'])
def test_recovery_terminal_cpu_prospective_specification(recovery_terminal_cpu, fault):
    test_recovery_prospective_cpu_specification(recovery_terminal_cpu, fault)
