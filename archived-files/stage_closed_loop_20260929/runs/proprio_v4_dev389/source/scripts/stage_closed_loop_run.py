#!/usr/bin/env python3
"""Immutable online Stage development runs, one owned GPU2 worker at a time."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import yaml

from c0_trace_replay import STUDY, SEEDS, atomic_json, digest, process_env, utc, CACHE
from c0_poe_online_retest import worker_env, rows

ROOT = STUDY/'artifacts/stage_closed_loop_20260929'
FRESH = STUDY/'artifacts/c0_poe_fresh_20260929'
GPU_UUID = 'GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e'
SOURCES = ['main.py','core/stage_evidence.py','core/stage_contact_handoff.py',
    'core/stage_grasp_guard.py','configs/stage_controller/grasp_v3.yaml',
    'core/stage_robot_evidence.py','core/stage_identity_memory.py','configs/stage_controller/proprio_v4.yaml',
    'core/stage_observation.py','core/gemini_grounder.py','core/poe_stage_capture.py',
    'core/rdt_policy_steer.py','utils/guidance_utils.py','core/env_adapters/libero_adapter.py',
    'vlm_query/stage_observation_v1.txt','configs/stage_controller/contact_v2.yaml',
    'configs/stage_controller/evidence_v1.yaml','scripts/stage_closed_loop_worker.py',
    'scripts/c0_poe_resilient_worker.py','scripts/stage_closed_loop_run.py']


def prepare(args):
    tasks = sorted(set(int(x) for x in args.tasks.split(',')))
    assert tasks and all(0 <= t < 10 for t in tasks)
    assert re.fullmatch('[a-zA-Z0-9_-]+',args.name)
    study = yaml.safe_load((STUDY/'research-state.yaml').read_text())
    assert study['resource_isolation']['status']=='ACTIVE'
    assert study['resource_isolation']['validation_status']=='PASS'
    folder=ROOT/'runs'/args.name; folder.mkdir(parents=True,exist_ok=True)
    output=folder/'output'
    old=json.loads((FRESH/'manifest-attempt2.json').read_text())
    replace={'main.episode_num':str(len(tasks)), 'backend.libero.task_ids_filter':json.dumps(tasks,separators=(',',':')),
        'main.episode_seed_schedule':json.dumps([SEEDS[t] for t in tasks],separators=(',',':')),
        'hydra.run.dir':str(output),'main.eds_eval.output_dir':str(output/'eds_eval'),
        '+perception.gemini.capture_dir':str(output/'captured_stage_inputs'),
        'main.eds_eval.method_label':args.controller,'main.eds_eval.job_id':args.name,
        'main.cached_functions_dir':str(CACHE) if args.reward=='historical' else 'null'}
    argv=[]
    for arg in old['argv']:
        k,sep,v=arg.partition('=')
        if k.lstrip('+')=='main.stage_min_query_gap_steps':continue
        argv.append(k+'='+replace.get(k,v) if sep else arg)
    argv[1]='scripts/stage_closed_loop_worker.py'
    argv.extend(['+stage_controller='+args.controller,'+main.episode_policy_rng_mode=per_seed_v1'])
    if args.reward=='fresh_frozen':
        argv.append('+main.cached_functions_root='+str(FRESH/'outputs/c0_poe_fresh_attempt2'))
    for arg in args.override:
        k,sep,v=arg.partition('=')
        if not sep:raise ValueError('override must be key=value')
        normalized=k.lstrip('+')
        argv=[x for x in argv if x.partition('=')[0].lstrip('+')!=normalized]
        argv.append(arg)
    cfg=subprocess.run(argv+['--cfg','job'],cwd=STUDY,env=process_env(),capture_output=True,text=True,timeout=90)
    if cfg.returncode:raise RuntimeError(cfg.stderr[-2200:])
    resolved=yaml.safe_load(cfg.stdout)
    assert resolved['main']['episode_policy_rng_mode']=='per_seed_v1'
    assert resolved['main']['stage_controller']==args.controller
    assert resolved['perception']['gemini']['api_key'] is None
    source_hashes={p:digest(STUDY/p) for p in SOURCES}
    manifest={'name':args.name,'tasks':tasks,'seeds':[SEEDS[t] for t in tasks],'controller':args.controller,
        'reward':args.reward,'argv':argv,'physical_gpu':2,'gpu_uuid':GPU_UUID,
        'allocator_ceiling_gib':48,'admission_free_gib':56,'source_sha256':source_hashes,
        'policy_rng':'per_seed_v1; same initial policy RNG for each environment seed independent of episode ordering',
        'base_manifest_sha256':digest(FRESH/'manifest-attempt2.json')}
    path=folder/'manifest.json'
    if path.exists() and json.loads(path.read_text())!=manifest:raise RuntimeError('Frozen manifest differs')
    atomic_json(path,manifest)
    for name,h in source_hashes.items():
        dest=folder/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and digest(dest)!=h:raise RuntimeError('Source snapshot differs')
        if not dest.exists():shutil.copy2(STUDY/name,dest)
    (folder/'resolved-config.yaml').write_text(cfg.stdout)
    return folder,manifest


def progress(output):
    e=rows(output/'eds_eval/stage_events.jsonl');m=rows(output/'eds_eval/episode_metadata.jsonl')
    videos=list(output.glob('episode_*/*agentview.mp4'))
    return {'started':max(len(m),len(list(output.glob('episode_*')))), 'completed':len(videos),
        'success':sum('success' in p.name for p in videos),'last_task':e[-1].get('task_id') if e else None,
        'last_step':e[-1].get('global_step') if e else None,'query_errors':sum(x.get('query_status')=='error' for x in e)}


def audit(folder,manifest):
    out=folder/'output';status=json.loads((out/'status.json').read_text())
    events=rows(out/'eds_eval/stage_events.jsonl');meta=rows(out/'eds_eval/episode_metadata.jsonl')
    metrics=rows(out/'eds_eval/eds_metrics.jsonl');q=[e for e in events if e.get('query_status') in ('ok','error')]
    checks={'worker_exit':status['exit_code']==0,
        'tasks_seeds':[(r['task_id'],r['episode_seed']) for r in meta]==list(zip(manifest['tasks'],manifest['seeds'])),
        'no_episode_errors':not list(out.glob('episode_*/error.txt')),
        'queries_valid':bool(q) and all(r.get('query_ok') for r in q),
        'ed_steps_match_gate':[(r['episode_id'],r['global_step']) for r in events if r['guidance_after']]==[(r['episode'],r['global_step']) for r in metrics],
        'reward_gate':all(not r['guidance_after'] or r['reward_capability']['available'] for r in events),
        'source_unchanged':all(digest(STUDY/p)==h for p,h in manifest['source_sha256'].items())}
    per_task=[]
    for i,t in enumerate(manifest['tasks']):
        videos=list((out/f'episode_{i+1}').glob('*agentview.mp4'))
        checks[f'video_{t}']=len(videos)==1
        ev=[r for r in events if r['task_id']==t]
        per_task.append({'task':t,'success':any('success' in p.name for p in videos),
            'guided_chunks':sum(r['guidance_after'] for r in ev),'chunks':len(ev),
            'queries':sum(r.get('query_status')=='ok' for r in ev),'videos':[str(p.relative_to(STUDY)) for p in videos]})
    text=(out/'results.txt').read_text() if (out/'results.txt').exists() else ''
    success=sum(r['success'] for r in per_task)
    checks['final_score']=f'Success count: {success}/{len(per_task)}' in text
    guarded=[r for r in rows(out/'eds_eval/safety_events.jsonl') if r.get('event')=='stage_grasp_guard_action']
    if manifest['controller'] in {'grasp_v3','proprio_v4'}:
        checks['arm_commands_preserved']=bool(guarded) and all(r['raw_action'][:6]==r['executed_action'][:6] for r in guarded)
        checks['release_allowed_at_goal']=all(not r['override'] for r in guarded if r['goal_aligned'])
    result={'valid':all(checks.values()),'checks':checks,'success':success,'episodes':len(per_task),'per_task':per_task,
        'stage_queries':len(q),'http_attempts':sum(r.get('api_request_attempts',0) for r in q),
        'http_retries':sum(r.get('api_sdk_retry_attempts',0) for r in q),'status':status,
        'guarded_action_rows':len(guarded),'gripper_overrides':sum(r['override'] for r in guarded)}
    atomic_json(folder/'audit.json',result)
    return result


def run(args):
    folder,manifest=prepare(args);out=folder/'output'
    if out.exists():raise RuntimeError('Output exists; no implicit rerun or overwrite')
    with (STUDY/'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        raw=subprocess.check_output(['nvidia-smi','-i','2','--query-gpu=uuid,memory.free,memory.used','--format=csv,noheader,nounits'],text=True)
        uuid,free,used=[s.strip() for s in raw.strip().split(',')]
        if uuid!=GPU_UUID or int(free)<56*1024:raise RuntimeError('GPU2 has insufficient safe headroom')
        out.mkdir();atomic_json(out/'admission.json',{'utc':utc(),'physical_gpu':2,'uuid':uuid,'free_mib':int(free),'other_used_mib':int(used),'co_residency':int(used)>1024,'allocator_ceiling_gib':48})
        started=time.monotonic();proc=None
        try:
            with (out/'console.log').open('w') as log:
                proc=subprocess.Popen(manifest['argv'],cwd=STUDY,env=worker_env(),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                while proc.poll() is None:
                    info=progress(out);info.update(utc=utc(),pid=proc.pid,elapsed_seconds=time.monotonic()-started)
                    atomic_json(out/'status.json',dict(status='running',**info));print(json.dumps(info),flush=True)
                    if info['started']>len(manifest['tasks']):raise RuntimeError('Excess task starts')
                    if time.monotonic()-started>len(manifest['tasks'])*3600+300:raise RuntimeError('Hung worker watchdog')
                    time.sleep(20)
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=15)
            elapsed=time.monotonic()-started
            atomic_json(out/'status.json',dict(status='exited',utc=utc(),exit_code=proc.returncode if proc else None,elapsed_seconds=elapsed,**progress(out)))
            atomic_json(out/'budget-charge.json',dict(episodes_started=progress(out)['started'],gpu_hours_upper_bound=elapsed/3600,protected_phase=False))
    result=audit(folder,manifest);print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run','audit'])
    p.add_argument('--name',required=True);p.add_argument('--tasks',default='0,1,2,3,4,5,6,7,8,9')
    p.add_argument('--controller',default='contact_v2',choices=['contact_v2','evidence_v1','grasp_v3','proprio_v4'])
    p.add_argument('--reward',default='fresh_frozen',choices=['fresh_frozen','historical','regenerate'])
    p.add_argument('--override',action='append',default=[])
    args=p.parse_args()
    if args.action=='run':run(args)
    elif args.action=='prepare':print(json.dumps(prepare(args)[1],indent=2))
    else:
        f=ROOT/'runs'/args.name;print(json.dumps(audit(f,json.loads((f/'manifest.json').read_text())),indent=2))
