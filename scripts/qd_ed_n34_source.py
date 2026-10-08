"""N34 source closure, including pinned dependency Python/config bytes and runtime origins.

No fetch, model import, installation or candidate-receipt discovery is performed.
"""
import hashlib
import importlib.metadata
from pathlib import Path
import sys
from scripts import qd_ed_n23_worker as w

RDT = 'third_party/rdt'
LEROBOT = 'third_party/lerobot'
LIBERO = 'third_party/libero_pro'
PINNED_SUBMODULES = {
    RDT: 'scripts/maniskill_model.py',
    LEROBOT: 'src/lerobot/__init__.py',
}
SOURCE_SUFFIXES = ('.py', '.yaml', '.yml', '.json')
RUNTIME_PREFIXES = ('libero', 'robosuite', 'mujoco', 'transformers', 'diffusers',
                    'torch', 'numpy', 'scipy', 'safetensors', 'tokenizers', 'cv2',
                    'PIL', 'einops', 'timm', 'huggingface_hub', 'hydra', 'omegaconf')
RDT_PREFIXES = ('models', 'configs', 'data', 'rdt')


def submodule_pin(root, submodule, commit='HEAD'):
    w.require(submodule in PINNED_SUBMODULES, 'unapproved source submodule')
    root = Path(root).resolve()
    mode, kind, pin = w._source_entry(root, commit, submodule)
    w.require((mode, kind) == ('160000', 'commit'), submodule + ' gitlink required')
    common = Path(w._source_git(root, 'rev-parse', '--git-common-dir').decode().strip())
    database = (root / common / 'modules' / submodule).resolve()
    w.require(database.is_dir(), 'pinned ' + submodule + ' object database unavailable')
    w.require(w._source_git(root, 'cat-file', '-t', pin, database=database).strip() == b'commit', submodule + ' pin not commit')
    return pin, database


def rdt_pin(root, commit='HEAD'):
    return submodule_pin(root, RDT, commit)


def submodule_paths(root, submodule, commit='HEAD'):
    pin, database = submodule_pin(root, submodule, commit)
    raw = w._source_git(Path(root), 'ls-tree', '-r', '--name-only', '-z', pin, database=database)
    paths = {submodule + '/' + name.decode() for name in raw.split(b'\0') if name
             and Path(name.decode()).suffix in SOURCE_SUFFIXES}
    w.require(submodule + '/' + PINNED_SUBMODULES[submodule] in paths,
              'pinned dependency entrypoint missing: ' + submodule)
    return paths


def rdt_paths(root, commit='HEAD'):
    return submodule_paths(root, RDT, commit)


def dependency_paths(root, commit='HEAD'):
    paths = set()
    for submodule in PINNED_SUBMODULES:
        paths.update(submodule_paths(root, submodule, commit))
    # LIBERO is a regular superproject tree, despite its stale .gitmodules entry.
    mode, kind, _ = w._source_entry(Path(root), commit, LIBERO)
    w.require((mode, kind) == ('040000', 'tree'), 'LIBERO tracked tree required')
    raw = w._source_git(Path(root), 'ls-tree', '-r', '--name-only', '-z', commit, '--', LIBERO)
    paths.update(name.decode() for name in raw.split(b'\0') if name
                 and Path(name.decode()).suffix in SOURCE_SUFFIXES)
    w.require(LIBERO + '/libero/libero/__init__.py' in paths, 'pinned LIBERO entrypoint missing')
    return paths


def source_record(root, paths, *, commit=None):
    root = Path(root).resolve()
    w.require(Path(w._source_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() == root, 'source root differs')
    commit = commit or w._source_git(root, 'rev-parse', 'HEAD').decode().strip()
    files = []
    for relative in sorted(set(paths)):
        name = Path(relative); path = root / name
        w.require(not name.is_absolute() and '..' not in name.parts and str(name) == relative and name.parts, 'unsafe source path')
        w.require(path.is_file() and not any((root / Path(*name.parts[:i])).is_symlink() for i in range(1,len(name.parts)+1)), 'source path missing or linked')
        submodule = next((s for s in PINNED_SUBMODULES if relative.startswith(s + '/')), None)
        if submodule is not None:
            pin, database = submodule_pin(root, submodule, commit)
            mode, kind, blob = w._source_entry(root, pin, relative[len(submodule)+1:], database)
            w.require(mode in ('100644', '100755') and kind == 'blob', 'dependency source not regular')
            committed = w._source_git(root, 'cat-file', 'blob', blob, database=database)
        else:
            committed = w._committed_source(root, commit, relative)
        data = path.read_bytes()
        w.require(data == committed, 'uncommitted source bytes: ' + relative)
        files.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
    return {'commit': commit, 'files': files, 'sha256': w.canonical_sha(files)}


def verify_source(root, record, *, commit=None):
    w.require(set(record) == {'commit', 'files', 'sha256'}, 'source record schema')
    expected = source_record(root, [x['path'] for x in record['files']], commit=commit)
    w.require(record == expected, 'source bytes/commit differ')


def attest_loaded(root, source):
    root = Path(root).resolve()
    index = {x['path']: x['sha256'] for x in source['files']}
    result = {}
    for name, module in list(sys.modules.items()):
        if name in ('torch.ops', 'torch.classes', '__main__'):
            continue  # virtual torch namespaces; worker __main__ has its own spec/origin attestor
        if name == '__mp_main__' and module is sys.modules.get('__main__'):
            continue  # multiprocessing's alias of the separately attested worker
        file = getattr(module, '__file__', None)
        if not file:
            continue
        path = Path(file).resolve()
        scoped = name.startswith(('core.', 'scripts.', 'utils.')) or name.split('.')[0] in RDT_PREFIXES
        if not scoped and not path.is_relative_to(root):
            continue
        w.require(path.is_relative_to(root), 'loaded adjacent checkout: ' + name)
        relative = str(path.relative_to(root))
        w.require(relative in index and w.sha(path) == index[relative], 'loaded source not frozen: ' + name)
        result[name] = {'path': relative, 'sha256': index[relative]}
    return result


def verify_runtime(closure, runtime_ref):
    w.require(closure['schema'] == 'n34-runtime-source-closure-v1' and closure['runtime'] == runtime_ref,
              'runtime closure binding')
    modules = closure['modules']
    w.require(isinstance(modules, dict) and modules and closure['required_after']
              and set(closure['required_after']) <= set(modules), 'runtime modules required')
    for record in modules.values():
        path = Path(record['path'])
        w.require(path.is_absolute() and path.is_file() and not path.is_symlink()
                  and str(path.resolve()) == str(path) and w.sha(path) == record['sha256'], 'runtime source bytes differ')
    w.require(closure['interpreter'] == {'path': str(Path(sys.executable).resolve()),
              'sha256': w.sha(Path(sys.executable).resolve()), 'version': sys.version}, 'runtime interpreter differs')
    w.require(isinstance(closure['versions'], dict) and all(closure['versions'].get(k) for k in ('python', 'torch', 'libero', 'robosuite', 'mujoco')), 'runtime versions required')
    versions = closure['distribution_versions']
    w.require(isinstance(versions, dict) and {'torch', 'numpy', 'robosuite', 'mujoco', 'transformers'} <= set(versions), 'installed distribution versions required')
    w.require(all(importlib.metadata.version(name) == version for name,version in versions.items()), 'installed distribution version differs')
    return closure


def attest_runtime(closure, runtime_ref, *, after=False):
    verify_runtime(closure, runtime_ref)
    inventory = {}
    for name, module in list(sys.modules.items()):
        if name in ('torch.ops', 'torch.classes'):
            continue  # no backing source file; torch._ops / torch._classes are inventoried
        file = getattr(module, '__file__', None)
        if file is None:
            continue
        path = Path(file).resolve()
        if path.is_relative_to(Path(__file__).resolve().parents[1]):
            continue  # separately bound to operational/scientific Git sources
        record = {'path': str(path), 'sha256': w.sha(path)}
        w.require(closure['modules'].get(name) == record, 'loaded runtime not frozen: ' + name)
        inventory[name] = record
    if after:
        w.require(set(closure['required_after']) <= set(inventory), 'required runtime modules not loaded')
    return inventory
