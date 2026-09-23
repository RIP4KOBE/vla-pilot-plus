#!/usr/bin/env python3
"""CPU-only attribution of recorded final slots; no archive replay or selection."""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import time

HISTORICAL_SCRIPT_SHA = '5ed4a49c0e9b62e43e5b98915e8bca252c6f598ce23a339d68b154e22906a839'
REPORTS = {
    'observed_pairs_t00_c0_20260923': 'f60ad2353dbc181e77d2fb8a01d67fdf71fa3f41a386512eee7f08bb096dbf68',
    'observed_pairs_t00_q0_20260923': 'eb4619939885ec83f7744f6e39f1cd62214c8b0f98f15797373b84b8e4a44348',
}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(spec):
    path = Path(spec['path']).resolve()
    require(sha(path) == spec['sha256'], 'file fingerprint differs: ' + str(path))
    return json.loads(path.read_text()), path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def summarize(slots, selected_fp, selected_quality):
    nonflagged = [s for s in slots if s['tail_classification'] == 'not_flagged_robust_regression']
    known = [s for s in nonflagged if s['effective_quality'] is not None]
    unknown_tail = [s for s in slots if s['tail_classification'] is None]
    unknown_quality = [s for s in nonflagged if s['effective_quality'] is None]
    distinct = [s for s in nonflagged if s['fingerprint'] != selected_fp]
    preserving = [s for s in known if s['effective_quality'] >= selected_quality]
    distinct_preserving = [s for s in preserving if s['fingerprint'] != selected_fp]
    def exists(positive, unresolved): return True if positive else None if unresolved else False
    distinct_unresolved = [s for s in unknown_tail + unknown_quality if s['fingerprint'] != selected_fp]
    best = max((s['effective_quality'] for s in known), default=None)
    return {'final_slots': len(slots), 'unknown_tail_slots': len(unknown_tail),
        'unknown_quality_slots': sum(s['effective_quality'] is None for s in slots),
        'any_nonflagged': exists(nonflagged, unknown_tail),
        'any_distinct_nonflagged': exists(distinct, [s for s in unknown_tail if s['fingerprint'] != selected_fp]),
        'any_nonflagged_quality_ge_selected': exists(preserving, unknown_tail + unknown_quality),
        'any_distinct_nonflagged_quality_ge_selected': exists(distinct_preserving, distinct_unresolved),
        'best_known_nonflagged_quality': best,
        'best_known_quality_minus_actual_selected': None if best is None else best - selected_quality,
        'maximum_scope': 'known_subset_only' if unknown_tail or unknown_quality else 'complete_recorded_final_pool',
        'best_known_exact_ties': [{'slot': s['slot'], 'fingerprint': s['fingerprint'],
            'fingerprint_differs_from_selected': s['fingerprint'] != selected_fp,
            'effective_quality': s['effective_quality'], 'matching_occurrence_ids': s['matching_occurrence_ids']}
            for s in known if s['effective_quality'] == best]}


def inspect_decision(rows, history, profile, a, c):
    torch = a.cpu_torch()
    final_event = a.one(rows, 'final_selection'); final = final_event['values']
    expected_rule = 'cost_argmin' if profile == 'C0' else 'archive_global_best'
    require(profile in {'C0', 'Q0'} and final['selection_rule'] == expected_rule, 'profile/final rule differs')
    population = final['population']; selected = final['selected_latent']; index = final['selected_index']
    require(population.ndim == 3 and selected.shape == (1, *population.shape[1:]) and
            type(index) is int and 0 <= index < len(population), 'final population/selection shape differs')
    require(c.tensor_identity(population[index:index+1], torch) == c.tensor_identity(selected, torch),
            'selected native tensor differs from final slot')
    selected_fp = a.fingerprint(selected[0]); selected_quality = float(final['selected_quality'])
    require(math.isfinite(selected_quality) and selected_fp == final['selected_canonical_fingerprint'] == history['selected_fingerprint']
            and selected_quality == history['actual_selected_quality'], 'selected identity/quality differs')
    require(selected_fp == a.one(rows, 'policy_action_decode')['values']['selected_canonical_fingerprint'], 'decode identity differs')
    batches = [r for r in rows if r['event'] == 'canonical_candidate_batch']
    require(batches and all(r['sequence'] < final_event['sequence'] for r in batches), 'canonical timing differs')
    historical = {r['occurrence_id']: r for r in history['candidates']}
    require(len(historical) == len(history['candidates']), 'historical occurrence duplicated')
    seen = set(); by_native = defaultdict(list)
    for batch in batches:
        v = batch['values']
        for row, action in enumerate(v['candidates']):
            occurrence = v['occurrence_ids'][row]; saved = historical.get(occurrence)
            identity = c.tensor_identity(action, torch); fp = a.fingerprint(action)
            require(saved is not None and occurrence not in seen and fp == v['canonical_fingerprints'][row] == saved['fingerprint']
                and saved['canonical_batch_sequence'] == batch['sequence'] and saved['candidate_row'] == row
                and saved['iteration'] == v['iter_idx'] and saved['effective_quality'] == float(v['effective_quality'][row])
                and saved['quality_dtype'] == str(v['effective_quality'].dtype), 'historical/native canonical linkage differs')
            seen.add(occurrence)
            by_native[json.dumps(identity, sort_keys=True)].append(saved)
    require(seen == set(historical), 'historical occurrence coverage differs')
    last = max(batches, key=lambda r: r['sequence'])['values']
    if profile == 'C0':
        require(c.tensor_identity(population, torch) == c.tensor_identity(last['candidates'], torch),
                'C0 final native population differs from last canonical batch')
    slots = []
    for i, action in enumerate(population):
        identity = c.tensor_identity(action, torch); fp = a.fingerprint(action)
        matches = by_native.get(json.dumps(identity, sort_keys=True), [])
        require(matches and all(m['fingerprint'] == fp for m in matches), 'final slot has no exact native canonical match')
        tail_values = {m['tail_classification'] for m in matches}
        tail = next(iter(tail_values)) if len(tail_values) == 1 else None
        reasons = sorted({reason for m in matches for reason in m['unknown_reasons'] + m['ineligible_reasons']})
        if len(tail_values) != 1: reasons.append('matching_occurrences_have_different_tail_classification')
        qualities = {(m['quality_dtype'], m['effective_quality']) for m in matches}
        quality = next(iter(qualities))[1] if len(qualities) == 1 else None
        attribution = 'all_native_matching_occurrences_agree' if quality is not None else 'Unknown'
        if profile == 'C0':
            quality = float(last['effective_quality'][i]); attribution = 'actual_last_canonical_batch_row'
        if i == index:
            require(selected_quality in {m['effective_quality'] for m in matches}, 'selected quality was not recorded for exact native action')
            require(quality is None or quality == selected_quality, 'attributed quality disagrees with actual selected quality')
            quality = selected_quality; attribution = 'explicit_final_selected_quality'
        quality_reasons = [] if quality is not None else ['matching_occurrences_have_different_native_quality']
        slots.append({'slot': i, 'selected': i == index, 'fingerprint': fp, 'native_tensor_identity': identity,
            'matching_occurrence_ids': [m['occurrence_id'] for m in matches],
            'matching_original_qualities': [{'occurrence_id': m['occurrence_id'], 'quality_dtype': m['quality_dtype'],
                'effective_quality': m['effective_quality']} for m in matches],
            'insertion_occurrence': 'Unknown', 'tail_classification': tail, 'unknown_or_ineligible_reasons': reasons,
            'effective_quality': quality, 'quality_attribution': attribution, 'quality_unknown_reasons': quality_reasons})
    return {'decision_id': history['decision_id'], 'global_step': history['global_step'], 'stage': history['stage'],
        'original_actual_A': history['original_actual_A'], 'original_actual_B': history['original_actual_B'],
        'pool_kind': 'actual_C0_final_population' if profile == 'C0' else 'actual_Q0_final_archive_elites',
        'selected_index': index, 'selected_fingerprint': selected_fp, 'actual_selected_quality': selected_quality,
        'slots': slots, 'summary': summarize(slots, selected_fp, selected_quality),
        'counterfactual_success': 'Unknown'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--execute-reviewed', action='store_true'); args = p.parse_args()
    require(args.execute_reviewed and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'review authorization and empty CUDA mask required')
    manifest = json.loads(args.manifest.read_text()); script_path = Path(__file__).resolve()
    require(manifest['schema'] == 'qd-ed-final-membership-input-v1' and manifest['script_sha256'] == sha(script_path)
            and manifest['protocol_sha256'] == sha(script_path.with_name('protocol.md')), 'script/protocol freeze differs')
    authorization, _ = ref(manifest['execution_authorization'])
    require(authorization['script'] == {'path': str(script_path), 'sha256': sha(script_path)} and
            authorization['protocol']['sha256'] == manifest['protocol_sha256'], 'execution authorization differs')
    history, _ = ref(manifest['historical_report']); key = history['episode_key']
    require(key in REPORTS and manifest['historical_report']['sha256'] == REPORTS[key]
            and key in authorization['allowed_episode_keys'], 'historical episode scope differs')
    original = history['input_manifest']
    inputs = {k: ref(original[k])[0] for k in ('plan', 'authorization', 'execution_authorization',
              'target_map', 'terminal', 'audit', 'supplemental_analysis')}
    plan = inputs['plan']; terminal = inputs['terminal']; analysis = inputs['supplemental_analysis']
    require(original['script_sha256'] == HISTORICAL_SCRIPT_SHA and history['cuda_initialized'] is False and
            history['promotion_status'] == 'NOT_EVALUATED' and terminal['episode_key'] == key, 'historical report condition differs')
    old_script = Path(manifest['historical_checker']['path']).resolve()
    require(manifest['historical_checker']['sha256'] == HISTORICAL_SCRIPT_SHA == sha(old_script), 'historical helper source differs')
    c = module('frozen_recorded_candidate_helpers', old_script)
    root = Path(plan['worktree']); sources = {r['path']: r['sha256'] for r in plan['code_files']}
    required = [c.ANALYZER, c.AUDITOR, 'core/rdt_policy_steer.py', 'core/qd_ed.py', 'core/decision_evidence.py']
    for path in required: require(sha(root/path) == sources[path], 'frozen source differs: '+path)
    a = module('frozen_membership_analysis_helpers', root/c.ANALYZER)
    audit = module('frozen_membership_auditor', root/c.AUDITOR)
    torch = a.cpu_torch(); started = time.monotonic(); peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    episode = Path(analysis['episode_dir']); compute = Path(inputs['audit']['episode_compute_file'])
    destination = args.output_dir.resolve()
    require(not destination.exists() and destination.is_relative_to(Path(plan['artifact_root'])/'continuation_20260923')
        and not destination.is_relative_to(Path(terminal['output_dir'])), 'new artifact directory required')
    for path, expected in analysis['input_sha256'].items(): require(sha(path) == expected, 'input fingerprint differs')
    fresh = audit.audit_episode(episode, compute)
    require(fresh['accepted'] is True and fresh['evidence_complete'] is True and fresh == analysis['audit']
        == {k:v for k,v in inputs['audit'].items() if k != 'wrapper_observation'}, 'fresh complete audit differs')
    events = audit.load_events(episode, json.loads((episode/'status.json').read_text()))
    grouped = defaultdict(list)
    for row in events: grouped[row['decision_id']].append(row)
    eligible = {d['decision_id'] for d in analysis['decisions'] if d['guidance'] and d['hypothesis_eligible']}
    require(eligible == {d['decision_id'] for d in history['decisions']}, 'eligible decision universe differs')
    decisions = [inspect_decision(grouped[d['decision_id']], d, terminal['identity']['profile'], a, c) for d in history['decisions']]
    require(not torch.cuda.is_initialized(), 'unexpected CUDA initialization')
    for path, expected in analysis['input_sha256'].items(): require(sha(path) == expected, 'input changed while reading')
    output = {'schema': 'qd-ed-direct-final-membership-v1', 'episode_key': key, 'attempt_id': history['attempt_id'],
        'original_success': history['original_success'], 'decisions': decisions,
        'excluded_decisions': history['excluded_decisions'], 'eligible_decisions': len(decisions),
        'input_manifest': manifest, 'source_sha256': {path:sources[path] for path in required},
        'authorization_condition': 'post_data_identity_v3', 'promotion_status': 'NOT_EVALUATED',
        'cuda_initialized': False, 'CPU_wall_seconds': time.monotonic()-started,
        'parent_ru_maxrss_before_kib': peak, 'parent_ru_maxrss_after_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'memory_scope': 'Cumulative parent process peaks including imports/audit, not exclusive analysis memory.',
        'statistical_unit': 'Episode; slots and decisions are correlated observations.', 'counterfactual_success': 'Unknown'}
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'final-population-membership.json').write_text(json.dumps(output,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'episode_key':key,'eligible_decisions':len(decisions),'promotion_status':'NOT_EVALUATED'}))


if __name__ == '__main__': main()
