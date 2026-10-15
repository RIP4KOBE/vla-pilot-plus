"""Immutable terminal N22 report; CPU-only, no dispatch or state mutation."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'
COHORT = 'N22_HOLD_LIFT_DEV_20260930'
ARMS = ('C0', 'Q0', 'N21', 'N22')
PLAN_SHA = '30846268778c46f2d9ad25a92abe7869395d3ead218da1a97dbf24fae4d07218'
TERMINAL_STATUS = {'completed_all_forty_audited', 'rejected_numeric_futility', 'failed', 'interrupted'}
COST_FIELDS = ('gpu_process_wall_seconds', 'guided_chunks', 'unguided_chunks',
               'candidate_evaluations', 'score_batches', 'model_forward_calls',
               'model_batch_rows', 'reward_calls', 'reward_evaluations',
               'reward_scoring_batches', 'provider_logical_call_attempts',
               'stage_codex_logical_call_attempts', 'provider_input_tokens',
               'provider_output_tokens', 'provider_cached_input_tokens',
               'provider_failed_calls')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact_counters(value):
    """Link bulky per-decision records by file hash, retain scalar summary."""
    if not isinstance(value, dict):
        return None
    return {k: v for k, v in value.items() if v is None or type(v) in (str, int, float, bool)}


def analyze(plan, status, events, audit_loader):
    require(status.get('status') in TERMINAL_STATUS, 'N22 is not terminal')
    rows = plan['episodes']
    require(len(rows) == 40 and [(x['task_id'], x['profile']) for x in rows]
            == [(task, arm) for task in range(10) for arm in ARMS], 'plan matrix differs')
    expected = {x['episode_key']: x for x in rows}
    events = [x for x in events if x.get('identity', {}).get('iteration') == COHORT]
    dispatch_rows = [x for x in events if x.get('event') == 'dispatched']
    terminal_rows = [x for x in events if x.get('event') in ('valid', 'aborted')]
    dispatched = {x['attempt_id']: x for x in dispatch_rows}
    terminals = {x['attempt_id']: x for x in terminal_rows}
    require(len(dispatched) == len(dispatch_rows) and len(terminals) == len(terminal_rows),
            'duplicate dispatch or terminal event')
    require(set(dispatched) == set(terminals), 'unsettled attempt or terminal without dispatch')
    counts = Counter(x['episode_key'] for x in dispatch_rows)
    require(set(counts) <= set(expected) and all(n == 1 for n in counts.values()),
            'unexpected episode or retry')
    require([x['episode_key'] for x in dispatch_rows] == list(expected)[:len(dispatched)],
            'dispatches are not the frozen prefix')
    results, missing = [], []
    for item in terminal_rows:
        key = item['episode_key']
        row = expected[key]
        require(item['identity']['task_id'] == row['task_id']
                and item['identity']['profile'] == row['profile'], 'terminal identity differs')
        require(dispatched[item['attempt_id']]['episode_key'] == key, 'dispatch identity differs')
        audit, reference = audit_loader(item)
        native_valid = (item['event'] == 'valid' and item.get('outcome_valid') is True
                        and audit.get('accepted') is True and audit.get('evidence_complete') is True)
        costs = {}
        for field in COST_FIELDS:
            value = item.get(field)
            valid = type(value) in (float, int) and math.isfinite(value) and value >= 0
            costs[field] = value if valid else None
            if not valid:
                missing.append({'episode_key': key, 'field': field})
        results.append({'episode_key': key, 'task_id': row['task_id'], 'arm': row['profile'],
                        'attempt_id': item['attempt_id'], 'event': item['event'],
                        'outcome_valid': item.get('outcome_valid'), 'success': item.get('success'),
                        'native_valid': native_valid, 'costs': costs, 'audit': reference,
                        'required_cost_telemetry_complete': item.get('required_cost_telemetry_complete'),
                        'provider_token_usage_complete': item.get('provider_token_usage_complete'),
                        'provider_usage_complete_calls': item.get('provider_usage_complete_calls'),
                        'quality_audit': compact_counters(audit.get('n22_hold_lift_quality_audit'
                                             if row['profile'] == 'N22' else 'n18_lift_quality_audit')),
                        'selection_audit': compact_counters(audit.get('n5_grasp_timing_audit'))})
    results.sort(key=lambda x: list(expected).index(x['episode_key']))
    audited = [x['episode_key'] for x in results if x['native_valid']]
    # A failed cohort may have a native-valid cell rejected by a stricter runtime gate.
    completed = status.get('completed_keys', [])
    require(len(set(completed)) == len(completed) and set(completed) <= set(audited),
            'supervisor completed set not supported by native evidence')
    require(completed == list(expected)[:len(completed)], 'audited supervisor prefix differs')
    accepted = [x for x in results if x['episode_key'] in completed]
    successes = {arm: sum(x['success'] is True for x in accepted if x['arm'] == arm) for arm in ARMS}
    require(successes == status['successes'], 'supervisor success counts differ')
    native = status.get('native', {}).get('N22', {})
    promoted = (len(accepted) == 40 and successes['N22'] >= 5
                and successes['N22'] >= max(successes[a] for a in ARMS[:-1])
                and native.get('guided_decisions', 0) > 0 and native.get('parent_rounds_verified', 0) > 0
                and status['status'] == 'completed_all_forty_audited')
    require(status.get('dev_gate_promoted') is promoted, 'promotion conflicts with frozen arithmetic')
    if status['status'] == 'rejected_numeric_futility':
        remaining = 10 - len(accepted) // 4
        require(len(accepted) == len(results) and len(accepted) % 4 == 0
                and successes['N22'] + remaining < 5
                and status['maximum_possible_candidate_successes'] == successes['N22'] + remaining,
                'numeric futility is not supported')
    if status['status'] == 'completed_all_forty_audited':
        require(len(accepted) == len(results) == 40, 'full-cohort terminal is incomplete')
    totals = {arm: {k: sum(x['costs'][k] or 0 for x in results if x['arm'] == arm)
                    for k in COST_FIELDS} for arm in ARMS}
    # run_plan raises after journaling an invalid terminal, before returning its
    # summary to the supervisor. Its charged costs are still in the ledger.
    observed_by_supervisor = status.get('attempted_keys', completed)
    require(observed_by_supervisor == list(expected)[:len(observed_by_supervisor)]
            and set(observed_by_supervisor) <= {x['episode_key'] for x in results}
            and set(completed) <= set(observed_by_supervisor), 'supervisor attempted prefix differs')
    supervisor_rows = [x for x in results if x['episode_key'] in observed_by_supervisor]
    for arm, values in status.get('cost_totals', {}).items():
        for key, value in values.items():
            if not any(x['arm'] == arm and x['costs'].get(key) is None for x in supervisor_rows):
                subtotal = sum(x['costs'][key] for x in supervisor_rows if x['arm'] == arm)
                require(math.isclose(subtotal, value, rel_tol=1e-9, abs_tol=1e-8),
                        'ledger and supervisor cost totals differ: ' + arm + '/' + key)
    task_rows = {t: {x['arm']: x['success'] is True for x in accepted if x['task_id'] == t}
                 for t in range(10)}
    matched_tasks = [t for t, values in task_rows.items() if set(values) == set(ARMS)]
    pairs = {arm: {'tasks': matched_tasks,
                   'gained': [t for t in matched_tasks if task_rows[t]['N22'] and not task_rows[t][arm]],
                   'lost': [t for t in matched_tasks if task_rows[t][arm] and not task_rows[t]['N22']]}
             for arm in ARMS[:-1]}
    disposition = ('ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else
                   'REJECT' if status['status'] in {'completed_all_forty_audited', 'rejected_numeric_futility'}
                   else 'INVALID_OR_INTERRUPTED')
    token_complete = all(x['provider_token_usage_complete'] is True for x in results)
    incomplete_usage = []
    for x in results:
        if x['provider_token_usage_complete'] is not True:
            attempts, measured = x['costs']['provider_logical_call_attempts'], x['provider_usage_complete_calls']
            unknown = attempts - measured if type(attempts) is int and type(measured) is int and 0 <= measured <= attempts else None
            incomplete_usage.append({'attempt_id': x['attempt_id'], 'unknown_token_calls': unknown})
    return {'dispatched': len(dispatched), 'planned': 40, 'audited_cells': len(accepted),
            'counts': {a: {'audited': sum(x['arm'] == a for x in accepted), 'success': successes[a]}
                       for a in ARMS}, 'rows': results, 'matched_task_comparisons': pairs,
            'cost_totals': totals, 'cost_missing_fields': missing,
            'charged_attempts_not_returned_to_supervisor': [x['attempt_id'] for x in results if x['episode_key'] not in observed_by_supervisor],
            'cost_totals_interpretation': 'Observed nonmissing counter sums. Missing cost fields and unobserved token usage are not zero; incomplete sums are lower bounds.',
            'provider_token_usage_complete': token_complete,
            'provider_token_aggregate_status': 'complete' if token_complete else 'partial_or_unknown',
            'incomplete_token_usage_attempts': incomplete_usage,
            'gpu_process_wall_seconds': sum(x['costs']['gpu_process_wall_seconds'] or 0 for x in results),
            'dev_gate_promoted': promoted, 'decision': disposition,
            'goal_status': 'TARGET_NOT_MET',
            'interpretation': 'Report successes over audited denominators only. Reused Dev is not independent generalization. Native mechanism activity is not causal efficacy. No protected phase is released by this report.'}


def main():
    plan_path = HERE / 'plan.frozen.v1.gpu7.json'
    status_path = HERE / 'execution/supervisor-status-gpu7-v1.json'
    require(sha(plan_path) == PLAN_SHA, 'frozen N22 plan differs')
    target = HERE / 'result-v1.json'
    require(not target.exists(), 'immutable report already exists')
    plan, status = read(plan_path), read(status_path)
    require(status.get('status') in TERMINAL_STATUS, 'N22 is still running; no report written')
    ledger = (ROOT / 'data/attempt-ledger.jsonl').read_bytes()
    events = [json.loads(line) for line in ledger.splitlines()]

    def load_audit(item):
        path = Path(item['output_dir']) / 'eds_eval/decision-evidence-audit.json'
        return (read(path), {'path': str(path), 'sha256': sha(path)}) if path.exists() else ({}, None)

    result = analyze(plan, status, events, load_audit)
    result.update(schema='n22-dev-cohort-result-v1', recorded_at=datetime.now(timezone.utc).isoformat(),
                  cohort_id=COHORT, source_commit=plan['source_commit'],
                  plan={'path': str(plan_path), 'sha256': sha(plan_path)},
                  terminal_status={'path': str(status_path), 'sha256': sha(status_path), 'content': status},
                  ledger_snapshot_sha256=hashlib.sha256(ledger).hexdigest(),
                  ledger_snapshot_bytes=len(ledger), reader_sha256=sha(__file__))
    with target.open('x') as f:
        f.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'path': str(target), 'sha256': sha(target), 'decision': result['decision'],
                      'counts': result['counts'], 'dispatched': result['dispatched'],
                      'gpu_process_wall_seconds': result['gpu_process_wall_seconds']}))


if __name__ == '__main__':
    main()
