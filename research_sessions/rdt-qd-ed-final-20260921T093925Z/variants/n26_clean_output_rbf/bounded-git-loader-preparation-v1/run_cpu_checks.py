"""Bounded synthetic checks only; children restricted to owned fixtures."""
import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time
import traceback
import unittest

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / 'validation-cost-cache-preparation-v1/verified_immutable_cache.py'
PREFIXES = tuple(Path(p).resolve() for p in {sys.prefix, sys.base_prefix, '/usr/lib/python3.12'})
PYTHON = str(Path(sys.executable).resolve())
DENIALS = []
EXPECTED_DENIALS = 0
START = time.monotonic()


def inside(p, root):
    return p == root or root in p.parents


def guard(event, args):
    def reject(reason):
        DENIALS.append({'event': event, 'reason': reason})
        raise PermissionError('bounded CPU scope: ' + reason)
    if event.startswith('socket.') or event in ('os.system', 'os.posix_spawn', 'os.fork'):
        reject('network/unapproved process')
    if event == 'import' and args[0].split('.')[0] in ('torch','numpy','requests','robosuite'):
        reject('prohibited runtime import')
    if event == 'subprocess.Popen':
        executable, argv, cwd, env = args
        if not isinstance(argv, (list, tuple)) or not cwd or not inside(Path(cwd).resolve(), HERE / 'fixtures'):
            reject('child outside synthetic repository fixtures')
        if not isinstance(env, dict) or env.get('CUDA_VISIBLE_DEVICES') != '':
            reject('child environment')
        if executable == '/usr/bin/git':
            if not any(v in argv for v in ('init','hash-object','mktree','commit-tree','cat-file')):
                reject('unapproved Git command')
            for v in argv:
                if isinstance(v, str) and v.startswith('--git-dir=') and not inside(Path(v[10:]).resolve(), HERE / 'fixtures'):
                    reject('Git directory outside fixture')
        elif executable == PYTHON:
            if len(argv) != 5 or argv[1:4] != ['-I','-B',str(HERE/'fake_child.py')]:
                reject('unapproved fake child')
        else:
            reject('unapproved child binary')
    if event in ('open','os.listdir','os.scandir','os.remove','os.rmdir','os.mkdir','os.rename','os.symlink'):
        raw = args[0]
        if isinstance(raw, int):
            return
        if not isinstance(raw, (str, bytes, os.PathLike)):
            reject('unrecognized filesystem target')
        if event == 'os.symlink' and not inside(Path(args[1]).absolute(), HERE):
            reject('symlink write outside preparation')
        p = Path(os.fsdecode(raw)).resolve()
        writing = event in ('os.remove','os.rmdir','os.mkdir','os.rename','os.symlink')
        if event == 'open':
            mode = args[1]
            flags = args[2] if len(args) > 2 else 0
            writing = (isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if inside(p, HERE):
            if event == 'os.rename' and not inside(Path(args[1]).resolve(), HERE):
                reject('rename leaves preparation')
            return
        if p == Path('/dev/null') and stat.S_ISCHR(p.stat().st_mode) and p.stat().st_rdev == os.makedev(1,3):
            return
        if not writing and (p == CACHE or any(inside(p, root) for root in PREFIXES)):
            return
        reject('read/write outside allowlisted preparation/dependency paths')


def limits():
    files = [p for p in HERE.rglob('*') if p.is_file()]
    count, total = len(files), sum(p.stat().st_size for p in files)
    if count > 256 or total > 8*1024*1024:
        raise RuntimeError('preparation file/byte limit exceeded')
    return {'regular_files': count, 'bytes': total}


def alarm(_sig, _frame):
    raise TimeoutError('aggregate synthetic test deadline reached')


def main():
    global EXPECTED_DENIALS
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name] = '2'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    allowed = sorted(os.sched_getaffinity(0))[:2]
    os.sched_setaffinity(0, allowed)
    prior = list(HERE.glob('cpu-run-*.json'))
    consumed = sum(json.loads(p.read_text())['wall_seconds'] for p in prior)
    if consumed >= 120:
        raise RuntimeError('aggregate test budget exhausted')
    version = len(prior) + 1
    log = HERE / ('cpu-run-%02d.log' % version)
    result_path = HERE / ('cpu-run-%02d.json' % version)
    before = limits()
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, 120-consumed)
    sys.dont_write_bytecode = True
    sys.addaudithook(guard)
    sys.path.insert(0, str(HERE))
    success = False
    tests = 0
    error = None
    with log.open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            for action in (lambda: open(HERE.parent/'unauthorized-dummy', 'rb'),
                           lambda: socket.socket(),
                           lambda: subprocess.Popen(['/bin/true'], cwd=str(HERE), env={'CUDA_VISIBLE_DEVICES':''})):
                try:
                    action()
                except PermissionError:
                    EXPECTED_DENIALS += 1
                else:
                    raise RuntimeError('negative guard failed')
            module = importlib.import_module('test_bounded_git_blob')
            suite = (unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:], module)
                     if len(sys.argv) > 1 else unittest.defaultTestLoader.loadTestsFromModule(module))
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            tests = result.testsRun
            for proc in module.SPAWNED:
                if proc.poll() is None:
                    raise RuntimeError('owned test child not reaped')
            success = result.wasSuccessful() and len(DENIALS) == EXPECTED_DENIALS
        except BaseException as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            traceback.print_exc()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    elapsed = time.monotonic()-START
    summary = {'schema': 'bounded-git-loader-synthetic-check-v1', 'passed': success,
        'tests_run': tests, 'selection': sys.argv[1:] or ['ALL'], 'wall_seconds': elapsed, 'prior_test_seconds': consumed,
        'aggregate_test_seconds': consumed+elapsed, 'cpu_affinity_count': len(allowed),
        'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES'], 'torch_imported': 'torch' in sys.modules,
        'expected_guard_denials': EXPECTED_DENIALS, 'unexpected_guard_denials': len(DENIALS)-EXPECTED_DENIALS,
        'denials': DENIALS, 'error': error, 'before': before, 'after': limits(),
        'real_history_reads': False, 'production_integration': False}
    with result_path.open('x') as stream:
        json.dump(summary, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: summary[k] for k in ('passed','tests_run','wall_seconds','aggregate_test_seconds','unexpected_guard_denials','error','after')}))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
