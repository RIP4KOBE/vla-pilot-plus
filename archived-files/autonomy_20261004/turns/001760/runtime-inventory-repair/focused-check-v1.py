"""Bounded CPU checks of exact builder/auditor AST; no runtime package imports."""
import ast
import copy
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

OUT = Path(__file__).resolve().parent
ROOT = Path.cwd()
BASE = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns')
AUTH = json.loads((OUT / 'authority-v1.json').read_text())
import datetime
assert not any(os.path.lexists(p) for p in AUTH['stop_authority']['paths'])
assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(AUTH['stop_authority']['deadline'].replace('Z', '+00:00'))
assert str(ROOT) == AUTH['worktree']

def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def load_functions(path, names, namespace):
    tree = ast.parse(path.read_bytes())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)

# Execute unchanged definitions while avoiding the worker's transitive torch import.
w = types.SimpleNamespace()
wns = {'Path': Path, 'hashlib': hashlib}
load_functions(ROOT / 'scripts/qd_ed_n23_worker.py', ['require', 'sha'], wns)
w.require, w.sha = wns['require'], wns['sha']
source_path = ROOT / 'scripts/qd_ed_n34_source.py'
source = types.ModuleType('focused_runtime_source')
source.__file__ = str(source_path)
source.w = w
source_tree = ast.parse(source_path.read_bytes())
source_tree.body = [n for n in source_tree.body if not (isinstance(n, ast.ImportFrom) and n.module == 'scripts')]
exec(compile(source_tree, str(source_path), 'exec'), source.__dict__)

probe_path = BASE / '000914/runtime-v1/runtime-import-probe-v1.py'
probe_tree = ast.parse(probe_path.read_bytes())
loop = next(n for n in probe_tree.body if isinstance(n, ast.For) and ast.unparse(n.target) == '(n, m)' and 'sys.modules.items()' in ast.unparse(n.iter))
probe_code = compile(ast.Module(body=[loop], type_ignores=[]), str(probe_path), 'exec')
checks = []

def passed(name):
    checks.append({'check': name, 'status': 'PASS'})

def rejects(name, closure, reason):
    try:
        source.attest_runtime(closure, closure['runtime'], after=True)
    except source.RuntimeOriginError as exc:
        assert reason in str(exc), str(exc)
        checks.append({'check': name, 'status': 'PASS', 'rejection': str(exc)})
    else:
        raise AssertionError(name + ' was accepted')

with tempfile.TemporaryDirectory(prefix='cpu-fixture-', dir=OUT) as directory:
    base = Path(directory)
    empty = base / 'OpenGL/GL/VERSION/__init__.py'
    empty.parent.mkdir(parents=True)
    empty.write_bytes(b'')
    nonempty = base / 'OpenGL/GL/__init__.py'
    nonempty.write_bytes(b'# inert package fixture\n')
    module_path = base / 'OpenGL/GL/VERSION/GL_1_0.py'
    module_path.write_bytes(b'')
    paths = {'OpenGL.GL.VERSION': empty, 'OpenGL.GL': nonempty, 'OpenGL.GL.VERSION.GL_1_0': module_path}
    modules = {name: types.SimpleNamespace(__name__=name, __file__=str(path), __spec__=importlib.machinery.ModuleSpec(name, None, origin=str(path), is_package=path.name=='__init__.py')) for name, path in paths.items()}
    fake_sys = types.SimpleNamespace(modules=modules, executable=sys.executable, version=sys.version)
    ns = {'sys': fake_sys, 'pathlib': __import__('pathlib'), 'root': ROOT, 'ref': ref, 'external': {}, 'local': {}, 'missing': []}
    exec(probe_code, ns)
    assert ns['external'] == {name: ref(path) for name, path in paths.items()}
    assert not ns['local'] and not ns['missing']
    passed('unchanged snapshot builder includes empty package, nonempty package, empty ordinary module')
    source.sys = fake_sys
    # Fixtures reside under the authorized output directory outside source root.
    closure = {'schema': 'n34-runtime-source-closure-v1', 'runtime': {'fixture': True}, 'modules': ns['external'], 'required_after': list(paths),
               'interpreter': {'path': str(Path(sys.executable).resolve()), 'sha256': w.sha(Path(sys.executable).resolve()), 'version': sys.version},
               'versions': {key: 'fixture' for key in ('python','torch','libero','robosuite','mujoco')},
               'distribution_versions': {key: 'fixture' for key in ('torch','numpy','robosuite','mujoco','transformers')}}
    with patch.object(source.importlib.metadata, 'version', lambda _: 'fixture'):
        assert source.attest_runtime(closure, closure['runtime'], after=True) == closure['modules']
        passed('unchanged strict auditor accepts explicitly frozen empty packages')
        absent = copy.deepcopy(closure)
        del absent['modules']['OpenGL.GL.VERSION']
        absent['required_after'].remove('OpenGL.GL.VERSION')
        rejects('unlisted empty package rejected', absent, 'loaded runtime not frozen: OpenGL.GL.VERSION')
        modules['unlisted_alias'] = modules['OpenGL.GL.VERSION']
        rejects('unlisted alias to identical empty bytes rejected', closure, 'loaded runtime not frozen: unlisted_alias')
        del modules['unlisted_alias']
        wrong = base / 'wrong/__init__.py'
        wrong.parent.mkdir(); wrong.write_bytes(b'')
        modules['OpenGL.GL.VERSION'].__file__ = str(wrong)
        rejects('same empty hash at different loaded path rejected', closure, 'loaded runtime not frozen: OpenGL.GL.VERSION')
        modules['OpenGL.GL.VERSION'].__file__ = str(empty)
        empty.write_bytes(b'# changed\n')
        rejects('changed frozen empty package bytes rejected', closure, 'runtime source bytes differ')
        empty.write_bytes(b'')
        assert source.attest_runtime(closure, closure['runtime'], after=True) == closure['modules']
        passed('restored fixture accepted without changing audit policy')

assert not any(name in sys.modules for name in ('torch', 'OpenGL', 'mujoco', 'robosuite'))
result = {'schema': 'n36-runtime-inventory-focused-cpu-checks-v1', 'status': 'PASS', 'checks': checks,
          'production_functions': ref(source_path), 'builder': ref(probe_path),
          'method': 'Unmodified builder loop and auditor definitions compiled from AST; only module table and distribution-version metadata synthetic. No production snapshot/probe executed.',
          'gpu_native_provider_execution': False, 'runtime_packages_imported': False}
(OUT / 'focused-check-results-v1.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'checks': len(checks)}))
