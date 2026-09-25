"""Real collector/bundle audit with invented CPU tensors; no policy/provider calls."""
import hashlib
import json

import numpy as np
import pytest
import torch

from core.decision_evidence import DecisionEvidence
from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk
from scripts import audit_decision_evidence as audit


def episode(tmp_path, *, count=3, variant="different", auxiliary=False, stage_init=None, n5=False, n6=False):
    rec = DecisionEvidence(tmp_path, episode=0)
    provider = lambda keypoints, trajectories: None
    keypoints = torch.zeros(1, 3, dtype=torch.bfloat16 if n5 else torch.float32)
    if n5:
        from core.qd_executed_quality import TEMPLATE
        path = tmp_path / "guidance.txt"
        path.write_text(TEMPLATE)
        provider._guidance_source_text = TEMPLATE
        provider._guidance_source_path = str(path)
    rec.begin_decision(global_step=0, stage=1, use_guidance=True,
                       keypoints=keypoints.double() if n5 else keypoints, providers=[provider])
    first = previous = None
    cell_ids = torch.arange(16, dtype=torch.int64)
    for j in range(11):
        iteration = j - 1
        if previous is not None:
            pa, quality = previous
            rec.record("archive_parent_allocation", iter_idx=iteration,
                parent_fingerprints=audit.fingerprints(pa), parent_lanes=["quality"] * 16,
                parent_cell_ids=cell_ids, parent_rewards=quality.float(), parent_costs=-quality.float(),
                original_archive_occurrences=None, weights={"quality": 1.0})
            rec.record("parent_allocation", iter_idx=iteration, source_population=pa,
                source_quality=quality.float(), source_costs=-quality.float(), parent_indices=cell_ids,
                elite_count=0, parent_cell_ids=cell_ids, offspring_sources=["quality"] * 16)
        actions = torch.zeros(16, 64, 128, dtype=torch.bfloat16)
        actions[:, :, 10] = -1
        actions[:, :, 39] = torch.arange(j * 16, j * 16 + 16).bfloat16()[:, None] / 256
        quality = -(torch.arange(16).bfloat16() / 16 + (j + 1))
        if j == 10:
            if n5:
                actions[1, :, 10] = 1
            if variant in {"same", "suffix", "inactive", "signed_zero", "gripper_zero"}:
                actions[0] = first[0][0]
                quality[0] = first[1][0]
                if variant == "suffix": actions[0, count:8, 40] = .25
                if variant == "inactive": actions[0, :, 2] = .25
                if variant == "signed_zero": actions[0, :, 39] = -0.0
                if variant == "gripper_zero": actions[0, :, 10] = 0
            if variant in {"ties", "duplicates"}:
                quality[1] = quality[0]
                if variant == "duplicates": actions[1] = actions[0]
        scopes = [("canonical_initial" if j == 0 else "canonical_offspring", iteration)]
        if auxiliary and j == 10: scopes.insert(0, ("auxiliary_pretest", iteration))
        for role, _ in scopes:
            rec.set_scoring_scope(role=role, iter_idx=iteration, site="synthetic_existing_return")
            rec.begin_score_call()
            full = torch.zeros(16, 9, 3, dtype=torch.bfloat16)
            for row in full:
                rec.record("projection_origin", source_eef_position=np.zeros(3), cast_eef_start=row[0])
            rec.begin_scoring(samples=actions, keypoints=keypoints, projected_xyz=full,
                              provider_input_xyz=full[:, 1:8], slice_kind="eds")
            for index in range(16):
                rec.scoring_candidate_index = index; rec.scoring_provider_index = 0
                rec.provider_return(provider, quality[index])
            score_id = rec.scoring_batch_id
            rec.record("scoring_aggregate", scoring_batch_id=score_id, aggregate_before_reward_mode=quality)
            rec.record("effective_quality", scoring_batch_id=score_id, reward_mode="normal", quality=quality, costs=-quality)
            if role != "auxiliary_pretest":
                canonical_sequence = rec.record("canonical_candidate_batch", iter_idx=iteration,
                                                candidates=actions, effective_quality=quality)
                if n6:
                    rec.record("qd_descriptor_assignment", iter_idx=iteration,
                        descriptor_mode="target_horizontal_radius_signed_height_v1",
                        descriptors=torch.zeros(16, 2), cell_ids=torch.full((16,), 10, dtype=torch.long),
                        overflow=torch.zeros(16, dtype=torch.bool),
                        bounds_lo=torch.tensor([-.04, -.04]), bounds_hi=torch.tensor([.04, .04]),
                        scoring_batch_id=score_id)
        if first is None: first = actions.clone(), quality.clone()
        previous = actions, quality
    costs = -quality; index = 1 if n5 else int(torch.argmin(costs)); selected = actions[index:index + 1]
    archive, rewards = first[0][:4], first[1][:4].float()
    best = min(range(4), key=lambda i: (-rewards[i].item(), audit.fingerprints(archive)[i], i))
    reference = {"population": archive, "rewards": rewards, "costs": -rewards, "cell_ids": cell_ids[:4],
        "global_best_index": best, "selected_latent": archive[best:best + 1], "selected_fingerprint": audit.fingerprints(archive)[best],
        "selected_cell": best, "selected_quality": rewards[best].item(), "selected_cost": -rewards[best].item()}
    raw = quality[index].item()
    grasp = ({"target_index": 0, "recognition_reason": "recognized_weighted_distance_template",
              "best_reach_m": 0., "eligible_indices": [1], "native_argmin_index": 0,
              "absolute_reach_m": 0.06, "relative_reach_m": 0.03,
              "projected_distances_m": torch.zeros(16, 8),
              "positive_commands": torch.arange(16)[:, None].expand(16, 8) == 1} if n5 else None)
    rec.record("final_selection", population=actions, selected_latent=selected, selected_index=index,
        selected_quality=raw, selected_cost=costs[index].item(), selected_fingerprint=audit.fingerprints(selected)[0],
        selected_cell=10 if n6 else index, selection_rule="terminal_grasp_proximity" if n5 else "terminal_population_first_argmin",
        qd_final_selection_mode="terminal_grasp_proximity_v1" if n5 else "terminal_population_v1",
        terminal_population={"iter_idx": 9, "canonical_event_sequence": canonical_sequence, "scoring_batch_id": score_id,
            "selected_occurrence_id": f"{rec.decision_id}:q{canonical_sequence}:r{index}",
            "minimum_cost_tie_indices": torch.nonzero(costs == costs.min()).reshape(-1).tolist(),
            "native_costs": costs, "raw_provider_quality": quality,
            "cell_ids": torch.full((16,), 10, dtype=torch.long) if n6 else cell_ids,
            "parent_cell_ids": cell_ids, "selected_parent_cell": index,
            **({"grasp_selection": grasp} if n5 else {})},
        archive_reference=reference, stage_reward_reference={"selected_raw_reward": quality[index],
            "reference_costs": -rewards, "reference_scope": "qd_archive_cost_spread"})
    initial = raw if stage_init is None else stage_init
    normalized = max(0., min(1.2, 1. - raw / initial)) if initial < -1e-6 else 0.
    rec.record("terminal_population_stage_binding", selected_raw_reward=raw,
        archive_cost_spread_scale=(rewards.max() - rewards.mean()).item(), stage_init_reward=initial, normalized_reward=normalized)
    decoded = decode_rdt_libero_action_chunk(selected.float(), 8)
    rec.record("policy_action_decode", selected_latent=selected.float(), action_chunk=decoded)
    rec.commit_decision(action_chunk=decoded, execution_horizon=8)
    for index in range(count):
        rec.dispatch(global_step=index, execution_index=index + 1)
        rec.record("executed_action", action_numpy=decoded[0, index].numpy())
        terminal = index == count - 1
        rec.pre_reset_outcome({"robot0_eef_pos": np.zeros(3)}, reward=0., terminated=terminal, success=terminal)
        rec.step_returned(terminated=terminal, truncated=False, success=terminal)
    rec.finish()
    compute = tmp_path / "episode_compute.jsonl"
    compute.write_text(json.dumps({"episode_id": 0, "outcome": "completed", "decision_evidence": rec.status()}) + "\n")
    return rec, compute


def rewrite(rec, event, edit):
    refs = [json.loads(line) for line in (rec.root / "events.jsonl").read_text().splitlines()]
    changed = False
    for ref in refs:
        path = rec.root / ref["bundle"]
        payload = torch.load(path, weights_only=True)
        for row in payload["events"]:
            if row["event"] == event and not changed:
                edit(row); changed = True
        torch.save(payload, path); ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert changed
    (rec.root / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in refs))


@pytest.mark.parametrize("variant,different_m,different8", [
    ("different", 1, 1), ("same", 0, 0), ("suffix", 0, 1), ("inactive", 0, 0),
    ("signed_zero", 0, 0), ("gripper_zero", 1, 1), ("ties", 1, 1), ("duplicates", 1, 1)])
def test_actual_collector_full_audit_native_choice_and_short_terminal_prefix(tmp_path, variant, different_m, different8):
    rec, compute = episode(tmp_path, variant=variant, auxiliary=True)
    result = audit.audit_episode(rec.root, compute)
    assert result["accepted"], result["errors"]
    gate = result["n4_terminal_population_audit"]
    assert [gate[k] for k in ("checked_decisions", "canonical_batches_verified", "canonical_candidates_verified",
                             "parent_rounds_verified", "actual_actions_verified")] == [1, 11, 176, 10, 3]
    assert gate["decoded_reference_actual_prefix_different_decisions"] == different_m
    assert gate["decoded_reference_first8_different_decisions"] == different8
    assert result["observed_scoring_roles"]["auxiliary_pretest"] == 1
    assert gate["decisions"][0]["minimum_cost_tie_indices"] == ([0, 1] if variant in {"ties", "duplicates"} else [0])


@pytest.mark.parametrize("stage_init", [0., .5, -1e-6, -.01, -100.])
def test_original_normalization_branch_and_clamp(tmp_path, stage_init):
    rec, compute = episode(tmp_path, count=8, stage_init=stage_init)
    result = audit.audit_episode(rec.root, compute)
    assert result["accepted"], result["errors"]


@pytest.mark.parametrize("event,field,edit,code", [
    ("final_selection", "terminal_population", lambda v: v.update(scoring_batch_id=1), "n4_last_canonical_source_mismatch"),
    ("final_selection", "terminal_population", lambda v: v.update(minimum_cost_tie_indices=[1]), "n4_first_native_cost_argmin_or_ties"),
    ("final_selection", "terminal_population", lambda v: v.update(minimum_cost_tie_indices=[False]), "n4_first_native_cost_argmin_or_ties"),
    ("final_selection", "terminal_population", lambda v: v.update(selected_occurrence_id="wrong"), "n4_selected_occurrence_mismatch"),
    ("final_selection", "terminal_population", lambda v: v.update(native_costs=v["native_costs"].float()), "n4_last_population_cost_raw_mismatch"),
    ("final_selection", "terminal_population", lambda v: v.update(selected_parent_cell=1), "n4_selected_parent_cell_mismatch"),
    ("final_selection", "archive_reference", lambda v: v.update(global_best_index=1), "n4_archive_global_best_reference_mismatch"),
    ("final_selection", "archive_reference", lambda v: v["costs"].add_(1), "n4_archive_native_cost_association"),
    ("final_selection", "stage_reward_reference", lambda v: v.update(reference_costs=torch.zeros(4)), "n4_stage_raw_or_archive_scale_reference"),
    ("terminal_population_stage_binding", None, lambda v: v.update(selected_raw_reward=0.), "n4_stage_written_raw_or_scale_invalid"),
    ("terminal_population_stage_binding", None, lambda v: v.update(normalized_reward=.5), "n4_stage_written_normalized_mismatch"),
    ("terminal_population_stage_binding", None, lambda v: v.update(archive_cost_spread_scale=float("nan")), "n4_stage_binding_invalid"),
    ("executed_action", None, lambda v: v["action_numpy"].add_(.125), "n4_actual_dispatch_mismatch"),
    ("scoring_inputs", None, lambda v: v["samples"].add_(.125), "n4_same_call_population_mismatch"),
    ("archive_parent_allocation", None, lambda v: v["parent_rewards"].add_(1), "n4_parent_values_or_lanes"),
    ("archive_parent_allocation", None, lambda v: v["parent_cell_ids"].add_(1), "n4_parent_cell_source_mismatch"),
])
def test_corrupt_native_source_choice_raw_reference_and_dispatch_rejected(tmp_path, event, field, edit, code):
    rec, compute = episode(tmp_path)
    rewrite(rec, event, lambda row: edit(row["values"] if field is None else row["values"][field]))
    result = audit.audit_episode(rec.root, compute)
    assert not result["accepted"] and result["errors"] == [code]
    assert result["original_execution_outcome"] == "completed"


def test_internally_consistent_recorded_chunk_still_must_match_deployed_decode(tmp_path):
    rec, compute = episode(tmp_path)
    for event in ("policy_action_decode", "decision_committed"):
        rewrite(rec, event, lambda row: row["values"]["action_chunk"].add_(.125))
    result = audit.audit_episode(rec.root, compute)
    assert not result["accepted"] and result["errors"] == ["n4_actual_deployed_decode_mismatch"]


def test_metric_join_exports_validated_selected_fingerprint_and_native_archive_costs(tmp_path):
    rec, compute = episode(tmp_path)
    result = audit.audit_episode(rec.root, compute)
    assert result["accepted"], result["errors"]
    decision = result["n4_terminal_population_audit"]["decisions"][0]
    selected = torch.zeros(1, 64, 128, dtype=torch.bfloat16)
    selected[:, :, 10] = -1
    selected[:, :, 39] = 160 / 256
    costs = torch.arange(4, dtype=torch.float32) / 16 + 1
    assert decision["selected_fingerprint"] == audit.fingerprints(selected)[0]
    assert decision["archive_reference_costs"] == audit._native_record(costs)
    assert decision["archive_reference_costs"]["sha256"] == decision["archive_cost_reference_sha256"]
    assert decision["archive_reference_costs"]["values"][decision["archive_reference_index"]] == decision["archive_reference_cost"]


def test_n5_audit_accepts_non_argmin_grasp_choice_and_rejects_false_eligibility(tmp_path):
    rec, compute = episode(tmp_path, n5=True)
    result = audit.audit_episode(rec.root, compute)
    assert result["accepted"], result["errors"]
    decision = result["n5_grasp_timing_audit"]["decisions"][0]
    assert decision["n5_grasp_selection"]["selected_index"] == 1
    assert decision["n5_grasp_selection"]["native_argmin_index"] == 0
    rewrite(rec, "final_selection", lambda row: row["values"]["terminal_population"]["grasp_selection"].update(eligible_indices=[0, 1]))
    result = audit.audit_episode(rec.root, compute)
    assert not result["accepted"] and result["errors"] == ["n5_eligibility_mismatch"]


def test_n5_audit_allows_float32_device_roundoff_but_rejects_material_distance_change(tmp_path):
    rec, compute = episode(tmp_path, n5=True)
    rewrite(rec, "final_selection", lambda row: row["values"]["terminal_population"]["grasp_selection"]
            ["projected_distances_m"][0, 0].fill_(2.9802322387695312e-8))
    accepted = audit.audit_episode(rec.root, compute)
    assert accepted["accepted"], accepted["errors"]
    rewrite(rec, "final_selection", lambda row: row["values"]["terminal_population"]["grasp_selection"]
            ["projected_distances_m"][0, 0].fill_(1e-4))
    rejected = audit.audit_episode(rec.root, compute)
    assert not rejected["accepted"] and rejected["errors"] == ["n5_distance_or_projection_mismatch"]


def test_n6_audit_binds_all_native_height_cells_and_rejects_false_assignment(tmp_path):
    rec, compute = episode(tmp_path, n5=True, n6=True)
    accepted = audit.audit_episode(rec.root, compute)
    assert accepted["accepted"], accepted["errors"]
    assert accepted["n6_height_audit"]["assignments_verified"] == 11
    rewrite(rec, "qd_descriptor_assignment", lambda row: row["values"]["cell_ids"][0].fill_(1))
    rejected = audit.audit_episode(rec.root, compute)
    assert not rejected["accepted"] and rejected["errors"] == ["n6_cell_or_threshold_association_mismatch"]
