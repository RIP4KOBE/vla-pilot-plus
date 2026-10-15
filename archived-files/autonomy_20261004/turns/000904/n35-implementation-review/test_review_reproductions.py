import pytest
from test_n35_closure_intent_integration import episode, expected, _patch_core_imports, stub_adapter, mock_batch


def test_normal_terminated_return_is_accepted(tmp_path, monkeypatch, stub_adapter, mock_batch):
    from core.decision_evidence import DecisionEvidence
    from core.qd_closure_intent import ClosureIntentMemory
    from scripts import qd_ed_n35_native as audit
    original_outcome = DecisionEvidence.pre_reset_outcome
    original_return = DecisionEvidence.step_returned
    original_ack = ClosureIntentMemory.acknowledge
    def outcome(self, raw_obs, **kwargs):
        if self.global_step == 7:
            kwargs.update(terminated=True, success=True)
        return original_outcome(self, raw_obs, **kwargs)
    def returned(self, **kwargs):
        if self.global_step == 7:
            kwargs.update(terminated=True, truncated=False, success=True)
        return original_return(self, **kwargs)
    def acknowledge(self, **kwargs):
        if kwargs['step'] == 7:
            kwargs.update(terminated=True, truncated=False)
        return original_ack(self, **kwargs)
    monkeypatch.setattr(DecisionEvidence, 'pre_reset_outcome', outcome)
    monkeypatch.setattr(DecisionEvidence, 'step_returned', returned)
    monkeypatch.setattr(ClosureIntentMemory, 'acknowledge', acknowledge)
    metrics, events, compute, generic_audit = episode(tmp_path, monkeypatch, stub_adapter, mock_batch, target=0.)
    generic = generic_audit()
    assert generic['accepted'], generic['errors']
    print('GENERIC_AUDIT_ACCEPTED', generic['accepted'])
    for e in events:
        if e['global_step'] == 7 and e['event'] in ('pre_reset_outcome', 'automatic_reset_boundary', 'step_returned', 'n35_step_acknowledged', 'n35_memory_reset'):
            print('TERMINAL_EVENT', e['event'], 'reset_sequence', e['reset_sequence'])
    assert not __import__('torch').cuda.is_initialized()
    audit.audit_events('N35', metrics, events, compute, expected_runtime=expected(events))


def test_missing_terminal_reset_must_be_rejected(tmp_path, monkeypatch, stub_adapter, mock_batch):
    from scripts import qd_ed_n35_native as audit
    metrics, events, compute, generic_audit = episode(tmp_path, monkeypatch, stub_adapter, mock_batch, target=0.)
    trust = expected(events)
    assert generic_audit()['accepted']
    audit.audit_events('N35', metrics, events, compute, expected_runtime=trust)
    stripped = [e for e in events if not (e['event'] == 'n35_memory_reset' and e['values']['reason'] == 'terminal')]
    assert len(stripped) == len(events) - 1
    assert generic_audit(ev=stripped)['accepted']
    print('REMOVED_ONE_REAL_TERMINAL_RESET; generic audit still accepts')
    with pytest.raises(ValueError):
        result = audit.audit_events('N35', metrics, stripped, compute, expected_runtime=trust)
        print('N35_AUDIT_ACCEPTED_MISSING_RESET', result['lifecycle'])
