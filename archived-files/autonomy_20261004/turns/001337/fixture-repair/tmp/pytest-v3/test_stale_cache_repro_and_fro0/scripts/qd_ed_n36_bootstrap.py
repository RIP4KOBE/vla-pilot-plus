"""Linux CPython source-only entry. Invoke by absolute script path, never -m.

Required interpreter arguments: -I -S -B -X pycache_prefix=/dev/null.
The non-directory cache prefix also covers encodings before this script starts.
No site/.pth/startup hook is executed. Native/frozen code remains subject to the
separate interpreter, runtime and native-build inventories.
"""
import sys

if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
        and sys.flags.optimize == 0
        and sys.pycache_prefix == '/dev/null'
        and sys._xoptions.get('pycache_prefix') == '/dev/null'):
    raise RuntimeError('N36 requires -I -S -B -X pycache_prefix=/dev/null startup')

# These are interpreter-owned frozen modules; no project/runtime Python import
# occurs before the source loader is installed.
import _frozen_importlib_external as external
import _hashlib
import posix

if posix.stat('/dev/null').st_mode & 0o170000 != 0o020000:
    raise RuntimeError('N36 cache prefix must be the /dev/null character device')

compiled = {}


def source_code(self, fullname):
    if 'validate_search' in globals():
        validate_search()
    path = self.get_filename(fullname)
    data = self.get_data(path)
    digest = _hashlib.openssl_sha256(data).hexdigest()
    if 'validate_origin' in globals():
        validate_origin(fullname, path, digest)
    code = self.source_to_code(data, path)
    key = (fullname, path)
    if key in compiled and compiled[key] != digest:
        raise RuntimeError('N36 source changed during import: ' + fullname)
    compiled[key] = digest
    return code


def reject_bytecode(*args, **kwargs):
    raise ImportError('N36 disallows sourceless and zip executable imports')


external.SourceFileLoader.get_code = source_code
external.SourcelessFileLoader.get_code = reject_bytecode
import zipimport
zipimport.zipimporter.get_code = reject_bytecode
zipimport.zipimporter.exec_module = reject_bytecode
zipimport.zipimporter.load_module = reject_bytecode

# CPython's pre-script source imports. They already used the impossible cache
# prefix; make this exception explicit and fail closed on new startup modules.
startup_sources = {}
for name, module in list(sys.modules.items()):
    spec = getattr(module, '__spec__', None)
    if getattr(spec, 'origin', None) in ('built-in', 'frozen', None):
        continue
    if name not in ('encodings', 'encodings.aliases', 'encodings.utf_8', '_hashlib'):
        raise RuntimeError('N36 unreviewed startup module: ' + name)
    if name.startswith('encodings'):
        if type(spec.loader) is not external.SourceFileLoader:
            raise RuntimeError('N36 encoding startup must use filesystem source')
        with open(module.__file__, 'rb') as stream:
            startup_sources[name] = (module.__file__, _hashlib.openssl_sha256(stream.read()).hexdigest())

with open(__file__, 'rb') as stream:
    bootstrap_digest = _hashlib.openssl_sha256(stream.read()).hexdigest()
sys.modules['_n36_source_bootstrap'] = sys.modules[__name__]

import os
import site
import runpy

# Restore only explicit search directories, without executing arbitrary .pth or
# sitecustomize code. Every imported path is still checked by runtime attestation.
root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
# Never inherit adjacent checkouts or arbitrary PYTHONPATH entries.
sys.path[:0] = [root] + [os.path.join(root, p) for p in
    ('third_party/lerobot/src', 'third_party/rdt', 'third_party/libero_pro')]
for directory in site.getsitepackages():
    if directory not in sys.path:
        sys.path.append(directory)

# Load the validator before enabling search checks: it uses only engineering
# code/stdlib and must not recursively import while validating Torch's path.
from scripts.qd_ed_n36_generated import admit as admit_generated, CONTENT_SHA

def validate_search():
    for entry in sys.path:
        path = os.path.realpath(entry)
        if not entry or not any(path == base or path.startswith(base + os.sep)
                                for base in (root, os.path.realpath(sys.prefix))):
            try:
                if entry != path:
                    raise ValueError('noncanonical generated directory')
                admit_generated(path, compiled)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                raise ImportError('N36 foreign import search path: ' + path) from exc


def validate_origin(fullname, filename, digest=None):
    path = os.path.realpath(filename)
    if any(path == base or path.startswith(base + os.sep)
           for base in (root, os.path.realpath(sys.prefix))):
        return
    if (fullname != '_remote_module_non_scriptable' or filename != path
            or os.path.basename(path) != fullname + '.py'
            or (digest is not None and digest != CONTENT_SHA)):
        raise ImportError('N36 foreign generated import origin: ' + filename)
    admit_generated(os.path.dirname(path), compiled)


class GeneratedSearchGuard:
    """Check native/namespace discoveries too, before PathFinder can load them."""
    @staticmethod
    def find_spec(fullname, path=None, target=None):
        validate_search()
        spec = external.PathFinder.find_spec(fullname, path, target)
        if spec is not None:
            if spec.origin is not None:
                validate_origin(fullname, spec.origin)
            for directory in spec.submodule_search_locations or ():
                validate_origin(fullname, directory)
        return spec


validate_search()
sys.meta_path.insert(sys.meta_path.index(external.PathFinder), GeneratedSearchGuard)

if len(sys.argv) < 2:
    raise SystemExit('usage: qd_ed_n36_bootstrap.py MODULE [ARGS...]')
target = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_module(target, run_name='__main__', alter_sys=True)
