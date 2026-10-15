"""Explicit, separately charged N35 CUDA/EGL check after a root release.

Never called by the episode controller. CPU tests replace the child and device
calls. This module creates neither a runtime release nor runtime readiness.
"""
import datetime as dt
import os
from pathlib import Path
import subprocess
import time

from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n35_accounting as accounting, qd_ed_n35_contract as c
from scripts import qd_ed_n35_release as release, qd_ed_n35_runner as adapter
from scripts import qd_ed_gpu_probe as probe


def wait_probe(process, started, identity, timeout):
    deadline = started + timeout
    def monitor(child, remaining):
        def bounded_run(command, **kwargs):
            left = deadline - time.monotonic()
            if left <= 0:
                raise subprocess.TimeoutExpired('owned healthcheck', timeout)
            kwargs['timeout'] = min(kwargs.get('timeout', left), left)
            return subprocess.run(command, **kwargs)
        r.check_exclusive_gpu(child, run=bounded_run, physical_gpu=7)
    try:
        return r.wait_exclusively(process, max(0., deadline-time.monotonic()),
                                  physical_gpu=7, monitor=monitor)
    except (KeyboardInterrupt, SystemExit):
        raise  # STOP/cancellation never signals a live admitted child.
    except BaseException:
        if process.poll() is None:
            try:
                process.wait(timeout=max(0., deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                adapter.cleanup_owned(process, identity)
        raise  # Missing exclusivity evidence cannot be repaired by an exit0.


def run_healthcheck(plan_ref, release_ref, resource_id, *, timeout_seconds=120):
    """One bounded probe, no retry, no episode attempt, no readiness mutation."""
    record = accounting.reserve_healthcheck(plan_ref, release_ref, resource_id,
                                            timeout_seconds=timeout_seconds)
    plan, runtime, authority = release.validate_release(plan_ref, release_ref)
    root = Path(plan['worktree'])
    # The durable in-flight resource blocks admissions during lock transfer.
    with r.locked(root/'data/qd-ed-runner.lock', nonblocking=True):
        plan, runtime, authority = release.validate_release(plan_ref, release_ref)
        resources = r.read_events(root/'data/gpu-healthcheck-ledger.jsonl')
        w.require([e for e in resources if e['resource_id']==resource_id]==[record],
                  'healthcheck reservation changed; no replay')
        output = Path(plan['artifact_root'])/'healthchecks'/resource_id
        r.owned(output, plan['artifact_root'])
        w.require(not output.exists() and not output.is_symlink(), 'healthcheck output exists')
        output.mkdir(parents=True)
        end = min(dt.datetime.fromisoformat(x.replace('Z','+00:00')) for x in
                  (c.DEADLINE, authority['coordinator_ends_at'], authority['weekly_window']['ends_at']))
        def before_start():
            stop=Path(plan['stop_path'])
            w.require(not stop.exists() and not stop.is_symlink()
                      and dt.datetime.now(dt.timezone.utc)<end, 'STOP/deadline before healthcheck start')
        process = identity = None
        started = finished = None
        event, result = 'aborted', {}
        base = {**record, 'output_dir':str(output),
                'runtime_manifest_sha256':plan['runtime']['sha256'],
                'source_script_sha256':w.sha(Path(probe.__file__))}
        try:
            before_start()
            adapter.device_check()
            env=r.child_environment(runtime)
            env.update(QD_ED_GPU_PROBE_PARENT_PID=str(os.getpid()), QD_ED_GPU_PROBE_RESOURCE_ID=resource_id)
            command=[str(r.PYTHON),str(Path(probe.__file__).resolve()),'_child',
                     '--manifest',plan['runtime']['path'],'--output',str(output),'--resource-id',resource_id]
            w.atomic_json(output/'command.json',{'argv':command,'release':release_ref})
            before_start()
            r.append_healthcheck_event(root,{**base,'event':'dispatched','time_unix':time.time()})
            with (output/'probe.log').open('w') as log:
                before_start()
                started=time.monotonic()
                process=subprocess.Popen(command,cwd=root,env=env,stdout=log,
                                         stderr=subprocess.STDOUT,start_new_session=True)
                identity=adapter.process_identity(process.pid)
                w.atomic_json(output/'process.json',{**identity,'resource_id':resource_id,'release':release_ref})
                code=wait_probe(process,started,identity,timeout_seconds)
                finished=time.monotonic()
            w.require(code==0,'healthcheck child exit not zero')
            result=r.read_json(output/'probe-evidence.json')
            w.require(result.get('resource_id')==resource_id,'healthcheck evidence identity')
            probe.validate_probe_evidence(result,runtime['gpu_mapping'])
            w.require(w.sha(output/'probe-frame.png')==result['frame_png_sha256'],'healthcheck frame fingerprint')
            w.require(w.sha(plan['runtime']['path'])==plan['runtime']['sha256'],'runtime changed during healthcheck')
            event='completed'
        except BaseException as exc:
            # Never settle an unknown/live handle or kill on STOP/interrupt.
            if process is not None and process.poll() is None:
                raise
            if isinstance(exc,(KeyboardInterrupt,SystemExit)):
                raise
            result={'reason':str(exc) if isinstance(exc,(ValueError,r.GateError)) else type(exc).__name__}
        elapsed=0. if started is None else (finished or time.monotonic())-started
        w.require(elapsed<=record['reserved_gpu_seconds'],'healthcheck exceeded reservation; root reconciliation required')
        terminal={**result,**base,'event':event,'time_unix':time.time(),
                  'gpu_process_wall_seconds':elapsed,
                  'measurement':'exclusive GPU7 child wall time including owned timeout cleanup'}
        r.append_healthcheck_event(root,terminal)
        w.atomic_json(output/'healthcheck-result.json',terminal)
        return {'status':'VALID' if event=='completed' else 'INVALID_STOP','terminal':terminal}
