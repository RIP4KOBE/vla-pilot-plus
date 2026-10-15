"""N34 source closure, including all pinned RDT Python/config bytes and runtime origins.

No fetch, model import, installation or candidate-receipt discovery is performed.
"""
import hashlib
from pathlib import Path
import sys
from scripts import qd_ed_n23_worker as w

RDT = 'third_party/rdt'
RUNTIME_PREFIXES = ('libero', 'robosuite', 'mujoco', 'transformers', 'diffusers',
                    'torch', 'numpy', 'scipy', 'safetensors', 'tokenizers', 'cv2',
                    'PIL', 'einops', 'timm', 'huggingface_hub', 'hydra', 'omegaconf')
RDT_PREFIXES = ('models', 'configs', 'data', 'rdt')


def rdt_pin(root, commit='HEAD'):
    root = Path(root).resolve()
    mode, kind, pin = w._source_entry(root, commit, RDT)
    w.require((mode, kind) == ('160000', 'commit'), 'RDT gitlink required')
    common = Path(w._source_git(root, 'rev-parse', '--git-common-dir').decode().strip())
    database = (root / common / 'modules' / RDT).resolve()
    w.require(database.is_dir(), 'pinned RDT object database unavailable')
    w.require(w._source_git(root, 'cat-file', '-t', pin, database=database).strip() == b'commit', 'RDT pin not commit')
    return pin, database


def rdt_paths(root, commit='HEAD'):
    pin, database = rdt_pin(root, commit)
    raw = w._source_git(Path(root), 'ls-tree', '-r', '--name-only', '-z', pin, database=database)
    paths = {RDT + '/' + name.decode() for name in raw.split(b'\0') if name
             and Path(name.decode()).suffix in ('.py', '.yaml', '.yml', '.json')}
    w.require(RDT + '/scripts/maniskill_model.py' in paths, 'pinned RDT scripts.maniskill_model missing')
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
        if relative.startswith(RDT + '/'):
            pin, database = rdt_pin(root, commit)
            mode, kind, blob = w._source_entry(root, pin, relative[len(RDT)+1:], database)
            w.require(mode in ('100644', '100755') and kind == 'blob', 'RDT source not regular')
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
