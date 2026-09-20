"""Current-ticket gains and measured forgetting select merged policies."""

from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from mode_gate.eval_manifest import generate_joint_manifest
from mode_gate.evaluation import (
    PolicyScore, gain_retention_tradeoffs, raw_promotion_decision, retention_metrics,
)
from mode_gate.policy_evaluator import (
    EvaluationContext, PolicyEvaluationSummary, RawEpisodeResult, RawPolicyEvaluator,
)
from mode_gate.promotion import (
    PROMOTION_PROTOCOL, PolicyCandidate, PolicyPromotionCoordinator, PromotionConfig,
    TriggerRecheckResult, TriggerTaskEvaluator, load_retention_history,
)


def score(name, sr, alpha=0.2):
    return PolicyScore(name, alpha, sr, {"current": sr})


def test_declines_are_allowed_and_new_gain_is_balanced_against_forgetting():
    scores = [score("large_gain_large_loss", .85, .8),
              score("balanced", .75, .4), score("dominated", .70, .6)]
    loss = {"large_gain_large_loss": .30, "balanced": .05, "dominated": .10}
    kwargs = dict(parent_current_sr=.50, current_task_scores=scores, forgetting=loss)
    result = raw_promotion_decision(**kwargs)
    assert result.winner.candidate_id == "balanced"
    assert result.status == "POLICY_STAGED"  # Its old-task SR DOES drop.
    assert set(result.eligible_ids) == {s.candidate_id for s in scores}
    assert raw_promotion_decision(**kwargs, forgetting_penalty=0).winner.candidate_id == "large_gain_large_loss"


def test_no_hidden_zero_drop_or_positive_tradeoff_gate():
    result = raw_promotion_decision(
        parent_current_sr=.50, current_task_scores=[score("improves", .55)],
        forgetting={"improves": .10},
    )
    assert result.winner.candidate_id == "improves"  # G - F is negative, still allowed.
    result = raw_promotion_decision(
        parent_current_sr=.50, current_task_scores=[score("no_gain", .50)],
        forgetting={"no_gain": 0.0},
    )
    assert result.status == "POLICY_STAGED" and result.winner.candidate_id == "no_gain"


def test_full_score_parent_and_tied_candidates_can_promote():
    result = raw_promotion_decision(
        parent_current_sr=1.0,
        current_task_scores=[score("tied_more_loss", 1, .2), score("tied_less_loss", 1, .4)],
        forgetting={"tied_more_loss": .1, "tied_less_loss": .05},
    )
    assert result.winner.candidate_id == "tied_less_loss"


def test_difference_score_not_positive_gain_or_pareto_flag_controls_ranking():
    result = raw_promotion_decision(
        parent_current_sr=.8,
        current_task_scores=[score("positive_gain_large_loss", .9, .8),
                             score("small_decline_no_loss", .79, .4)],
        forgetting={"positive_gain_large_loss": .3, "small_decline_no_loss": 0},
    )
    assert result.winner.candidate_id == "small_decline_no_loss"


def test_tradeoff_ties_prefer_less_forgetting_not_larger_alpha():
    result = raw_promotion_decision(
        parent_current_sr=.5,
        current_task_scores=[score("gain30_loss20", .8, .8), score("gain20_loss10", .7, .4)],
        forgetting={"gain30_loss20": .2, "gain20_loss10": .1},
    )
    assert result.winner.candidate_id == "gain20_loss10"


def test_old_task_gains_do_not_cancel_other_old_task_losses():
    parent = PolicyScore("parent", 0, .5, {"a": .8, "b": .2})
    candidate = PolicyScore("candidate", .4, .6, {"a": .4, "b": .8})
    metrics = retention_metrics(parent=parent, candidate=candidate)
    assert metrics["macro_delta"] == pytest.approx(.1)
    assert metrics["macro_forgetting"] == pytest.approx(.2)
    assert metrics["regressed_tasks"] == ["a"]
    assert metrics["max_task_forgetting"] == pytest.approx(.4)
    assert metrics["zero_drop_required"] is False
    assert metrics["statistical_zero_forgetting_proven"] is False


@pytest.mark.parametrize("kwargs", [
    {"forgetting": {}}, {"forgetting": {"c": -0.1}},
    {"forgetting": {"c": float("nan")}}, {"forgetting_penalty": -1},
    {"forgetting_penalty": float("inf")}, {"parent_current_sr": 1.1},
])
def test_tradeoff_rejects_incomplete_or_invalid_evidence(kwargs):
    params = dict(parent_current_sr=.5, current_task_scores=[score("c", .6)], forgetting={"c": .1})
    params.update(kwargs)
    with pytest.raises(ValueError):
        gain_retention_tradeoffs(**params)


@pytest.mark.parametrize("kwargs", [
    {"current_task_splits": ["policy_final_sealed"]},
    {"retention_split": "demo_online_pool"}, {"current_policy_seed_repeats": 0},
    {"current_policy_seed_repeats": True}, {"forgetting_penalty": -1},
    {"current_task_splits": ["policy_alpha_selection", "policy_alpha_selection"]},
    {"retention_scope": "all_unvisited_tasks"},
])
def test_config_does_not_open_training_or_final_banks(kwargs):
    with pytest.raises(ValueError):
        PromotionConfig(**kwargs)


def test_seen_demo_success_cannot_outvote_held_out_results():
    result = TriggerRecheckResult("candidate", "parent", 10, 10, 4, 12, 0, 10, 5, 12)
    assert result.candidate_score == 4 / 12
    assert result.comparison_complete
    assert not result.to_dict()["current_task_improved"]
    assert result.to_dict()["score_basis"] == "held_out_current_task_only"


@pytest.fixture
def manifest_ticket():
    manifest = generate_joint_manifest([
        dict(suite=f"libero_{i // 10}", task_id=str(i), task_index=i % 10,
             perturbation_variant="base", init_state_ids=list(map(str, range(50))))
        for i in range(40)
    ], dataset_hash="d", bddl_hash="b", init_state_manifest_hash="i", generator_git_sha="g")
    task = next(t for t in manifest["tasks"] if len(t["splits"]["policy_alpha_selection"]) == 3
                and len(t["splits"]["policy_regression"]) == 6)
    ticket = {key: task[key] for key in ("suite", "task_id", "perturbation_variant")}
    ticket.update(ticket_id="ticket", init_state_ids=task["splits"]["demo_online_pool"],
                  eval_init_state_ids=task["splits"]["policy_regression"])
    return manifest, ticket, task


def test_current_task_bank_is_held_out_and_paired(manifest_ticket):
    manifest, ticket, task = manifest_ticket
    trigger = TriggerTaskEvaluator(evaluator=None, manifest=manifest, ticket=ticket)
    contexts = trigger.current_contexts
    assert len(contexts) == 18
    assert {c.task_key for c in contexts} == {task["task_key"]}
    states = {c.init_state_id for c in contexts}
    assert len(states) == 9
    for split, ids in task["splits"].items():
        if split not in PromotionConfig().current_task_splits:
            assert not states.intersection(map(str, ids))
    assert len({c.episode_key for c in contexts}) == 18
    assert trigger.identity["contexts"] == [asdict(c) for c in contexts]
    bad_ticket = {**ticket, "init_state_ids": [contexts[0].init_state_id]}
    with pytest.raises(ValueError):
        TriggerTaskEvaluator(evaluator=None, manifest=manifest, ticket=bad_ticket)


def test_all_merged_candidates_get_both_banks_and_report_config(manifest_ticket, tmp_path):
    manifest, ticket, task = manifest_ticket
    current_task = task["task_key"]
    old_tasks = sorted(t["task_key"] for t in manifest["tasks"] if t["task_key"] != current_task)
    calls = []
    cached = {}
    current_counts = {"parent": 6, "c2": 9, "c4": 12, "c6": 15, "c8": 18}

    class Evaluator:
        def evaluate(self, *, policy_id, checkpoint_path, checkpoint_digest, contexts, metric_role):
            key = (policy_id, metric_role)
            if key in cached:
                return cached[key]
            calls.append((policy_id, metric_role, tuple(contexts)))
            is_current = "current_task:" in metric_role
            if is_current:
                assert {c.task_key for c in contexts} == {current_task}
                vector = tuple(int(i < current_counts[policy_id]) for i in range(len(contexts)))
            else:
                assert current_task not in {c.task_key for c in contexts}
                # c4 loses one old task; c6 loses all; c8 loses about half.
                loses = {"parent": set(), "c2": set(), "c4": {old_tasks[0]},
                         "c6": set(old_tasks), "c8": set(old_tasks[:20])}[policy_id]
                vector = tuple(int(c.task_key not in loses) for c in contexts)
            per_task = {}
            for context, value in zip(contexts, vector):
                per_task.setdefault(context.task_key, []).append(value)
            sr = {k: sum(v) / len(v) for k, v in per_task.items()}
            result = PolicyEvaluationSummary(
                policy_id, checkpoint_digest, metric_role, sum(vector), len(vector),
                sum(vector) / len(vector), (0, 1), sum(sr.values()) / len(sr), sr, vector,
            )
            cached[key] = result
            return result

    evaluator = Evaluator()
    parent = PolicyCandidate("parent", "/parent", "parent-digest", 0)
    candidates = [PolicyCandidate(f"c{i}", f"/c{i}", f"digest-{i}", i / 10) for i in (2, 4, 6, 8)]

    def run(config):
        return PolicyPromotionCoordinator(
            evaluator=evaluator, manifest=manifest, output_root=tmp_path, config=config, bootstrap_draws=2,
            retention_history={"schema_version": "policy-retention-history-v1",
                               "manifest_hash": manifest["manifest_sha256"], "task_keys": old_tasks},
        ).run(parent=parent, candidates=candidates, trigger_evaluator=TriggerTaskEvaluator(
            evaluator=evaluator, manifest=manifest, ticket=ticket, config=config))

    report = run(PromotionConfig())
    assert report["selection_protocol"] == PROMOTION_PROTOCOL
    assert report["decision"]["winner"]["policy_id"] == "c4"
    assert report["regression"]["checks"]["c4"]["macro_forgetting"] == pytest.approx(1 / 39)
    assert report["regression"]["not_evaluated"] == []
    assert report["current_task"]["episodes_per_policy"] == 18
    assert report["regression"]["episodes"] == 97
    assert len(calls) == 10
    assert all("current_task:" in call[1] for call in calls[:5])
    assert all("retention:" in call[1] for call in calls[5:])
    assert len({tuple(c.episode_key for c in call[2]) for call in calls[:5]}) == 1
    assert len({tuple(c.episode_key for c in call[2]) for call in calls[5:]}) == 1
    assert run(PromotionConfig()) == report and len(calls) == 10
    changed = run(PromotionConfig(forgetting_penalty=0))
    assert changed["input_hash"] != report["input_hash"]
    assert changed["decision"]["winner"]["policy_id"] == "c8"
    assert changed["promotion_config"]["forgetting_penalty"] == 0
    assert len(calls) == 10  # Same raw evidence, different selection config.
    progress = json.loads((tmp_path / "progress.json").read_text())
    assert progress["state"] == "COMPLETE"
    assert progress["promotion_config"] == changed["promotion_config"]


@pytest.mark.parametrize("gate_kind", ["EXPANSION", "REUSE"])
@pytest.mark.parametrize("parent_successes,candidate_successes", [(18, 18), (18, 17)])
def test_first_task_skips_retention_and_has_no_hidden_trigger_gate(
    manifest_ticket, tmp_path, gate_kind, parent_successes, candidate_successes,
):
    manifest, ticket, task = manifest_ticket

    class NoRetentionEvaluator:
        def evaluate(self, **kwargs):
            pytest.fail("first task must not run a future-task retention episode")

    parent = PolicyCandidate("parent", "/parent", "pd", 0)
    candidates = [PolicyCandidate(f"c{i}", f"/c{i}", f"digest-{i}", i / 10) for i in (2, 4, 6, 8)]
    comparisons = []

    def trigger(candidate, baseline):
        comparisons.append(candidate.policy_id)
        return TriggerRecheckResult(candidate.policy_id, baseline.policy_id, 0, 0,
                                    candidate_successes, 18, 0, 0, parent_successes, 18)

    coordinator = PolicyPromotionCoordinator(
        evaluator=NoRetentionEvaluator(), manifest=manifest, output_root=tmp_path, bootstrap_draws=2,
        retention_history={"schema_version": "policy-retention-history-v1",
                           "manifest_hash": manifest["manifest_sha256"], "task_keys": []},
    )
    run = coordinator.run if gate_kind == "EXPANSION" else coordinator.run_reuse
    report = run(parent=parent, candidates=candidates, trigger_evaluator=trigger,
                 trigger_identity={"ticket_id": ticket["ticket_id"], "task_key": task["task_key"]})
    assert comparisons == ["c2", "c4", "c6", "c8"]
    assert report["decision"]["winner"]["policy_id"] == "c2"
    assert report["decision"]["status"] == "POLICY_STAGED"
    assert report["tradeoff"]["strict_current_task_improvement_required"] is False
    assert report["tradeoff"]["old_task_forgetting_applicable"] is False
    assert report["regression"]["evaluated"] is False
    assert report["regression"]["episodes"] == 0
    assert report["regression"]["skip_reason"] == "no_prior_completed_tasks"
    # Resident slow worker consumes this field; it must not reject full-score ties.
    assert report["trigger_recheck"]["c2"]["passed"] is True
    assert report["trigger_recheck"]["c2"]["comparison_complete"] is True
    assert report["trigger_recheck"]["c2"]["current_task_improved"] is False


def test_retention_history_includes_only_actual_formal_completions(manifest_ticket, tmp_path):
    manifest, ticket, current = manifest_ticket
    prior, future = [t for t in manifest["tasks"] if t["task_key"] != current["task_key"]][:2]
    plan = {"manifest_sha256": manifest["manifest_sha256"], "experiment_role": "full_architecture_online",
            "contexts": [{"context_id": str(i), "task_key": t["task_key"]}
                         for i, t in enumerate((prior, current, future))]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "status.json").write_text(json.dumps({"contexts_completed": 0}))
    first = load_retention_history(experiment_output=tmp_path, manifest=manifest)
    assert first["task_keys"] == []
    assert first["pretraining_retention_included"] is False
    rows = [{"event": "EPISODE_COMPLETED", "context_id": "0", "task_key": prior["task_key"]},
            {"event": "EPISODE_STARTED", "context_id": "1", "task_key": current["task_key"]}]
    (tmp_path / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    history = load_retention_history(experiment_output=tmp_path, manifest=manifest)
    assert history["task_keys"] == [prior["task_key"]]
    assert history["completed_context_ids"] == ["0"]
    assert history["sources"]["episode_ledger_sha256"]
    assert future["task_key"] not in history["task_keys"]
    rows.append({"event": "EPISODE_COMPLETED", "context_id": "unknown", "task_key": prior["task_key"]})
    (tmp_path / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="formal plan"):
        load_retention_history(experiment_output=tmp_path, manifest=manifest)


def test_missing_retention_ledger_cannot_silently_erase_existing_history(manifest_ticket, tmp_path):
    manifest, _, _ = manifest_ticket
    (tmp_path / "plan.json").write_text(json.dumps({"manifest_sha256": manifest["manifest_sha256"],
        "experiment_role": "full_architecture_online", "contexts": []}))
    (tmp_path / "status.json").write_text(json.dumps({"contexts_completed": 1}))
    with pytest.raises(ValueError, match="missing completed-context history"):
        load_retention_history(experiment_output=tmp_path, manifest=manifest)


def test_later_retention_excludes_current_and_unvisited_tasks(manifest_ticket, tmp_path):
    manifest, ticket, current = manifest_ticket
    prior = next(t for t in manifest["tasks"] if t["task_key"] != current["task_key"])
    calls = []

    class Evaluator:
        def evaluate(self, *, policy_id, checkpoint_path, checkpoint_digest, contexts, metric_role):
            assert {c.task_key for c in contexts} == {prior["task_key"]}
            calls.append(policy_id)
            count = len(contexts)
            return PolicyEvaluationSummary(policy_id, checkpoint_digest, metric_role, count, count,
                                           1, (0, 1), 1, {prior["task_key"]: 1}, (1,) * count)

    parent = PolicyCandidate("parent", "/parent", "pd", 0)
    candidates = [PolicyCandidate(f"c{i}", f"/c{i}", f"d{i}", i / 10) for i in (2, 4, 6, 8)]
    coordinator = PolicyPromotionCoordinator(
        evaluator=Evaluator(), manifest=manifest, output_root=tmp_path, bootstrap_draws=2,
        retention_history={"schema_version": "policy-retention-history-v1",
                           "manifest_hash": manifest["manifest_sha256"],
                           "task_keys": [prior["task_key"], current["task_key"]]},
    )
    report = coordinator.run(
        parent=parent, candidates=candidates,
        trigger_evaluator=lambda c, p: TriggerRecheckResult(c.policy_id, p.policy_id, 0, 0, 18, 18, 0, 0, 18, 18),
        trigger_identity={"task_key": current["task_key"], "ticket_id": ticket["ticket_id"]},
    )
    assert calls == ["parent", "c2", "c4", "c6", "c8"]
    assert report["regression"]["old_task_keys"] == [prior["task_key"]]
    assert report["regression"]["episodes"] == len(prior["splits"]["policy_alpha_selection"])
    assert report["decision"]["winner"]["policy_id"] == "c2"


@pytest.mark.parametrize("success", [False, True])
def test_compatible_raw_episodes_are_reused_without_relabeling(tmp_path, success):
    context = EvaluationContext("libero_10", "task", 2, "use_language", "3", 41, 52)
    calls = []

    def execute(policy, checkpoint, ctx):
        calls.append(ctx)
        return RawEpisodeResult(success, 123, "/original-output", {"native_predicate": success})

    evaluator = RawPolicyEvaluator(executor=execute, ledger_path=tmp_path / "episodes.jsonl",
                                   manifest_hash="manifest", reuse_raw_results=True)
    args = dict(policy_id="candidate", checkpoint_path=tmp_path,
                checkpoint_digest="digest", contexts=[context])
    original = evaluator.evaluate(**args, metric_role="promotion_raw:alpha100")
    original_bytes = (tmp_path / "episodes.jsonl").read_bytes()
    result = evaluator.evaluate(**args, metric_role="promotion_raw:current_task:ticket")
    assert result.raw_vector == original.raw_vector == (int(success),)
    assert calls == [context]
    assert (tmp_path / "episodes.jsonl").read_bytes().startswith(original_bytes)
    rows = list(evaluator.ledger.events.iter_valid())
    assert rows[-1]["metadata"]["reused_raw_episode_key"] == rows[0]["episode_key"]
    assert rows[-1]["steps"] == 123 and rows[-1]["output_dir"] == "/original-output"


@pytest.mark.parametrize("mismatch", [
    "checkpoint", "manifest", "policy_id", "profile", "policy_seed", "env_seed",
    "init_state", "source_role", "destination_role", "invalidated", "opt_in", "not_raw",
])
def test_raw_reuse_rejects_mismatched_or_forbidden_evidence(tmp_path, mismatch):
    context = EvaluationContext("libero_10", "task", 2, "use_language", "3", 41, 52)
    calls = []

    def execute(policy, checkpoint, ctx):
        calls.append(ctx)
        return RawEpisodeResult(True, 7, f"/output-{len(calls)}")

    evaluator = RawPolicyEvaluator(executor=execute, ledger_path=tmp_path / "episodes.jsonl",
                                   manifest_hash="manifest", reuse_raw_results=True)
    args = dict(policy_id="candidate", checkpoint_path=tmp_path,
                checkpoint_digest="digest", contexts=[context])
    evaluator.evaluate(**args, metric_role="deployed_final" if mismatch == "source_role" else "promotion_raw:alpha100")
    if mismatch == "checkpoint":
        args["checkpoint_digest"] = "changed-digest"
    elif mismatch == "manifest":
        evaluator.manifest_hash = "changed-manifest"
    elif mismatch == "policy_id":
        args["policy_id"] = "other-policy"
    elif mismatch == "profile":
        args["evaluation_profile"] = {"changed": True}
    elif mismatch in {"policy_seed", "env_seed", "init_state"}:
        field = "init_state_id" if mismatch == "init_state" else mismatch
        args["contexts"] = [replace(context, **{field: "4" if field == "init_state_id" else 99})]
    elif mismatch == "invalidated":
        row = next(evaluator.ledger.events.iter_valid())
        evaluator.ledger.invalidate(row["episode_key"], reason="invalid source")
    elif mismatch == "opt_in":
        evaluator.reuse_raw_results = False
    elif mismatch == "not_raw":
        args["require_raw_profile"] = False
    role = "deployed_dev" if mismatch == "destination_role" else "promotion_raw:current_task:ticket"
    assert evaluator.evaluate(**args, metric_role=role).episodes == 1
    assert len(calls) == 2
    assert "reused_raw_episode_key" not in list(evaluator.ledger.events.iter_valid())[-1]["metadata"]
