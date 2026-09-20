"""Feedback must correct predictions without inventing counterfactual outcomes."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from mode_gate.incidents import IncidentMemory, VerifierDecisionRecord
from mode_gate.io_utils import sha256_file
from mode_gate.verifier import CandidateVerifierInput, save_verifier_input, load_verifier_input
from mode_gate.verifier_feedback import derive_verifier_feedback, publish_verifier_feedback
from mode_gate.verifier_training import (build_verifier_examples, validate_independent_groups,
    train_verifier, VerifierTrainingConfig, record_verifier_training_usage)

THREAD = "01a0893c-15b0-7203-881c-de3c5bcee058"


def decision(memory, *, identity="r", proposal="EXPANSION", route="EXECUTE", remaining=2,
             decision_rule="head_argmax"):
    feature = save_verifier_input(memory.root / f"{identity}.npz", CandidateVerifierInput(
        np.random.default_rng(len(identity)).normal(size=2048).astype(np.float32),
        np.ones((3, 4, 15), dtype=np.float32), np.zeros((0, 15), np.float32),
        remaining, context_id=identity, backbone_id="frozen-v44", decision_step=30),
        metadata={"policy_id": "p", "snapshot_id": "snapshot-" + identity})
    row = VerifierDecisionRecord(identity, "context-" + identity, "p", "snapshot-" + identity,
        hashlib.sha256(identity.encode()).hexdigest(), "", route, proposal,
        (0., 1.) if proposal == "EXPANSION" else (1., 0.), .8,
        decision_rule, "learned_verifier", 1, remaining, retry_index=50 - remaining,
        verifier_feature_path=str(feature), provenance={"episode_id": "episode-" + identity})
    memory.record_decision(row)
    memory.record_fact(episode_id=row.provenance["episode_id"], context_id=identity,
        kind="decision_context", payload={"step": 30, "policy_id": "p", "route": route,
            "retry_index": row.retry_index, "remaining_budget": remaining,
            "verifier_proposal": proposal, "verifier_id": "old-head"})
    return row


def continuation(memory, row, count, *, success_at=None, policy_id="p", mutate=None):
    retry = row.retry_index
    episode_id = row.provenance["episode_id"]
    for i in range(1, count + 1):
        chunk = (i - 1) // 10
        context = row.record_id if not chunk else f"{row.record_id}-chunk-{chunk}"
        if i % 10 == 1:
            if chunk:
                memory.record_fact(episode_id=episode_id, context_id=context, kind="decision_context",
                    payload={"step": 30 + i - 1, "policy_id": policy_id, "route": row.route,
                             "retry_index": retry, "remaining_budget": 50 - retry})
            retry += int(row.route == "RE-STEER")
        payload = {"step": 30 + i, "policy_id": policy_id, "native_success": i == success_at,
                   "retry_index": retry, "action_osc": [0.] * 7, "observed_pose": [0.] * 7}
        if mutate:
            mutate(i, payload)
        memory.record_fact(episode_id=episode_id, context_id=context, kind="executed_step", payload=payload)


def annotation(row, feedback, **kwargs):
    return {"record_id": row.record_id, "episode_id": row.provenance["episode_id"],
            "label_version": row.label_version, "label": feedback["target_label"],
            "reason": "根据同一 policy 的连续实际执行纠正原判断", "evidence_refs": feedback["evidence_refs"],
            "use_for_training": True, "source": "observed_verifier_feedback", "weight": 1.5,
            "feedback_id": feedback["feedback_id"], "decision_reward": feedback["decision_reward"],
            "planner_provenance": {"planner_thread_id": THREAD}, **kwargs}


@pytest.mark.parametrize("proposal,route,reward", [
    ("EXPANSION", "EXECUTE", -1), ("EXPANSION", "RE-STEER", -1), ("RE-STEER", "RE-STEER", 1)])
def test_native_success_corrects_or_rewards_original_proposal(tmp_path, proposal, route, reward):
    memory = IncidentMemory(tmp_path)
    row = decision(memory, proposal=proposal, route=route)
    original = memory.decisions.path.read_bytes()
    input_hash = sha256_file(row.verifier_feature_path)
    assert derive_verifier_feedback(memory)[0]["status"] == "PENDING"
    continuation(memory, row, 17, success_at=17)
    first = publish_verifier_feedback(memory)
    feedback = first["observed"][0]
    assert feedback["target_label"] == "RE-STEER" and feedback["decision_reward"] == reward
    assert feedback["continuation_steps"] == 17 and feedback["maximum_continuation_steps"] == 20
    assert feedback["verifier_id"] == "old-head" and feedback["actual_initial_route"] == route
    assert publish_verifier_feedback(memory)["new_observed"] == 0 and first["new_observed"] == 1
    assert memory.decisions.path.read_bytes() == original
    assert sha256_file(row.verifier_feature_path) == input_hash
    assert not list(memory.experiences.interpretations.iter_valid())  # Planner still owns labels.
    stored = memory.annotate(annotation(row, feedback))
    assert stored["label"] == "RE-STEER" and stored["weight"] > 0
    assert load_verifier_input(row.verifier_feature_path).executed_history.shape == (0, 15)


@pytest.mark.parametrize("proposal,reward", [("EXPANSION", 1), ("RE-STEER", -1)])
def test_only_actual_remaining_retry_exhaustion_supports_failure(tmp_path, proposal, reward):
    memory = IncidentMemory(tmp_path)
    row = decision(memory, proposal=proposal, route="RE-STEER")
    continuation(memory, row, 20)
    feedback = derive_verifier_feedback(memory)[0]
    assert feedback["target_label"] == "EXPANSION" and feedback["decision_reward"] == reward
    assert feedback["reason"] == "observed_remaining_retry_chunks_exhausted"


@pytest.mark.parametrize("success_at,observed", [(20, True), (21, False)])
def test_success_horizon_counts_actual_steps_not_unchanged_retry_index(tmp_path, success_at, observed):
    memory = IncidentMemory(tmp_path)
    row = decision(memory, route="EXECUTE")
    continuation(memory, row, success_at, success_at=success_at)
    feedback = derive_verifier_feedback(memory)[0]
    assert (feedback["status"] == "OBSERVED") is observed
    if not observed:
        assert feedback["target_label"] is None and feedback["decision_reward"] is None
    # Out-of-feedback-horizon native success is still task success, never altered.
    assert list(memory.experiences.facts.iter_valid())[-1]["payload"]["native_success"] is True


@pytest.mark.parametrize("problem", ["gap", "duplicate", "retry_reset", "changed_policy", "non_native_success",
    "missing_action", "excluded", "early_stop", "terminal", "restore", "route_only", "unexecuted_decision"])
def test_insufficient_or_wrong_lineage_never_gets_automatic_reward(tmp_path, problem):
    memory = IncidentMemory(tmp_path)
    row = decision(memory, route="EXPANSION" if problem == "route_only" else "RE-STEER")
    def mutate(i, payload):
        if i == 2:
            if problem == "gap":
                payload["step"] += 1
            if problem == "duplicate":
                payload["step"] -= 1
            if problem == "retry_reset":
                payload["retry_index"] = 0
            if problem == "missing_action":
                payload.pop("action_osc")
        if problem == "non_native_success":
            payload.update(native_success=False, success=True, planner_success=True, reward=1.)
    kind = {"terminal": "rollout_completed", "restore": "snapshot_restored",
            "early_stop": "retry_outcome", "unexecuted_decision": "decision_context"}.get(problem)
    if kind:
        memory.record_fact(episode_id=row.provenance["episode_id"], context_id="replacement",
            kind=kind, payload={"censored": True, "native_success": False,
                                "policy_id": "p", "step": 30, "route": "RE-STEER"})
    continuation(memory, row, 5, success_at=5, mutate=mutate,
                 policy_id="merged-p" if problem == "changed_policy" else "p")
    if problem == "excluded":
        memory.record_fact(episode_id=row.provenance["episode_id"], context_id=row.record_id,
            kind="formal_attempt_excluded_by_protocol_update", payload={"use_for_training": False})
    result = derive_verifier_feedback(memory)[0]
    assert result["status"] in {"PENDING", "CENSORED"} and result["decision_reward"] is None
    assert not publish_verifier_feedback(memory)["observed"]


def test_different_episode_success_and_non_head_routes_are_not_rewards(tmp_path):
    memory = IncidentMemory(tmp_path)
    row = decision(memory)
    other = decision(memory, identity="other", proposal=None, route="EXECUTE", decision_rule="fixed_budget_50")
    continuation(memory, other, 1, success_at=1)
    result = derive_verifier_feedback(memory)
    assert len(result) == 1 and result[0]["record_id"] == row.record_id
    assert result[0]["status"] == "PENDING"


@pytest.mark.parametrize("change", [{"label": "EXPANSION"}, {"decision_reward": 1},
    {"feedback_id": "invented"}, {"feedback_id": None}, {"evidence_refs": []},
    {"weight": -1.}, {"weight": float("nan")}, {"weight": float("inf")}])
def test_annotation_revalidates_reward_and_never_uses_negative_loss_weights(tmp_path, change):
    memory = IncidentMemory(tmp_path)
    row = decision(memory)
    continuation(memory, row, 1, success_at=1)
    feedback = derive_verifier_feedback(memory)[0]
    with pytest.raises(ValueError):
        memory.annotate(annotation(row, feedback, **change))


def test_feedback_and_ordinary_labels_mix_without_future_inputs(tmp_path):
    torch.set_num_threads(1)
    memory = IncidentMemory(tmp_path / "incidents")
    corrected = decision(memory, identity="corrected")
    continuation(memory, corrected, 3, success_at=3)
    feedback = publish_verifier_feedback(memory)["observed"][0]
    a = memory.annotate(annotation(corrected, feedback))
    plain = decision(memory, identity="plain")
    fact = memory.record_fact(episode_id=plain.provenance["episode_id"], context_id=plain.record_id,
        kind="native_outcome", payload={"native_success": False})
    ordinary = annotation(plain, feedback, label="EXPANSION", evidence_refs=[{"event_id": fact["event_id"]}],
                          source="planner_video_analysis", weight=.7)
    ordinary.pop("feedback_id")
    ordinary.pop("decision_reward")
    b = memory.annotate(ordinary)
    check = decision(memory, identity="independent-check")
    continuation(memory, check, 1, success_at=1)
    c = memory.annotate(annotation(check, derive_verifier_feedback(memory, record_ids=[check.record_id])[0]))
    request = memory.experiences.request_training(train_annotation_ids=[a["annotation_id"], b["annotation_id"]],
        independent_annotation_ids=[c["annotation_id"]], reason="普通标签和纠错信号联合训练",
        planner_provenance={"planner_thread_id": THREAD})
    inputs_before = {x: sha256_file(memory.root / f"{x}.npz") for x in (corrected.record_id, plain.record_id, check.record_id)}
    rows = build_verifier_examples(memory, policy_id="p", request=request)
    by_id = {x.record_id: x for x in rows}
    assert by_id[corrected.record_id].target_class == 0 and by_id[plain.record_id].target_class == 1
    assert by_id[corrected.record_id].weight == 1.5 and by_id[plain.record_id].weight == .7
    for bad in (-1., float("nan"), float("inf")):
        with pytest.raises(ValueError, match="weight"):
            validate_independent_groups([replace(rows[0], weight=bad)])
    with pytest.raises(ValueError, match="leakage"):
        validate_independent_groups([by_id[corrected.record_id], replace(by_id[check.record_id], group_id=by_id[corrected.record_id].group_id)])
    result = train_verifier(rows, policy_id="p", output_root=tmp_path / "head",
        config=VerifierTrainingConfig(device="cpu", max_epochs=2, patience=2, batch_size=2),
        reviewer=lambda metrics: {"accept": False, "reason": "混合训练连通性测试，不部署", "planner_provenance": {"planner_thread_id": THREAD}})
    record_verifier_training_usage(memory, result, rows, request_id=request["event_id"])
    usage = list(memory.experiences.training_usage.iter_valid())[0]
    assert len(usage["observed_feedback"]) == 2 and len(usage["examples"]) == 3
    assert {x["decision_reward"] for x in usage["observed_feedback"]} == {-1}
    assert result.metrics["train"]["contexts"] == 2 and result.metrics["independent"]["contexts"] == 1
    manifest = json.loads((Path(result.artifact_root) / "manifest.json").read_text())
    assert manifest["metadata"]["backbone_frozen"] is True and not result.gate.passed
    assert inputs_before == {x: sha256_file(memory.root / f"{x}.npz") for x in inputs_before}
    # An append-only exclusion invalidates derived feedback at training selection,
    # even if an old annotation or ledger record still contains a reward.
    memory.record_fact(episode_id=corrected.provenance["episode_id"], context_id=corrected.record_id,
        kind="formal_attempt_excluded_by_protocol_update", payload={"use_for_training": False})
    with pytest.raises(ValueError, match="invalidated"):
        build_verifier_examples(memory, policy_id="p", request=request)


def test_planner_can_discover_and_select_feedback_without_automatic_training(tmp_path):
    from mode_gate.experience_planner import ExperiencePlanner
    memory = IncidentMemory(tmp_path)
    row = decision(memory)
    continuation(memory, row, 2, success_at=2)
    commands = [("search", {"collection": "verifier_feedback"}), ("finish", {"reason": "保留证据，暂不 retrain"})]
    class Client:
        def request(self, **kwargs):
            assert "decision_reward=+1" in kwargs["prompt"]
            if len(commands) == 1:
                assert "native_success_within_remaining_horizon" in kwargs["prompt"]
            action, arguments = commands.pop(0)
            return SimpleNamespace(text=json.dumps({"action": action, "arguments": arguments}),
                                   planner_metadata={"planner_thread_id": THREAD})
    result = ExperiencePlanner(memory, client=Client()).run(purpose="verifier_training", current={"policy_id": "p"})
    assert result["training_request"] is None and not commands
    assert not list(memory.experiences.interpretations.iter_valid())


@pytest.mark.parametrize("change", [{"remaining_budget": 1}, {"decision_step": 31}])
def test_feedback_cannot_train_on_rewritten_budget_or_future_input(tmp_path, change):
    memory = IncidentMemory(tmp_path)
    row = decision(memory)
    continuation(memory, row, 1, success_at=1)
    note = memory.annotate(annotation(row, derive_verifier_feedback(memory)[0]))
    request = memory.experiences.request_training(train_annotation_ids=[note["annotation_id"]],
        independent_annotation_ids=[], reason="连通性测试", planner_provenance={"planner_thread_id": THREAD})
    path = Path(row.verifier_feature_path)
    save_verifier_input(path, replace(load_verifier_input(path), **change),
        metadata={"policy_id": "p", "snapshot_id": row.snapshot_id})
    with pytest.raises(ValueError, match="provenance/time"):
        build_verifier_examples(memory, policy_id="p", request=request)
