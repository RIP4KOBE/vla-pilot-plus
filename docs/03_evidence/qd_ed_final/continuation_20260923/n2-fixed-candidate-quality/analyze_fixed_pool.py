#!/usr/bin/env python3
"""Prospective CPU-only N2 reranking of explicitly authorized recorded final pools.

No provider, model, projector, simulator, archive replay, or GPU invocation.
Actual bundle reads require a separate SHA-bound root authorization after review.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time

N2_PROTOCOL_SHA = 'd5e560bb48cb705e13c931290adfccb3da905cf0a352e8d7bde8188dc5ca75b1'
MEMBERSHIP_SCRIPT_SHA = '732763eef2b11909318500b4f95f8d403cf57db4da706dffb7afe53c74a0b160'
HISTORY_SCRIPT_SHA = '5ed4a49c0e9b62e43e5b98915e8bca252c6f598ce23a339d68b154e22906a839'
MEMBERSHIP_REPORTS = {
    'observed_pairs_t00_c0_20260923': 'fda61dee79c6df38e1772120b44fb24adf3ec0ff00bda791bc13e4a30cc107b8',
    'observed_pairs_t00_q0_20260923': '40b319e2e41339cda84ba1f27cb61ff4dc71665dc4ee14ab6e46c64c0a6716b8',
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(spec):
    path = Path(spec['path']).resolve()
    require(sha(path) == spec['sha256'], 'file fingerprint differs: ' + str(path))
    return json.loads(path.read_text()), path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def same_native(left, right, c, torch):
    return c.tensor_identity(left, torch) == c.tensor_identity(right, torch)


def occurrence_input(saved, rows, context, target_map, a, c):
    """Join an original canonical occurrence, including its actual saved score input."""
    torch = a.cpu_torch()
    lookup = {row['sequence']: row for row in rows}
    require(len(lookup) == len(rows), 'duplicate event sequence')
    batch = lookup[saved['canonical_batch_sequence']]
    score = lookup[saved['scoring_batch_sequence']]
    require(batch['event'] == 'canonical_candidate_batch' and score['event'] == 'scoring_inputs'
            and score['sequence'] < batch['sequence'], 'canonical score ordering differs')
    bv, sv, index = batch['values'], score['values'], saved['candidate_row']
    scope = sv['scoring_scope']
    require(scope == saved['scoring_scope'] and scope['role'].startswith('canonical_')
            and scope['iter_idx'] == bv['iter_idx'] == saved['iteration'], 'canonical score role/iteration differs')
    require(same_native(sv['samples'], bv['candidates'], c, torch), 'canonical samples differ in native bytes')
    require(bv['occurrence_ids'][index] == saved['occurrence_id'], 'canonical occurrence row differs')
    eff_event = a.one([row for row in rows if row['event'] == 'effective_quality'
                      and row['values']['scoring_batch_id'] == score['sequence']], 'effective_quality')
    ev = eff_event['values']
    require(score['sequence'] < eff_event['sequence'] < batch['sequence']
            and same_native(ev['quality'], bv['effective_quality'], c, torch), 'canonical effective quality linkage differs')
    require(ev['reward_mode'] == saved['reward_mode'] == 'normal', 'only original normal provider quality applies')
    projection = sv['projected_xyz'][index]
    provider_input = sv['provider_input_xyz'][index]
    origin_event = lookup[sv['projection_origin_sequences'][index]]
    require(origin_event['event'] == 'projection_origin' and origin_event['sequence'] < score['sequence'],
            'projection source ordering differs')
    origin = origin_event['values']['source_eef_position']
    values = {'projection': projection, 'provider_input': provider_input,
              'source_eef': origin, 'keypoints': sv['keypoints']}
    identities = {k: c.tensor_identity(v, torch) for k, v in values.items()}
    require(identities == saved['recorded_value_identity'], 'saved geometry native identity differs')
    require(tuple(projection.shape) == (9, 3) and sv['slice_kind'] == 'eds'
            and same_native(provider_input, projection[1:8], c, torch), 'original provider slice is not native t1..t7')
    # Q8 is stored like original canonical samples, NOT like final archive's FP32 container.
    sample_dtype = sv['samples'].dtype
    require(projection.dtype == sv['keypoints'].dtype == bv['effective_quality'].dtype == sample_dtype,
            'native samples/projection/keypoints/canonical quality dtype differs')
    require(saved['quality_dtype'] == str(sample_dtype)
            and saved['effective_quality'] == float(bv['effective_quality'][index]), 'original native quality differs')
    target, reviewed, reason = a.resolve_target(context, {'keypoints': sv['keypoints']}, target_map)
    require(reason is None and target is not None and target == saved['frozen_target'], 'reviewed target differs')
    require(reviewed['distance_progress_interpretation'] == 'approach_proxy', 'approach semantic review required')
    return {'projection': projection, 'keypoints': sv['keypoints'], 'target_index': reviewed['keypoint_index'],
            'target': target, 'reviewed_target': reviewed, 'native_identity': identities,
            'sample_dtype': sample_dtype, 'old_quality': saved['effective_quality'],
            'scoring_batch_sequence': score['sequence']}


def rerank_decision(rows, history, membership, selected_analysis, target_map, profile, a, c, m, quality_helper):
    """Compute each actual final slot once; never replay/search or pick by A/B."""
    torch = a.cpu_torch()
    require(selected_analysis['guidance'] and selected_analysis['hypothesis_eligible']
            and selected_analysis['decision_id'] == history['decision_id'] == membership['decision_id'],
            'decision is not in the complete eligible universe')
    require(m.inspect_decision(rows, history, profile, a, c) == membership, 'saved final membership differs')
    context = a.one(rows, 'decision_context')['values']
    require(context['use_guidance'] is True, 'guided context required')
    final = a.one(rows, 'final_selection')['values']
    historical = {entry['occurrence_id']: entry for entry in history['candidates']}
    last = max((r for r in rows if r['event'] == 'canonical_candidate_batch'), key=lambda r: r['sequence'])['values']
    slots, native_q8 = [], []
    for slot in membership['slots']:
        ids = slot['matching_occurrence_ids']
        # C0 lineage is exact; Q0 insertion occurrence was not recorded. Require agreement of ALL matches.
        used = [last['occurrence_ids'][slot['slot']]] if profile == 'C0' else ids
        require(used and all(oid in ids for oid in used), 'final slot lineage differs')
        sources = [occurrence_input(historical[oid], rows, context, target_map, a, c) for oid in used]
        signature = lambda v: (v['native_identity'], v['target_index'], v['old_quality'])
        require(all(signature(value) == signature(sources[0]) for value in sources),
                'Q0 final slot matching occurrences have ambiguous native input or original quality')
        source = sources[0]
        require(source['target'] == selected_analysis['frozen_target'], 'selected frozen target differs')
        require(slot['effective_quality'] == source['old_quality'], 'attributed old quality differs')
        before = {k: c.tensor_identity(source[k], torch) for k in ('projection', 'keypoints')}
        quality = quality_helper(source['projection'].unsqueeze(0), source['keypoints'], target_index=source['target_index'])
        require(torch.is_tensor(quality) and tuple(quality.shape) == (1,) and quality.device.type == 'cpu'
                and quality.dtype == source['sample_dtype'] and bool(torch.isfinite(quality).all()),
                'Q8 must retain canonical sample storage dtype and be finite CPU scalar')
        require(before == {k: c.tensor_identity(source[k], torch) for k in before}, 'quality helper mutated recorded inputs')
        native_q8.append(quality[0])
        projection, target = source['projection'], source['target']
        d7, d8 = a.distance(a.plain(projection[7]), target), a.distance(a.plain(projection[8]), target)
        scored_target = a.plain(source['keypoints'][source['target_index']])
        slots.append({'slot': slot['slot'], 'fingerprint': slot['fingerprint'],
            'native_tensor_identity': slot['native_tensor_identity'], 'matching_occurrence_ids': ids,
            'used_occurrence_ids': used, 'insertion_occurrence': 'actual_last_batch_row' if profile == 'C0' else 'Unknown',
            'association': 'actual_last_canonical_batch_row' if profile == 'C0' else 'all_native_matches_agree',
            'source_identity': source['native_identity'], 'source_scoring_sequences': [s['scoring_batch_sequence'] for s in sources],
            'q8': float(quality[0]), 'q8_dtype': str(quality.dtype), 'q8_native_identity': c.tensor_identity(quality, torch),
            'original_quality': source['old_quality'], 'original_quality_dtype': str(source['sample_dtype']),
            'original_quality_minus_actual_selected': source['old_quality'] - membership['actual_selected_quality'],
            'target_identity': source['reviewed_target'], 'frozen_target': target, 'native_scored_target': scored_target,
            'projected_t7': a.plain(projection[7]), 'projected_t8': a.plain(projection[8]),
            'projected_distance7_m': d7, 'projected_distance8_m': d8, 'projected_tail_delta_m': d8 - d7,
            'native_scored_distance7_m': a.distance(a.plain(projection[7]), scored_target),
            'native_scored_distance8_m': a.distance(a.plain(projection[8]), scored_target),
            'geometry_arithmetic': 'descriptive float64 distances from stored coordinates; Q8 uses native scored keypoints and helper arithmetic'})
    require(slots, 'empty final pool')
    q8 = torch.stack(native_q8)
    maximum = q8.max()
    tied_indices = torch.nonzero(q8 == maximum, as_tuple=False).flatten().tolist()
    ties = [slots[index] for index in tied_indices]
    # Same original pool-rule ordering, explicitly secondary to all-tie reporting.
    representative = ties[0] if profile == 'C0' else min(ties, key=lambda s: (s['fingerprint'], s['slot']))
    selected = slots[membership['selected_index']]
    require(selected['fingerprint'] == membership['selected_fingerprint'], 'selected slot differs')
    robust_changed = all(s['fingerprint'] != selected['fingerprint'] for s in ties)
    return {'decision_id': membership['decision_id'], 'global_step': membership['global_step'], 'stage': membership['stage'],
        'original_actual_A': history['original_actual_A'], 'original_actual_B': history['original_actual_B'],
        'pool_kind': membership['pool_kind'], 'slots': slots, 'actual_selected_slot': selected['slot'],
        'actual_selected_fingerprint': selected['fingerprint'], 'actual_selected_original_quality': selected['original_quality'],
        'actual_selected_q8': selected['q8'], 'q8_maximum': float(maximum), 'q8_dtype': str(q8.dtype),
        'q8_gain_from_actual_selected': float(maximum) - selected['q8'],
        'all_exact_maximum_slots': tied_indices, 'all_exact_maximum_fingerprints': [s['fingerprint'] for s in ties],
        'all_exact_maximum_original_quality_tradeoffs': [s['original_quality_minus_actual_selected'] for s in ties],
        'deterministic_representative_slot': representative['slot'],
        'deterministic_representative_fingerprint': representative['fingerprint'],
        'deterministic_representative_changed': representative['fingerprint'] != selected['fingerprint'],
        'representative_rule': 'lowest_final_slot' if profile == 'C0' else 'lowest_fingerprint_then_final_slot',
        'tie_robust_changed': robust_changed,
        'mixed_tie_contains_actual_selected_and_distinct': not robust_changed and any(s['fingerprint'] != selected['fingerprint'] for s in ties),
        'counterfactual_success': 'Unknown', 'new_search_population': 'Unknown'}


def summarize(decisions):
    def counts(rows):
        return {'decisions': len(rows), 'final_slots': sum(len(d['slots']) for d in rows),
            'tie_robust_changed': sum(d['tie_robust_changed'] for d in rows),
            'deterministic_representative_changed': sum(d['deterministic_representative_changed'] for d in rows),
            'mixed_tie_retaining_selected': sum(d['mixed_tie_contains_actual_selected_and_distinct'] for d in rows)}
    return {'all_eligible': counts(decisions), 'A_strata_descriptive_only': {
        name: counts([d for d in decisions if d['original_actual_A'] is value])
        for name, value in [('A', True), ('non_A', False), ('Unknown', None)]},
        'recorded_choice_activity_gate': any(d['tie_robust_changed'] for d in decisions),
        'activity_gate_definition': 'At least one eligible decision where EVERY exact native Q8 maximum has a different fingerprint from actual selection.',
        'promotion_status': 'NOT_EVALUATED', 'counterfactual_success': 'Unknown',
        'statistical_unit': 'Episode; slots/decisions are correlated observations.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--execute-reviewed', action='store_true')
    args = p.parse_args()
    require(args.execute_reviewed and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'root review and empty CUDA mask required')
    manifest = json.loads(args.manifest.read_text()); script = Path(__file__).resolve()
    require(manifest['schema'] == 'qd-ed-n2-fixed-pool-input-v1'
        and manifest['script_sha256'] == sha(script) and manifest['protocol_sha256'] == sha(script.with_name('protocol.md')),
        'script/protocol freeze differs')
    auth, _ = ref(manifest['execution_authorization'])
    require(auth['script'] == {'path': str(script), 'sha256': sha(script)}
            and auth['protocol_sha256'] == manifest['protocol_sha256']
            and auth['quality_helper'] == manifest['quality_helper'] and auth['n2_protocol'] == manifest['n2_protocol'],
            'execution authorization differs')
    require(manifest['n2_protocol']['sha256'] == N2_PROTOCOL_SHA == sha(manifest['n2_protocol']['path']), 'N2 definition differs')
    membership, _ = ref(manifest['membership_report']); key = membership['episode_key']
    require(key in MEMBERSHIP_REPORTS and MEMBERSHIP_REPORTS[key] == manifest['membership_report']['sha256']
            and manifest['membership_report'] in auth['allowed_membership_reports'], 'only fixed task0 C0/Q0 reports authorized')
    require(membership['schema'] == 'qd-ed-direct-final-membership-v1'
            and membership['authorization_condition'] == 'post_data_identity_v3' and membership['cuda_initialized'] is False,
            'membership provenance differs')
    require(sha(manifest['membership_checker']['path']) == manifest['membership_checker']['sha256'] == MEMBERSHIP_SCRIPT_SHA,
            'membership checker differs')
    m = module('n2_frozen_membership', manifest['membership_checker']['path'])
    history, _ = ref(membership['input_manifest']['historical_report'])
    require(history['episode_key'] == key and membership['input_manifest']['historical_report']['sha256'] == m.REPORTS[key],
            'historical report differs')
    original = history['input_manifest']
    inputs = {k: ref(original[k])[0] for k in ('plan', 'authorization', 'execution_authorization', 'target_map', 'terminal', 'audit', 'supplemental_analysis')}
    checker = membership['input_manifest']['historical_checker']
    require(checker['sha256'] == sha(checker['path']) == original['script_sha256'] == HISTORY_SCRIPT_SHA, 'historical source differs')
    c = module('n2_frozen_history', checker['path'])
    require(original['plan']['sha256'] == c.PLAN_SHA and original['authorization']['sha256'] == c.AUTH_SHA
            and original['target_map']['sha256'] == c.MAP_SHA, 'original identity authorization differs')
    plan, terminal, analysis = inputs['plan'], inputs['terminal'], inputs['supplemental_analysis']
    require(terminal['episode_key'] == key and terminal['event'] == 'valid' and terminal['outcome_valid'] is True
            and terminal['physical_gpu'] == 3 and terminal['identity']['task_id'] == 0, 'only valid recorded task0 condition applies')
    plan_row = next(r for r in plan['episodes'] if r['episode_key'] == key)
    require(terminal['identity'] == {k: plan_row[k] for k in ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')}
            and terminal['plan_sha256'] == c.PLAN_SHA and terminal['source_commit'] == plan['source_commit']
            and terminal['profile_manifest_sha256'] == plan['profiles_sha256']
            and terminal['runtime_inventory_sha256'] == plan['runtime_inventory_sha256']
            and terminal['runtime_manifest_sha256'] == plan['runtime_manifest_sha256'], 'frozen episode identity differs')
    root = Path(plan['worktree']); sources = {r['path']: r['sha256'] for r in plan['code_files']}
    required = [c.ANALYZER, c.AUDITOR, 'core/rdt_policy_steer.py', 'core/qd_ed.py', 'core/decision_evidence.py']
    # HEAD may contain later protocol-only commits; actual historical source bytes are authoritative.
    for path in required:
        require(sha(root/path) == sources[path], 'observed source bytes differ: ' + path)
    a = module('n2_frozen_selected', root/c.ANALYZER)
    audit = module('n2_frozen_auditor', root/c.AUDITOR)
    helper_path = Path(manifest['quality_helper']['path']).resolve()
    require(helper_path.name == 'qd_executed_quality.py' and sha(helper_path) == manifest['quality_helper']['sha256'], 'N2 helper differs')
    torch = a.cpu_torch(); started = time.monotonic(); peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    helper = module('n2_reviewed_quality_helper', helper_path)
    output = Path(terminal['output_dir']).resolve(); episode = output/'eds_eval/decision_evidence/episode_000'
    compute = output/'eds_eval/episode_compute.jsonl'
    require(inputs['audit']['accepted'] is True and inputs['audit']['evidence_complete'] is True
            and analysis['audit']['accepted'] is True and analysis['audit']['evidence_complete'] is True,
            'prior accepted complete audits required before bundle reads')
    require(analysis['schema'] == 'qd-ed-selected-decision-analysis-v2'
            and analysis['input_kind'] == 'audited_runtime_episode' and analysis['task_id'] == 0
            and analysis['episode_seed'] == plan_row['env_seed']
            and analysis['cuda_initialized_before'] is False and analysis['cuda_initialized_after'] is False
            and analysis['source_sha256'] == {'analysis': sources[c.ANALYZER], 'existing_auditor': sources[c.AUDITOR]},
            'selected analysis source/condition differs')
    require(analysis['episode_dir'] == str(episode) and inputs['audit']['episode_dir'] == str(episode)
            and inputs['audit']['episode_compute_file'] == str(compute), 'episode linkage differs')
    destination = args.output_dir.resolve()
    require(not destination.exists() and destination.is_relative_to(Path(plan['artifact_root'])/'continuation_20260923')
            and not destination.is_relative_to(output), 'new independent output directory required')
    target_map, map_hashes = a.load_target_map(original['target_map']['path'])
    for path, expected in analysis['input_sha256'].items():
        resolved = Path(path).resolve()
        require(resolved.is_relative_to(episode) or resolved == compute or str(resolved) in map_hashes, 'input escapes authorized episode/map')
        require(sha(path) == expected, 'supplemental input differs: ' + path)
    fresh = audit.audit_episode(episode, compute)
    require(fresh['accepted'] is True and fresh['evidence_complete'] is True
            and fresh == analysis['audit'] == {k:v for k,v in inputs['audit'].items() if k != 'wrapper_observation'}, 'fresh complete audit differs')
    events = audit.load_events(episode, json.loads((episode/'status.json').read_text()))  # frozen weights_only loader
    grouped = defaultdict(list)
    for event in events:
        grouped[event['decision_id']].append(event)
    eligible = [d for d in analysis['decisions'] if d['guidance'] and d['hypothesis_eligible']]
    selected = {d['decision_id']: d for d in eligible}
    histories = {d['decision_id']: d for d in history['decisions']}
    members = {d['decision_id']: d for d in membership['decisions']}
    require(len(selected) == len(eligible) and len(histories) == len(history['decisions'])
            and len(members) == len(membership['decisions']) and selected.keys() == histories.keys() == members.keys()
            and set(grouped) == {d['decision_id'] for d in analysis['decisions']}
            and history['excluded_decisions'] == membership['excluded_decisions'], 'all eligible decision universe differs')
    decisions = [rerank_decision(grouped[did], histories[did], members[did], selected[did], target_map,
                 terminal['identity']['profile'], a, c, m, helper.executed_prefix_quality) for did in selected]
    require(not torch.cuda.is_initialized(), 'unexpected CUDA initialization')
    for path, expected in {**analysis['input_sha256'], **map_hashes, str(helper_path): manifest['quality_helper']['sha256']}.items():
        require(sha(path) == expected, 'input/helper changed during reading')
    for path in required:
        require(sha(root/path) == sources[path], 'source changed during reading: ' + path)
    require(sha(script) == manifest['script_sha256'] and sha(script.with_name('protocol.md')) == manifest['protocol_sha256'],
            'analysis definition changed during reading')
    report = {'schema': 'qd-ed-n2-recorded-final-pool-v1', 'episode_key': key, 'attempt_id': membership['attempt_id'],
        'original_success': membership['original_success'], 'decisions': decisions, 'summary': summarize(decisions),
        'excluded_decisions': history['excluded_decisions'], 'eligible_decisions': len(decisions), 'input_manifest': manifest,
        'input_sha256': analysis['input_sha256'], 'source_sha256': {p:sources[p] for p in required},
        'target_identity_condition': 'post_data_identity_v3; original frozen map-v2 results unchanged',
        'scope': 'All eligible decisions; actual recorded final pools only, no search or full-archive replay.',
        'numerical_condition': 'CPU helper native dtype/reduction/storage; no GPU bitwise-equivalence claim.',
        'counterfactual_success': 'Unknown', 'promotion_status': 'NOT_EVALUATED', 'cuda_initialized': False,
        'CPU_wall_seconds': time.monotonic()-started, 'ru_maxrss_before_kib': peak,
        'ru_maxrss_after_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'n2-fixed-pool.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({'episode_key': key, 'summary': report['summary']}))


if __name__ == '__main__':
    main()
