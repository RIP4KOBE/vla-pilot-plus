"""Independent N24 witness replay; no production cache/archive helper imports."""
import hashlib
import math

import torch


MODE = "canonical_full_close_v1"


def audit_rescue(kinds, context, require, fingerprints):
    def same(a, b):
        return (torch.is_tensor(a) and torch.is_tensor(b) and a.dtype == b.dtype
                and a.shape == b.shape and a.device.type == b.device.type == "cpu"
                and torch.equal(a.contiguous().reshape(-1).view(torch.uint8), b.contiguous().reshape(-1).view(torch.uint8)))

    def check(a, b, name):
        if torch.is_tensor(b):
            require(same(a, b), "n24_" + name)
        else:
            if type(b) in (bool, int, float, str, type(None)):
                require(type(a) is type(b), "n24_type_" + name)
            require(a == b, "n24_" + name)

    def indexed(kind, iterations):
        rows = kinds[kind]
        require(len(rows) == len(iterations) and [r["values"].get("iter_idx") for r in rows] == iterations,
                "n24_coverage_" + kind)
        return {r["values"]["iter_idx"]: r for r in rows}

    require(len(kinds["gripper_rescue_begin"]) == 1 and len(kinds["final_selection"]) == 1,
            "n24_begin_final_coverage")
    begin = kinds["gripper_rescue_begin"][0]; bv = begin["values"]
    final = kinds["final_selection"][0]["values"]
    require(bv.get("mode") == final.get("gripper_rescue_mode") == MODE
            and final.get("quality_mode") == "actuator_clipped_provider_v1"
            and bv.get("sparse_exponent") == 1.0 and type(bv.get("run_seed")) is int,
            "n24_explicit_mode")
    canonical = indexed("canonical_candidate_batch", list(range(-1, 10)))
    assignments = indexed("qd_descriptor_assignment", list(range(-1, 10)))
    updates = indexed("gripper_rescue_cache", list(range(-1, 10)))
    overrides = indexed("gripper_rescue_parents", list(range(10)))
    allocations = indexed("archive_parent_allocation", list(range(10)))
    parents = indexed("parent_allocation", list(range(10)))
    scoring = {r["sequence"]: r for r in kinds["scoring_inputs"]}
    effective = {r["values"]["scoring_batch_id"]: r for r in kinds["effective_quality"]}
    ctx = bv["context"]
    require(ctx["episode"] == context["episode"] and ctx["global_step"] == context["global_step"]
            and ctx["stage"] == context["values"]["stage"], "n24_context")
    require(len(kinds["actuator_metadata_snapshot"]) == 1, "n24_actuator_context_missing")
    check(ctx["controller"], kinds["actuator_metadata_snapshot"][0]["values"]["metadata"]["context"], "controller_context")
    archive, visits, history, best = {}, [0] * 16, [], None
    actual_allocations, substitutions, updated_count = {}, 0, 0
    all_occurrences = set()

    for iteration in range(-1, 10):
        row = canonical[iteration]; cv = row["values"]
        assignment = assignments[iteration]; dv = assignment["values"]
        update = updates[iteration]; uv = update["values"]
        sid = dv["scoring_batch_id"]
        require(sid in scoring and sid in effective and row["sequence"] < assignment["sequence"] < update["sequence"],
                "n24_canonical_order")
        source, ev = scoring[sid]["values"], effective[sid]["values"]
        for field in ("decision_id", "reset_sequence", "global_step", "episode"):
            require(all(record[field] == context[field] for record in (row, assignment, update)), "n24_event_context")
        points = source["keypoints"].contiguous()
        check(ctx["keypoints"], {"dtype": str(points.dtype), "shape": list(points.shape),
            "sha256": hashlib.sha256(points.view(torch.uint8).numpy().tobytes()).hexdigest()}, "target_identity")
        check(ctx["provider"], ev["provider_identity"], "provider_identity")
        check(uv["context"], ctx, "cache_context")
        for name, key in (("bounds_lo", "bounds_lo"), ("bounds_hi", "bounds_hi")):
            check(dv[name], bv[key], "fixed_bounds")
        actions, quality, costs, raw = cv["candidates"], cv["effective_quality"], ev["costs"], cv["raw_provider_quality"]
        require(actions.shape == (16,64,128) and actions.dtype in (torch.float32, torch.bfloat16)
                and torch.isfinite(actions).all(), "n24_actions")
        for value in (quality, costs, raw):
            require(value.shape == (16,) and value.dtype == actions.dtype and torch.isfinite(value).all(), "n24_native_values")
        check(costs, -quality, "cost_quality")
        check(quality, ev["quality"], "quality_source")
        check(raw, ev["raw_provider_quality"], "raw_source")
        check(actions, source["samples"], "action_source")
        fps = fingerprints(actions)
        check(cv["canonical_fingerprints"], fps, "canonical_fingerprints")
        ids = [f"{context['decision_id']}:q{row['sequence']}:r{i}" for i in range(16)]
        check(cv["occurrence_ids"], ids, "occurrence_ids")
        require(not all_occurrences.intersection(ids), "n24_duplicate_occurrences")
        all_occurrences.update(ids)
        mode = (actions[:, :8, 10] >= 0).all(dim=1)
        check(uv["full_close_rows"], torch.nonzero(mode).flatten(), "full_close_predicate")
        changed = False
        update_count = 0
        for index in range(16):
            candidate = {"iteration": iteration, "row": index,
                "action": actions[index], "cost": costs[index], "quality": quality[index], "raw": raw[index],
                "descriptor": dv["descriptors"][index], "cell": int(dv["cell_ids"][index]),
                "fingerprint": fps[index], "canonical_sequence": row["sequence"],
                "scoring_batch_id": sid, "occurrence_id": ids[index]}
            history.append(candidate)
            if mode[index] and (best is None or float(candidate["cost"]) < float(best["cost"])):
                best, changed = candidate, True
                update_count += 1
            cell = candidate["cell"]; visits[cell] += 1
            old = archive.get(cell)
            if old is None or (-float(candidate["quality"]), candidate["fingerprint"]) < (-float(old["quality"]), old["fingerprint"]):
                archive[cell] = candidate
        check(uv["updated"], changed, "cache_update")
        check(uv["update_count"], update_count, "cache_update_count")
        updated_count += update_count

        def verify_reference(record):
            if best is None:
                check(record, None, "empty_cache")
                return
            require(isinstance(record, dict) and set(record) == set(best) - {"action"}, "n24_cache_reference_fields")
            for name, value in best.items():
                if name != "action": check(record[name], value, "cache_" + name)

        verify_reference(uv["cache"])
        if iteration == 9:
            continue
        i = iteration + 1
        alloc, override, parent = allocations[i], overrides[i], parents[i]
        av, ov, pv = alloc["values"], override["values"], parent["values"]
        require(update["sequence"] < alloc["sequence"] < override["sequence"] < parent["sequence"]
                < scoring[assignments[i]["values"]["scoring_batch_id"]]["sequence"], "n24_parent_causal_order")
        for record in (alloc, override, parent):
            require(all(record[field] == context[field] for field in ("decision_id","reset_sequence","global_step","episode")), "n24_parent_context")
        # Independent reconstruction of unmodified fixed sparse allocation.
        occupied = sorted(archive)
        seed = int.from_bytes(hashlib.sha256(f"{bv['run_seed']}:{ctx['episode']}:{ctx['global_step']}:{i}".encode("ascii")).digest()[:8], "big") & ((1 << 63) - 1)
        generator = torch.Generator(device="cpu").manual_seed(seed)
        permutation = torch.randperm(len(occupied), generator=generator).tolist()
        ranks = {occupied[offset]: rank for rank, offset in enumerate(permutation)}
        weights = {cell: (float(visits[cell]) + 1.) ** -1.0 for cell in occupied}
        total = sum(weights.values())
        exact = {cell: 16 * weights[cell] / total for cell in occupied}
        counts = {cell: math.floor(exact[cell]) for cell in occupied}
        for cell in sorted(occupied, key=lambda c: (-(exact[c] - counts[c]), ranks[c]))[:16-sum(counts.values())]:
            counts[cell] += 1
        cells = [cell for cell in occupied for _ in range(counts[cell])]
        entries = [archive[cell] for cell in cells]
        original = torch.stack([item["action"] for item in entries])
        descriptors = torch.stack([item["descriptor"] for item in entries])
        vectors = {name: torch.tensor([float(item[key]) for item in entries], dtype=torch.float32)
                   for name, key in (("parent_costs","cost"),("parent_rewards","quality"),("parent_raw_rewards","raw"))}
        for name, value in vectors.items(): check(av[name], value, "original_" + name)
        for name, value in (("parent_cell_ids",torch.tensor(cells)),("parent_fingerprints",[e["fingerprint"] for e in entries]),
                ("parent_lanes",["quality"]*16),("slot_counts",{str(k):v for k,v in counts.items()}),
                ("sparse_slot_counts",{str(k):v for k,v in counts.items()}),("weights",{str(k):v for k,v in weights.items()})):
            check(av[name], value, "original_" + name)
        require(av["global_quality_anchor_count"] == 0 and av["secondary_parent_count"] == 0, "n24_original_lanes")
        check(ov["original_actions"], original, "original_actions")
        check(ov["original_descriptors"], descriptors, "original_descriptors")
        check(ov["context"], ctx, "supply_context"); verify_reference(ov["cache"])
        mask = (original[:, :8, 10] >= 0).all(dim=1)
        check(ov["original_full_close_mask"], mask, "original_predicate")
        slot = int(torch.argmax(vectors["parent_costs"])) if best is not None and not mask.any() else None
        check(ov["replacement_slot"], slot, "first_worst_slot")
        require(ov["mode"] == pv.get("gripper_rescue_mode") == MODE and ov["exact_survivor"] is False
                and ov["original_is_archive_allocation"] is True and ov["actual_is_archive_allocation"] == (slot is None), "n24_mode_or_archive_claim")
        actual = original.clone(); actual_desc = descriptors.clone(); actual_cells = torch.tensor(cells)
        if slot is not None:
            actual[slot] = best["action"]; actual_desc[slot] = best["descriptor"]; actual_cells[slot] = best["cell"]
            for name, key in (("parent_costs","cost"),("parent_rewards","quality"),("parent_raw_rewards","raw")):
                vectors[name][slot] = best[key]
        for name, value in (("actual_actions",actual),("actual_costs",vectors["parent_costs"]),
                ("actual_quality",vectors["parent_rewards"]),("actual_raw",vectors["parent_raw_rewards"]),
                ("actual_cells",actual_cells),("actual_descriptors",actual_desc)):
            check(ov[name], value, name)
        for name, value in (("source_population",actual),("source_costs",vectors["parent_costs"]),
                ("source_quality",vectors["parent_rewards"]),("source_raw_rewards",vectors["parent_raw_rewards"]),
                ("parent_cell_ids",actual_cells),("parent_indices",torch.arange(16))):
            check(pv[name], value, "ed_" + name)
        require(pv["elite_count"] == 0, "n24_no_exact_survivor")
        check(pv["offspring_sources"], ["qd_gripper_rescue_offspring" if j == slot else "qd_archive_offspring" for j in range(16)], "ed_sources")
        actual_allocations[i] = {**av, **vectors, "parent_cell_ids":actual_cells,
                                "parent_fingerprints":fingerprints(actual)}
        substitutions += int(slot is not None)
    # The cache must never become an extra spatial-archive insertion, including
    # after the last allocation where the next-round witness cannot expose it.
    ar = final["archive_reference"]
    ordered = [archive[cell] for cell in sorted(archive)]
    check(ar["population"], torch.stack([item["action"] for item in ordered]), "final_archive_actions")
    check(ar["cell_ids"], torch.tensor(sorted(archive)), "final_archive_cells")
    check(ar["costs"], torch.tensor([float(item["cost"]) for item in ordered]), "final_archive_costs")
    check(ar["rewards"], torch.tensor([float(item["quality"]) for item in ordered]), "final_archive_quality")
    return {"checked_decisions":1,"canonical_batches_verified":11,"canonical_candidates_verified":176,
            "parent_rounds_verified":10,"cache_updates":updated_count,"substitutions":substitutions}, actual_allocations
