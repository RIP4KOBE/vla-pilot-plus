"""CPU-only prospective amendment tests with real hash-bound metadata."""
import copy
from pathlib import Path
import pytest
from scripts import qd_ed_n32r3_paths as paths, qd_ed_n32r3_bridge as bridge
from scripts import qd_ed_n32r3_history as history, qd_ed_n32r3_contract as c
from scripts import qd_ed_n32r3_release as release, qd_ed_n23_worker as w
from test_n32r3_continuation import fixture, write
from test_n32r3_execution import release_chain

ORIGINAL_PREPARATION_ANCHOR = history.verify_preparation_anchor


@pytest.fixture
def amended(fixture, tmp_path):
    plan, events, mapping, parent = fixture
    root = tmp_path / 'owning'; root.mkdir()
    lexical = tmp_path / 'lexical'; lexical.symlink_to(root, target_is_directory=True)
    plan['artifact_root'] = str(root / 'prospective')
    plan['runtime'] = write(tmp_path / 'new-runtime.json', {'artifact_root': str(root)})
    commands = []
    for entry in mapping['proposed_cells']:
        row = entry['proposed_row']; old_id = entry['old_attempt_id']
        original = c.read_ref(entry['parent_expected_manifest'])
        old_output = original['output_dir']
        original['argv'] += [field + '=' + old_output + suffix for field, suffix in paths.OUTPUT_FIELDS.items()]
        ref = write(Path(entry['parent_expected_manifest']['path']), original)
        entry['parent_expected_manifest'] = parent['expected_manifests'][old_id] = ref
        output = str(lexical / 'prospective' / 'attempts' / row['episode_key'])
        argv = original['argv'][:3] + [field + '=' + output + suffix for field, suffix in paths.OUTPUT_FIELDS.items()]
        commands.append({'old_attempt_id': old_id, 'new_attempt_id': row['episode_key'],
                         'parent_expected_manifest': ref, 'old_argv': original['argv'],
                         'proposed_argv': argv, 'proposed_output_dir': output,
                         'exact_changes': paths.changes(original['argv'], argv)})
    plan['parent_plan'] = write(tmp_path / 'parent-updated.json', parent)
    expected = {'schema': 'n32-execution-release-v1', 'approved': True, 'plan': plan['parent_plan'],
                **{k: parent[k] for k in ('authority', 'protocol', 'source', 'runtime', 'limits', 'phase_authorization')}}
    plan['parent_review'] = write(tmp_path / 'parent-review-updated.json',
        {**expected, 'schema': 'n32-root-production-review-v1', 'decision': 'APPROVED'})
    plan['parent_release'] = write(tmp_path / 'parent-release-updated.json', {**expected, 'root_review': plan['parent_review']})
    mapping['parent_plan'] = plan['parent_plan']
    mapping['continuity_evidence'] = write(tmp_path / 'evidence-updated.json', {'inputs': {
        'plan.frozen.v1.json': plan['parent_plan'], 'execution-release-v1.json': plan['parent_release'],
        'root-production-review-v1.json': plan['parent_review']}})
    plan['command_candidates'] = mapping['command_candidates'] = write(tmp_path / 'commands-updated.json', {'commands': commands})
    plan['carry_forward_map'] = write(tmp_path / 'map-updated.json', mapping)
    amendment = paths.expected_amendment(plan)
    plan['command_path_amendment'] = write(tmp_path / 'amendment.json', amendment)
    return plan, amendment, commands, mapping


def test_exact16_amendment_and_bridge(amended, monkeypatch):
    plan, amendment, commands, mapping = amended
    assert paths.verify_amendment(plan) == amendment
    assert len(amendment['pairs']) == 16 and amendment['release_enabled'] is False
    for row, pair in zip(plan['episodes'], amendment['pairs']):
        monkeypatch.setattr(bridge.old, 'command', lambda *args: (pair['amended_argv'], Path(pair['amended_output_dir'])))
        assert bridge.command(plan, {}, row) == (pair['amended_argv'], Path(pair['amended_output_dir']))
        assert c.commitments(plan, row)['command_path_amendment'] == plan['command_path_amendment']
        # Removing adoption cannot silently canonicalize the command.
        unamended = {k: v for k, v in plan.items() if k != 'command_path_amendment'}
        assert 'command_path_amendment' not in c.commitments(unamended, row)
        with pytest.raises(ValueError, match='non-identity command change'):
            bridge.command(unamended, {}, row)
    assert len(mapping['accepted_cells']) == 14


@pytest.mark.parametrize('fault', ['seed', 'runtime_binding', 'output', 'equivalent_lexical', 'wrong_root',
    'runtime', 'scientific_source', 'row', 'drop', 'duplicate', 'reorder', 'parent', 'old_argv', 'enabled', 'extra'])
def test_amendment_exact_equality(amended, tmp_path, fault):
    plan, amendment, _, _ = amended
    pair = amendment['pairs'][0]
    if fault == 'seed': pair['amended_argv'][2] = 'seed=999'
    elif fault == 'runtime_binding': pair['amended_argv'].append('main.eds_config.n32_runtime_binding=changed')
    elif fault == 'output': pair['amended_output_dir'] += '-other'
    elif fault == 'equivalent_lexical': pair['amended_argv'][3] += '/.'
    elif fault == 'wrong_root': amendment['artifact_root'] = str(tmp_path / 'foreign')
    elif fault in ('runtime', 'scientific_source'): amendment[fault] = {}
    elif fault == 'row': pair['row'] = {**pair['row'], 'task_id': 99}
    elif fault == 'drop': amendment['pairs'].pop()
    elif fault == 'duplicate': amendment['pairs'][-1] = copy.deepcopy(pair)
    elif fault == 'reorder': amendment['pairs'].reverse()
    elif fault == 'parent': pair['parent_expected_manifest'] = plan['parent_plan']
    elif fault == 'old_argv': pair['original_argv'][2] = 'seed=999'
    elif fault == 'enabled': amendment['release_enabled'] = True
    else: amendment['approved'] = True
    plan['command_path_amendment'] = write(tmp_path / 'altered-amendment.json', amendment)
    with pytest.raises(ValueError): paths.verify_amendment(plan)


@pytest.mark.parametrize('fault', ['old_argv', 'delta', 'parent', 'drop', 'duplicate', 'arbitrary_output', 'duplicate_field', 'map', 'root', 'runtime_root'])
def test_originals_still_validated(amended, tmp_path, fault):
    plan, amendment, commands, mapping = amended
    candidate = commands[0]
    if fault == 'old_argv': candidate['old_argv'][2] = 'seed=999'
    elif fault == 'delta': candidate['exact_changes'] = []
    elif fault == 'parent': candidate['parent_expected_manifest'] = commands[1]['parent_expected_manifest']
    elif fault == 'drop': commands.pop()
    elif fault == 'duplicate': commands[-1] = copy.deepcopy(candidate)
    elif fault == 'arbitrary_output':
        candidate['proposed_output_dir'] += '-other'
        candidate['proposed_argv'] = [x + '-other' if x.startswith('hydra.run.dir=') else x for x in candidate['proposed_argv']]
        candidate['exact_changes'] = paths.changes(candidate['old_argv'], candidate['proposed_argv'])
    elif fault == 'duplicate_field': candidate['proposed_argv'].append(candidate['proposed_argv'][3])
    elif fault == 'map': mapping['accepted_cells'].pop()
    elif fault == 'root': plan['artifact_root'] = str(tmp_path / 'foreign')
    elif fault == 'runtime_root': plan['runtime'] = write(tmp_path / 'foreign-runtime.json', {'artifact_root': str(tmp_path / 'foreign')})
    plan['command_candidates'] = mapping['command_candidates'] = write(tmp_path / 'changed-commands.json', {'commands': commands})
    plan['carry_forward_map'] = write(tmp_path / 'changed-map.json', mapping)
    # Even deriving a fresh hash-bound amendment cannot legitimize these changes.
    with pytest.raises((ValueError, bridge.runner.GateError)): paths.expected_amendment(plan)


def test_original_review_anchor_not_replaced(amended, monkeypatch):
    plan, _, _, _ = amended
    monkeypatch.setattr(history, 'verify_preparation_anchor', ORIGINAL_PREPARATION_ANCHOR)
    with pytest.raises(ValueError, match='independent preparation review anchor'):
        paths.verify_amendment(plan)


def test_amendment_digest_required(amended):
    plan, _, _, _ = amended
    Path(plan['command_path_amendment']['path']).write_text('{}')
    with pytest.raises(ValueError): paths.verify_amendment(plan)


def test_actual_command_still_exact(amended, monkeypatch):
    plan, amendment, _, _ = amended
    pair = amendment['pairs'][0]
    argv = list(pair['amended_argv']); argv[2] = 'seed=999'
    monkeypatch.setattr(bridge.old, 'command', lambda *args: (argv, Path(pair['amended_output_dir'])))
    with pytest.raises(ValueError, match='non-identity command change'):
        bridge.command(plan, {}, plan['episodes'][0])


@pytest.mark.parametrize("missing", ["release", "review"])
def test_release_must_commit_amendment(release_chain, tmp_path, missing):
    plan, plan_ref, release_ref, *_ = release_chain
    plan['command_path_amendment'] = write(tmp_path / 'unreviewed-amendment.json', {})
    changed_plan_ref = write(tmp_path / 'changed-plan.json', plan)
    detached = w.read_ref(release_ref)
    review = w.read_ref(detached['root_review'])
    detached['plan'] = review['plan'] = changed_plan_ref
    if missing == 'review':
        detached['continuation'] = c.commitments(plan, plan['episodes'][0])
    detached['root_review'] = write(tmp_path / 'changed-review.json', review)
    changed_release = write(tmp_path / 'changed-release.json', detached)
    with pytest.raises(ValueError, match='external release differs' if missing == 'release' else 'root review differs'):
        release.validate_release(changed_plan_ref, changed_release)


def test_manifest_commits_amendment_and_rejects_omission(amended, tmp_path, monkeypatch):
    plan, _, _, _ = amended
    row = plan['episodes'][1]  # C0: no scientific resolver mock needed.
    runtime = c.read_ref(plan['runtime'])
    runtime.update(tasks={str(row['task_id']): {'task_id': row['task_id'], 'init_index': row['init_index'],
        'init_path': 'init', 'bddl_path': 'bddl'}}, files=[{'path': 'init', 'sha256': row['init_file_sha256']},
        {'path': 'bddl', 'sha256': row['bddl_sha256']}])
    plan['runtime'] = write(tmp_path / 'manifest-runtime.json', runtime)
    plan['command_path_amendment'] = write(tmp_path / 'manifest-amendment.json', paths.expected_amendment(plan))
    pair = paths.verify_amendment(plan)['pairs'][1]
    monkeypatch.setattr(bridge.old, 'command', lambda *args: (pair['amended_argv'], Path(pair['amended_output_dir'])))
    config = {'backend': {'libero': {'max_episode_steps': 720}},
              'policy': {'rdt': {'control_frequency': 20, 'action_chunk_horizon': 8}}}
    monkeypatch.setattr(bridge.old, 'compose_launch', lambda *args: (config, {}))
    monkeypatch.setattr(bridge, 'source_paths', lambda *args: set())
    plan['source']['files'] = []
    manifest = bridge.manifest(plan, runtime, row)
    assert manifest['continuation']['command_path_amendment'] == plan['command_path_amendment']
    ref = write(tmp_path / 'fresh-manifest.json', manifest)
    assert bridge.verify_manifest(ref, plan, runtime, row) == manifest
    del manifest['continuation']['command_path_amendment']
    with pytest.raises(ValueError, match='external manifest/config/task/source differs'):
        bridge.verify_manifest(write(tmp_path / 'omitted-manifest.json', manifest), plan, runtime, row)
