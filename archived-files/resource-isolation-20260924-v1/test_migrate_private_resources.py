"""CPU synthetic fixtures only. Never call migrate() or touch actual worktrees."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

D=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('private_resource_migration',D/'migrate-private-resources.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def line(event):
    return ('  '+json.dumps(event,sort_keys=False)+' \n').encode()


def group(identifier,output,*,seconds=10.,bucket='development',retry_of=None,health=False,dispatch=True):
    key='resource_id' if health else 'attempt_id'
    base={key:identifier,'output_dir':str(output),'retry_of':retry_of,'budget_bucket':bucket}
    rows=[dict(base,event='reserved')]
    if dispatch:rows.append(dict(base,event='dispatched'))
    rows.append(dict(base,event=('completed' if health else 'valid') if dispatch else 'aborted',
        gpu_process_wall_seconds=seconds,outcome_valid=True))
    return rows


def fixture_events(tmp_path):
    artifacts={'W':tmp_path/'WA','X':tmp_path/'XA'}
    x=group('x',artifacts['X']/'attempts/x',seconds=17.)
    w=group('w',artifacts['W']/'attempts/w',seconds=.125,bucket='recovery',retry_of='x')
    p=group('pred',artifacts['W']/'attempts/pred',seconds=0.,dispatch=False)
    # Noncontiguous groups still retain their original global line order.
    rows=[x[0],w[0],x[1],w[1],x[2],w[2],*p]
    return artifacts,rows,b''.join(map(line,rows))


def test_partition_bytes_order_group_cost_and_cross_owner_chain(tmp_path):
    artifacts,rows,data=fixture_events(tmp_path)
    parts,groups,cross=m.partition(data,artifacts=artifacts)
    assert parts['W']==b''.join(line(x) for x in rows if x['attempt_id']!='x')
    assert parts['X']==b''.join(line(x) for x in rows if x['attempt_id']=='x')
    assert cross[0]['child_id']=='w' and cross[0]['parent_id']=='x'
    assert b'"attempt_id": "x"' not in parts['W']
    proof=m.conservation(data,groups,parts)
    assert proof['original_dispatched']==2 and proof['original_seconds_decimal']=='17.125'
    assert proof['partitions']['W']['seconds_decimal']=='0.125'
    stats=m.snapshot(parts['W'],b'')
    assert stats['dispatched']==1 and stats['reserved_attempts']==2 and stats['aborted']==1


@pytest.mark.parametrize('mutation',['inflight','output_change','missing_parent','negative_cost','duplicate','unknown_owner','blank','truncated'])
def test_partition_rejects_ambiguous_unfinished_or_corrupt_input(tmp_path,mutation):
    artifacts,rows,data=fixture_events(tmp_path)
    if mutation=='inflight': rows=rows[:-1]
    elif mutation=='output_change': rows[3]['output_dir']=str(artifacts['X']/'drift')
    elif mutation=='missing_parent':
        for row in rows:
            if row['attempt_id']=='w':row['retry_of']='not-recorded'
    elif mutation=='negative_cost':rows[4]['gpu_process_wall_seconds']=-1
    elif mutation=='duplicate':rows.insert(1,copy.deepcopy(rows[0]))
    elif mutation=='unknown_owner':
        for row in rows:
            if row['attempt_id']=='w':row['output_dir']=str(tmp_path/'unknown')
    data=b''.join(map(line,rows))
    if mutation=='blank':data+=b'\n'
    if mutation=='truncated':data=data[:-1]
    with pytest.raises(RuntimeError):m.partition(data,artifacts=artifacts)


def test_health_counts_hours_not_episode_attempts(tmp_path):
    artifacts={'W':tmp_path/'WA','X':tmp_path/'XA'}
    data=b''.join(map(line,group('health',artifacts['W']/'probe',health=True,seconds=36.)))
    parts,groups,_=m.partition(data,health=True,artifacts=artifacts)
    proof=m.conservation(data,groups,parts);stats=m.snapshot(b'',parts['W'])
    assert proof['original_seconds_decimal']=='36.0' and stats['dispatched']==0
    assert stats['gpu_hours_consumed']==.01 and stats['gpu_hours_by_bucket']['recovery']==.01


def state(owner):
    auth={'path':str(m.D/'authorization.json'),'sha256':m.AUTH_SHA}
    return {'run_name':m.W.name,'artifacts':str(m.A if owner=='W' else m.AX),
      'max_concurrent_gpu_workers':9,'budget':{'max_episode_attempts':250,'max_gpu_hours':48,
        'reserved':copy.deepcopy(m.CAPS['X']),'gpu_hour_reservations':{'validation':14.,'formal':10.},
        'n1w_authorization':{'path':'frozen-authority.json','sha256':m.N1W_SHA},'attempt_reallocation':{'old_shared':True}},
      'resource_isolation':{'status':'DRAINING_FOR_USER_AUTHORIZED_ISOLATION','authorization':auth},
      'execution_migration':{'same_study_budget':True,'shared_journal_root':'/historical/shared'},
      'external_resource_hold':{'active':True,'do_not_auto_resume':True},
      'n1u_priority_authorization':{'active':True},'authorized_gpu_selection':{'candidate_indices':[7]}}


def test_private_state_exact_caps_workers_authority_and_history_preserved():
    stats=m.snapshot(b'',b'');states={o:state(o) for o in ('W','X')};original=copy.deepcopy(states)
    outputs={o:m.new_state(states[o],o,stats,auth_ref=states[o]['resource_isolation']['authorization'],
        worktree=m.W if o=='W' else m.X,archive_ref={'path':'archive','sha256':'hash'}) for o in states}
    assert states==original
    for owner,s in outputs.items():
        assert s['max_concurrent_gpu_workers']==1 and 'max_parallel_gpu_workers' not in s
        assert s['budget']['reserved']==m.CAPS[owner]
        assert s['budget']['resource_isolation_authorization']==original[owner]['resource_isolation']['authorization']
        assert s['resource_isolation']['status']=='MIGRATED_PENDING_VALIDATION'
        assert s['external_resource_hold']['active'] is False
        assert s['n1u_priority_authorization']['active'] is False
        assert s['authorized_gpu_selection']['single_exclusive_worker'] is True
        assert s['authorized_gpu_selection']['rescan_if_unavailable'] is True
    assert 'n1w_authorization' not in outputs['W']['budget']
    assert 'attempt_reallocation' not in outputs['W']['budget']
    assert outputs['X']['budget']['attempt_reallocation']['old_shared'] is True
    assert outputs['X']['budget']['attempt_reallocation']['cross_study_authority'] is False
    assert outputs['X']['budget']['n1w_authorization']==original['X']['budget']['n1w_authorization']
    migration=outputs['X']['execution_migration']
    assert migration['same_study_budget'] is False and 'shared_journal_root' not in migration
    assert migration['historical_shared_migration']['original']==original['X']['execution_migration']


@pytest.mark.parametrize('mutation',['owner','draining','authority','protected','caps'])
def test_state_refuses_wrong_owner_or_authority(mutation):
    s=state('X');auth=copy.deepcopy(s['resource_isolation']['authorization'])
    if mutation=='owner':s['artifacts']=str(m.A)
    if mutation=='draining':s['resource_isolation']['status']='ACTIVE'
    if mutation=='authority':s['budget']['n1w_authorization']['sha256']='wrong'
    if mutation=='protected':s['budget']['gpu_hour_reservations']['formal']=9.
    if mutation=='caps':s['budget']['reserved']['development']=126
    with pytest.raises(RuntimeError):m.new_state(s,'X',m.snapshot(b'',b''),auth_ref=auth,worktree=m.X,archive_ref={})


def test_atomic_new_preserves_existing_and_private_permissions(tmp_path):
    path=tmp_path/'new.json';m.durable_new(path,b'exact\n')
    assert path.read_bytes()==b'exact\n' and path.stat().st_mode&0o777==0o600
    with pytest.raises(RuntimeError):m.durable_new(path,b'changed')
    assert path.read_bytes()==b'exact\n'


def test_actual_cpu_helper_lease_and_forged_owner_rejected(tmp_path):
    root=tmp_path/'W';(root/'data').mkdir(parents=True);lock=root/'data/qd-ed-runner.lock';lock.touch()
    helper=tmp_path/'drain-and-hold-v2.py'
    helper.write_text("import fcntl,sys\np=open(sys.argv[1],'rb')\nfcntl.flock(p,fcntl.LOCK_EX)\nprint('HELD',flush=True)\nsys.stdin.readline()\n")
    process=subprocess.Popen([sys.executable,str(helper),str(lock)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert process.stdout.readline().strip()=='HELD'
        drain={'authorization_sha256':m.AUTH_SHA,'inflight_attempts':[],'inflight_healthchecks':[],
            'active_episode_interrupted':False,'latest_terminal_artifact_matches_journal':True,'supervisor_pid':99999999}
        (tmp_path/'drain-result.json').write_bytes(m.json_bytes(drain))
        lease={'schema':'two-study-migration-lease-v1','status':'OLD_SHARED_RUNNER_LEASE_HELD_FOR_MIGRATION',
            'pid':process.pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'lock_path':str(lock),'lock_inode':lock.stat().st_ino,'drain_result_sha256':m.digest(tmp_path/'drain-result.json')}
        (tmp_path/'migration-lease.json').write_bytes(m.json_bytes(lease))
        checked=m.verify_lease(tmp_path,root);assert checked['helper']['pid']==process.pid
        with pytest.raises(RuntimeError,match='PID reused'):
            m.verify_lease(tmp_path,root,expected_process={'pid':process.pid,'proc_start_ticks':'wrong'})
        lease['pid']=os.getpid();(tmp_path/'migration-lease.json').write_bytes(m.json_bytes(lease))
        with pytest.raises(RuntimeError):m.verify_lease(tmp_path,root)
    finally:
        process.communicate('\n',timeout=5)
    assert process.returncode==0
