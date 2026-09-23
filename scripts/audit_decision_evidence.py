#!/usr/bin/env python3
"""Offline, single-episode evidence gate; never changes execution outcomes.

Requires explicit paths. Loads only named, SHA-verified bundles with weights_only.
Content fingerprints identify equal actions, not original archive occurrences.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
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
            n2_active = any(r["values"].get("quality_mode") == "executed_prefix_v1"
                            for kind in ("canonical_candidate_batch", "effective_quality", "final_selection")
                            for r in kinds[kind])
            known_candidates = defaultdict(list)
            known_dual_quality = defaultdict(list)
            for item in candidate_rows:
                value = item["values"]
                if n2_active:
                    require(value.get("quality_mode") == "executed_prefix_v1", "n2_canonical_mode_missing")
                require(tensor(value["candidates"]), "candidate_tensor_invalid")
                fps = fingerprints(value["candidates"])
                require(fps == value["canonical_fingerprints"], "candidate_fingerprint_mismatch")
                require(value["occurrence_ids"] == [f"{decision_id}:q{item['sequence']}:r{i}" for i in range(len(fps))], "candidate_occurrence_invalid")
                require(tensor(value["effective_quality"]) and value["effective_quality"].shape == (len(fps),), "candidate_quality_invalid")
                for fp, quality in zip(fps, value["effective_quality"]):
                    known_candidates[fp].append(quality.item())
                if value.get("quality_mode") == "executed_prefix_v1":
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
                if n2_active:
                    require(final.get("quality_mode") == "executed_prefix_v1", "n2_final_mode_missing")
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
                if n2_active and scope["role"] in ("canonical_initial", "canonical_offspring", "canonical_population"):
                    require(effective[0].get("quality_mode") == "executed_prefix_v1", "n2_effective_mode_missing")
                if effective[0].get("quality_mode") == "executed_prefix_v1":
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
