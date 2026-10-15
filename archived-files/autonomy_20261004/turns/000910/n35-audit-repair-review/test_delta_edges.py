import copy
import pytest
import torch
from test_n35_closure_intent_integration import episode, expected, _patch_core_imports, stub_adapter, mock_batch
from scripts import qd_ed_n35_native as audit


def test_additional_return_flags_and_order(tmp_path, monkeypatch, stub_adapter, mock_batch):
    metrics, original, compute, generic = episode(tmp_path, monkeypatch, stub_adapter, mock_batch,
        target=0., terminal_kind="terminated", terminal_prefix=4)
    trust = expected(original)
    for success, truncated in [(False, False), (False, True), (True, True)]:
        events = copy.deepcopy(original)
        for e in events:
            if e["global_step"] == 3 and e["event"] in ("pre_reset_outcome", "step_returned"):
                e["values"]["success"] = success
                if e["event"] == "step_returned": e["values"]["truncated"] = truncated
        result = generic(ev=events)
        assert result["accepted"], result["errors"]
        result = audit.audit_events("N35", metrics, events, compute, expected_runtime=trust)
        assert result["lifecycle"]["acknowledgements"] == 4
        assert result["lifecycle"]["resets"] == ["terminal"]
        print("ACCEPTED_FLAGS", success, truncated)
    for fault in ("nonterminal_ack_delayed", "missing_epoch", "extra_epoch", "initial_epoch", "success_mismatch"):
        events = copy.deepcopy(original)
        if fault == "nonterminal_ack_delayed":
            ack = next(e for e in events if e["event"] == "n35_step_acknowledged")
            marker = copy.deepcopy(ack); marker["event"] = "passive_review_marker"; marker["values"] = {}
            events.insert(events.index(ack), marker)
        elif fault in ("missing_epoch", "extra_epoch"):
            for e in events:
                if e["reset_sequence"] == 1: e["reset_sequence"] = 0 if fault == "missing_epoch" else 2
        elif fault == "initial_epoch":
            for e in events: e["reset_sequence"] += 1
        else:
            next(e for e in reversed(events) if e["event"] == "step_returned")["values"]["success"] = False
        for i,e in enumerate(events, 1): e["sequence"] = i
        with pytest.raises(ValueError): audit.audit_events("N35", metrics, events, compute, expected_runtime=trust)
        print("REJECTED_EDGE", fault)
    assert not torch.cuda.is_initialized()
