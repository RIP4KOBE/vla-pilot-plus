"""Exact local-hub source admission derived only from a bound runtime manifest.

No discovery, download, model construction, or manifest mutation. Package search
locations permit traversal only; every executable file still needs its own row.
"""
import hashlib
import importlib.machinery
import json
import os
import sys


def require(ok, message):
    if not ok:
        raise ImportError('N36 DINO ' + message)


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


class DinoSources:
    def __init__(self, reference):
        require(set(reference) == {'path', 'sha256'}, 'manifest reference fields')
        path = reference['path']
        require(os.path.isabs(path) and path == os.path.realpath(path), 'manifest path not canonical')
        with open(path, 'rb') as stream:
            data = stream.read()
        require(hashlib.sha256(data).hexdigest() == reference['sha256'], 'manifest hash differs')
        manifest = json.loads(data)
        require(manifest['schema'] == 'qd-ed-runtime-setup-v1', 'manifest schema')
        home = manifest['environment']['TORCH_HOME']
        require(os.path.isabs(home) and home == os.path.realpath(home), 'TORCH_HOME not canonical')
        self.root = os.path.join(home, 'hub', 'facebookresearch_dinov2_main')
        require(self.root == os.path.realpath(self.root), 'root not canonical')
        self.reference = dict(reference)
        self.files, self.names, self.packages = {}, {}, {}
        for row in manifest['files']:
            path = row['path']
            if not path.startswith(self.root + os.sep) or not path.endswith('.py'):
                continue
            require(set(row) == {'path', 'resolved_path', 'sha256', 'size_bytes'}, 'source row fields')
            require(path == row['resolved_path'] == os.path.realpath(path), 'source path not canonical')
            require(path not in self.files, 'duplicate source row')
            require(type(row['size_bytes']) is int and row['size_bytes'] >= 0
                    and isinstance(row['sha256'], str) and len(row['sha256']) == 64
                    and all(c in '0123456789abcdef' for c in row['sha256']), 'source hash/size')
            relative = path[len(self.root) + 1:]
            if relative == 'hubconf.py':
                name = 'hubconf.py'  # torch.hub.MODULE_HUBCONF, not sys.modules
            else:
                parts = relative[:-3].split(os.sep)
                if parts[-1] == '__init__':
                    parts.pop()
                require(parts and all(p.isidentifier() for p in parts), 'source module name')
                name = '.'.join(parts)
            require(name not in self.names, 'ambiguous source module')
            self.files[path] = dict(row)
            self.names[name] = path
            parent = os.path.dirname(path)
            while parent != self.root:
                self.packages[parent[len(self.root) + 1:].replace(os.sep, '.')] = parent
                parent = os.path.dirname(parent)
        require(self.names.get('hubconf.py') == self.root + '/hubconf.py'
                and self.names.get('dinov2') == self.root + '/dinov2/__init__.py', 'required source rows missing')

    def contains(self, path):
        return isinstance(path, str) and (path == self.root or path.startswith(self.root + os.sep))

    def check_file(self, name, path, compiled_digest=None):
        require(path == os.path.realpath(path) and self.names.get(name) == path,
                'unlisted source or module origin: ' + str(path))
        row = self.files[path]
        require(os.path.getsize(path) == row['size_bytes'] and digest(path) == row['sha256'],
                'source bytes differ: ' + path)
        require(compiled_digest is None or compiled_digest == row['sha256'], 'compiled bytes differ: ' + path)

    def check_package(self, name, path):
        require(path == os.path.realpath(path) and self.packages.get(name) == path,
                'package path differs: ' + str(path))

    def check_origin(self, name, path, compiled_digest=None):
        if path in self.packages.values():
            require(compiled_digest is None, 'directory is not source')
            self.check_package(name, path)
        else:
            self.check_file(name, path, compiled_digest)

    def check_search(self, entry):
        require(entry == self.root == os.path.realpath(entry), 'search root differs')
        self.check_file('hubconf.py', self.root + '/hubconf.py')

    def audit(self, compiled):
        # Also retain hubconf and modules removed from sys.modules. A local hub
        # executes hubconf outside sys.modules, including on repeated loads.
        records = []
        for (name, path), value in sorted(compiled.items()):
            if self.contains(os.path.realpath(path)) or name in ('dinov2', 'hubconf.py') or name.startswith('dinov2.'):
                self.check_file(name, path, value)
                records.append({'module': name, 'path': path, 'sha256': value})
        for name, module in list(sys.modules.items()):
            spec = getattr(module, '__spec__', None)
            path = getattr(module, '__file__', None)
            origin = getattr(spec, 'origin', None)
            if not (name == 'dinov2' or name.startswith('dinov2.') or self.contains(path) or self.contains(origin)):
                continue
            require(spec is not None and spec.name == name and module.__name__ == name, 'cached module identity differs')
            locations = getattr(spec, 'submodule_search_locations', None)
            if path is None:
                require(name not in self.names and origin is None and locations is not None
                        and isinstance(spec.loader, importlib.machinery.NamespaceLoader)
                        and getattr(module, '__loader__', None) is spec.loader, 'namespace identity differs')
            else:
                self.check_file(name, path)
                require(origin == path and type(spec.loader) is importlib.machinery.SourceFileLoader
                        and getattr(module, '__loader__', None) is spec.loader
                        and spec.loader.path == path and spec.loader.name == name
                        and compiled.get((name, path)) == self.files[path]['sha256'],
                        'cached module lacks source execution/origin proof')
            if locations is not None:
                require(list(locations) == [self.packages.get(name)]
                        and list(getattr(module, '__path__', ())) == list(locations), 'cached package paths differ')
                self.check_package(name, list(locations)[0])
        return {'runtime_manifest': dict(self.reference), 'root': self.root, 'compiled': records}

    def verify(self, claim, compiled):
        require(claim.get('runtime_manifest') == self.reference and claim.get('root') == self.root,
                'receipt manifest/root differs')
        expected = []
        for row in compiled:
            if self.contains(os.path.realpath(row['path'])) or row['module'] in ('dinov2', 'hubconf.py') or row['module'].startswith('dinov2.'):
                self.check_file(row['module'], row['path'], row['sha256'])
                expected.append(row)
        require(claim.get('compiled') == expected, 'receipt execution coverage differs')
