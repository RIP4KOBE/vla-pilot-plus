"""Prospective N32 launch/config/source bridge; no runtime evidence is an input."""
import ast
import copy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path
import sys
from typing import Optional

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n31_bridge as frozen_bridge

ROOT = Path(__file__).resolve().parents[1]
MODE = 'archive_eligible_capture_v1'
RUNTIME_SOURCES = ('qd_archive_eligible_runtime.py', 'qd_archive_eligible_capture.py',
                   'qd_capture_dwell.py', 'qd_capture_dwell_proposal.py', 'qd_ed.py', 'rdt_policy_steer.py')


def source_paths(root=ROOT):
    root = Path(root)
    paths = frozen_bridge.source_paths(root) | runner.REQUIRED_CODE | w.REQUIRED_SOURCE
    for pattern in ('scripts/qd_ed_n32_*.py', 'core/qd_archive_eligible*.py',
                    'tests/test_n32*.py', 'configs/qd_ed_final/candidate_n32.json',
                    'docs/experiments/n32*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    # Hydra composition and imported numerical dependencies are part of the freeze.
    for folder, suffix in (('configs', '*.yaml'), ('core', '*.py'), ('utils', '*.py')):
        paths.update(str(p.relative_to(root)) for p in (root / folder).rglob(suffix))
    # RDT prepends third_party/rdt to sys.path in from_pretrained, so this
    # vendored file is loaded as scripts.maniskill_model and is attested too.
    # Require it even in an uninitialized checkout: a glob would silently omit
    # the exact dependency that invalidated the first N32 C0 attempt. Freezing
    # submodule bytes requires a separately reviewed source-record integration.
    paths.add('third_party/rdt/scripts/maniskill_model.py')
    return paths


def profiles(root=ROOT):
    root = Path(root)
    result = json.loads((root / 'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())
    w.require(set(result['profiles']) == {'C0', 'Q0'}, 'closed baseline profiles')
    candidate = json.loads((root / 'configs/qd_ed_final/candidate_n32.json').read_text())
    q0 = result['profiles']['Q0']
    w.require(candidate['profile'] == {**q0['restored_profile'], 'capture_dwell_proposal_mode': 'off',
                                     'archive_eligible_capture_mode': MODE}, 'N32 sole science delta')
    w.require(candidate['baseline_provenance']['sha256'] == w.sha(root / 'configs/qd_ed_final/n4_observed_baseline_profiles.json'), 'baseline hash')
    active = copy.deepcopy(q0)
    active['historical_label'] = 'N32'
    active['restored_profile'] = copy.deepcopy(candidate['profile'])
    active['resolved_eds_config'].update(capture_dwell_proposal_mode='off', archive_eligible_capture_mode=MODE)
    active['static_override_values'].update({'main.eds_config.capture_dwell_proposal_mode': 'off',
                                           'main.eds_config.archive_eligible_capture_mode': MODE})
    active['hydra_overrides'] = [f'{k}={runner.hydra(v)}' for k, v in active['static_override_values'].items()]
    result['profiles']['N32'] = active
    return result


def command(plan, runtime, row):
    w.require(row in plan['episodes'] and row['profile'] in ('C0', 'Q0', 'N32'), 'exact draft row')
    argv, output = runner.build_command(plan, profiles(plan['worktree']), runtime, row, row['episode_key'])
    if row['profile'] == 'N32':
        binding = {'task_id': row['task_id'], 'source_commit': plan['source']['commit'], 'run_id': row['episode_key']}
        argv.append('main.eds_config.n32_runtime_binding={' + ','.join(f'{k}:{runner.hydra(v)}' for k, v in binding.items()) + '}')
    return argv, output


def resolve_constructor(eds, root=ROOT):
    """Compile the exact dataclass/constructor/parsers without model imports.

    This computes serialization, not an alternative policy validator. The real
    policy still runs all validators. Tests compare against its complete resolver.
    """
    path = Path(root) / 'core/rdt_policy_steer.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_EDSConfig')
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_resolve_eds_config_with_reference_defaults')
    namespace = dict(dataclass=dataclass, Optional=Optional, Integral=Integral, Real=Real, math=math, __name__=__name__)
    # Resolve the four imported default constants from source literals, no imports.
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('core.'):
            for alias in node.names:
                name = alias.asname or alias.name
                if name in {'NOISY_SOURCE', 'LEGACY_RBF_UPDATE', 'DEFAULT_RBF_PLACEMENT', 'DEFAULT_FINAL_SELECTION_MODE'}:
                    dep = ast.parse((Path(root) / (node.module.replace('.', '/') + '.py')).read_text())
                    value = next(n.value for n in dep.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == alias.name for t in n.targets))
                    namespace[name] = ast.literal_eval(value)
    helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith('_parse_eds_')]
    constructor = copy.deepcopy(method)
    w.require(len(constructor.body) > 3 and isinstance(constructor.body[2], ast.Assign)
              and constructor.body[2].targets[0].id == 'resolved', 'policy constructor structure drift')
    constructor.body = constructor.body[:3] + [ast.Return(value=ast.Name(id='resolved', ctx=ast.Load()))]
    module = ast.fix_missing_locations(ast.Module(body=[cls, *helpers, constructor], type_ignores=[]))
    exec(compile(module, str(path), 'exec'), namespace)
    return asdict(namespace[constructor.name](None, eds))


def compose_launch(argv, root=ROOT):
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    with initialize_config_dir(config_dir=str(Path(root).resolve() / 'configs'), version_base=None):
        cfg = compose(config_name='config', overrides=argv[2:])
        eds = OmegaConf.to_container(cfg.main.eds_config, resolve=True)
        evaluation = OmegaConf.to_container(cfg.main.eds_eval, resolve=True)
        pretest = OmegaConf.to_container(cfg.main.eds_mechanism_pretest, resolve=True)
        eds.update(reward_mode=evaluation.get('reward_mode', eds.get('reward_mode', 'normal')),
                   shuffle_seed=evaluation.get('shuffle_seed', eds.get('shuffle_seed', 0)))
        if pretest:
            eds['mechanism_pretest'] = pretest
        config = OmegaConf.to_container(cfg, resolve=False)
    return config, resolve_constructor(eds, root)


def manifest(plan, runtime, row):
    task = runtime['tasks'][str(row['task_id'])]
    w.require(task['task_id'] == row['task_id'] and task['init_index'] == row['init_index'], 'runtime task/init identity')
    files = {v['path']: v['sha256'] for v in runtime['files']}
    w.require(files[task['init_path']] == row['init_file_sha256']
              and files[task['bddl_path']] == row['bddl_sha256'], 'runtime task input hashes')
    argv, output = command(plan, runtime, row)
    config, resolved = compose_launch(argv, plan['worktree'])
    w.require(config['backend']['libero']['max_episode_steps'] == 720
              and config['policy']['rdt']['control_frequency'] == 20
              and config['policy']['rdt']['action_chunk_horizon'] == 8, 'frozen episode schedule')
    index = {x['path']: x['sha256'] for x in plan['source']['files']}
    expected = None
    if row['profile'] == 'N32':
        expected = {'binding': resolved['n32_runtime_binding'],
                    'config_sha256': hashlib.sha256(json.dumps(resolved, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                    'source_hashes': {**{name: index['core/' + name] for name in RUNTIME_SOURCES}, 'main.py': index['main.py']}}
    return {'schema': 'n32-external-runtime-v1', 'row': row, 'source': plan['source'],
            'runtime': plan['runtime'], 'argv': argv, 'output_dir': str(output),
            'composed_config_sha256': w.canonical_sha(config), 'resolved_config': resolved,
            'expected_runtime': expected}


def verify_manifest(reference, plan, runtime, row):
    w.verify_source(plan['worktree'], plan['source'])
    w.require(source_paths(plan['worktree']) <= {v['path'] for v in plan['source']['files']}, 'incomplete source inventory')
    w.require(w.read_ref(plan['runtime']) == runtime, 'runtime changed')
    actual = w.read_ref(reference)
    w.require(actual == json.loads(json.dumps(manifest(plan, runtime, row))), 'external manifest/config/task/source differs')
    return actual


def attest_loaded(root, source):
    """Attest loaded repository module origins and backing bytes, not arbitrary bytecode."""
    root = Path(root).resolve()
    index = {v['path']: v['sha256'] for v in source['files']}
    loaded = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith(('core.', 'scripts.', 'utils.')):
            continue
        file = getattr(module, '__file__', None)
        if not file:
            continue
        path = Path(file).resolve()
        w.require(path.is_relative_to(root), 'loaded adjacent checkout: ' + name)
        relative = str(path.relative_to(root))
        w.require(relative in index and w.sha(path) == index[relative], 'loaded source not frozen: ' + name)
        loaded[name] = {'path': relative, 'sha256': index[relative]}
    return loaded
