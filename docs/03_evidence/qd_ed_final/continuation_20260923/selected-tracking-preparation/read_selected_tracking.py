#!/usr/bin/env python3
"""Explicitly authorized selected-only CPU tracking; no scorer or projector calls."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import time

HERE = Path(__file__).resolve().parent
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
SOURCE = '525506ca3198f54d86dadf84bbb76eb64926d87a'
REPORT_SHA = 'd376f98a0d0d23d7b73b0a20ab768594c63ed6a6abce9473e0e67d2247bc88ab'
CHRON_FREEZE_SHA = '19f3c4cd12c8306270f9f721e1ffc881a9e4aa79175db486e4fa3cbdad963a90'
CHRON_READER_SHA = 'b19331ff6861210056858d56da6dcbd2d6a24f06fc91e24dcc1beb0d4df18b3e'
AUDITOR_SHA = 'c5936a251bc8145093392136fc8b06779c499cb456953d1079fc4e26c68e1b95'
REUSE_BINDING_SHA = '1fbe250181457e9f86bfe202341e26265eaff9f77e4ede1045721fba9590d749'
COHORT = 'N2_EXECUTED_QUALITY_DEV_20260923'
IDENTITY = ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')
META = ('sequence', 'event', 'decision_id', 'global_step', 'reset_sequence')
KEEP = {'decision_context', 'projection_origin', 'scoring_inputs', 'final_selection',
        'policy_action_decode', 'decision_committed', 'action_dispatch', 'executed_action',
        'pre_reset_outcome', 'automatic_reset_boundary', 'step_returned'}
CANONICAL = {'canonical_initial', 'canonical_offspring', 'canonical_population',
             'canonical_memory_fresh', 'canonical_memory_adapted'}
SOURCE_FILES = {'main.py', 'core/rdt_policy_steer.py', 'core/env_adapters/libero_adapter.py',
                'core/rdt_libero_action_converter.py', 'core/decision_evidence.py',
                'scripts/audit_decision_evidence.py'}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def sha(data): return hashlib.sha256(data).hexdigest()


def parse(data):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate_json_key'); out[key] = value
        return out
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def xjson(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')


class Inputs:
    def __init__(self, root): self.root, self.hashes = Path(root).resolve(), {}

    def path(self, path):
        p = Path(path)
        require(p.is_absolute() and p == p.resolve() and p.is_relative_to(self.root), 'input_path_invalid')
        return p

    def raw(self, ref):
        require(set(ref) == {'path', 'sha256'} and isinstance(ref['sha256'], str)
                and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'reference_invalid')
        p = self.path(ref['path']); data = p.read_bytes()
        require(sha(data) == ref['sha256'], 'input_sha_mismatch')
        self.hashes[str(p)] = ref['sha256']; return data

    def read(self, ref, lines=False):
        data = self.raw(ref)
        return [parse(line) for line in data.splitlines() if line.strip()] if lines else parse(data)

    def finish(self):
        require(all(sha(Path(p).read_bytes()) == h for p, h in self.hashes.items()), 'input_changed')


def admit(manifest, inputs, source_refs):
    """Reuse exact-bound completed chronology audits; no tensor load or re-audit."""
    require(manifest['schema'] == 'selected-tracking-input-v1', 'manifest_schema')
    require(manifest['matrix_report']['sha256'] == REPORT_SHA, 'report_not_reviewed')
    report = inputs.read(manifest['matrix_report'])
    require(report['schema'] == 'qd-ed-n2-matrix-report-v1' and report['cohort_id'] == COHORT
            and report['matrix'] == 'complete_valid_30', 'matrix_not_complete')
    prov = inputs.read(manifest['chronology_provenance'])
    chron = inputs.read(manifest['chronology_index']); status = inputs.read(manifest['chronology_status'])
    require(manifest['fresh_audit_bindings']['sha256'] == REUSE_BINDING_SHA, 'reuse_binding_not_reviewed')
    binding = inputs.read(manifest['fresh_audit_bindings'])
    require(binding['schema'] == 'n2-dev-fresh-audit-provenance-bindings-v1' and binding['complete'] is True
            and binding['source_index'] == manifest['chronology_index']
            and binding['source_provenance'] == manifest['chronology_provenance']
            and binding['reader_status'] == manifest['chronology_status']
            and binding['auditor_source']['sha256'] == AUDITOR_SHA, 'reuse_binding_differs')
    chron_root = Path(manifest['chronology_index']['path']).parent
    require(Path(manifest['chronology_provenance']['path']) == chron_root/'inputs-and-audit.json'
            and Path(manifest['chronology_status']['path']) == chron_root/'status.json', 'chronology_roots_differ')
    require(prov['schema'] == 'n2-dev-chronology-provenance-v1' and prov['complete'] is True
            and prov['matrix_authority'] == manifest['matrix_report'] and prov['cuda_initialized'] is False
            and prov['new_quality_computation'] is False, 'chronology_provenance_invalid')
    require(status['complete'] is True and status['cells'] == 30 and status['original_task_outcomes_changed'] is False
            and chron['schema'] == 'n2-dev-closed-loop-chronology-v1' and chron['complete'] is True, 'chronology_incomplete')
    ca = inputs.read(manifest['chronology_authorization'])
    require(manifest['chronology_authorization']['sha256'] == prov['authorization_sha256']
            and ca['schema'] == 'n2-dev-chronology-read-authorization-v1'
            and ca['status'] == 'AUTHORIZED_CPU_READ' and ca['scope_reviewed'] is True
            and ca['freeze'] == prov['freeze'] and ca['matrix_report'] == manifest['matrix_report'], 'chronology_authorization_differs')
    require(prov['freeze']['sha256'] == CHRON_FREEZE_SHA, 'chronology_freeze_differs')
    cf = inputs.read(prov['freeze'])
    require(cf['local_files']['read_full_dev.py'] == CHRON_READER_SHA, 'chronology_reader_differs')
    require(prov['source_dependencies']['sources']['auditor']['sha256'] == AUDITOR_SHA, 'audit_source_differs')
    bound = prov['input_hashes']
    def recorded(ref, *, lines=False):
        require(bound.get(ref['path']) == ref['sha256'], 'not_bound_by_completed_chronology')
        return inputs.read(ref, lines)
    ci = recorded(ca['input_manifest'])
    require(ci['schema'] == 'n2-dev-chronology-input-v1' and ci['matrix_report'] == manifest['matrix_report'], 'chronology_input_differs')
    recorded(manifest['matrix_report'])
    base_ref = report['input_manifest']['base_plan']; base = recorded(base_ref)
    require(base['source_commit'] == SOURCE and base['n2_cohort']['cohort_id'] == COHORT, 'episode_source_differs')
    inventory = {r['path']: r['sha256'] for r in base['code_files']}
    require(len(inventory) == len(base['code_files']) and inventory.get('scripts/audit_decision_evidence.py') == AUDITOR_SHA, 'source_inventory_invalid')
    require(len(source_refs) == len(SOURCE_FILES) and {r['relative_path'] for r in source_refs} == SOURCE_FILES
            and all(inventory.get(r['relative_path']) == r['sha256'] for r in source_refs), 'interpreted_source_not_episode_inventory')
    originals = [r for r in base['episodes'] if not r.get('retry_of')]
    expected = [(t, arm) for t in range(10) for arm in ('C0', 'Q0', 'N2')]
    require([(r['task_id'], r['profile']) for r in originals] == expected
            and [(c['identity']['task_id'], c['identity']['profile']) for c in report['cells']] == expected, 'matrix_universe_differs')
    require(len(chron['cells']) == len(ci['cells']) == len(binding['cells']) == 30, 'not_exactly_30')
    by_id = lambda rows, key: {r[key]: r for r in rows}
    selected_ids = {c['valid_attempt_id'] for c in report['cells']}
    require(len(selected_ids) == 30 and None not in selected_ids, 'representatives_ambiguous')
    chron_by = by_id(chron['cells'], 'attempt_id'); extra_by = by_id(ci['cells'], 'attempt_id')
    audits_by = by_id(binding['cells'], 'attempt_id')
    require(set(chron_by) == set(extra_by) == set(audits_by) == selected_ids, 'representative_sets_differ')
    admitted = []
    for original, cell in zip(originals, report['cells']):
        aid = cell['valid_attempt_id']; c = chron_by[aid]; extra = extra_by[aid]
        require(cell['status'] == 'complete_valid' and c['identity'] == cell['identity']
                == {k: original[k] for k in IDENTITY}, 'cell_identity_differs')
        representatives = [a for a in cell['attempts'] if a['status'] == 'complete_valid']
        require(len(representatives) == 1 and representatives[0]['terminal']['attempt_id'] == aid, 'terminal_representative_differs')
        saved = representatives[0]; terminal = recorded(saved['references']['terminal'])
        require(all(terminal.get(k) == v for k, v in saved['terminal'].items()) and terminal['attempt_id'] == aid
                and terminal['event'] == 'valid' and terminal['outcome_valid'] is True
                and terminal['source_commit'] == SOURCE and terminal['identity'] == cell['identity']
                and terminal.get('retry_of') == c.get('retry_of'), 'terminal_identity_differs')
        root = inputs.path(terminal['output_dir']); ep = root/'eds_eval/decision_evidence/episode_000'
        require(root.parent == inputs.root/'attempts' and root.name == aid, 'attempt_root_differs')
        key = f"t{original['task_id']:02d}-{original['profile'].lower()}"
        require(c['cell'] == key and c['path'] == key+'.json', 'chronology_cell_label_differs')
        certificate = audits_by[aid]
        require(certificate['cell'] == key and certificate['episode_dir'] == str(ep)
                and certificate['accepted'] is True and certificate['evidence_complete'] is True and certificate['errors'] == []
                and certificate['derived_cell'] == {'path': str(chron_root/c['path']), 'sha256': c['sha256']}, 'cell_reuse_binding_differs')
        # Derived chronology scientific arrays are neither opened nor decoded.
        fresh_ref = certificate['fresh_audit']
        require(Path(fresh_ref['path']) == chron_root/(key+'-fresh-audit.json'), 'fresh_audit_path_differs')
        audit = inputs.read(fresh_ref)
        require(audit['schema'] == 'qd-ed-decision-evidence-audit-v1' and audit['accepted'] is True
                and audit['evidence_complete'] is True and audit['errors'] == []
                and audit['original_execution_outcome'] == 'completed'
                and audit['episode_dir'] == str(ep)
                and audit['episode_compute_file'] == str(root/'eds_eval/episode_compute.jsonl'), 'fresh_audit_not_complete_or_linked')
        for kind, path in (('status', ep/'status.json'), ('index', ep/'events.jsonl'),
                           ('metadata', root/'eds_eval/episode_metadata.jsonl')):
            require(Path(extra[kind]['path']) == path, 'collector_path_differs')
        st = recorded(extra['status']); index = recorded(extra['index'], lines=True)
        metadata = recorded(extra['metadata'], lines=True)
        compute_ref = saved['references']['compute']; compute = recorded(compute_ref, lines=True)
        require(Path(compute_ref['path']) == root/'eds_eval/episode_compute.jsonl', 'compute_path_differs')
        require(certificate['bundle_index'] == extra['index'] and certificate['collector_status'] == extra['status']
                and certificate['episode_compute'] == compute_ref, 'reuse_input_references_differ')
        ident = {'episode_id': 0, 'task_id': original['task_id'], 'episode_seed': original['env_seed']}
        require(metadata == [ident] and len(compute) == 1 and all(compute[0][k] == v for k, v in ident.items())
                and compute[0]['outcome'] == 'completed', 'compute_metadata_identity_differs')
        require(st['schema'] == 'qd-ed-decision-evidence-v1' and st['episode'] == 0
                and st['complete'] is True and st['failed'] is False and st['pending_action'] is False
                and len(index) == st['bundles'], 'collector_incomplete')
        require({p.name for p in ep.glob('bundle_*.pt')} == {r['bundle'] for r in index}, 'unindexed_bundle')
        require(certificate['bundle_hash_count'] == len(index) and certificate['bundle_hash_map'] == {
            'exact_parent_directory': str(ep), 'field': 'input_hashes', 'filename_pattern': 'bundle_*.pt',
            'provenance': manifest['chronology_provenance']}, 'bundle_map_binding_differs')
        bound_bundle_paths = {p for p in bound if Path(p).parent == ep and Path(p).match('bundle_*.pt')}
        require(bound_bundle_paths == {str(ep/r['bundle']) for r in index}, 'bound_bundle_set_differs')
        for number, ref in enumerate(index, 1):
            require(ref['bundle'] == f'bundle_{number:06d}.pt', 'bundle_index_invalid')
            br = {'path': str(ep/ref['bundle']), 'sha256': ref['sha256']}
            require(bound.get(br['path']) == br['sha256'], 'bundle_not_bound_by_fresh_chronology')
            inputs.raw(br)  # Every bundle in every cell verified before first decode.
        admitted.append({'attempt_id': aid, 'identity': cell['identity'], 'retry_of': terminal.get('retry_of'),
                         'ep': ep, 'index': index, 'status': st, 'compute': compute[0], 'cell': key})
    return admitted


def cpu_torch():
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'empty_CUDA_mask_required')
    import torch
    require(not torch.cuda.is_initialized(), 'CUDA_initialized')
    return torch


def native_bytes(t): return t.detach().cpu().contiguous().reshape(-1).view(cpu_torch().uint8).numpy().tobytes()


def tensor(t, shape=None):
    torch = cpu_torch()
    require(torch.is_tensor(t) and t.device.type == 'cpu' and t.is_floating_point()
            and bool(torch.isfinite(t).all()) and (shape is None or tuple(t.shape) == tuple(shape)), 'native_tensor_invalid')
    return t


def same(a, b): return a.dtype == b.dtype and a.shape == b.shape and native_bytes(a) == native_bytes(b)


def fingerprint(t):
    return sha(t.float().contiguous().numpy().astype('<f4', copy=False).tobytes())


def native_info(t):
    torch = cpu_torch(); tensor(t)
    up = torch.nextafter(t, torch.full_like(t, float('inf'))).double()-t.double()
    down = t.double()-torch.nextafter(t, torch.full_like(t, -float('inf'))).double()
    spacing = torch.maximum(up.abs(), down.abs())
    return {'shape': list(t.shape), 'dtype': str(t.dtype), 'native_sha256': sha(native_bytes(t)),
            'max_adjacent_spacing': float(spacing.max()) if bool(torch.isfinite(spacing).all()) else None}


def one(rows, kind):
    values = [r for r in rows if r['event'] == kind]
    require(len(values) == 1, 'missing_or_duplicate_'+kind); return values[0]


def providers(value):
    fields = ('ordinal', 'original_code_sha256', 'source_text_sha256', 'source_path')
    result = [{k: p.get(k) for k in fields} for p in value]
    known = bool(result) and [p['ordinal'] for p in result] == list(range(len(result)))
    known = known and all(isinstance(p[k], str) and re.fullmatch('[0-9a-f]{64}', p[k])
                          for p in result for k in ('original_code_sha256', 'source_text_sha256'))
    known = known and all(isinstance(p['source_path'], str) and bool(p['source_path']) for p in result)
    return result, bool(known)


def selected(rows):
    """Only selected-content rows are inspected beyond their matching bytes."""
    torch = cpu_torch(); final = one(rows, 'final_selection')['values']; decoded = one(rows, 'policy_action_decode')['values']
    chosen = tensor(final['selected_latent'], (1, 64, 128))
    raw = tensor(decoded['selected_latent'], (1, 64, 128))
    fp = fingerprint(chosen[0])
    require(fp == final['selected_canonical_fingerprint'] == decoded['selected_canonical_fingerprint'], 'selected_identity_mismatch')
    require(raw.dtype == torch.float32 and same(raw, chosen.float()), 'selected_decode_cast_mismatch')
    lookup = {r['sequence']: r for r in rows}; matches = []; native_mismatch = False
    for score in (r for r in rows if r['event'] == 'scoring_inputs'):
        v = score['values']
        if v['scoring_scope']['role'] not in CANONICAL: continue
        for index, sample in enumerate(v['samples']):
            if fingerprint(sample) != fp: continue
            if not same(sample, chosen[0]): native_mismatch = True; continue
            origins = v.get('projection_origin_sequences')
            if origins is None or index >= len(origins) or origins[index] not in lookup:
                return None, 'Unknown_selected_origin_missing'
            origin = lookup[origins[index]]
            require(origin['event'] == 'projection_origin' and origin['decision_id'] == score['decision_id']
                    and origin['sequence'] < score['sequence'], 'selected_origin_sequence_invalid')
            x = tensor(v['projected_xyz'][index], (9, 3)); o = tensor(origin['values']['source_eef_position'], (3,))
            cast = tensor(origin['values']['cast_eef_start'], (3,))
            require(same(cast, x[0]) and same(cast, o.to(cast.dtype)), 'selected_origin_cast_mismatch')
            matches.append({'x': x, 'origin': o, 'cast': cast, 'score_sequence': score['sequence'], 'row': index,
                            'origin_sequence': origin['sequence'], 'role': v['scoring_scope']['role']})
    if native_mismatch: return None, 'Unknown_canonical_fingerprint_native_identity_ambiguous'
    if not matches: return None, 'Unknown_no_selected_canonical_projection'
    first = matches[0]
    if any(not all(same(m[k], first[k]) for k in ('x', 'origin', 'cast')) for m in matches[1:]):
        return None, 'Unknown_selected_projection_or_origin_ambiguous'
    return {'x': first['x'], 'origin': first['origin'], 'cast': first['cast'], 'chosen': chosen[0],
            'occurrences': [{k: m[k] for k in ('score_sequence', 'row', 'origin_sequence', 'role')} for m in matches]}, None


def actions(rows):
    decoded = tensor(one(rows, 'policy_action_decode')['values']['action_chunk'], (1, 8, 7))
    committed = one(rows, 'decision_committed')['values']
    require(committed['execution_horizon'] == 8 and same(decoded, tensor(committed['action_chunk'], (1, 8, 7))), 'committed_action_mismatch')
    dispatches = [r for r in rows if r['event'] == 'action_dispatch']; out = []
    require(0 < len(dispatches) <= 8, 'actual_prefix_length_invalid')
    for index, d in enumerate(dispatches, 1):
        require(type(d['values']['execution_index']) is int and d['values']['execution_index'] == index, 'execution_index_gap')
        limit = dispatches[index]['sequence'] if index < len(dispatches) else math.inf
        window = [r for r in rows if d['sequence'] < r['sequence'] < limit]
        sent, obs, returned = (one(window, k) for k in ('executed_action', 'pre_reset_outcome', 'step_returned'))
        require(d['sequence'] < sent['sequence'] < obs['sequence'] < returned['sequence']
                and all(r['global_step'] == d['global_step'] and r['decision_id'] == d['decision_id'] for r in (sent, obs, returned))
                and sent['reset_sequence'] == obs['reset_sequence'] == d['reset_sequence'], 'actual_response_link_invalid')
        command = tensor(sent['values']['action_numpy'], (7,)); eef = tensor(obs['values']['observation']['robot0_eef_pos'], (3,))
        require(command.dtype == cpu_torch().float32, 'sent_dtype_invalid')
        ended = bool(obs['values']['terminated'] or returned['values']['truncated'])
        require(index == len(dispatches) or not ended, 'action_after_terminal')
        out.append({'i': index, 'global_step': d['global_step'], 'reset_sequence': d['reset_sequence'],
                    'command': command, 'eef': eef, 'ended': ended, 'outcome_sequence': obs['sequence'],
                    'sent_decode_delta': (command.double()-decoded[0, index-1].double()).tolist()})
    require([a['global_step'] for a in out] == list(range(out[0]['global_step'], out[0]['global_step']+len(out))), 'actual_step_gap')
    return decoded, out


def describe(rows, previous=None):
    torch = cpu_torch(); ctx = one(rows, 'decision_context'); v = ctx['values']
    ids, ids_known = providers(v['providers']); decoded, actual = actions(rows)
    require(actual[0]['global_step'] == ctx['global_step'] and actual[0]['reset_sequence'] == ctx['reset_sequence'], 'decision_action_origin_mismatch')
    d = {k: ctx[k] for k in ('decision_id', 'global_step', 'reset_sequence')}
    d.update(stage=v['stage'], use_guidance=v['use_guidance'], providers=ids, provider_identity_known=ids_known,
             m=len(actual), last_global_step=actual[-1]['global_step'], ended=actual[-1]['ended'],
             actual_prefix=[{'i': a['i'], 'global_step': a['global_step'], 'outcome_sequence': a['outcome_sequence'],
                             'eef': a['eef'].double().tolist(), 'eef_native': native_info(a['eef']),
                             'sent': a['command'].double().tolist(), 'sent_native': native_info(a['command']),
                             'sent_decode_delta': a['sent_decode_delta']} for a in actual])
    d['projected'] = None; d['tracking'] = None
    if not v['use_guidance']:
        d['tracking_status'] = 'Unknown_unguided_no_recorded_selected_projection'; return d
    selected_value, reason = selected(rows)
    if selected_value is None: d['tracking_status'] = reason; return d
    s = selected_value; x = s['x'].double(); origin = s['origin'].double(); cast = s['cast'].double()
    source_actions = s['chosen'][:8, [39, 40, 41, 42, 43, 44]].double()
    d['selected_decode_position_rotation_delta'] = (decoded[0, :, :6].double()-source_actions).tolist()
    d['selected_native'] = native_info(s['chosen'])
    d['projected'] = {'xyz': x.tolist(), 'native': native_info(s['x']), 'origin': origin.tolist(),
                      'origin_native': native_info(s['origin']), 'cast_native': native_info(s['cast']),
                      'origin_cast_delta': (origin-cast).tolist(), 'occurrences': s['occurrences'],
                      'original_insertion_ancestry': 'Unknown'}
    bridge_known = (previous is not None and previous['last_global_step']+1 == d['global_step']
                    and previous['reset_sequence'] == d['reset_sequence'] and not previous['ended'])
    d['projected']['origin_bridge'] = ((origin-torch.tensor(previous['actual_prefix'][-1]['eef'], dtype=torch.float64)).tolist()
                                      if bridge_known else None)
    tracking = []
    for a in actual:
        i = a['i']; p = a['eef'].double(); absolute = p-x[i]; disp = (p-origin)-(x[i]-x[0])
        p_before = origin if i == 1 else actual[i-2]['eef'].double()
        delta_error = (p-p_before)-(x[i]-x[i-1])
        tracking.append({'i': i, 'e_abs': absolute.tolist(), 'e_disp': disp.tolist(),
                         'abs_l2': float(absolute.norm()), 'disp_l2': float(disp.norm()),
                         'abs_sse': float(absolute.square().sum()), 'disp_sse': float(disp.square().sum()),
                         'step_vector_error': delta_error.tolist(),
                         'first_step_origin': 'controller_source_not_independent_preaction_observation' if i == 1 else 'preceding_post_action'})
    d['tracking'] = tracking; d['tracking_status'] = 'known_recorded_selected_prefix'
    d['summary'] = {'m': len(tracking), 'abs_mse': sum(a['abs_sse'] for a in tracking)/len(tracking),
                    'disp_mse': sum(a['disp_sse'] for a in tracking)/len(tracking),
                    'last_e_abs': tracking[-1]['e_abs'], 'last_e_disp': tracking[-1]['e_disp'],
                    'sent_decode_changed_steps': sum(any(v != 0 for v in a['sent_decode_delta']) for a in actual),
                    'sent_outside_declared_unit_bounds_components': sum(int((a['command'].abs()>1).sum()) for a in actual)}
    return d


def temporal_pair(previous, current):
    reason = None
    if previous is None: reason = 'no_previous_decision'
    elif not previous['use_guidance'] or not current['use_guidance']: reason = 'unguided_boundary'
    elif previous['reset_sequence'] != current['reset_sequence'] or previous['ended']: reason = 'reset_or_terminal_boundary'
    elif previous['last_global_step']+1 != current['global_step']: reason = 'noncontiguous_boundary'
    elif previous['m'] != 8: reason = 'previous_prefix_not_full_eight'
    elif type(previous['stage']) is not int or type(current['stage']) is not int or previous['stage'] != current['stage']: reason = 'stage_changed_or_unknown'
    elif not previous['provider_identity_known'] or not current['provider_identity_known']: reason = 'provider_identity_unknown'
    elif previous['providers'] != current['providers']: reason = 'provider_identity_changed'
    elif previous['tracking'] is None or current['tracking'] is None: reason = 'selected_tracking_unknown'
    out = {'previous_decision_id': previous['decision_id'] if previous else None, 'current_decision_id': current['decision_id']}
    if reason is not None: return {**out, 'status': 'Unknown_or_ineligible', 'reason': reason}
    r = previous['tracking'][-1]['e_disp']; comparisons = []
    for point in current['tracking']:
        i = point['i']; transported = [e-(i/8)*bias for e, bias in zip(point['e_disp'], r)]
        zero = point['disp_sse']; changed = sum(x*x for x in transported)
        comparisons.append({'i': i, 'zero_prediction_error': point['e_disp'], 'transported_error': transported,
                            'zero_sse': zero, 'transported_sse': changed, 'sse_difference': changed-zero})
    return {**out, 'status': 'retrospective_predictive_check', 'previous_e_disp_8': r, 'current_m': current['m'],
            'points': comparisons, 'zero_mse': sum(p['zero_sse'] for p in comparisons)/len(comparisons),
            'transported_mse': sum(p['transported_sse'] for p in comparisons)/len(comparisons),
            'effect_claim': 'none_observed_selected_paths_not_changed'}


def pruned(row):
    """Never access provider returns, keypoints, qualities or final-pool ranks."""
    kind = row['event']; v = row['values']
    if kind not in KEEP: return None
    if kind == 'scoring_inputs':
        if v['scoring_scope']['role'] not in CANONICAL: return None
        keys = ('samples', 'projected_xyz', 'projection_origin_sequences', 'scoring_scope')
    elif kind == 'decision_context': keys = ('stage', 'use_guidance', 'providers')
    elif kind == 'final_selection': keys = ('selected_latent', 'selected_canonical_fingerprint')
    elif kind == 'policy_action_decode': keys = ('selected_latent', 'selected_canonical_fingerprint', 'action_chunk')
    elif kind == 'pre_reset_outcome':
        return {**{k: row[k] for k in (*META, 'episode')}, 'values': {
            'observation': {'robot0_eef_pos': v['observation']['robot0_eef_pos']}, 'terminated': v['terminated']}}
    elif kind == 'step_returned': keys = ('terminated', 'truncated')
    else: return row
    return {**{k: row[k] for k in (*META, 'episode')}, 'values': {k: v[k] for k in keys}}


def stream_decisions(item, inputs):
    torch = cpu_torch(); pending = []; expected_sequence = 1
    for ref in item['index']:
        data = inputs.raw({'path': str(item['ep']/ref['bundle']), 'sha256': ref['sha256']})
        payload = torch.load(io.BytesIO(data), map_location='cpu', weights_only=True)
        require(payload['schema'] == 'qd-ed-decision-evidence-v1', 'bundle_schema')
        rows = payload['events']
        require(rows and ref['first_sequence'] == rows[0]['sequence'] and ref['last_sequence'] == rows[-1]['sequence']
                and ref['events'] == [{k: r[k] for k in META} for r in rows], 'bundle_index_metadata_differs')
        for row in rows:
            require(row['sequence'] == expected_sequence and row['episode'] == 0, 'bundle_sequence_or_episode_differs')
            expected_sequence += 1
            value = pruned(row)
            if value is None: continue
            if pending and value['decision_id'] != pending[0]['decision_id']:
                yield pending; pending = []
            pending.append(value)
        del rows, payload, data
    if pending: yield pending


def episode(item, inputs):
    decisions, pairs, previous = [], [], None
    for rows in stream_decisions(item, inputs):
        d = describe(rows, previous); pairs.append(temporal_pair(previous, d)); decisions.append(d); previous = d
    require(len(decisions) == item['status']['decisions'] and sum(d['use_guidance'] for d in decisions) == item['compute']['guided_chunks'], 'decision_count_differs')
    require([a['global_step'] for d in decisions for a in d['actual_prefix']] == list(range(sum(d['m'] for d in decisions))), 'episode_action_gap')
    per_step = []
    for i in range(1, 9):
        points = [p for d in decisions if d['tracking'] for p in d['tracking'] if p['i'] == i]
        per_step.append({'i': i, 'n': len(points),
            'e_abs_mean': [sum(p['e_abs'][axis] for p in points)/len(points) for axis in range(3)] if points else None,
            'e_disp_mean': [sum(p['e_disp'][axis] for p in points)/len(points) for axis in range(3)] if points else None,
            'abs_l2_values': [p['abs_l2'] for p in points], 'disp_l2_values': [p['disp_l2'] for p in points]})
    return {'schema': 'selected-tracking-episode-v1', 'attempt_id': item['attempt_id'], 'identity': item['identity'],
            'retry_of': item['retry_of'], 'decisions': decisions, 'temporal_pairs': pairs,
            'summary': {'decisions': len(decisions), 'guided': sum(d['use_guidance'] for d in decisions),
                        'observed_actions': sum(d['m'] for d in decisions),
                        'tracking_status_counts': dict(Counter(d['tracking_status'] for d in decisions)),
                        'pair_status_counts': dict(Counter(p.get('reason', p['status']) for p in pairs)), 'by_step': per_step},
            'unknown': ['cause', 'contact_grasp', 'target_progress', 'controller_internal_clipping_scaling',
                        'counterfactual_candidate_outcomes', 'deployment_effect', 'independent_chunk_significance']}


def run(auth_path, auth_sha, output):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'empty_CUDA_mask_required')
    inputs = Inputs(ROOT); auth = inputs.read({'path': str(Path(auth_path).resolve()), 'sha256': auth_sha})
    require(auth['schema'] == 'selected-tracking-authorization-v1' and auth['status'] == 'AUTHORIZED_CPU_SELECTED_TRACKING'
            and auth['retrospective_transport_approved'] is True and auth['source_commit'] == SOURCE, 'read_not_authorized')
    freeze = inputs.read(auth['freeze'])
    require(freeze['status'] == 'CPU_TESTED_FROZEN_NO_ACTUAL_READ' and freeze['actual_read_authorized'] is False, 'freeze_invalid')
    required = {'read_selected_tracking.py', 'test_selected_tracking.py', 'protocol-v1.md', 'input-schema-v1.json', 'source-review-v1.json'}
    require(required <= set(freeze['local_files']), 'freeze_inventory_missing')
    for name, h in freeze['local_files'].items():
        require(Path(name).name == name and sha((HERE/name).read_bytes()) == h, 'definition_changed')
    source_review = parse((HERE/'source-review-v1.json').read_bytes())
    require(source_review['source_commit'] == SOURCE, 'interpreted_source_commit_differs')
    source_refs = source_review['source_files']
    require(all(sha(Path(r['path']).read_bytes()) == r['sha256'] for r in source_refs), 'frozen_source_changed')
    manifest = inputs.read(auth['input_manifest']); out = inputs.path(output)
    require(out.is_relative_to(inputs.root/'continuation_20260923/selected-tracking-analysis'), 'output_scope_invalid')
    out.mkdir(parents=True, exist_ok=False); phase = 'all30_admission'; cell = None; start = time.monotonic()
    try:
        admitted = admit(manifest, inputs, source_refs); torch = cpu_torch(); index = []
        for item in admitted:
            phase = 'selected_extraction'; cell = item['cell']; result = episode(item, inputs)
            name = cell+'.json'; xjson(out/name, result)
            index.append({'cell': cell, 'attempt_id': item['attempt_id'], 'path': name,
                          'sha256': sha((out/name).read_bytes()), 'summary': result['summary']})
        phase = 'final_verification'; cell = None; inputs.finish()
        require(not torch.cuda.is_initialized(), 'CUDA_initialized')
        require(all(sha((HERE/name).read_bytes()) == h for name, h in freeze['local_files'].items()), 'definition_changed')
        require(all(sha(Path(r['path']).read_bytes()) == r['sha256'] for r in source_refs), 'frozen_source_changed')
        xjson(out/'inputs-and-source-hashes.json', {'complete': True, 'input_hashes': inputs.hashes,
            'authorization_sha256': auth_sha, 'source_commit': SOURCE, 'freeze': auth['freeze'],
            'fresh_audits_reused': 30, 'audit_invocations': 0, 'cuda_initialized': False,
            'wall_seconds': time.monotonic()-start, 'scientific_scope': 'selected_recorded_geometry_only_no_fit_no_counterfactual'})
        xjson(out/'index.json', {'schema': 'selected-tracking-index-v1', 'complete': True, 'cells': index})
        xjson(out/'status.json', {'complete': True, 'cells': 30, 'original_outcomes_changed': False})
    except BaseException as error:
        xjson(out/'status.json', {'complete': False, 'phase': phase, 'cell': cell, 'error_type': type(error).__name__,
            'error_code': str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Za-z0-9_]+', str(error)) else None,
            'original_outcomes_changed': False})
        raise
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization', type=Path, required=True); p.add_argument('--authorization-sha256', required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--execute-reviewed', action='store_true')
    args = p.parse_args(); require(args.execute_reviewed, 'explicit_reviewed_execution_required')
    print(run(args.authorization, args.authorization_sha256, args.output))
