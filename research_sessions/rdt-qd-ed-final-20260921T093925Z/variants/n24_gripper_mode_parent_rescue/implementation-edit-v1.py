from pathlib import Path
import hashlib,json
w=Path.cwd()
p=w/'core/rdt_policy_steer.py';s=p.read_text()
def replace(a,b):
 global s
 assert a in s,a[:80];s=s.replace(a,b,1)
replace('from core.qd_ed import (','from core.qd_gripper_parent_rescue import (\n    MODE as GRIPPER_RESCUE_MODE, CanonicalCloseCache, native_identity,\n)\nfrom core.qd_ed import (')
replace('    qd_quality_mode: str = "provider"','    qd_quality_mode: str = "provider"\n    qd_gripper_rescue_mode: str = "none"')
replace('        def record_shadow_qd_candidates(','''        rescue_cache = None
        canonical_link = {}
        def rescue_context():
            return {"episode": int(getattr(self, "_eds_episode_index", 0)),
                    "global_step": int(global_step), "stage": int(current_stage),
                    "provider": dict(quality_contract.identity),
                    "controller": dict(quality_contract.metadata["context"]),
                    "keypoints": native_identity(keypoints)}

        def observe_rescue(iteration, descriptors, cells):
            if rescue_cache is None:
                return
            started = time.perf_counter()
            witness = rescue_cache.observe(iteration=iteration, actions=population,
                costs=population_scores, quality=population_rewards,
                raw=original_rewards(population_info, population_rewards, population),
                descriptors=descriptors, cells=cells, context=rescue_context(),
                bounds=(qd_bounds.lo, qd_bounds.hi), **canonical_link)
            metrics.qd_gripper_rescue_checks += 16
            metrics.qd_gripper_rescue_updates += int(witness["updated"])
            evidence = getattr(self, "_decision_evidence", None)
            if evidence is not None:
                evidence.record("gripper_rescue_cache", **witness)
            metrics.qd_gripper_rescue_overhead_seconds += time.perf_counter() - started

        def record_shadow_qd_candidates(''')
replace('            nonlocal terminal_canonical_sequence, terminal_scoring_batch_id','            nonlocal terminal_canonical_sequence, terminal_scoring_batch_id, canonical_link')
replace('                if terminal_mode and iter_idx == 9:\n                    terminal_canonical_sequence', '''                canonical_link = {"canonical_sequence": sequence,
                    "scoring_batch_id": evidence.scoring_batch_id, "decision_id": evidence.decision_id}
                if terminal_mode and iter_idx == 9:
                    terminal_canonical_sequence''')
replace('            qd_archive = QDArchive(','''            if cfg.qd_gripper_rescue_mode == GRIPPER_RESCUE_MODE:
                rescue_cache = CanonicalCloseCache(rescue_context(), (qd_bounds.lo, qd_bounds.hi))
                metrics.qd_gripper_rescue_mode = GRIPPER_RESCUE_MODE
                evidence = getattr(self, "_decision_evidence", None)
                if evidence is not None:
                    evidence.record("gripper_rescue_begin", mode=GRIPPER_RESCUE_MODE,
                        context=rescue_context(), run_seed=cfg.shuffle_seed,
                        sparse_exponent=cfg.qd_sparse_exponent,
                        bounds_lo=qd_bounds.lo, bounds_hi=qd_bounds.hi)
                observe_rescue(-1, initial_descriptors, initial_cell_ids)
            qd_archive = QDArchive(''')
replace('                population = allocation.parent_actions.to(','''                rescue_actual = None
                if rescue_cache is not None:
                    started = time.perf_counter()
                    original_descriptors = torch.stack([
                        qd_archive.entries[int(cell)].descriptor_xy_m
                        for cell in allocation.parent_cell_ids.tolist()])
                    rescue_actual = rescue_cache.supply(allocation, original_descriptors,
                        iteration=i, context=rescue_context(), bounds=(qd_bounds.lo, qd_bounds.hi))
                    metrics.qd_gripper_rescue_substitutions += int(rescue_actual.slot is not None)
                    metrics.qd_gripper_rescue_actual_cells_by_iter.append(rescue_actual.cells.tolist())
                    if evidence is not None:
                        evidence.record("gripper_rescue_parents", **rescue_actual.witness,
                            original_actions=allocation.parent_actions,
                            original_descriptors=original_descriptors,
                            actual_actions=rescue_actual.actions, actual_costs=rescue_actual.costs,
                            actual_quality=rescue_actual.quality, actual_raw=rescue_actual.raw,
                            actual_cells=rescue_actual.cells, actual_descriptors=rescue_actual.descriptors)
                    metrics.qd_gripper_rescue_overhead_seconds += time.perf_counter() - started
                population = (rescue_actual.actions if rescue_actual else allocation.parent_actions).to(''')
replace('                population_scores = allocation.parent_costs.to(','                population_scores = (rescue_actual.costs if rescue_actual else allocation.parent_costs).to(')
replace('                population_rewards = allocation.parent_rewards.to(','                population_rewards = (rescue_actual.quality if rescue_actual else allocation.parent_rewards).to(')
replace('                qd_parent_cell_ids = allocation.parent_cell_ids.to(','                qd_parent_cell_ids = (rescue_actual.cells if rescue_actual else allocation.parent_cell_ids).to(')
replace('''                    metrics.qd_parent_descriptor_values_by_iter.append([
                        qd_archive.entries[int(cell)].descriptor_xy_m.detach().float().cpu().tolist()
                        for cell in allocation.parent_cell_ids.tolist()
                    ])''','''                    metrics.qd_parent_descriptor_values_by_iter.append(
                        rescue_actual.descriptors.detach().float().cpu().tolist() if rescue_actual else [
                        qd_archive.entries[int(cell)].descriptor_xy_m.detach().float().cpu().tolist()
                        for cell in allocation.parent_cell_ids.tolist()])''')
replace('                occupied_count = len(qd_archive.entries)','''                if rescue_actual is not None and rescue_actual.slot is not None:
                    chunk_population_sources = tuple(
                        "qd_gripper_rescue" if slot == rescue_actual.slot else source
                        for slot, source in enumerate(chunk_population_sources))
                occupied_count = len(qd_archive.entries)''')
replace('                if survivor_slots:\n                    parent_selection_kinds', '''                if rescue_actual is not None and rescue_actual.slot is not None:
                    parent_selection_kinds[rescue_actual.slot] = "qd_gripper_rescue"
                if survivor_slots:
                    parent_selection_kinds''')
replace('                if allocation.secondary_parent_count:\n                    qd_parent_count_by_source', '''                if rescue_actual is not None and rescue_actual.slot is not None:
                    qd_parent_count_by_source["qd_archive_offspring"] -= 1
                    qd_parent_count_by_source["qd_gripper_rescue_offspring"] = 1
                if allocation.secondary_parent_count:
                    qd_parent_count_by_source''')
replace('                                offspring_sources=plan.offspring_sources)','''                                offspring_sources=plan.offspring_sources,
                                **({"gripper_rescue_mode": GRIPPER_RESCUE_MODE,
                                    "source_raw_rewards": rescue_actual.raw}
                                   if rescue_cache is not None else {}))''')
replace('                if terminal_mode and i == 9:\n                    # Freeze', '''                observe_rescue(i, child_descriptors, child_cell_ids)
                if terminal_mode and i == 9:
                    # Freeze''')
replace('            evidence.record("final_selection", population=population, selected_latent=selected,','''            evidence.record("final_selection", population=population, selected_latent=selected,
                            **({"gripper_rescue_mode": GRIPPER_RESCUE_MODE} if rescue_cache is not None else {}),''')
replace('            qd_quality_mode=str(cfg.get("qd_quality_mode", "provider")),','''            qd_quality_mode=str(cfg.get("qd_quality_mode", "provider")),
            qd_gripper_rescue_mode=str(cfg.get("qd_gripper_rescue_mode", "none")),''')
replace('        if resolved.qd_degenerate_fallback_policy not in {"none", "control_v1"}:','''        if resolved.qd_gripper_rescue_mode not in {"none", GRIPPER_RESCUE_MODE}:
            raise ValueError("Unsupported QD gripper rescue mode")
        if resolved.qd_gripper_rescue_mode == GRIPPER_RESCUE_MODE:
            required_rescue = {"qd_quality_mode": ACTUATOR_CLIPPED_MODE,
                "qd_parent_survivor_count": 0, "qd_sparse_exponent": 1.0,
                "qd_metrics_observer": True, "qd_tie_break": "stable_fingerprint",
                "qd_overflow_policy": "clamp_edge"}
            for field_name, expected in required_rescue.items():
                if getattr(resolved, field_name) != expected:
                    raise ValueError(f"N24 parent rescue requires {field_name}={expected!r}")
        if resolved.qd_degenerate_fallback_policy not in {"none", "control_v1"}:''')
p.write_text(s)
p=w/'core/decision_evidence.py';s=p.read_text().replace('frozen["source_identity_scope"] = "eligible pool slots, which QD has already allocated; not original archive occurrences"','frozen["source_identity_scope"] = ("actual parent pool after conditional N24 canonical rescue; not an archive membership claim"\n                    if frozen.get("gripper_rescue_mode") == "canonical_full_close_v1" else\n                    "eligible pool slots, which QD has already allocated; not original archive occurrences")');p.write_text(s)
p=w/'core/eds_eval_metrics.py';s=p.read_text().replace('    qd_quality_mode: str = "provider"','''    qd_gripper_rescue_mode: str = "none"
    qd_gripper_rescue_checks: int = 0
    qd_gripper_rescue_updates: int = 0
    qd_gripper_rescue_substitutions: int = 0
    qd_gripper_rescue_actual_cells_by_iter: list[list[int]] = field(default_factory=list)
    qd_gripper_rescue_overhead_seconds: float = 0.0
    qd_gripper_rescue_allocation_scope: str = "qd slots/weights/coverage describe original archive allocation; actual cells/descriptors/source counts include rescue"
    qd_quality_mode: str = "provider"''').replace('        payload = _to_json_safe(self)','''        payload = _to_json_safe(self)
        if self.qd_gripper_rescue_mode == "none":
            for key in list(payload):
                if key.startswith("qd_gripper_rescue_"):
                    payload.pop(key)''');p.write_text(s)
p=w/'configs/config.yaml';s=p.read_text().replace('    qd_quality_mode: provider','    qd_quality_mode: provider\n    qd_gripper_rescue_mode: none');p.write_text(s)
p=w/'configs/qd_ed_final/candidate_n23.json';parent=json.loads(p.read_text());candidate=json.loads(p.read_text());field='qd_gripper_rescue_mode';candidate.update(label='N24',algorithm_contract='n24_gripper_mode_parent_rescue_v1',parent_candidate={'path':str(p.relative_to(w)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},only_algorithm_change={field:{'before':'none','after':'canonical_full_close_v1'}});candidate['profile'][field]='canonical_full_close_v1';(p.parent/'candidate_n24.json').write_text(json.dumps(candidate,indent=2)+'\n')
p=w/'scripts/qd_ed_final_runner.py';s=p.read_text();marker="    elif contract == 'n23_actuator_clipped_provider_quality_v1':";assert marker in s;s=s.replace(marker,"""    elif contract == 'n24_gripper_mode_parent_rescue_v1':
        require(candidate_id == 'N24', 'N24 contract requires N24 identity')
        parent = candidate.get('parent_candidate')
        require(isinstance(parent, dict) and parent.get('path') == 'configs/qd_ed_final/candidate_n23.json'
                and parent.get('sha256') == digest(ROOT / parent['path']), 'N24 parent N23 identity differs')
        inherited = read_json(ROOT / parent['path'])['profile']
        field = 'qd_gripper_rescue_mode'
        require(set(profile) == set(inherited) | {field}
                and profile.get(field) == 'canonical_full_close_v1'
                and {k: v for k, v in profile.items() if k != field} == inherited
                and candidate.get('only_algorithm_change') == {field: {'before': 'none', 'after': 'canonical_full_close_v1'}},
                'N24 must change only the search-local gripper parent rescue')
"""+marker,1);s=s.replace("    fields = (('qd_descriptor'", "    fields = (('qd_descriptor', 'qd_final_selection_mode', 'qd_quality_mode', 'qd_gripper_rescue_mode')\n              if candidate_id == 'N24' else\n              ('qd_descriptor'",1);p.write_text(s)
