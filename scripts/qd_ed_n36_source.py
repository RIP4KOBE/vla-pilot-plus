"""Check the live source-only loader and join compiled bytes to frozen inventories.

This supplements (never replaces) module origin and native-build attestation.
"""
import importlib.machinery
import hashlib
import _imp
import runpy
import os
import copy
from pathlib import Path
import sys
import zipimport


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(python, root, module, *args):
    return [str(python), '-I', '-S', '-B', '-X', 'pycache_prefix=/dev/null',
            str(Path(root).resolve() / 'scripts/qd_ed_n36_bootstrap.py'), module, *args]


def active():
    state = sys.modules.get('_n36_source_bootstrap')
    require(state is not None and sys.flags.isolated and sys.flags.no_site
        and sys.flags.optimize == 0
        and sys.flags.dont_write_bytecode and sys.pycache_prefix == '/dev/null'
        and sys._xoptions.get('pycache_prefix') == '/dev/null', 'N36 source-only startup absent')
    require(importlib.machinery.SourceFileLoader.get_code is state.source_code
        and importlib.machinery.SourcelessFileLoader.get_code is state.reject_bytecode
        and zipimport.zipimporter.get_code is state.reject_bytecode
        and zipimport.zipimporter.exec_module is state.reject_bytecode
        and zipimport.zipimporter.load_module is state.reject_bytecode, 'N36 executable loader replaced')
    return state


def run_main(path):
    """Compile the exact Main path, preserving run_path's script globals/argv.

    _run_module_code belongs to the externally bound CPython standard library.
    In particular __spec__ remains None and __package__ remains the empty string.
    """
    active()
    path = str(Path(path).resolve())
    code = importlib.machinery.SourceFileLoader('main', path).get_code('main')
    return runpy._run_module_code(code, mod_name='__main__', pkg_name='', script_name=path)


def interpreter_identity():
    path = str(Path(sys.executable).resolve())
    return {'path': path, 'sha256': sha(path), 'version': sys.version}


def alias_claim(runtime, binding):
    # This fixed rule has no extensible names, paths or hash-only fallback.
    require(all(name in runtime['modules'] for name in ('os.path', 'posixpath')),
            'N36 alias inventory incomplete')
    return {'rule': 'n36-frozen-os.path-posixpath-v1',
            'binding': copy.deepcopy(binding), 'interpreter': copy.deepcopy(runtime['interpreter']),
            'alias': 'os.path', 'canonical': 'posixpath',
            'spec_name': 'posixpath', 'origin': 'frozen',
            'loader': '_frozen_importlib.FrozenImporter', 'is_frozen': True,
            'same_module_object': True,
            'records': {name: copy.deepcopy(runtime['modules'][name]) for name in ('os.path', 'posixpath')}}


def live_alias(runtime, binding):
    if binding is not None:
        process = {'pid': os.getpid(),
                   'proc_start_ticks': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
                   'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        require(binding.get('process') == process, 'N36 alias live process differs')
    alias, canonical = sys.modules.get('os.path'), sys.modules.get('posixpath')
    spec = getattr(canonical, '__spec__', None)
    require(alias is not None and alias is canonical is os.path
            and canonical.__name__ == 'posixpath'
            and getattr(spec, 'name', None) == 'posixpath'
            and getattr(spec, 'origin', None) == 'frozen'
            and spec.loader is importlib.machinery.FrozenImporter
            and getattr(canonical, '__loader__', None) is importlib.machinery.FrozenImporter
            and _imp.is_frozen('posixpath'), 'N36 frozen alias live identity differs')
    require(runtime['interpreter'] == interpreter_identity(), 'N36 alias interpreter differs')
    for name, module in (('os.path', alias), ('posixpath', canonical)):
        path = str(Path(module.__file__).resolve())
        require(module.__file__ == path
                and runtime['modules'].get(name) == {'path': path, 'sha256': sha(path)},
                'N36 frozen alias inventory differs: ' + name)
    return alias_claim(runtime, binding)


def verify_alias(receipt, runtime, runtime_receipt, binding):
    require(receipt.get('schema') == 'n36-source-execution-v2', 'N36 alias receipt schema')
    require(isinstance(binding, dict) and set(binding) == {'context', 'runtime_closure', 'process', 'phase'}
            and binding['phase'] in ('runtime_before', 'runtime_after')
            and all(isinstance(binding[k], dict) and set(binding[k]) == {'path', 'sha256'}
                    for k in ('context', 'runtime_closure'))
            and isinstance(binding['process'], dict)
            and set(binding['process']) == {'pid', 'proc_start_ticks', 'boot_id'}
            and type(binding['process']['pid']) is int and binding['process']['pid'] > 0
            and isinstance(binding['process']['proc_start_ticks'], str)
            and binding['process']['proc_start_ticks'].isdigit()
            and isinstance(binding['process']['boot_id'], str) and bool(binding['process']['boot_id']),
            'N36 alias external binding required')
    require(receipt.get('binding') == binding == runtime_receipt.get('binding'),
            'N36 alias context/process/phase differs')
    require(receipt.get('interpreter') == runtime['interpreter'] == interpreter_identity(),
            'N36 alias interpreter differs')
    claim = receipt.get('frozen_aliases', {}).get('os.path')
    require(set(receipt.get('frozen_aliases', {})) == {'os.path'}
            and claim == alias_claim(runtime, binding)
            and claim['same_module_object'] is True and claim['is_frozen'] is True
            and 'posixpath' in receipt['frozen_modules'] and _imp.is_frozen('posixpath'),
            'N36 frozen alias proof differs')
    for name in ('os.path', 'posixpath'):
        require(runtime_receipt['modules'].get(name) == runtime['modules'][name],
                'N36 alias canonical inventory evidence missing/differs')
    require(runtime['modules']['os.path'] == runtime['modules']['posixpath'],
            'N36 alias inventory paths/hashes differ')
    return {'os.path'}


def attest(root, source, runtime, *, binding=None):
    state = active()
    root = Path(root).resolve()
    index = {str(root / row['path']): row['sha256'] for row in source['files']}
    index.update({row['path']: row['sha256'] for row in runtime['modules'].values()})
    generated = {name: rule['sha256'] for name, rule in runtime.get('generated_modules', {}).items()}
    records = []
    for (name, filename), digest in sorted(state.compiled.items()):
        path = str(Path(filename).resolve())
        require(index.get(path, generated.get(name)) == digest and sha(Path(path)) == digest,
                'N36 compiled source not frozen: ' + name)
        records.append({'module': name, 'path': path, 'sha256': digest})
    bootstrap = str(root / 'scripts/qd_ed_n36_bootstrap.py')
    require(str(Path(state.__file__).resolve()) == bootstrap
        and index.get(bootstrap) == state.bootstrap_digest == sha(Path(bootstrap)), 'N36 bootstrap not frozen')
    startup = []
    for name, (filename, digest) in sorted(state.startup_sources.items()):
        path = str(Path(filename).resolve())
        require(index.get(path) == digest == sha(Path(path)), 'N36 startup source not frozen')
        startup.append({'module': name, 'path': path, 'sha256': digest})
    # No unrecorded custom Python loader may slip through the module inventory.
    known = {(r['module'], r['path']) for r in records + startup}
    frozen = []
    aliases = {}
    for name, module in list(sys.modules.items()):
        if name in ('torch.ops', 'torch.classes'):
            # Same two virtual namespaces explicitly excepted by the existing
            # source/runtime attestors; bind their actual implementing classes.
            owner_name, class_name = (('torch._ops', '_Ops') if name == 'torch.ops'
                                      else ('torch._classes', '_Classes'))
            owner = sys.modules.get(owner_name)
            require(owner is not None and type(module) is getattr(owner, class_name)
                and module is getattr(sys.modules['torch'], name.split('.')[1])
                and (owner_name, str(Path(owner.__file__).resolve())) in known,
                'N36 virtual Torch namespace owner differs')
            continue
        spec = getattr(module, '__spec__', None)
        filename = getattr(module, '__file__', None)
        if name == 'os.path':
            aliases[name] = live_alias(runtime, binding)
        if getattr(spec, 'origin', None) == 'frozen':
            require(_imp.is_frozen(spec.name) and spec.loader is importlib.machinery.FrozenImporter,
                    'N36 unbound frozen module: ' + name)
            frozen.append(spec.name)
            continue
        require(not filename or not str(filename).endswith(('.pyc', '.pyo')),
                'N36 bytecode module loaded: ' + name)
        if not filename or not str(filename).endswith('.py'):
            continue
        path = str(Path(filename).resolve())
        if module is state:
            continue
        canonical = getattr(spec, 'name', name)
        require((canonical, path) in known, 'N36 unrecorded Python execution: ' + name)
    return {'schema': 'n36-source-execution-v2', 'binding': copy.deepcopy(binding),
        'interpreter': copy.deepcopy(runtime['interpreter']), 'frozen_aliases': aliases, 'bootstrap': {'path': bootstrap, 'sha256': state.bootstrap_digest},
        'compiled': records, 'startup_source_only': startup, 'frozen_modules': sorted(set(frozen)),
        'exceptions': ['interpreter-bound built-in/frozen modules', 'separately inventoried native extensions',
                       'existing independently validated generated-runtime rules',
                       'torch.ops/classes instances of inventoried owner classes']}


def verify_receipt(receipt, root, source, runtime, *, loaded=None, runtime_receipt=None, binding=None):
    require(receipt['schema'] == 'n36-source-execution-v2', 'N36 execution receipt schema')
    index = {str(Path(root).resolve() / row['path']): row['sha256'] for row in source['files']}
    index.update({row['path']: row['sha256'] for row in runtime['modules'].values()})
    generated = {name: rule['sha256'] for name, rule in runtime.get('generated_modules', {}).items()}
    require(receipt['bootstrap'] == {'path': str(Path(root).resolve() / 'scripts/qd_ed_n36_bootstrap.py'),
        'sha256': index.get(str(Path(root).resolve() / 'scripts/qd_ed_n36_bootstrap.py'))}, 'N36 bootstrap receipt')
    for row in receipt['compiled'] + receipt['startup_source_only']:
        require(index.get(row['path'], generated.get(row['module'])) == row['sha256'], 'N36 executable receipt bytes')
    require({r['module'] for r in receipt['startup_source_only']} == {'encodings', 'encodings.aliases', 'encodings.utf_8'},
            'N36 startup receipt coverage')
    frozen = receipt['frozen_modules']
    require(frozen == sorted(set(frozen)) and all(_imp.is_frozen(name) for name in frozen), 'N36 frozen exceptions')
    known = {(r['path'], r['sha256']) for r in receipt['compiled'] + receipt['startup_source_only']}
    observed = list((loaded or {}).values())
    if runtime_receipt is not None:
        from scripts import qd_ed_n34_source as closure
        require(binding is not None, 'N36 external runtime binding required')
        closure.verify_runtime_receipt(runtime, runtime_receipt, binding=binding, after=False)
        aliases = verify_alias(receipt, runtime, runtime_receipt, binding)
        observed += [row for name, row in runtime_receipt['modules'].items() if name not in frozen and name not in aliases]
        observed += [e['record'] for e in runtime_receipt['generated_modules'].values()]
    for row in observed:
        path = Path(row['path'])
        path = str(path if path.is_absolute() else Path(root).resolve() / path)
        if path == receipt['bootstrap']['path']:
            continue
        if path.endswith('.py'):
            require((path, row['sha256']) in known, 'N36 module missing executable receipt: ' + path)
    required = {'scripts.qd_ed_n36_worker', 'scripts.qd_ed_n36_native', 'scripts.qd_ed_n36_arithmetic',
                'scripts.audit_decision_evidence', 'scripts.qd_ed_n36_source'}
    require(required <= {r['module'] for r in receipt['compiled']}, 'N36 executable receipt coverage')
