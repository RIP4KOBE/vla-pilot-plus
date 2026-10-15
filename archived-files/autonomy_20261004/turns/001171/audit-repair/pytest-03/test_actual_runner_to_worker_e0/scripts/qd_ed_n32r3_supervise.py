"""Strict 14 original + 16 prospective reconciliation; no scientific evaluation."""
from scripts import qd_ed_n23_worker as w, qd_ed_n32r3_contract as c
from scripts.qd_ed_n32_supervise import c_identity
from scripts.qd_ed_n32r3_history import verified_parent


def progress(outcomes):
    keys = [(x['task_id'], x['profile']) for x in outcomes]
    w.require(len(keys) == len(set(keys)) and keys == [(t,a) for t in range(10) for a in c.ARMS][:len(keys)]
              and all(type(x['success']) is bool for x in outcomes), 'complete valid semantic prefix')
    triples = len(outcomes)//3
    successes = sum(x['success'] for x in outcomes[:triples*3] if x['profile'] == 'N32')
    controls = {arm: sum(x['success'] for x in outcomes if x['profile'] == arm) for arm in c.ARMS}
    return {'complete_valid_triples': triples, 'n32_successes': successes,
            'futile': successes + 10 - triples < 5,
            'prospective_dev_necessary_gate_met': len(outcomes) == 30 and successes >= 5
                 and successes >= max(controls['C0'], controls['Q0']),
            'scientific_promotion': False, 'http_counters': 'Unknown'}


def reconcile(plan, events, verify_terminal, *, live_handles=()):
    w.require(plan['episodes'] == c.expected_rows(plan['worktree']), 'exact continuation matrix')
    outcomes = verified_parent(plan, events)
    w.require(len(outcomes) == 14, 'missing original controls')
    local = [e for e in events if e.get('identity', {}).get('iteration') == c.COHORT]
    groups = []
    for event in local:
        if not groups or event['attempt_id'] != groups[-1][0]['attempt_id']:
            groups.append([])
        groups[-1].append(event)
    ids = [g[0]['attempt_id'] for g in groups]
    w.require(len(ids) == len(set(ids)) and len(ids) <= 16, 'duplicate recovery/attempt')
    # An alias under a different iteration cannot hide a replay/recovery.
    expected_ids = {x['episode_key'] for x in plan['episodes']}
    w.require(all(e in local for e in events if e['attempt_id'] in expected_ids or e.get('recovery_of') == c.OLD_INVALID), 'foreign iteration alias/recovery')
    def result(status, row=None):
        return {'status': status, 'next_row': row, 'outcomes': outcomes, 'charged_events': events, **progress(outcomes)}
    for index, group in enumerate(groups):
        row = plan['episodes'][index]
        binding = c.commitments(plan, row)
        w.require(all(e['attempt_id'] == e['episode_key'] == row['episode_key'] and e['identity'] == c_identity(row)
                      and e.get('schema') == 'n32r3-lifecycle-v1' and e.get('continuation') == binding
                      and e.get('retry_of') is None and e.get('recovery_of') == c.recovery_of(row) for e in group), 'execution/mapping identity')
        immutable = ('attempt_id','identity','episode_key','budget_bucket','plan_sha256','release','source_commit',
                     'runtime_manifest_sha256','runtime_inventory_sha256','init_row_sha256','output_dir','physical_gpu','ledger_prefix','context','continuation','semantic_key')
        w.require(all(all(k in e and e[k] == group[0][k] for k in immutable) for e in group), 'lifecycle binding changed')
        kinds = [e['event'] for e in group]
        if kinds in (['reserved'], ['reserved','dispatched']):
            w.require(index == len(groups)-1, 'dispatch after unsettled')
            return result('LIVE_OR_UNSETTLED')
        if kinds != ['reserved','dispatched','valid']:
            w.require(index == len(groups)-1, 'dispatch after invalid')
            return result('INVALID_STOP')
        final = group[-1]
        try:
            w.require(final['outcome_valid'] is True and final['required_cost_telemetry_complete'] is True
                      and type(final['success']) is bool, 'invalid Stage/terminal')
            verify_terminal(row, final)
        except (ValueError, KeyError, TypeError, OSError, RuntimeError):
            w.require(index == len(groups)-1, 'dispatch after invalid audit')
            return result('INVALID_STOP')
        outcomes.append({'task_id': row['task_id'], 'profile': row['profile'], 'success': final['success'], 'attempt_id': final['attempt_id']})
        if len(outcomes)%3 == 0 and progress(outcomes)['futile']:
            w.require(index == len(groups)-1, 'dispatch after futility')
            return result('NUMERIC_FUTILITY')
    if live_handles:
        return result('LIVE_OR_UNSETTLED')
    return result('COMPLETE' if len(outcomes) == 30 else 'READY_FOR_ROOT_RELEASE',
                  None if len(outcomes) == 30 else plan['episodes'][len(groups)])
