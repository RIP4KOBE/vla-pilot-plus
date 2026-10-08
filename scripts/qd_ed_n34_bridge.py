"""Prospective N34 composition; candidate evidence never supplies trust anchors."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n32_bridge as helpers
from scripts import qd_ed_n34_source as closure

ROOT = Path(__file__).resolve().parents[1]
MODE = 'observed_jaw_approach_v1'
SCIENTIFIC_COMMIT = '71ffff1a0f70d9874b309db9ef1843c02bf17ebf'
runner = helpers.runner
compose_launch = helpers.compose_launch
resolve_constructor = helpers.resolve_constructor


def runtime_sources(root=ROOT):
    tree = ast.parse((Path(root) / 'core/qd_observed_jaw_approach.py').read_text())
    return ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign)
                                and any(isinstance(t, ast.Name) and t.id == 'SOURCE_FILES' for t in n.targets)))


RUNTIME_SOURCES = runtime_sources()


def source_paths(root=ROOT):
    root = Path(root)
    paths = helpers.source_paths(root)
    for folder, pattern in (('scripts', '*.py'), ('tests', '*n34*.py'), ('docs/experiments', 'n34*.md')):
        paths.update(str(p.relative_to(root)) for p in (root / folder).glob(pattern))
    # Keep deleted committed patches visible; include new local files so the
    # existing source_record check rejects bytes that are not committed.
    raw = w._source_git(root, 'ls-tree', '-r', '--name-only', '-z', 'HEAD', '--', 'patches')
    paths.update(name.decode() for name in raw.split(b'\0') if name
                 and Path(name.decode()).suffix == '.py')
    paths.update(str(p.relative_to(root)) for p in (root / 'patches').rglob('*.py'))
    paths.add('configs/qd_ed_final/candidate_n34.json')
    paths.update(closure.dependency_paths(root))
    return paths


def scientific_paths(root=ROOT):
    root = Path(root)
    paths = set(runtime_sources(root)) | {'configs/qd_ed_final/candidate_n34.json',
        'configs/qd_ed_final/n4_observed_baseline_profiles.json',
        'configs/qd_ed_final/n31_dev_task_identities.json',
        'scripts/qd_ed_n34_native.py', 'scripts/qd_ed_n34_reference.py'}
    for folder, pattern in (('configs', '*.yaml'), ('core', '*.py'), ('utils', '*.py')):
        paths.update(str(p.relative_to(root)) for p in (root / folder).rglob(pattern))
    paths.update(closure.rdt_paths(root, SCIENTIFIC_COMMIT))
    return paths


def profiles(root=ROOT):
    root = Path(root)
    baseline = root / 'configs/qd_ed_final/n4_observed_baseline_profiles.json'
    result = json.loads(baseline.read_text())
    w.require(set(result['profiles']) == {'C0', 'Q0'}, 'closed baseline profiles')
    candidate = json.loads((root / 'configs/qd_ed_final/candidate_n34.json').read_text())
    q0 = result['profiles']['Q0']
    w.require(candidate['profile'] == {**q0['restored_profile'], 'capture_dwell_proposal_mode': 'off',
                                     'observed_jaw_approach_mode': MODE}, 'N34 sole science delta')
    w.require(candidate['baseline_provenance']['sha256'] == w.sha(baseline), 'baseline hash')
    active = copy.deepcopy(q0)
    active['historical_label'] = 'N34'
    active['restored_profile'] = copy.deepcopy(candidate['profile'])
    delta = {'capture_dwell_proposal_mode': 'off', 'archive_eligible_capture_mode': 'off',
             'observed_jaw_approach_mode': MODE}
    active['resolved_eds_config'].update(delta)
    active['static_override_values'].update({'main.eds_config.' + k: v for k, v in delta.items()})
    active['hydra_overrides'] = [f'{k}={runner.hydra(v)}' for k, v in active['static_override_values'].items()]
    result['profiles']['N34'] = active
    return result


def command(plan, runtime, row):
    from scripts import qd_ed_n34_contract as c
    w.require(row in plan['episodes'] and row in c.expected_rows(plan['worktree']), 'exact fresh N34 matrix row')
    argv, output = runner.build_command(plan, profiles(plan['worktree']), runtime, row, row['episode_key'])
    if row['profile'] == 'N34':
        binding = {'task_id': row['task_id'], 'source_commit': plan['scientific_source']['commit'], 'run_id': row['episode_key']}
        argv.append('main.eds_config.n34_runtime_binding={' + ','.join(f'{k}:{runner.hydra(v)}' for k,v in binding.items()) + '}')
    return argv, output


def manifest(plan, runtime, row):
    task = runtime['tasks'][str(row['task_id'])]
    files = {v['path']: v['sha256'] for v in runtime['files']}
    w.require(task['task_id'] == row['task_id'] and task['init_index'] == row['init_index']
              and files[task['init_path']] == row['init_file_sha256']
              and files[task['bddl_path']] == row['bddl_sha256'], 'runtime task input hashes')
    argv, output = command(plan, runtime, row)
    config, resolved = compose_launch(argv, plan['worktree'])
    w.require(config['backend']['libero']['max_episode_steps'] == 720
              and config['policy']['rdt']['control_frequency'] == 20
              and config['policy']['rdt']['action_chunk_horizon'] == 8, 'frozen schedule')
    w.require(resolved['capture_dwell_proposal_mode'] == resolved['archive_eligible_capture_mode'] == 'off', 'exclusive N34 mode')
    w.require(resolved['observed_jaw_approach_mode'] == (MODE if row['profile'] == 'N34' else 'off')
              and resolved['n32_runtime_binding'] is None, 'wrong profile binding')
    expected = None
    if row['profile'] == 'N34':
        binding = {'task_id': row['task_id'], 'source_commit': plan['scientific_source']['commit'], 'run_id': row['episode_key']}
        w.require(resolved['n34_runtime_binding'] == binding, 'prospective runtime binding differs')
        index = {x['path']: x['sha256'] for x in plan['scientific_source']['files']}
        expected = {'binding': binding,
                    'config_sha256': hashlib.sha256(json.dumps(resolved, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                    'source_hashes': {name: index[name] for name in runtime_sources(plan['worktree'])}}
    else:
        w.require(resolved['n34_runtime_binding'] is None, 'control N34 binding')
    return {'schema': 'n34-external-runtime-v1', 'row': row, 'source': plan['source'],
            'scientific_source': plan['scientific_source'], 'runtime': plan['runtime'],
            'runtime_closure': plan['runtime_closure'], 'controller_semantics': plan['controller_semantics'],
            'argv': argv, 'output_dir': str(output), 'composed_config_sha256': w.canonical_sha(config),
            'resolved_config': resolved, 'expected_runtime': expected}


def verify_sources(plan):
    root = Path(plan['worktree'])
    closure.verify_source(root, plan['source'])
    closure.verify_source(root, plan['scientific_source'], commit=SCIENTIFIC_COMMIT)
    w.require(source_paths(root) <= {x['path'] for x in plan['source']['files']}, 'operational source closure incomplete')
    w.require(scientific_paths(root) <= {x['path'] for x in plan['scientific_source']['files']}, 'scientific source closure incomplete')
    operational = {x['path']: x['sha256'] for x in plan['source']['files']}
    w.require(all(operational.get(x['path']) == x['sha256'] for x in plan['scientific_source']['files']), 'scientific/operational source differs')


def verify_manifest(reference, plan, runtime, row):
    verify_sources(plan)
    w.require(w.read_ref(plan['runtime']) == runtime, 'runtime changed')
    closure.verify_runtime(w.read_ref(plan['runtime_closure']), plan['runtime'])
    actual = w.read_ref(reference)
    w.require(actual == json.loads(json.dumps(manifest(plan, runtime, row))), 'external manifest/config/task/source differs')
    return actual


def attest_loaded(root, source):
    return closure.attest_loaded(root, source)
