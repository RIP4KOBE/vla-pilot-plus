"""CPU continuation fixtures. No deployment approval, GPU or scientific evidence.

Public preparation runs real prefix/manifest/receipt/identity validation. The
runtime/provider/controller deployment leaves are synthetic, explicitly checked
stand-ins. No fixture is exported as a production release.
"""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n23_worker as w, qd_ed_n34_contract as c
from scripts import qd_ed_n34_continuation as cc
from scripts import qd_ed_n34_continuation_prepare as prep
from scripts import qd_ed_n34_continuation_release as rel
from scripts import qd_ed_n34_continuation_runner as runner
from scripts import qd_ed_n34_worker as worker, qd_ed_n34_supervise as s


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return c.ref(path)


def anchor(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encoded(events):
    return b''.join((json.dumps(x) + '\n').encode() for x in events)


def invalid_history():
    result = []
    for key, cohort, bucket in c.INVALID_HISTORY:
        for event in ('reserved', 'dispatched', 'aborted'):
            result.append({'attempt_id': key, 'episode_key': key, 'identity': {'iteration': cohort, 'split': 'dev'},
                           'event': event, 'budget_bucket': bucket, 'outcome_valid': False, 'success': None,
                           'required_cost_telemetry_complete': False, 'gpu_process_wall_seconds': 11.})
    return result


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    rows = c.expected_rows()
    data = tmp_path / 'data'; data.mkdir()
    ledger = data / 'attempt-ledger.jsonl'
    # Deployment semantics are an independently tested leaf; no installed runtime
    # is opened by this fixture. Retained receipt/runtime binding remains real.
    proof = {'source': {'path': '/synthetic/controller.py', 'sha256': 'a' * 64},
             'module': 'robosuite.synthetic', 'class': 'OperationalSpaceController', 'instance': {'synthetic': True}}
    monkeypatch.setattr(worker.controller, 'verify_semantics', lambda *args: proof)
    monkeypatch.setattr(cc.legacy.r, 'stage_overrides', lambda rt: w.require(
        rt['frozen_stage_provider'] == {'backend': 'codex_cli', 'model': 'gpt-6-astra', 'auth_mode': 'chatgpt'},
        'synthetic provider differs'))
    provider = {'backend': 'codex_cli', 'model': 'gpt-6-astra', 'auth_mode': 'chatgpt'}
    runtime_ref = write(tmp_path / 'runtime-old.json', {'frozen_stage_provider': provider})
    closure_ref = write(tmp_path / 'closure-old.json', {'schema': 'n34-runtime-source-closure-v2',
        'runtime': runtime_ref, 'modules': {'synthetic': proof['source']}, 'required_after': ['synthetic'],
        'generated_modules': {}})
    semantics_ref = write(tmp_path / 'semantics.json', proof)
    names = ['scripts.qd_ed_n34_worker', 'scripts.qd_ed_n34_source', 'scripts.qd_ed_n34_native',
             'scripts.qd_ed_n31_native', 'scripts.audit_decision_evidence', 'scripts.qd_ed_n34_controller']
    inventory = {name: {'path': name.replace('.', '/') + '.py', 'sha256': 'b' * 64} for name in names}
    source = {'commit': cc.BASE, 'files': list(inventory.values()), 'sha256': w.canonical_sha(list(inventory.values()))}
    original = {'schema': 'n34-released-plan-v1', 'frozen': True, 'release_enabled': True,
        'worktree': str(tmp_path), 'source': source, 'scientific_source': copy.deepcopy(source),
        'episodes': rows, 'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
        'runtime': runtime_ref, 'runtime_closure': closure_ref, 'controller_semantics': semantics_ref,
        'stop_path': str(tmp_path / 'STOP'), 'expected_manifests': {}, 'runtime_inventory_sha256': 'e' * 64,
        'phase_authorization': {'dev': True, 'validation': False, 'formal': False},
        'authority': write(tmp_path / 'old-authority.json', {'synthetic_only': True}),
        'artifact_root': str(tmp_path / 'old-artifacts'), 'run_name': 'synthetic',
        'seed_plan_sha256': 'f' * 64, 'input_contract_label': 'input_repaired'}
    for row in rows:
        output = tmp_path / 'old-artifacts' / row['episode_key']
        manifest = {'row': row, 'source': source, 'scientific_source': original['scientific_source'],
            'runtime': runtime_ref, 'runtime_closure': closure_ref, 'controller_semantics': semantics_ref,
            'output_dir': str(output), 'argv': ['/synthetic/python', '/synthetic/main.py'],
            'expected_runtime': {'synthetic': row['episode_key']} if row['profile'] == 'N34' else None}
        original['expected_manifests'][row['episode_key']] = write(tmp_path / 'old-manifests' / (row['episode_key'] + '.json'), manifest)
    original['protocol'] = write(tmp_path / 'old-protocol.json', {'episodes': rows, 'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT})
    plan_ref = write(tmp_path / 'old-plan.json', original)
    release = {k: original[k] for k in ('authority', 'protocol', 'source', 'scientific_source',
        'runtime_closure', 'controller_semantics', 'runtime', 'limits', 'phase_authorization')}
    release.update(schema='n34-execution-release-v1', approved=True, plan=plan_ref)
    review_ref = write(tmp_path / 'old-review.json', {**release, 'schema': 'n34-root-production-review-v1', 'decision': 'APPROVED'})
    release_ref = write(tmp_path / 'old-release.json', {**release, 'root_review': review_ref})
    events = invalid_history(); checks = []; outcomes = []
    for row in rows[:19]:
        manifest_ref = original['expected_manifests'][row['episode_key']]
        manifest = w.read_ref(manifest_ref); output = Path(manifest['output_dir'])
        context = {'schema': 'n34-worker-context-v1', 'plan': plan_ref, 'release': release_ref,
            'expected_manifest': manifest_ref, 'episode_key': row['episode_key'], 'attempt_id': row['episode_key'],
            'main_argv': manifest['argv'][1:], 'worker_contract': c.WORKER_CONTRACT}
        context_ref = write(output / 'n34-worker-context.json', context)
        process = {'pid': row['task_id'] + 100, 'boot_id': 'fixture', 'proc_start_ticks': 10}
        write(output / 'process.json', {**process, 'context': context_ref, 'release': release_ref, 'attempt_id': row['episode_key']})
        write(output / 'eds_eval/n34-worker-start.json', {'context': context_ref, 'process': process})
        write(output / 'command.json', {'argv': [manifest['argv'][0], '-m', 'scripts.qd_ed_n34_worker',
              '--context', context_ref['path'], '--context-sha256', context_ref['sha256']],
              'main_argv': manifest['argv'], 'context': context_ref})
        gate = {'profile': row['profile'], 'guided_decisions': 0}
        report = {'accepted': True, 'evidence_complete': True, 'n23_arithmetic_backend': {'kind': 'cpu', 'logical_device': 'cpu'}}
        if row['profile'] == 'N34':
            gate['runtime_identity'] = manifest['expected_runtime']; report['n34_observed_jaw_audit'] = gate
        else:
            report.update(n31_capture_dwell_audit=gate, n34_control_absence={'profile': row['profile'], 'events': 0, 'metrics': 0})
        audit_ref = write(output / 'eds_eval/decision-evidence-audit.json', report)
        receipt = {'schema': 'n34-worker-receipt-v2', 'context': context_ref, 'plan': plan_ref,
            'row': row, 'attempt_id': row['episode_key'], 'expected_manifest': manifest_ref,
            'source': source, 'scientific_source': original['scientific_source'], 'audit_report': audit_ref,
            'accepted': True, 'process_unchanged': True, 'main_exit_code': 0, 'process': process,
            'loaded_before': inventory, 'loaded_after': inventory, 'controller_instances': [proof],
            'worker_cuda': {'physical_gpu': 7, 'uuid': c.GPU_UUID, 'logical_device': 'cuda:0', 'actual_uuid': c.GPU_UUID},
            'audit_backend': report['n23_arithmetic_backend'], 'native_counts': gate,
            'evidence': {'files': [], 'sha256': w.canonical_sha([])}}
        for phase in ('runtime_before', 'runtime_after'):
            receipt[phase] = {'schema': 'n34-runtime-receipt-v2', 'binding': worker.runtime_receipt_binding(context_ref, original, process, phase),
                             'modules': {'synthetic': proof['source']}, 'generated_modules': {}}
        receipt_ref = write(output / 'eds_eval/n34-worker-receipt.json', receipt)
        base = {'attempt_id': row['episode_key'], 'episode_key': row['episode_key'], 'identity': s.c_identity(row),
            'budget_bucket': row['budget_bucket'], 'replacement': row['replacement'], 'plan_sha256': plan_ref['sha256'],
            'release': release_ref, 'source_commit': cc.BASE, 'runtime_manifest_sha256': runtime_ref['sha256'],
            'runtime_inventory_sha256': original['runtime_inventory_sha256'], 'init_row_sha256': row['init_row_sha256'],
            'output_dir': str(output), 'physical_gpu': 7, 'ledger_prefix': anchor(encoded(events)), 'context': context_ref,
            'stage_backend': 'codex_cli', 'stage_model': 'gpt-6-astra', 'stage_condition': 'synthetic'}
        final = {**base, 'event': 'valid', 'outcome_valid': True, 'required_cost_telemetry_complete': True,
                 'success': row['profile'] == 'N34' and row['task_id'] == 0,
                 'n34_worker_receipt': receipt_ref, 'gpu_process_wall_seconds': 100.}
        events.extend([{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'}, final])
        write(output / 'attempt-result.json', final)
        checks.append({'attempt_id': row['episode_key'], 'receipt': receipt_ref, 'audit_report': audit_ref})
        outcomes.append({k: v for k, v in cc._outcome(row, final, 'retained_legacy').items() if k != 'origin'})
    ledger.write_bytes(encoded(events))
    anchors = {'attempt-ledger.jsonl': anchor(ledger.read_bytes())}
    for name in ('gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl'):
        (data / name).write_bytes(b''); anchors[name] = anchor(b'')
    terminal = {'source': cc.BASE, 'scientific_source': original['scientific_source'],
        'controller': {'plan': plan_ref, 'release': release_ref}, 'worker_handles': [],
        'disposition': 'BUDGET_CAPPED_PARTIAL_COHORT_NO_PROMOTION', 'ledger_prefixes': anchors,
        'receipt_checks': checks, 'reconciliation': {'outcomes': outcomes}}
    terminal_ref = write(tmp_path / 'terminal.json', terminal)
    design = {'schema': 'n34-separate-continuation-design-v1', 'source': cc.BASE, 'predecessor_plan': plan_ref,
        'terminal_reconciliation': terminal_ref, 'retained_valid_episode_keys': [x['episode_key'] for x in rows[:19]],
        'unobserved_original_rows': rows[19:], 'unchanged_gates': cc.GATES, 'deadline': c.DEADLINE,
        'ledger_prefix': anchors['attempt-ledger.jsonl'], 'scientific_interpretation': 'SYNTHETIC outcome-aware amended Dev screen'}
    design_ref = write(tmp_path / 'design.json', design)
    monkeypatch.setattr(cc, 'DESIGN_SHA', design_ref['sha256'])
    authority = {'schema': 'n34-continuation-cpu-implementation-authority-v1', 'status': 'CPU_ONLY_NO_GPU_RELEASE',
        'gpu_authorized': False, 'source': cc.BASE, 'design': design_ref, 'ledger_prefixes': anchors}
    authority_ref = write(tmp_path / 'authority.json', authority)
    return SimpleNamespace(root=tmp_path, data=data, ledger=ledger, authority_ref=authority_ref,
        design=design, design_ref=design_ref, original=original, terminal=terminal, events=events, rows=rows,
        provider=provider, proof=proof)


def candidate(f):
    return prep.prepare(f.root / 'candidate', f.authority_ref)


def extended(f, count, candidate_success=True):
    events = copy.deepcopy(f.events)
    for row in f.rows[19:19 + count]:
        base = copy.deepcopy(f.events[-1])
        base.update(attempt_id=row['episode_key'], episode_key=row['episode_key'], identity=s.c_identity(row),
                    budget_bucket=row['budget_bucket'], replacement=None, init_row_sha256=row['init_row_sha256'],
                    source_commit='c' * 40, success=candidate_success if row['profile'] == 'N34' else False)
        events.extend({**base, 'event': kind} for kind in ('reserved', 'dispatched', 'valid'))
    return events


def test_public_preparation_preserves_exact_retained_and_missing(fixture):
    f = fixture; plan = candidate(f)
    summary = prep.validate_candidate(plan, ledger_directory=f.data)
    assert plan['episodes'] == f.rows[19:] and len(plan['identity_mapping']) == 11
    assert plan['expected_manifests'] == {r['episode_key']: None for r in f.rows[19:]}
    assert summary['valid_cells'] == 19 and summary['complete_triples'] == 6
    assert summary['matched_denominator_per_arm'] == 6 and summary['planned_denominator_per_arm'] == 10
    assert summary['candidate_upper_bound'] == 5 and summary['matched_successes'] == {'C0': 0, 'Q0': 0, 'N34': 1}
    assert not summary['validation_authorized'] and not summary['automatic_promotion']
    assert summary['root_scientific_review_required']
    with pytest.raises(ValueError, match='immutable'):
        candidate(f)
    with pytest.raises(ValueError, match='disabled'):
        rel.validate_release(c.ref(f.root / 'candidate/plan.DISABLED-v1.json'), None)


@pytest.mark.parametrize('mutation', ['prefix', 'receipt', 'native_audit', 'manifest', 'terminal', 'context', 'process', 'command', 'runtime'])
def test_public_validation_rejects_tampered_retained_artifacts(fixture, mutation):
    f = fixture; plan = candidate(f)
    paths = {'prefix': f.ledger, 'receipt': Path(f.terminal['receipt_checks'][2]['receipt']['path']),
        'native_audit': Path(f.terminal['receipt_checks'][2]['audit_report']['path']),
        'manifest': Path(f.original['expected_manifests'][f.rows[2]['episode_key']]['path']),
        'runtime': Path(f.original['runtime_closure']['path'])}
    output = Path(w.read_ref(f.original['expected_manifests'][f.rows[2]['episode_key']])['output_dir'])
    paths.update(terminal=output/'attempt-result.json', context=output/'n34-worker-context.json',
                 process=output/'process.json', command=output/'command.json')
    path = paths[mutation]
    if mutation == 'prefix':
        raw = path.read_bytes(); path.write_bytes(raw.replace(b'11.0', b'12.0', 1))
    elif mutation in ('terminal', 'process', 'command'):
        doc = json.loads(path.read_text()); doc[next(iter(doc))] = 'tampered'; path.write_text(json.dumps(doc))
    else:
        path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError):
        prep.validate_candidate(plan, ledger_directory=f.data)


@pytest.mark.parametrize('mutation', ['omit', 'duplicate', 'retained', 'seed', 'source', 'mapping', 'ceiling', 'promotion'])
def test_public_validation_rejects_identity_and_policy_mutations(fixture, mutation):
    f = fixture; plan = candidate(f)
    if mutation == 'omit': plan['episodes'].pop()
    elif mutation == 'duplicate': plan['episodes'][-1] = plan['episodes'][0]
    elif mutation == 'retained': plan['episodes'][0] = f.rows[0]
    elif mutation == 'seed': plan['episodes'][0]['policy_seed'] += 1
    elif mutation == 'source': plan['scientific_source']['commit'] = '0' * 40
    elif mutation == 'mapping': plan['identity_mapping'][0]['original'] = f.rows[18]
    elif mutation == 'ceiling': plan['limits'] = {**plan['limits'], 'max_gpu_seconds': 20241}
    else: plan['automatic_promotion'] = True
    with pytest.raises(ValueError):
        prep.validate_candidate(plan, ledger_directory=f.data)


@pytest.mark.parametrize('mutation', ['replay_retained', 'omit_retained', 'duplicate_missing', 'omit_missing', 'mixed_seed', 'mixed_source'])
def test_reconciliation_rejects_replay_omissions_and_mixed_closure(fixture, mutation):
    f = fixture; plan = candidate(f); events = extended(f, 2)
    if mutation == 'replay_retained': events.extend(copy.deepcopy(f.events[-3:]))
    elif mutation == 'omit_retained': del events[-9:-6]
    elif mutation == 'duplicate_missing': events[-3:] = copy.deepcopy(events[-6:-3])
    elif mutation == 'omit_missing': del events[-6:-3]
    elif mutation == 'mixed_seed': events[-1]['identity']['policy_seed'] += 1
    else: events[-1]['source_commit'] = 'wrong'
    with pytest.raises(ValueError):
        cc.reconcile(plan, plan['retained_outcomes'], events, lambda *a: None)


def test_complete_triples_futility_and_invalid_new_cells(fixture):
    f = fixture; plan = candidate(f)
    for count, status, triples, upper in [(0, 'READY_FOR_ROOT_RELEASE', 6, 5),
        (1, 'READY_FOR_ROOT_RELEASE', 6, 5), (2, 'NUMERIC_FUTILITY', 7, 4)]:
        result = cc.reconcile(plan, plan['retained_outcomes'], extended(f, count, False), lambda *a: None)
        assert result['status'] == status and result['summary']['complete_triples'] == triples
        assert result['summary']['candidate_upper_bound'] == upper
    events = extended(f, 2, False); events[-1]['outcome_valid'] = False
    result = cc.reconcile(plan, plan['retained_outcomes'], events, lambda *a: None)
    assert result['status'] == 'INVALID_STOP' and result['summary']['complete_triples'] == 6
    assert result['next_row'] is None
    with pytest.raises(ValueError, match='futility'):
        cc.reconcile(plan, plan['retained_outcomes'], extended(f, 3, False), lambda *a: None)
    result = cc.reconcile(plan, plan['retained_outcomes'], extended(f, 11, True), lambda *a: None)
    assert result['status'] == 'COMPLETE' and result['summary']['valid_cells'] == 30
    assert result['summary']['amended_dev_necessary_gate_met']
    assert result['summary']['matched_denominator_per_arm'] == 10
    assert not result['summary']['validation_authorized'] and not result['summary']['automatic_promotion']
    assert not result['summary']['independent_replication'] and not result['summary']['confirmatory_evidence']


def test_missing_validation_cannot_be_bypassed(fixture):
    f = fixture; plan = candidate(f)
    def reject(*args): raise ValueError('new native receipt invalid')
    with pytest.raises(ValueError, match='new native receipt'):
        cc.reconcile(plan, plan['retained_outcomes'], extended(f, 1), reject)
    events = extended(f, 1)[:-1]
    result = cc.reconcile(plan, plan['retained_outcomes'], events, reject)
    assert result['status'] == 'LIVE_OR_UNSETTLED' and result['next_row'] is None


def allowance():
    return {'authority_starts_at': '2026-10-09T00:00:00Z', 'authority_ends_at': c.DEADLINE,
        'private_budget': True, 'gpu_idle': True, 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID,
        'live_handles': [], 'unsettled_reservations': 0, 'global_seconds_remaining': 200000,
        'private_seconds_remaining': 200000, 'incremental_seconds_remaining': 20240,
        'protected_seconds_remaining': 44 * 3600, 'global_attempts_remaining': 1000,
        'protected_attempts_remaining': 220, 'incremental_attempts_remaining': 11, 'bucket_attempts_remaining': 8}


@pytest.mark.parametrize('mutation', ['stop', 'symlink_stop', 'expired', 'short_window', 'increment', 'private',
    'global', 'reserve', 'attempt_reserve', 'no_attempt', 'gpu_uuid', 'gpu', 'unsettled', 'old_row', 'nan', 'ceiling'])
def test_admission_rejections(tmp_path, mutation):
    a = allowance(); now = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc); stop = tmp_path/'STOP'; row = c.expected_rows()[19]
    if mutation == 'stop': stop.touch()
    elif mutation == 'symlink_stop': stop.symlink_to(tmp_path/'missing')
    elif mutation == 'expired': now = dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc)
    elif mutation == 'short_window': a['authority_ends_at'] = '2026-10-09T00:30:39Z'
    elif mutation in ('increment', 'private', 'global'): a[{'increment':'incremental_seconds_remaining', 'private':'private_seconds_remaining', 'global':'global_seconds_remaining'}[mutation]] = 1839.99
    elif mutation == 'reserve': a['protected_seconds_remaining'] = 200000 - 1839
    elif mutation == 'attempt_reserve': a['global_attempts_remaining'] = 220
    elif mutation == 'no_attempt': a['incremental_attempts_remaining'] = 0
    elif mutation == 'gpu_uuid': a['gpu_uuid'] = 'GPU-wrong'
    elif mutation == 'gpu': a['physical_gpu'] = 0
    elif mutation == 'unsettled': a['unsettled_reservations'] = 1
    elif mutation == 'old_row': row = c.expected_rows()[18]
    elif mutation == 'nan': a['incremental_seconds_remaining'] = float('nan')
    else: a['incremental_seconds_remaining'] = 20241
    with pytest.raises(ValueError): cc.guard(row, a, now=now, stop_path=stop)


def test_exact_1840_boundary_and_no_old_balance_reuse(tmp_path):
    a = allowance(); a['incremental_seconds_remaining'] = 1840
    a['authority_ends_at'] = '2026-10-09T00:30:40Z'
    assert cc.guard(c.expected_rows()[19], a, now=dt.datetime(2026,10,9,tzinfo=dt.timezone.utc), stop_path=tmp_path/'STOP') == 1840
    assert c.LIMITS['cohort_gpu_seconds'] == 18000
    assert cc.LIMITS['max_gpu_seconds'] == 20240 and cc.LIMITS['automatic_recoveries'] == 0


def released_fixture(f, monkeypatch):
    """Real detached-boundary orchestration with checked deployment leaves."""
    plan = candidate(f)
    new_runtime = {'schema': 'qd-ed-runtime-setup-v1', 'worktree': str(f.root), 'artifact_root': str(f.root),
        'gpu_mapping': {'physical_gpu': 7, 'uuid': c.GPU_UUID, 'egl_device_index': 4},
        'cuda_egl_verified': True, 'provider_ready': True, 'stage_recovered_error_condition': rel.r.E2_STAGE_CONDITION,
        'frozen_stage_provider': f.provider, 'files': [], 'tasks': {}}
    runtime_ref = write(f.root / 'new-runtime.json', new_runtime)
    plan.update(schema='n34-continuation-plan-v1', frozen=True, release_enabled=True, worktree=str(f.root),
        phase_authorization={'dev': True, 'validation': False, 'formal': False},
        runtime=runtime_ref, runtime_closure=write(f.root/'new-closure.json', {'runtime': runtime_ref, 'synthetic': True}),
        controller_semantics=f.original['controller_semantics'], source={**f.original['source'], 'commit': 'c' * 40},
        artifact_root=str(f.root/'new-artifacts'))
    for k in ('run_name', 'runtime_inventory_sha256', 'seed_plan_sha256', 'input_contract_label'):
        plan[k] = f.original[k]
    equality = {'synthetic': True, 'base_commit': cc.BASE, 'operational_commit': plan['source']['commit']}
    plan['scientific_equality'] = write(f.root/'equality.json', equality)
    plan['authority'] = write(f.root/'new-authority.json', {
        'schema': 'n34-continuation-budget-authority-v1', 'approved': True, 'label': cc.LABEL,
        'design': plan['design'], 'limits': cc.LIMITS, 'ledger_prefixes': plan['ledger_prefixes'],
        'coordinator_ends_at': c.DEADLINE, 'validation_authorized': False, 'formal_authorized': False,
        'caps': c.CAPS, 'weekly_window': {'origin_gpu_hours': 0., 'increment_gpu_hours': 100., 'ends_at': c.DEADLINE},
        'starts_at': '2026-10-09T00:00:00Z', 'amendment': 'synthetic',
        'approval_basis': write(f.root/'basis.json', {'synthetic_only': True})})
    for row in plan['episodes']:
        plan['expected_manifests'][row['episode_key']] = write(f.root/'new-manifests'/(row['episode_key']+'.json'),
            {'row': row, 'source': plan['source'], 'scientific_source': plan['scientific_source'],
             'runtime': runtime_ref, 'argv': ['/synthetic/python', '/synthetic/main.py'],
             'output_dir': str(f.root/'new-artifacts'/row['episode_key'])})
    plan_ref = write(f.root/'new-plan.json', plan)
    release = {k: plan[k] for k in ('design', 'label', 'source', 'scientific_source', 'scientific_equality',
               'runtime', 'runtime_closure', 'controller_semantics', 'authority', 'limits', 'phase_authorization', 'automatic_promotion')}
    release.update(schema='n34-continuation-execution-release-v1', approved=True, plan=plan_ref)
    review_ref = write(f.root/'new-review.json', {**release, 'schema': 'n34-continuation-root-review-v1', 'decision': 'APPROVED',
        'scientific_interpretation': f.design['scientific_interpretation'], 'retained_equivalence_reviewed': True,
        'validation_requires_new_root_scientific_review': True})
    release_ref = write(f.root/'new-release.json', {**release, 'root_review': review_ref})
    calls = []
    def checked(name, fn):
        def invoke(*args, **kwargs):
            calls.append(name); return fn(*args, **kwargs)
        return invoke
    def eq_check(root, original, source):
        w.require(original == f.original and source == plan['source'], 'synthetic source changed'); return equality
    def manifest_check(ref, actual, runtime, row):
        doc = w.read_ref(ref)
        w.require(doc['row'] == row and doc['source'] == actual['source'] and doc['runtime'] == actual['runtime']
                  and row in f.rows[19:], 'synthetic new manifest/source differs'); return doc
    monkeypatch.setattr(rel.b, 'ROOT', f.root)
    monkeypatch.setattr(rel, 'source_equivalence', checked('source', eq_check))
    monkeypatch.setattr(rel.b, 'attest_loaded', checked('loaded', lambda *a: {}))
    monkeypatch.setattr(rel.b.closure, 'verify_runtime', checked('runtime', lambda doc, ref: doc))
    monkeypatch.setattr(rel.r, 'verify_files', checked('files', lambda *a, **kw: None))
    monkeypatch.setattr(rel.r, 'validate_runtime_inputs', checked('inputs', lambda *a: None))
    monkeypatch.setattr(rel.b, 'profiles', lambda *a: {'profiles': {}})
    monkeypatch.setattr(rel.b, '_verify_manifest_bound', checked('manifest', manifest_check))
    return plan, plan_ref, release_ref, calls


def test_public_release_and_worker_context_use_new_closure(fixture, monkeypatch):
    f = fixture; plan, plan_ref, release_ref, calls = released_fixture(f, monkeypatch)
    result = rel.validate_release(plan_ref, release_ref)
    assert result[0] == plan and calls.count('manifest') == 11
    assert {'source', 'loaded', 'runtime', 'files', 'inputs'} <= set(calls)
    context = worker.context_for(plan_ref, plan['episodes'][0], release_ref)
    ref = write(f.root/'context-new.json', context)
    assert worker.validate_context(ref)[3] == plan['episodes'][0]
    assert worker.release_api(plan_ref) is rel
    assert worker.release_api(f.design['predecessor_plan']) is cc.legacy
    context.update(episode_key=f.rows[0]['episode_key'], attempt_id=f.rows[0]['episode_key'])
    with pytest.raises(ValueError, match='exact primary'):
        worker.validate_context(write(f.root/'context-replay.json', context))


@pytest.mark.parametrize('field', ['source', 'env_seed', 'policy_seed'])
def test_public_release_rejects_new_manifest_mixing(fixture, monkeypatch, field):
    f = fixture; plan, plan_ref, release_ref, _ = released_fixture(f, monkeypatch)
    ref = plan['expected_manifests'][plan['episodes'][0]['episode_key']]
    doc = w.read_ref(ref)
    if field == 'source': doc['source']['commit'] = cc.BASE
    else: doc['row'][field] += 1
    # Rehashing a bad manifest is insufficient: the immutable released plan still
    # binds its original hash, then the new-manifest leaf independently checks it.
    write(Path(ref['path']), doc)
    with pytest.raises(ValueError): rel.validate_release(plan_ref, release_ref)


def test_release_rejects_wrong_root_review(fixture, monkeypatch):
    f = fixture; _, plan_ref, release_ref, _ = released_fixture(f, monkeypatch)
    release = w.read_ref(release_ref); review = w.read_ref(release['root_review'])
    review['validation_requires_new_root_scientific_review'] = False
    release['root_review'] = write(f.root/'bad-review.json', review)
    with pytest.raises(ValueError, match='root review'):
        rel.validate_release(plan_ref, write(f.root/'bad-release.json', release))


def test_new_release_cannot_rewrite_resource_prefix_count(fixture, monkeypatch):
    f = fixture; plan, plan_ref, release_ref, _ = released_fixture(f, monkeypatch)
    # The release binds plan bytes: changing count fails even before admission.
    plan['resource_prefix_event_count'] = 1000
    write(Path(plan_ref['path']), plan)
    with pytest.raises(ValueError): rel.validate_release(plan_ref, release_ref)


def test_runner_rejects_disabled_candidate_before_locks_or_dispatch(fixture, monkeypatch):
    f = fixture; candidate(f)
    def forbidden(*a, **kw): pytest.fail('lock/process/device used for disabled candidate')
    monkeypatch.setattr(runner.r, 'locked', forbidden)
    monkeypatch.setattr(runner.subprocess, 'Popen', forbidden)
    monkeypatch.setattr(runner, 'device_check', forbidden)
    with pytest.raises(ValueError, match='disabled'):
        runner.execute_one(c.ref(f.root/'candidate/plan.DISABLED-v1.json'), None)


def test_accounting_retains_history_and_all_incremental_preparation(fixture, monkeypatch):
    f = fixture; plan, _, _, _ = released_fixture(f, monkeypatch)
    authority = w.read_ref(plan['authority'])
    resources = [{'resource_id': 'unlabelled-preparation', 'event': 'reserved'},
                 {'resource_id': 'unlabelled-preparation', 'event': 'dispatched'},
                 {'resource_id': 'unlabelled-preparation', 'event': 'completed', 'gpu_process_wall_seconds': 18300.}]
    snap = rel.r.budget_snapshot(f.events, resources)
    state = {'n34_continuation_budget_authority': plan['authority'],
        'budget': {'max_episode_attempts': 1800, 'max_gpu_hours': 224., 'reserved': c.CAPS['buckets'],
                   'gpu_hour_reservations': c.CAPS['protected_gpu_hours'], 'amendment': 'synthetic',
                   'dispatched': snap['dispatched'], 'gpu_hours_consumed': snap['gpu_hours_consumed']},
        'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True}}
    reservations = [{'event': 'gpu_hour_reservations_changed', 'gpu_hour_reservations': c.CAPS['protected_gpu_hours'],
                     'rationale': 'synthetic unchanged reserves', 'time_unix': 0}]
    monkeypatch.setattr(rel.r, 'authorized_gpu', lambda *a: 7)
    row = plan['episodes'][0]; now = dt.datetime(2026,10,9,tzinfo=dt.timezone.utc)
    result = rel.admission(plan, authority, state, f.events, resources, reservations, row, now=now, gpu_idle=True)
    assert result['dispatched'] == 30  # 11 old invalids + retained19, never reset
    assert result['gpu_hours_consumed'] == pytest.approx((121 + 1900 + 18300) / 3600)
    resources[-1]['gpu_process_wall_seconds'] = 18401.  # Leaves only1839, not1840.
    state['budget']['gpu_hours_consumed'] = rel.r.budget_snapshot(f.events, resources)['gpu_hours_consumed']
    with pytest.raises(ValueError, match='full1840'):
        rel.admission(plan, authority, state, f.events, resources, reservations, row, now=now, gpu_idle=True)


def test_source_equivalence_rejects_science_delta_before_runtime_reads(monkeypatch):
    original = {'source': {'commit': cc.BASE}}
    source = {'commit': 'c' * 40}
    def git(root, *args):
        if args[0] == 'rev-parse': return (source['commit']+'\n').encode()
        assert args[:3] == ('diff', '--name-only', '-z')
        return b'core/qd_observed_jaw_approach.py\0'
    monkeypatch.setattr(w, '_source_git', git)
    with pytest.raises(ValueError, match='non-operational'):
        rel.source_equivalence(c.ROOT, original, source)


def test_public_runner_reaches_only_first_missing_reservation(fixture, monkeypatch):
    from contextlib import nullcontext
    f = fixture; plan, plan_ref, release_ref, _ = released_fixture(f, monkeypatch)
    snap = rel.r.budget_snapshot(f.events, [])
    state = {'run_name': plan['run_name'], 'artifacts': str(f.root),
        'n34_continuation_budget_authority': plan['authority'],
        'budget': {'max_episode_attempts': 1800, 'max_gpu_hours': 224., 'reserved': c.CAPS['buckets'],
                   'gpu_hour_reservations': c.CAPS['protected_gpu_hours'], 'amendment': 'synthetic',
                   'dispatched': snap['dispatched'], 'gpu_hours_consumed': snap['gpu_hours_consumed']},
        'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True}}
    reservations = [{'event': 'gpu_hour_reservations_changed', 'gpu_hour_reservations': c.CAPS['protected_gpu_hours'],
                     'rationale': 'synthetic unchanged reserves', 'time_unix': 0}]
    monkeypatch.setattr(rel.r, 'authorized_gpu', lambda *a: 7)
    monkeypatch.setattr(runner.r, 'locked', lambda *a, **kw: nullcontext())
    monkeypatch.setattr(runner, 'snapshot', lambda *a: (state, f.events, [], reservations))
    def dead_process(*args): raise FileNotFoundError('synthetic dead process')
    monkeypatch.setattr(runner, 'process_identity', dead_process)
    monkeypatch.setattr(runner, 'check_probe', lambda *a: None)
    monkeypatch.setattr(runner, 'device_check', lambda: {'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID})
    monkeypatch.setattr(runner.r, 'child_environment', lambda *a: {})
    monkeypatch.setattr(runner.r, 'verify_provider', lambda *a, **kw: None)
    class ReservedBoundary(Exception): pass
    def boundary(root, event):
        assert event['event'] == 'reserved'
        assert event['episode_key'] == f.rows[19]['episode_key']
        assert event['identity'] == s.c_identity(f.rows[19])
        assert event['source_commit'] == plan['source']['commit'] != cc.BASE
        assert event['plan_sha256'] == plan_ref['sha256']
        assert event['release'] == release_ref and event['budget_bucket'] == 'development'
        raise ReservedBoundary
    monkeypatch.setattr(runner.r, 'append_event_locked', boundary)
    monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **kw: pytest.fail('actual process prohibited'))
    # Use a fixed fixture date; production clock remains untouched.
    real_dt = runner.dt.datetime
    class FixtureDate(real_dt):
        @classmethod
        def now(cls, tz=None): return cls(2026,10,9,tzinfo=dt.timezone.utc)
    monkeypatch.setattr(runner.dt, 'datetime', FixtureDate)
    with pytest.raises(ReservedBoundary): runner.execute_one(plan_ref, release_ref)


@pytest.mark.parametrize('missing', range(11))
def test_each_original_invalid_history_is_required(fixture, missing):
    f = fixture
    events = copy.deepcopy(f.events); del events[3*missing:3*missing+3]
    with pytest.raises(ValueError, match='old terminal'):
        c.require_replacement_history(events)
