"""One prospective identity amendment; no approval, allocation or science changes.

The immutable protocol remains the scientific authority. These exact structural
wrappers can acquire execution authority only through the detached root release.
No digest supplied by a plan can replace the original trust anchors.
"""
from scripts import qd_ed_n23_worker as w, qd_ed_n36_contract as c

ALLOCATION_SHA = 'fe8d16d01e56a236153e73801e4914b830edde2dc668ac9c33dc1549c10f5358'
PRESERVED_ATTEMPT = {'attempt_id': 'n36_dev_t00_c0_001147',
                     'gpu_seconds': 86.40354533703066}


def allocation(reference, root=c.ROOT):
    w.require(reference['sha256'] == ALLOCATION_SHA, 'exact N36R1 allocation proposal')
    proposal = w.read_ref(reference)
    rows = c.expected_rows(root, cohort=c.RECOVERY_COHORT)
    w.require([a['prospective_row'] for a in proposal['attempts']] == rows
              and proposal['cohort'] == c.RECOVERY_COHORT
              and proposal['automatic_recoveries'] == 0
              and proposal['allocation_is_not_authority'] is True,
              'N36R1 allocation is identities only')
    return proposal


def accounting(reference, root=c.ROOT):
    amendment = w.read_ref(reference)
    base_ref = amendment['inherited_accounting']
    w.require(base_ref['sha256'] == c.ACCOUNTING_SHA, 'frozen accounting anchor')
    w.read_ref(base_ref)
    allocation(amendment['allocation'], root)
    expected = {'schema': 'n36r1-accounting-inheritance-v1',
                'cohort': c.RECOVERY_COHORT, 'inherited_accounting': base_ref,
                'allocation': amendment['allocation'],
                'preserved_attempt': PRESERVED_ATTEMPT,
                'automatic_recoveries': 0, 'new_budget_authority': False}
    w.require(amendment == expected, 'exact N36R1 accounting inheritance')
    return amendment


def validate_protocol(plan):
    """Validate an unsigned proposal too; this does not confer release authority."""
    w.require(c.cohort(plan) == c.RECOVERY_COHORT, 'N36R1 protocol cohort')
    amendment = w.read_ref(plan['protocol'])
    base_ref = amendment['inherited_protocol']
    w.require(base_ref['sha256'] == c.PROTOCOL_SHA, 'frozen scientific protocol anchor')
    base = w.read_ref(base_ref)
    w.require(base['episodes'] == c.expected_rows(plan['worktree'])
              and base['accounting']['sha256'] == c.ACCOUNTING_SHA,
              'original scientific protocol/accounting')
    w.require(plan['protocol_review']['sha256'] == c.PROTOCOL_REVIEW_SHA,
              'exact inherited root protocol review')
    review = w.read_ref(plan['protocol_review'])
    w.require(review['protocol'] == base_ref and review['source'] == base['base_source']
              and review['status'] == 'PASS_PROTOCOL_DESIGN_FOR_ISOLATED_CPU_IMPLEMENTATION_ONLY',
              'inherited review covers original science only')
    ledger = accounting(plan['accounting'], plan['worktree'])
    w.require(ledger['inherited_accounting'] == base['accounting'], 'accounting inheritance differs')
    expected = {'schema': 'n36r1-operational-protocol-v1', 'cohort': c.RECOVERY_COHORT,
                'inherited_protocol': base_ref, 'inherited_protocol_review': plan['protocol_review'],
                'accounting': plan['accounting'], 'allocation': ledger['allocation'],
                'episodes': c.plan_rows(plan), 'automatic_recoveries': 0,
                'scientific_changes': False}
    w.require(amendment == expected and plan['episodes'] == expected['episodes'],
              'exact structural N36R1 amendment; science immutable')
    return amendment


def validate_authority(plan, authority):
    protocol = validate_protocol(plan)
    w.require(authority['cohort'] == c.RECOVERY_COHORT
              and authority['protocol'] == plan['protocol']
              and authority['accounting'] == protocol['accounting']
              and authority['amendment'] == plan['accounting'],
              'N36R1 authority protocol/accounting/amendment refs differ')


def preserve_charge(events):
    """Keep the failed primary charged; root prefix validation remains mandatory."""
    key = PRESERVED_ATTEMPT['attempt_id']
    group = [e for e in events if e.get('attempt_id') == key or e.get('episode_key') == key]
    w.require([e['event'] for e in group] == ['reserved', 'dispatched', 'aborted']
              and all(e.get('attempt_id') == e.get('episode_key') == key for e in group)
              and group[-1].get('gpu_process_wall_seconds') == PRESERVED_ATTEMPT['gpu_seconds'],
              'original invalid attempt and exact charge must remain')


def resource_events(plan, resources):
    """Select the complete fresh healthcheck histories, rejecting disguised rows."""
    permitted = {'n36_healthcheck_' + row['episode_key'] for row in c.plan_rows(plan)}
    permitted.add('n36_healthcheck_n36r1_preparation_001203')
    selected = {e['resource_id'] for e in resources
                if e.get('cohort') == c.RECOVERY_COHORT
                or e.get('kind') == 'n36r1_resource_preparation_v1'
                or str(e.get('resource_id', '')).startswith('n36_healthcheck_n36r1')}
    local = [e for e in resources if e['resource_id'] in selected]
    binding = c.operational_binding(plan)
    w.require(all(e['resource_id'] in permitted
                  and e.get('kind') == 'n36r1_resource_preparation_v1'
                  and all(e.get(k) == v for k, v in binding.items()) for e in local),
              'N36R1 healthcheck identity/protocol/accounting binding')
    return local
