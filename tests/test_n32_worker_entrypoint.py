"""Actual -m entrypoint, intercepted at main before dispatch; no GPU/simulation."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import qd_ed_n32_bridge as b, qd_ed_n23_worker as w


# sitecustomize installs a test-only trace before Python executes the real -m
# worker. No public production bypass is introduced, and no canonical worker is
# imported in the child. Stop at main before parsing args or opening dispatch.
HOOK = r'''
import json, os, sys, runpy
from pathlib import Path

def trace(frame, event, arg):
    if event != 'call' or frame.f_code.co_name != 'main' or frame.f_globals.get('__spec__', None) is None:
        return trace
    if frame.f_globals['__spec__'].name != 'scripts.qd_ed_n32_worker':
        return trace
    sys.settrace(None)
    g = frame.f_globals
    root = Path(os.environ['TEST_ROOT'])
    source = json.loads(Path(os.environ['TEST_SOURCE']).read_text())
    fault = os.environ.get('TEST_FAULT', '')
    assert g['__name__'] == '__main__'
    assert 'scripts.qd_ed_n32_worker' not in sys.modules
    try:
        old = g['b'].attest_loaded(root, source)
        assert 'scripts.qd_ed_n32_worker' not in old
        if fault == 'spec_name': g['__spec__'].name = 'scripts.wrong'
        if fault == 'missing_spec': g['__spec__'] = None
        if fault == 'origin': g['__spec__'].origin = str(root / 'scripts/qd_ed_n32_bridge.py')
        if fault == 'file': g['__file__'] = str(root / 'scripts/qd_ed_n32_bridge.py')
        if fault == 'hash':
            next(r for r in source['files'] if r['path'] == 'scripts/qd_ed_n32_worker.py')['sha256'] = '0' * 64
        if fault == 'missing':
            source['files'] = [r for r in source['files'] if r['path'] != 'scripts/qd_ed_n32_worker.py']
        if fault == 'tamper':
            with (root / 'scripts/qd_ed_n32_worker.py').open('a') as f: f.write('\n# post-freeze tamper\n')
        before = g['attest_worker_loaded'](root, source)
        runpy.run_path(os.environ['TEST_MAIN'], run_name='__main__')
        after = g['attest_worker_loaded'](root, source)
        assert before == after
        assert 'scripts.qd_ed_n32_worker' not in sys.modules
        result = dict(before=before, after=after, old=old)
    except ValueError as exc:
        result = dict(error=str(exc))
    Path(os.environ['TEST_RESULT']).write_text(json.dumps(result))
    raise SystemExit(0)
sys.settrace(trace)
'''


def entrypoint(tmp_path, fault=''):
    root = b.ROOT
    if fault == 'tamper':
        # Only copied test bytes may be changed. Preserve all scripts dependencies
        # locally; core/utils imports (if any) retain their normal frozen checks.
        import shutil
        root = tmp_path / 'checkout'
        shutil.copytree(b.ROOT / 'scripts', root / 'scripts',
                        ignore=shutil.ignore_patterns('__pycache__'))
    source = {'files': [{'path': str(p.relative_to(root)), 'sha256': w.sha(p)}
                        for folder in ('scripts', 'core', 'utils')
                        for p in (root / folder).rglob('*.py')]}
    (tmp_path / 'source.json').write_text(json.dumps(source))
    (tmp_path / 'sitecustomize.py').write_text(HOOK)
    (tmp_path / 'synthetic_main.py').write_text("assert __name__ == '__main__'\n")
    env = {**os.environ, 'PYTHONPATH': str(tmp_path) + os.pathsep + str(root),
           'PYTHONDONTWRITEBYTECODE': '1', 'CUDA_VISIBLE_DEVICES': '',
           'TEST_ROOT': str(root), 'TEST_SOURCE': str(tmp_path / 'source.json'),
           'TEST_RESULT': str(tmp_path / 'result.json'), 'TEST_FAULT': fault,
           'TEST_MAIN': str(tmp_path / 'synthetic_main.py')}
    result = subprocess.run([sys.executable, '-m', 'scripts.qd_ed_n32_worker'],
                            cwd=root, env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads((tmp_path / 'result.json').read_text())


@pytest.fixture(scope='module')
def worker_entrypoint_inventory(tmp_path_factory):
    return entrypoint(tmp_path_factory.mktemp('worker-entrypoint'))


def test_real_m_inventory_and_old_failure(worker_entrypoint_inventory):
    result = worker_entrypoint_inventory
    name = 'scripts.qd_ed_n32_worker'
    assert name not in result['old']
    for phase in ('before', 'after'):
        record = result[phase][name]
        assert record == {'path': 'scripts/qd_ed_n32_worker.py',
                          'sha256': w.sha(b.ROOT / 'scripts/qd_ed_n32_worker.py'),
                          'module_name': '__main__', 'spec_name': name,
                          'origin': str(b.ROOT / 'scripts/qd_ed_n32_worker.py')}
    print('Real -m: old inventory omits worker; repaired before/after attest exact spec/origin/hash.')


@pytest.mark.parametrize('fault,reason', [
    ('spec_name', 'worker module spec differs'),
    ('missing_spec', 'worker module spec differs'),
    ('origin', 'worker module origin differs'),
    ('file', 'worker module origin differs'),
    ('hash', 'worker source not frozen'),
    ('missing', 'worker source not frozen'),
    ('tamper', 'worker source not frozen'),
])
def test_real_m_rejects_wrong_identity(tmp_path, fault, reason):
    assert entrypoint(tmp_path, fault) == {'error': reason}
