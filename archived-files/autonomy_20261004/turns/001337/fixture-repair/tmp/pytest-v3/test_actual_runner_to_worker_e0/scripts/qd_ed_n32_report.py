"""N32 draft reporting preserves unknown cells and charges, without promotion."""
from scripts import qd_ed_n32_contract as c


def summary(reconciliation, events):
    outcomes = reconciliation['outcomes']
    cells = {(x['task_id'], x['profile']): x['success'] for x in outcomes}
    totals = {arm: sum(x['success'] for x in outcomes if x['profile'] == arm) for arm in c.ARMS}
    complete = reconciliation['status'] == 'COMPLETE' and len(outcomes) == 30
    return {'status': reconciliation['status'],
            'matrix': [{'task_id': task, **{arm: cells.get((task, arm), 'Unknown') for arm in c.ARMS}} for task in range(10)],
            'prospective_dev_necessary_gate_met': complete and totals['N32'] >= max(5, totals['C0'], totals['Q0']),
            'validation_authorized': False, 'formal_authorized': False, 'release_enabled': False,
            'http_counters': 'Unknown', 'charges_and_health_events_preserved': events,
            'automatic_recoveries': 0}
