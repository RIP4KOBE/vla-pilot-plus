"""Canonical authority and synthetic launch races: no device or owner writes."""
import datetime as dt
import errno
from pathlib import Path
import pytest
from scripts import qd_ed_n36_stop as stop, qd_ed_n36_contract as c
from scripts import qd_ed_n36_runner as adapter, qd_ed_final_runner as r
from test_n36_runner import lifecycle, synthetic_accounting_margin

pytestmark = pytest.mark.usefixtures('synthetic_accounting_margin')

NOW = dt.datetime(2026, 10, 10, tzinfo=dt.timezone.utc)


def test_lexical_authority_is_independent_of_checkout_resolution(monkeypatch):
    assert stop.OWNER_STOP.startswith('/home/hynx/lizhuo/')
    assert stop.DATA_STOP.startswith('/mnt/data/shared2/hynx/')
    assert stop.OWNER_STOP != stop.DATA_STOP
    # Restoring literal authority counters the imported synthetic fixture.
    monkeypatch.setattr(stop, 'STOP_PATHS', (stop.OWNER_STOP, stop.DATA_STOP))
    seen = []
    def absent(path):
        seen.append(path)
        raise FileNotFoundError(errno.ENOENT, 'fixture absence', path)
    monkeypatch.setattr(stop.os, 'lstat', absent)
    stop.check(now=NOW)
    assert seen == [stop.OWNER_STOP, stop.DATA_STOP]


@pytest.mark.parametrize('location', [0, 1, 'both'])
@pytest.mark.parametrize('kind', ['file', 'directory', 'dangling', 'permission', 'io', 'notdir'])
def test_each_canonical_entry_fails_closed(tmp_path, monkeypatch, location, kind):
    # Actual filesystem entry semantics, redirected from exact lexical paths.
    monkeypatch.setattr(stop, 'STOP_PATHS', (stop.OWNER_STOP, stop.DATA_STOP))
    actual = tmp_path/'entry'
    if kind == 'file': actual.touch()
    elif kind == 'directory': actual.mkdir()
    elif kind == 'dangling': actual.symlink_to(tmp_path/'missing')
    original = stop.os.lstat
    def lstat(path):
        if path not in stop.STOP_PATHS: return original(path)
        if location == 'both' or path == stop.STOP_PATHS[location]:
            if kind in ('permission', 'io', 'notdir'):
                raise OSError({'permission':errno.EACCES, 'io':errno.EIO, 'notdir':errno.ENOTDIR}[kind], kind)
            return original(actual)
        raise FileNotFoundError(errno.ENOENT, 'absent', path)
    monkeypatch.setattr(stop.os, 'lstat', lstat)
    with pytest.raises(ValueError, match='STOP'): stop.check(now=NOW)


@pytest.mark.parametrize('fault', ['owner', 'path', 'deadline', 'source'])
def test_plan_cannot_replace_canonical_authority(fault):
    plan = {'worktree': str(c.ROOT), 'stop_path': c.stop_path(), 'stop_authority': stop.binding()}
    if fault == 'owner': plan['stop_authority']['paths'][0] = '/arbitrary/STOP'
    elif fault == 'path': plan['stop_path'] = '/arbitrary/STOP'
    elif fault == 'deadline': plan['stop_authority']['deadline'] = '2099-01-01T00:00:00Z'
    else: plan['stop_authority']['owner_source'] = '0'*40
    with pytest.raises(ValueError, match='STOP'): c.validate_stop_binding(plan)


@pytest.mark.parametrize('seconds,need', [(0, 0), (1839,1840), (1939,1940)])
def test_deadline_full_attempt_and_health_headroom(seconds, need):
    end = dt.datetime.fromisoformat(stop.DEADLINE.replace('Z','+00:00'))
    with pytest.raises(ValueError, match='deadline'):
        stop.check(now=end-dt.timedelta(seconds=seconds), need=need)


@pytest.mark.parametrize('location', [0,1])
@pytest.mark.parametrize('boundary', ['reserved','dispatched'])
def test_independent_stop_launch_races(lifecycle, monkeypatch, location, boundary):
    root, plan, plan_ref, release_ref = lifecycle
    append = r.append_event_locked
    def race(root, event):
        append(root,event)
        if event['event'] == boundary: Path(stop.STOP_PATHS[location]).symlink_to(root/'absent')
    monkeypatch.setattr(r, 'append_event_locked', race)
    monkeypatch.setattr(adapter.subprocess, 'Popen', lambda *a, **kw: pytest.fail('worker launched after STOP'))
    with pytest.raises(ValueError, match='STOP'): adapter.execute_one(plan_ref, release_ref)
    events = r.read_events(root/'data/attempt-ledger.jsonl')
    assert [e['event'] for e in events] == (['reserved'] if boundary == 'reserved' else ['reserved','dispatched'])
    assert events[0]['reserved_gpu_seconds'] == 1840
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'LIVE_OR_UNSETTLED'


@pytest.mark.parametrize('location', [0,1])
@pytest.mark.parametrize('boundary', ['reserved','dispatched'])
def test_independent_healthcheck_launch_races(lifecycle, monkeypatch, location, boundary):
    from scripts import qd_ed_n36_healthcheck as health, qd_ed_n36_accounting as accounting
    root, plan, plan_ref, release_ref = lifecycle
    if boundary == 'reserved':
        reserve = accounting.reserve_healthcheck
        def race(*args, **kw):
            result = reserve(*args, **kw)
            Path(stop.STOP_PATHS[location]).touch()
            return result
        monkeypatch.setattr(accounting,'reserve_healthcheck',race)
    else:
        append = r.append_healthcheck_event
        def race(root,event):
            append(root,event)
            if event['event']=='dispatched': Path(stop.STOP_PATHS[location]).touch()
        monkeypatch.setattr(r,'append_healthcheck_event',race)
    monkeypatch.setattr(health.subprocess,'Popen',lambda *a, **kw:pytest.fail('STOP must prohibit probe launch'))
    result = health.run_healthcheck(plan_ref,release_ref,'n36_healthcheck_preparation')
    assert result['status']=='INVALID_STOP'
    assert result['terminal']['gpu_process_wall_seconds']==0
    assert 'STOP' in result['terminal']['reason']


@pytest.mark.parametrize('location',[0,1])
def test_worker_context_checks_entry_but_allows_settlement(lifecycle,monkeypatch,location):
    from scripts import qd_ed_n36_worker as worker, qd_ed_n36_release as release
    root,plan,plan_ref,release_ref=lifecycle
    context=worker.context_for(plan_ref,plan['episodes'][0],release_ref)
    manifests={key:worker.w.read_ref(ref) for key,ref in plan['expected_manifests'].items()}
    authority=worker.w.read_ref(plan['authority'])
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU_UUID}}
    monkeypatch.setattr(release,'_verify_release_transaction',lambda *a:(plan,runtime,authority,manifests))
    ref={'path':str(root/'context.json'),'sha256':'synthetic'}
    read=worker.w.read_ref
    monkeypatch.setattr(worker.w,'read_ref',lambda value:context if value==ref else read(value))
    worker._validate_context(ref,admission=True)
    Path(stop.STOP_PATHS[location]).touch()
    with pytest.raises(ValueError,match='STOP'):worker._validate_context(ref,admission=True)
    assert worker._validate_context(ref)[0]==context


@pytest.mark.parametrize('location',[0,1])
def test_stop_after_worker_entry_prevents_main_and_retains_receipt(tmp_path,monkeypatch,location):
    import ast
    from contextlib import nullcontext
    import json
    import os
    import sys
    import time
    from types import SimpleNamespace
    from scripts import qd_ed_n23_worker as w
    path=c.ROOT/'scripts/qd_ed_n36_worker.py'
    names={'_run_in_process', 'persist_runtime_observation'}
    functions=[n for n in ast.parse(path.read_text()).body
               if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in functions} == names
    # Explicit local containment, independent of the imported accounting fixture.
    paths=tuple(str(tmp_path/name/'STOP') for name in ('owner', 'autonomy_20261004'))
    for entry in paths: Path(entry).parent.mkdir(parents=True,exist_ok=True)
    monkeypatch.setattr(stop,'STOP_PATHS',paths)
    root=tmp_path/'study_worktree'; root.mkdir()
    output=root/'output'; (output/'eds_eval').mkdir(parents=True)
    plan={'schema':'n36-released-plan-v1','worktree':str(root),'stop_path':c.stop_path(root),'stop_authority':stop.binding(),
          'source':{},'scientific_source':{},'runtime_closure':{},'controller_semantics':{},'runtime':{},'native_build':{}}
    authority={'coordinator_ends_at':c.DEADLINE,'weekly_window':{'ends_at':c.DEADLINE}}
    context={'plan':{},'expected_manifest':{},'attempt_id':'cpu-fixture','main_argv':[str(root/'main.py')]}
    calls=[]
    def validate(_, *, admission=False):
        calls.append(admission)
        if admission:c.launch_guard(plan,authority)
        return context,plan,{}, {},{'output_dir':str(output)}
    def attest(*args,**kw):
        Path(stop.STOP_PATHS[location]).touch()
        return {}
    namespace=dict(Path=Path,c=c,sys=SimpleNamespace(argv=[]),os=os,time=time,validate_context=validate,
        source_execution=SimpleNamespace(active=lambda:None,bind_dino=lambda _:None,attest=lambda *a,**kw:{},
                                         run_main=lambda *a:pytest.fail('STOP must prohibit Main')),
        verify_dispatch_record=lambda *a:None,
        w=SimpleNamespace(process_identity=lambda:{},require=w.require,atomic_json=w.atomic_json,read_ref=lambda _:{}),
        closure=SimpleNamespace(attest_runtime_receipt=attest,RuntimeOriginError=type('OriginError',(ValueError,),{})),
        controller=SimpleNamespace(verify_semantics=lambda *a:{},observe_instances=lambda _:nullcontext([])),
        native_build=SimpleNamespace(attest=lambda _:{}),attest_worker_loaded=lambda *a:{},runtime_receipt_binding=lambda *a:{})
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(path),'exec'),namespace)
    assert namespace['_run_in_process']({})==2
    receipt=json.loads((output/'eds_eval/n36-worker-receipt.json').read_text())
    observation=output/'eds_eval/n36-runtime-before.json'
    assert receipt['observation_before']==c.ref(observation)
    assert json.loads(observation.read_text())=={
        'runtime_before':{},'execution_before':{},'loaded_before':{},'native_build_before':{}}
    assert observation.stat().st_mode & 0o777 == 0o444
    assert receipt['error_type']=='ValueError'
    assert Path(paths[location]).is_file()
    assert not Path(paths[1-location]).exists()
    assert calls==[True,True]
    assert receipt['accepted'] is False and receipt['classification']=='INVALID'
    assert receipt['main_exit_code'] is None and 'STOP' in receipt['error']


def test_exact_authority_accepts_supported_session_layout(monkeypatch):
    monkeypatch.setattr(stop,'STOP_PATHS',(stop.OWNER_STOP,stop.DATA_STOP))
    plan={'worktree':str(c.ROOT),'stop_path':c.stop_path(),'stop_authority':stop.binding()}
    c.validate_stop_binding(plan)
    plan['worktree']='/unrelated/variants/x/implementation_worktree'
    plan['stop_path']=c.stop_path(plan['worktree'])
    with pytest.raises(ValueError,match='layout'):c.validate_stop_binding(plan)


def test_deadline_does_not_shrink_full_attempt_requirement():
    end=dt.datetime.fromisoformat(stop.DEADLINE.replace('Z','+00:00'))
    stop.check(now=end-dt.timedelta(seconds=1840),need=1840)
    with pytest.raises(ValueError,match='deadline'):
        stop.check(now=end-dt.timedelta(seconds=1839.99),ends_at='2099-01-01T00:00:00Z',need=1840)
