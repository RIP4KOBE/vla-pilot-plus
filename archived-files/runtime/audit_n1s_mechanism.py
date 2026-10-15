"""CPU-only descriptive audit of finished N1S episodes; no new decision gates."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import statistics

A = Path(__file__).resolve().parents[1]
W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
rows = []
for line in (W / 'data/attempt-ledger.jsonl').read_text().splitlines():
    e = json.loads(line)
    if e.get('identity', {}).get('iteration') != 'N1S' or e.get('outcome_valid') is not True:
        continue
    path = Path(e['output_dir']) / 'eds_eval/eds_metrics.jsonl'
    raw = path.read_bytes()
    metrics = [json.loads(line) for line in raw.splitlines() if line.strip()]
    active = [m for m in metrics if m.get('qd_archive_active_for_chunk')]
    row = {'attempt_id': e['attempt_id'], 'profile': e['identity']['profile'], 'task_id': e['identity']['task_id'],
        'success': e['success'], 'metrics_sha256': hashlib.sha256(raw).hexdigest(),
        'recorded_chunks': len(metrics), 'active_qd_chunks': len(active),
        'descriptor_counts': dict(collections.Counter(m['qd_descriptor'] for m in active)),
        'candidate_counts': dict(collections.Counter(m['search_evaluation_count'] for m in metrics)),
        'score_batches': dict(collections.Counter(m['score_call_count'] for m in metrics)),
        'invariant_totals': {k: sum(m.get(k, 0) for m in metrics) for k in (
            'nonfinite_count','qd_accounting_violation_count','qd_elite_monotonicity_violation_count',
            'qd_final_selection_mismatch_count','qd_secondary_invariant_violation_count')},
        'max_occupied_cells': max([n for m in active for n in m['qd_occupied_cells_by_iter']], default=None)}
    overflow = [v for m in active for v in m['qd_descriptor_overflow_ratio_by_iter']]
    row['mean_overflow_fraction'] = statistics.mean(overflow) if overflow else None
    if e['identity']['profile'] == 'N1':
        assert all(m['qd_descriptor'] == 'target_distance_gripper_duty_v1' for m in active)
        assert all(m['qd_descriptor_axes'] == [{'name':'target_distance','unit':'m'},
            {'name':'positive_gripper_command_duty','unit':'fraction'}] for m in active)
        row['chunks_with_multiple_proposed_duties'] = sum(
            len({d[1] for batch in m['shadow_qd_candidate_stream'] for d in batch['descriptor_values']}) > 1
            for m in active)
        row['chunks_with_multiple_sampled_parent_duties'] = sum(
            any(len({d[1] for d in batch}) > 1 for batch in m['qd_parent_descriptor_values_by_iter'])
            for m in active)
        row['parent_batches_total'] = sum(len(m['qd_parent_descriptor_values_by_iter']) for m in active)
        row['parent_batches_with_multiple_duties'] = sum(
            len({d[1] for d in batch}) > 1 for m in active for batch in m['qd_parent_descriptor_values_by_iter'])
        row['archive_iterations_with_positive_duty_span'] = sum(
            v[1] > 0 for m in active for v in m['qd_archive_descriptor_axis_span_by_iter'])
    rows.append(row)
out = A / 'analysis/n1s/finished-mechanism-audit.json'
out.parent.mkdir(parents=True, exist_ok=True)
result = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'iteration':'N1S',
    'completed': len(rows), 'planned':30,
    'note':'Descriptive telemetry only. Proposal variety and parent sampling are different quantities; neither establishes counterfactual task success. No post hoc coverage threshold.',
    'rows': rows}
temp = out.with_suffix('.json.tmp')
temp.write_text(json.dumps(result, indent=2)); temp.replace(out)
print(json.dumps({'completed':len(rows),'last':rows[-1] if rows else None}))
