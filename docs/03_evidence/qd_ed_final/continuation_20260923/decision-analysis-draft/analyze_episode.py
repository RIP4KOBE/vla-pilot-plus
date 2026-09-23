#!/usr/bin/env python3
"""CPU-only selected-decision analysis after the existing evidence audit passes.

No provider, policy, simulator or unexecuted-candidate outcome is evaluated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cpu_torch():
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'explicit empty CUDA_VISIBLE_DEVICES required')
    import torch
    require(not torch.cuda.is_initialized(), 'CUDA already initialized; CPU analysis refused')
    return torch


def norm(vector):
    return math.sqrt(sum(float(x) ** 2 for x in vector))


def sub(left, right):
    return [float(a) - float(b) for a, b in zip(left, right)]


def distance(left, right):
    return norm(sub(left, right))


def plain(value):
    return value.detach().double().tolist() if hasattr(value, 'detach') else value


def one(rows, name):
    matching = [r for r in rows if r['event'] == name]
    require(len(matching) == 1, 'missing or duplicate ' + name)
    return matching[0]


def fingerprint(value):
    return hashlib.sha256(value.detach().float().contiguous().numpy().astype('<f4', copy=False).tobytes()).hexdigest()


def ulp_norm(value):
    """Conservative one-ULP coordinate norm in the stored dtype, not restored precision."""
    torch = cpu_torch()
    value = value.detach()
    positive = torch.full_like(value, float('inf'))
    negative = torch.full_like(value, -float('inf'))
    gap = torch.maximum((torch.nextafter(value, positive) - value).abs(),
                        (value - torch.nextafter(value, negative)).abs())
    return max(1e-9, norm(gap.double().reshape(-1).tolist()))


def provider_identity(provider):
    """Shared wrapper bytecode cannot identify the wrapped reward semantics."""
    values = [provider.get('original_code_sha256'), provider.get('source_text_sha256')]
    if not all(isinstance(v, str) and len(v) == 64 and all(c in '0123456789abcdef' for c in v) for v in values):
        return None
    source_path = provider.get('source_path')
    if not isinstance(source_path, str) or not Path(source_path).is_absolute():
        return None
    return (*values, source_path)


def load_target_map(path):
    """Verify explicitly reviewed metadata; never execute or infer provider semantics."""
    if path is None:
        return {}, {}
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    require(data.get('schema') == 'qd-ed-provider-target-map-v2', 'target map schema invalid; shared-wrapper v1 is unsafe')
    entries, hashes = {}, {str(path): digest(path)}
    for entry in data['entries']:
        identity = provider_identity(entry)
        require(identity is not None, 'original provider code/source identity incomplete')
        require(identity not in entries, 'duplicate original-provider/source target mapping')
        require(type(entry.get('keypoint_index')) is int and entry['keypoint_index'] >= 0,
                'keypoint index invalid')
        require(entry.get('reviewed_against_frozen_provider_source') is True
                and bool(entry.get('target_expression')), 'explicit provider semantics review required')
        require(entry.get('target_selection') == 'fixed_keypoint_index', 'unique static keypoint target review required')
        require(entry.get('distance_progress_interpretation', 'descriptive_only') in {'approach_proxy', 'descriptive_only'},
                'unknown distance-progress interpretation')
        require(entry.get('distance_progress_interpretation', 'descriptive_only') != 'approach_proxy'
                or bool(entry.get('approach_review_basis')), 'approach reward interpretation needs a review basis')
        source = Path(entry['source_path'])
        require(source.is_absolute() and source.is_file() and not source.is_symlink(),
                'target map needs explicit absolute regular source path')
        require(source.suffix in {'.py', '.txt'}, 'target source must be an explicitly reviewed Python/text file')
        actual = digest(source)
        require(actual == entry['source_sha256'], 'reviewed provider source SHA mismatch')
        require(entry.get('source_text_transform') == 'identity', 'minimal map only supports verified unchanged loader source text')
        require(hashlib.sha256(source.read_text(encoding='utf-8').encode('utf-8')).hexdigest() == entry['source_text_sha256'],
                'reviewed source text differs from recorded loader text identity')
        hashes[str(source)] = actual
        entries[identity] = dict(entry)
    return entries, hashes


def resolve_target(context, projected, target_map):
    """A frozen keypoint is not an observed object pose; ambiguous semantics stay unknown."""
    torch = cpu_torch()
    providers = context.get('providers', [])
    if len(providers) != 1:
        return None, None, 'target_unknown_no_unique_provider'
    identity = provider_identity(providers[0])
    if identity is None:
        return None, None, 'target_unknown_original_provider_source_identity_incomplete'
    entry = target_map.get(identity)
    if entry is None:
        return None, None, 'target_unknown_no_reviewed_provider_mapping'
    points = context.get('keypoints')
    index = entry['keypoint_index']
    if not torch.is_tensor(points) or points.ndim != 2 or points.shape[1] != 3 or index >= len(points):
        return None, None, 'target_unknown_context_keypoint_missing'
    if projected is None:
        return None, None, 'target_unknown_no_selected_scoring_input'
    scored = projected['keypoints']
    # Exact full-array equality after the existing dtype cast protects against reordered keypoints.
    if not torch.is_tensor(scored) or scored.shape != points.shape or not torch.equal(points.to(scored.dtype), scored):
        return None, None, 'target_unknown_scoring_keypoints_differ_from_context'
    if not torch.isfinite(points[index]).all():
        return None, None, 'target_unknown_nonfinite_keypoint'
    return plain(points[index]), {**entry, 'runtime_original_code_text_path_match': True}, None


def selected_projection(rows, event_lookup):
    """Collapse equal recorded value tuples, never invent original archive ancestry."""
    torch = cpu_torch()
    decoded = one(rows, 'policy_action_decode')['values']
    selected_fp = decoded['selected_canonical_fingerprint']
    candidates = []
    for score in (r for r in rows if r['event'] == 'scoring_inputs'):
        values = score['values']
        if not values['scoring_scope']['role'].startswith('canonical_'):
            continue
        for index, sample in enumerate(values['samples']):
            if fingerprint(sample) != selected_fp:
                continue
            origins = values.get('projection_origin_sequences')
            if not origins:
                continue
            origin = event_lookup[origins[index]]['values']['source_eef_position']
            candidates.append({'score_sequence': score['sequence'], 'row': index,
                'scope': values['scoring_scope'], 'projection': values['projected_xyz'][index],
                'provider_input': values['provider_input_xyz'][index],
                'origin': origin, 'keypoints': values['keypoints'], 'slice_kind': values['slice_kind']})
    if not candidates:
        return None, 'no_canonical_selected_projection', []
    first = candidates[0]
    names = ('projection', 'provider_input', 'origin', 'keypoints')
    if any(not all(torch.equal(candidate[name], first[name]) for name in names) for candidate in candidates[1:]):
        return None, 'selected_fingerprint_has_ambiguous_projection_or_origin', []
    associations = []
    for candidate in candidates:
        related = [row for row in rows if row['values'].get('scoring_batch_id') == candidate['score_sequence']]
        effective = one(related, 'effective_quality')['values']
        aggregate = one(related, 'scoring_aggregate')['values']
        associations.append({'scoring_batch_sequence': candidate['score_sequence'], 'row': candidate['row'],
            'scope': candidate['scope'], 'reward_mode': effective['reward_mode'],
            'effective_quality': float(effective['quality'][candidate['row']]),
            'aggregate_before_reward_mode': float(aggregate['aggregate_before_reward_mode'][candidate['row']]),
            'provider_returns': [{'provider_ordinal': r['values']['provider_ordinal'],
                'context_provider_ordinal': r['values']['context_provider_ordinal'],
                'value': plain(r['values']['result'])} for r in related
                if r['event'] == 'provider_return' and r['values']['candidate_index'] == candidate['row']]})
    return first, None, associations


def dispatch_observations(rows):
    dispatches = [r for r in rows if r['event'] == 'action_dispatch']
    observations = []
    for index, dispatch in enumerate(dispatches):
        end = dispatches[index + 1]['sequence'] if index + 1 < len(dispatches) else float('inf')
        window = [r for r in rows if dispatch['sequence'] < r['sequence'] < end]
        sent = one(window, 'executed_action')
        outcome = one(window, 'pre_reset_outcome')
        returned = one(window, 'step_returned')
        require(outcome['reset_sequence'] == dispatch['reset_sequence'], 'outcome crossed reset boundary')
        require(outcome['sequence'] < returned['sequence'], 'outcome is not pre-return')
        value = outcome['values']; obs = value['observation']
        observations.append({'execution_index': dispatch['values']['execution_index'],
            'global_step': dispatch['global_step'], 'action': plain(sent['values']['action_numpy']),
            'eef': plain(obs['robot0_eef_pos']),
            'eef_source_dtype': str(obs['robot0_eef_pos'].dtype),
            'eef_ulp_m': ulp_norm(obs['robot0_eef_pos']),
            'gripper_qpos': plain(obs.get('robot0_gripper_qpos')),
            'gripper_qvel': plain(obs.get('robot0_gripper_qvel')),
            'reward': plain(value['reward']), 'success': value['success'],
            'terminated': value['terminated'], 'truncated': returned['values']['truncated'],
            'outcome_sequence': outcome['sequence']})
    require([row['execution_index'] for row in observations] == list(range(1, len(observations) + 1)),
            'actual prefix is noncontiguous')
    return observations


def numerical_diagnostics(projection, origin, target, observations, projection_ulp, origin_ulp=1e-9):
    """Pure scalar formulas, separately exercised by explicitly synthetic unit fixtures."""
    count = len(observations)
    require(0 < count < len(projection), 'projection must cover the nonempty executed prefix')
    require(all(len(p) == 3 and all(math.isfinite(x) for x in p) for p in projection + [origin]),
            'projection/origin must contain finite xyz')
    actual = [origin, *[r['eef'] for r in observations]]
    projected = projection[:count + 1]
    actual_dist = [distance(p, target) for p in actual] if target is not None else None
    predicted_dist = [distance(p, target) for p in projected] if target is not None else None
    actual_progress = actual_dist[0] - actual_dist[-1] if target is not None else None
    # Both progress estimates use the observed source origin; preserve cast-t0 error separately.
    predicted_progress = actual_dist[0] - predicted_dist[-1] if target is not None else None
    errors = [distance(actual[t], projected[t]) for t in range(1, count + 1)]
    true_delta = [sub(actual[t], actual[t-1]) for t in range(1, count + 1)]
    model_delta = [sub(projected[t], projected[t-1]) for t in range(1, count + 1)]
    denominator = sum(norm(row) ** 2 for row in model_delta)
    gain = (sum(sum(a*b for a,b in zip(x,y)) for x,y in zip(true_delta,model_delta)) / denominator
            if denominator > sum(value ** 2 for value in projection_ulp[1:count+1]) else None)
    eps_end = projection_ulp[count] + observations[-1]['eef_ulp_m']
    result = {'observed_prefix_length': count, 'actual_frozen_target_distance_m': actual_dist,
        'selected_projected_frozen_target_distance_m': predicted_dist,
        'actual_frozen_target_progress_m': actual_progress,
        'predicted_frozen_target_progress_m': predicted_progress,
        'progress_optimism_m': predicted_progress - actual_progress if target is not None else None,
        'eef_projection_error_m': errors,
        'eef_projection_rmse_m': math.sqrt(sum(x*x for x in errors) / count),
        'endpoint_projection_error_m': errors[-1], 'projected_motion_tracking_gain': gain,
        'projected_t0_source_cast_error_m': distance(origin, projection[0]),
        'stored_projection_ulp_m': projection_ulp,
        'endpoint_precision_floor_m': eps_end,
        'actual_progress_precision_floor_m': origin_ulp + observations[-1]['eef_ulp_m'],
        'predicted_progress_precision_floor_m': origin_ulp + projection_ulp[count],
        'projection_optimism_witness': bool(predicted_progress > origin_ulp + projection_ulp[count]
            and actual_progress <= origin_ulp + observations[-1]['eef_ulp_m']
            and errors[-1] > eps_end) if target is not None else None,
        'step7_to8': None}
    if count >= 8 and len(projection) >= 9:
        actual_regression = actual_dist[8] - actual_dist[7] if target is not None else None
        predicted_regression = predicted_dist[8] - predicted_dist[7] if target is not None else None
        actual_floor = observations[6]['eef_ulp_m'] + observations[7]['eef_ulp_m']
        predicted_floor = projection_ulp[7] + projection_ulp[8]
        q7, q8 = observations[6]['gripper_qpos'], observations[7]['gripper_qpos']
        result['step7_to8'] = {'actual_distance_increase_m': actual_regression,
            'predicted_distance_increase_m': predicted_regression,
            'actual_progress_through_step7_m': actual_dist[0] - actual_dist[7] if target is not None else None,
            'actual_progress_through_step8_m': actual_dist[0] - actual_dist[8] if target is not None else None,
            'predicted_precision_floor_m': predicted_floor, 'actual_precision_floor_m': actual_floor,
            'actual_regression_robust': actual_regression > actual_floor if target is not None else None,
            'predicted_regression_robust': predicted_regression > predicted_floor if target is not None else None,
            'both_regress_robust': actual_regression > actual_floor and predicted_regression > predicted_floor if target is not None else None,
            'positive_progress_reversed': (actual_dist[0] - actual_dist[7] > origin_ulp + observations[6]['eef_ulp_m']
                and actual_dist[0] - actual_dist[8] < -(origin_ulp + observations[7]['eef_ulp_m'])) if target is not None else None,
            'gripper_commands': [observations[6]['action'][6], observations[7]['action'][6]],
            'gripper_command_switched': observations[6]['action'][6] != observations[7]['action'][6],
            'gripper_qpos_change_l2': distance(q7, q8) if q7 is not None and q8 is not None else None}
        result['through_step7'] = numerical_diagnostics(projection[:8], origin, target,
            observations[:7], projection_ulp[:8], origin_ulp)
    return result


def analyze_events(events, *, input_kind, target_map=None):
    torch = cpu_torch()
    require(input_kind in {'audited_runtime_episode', 'synthetic_unit_fixture'}, 'input provenance required')
    by_decision = defaultdict(list)
    lookup = {row['sequence']: row for row in events}
    for row in events:
        by_decision[row['decision_id']].append(row)
    decisions = []
    for decision_id, rows in by_decision.items():
        context = one(rows, 'decision_context')['values']
        committed = one(rows, 'decision_committed')['values']
        observations = dispatch_observations(rows)
        require(bool(observations), 'unexecuted decision cannot provide outcome evidence')
        projected, missing, associations = selected_projection(rows, lookup)
        target, target_review, target_missing = resolve_target(context, projected, target_map or {})
        current = {'decision_id': decision_id, 'global_step': rows[0]['global_step'],
            'stage': context['stage'], 'guidance': bool(context['use_guidance']),
            'provider_code_sha256': [x.get('code_sha256') for x in context['providers']],
            'provider_identities': context['providers'],
            'frozen_target': target, 'target_review': target_review,
            'target_scope': 'reviewed provider keypoint at decision time; not contemporaneous object pose',
            'committed_execution_horizon': committed['execution_horizon'],
            'executed_prefix_length': len(observations), 'actual_steps': observations,
            'actual_gripper_command_prefix': [r['action'][6] for r in observations],
            'selected_projection_associations': associations,
            'association_scope': 'equal content/value class, not inferred original archive occurrence',
            'selected_quality': next((r['values']['selected_quality'] for r in rows if r['event'] == 'final_selection'), None),
            'diagnostics': None, 'unknown_reasons': [],
            'hypothesis_eligible': False, 'hypothesis_ineligible_reasons': [],
            'unexecuted_candidate_outcomes': 'Unknown', 'grasp_success': 'Unknown'}
        if missing:
            current['unknown_reasons'].append(missing)
        if target is None:
            current['unknown_reasons'].append(target_missing)
        if projected is not None:
            projection = projected['projection']
            current['selected_projected_xyz'] = plain(projection)
            current['projection_dtype'] = str(projection.dtype)
            current['actual_source_eef'] = plain(projected['origin'])
            current['source_eef_dtype'] = str(projected['origin'].dtype)
            current['provider_slice_is_t1_through_t7'] = bool(projected['slice_kind'] == 'eds'
                and projection.shape == (9, 3) and torch.equal(projected['provider_input'], projection[1:8]))
            decoded = one(rows, 'policy_action_decode')['values']['action_chunk'][0]
            current['sent_vs_decoded_translation_max_abs_difference'] = max(
                abs(float(decoded[i,j]) - observations[i]['action'][j])
                for i in range(len(observations)) for j in range(3))
            current['sent_vs_committed_max_abs_difference'] = max(
                abs(float(committed['action_chunk'][0,i,j]) - observations[i]['action'][j])
                for i in range(len(observations)) for j in range(7))
            current['command_translation_matches_projection_source'] = current['sent_vs_decoded_translation_max_abs_difference'] == 0
            if not current['command_translation_matches_projection_source']:
                current['unknown_reasons'].append('actual_translation_changed_after_decode; separate command-transform attribution')
            if len(observations) < len(projection):
                current['diagnostics'] = numerical_diagnostics(plain(projection), plain(projected['origin']),
                    target, observations, [ulp_norm(row) for row in projection], ulp_norm(projected['origin']))
                current['hypothesis_eligible'] = bool(current['command_translation_matches_projection_source']
                    and context['use_guidance'] and current['provider_slice_is_t1_through_t7'] and target is not None
                    and target_review.get('distance_progress_interpretation', 'descriptive_only') == 'approach_proxy'
                    and all(a['reward_mode'] == 'normal' for a in associations))
                eligibility = {'actual_translation_changed_after_decode': current['command_translation_matches_projection_source'],
                    'guidance_off': bool(context['use_guidance']),
                    'provider_slice_not_t1_through_t7': current['provider_slice_is_t1_through_t7'],
                    'target_unknown': target is not None,
                    'approach_objective_not_reviewed': target_review is not None and
                        target_review.get('distance_progress_interpretation', 'descriptive_only') == 'approach_proxy',
                    'reward_mode_not_normal': all(a['reward_mode'] == 'normal' for a in associations)}
                current['hypothesis_ineligible_reasons'] = [name for name, passed in eligibility.items() if not passed]
            else:
                current['unknown_reasons'].append('projection_does_not_cover_actual_prefix')
        if len(observations) < 8:
            current['unknown_reasons'].append('step7_to8_unknown_for_short_actual_prefix')
        decisions.append(current)
    grouped = defaultdict(list)
    for row in decisions:
        key = json.dumps({'stage': row['stage'], 'guidance': row['guidance'],
                          'provider_code_sha256': row['provider_code_sha256'],
                          'provider_identities': row['provider_identities']}, sort_keys=True)
        grouped[key].append(row)
    strata = []
    for key, rows in grouped.items():
        available = [r for r in rows if r['diagnostics'] is not None]
        with_target = [r for r in available if r['frozen_target'] is not None]
        eligible = [r for r in available if r.get('hypothesis_eligible')]
        full = [r for r in eligible if r['diagnostics']['step7_to8'] is not None]
        strata.append({**json.loads(key), 'decisions': len(rows), 'diagnostic_decisions': len(available),
            'hypothesis_eligible_decisions': len(eligible), 'full_eight_step_decisions': len(full),
            'actual_progress_median_m': statistics.median(r['diagnostics']['actual_frozen_target_progress_m'] for r in with_target) if with_target else None,
            'projection_rmse_median_m': statistics.median(r['diagnostics']['eef_projection_rmse_m'] for r in available) if available else None,
            'projection_optimism_witnesses': sum(r['diagnostics']['projection_optimism_witness'] for r in eligible),
            'projection_optimism_witness_ids': [r['decision_id'] for r in eligible if r['diagnostics']['projection_optimism_witness']],
            'step7_to8_joint_regression_witnesses': sum(r['diagnostics']['step7_to8']['both_regress_robust'] for r in full),
            'step7_to8_joint_regression_witness_ids': [r['decision_id'] for r in full if r['diagnostics']['step7_to8']['both_regress_robust']],
            'step7_to8_reversal_witnesses': sum(r['diagnostics']['step7_to8']['positive_progress_reversed'] for r in full)})
    require(not torch.cuda.is_initialized(), 'unexpected CUDA initialization')
    return {'schema': 'qd-ed-selected-decision-analysis-v2', 'input_kind': input_kind,
        'decisions': decisions, 'strata': strata,
        'causal_limit': 'selected executed actions only; target-relative EEF proxy is not task or grasp success',
        'promotion_status': 'NOT_EVALUATED; single-episode descriptive output is not a candidate gate',
        'cuda_initialized_after': False}


def analyze_episode(episode_dir, episode_compute, root, target_map_path=None, *, input_kind='audited_runtime_episode'):
    torch = cpu_torch()
    sys.path.insert(0, str(root / 'scripts'))
    import audit_decision_evidence as audit
    episode_dir, episode_compute = Path(episode_dir).resolve(), Path(episode_compute).resolve()
    files = [episode_dir / 'status.json', episode_dir / 'events.jsonl', episode_compute]
    before = {str(path): digest(path) for path in files}
    target_map, target_hashes = load_target_map(target_map_path)
    report = audit.audit_episode(episode_dir, episode_compute)
    require(report['accepted'] is True and report['evidence_complete'] is True,
            'existing episode audit refused: ' + ', '.join(report['errors']))
    status = json.loads((episode_dir / 'status.json').read_text())
    events = audit.load_events(episode_dir, status)  # SHA verified, weights_only, CPU.
    result = analyze_events(events, input_kind=input_kind, target_map=target_map)
    before.update({str(episode_dir / row['bundle']): row['sha256'] for row in
                   [json.loads(line) for line in (episode_dir / 'events.jsonl').read_text().splitlines()]})
    before.update(target_hashes)
    require(all(digest(path) == expected for path,expected in before.items()), 'evidence changed while reading')
    matching = [json.loads(line) for line in episode_compute.read_text().splitlines()
                if json.loads(line).get('episode_id') == status['episode']]
    execution = matching[0]
    result.update(episode_dir=str(episode_dir), audit=report, input_sha256=before,
                  task_id=execution.get('task_id'), episode_id=status['episode'],
                  episode_seed=execution.get('episode_seed'),
                  original_execution_outcome=execution['outcome'],
                  source_sha256={'analysis': digest(__file__), 'existing_auditor': digest(audit.__file__)},
                  cuda_initialized_before=False, cuda_initialized_after=torch.cuda.is_initialized())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode-dir', required=True, type=Path)
    parser.add_argument('--episode-compute', required=True, type=Path)
    parser.add_argument('--target-map', type=Path, help='Optional reviewed provider-target map; otherwise target distance is Unknown')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = next(path for path in Path(__file__).resolve().parents if (path / 'scripts/audit_decision_evidence.py').is_file())
    require(not args.output.resolve().is_relative_to(args.episode_dir.resolve()), 'output must be outside read-only episode')
    require(args.output.resolve() != args.episode_compute.resolve(), 'output would overwrite episode compute')
    result = analyze_episode(args.episode_dir, args.episode_compute, root, args.target_map)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')
    print(json.dumps({'output': str(args.output), 'decisions': len(result['decisions']),
                      'audit_accepted': True, 'cuda_initialized': result['cuda_initialized_after']}))


if __name__ == '__main__':
    main()
