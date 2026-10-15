#!/usr/bin/env python3
"""One GPU2 full episode to validate evidence_v1 integration, not a benchmark."""
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

from c0_trace_replay import STUDY, atomic_json, digest, gpu_idle, process_env, utc
from c0_poe_online_retest import worker_env, rows

ROOT = STUDY/'artifacts/stage_consistency_20260929'
OUTPUT = ROOT/'gpu2_task3_smoke'
MANIFEST = ROOT/'gpu-smoke-manifest.json'
FILES = ['main.py', 'core/stage_evidence.py', 'core/stage_observation.py', 'core/gemini_grounder.py',
         'core/poe_stage_capture.py', 'core/rdt_policy_steer.py', 'utils/guidance_utils.py',
         'vlm_query/stage_observation_v1.txt', 'configs/stage_controller/evidence_v1.yaml',
         'scripts/c0_poe_resilient_worker.py', 'scripts/stage_evidence_gpu_smoke.py']


def prepare():
    state = yaml.safe_load((STUDY/'research-state.yaml').read_text())
    assert state['resource_isolation']['status'] == 'ACTIVE'
    assert state['resource_isolation']['validation_status'] == 'PASS'
    base = STUDY/'artifacts/c0_poe_fresh_20260929'
    old = json.loads((base/'manifest-attempt2.json').read_text())
    reward = base/'outputs/c0_poe_fresh_attempt2/episode_4/vlm_agent'
    replacements = {'main.episode_num': '1', 'backend.libero.task_ids_filter': '[3]',
        'main.episode_seed_schedule': '[546]', 'main.cached_functions_dir': str(reward),
        'hydra.run.dir': str(OUTPUT), 'main.eds_eval.output_dir': str(OUTPUT/'eds_eval'),
        '+perception.gemini.capture_dir': str(OUTPUT/'captured_stage_inputs'),
        'main.eds_eval.method_label': 'stage_evidence_v1_smoke',
        'main.eds_eval.job_id': 'stage_evidence_v1_task3_functional_smoke'}
    argv = []
    for arg in old['argv']:
        key, sep, value = arg.partition('=')
        if key.lstrip('+') == 'main.stage_min_query_gap_steps':
            continue
        argv.append(key+'='+replacements.get(key, value) if sep else arg)
    argv.append('+stage_controller=evidence_v1')
    # Compose before loading weights; credential never enters Hydra config.
    cfg = subprocess.run(argv+['--cfg', 'job'], cwd=STUDY, env=process_env(),
                         capture_output=True, text=True, timeout=90)
    if cfg.returncode:
        raise RuntimeError('Hydra configuration failed: '+cfg.stderr[-2400:])
    resolved = yaml.safe_load(cfg.stdout)
    assert resolved['main']['stage_controller'] == 'evidence_v1'
    assert resolved['main']['stage_min_query_gap_steps'] == 16
    assert resolved['perception']['gemini']['api_key'] is None
    assert resolved['backend']['libero']['task_ids_filter'] == [3]
    manifest = dict(argv=argv, physical_gpu=2, gpu_uuid=old['gpu_uuid'], episodes=1, task_id=3, seed=546,
        purpose='functional integration smoke; no success-rate or paired C0 inference',
        reward='Reuse task3 reward freshly generated in the prior Gem3 experiment to isolate the control fix',
        policy_rng='new process seed0; NOT task3 continuous RNG state from the ten-task cohort',
        source_sha256={p: digest(STUDY/p) for p in FILES},
        reward_sha256={p.name: digest(p) for p in reward.iterdir() if p.is_file()},
        base_manifest_sha256=digest(base/'manifest-attempt2.json'))
    if MANIFEST.exists() and json.loads(MANIFEST.read_text()) != manifest:
        raise RuntimeError('Frozen smoke manifest changed')
    atomic_json(MANIFEST, manifest)
    for name in FILES:
        dest = ROOT/'frozen_source'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and digest(dest) != manifest['source_sha256'][name]:
            raise RuntimeError('Frozen smoke source changed')
        if not dest.exists():
            shutil.copy2(STUDY/name, dest)
    return manifest


def audit():
    status = json.loads((OUTPUT/'status.json').read_text())
    events = rows(OUTPUT/'eds_eval/stage_events.jsonl')
    metrics = rows(OUTPUT/'eds_eval/eds_metrics.jsonl')
    queries = [e for e in events if e['query_status'] in ('ok', 'error')]
    videos = list(OUTPUT.glob('episode_*/*agentview.mp4'))
    checks = dict(worker_exit=status['exit_code'] == 0, video=len(videos) == 1,
        no_episode_error=not list(OUTPUT.glob('episode_*/error.txt')),
        live_queries=bool(queries) and all(e['query_ok'] for e in queries),
        capability_gate=all(not e['guidance_after'] or e['reward_capability']['available'] for e in events),
        no_unconfirmed_completion=all(e['stage_after'] != 0 or e['completion_evidence_count'] >= 2 for e in events),
        ed_steps_match_gate=[e['global_step'] for e in events if e['guidance_after']] == [m['global_step'] for m in metrics],
        captures=len(list((OUTPUT/'captured_stage_inputs').glob('request_*'))) == len(queries))
    manifest = json.loads(MANIFEST.read_text())
    checks['frozen_source_unchanged'] = all(digest(STUDY/p) == h for p,h in manifest['source_sha256'].items())
    result = dict(valid=all(checks.values()), checks=checks, queries=len(queries), chunks=len(events),
        guided_chunks=sum(e['guidance_after'] for e in events),
        success=sum('success' in p.name for p in videos), videos=[str(p.relative_to(STUDY)) for p in videos],
        zero_score_eds_chunks=sum(m.get('initial_best_reward') == 0 and m.get('final_best_reward') == 0 for m in metrics),
        stage0_decisions=sum(e['stage_after']==0 for e in events), status=status)
    atomic_json(OUTPUT/'audit.json', result)
    return result


def run():
    manifest = prepare()
    if OUTPUT.exists():
        raise RuntimeError('Existing smoke output must be preserved')
    with (STUDY/'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not gpu_idle():
            raise RuntimeError('GPU2 is busy')
        actual_uuid = subprocess.check_output(['nvidia-smi', '-i', '2', '--query-gpu=uuid', '--format=csv,noheader'], text=True).strip()
        if actual_uuid != manifest['gpu_uuid']:
            raise RuntimeError('GPU2 UUID changed')
        OUTPUT.mkdir()
        started = time.monotonic(); proc = None
        try:
            with (OUTPUT/'console.log').open('w') as log:
                proc = subprocess.Popen(manifest['argv'], cwd=STUDY, env=worker_env(),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                while proc.poll() is None:
                    events = rows(OUTPUT/'eds_eval/stage_events.jsonl')
                    info = dict(utc=utc(), pid=proc.pid, elapsed_seconds=time.monotonic()-started,
                        last_step=events[-1]['global_step'] if events else None, chunks=len(events))
                    atomic_json(OUTPUT/'status.json', dict(status='running', **info))
                    print(json.dumps(info), flush=True)
                    if time.monotonic()-started > 3600:
                        raise RuntimeError('One-hour smoke watchdog')
                    time.sleep(15)
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=15)
            elapsed = time.monotonic()-started
            atomic_json(OUTPUT/'status.json', dict(status='exited', utc=utc(),
                exit_code=proc.returncode if proc else None, elapsed_seconds=elapsed))
            atomic_json(OUTPUT/'budget-charge.json', dict(episodes_started=len(list(OUTPUT.glob('episode_*'))),
                gpu_hours_upper_bound=elapsed/3600, protected_phase=False))
    print(json.dumps(audit(), indent=2), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('action', choices=('prepare','run','audit'))
    action=parser.parse_args().action
    if action == 'run':run()
    else:print(json.dumps(prepare() if action == 'prepare' else audit(), indent=2))
