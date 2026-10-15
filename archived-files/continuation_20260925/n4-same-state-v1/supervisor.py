#!/usr/bin/env python3
"""Run one frozen diagnostic on owned GPU3 and account for every dispatch."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

D = Path(__file__).resolve().parent
W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
spec = importlib.util.spec_from_file_location('qd_ed_final_runner', W / 'scripts/qd_ed_final_runner.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

def preflight(plan):
    assert plan['schema'] == 'n4-same-state-diagnostic-plan-v1'
    assert plan['physical_gpu'] == 3 and plan['egl_device_index'] == 0
    assert plan['gpu_uuid'] == 'GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315'
    assert plan['timeout_seconds'] == 1800 and plan['cleanup_seconds'] == 40
    assert plan['max_diagnostic_transitions'] == 32 and plan['max_settling_steps'] == 40
    assert not plan['validation_authorized'] and not plan['formal_authorized']
    assert plan['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert r.digest(__file__) == plan['supervisor_sha256']
    for key, hashkey in (('source_config','source_config_sha256'),('source_plan','source_plan_sha256'),
                         ('runtime_manifest','runtime_manifest_sha256'),('protocol','protocol_sha256')):
        assert r.digest(plan[key]) == plan[hashkey], key
    assert r.digest(D/'child.py') == plan['child_sha256']
    r.verify_files(plan['critical_code'])
    r.verify_files(plan['task_input_files'])
    assert r.digest(plan['checkpoint']['path']) == plan['checkpoint']['sha256']
    for item in plan['encoder_files']:
        path = Path(item['path'])
        assert path.is_file() and path.stat().st_size == item['size_bytes']
        assert str(path.resolve()) == item['realpath']
    runtime = r.read_json(plan['runtime_manifest'])
    assert runtime['gpu_mapping']['uuid'] == plan['gpu_uuid']
    assert runtime['gpu_mapping']['physical_gpu'] == 3
    assert runtime['gpu_mapping']['egl_device_index'] == 0
    state = r.read_state(W/'research-state.yaml')
    assert state['external_resource_hold']['active'] is False
    row = {'split':'dev','iteration':'N4_SAME_STATE_DIAGNOSTIC_20260925',
           'profile':'N4_DIAGNOSTIC','task_id':9,'env_seed':plan['env_seed'],
           'policy_seed':plan['policy_seed'],'init_index':0,
           'budget_bucket':'development','timeout_seconds':1800}
    events = r.read_events(W/'data/attempt-ledger.jsonl')
    r.check_retry(events,row)
    timeout = r.check_budget(state,events,row,
            r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'),
            r.read_events(W/'data/gpu-hour-reservation-ledger.jsonl'),physical_gpu=3)
    assert timeout == 1800
    admission = r.gpu_admission(physical_gpu=3,expected_uuid=plan['gpu_uuid'])
    env = r.child_environment(runtime)
    r.verify_provider(runtime,env,root=W)
    assert env['CUDA_VISIBLE_DEVICES']=='3' and env['MUJOCO_EGL_DEVICE_ID']=='0'
    return row,runtime,env,admission,timeout

def main():
    path = D/'plan.frozen.json'
    plan = r.read_json(path)
    with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
        row,runtime,env,admission,timeout=preflight(plan)
        output=Path(plan['output_dir'])
        assert not output.exists()
        assert not (D/'attempt-result.json').exists()
        base={'attempt_id':plan['attempt_id'],'identity':r.episode_identity(row),
              'episode_key':'n4_same_state_t09_20260925','budget_bucket':'development',
              'diagnostic_only':True,'official_task_success_rate':None,
              'plan_sha256':r.digest(path),'protocol_sha256':plan['protocol_sha256'],
              'source_config_sha256':plan['source_config_sha256'],
              'runtime_manifest_sha256':plan['runtime_manifest_sha256'],
              'init_row_sha256':plan['init_row_sha256'],
              'source_commit':plan['source_commit'],'output_dir':str(output),
              'physical_gpu':3,'gpu_uuid':plan['gpu_uuid'],
              'stage_backend':'codex_cli','stage_model':'gpt-6-astra',
              'stage_condition':'N4_E1_t180'}
        r.append_event(W,{**base,'event':'reserved','time_unix':time.time(),'admission':admission})
        print(json.dumps({'event':'reserved','attempt_id':plan['attempt_id']}),flush=True)
        process=None; dispatched=False; started=time.monotonic()
        outcome={'outcome_valid':False,'retryable_infrastructure':False}
        final='aborted'
        try:
            r.gpu_admission(physical_gpu=3,expected_uuid=plan['gpu_uuid'])
            assert r.runtime_gpu(runtime,r.read_state(W/'research-state.yaml'))==3
            r.append_event(W,{**base,'event':'dispatched','time_unix':time.time(),
                              'timeout_seconds':timeout})
            dispatched=True;started=time.monotonic()
            print(json.dumps({'event':'dispatched','attempt_id':plan['attempt_id']}),flush=True)
            command=[str(r.PYTHON),str(D/'child.py'),str(path)]
            with (D/'child.log').open('x') as log:
                process=subprocess.Popen(command,cwd=W,env=env,stdout=log,
                                         stderr=subprocess.STDOUT,start_new_session=True)
                r.durable_json(D/'process.json',{'pid':process.pid,'attempt_id':plan['attempt_id'],
                    'boot_id':plan['boot_id'],'time_unix':time.time(),
                    'command':command})
                exit_code=r.wait_exclusively(process,timeout,physical_gpu=3)
            assert exit_code==0, f'child exit code {exit_code}'
            result=r.read_json(output/'result.json')
            assert result['schema']=='n4-same-state-diagnostic-result-v1'
            assert result['attempt_id']==plan['attempt_id'] and result['diagnostic_only'] is True
            assert result['official_task_success_rate'] is None
            assert result['status'] in ('NO_SELECTION_CONTRAST','INFEASIBLE_STATE_RESTORE','COMPLETED_CONTRAST')
            resources=result['resources']
            assert 0<=resources['transitions']<=32 and 1<=resources['resets']<=4
            assert resources['settling_steps']<=40
            assert not (output/'results.txt').exists(), 'official SR artifact unexpectedly written'
            compute=r.read_events(output/'eds_eval/episode_compute.jsonl')
            assert len(compute)==1 and compute[0]['episode_seed']==plan['env_seed']
            outcome.update(diagnostic_status=result['status'],resources=resources,
                           diagnostic_result_sha256=r.digest(output/'result.json'),
                           episode_compute_sha256=r.digest(output/'eds_eval/episode_compute.jsonl'))
            final='valid'
        except BaseException as error:
            outcome.update(failure_class=type(error).__name__,reason=str(error)[:700])
            if isinstance(error,(KeyboardInterrupt,SystemExit)):
                raise
        finally:
            r.terminate_owned(process)
            elapsed=time.monotonic()-started if dispatched else 0.0
            terminal={**base,**outcome,'event':final,'time_unix':time.time(),
                      'gpu_process_wall_seconds':elapsed,
                      'gpu_time_measurement':'exclusive GPU3 process wall-time upper bound including startup/cleanup'}
            r.append_event(W,terminal)
            r.durable_json(D/'attempt-result.json',terminal)
            print(json.dumps({'event':final,'diagnostic_status':outcome.get('diagnostic_status'),
                              'gpu_process_wall_seconds':elapsed,'failure_class':outcome.get('failure_class')}),flush=True)
        if final!='valid':
            raise RuntimeError('diagnostic attempt failed; no automatic retry')

if __name__=='__main__':main()
