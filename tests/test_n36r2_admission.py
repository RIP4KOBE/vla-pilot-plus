"""Focused CPU-only boundaries; no source adoption, release token or worker launch."""
import copy
import datetime as dt
import json
from pathlib import Path
import pytest
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as release
from scripts import qd_ed_n36r2_admission as gate, qd_ed_n36r2_draft as draft
from scripts import qd_ed_n36_source as source, qd_ed_n36_stop as stop
from scripts import qd_ed_n36_worker as worker
from scripts import qd_ed_n36_accounting as accounting


def plan():
    return {'cohort': c.DRAFT_RECOVERY_COHORT, 'worktree': str(gate.SOURCE),
            'resource_routing': {'source_cwd': str(gate.SOURCE), 'owner_root': str(gate.OWNER),
                                'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID},
            'protocol': {'path':'protocol','sha256':'p'}, 'protocol_review': {'path':'review','sha256':'r'},
            'accounting': {'path':'accounting','sha256':'a'}}


def test_private_owner_and_scientific_cwd_are_distinct():
    p = plan()
    assert gate.owner_root(p) == gate.OWNER
    assert gate.owner_root(p) != Path(p['worktree'])
    for key, value in [('owner_root','/tmp/foreign'), ('source_cwd',str(gate.OWNER)),
                       ('physical_gpu',6), ('gpu_uuid','another GPU')]:
        bad = copy.deepcopy(p); bad['resource_routing'][key] = value
        with pytest.raises(ValueError): gate.owner_root(bad)


def test_adjacent_empty_and_symlink_import_search_rejected(tmp_path):
    root = tmp_path/'source'; root.mkdir()
    prefix = tmp_path/'python'; prefix.mkdir()
    adjacent = tmp_path/'other'; adjacent.mkdir()
    source.validate_search_path(root, [str(root),str(prefix/'lib')], prefix)
    link = root/'escape'; link.symlink_to(adjacent, target_is_directory=True)
    for entry in ['', str(adjacent), str(link)]:
        with pytest.raises(ValueError): source.validate_search_path(root,[entry],prefix)


def resource():
    p = plan()
    return {**c.operational_binding(p), 'resource_id': gate.PREPARATION_ID,
            'kind':gate.KIND, 'event':'reserved', 'timeout_seconds':20,
            'cleanup_seconds':40, 'reserved_gpu_seconds':60}


def test_resource_namespace_and_finite_ceiling():
    p = plan(); good = resource()
    assert gate.resource_events(p,[good]) == [good]
    for key,value in [('resource_id','n36_healthcheck_n36r1_preparation_001203'),
                      ('kind','n36r1_resource_preparation_v1'),('timeout_seconds',21),
                      ('timeout_seconds',True),('cleanup_seconds',39),('reserved_gpu_seconds',59),
                      ('accounting',{'path':'foreign','sha256':'x'})]:
        bad={**good,key:value}
        with pytest.raises(ValueError): gate.resource_events(p,[bad])
    # A same-id terminal cannot hide under a foreign cohort.
    with pytest.raises(ValueError): gate.resource_events(p,[good,{**good,'cohort':'foreign'}])


def test_both_invalid_charges_are_independently_required():
    events=[]
    for retained in draft.PRESERVED:
        events += [{'event':event,'attempt_id':retained['attempt_id'],
                    'episode_key':retained['attempt_id'],'gpu_process_wall_seconds':retained['gpu_seconds']}
                   for event in ('reserved','dispatched','aborted')]
    gate.preserve_charges(events)
    for i in (2,5):
        bad=copy.deepcopy(events);bad[i]['gpu_process_wall_seconds']=0
        with pytest.raises(ValueError): gate.preserve_charges(bad)
    with pytest.raises(ValueError): gate.preserve_charges(events[3:])


def test_missing_real_release_fails_before_pure_allowance_can_admit():
    with pytest.raises((KeyError,TypeError,ValueError)):
        c.pre_dispatch(c.expected_rows(cohort=c.DRAFT_RECOVERY_COHORT)[0], {},
            now=dt.datetime.now(dt.timezone.utc), stop_path=stop.STOP_PATHS[0],
            cohort=c.DRAFT_RECOVERY_COHORT)
    with pytest.raises((KeyError,ValueError)):
        release.validate_plan({**plan(),'schema':'n36-release-draft-v1','frozen':False,'release_enabled':False})
    with pytest.raises((KeyError,TypeError,ValueError)):
        gate.independent_review(plan())


def test_health_and_full_episode_reserves_cannot_borrow():
    snap={'gpu_hours_consumed':75.49265038509455,'running':0,'gpu_healthcheck_inflight':0}
    local={'gpu_hours_consumed':0.,'gpu_healthcheck_hours':0.}
    args={'retained_margin_hours':.23357169027962,'protected_hours':36.2408240024308155}
    assert accounting.headroom(snap,local,**args)['reserved_gpu_seconds']==1840
    for bad in [{**snap,'gpu_hours_consumed':221.}, {**snap,'running':1},
                {**snap,'gpu_healthcheck_inflight':1}, {**snap,'gpu_hours_consumed':float('nan')}]:
        with pytest.raises(ValueError): accounting.headroom(bad,local,**args)
    with pytest.raises(ValueError):
        accounting.headroom(snap,{'gpu_hours_consumed':0.5,'gpu_healthcheck_hours':0.5},**args,healthcheck=True,need=60)


def test_stop_aliases_and_exact_full_headroom(monkeypatch,tmp_path):
    aliases=[str(tmp_path/'owner-stop'),str(tmp_path/'data-stop')]
    monkeypatch.setattr(stop,'STOP_PATHS',aliases)
    end=dt.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
    stop.check(now=end-dt.timedelta(seconds=1840),need=1840)
    with pytest.raises(ValueError): stop.check(now=end-dt.timedelta(seconds=1839),need=1840)
    for alias in aliases:
        Path(alias).symlink_to(tmp_path/'absent')
        with pytest.raises(ValueError): stop.check(now=end-dt.timedelta(seconds=1900),need=1840)
        Path(alias).unlink()


def test_runtime_observation_is_create_once_and_hash_bound(tmp_path):
    (tmp_path/'eds_eval').mkdir()
    receipt={key+'_before':{'binding':{'process':{'pid':123,'boot_id':'test','proc_start_ticks':'1'}}}
             for key in ('runtime','execution','loaded','native_build')}
    ref=worker.persist_runtime_observation(tmp_path,'before',receipt)
    assert worker.w.read_ref(ref)==receipt
    assert Path(ref['path']).stat().st_mode & 0o222 == 0
    with pytest.raises(FileExistsError): worker.persist_runtime_observation(tmp_path,'before',receipt)
    Path(ref['path']).chmod(0o644);Path(ref['path']).write_text('{}')
    with pytest.raises(ValueError): worker.w.read_ref(ref)


def test_independent_review_cannot_reuse_old_source(monkeypatch):
    p=plan()
    for key in ('source','scientific_source','runtime','runtime_closure','native_build','controller_semantics'):
        p[key]={'path':key,'sha256':'new-bound-source'}
    p['b5_review']={'path':'review','sha256':'review-ref'}
    review={'schema':'n36r2-independent-b5-review-v1',
        'decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',
        **{key:p[key] for key in ('source','scientific_source','protocol','accounting','runtime',
            'runtime_closure','native_build','controller_semantics','resource_routing')},
        'worker_receipts_are_future':True,'release_enabled':False}
    monkeypatch.setattr(gate.w,'read_ref',lambda ref:review)
    gate.independent_review(p)
    for key in ('source','runtime','accounting','resource_routing'):
        old=review[key];review[key]={'stale':True}
        with pytest.raises(ValueError): gate.independent_review(p)
        review[key]=old


def test_disabled_context_cannot_enter_worker(tmp_path):
    context={'schema':'n36-worker-context-v1','plan':None,'release':None,'expected_manifest':None,
             'episode_key':'n36r2_dev_t00_c0_001250','attempt_id':'n36r2_dev_t00_c0_001250',
             'main_argv':[],'worker_contract':c.WORKER_CONTRACT}
    path=tmp_path/'disabled-context.json';path.write_text(json.dumps(context))
    with pytest.raises((TypeError,KeyError,ValueError)):
        worker.validate_context(c.ref(path),admission=True)


def test_real_bootstrap_excludes_inherited_adjacent_checkout(tmp_path):
    import os
    import subprocess
    import sys
    adjacent=tmp_path/'foreign-checkout';adjacent.mkdir()
    command=source.command(sys.executable,c.ROOT,'site')
    result=subprocess.run(command,env={**os.environ,'PYTHONPATH':str(adjacent)},
                          text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert result.returncode==0, result.stderr
    assert str(adjacent) not in result.stdout
    assert str(c.ROOT/'third_party/lerobot/src') in result.stdout
