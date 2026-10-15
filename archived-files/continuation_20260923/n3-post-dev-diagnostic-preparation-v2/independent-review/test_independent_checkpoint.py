"""Independent metadata-only synthetic checks; no episode or tensor reader."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

E = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-decision-evidence-20260923/docs/03_evidence/qd_ed_final/continuation_20260923/n3-post-dev-diagnostic-preparation-v2')
READER_SHA = '731e8dde617d89cf538caf13c11f23b267b03225c32f93660fe9a1d731e8ae40'
assert hashlib.sha256((E/'read_full_dev.py').read_bytes()).hexdigest() == READER_SHA
spec = importlib.util.spec_from_file_location('independent_checkpoint_v2', E/'read_full_dev.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def put(path, obj):
    data = json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
    path.write_bytes(data)
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}


def fixture(root):
    # This is invented metadata, not a replay or copy of a scientific record.
    original = [dict(episode_key='one', task_id=0, profile='C0')]
    base = {k: str(i)*64 for i, k in enumerate(m.BINDING, 1)}
    base.update(source_commit=m.SOURCE, code_files=[{'path': 'synthetic.py', 'sha256': 'a'*64}],
                candidate_profiles={'N3': {'quality_mode': 'executed_feedback_v1'}}, episodes=original,
                n3_cohort={'cohort_id': m.COHORT, 'protocol': {'sha256': 'b'*64},
                           'checkpoint_release': None, 'science': {'weights': [1, 3]},
                           'resource': {'episodes': 30, 'gpu_hours': 48}})
    checks = ['finite_action', 'source_compute', 'raw_stage_separation', 'substantive_qd_activation',
              'exact_native_past_feedback_timing_selection', 'native_feedback_bundle_alignment',
              'runtime_tracking_validity', 'substantive_feedback_search_activity']
    release = dict(schema='qd-ed-n3-checkpoint-v1', cohort_id=m.COHORT, source_commit=m.SOURCE,
                   source_files_sha256=m.sha(json.dumps(base['code_files'], sort_keys=True, separators=(',', ':')).encode()),
                   protocol_sha256='b'*64, runtime_tracking_validity='known_valid',
                   attempt_ids=['synthetic-c0', 'synthetic-q0', 'synthetic-n3'], checks={k: True for k in checks})
    expected = copy.deepcopy(release)
    release['evidence'] = [{'path': str(root/'NEVER_READ.pt'), 'sha256': 'c'*64}]
    release_ref = put(root/'release.json', release)
    post = copy.deepcopy(base)
    post['n3_cohort']['checkpoint_release'] = release_ref
    recovery = copy.deepcopy(post)
    recovery['episodes'].append(dict(original[0], episode_key='retry', retry_of='synthetic-invalid'))
    base_ref = put(root/'base.json', base)
    refs = [put(root/'post.json', post), put(root/'recovery.json', recovery)]
    definition = {'checkpoint_admission': dict(base_plan=base_ref, plan_revisions=refs,
        checkpoint_release=release_ref, release_metadata=expected, base_checkpoint_value=None)}
    return {'base_plan': copy.deepcopy(base_ref), 'plan_revisions': copy.deepcopy(refs)}, base, original, definition


class Reads(m.Inputs):
    def __init__(self, root):
        super().__init__(root)
        self.calls = []

    def bytes(self, ref):
        self.calls.append(ref['path'])
        assert Path(ref['path']).name in {'release.json', 'post.json', 'recovery.json'}
        return super().bytes(ref)


def change_revision(root, authority, definition, edit):
    contract = definition['checkpoint_admission']
    path = Path(contract['plan_revisions'][1]['path'])
    value = json.loads(path.read_bytes())
    edit(value)
    ref = put(path, value)
    authority['plan_revisions'][1] = copy.deepcopy(ref)
    contract['plan_revisions'][1] = ref


def test_exact_null_post_and_recovery_only_read_three_metadata_files(tmp_path):
    authority, base, originals, definition = fixture(tmp_path)
    inputs = Reads(tmp_path)
    plans = m.admit_plans(authority, base, originals, definition, inputs)
    assert len(plans) == 3
    assert len(plans[authority['plan_revisions'][1]['sha256']]['episodes']) == 2
    assert [Path(p).name for p in inputs.calls] == ['release.json', 'post.json', 'recovery.json']
    inputs.finish()


@pytest.mark.parametrize('value', ['missing', 'reference'])
def test_base_requires_present_null_before_any_read(tmp_path, value):
    authority, base, originals, definition = fixture(tmp_path)
    if value == 'missing':
        del base['n3_cohort']['checkpoint_release']
    else:
        base['n3_cohort']['checkpoint_release'] = definition['checkpoint_admission']['checkpoint_release']
    inputs = Reads(tmp_path)
    with pytest.raises(ValueError, match='base_checkpoint_must_be_explicit_null'):
        m.admit_plans(authority, base, originals, definition, inputs)
    assert inputs.calls == []


@pytest.mark.parametrize('value', ['missing', 'null', 'wrong_ref'])
def test_revision_requires_exact_certificate_reference(tmp_path, value):
    authority, base, originals, definition = fixture(tmp_path)
    def edit(plan):
        if value == 'missing': del plan['n3_cohort']['checkpoint_release']
        elif value == 'null': plan['n3_cohort']['checkpoint_release'] = None
        else: plan['n3_cohort']['checkpoint_release']['sha256'] = '0'*64
    change_revision(tmp_path, authority, definition, edit)
    with pytest.raises(ValueError, match='revision_checkpoint_reference_differs'):
        m.admit_plans(authority, base, originals, definition, Reads(tmp_path))


@pytest.mark.parametrize('value', ['science', 'resource', 'new_cohort_key', 'runtime_inventory'])
def test_noncheckpoint_conditions_cannot_change_even_with_rehashed_plan(tmp_path, value):
    authority, base, originals, definition = fixture(tmp_path)
    def edit(plan):
        if value == 'science': plan['n3_cohort']['science']['weights'] = [3, 1]
        elif value == 'resource': plan['n3_cohort']['resource']['episodes'] = 31
        elif value == 'new_cohort_key': plan['n3_cohort']['extra_permission'] = True
        else: plan['runtime_inventory_sha256'] = '0'*64
    change_revision(tmp_path, authority, definition, edit)
    with pytest.raises(ValueError, match='revision_changes_frozen_condition'):
        m.admit_plans(authority, base, originals, definition, Reads(tmp_path))


def test_integer_one_is_not_a_true_checkpoint_check(tmp_path):
    authority, base, originals, definition = fixture(tmp_path)
    contract = definition['checkpoint_admission']
    path = Path(contract['checkpoint_release']['path'])
    release = json.loads(path.read_bytes())
    release['checks']['finite_action'] = 1
    # Deliberately rehash: JSON equality equates 1 and True; the explicit is-True gate must reject.
    contract['checkpoint_release'] = put(path, release)
    with pytest.raises(ValueError, match='checkpoint_source_binding_differs'):
        m.admit_plans(authority, base, originals, definition, Reads(tmp_path))


def test_unpinned_revision_rejected_before_reads(tmp_path):
    authority, base, originals, definition = fixture(tmp_path)
    authority['plan_revisions'].append(copy.deepcopy(authority['plan_revisions'][0]))
    inputs = Reads(tmp_path)
    with pytest.raises(ValueError, match='named_plan_references_differ'):
        m.admit_plans(authority, base, originals, definition, inputs)
    assert inputs.calls == []


def test_certificate_bytes_cannot_change_outside_subset_metadata(tmp_path):
    authority, base, originals, definition = fixture(tmp_path)
    path = Path(definition['checkpoint_admission']['checkpoint_release']['path'])
    release = json.loads(path.read_bytes())
    release['extra_permission'] = True
    put(path, release)
    with pytest.raises(ValueError, match='input_sha_mismatch'):
        m.admit_plans(authority, base, originals, definition, Reads(tmp_path))
