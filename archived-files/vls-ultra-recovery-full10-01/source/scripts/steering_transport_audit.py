"""Offline checks of saved transport summaries; no repository imports or I/O.

Mirrors observable invariants of frozen core/codex_stage.py and its policy.
The raw event stream and fallback/error text are not retained in the capture:
full parser replay is impossible. Notice classifications plus successful runtime
validation are attestations from the separately hash-verified runtime, not an
independent reconstruction of omitted text. Caller must bind model/effort,
retry-count configuration, policy SHA, request fingerprints and capture identity.
"""
import hashlib
import math

FALLBACK_PREFIX = 'Falling back from WebSockets to HTTPS transport. '
WARNING_TEMPLATE = ('Model metadata for `{model}` not found. Defaulting to fallback metadata; '
                    'this can degrade performance and cause issues.')
FALLBACK_POLICIES = {'completed_transport_fallback_v1', 'completed_transport_fallback_preturn_v2',
    'completed_transport_fallback_preturn_multiline_v3', 'completed_known_startup_warnings_v4',
    'completed_known_startup_warnings_combo_v5', 'completed_transport_cycles_v6'}
PRETURN_POLICIES = FALLBACK_POLICIES - {'completed_transport_fallback_v1'}
WARNING_POLICIES = {'completed_known_startup_warnings_v4',
                   'completed_known_startup_warnings_combo_v5', 'completed_transport_cycles_v6'}
COMBO_POLICIES = {'completed_known_startup_warnings_combo_v5', 'completed_transport_cycles_v6'}
ALL_POLICIES = FALLBACK_POLICIES | {'strict_v1', 'completed_reconnect_v1'}
RETRYABLE = {'codex_expected_one_completed_turn', 'codex_timeout',
             'codex_transport_failure', 'codex_nonzero_exit'}
TERMINAL_SIGNALS = {'authentication_failed', 'permission_denied', 'quota_exhausted'}


def _nat(value):
    return type(value) is int and value >= 0


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _audit(response, policy):
    t, c = response['transport'], response['counters']
    completion = response.get('completion_metadata') or {}
    event_policy = policy.get('event_policy', 'strict_v1')
    checks = {
        'runtime_validated_response': response.get('ok') is True
            and response.get('error_type') is None
            and isinstance(response.get('raw_response'), str) and bool(response['raw_response'].strip())
            and completion.get('finish_reason') == 'validated_turn_completed',
        'transport_policy_matches': event_policy in ALL_POLICIES
            and t.get('event_policy', 'strict_v1') == event_policy
            and t.get('model') == policy.get('model') == completion.get('response_model')
            and t.get('reasoning_effort') == policy.get('reasoning_effort') == completion.get('reasoning_effort'),
        'successful_process': type(t.get('process_returncode')) is int and t['process_returncode'] == 0
            and t.get('process_timed_out') is False,
    }
    events, items = t.get('event_types', []), t.get('item_types', [])
    allowed = {'thread.started', 'turn.started', 'turn.completed', 'item.started', 'item.updated', 'item.completed', 'error'}
    item_indices = [i for i, e in enumerate(events) if e in {'item.started', 'item.updated', 'item.completed'}]
    shape_ok = isinstance(events, list) and isinstance(items, list) and len(item_indices) == len(items)
    checks['event_summary_shape'] = shape_ok and all(e in allowed for e in events)
    if not shape_ok:
        checks['event_sequence'] = False
        return checks
    indexed_items = dict(zip(item_indices, items))
    messages = [i for i, kind in indexed_items.items() if kind == 'agent_message' and events[i] == 'item.completed']
    starts = [i for i,e in enumerate(events) if e == 'turn.started']
    completes = [i for i,e in enumerate(events) if e == 'turn.completed']
    threads = [i for i,e in enumerate(events) if e == 'thread.started']
    checks['one_completed_turn_and_response'] = (len(starts) == len(completes) == len(messages) == 1
        and t.get('completed_turns') == 1 and (event_policy not in PRETURN_POLICIES or len(threads) == 1))
    if not checks['one_completed_turn_and_response']:
        checks['event_sequence'] = False
        return checks
    start, complete, message = starts[0], completes[0], messages[0]
    checks['event_sequence'] = (event_policy not in FALLBACK_POLICIES or message < complete)
    fallback = t.get('transport_fallback_notices', [])
    warnings = t.get('model_metadata_warning_notices', [])
    errors = t.get('error_events', [])
    diagnostics = t.get('error_diagnostics', [])
    diag = {r['event_index']:r for r in diagnostics}
    fallback_indices, warning_indices, error_indices = [], [], []
    notices_ok = (len(fallback) <= 1 and len(warnings) <= 1 and len(diag) == len(diagnostics))
    for notice in fallback:
        i = notice.get('event_index'); fallback_indices.append(i)
        diagnostic = diag.get(i, {})
        preturn = event_policy in PRETURN_POLICIES and i == 1 and threads == [0] and i < start
        notices_ok &= (event_policy in FALLBACK_POLICIES and type(i) is int
            and indexed_items.get(i) == 'error' and events[i] == 'item.completed'
            and notice.get('classification') == 'websocket_to_https_fallback_notice'
            and _sha(notice.get('message_sha256')) and type(notice.get('message_length')) is int
            and len(FALLBACK_PREFIX) < notice['message_length'] <= 2048
            and i < complete and i < message and (start < i or preturn)
            and diagnostic.get('source') == 'error_item' and diagnostic.get('contains_nul') is False
            and (event_policy not in {'completed_transport_fallback_v1','completed_transport_fallback_preturn_v2'}
                 or diagnostic.get('contains_line_break') is False))
    for notice in warnings:
        i = notice.get('event_index'); warning_indices.append(i)
        expected = WARNING_TEMPLATE.format(model=policy.get('model'))
        notices_ok &= (event_policy in WARNING_POLICIES and i == 1 and threads == [0] and i < start
            and indexed_items.get(i) == 'error' and events[i] == 'item.completed'
            and notice.get('classification') == 'exact_model_metadata_fallback_warning'
            and notice.get('message_sha256') == hashlib.sha256(expected.encode()).hexdigest()
            and notice.get('message_length') == len(expected))
    if fallback_indices and warning_indices:
        notices_ok &= event_policy in COMBO_POLICIES and warning_indices[0] < fallback_indices[0]
    for notice in errors:
        i = notice.get('event_index'); error_indices.append(i)
        notices_ok &= (event_policy != 'strict_v1' and type(i) is int and 0 <= i < len(events)
            and events[i] == 'error' and start < i < min(complete, message)
            and notice.get('classification') == 'numbered_reconnecting_notice'
            and type(notice.get('attempt')) is int and type(notice.get('maximum')) is int
            and 1 <= notice['attempt'] <= notice['maximum'] <= 999 and _sha(notice.get('message_sha256')))
    # Item-start/update summaries are allowed for reasoning and agent messages.
    # Every error item/event must instead have exactly one authorized notice.
    error_item_indices = [i for i,k in indexed_items.items() if k == 'error']
    checks['only_authorized_event_items'] = all(k in {'reasoning','agent_message','error'} for k in items)
    checks['error_notice_bijection'] = (sorted(fallback_indices+warning_indices) == error_item_indices
        and len(set(fallback_indices+warning_indices)) == len(fallback_indices+warning_indices)
        and error_indices == [i for i,e in enumerate(events) if e == 'error'])
    checks['authorized_notice_semantics'] = bool(notices_ok)
    phases = [errors]
    if event_policy == 'completed_transport_cycles_v6' and fallback_indices:
        phases = [[n for n in errors if n['event_index'] < fallback_indices[0]],
                  [n for n in errors if n['event_index'] > fallback_indices[0]]]
    checks['reconnect_sequence'] = True
    if event_policy in COMBO_POLICIES:
        checks['reconnect_sequence'] = all(len(phase) <= 5 and all(
            a['attempt'] < b['attempt'] and a['maximum'] == b['maximum']
            for a,b in zip(phase,phase[1:])) for phase in phases)
    usages = t.get('observed_usage', [])
    usage_ok = isinstance(usages,list) and len(usages) == 1
    if usage_ok:
        usage = usages[0]
        usage_ok = (all(_nat(usage.get(k)) for k in ('input_tokens','cached_input_tokens','output_tokens'))
            and usage['cached_input_tokens'] <= usage['input_tokens']
            and (usage.get('reasoning_output_tokens') is None or _nat(usage['reasoning_output_tokens'])))
    checks['valid_observed_usage'] = usage_ok and completion.get('usage') == usages
    failed, physical, retry_count = t.get('failed_transport_attempts', []), t.get('physical_call_attempts'), t.get('transport_retry_count',0)
    checks['bounded_transport_retries'] = (_nat(retry_count) and retry_count <= 20 and _nat(physical)
        and physical == len(failed)+1 and 1 <= physical <= retry_count+1
        and c.get('logical_call_attempts') == physical)
    failure_ok = True
    for attempt in failed:
        signals = set(attempt.get('stderr_diagnostic', {}).get('signals', []))
        for diagnostic in attempt.get('error_diagnostics', []): signals.update(diagnostic.get('signals', []))
        failure_ok &= (attempt.get('error') in RETRYABLE and attempt.get('completed_turns', 0) == 0
            and 'turn.completed' not in attempt.get('event_types', []) and not signals.intersection(TERMINAL_SIGNALS))
    checks['only_incomplete_retryable_failures'] = bool(failure_ok)
    checks['successful_call_counters'] = (c.get('completed_turns') == c.get('usage_complete_calls') == 1
        and c.get('failed_calls') == 0 and isinstance(c.get('call_latency_s'), (int,float))
        and math.isfinite(c['call_latency_s']) and c['call_latency_s'] >= 0)
    if usage_ok:
        checks['token_counters_match_observed_usage'] = all(c.get(k) == usages[0].get(k)
            for k in ('input_tokens','cached_input_tokens','output_tokens')) and (
                c.get('reasoning_output_tokens') is None
                or c.get('reasoning_output_tokens') == usages[0].get('reasoning_output_tokens'))
        # The cumulative counter becomes unknown after any missing reasoning usage;
        # later per-call deltas remain None even when this call's usage is known.
    return checks


def audit_transport(response, policy) -> dict[str, bool | None]:
    """Return observable checks; malformed summaries fail without executing code."""
    try:
        return _audit(response, policy)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        return {'transport_summary_well_formed': False}
