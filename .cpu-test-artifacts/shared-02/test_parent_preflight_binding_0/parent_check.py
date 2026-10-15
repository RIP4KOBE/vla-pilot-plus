
import copy
import json
import sys
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n36_source as source
from scripts import qd_ed_n36_runner as runner
from scripts import qd_ed_n36_healthcheck as health

root = Path(__file__).parent
entrypoint = sys.argv[1]
state = source.active()
# Snapshot only this synthetic source tree and this CPU interpreter's imports.
frozen = {'files': [{'path': str(p.relative_to(root)), 'sha256': source.sha(p)}
                    for p in root.rglob('*.py')]}
runtime = {'modules': {}, 'generated_modules': {}, 'interpreter': source.interpreter_identity()}
for name, path in list(state.compiled) + [(n, p) for n, (p, h) in state.startup_sources.items()]:
    if not Path(path).resolve().is_relative_to(root):
        runtime['modules'][name] = {'path': str(Path(path).resolve()), 'sha256': source.sha(path)}
for name in ['os.path', 'posixpath'] + [n for pair in source.IMPORTLIB_FROZEN_PAIRS for n in pair]:
    path = str(Path(sys.modules[name].__file__).resolve())
    runtime['modules'][name] = {'path': path, 'sha256': source.sha(path)}

def write(name, value):
    path = root / name
    path.write_text(json.dumps(value, sort_keys=True))
    return {'path': str(path), 'sha256': source.sha(path)}

runtime_ref = write('synthetic-runtime.json', runtime)
plan = {'worktree': str(root), 'source': frozen, 'runtime_closure': runtime_ref}
plan_ref = write('synthetic-plan.json', plan)
release_ref = write('synthetic-release.json', {'plan': plan_ref, 'runtime_closure': runtime_ref})
events = []
reject_validation = False

def validate(p, r):
    events.append('validate')
    assert p == plan_ref and r == release_ref
    assert w.read_ref(p) == plan
    assert w.read_ref(r) == {'plan': p, 'runtime_closure': runtime_ref}
    if reject_validation:
        raise ValueError('synthetic release rejected')
    return plan, {}, {}

# Release governance is stubbed; hash reads and all source/binding checks are real.
runner.release.validate_release = validate
runner.release.validate_health_release = validate
runner.owner_root = lambda p: root
health.c.cohort = lambda p: health.c.DRAFT_N36R3_COHORT

class BoundaryReached(Exception):
    pass

def boundary(*args, **kwargs):
    events.append('boundary')
    raise BoundaryReached()

def forbidden(*args, **kwargs):
    raise AssertionError('CPU preflight crossed forbidden operational boundary')

health.accounting.reserve_healthcheck = boundary
runner.r.locked = boundary
runner.device_check = forbidden
runner.r.verify_provider = forbidden
runner.r.runtime_gpu = forbidden
runner.r.append_event_locked = forbidden
runner.r.append_healthcheck_event = forbidden
runner.subprocess.Popen = forbidden

attest = source.attest
fault = None

def checked_attest(source_root, source_record, closure, *, binding):
    events.append('attest')
    assert events == ['validate', 'attest']
    expected = {'context': release_ref, 'runtime_closure': runtime_ref,
                'process': w.process_identity(), 'phase': 'runtime_before'}
    assert binding == expected
    assert source_root == root and source_record == frozen and closure == runtime
    candidate = copy.deepcopy(binding)
    if fault == 'unbound':
        candidate = None
    elif fault in ('pid', 'proc_start_ticks', 'boot_id'):
        candidate['process'][fault] = (candidate['process'][fault] + 1 if fault == 'pid'
                                       else candidate['process'][fault] + '0')
    receipt = attest(source_root, source_record, closure, binding=candidate)
    observed = {'binding': copy.deepcopy(binding), 'modules': copy.deepcopy(closure['modules'])}
    # Exercise the retained, exact-shape binding consumer as well as live checks.
    assert source.verify_importlib_aliases(receipt, closure, observed, expected) == {
        'os.path', 'importlib._bootstrap', 'importlib._bootstrap_external'}
    for field in ('context', 'runtime_closure', 'phase'):
        changed = copy.deepcopy(expected)
        if field == 'phase':
            changed[field] = 'runtime_after'
        else:
            changed[field]['sha256'] = '0' * 64
        try:
            source.verify_importlib_aliases(receipt, closure, observed, changed)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted cross-bound ' + field)
    return receipt

source.attest = checked_attest

def invoke():
    if entrypoint == 'healthcheck':
        return health.run_healthcheck(plan_ref, release_ref, 'synthetic-no-admission')
    return runner.execute_one(plan_ref, release_ref)

reject_validation = True
try:
    invoke()
except ValueError as exc:
    assert str(exc) == 'synthetic release rejected'
else:
    raise AssertionError('accepted rejected release')
assert events == ['validate']
reject_validation = False

for fault in ('unbound', 'pid', 'proc_start_ticks', 'boot_id', None):
    events.clear()
    try:
        invoke()
    except ValueError as exc:
        assert fault is not None
        assert ('binding required' if fault == 'unbound' else 'live process differs') in str(exc)
        assert events == ['validate', 'attest']
    except BoundaryReached:
        assert fault is None and events == ['validate', 'attest', 'boundary']
    else:
        raise AssertionError('caller escaped CPU boundary')
print('parent binding verified: ' + entrypoint)
