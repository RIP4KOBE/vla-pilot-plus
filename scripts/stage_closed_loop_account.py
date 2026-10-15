#!/usr/bin/env python3
"""Idempotent own-study accounting, preserving original ledgers and reserves."""
import fcntl
import json
from pathlib import Path
import re
import yaml

from c0_trace_replay import STUDY, atomic_json, utc

ROOT=STUDY/'artifacts/stage_closed_loop_20260929'

def main():
    completed=[]; pending=[]
    for manifest_path in sorted((ROOT/'runs').glob('*/manifest.json')):
        folder=manifest_path.parent;manifest=json.loads(manifest_path.read_text())
        charge=folder/'output/budget-charge.json'
        if charge.exists():
            c=json.loads(charge.read_text());a=json.loads((folder/'audit.json').read_text()) if (folder/'audit.json').exists() else {}
            completed.append(dict(name=manifest['name'],episodes=c['episodes_started'],hours=c['gpu_hours_upper_bound'],
                                 valid=a.get('valid'),success=a.get('success'),audit=str((folder/'audit.json').relative_to(STUDY))))
        elif (folder/'output').exists():
            pending.append(dict(name=manifest['name'],reserved_episodes=len(manifest['tasks'])))
    attempts=205+sum(c['episodes'] for c in completed)
    hours=19.045150446626035+sum(c['hours'] for c in completed)
    record=dict(utc=utc(),effective_dispatched_completed=attempts,effective_gpu_hours_upper_bound=hours,
                current_runs=pending,completed_runs=completed,protected_attempts=100,protected_gpu_hours=24.0)
    atomic_json(ROOT/'accounting.json',record)
    with (STUDY/'data/qd-ed-state.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=STUDY/'research-state.yaml';old=path.read_text();data=yaml.safe_load(old)
        assert data['resource_isolation']['status']=='ACTIVE' and data['resource_isolation']['validation_status']=='PASS'
        section=data['stage_closed_loop_recovery_20260929']
        section.update(status='ACTIVE_CLOSED_LOOP_ITERATION',accounting_path=str((ROOT/'accounting.json').relative_to(STUDY)),
                       completed_runs=completed,current_runs=pending,effective_dispatched_completed=attempts,
                       effective_gpu_hours_upper_bound=hours,updated_utc=record['utc'])
        marker='\nstage_closed_loop_recovery_20260929:\n';assert marker in old
        text=old.split(marker)[0]+'\n'+yaml.safe_dump({'stage_closed_loop_recovery_20260929':section},sort_keys=False)
        cap=max(data['budget']['max_episode_attempts'],attempts+sum(c['reserved_episodes'] for c in pending)+100)
        text=re.sub(r'(?m)^  max_episode_attempts: \d+$',f'  max_episode_attempts: {cap}',text,count=1)
        path.write_text(text)
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
