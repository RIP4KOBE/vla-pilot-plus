"""Exact new command composition with separate operational/scientific source."""
import hashlib
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n32_bridge as old
from scripts import qd_ed_n32r3_contract as c
from scripts import qd_ed_n32r3_paths as paths

ROOT, profiles, attest_loaded = old.ROOT, old.profiles, old.attest_loaded
RUNTIME_SOURCES, runner = old.RUNTIME_SOURCES, old.runner


def source_paths(root=ROOT):
    return old.source_paths(root) | {str(p.relative_to(root)) for pattern in
                                   ('scripts/qd_ed_n32r3_*.py', 'tests/test_n32r3*.py') for p in Path(root).glob(pattern)}


def command(plan, runtime, row):
    # Only the scientific runtime binding retains the original scientific commit.
    # The manifest/worker/release separately attest the actual operational commit.
    argv, output = old.command({**plan, 'source': plan['scientific_source']}, runtime, row)
    candidates = c.read_ref(plan['command_candidates'])
    matches = [x for x in candidates['commands'] if x['new_attempt_id'] == row['episode_key']]
    w.require(len(matches) == 1, 'exact command candidate')
    candidate = matches[0]
    paths.verify_original(candidate)
    expected_argv, expected_output = candidate['proposed_argv'], candidate['proposed_output_dir']
    if 'command_path_amendment' in plan:
        amendment = paths.verify_amendment(plan)
        pair = next(x for x in amendment['pairs'] if x['new_attempt_id'] == row['episode_key'])
        w.require(pair['row'] == row, 'amended command row')
        expected_argv, expected_output = pair['amended_argv'], pair['amended_output_dir']
    w.require(argv == expected_argv and str(output) == expected_output, 'non-identity command change')
    return argv, output


def manifest(plan, runtime, row):
    task = runtime['tasks'][str(row['task_id'])]
    files = {v['path']: v['sha256'] for v in runtime['files']}
    w.require(task['task_id'] == row['task_id'] and task['init_index'] == row['init_index']
              and files[task['init_path']] == row['init_file_sha256'] and files[task['bddl_path']] == row['bddl_sha256'], 'runtime task hashes')
    argv, output = command(plan, runtime, row)
    config, resolved = old.compose_launch(argv, plan['worktree'])
    w.require(config['backend']['libero']['max_episode_steps'] == 720
              and config['policy']['rdt']['control_frequency'] == 20
              and config['policy']['rdt']['action_chunk_horizon'] == 8, 'frozen episode schedule')
    index = {x['path']: x['sha256'] for x in plan['scientific_source']['files']}
    expected = None
    if row['profile'] == 'N32':
        expected = {'binding': resolved['n32_runtime_binding'],
                    'config_sha256': hashlib.sha256(json.dumps(resolved, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                    'source_hashes': {**{name: index['core/'+name] for name in RUNTIME_SOURCES}, 'main.py': index['main.py']}}
    result = {'schema': 'n32r3-external-runtime-v1', 'row': row, 'source': plan['source'],
              'runtime': plan['runtime'], 'argv': argv, 'output_dir': str(output),
              'composed_config_sha256': w.canonical_sha(config), 'resolved_config': resolved,
              'expected_runtime': expected, 'continuation': c.commitments(plan, row)}
    return result


def verify_manifest(reference, plan, runtime, row):
    w.verify_source(plan['worktree'], plan['source'])
    w.require(source_paths(Path(plan['worktree'])) <= {v['path'] for v in plan['source']['files']}, 'complete continuation source')
    w.require(w.read_ref(plan['runtime']) == runtime, 'runtime changed')
    actual = w.read_ref(reference)
    w.require(actual == json.loads(json.dumps(manifest(plan, runtime, row))), 'external manifest/config/task/source differs')
    return actual


def semantic_key(plan, manifest):
    """Exact command normalization, after command() has checked bound substitutions."""
    row = manifest['row']
    candidates = c.read_ref(plan['command_candidates'])['commands']
    candidate = next(x for x in candidates if x['new_attempt_id'] == row['episode_key'])
    parent = c.read_ref(candidate['parent_expected_manifest'])
    return w.canonical_sha({'row': {k: row[k] for k in c.SEMANTIC_FIELDS},
                            'scientific_source': plan['scientific_source'],
                            'parent_runtime': parent['runtime'], 'normalized_argv': parent['argv'],
                            'normalized_config_sha256': parent['composed_config_sha256']})
