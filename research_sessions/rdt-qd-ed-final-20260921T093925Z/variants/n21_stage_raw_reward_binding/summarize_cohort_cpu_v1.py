"""Close N21 from terminal ledger/native audit; no dispatch or state mutation."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'
COHORT = 'N21_STAGE_RAW_DEV_20260930'

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    plan_path = HERE / 'plan.frozen.v1.gpu7.json'
    status_path = HERE / 'execution/supervisor-status-gpu7-v1.json'
    plan, status = read(plan_path), read(status_path)
    assert status['status'] in ('rejected_task0_necessary_gate', 'completed_all_twelve_audited', 'failed', 'interrupted')
    events = [json.loads(line) for line in (ROOT / 'data/attempt-ledger.jsonl').open()]
    events = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    dispatched = {e['attempt_id']: e for e in events if e['event'] == 'dispatched'}
    terminals = {e['attempt_id']: e for e in events if e['event'] in ('valid', 'aborted')}
    assert set(dispatched) <= set(terminals), 'still running'
    cost_fields = ('gpu_process_wall_seconds', 'guided_chunks', 'unguided_chunks',
                   'candidate_evaluations', 'score_batches', 'model_forward_calls',
                   'model_batch_rows', 'reward_calls', 'reward_evaluations',
                   'reward_scoring_batches', 'provider_logical_call_attempts',
                   'stage_codex_logical_call_attempts', 'provider_input_tokens',
                   'provider_output_tokens', 'provider_cached_input_tokens',
                   'provider_failed_calls')
    rows = []
    for row in plan['episodes']:
        matches = [e for e in terminals.values() if e['episode_key'] == row['episode_key']]
        assert len(matches) <= 1, 'unexpected retry'
        if not matches:
            continue
        terminal = matches[0]
        audit_path = Path(terminal['output_dir']) / 'eds_eval/decision-evidence-audit.json'
        audit = read(audit_path) if audit_path.exists() else {}
        rows.append({'episode_key': row['episode_key'], 'task_id': row['task_id'],
                     'arm': row['profile'], 'attempt_id': terminal['attempt_id'],
                     'event': terminal['event'], 'outcome_valid': terminal.get('outcome_valid'),
                     'success': terminal.get('success'), 'costs': {k: terminal.get(k) for k in cost_fields},
                     'audit_path': str(audit_path),
                     'audit_sha256': sha(audit_path) if audit_path.exists() else None,
                     'audit_accepted': audit.get('accepted'),
                     'evidence_complete': audit.get('evidence_complete'),
                     'native_quality_audit': audit.get('n18_lift_quality_audit'),
                     'native_selection_audit': audit.get('n5_grasp_timing_audit')})
    result = {'schema': 'n21-dev-cohort-result-v1',
              'recorded_at': datetime.now(timezone.utc).isoformat(),
              'source_commit': plan['source_commit'], 'cohort_id': COHORT,
              'plan': {'path': str(plan_path), 'sha256': sha(plan_path)},
              'terminal_status': {'path': str(status_path), 'sha256': sha(status_path), 'content': status},
              'dispatched': len(dispatched), 'planned': len(plan['episodes']),
              'gpu_process_wall_seconds': sum(e.get('gpu_process_wall_seconds', 0) for e in terminals.values()),
              'dev_gate_promoted': status.get('dev_gate_promoted', False),
              'goal_status': 'TARGET_NOT_MET', 'rows': rows,
              'interpretation': 'Incomplete cohorts are not scored as full four-task development results. Native validity and simulator outcome are distinct. No protected phase released by this report.'}
    target = HERE / 'result-v1.json'
    assert not target.exists(), 'immutable result already exists'
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'path': str(target), 'sha256': sha(target), 'dispatched': len(dispatched),
                      'status': status['status'], 'rows': [{'task': x['task_id'], 'arm': x['arm'],
                        'success': x['success'], 'audit': x['audit_accepted'], 'costs': x['costs'],
                        'native_quality': x['native_quality_audit']} for x in rows]}))

if __name__ == '__main__':
    main()
