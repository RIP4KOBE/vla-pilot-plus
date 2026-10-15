#!/usr/bin/env python3
"""Index saved cohort results without recomputing their frozen source audits."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'artifacts/stage_closed_loop_20260929'


def main():
    results=[]
    for path in (ROOT/'runs').glob('*/manifest.json'):
        folder=path.parent
        if not (folder/'output').exists():
            continue
        manifest=json.loads(path.read_text())
        audit=json.loads((folder/'audit.json').read_text()) if (folder/'audit.json').exists() else {}
        status=json.loads((folder/'output/status.json').read_text()) if (folder/'output/status.json').exists() else {}
        admission=json.loads((folder/'output/admission.json').read_text()) if (folder/'output/admission.json').exists() else {}
        diagnostic=manifest.get('online_performance_result') is False
        row=dict(name=manifest['name'],started_utc=admission.get('utc',''),
            cohort='historical_replay_calibration' if diagnostic else ('full10_online' if len(manifest['tasks'])==10 else 'development_subset'),
            reward=manifest.get('reward'),initialization_protocol=manifest.get('initialization_protocol',manifest.get('policy_rng','historical_continuous')),
            status=('USER_INTERRUPTED_PROVIDER_SWITCH' if (folder/'user-provider-switch-interruption.json').exists()
                    else ('VALID' if audit.get('valid') else ('INVALID' if audit else 'RUNNING'))),
            reported_success=audit.get('success',status.get('success')),planned_episodes=len(manifest['tasks']),
            completed_episodes=status.get('completed',0),elapsed_seconds=status.get('elapsed_seconds'),
            audit=f'runs/{manifest["name"]}/audit.json' if audit else '',
            videos=f'runs/{manifest["name"]}/videos.html' if (folder/'videos.html').exists() else '')
        results.append(row)
    results.sort(key=lambda x:x['started_utc'])
    (ROOT/'batch-summary.json').write_text(json.dumps(dict(note='Invalid or subset results cannot establish full online recovery. Calibration is not online performance. Never combine successes across cohorts.',runs=results),indent=2)+'\n')
    with (ROOT/'batch-summary.tsv').open('w') as file:
        writer=csv.DictWriter(file,fieldnames=list(results[0]),delimiter='\t')
        writer.writeheader();writer.writerows(results)
    lines=['# Closed-loop cohort evidence','',
        'Only a valid complete online ten-task cohort can meet the recovery criterion. Invalid scores are nominal counts, not valid estimates; historical replay is diagnostic only.','',
        '| Cohort | Type | Status | Success / completed | Initialization | Evidence |',
        '| --- | --- | --- | --- | --- | --- |']
    for row in results:
        evidence=' '.join(f'[{key}]({row[key]})' for key in ('audit','videos') if row[key])
        lines.append(f"| {row['name']} | {row['cohort']} | {row['status']} | {row['reported_success']} / {row['completed_episodes']} | {row['initialization_protocol']} | {evidence} |")
    (ROOT/'all-runs-index.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
