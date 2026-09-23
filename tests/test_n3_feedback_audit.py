"""Pure synthetic native-event fixtures for N3 audit; not runtime evidence."""
from collections import defaultdict
import copy

import pytest
import torch

from scripts import audit_decision_evidence as audit


def fixture(*, start=0, previous=None, terminal=False, eligible=True, committed=True, count=8):
    kinds = defaultdict(list)
    events = []
    def event(kind, **values):
        row = {"sequence": len(events) + 1, "event": kind, "values": values, "global_step": values.get("global_step", start)}
        events.append(row); kinds[kind].append(row)
        return row
    native = torch.linspace(-.3, .2, 64 * 128).reshape(1, 64, 128).bfloat16()
    projection = torch.linspace(-.04, .06, 27).reshape(1, 9, 3).bfloat16()
    origin = torch.tensor([.024132, -.014231, .051321], dtype=torch.float32)
    raw = torch.tensor([-.25], dtype=torch.bfloat16)
    identity = {"source_text_sha256": "a" * 64}
    tracker = {"instance_id": 13, "generation": 1, "targets": {"2": {"valid": eligible, "status": "tracked"}}}
    context = event("decision_context", global_step=start, stage=1, providers=[identity])
    origin_event = event("projection_origin", source_eef_position=origin)
    score = event("scoring_inputs", samples=native, projected_xyz=projection,
        projection_origin_sequences=[origin_event["sequence"]], scoring_scope={"role": "canonical_initial"})
    event("scoring_aggregate", scoring_batch_id=score["sequence"], aggregate_before_reward_mode=raw)
    event("effective_quality", scoring_batch_id=score["sequence"], quality=raw if previous is None else raw + 1,
          provider_identity=identity, target_index=2)
    current = {"episode_generation": 0, "global_step": start, "stage": 1,
               "provider_identity": identity, "target_index": 2, "registry_instance_id": 13,
               "registry_generation": 1, "target_valid": eligible, "target_status": "tracked", "tracker_snapshot": tracker}
    selected = {"selected_native_sha256": audit._native_sha(native[0]), "projection": audit._native_record(projection[0]),
                "source_origin": audit._native_record(origin), "raw_provider_quality": audit._native_record(raw[0]),
                "start_global_step": start, "eligible": eligible}
    event("execution_feedback_selection", active=previous is not None, selected=selected, context=current,
          previous={} if previous is None else {k: v for k, v in previous["completed"].items() if k != "context"})
    final = {"selected_latent": native, "selected_raw_provider_quality": raw.item()}
    event("execution_feedback_commit", global_step=start, committed=committed,
          history_reason="fixture", selected_native_sha256=selected["selected_native_sha256"] if committed else None)
    actions = torch.arange(56, dtype=torch.float32).reshape(1, 8, 7) / 99
    event("decision_committed", execution_horizon=8, action_chunk=actions)
    for i in range(count):
        event("action_dispatch", global_step=start + i, execution_index=i + 1)
        event("executed_action", global_step=start + i, action_numpy=actions[0, i])
        endpoint = torch.tensor([.131243 + i / 19, -.078273421, .02346576], dtype=torch.float64)
        event("pre_reset_outcome", global_step=start + i, observation={"robot0_eef_pos": endpoint})
        terminated = terminal and i == count - 1
        completed = None
        if i == 7 and not terminated:
            residual = (endpoint - origin.double()) - (projection[0, 8].double() - projection[0, 0].double())
            completed = {"context": current, "selected_native_sha256": selected["selected_native_sha256"],
                         "start_global_step": start, "end_global_step": start + i, "ack_count": 8,
                         "feedback_was_active": previous is not None, "terminated": False, "truncated": False,
                         "projection": selected["projection"], "source_origin": selected["source_origin"],
                         "actual_endpoint": audit._native_record(endpoint), "residual": audit._native_record(residual)}
        if committed:
            event("execution_feedback_ack", global_step=start + i, execution_index=i + 1,
                  action=actions[0, i], actual_endpoint=endpoint.clone(), completed=completed,
                  selected_native_sha256=selected["selected_native_sha256"], terminated=terminated, truncated=False)
        event("step_returned", global_step=start + i, terminated=terminated, truncated=False)
    return kinds, context, final, events, previous


def test_exact_native_no_history_then_active_and_terminal_partial():
    first = audit._audit_n3_feedback(*fixture())
    assert first["completed"]["ack_count"] == 8
    second = audit._audit_n3_feedback(*fixture(start=8, previous=first))
    assert second["completed"]["feedback_was_active"]
    assert audit._audit_n3_feedback(*fixture(start=16, previous=second, terminal=True, count=3)) is None
    assert audit._audit_n3_feedback(*fixture(eligible=False, committed=False)) is None


@pytest.mark.parametrize("corruption,code", [
    ("endpoint", "n3_ack_not_native_pre_reset_endpoint"),
    ("origin", "n3_selected_projection_origin_or_raw_mismatch"),
    ("selected", "n3_selected_native_identity_mismatch"),
    ("before8", "n3_completed_before_eight_or_terminal"),
    ("action", "n3_ack_not_actual_committed_action"),
    ("previous", "n3_previous_not_actual_completed_ack"),
    ("no_previous", "n3_active_without_complete_predecessor"),
    ("residual", "n3_completed_residual_or_identity_mismatch"),
    ("registry", "n3_feedback_continuity_mismatch"),
    ("missing_ack", "n3_ack_coverage_mismatch"),
])
def test_corrupted_native_feedback_is_rejected(corruption, code):
    first = audit._audit_n3_feedback(*fixture())
    args = list(fixture(start=8, previous=first))
    kinds = args[0]
    selected = kinds["execution_feedback_selection"][0]["values"]
    if corruption == "endpoint": kinds["execution_feedback_ack"][0]["values"]["actual_endpoint"] = torch.zeros(3, dtype=torch.float64)
    if corruption == "origin": selected["selected"]["source_origin"] = audit._native_record(torch.zeros(3))
    if corruption == "selected": selected["selected"]["selected_native_sha256"] = "0" * 64
    if corruption == "before8": kinds["execution_feedback_ack"][0]["values"]["completed"] = {}
    if corruption == "action": kinds["execution_feedback_ack"][0]["values"]["action"] = torch.zeros(7)
    if corruption == "previous": selected["previous"]["actual_endpoint"] = audit._native_record(torch.zeros(3))
    if corruption == "no_previous": args[-1] = None
    if corruption == "residual": kinds["execution_feedback_ack"][-1]["values"]["completed"]["residual"] = audit._native_record(torch.zeros(3, dtype=torch.float64))
    if corruption == "registry":
        selected["context"]["registry_instance_id"] = 22
        selected["context"]["tracker_snapshot"]["instance_id"] = 22
    if corruption == "missing_ack": kinds["execution_feedback_ack"].pop()
    with pytest.raises(audit.AuditFailure, match=code):
        audit._audit_n3_feedback(*args)


def test_explicit_inactive_missing_endpoint_clear_stays_unknown_without_history():
    args = fixture()
    kinds = args[0]
    kinds["execution_feedback_ack"][:] = kinds["execution_feedback_ack"][:1]
    ack = kinds["execution_feedback_ack"][0]["values"]
    ack["actual_endpoint"] = None
    ack["history_reason"] = "actual_endpoint_missing_or_invalid"
    assert audit._audit_n3_feedback(*args) is None
    ack.pop("history_reason")
    with pytest.raises(audit.AuditFailure, match="n3_ack_coverage_mismatch"):
        audit._audit_n3_feedback(*args)


def test_terminal_guided_ack_never_requires_usable_post_reset_p8():
    previous = audit._audit_n3_feedback(*fixture())
    for length in (3, 8):
        args = fixture(start=8, previous=previous, terminal=True, count=length)
        final_ack = args[0]["execution_feedback_ack"][-1]
        final_ack["values"]["actual_endpoint"] = None
        final_ack["reset_sequence"] = 1
        args[0]["pre_reset_outcome"][-1]["reset_sequence"] = 0
        args[0]["step_returned"][-1]["reset_sequence"] = 1
        assert audit._audit_n3_feedback(*args) is None
        final_ack["values"]["completed"] = previous["completed"]
        with pytest.raises(audit.AuditFailure, match="n3_completed_before_eight_or_terminal"):
            audit._audit_n3_feedback(*args)
