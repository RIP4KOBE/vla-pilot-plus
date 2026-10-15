"""Pure N34 reconciliation and an explicit detached-release launch entrypoint."""
from scripts import qd_ed_n23_worker as w, qd_ed_n34_contract as c


def reconcile(plan, events, verify_terminal, *, live_handles=()):
    """Reverify the unique contiguous prefix; never select/retry a duplicate cell."""
    rows = plan['episodes']
    w.require(rows == c.expected_rows(plan['worktree']), 'exact task-major matrix')
    w.require(all(isinstance(e.get('identity', {}), dict) for e in events), 'malformed journal identity')
    keys = {r['episode_key'] for r in rows}
    local = [e for e in events if e.get('identity', {}).get('iteration') == c.COHORT
             or e.get('attempt_id') in keys or e.get('episode_key') in keys]
    groups = []
    for event in local:
        w.require(all(event.get(k) is None for k in ('retry_of', 'recovery_of')), 'zero automatic recovery')
        if not groups or groups[-1][0]['attempt_id'] != event['attempt_id']:
            groups.append([])
        groups[-1].append(event)
    ids = [g[0]['attempt_id'] for g in groups]
    w.require(len(set(ids)) == len(ids) and len(groups) <= 30, 'duplicate/replayed attempt')
    outcomes = []
    for index, group in enumerate(groups):
        row = rows[index]
        w.require(all(e['attempt_id'] == row['episode_key'] and e['episode_key'] == row['episode_key'] and e['identity'] == c_identity(row) for e in group), 'duplicate/reordered/task identity')
        if plan.get('schema') == 'n34-released-plan-v1':
            immutable = ('attempt_id', 'identity', 'episode_key', 'budget_bucket', 'plan_sha256', 'release',
                         'source_commit', 'runtime_manifest_sha256', 'runtime_inventory_sha256',
                         'init_row_sha256', 'output_dir', 'physical_gpu', 'ledger_prefix', 'context')
            w.require(all(all(key in e and e[key] == group[0][key] for key in immutable) for e in group),
                      'lifecycle binding changed')
        kinds = [e['event'] for e in group]
        if kinds in (['reserved'], ['reserved', 'dispatched']):
            w.require(index == len(groups) - 1, 'dispatch after live handle')
            return {'status': 'LIVE_OR_UNSETTLED', 'next_row': None, 'outcomes': outcomes}
        if kinds != ['reserved', 'dispatched', 'valid']:
            return {'status': 'INVALID_STOP', 'next_row': None, 'outcomes': outcomes, 'charged_events': local}
        final = group[-1]
        try:
            w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True
                      and type(final.get('success')) is bool, 'invalid terminal')
            verify_terminal(row, final)
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
            return {'status': 'INVALID_STOP', 'next_row': None, 'outcomes': outcomes, 'charged_events': local, 'reason': str(exc)}
        outcomes.append({'task_id': row['task_id'], 'profile': row['profile'], 'success': final['success'],
                         'episode_key': row['episode_key'], 'attempt_id': final['attempt_id']})
        if len(outcomes) % 3 == 0 and sum(x['success'] for x in outcomes if x['profile'] == 'N34') + 10 - len(outcomes) // 3 < 5:
            w.require(index == len(groups) - 1, 'dispatch after complete-triple futility')
            return {'status': 'NUMERIC_FUTILITY', 'next_row': None, 'outcomes': outcomes}
    return {'status': 'LIVE_OR_UNSETTLED' if live_handles else ('COMPLETE' if len(outcomes) == 30 else 'READY_FOR_ROOT_RELEASE'),
            'next_row': None if live_handles or len(outcomes) == 30 else rows[len(outcomes)], 'outcomes': outcomes}


def c_identity(row):
    return {key: row[key] for key in ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')}


def launch(plan_ref=None, release_ref=None):
    if plan_ref is None or release_ref is None:
        c.require_release(None)
    from scripts.qd_ed_n34_runner import launch as released_launch
    return released_launch(plan_ref, release_ref)


def next_dispatch(plan, events, verify_terminal, allowance, *, now, live_handles=()):
    """Compose reconciliation and pre-dispatch guards under future runner locks.

    Returns a recommendation only. An adopted adapter must hold the normal
    runner/state locks while collecting this snapshot and reserving one primary.
    STOP is never forwarded to a running process and no handle is signalled.
    """
    c.validate_draft(plan)
    result = reconcile(plan, events, verify_terminal, live_handles=live_handles)
    if result['next_row'] is not None:
        c.pre_dispatch(result['next_row'], allowance, now=now, stop_path=plan['stop_path'])
    return result
