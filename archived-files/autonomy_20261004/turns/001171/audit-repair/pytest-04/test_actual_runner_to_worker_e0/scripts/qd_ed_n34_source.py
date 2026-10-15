"""N34 source closure, including pinned dependency Python/config bytes and runtime origins.

No fetch, model import, installation or candidate-receipt discovery is performed.
"""
import ast
from contextlib import contextmanager
import json
import os
import subprocess
import time
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
from pathlib import Path
import sys
import tempfile
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

# This rule supports exactly the reviewed installed implementation. A Torch
# upgrade requires a new reviewed rule, not just a newly observed content hash.
GENERATED_NAME = '_remote_module_non_scriptable'
GENERATOR_NAME = 'torch.distributed.nn.jit.instantiator'
TEMPLATE_NAME = 'torch.distributed.nn.jit.templates.remote_module_template'
GENERATED_RULE = 'torch-remote-non-scriptable-v1'
GENERATOR_SHA = '567d1314ee27ff0b3bd22e7c4d1157246469de25e7a3183d96debe167b193615'
TEMPLATE_SHA = '0ff1856bbd031b5298d46c06c0502abc20bd804f42c1949ed4127e8c773660cc'


def _runtime_file(record):
    w.require(isinstance(record, dict) and set(record) == {'path', 'sha256'},
              'runtime file record schema')
    path = Path(record['path'])
    w.require(path.is_absolute() and path.is_file() and not path.is_symlink()
              and str(path.resolve()) == str(path) and w.sha(path) == record['sha256'],
              'runtime source bytes differ')
    return path


def _live_source(name, path):
    """Bind all import origin fields, without importing the module to attest it."""
    module = sys.modules.get(name)
    spec = getattr(module, '__spec__', None)
    loader = getattr(spec, 'loader', None)
    cached = importlib.util.cache_from_source(str(path))
    w.require(module is not None and getattr(module, '__name__', None) == name
              and getattr(module, '__file__', None) == str(path)
              and getattr(module, '__package__', None) == name.rpartition('.')[0]
              and isinstance(spec, importlib.machinery.ModuleSpec)
              and spec.name == name and spec.origin == str(path)
              and spec.has_location and spec.submodule_search_locations is None
              and spec.loader_state is None
              and spec.cached == cached and getattr(module, '__cached__', None) == cached
              and type(loader) is importlib.machinery.SourceFileLoader
              and getattr(module, '__loader__', None) is loader
              and loader.name == name and loader.path == str(path),
              'generated runtime live origin/spec differs: ' + name)
    return module


def _generated_runtime(closure):
    """Validate a prospective rule and any live instance; never learn trust from it."""
    rules = closure.get('generated_modules', {})
    if closure.get('schema') != 'n34-runtime-source-closure-v2':
        w.require(not rules and 'generated_modules' not in closure,
                  'generated runtime requires closure v2')
        return {}
    w.require(isinstance(rules, dict) and set(rules) == {GENERATED_NAME},
              'generated runtime names differ')
    rule = rules[GENERATED_NAME]
    w.require(isinstance(rule, dict)
              and set(rule) == {'rule', 'generator', 'template', 'sha256'}
              and rule['rule'] == GENERATED_RULE, 'generated runtime rule schema')
    w.require(GENERATED_NAME not in closure['modules']
              and GENERATED_NAME in closure['required_after'],
              'generated runtime must be separately required')
    for key, name, digest in (('generator', GENERATOR_NAME, GENERATOR_SHA),
                              ('template', TEMPLATE_NAME, TEMPLATE_SHA)):
        path = _runtime_file(rule[key])
        w.require(rule[key]['sha256'] == digest
                  and closure['modules'].get(name) == rule[key],
                  'unsupported generated runtime ' + key)
        if name in sys.modules:
            _live_source(name, path)

    # Parse only frozen string literals: no Torch execution or probe import is
    # needed to calculate the prospective content commitment.
    tree = ast.parse(Path(rule['template']['path']).read_bytes())
    strings = {node.targets[0].id: ast.literal_eval(node.value)
               for node in tree.body if isinstance(node, ast.Assign)
               and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
    content = (strings['_TEMPLATE_PREFIX']
               + strings['_REMOTE_FORWARD_TEMPLATE_ENABLE_MOVING_CPU_TENSORS_TO_CUDA']).format(
                   assign_module_interface_cls='module_interface_cls = None',
                   args='*args', kwargs='**kwargs', arg_types='*args, **kwargs',
                   arrow_and_return_type='', arrow_and_future_return_type='',
                   jit_script_decorator='').encode('utf-8')
    w.require(hashlib.sha256(content).hexdigest() == rule['sha256'],
              'generated runtime prospective content differs')

    generator = sys.modules.get(GENERATOR_NAME)
    directory = None
    if generator is not None:
        owner = getattr(generator, '_TEMP_DIR', None)
        w.require(type(owner) is tempfile.TemporaryDirectory,
                  'generated runtime directory owner differs')
        directory = Path(owner.name)
        finalizer = owner._finalizer.peek()
        w.require(directory.is_absolute() and directory.is_dir()
                  and str(directory.resolve()) == str(directory) and not directory.is_symlink()
                  and getattr(generator, 'INSTANTIATED_TEMPLATE_DIR_PATH', None) == str(directory)
                  and finalizer is not None and finalizer[0] is owner
                  and finalizer[2] == (str(directory),),
                  'generated runtime directory binding differs')
    inventory = {}
    if GENERATED_NAME in sys.modules:
        w.require(directory is not None and TEMPLATE_NAME in sys.modules,
                  'generated runtime owner/template not loaded')
        path = directory / (GENERATED_NAME + '.py')
        record = {'path': str(path), 'sha256': rule['sha256']}
        _runtime_file(record)
        _live_source(GENERATED_NAME, path)
        inventory[GENERATED_NAME] = record
    for name, module in list(sys.modules.items()):
        file = getattr(module, '__file__', None)
        in_directory = file is not None and directory is not None and Path(file).resolve().is_relative_to(directory)
        w.require(name == GENERATED_NAME or not (name.startswith('_remote_module_') or in_directory),
                  'unexpected generated runtime module: ' + name)
    return inventory


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


@contextmanager
def verification_phase(name):
    """Untrusted stderr diagnostics only; never an acceptance/start receipt."""
    started = time.perf_counter()
    def emit(event, **extra):
        print(json.dumps({'schema': 'n34-verification-phase-v1', 'phase': name,
                          'event': event, 'pid': os.getpid(),
                          'monotonic_seconds': time.perf_counter(), **extra}),
              file=sys.stderr, flush=True)
    emit('begin')
    try:
        yield
    except BaseException:
        emit('failed', elapsed_seconds=time.perf_counter() - started)
        raise
    else:
        emit('end', elapsed_seconds=time.perf_counter() - started)


def _source_tree(root, commit, database):
    entries = {}
    raw = w._source_git(root, 'ls-tree', '-r', '-z', commit, database=database)
    for row in raw.split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        name = name.decode()
        w.require(name not in entries, 'duplicate source Git path')
        entries[name] = metadata.decode().split()
    return entries


def _source_blobs(root, blobs, database):
    """One local batch per database, discarded at the end of this call."""
    blobs = sorted(set(blobs))
    if not blobs:
        return {}
    command = ['git', '--no-replace-objects']
    if database is not None:
        command.append('--git-dir=' + str(database))
    raw = subprocess.check_output(command + ['cat-file', '--batch'], cwd=root,
        input=('\n'.join(blobs) + '\n').encode('ascii'),
        env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})
    result, offset = {}, 0
    for blob in blobs:
        end = raw.find(b'\n', offset)
        w.require(end >= offset, 'source Git batch header missing')
        fields = raw[offset:end].split()
        w.require(len(fields) == 3 and fields[0].decode() == blob
                  and fields[1] == b'blob' and fields[2].isdigit(),
                  'source Git batch object/type differs')
        size = int(fields[2]); offset = end + 1
        data = raw[offset:offset + size]
        w.require(len(data) == size and raw[offset + size:offset + size + 1] == b'\n',
                  'source Git batch body differs')
        # Also reject corrupt local object content, not merely wrong batch IDs.
        w.require(len(blob) in (40, 64), 'source Git object id differs')
        digest = hashlib.new('sha1' if len(blob) == 40 else 'sha256',
                             b'blob ' + str(size).encode() + b'\0' + data).hexdigest()
        w.require(digest == blob, 'source Git blob digest differs')
        result[blob] = data
        offset += size + 1
    w.require(offset == len(raw), 'source Git batch trailing bytes')
    return result


def source_record(root, paths, *, commit=None):
    root = Path(root).resolve()
    w.require(Path(w._source_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() == root, 'source root differs')
    commit = commit or w._source_git(root, 'rev-parse', 'HEAD').decode().strip()
    # Resolve each registered database/pin once, never from dependency HEAD.
    groups = {}
    for relative in sorted(set(paths)):
        name = Path(relative); path = root / name
        w.require(not name.is_absolute() and '..' not in name.parts and str(name) == relative and name.parts, 'unsafe source path')
        w.require(path.is_file() and not any((root / Path(*name.parts[:i])).is_symlink() for i in range(1,len(name.parts)+1)), 'source path missing or linked')
        submodule = next((s for s in PINNED_SUBMODULES if relative.startswith(s + '/')), None)
        groups.setdefault(submodule, []).append(relative)
    files = []
    for submodule, names in groups.items():
        pin, database = submodule_pin(root, submodule, commit) if submodule else (commit, None)
        entries = _source_tree(root, pin, database)
        selected = {}
        for relative in names:
            key = relative[len(submodule)+1:] if submodule else relative
            w.require(key in entries, 'source Git object missing')
            mode, kind, blob = entries[key]
            w.require(mode in ('100644', '100755') and kind == 'blob', 'source Git object not regular')
            selected[relative] = blob
        committed = _source_blobs(root, selected.values(), database)
        for relative, blob in selected.items():
            path = root / relative
            name = Path(relative)
            w.require(path.is_file() and not any((root / Path(*name.parts[:i])).is_symlink() for i in range(1,len(name.parts)+1)), 'source path missing or linked')
            data = path.read_bytes()
            w.require(data == committed[blob], 'uncommitted source bytes: ' + relative)
            files.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
    files.sort(key=lambda row: row['path'])
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
    w.require(closure['schema'] in ('n34-runtime-source-closure-v1', 'n34-runtime-source-closure-v2')
              and closure['runtime'] == runtime_ref,
              'runtime closure binding')
    modules = closure['modules']
    w.require(isinstance(modules, dict) and modules and closure['required_after']
              and set(closure['required_after']) <= set(modules) | set(closure.get('generated_modules', {})),
              'runtime modules required')
    for record in modules.values():
        _runtime_file(record)
    _generated_runtime(closure)
    w.require(closure['interpreter'] == {'path': str(Path(sys.executable).resolve()),
              'sha256': w.sha(Path(sys.executable).resolve()), 'version': sys.version}, 'runtime interpreter differs')
    w.require(isinstance(closure['versions'], dict) and all(closure['versions'].get(k) for k in ('python', 'torch', 'libero', 'robosuite', 'mujoco')), 'runtime versions required')
    versions = closure['distribution_versions']
    w.require(isinstance(versions, dict) and {'torch', 'numpy', 'robosuite', 'mujoco', 'transformers'} <= set(versions), 'installed distribution versions required')
    w.require(all(importlib.metadata.version(name) == version for name,version in versions.items()), 'installed distribution version differs')
    return closure


def attest_runtime(closure, runtime_ref, *, after=False):
    verify_runtime(closure, runtime_ref)
    inventory = _generated_runtime(closure)
    for name, module in list(sys.modules.items()):
        if name in inventory:
            continue  # already attested against the explicit prospective rule
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


def _retained_origin(name, path):
    """Canonical claims emitted only after the live origin/owner checks pass."""
    path = str(path)
    return {'module_name': name, 'file': path, 'package': name.rpartition('.')[0],
            'cached': importlib.util.cache_from_source(path),
            'spec': {'name': name, 'origin': path, 'has_location': True,
                     'submodule_search_locations': None, 'loader_state': None,
                     'cached': importlib.util.cache_from_source(path)},
            'loader': {'type': 'importlib.machinery.SourceFileLoader',
                       'name': name, 'path': path, 'module_loader_is_spec_loader': True}}


def attest_runtime_receipt(closure, runtime_ref, *, binding, after=False):
    """Retain checked source/origin claims inside the process-bound receipt.

    No temporary path becomes authority. Content is independently committed by
    the prospective rule; origin remains a trusted worker's point-in-time claim.
    """
    inventory = attest_runtime(closure, runtime_ref, after=after)
    generated = {}
    for name, rule in closure.get('generated_modules', {}).items():
        if name not in inventory:
            continue
        record = inventory.pop(name)
        path = Path(record['path'])
        content = path.read_bytes()
        w.require(hashlib.sha256(content).hexdigest() == rule['sha256'],
                  'retained generated content differs')
        generated[name] = {'rule': rule, 'record': record,
                           'source_utf8': content.decode('utf-8'),
                           'origin': _retained_origin(name, path),
                           'generator_origin': _retained_origin(GENERATOR_NAME, rule['generator']['path']),
                           'template_origin': _retained_origin(TEMPLATE_NAME, rule['template']['path']),
                           'owner': {'type': 'tempfile.TemporaryDirectory', 'name': str(path.parent),
                                     'exported_directory': str(path.parent),
                                     'finalizer_owner_identity': True,
                                     'finalizer_args': [str(path.parent)],
                                     'canonical_directory': True, 'regular_source': True}}
    return {'schema': 'n34-runtime-receipt-v2', 'binding': binding,
            'modules': inventory, 'generated_modules': generated}


def verify_runtime_receipt(closure, receipt, *, binding, after=False):
    """Parent consumption after process exit: never reopen worker temp paths."""
    w.require(isinstance(receipt, dict) and set(receipt) == {
        'schema', 'binding', 'modules', 'generated_modules'}
        and receipt['schema'] == 'n34-runtime-receipt-v2'
        and receipt['binding'] == binding, 'runtime receipt schema/binding differs')
    ordinary, generated = receipt['modules'], receipt['generated_modules']
    rules = closure.get('generated_modules', {})
    w.require(isinstance(ordinary, dict) and isinstance(generated, dict)
              and not set(ordinary) & set(rules) and set(generated) <= set(rules),
              'runtime receipt names differ')
    w.require(all(name in closure['modules'] and closure['modules'][name] == record
                  for name, record in ordinary.items()), 'runtime receipt source differs')
    for name, evidence in generated.items():
        rule = rules[name]
        w.require(isinstance(evidence, dict) and isinstance(evidence.get('record'), dict)
                  and isinstance(evidence['record'].get('path'), str)
                  and isinstance(evidence.get('source_utf8'), str), 'generated receipt schema')
        path = Path(evidence['record']['path'])
        # Lexical check only: the owning TemporaryDirectory has been cleaned up.
        w.require(path.is_absolute() and str(path) == evidence['record']['path']
                  and '..' not in path.parts and path.name == name + '.py',
                  'generated receipt path differs')
        expected = {'rule': rule, 'record': {'path': str(path), 'sha256': rule['sha256']},
                    'source_utf8': evidence['source_utf8'],
                    'origin': _retained_origin(name, path),
                    'generator_origin': _retained_origin(GENERATOR_NAME, rule['generator']['path']),
                    'template_origin': _retained_origin(TEMPLATE_NAME, rule['template']['path']),
                    'owner': {'type': 'tempfile.TemporaryDirectory', 'name': str(path.parent),
                              'exported_directory': str(path.parent),
                              'finalizer_owner_identity': True, 'finalizer_args': [str(path.parent)],
                              'canonical_directory': True, 'regular_source': True}}
        w.require(w.canonical_sha(evidence) == w.canonical_sha(expected)
                  and hashlib.sha256(evidence['source_utf8'].encode('utf-8')).hexdigest() == rule['sha256'],
                  'generated receipt rule/content/origin differs')
        w.require(ordinary.get(GENERATOR_NAME) == rule['generator']
                  and ordinary.get(TEMPLATE_NAME) == rule['template'],
                  'generated receipt owner/template absent')
    if after:
        w.require(set(closure['required_after']) <= set(ordinary) | set(generated),
                  'runtime receipt incomplete')
