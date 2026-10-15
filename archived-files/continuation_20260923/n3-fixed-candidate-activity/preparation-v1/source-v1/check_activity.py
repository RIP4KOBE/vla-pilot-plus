#!/usr/bin/env python3
"""Prospective conditional N3 activity on exact recorded Q0 final pools only."""
import argparse
import collections
import hashlib
import importlib.util
import io
import json
import marshal
import os
from pathlib import Path
import sys
import time
import types

ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
PROTOCOL_SHA = '05c83a8eb3801d4a4c4f41bee28c531505a7767aa56ba482399013068679b931'
REPORT_SHA = 'd376f98a0d0d23d7b73b0a20ab768594c63ed6a6abce9473e0e67d2247bc88ab'
TRACK_INDEX_SHA = 'd0ed98c7b8dfd4c3c1fd1a584368b5b33a3ff91383dc0e6beb90d04f941fada7'
TRACK_PROVENANCE_SHA = 'b76e99c0d1985a93ce285c84f0068a04519f09973388082f7aac7aeba3395ba6'
TRACK_STATUS_SHA = '263f930a951ba98a540255a7d2ff469b37d812c268493aa713d2a1010574d13e'
BINDING_SHA = '1fbe250181457e9f86bfe202341e26265eaff9f77e4ede1045721fba9590d749'
TRACK_READER_SHA = 'a33714747a47415c8a8d64ba3297a016550e95b6f54a174a1654875603deec26'
SOURCE = '525506ca3198f54d86dadf84bbb76eb64926d87a'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def xjson(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')


def provider_semantics(recorded, source_text, semantic):
    """No exec/provider call: full template AST and actual-loader filename binding."""
    if len(recorded) != 1 or recorded[0].get('ordinal') != 0:
        return None, 'requires_single_recorded_provider'
    p = recorded[0]
    if isinstance(source_text, dict):
        return None, source_text['unavailable_reason']
    if source_text is None:
        return None, 'Unknown_provider_source_unavailable'
    if digest(source_text.encode('utf-8')) != p.get('source_text_sha256'):
        return None, 'Unknown_provider_source_text_mismatch'
    try:
        _, name, index = semantic._template_index(source_text)
    except (ValueError, SyntaxError, TypeError):
        return None, 'unsupported_complete_provider_template'
    # Frozen loader has no future flags. Its exec(str) interns <string>.
    # This exact difference is documented by the prior loader identity audit.
    code = compile(source_text, sys.intern('<string>'), 'exec', flags=0,
                   dont_inherit=True, optimize=0)
    definitions = [c for c in code.co_consts if isinstance(c, types.CodeType) and c.co_name == name]
    if len(definitions) != 1 or digest(marshal.dumps(definitions[0])) != p.get('original_code_sha256'):
        return None, 'Unknown_provider_original_code_mismatch'
    return index, 'source_original_code_and_complete_template'


def ranking(slots, old, new, selected_index, st):
    """Native maxima and ordering, never use a selected tie to manufacture activity."""
    torch = st.cpu_torch()
    require(slots and len(slots) == len(old) == len(new), 'empty_or_mismatched_final_pool')
    require(type(selected_index) is int and 0 <= selected_index < len(slots), 'selected_slot_invalid')
    before, after = torch.stack(old), torch.stack(new)
    require(before.dtype == after.dtype and bool(torch.isfinite(before).all())
            and bool(torch.isfinite(after).all()), 'native_quality_dtype_or_finite_mismatch')
    require(before[selected_index] == before.max(), 'recorded_Q0_selection_not_raw_maximum')
    old_ties = torch.nonzero(before == before.max()).flatten().tolist()
    ties = torch.nonzero(after == after.max()).flatten().tolist()
    selected_native = slots[selected_index]['native_identity']
    changed = all(slots[i]['native_identity'] != selected_native for i in ties)
    witnesses = []
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            raw_order = int(before[i] > before[j]) - int(before[i] < before[j])
            internal_order = int(after[i] > after[j]) - int(after[i] < after[j])
            if raw_order != internal_order:
                witnesses.append({'slots': [i, j], 'raw_order': raw_order, 'internal_order': internal_order})
    return {'actual_selected_slot': selected_index,
            'actual_selected_native_identity': selected_native,
            'actual_selected_fingerprint': slots[selected_index]['fingerprint'],
            'all_native_raw_maximum_slots': old_ties, 'all_native_internal_maximum_slots': ties,
            'all_native_internal_maximum_identities': [slots[i]['native_identity'] for i in ties],
            'all_native_internal_maximum_fingerprints': [slots[i]['fingerprint'] for i in ties],
            'all_internal_maximum_raw_tradeoffs_from_selected': [float(before[i]) - float(before[selected_index]) for i in ties],
            'actual_selected_raw_quality': float(before[selected_index]),
            'actual_selected_internal_quality': float(after[selected_index]),
            'raw_maximum': float(before.max()), 'internal_maximum': float(after.max()),
            'native_storage_dtype': str(after.dtype), 'tie_robust_native_changed_choice': changed,
            'quality_dependent_ranking_witnesses': witnesses,
            'conditional_mathematical_activity': changed or bool(witnesses)}


def final_pool(rows, residual, target_index, st, quality):
    """Join ALL native-equal occurrences of each real final slot, then call helper."""
    torch = st.cpu_torch()
    final = st.one(rows, 'final_selection')['values']
    pool = st.tensor(final['population'])
    require(pool.ndim == 3 and tuple(pool.shape[1:]) == (64, 128) and len(pool) > 0, 'final_pool_shape')
    chosen = st.tensor(final['selected_latent'], (1, 64, 128))
    si = final['selected_index']
    require(type(si) is int and 0 <= si < len(pool) and st.same(pool[si], chosen[0]), 'selected_pool_identity')
    require(st.fingerprint(chosen[0]) == final['selected_canonical_fingerprint'], 'selected_fingerprint')
    lookup = {r['sequence']: r for r in rows}
    require(len(lookup) == len(rows), 'duplicate_sequence')
    native_key = lambda t: (str(t.dtype), tuple(t.shape), st.native_bytes(t))
    pool_keys = {native_key(sample) for sample in pool}
    occurrences = collections.defaultdict(list)
    for score in (r for r in rows if r['event'] == 'scoring_inputs'):
        v = score['values']
        if v['scoring_scope']['role'] not in st.CANONICAL:
            continue
        samples = st.tensor(v['samples'])
        # Scan sample identities only; no non-final candidate geometry/quality analysis.
        relevant = [i for i, sample in enumerate(samples) if native_key(sample) in pool_keys]
        if not relevant:
            continue
        matches = [r for r in rows if r['event'] == 'effective_quality'
                   and r['values']['scoring_batch_id'] == score['sequence']]
        eff = st.one(matches, 'effective_quality')
        ev = eff['values']
        require(ev['reward_mode'] == 'normal' and 'quality_mode' not in ev
                and score['sequence'] < eff['sequence'], 'not_original_Q0_quality')
        aggregate = st.one([r for r in rows if r['event'] == 'scoring_aggregate'
                           and r['values']['scoring_batch_id'] == score['sequence']], 'scoring_aggregate')
        require(score['sequence'] < aggregate['sequence'] < eff['sequence'], 'raw_aggregate_order')
        canonical = [r for r in rows if r['event'] == 'canonical_candidate_batch'
                     and r['values']['iter_idx'] == v['scoring_scope']['iter_idx']
                     and eff['sequence'] < r['sequence'] and st.same(r['values']['candidates'], samples)]
        require(len(canonical) == 1, 'canonical_batch_association')
        batch = canonical[0]
        for i in relevant:
            x = st.tensor(v['projected_xyz'][i], (9, 3)); kp = st.tensor(v['keypoints'])
            raw = st.tensor(ev['quality'][i]).reshape(())
            require(x.dtype == kp.dtype == raw.dtype == samples.dtype
                    and v['slice_kind'] == 'eds'
                    and st.same(v['provider_input_xyz'][i], x[1:8]), 'native_original_T7_contract')
            require(st.same(raw, aggregate['values']['aggregate_before_reward_mode'][i].reshape(()))
                    and st.same(raw, batch['values']['effective_quality'][i].reshape(())), 'raw_quality_association')
            pr = [r for r in rows if r['event'] == 'provider_return'
                  and r['values']['scoring_batch_id'] == score['sequence']
                  and r['values']['candidate_index'] == i]
            require(len(pr) == 1 and pr[0]['values']['provider_ordinal'] == 0
                    and pr[0]['values']['context_provider_ordinal'] == 0
                    and score['sequence'] < pr[0]['sequence'] < aggregate['sequence'], 'singleton_provider_return_association')
            returned = st.tensor(pr[0]['values']['result']).reshape(())
            require(st.same(returned.to(raw.dtype), raw), 'provider_return_native_storage_mismatch')
            origin_seq = v['projection_origin_sequences'][i]
            origin_event = lookup[origin_seq]
            require(origin_event['event'] == 'projection_origin' and origin_seq < score['sequence'], 'origin_association')
            origin = st.tensor(origin_event['values']['source_eef_position'], (3,))
            cast = st.tensor(origin_event['values']['cast_eef_start'], (3,))
            require(st.same(x[0], cast) and st.same(cast, origin.to(cast.dtype)), 'origin_cast_association')
            identity = {k: st.native_info(z) for k, z in {'projection': x, 'keypoints': kp,
                        'origin': origin, 'cast': cast, 'raw': raw.reshape(1), 'provider_return': returned.reshape(1)}.items()}
            occurrences[native_key(samples[i])].append(
                {'identity': identity, 'projection': x, 'keypoints': kp, 'raw': raw,
                 'provider_return_before_storage':float(returned),
                 'reference': {'score_sequence': score['sequence'], 'candidate_row': i,
                               'origin_sequence': origin_seq, 'provider_return_sequence': pr[0]['sequence'],
                               'canonical_sequence': batch['sequence'],
                               'occurrence_id': batch['values']['occurrence_ids'][i]}})
    slots, old, new = [], [], []
    for index, sample in enumerate(pool):
        matches = occurrences[native_key(sample)]
        if not matches:
            return {'status': 'Unknown', 'reason': 'final_slot_has_no_exact_native_canonical_occurrence', 'slot': index}
        source = matches[0]
        if any(m['identity'] != source['identity'] for m in matches):
            return {'status': 'Unknown', 'reason': 'native_equal_final_slot_has_conflicting_occurrences', 'slot': index,
                    'matching_occurrences': [m['reference'] for m in matches]}
        before = {k: st.native_info(source[k]) for k in ('projection', 'keypoints')}
        residual_before = st.native_info(residual)
        q = quality(source['projection'].unsqueeze(0), source['keypoints'],
                    target_index=target_index, residual_previous=residual)
        require(q.shape == (1,) and q.dtype == sample.dtype and q.device.type == 'cpu'
                and bool(torch.isfinite(q).all()), 'N3_helper_storage_contract')
        require(before == {k: st.native_info(source[k]) for k in before}
                and residual_before == st.native_info(residual), 'helper_mutated_input')
        old.append(source['raw']);new.append(q[0])
        slots.append({'slot': index, 'fingerprint': st.fingerprint(sample), 'native_identity': st.native_info(sample),
                      'matching_occurrences': [m['reference'] for m in matches],
                      'insertion_ancestry': 'Unknown', 'source_identity': source['identity'],
                      'provider_return_before_native_storage':source['provider_return_before_storage'],
                      'raw_quality': float(source['raw']), 'raw_quality_native': st.native_info(source['raw'].reshape(1)),
                      'internal_quality': float(q[0]), 'internal_quality_native': st.native_info(q)})
    require(float(old[si]) == final['selected_quality'], 'actual_selected_raw_quality_mismatch')
    return {'status': 'conditional_mathematical_check', 'slots': slots,
            **ranking(slots, old, new, si, st), 'historical_runtime_eligibility': 'Unknown_missing_tracker_validity_tokens',
            'counterfactual_new_search_or_task_outcome': 'Unknown'}


def check_decision(rows, derived, pair, previous, sources, st, semantic, quality):
    ctx = st.one(rows, 'decision_context')
    require(ctx['decision_id'] == derived['decision_id'] == pair['current_decision_id']
            and ctx['global_step'] == derived['global_step']
            and ctx['reset_sequence'] == derived['reset_sequence'], 'derived_decision_identity')
    cv = ctx['values']
    ids, known = st.providers(cv['providers'])
    require(ids == derived['providers'] and known == derived['provider_identity_known']
            and cv['stage'] == derived['stage'] and cv['use_guidance'] == derived['use_guidance'], 'derived_provider_or_stage_identity')
    base = {'decision_id': derived['decision_id'], 'global_step': derived['global_step'],
            'use_guidance': derived['use_guidance'], 'structural_disposition': pair.get('reason', pair['status']),
            'historical_runtime_eligibility': 'Unknown_missing_tracker_validity_tokens'}
    if pair['status'] != 'retrospective_predictive_check':
        return {**base, 'status': 'not_structurally_eligible', 'reason': pair['reason']}
    require(previous is not None and previous['decision_id'] == pair['previous_decision_id']
            and previous['m'] == 8 and not previous['ended'] and previous['use_guidance'] and derived['use_guidance']
            and previous['last_global_step'] + 1 == derived['global_step']
            and previous['reset_sequence'] == derived['reset_sequence']
            and type(previous['stage']) is int and previous['stage'] == derived['stage']
            and previous['provider_identity_known'] and known and previous['providers'] == ids,
            'eligible_pair_structure_contradiction')
    require(pair['previous_e_disp_8'] == previous['tracking'][-1]['e_disp'], 'past_residual_identity')
    target, reason = provider_semantics(cv['providers'], sources.get(ids[0].get('source_path')) if ids else None, semantic)
    if target is None:
        return {**base, 'status': 'Unknown', 'reason': reason}
    selected, error = st.selected(rows)
    require(error is None and selected is not None
            and st.native_info(selected['chosen']) == derived['selected_native']
            and st.native_info(selected['x']) == derived['projected']['native']
            and st.native_info(selected['origin']) == derived['projected']['origin_native'], 'approved_selected_native_join')
    residual = st.cpu_torch().tensor(pair['previous_e_disp_8'], dtype=st.cpu_torch().float64)
    st.tensor(residual, (3,))
    return {**base, 'past_decision_id': previous['decision_id'], 'past_residual': residual.tolist(),
            'past_selected_native': previous['selected_native'], 'target_index_from_template': target,
            'provider_source_identity': ids, 'semantic_binding': reason,
            **final_pool(rows, residual, target, st, quality)}


def stream(item, inputs, st):
    """Keep only recorded fields needed for joins; weights_only native CPU load."""
    keep = {'decision_context', 'projection_origin', 'scoring_inputs', 'provider_return',
            'scoring_aggregate', 'effective_quality', 'canonical_candidate_batch',
            'final_selection', 'policy_action_decode'}
    pending = []; sequence = 1
    for ref in item['index']:
        data = inputs.raw({'path': str(item['episode']/ref['bundle']), 'sha256': ref['sha256']})
        payload = st.cpu_torch().load(io.BytesIO(data), map_location='cpu', weights_only=True)
        rows = payload['events']
        require(payload['schema'] == 'qd-ed-decision-evidence-v1'
                and ref['events'] == [{k:r[k] for k in st.META} for r in rows], 'bundle_index_metadata')
        for row in rows:
            require(row['sequence'] == sequence and row['episode'] == 0, 'bundle_sequence')
            sequence += 1
            if row['event'] not in keep:
                continue
            if pending and row['decision_id'] != pending[0]['decision_id']:
                yield pending;pending = []
            if row['event'] in {'scoring_inputs', 'provider_return', 'scoring_aggregate', 'effective_quality'}:
                if row['values']['scoring_scope']['role'] not in st.CANONICAL:
                    continue
            pending.append(row)
    if pending:
        yield pending


def admit(manifest, inputs, st):
    """Exact Q0 ten and approved completed-chain membership before any decode."""
    require(manifest['schema'] == 'n3-recorded-final-pool-input-v1', 'manifest_schema')
    fixed = {'matrix_report': REPORT_SHA, 'tracking_index': TRACK_INDEX_SHA,
             'tracking_provenance': TRACK_PROVENANCE_SHA, 'tracking_status': TRACK_STATUS_SHA,
             'fresh_audit_bindings': BINDING_SHA}
    values = {}
    for key, h in fixed.items():
        require(manifest[key]['sha256'] == h, 'not_reviewed_'+key)
        values[key] = inputs.read(manifest[key])
    report, index, prov, status, binding = (values[k] for k in fixed)
    require(report['matrix'] == 'complete_valid_30' and index['complete'] is True
            and prov['complete'] is True and prov['source_commit'] == SOURCE and prov['cuda_initialized'] is False
            and status['complete'] is True and status['cells'] == 30, 'incomplete_approved_chain')
    bound = prov['input_hashes']; cell_index = {r['cell']:r for r in index['cells']}
    cells = [r for r in report['cells'] if r['identity']['profile'] == 'Q0']
    require([c['identity']['task_id'] for c in cells] == list(range(10)), 'exact_all_Q0_universe')
    certs = {r['attempt_id']:r for r in binding['cells']};out = [];provider_refs = {}
    for cell in cells:
        aid = cell['valid_attempt_id']; key = f"t{cell['identity']['task_id']:02d}-q0"
        ri = cell_index[key];cert = certs[aid]
        require(cell['status'] == 'complete_valid' and ri['attempt_id'] == aid and cert['cell'] == key
                and cert['accepted'] is True and cert['evidence_complete'] is True and cert['errors'] == [], 'representative_or_audit_binding')
        derived_ref = {'path':str(Path(manifest['tracking_index']['path']).parent/ri['path']), 'sha256':ri['sha256']}
        derived = inputs.read(derived_ref)
        require(derived['attempt_id'] == aid and derived['identity'] == cell['identity'], 'tracking_representative')
        for d in derived['decisions']:
            for p in d['providers']:
                if p.get('source_path') and p.get('source_text_sha256'):
                    require(p['source_path'] not in provider_refs or provider_refs[p['source_path']] == p['source_text_sha256'], 'provider_path_changed_source')
                    provider_refs[p['source_path']] = p['source_text_sha256']
        fresh = inputs.read(cert['fresh_audit'])
        require(fresh['accepted'] is True and fresh['evidence_complete'] is True and fresh['errors'] == []
                and fresh['episode_dir'] == cert['episode_dir'], 'fresh_audit_incomplete')
        ep = inputs.path(cert['episode_dir'])
        require(ep == ROOT/'attempts'/aid/'eds_eval/decision_evidence/episode_000', 'episode_path')
        for name in ('bundle_index','collector_status'):
            require(bound.get(cert[name]['path']) == cert[name]['sha256'], 'unbound_collector_input')
        records = inputs.read(cert['bundle_index'], lines=True);cs = inputs.read(cert['collector_status'])
        require(cs['complete'] is True and cs['failed'] is False and cs['pending_action'] is False
                and len(records) == cs['bundles'] == cert['bundle_hash_count'], 'collector_incomplete')
        require({p.name for p in ep.glob('bundle_*.pt')} == {r['bundle'] for r in records}, 'unindexed_bundle')
        for n, r in enumerate(records,1):
            require(r['bundle'] == f'bundle_{n:06d}.pt' and bound.get(str(ep/r['bundle'])) == r['sha256'], 'bundle_not_approved')
            inputs.raw({'path':str(ep/r['bundle']), 'sha256':r['sha256']})
        out.append({'cell':key, 'attempt_id':aid, 'identity':cell['identity'], 'episode':ep,
                    'index':records, 'derived':derived, 'tracking_reference':derived_ref})
    # Every observed source is listed prospectively, including unsupported providers.
    require({r['path']:r['sha256'] for r in manifest['provider_sources']} == provider_refs
            and len(manifest['provider_sources']) == len(provider_refs), 'provider_source_scope')
    sources = {}
    for ref in manifest['provider_sources']:
        try:
            sources[ref['path']] = inputs.raw(ref).decode('utf-8')
        except (FileNotFoundError, UnicodeDecodeError):
            sources[ref['path']] = {'unavailable_reason':'Unknown_provider_source_unavailable'}
        except ValueError as exc:
            if str(exc) != 'input_sha_mismatch':
                raise
            sources[ref['path']] = {'unavailable_reason':'Unknown_provider_source_text_mismatch'}
    return out, sources


def summary(decisions):
    done = [d for d in decisions if d['status'] == 'conditional_mathematical_check']
    return {'decisions':len(decisions), 'guided_decisions':sum(d['use_guidance'] for d in decisions),
            'status_counts':dict(collections.Counter(d['status'] for d in decisions)),
            'dispositions':dict(collections.Counter(d.get('reason',d['status']) for d in decisions)),
            'structurally_eligible':sum(d['structural_disposition']=='retrospective_predictive_check' for d in decisions),
            'conditional_checks':len(done), 'native_changed_choice':sum(d['tie_robust_native_changed_choice'] for d in done),
            'ranking_witness_decisions':sum(bool(d['quality_dependent_ranking_witnesses']) for d in done),
            'conditional_activity_gate':any(d['conditional_mathematical_activity'] for d in done),
            'historical_runtime_eligibility':'Unknown_missing_tracker_validity_tokens',
            'online_authorization':False, 'task_benefit':'Unknown'}


def run(auth_path, auth_sha, output):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'empty_CUDA_mask_required')
    require(sys.version_info[:3] == (3,12,12) and sys.flags.optimize == 0 and marshal.version == 4,
            'frozen_python_compile_contract')
    auth_data = Path(auth_path).read_bytes();require(digest(auth_data)==auth_sha,'authorization_sha')
    auth = json.loads(auth_data)
    require(auth['schema']=='n3-recorded-final-pool-authorization-v1' and auth['status']=='AUTHORIZED_CPU_READ'
            and auth['conditional_math_only'] is True, 'actual_read_not_authorized')
    freeze_ref = auth['freeze'];freeze_data=Path(freeze_ref['path']).read_bytes()
    require(digest(freeze_data)==freeze_ref['sha256'],'freeze_sha');freeze=json.loads(freeze_data)
    own = Path(__file__).resolve()
    require(freeze['local_files']['check_activity.py']==digest(own.read_bytes()),'script_freeze')
    for name,h in freeze['local_files'].items():
        require(Path(name).name==name and digest((own.parent/name).read_bytes())==h,'local_freeze_changed')
    dep=freeze['dependencies']
    require(dep['tracking_reader']['sha256']==TRACK_READER_SHA and dep['n3_protocol']['sha256']==PROTOCOL_SHA,'definition_changed')
    for ref in dep.values():
        require(digest(Path(ref['path']).read_bytes())==ref['sha256'],'dependency_changed')
    st=module('n3_frozen_tracking',dep['tracking_reader']['path']);inputs=st.Inputs(ROOT)
    manifest=inputs.read(auth['input_manifest'])
    out=inputs.path(output)
    require(out.is_relative_to(ROOT/'continuation_20260923/n3-fixed-candidate-activity'),'output_scope')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();phase='admission'
    try:
        admitted,sources=admit(manifest,inputs,st)
        require(st.cpu_torch().__version__ == freeze['cpu_environment']['torch_version'], 'frozen_CPU_torch_version')
        # Bind helper's sole local import, without importing policy/environment modules.
        semantic=module('core.qd_executed_quality',dep['semantic_helper']['path'])
        helper=module('n3_quality_helper',dep['quality_helper']['path'])
        index=[];all_decisions=[];phase='recorded_final_pool_check'
        for item in admitted:
            derived=item['derived'];ds=derived['decisions'];ps=derived['temporal_pairs'];rows_out=[]
            require(len(ds)==len(ps),'derived_pair_count');previous=None
            for n,rows in enumerate(stream(item,inputs,st)):
                require(n<len(ds),'extra_decision')
                rows_out.append(check_decision(rows,ds[n],ps[n],previous,sources,st,semantic,helper.executed_feedback_quality))
                previous=ds[n]
            require(len(rows_out)==len(ds),'missing_decision')
            result={'schema':'n3-recorded-final-pool-activity-v1','cell':item['cell'],'attempt_id':item['attempt_id'],
                    'identity':item['identity'],'tracking_reference':item['tracking_reference'],
                    'decisions':rows_out,'summary':summary(rows_out)}
            path=out/(item['cell']+'.json');xjson(path,result)
            index.append({'cell':item['cell'],'path':path.name,'sha256':digest(path.read_bytes()),'summary':result['summary']})
            all_decisions.extend(rows_out)
        phase='final_verification';inputs.finish()
        require(digest(Path(auth_path).read_bytes())==auth_sha
                and digest(Path(freeze_ref['path']).read_bytes())==freeze_ref['sha256'], 'authorization_or_freeze_changed')
        for name,h in freeze['local_files'].items():
            require(digest((own.parent/name).read_bytes())==h,'local_freeze_changed_during_read')
        for ref in dep.values():
            require(digest(Path(ref['path']).read_bytes())==ref['sha256'],'dependency_changed_during_read')
        require(not st.cpu_torch().cuda.is_initialized(),'CUDA_initialized')
        xjson(out/'index.json',{'complete':True,'cells':index,'summary':summary(all_decisions)})
        xjson(out/'provenance.json',{'complete':True,'authorization_sha256':auth_sha,'freeze':freeze_ref,
              'input_manifest':auth['input_manifest'],'input_hashes':inputs.hashes,'source_commit':SOURCE,
              'dependencies':dep,'cuda_initialized':False,'provider_model_projector_simulator_calls':0,
              'cpu_environment':freeze['cpu_environment'],
              'wall_seconds':time.monotonic()-started,'historical_runtime_eligibility':'Unknown_missing_tracker_validity_tokens'})
        xjson(out/'status.json',{'complete':True,'cells':10,'original_outcomes_changed':False})
    except Exception as exc:
        xjson(out/'status.json',{'complete':False,'phase':phase,'error_type':type(exc).__name__,
                               'error':str(exc),'original_outcomes_changed':False})
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization',required=True);p.add_argument('--authorization-sha256',required=True)
    p.add_argument('--output',required=True);p.add_argument('--execute-reviewed',action='store_true')
    args=p.parse_args();require(args.execute_reviewed,'explicit_review_required')
    run(args.authorization,args.authorization_sha256,args.output)
