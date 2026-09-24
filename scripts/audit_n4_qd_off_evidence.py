#!/usr/bin/env python3
"""Additive protected-phase QD-OFF audit; original generic/N4 audit is unchanged.

No provider, policy, projection or simulation call. Decoding uses the deployed
pure action converter. This is total QD removal, with the C0 active algorithm.
"""
import argparse
from collections import defaultdict
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'n4-native-qd-off-audit-v1'


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def check_decision(kinds, context, audit, decoder):
    import torch
    require = audit.require
    def one(kind):
        require(len(kinds[kind]) == 1, 'qd_off_missing_or_duplicate_' + kind)
        return kinds[kind][0]
    def native(value, shape, dtype=None):
        require(audit.tensor(value) and value.is_floating_point() and tuple(value.shape) == tuple(shape)
            and (dtype is None or value.dtype == dtype), 'qd_off_native_shape_dtype_or_finite')
        return value
    def same(a, b):
        return audit.tensor(a) and audit.tensor(b) and audit._native_sha(a) == audit._native_sha(b)
    def numeric(a, b):
        return audit.tensor(a) and audit.tensor(b) and a.dtype == b.dtype == torch.float32 and a.shape == b.shape and torch.equal(a, b)
    require(not kinds['archive_parent_allocation'] and not kinds['terminal_population_stage_binding']
            and not kinds['execution_feedback_selection'], 'qd_off_archive_or_feedback_events')
    canonical = kinds['canonical_candidate_batch']
    require([r['values']['iter_idx'] for r in canonical] == list(range(-1, 10)), 'qd_off_canonical_11_coverage')
    sources = [r for r in kinds['scoring_inputs'] if r['values']['scoring_scope']['role'] != 'auxiliary_pretest']
    scoring = {r['values']['scoring_scope']['iter_idx']: r for r in sources}
    parents = {r['values']['iter_idx']: r for r in kinds['parent_allocation']}
    require(len(sources) == len(scoring) == 11 and set(scoring) == set(range(-1, 10)), 'qd_off_scoring_11_coverage')
    require(len(kinds['parent_allocation']) == len(parents) == 10 and set(parents) == set(range(10)), 'qd_off_parent_10_coverage')
    previous = None; batches = []; links = []
    for row in canonical:
        cv = row['values']; iteration = cv['iter_idx']; source = scoring[iteration]; scope = source['values']['scoring_scope']
        require(scope['role'] == ('canonical_initial' if iteration == -1 else 'canonical_offspring'), 'qd_off_scoring_role')
        actions = native(cv['candidates'], (16, 64, 128))
        quality = native(cv['effective_quality'], (16,), actions.dtype)
        require(same(actions, source['values']['samples']), 'qd_off_same_call_population')
        related = lambda kind: [r for r in kinds[kind] if r['values']['scoring_batch_id'] == source['sequence']]
        aggregates, effectives = related('scoring_aggregate'), related('effective_quality')
        require(len(aggregates) == len(effectives) == 1, 'qd_off_same_call_scores')
        aggregate, effective = aggregates[0], effectives[0]; ev = effective['values']
        require(ev.get('quality_mode', 'provider') == cv.get('quality_mode', 'provider') == 'provider'
            and ev['reward_mode'] == 'normal' and ev['scoring_scope'] == aggregate['values']['scoring_scope'] == scope,
            'qd_off_raw_provider_mode')
        costs = native(ev['costs'], (16,), actions.dtype)
        require(same(quality, ev['quality']) and same(quality, aggregate['values']['aggregate_before_reward_mode'])
            and same(costs, -quality), 'qd_off_native_cost_raw')
        require(source['sequence'] < aggregate['sequence'] < effective['sequence'] < row['sequence'], 'qd_off_scoring_order')
        if previous is not None:
            prior, prior_actions, prior_quality, prior_costs = previous
            parent = parents[iteration]; pv = parent['values']; indices = pv['parent_indices']
            require(prior['sequence'] < parent['sequence'] < source['sequence'], 'qd_off_parent_prior_only')
            require(same(pv['source_population'], prior_actions) and same(pv['source_quality'], prior_quality)
                and same(pv['source_costs'], prior_costs), 'qd_off_parent_previous_population')
            require(pv['parent_cell_ids'] is None and pv['elite_count'] == 0 and torch.is_tensor(indices)
                and indices.device.type == 'cpu' and indices.dtype == torch.int64 and indices.shape == (16,)
                and bool(((indices >= 0) & (indices < 16)).all()), 'qd_off_parent_indices_or_archive_metadata')
            links.append({'iter_idx': iteration, 'parent_sequence': parent['sequence'],
                'source_canonical_sequence': prior['sequence'], 'parent_indices': indices.tolist(),
                'source_occurrence_ids': [prior['values']['occurrence_ids'][i] for i in indices.tolist()]})
        batches.append({'iter_idx': iteration, 'canonical_sequence': row['sequence'], 'scoring_batch_id': source['sequence']})
        previous = row, actions, quality, costs
    last, actions, quality, costs = previous
    final_event = one('final_selection'); final = final_event['values']; decoded_event = one('policy_action_decode')
    require(final['selection_rule'] == 'cost_argmin' and final.get('quality_mode', 'provider') == 'provider'
        and not any(k in final for k in ('terminal_population', 'archive_reference', 'stage_reward_reference')),
        'qd_off_final_mode')
    require(last['sequence'] < final_event['sequence'] < decoded_event['sequence'], 'qd_off_final_order')
    require(same(final['population'], actions), 'qd_off_final_last_population')
    index = int(torch.argmin(costs).item())
    ties = torch.nonzero(costs == costs.min(), as_tuple=False).reshape(-1).tolist()
    require(type(final['selected_index']) is int and final['selected_index'] == index, 'qd_off_first_native_argmin')
    selected = native(final['selected_latent'], (1, 64, 128), actions.dtype)
    require(same(selected, actions[index:index+1]) and final['selected_cost'] == costs[index].item()
        and final['selected_quality'] == quality[index].item(), 'qd_off_selected_native_raw_cost')
    decoded = decoded_event['values']; committed = one('decision_committed')['values']
    require(same(decoded['selected_latent'], selected.float()), 'qd_off_selected_policy_cast')
    commands = decoder.decode_rdt_libero_action_chunk(decoded['selected_latent'], 8)
    require(numeric(commands, decoded['action_chunk']) and numeric(commands, committed['action_chunk'])
        and committed['execution_horizon'] == 8, 'qd_off_deployed_decode')
    m = len(kinds['action_dispatch']); sent = kinds['executed_action']
    require(1 <= m <= 8 and len(sent) == m, 'qd_off_actual_prefix')
    require(all(numeric(row['values']['action_numpy'], commands[0, i]) for i, row in enumerate(sent)), 'qd_off_actual_dispatch')
    return {'decision_id': context['decision_id'], 'global_step': context['global_step'],
        'canonical_batches_verified': 11, 'canonical_candidates_verified': 176, 'parent_rounds_verified': 10,
        'actual_prefix_length': m, 'selected_index': index, 'selected_cost': final['selected_cost'],
        'selected_raw_reward': final['selected_quality'], 'minimum_cost_tie_indices': ties,
        'selected_occurrence_id': last['values']['occurrence_ids'][index],
        'selected_native_sha256': audit._native_sha(selected[0]), 'selected_fingerprint': audit.fingerprints(selected)[0],
        'terminal_native_costs': audit._native_record(costs), 'terminal_raw_provider_quality': audit._native_record(quality),
        'terminal_native_ids': [audit._native_sha(a) for a in actions], 'canonical_sources': batches,
        'parent_associations': links, 'stage_scope': 'original no-archive source uses selected raw and population spread; no recorded normalized Stage input'}


def native_audit_alignment(audit, metrics, *, require):
    """Strict metadata association; no native read/import or new activity gate."""
    require(audit.get('accepted') is True and audit.get('evidence_complete') is True
        and audit.get('errors') == [], 'QD-OFF accepted complete audit required')
    gate = audit.get('n4_qd_off_audit', {})
    n = len(metrics); decisions = gate.get('decisions', [])
    require(gate.get('schema') == SCHEMA and gate.get('checked_decisions') == len(decisions) == n
        and gate.get('canonical_batches_verified') == 11*n and gate.get('canonical_candidates_verified') == 176*n
        and gate.get('parent_rounds_verified') == 10*n, 'QD-OFF native coverage differs')
    steps = [m.get('global_step') for m in metrics]
    require(all(type(s) is int for s in steps) and steps == sorted(set(steps))
        and steps == [d.get('global_step') for d in decisions], 'QD-OFF native/metric steps differ')
    for m, d in zip(metrics, decisions):
        require(m.get('qd_archive_active_for_chunk') is False and m.get('qd_archive_enabled') is False
            and m.get('qd_quality_mode', 'provider') == 'provider'
            and m.get('qd_final_selection_mode', 'archive_global_best') == 'archive_global_best'
            and 'qd_terminal_population' not in m and 'qd_archive_reference' not in m, 'QD-OFF resolved consumer differs')
        for a, b in [('selected_idx', 'selected_index'), ('selected_cost', 'selected_cost'), ('selected_reward', 'selected_raw_reward')]:
            require(a in m and b in d and type(m[a]) is type(d[b]) and m[a] == d[b], 'QD-OFF metric/native differs: ' + a)
        require(d.get('canonical_batches_verified') == 11 and d.get('canonical_candidates_verified') == 176
            and d.get('parent_rounds_verified') == 10 and type(d.get('actual_prefix_length')) is int
            and 1 <= d['actual_prefix_length'] <= 8, 'QD-OFF native decision coverage differs')
        costs = d.get('terminal_native_costs', {}); values = costs.get('values', [])
        require(costs.get('shape') == [16] and len(values) == 16
            and d['selected_index'] == values.index(min(values))
            and d['selected_cost'] == values[d['selected_index']]
            and d.get('minimum_cost_tie_indices') == [i for i, v in enumerate(values) if v == min(values)],
            'QD-OFF native first-index/ties summary differs')
    require(gate.get('actual_actions_verified') == sum(d['actual_prefix_length'] for d in decisions), 'QD-OFF actual-m aggregate differs')
    return {k: gate[k] for k in ('schema', 'checked_decisions', 'canonical_batches_verified',
        'canonical_candidates_verified', 'parent_rounds_verified', 'actual_actions_verified')}


def audit_episode(episode_dir, episode_compute_file):
    base = module(ROOT/'scripts/audit_decision_evidence.py', '_n4_off_generic_audit')
    decoder = module(ROOT/'core/rdt_libero_action_converter.py', '_n4_off_deployed_decoder')
    captured = []; original_load = base.load_events
    def load(root, status):
        events = original_load(root, status); captured.extend(events); return events
    base.load_events = load
    report = base.audit_episode(episode_dir, episode_compute_file)
    if not report['accepted']:
        return report
    try:
        grouped = defaultdict(list)
        for row in captured: grouped[row['decision_id']].append(row)
        decisions = []
        for rows in grouped.values():
            context = next(row for row in rows if row['event'] == 'decision_context')
            kinds = defaultdict(list)
            for row in rows: kinds[row['event']].append(row)
            if context['values']['use_guidance'] and context['values']['providers']:
                decisions.append(check_decision(kinds, context, base, decoder))
            else:
                base.require(not kinds['final_selection'] and not kinds['archive_parent_allocation'], 'qd_off_unguided_consumer')
        report['n4_qd_off_audit'] = {'schema': SCHEMA, 'checked_decisions': len(decisions),
            'canonical_batches_verified': 11*len(decisions), 'canonical_candidates_verified': 176*len(decisions),
            'parent_rounds_verified': 10*len(decisions),
            'actual_actions_verified': sum(d['actual_prefix_length'] for d in decisions), 'decisions': decisions,
            'scope': 'Total QD removal; C0 active algorithm; no archive, native last-population consumer and deployed actual-m commands; no task benefit or isolated-parent causal claim'}
    except Exception as error:
        report['accepted'] = False
        report['errors'].append(str(error) if isinstance(error, base.AuditFailure) else 'qd_off_invalid_evidence:' + type(error).__name__)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode-dir', type=Path, required=True)
    parser.add_argument('--episode-compute', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('CPU-only audit requires empty CUDA mask')
    report = audit_episode(args.episode_dir, args.episode_compute)
    with args.output.open('x') as stream: json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'accepted': report['accepted'], 'output': str(args.output)}))
    raise SystemExit(0 if report['accepted'] else 1)


if __name__ == '__main__': main()
