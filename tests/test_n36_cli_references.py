"""CPU-only CLI regressions using temporary files; no operational authority."""
import copy
import json
from pathlib import Path
import sys

import pytest

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n36_contract as c
from scripts import qd_ed_n36_release as release
from scripts import qd_ed_n36_runner as runner
from scripts import qd_ed_n36_source as source


def write(path, value):
    Path(path).write_text(json.dumps(value))
    return {'path': str(path), 'sha256': w.sha(path)}


@pytest.fixture
def alias(tmp_path):
    directory = tmp_path / 'real'
    directory.mkdir()
    alias = tmp_path / 'lexical'
    alias.symlink_to(directory, target_is_directory=True)
    return alias


def invoke(monkeypatch, plan_ref, release_ref):
    monkeypatch.setattr(sys, 'argv', ['runner', '--plan', plan_ref['path'],
        '--plan-sha256', plan_ref['sha256'], '--release', release_ref['path'],
        '--release-sha256', release_ref['sha256']])
    runner.main()


@pytest.mark.parametrize('suffix', ['/', '//./'])
def test_main_forwards_exact_paths_and_hashes(alias, monkeypatch, capsys, suffix):
    refs = [write(str(alias) + suffix + name + '.json', {'synthetic': name})
            for name in ('plan', 'release')]
    assert all(ref['path'] != str(Path(ref['path']).resolve()) for ref in refs)
    calls = []

    def launch(*received):
        calls.append(received)
        assert list(received) == refs
        assert [w.read_ref(ref) for ref in received] == [
            {'synthetic': 'plan'}, {'synthetic': 'release'}]
        return {'status': 'SYNTHETIC_ONLY'}

    monkeypatch.setattr(runner, 'launch', launch)
    invoke(monkeypatch, *refs)
    assert calls == [tuple(refs)]
    assert capsys.readouterr().out == 'SYNTHETIC_ONLY\n'


@pytest.mark.parametrize('index', [0, 1], ids=['plan', 'release'])
def test_main_rejects_relative_reference_before_launch(alias, monkeypatch, capsys, index):
    refs = [write(alias / (name + '.json'), {}) for name in ('plan', 'release')]
    refs[index]['path'] = 'relative.json'
    monkeypatch.setattr(runner, 'launch', lambda *args: pytest.fail('launch reached'))
    with pytest.raises(SystemExit) as exc:
        invoke(monkeypatch, *refs)
    assert exc.value.code == 2
    assert '--' + ('plan', 'release')[index] + ' must be an absolute path' in capsys.readouterr().err


@pytest.mark.parametrize('fault,reason', [
    (None, 'frozen protocol v2 only'),
    ('plan_hash', 'file reference hash/path differs'),
    ('release_hash', 'file reference hash/path differs'),
    ('plan_path', 'external release differs'),
    ('bound_plan_hash', 'external release differs'),
    ('review_plan_path', 'root review differs'),
])
def test_main_retains_release_hash_and_equality_gates(alias, monkeypatch, fault, reason):
    # Stub only plan governance. Hash reads and detached release/review equality
    # are real. The synthetic protocol deliberately fails before deeper evidence
    # reads; reaching that gate is NOT a successful production release validation.
    monkeypatch.setattr(release, 'validate_plan', lambda plan: None)
    plan = {key: {} for key in ('native_build', 'authority', 'protocol_review',
        'source', 'scientific_source', 'runtime_closure', 'controller_semantics',
        'runtime', 'phase_authorization')}
    plan['protocol'] = {'path': str(alias / 'unused.json'), 'sha256': '0' * 64}
    plan_ref = write(alias / 'plan.json', plan)
    expected = {**plan, 'schema': 'n36-execution-release-v1', 'approved': True,
                'plan': plan_ref, 'limits': c.LIMITS}
    review = {**copy.deepcopy(expected), 'schema': 'n36-root-production-review-v1',
              'decision': 'APPROVED'}
    if fault == 'review_plan_path':
        review['plan']['path'] = str(Path(plan_ref['path']).resolve())
    review_ref = write(alias / 'review.json', review)
    detached = {**copy.deepcopy(expected), 'root_review': review_ref}
    if fault == 'bound_plan_hash':
        detached['plan']['sha256'] = '0' * 64
    release_ref = write(alias / 'release.json', detached)
    if fault == 'plan_hash':
        plan_ref['sha256'] = '0' * 64
    elif fault == 'release_hash':
        release_ref['sha256'] = '0' * 64
    elif fault == 'plan_path':
        plan_ref['path'] = str(Path(plan_ref['path']).resolve())
    monkeypatch.setattr(runner, 'launch', release.validate_release)
    with pytest.raises(ValueError, match=reason):
        invoke(monkeypatch, plan_ref, release_ref)


@pytest.mark.parametrize('fault', ['path', 'sha256'])
def test_runtime_binding_rejects_changed_release_reference(alias, fault):
    release_ref = write(alias / 'release.json', {'synthetic': True})
    binding = {'context': release_ref, 'runtime_closure': write(alias / 'runtime.json', {}),
               'process': {'pid': 1, 'proc_start_ticks': '1', 'boot_id': 'synthetic'},
               'phase': 'runtime_before'}
    changed = copy.deepcopy(binding)
    changed['context'][fault] = (str(Path(release_ref['path']).resolve())
                               if fault == 'path' else '0' * 64)
    # The existing consumer rejects cross-binding before inspecting any runtime.
    receipt = {'schema': 'n36-source-execution-v2', 'binding': binding}
    with pytest.raises(ValueError, match='N36 alias context/process/phase differs'):
        source.verify_importlib_aliases(receipt, {}, {'binding': binding}, changed)
