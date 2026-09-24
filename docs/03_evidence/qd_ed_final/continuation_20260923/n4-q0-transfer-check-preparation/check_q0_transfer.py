#!/usr/bin/env python3
"""N4 finite Q0 transfer check; no algorithm implementation or execution authority."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import torch

HERE = Path(__file__).resolve().parent
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
SOURCE = 'bd618b931eb9d8fc2c01b978c4ef220c9bb03889'
COHORT = 'N3_EXECUTED_FEEDBACK_DEV_20260923'
IDENTITY = ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')
CANONICAL = {'canonical_initial', 'canonical_offspring', 'canonical_population'}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def sha(data): return hashlib.sha256(data).hexdigest()


def load_module(name, ref):
    path = Path(ref['path']); require(sha(path.read_bytes()) == ref['sha256'], 'dependency_sha_differs')
    spec = importlib.util.spec_from_file_location('n4_q0_' + name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module); return module


def dependencies(definition):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not torch.cuda.is_initialized(), 'CPU_mask_required')
    require(sys.version.split()[0] == definition['python_version'] and torch.__version__ == definition['torch_version']
            and torch.get_default_dtype() == torch.float32, 'environment_identity_differs')
    return {name: load_module(name, ref) for name, ref in definition['modules'].items() if name != 'report'}


def one(rows, event):
    found = [r for r in rows if r['event'] == event]
    require(len(found) == 1, 'missing_or_duplicate_' + event); return found[0]


def fingerprint(t):
    # Collector's metadata convention only; native bytes remain the join key.
    return sha(t.float().contiguous().numpy().astype('<f4', copy=False).tobytes())


def native_tensor(t, shape, native):
    require(torch.is_tensor(t) and tuple(t.shape) == tuple(shape) and t.is_floating_point(), 'native_shape_or_type')
    native.native_id(t); return t


def value_record(t, native):
    return {'dtype': str(t.dtype), 'shape': list(t.shape), 'native_id': native.native_id(t), 'values': t.tolist()}


def numeric_same(a, b):
    # FP32 numeric equality deliberately treats +0 and -0 as equal.
    return a.dtype == b.dtype == torch.float32 and a.shape == b.shape and bool(torch.isfinite(a).all() and torch.isfinite(b).all() and torch.equal(a, b))


def decode_and_dispatch(rows, modules, selected=None):
    native = modules['native']; decoded_event = one(rows, 'policy_action_decode')
    raw = native_tensor(decoded_event['values']['selected_latent'], (1, 64, 128), native)
    require(raw.dtype == torch.float32, 'deployed_raw_decode_dtype_differs')
    if selected is not None:
        require(native.same(raw, selected.float()), 'selected_to_deployed_FP32_cast_differs')
    decoded = native_tensor(decoded_event['values']['action_chunk'], (1, 8, 7), native)
    actual = modules['decoder'].decode_rdt_libero_action_chunk(raw, 8)
    require(numeric_same(decoded, actual), 'deployed_actual_decode_differs')
    committed = one(rows, 'decision_committed')
    require(decoded_event['sequence'] < committed['sequence'] and committed['values']['execution_horizon'] == 8
            and numeric_same(decoded, committed['values']['action_chunk']), 'committed_decode_differs')
    dispatches = [r for r in rows if r['event'] == 'action_dispatch']; m = len(dispatches)
    require(1 <= m <= 8 and [r['values']['execution_index'] for r in dispatches] == list(range(1, m+1)), 'actual_prefix_invalid')
    require([r['global_step'] for r in dispatches] == list(range(rows[0]['global_step'], rows[0]['global_step']+m)), 'dispatch_global_prefix_gap')
    sent_rows = []
    for i, dispatch in enumerate(dispatches):
        stop = dispatches[i+1]['sequence'] if i+1 < m else float('inf')
        window = [r for r in rows if dispatch['sequence'] < r['sequence'] < stop]
        sent, outcome, returned = [one(window, e) for e in ('executed_action', 'pre_reset_outcome', 'step_returned')]
        require(committed['sequence'] < dispatch['sequence'] < sent['sequence'] < outcome['sequence'] < returned['sequence']
                and outcome['reset_sequence'] == dispatch['reset_sequence'], 'dispatch_ack_or_pre_reset_order_differs')
        command = native_tensor(sent['values']['action_numpy'], (7,), native)
        require(numeric_same(command, decoded[0, i]), 'actual_dispatched_command_differs')
        sent_rows.append(command)
        if i < m-1: require(not outcome['values']['terminated'] and not returned['values']['truncated'], 'dispatch_after_terminal')
    return actual, torch.stack(sent_rows), m


def check_guided(rows, modules):
    native = modules['native']; by = defaultdict(list)
    for r in rows: by[r['event']].append(r)
    canonical = by['canonical_candidate_batch']
    require([r['values']['iter_idx'] for r in canonical] == list(range(-1, 10)), 'canonical_11_iteration_coverage')
    sources = [r for r in by['scoring_inputs'] if r['values']['scoring_scope']['role'] in CANONICAL]
    scoring = {r['values']['scoring_scope']['iter_idx']: r for r in sources}
    allocations = {r['values']['iter_idx']: r for r in by['archive_parent_allocation']}
    parents = {r['values']['iter_idx']: r for r in by['parent_allocation']}
    require(len(sources) == len(scoring) == 11 and set(scoring) == set(range(-1, 10)), 'canonical_scoring_coverage')
    require(len(by['archive_parent_allocation']) == len(by['parent_allocation']) == len(allocations) == len(parents) == 10
            and set(allocations) == set(parents) == set(range(10)), 'parent_round_coverage')
    known = defaultdict(list); batches = []; parent_records = []; occurrence_ids = set()
    for row in canonical:
        cv = row['values']; iteration = cv['iter_idx']; source = scoring[iteration]; scope = source['values']['scoring_scope']
        require(scope['role'] == ('canonical_initial' if iteration == -1 else 'canonical_offspring'), 'Q0_elite_zero_scoring_role')
        population = native_tensor(cv['candidates'], (16, 64, 128), native)
        quality = native_tensor(cv['effective_quality'], (16,), native)
        require(population.dtype == quality.dtype and native.same(population, source['values']['samples']), 'same_call_native_population_differs')
        linked = [r for r in rows if r['values'].get('scoring_batch_id') == source['sequence']]
        aggregate = one(linked, 'scoring_aggregate'); effective = one(linked, 'effective_quality'); ev = effective['values']
        require(ev.get('quality_mode', 'provider') == 'provider' and cv.get('quality_mode', 'provider') == 'provider'
                and ev['reward_mode'] == 'normal' and ev['scoring_scope'] == aggregate['values']['scoring_scope'] == scope,
                'Q0_original_provider_mode_differs')
        costs = native_tensor(ev['costs'], (16,), native)
        require(native.same(quality, aggregate['values']['aggregate_before_reward_mode']) and native.same(quality, ev['quality'])
                and costs.dtype == quality.dtype and native.same(costs, -quality), 'same_call_cost_raw_sign_differs')
        require(source['sequence'] < aggregate['sequence'] < effective['sequence'] < row['sequence'], 'canonical_call_order_differs')
        if iteration >= 0:
            parent, allocation = parents[iteration], allocations[iteration]; pv, av = parent['values'], allocation['values']
            require(all(prior['sequence'] < allocation['sequence'] < parent['sequence'] < source['sequence']
                        for prior in canonical if prior['values']['iter_idx'] < iteration), 'parent_prior_only_order_differs')
            parent_actions = native_tensor(pv['source_population'], (16, 64, 128), native)
            require(parent_actions.dtype == population.dtype and pv['elite_count'] == 0
                    and pv['parent_indices'].dtype == torch.int64 and torch.equal(pv['parent_indices'], torch.arange(16)), 'Q0_sparse_identity_parent_contract')
            pr = native_tensor(av['parent_rewards'], (16,), native); pc = native_tensor(av['parent_costs'], (16,), native)
            require(pr.dtype == pc.dtype == torch.float32 and native.same(pr, pv['source_quality'])
                    and native.same(pc, pv['source_costs']), 'archive_parent_FP32_container_differs')
            require(len(av['parent_fingerprints']) == 16 and av['parent_lanes'] == ['quality']*16, 'Q0_parent_lane_contract')
            links = []
            for i, action in enumerate(parent_actions):
                nid = native.native_id(action); matches = known[nid]
                require(matches and all(x['quality'] == pr[i].item() and x['cost'] == pc[i].item() for x in matches), 'parent_native_prior_cost_association_unknown')
                require(av['parent_fingerprints'][i] == fingerprint(action), 'parent_fingerprint_differs')
                links.append({'slot': i, 'native_id': nid, 'matching_occurrence_ids': [x['occurrence_id'] for x in matches]})
            parent_records.append({'iter_idx': iteration, 'allocation_sequence': allocation['sequence'], 'parent_sequence': parent['sequence'], 'parent_indices': pv['parent_indices'].tolist(), 'slots': links, 'unique_insertion_ancestry': 'Unknown'})
        ids = [native.native_id(a) for a in population]
        require(len(cv['occurrence_ids']) == len(set(cv['occurrence_ids'])) == 16 and len(cv['canonical_fingerprints']) == 16, 'canonical_occurrence_count')
        for i, action in enumerate(population):
            occurrence = cv['occurrence_ids'][i]
            require(occurrence not in occurrence_ids and cv['canonical_fingerprints'][i] == fingerprint(action), 'canonical_occurrence_identity_differs')
            occurrence_ids.add(occurrence)
            known[ids[i]].append({'occurrence_id': occurrence, 'iter_idx': iteration, 'row': i,
                'canonical_sequence': row['sequence'], 'scoring_sequence': source['sequence'], 'quality': quality[i].item(), 'cost': costs[i].item(), 'dtype': str(costs.dtype)})
        batches.append({'iter_idx': iteration, 'canonical_sequence': row['sequence'], 'scoring_sequence': source['sequence'],
            'native_ids': ids, 'occurrence_ids': cv['occurrence_ids'], 'stored_cost': value_record(costs, native), 'original_quality': value_record(quality, native)})
    final_event = one(rows, 'final_selection'); final = final_event['values']; decoded_event = one(rows, 'policy_action_decode')
    require(canonical[-1]['sequence'] < final_event['sequence'] < decoded_event['sequence'] and final['selection_rule'] == 'archive_global_best', 'actual_final_consumer_order_or_rule')
    archive = final['population']; require(torch.is_tensor(archive) and archive.ndim == 3 and 1 <= len(archive) <= 16, 'archive_pool_shape')
    native_tensor(archive, (len(archive), 64, 128), native)
    selected_index = final['selected_index']; require(type(selected_index) is int and 0 <= selected_index < len(archive), 'actual_selected_index')
    selected = native_tensor(final['selected_latent'], (1, 64, 128), native)
    require(native.same(selected, archive[selected_index:selected_index+1]), 'actual_selected_native_slot')
    final_slots = []
    for i, action in enumerate(archive):
        nid = native.native_id(action); matches = known[nid]
        require(matches and len({(x['dtype'], x['quality'], x['cost']) for x in matches}) == 1, 'archive_raw_cost_native_association_unknown')
        final_slots.append({'slot': i, 'native_id': nid, 'quality': matches[0]['quality'], 'cost': matches[0]['cost'], 'matching_occurrences': matches})
    chosen = final_slots[selected_index]
    require(final['selected_quality'] == chosen['quality'] == max(x['quality'] for x in final_slots)
            and final['selected_cost'] == chosen['cost'], 'actual_selected_raw_cost_differs')
    require(final['selected_canonical_fingerprint'] == decoded_event['values']['selected_canonical_fingerprint'] == fingerprint(selected[0])
            and final['selected_fingerprint'] == fingerprint(selected[0]), 'actual_selected_fingerprint_differs')
    actual_commands, sent, m = decode_and_dispatch(rows, modules, selected)
    last = canonical[-1]['values']['candidates']; last_batch = batches[-1]
    # This is the same-call stored native cost tensor, not reconstructed quality.
    last_cost = one([r for r in rows if r['values'].get('scoring_batch_id') == last_batch['scoring_sequence']], 'effective_quality')['values']['costs']
    alternative_index = int(torch.argmin(last_cost).item()); ties = torch.nonzero(last_cost == last_cost.min(), as_tuple=False).reshape(-1).tolist()
    require(alternative_index == ties[0], 'first_index_native_argmin_contract')
    alternative = last[alternative_index:alternative_index+1]
    alternative_commands = modules['decoder'].decode_rdt_libero_action_chunk(alternative, 8)
    require(alternative_commands.dtype == torch.float32 and torch.isfinite(alternative_commands).all(), 'alternative_decode_invalid')
    changed = actual_commands[0] != alternative_commands[0]
    full_positions = torch.nonzero(changed, as_tuple=False).tolist(); prefix_positions = torch.nonzero(changed[:m], as_tuple=False).tolist()
    selected_id = native.native_id(selected[0]); member_indices = [i for i, nid in enumerate(last_batch['native_ids']) if nid == selected_id]
    return {'status': 'known_guided_comparison', 'actual_prefix_length': m, 'canonical_batches': batches, 'canonical_evaluations': 176,
        'parent_rounds': parent_records, 'actual_archive_slots': final_slots, 'actual_selected_index': selected_index,
        'actual_selected_native_id': selected_id, 'actual_selected_quality': final['selected_quality'], 'actual_selected_cost': final['selected_cost'],
        'last_canonical_membership_indices': member_indices, 'nonmember': not member_indices,
        'alternative_first_index': alternative_index, 'alternative_native_id': native.native_id(alternative[0]),
        'minimum_cost_tie_indices': ties, 'minimum_cost_tie_native_ids': [last_batch['native_ids'][i] for i in ties],
        'alternative_native_identity_differs': not native.same(selected, alternative),
        'actual_commands_FP32': value_record(actual_commands[0], native), 'alternative_hypothetical_commands_FP32': value_record(alternative_commands[0], native),
        'actual_dispatched_commands_FP32': value_record(sent, native), 'different_first8_positions': full_positions,
        'different_actual_m_positions': prefix_positions, 'different_first8': bool(full_positions), 'different_actual_m': bool(prefix_positions),
        'difference_only_after_m': bool(full_positions) and not prefix_positions,
        'nonmember_and_actual_m_difference': not member_indices and bool(prefix_positions),
        'auxiliary_scoring_batches_excluded': len(by['scoring_inputs'])-len(sources), 'counterfactual_trajectory_or_outcome': 'Unknown'}


def admit(manifest, auth, definition, modules, inputs):
    """Ten Q0 snapshots only; complete native hash admission before decode."""
    require(manifest['schema'] == 'n4-q0-transfer-input-v1' and auth['reviewed_manifest'] == auth['manifest']
            and auth['completed_Q0_scope_reviewed'] is True, 'reviewed_Q0_scope_missing')
    require(manifest['matrix_report']['sha256'] == definition['matrix_report_sha256']
            and manifest['matrix_report_input']['sha256'] == definition['matrix_input_sha256']
            and manifest['completed_diagnostic_provenance']['sha256'] == definition['completed_diagnostic_provenance_sha256'], 'fixed_metadata_identity_differs')
    matrix = inputs.read(manifest['matrix_report']); authority = inputs.read(manifest['matrix_report_input'])
    provenance = inputs.read(manifest['completed_diagnostic_provenance'])
    require(matrix['schema'] == 'qd-ed-n3-matrix-report-v1' and matrix['cohort_id'] == COHORT
            and matrix['matrix'] == 'complete_valid_30' and matrix['input_scope_complete'] is True
            and matrix['inflight_records'] == [] and authority['input_scope_complete'] is True
            and matrix['input_manifest'] == authority and matrix['input_manifest_sha256'] == manifest['matrix_report_input']['sha256'], 'complete_matrix_authority_differs')
    require(provenance['complete'] is True and provenance['source_commit'] == SOURCE
            and provenance['cuda_initialized'] is False and provenance['new_quality_computation'] is False
            and provenance['fresh_audit_calls'] == 0, 'completed_snapshot_provenance_differs')
    bound = provenance['input_hashes']
    def recorded(ref, lines=False):
        require(bound.get(ref['path']) == ref['sha256'], 'not_bound_by_completed_diagnostic')
        return inputs.read(ref, lines=lines)
    base = recorded(authority['base_plan']); originals = [r for r in base['episodes'] if not r.get('retry_of')]
    universe = [(t, a) for t in range(10) for a in ('C0', 'Q0', 'N3')]
    require(base['source_commit'] == SOURCE and base['artifact_root'] == str(inputs.root)
            and [(r['task_id'], r['profile']) for r in originals] == universe
            and [(c['identity']['task_id'], c['identity']['profile']) for c in matrix['cells']] == universe, 'original_scientific_universe_differs')
    inventory = {r['path']: r['sha256'] for r in base['code_files']}
    require(len(inventory) == len(base['code_files']) and all(inventory.get(p) == s for p, s in definition['reviewed_source_sha256'].items()), 'scientific_source_inventory_differs')
    require(definition['modules']['decoder']['sha256'] == inventory['core/rdt_libero_action_converter.py']
            and definition['modules']['report']['sha256'] == authority['script_sha256'] == inventory['scripts/qd_ed_n3_report.py'], 'decoder_or_report_source_differs')
    metadata = {p: inventory[p] for p in ('scripts/qd_ed_n3_report.py', 'scripts/qd_ed_n3_plan.py')}
    require(auth['reviewed_metadata_sources'] == metadata, 'metadata_source_review_missing')
    modules['report'] = load_module('report', definition['modules']['report'])
    admission_definition = inputs.read(definition['admission_definition'])
    plans = modules['stream'].admit_plans(authority, base, originals, admission_definition, inputs)
    require([c['valid_attempt_id'] for c in matrix['cells'][:3]] == admission_definition['checkpoint_admission']['release_metadata']['attempt_ids'], 'checkpoint_first3_differs')
    require(all(len({r['episode_key'] for r in p['episodes']}) == len(p['episodes']) for p in plans.values()), 'own_plan_row_ambiguity')
    cells = [c for c in matrix['cells'] if c['identity']['profile'] == 'Q0']; extras = manifest['cells']; snapshots = auth['completed_audit_snapshots']
    require(len(cells) == len(extras) == len(snapshots) == 10 and [c['identity']['task_id'] for c in cells] == list(range(10))
            and len({c['valid_attempt_id'] for c in cells}) == 10
            and [e['attempt_id'] for e in extras] == [c['valid_attempt_id'] for c in cells]
            and len({s['attempt_id'] for s in snapshots}) == 10
            and {s['attempt_id'] for s in snapshots} == {c['valid_attempt_id'] for c in cells}, 'exact_10_Q0_representatives_required')
    by_snapshot = {s['attempt_id']: s for s in snapshots}; admitted = []
    for cell, extra in zip(cells, extras):
        ident = cell['identity']; original = originals[ident['task_id']*3+1]
        require(cell['status'] == 'complete_valid' and not cell['inflight'] and ident == {k: original[k] for k in IDENTITY}, 'accepted_Q0_identity_differs')
        reps = [a for a in cell['attempts'] if a['status'] == 'complete_valid']; require(len(reps) == 1, 'multiple_valid_representatives')
        saved = reps[0]; refs = saved['references']; terminal = recorded(refs['terminal']); aid = cell['valid_attempt_id']
        require(set(refs) == {'terminal', 'audit', 'compute', 'metrics'} and terminal['attempt_id'] == aid
                and terminal['event'] == 'valid' and terminal['outcome_valid'] is True
                and all(terminal.get(k) == v for k, v in saved['terminal'].items()), 'accepted_terminal_differs')
        require(terminal['plan_sha256'] in plans, 'unlisted_own_plan')
        row = modules['report'].validate_record_identity(terminal, plans[terminal['plan_sha256']], terminal['plan_sha256'])
        require(terminal['identity'] == ident and row['init_row_sha256'] == original['init_row_sha256'], 'own_plan_cell_differs')
        if terminal.get('retry_of'):
            prior = [a for a in cell['attempts'] if a['terminal']['attempt_id'] == terminal['retry_of']]
            require(len(prior) == 1 and prior[0]['terminal']['outcome_valid'] is False and prior[0]['terminal']['identity'] == ident, 'recovery_predecessor_link_differs')
        out = inputs.path(terminal['output_dir']); ed = out/'eds_eval'; ep = ed/'decision_evidence/episode_000'
        require(out.parent == inputs.root/'attempts' and out.name == aid, 'owned_attempt_path_differs')
        for kind, path in {'terminal': out/'attempt-result.json', 'audit': ed/'decision-evidence-audit.json', 'compute': ed/'episode_compute.jsonl', 'metrics': ed/'eds_metrics.jsonl'}.items():
            require(inputs.path(refs[kind]['path']) == path and bound.get(str(path)) == refs[kind]['sha256'], 'canonical_accepted_reference_differs')
        audit = recorded(refs['audit']); compute_rows = recorded(refs['compute'], True)
        require(audit['accepted'] is True and audit['evidence_complete'] is True and audit['errors'] == []
                and audit['original_execution_outcome'] == 'completed' and audit['episode_dir'] == str(ep)
                and audit['episode_compute_file'] == str(ed/'episode_compute.jsonl') and len(compute_rows) == 1, 'accepted_audit_binding_differs')
        compute = compute_rows[0]; metadata_ident = {'episode_id': 0, 'task_id': row['task_id'], 'episode_seed': row['env_seed']}
        require(all(compute[k] == v for k, v in metadata_ident.items()) and compute['outcome'] == terminal['compute_outcome'] == 'completed', 'compute_identity_differs')
        require(set(extra) == {'attempt_id', 'metadata', 'status', 'index'}, 'unexpected_cell_input_fields')
        for kind, path in {'metadata': ed/'episode_metadata.jsonl', 'status': ep/'status.json', 'index': ep/'events.jsonl'}.items():
            require(inputs.path(extra[kind]['path']) == path, 'collector_reference_path_differs')
        require(recorded(extra['metadata'], True) == [metadata_ident], 'collector_metadata_differs')
        status = recorded(extra['status']); index = recorded(extra['index'], True)
        expected = {'attempt_id': aid, 'audit': refs['audit'], 'status': extra['status'], 'index': extra['index'],
                    'auditor_sha256': inventory['scripts/audit_decision_evidence.py'], 'binding': modules['stream'].SNAPSHOT}
        require(by_snapshot[aid] == expected, 'root_completed_audit_snapshot_differs')
        require(status['schema'] == 'qd-ed-decision-evidence-v1' and status['episode'] == 0 and status['complete'] is True
                and status['failed'] is False and status['pending_action'] is False
                and status['bundles'] == len(index) == compute['decision_evidence']['bundles'], 'collector_not_complete')
        names = [f'bundle_{i:06d}.pt' for i in range(1, len(index)+1)]
        require([r['bundle'] for r in index] == names and {p.name for p in ep.glob('bundle_*.pt')} == set(names), 'exact_bundle_inventory_differs')
        admitted.append({'ep': ep, 'index': index, 'status': status, 'compute': compute, 'terminal': terminal, 'cell': f"t{ident['task_id']:02d}-q0", 'references': refs})
    # Uniform metadata admission is complete; hash every Q0 indexed native file before decoding any.
    for item in admitted:
        for r in item['index']:
            ref = {'path': str(item['ep']/r['bundle']), 'sha256': r['sha256']}
            require(bound.get(ref['path']) == ref['sha256'], 'native_snapshot_binding_differs'); inputs.bytes(ref)
    return admitted


def inspect_decision(rows, modules):
    context = one(rows, 'decision_context'); c = context['values']
    require(all(r['decision_id'] == context['decision_id'] and r['episode'] == context['episode'] for r in rows), 'decision_identity_mixed')
    dispatches = [r for r in rows if r['event'] == 'action_dispatch']; m = len(dispatches)
    require(type(c['use_guidance']) is bool and 1 <= m <= 8
            and [r['values']['execution_index'] for r in dispatches] == list(range(1, m+1))
            and [r['global_step'] for r in dispatches] == list(range(context['global_step'], context['global_step']+m)), 'context_actual_prefix_invalid')
    base = {'decision_id': context['decision_id'], 'context_sequence': context['sequence'],
            'global_step': context['global_step'], 'reset_sequence': context['reset_sequence'],
            'stage': c['stage'], 'previous_stage': c.get('previous_stage'), 'stage_changed': c.get('stage_changed'),
            'previous_decision_id': c.get('previous_decision_id'), 'provider_identities': c.get('providers'),
            'guided': c['use_guidance'], 'actual_prefix_length': m}
    if not c['use_guidance']:
        return {**base, 'status': 'not_applicable_unguided', 'comparison': None}
    try:
        comparison = check_guided(rows, modules)
    except ValueError as error:
        return {**base, 'status': 'Unknown_required_association', 'reason': str(error), 'comparison': None}
    return {**base, 'status': 'known_guided_comparison', 'comparison': comparison}


def summarize(cells, expected):
    rows = [r for c in cells for r in c['decisions']]; guided = [r for r in rows if r['guided']]
    known = [r['comparison'] for r in guided if r['status'] == 'known_guided_comparison']
    require(len(cells) == expected['cells'] and len(rows) == expected['decisions'] and len(guided) == expected['guided']
            and sum(r['actual_prefix_length'] for r in rows) == expected['actions'], 'complete_known_inventory_differs')
    counts = dict(Counter(r['status'] for r in rows)); witnesses = sum(v['nonmember_and_actual_m_difference'] for v in known)
    fields = ('nonmember', 'alternative_native_identity_differs', 'different_first8', 'different_actual_m', 'difference_only_after_m', 'nonmember_and_actual_m_difference')
    return {'cells': len(cells), 'decisions': len(rows), 'guided': len(guided), 'actual_actions': expected['actions'],
            'dispositions': counts, 'known_guided_associations': len(known), 'unknown_required_associations': len(guided)-len(known),
            'known_comparison_counts': {key: sum(v[key] for v in known) for key in fields},
            'native_cost_tie_decisions': sum(len(v['minimum_cost_tie_indices']) > 1 for v in known),
            'gate_passed': len(known) == expected['guided'] and witnesses >= 1,
            'gate_scope': 'complete fixed-pool native/decode activity prerequisite only; no task benefit or online authority'}


def run(auth_path, auth_sha, output):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not torch.cuda.is_initialized(), 'CPU_mask_required')
    definition = json.loads((HERE/'dependencies-v1.json').read_text()); modules = dependencies(definition)
    helper = modules['stream']; inputs = helper.Inputs(ROOT)
    auth = inputs.read({'path': str(Path(auth_path).resolve()), 'sha256': auth_sha})
    require(auth['schema'] == 'n4-q0-transfer-read-authorization-v1' and auth['status'] == 'authorized', 'actual_read_not_authorized')
    freeze = inputs.read(auth['freeze'])
    require(freeze['actual_read_authorized'] is False and freeze['files']['check_q0_transfer.py'] == sha(Path(__file__).read_bytes()), 'freeze_identity_differs')
    for name, digest in freeze['files'].items():
        require(Path(name).name == name and sha((HERE/name).read_bytes()) == digest, 'local_freeze_differs')
    manifest = inputs.read(auth['manifest']); out = inputs.path(output)
    require(str(out) == auth['output'] and out.is_relative_to(inputs.root/'continuation_20260923/n4-q0-transfer-check-analysis') and not out.exists(), 'new_authorized_output_required')
    out.mkdir(parents=True, exist_ok=False); phase = 'admission'; start = time.monotonic(); current = None
    def status(value): (out/'status.json').write_text(json.dumps(value, allow_nan=False)+'\n')
    status({'complete': False, 'phase': phase})
    try:
        admitted = admit(manifest, auth, definition, modules, inputs); cells = []; index = []
        for item in admitted:
            phase = 'extraction'; current = item['cell']; decisions = []
            for rows in helper.stream_decisions(item, inputs, torch): decisions.append(inspect_decision(rows, modules))
            require(len(decisions) == item['status']['decisions']
                    and sum(r['guided'] for r in decisions) == item['compute']['guided_chunks'], 'cell_decision_inventory_differs')
            require([r['global_step'] for r in decisions] == [sum(d['actual_prefix_length'] for d in decisions[:i]) for i in range(len(decisions))], 'decision_global_prefix_gap')
            cell = {'schema': 'n4-q0-transfer-cell-v1', 'cell': current, 'attempt_id': item['terminal']['attempt_id'], 'identity': item['terminal']['identity'],
                    'retry_of': item['terminal'].get('retry_of'), 'accepted_audit': item['references']['audit'], 'terminal_reference': item['references']['terminal'], 'decisions': decisions}
            helper.xjson(out/(current+'.json'), cell); cells.append(cell)
            index.append({'cell': current, 'attempt_id': cell['attempt_id'], 'path': current+'.json', 'sha256': sha((out/(current+'.json')).read_bytes())})
            print(json.dumps({'completed_cells': len(cells), 'cell': current}), flush=True)
        phase = 'final_verification'; current = None
        summary = summarize(cells, definition['inventory']); inputs.finish()
        require(not torch.cuda.is_initialized(), 'CUDA_initialized')
        for ref in definition['modules'].values(): require(sha(Path(ref['path']).read_bytes()) == ref['sha256'], 'dependency_changed')
        for name, digest in freeze['files'].items(): require(sha((HERE/name).read_bytes()) == digest, 'local_source_changed')
        helper.xjson(out/'index.json', {'schema': 'n4-q0-transfer-index-v1', 'complete': True, 'cells': index, 'summary': summary, 'matrix_authority': manifest['matrix_report']})
        helper.xjson(out/'provenance.json', {'complete': True, 'authorization_sha256': auth_sha, 'manifest': auth['manifest'], 'freeze': auth['freeze'],
            'source_commit': SOURCE, 'dependencies': definition, 'input_hashes': inputs.hashes, 'cuda_initialized': False,
            'fresh_audit_calls': 0, 'new_quality_computation': False, 'hypothetical_decodes_only': True, 'CPU_wall_seconds': time.monotonic()-start})
        status({'complete': True, 'cells': 10, 'index_sha256': sha((out/'index.json').read_bytes()), 'gate_passed': summary['gate_passed']})
    except Exception as error:
        status({'complete': False, 'phase': phase, 'cell': current, 'error_type': type(error).__name__, 'error': str(error)}); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--authorization', required=True)
    parser.add_argument('--authorization-sha256', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--execute-reviewed', action='store_true'); args = parser.parse_args()
    require(args.execute_reviewed, 'explicit_review_required'); run(args.authorization, args.authorization_sha256, args.output)


if __name__ == '__main__': main()
