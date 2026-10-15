"""Invented CPU journals only; importing the migration module does not run it."""
import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest

SOURCE = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/resource-isolation-20260924-v1/migrate-private-resources.py')
spec = importlib.util.spec_from_file_location('independent_resource_migration', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def line(identifier, owner, phase, seconds=None, retry=None):
    item = {'attempt_id': identifier, 'event': phase, 'output_dir': '/invented/' + owner + '/' + identifier,
            'budget_bucket': 'development', 'retry_of': retry}
    if seconds is not None:
        item.update(gpu_process_wall_seconds=seconds, outcome_valid=True)
    return (json.dumps(item, separators=(', ', ': ')) + '  \n').encode()


def test_interleaved_bytes_and_cross_owner_lineage_are_not_double_charged():
    wl = [line('original', 'W', phase, .1 if phase == 'valid' else None)
          for phase in ('reserved', 'dispatched', 'valid')]
    xl = [line('child', 'X', phase, .2 if phase == 'valid' else None, 'original')
          for phase in ('reserved', 'dispatched', 'valid')]
    original = b''.join(x for pair in zip(wl, xl) for x in pair)
    parts, groups, cross = m.partition(original, artifacts={'W': Path('/invented/W'), 'X': Path('/invented/X')})
    assert parts == {'W': b''.join(wl), 'X': b''.join(xl)}
    assert [g['source_line_numbers'] for g in groups] == [[1, 3, 5], [2, 4, 6]]
    assert len(cross) == 1 and cross[0]['parent_owner'] == 'W' and cross[0]['child_owner'] == 'X'
    proof = m.conservation(original, groups, parts)
    assert proof['original_seconds_decimal'] == '0.3'
    assert proof['partitions']['W']['seconds_decimal'] == '0.1'
    assert proof['partitions']['X']['seconds_decimal'] == '0.2'
    assert proof['original_dispatched'] == 2


@pytest.mark.parametrize('defect', ['inflight', 'prefix_collision', 'dangling_retry'])
def test_ownership_and_unfinished_ambiguities_stop_before_outputs(defect):
    owner = 'W-suffix' if defect == 'prefix_collision' else 'W'
    phases = ('reserved', 'dispatched') if defect == 'inflight' else ('reserved', 'dispatched', 'valid')
    data = b''.join(line('a', owner, p, .1 if p == 'valid' else None,
                         'missing-parent' if defect == 'dangling_retry' else None) for p in phases)
    with pytest.raises(RuntimeError):
        m.partition(data, artifacts={'W': Path('/invented/W'), 'X': Path('/invented/X')})


def test_state_scope_caps_and_holds_change_without_mutating_original(monkeypatch, tmp_path):
    w, x, a, ax = [tmp_path / name for name in ('study-W', 'study-X', 'artifacts-W', 'artifacts-X')]
    for name, value in [('W', w), ('X', x), ('A', a), ('AX', ax)]:
        monkeypatch.setattr(m, name, value)
    auth = {'path': str(tmp_path / 'authorization.json'), 'sha256': 'a' * 64}
    original = {'run_name': w.name, 'artifacts': str(a), 'budget': {
        'max_episode_attempts': 250, 'max_gpu_hours': 48,
        'reserved': copy.deepcopy(m.CAPS['X']), 'gpu_hour_reservations': {'validation': 14., 'formal': 10.},
        'n1w_authorization': {'path': 'historical.json', 'sha256': m.N1W_SHA}, 'attempt_reallocation': {'old': True}},
        'gpu_pool': [3], 'max_concurrent_gpu_workers': 1,
        'external_resource_hold': {'active': True, 'do_not_auto_resume': True},
        'resource_priority': {'active': True},
        'resource_isolation': {'status': 'DRAINING_FOR_USER_AUTHORIZED_ISOLATION', 'authorization': auth}}
    before = copy.deepcopy(original)
    result = m.new_state(original, 'W', m.snapshot(b'', b''), auth_ref=auth, worktree=w,
                         archive_ref={'path': str(tmp_path / 'state-W.yaml'), 'sha256': 'b' * 64})
    assert original == before
    assert result['budget']['max_episode_attempts'] == 240 and result['budget']['reserved'] == m.CAPS['W']
    assert 'n1w_authorization' not in result['budget'] and 'attempt_reallocation' not in result['budget']
    assert result['max_concurrent_gpu_workers'] == 1 and result['gpu_pool'] == [3]
    assert result['external_resource_hold']['active'] is False
    assert result['external_resource_hold']['do_not_auto_resume'] is False
    assert result['resource_priority']['active'] is False
    assert result['resource_isolation']['status'] == 'MIGRATED_PENDING_VALIDATION'


def test_partial_replace_keeps_archive_progress_and_no_activation(monkeypatch, tmp_path):
    """Filesystem failure mechanics only; every resource path is an invented tmp root.

    External lease and source-inventory checks are stubbed for this one test;
    their real checks are separately reviewed/tested. No actual entrypoint runs.
    """
    w, x, a, ax, d = [tmp_path / n for n in ('W', 'X', 'A', 'AX', 'D')]
    for root in (w, x):
        (root / 'data').mkdir(parents=True)
    d.mkdir()
    for key, value in [('W', w), ('X', x), ('A', a), ('AX', ax), ('D', d)]:
        monkeypatch.setattr(m, key, value)
    copy_path = d / 'migrate-private-resources.py'
    copy_path.write_bytes(SOURCE.read_bytes())
    monkeypatch.setattr(m, '__file__', str(copy_path))
    auth_value = {'schema': 'explicit-user-two-study-resource-isolation-v1',
        'max_owned_workers_combined': 2, 'max_owned_workers_per_study': 1, 'studies': []}
    for owner, root, artifact, gpu in [('W', w, a, 3), ('X', x, ax, 2)]:
        auth_value['studies'].append({'worktree': str(root), 'artifact_root': str(artifact),
            'physical_gpu': gpu, 'max_episode_attempts': 240 if owner == 'W' else 250,
            'max_gpu_hours': 48, 'bucket_caps': m.CAPS[owner]})
    (d / 'authorization.json').write_bytes(m.json_bytes(auth_value))
    monkeypatch.setattr(m, 'AUTH_SHA', m.digest(d / 'authorization.json'))
    auth_ref = {'path': str(d / 'authorization.json'), 'sha256': m.AUTH_SHA}
    for owner, root, artifact in [('W', w, a), ('X', x, ax)]:
        state = {'run_name': w.name, 'artifacts': str(artifact), 'budget': {
            'reserved': m.CAPS['X'], 'max_episode_attempts': 250, 'max_gpu_hours': 48,
            'gpu_hour_reservations': {'validation': 14., 'formal': 10.},
            'n1w_authorization': {'path': 'invented.json', 'sha256': m.N1W_SHA}},
            'max_concurrent_gpu_workers': 1, 'resource_isolation': {
                'status': 'DRAINING_FOR_USER_AUTHORIZED_ISOLATION', 'authorization': auth_ref}}
        (root / 'research-state.yaml').write_text(m.yaml.safe_dump(state))
    def group(identifier, artifact, health=False):
        phases = ['reserved', 'dispatched', 'completed' if health else 'valid']
        base = {'resource_id' if health else 'attempt_id': identifier,
                'output_dir': str(artifact / identifier), 'budget_bucket': 'development'}
        return b''.join(m.json_bytes({**base, 'event': phase,
            **({'gpu_process_wall_seconds': 1.} if i == 2 else {})}).replace(b'\n', b'') + b'\n'
            for i, phase in enumerate(phases))
    episodes = group('we', a) + group('xe', ax)
    health = group('wh', a, True) + group('xh', ax, True)
    for name, value in zip(m.JOURNALS, (episodes, health, b'')):
        (w / 'data' / name).write_bytes(value)
    for name in m.LOCKS:
        (w / 'data' / name).touch()
    for name in m.JOURNALS + m.LOCKS:
        (x / 'data' / name).symlink_to(w / 'data' / name)
    plans = {}
    for owner, resource in [('W', 'wh'), ('X', 'xh')]:
        runtime = d / (owner + '-runtime.json')
        runtime.write_bytes(m.json_bytes({'cuda_egl_probe': {'resource_id': resource}}))
        plan = d / (owner + '-plan.json')
        plan.write_bytes(m.json_bytes({'runtime_manifest_path': str(runtime),
            'n4_cohort': {'health_resources': [{'resource_id': resource}]}}))
        plans[owner] = (plan, m.digest(plan))
    monkeypatch.setattr(m, 'PLANS', plans)
    lock = (w / 'data/qd-ed-runner.lock').stat()
    proof = {'helper': {'pid': 123, 'proc_start_ticks': '1'},
             'lock_device': lock.st_dev, 'lock_inode': lock.st_ino}
    monkeypatch.setattr(m, 'verify_lease', lambda *args, **kw: proof)
    monkeypatch.setattr(m, 'immutable_inventory', lambda _: {'heads': {}, 'files': []})
    monkeypatch.setattr(m, 'verify_immutable', lambda _: None)
    original_replace = os.replace
    calls = []
    def fail_second(source, destination):
        calls.append(str(destination))
        if len(calls) == 2:
            raise OSError('invented second replacement failure')
        original_replace(source, destination)
    monkeypatch.setattr(m.os, 'replace', fail_second)
    with pytest.raises(OSError, match='invented second'):
        m.migrate()
    assert (d / 'archive/shared/attempt-ledger.jsonl').read_bytes() == episodes
    assert (d / 'archive/shared/gpu-healthcheck-ledger.jsonl').read_bytes() == health
    partial = m.read_json(d / 'migration-partial.json')
    assert partial['applied'] == [str(w / 'data/attempt-ledger.jsonl')]
    assert partial['do_not_release_old_lease'] is True
    assert partial['automatic_retry_or_rollback'] is False
    assert (d / 'migration-prepared.json').is_file() and (d / 'migration-progress-01.json').is_file()
    assert not (d / 'migration.json').exists() and not (d / 'release-migration-lease.json').exists()
    assert all((x / 'data' / name).is_symlink() for name in m.JOURNALS + m.LOCKS)
    assert (w / 'data/qd-ed-runner.lock').stat().st_ino == lock.st_ino
