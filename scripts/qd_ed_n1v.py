"""Prospective, explicitly approved N1V/N1W budget and bounded timeout protocol.

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


N1W_AUTH_SHA = '445306c7023e0cba6a5affeaf2afab5af91bb393b9b39bf64341ba17b2c11258'
N1W_CAPS = {'baseline': 13, 'development': 125, 'validation': 60, 'formal': 40, 'recovery': 12}
N1W_CONTRACT = {**CONTRACT, 'schema': 'qd-ed-n1w-timeout-recovery-v1', 'iteration': 'N1W',
                'max_total_recoveries': 5, 'authorization_sha256': N1W_AUTH_SHA,
                'failure_detail': 'n1w_stage_timeout'}
N1X_AUTH_SHA = '0e90a4d21c0679ebec7ecddb8c15c87b421d60d76c85c8a2e0b5e9ac243a8adb'
N1X_CONTRACT = {**N1W_CONTRACT, 'schema': 'qd-ed-n1x-timeout-recovery-v1',
                'iteration': 'N1X', 'authorization_sha256': N1X_AUTH_SHA,
                'failure_detail': 'n1x_stage_timeout'}
N1Y_AUTH_SHA = '495bd36ebece8d659d134544020409bc57c3d8fd42993abc7dee5e3518e49edf'
N1Y_CONTRACT = {**N1X_CONTRACT, 'schema': 'qd-ed-n1y-timeout-recovery-v1',
                'iteration': 'N1Y', 'authorization_sha256': N1Y_AUTH_SHA,
                'failure_detail': 'n1y_stage_timeout'}
N1Z_AUTH_SHA = '3a0849094437d9aaa6cac68bdb2e5c27cb2a0aa824de45cb58dc1542b6dc942f'
N1Z_CONTRACT = {**N1Y_CONTRACT, 'schema': 'qd-ed-n1z-timeout-recovery-v1',
                'iteration': 'N1Z', 'authorization_sha256': N1Z_AUTH_SHA,
                'failure_detail': 'n1z_stage_timeout'}


def settings(iteration):
    """Separate immutable authorities; never infer one cohort's policy from another."""
    if iteration not in {'N1V', 'N1W', 'N1X', 'N1Y', 'N1Z'}:
        return None
    if iteration == 'N1Z':
        return {'iteration': 'N1Z', 'key': 'n1z', 'sha': N1Z_AUTH_SHA,
                'caps': N1W_CAPS, 'contract': N1Z_CONTRACT, 'limit': 5,
                'limit_word': 'five',
                'condition': 'codex_login_luna_low_json_transport_fallback_preturn_multiline_90s_v3'}
    if iteration == 'N1Y':
        return {'iteration': 'N1Y', 'key': 'n1y', 'sha': N1Y_AUTH_SHA,
                'caps': N1W_CAPS, 'contract': N1Y_CONTRACT, 'limit': 5,
                'limit_word': 'five',
                'condition': 'codex_login_luna_low_json_transport_fallback_preturn_90s_v2'}
    if iteration == 'N1X':
        return {'iteration': 'N1X', 'key': 'n1x', 'sha': N1X_AUTH_SHA,
                'caps': N1W_CAPS, 'contract': N1X_CONTRACT, 'limit': 5,
                'limit_word': 'five',
                'condition': 'codex_login_luna_low_json_transport_fallback_90s_v1'}
    newer = iteration == 'N1W'
    return {'iteration': iteration, 'key': iteration.lower(),
            'sha': N1W_AUTH_SHA if newer else AUTH_SHA,
            'caps': N1W_CAPS if newer else CAPS,
            'contract': N1W_CONTRACT if newer else CONTRACT,
            'limit': 5 if newer else 6,
            'limit_word': 'five' if newer else 'six',
            'condition': ('codex_login_astra_low_json_transport_fallback_180s_v1' if newer else
                          'codex_login_astra_low_json_reconnect_180s_v1')}


def budget_authority(budget, read_json, digest, require, *, legacy_caps):
    present = [name for name in ('N1V', 'N1W', 'N1X', 'N1Y', 'N1Z') if budget.get(name.lower() + '_authorization') is not None]
    require(len(present) <= 1, 'multiple active bounded-cohort budget authorities')
    if not present:
        return 240, legacy_caps
    cfg = settings(present[0]); label = cfg['iteration']
    ref = budget[cfg['key'] + '_authorization']
    require(ref.get('sha256') == cfg['sha'] and digest(ref['path']) == cfg['sha'],
            f'{label} budget authorization fingerprint mismatch')
    auth = read_json(ref['path'])
    require(auth.get('approved') is True and auth.get('caps') == cfg['caps']
            and auth.get('max_episode_attempts') == 250 and auth.get('max_gpu_hours') == 48,
            f'{label} budget authorization content mismatch')
    require(budget.get('reserved') == cfg['caps'] and budget.get('gpu_hour_reservations') ==
            {'validation': 14., 'formal': 10.}, f'{label} approved allocations changed')
    return 250, cfg['caps']


def validate_contract(r, plan, state):
    iterations = {row.get('iteration') for row in plan.get('episodes', [])}
    registered = iterations & {'N1V', 'N1W', 'N1X', 'N1Y', 'N1Z'}
    present = [name for name in ('N1V', 'N1W', 'N1X', 'N1Y', 'N1Z') if plan.get(name.lower() + '_recovery') is not None]
    if not registered and not present:
        return
    r.require(len(iterations) == len(registered) == len(present) == 1
              and present[0] in registered, 'bounded cohort requires one explicit matching iteration')
    cfg = settings(present[0]); label = cfg['iteration']; key = cfg['key']
    r.require(plan.get(key + '_recovery') == cfg['contract'], f'{label} requires its exact prospective recovery contract')
    if label in {'N1X', 'N1Y', 'N1Z'}:
        r.require(plan.get('stage_schedule') == {'min_query_gap_steps': 32, 'max_queries': 14},
                  'N1X Stage schedule changed')
    ceiling, _ = budget_authority(state['budget'], r.read_json, r.digest, r.require, legacy_caps=r.BUCKETS)
    ref = plan.get(key + '_authorization')
    r.require(ceiling == 250 and ref is not None and ref == state['budget'].get(key + '_authorization'),
              f'{label} plan/shared budget authority mismatch')
    r.require({'scripts/qd_ed_n1v.py', 'scripts/qd_ed_n1v_supervise.py'} <=
              {f['path'] for f in plan.get('code_files', [])}, f'{label} protocol source is not frozen')
    for row in plan['episodes']:
        r.require(row.get('iteration') == label and row.get('split') == 'dev'
                  and row.get('profile') in {'C0', 'Q0', 'N1'}
                  and row.get('timeout_seconds') == 1800
                  and row.get('budget_bucket') == ('recovery' if row.get('retry_of') else 'development'),
                  f'{label} episode contract changed')


def validate_transport_binding(r, plan, runtime):
    for row in plan.get('episodes', []):
        cfg = settings(row.get('iteration'))
        if cfg:
            r.require(r.codex_stage_condition(runtime) == cfg['condition'],
                      f"{cfg['iteration']} frozen Stage acceptance condition changed")
    if runtime.get('frozen_stage_provider', {}).get('event_policy') == 'completed_transport_fallback_v1':
        r.require(all(row.get('iteration') in {'N1W', 'N1X'} for row in plan['episodes']),
                  'transport fallback acceptance requires an approved N1W/N1X cohort')
    if runtime.get('frozen_stage_provider', {}).get('event_policy') == 'completed_transport_fallback_preturn_v2':
        r.require(all(row.get('iteration') == 'N1Y' for row in plan['episodes']),
                  'pre-turn transport fallback acceptance requires N1Y')
    if runtime.get('frozen_stage_provider', {}).get('event_policy') == 'completed_transport_fallback_preturn_multiline_v3':
        r.require(all(row.get('iteration') == 'N1Z' for row in plan['episodes']),
                  'multiline pre-turn transport fallback acceptance requires N1Z')


def check_retry(groups, row, identity, require):
    cfg = settings(row.get('iteration'))
    if cfg is None:
        return
    label = cfg['iteration']; key = cfg['key']
    cohort = [g for g in groups.values() if g[0].get('identity', {}).get('iteration') == label
              and any(e['event'] == 'dispatched' for e in g)]
    prior = [g for g in cohort if g[0]['identity'] == identity(row)]
    if not row.get('retry_of'):
        require(not prior, f'{label} primary cell already dispatched')
        return
    require(len(prior) == 1 and prior[0][0].get('retry_of') is None,
            f'{label} permits at most one recovery per original cell')
    last = prior[0][-1]
    require(row['retry_of'] == last['attempt_id'] and last['event'] == 'aborted'
            and last.get('retryable_infrastructure') is True
            and last.get('failure_detail') == key + '_stage_timeout'
            and last.get(key + '_authorization_sha256') == cfg['sha'],
            f'{label} recovery requires a prospectively classified Stage timeout')
    require(sum(bool(g[0].get('retry_of')) for g in cohort) < cfg['limit'],
            f"{label} {cfg['limit_word']}-recovery limit exhausted")


def timeout_outcome(r, plan, output, row, profile, runtime):
    """Called only before first terminal append, following clean child exit 0.

Missing evidence or a conflicting error rejects recovery; callers retain the
original nonretryable scientific-invalid outcome and the diagnostic reason.
"""
    cfg = settings(row.get('iteration'))
    if cfg is None or plan.get(cfg['key'] + '_recovery') != cfg['contract']:
        return None
    label = cfg['iteration']; key = cfg['key']
    output = Path(output)
    try:
        r.require(r.codex_stage_condition(runtime) == cfg['condition'],
                  f'{label} Stage condition changed')
        r.validate_resolved_identity(output, row, profile, runtime)
        metrics = r.validate_metric_identity(output, row, profile)
        faults = r.read_json(output / 'gpu-kernel-xid.json')
        r.require(faults.get('schema') == 'qd-ed-kernel-xid-monitor-v1'
                  and faults.get('physical_gpu') == 2 and faults.get('records') == [],
                  f'{label} timeout has unknown or conflicting GPU fault evidence')
        errors = list(output.glob('episode_*/error.txt'))
        r.require(len(errors) == 1 and errors[0].read_text().rstrip().endswith(
                  'RuntimeError: stage_json_query_failed: codex_timeout'), f'{label} execution error is not a Stage timeout')
        fail_errors = list(output.glob('episode_*/*fail_error.txt'))
        r.require(len(fail_errors) == 1 and fail_errors[0].read_text().strip() ==
                  'Episode failed due to execution error: stage_json_query_failed: codex_timeout',
                  f'{label} terminal execution error conflicts with timeout')
        safety = r.read_events(output / 'eds_eval/safety_events.jsonl')
        r.require(not any(e.get('count', 0) > 0 for e in safety), f'{label} safety violation')
        costs = r.episode_compute(output, row, runtime)
        summary = r.stage_query_summary(output, row)
        actual = [e for e in r.read_events(output / 'eds_eval/stage_events.jsonl')
                  if e.get('query_status') != 'skipped']
        r.require(actual and len(actual) == costs['provider_logical_call_attempts']
                  and summary['stage_failed_queries'] == 1 and costs['provider_failed_calls'] == 1,
                  f'{label} timeout call accounting mismatch')
        last = actual[-1]; transport = last.get('transport', {})
        r.require(last.get('query_status') == 'error' and last.get('query_ok') is False
                  and last.get('error') == 'codex_timeout' and last.get('raw_response') is None
                  and last.get('codex_completed_turns') == 0 and last.get('codex_usage_complete_calls') == 0
                  and transport.get('process_timed_out') is True and transport.get('completed_turns') == 0
                  and transport.get('diagnostics_version') == 'redacted_cli_v1',
                  f'{label} requires an explicit incomplete timed-out Stage call')
        r.require(all(e.get('query_status') == 'ok' and e.get('query_ok') is True
                      and e.get('codex_usage_complete_calls') == 1 for e in actual[:-1]),
                  f'{label} has other unsuccessful or unaccounted Stage calls')
        for e in actual:
            t = e.get('transport', {})
            r.require(e.get('codex_logical_call_attempts') == 1
                      and t.get('public_config_sha256') == costs['stage_transport']['public_config_sha256']
                      and t.get('application_max_attempts') == 1
                      and e.get('api_request_attempts') is None and e.get('api_sdk_retry_attempts') is None
                      and e.get('api_request_counter_available') is False,
                      f'{label} call identity/HTTP observation mismatch')
        for suffix in r.CODEX_COUNT_SUFFIXES:
            values = [e.get('codex_' + suffix) for e in actual]
            r.require(all(type(v) is int and v >= 0 for v in values)
                      and sum(values) == costs['provider_' + suffix], f'{label} token/call subtotal mismatch')
        latencies = [e.get('codex_call_latency_s') for e in actual]
        r.require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in latencies)
                  and math.isclose(sum(latencies), costs['provider_call_latency_s'], abs_tol=1e-6),
                  f'{label} call latency mismatch')
        r.require(costs['compute_outcome'] == 'execution_error' and costs['guided_chunks'] == len(metrics)
                  and costs['reward_scoring_batches'] >= sum(m['score_call_count'] for m in metrics)
                  and costs['required_cost_telemetry_complete'] is False,
                  f'{label} interrupted episode accounting mismatch')
        evidence_files = ['.hydra/config.yaml', 'gpu-kernel-xid.json', 'eds_eval/episode_metadata.jsonl',
                          'eds_eval/episode_compute.jsonl', 'eds_eval/stage_events.jsonl']
        return {**costs, **summary, 'reason': f'prospectively classified {label} Stage timeout',
                'failure_detail': key + '_stage_timeout', 'failure_class': 'infrastructure',
                'retryable_infrastructure': True, 'success': False, 'task_failure': False,
                'outcome_valid': False, key + '_authorization_sha256': cfg['sha'],
                'failed_call_token_usage': None, 'failed_call_token_usage_status': 'UNKNOWN',
                'recovery_evidence': {f: r.digest(output / f) for f in evidence_files}}
    except (r.GateError, OSError, ValueError, KeyError, TypeError) as exc:
        r.durable_json(output / (key + '-recovery-rejected.json'),
                       {'eligible': False, 'reason': str(exc) if isinstance(exc, r.GateError) else type(exc).__name__})
        return None
