"""CPU-only synthetic release documents with real file/alias verification."""
import copy
from pathlib import Path

import pytest

from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n32_release as release
from test_n32_production import release_chain
from test_n32_release import draft, trusted, write

# release_chain spies on this gate; restore the real implementation below.
VERIFY_FILES = r.verify_files


@pytest.fixture
def alias_chain(release_chain, tmp_path_factory, monkeypatch):
    plan, plan_ref, release_ref, seen = release_chain
    layout = tmp_path_factory.mktemp('compatibility-layout')
    alias = layout / 'historical-worktree'
    alias.symlink_to(plan['worktree'], target_is_directory=True)
    runtime = w.read_ref(plan['runtime'])
    runtime['worktree'] = str(alias)
    # Replace nonexistent task-input fixture records with real cache records.
    # No production runtime, manifest or release is opened or rewritten.
    runtime['files'] = [w_ref for w_ref in runtime['files']
                        if Path(w_ref['path']).is_relative_to(runtime['artifact_root'])]
    payload = alias / 'scripts/qd_ed_n32_release.py'
    record = {'path': str(payload), 'sha256': w.sha(payload),
              'resolved_path': str(payload.resolve()), 'size_bytes': payload.stat().st_size}
    runtime['files'].append(record)
    monkeypatch.setattr(r, 'verify_files', VERIFY_FILES)

    def bind():
        # Rebind only the synthetic test DAG before exercising semantic checks.
        plan['runtime'] = write(Path(plan['runtime']['path']), runtime)
        new_plan_ref = write(Path(plan_ref['path']), plan)
        released = w.read_ref(release_ref)
        review = w.read_ref(released['root_review'])
        for document in (review, released):
            document.update(plan=new_plan_ref, runtime=plan['runtime'])
        released['root_review'] = write(Path(released['root_review']['path']), review)
        return new_plan_ref, write(Path(release_ref['path']), released)

    return plan, runtime, record, layout, seen, bind


def test_validated_runtime_alias_accepted(alias_chain):
    plan, runtime, record, _, seen, bind = alias_chain
    frozen = copy.deepcopy(runtime)
    # Reproduce the old lexical-prefix failure before checking the repair.
    with pytest.raises(r.GateError, match='input symlink escapes owned roots'):
        VERIFY_FILES(runtime['files'], allowed_roots=(plan['worktree'], runtime['artifact_root']))
    refs = bind()
    assert release.validate_release(*refs)[1] == frozen
    assert w.read_ref(plan['runtime']) == frozen
    assert seen == ['generic-runtime'] + [row['episode_key'] for row in plan['episodes']]


@pytest.mark.parametrize('fault,message', [
    ('unrelated_alias', 'input symlink escapes owned roots'),
    ('escaping_symlink', 'input symlink escapes owned roots'),
    ('foreign_runtime_alias', 'runtime checkout/device/provider'),
    ('sha256', 'frozen file changed'),
    ('resolved_path', 'input link resolution changed'),
    ('size_bytes', 'frozen file size changed'),
    ('link_target', 'input symlink target changed'),
])
def test_runtime_alias_rejects_drift(alias_chain, fault, message):
    plan, runtime, record, layout, seen, bind = alias_chain
    if fault == 'unrelated_alias':
        other = layout / 'unrelated-worktree'
        other.symlink_to(plan['worktree'], target_is_directory=True)
        record['path'] = str(other / 'scripts/qd_ed_n32_release.py')
    elif fault == 'escaping_symlink':
        outside = layout / 'outside'; outside.write_text('synthetic outside bytes')
        escaping = Path(runtime['artifact_root']) / 'escaping-file'
        escaping.symlink_to(outside)
        # Even exact hashes and resolution cannot authorize an escaped target.
        record.update(path=str(escaping), sha256=w.sha(outside),
                      resolved_path=str(outside), size_bytes=outside.stat().st_size)
    elif fault == 'foreign_runtime_alias':
        alias = Path(runtime['worktree'])
        alias.unlink(); alias.symlink_to(runtime['artifact_root'], target_is_directory=True)
    elif fault == 'sha256': record['sha256'] = '0' * 64
    elif fault == 'resolved_path': record['resolved_path'] = str(layout / 'wrong')
    elif fault == 'size_bytes': record['size_bytes'] += 1
    elif fault == 'link_target': record['link_target'] = 'wrong-target'
    with pytest.raises((r.GateError, ValueError), match=message):
        release.validate_release(*bind())
    assert seen == []  # Rejected before downstream runtime/manifest gates.
