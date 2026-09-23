#!/usr/bin/env python3
"""Bounded post-outcome CPU description. No provider, projector, model or simulator."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gc
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import torch

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
A = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
HEAD = '525506ca3198f54d86dadf84bbb76eb64926d87a'
AUTH_SHA = '5301e7ee421148b5cf0dd470c0f24b1a3977ec5d2146e52050ab717cea7d2b0b'
IDS = (
    'rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_c0_20260923__3cc1e46f83d0',
    'rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_q0_recovery1_20260923__28dd3c7a9e74',
    'rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_n2_20260923__45c5f8694f85',
)
STAGE_KEYS = ('episode_id', 'task_id', 'episode_seed', 'global_step', 'chunk_id',
    'trigger_reason', 'stage_before', 'stage_after', 'guidance_before', 'guidance_after',
    'query_status', 'query_ok', 'skipped_reason', 'vlm_query_count', 'vlm_query_limit',
    'parsed_stage', 'parsed_guidance', 'gripper_value_used', 'previous_gripper_value',
    'first_gripper_value', 'last_gripper_value')
UNKNOWN = {
    'target_aware_quantities': 'Unknown: initial authorization supplies no target map',
    'selected_projection_diagnostics': 'Not evaluated: optional analysis omitted; no projection recomputed',
    'actual_normalized_stage_input': 'Unknown: not independently recorded',
    'contemporaneous_object_pose_contact_grasp': 'Unknown: not in this collector',
    'keypoint_attachment_and_fallback': 'Unknown: tracker registry and fallback flag not recorded',
    'unique_archive_insertion_ancestry': 'Unknown: content identity is not occurrence ancestry',
    'projector_call_count': 'Unknown: no production counter',
    'unexecuted_candidate_and_stage_outcomes': 'Unknown: no real counterfactual',
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plain(value):
    if torch.is_tensor(value):
        require(value.device.type == 'cpu' and bool(torch.isfinite(value).all()), 'nonfinite_or_nonCPU_tensor')
        return value.tolist()
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def tensor_record(value):
    return None if value is None else {'dtype': str(value.dtype), 'shape': list(value.shape), 'value': plain(value)}


def native_key(value):
    require(torch.is_tensor(value) and value.device.type == 'cpu', 'native_identity_requires_cpu_tensor')
    return (str(value.dtype), tuple(value.shape), sha(value.contiguous().view(torch.uint8).numpy().tobytes()))


def distance(a, b):
    require(len(a) == len(b), 'vector_shape_mismatch')
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def one(rows, event):
    found = [r for r in rows if r['event'] == event]
    require(len(found) == 1, 'missing_or_duplicate_' + event)
    return found[0]


def provider_signature(providers):
    # Wrapper bytes are retained, but wrapper-only variation is not a new semantic provider.
    names = ('ordinal', 'original_code_sha256', 'source_text_sha256', 'source_path')
    return [{k: p.get(k) for k in names} for p in providers]


def selected_quality(rows, guided):
    if not guided:
        return {'status': 'Unknown', 'reason': 'unguided_no_canonical_quality'}
    final = one(rows, 'final_selection')['values']
    selected = final['selected_latent'][0]
    key = native_key(selected)
    matches = []
    for score in (r for r in rows if r['event'] == 'scoring_inputs'):
        v = score['values']
        if not v['scoring_scope']['role'].startswith('canonical_'):
            continue
        indices = [i for i, x in enumerate(v['samples']) if native_key(x) == key]
        if not indices:
            continue
        related = [r for r in rows if r['values'].get('scoring_batch_id') == score['sequence']]
        effective = one(related, 'effective_quality')['values']
        aggregate = one(related, 'scoring_aggregate')['values']['aggregate_before_reward_mode']
        for i in indices:
            matches.append({'scoring_sequence': score['sequence'], 'candidate_index': i,
                'scope': v['scoring_scope'], 'raw': float(aggregate[i]),
                'raw_dtype': str(aggregate.dtype), 'internal': float(effective['quality'][i]),
                'internal_dtype': str(effective['quality'].dtype),
                'mode': effective.get('quality_mode', 'provider'), 'reward_mode': effective['reward_mode']})
    if not matches:
        return {'status': 'Unknown', 'reason': 'no_native_selected_canonical_match'}
    values = {(m['raw'], m['raw_dtype'], m['internal'], m['internal_dtype'], m['mode'], m['reward_mode']) for m in matches}
    if len(values) != 1:
        return {'status': 'Unknown', 'reason': 'duplicate_native_content_quality_ambiguous', 'matches': matches}
    first = matches[0]
    require(first['internal'] == final['selected_quality'], 'selected_internal_quality_mismatch')
    if 'selected_raw_provider_quality' in final:
        require(first['raw'] == final['selected_raw_provider_quality'], 'selected_raw_quality_mismatch')
    return {'status': 'known', 'selected_native_dtype': key[0], 'selected_native_shape': list(key[1]),
        'selected_native_sha256': key[2], 'selected_canonical_fingerprint': final['selected_canonical_fingerprint'],
        'selected_index': final['selected_index'], 'selected_raw_provider_quality': first['raw'],
        'selected_internal_quality': first['internal'], 'raw_source_dtype': first['raw_dtype'],
        'internal_source_dtype': first['internal_dtype'], 'quality_mode': first['mode'],
        'reward_mode': first['reward_mode'], 'selection_rule': final['selection_rule'],
        'canonical_matching_occurrences': matches,
        'association_scope': 'equal native content with consistent quality; no unique insertion ancestry'}


def actual_steps(rows):
    result = []
    dispatches = [r for r in rows if r['event'] == 'action_dispatch']
    for j, dispatch in enumerate(dispatches):
        end = dispatches[j+1]['sequence'] if j+1 < len(dispatches) else math.inf
        window = [r for r in rows if dispatch['sequence'] < r['sequence'] < end]
        sent, outcome, returned = [one(window, name) for name in ('executed_action', 'pre_reset_outcome', 'step_returned')]
        require(outcome['reset_sequence'] == dispatch['reset_sequence'], 'pre_reset_observation_crossed_boundary')
        require(outcome['sequence'] < returned['sequence'], 'observation_after_return')
        obs, value = outcome['values']['observation'], outcome['values']
        result.append({'decision_id': dispatch['decision_id'], 'global_step': dispatch['global_step'],
            'reset_sequence': dispatch['reset_sequence'], 'execution_index': dispatch['values']['execution_index'],
            'command': tensor_record(sent['values']['action_numpy']),
            'eef': tensor_record(obs['robot0_eef_pos']), 'eef_quaternion': tensor_record(obs.get('robot0_eef_quat')),
            'gripper_qpos': tensor_record(obs.get('robot0_gripper_qpos')),
            'gripper_qvel': tensor_record(obs.get('robot0_gripper_qvel')),
            'reward': plain(value['reward']), 'terminated': value['terminated'], 'success': value['success'],
            'truncated': returned['values']['truncated'], 'observation_sequence': outcome['sequence'],
            'observation_origin': value['origin'], 'returned_reset_sequence': returned['reset_sequence']})
    require([r['execution_index'] for r in result] == list(range(1, len(result)+1)), 'prefix_gap')
    return result


def sign_runs(steps):
    runs = []
    for row in steps:
        command = row['command']['value'][6]
        sign = (command > 0) - (command < 0)
        if runs and runs[-1]['sign'] == sign and runs[-1]['last_step'] + 1 == row['global_step'] and runs[-1]['reset_sequence'] == row['reset_sequence']:
            runs[-1]['last_step'] = row['global_step']; runs[-1]['count'] += 1
        else:
            runs.append({'sign': sign, 'first_step': row['global_step'], 'last_step': row['global_step'],
                         'count': 1, 'reset_sequence': row['reset_sequence']})
    return runs


def motion_summary(steps, previous=None):
    require(bool(steps), 'empty_motion_segment')
    connected_previous = previous is not None and previous['global_step']+1 == steps[0]['global_step'] and previous['reset_sequence'] == steps[0]['reset_sequence'] and not previous['terminated'] and not previous['truncated']
    points = ([previous] if connected_previous else []) + steps
    edges = [(a, b) for a, b in zip(points, points[1:]) if b['global_step'] == a['global_step']+1 and a['reset_sequence'] == b['reset_sequence'] and not a['terminated'] and not a['truncated']]
    contiguous = len(edges) == len(points)-1
    qpos = [r['gripper_qpos']['value'] for r in steps if r['gripper_qpos'] is not None]
    qshape = bool(qpos) and len(qpos) == len(steps) and all(len(q) == len(qpos[0]) for q in qpos)
    signs = sign_runs(steps)
    changes = sum(a['sign'] != b['sign'] and a['last_step']+1 == b['first_step'] and a['reset_sequence'] == b['reset_sequence'] for a, b in zip(signs, signs[1:]))
    return {'observed_steps': len(steps), 'first_step': steps[0]['global_step'], 'last_step': steps[-1]['global_step'],
        'motion_origin': 'preceding_contiguous_post_action_observation' if connected_previous else 'first_post_action_observation_initial_origin_missing',
        'origin_step': points[0]['global_step'], 'eef_start': points[0]['eef']['value'], 'eef_end': points[-1]['eef']['value'],
        'eef_net_displacement_m': distance(points[0]['eef']['value'], points[-1]['eef']['value']) if contiguous else None,
        'eef_path_length_m': sum(distance(a['eef']['value'], b['eef']['value']) for a, b in edges),
        'contiguous_observed_edges': len(edges), 'all_points_contiguous': contiguous,
        'command_sign_runs': signs, 'command_sign_changes': changes,
        'gripper_qpos_start': qpos[0] if qshape else None, 'gripper_qpos_end': qpos[-1] if qshape else None,
        'gripper_qpos_min': [min(q[i] for q in qpos) for i in range(len(qpos[0]))] if qshape else None,
        'gripper_qpos_max': [max(q[i] for q in qpos) for i in range(len(qpos[0]))] if qshape else None}


def keypoint_link(previous, current):
    base = {'status': 'Unknown', 'reason': 'first_decision_or_incompatible_shape_reset_contiguity',
            'attachment_continuity': 'Unknown: registry/fallback not recorded'}
    if previous is None or previous['reset_sequence'] != current['reset_sequence'] or previous['last_executed_step']+1 != current['global_step']:
        return base
    a, b = previous['keypoints'], current['keypoints']
    if a is None or b is None or a['shape'] != b['shape'] or len(a['shape']) != 2 or a['shape'][1] != 3:
        return base
    return {'status': 'recorded_same_index_only', 'previous_decision_id': previous['decision_id'],
        'displacement_m': [distance(x, y) for x, y in zip(a['value'], b['value'])],
        'attachment_continuity': 'Unknown: same index in episode is not proof of persistent attachment or nonfallback',
        'real_object_motion': 'Unknown'}


def summarize_decisions(decisions, steps, stage_events):
    runs = []
    for d in decisions:
        signature = (d['stage'], d['use_guidance'], json.dumps(provider_signature(d['providers']), sort_keys=True), d['reset_sequence'])
        contiguous = bool(runs) and runs[-1]['last_step']+1 == d['global_step']
        if runs and runs[-1]['_signature'] == signature and contiguous:
            runs[-1]['decision_ids'].append(d['decision_id']); runs[-1]['last_step'] = d['last_executed_step']
        else:
            runs.append({'_signature': signature, 'stage': d['stage'], 'use_guidance': d['use_guidance'],
                'provider_signature': provider_signature(d['providers']), 'reset_sequence': d['reset_sequence'],
                'first_step': d['global_step'], 'last_step': d['last_executed_step'], 'decision_ids': [d['decision_id']]})
    by_step = {s['global_step']: s for s in steps}
    for run in runs:
        del run['_signature']
        segment = [s for s in steps if run['first_step'] <= s['global_step'] <= run['last_step']]
        run['motion'] = motion_summary(segment, by_step.get(run['first_step']-1))
        run['chunk_count'] = len(run['decision_ids'])
    transitions = []
    for a, b in zip(decisions, decisions[1:]):
        if (a['stage'], a['use_guidance']) != (b['stage'], b['use_guidance']):
            same_step = [e for e in stage_events if e.get('global_step') == b['global_step']]
            agreeing = [e for e in same_step if e.get('stage_after') == b['stage'] and e.get('guidance_after') == b['use_guidance']]
            transitions.append({'global_step': b['global_step'], 'stage_before': a['stage'], 'stage_after': b['stage'],
                'guidance_before': a['use_guidance'], 'guidance_after': b['use_guidance'],
                'same_step_events': same_step,
                'association': 'recorded_same_step_stage_state_agrees' if len(agreeing) == 1 else 'Unknown: no unique agreeing Stage event'})
    off = [r['global_step'] for r in transitions if r['guidance_before'] and not r['guidance_after']]
    on = [r['global_step'] for r in transitions if not r['guidance_before'] and r['guidance_after']]
    guided = [d for d in decisions if d['use_guidance']]
    return {'state_runs': runs, 'stage_guidance_transitions': transitions,
        'first_on_to_off_step': off[0] if off else None, 'all_on_to_off_steps': off,
        'all_off_to_on_steps': on, 'last_guided_decision_step': guided[-1]['global_step'] if guided else None,
        'last_guided_executed_step': guided[-1]['last_executed_step'] if guided else None,
        'terminal_step': steps[-1]['global_step'], 'episode_motion': motion_summary(steps),
        'query_status_counts': dict(Counter(str(e.get('query_status')) for e in stage_events)),
        'trigger_counts': dict(Counter(str(e.get('trigger_reason')) for e in stage_events))}


def xjson(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2, allow_nan=False); f.write('\n')


def run(args):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'explicit_empty_CUDA_mask_required')
    require(not torch.cuda.is_initialized(), 'CUDA_already_initialized')
    hashes = {}
    def read(path, expected=None):
        path = Path(path)
        require(not path.is_symlink(), 'symlink_input')
        data = path.read_bytes(); digest = sha(data)
        require(expected is None or digest == expected, 'input_sha_mismatch:' + str(path))
        hashes[str(path)] = digest
        return data
    auth = json.loads(read(args.authorization, AUTH_SHA))
    protocol = read(auth['protocol']['path'], auth['protocol']['sha256'])
    schema = json.loads(read(auth['source_schema']['path'], auth['source_schema']['sha256']))
    freeze = json.loads(read(args.freeze))
    require(freeze['status'] == 'CPU_TESTED_FROZEN_BEFORE_SCIENTIFIC_READ', 'unfrozen_reader')
    require(sha(Path(__file__).read_bytes()) == freeze['reader_sha256'], 'reader_changed_after_freeze')
    require(subprocess.check_output(['git','rev-parse','HEAD'], cwd=W, text=True).strip() == HEAD == auth['frozen_dev_source_commit'], 'source_HEAD_mismatch')
    for rel, binding in schema['sources'].items():
        read(W/rel, binding['sha256'])
    for binding in freeze['files']:
        read(binding['path'], binding['sha256'])
    require(len(auth['attempts']) == 3, 'authorized_attempt_count')
    require([Path(row['terminal']['path']).parent.name for row in auth['attempts']] == list(IDS), 'exact_attempt_id_mismatch')
    out = args.output
    require(out.resolve().is_relative_to(A/'continuation_20260923/n2-dev-v1/explanatory-read-v1'), 'output_outside_isolated_directory')
    out.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location('frozen_current_auditor', W/'scripts/audit_decision_evidence.py')
    auditor = importlib.util.module_from_spec(spec); spec.loader.exec_module(auditor)
    results, provenance = [], []
    for arm, allowed in zip(('C0', 'Q0', 'N2'), auth['attempts']):
        base = Path(allowed['terminal']['path']).parent
        require(base == A/'attempts'/IDS[len(results)], 'attempt_root_mismatch')
        inputs = {kind: read(ref['path'], ref['sha256']) for kind, ref in allowed.items()}
        terminal, prior = json.loads(inputs['terminal']), json.loads(inputs['audit'])
        compute_rows = [json.loads(x) for x in inputs['compute'].splitlines() if x]
        require(len(compute_rows) == 1, 'multiple_episodes')
        compute = compute_rows[0]
        require(terminal['outcome_valid'] is True and terminal['source_commit'] == HEAD and compute['outcome'] == 'completed', 'terminal_not_admitted')
        require(terminal['identity']['profile'] == arm and terminal['identity']['task_id'] == 0 and terminal['identity']['env_seed'] == 1969522881 and terminal['identity']['policy_seed'] == 1969522881 and terminal['identity']['init_index'] == 0, 'terminal_identity_mismatch')
        require(compute['episode_id'] == 0 and compute['task_id'] == 0 and compute['episode_seed'] == 1969522881, 'compute_identity_mismatch')
        require(prior['accepted'] is True and prior['evidence_complete'] is True and not prior['errors'], 'original_audit_not_accepted')
        ed = base/'eds_eval'; ep = ed/'decision_evidence/episode_000'
        metadata = [json.loads(x) for x in read(ed/'episode_metadata.jsonl').splitlines() if x]
        require(metadata == [{'episode_id':0, 'episode_seed':1969522881, 'task_id':0}], 'episode_metadata_identity_mismatch')
        stages = [{k: value.get(k) for k in STAGE_KEYS} for value in (json.loads(x) for x in read(ed/'stage_events.jsonl').splitlines() if x)]
        require(all(e['task_id'] == 0 and e['episode_seed'] == 1969522881 and e['episode_id'] == 0 for e in stages), 'stage_identity_mismatch')
        metrics = [json.loads(x) for x in inputs['metrics'].splitlines() if x]
        status = json.loads(read(ep/'status.json'))
        require(status['complete'] is True and status['failed'] is False and status['pending_action'] is False, 'collector_not_complete')
        refs = [json.loads(x) for x in read(ep/'events.jsonl').splitlines() if x]
        for i, ref in enumerate(refs, 1):
            require(ref['bundle'] == f'bundle_{i:06d}.pt', 'unsafe_bundle_reference')
            read(ep/ref['bundle'], ref['sha256'])
        fresh = auditor.audit_episode(ep, ed/'episode_compute.jsonl')
        xjson(out/(arm.lower()+'-fresh-audit.json'), fresh)
        require(fresh['accepted'] is True and fresh['evidence_complete'] is True and not fresh['errors'], 'fresh_audit_rejected:' + arm)
        require(not torch.cuda.is_initialized(), 'CUDA_initialized_by_audit')
        # Process one decision at a time after complete fresh audit; retain no entire population tensors.
        decisions, steps, pending = [], [], []
        metric_by_step = {m['global_step']: m for m in metrics}
        def finish(rows):
            ctx = one(rows, 'decision_context'); value = ctx['values']
            observed = actual_steps(rows)
            require(bool(observed), 'decision_no_actual_steps')
            d = {'decision_id': ctx['decision_id'], 'global_step': ctx['global_step'], 'reset_sequence': ctx['reset_sequence'],
                'last_executed_step': observed[-1]['global_step'], 'executed_prefix_length': len(observed),
                'stage': value['stage'], 'previous_stage': value['previous_stage'], 'stage_changed': value['stage_changed'],
                'use_guidance': value['use_guidance'], 'providers': plain(value['providers']),
                'keypoints': tensor_record(value['keypoints']),
                'quality': selected_quality(rows, value['use_guidance'] and bool(value['providers'])),
                'target_aware_quantities': UNKNOWN['target_aware_quantities']}
            d['keypoint_link_from_previous'] = keypoint_link(decisions[-1] if decisions else None, d)
            m = metric_by_step.get(d['global_step'])
            d['recorded_metric_quality'] = None if m is None else {k:m.get(k) for k in ('selected_reward','qd_quality_mode','qd_quality_applicable','qd_quality_reason','qd_selected_raw_reward','qd_selected_raw_gap','qd_final_best_raw_reward')}
            if d['quality']['status'] == 'known' and m is not None:
                require(d['quality']['selected_internal_quality'] == m['selected_reward'], 'selected_metric_quality_mismatch')
            decisions.append(d); steps.extend(observed)
        for ref in refs:
            payload = torch.load(io.BytesIO(read(ep/ref['bundle'], ref['sha256'])), map_location='cpu', weights_only=True)
            for row in payload['events']:
                if pending and row['decision_id'] != pending[0]['decision_id']:
                    finish(pending); pending = []
                pending.append(row)
        if pending:
            finish(pending)
        require(len(decisions) == status['decisions'] and sum(d['use_guidance'] for d in decisions) == compute['guided_chunks'], 'decision_count_mismatch')
        require([s['global_step'] for s in steps] == list(range(len(steps))), 'episode_step_gap')
        summary = summarize_decisions(decisions, steps, stages)
        results.append({'arm': arm, 'attempt_id': terminal['attempt_id'], 'retry_of': terminal.get('retry_of'),
            'original_outcome': {'condition_valid': terminal['outcome_valid'], 'success': terminal['success'], 'task_failure': terminal['task_failure'], 'compute_outcome': compute['outcome']},
            'decisions': decisions, 'actual_steps': steps, 'stage_events': stages, 'summary': summary,
            'guided_chunks': compute['guided_chunks'], 'unguided_chunks': compute['unguided_chunks'], 'unknown': UNKNOWN})
        provenance.append({'arm': arm, 'root': str(base), 'fresh_audit_accepted': fresh['accepted'], 'bundle_count': len(refs),
            'source_commit': terminal['source_commit'], 'n2_frozen_identity': terminal['n2_frozen_identity'],
            'init_row_sha256': terminal['init_row_sha256'], 'plan_sha256': terminal['plan_sha256'],
            'runtime_manifest_sha256': terminal['runtime_manifest_sha256'],
            'metadata': metadata, 'compute': compute,
            'identity_limits': 'Same task/seed/init/cohort does not equate diverged closed-loop states'})
        del pending, payload; gc.collect()
        print(json.dumps({'completed_arm': arm, 'fresh_audit': True, 'decisions': len(decisions), 'actual_steps': len(steps)}), flush=True)
    require(all(p['n2_frozen_identity'] == provenance[0]['n2_frozen_identity'] and p['init_row_sha256'] == provenance[0]['init_row_sha256'] and p['runtime_manifest_sha256'] == provenance[0]['runtime_manifest_sha256'] for p in provenance), 'common_cohort_identity_mismatch')
    require(not torch.cuda.is_initialized(), 'CUDA_initialized')
    # Check every input again after analysis, without revising any input.
    require(all(sha(Path(p).read_bytes()) == digest for p, digest in hashes.items()), 'input_changed_during_analysis')
    xjson(out/'closed-loop-sequence.json', {'schema':'task0-closed-loop-descriptive-v1', 'post_outcome_exploratory':True, 'arms':results})
    xjson(out/'inputs-and-audit.json', {'schema':'task0-closed-loop-provenance-v1', 'source_commit':HEAD,
        'authorization_sha256':AUTH_SHA, 'reader_sha256':sha(Path(__file__).read_bytes()), 'freeze_sha256':sha(args.freeze.read_bytes()),
        'input_sha256':hashes, 'arms':provenance, 'target_map':None, 'unknown':UNKNOWN,
        'cuda_initialized_before':False, 'cuda_initialized_after':torch.cuda.is_initialized(),
        'source_model_provider_projector_simulator_calls':0,
        'read_scope':'Only exact three authorized accepted task0 roots; current CPU auditor; no invalid/other episodes or images/log prose'})
    with (out/'comparison.md').open('x') as f:
        f.write('# Task0 closed-loop descriptive comparison\n\nPost-outcome Dev exploration; no causal, grasp, performance, promotion or cohort-change claim. All target-aware quantities are Unknown; no target map was supplied. Optional projection diagnostics were not evaluated.\n\n')
        f.write('| Arm | Original success | Guided / unguided chunks | First ON→OFF step | All OFF→ON steps | Last guided action step |\n|---|---:|---:|---:|---|---:|\n')
        for arm in results:
            s=arm['summary']; f.write(f"| {arm['arm']} | {arm['original_outcome']['success']} | {arm['guided_chunks']} / {arm['unguided_chunks']} | {s['first_on_to_off_step']} | {s['all_off_to_on_steps']} | {s['last_guided_executed_step']} |\n")
        f.write('\nSteps are zero-based action indices; boundary step 24 is after 24 executed actions. Full output retains all Stage triggers/replies, actual decisions, commands, pre-reset EEF/gripper observations and decision keypoints. A same-step Stage reply association is recorded chronology, not proof of causal benefit/harm.\n')
        for arm in results:
            f.write(f"\n## {arm['arm']} actual state runs\n\n")
            for r in arm['summary']['state_runs']:
                m=r['motion']; f.write(f"- Steps {r['first_step']}–{r['last_step']}: Stage {r['stage']}, guidance {r['use_guidance']}, {r['chunk_count']} chunks. Observed EEF net {m['eef_net_displacement_m']} m; path {m['eef_path_length_m']} m across {m['contiguous_observed_edges']} edges; origin={m['motion_origin']}. Command sign changes {m['command_sign_changes']}; gripper qpos start/end {m['gripper_qpos_start']} / {m['gripper_qpos_end']}.\n")
        f.write('\nLimits: normalized Stage inputs were not logged; logged gripper_value_used can be the preceding chunk’s first command, not its last sent action or qpos. Keypoints are policy tracker outputs with unrecorded attachment/fallback status, not independently verified object or contact motion. Same seed/init does not create matched later states or unexecuted counterfactuals. First-step pre-action EEF origin is absent from this actual-only summary; no reset observation is substituted. Raw provider and internal quality remain separate; no new model/provider/projector call or fitted threshold was introduced.\n')
    print(json.dumps({'output':str(out), 'cuda_initialized':torch.cuda.is_initialized(), 'artifact_sha256':{p.name:sha(p.read_bytes()) for p in out.iterdir() if p.is_file()}}), flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization',type=Path,required=True)
    p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())


if __name__ == '__main__':
    main()
