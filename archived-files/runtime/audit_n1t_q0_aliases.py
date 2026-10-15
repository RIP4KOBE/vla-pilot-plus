"""Exact stored-action Q0 replay on all prespecified saved N1T trace chunks."""
import collections
import datetime
import hashlib
import json
from pathlib import Path
import sys

A = Path(__file__).resolve().parents[1]
W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
sys.path.insert(0, str(W / 'scripts'))
from qd_ed_executable_behavior_diagnostic import audit_trace

out = A / 'analysis/n1t/q0-action-aliases'
out.mkdir(parents=True, exist_ok=True)
reports = []
for line in (W / 'data/attempt-ledger.jsonl').read_text().splitlines():
    event = json.loads(line)
    identity = event.get('identity', {})
    if identity.get('iteration') != 'N1T' or identity.get('profile') != 'Q0' or event.get('outcome_valid') is not True:
        continue
    target = out / (event['attempt_id'] + '.json')
    if target.exists():
        reports.append(json.loads(target.read_text()))
        continue
    paths = sorted((Path(event['output_dir']) / 'eds_eval/qualitative').glob('episode_*/chunk_*/tensors/mechanism_trace.pt'))
    traces = [audit_trace(path) for path in paths]
    totals = collections.Counter()
    for trace in traces:
        totals.update(trace['counts'])
    report = {'attempt_id': event['attempt_id'], 'task_id': identity['task_id'],
        'source_commit': event['source_commit'], 'plan_sha256': event['plan_sha256'],
        'audit_script_sha256': hashlib.sha256((W / 'scripts/qd_ed_executable_behavior_diagnostic.py').read_bytes()).hexdigest(),
        'traces': traces, 'totals': dict(totals),
        'scope': 'All saved prespecified N1T Q0 chunks for this completed episode; exact stored action/fingerprint/archive replay. Corrected task cache and common JSON Stage condition.',
        'limitations': ['Only first two saved chunks, not whole-episode coverage.',
            'No unexecuted-action task outcomes or grasp/contact labels.',
            'Positive-command duty separation is pairwise only, not guaranteed N1 survivor retention.',
            't7/t8 geometry uses stored BF16 trajectory and float32 descriptors.',
            'Rejecting different executable actions does not by itself prove harmful selection.'],
        'gpu_calls': 0, 'model_calls': 0, 'environment_calls': 0, 'new_episodes': 0}
    target.write_text(json.dumps(report, indent=2))
    reports.append(report)
totals = collections.Counter()
for report in reports:
    totals.update(report['totals'])
summary = {'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'completed_Q0_tasks':len(reports), 'trace_count':sum(len(v['traces']) for v in reports),
    'counts':dict(totals), 'reports':[v['attempt_id'] for v in reports]}
(out / 'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
