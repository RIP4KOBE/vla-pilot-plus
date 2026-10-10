"""Finite N36R2 draft identity inheritance. Never dispatch or release authority.

The N36 and N36R1 anchors are unchanged. Production release and admission
explicitly reject this cohort pending independent review and future source work.
"""
from scripts import qd_ed_n23_worker as w, qd_ed_n36_contract as c

PRESERVED = [
    {'attempt_id': 'n36_dev_t00_c0_001147', 'gpu_seconds': 86.40354533703066},
    {'attempt_id': 'n36r1_dev_t00_c0_001203', 'gpu_seconds': 809.4826372319367},
]


def allocation(reference, root=c.ROOT):
    value = w.read_ref(reference)
    expected = {'schema': 'n36r2-allocation-draft-v1',
                'cohort': c.DRAFT_RECOVERY_COHORT,
                'episodes': c.expected_rows(root, cohort=c.DRAFT_RECOVERY_COHORT),
                'automatic_recoveries': 0, 'allocation_is_not_authority': True,
                'release_enabled': False}
    w.require(value == expected, 'exact finite N36R2 allocation draft')
    return value


def validate_protocol(plan):
    w.require(c.cohort(plan) == c.DRAFT_RECOVERY_COHORT, 'N36R2 draft cohort')
    value = w.read_ref(plan['protocol'])
    base_ref = value['inherited_protocol']
    w.require(base_ref['sha256'] == c.PROTOCOL_SHA, 'frozen scientific protocol anchor')
    base = w.read_ref(base_ref)
    w.require(base['episodes'] == c.expected_rows(plan['worktree'])
              and base['accounting']['sha256'] == c.ACCOUNTING_SHA,
              'original scientific protocol/accounting')
    w.require(plan['protocol_review']['sha256'] == c.PROTOCOL_REVIEW_SHA,
              'exact inherited protocol review')
    review = w.read_ref(plan['protocol_review'])
    w.require(review['protocol'] == base_ref and review['source'] == base['base_source']
              and review['status'] == 'PASS_PROTOCOL_DESIGN_FOR_ISOLATED_CPU_IMPLEMENTATION_ONLY',
              'inherited review covers original science only')
    ledger = w.read_ref(plan['accounting'])
    w.read_ref(base['accounting'])
    allocation(ledger['allocation'], plan['worktree'])
    expected_ledger = {'schema': 'n36r2-accounting-draft-v1',
                       'cohort': c.DRAFT_RECOVERY_COHORT,
                       'inherited_accounting': base['accounting'],
                       'allocation': ledger['allocation'],
                       'ledger_snapshot': ledger['ledger_snapshot'],
                       'preserved_attempts': PRESERVED,
                       'automatic_recoveries': 0, 'new_budget_authority': False,
                       'release_enabled': False}
    w.require(ledger == expected_ledger, 'exact N36R2 accounting inheritance')
    snapshot = w.read_ref(ledger['ledger_snapshot'])
    # This binds a read-only calculation, not authority or a live admission token.
    w.require(snapshot['dispatched'] == 504
              and snapshot['gpu_hours_consumed'] == 75.49265038509455
              and snapshot['preserved_attempts'] == PRESERVED
              and snapshot['protected_gpu_hours'] == c.CAPS['protected_gpu_hours']
              and snapshot['release_enabled'] is False, 'retained N36R2 accounting basis')
    expected = {'schema': 'n36r2-operational-protocol-draft-v1',
                'cohort': c.DRAFT_RECOVERY_COHORT, 'inherited_protocol': base_ref,
                'inherited_protocol_review': plan['protocol_review'],
                'accounting': plan['accounting'], 'allocation': ledger['allocation'],
                'episodes': c.plan_rows(plan), 'automatic_recoveries': 0,
                'scientific_changes': False, 'release_enabled': False}
    w.require(value == expected and plan['episodes'] == expected['episodes'],
              'exact structural N36R2 draft; science immutable')
    return value
