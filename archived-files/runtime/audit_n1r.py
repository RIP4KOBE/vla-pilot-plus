"""Read completed N1R evidence on CPU; write only derived, incomplete reports."""
from pathlib import Path
import collections
import csv
import datetime
import io
import json
import statistics
import sys

A = Path(__file__).resolve().parents[1]
W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as runner
import qd_ed_final_report as report

plan = runner.read_json(W / 'data/qd-ed-n1r-post-reboot-plan.json')
events = runner.read_events(W / 'data/attempt-ledger.jsonl')
summary = report.summarize(plan, events, 'dev', 'N1R')
summary['observed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
folder = A / 'analysis/n1r'
folder.mkdir(parents=True, exist_ok=True)
runner.durable_json(folder / 'latest-outcomes.json', summary)

rows = []
for sample in summary['samples']:
    if sample['status'] != 'completed':
        continue
    attempt_id = sample['attempt_ids'][-1]
    out = runner.owned(A / 'attempts' / attempt_id, A)
    terminal = runner.read_json(out / 'attempt-result.json')
    assert terminal['outcome_valid'] is True
    assert terminal['identity']['iteration'] == 'N1R'
    phases = runner.read_events(out / 'eds_eval/phase_timing.jsonl')
    timings = collections.defaultdict(list)
    for item in phases:
        if item.get('event') == 'exit':
            timings[item['name']].append(item['elapsed_s'])
    steps = [item['global_step'] for item in phases
             if item.get('event') == 'exit' and item['name'] == 'adapter_step']
    assert steps == list(range(len(steps))) and 0 < len(steps) <= 720
    if not terminal['success']:
        assert len(steps) == 720
    faults = runner.read_json(out / 'gpu-kernel-xid.json')
    guided, unguided = terminal['guided_chunks'], terminal['unguided_chunks']
    row = {
        'task_id': sample['task_id'], 'profile': sample['profile'],
        'attempt_id': attempt_id, 'success': terminal['success'],
        'steps': len(steps), 'wall_s': terminal['gpu_process_wall_seconds'],
        'stage_calls': terminal['stage_successful_queries'],
        'stage_failed_calls': terminal['stage_failed_queries'],
        'stage_wall_s': terminal['provider_call_latency_s'],
        'stage_wall_fraction': terminal['provider_call_latency_s'] / terminal['gpu_process_wall_seconds'],
        'guided_chunks': guided, 'unguided_chunks': unguided,
        'guided_fraction': guided / (guided + unguided),
        'search_candidate_evaluations': terminal['candidate_evaluations'],
        'qd_activity_observed': terminal['qd_activity_observed'],
        'adapter_step_median_s': statistics.median(timings['adapter_step']),
        'fresh_action_median_s': statistics.median(timings['select_action_fresh']),
        'fresh_action_total_s': sum(timings['select_action_fresh']),
        'xid_records': len(faults['records']),
        'required_cost_telemetry_complete': terminal['required_cost_telemetry_complete'],
    }
    rows.append(row)
runner.durable_json(folder / 'completed-runtime-audit.json', {
    'observed_at': summary['observed_at'], 'iteration': 'N1R', 'planned': 30,
    'completed': len(rows), 'scientific_comparison_complete': len(rows) == 30,
    'note': 'Incomplete task subset; no promotion decision or causal inference from runtime differences.',
    'rows': rows,
})
if rows:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    target = folder / 'completed-runtime-audit.csv'
    temporary = target.with_suffix('.csv.tmp')
    temporary.write_text(buffer.getvalue())
    temporary.replace(target)
print(json.dumps({'completed': len(rows), 'planned': 30, 'last': rows[-1] if rows else None}, ensure_ascii=False))
