import copy
import pytest
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as release


@pytest.fixture
def draft(monkeypatch):
    review = {'path': 'review', 'sha256': c.PROTOCOL_REVIEW_SHA}
    rows = c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)
    previous = {'cohort': c.DRAFT_RECOVERY_COHORT,
                'episodes': c.expected_rows(cohort=c.DRAFT_RECOVERY_COHORT),
                'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
                'protocol': 'old-protocol', 'accounting': 'old-accounting',
                'protocol_review': review}
    terminal = {'schema': 'n36r3-production-closure-terminal-reconciliation-v1',
                'release_enabled': False, 'ledger_prefix': {'sha256': 'retained'},
                'health_ledger_prefix': {'sha256': 'health-retained'}}
    ledger = {'schema': 'n36r3-accounting-draft-v1', 'cohort': c.DRAFT_N36R3_COHORT,
              'inherited_accounting': 'old-accounting', 'terminal_reconciliation': 'terminal',
              'retained_ledger_prefix': terminal['ledger_prefix'],
              'retained_health_ledger_prefix': terminal['health_ledger_prefix'],
              'allocation': 'allocation', 'all_prior_charges_retained': True,
              'N36R2_status': 'INVALID', 'N36R2_charges_retained': True,
              'protected_gpu_hours': c.CAPS['protected_gpu_hours'],
              'automatic_recoveries': 0, 'new_budget_authority': False,
              'current_headroom': None, 'release_enabled': False}
    protocol = {'schema': 'n36r3-operational-protocol-draft-v1',
                'cohort': c.DRAFT_N36R3_COHORT, 'previous_plan': 'previous',
                'inherited_protocol': 'old-protocol', 'inherited_protocol_review': review,
                'accounting': 'accounting', 'allocation': 'allocation', 'episodes': rows,
                'automatic_recoveries': 0, 'scientific_changes': False, 'release_enabled': False}
    values = {'previous': previous, 'terminal': terminal, 'accounting': ledger,
              'protocol': protocol, 'old-accounting': {},
              'old-protocol': {'episodes': previous['episodes']},
              'allocation': {'schema': 'n36r3-allocation-draft-v1',
                'cohort': c.DRAFT_N36R3_COHORT, 'episodes': rows,
                'automatic_recoveries': 0, 'allocation_is_not_authority': True,
                'release_enabled': False}}
    monkeypatch.setattr(c.w, 'read_ref', lambda r: {} if r == review else values[r])
    plan = {'schema': 'n36-release-draft-v1', 'cohort': c.DRAFT_N36R3_COHORT,
            'worktree': str(c.ROOT), 'frozen': False, 'release_enabled': False,
            'protocol': 'protocol', 'accounting': 'accounting', 'protocol_review': review}
    return plan, values


def test_finite_fresh_identity_preserves_science():
    rows = c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)
    old_keys = {r['episode_key'] for cohort in c.IDENTITIES if cohort != c.DRAFT_N36R3_COHORT
                for r in c.expected_rows(cohort=cohort)}
    assert len(rows) == 40 and not old_keys & {r['episode_key'] for r in rows}
    for old, new in zip(c.expected_rows(), rows):
        assert {k:v for k,v in old.items() if k not in ('iteration','episode_key')} == {
            k:v for k,v in new.items() if k not in ('iteration','episode_key')}
    with pytest.raises(ValueError):
        c.expected_rows(cohort='N36R3_NONPROGRESS_TANGENT_DEV_001315')


def test_structural_protocol(draft):
    plan, values = draft
    assert c.validate_n36r3_protocol(plan) == values['protocol']


@pytest.mark.parametrize('field,value', [('N36R2_charges_retained', False),
    ('all_prior_charges_retained', False), ('current_headroom', 40),
    ('new_budget_authority', True), ('automatic_recoveries', 1),
    ('retained_ledger_prefix', {}), ('protected_gpu_hours', {})])
def test_no_accounting_reset(draft, field, value):
    plan, values = draft
    values['accounting'][field] = value
    with pytest.raises(ValueError):
        c.validate_n36r3_protocol(plan)


def test_no_old_identity_alias(draft):
    plan, values = draft
    values['allocation']['episodes'] = c.expected_rows(cohort=c.DRAFT_RECOVERY_COHORT)
    with pytest.raises(ValueError):
        c.validate_n36r3_protocol(plan)


def test_admission_and_forged_release_fail(draft):
    plan, _ = draft
    with pytest.raises(ValueError, match='N36R3 draft only'):
        c.pre_dispatch({}, {}, now=None, stop_path='', cohort=c.DRAFT_N36R3_COHORT)
    forged = {**plan, 'schema': 'n36-released-plan-v1', 'frozen': True,
              'release_enabled': True, 'episodes': c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)}
    with pytest.raises(ValueError, match='N36R3 draft only'):
        release.validate_plan(forged)


def test_prepare_uses_disabled_protocol_and_fresh_manifests(draft, monkeypatch, tmp_path):
    from scripts import qd_ed_n36_prepare as p, qd_ed_n36_build as build
    plan, values = draft
    values['runtime'] = {'stage_recovered_error_condition': p.b.runner.E2_STAGE_CONDITION,
                         'frozen_stage_provider': {'backend': 'codex_cli'}}
    values['closure'] = {}
    monkeypatch.setattr(build, 'manifest', lambda ref: None)
    monkeypatch.setattr(p.b.closure, 'source_record', lambda *a: {'commit': 'unit-fixture'})
    monkeypatch.setattr(p.b, 'source_paths', lambda root: [])
    monkeypatch.setattr(p.b.closure, 'verify_runtime', lambda *a: None)
    calls = []
    monkeypatch.setattr(p, 'verify_disabled_n36r3_controller', lambda *a: calls.append(a))
    monkeypatch.setattr(p.b.runner, 'stage_overrides', lambda *a: None)
    monkeypatch.setattr(p.b, 'manifest', lambda plan, runtime, row: {'row': row})
    result = p.prepare(tmp_path/'draft', 'runtime', runtime_closure_ref='closure',
                       controller_semantics_ref='controller', native_build_ref='native',
                       recovery_protocol_ref='protocol')
    assert calls and result['release_enabled'] is False
    assert result['episodes'] == c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)
    assert len(result['expected_manifests']) == 40
    c.validate_draft(result)
    with pytest.raises(ValueError, match='already exists'):
        p.prepare(tmp_path/'draft', 'runtime', runtime_closure_ref='closure',
                  controller_semantics_ref='controller', native_build_ref='native',
                  recovery_protocol_ref='protocol')


@pytest.mark.parametrize('mutation', [None, 'approved', 'source', 'runtime'])
def test_controller_rebinding_cannot_invent_review(draft, monkeypatch, mutation):
    from scripts import qd_ed_n36_prepare as p, qd_ed_n34_controller as controller
    _, values = draft
    values['previous'].update(controller_semantics='historical-review', runtime='old-runtime',
                              runtime_closure='old-closure')
    values['old-closure'] = {}
    historical = {'module': 'robosuite.controller', 'source': {'sha256': 'unchanged'},
                  'instance': {'control_delta': True}, 'semantics': {'review': 'inherited'}}
    calls = []
    def verify(*args):
        calls.append(args)
        return historical
    monkeypatch.setattr(controller, 'verify_semantics', verify)
    candidate = {'schema': 'n36r3-controller-semantics-draft-v1',
                 'status': 'DISABLED_PENDING_ROOT_REVIEW', 'release_enabled': False,
                 'runtime': 'new-runtime', 'inherited_review': 'historical-review', **historical}
    values['candidate'] = candidate
    closure = {'modules': {'robosuite.controller': historical['source']},
               'required_after': ['robosuite.controller']}
    if mutation == 'approved': candidate['status'] = 'ROOT_REVIEWED'
    if mutation == 'source': closure['modules']['robosuite.controller'] = {'sha256': 'changed'}
    if mutation == 'runtime': candidate['runtime'] = 'old-runtime'
    if mutation is None:
        assert p.verify_disabled_n36r3_controller('candidate', 'new-runtime', closure,
                                                 values['protocol']) == candidate
    else:
        with pytest.raises(ValueError):
            p.verify_disabled_n36r3_controller('candidate', 'new-runtime', closure, values['protocol'])
    assert calls == [('historical-review', 'old-runtime', {})]
