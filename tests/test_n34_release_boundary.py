"""Detached-release wiring on ephemeral CPU documents, NOT real release acceptance.

The public validator and its complete orchestration execute. Installed source,
loaded modules, runtime, controller, runtime-input and manifest leaf validators
are replaced by checked synthetic stand-ins, with explicit failure propagation
coverage. No approvals from this fixture are exported or usable in production.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n34_bridge as b, qd_ed_n34_contract as c
from scripts import qd_ed_n34_release as release, qd_ed_n34_runner as runner
from scripts import qd_ed_n34_supervise as supervisor, qd_ed_n34_worker as worker


def write(path, value):
    path.write_text(json.dumps(value))
    return c.ref(path)


class BoundaryReached(Exception):
    """Stop before any actual lock, worker side effect, or receipt consumption."""


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    calls = []
    read_ref = w.read_ref
    def synthetic_closure(reference):
        if reference == c.REPLACEMENT['terminal_closure']:
            calls.append('terminal_closure')
            return {'synthetic_only': True}
        return read_ref(reference)
    monkeypatch.setattr(w, 'read_ref', synthetic_closure)
    runtime = {'schema': 'qd-ed-runtime-setup-v1', 'worktree': str(b.ROOT),
               'artifact_root': str(tmp_path), 'files': [], 'tasks': {},
               'gpu_mapping': {'physical_gpu': 7, 'uuid': c.GPU_UUID, 'egl_device_index': 4},
               'cuda_egl_verified': True, 'provider_ready': True,
               'stage_recovered_error_condition': release.r.E2_STAGE_CONDITION,
               'frozen_stage_provider': {'backend': 'codex_cli'}}
    runtime_ref = write(tmp_path / 'runtime.json', runtime)
    source_file = tmp_path / 'synthetic_source.py'
    source_file.write_text('# synthetic CPU source, not production closure\n')
    source = {'commit': 'a' * 40, 'files': [c.ref(source_file)]}
    plan = {'schema': 'n34-released-plan-v1', 'frozen': True, 'release_enabled': True,
            'worktree': str(b.ROOT), 'artifact_root': str(tmp_path / 'artifacts'),
            'episodes': c.expected_rows(), 'limits': copy.deepcopy(c.LIMITS),
            'worker_contract': c.WORKER_CONTRACT, 'deadline': c.DEADLINE,
            'stop_path': c.stop_path(), 'phase_authorization': {'dev': True, 'validation': False, 'formal': False},
            'attempt_identity': 'episode_key', 'source': source, 'scientific_source': copy.deepcopy(source),
            'runtime': runtime_ref, 'expected_manifests': {},
            'runtime_closure': write(tmp_path / 'closure.json', {'synthetic_only': True}),
            'controller_semantics': write(tmp_path / 'controller.json', {'synthetic_only': True})}
    protocol = {'schema': 'n34-production-protocol-v1', 'cohort': c.COHORT,
                'episodes': plan['episodes'], 'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
                'attempt_identity': 'episode_key', 'deadline': c.DEADLINE,
                'promotion': {'all_valid_cells': 30, 'n34_min_successes': 5,
                              'at_least_both_controls': True, 'matched_controls_required': True},
                'futility': 'complete_valid_triples_only', 'validation_authorized': False, 'formal_authorized': False}
    authority = {'schema': 'n34-budget-authority-v1', 'approved': True, 'cohort': c.COHORT,
                 'limits': c.LIMITS, 'prospective_recovery': copy.deepcopy(c.REPLACEMENT), 'validation_authorized': False, 'formal_authorized': False,
                 'coordinator_ends_at': release.COORDINATOR_END,
                 'caps': copy.deepcopy(c.CAPS),
                 'weekly_window': {'ends_at': c.DEADLINE, 'origin_gpu_hours': 0., 'increment_gpu_hours': 50.},
                 'approval_basis': write(tmp_path / 'basis.json', {'synthetic_only': True})}
    plan['protocol'] = write(tmp_path / 'protocol.json', protocol)
    plan['authority'] = write(tmp_path / 'authority.json', authority)
    for row in plan['episodes']:
        plan['expected_manifests'][row['episode_key']] = write(tmp_path / (row['episode_key'] + '.json'),
            {'row': row, 'argv': ['synthetic-python', 'synthetic-main'],
             'output_dir': str(tmp_path / 'artifacts' / row['episode_key'])})

    def checked(name, fn):
        def check(*args, **kwargs):
            calls.append(name)
            return fn(*args, **kwargs)
        return check

    def source_check(actual):
        w.require(actual['source'] == source and actual['scientific_source'] == source
                  and w.sha(source_file) == source['files'][0]['sha256'], 'synthetic source differs')

    def manifest_check(ref, actual, rt, row):
        manifest = w.read_ref(ref)
        w.require(manifest['row'] == row, 'synthetic manifest differs')
        return manifest

    monkeypatch.setattr(b, 'verify_sources', checked('sources', source_check))
    monkeypatch.setattr(b, 'attest_loaded', checked('loaded', lambda *a: {}))
    monkeypatch.setattr(b, 'source_paths', lambda *a: {str(source_file)})
    monkeypatch.setattr(b.closure, 'verify_runtime', checked('runtime', lambda doc, ref: doc))
    monkeypatch.setattr(worker.controller, 'verify_semantics', checked('controller', lambda ref, *a: w.read_ref(ref)))
    monkeypatch.setattr(release.r, 'stage_overrides', checked('stage', lambda *a: []))
    monkeypatch.setattr(release.r, 'verify_files', checked('files', lambda *a, **kw: None))
    monkeypatch.setattr(release.r, 'validate_runtime_inputs', checked('inputs', lambda *a: None))
    monkeypatch.setattr(b, '_verify_manifest_bound', checked('manifest', manifest_check))
    # Pure real profiles, ownership, runtime_gpu, reference hashes, plan/protocol/
    # root review/authority/caps/phase validators remain in use.
    f = SimpleNamespace(root=tmp_path, plan=plan, authority=authority, protocol=protocol,
                        calls=calls, source_file=source_file, runtime=runtime)
    freeze(f)
    return f


def freeze(f):
    """Re-anchor synthetic documents to test semantic rejection beyond hashes."""
    f.plan_ref = write(f.root / 'plan.json', f.plan)
    expected = {'schema': 'n34-execution-release-v1', 'approved': True, 'plan': f.plan_ref,
                **{k: f.plan[k] for k in ('authority', 'protocol', 'source', 'scientific_source',
                   'runtime_closure', 'controller_semantics', 'runtime', 'limits', 'phase_authorization')}}
    f.review = {**expected, 'schema': 'n34-root-production-review-v1', 'decision': 'APPROVED'}
    f.detached = {**expected, 'root_review': write(f.root / 'review.json', f.review)}
    f.release_ref = write(f.root / 'release.json', f.detached)


CONSUMERS = ['validate', 'supervise', 'runner', 'runner_main', 'context_for', 'context',
             'worker', 'in_process', 'worker_main', 'receipt', 'terminal']


def consume(f, name, monkeypatch):
    def reached(*a, **kw):
        raise BoundaryReached()
    # Stop before locks, model/env/dispatch identity, and receipt file reads.
    monkeypatch.setattr(release.r, 'locked', reached)
    monkeypatch.setattr(worker.w, 'process_identity', reached)
    row = f.plan['episodes'][0]
    context = {'schema': 'n34-worker-context-v1', 'plan': f.plan_ref, 'release': f.release_ref,
               'expected_manifest': f.plan['expected_manifests'][row['episode_key']],
               'episode_key': row['episode_key'], 'attempt_id': row['episode_key'],
               'main_argv': ['synthetic-main'], 'worker_contract': c.WORKER_CONTRACT}
    if getattr(f, 'omit_context_release', False):
        context.pop('release')
    context_ref = write(f.root / 'context.json', context)
    if name == 'validate': return release.validate_release(f.plan_ref, f.release_ref)
    if name == 'supervise': return supervisor.launch(f.plan_ref, f.release_ref)
    if name == 'runner': return runner.launch(f.plan_ref, f.release_ref)
    if name == 'runner_main':
        monkeypatch.setattr(runner.argparse.ArgumentParser, 'parse_args', lambda *a: SimpleNamespace(
            plan=f.plan_ref['path'], plan_sha256=f.plan_ref['sha256'],
            release=f.release_ref['path'], release_sha256=f.release_ref['sha256']))
        return runner.main()
    if name == 'context_for': return worker.context_for(f.plan_ref, row, f.release_ref)
    if name == 'context': return worker.validate_context(context_ref)
    if name == 'worker': return worker.run_worker(context_ref)
    if name == 'in_process': return worker._run_in_process(context_ref)
    if name == 'worker_main':
        monkeypatch.setattr(worker.sys, 'argv', ['worker', '--context', context_ref['path'], '--context-sha256', context_ref['sha256']])
        class Gate:
            def read(self, size):
                assert f.calls.count('manifest') == 30  # every row, before gate
                return b'G'
        monkeypatch.setattr(worker.sys, 'stdin', SimpleNamespace(buffer=Gate()))
        return worker.main()
    if name == 'receipt':
        # Invalid sentinel is deliberately read only after release/context checks.
        return worker.verify_receipt(context_ref, {'sentinel': True}, {})
    if name == 'terminal':
        return worker.verify_terminal(f.plan_ref, row, {}, f.release_ref)
    raise AssertionError(name)


@pytest.mark.parametrize('consumer', CONSUMERS)
def test_public_consumer_reaches_next_gate_only_after_full_release(fixture, consumer, monkeypatch):
    f = fixture
    if consumer in ('supervise', 'runner', 'runner_main', 'worker', 'in_process', 'worker_main'):
        with pytest.raises(BoundaryReached): consume(f, consumer, monkeypatch)
    elif consumer == 'receipt':
        with pytest.raises(ValueError, match='invalid file reference'): consume(f, consumer, monkeypatch)
    elif consumer == 'terminal':
        with pytest.raises(KeyError, match='identity'): consume(f, consumer, monkeypatch)
    else:
        result = consume(f, consumer, monkeypatch)
        assert result
    assert {'sources', 'loaded', 'runtime', 'controller', 'stage', 'files', 'inputs'} <= set(f.calls)
    assert f.calls.count('manifest') >= 30


FAULTS = ['draft', 'booleans_only', 'missing_release', 'plan_hash', 'release_hash', 'tampered_release',
          'review_hash', 'review_decision', 'authority_hash', 'authority_unapproved', 'authority_caps',
          'approval_basis', 'protocol', 'source_binding', 'source_bytes', 'runtime_hash',
          'closure_hash', 'controller_hash', 'phase', 'limits', 'manifest_hash']


def corrupt(f, fault):
    if fault == 'draft': f.plan.update(schema='n34-release-draft-v1', frozen=False, release_enabled=False)
    if fault == 'booleans_only': f.plan['schema'] = 'n34-release-draft-v1'
    if fault == 'phase': f.plan['phase_authorization']['validation'] = True
    if fault == 'limits': f.plan['limits']['automatic_recoveries'] = 1
    if fault == 'source_bytes': f.source_file.write_text('# changed after freeze\n')
    if fault in ('runtime_hash', 'closure_hash', 'controller_hash', 'authority_hash'):
        key = {'runtime_hash': 'runtime', 'closure_hash': 'runtime_closure',
               'controller_hash': 'controller_semantics', 'authority_hash': 'authority'}[fault]
        f.plan[key]['sha256'] = '0' * 64
    if fault == 'manifest_hash': next(iter(f.plan['expected_manifests'].values()))['sha256'] = '0' * 64
    if (fault.startswith('authority_') and fault != 'authority_hash') or fault == 'approval_basis':
        if fault == 'authority_unapproved': f.authority['approved'] = False
        if fault == 'authority_caps': f.authority['caps']['buckets']['formal'] = 0
        if fault == 'approval_basis': f.authority['approval_basis']['sha256'] = '0' * 64
        f.plan['authority'] = write(f.root / 'authority.json', f.authority)
    if fault == 'protocol':
        f.protocol['promotion']['n34_min_successes'] = 4
        f.plan['protocol'] = write(f.root / 'protocol.json', f.protocol)
    freeze(f)
    if fault == 'source_binding':
        f.detached['source'] = {'forged': True}
        f.release_ref = write(f.root / 'release.json', f.detached)
    if fault == 'review_hash': f.detached['root_review']['sha256'] = '0' * 64
    if fault == 'review_decision':
        f.review['decision'] = 'PENDING'
        f.detached['root_review'] = write(f.root / 'review.json', f.review)
    if fault in ('review_hash', 'review_decision'):
        f.release_ref = write(f.root / 'release.json', f.detached)
    if fault == 'missing_release': Path(f.release_ref['path']).unlink()
    if fault == 'plan_hash': f.plan_ref['sha256'] = '0' * 64
    if fault == 'release_hash': f.release_ref['sha256'] = '0' * 64
    if fault == 'tampered_release': (f.root / 'release.json').write_text('{}')


@pytest.mark.parametrize('consumer', CONSUMERS)
@pytest.mark.parametrize('fault', FAULTS)
def test_public_consumers_reject_bad_detached_closure(fixture, consumer, fault, monkeypatch):
    corrupt(fixture, fault)
    # No boundary sentinel, receipt sentinel or missing terminal key may be hit.
    with pytest.raises(ValueError) as error:
        consume(fixture, consumer, monkeypatch)
    assert str(error.value) != 'invalid file reference'


@pytest.mark.parametrize('consumer', ['context', 'worker', 'in_process', 'worker_main', 'receipt'])
def test_no_context_release_is_never_a_draft_fallback(fixture, consumer, monkeypatch):
    fixture.omit_context_release = True
    with pytest.raises(ValueError, match='explicit detached release required'):
        consume(fixture, consumer, monkeypatch)
    assert not fixture.calls


@pytest.mark.parametrize('consumer', ['validate', 'supervise', 'runner', 'context_for', 'terminal'])
def test_missing_external_reference(fixture, consumer, monkeypatch):
    fixture.release_ref = None
    with pytest.raises(ValueError, match='invalid file reference|draft only'):
        consume(fixture, consumer, monkeypatch)


@pytest.mark.parametrize('leaf', ['verify_sources', 'attest_loaded', 'verify_runtime', 'verify_semantics',
                                  'stage_overrides', 'verify_files', 'validate_runtime_inputs', '_verify_manifest_bound'])
@pytest.mark.parametrize('consumer', CONSUMERS)
def test_leaf_failure_propagates_without_consumer_bypass(fixture, leaf, consumer, monkeypatch):
    owner = (b if leaf in ('verify_sources', 'attest_loaded', '_verify_manifest_bound') else
             b.closure if leaf == 'verify_runtime' else worker.controller if leaf == 'verify_semantics' else release.r)
    def reject(*a, **kw): raise ValueError('full verifier leaf rejected: ' + leaf)
    monkeypatch.setattr(owner, leaf, reject)
    with pytest.raises(ValueError, match='full verifier leaf rejected: ' + leaf):
        consume(fixture, consumer, monkeypatch)


def test_bare_plan_booleans_never_authorize():
    with pytest.raises(ValueError, match='draft only'):
        c.require_release({'approved': True, 'frozen': True, 'release_enabled': True})


@pytest.mark.parametrize('module', ['scripts.qd_ed_n34_worker', 'scripts.qd_ed_n34_runner'])
@pytest.mark.parametrize('fault', ['draft', 'missing_ref', 'bad_hash'])
def test_real_cli_fails_closed_without_parent_gate_or_side_effects(tmp_path, module, fault):
    import os
    import subprocess
    import sys

    plan = write(tmp_path / 'draft.json', {'schema': 'n34-release-draft-v1',
                                         'frozen': False, 'release_enabled': False})
    detached = write(tmp_path / 'release.json', {'approved': True})
    if fault == 'bad_hash': plan['sha256'] = '0' * 64
    if fault == 'missing_ref': Path(plan['path']).unlink()
    if module.endswith('worker'):
        context = write(tmp_path / 'context.json', {'schema': 'n34-worker-context-v1',
            'plan': plan, 'release': detached, 'expected_manifest': {}, 'episode_key': 'synthetic',
            'attempt_id': 'synthetic', 'main_argv': [], 'worker_contract': c.WORKER_CONTRACT})
        args = ['--context', context['path'], '--context-sha256', context['sha256']]
    else:
        args = ['--plan', plan['path'], '--plan-sha256', plan['sha256'],
                '--release', detached['path'], '--release-sha256', detached['sha256']]
    before = sorted(p.name for p in tmp_path.iterdir())
    result = subprocess.run([sys.executable, '-B', '-m', module, *args], cwd=b.ROOT,
        env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1',
             'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'NUMEXPR_NUM_THREADS': '2'},
        input='', capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert ('released plan contract' if fault == 'draft' else 'file reference hash/path differs') in result.stderr
    assert 'parent dispatch gate absent' not in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == before


@pytest.mark.parametrize('fault', ['missing', 'different_old', 'different_closure', 'stale_closure', 'stale_closure_path', 'automatic', 'caps'])
def test_recovery_requires_exact_detached_root_authority(fixture, fault):
    f = fixture
    if fault == 'missing': f.authority.pop('prospective_recovery')
    if fault == 'different_old': f.authority['prospective_recovery']['old_episode_key'] = 'arbitrary'
    if fault == 'different_closure': f.authority['prospective_recovery']['terminal_closure']['sha256'] = '0' * 64
    if fault in ('stale_closure', 'stale_closure_path'):
        from test_n34_recovery_identity import STALE_CLOSURE
        closure = f.authority['prospective_recovery']['terminal_closure']
        closure['path'] = STALE_CLOSURE['path']
        if fault == 'stale_closure': closure['sha256'] = STALE_CLOSURE['sha256']
    if fault == 'automatic': f.authority['prospective_recovery']['automatic'] = True
    if fault == 'caps': f.authority['caps']['gpu_hours'] += 1
    f.plan['authority'] = write(f.root / 'authority.json', f.authority)
    freeze(f)
    with pytest.raises(ValueError, match='recovery authority|unchanged root caps'):
        release.validate_release(f.plan_ref, f.release_ref)


def test_stale_n34r8_release_matrix_rejected():
    # Exercise the plan gate in memory, without generating an APPROVED release.
    plan = {'schema': 'n34-released-plan-v1', 'frozen': True, 'release_enabled': True,
            'worktree': str(c.ROOT), 'episodes': c.expected_rows(),
            'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
            'deadline': c.DEADLINE, 'stop_path': c.stop_path(),
            'phase_authorization': {'dev': True, 'validation': False, 'formal': False},
            'attempt_identity': 'episode_key',
            'expected_manifests': {row['episode_key']: {} for row in c.expected_rows()}}
    release.validate_plan(plan)
    for row in plan['episodes']:
        row['episode_key'] = row['episode_key'].replace('n34r9_', 'n34r8_')
        row['iteration'] = c.OLD_COHORT
    with pytest.raises(ValueError, match='released plan contract'):
        release.validate_plan(plan)


def test_recovery_terminal_closure_hash_is_verified(fixture, monkeypatch):
    f = fixture
    read_ref = w.read_ref
    def reject_closure(reference):
        if reference == c.REPLACEMENT['terminal_closure']:
            raise ValueError('synthetic terminal closure hash mismatch')
        return read_ref(reference)
    monkeypatch.setattr(w, 'read_ref', reject_closure)
    with pytest.raises(ValueError, match='terminal closure hash mismatch'):
        release.validate_release(f.plan_ref, f.release_ref)
