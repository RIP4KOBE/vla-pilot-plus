"""Prospective, explicitly approved N1V budget and bounded timeout protocol.

No function edits an existing journal record. A timeout is not a valid task
outcome; its observed token subtotal remains incomplete, never imputed to zero.
"""
from pathlib import Path
import math

AUTH_SHA = '531c66107cafe3ad650b974f459f0f4a3ddc085042dd8354d7e59b562af87015'
CAPS = {'baseline': 13, 'development': 124, 'validation': 60, 'formal': 40, 'recovery': 13}
CONTRACT = {'schema': 'qd-ed-n1v-timeout-recovery-v1', 'iteration': 'N1V',
            'max_recoveries_per_cell': 1, 'max_total_recoveries': 6,
            'authorization_sha256': AUTH_SHA, 'failure_detail': 'n1v_stage_timeout',
            'legal_failure_retry': False, 'retroactive_reclassification': False}


def budget_authority(budget, read_json, digest, require, *, legacy_caps):
    ref = budget.get('n1v_authorization')
    if ref is None:
        return 240, legacy_caps
    require(ref.get('sha256') == AUTH_SHA and digest(ref['path']) == AUTH_SHA,
            'N1V budget authorization fingerprint mismatch')
    auth = read_json(ref['path'])
    require(auth.get('approved') is True and auth.get('caps') == CAPS
            and auth.get('max_episode_attempts') == 250 and auth.get('max_gpu_hours') == 48,
            'N1V budget authorization content mismatch')
    require(budget.get('reserved') == CAPS and budget.get('gpu_hour_reservations') ==
            {'validation': 14., 'formal': 10.}, 'N1V approved allocations changed')
    return 250, CAPS


def validate_contract(r, plan, state):
    contract = plan.get('n1v_recovery')
    is_n1v = any(row.get('iteration') == 'N1V' for row in plan.get('episodes', []))
    if not is_n1v and contract is None:
        return
    r.require(contract == CONTRACT and is_n1v, 'N1V requires its exact prospective recovery contract')
    ceiling, _ = budget_authority(state['budget'], r.read_json, r.digest, r.require, legacy_caps=r.BUCKETS)
    r.require(ceiling == 250 and plan.get('n1v_authorization') == state['budget'].get('n1v_authorization'),
              'N1V plan/shared budget authority mismatch')
    r.require({'scripts/qd_ed_n1v.py', 'scripts/qd_ed_n1v_supervise.py'} <=
              {f['path'] for f in plan.get('code_files', [])}, 'N1V protocol source is not frozen')
    for row in plan['episodes']:
        r.require(row.get('iteration') == 'N1V' and row.get('split') == 'dev'
                  and row.get('profile') in {'C0', 'Q0', 'N1'}
                  and row.get('timeout_seconds') == 1800
                  and row.get('budget_bucket') == ('recovery' if row.get('retry_of') else 'development'),
                  'N1V episode contract changed')


def check_retry(groups, row, identity, require):
    if row.get('iteration') != 'N1V':
        return
    cohort = [g for g in groups.values() if g[0].get('identity', {}).get('iteration') == 'N1V'
              and any(e['event'] == 'dispatched' for e in g)]
    prior = [g for g in cohort if g[0]['identity'] == identity(row)]
    if not row.get('retry_of'):
        require(not prior, 'N1V primary cell already dispatched')
        return
    require(len(prior) == 1 and prior[0][0].get('retry_of') is None,
            'N1V permits at most one recovery per original cell')
    last = prior[0][-1]
    require(row['retry_of'] == last['attempt_id'] and last['event'] == 'aborted'
            and last.get('retryable_infrastructure') is True
            and last.get('failure_detail') == 'n1v_stage_timeout'
            and last.get('n1v_authorization_sha256') == AUTH_SHA,
            'N1V recovery requires a prospectively classified Stage timeout')
    require(sum(bool(g[0].get('retry_of')) for g in cohort) < 6,
            'N1V six-recovery limit exhausted')


def timeout_outcome(r, plan, output, row, profile, runtime):
    """Called only before first terminal append, following clean child exit 0.

Missing evidence or a conflicting error rejects recovery; callers retain the
original nonretryable scientific-invalid outcome and the diagnostic reason.
"""
    if plan.get('n1v_recovery') != CONTRACT or row.get('iteration') != 'N1V':
        return None
    output = Path(output)
    try:
        r.require(r.codex_stage_condition(runtime) == 'codex_login_astra_low_json_reconnect_180s_v1',
                  'N1V Stage condition changed')
        r.validate_resolved_identity(output, row, profile, runtime)
        metrics = r.validate_metric_identity(output, row, profile)
        faults = r.read_json(output / 'gpu-kernel-xid.json')
        r.require(faults.get('schema') == 'qd-ed-kernel-xid-monitor-v1'
                  and faults.get('physical_gpu') == 2 and faults.get('records') == [],
                  'N1V timeout has unknown or conflicting GPU fault evidence')
        errors = list(output.glob('episode_*/error.txt'))
        r.require(len(errors) == 1 and errors[0].read_text().rstrip().endswith(
                  'RuntimeError: stage_json_query_failed: codex_timeout'), 'N1V execution error is not a Stage timeout')
        fail_errors = list(output.glob('episode_*/*fail_error.txt'))
        r.require(len(fail_errors) == 1 and fail_errors[0].read_text().strip() ==
                  'Episode failed due to execution error: stage_json_query_failed: codex_timeout',
                  'N1V terminal execution error conflicts with timeout')
        safety = r.read_events(output / 'eds_eval/safety_events.jsonl')
        r.require(not any(e.get('count', 0) > 0 for e in safety), 'N1V safety violation')
        costs = r.episode_compute(output, row, runtime)
        summary = r.stage_query_summary(output, row)
        actual = [e for e in r.read_events(output / 'eds_eval/stage_events.jsonl')
                  if e.get('query_status') != 'skipped']
        r.require(actual and len(actual) == costs['provider_logical_call_attempts']
                  and summary['stage_failed_queries'] == 1 and costs['provider_failed_calls'] == 1,
                  'N1V timeout call accounting mismatch')
        last = actual[-1]; transport = last.get('transport', {})
        r.require(last.get('query_status') == 'error' and last.get('query_ok') is False
                  and last.get('error') == 'codex_timeout' and last.get('raw_response') is None
                  and last.get('codex_completed_turns') == 0 and last.get('codex_usage_complete_calls') == 0
                  and transport.get('process_timed_out') is True and transport.get('completed_turns') == 0
                  and transport.get('diagnostics_version') == 'redacted_cli_v1',
                  'N1V requires an explicit incomplete timed-out Stage call')
        r.require(all(e.get('query_status') == 'ok' and e.get('query_ok') is True
                      and e.get('codex_usage_complete_calls') == 1 for e in actual[:-1]),
                  'N1V has other unsuccessful or unaccounted Stage calls')
        for e in actual:
            t = e.get('transport', {})
            r.require(e.get('codex_logical_call_attempts') == 1
                      and t.get('public_config_sha256') == costs['stage_transport']['public_config_sha256']
                      and t.get('application_max_attempts') == 1
                      and e.get('api_request_attempts') is None and e.get('api_sdk_retry_attempts') is None
                      and e.get('api_request_counter_available') is False,
                      'N1V call identity/HTTP observation mismatch')
        for suffix in r.CODEX_COUNT_SUFFIXES:
            values = [e.get('codex_' + suffix) for e in actual]
            r.require(all(type(v) is int and v >= 0 for v in values)
                      and sum(values) == costs['provider_' + suffix], 'N1V token/call subtotal mismatch')
        latencies = [e.get('codex_call_latency_s') for e in actual]
        r.require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in latencies)
                  and math.isclose(sum(latencies), costs['provider_call_latency_s'], abs_tol=1e-6),
                  'N1V call latency mismatch')
        r.require(costs['compute_outcome'] == 'execution_error' and costs['guided_chunks'] == len(metrics)
                  and costs['reward_scoring_batches'] >= sum(m['score_call_count'] for m in metrics)
                  and costs['required_cost_telemetry_complete'] is False,
                  'N1V interrupted episode accounting mismatch')
        evidence_files = ['.hydra/config.yaml', 'gpu-kernel-xid.json', 'eds_eval/episode_metadata.jsonl',
                          'eds_eval/episode_compute.jsonl', 'eds_eval/stage_events.jsonl']
        return {**costs, **summary, 'reason': 'prospectively classified N1V Stage timeout',
                'failure_detail': 'n1v_stage_timeout', 'failure_class': 'infrastructure',
                'retryable_infrastructure': True, 'success': False, 'task_failure': False,
                'outcome_valid': False, 'n1v_authorization_sha256': AUTH_SHA,
                'failed_call_token_usage': None, 'failed_call_token_usage_status': 'UNKNOWN',
                'recovery_evidence': {f: r.digest(output / f) for f in evidence_files}}
    except (r.GateError, OSError, ValueError, KeyError, TypeError) as exc:
        r.durable_json(output / 'n1v-recovery-rejected.json',
                       {'eligible': False, 'reason': str(exc) if isinstance(exc, r.GateError) else type(exc).__name__})
        return None
