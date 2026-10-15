#!/usr/bin/env python3
"""Record historical RNG initializations only after an exact replay calibration.

This is a diagnostic calibration, never an online performance result.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import yaml

from c0_trace_replay import STUDY, SEEDS, TRACE, CACHE, digest, atomic_json, process_env, utc
from stage_closed_loop_run import ROOT, GPU_UUID, SOURCES, progress
from c0_poe_online_retest import rows
import c0_current_trace_replay as historical_audit

NAME = 'historical_initialization_calibration_v1'
FOLDER = ROOT/'runs'/NAME
EXTRA_SOURCES = ['core/episode_rng_fixture.py', 'core/episode_rng_hooks.py',
    'scripts/stage_rng_fixture_worker.py', 'scripts/stage_rng_calibration.py',
    'scripts/c0_current_trace_replay.py', 'core/trace_replay_stage.py']


def prepare():
    state = yaml.safe_load((STUDY/'research-state.yaml').read_text())
    assert state['resource_isolation']['status'] == 'ACTIVE'
    assert state['resource_isolation']['validation_status'] == 'PASS'
    old_path = STUDY/'artifacts/c0_trace_replay_20260925/current-manifest-v2.json'
    old = json.loads(old_path.read_text())
    output = FOLDER/'output'
    argv = list(old['argv'])
    argv[1] = 'scripts/stage_rng_fixture_worker.py'
    replacement = {'hydra.run.dir':str(output), 'main.eds_eval.output_dir':str(output/'eds_eval')}
    argv = [x.partition('=')[0]+'='+replacement[x.partition('=')[0]]
            if x.partition('=')[0] in replacement else x for x in argv]
    argv += ['+main.episode_policy_rng_mode=continuous',
             '+main.episode_rng_record_dir='+str(FOLDER/'fixtures')]
    cfg = subprocess.run(argv+['--cfg','job'],cwd=STUDY,env=process_env(),capture_output=True,text=True,timeout=90)
    if cfg.returncode:
        raise RuntimeError(cfg.stderr[-2500:])
    resolved = yaml.safe_load(cfg.stdout)
    assert resolved['main'].get('stage_controller','legacy') == 'legacy'
    assert resolved['perception']['gemini']['backend'] == 'trace_replay'
    assert resolved['main']['cached_functions_dir'] == str(CACHE)
    sources = {name:digest(STUDY/name) for name in sorted(set(SOURCES+EXTRA_SOURCES))}
    manifest = dict(name=NAME,tasks=list(range(10)),seeds=SEEDS,argv=argv,source_sha256=sources,
        protocol='diagnostic_historical_replay_rng_recording',controller='legacy',reward='historical',
        online_performance_result=False,physical_gpu=2,gpu_uuid=GPU_UUID,
        historical_manifest_sha256=digest(old_path),historical_trace_sha256=digest(TRACE),
        historical_cache_sha256={p.name:digest(p) for p in CACHE.iterdir() if p.is_file()})
    FOLDER.mkdir(parents=True,exist_ok=True)
    path = FOLDER/'manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError('Frozen calibration manifest differs')
    atomic_json(path,manifest)
    (FOLDER/'resolved-config.yaml').write_text(cfg.stdout)
    for name, sha in sources.items():
        destination = FOLDER/'source'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists() and digest(destination) != sha:
            raise RuntimeError('Frozen calibration source differs')
        if not destination.exists():
            shutil.copy2(STUDY/name,destination)
    return manifest


def audit(manifest):
    output = FOLDER/'output'
    historical_audit.OUTPUT = output
    replay = historical_audit.audit()
    journal = rows(output/'eds_eval/episode_rng_events.jsonl')
    checks = dict(exact_historical_replay=replay['valid_full_replay'],
        source_unchanged=all(digest(STUDY/p)==h for p,h in manifest['source_sha256'].items()),
        rng_events=[(r['metadata']['task_id'],r['metadata']['episode_seed'],r['metadata']['phase']) for r in journal]
            == [(t,SEEDS[t],phase) for t in range(10) for phase in ('prepare','rollout')],
        rng_files_unchanged=bool(journal) and all(r.get('mode')=='record' and digest(Path(r['path']))==r['sha256'] for r in journal))
    result = dict(valid=all(checks.values()), checks=checks, success=replay['success_count'],episodes=10,
                  protocol='diagnostic_historical_replay_rng_recording',online_performance_result=False,
                  replay=replay, status=json.loads((output/'status.json').read_text()))
    atomic_json(FOLDER/'audit.json',result)
    if result['valid']:
        fixture_manifest = dict(schema='episode_rng_fixture_manifest_v1',calibration_valid=True,
            calibration_audit_sha256=digest(FOLDER/'audit.json'),
            purpose='RNG initialization only; no historical replies, actions, reward or environment states',
            fixtures={f"{r['metadata']['task_id']}:{r['metadata']['phase']}":
                      dict(file=str(Path(r['path']).relative_to(FOLDER)),sha256=r['sha256'],
                           metadata=r['metadata'],state_signature=r['state_signature']) for r in journal})
        atomic_json(FOLDER/'fixture-manifest.json',fixture_manifest)
    return result


def run():
    manifest = prepare()
    output = FOLDER/'output'
    if output.exists():
        raise RuntimeError('Calibration output exists; never overwrite or implicitly resume')
    with (STUDY/'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        raw = subprocess.check_output(['nvidia-smi','-i','2','--query-gpu=uuid,memory.free,memory.used','--format=csv,noheader,nounits'],text=True)
        uuid, free, used = [part.strip() for part in raw.strip().split(',')]
        if uuid != GPU_UUID or int(free)<56*1024:
            raise RuntimeError('GPU2 has insufficient safe headroom')
        output.mkdir()
        atomic_json(output/'admission.json',dict(utc=utc(),physical_gpu=2,uuid=uuid,free_mib=int(free),other_used_mib=int(used),allocator_ceiling_gib=48))
        started = time.monotonic()
        proc = None
        try:
            with (output/'console.log').open('w') as logfile:
                proc = subprocess.Popen(manifest['argv'],cwd=STUDY,env=process_env(),stdout=logfile,stderr=subprocess.STDOUT,start_new_session=True)
                while proc.poll() is None:
                    info = dict(utc=utc(),pid=proc.pid,elapsed_seconds=time.monotonic()-started,**progress(output))
                    atomic_json(output/'status.json',dict(status='running',**info))
                    print(json.dumps(info),flush=True)
                    if info['started']>10 or info['elapsed_seconds']>15000:
                        raise RuntimeError('Calibration watchdog exceeded')
                    time.sleep(20)
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL)
                    proc.wait(timeout=15)
            elapsed = time.monotonic()-started
            atomic_json(output/'status.json',dict(status='exited',utc=utc(),exit_code=proc.returncode if proc else None,elapsed_seconds=elapsed,**progress(output)))
            atomic_json(output/'budget-charge.json',dict(episodes_started=progress(output)['started'],gpu_hours_upper_bound=elapsed/3600,protected_phase=False))
    print(json.dumps(audit(manifest),indent=2),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','audit'])
    args = parser.parse_args()
    if args.action == 'run':
        run()
    elif args.action == 'prepare':
        print(json.dumps(prepare(),indent=2))
    else:
        print(json.dumps(audit(json.loads((FOLDER/'manifest.json').read_text())),indent=2))
