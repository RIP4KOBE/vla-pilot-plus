"""Bounded prospective support for turn 001467; creates no spend authority.

The two pinned, disabled drafts describe retained charges and immutable science.
They are inputs to a future independent review/adoption, never a release token.
"""
from scripts import qd_ed_n23_worker as w, qd_ed_n36_contract as c

PROTOCOL_SHA = '90b2704255fa1d5a47a762fe31df37e8ba88697dc72f5a9d43c25bf8f43a8170'
ACCOUNTING_SHA = 'a60c3be578ea6ce48f37ee73205f06e391859899bf96a74c1509017880a0e43d'
PREPARATION_ID = 'n36_healthcheck_n36r4_preparation_001467'
KIND = 'n36r4_resource_preparation_v1'
HEALTH = {'preparation_id': PREPARATION_ID, 'max_invocations': 41,
          'timeout_seconds': 20, 'cleanup_seconds': 40,
          'per_invocation_seconds': 60, 'aggregate_seconds': 1800}
ARITHMETIC_KEYS = ('retained_attempts', 'new_primary_attempts', 'prospective_attempts',
                   'remaining_attempts_after', 'automatic_recoveries', 'buckets',
                   'protected_remaining_attempts', 'protected_remaining_gpu_hours',
                   'hours', 'seconds', 'health')


def validate_protocol(plan):
    from scripts import qd_ed_n36r3_admission as gate
    w.require(c.cohort(plan) == c.DRAFT_N36R4_COHORT, 'exact N36R4 identity')
    owner = gate.owner_root(plan)
    c.validate_stop_binding(plan)
    output_suffix = ('autonomy_20261004/turns/001467/'
                     'recovery-preparation/prospective-artifacts-001467')
    expected_output = owner.parent / output_suffix
    w.require(plan['artifact_root'] == str(expected_output)
              and expected_output.resolve() == gate.SOURCE.parents[2] / output_suffix
              and (expected_output.parent / 'prospective-reports-001467').resolve()
                  == (gate.SOURCE.parents[2] / output_suffix).parent / 'prospective-reports-001467',
              'N36R4 exact output routing')
    w.require(plan['protocol']['sha256'] == PROTOCOL_SHA
              and plan['accounting']['sha256'] == ACCOUNTING_SHA,
              'N36R4 exact prospective protocol/accounting drafts required')
    protocol = w.read_ref(plan['protocol'])
    ledger = w.read_ref(plan['accounting'])
    allocation = w.read_ref(protocol['allocation'])
    w.require(protocol['cohort'] == ledger['cohort'] == c.DRAFT_N36R4_COHORT
              and protocol['accounting'] == plan['accounting']
              and protocol['scientific_protocol_review'] == plan['protocol_review']
              and plan['protocol_review']['sha256'] == c.PROTOCOL_REVIEW_SHA
              and protocol['terminal_reconciliation'] == ledger['terminal_reconciliation']
              and allocation == {'cohort': c.DRAFT_N36R4_COHORT,
                  'episodes': c.plan_rows(plan), 'limits': c.LIMITS,
                  'accounting': plan['accounting'], 'release_enabled': False}
              and plan['episodes'] == c.plan_rows(plan)
              and plan['limits'] == c.LIMITS and plan['worker_contract'] == c.WORKER_CONTRACT
              and plan['deadline'] == c.DEADLINE,
              'N36R4 immutable science/allocation binding differs')
    w.require(ledger['retained_snapshot']['dispatched'] == 506
              and ledger['retained_snapshot']['reserved_attempts'] == 506
              and ledger['retained_snapshot']['gpu_hours_consumed'] == 75.60616276674473
              and ledger['hours']['retained_admission_margin'] == '0.23357169027962'
              and ledger['caps'] == c.CAPS and ledger['automatic_recoveries'] == 0
              and ledger['draft_only'] is True and ledger['root_adopted'] is False
              and ledger['release_enabled'] is protocol['release_enabled'] is False,
              'N36R4 retained accounting is a disabled draft only')
    return protocol


def validate_accounting(plan, authority, accounting, snapshot):
    """Match fresh root adoption to the exact retained baseline, not old headroom."""
    validate_protocol(plan)
    ledger = w.read_ref(plan['accounting'])
    fields = ('path', 'bytes', 'sha256')
    actual = {name: {key: anchor[key] for key in fields}
              for name, anchor in authority['ledger_prefixes'].items()}
    retained = {name: {key: anchor[key] for key in fields}
                for name, anchor in ledger['retained_ledger_prefixes'].items()}
    w.require(actual == retained and snapshot == ledger['retained_snapshot']
              and accounting['arithmetic'] == {key: ledger[key] for key in ARITHMETIC_KEYS},
              'N36R4 exact retained prefixes/snapshot/margin/arithmetic required')


def margin_reference(plan):
    # A bounded, hash-checked chain to the existing normalization, not a newly
    # synthesized allowance. retained_margin still verifies its original prefix.
    from scripts import qd_ed_n36r3_admission as gate
    protocol = validate_protocol(plan)
    previous = w.read_ref(protocol['previous_plan'])
    w.require(c.cohort(previous) == c.DRAFT_N36R3_COHORT, 'N36R4 predecessor identity')
    reference = gate.margin_reference(previous)
    w.require(reference['sha256'] == c.ACCOUNTING_SHA, 'N36R4 retained margin reference')
    return reference
