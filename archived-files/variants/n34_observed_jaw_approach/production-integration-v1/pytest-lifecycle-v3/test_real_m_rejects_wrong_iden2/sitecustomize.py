
import json, os, sys, runpy
from pathlib import Path

def trace(frame, event, arg):
    if event != 'call' or frame.f_code.co_name != 'main' or frame.f_globals.get('__spec__', None) is None:
        return trace
    if frame.f_globals['__spec__'].name != 'scripts.qd_ed_n34_worker':
        return trace
    sys.settrace(None)
    g = frame.f_globals
    root = Path(os.environ['TEST_ROOT'])
    source = json.loads(Path(os.environ['TEST_SOURCE']).read_text())
    fault = os.environ.get('TEST_FAULT', '')
    assert g['__name__'] == '__main__'
    assert 'scripts.qd_ed_n34_worker' not in sys.modules
    try:
        old = g['b'].attest_loaded(root, source)
        assert 'scripts.qd_ed_n34_worker' not in old
        if fault == 'spec_name': g['__spec__'].name = 'scripts.wrong'
        if fault == 'missing_spec': g['__spec__'] = None
        if fault == 'origin': g['__spec__'].origin = str(root / 'scripts/qd_ed_n34_bridge.py')
        if fault == 'file': g['__file__'] = str(root / 'scripts/qd_ed_n34_bridge.py')
        if fault == 'hash':
            next(r for r in source['files'] if r['path'] == 'scripts/qd_ed_n34_worker.py')['sha256'] = '0' * 64
        if fault == 'missing':
            source['files'] = [r for r in source['files'] if r['path'] != 'scripts/qd_ed_n34_worker.py']
        if fault == 'tamper':
            with (root / 'scripts/qd_ed_n34_worker.py').open('a') as f: f.write('\n# post-freeze tamper\n')
        before = g['attest_worker_loaded'](root, source)
        runpy.run_path(os.environ['TEST_MAIN'], run_name='__main__')
        after = g['attest_worker_loaded'](root, source)
        assert before == after
        assert 'scripts.qd_ed_n34_worker' not in sys.modules
        result = dict(before=before, after=after, old=old)
    except ValueError as exc:
        result = dict(error=str(exc))
    Path(os.environ['TEST_RESULT']).write_text(json.dumps(result))
    raise SystemExit(0)
sys.settrace(trace)
