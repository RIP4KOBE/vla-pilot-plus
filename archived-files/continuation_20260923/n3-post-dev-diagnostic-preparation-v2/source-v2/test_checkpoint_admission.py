"""V2 metadata-only correction tests; all episode fixtures are invented."""
import ast
import copy
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('n3_checkpoint_v2', HERE/'read_full_dev.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
DEFINITION = m.parse((HERE/'dependencies-v2.json').read_bytes())


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value).encode(); path.write_bytes(data)
    return {'path': str(path), 'sha256': m.sha(data)}


def canonical(value):
    return m.sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def metadata_fixture(root):
    originals = [{'episode_key': f't{t}-{a}', 'task_id': t, 'profile': a} for t in range(10) for a in m.ARMS]
    base = dict(source_commit=m.SOURCE, profiles_sha256='a'*64, runtime_manifest_sha256='b'*64,
                runtime_inventory_sha256='c'*64, seed_plan_sha256='d'*64,
                code_files=[{'path': 'synthetic.py', 'sha256': 'e'*64}], candidate_profiles={'N3': {'sha256': 'f'*64}},
                episodes=originals, n3_cohort={'cohort_id': m.COHORT, 'protocol': {'sha256': '1'*64},
                'checkpoint_release': None, 'limits': {'timeout_s': 1800}, 'budget_allocation': {'development': 14},
                'runtime_prerequisites': {'same_gpu': 3}})
    definition = copy.deepcopy(DEFINITION)
    release = copy.deepcopy(definition['checkpoint_admission']['release_metadata'])
    release.update(source_files_sha256=canonical(base['code_files']), protocol_sha256=base['n3_cohort']['protocol']['sha256'],
                   attempt_ids=['synthetic-c0', 'synthetic-q0', 'synthetic-n3'])
    release['evidence'] = [{'path': str(root/'NEVER_OPEN_EVIDENCE'), 'sha256': '0'*64}]
    release_ref = put(root/'release.json', release)
    post = copy.deepcopy(base); post['n3_cohort']['checkpoint_release'] = release_ref
    recovery = copy.deepcopy(post); recovery['episodes'].append(dict(originals[-2], episode_key='retry', retry_of='t9-Q0'))
    base_ref = put(root/'base.json', base)
    revisions = [put(root/'post.json', post), put(root/'recovery.json', recovery)]
    definition['checkpoint_admission'] = dict(base_plan=base_ref, plan_revisions=revisions, checkpoint_release=release_ref,
        release_metadata={k: release[k] for k in DEFINITION['checkpoint_admission']['release_metadata']}, base_checkpoint_value=None)
    authority = {'base_plan': base_ref, 'plan_revisions': revisions}
    return authority, base, originals, definition


def test_exact_null_postcheckpoint_and_recovery_public_metadata_only(tmp_path):
    authority, base, originals, definition = metadata_fixture(tmp_path)
    inputs = m.Inputs(tmp_path)
    plans = m.admit_plans(authority, base, originals, definition, inputs)
    assert len(plans) == 3
    assert len(plans[authority['plan_revisions'][1]['sha256']]['episodes']) == 31
    assert set(inputs.hashes) == {str(tmp_path/name) for name in ('release.json', 'post.json', 'recovery.json')}
    assert not (tmp_path/'NEVER_OPEN_EVIDENCE').exists()


@pytest.mark.parametrize('defect', [
    'base_missing', 'base_reference', 'revision_missing', 'revision_null', 'revision_wrong_path', 'revision_wrong_sha',
    'unexpected_cohort_field', 'scientific_limits', 'resource_budget', 'source', 'code_inventory', 'candidate', 'original_rows',
    'release_schema', 'release_source', 'release_protocol', 'release_code', 'release_cohort', 'release_checks',
    'release_first3', 'release_bytes', 'named_revision_missing', 'named_revision_extra', 'named_revision_wrong', 'named_base_wrong'])
def test_metadata_defects_fail_before_native_or_evidence_reads(tmp_path, defect):
    authority, base, originals, definition = metadata_fixture(tmp_path)
    contract = definition['checkpoint_admission']
    if defect == 'base_missing': del base['n3_cohort']['checkpoint_release']
    elif defect == 'base_reference': base['n3_cohort']['checkpoint_release'] = contract['checkpoint_release']
    elif defect.startswith('named_'):
        authority = copy.deepcopy(authority)
        if defect == 'named_revision_missing': authority['plan_revisions'].pop()
        elif defect == 'named_revision_extra': authority['plan_revisions'].append(authority['plan_revisions'][0])
        elif defect == 'named_revision_wrong': authority['plan_revisions'][0]['sha256'] = '0'*64
        else: authority['base_plan']['path'] = str(tmp_path/'another-base.json')
    elif defect.startswith('release_'):
        path = Path(contract['checkpoint_release']['path']); release = m.parse(path.read_bytes())
        key = {'release_schema': 'schema', 'release_source': 'source_commit', 'release_protocol': 'protocol_sha256',
               'release_code': 'source_files_sha256', 'release_cohort': 'cohort_id', 'release_checks': 'checks',
               'release_first3': 'attempt_ids', 'release_bytes': 'scope'}[defect]
        release[key] = {'finite_action': False} if key == 'checks' else ['wrong'] if key == 'attempt_ids' else 'wrong'
        ref = put(path, release)
        # Rebind file SHA for semantic negative cases; expected metadata stays fixed.
        if defect != 'release_bytes': contract['checkpoint_release'] = ref
    else:
        ref = contract['plan_revisions'][1]; path = Path(ref['path']); plan = m.parse(path.read_bytes())
        if defect == 'revision_missing': del plan['n3_cohort']['checkpoint_release']
        elif defect == 'revision_null': plan['n3_cohort']['checkpoint_release'] = None
        elif defect == 'revision_wrong_path': plan['n3_cohort']['checkpoint_release']['path'] = str(tmp_path/'wrong.json')
        elif defect == 'revision_wrong_sha': plan['n3_cohort']['checkpoint_release']['sha256'] = '0'*64
        elif defect == 'unexpected_cohort_field': plan['n3_cohort']['new_permission'] = True
        elif defect == 'scientific_limits': plan['n3_cohort']['limits']['timeout_s'] = 1
        elif defect == 'resource_budget': plan['n3_cohort']['budget_allocation']['development'] = 0
        elif defect == 'source': plan['source_commit'] = '0'*40
        elif defect == 'code_inventory': plan['code_files'][0]['sha256'] = '0'*64
        elif defect == 'candidate': plan['candidate_profiles']['N3']['sha256'] = '0'*64
        else: plan['episodes'][0]['profile'] = 'changed'
        contract['plan_revisions'][1] = put(path, plan)
    inputs = m.Inputs(tmp_path)
    with pytest.raises(ValueError): m.admit_plans(authority, base, originals, definition, inputs)
    assert not any(p.endswith('.pt') or 'NEVER_OPEN' in p for p in inputs.hashes)


def full_fixture(root):
    """Reuse only v1's synthetic30 metadata builder, not its old tests/readers."""
    old = m.dependency_module('v1_synthetic_fixture', DEFINITION['test_sources']['v1_wrapper_fixture'])
    manifest, auth = old.identity_fixture(root, recovery=True)
    report = m.parse(Path(manifest['matrix_report']['path']).read_bytes())
    authority = report['input_manifest']; old_base_ref = authority['base_plan']; old_recovery_ref = authority['plan_revisions'][0]
    base = m.parse(Path(old_base_ref['path']).read_bytes()); base['n3_cohort']['checkpoint_release'] = None
    release = copy.deepcopy(DEFINITION['checkpoint_admission']['release_metadata'])
    release.update(source_files_sha256=canonical(base['code_files']), protocol_sha256=base['n3_cohort']['protocol']['sha256'],
                   attempt_ids=[c['valid_attempt_id'] for c in report['cells'][:3]])
    release_ref = put(root/'release.json', release)
    post = copy.deepcopy(base); post['n3_cohort']['checkpoint_release'] = release_ref
    recovery = m.parse(Path(old_recovery_ref['path']).read_bytes()); recovery['n3_cohort']['checkpoint_release'] = release_ref
    base_ref = put(Path(old_base_ref['path']), base)
    post_ref = put(root/'post.json', post); recovery_ref = put(Path(old_recovery_ref['path']), recovery)
    for cell in report['cells']:
        saved = next(a for a in cell['attempts'] if a['status'] == 'complete_valid')
        terminal = saved['terminal']; terminal['plan_sha256'] = recovery_ref['sha256'] if terminal.get('retry_of') else base_ref['sha256']
        saved['references']['terminal'] = put(Path(saved['references']['terminal']['path']), terminal)
    authority.update(base_plan=base_ref, plan_revisions=[post_ref, recovery_ref])
    authority_ref = put(Path(manifest['matrix_report_input']['path']), authority)
    report['input_manifest_sha256'] = authority_ref['sha256']
    report_ref = put(Path(manifest['matrix_report']['path']), report)
    manifest.update(matrix_report=report_ref, matrix_report_input=authority_ref); auth['reviewed_matrix_report'] = report_ref
    definition = copy.deepcopy(DEFINITION)
    definition['checkpoint_admission'] = dict(base_plan=base_ref, plan_revisions=[post_ref, recovery_ref], checkpoint_release=release_ref,
        release_metadata=release, base_checkpoint_value=None)
    return manifest, auth, definition


def test_real_all30_admission_accepts_metadata_recovery_without_decode(tmp_path, monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    manifest, auth, definition = full_fixture(tmp_path)
    modules = m.dependencies(definition); calls = []
    monkeypatch.setattr(modules['task0'].torch, 'load', lambda *a, **k: calls.append(True))
    inputs = m.Inputs(tmp_path)
    _, rows = m.admit(manifest, auth, definition, modules, inputs)
    assert len(rows) == 30 and rows[1]['terminal']['retry_of'] == 't0-Q0'
    assert len([p for p in inputs.hashes if p.endswith('.pt')]) == 30
    assert calls == [] and not any('NEVER_OPEN' in p for p in inputs.hashes)


def test_checkpoint_first3_identity_mismatch_stops_before_native_hash(tmp_path, monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    manifest, auth, definition = full_fixture(tmp_path)
    contract = definition['checkpoint_admission']
    release = m.parse(Path(contract['checkpoint_release']['path']).read_bytes()); release['attempt_ids'][0] = 'foreign'
    contract['release_metadata'] = release
    contract['checkpoint_release'] = put(Path(contract['checkpoint_release']['path']), release)
    for i, ref in enumerate(contract['plan_revisions']):
        value = m.parse(Path(ref['path']).read_bytes()); value['n3_cohort']['checkpoint_release'] = contract['checkpoint_release']
        contract['plan_revisions'][i] = put(Path(ref['path']), value)
    # Rebind public authority to the deliberately wrong certificate; cell universe remains unchanged.
    authority = m.parse(Path(manifest['matrix_report_input']['path']).read_bytes()); authority['plan_revisions'] = contract['plan_revisions']
    authority_ref = put(Path(manifest['matrix_report_input']['path']), authority)
    report = m.parse(Path(manifest['matrix_report']['path']).read_bytes()); report.update(input_manifest=authority, input_manifest_sha256=authority_ref['sha256'])
    report_ref = put(Path(manifest['matrix_report']['path']), report)
    manifest.update(matrix_report_input=authority_ref, matrix_report=report_ref); auth['reviewed_matrix_report'] = report_ref
    modules = m.dependencies(definition); inputs = m.Inputs(tmp_path)
    with pytest.raises(ValueError, match='checkpoint_first3_representatives_differ'):
        m.admit(manifest, auth, definition, modules, inputs)
    assert not any(p.endswith('.pt') for p in inputs.hashes)


def test_unchanged_scientific_function_bytes_and_old_dependency_hashes():
    old_dir = Path(DEFINITION['test_sources']['v1_wrapper_fixture']['path']).parent
    old_source = (old_dir/'read_full_dev.py').read_text(); new_source = (HERE/'read_full_dev.py').read_text()
    def functions(source):
        return {node.name: ast.get_source_segment(source, node) for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
    previous, current = functions(old_source), functions(new_source)
    for name in previous.keys() - {'admit', 'run'}: assert previous[name] == current[name], name
    old_definition = m.parse((old_dir/'dependencies-v1.json').read_bytes())
    for key in ('modules', 'reviewed_source_sha256', 'called_functions', 'closure', 'python_version', 'torch_version'):
        assert DEFINITION[key] == old_definition[key]
