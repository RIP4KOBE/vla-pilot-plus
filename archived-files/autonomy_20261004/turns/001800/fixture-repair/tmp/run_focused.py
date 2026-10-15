import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

tmp = Path(__file__).resolve().parent
authority = json.loads((tmp.parent / 'authority-v1.json').read_text())
root = Path(authority['worktree'])
stops = [Path(p) for p in authority['stop_authority']['paths']]
deadline = dt.datetime.fromisoformat(authority['stop_authority']['deadline'].replace('Z', '+00:00')).timestamp()
assert not any(p.exists() for p in stops)
assert time.time() < min(deadline, dt.datetime(2026, 10, 11, 5, 25, 53, tzinfo=dt.timezone.utc).timestamp())
label = sys.argv[1]
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
def ref(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
paths = ['tests/test_n36_readiness_prepare.py', 'tests/test_n36_preparation_binding.py',
         'tests/test_n36_importlib_alias.py', 'tests/test_n36_frozen_alias.py',
         'scripts/qd_ed_n36_source.py', 'scripts/qd_ed_n36_readiness_prepare.py',
         'scripts/qd_ed_n36_engineering_r1.py', 'scripts/qd_ed_n34_source.py',
         'scripts/qd_ed_n36_build.py', 'configs/qd_ed_final/n36_engineering_r1_spec.disabled.json']
assert git('status', '--porcelain') == ''
sources = [ref(root / p) for p in paths]
env_updates = dict(OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
                  NUMEXPR_NUM_THREADS='2', VECLIB_MAXIMUM_THREADS='2',
                  PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='', TMPDIR=str(tmp),
                  PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
tests = ['tests/test_n36_preparation_binding.py',
         'tests/test_n36_readiness_prepare.py::test_exact_measured_derivation_and_disabled_baseline',
         'tests/test_n36_readiness_prepare.py::test_measured_derivation_reaches_real_receipt_verifier',
         'tests/test_n36_readiness_prepare.py::test_measured_partition_rejects_foreign_journal_row',
         'tests/test_n36_importlib_alias.py', 'tests/test_n36_frozen_alias.py']
command = ['taskset', '-c', '0,1', sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
           *tests, '-k', 'not live_rejects_substitution and not producer_rejects_substitution',
           '--basetemp=' + str(tmp / ('pytest-' + label))]
log = tmp / ('test-' + label + '.log')
record = dict(command=' '.join(k + '=' + shlex.quote(v) for k, v in env_updates.items()) + ' ' +
              shlex.join(command) + ' > ' + shlex.quote(str(log)) + ' 2>&1',
              cwd=str(root), source_commit=git('rev-parse', 'HEAD'), source_tree=git('rev-parse', 'HEAD^{tree}'),
              sources=sources, started_at=dt.datetime.now(dt.timezone.utc).isoformat())
started = time.monotonic()
with log.open('wb') as stream:
    child = subprocess.Popen(command, cwd=root, env={**os.environ, **env_updates}, stdout=stream, stderr=subprocess.STDOUT)
    while child.poll() is None:
        if any(p.exists() for p in stops) or time.time() >= deadline or time.monotonic() - started > 180:
            child.terminate()
            record['interrupted'] = True
            break
        time.sleep(0.25)
    record['exit_code'] = child.wait(timeout=10)
record.update(elapsed_seconds=time.monotonic() - started, log=ref(log),
              source_after=git('rev-parse', 'HEAD'), working_tree=git('status', '--porcelain'),
              source_hashes_unchanged=sources == [ref(root / p) for p in paths])
(tmp / ('run-' + label + '.json')).write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: record[k] for k in ('source_commit', 'exit_code', 'elapsed_seconds', 'source_hashes_unchanged', 'log')}, indent=2))
print(log.read_text()[-14000:])
