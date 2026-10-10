"""Fresh Dev denominators and necessary gate, never promotion or efficacy from CPU."""
from scripts import qd_ed_n36_contract as c


def summary(reconciliation, events):
    from scripts.qd_ed_n23_worker import require
    require(reconciliation.get('purpose') != 'engineering_diagnostic_only'
            and not any(event.get('purpose') == 'engineering_diagnostic_only'
                        or str(event.get('cohort', '')).startswith('N36_ENGINEERING_')
                        or str(event.get('identity', {}).get('iteration', '')).startswith('N36_ENGINEERING_')
                        for event in events), 'engineering evidence is ineligible for scientific aggregation')
    outcomes=reconciliation['outcomes']
    cells={(x['task_id'],x['profile']):x['success'] for x in outcomes}
    totals={arm:sum(x['success'] for x in outcomes if x['profile']==arm) for arm in c.ARMS}
    denominators={arm:sum(x['profile']==arm for x in outcomes) for arm in c.ARMS}
    complete=reconciliation['status']=='COMPLETE' and len(outcomes)==40
    return {'status':reconciliation['status'],'successes':totals,'valid_denominators':denominators,
        'planned_denominators':{arm:10 for arm in c.ARMS},
        'matrix':[{'task_id':t,**{arm:cells.get((t,arm),'Unknown') for arm in c.ARMS}} for t in range(10)],
        'prospective_dev_necessary_gate_met':complete and totals['N36']>=max(5,totals['C0'],totals['Q0'],totals['N34']),
        'mechanism_review_required':True,'independent_review_required':True,
        'target_met':False,'validation_authorized':False,'formal_authorized':False,'release_enabled':False,
        'charges_and_health_events_preserved':events,'automatic_recoveries':0,'http_counters':'Unknown'}
