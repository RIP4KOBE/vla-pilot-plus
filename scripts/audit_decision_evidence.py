#!/usr/bin/env python3
"""Offline, single-episode evidence gate; never changes execution outcomes.

Requires explicit paths. Loads only named, SHA-verified bundles with weights_only.
Content fingerprints identify equal actions, not original archive occurrences.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import io
import math
import re
from pathlib import Path

import torch


class AuditFailure(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise AuditFailure(code)


def fingerprints(batch):
    return [hashlib.sha256(row.float().contiguous().numpy().astype("<f4", copy=False).tobytes()).hexdigest()
            for row in batch]


def tensor(value):
    return torch.is_tensor(value) and value.device.type == "cpu" and bool(torch.isfinite(value).all())


def load_events(root, status):
    events = []
    refs = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    require(len(refs) == status["bundles"], "bundle_count_mismatch")
    require({p.name for p in root.glob("bundle_*.pt")} == {r["bundle"] for r in refs}, "unindexed_bundle")
    for index, ref in enumerate(refs, 1):
        name = f"bundle_{index:06d}.pt"
        require(ref["bundle"] == name, "bundle_order_or_path_invalid")
        path = root / name
        require(not path.is_symlink(), "symlink_bundle")
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == ref["sha256"], "bundle_sha_mismatch")
        payload = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
        require(payload["schema"] == "qd-ed-decision-evidence-v1", "bundle_schema_invalid")
        rows = payload["events"]
        require(bool(rows), "empty_bundle")
        require(ref["first_sequence"] == rows[0]["sequence"] and ref["last_sequence"] == rows[-1]["sequence"], "bundle_sequence_mismatch")
        require(ref["events"] == [{k: r[k] for k in ("sequence", "event", "decision_id", "global_step", "reset_sequence")} for r in rows], "index_metadata_mismatch")
        events.extend(rows)
    require([r["sequence"] for r in events] == list(range(1, len(events) + 1)), "event_sequence_gap")
    require(all(r["episode"] == status["episode"] for r in events), "episode_mismatch")
    return events


def _native_sha(value):
    value = value.detach().cpu().contiguous()
    prefix = f"{value.dtype}:{tuple(value.shape)}:".encode()
    return hashlib.sha256(prefix + value.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def _native_record(value):
    return {"dtype": str(value.dtype), "shape": list(value.shape),
            "sha256": _native_sha(value), "values": value.tolist()}


def _audit_n4_terminal_population(kinds, context, final_event):
    """Audit the actual N4 consumer; reference decoding is not a rollout.

    Called after the generic audit has checked providers, event sequence and
    executed pre-reset lifecycle. No scores, projections or archive are rerun.
    """
    def one(kind):
        require(len(kinds[kind]) == 1, "n4_missing_or_duplicate_" + kind)
        return kinds[kind][0]

    def native(value, shape, dtype=None):
        require(tensor(value) and value.is_floating_point() and tuple(value.shape) == tuple(shape)
                and (dtype is None or value.dtype == dtype), "n4_native_shape_dtype_or_finite")
        return value

    def same(left, right):
        return tensor(left) and tensor(right) and _native_sha(left) == _native_sha(right)

    def numeric_same(left, right):
        return (tensor(left) and tensor(right) and left.dtype == right.dtype == torch.float32
                and left.shape == right.shape and torch.equal(left, right))

    canonical = kinds["canonical_candidate_batch"]
    require([r["values"]["iter_idx"] for r in canonical] == list(range(-1, 10)), "n4_canonical_11_coverage")
    sources = [r for r in kinds["scoring_inputs"] if r["values"]["scoring_scope"]["role"] != "auxiliary_pretest"]
    scoring = {r["values"]["scoring_scope"]["iter_idx"]: r for r in sources}
    allocations = {r["values"]["iter_idx"]: r for r in kinds["archive_parent_allocation"]}
    parents = {r["values"]["iter_idx"]: r for r in kinds["parent_allocation"]}
    require(len(sources) == len(scoring) == 11 and set(scoring) == set(range(-1, 10)), "n4_scoring_11_coverage")
    require(len(kinds["archive_parent_allocation"]) == len(kinds["parent_allocation"])
            == len(allocations) == len(parents) == 10 and set(allocations) == set(parents) == set(range(10)),
            "n4_parent_10_coverage")
    known, batches, parent_links = defaultdict(list), [], []
    final_costs = None
    for row in canonical:
        value = row["values"]; iteration = value["iter_idx"]; source = scoring[iteration]
        scope = source["values"]["scoring_scope"]
        require(scope["role"] == ("canonical_initial" if iteration == -1 else "canonical_offspring"), "n4_scoring_role")
        actions = native(value["candidates"], (16, 64, 128))
        quality = native(value["effective_quality"], (16,), actions.dtype)
        require(same(actions, source["values"]["samples"]), "n4_same_call_population_mismatch")
        linked = lambda kind: [r for r in kinds[kind] if r["values"]["scoring_batch_id"] == source["sequence"]]
        aggregates, effectives = linked("scoring_aggregate"), linked("effective_quality")
        require(len(aggregates) == len(effectives) == 1, "n4_same_call_score_missing_or_duplicate")
        aggregate, effective = aggregates[0], effectives[0]; ev = effective["values"]
        require(ev.get("quality_mode", "provider") == value.get("quality_mode", "provider") == "provider"
                and ev["reward_mode"] == "normal" and ev["scoring_scope"] == aggregate["values"]["scoring_scope"] == scope,
                "n4_original_provider_mode_mismatch")
        costs = native(ev["costs"], (16,), actions.dtype)
        require(same(quality, ev["quality"]) and same(quality, aggregate["values"]["aggregate_before_reward_mode"])
                and same(costs, -quality), "n4_same_call_raw_cost_mismatch")
        require(source["sequence"] < aggregate["sequence"] < effective["sequence"] < row["sequence"], "n4_same_call_order")
        if iteration >= 0:
            allocation, parent = allocations[iteration], parents[iteration]
            av, pv = allocation["values"], parent["values"]
            require(all(prior["sequence"] < allocation["sequence"] < parent["sequence"] < source["sequence"]
                        for prior in canonical if prior["values"]["iter_idx"] < iteration), "n4_parent_prior_only_order")
            pa = native(pv["source_population"], (16, 64, 128), actions.dtype)
            indices = pv["parent_indices"]
            require(pv["elite_count"] == 0 and torch.is_tensor(indices) and indices.dtype == torch.int64
                    and indices.device.type == "cpu" and torch.equal(indices, torch.arange(16)), "n4_sparse_parent_contract")
            pr, pc = native(av["parent_rewards"], (16,), torch.float32), native(av["parent_costs"], (16,), torch.float32)
            require(same(pr, pv["source_quality"]) and same(pc, pv["source_costs"])
                    and av["parent_lanes"] == ["quality"] * 16, "n4_parent_values_or_lanes")
            allocated_cells = av["parent_cell_ids"]
            require(tensor(allocated_cells) and allocated_cells.dtype == torch.int64 and allocated_cells.shape == (16,)
                    and bool(((allocated_cells >= 0) & (allocated_cells < 16)).all())
                    and same(allocated_cells, pv["parent_cell_ids"]), "n4_parent_cell_source_mismatch")
            slots = []
            for index, action in enumerate(pa):
                matches = known[_native_sha(action)]
                require(matches and all(m["quality"] == pr[index].item() and m["cost"] == pc[index].item()
                                        for m in matches), "n4_parent_native_prior_association")
                slots.append({"slot": index, "matching_occurrence_ids": [m["occurrence_id"] for m in matches]})
            parent_links.append({"iter_idx": iteration, "allocation_sequence": allocation["sequence"],
                                 "parent_sequence": parent["sequence"], "slots": slots})
        for index, action in enumerate(actions):
            known[_native_sha(action)].append({"occurrence_id": value["occurrence_ids"][index],
                "iter_idx": iteration, "row": index, "quality": quality[index].item(), "cost": costs[index].item()})
        batches.append({"iter_idx": iteration, "canonical_sequence": row["sequence"], "scoring_batch_id": source["sequence"]})
        final_costs = costs

    final = final_event["values"]; terminal = final["terminal_population"]; archive = final["archive_reference"]
    last = canonical[-1]; last_values = last["values"]
    require(final["selection_rule"] == "terminal_population_first_argmin"
            and final.get("qd_final_selection_mode") == "terminal_population_v1"
            and final.get("quality_mode", "provider") == "provider", "n4_final_mode_mismatch")
    require(last["sequence"] < final_event["sequence"] < one("policy_action_decode")["sequence"], "n4_final_order")
    require(terminal["iter_idx"] == 9 and terminal["canonical_event_sequence"] == last["sequence"]
            and terminal["scoring_batch_id"] == scoring[9]["sequence"], "n4_last_canonical_source_mismatch")
    population = native(final["population"], (16, 64, 128), last_values["candidates"].dtype)
    require(same(population, last_values["candidates"]) and same(terminal["native_costs"], final_costs)
            and same(terminal["raw_provider_quality"], last_values["effective_quality"]), "n4_last_population_cost_raw_mismatch")
    minimum = int(torch.argmin(final_costs).item())
    ties = torch.nonzero(final_costs == final_costs.min(), as_tuple=False).reshape(-1).tolist()
    require(type(final["selected_index"]) is int and final["selected_index"] == minimum
            and isinstance(terminal["minimum_cost_tie_indices"], list)
            and all(type(i) is int for i in terminal["minimum_cost_tie_indices"])
            and terminal["minimum_cost_tie_indices"] == ties, "n4_first_native_cost_argmin_or_ties")
    require(terminal["selected_occurrence_id"] == last_values["occurrence_ids"][minimum], "n4_selected_occurrence_mismatch")
    selected = native(final["selected_latent"], (1, 64, 128), population.dtype)
    require(same(selected, population[minimum:minimum + 1]) and final["selected_cost"] == final_costs[minimum].item()
            and final["selected_quality"] == last_values["effective_quality"][minimum].item(), "n4_selected_native_cost_raw_mismatch")
    cells = terminal["cell_ids"]
    require(tensor(cells) and cells.dtype == torch.int64 and cells.shape == (16,)
            and bool(((cells >= 0) & (cells < 16)).all()) and final["selected_cell"] == cells[minimum].item(), "n4_selected_recorded_cell_mismatch")
    parent_cells = terminal["parent_cell_ids"]
    require(tensor(parent_cells) and parent_cells.dtype == torch.int64 and parent_cells.shape == (16,)
            and same(parent_cells, allocations[9]["values"]["parent_cell_ids"])
            and terminal["selected_parent_cell"] == parent_cells[minimum].item(), "n4_selected_parent_cell_mismatch")
    require(final["selected_fingerprint"] == fingerprints(selected)[0], "n4_selected_fingerprint_mismatch")

    ap = archive["population"]
    require(tensor(ap) and ap.ndim == 3 and 1 <= len(ap) <= 16, "n4_archive_shape")
    native(ap, (len(ap), 64, 128), population.dtype)
    ar, ac = native(archive["rewards"], (len(ap),), torch.float32), native(archive["costs"], (len(ap),), torch.float32)
    cell_ids = archive["cell_ids"]
    require(tensor(cell_ids) and cell_ids.dtype == torch.int64 and cell_ids.shape == (len(ap),)
            and cell_ids.tolist() == sorted(set(cell_ids.tolist())) and bool(((cell_ids >= 0) & (cell_ids < 16)).all()), "n4_archive_cells")
    archive_links = []
    for index, action in enumerate(ap):
        matches = known[_native_sha(action)]
        require(matches and all(m["quality"] == ar[index].item() and m["cost"] == ac[index].item() for m in matches), "n4_archive_native_cost_association")
        archive_links.append({"slot": index, "matching_occurrence_ids": [m["occurrence_id"] for m in matches]})
    afp = fingerprints(ap)
    best = min(range(len(ap)), key=lambda i: (-ar[i].item(), afp[i], cell_ids[i].item()))
    require(type(archive["global_best_index"]) is int and archive["global_best_index"] == best
            and same(archive["selected_latent"], ap[best:best + 1])
            and archive["selected_fingerprint"] == afp[best] and archive["selected_cell"] == cell_ids[best].item()
            and archive["selected_quality"] == ar[best].item() and archive["selected_cost"] == ac[best].item(), "n4_archive_global_best_reference_mismatch")

    reference = final["stage_reward_reference"]
    require(reference["reference_scope"] == "qd_archive_cost_spread" and same(reference["reference_costs"], ac)
            and same(reference["selected_raw_reward"], last_values["effective_quality"][minimum]), "n4_stage_raw_or_archive_scale_reference")
    binding = one("terminal_population_stage_binding"); bv = binding["values"]
    require(final_event["sequence"] < binding["sequence"] < one("policy_action_decode")["sequence"], "n4_stage_binding_order")
    require(all(type(bv[k]) in (int, float) and math.isfinite(bv[k]) for k in
                ("selected_raw_reward", "archive_cost_spread_scale", "stage_init_reward", "normalized_reward")), "n4_stage_binding_invalid")
    require(bv["selected_raw_reward"] == final["selected_quality"] and bv["archive_cost_spread_scale"] >= 0, "n4_stage_written_raw_or_scale_invalid")
    normalized = max(0.0, min(1.2, 1.0 - bv["selected_raw_reward"] / bv["stage_init_reward"])) if bv["stage_init_reward"] < -1e-6 else 0.0
    require(bv["normalized_reward"] == normalized, "n4_stage_written_normalized_mismatch")
    # Source + real-call CPU tests bind scale to the captured original archive
    # vector. Do not pretend CPU reduction recreates bit-exact GPU FP32 mean.
    decoder_path = Path(__file__).resolve().parents[1] / "core" / "rdt_libero_action_converter.py"
    spec = importlib.util.spec_from_file_location("n4_audit_deployed_decoder", decoder_path)
    decoder = importlib.util.module_from_spec(spec); spec.loader.exec_module(decoder)
    decoded_event = one("policy_action_decode"); decoded = decoded_event["values"]
    require(same(decoded["selected_latent"], selected.float()), "n4_selected_policy_cast_mismatch")
    actual = decoder.decode_rdt_libero_action_chunk(decoded["selected_latent"], 8)
    require(numeric_same(actual, decoded["action_chunk"]) and numeric_same(actual, one("decision_committed")["values"]["action_chunk"])
            and one("decision_committed")["values"]["execution_horizon"] == 8, "n4_actual_deployed_decode_mismatch")
    dispatches, sent = kinds["action_dispatch"], kinds["executed_action"]
    m = len(dispatches)
    require(1 <= m <= 8 and len(sent) == m, "n4_actual_prefix_invalid")
    for index, row in enumerate(sent):
        require(numeric_same(row["values"]["action_numpy"], actual[0, index]), "n4_actual_dispatch_mismatch")
    hypothetical = decoder.decode_rdt_libero_action_chunk(archive["selected_latent"].float(), 8)
    differences = torch.nonzero(actual[0] != hypothetical[0], as_tuple=False).tolist()
    return {"decision_id": context["decision_id"], "global_step": context["global_step"],
        "canonical_batches_verified": 11, "canonical_candidates_verified": 176, "parent_rounds_verified": 10,
        "actual_prefix_length": m, "selected_index": minimum, "minimum_cost_tie_indices": ties,
        "selected_occurrence_id": terminal["selected_occurrence_id"], "selected_native_sha256": _native_sha(selected[0]),
        "selected_fingerprint": final["selected_fingerprint"],
        "selected_cell": final["selected_cell"], "selected_parent_cell": terminal["selected_parent_cell"],
        "selected_cost": final["selected_cost"], "selected_raw_reward": final["selected_quality"],
        "terminal_native_ids": [_native_sha(action) for action in population],
        "terminal_native_costs": _native_record(final_costs),
        "terminal_raw_provider_quality": _native_record(last_values["effective_quality"]),
        "archive_reference_native_sha256": _native_sha(archive["selected_latent"][0]),
        "archive_reference_index": best, "archive_reference_cell": archive["selected_cell"],
        "archive_reference_fingerprint": archive["selected_fingerprint"],
        "archive_reference_raw_reward": archive["selected_quality"], "archive_reference_cost": archive["selected_cost"],
        "archive_reference_costs": _native_record(ac),
        "canonical_sources": batches, "parent_associations": parent_links, "archive_associations": archive_links,
        "decoded_reference_first8_diff_positions": differences,
        "decoded_reference_actual_prefix_diff_positions": [p for p in differences if p[0] < m],
        "stage_binding_sequence": binding["sequence"], "stage_raw_reward": bv["selected_raw_reward"],
        "stage_init_reward": bv["stage_init_reward"], "normalized_reward_written": bv["normalized_reward"],
        "archive_cost_spread_scale": bv["archive_cost_spread_scale"],
        "archive_cost_reference_sha256": _native_sha(ac), "reference_scope": "stored archive action decoded only; counterfactual outcome Unknown",
        "limits": "unique archive insertion ancestry and actual normalized Stage input Unknown; GPU scale reduction bound by original source/call tests, not recreated by CPU"}


def _audit_n3_feedback(kinds, context, final, events, previous):
    """N3-only native provenance gate on already SHA-verified CPU events."""
    def one(kind):
        require(len(kinds[kind]) == 1, "n3_missing_or_duplicate_" + kind)
        return kinds[kind][0]
    selection = one("execution_feedback_selection")
    feedback = selection["values"]
    selected, current = feedback["selected"], feedback["context"]
    require(type(feedback["active"]) is bool and type(selected["eligible"]) is bool, "n3_activity_invalid")
    require(current["global_step"] == context["global_step"] == selected["start_global_step"]
            and current["stage"] == context["values"]["stage"], "n3_context_step_or_stage_mismatch")
    require(len(context["values"]["providers"]) == 1 and current["provider_identity"]["source_text_sha256"]
            == context["values"]["providers"][0]["source_text_sha256"], "n3_provider_source_mismatch")
    require(selected["selected_native_sha256"] == _native_sha(final["selected_latent"][0]), "n3_selected_native_identity_mismatch")
    matched = []
    for score in kinds["scoring_inputs"]:
        value = score["values"]
        if value["scoring_scope"]["role"] not in {"canonical_initial", "canonical_offspring", "canonical_population"}:
            continue
        aggregates = [r["values"]["aggregate_before_reward_mode"] for r in kinds["scoring_aggregate"]
                      if r["values"]["scoring_batch_id"] == score["sequence"]]
        effective = [r["values"] for r in kinds["effective_quality"]
                     if r["values"]["scoring_batch_id"] == score["sequence"]][0]
        require(effective["provider_identity"] == current["provider_identity"]
                and effective["target_index"] == current["target_index"], "n3_semantic_context_mismatch")
        if not feedback["active"]:
            require(effective["quality"].dtype == aggregates[0].dtype
                    and torch.equal(effective["quality"], aggregates[0]), "n3_inactive_quality_not_raw")
        for index, sample in enumerate(value["samples"]):
            if _native_sha(sample) != selected["selected_native_sha256"]:
                continue
            origin = events[value["projection_origin_sequences"][index] - 1]["values"]["source_eef_position"]
            projection = value["projected_xyz"][index]
            raw = aggregates[0][index]
            matched.append((projection, origin, raw))
    require(bool(matched), "n3_selected_canonical_association_missing")
    association = [selected["projection"] == _native_record(p) and selected["source_origin"] == _native_record(o)
                   and selected["raw_provider_quality"] == _native_record(r) for p, o, r in matched]
    require(any(association), "n3_selected_projection_origin_or_raw_mismatch")
    if selected["eligible"]:
        require(all(association), "n3_eligible_selected_association_ambiguous")
        tracker = current["tracker_snapshot"]
        target = tracker["targets"][str(current["target_index"])]
        require(current["target_valid"] is True and target["valid"] is True
                and target["status"] == current["target_status"] in {"tracked", "static_background"}
                and tracker["instance_id"] == current["registry_instance_id"]
                and tracker["generation"] == current["registry_generation"], "n3_target_registry_invalid")
    require(selected["raw_provider_quality"]["values"] == final["selected_raw_provider_quality"], "n3_selected_raw_stage_mismatch")
    if feedback["active"]:
        require(selected["eligible"] and previous is not None, "n3_active_without_complete_predecessor")
        expected_previous = {k: v for k, v in previous["completed"].items() if k != "context"}
        require(feedback["previous"] == expected_previous, "n3_previous_not_actual_completed_ack")
        old = previous["context"]
        fields = ("episode_generation", "stage", "provider_identity", "target_index", "registry_instance_id", "registry_generation")
        require(all(old[k] == current[k] for k in fields) and old["target_valid"] is True
                and current["global_step"] == previous["completed"]["end_global_step"] + 1,
                "n3_feedback_continuity_mismatch")
    else:
        require(feedback["previous"] == {}, "n3_inactive_has_previous")
    commit = one("execution_feedback_commit")
    require(selection["sequence"] < commit["sequence"] < one("decision_committed")["sequence"], "n3_commit_order_invalid")
    require(commit["values"]["global_step"] == current["global_step"], "n3_commit_step_mismatch")
    acks = kinds["execution_feedback_ack"]
    require(type(commit["values"]["committed"]) is bool and isinstance(commit["values"]["history_reason"], str)
            and bool(commit["values"]["history_reason"]), "n3_commit_status_unknown")
    if not commit["values"]["committed"]:
        require(not feedback["active"] and not acks, "n3_active_or_ack_without_commit")
        return None
    require(selected["eligible"] and commit["values"]["selected_native_sha256"] == selected["selected_native_sha256"], "n3_commit_selected_mismatch")
    require(one("decision_committed")["values"]["execution_horizon"] == 8, "n3_committed_prefix_not_eight")
    dispatches, outcomes, returned = kinds["action_dispatch"], kinds["pre_reset_outcome"], kinds["step_returned"]
    sent = kinds["executed_action"]
    chunk = one("decision_committed")["values"]["action_chunk"]
    clear_reasons = {"actual_endpoint_missing_or_invalid", "acknowledged_action_identity_mismatch",
                     "duplicate_missing_or_out_of_order_ack"}
    explicit_inactive_clear = (not feedback["active"] and bool(acks)
        and acks[-1]["values"].get("history_reason") in clear_reasons)
    require(len(dispatches) == len(outcomes) == len(returned) == len(sent)
            and (len(acks) == len(dispatches) or (explicit_inactive_clear and 0 < len(acks) < len(dispatches))),
            "n3_ack_coverage_mismatch")
    completed = None
    for index, (ack, dispatch, outcome, result) in enumerate(zip(acks, dispatches, outcomes, returned), 1):
        av = ack["values"]
        endpoint = outcome["values"]["observation"]["robot0_eef_pos"]
        require(outcome["sequence"] < ack["sequence"] < result["sequence"], "n3_ack_order_invalid")
        if explicit_inactive_clear and index == len(acks):
            # Explicitly recorded pre-activation clear supplies no endpoint/residual proof.
            # Existing generic execution evidence remains checked; no absent event is inferred.
            require(av["completed"] is None, "n3_inactive_clear_has_completion")
            return None
        require(av["global_step"] == dispatch["global_step"] == outcome["global_step"] == result["global_step"]
                and av["execution_index"] == dispatch["values"]["execution_index"] == index
                and av["selected_native_sha256"] == selected["selected_native_sha256"], "n3_ack_identity_or_step_mismatch")
        require(tensor(av["action"]) and _native_record(av["action"]) == _native_record(chunk[0, index - 1])
                == _native_record(sent[index - 1]["values"]["action_numpy"]), "n3_ack_not_actual_committed_action")
        require(av["terminated"] == result["values"]["terminated"] and av["truncated"] == result["values"]["truncated"], "n3_ack_terminal_mismatch")
        terminal = av["terminated"] or av["truncated"]
        if terminal:
            # Existing automatic reset can mutate the returned nested view. It is never p8 history.
            require(av["completed"] is None, "n3_completed_before_eight_or_terminal")
            continue
        require(tensor(av["actual_endpoint"]) and _native_record(av["actual_endpoint"]) == _native_record(endpoint), "n3_ack_not_native_pre_reset_endpoint")
        if index == 8:
            projection, origin, _ = next(row for row, ok in zip(matched, association) if ok)
            residual = (endpoint.double() - origin.double()) - (projection[8].double() - projection[0].double())
            expected = {"context": current, "selected_native_sha256": selected["selected_native_sha256"],
                "start_global_step": current["global_step"], "end_global_step": av["global_step"], "ack_count": 8,
                "feedback_was_active": feedback["active"], "terminated": False, "truncated": False,
                "projection": _native_record(projection), "source_origin": _native_record(origin),
                "actual_endpoint": _native_record(endpoint), "residual": _native_record(residual)}
            require(av["completed"] == expected, "n3_completed_residual_or_identity_mismatch")
            completed = expected
        else:
            require(av["completed"] is None, "n3_completed_before_eight_or_terminal")
    return None if completed is None else {"context": current, "completed": completed}


def audit_episode(episode_dir, episode_compute_file):
    report = {"schema": "qd-ed-decision-evidence-audit-v1", "accepted": False,
              "episode_dir": str(Path(episode_dir).resolve()),
              "episode_compute_file": str(Path(episode_compute_file).resolve()),
              "original_execution_outcome": None, "evidence_complete": None,
              "observed_counts": None, "projection_dtypes": None, "errors": [],
              "identity_limit": "content fingerprints and allocated slots; original archive occurrences unknown",
              "action_linkage": "dispatch index links decoded and postprocessed actions; postprocessor is not recomputed"}
    try:
        root = Path(episode_dir)
        name_match = re.fullmatch(r"episode_(\d+)", root.name)
        require(name_match is not None, "episode_directory_name_invalid")
        episode = int(name_match.group(1))
        compute_rows = [json.loads(line) for line in Path(episode_compute_file).read_text().splitlines()]
        matching = [r for r in compute_rows if r.get("episode_id") == episode]
        require(len(matching) == 1, "execution_record_missing_or_ambiguous")
        execution = matching[0]
        report["original_execution_outcome"] = execution["outcome"]
        require(execution["outcome"] in ("completed", "execution_error", "preparation_error"), "execution_outcome_unknown")
        status = json.loads((root / "status.json").read_text())
        require(status["schema"] == "qd-ed-decision-evidence-v1" and status["episode"] == episode, "status_schema_or_episode_invalid")
        report["evidence_complete"] = status["complete"]
        require("decision_evidence" in execution, "execution_evidence_status_missing")
        events = load_events(root, status)
        counts = Counter(r["event"] for r in events)
        report["observed_counts"] = dict(counts)
        report["observed_counts_scope"] = "SHA-verified persisted events, never extrapolated to missing work"
        contexts = {r["decision_id"]: r for r in events if r["event"] == "decision_context"}
        require(len(contexts) == counts["decision_context"] == status["decisions"] > 0, "decision_count_invalid")
        require(counts["decision_committed"] == status["committed_decisions"] == len(contexts), "uncommitted_decision")
        require(all(r["decision_id"] in contexts for r in events), "unknown_decision")
        by_decision = defaultdict(list)
        for row in events:
            by_decision[row["decision_id"]].append(row)
        dtype_rows, scope_counts = [], Counter()
        expected_step, episode_ended, reset_sequence = 0, False, 0
        previous_decision, previous_stage = None, None
        previous_feedback_certificate = None
        for decision_id, context in contexts.items():
            context_value = context["values"]
            require(context_value["previous_decision_id"] == previous_decision
                    and context_value["previous_stage"] == previous_stage, "decision_context_link_mismatch")
            require(context_value["stage_changed"] == (previous_stage is not None and previous_stage != context_value["stage"]), "stage_change_mismatch")
            previous_decision, previous_stage = decision_id, context_value["stage"]
            providers = context_value["providers"]
            require([p["ordinal"] for p in providers] == list(range(len(providers))), "provider_identity_ordinals_invalid")
            for provider in providers:
                def valid_hash(value):
                    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
                require(valid_hash(provider.get("original_code_sha256")) or valid_hash(provider.get("source_text_sha256")), "provider_identity_missing")
                require(provider.get("original_identity_origin") in ("direct_callable", "loader_attached_original"), "provider_identity_origin_unknown")
            rows = by_decision[decision_id]
            kinds = defaultdict(list)
            for row in rows:
                kinds[row["event"]].append(row)
            require(rows[0] == context, "decision_context_not_first")
            def one(kind):
                require(len(kinds[kind]) == 1, "missing_or_duplicate_" + kind)
                return kinds[kind][0]
            decoded = one("policy_action_decode")["values"]
            committed = one("decision_committed")
            chunk = decoded["action_chunk"]
            require(tensor(chunk) and chunk.ndim == 3 and chunk.shape[0] == 1 and chunk.shape[2] == 7, "action_chunk_invalid")
            require(torch.equal(chunk, committed["values"]["action_chunk"]), "committed_action_mismatch")
            horizon = chunk.shape[1]
            require(0 < committed["values"]["execution_horizon"] <= horizon, "execution_horizon_invalid")
            require(decoded["selected_canonical_fingerprint"] == fingerprints(decoded["selected_latent"])[0], "decoded_fingerprint_mismatch")
            guided = context["values"]["use_guidance"] and bool(context["values"]["providers"])
            candidate_rows = kinds["canonical_candidate_batch"]
            dual_modes = {r["values"].get("quality_mode")
                          for kind in ("canonical_candidate_batch", "effective_quality", "final_selection")
                          for r in kinds[kind] if r["values"].get("quality_mode") in
                          {"executed_prefix_v1", "executed_feedback_v1"}}
            require(len(dual_modes) <= 1, "dual_quality_mixed_modes")
            dual_mode = next(iter(dual_modes), None)
            dual_active = dual_mode is not None
            known_candidates = defaultdict(list)
            known_dual_quality = defaultdict(list)
            for item in candidate_rows:
                value = item["values"]
                if dual_active:
                    require(value.get("quality_mode") == dual_mode, "n2_canonical_mode_missing")
                require(tensor(value["candidates"]), "candidate_tensor_invalid")
                fps = fingerprints(value["candidates"])
                require(fps == value["canonical_fingerprints"], "candidate_fingerprint_mismatch")
                require(value["occurrence_ids"] == [f"{decision_id}:q{item['sequence']}:r{i}" for i in range(len(fps))], "candidate_occurrence_invalid")
                require(tensor(value["effective_quality"]) and value["effective_quality"].shape == (len(fps),), "candidate_quality_invalid")
                for fp, quality in zip(fps, value["effective_quality"]):
                    known_candidates[fp].append(quality.item())
                if value.get("quality_mode") == dual_mode and dual_active:
                    raw = value.get("raw_provider_quality")
                    require(tensor(raw) and raw.shape == value["effective_quality"].shape
                            and raw.dtype == value["effective_quality"].dtype, "n2_candidate_raw_invalid")
                    for fp, quality, original in zip(fps, value["effective_quality"], raw):
                        known_dual_quality[fp].append((quality.item(), original.item()))
            if guided:
                require(bool(candidate_rows), "guided_candidates_missing")
                final = one("final_selection")["values"]
                fp = fingerprints(final["selected_latent"])[0]
                require(fp == final["selected_canonical_fingerprint"] == decoded["selected_canonical_fingerprint"], "selected_decode_mismatch")
                require(fp == fingerprints(final["population"])[final["selected_index"]], "selected_pool_mismatch")
                require(fp in known_candidates and final["selected_quality"] in known_candidates[fp], "selected_quality_not_observed")
                if dual_active:
                    require(final.get("quality_mode") == dual_mode, "n2_final_mode_missing")
                    raw = final.get("raw_provider_quality")
                    expected_raw_dtype = torch.float32 if final["selection_rule"] == "archive_global_best" else final["population"].dtype
                    require(tensor(raw) and raw.shape == (len(final["population"]),)
                            and raw.dtype == expected_raw_dtype, "n2_final_raw_invalid")
                    require(final.get("selected_raw_provider_quality") == raw[final["selected_index"]].item(), "n2_selected_raw_index_mismatch")
                    require((final["selected_quality"], final["selected_raw_provider_quality"])
                            in known_dual_quality[fp], "n2_selected_raw_not_observed")
            for item in kinds["parent_allocation"]:
                value = item["values"]
                fps = fingerprints(value["source_population"])
                require(value["source_fingerprints"] == fps, "parent_source_mismatch")
                require(value["parent_fingerprints"] == [fps[i] for i in value["parent_indices"].tolist()], "parent_selection_mismatch")
                require(value["original_archive_occurrences"] is None, "unsupported_archive_occurrence_claim")
            archive_rows = {r["values"]["iter_idx"]: r["values"] for r in kinds["archive_parent_allocation"]}
            for row in kinds["parent_allocation"]:
                value = row["values"]
                if value["iter_idx"] in archive_rows:
                    archive = archive_rows[value["iter_idx"]]
                    require(archive["parent_fingerprints"] == value["source_fingerprints"], "archive_allocation_mismatch")
                    require(len(archive["parent_lanes"]) == len(archive["parent_fingerprints"]), "archive_lanes_missing")
                    require(archive["original_archive_occurrences"] is None and isinstance(archive["weights"], dict), "archive_metadata_missing")
            score_ids = set()
            for score in kinds["scoring_inputs"]:
                score_id, value = score["sequence"], score["values"]
                score_ids.add(score_id)
                scope = value["scoring_scope"]
                role = scope["role"]
                require(role in ("canonical_initial", "canonical_offspring", "canonical_population",
                    "canonical_memory_fresh", "canonical_memory_adapted", "auxiliary_pretest"), "unknown_scoring_role")
                require(type(scope["iter_idx"]) is int and bool(scope["site"]), "scoring_site_missing")
                scope_counts[role] += 1
                samples, full, used = value["samples"], value["projected_xyz"], value["provider_input_xyz"]
                require(tensor(samples) and tensor(full) and tensor(used), "projection_nonfinite_or_missing")
                require(full.shape == (samples.shape[0], horizon + 1, 3), "full_projection_incomplete")
                require(value["slice_kind"] == "eds" and used.dtype == full.dtype and torch.equal(used, full[:, 1:horizon, :3]), "provider_projection_slice_mismatch")
                origins = value["projection_origin_sequences"]
                require(origins is not None and len(origins) == samples.shape[0], "initial_eef_origin_missing")
                for index, sequence in enumerate(origins):
                    origin = events[sequence - 1]
                    require(origin["event"] == "projection_origin" and origin["decision_id"] == decision_id and sequence < score_id, "projection_origin_link_invalid")
                    require(tensor(origin["values"]["source_eef_position"]), "native_eef_origin_missing")
                    require(torch.equal(origin["values"]["cast_eef_start"], full[index, 0]), "projection_t0_mismatch")
                dtype_rows.append({"decision_id": decision_id, "scoring_batch_id": score_id,
                    "sample_dtype": str(samples.dtype), "projection_dtype": str(full.dtype),
                    "points_including_t0": full.shape[1]})
                related = lambda kind: [r["values"] for r in kinds[kind] if r["values"]["scoring_batch_id"] == score_id]
                returned, effective, aggregates = related("provider_return"), related("effective_quality"), related("scoring_aggregate")
                expected = [(i, j) for i in range(samples.shape[0]) for j in range(len(context["values"]["providers"]))]
                require([(v["candidate_index"], v["provider_ordinal"]) for v in returned] == expected, "provider_return_coverage_invalid")
                require(len(effective) == len(aggregates) == 1, "effective_quality_missing_or_duplicate")
                require(all(v["scoring_scope"] == scope for v in returned + effective + aggregates), "scoring_role_link_mismatch")
                identity_fields = ("code_sha256", "original_code_sha256", "source_text_sha256", "source_path")
                for value in returned:
                    linked = value["context_provider_ordinal"]
                    require(type(linked) is int and 0 <= linked < len(providers), "provider_context_link_missing")
                    require(all(providers[linked].get(k) == providers[value["provider_ordinal"]].get(k)
                                for k in identity_fields), "provider_context_identity_mismatch")
                require(all((tensor(v.get("result")) and v["result"].numel() == 1)
                    or (type(v.get("result")) in (int, float, bool) and math.isfinite(v["result"]))
                    for v in returned), "raw_provider_result_missing_or_invalid")
                require(tensor(effective[0]["quality"]) and effective[0]["quality"].shape == (samples.shape[0],)
                    and torch.equal(effective[0]["quality"], -effective[0]["costs"]), "effective_quality_cost_mismatch")
                require(tensor(aggregates[0]["aggregate_before_reward_mode"])
                    and aggregates[0]["aggregate_before_reward_mode"].shape == (samples.shape[0],), "aggregate_quality_invalid")
                if dual_active and scope["role"] in ("canonical_initial", "canonical_offspring", "canonical_population"):
                    require(effective[0].get("quality_mode") == dual_mode, "n2_effective_mode_missing")
                if effective[0].get("quality_mode") == dual_mode and dual_active:
                    require(scope["role"] in ("canonical_initial", "canonical_offspring", "canonical_population"), "n2_auxiliary_quality_changed")
                    raw = effective[0].get("raw_provider_quality")
                    aggregate = aggregates[0]["aggregate_before_reward_mode"]
                    require(tensor(raw) and raw.shape == aggregate.shape and raw.dtype == aggregate.dtype
                            and torch.equal(raw, aggregate), "n2_raw_aggregate_mismatch")
                    require(effective[0]["reward_mode"] == "normal", "n2_reward_mode_invalid")
            for kind in ("provider_return", "effective_quality", "scoring_aggregate"):
                require(all(r["values"]["scoring_batch_id"] in score_ids for r in kinds[kind]), "orphan_score_result")
            if guided:
                require(bool(score_ids), "guided_scoring_missing")
                iterations = [r["values"]["iter_idx"] for r in candidate_rows]
                require(iterations == list(range(-1, len(iterations) - 1)), "canonical_iteration_gap")
                offspring_iters = [r["values"]["scoring_scope"]["iter_idx"] for r in kinds["scoring_inputs"]
                                   if r["values"]["scoring_scope"]["role"] == "canonical_offspring"]
                require(offspring_iters == iterations[1:], "canonical_offspring_count_mismatch")
                require([r["values"]["iter_idx"] for r in kinds["parent_allocation"]] == iterations[1:], "parent_allocation_count_mismatch")
                if final["selection_rule"] == "archive_global_best":
                    require(list(archive_rows) == iterations[1:], "archive_allocation_missing")
                initial_roles = Counter(r["values"]["scoring_scope"]["role"] for r in kinds["scoring_inputs"]
                                        if r["values"]["scoring_scope"]["iter_idx"] == -1)
                require(initial_roles == {"canonical_initial": 1} or initial_roles == {
                    "canonical_memory_fresh": 1, "canonical_memory_adapted": 1}, "canonical_initial_count_mismatch")
            pending, prefixes = None, 0
            for row in rows:
                require(row["reset_sequence"] == reset_sequence, "reset_sequence_mismatch")
                kind, value = row["event"], row["values"]
                if kind == "action_dispatch":
                    require(not episode_ended and pending is None and row["sequence"] > committed["sequence"], "dispatch_before_commit_or_after_terminal_or_overlapping")
                    prefixes += 1
                    require(row["global_step"] == expected_step and value["execution_index"] == prefixes, "execution_prefix_gap")
                    require(prefixes <= committed["values"]["execution_horizon"], "execution_past_committed_horizon")
                    pending = {"step": expected_step, "sent": False, "outcome": None, "reset": False}
                elif kind in ("executed_action", "pre_reset_outcome", "automatic_reset_boundary", "step_returned"):
                    require(pending is not None and row["global_step"] == pending["step"], "orphan_execution_event")
                    if kind == "executed_action":
                        require(not pending["sent"] and tensor(value["action_numpy"]) and value["action_numpy"].shape == (7,), "executed_action_invalid")
                        pending["sent"] = True
                    elif kind == "pre_reset_outcome":
                        require(pending["sent"] and pending["outcome"] is None, "outcome_order_invalid")
                        require(tensor(value["observation"].get("robot0_eef_pos")), "executed_eef_missing")
                        pending["outcome"] = value
                    elif kind == "automatic_reset_boundary":
                        require(pending["outcome"] is not None and pending["outcome"]["terminated"] and not pending["reset"], "reset_without_terminal")
                        require(value["reset_will_follow"] is True and value["reset_completed"] is None, "reset_claim_invalid")
                        pending["reset"] = True
                        reset_sequence += 1
                    else:
                        outcome = pending["outcome"]
                        require(outcome is not None and value["terminated"] == outcome["terminated"] and value["success"] == outcome["success"], "returned_outcome_mismatch")
                        require(not value["terminated"] or pending["reset"], "terminal_reset_boundary_missing")
                        expected_step += 1
                        episode_ended = bool(value["terminated"] or value["truncated"])
                        pending = None
            require(pending is None and prefixes > 0, "unfinished_or_unexecuted_decision")
            n4_markers = any(r["values"].get("selection_rule") == "terminal_population_first_argmin"
                             or r["values"].get("qd_final_selection_mode") == "terminal_population_v1"
                             or "terminal_population" in r["values"] for r in kinds["final_selection"])
            if n4_markers or kinds["terminal_population_stage_binding"]:
                require(guided and not dual_active, "n4_unguided_or_dual_quality")
                n4 = _audit_n4_terminal_population(kinds, context, one("final_selection"))
                gate = report.setdefault("n4_terminal_population_audit", {
                    "schema": "n4-native-terminal-population-audit-v1", "checked_decisions": 0,
                    "canonical_batches_verified": 0, "canonical_candidates_verified": 0,
                    "parent_rounds_verified": 0, "actual_actions_verified": 0,
                    "decoded_reference_first8_different_decisions": 0,
                    "decoded_reference_actual_prefix_different_decisions": 0,
                    "decisions": [], "scope": "N4 last canonical16 native-cost first-index consumer, all canonical/parent associations, original raw/Stage metadata and deployed actual command linkage; stored archive-reference decoding is not a counterfactual rollout"})
                gate["checked_decisions"] += 1
                for field in ("canonical_batches_verified", "canonical_candidates_verified", "parent_rounds_verified"):
                    gate[field] += n4[field]
                gate["actual_actions_verified"] += n4["actual_prefix_length"]
                gate["decoded_reference_first8_different_decisions"] += int(bool(n4["decoded_reference_first8_diff_positions"]))
                gate["decoded_reference_actual_prefix_different_decisions"] += int(bool(n4["decoded_reference_actual_prefix_diff_positions"]))
                gate["decisions"].append(n4)
            if dual_mode == "executed_feedback_v1":
                previous_feedback_certificate = _audit_n3_feedback(
                    kinds, context, final, events, previous_feedback_certificate)
                gate = report.setdefault("n3_feedback_audit", {"schema": "n3-native-feedback-audit-v1",
                    "checked_decisions": 0, "active_previous_ack_verified": 0, "inactive_decisions": 0,
                    "uncommitted_clears": 0, "inactive_ack_clears_unknown": 0, "complete_nonterminal_prefixes": 0,
                    "scope": "recognized N3 decisions; native canonical selected projection/origin/raw; nonterminal acknowledged command/EEF; immediate complete predecessor/residual; explicit inactive clears and terminal endpoints are excluded from usable feedback; no task-effect claim"})
                gate["checked_decisions"] += 1
                gate["active_previous_ack_verified" if kinds["execution_feedback_selection"][0]["values"]["active"] else "inactive_decisions"] += 1
                gate["uncommitted_clears"] += int(not kinds["execution_feedback_commit"][0]["values"]["committed"])
                gate["complete_nonterminal_prefixes"] += int(previous_feedback_certificate is not None)
                acknowledgements = kinds["execution_feedback_ack"]
                gate["inactive_ack_clears_unknown"] += int(bool(acknowledgements) and
                    acknowledgements[-1]["values"].get("history_reason") in {
                        "actual_endpoint_missing_or_invalid", "acknowledged_action_identity_mismatch",
                        "duplicate_missing_or_out_of_order_ack"})
            else:
                previous_feedback_certificate = None
        require(episode_ended, "episode_terminal_return_missing")
        report["projection_dtypes"] = dtype_rows
        report["observed_scoring_roles"] = dict(scope_counts)
        require(status["complete"] is True and status["failed"] is False and status["pending_action"] is False, "evidence_status_incomplete")
        observed_status = execution["decision_evidence"]
        require(observed_status["complete"] is True and observed_status["failed"] is False and observed_status["bundles"] == status["bundles"], "execution_audit_status_incomplete_or_mismatch")
        report["accepted"] = True
    except Exception as error:
        report["errors"].append(str(error) if isinstance(error, AuditFailure) else "invalid_or_missing_evidence:" + type(error).__name__)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_dir", type=Path)
    parser.add_argument("--episode-compute", type=Path, required=True)
    args = parser.parse_args()
    report = audit_episode(args.episode_dir, args.episode_compute)
    print(json.dumps(report, allow_nan=False, sort_keys=True))
    return 0 if report["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
