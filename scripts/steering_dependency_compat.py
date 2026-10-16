"""Install and verify the exact Robosuite compatibility files used in evaluation.

Only the pinned upstream bytes or the already patched bytes are accepted.
No simulator import, environment activation, network access, or GPU work occurs.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

MANIFEST = Path(__file__).with_name('dependency_patches') / 'robosuite-1.4.0.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_location():
    distribution = importlib.metadata.distribution('robosuite')
    return Path(distribution.locate_file('robosuite')).resolve(), distribution.version


def contract():
    specification = json.loads(MANIFEST.read_text())
    root, version = package_location()
    if version != specification['version']:
        raise ValueError(f'Expected robosuite {specification["version"]}, found {version}')
    entries = []
    for relative, expected in specification['files'].items():
        path = root / relative
        patch = MANIFEST.parent / expected['patch']
        if not path.resolve().is_relative_to(root) or not patch.resolve().is_relative_to(MANIFEST.parent.resolve()):
            raise ValueError('Compatibility file path escapes its root')
        if path.is_symlink() or digest(patch.read_bytes()) != expected['patch_sha256']:
            raise ValueError(f'Compatibility patch/file identity differs: {relative}')
        entries.append((relative, path, patch, expected, path.read_bytes()))
    return root, version, entries


def verify_runtime_compat():
    root, version, entries = contract()
    files = {}
    for relative, _, _, expected, content in entries:
        actual = digest(content)
        if actual != expected['patched_sha256']:
            raise ValueError(f'Robosuite compatibility is missing or changed: {relative}; '
                             'run python scripts/prepare_steering_assets.py install-runtime-compat')
        files[relative] = actual
    return {'valid': True, 'distribution': 'robosuite', 'version': version,
            'root': str(root), 'files': files, 'manifest_sha256': digest(MANIFEST.read_bytes())}


def install_runtime_compat():
    root, _, entries = contract()
    if not root.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError('Refusing to modify a dependency outside the active Python environment')
    pending = []
    # Validate every input before changing any installed file.
    for relative, path, patch, expected, content in entries:
        actual = digest(content)
        if actual == expected['patched_sha256']:
            continue
        if actual != expected['upstream_sha256']:
            raise ValueError(f'Unknown Robosuite file; no files changed: {relative}')
        pending.append((relative, path, patch, expected, content))
    staged = []
    with tempfile.TemporaryDirectory(prefix='steering-compat-') as directory:
        stage = Path(directory)
        for relative, path, patch, expected, content in pending:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.replace(b'\r\n', b'\n'))
            subprocess.run(['git', 'apply', '--check', str(patch.resolve())], cwd=stage, check=True,
                           capture_output=True)
            subprocess.run(['git', 'apply', str(patch.resolve())], cwd=stage, check=True,
                           capture_output=True)
            result = target.read_bytes()
            # Preserve the legacy files' exact CRLF/mixed-newline bytes as well
            # as their logic, so the installed dependency has one known hash.
            newlines = expected.get('output_newlines', {})
            if newlines.get('default') == 'crlf':
                lf_only = set(newlines.get('lf_only_lines', []))
                result = b''.join(line if number in lf_only else line.replace(b'\n', b'\r\n')
                                  for number, line in enumerate(result.splitlines(keepends=True), 1))
            if digest(result) != expected['patched_sha256']:
                raise ValueError(f'Unexpected compatibility output; no files changed: {relative}')
            staged.append((path, result))
        for path, content in staged:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.steering-compat-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            try:
                temporary.chmod(stat.S_IMODE(path.stat().st_mode))
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    report = verify_runtime_compat()
    report['updated_files'] = [str(path.relative_to(root)) for path, _ in staged]
    return report
