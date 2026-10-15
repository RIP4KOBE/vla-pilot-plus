#!/usr/bin/env python3
"""Explicitly authorized CPU chronology; matrix outcomes/costs remain authoritative."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import time

HERE = Path(__file__).resolve().parent
ARTIFACT_ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
SOURCE_COMMIT = '525506ca3198f54d86dadf84bbb76eb64926d87a'
BASE_PLAN_SHA = 'ec037ec84555bd46d3b776f29979545d21b21c1f3671c3bd32b07e933d5cdc45'
MATRIX_SHA = '8299647ed0ec904e230058a96a8d0b2d2714e2a3879341ea6917416093c3dfe2'
HELPER_SHA = '1212c3c9675403dc0e8f3b97948ab8d6d9a5f873ccfa615564041da3fe5c309f'
COHORT = 'N2_EXECUTED_QUALITY_DEV_20260923'
IDENTITY = ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')
BINDING = ('source_commit', 'profiles_sha256', 'runtime_manifest_sha256', 'runtime_inventory_sha256', 'seed_plan_sha256')
KEEP = {'decision_context', 'action_dispatch', 'executed_action', 'pre_reset_outcome', 'automatic_reset_boundary', 'step_returned'}
UNKNOWN = {'normalized_stage_input': 'not_recorded', 'physical_grasp_contact_release': 'not_observed',
           'target_progress': 'not_evaluated_no_target_map', 'counterfactual_outcome': 'not_observed',
           'keypoint_attachment_fallback': 'not_evaluated', 'stage_reply_correctness': 'not_established'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse(data):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def xjson(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


class Inputs:
    def __init__(self, root):
        self.root, self.hashes, self.absent = Path(root).resolve(), {}, []

    def path(self, path):
        p = Path(path)
        require(p.is_absolute() and p.resolve().is_relative_to(self.root), 'input_outside_owned_root')
        require(p == p.resolve(), 'symlink_or_noncanonical_input')
        return p

    def read(self, ref, *, lines=False):
        require(set(ref) == {'path', 'sha256'} and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'invalid_reference')
        p = self.path(ref['path']); data = p.read_bytes()
        require(sha(data) == ref['sha256'], 'input_sha_mismatch')
        self.hashes[str(p)] = ref['sha256']
        return [parse(line) for line in data.splitlines() if line.strip()] if lines else parse(data)

    def finish(self):
        require(all(sha(Path(p).read_bytes()) == s for p, s in self.hashes.items()), 'input_changed')
        require(all(not p.exists() for p in self.absent), 'declared_absent_source_appeared')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def dependencies(path=HERE/'dependencies-v1.json'):
    manifest = parse(Path(path).read_bytes())
    require(manifest['schema'] == 'n2-dev-chronology-dependencies-v1', 'dependency_schema')
    for ref in manifest['sources'].values():
        require(sha(Path(ref['path']).read_bytes()) == ref['sha256'], 'dependency_sha_mismatch')
    refs = manifest['sources']
    require(refs['task0_helpers']['sha256'] == HELPER_SHA and refs['matrix_reporter']['sha256'] == MATRIX_SHA, 'frozen_dependency_differs')
    helper = module(refs['task0_helpers']['path'], 'frozen_task0_chronology_helpers')
    require(not helper.torch.cuda.is_initialized(), 'CUDA_initialized')
    auditor = module(refs['auditor']['path'], 'frozen_chronology_auditor')
    return helper, auditor, manifest


def source_identity(plan):
    files = {r['path']: r['sha256'] for r in plan['code_files']}
    require(len(files) == len(plan['code_files']), 'duplicate_source_path')
    return {'source_commit': plan['source_commit'], 'code_files': files}


def admit(manifest, inputs, deps):
    """All30 identity/accepted-evidence checks happen before any bundle decoding."""
    require(manifest['schema'] == 'n2-dev-chronology-input-v1', 'input_schema')
    report = inputs.read(manifest['matrix_report'])
    require(report['schema'] == 'qd-ed-n2-matrix-report-v1' and report['cohort_id'] == COHORT and report['matrix'] == 'complete_valid_30', 'matrix_not_complete')
    authority = report['input_manifest']
    require(authority['script_sha256'] == MATRIX_SHA and authority['base_plan']['sha256'] == BASE_PLAN_SHA and authority['input_scope_complete'] is True, 'matrix_authority_differs')
    base = inputs.read(authority['base_plan'])
    require(base['source_commit'] == SOURCE_COMMIT and base['n2_cohort']['cohort_id'] == COHORT, 'Dev_source_or_cohort_differs')
    originals = [r for r in base['episodes'] if not r.get('retry_of')]
    expected = [(t, arm) for t in range(10) for arm in ('C0', 'Q0', 'N2')]
    require([(r['task_id'], r['profile']) for r in originals] == expected, 'original_matrix_differs')
    plans = {authority['base_plan']['sha256']: base}
    for ref in authority.get('plan_revisions', []):
        plan = inputs.read(ref)
        require(source_identity(plan) == source_identity(base) and all(plan[k] == base[k] for k in BINDING)
                and plan['candidate_profiles'] == base['candidate_profiles']
                and [r for r in plan['episodes'] if not r.get('retry_of')] == originals, 'revision_source_or_scientific_identity_differs')
        plans[ref['sha256']] = plan
    require(base['code_files'] and {r['path']: r['sha256'] for r in base['code_files']}.get('scripts/audit_decision_evidence.py') == deps['sources']['auditor']['sha256'], 'auditor_not_episode_source')
    cells = report['cells']
    require(len(cells) == 30 and [(c['identity']['task_id'], c['identity']['profile']) for c in cells] == expected, 'report_cell_universe_differs')
    selected = {c['valid_attempt_id']: c for c in cells}
    require(len(selected) == 30 and None not in selected, 'ambiguous_valid_representatives')
    extras = manifest['cells']
    require(len(extras) == 30 and len({x['attempt_id'] for x in extras}) == 30 and {x['attempt_id'] for x in extras} == set(selected), 'manifest_cell_universe_differs')
    extra_by_id = {x['attempt_id']: x for x in extras}; admitted = []
    for original, cell in zip(originals, cells):
        require(cell['status'] == 'complete_valid' and cell['identity'] == {k: original[k] for k in IDENTITY}, 'report_cell_not_admitted')
        representatives = [a for a in cell['attempts'] if a['status'] == 'complete_valid']
        require(len(representatives) == 1 and representatives[0]['terminal']['attempt_id'] == cell['valid_attempt_id'], 'representative_differs')
        saved = representatives[0]; refs = saved['references']; terminal = inputs.read(refs['terminal'])
        require(terminal['attempt_id'] == cell['valid_attempt_id'] and terminal['event'] == 'valid' and terminal['outcome_valid'] is True, 'terminal_not_valid')
        require(all(terminal.get(k) == v for k, v in saved['terminal'].items()), 'matrix_terminal_differs')
        require(terminal['plan_sha256'] in plans, 'unlisted_terminal_plan')
        plan = plans[terminal['plan_sha256']]
        matches = [r for r in plan['episodes'] if r['episode_key'] == terminal['episode_key']]
        require(len(matches) == 1, 'ambiguous_terminal_row'); row = matches[0]
        require(terminal['identity'] == {k: row[k] for k in IDENTITY} == cell['identity'] and terminal.get('retry_of') == row.get('retry_of'), 'terminal_cell_or_retry_differs')
        require(terminal['physical_gpu'] == 3 and terminal['init_row_sha256'] == row['init_row_sha256'] == original['init_row_sha256']
                and terminal['source_commit'] == plan['source_commit'] and terminal['profile_manifest_sha256'] == plan['profiles_sha256']
                and all(terminal[k] == plan[k] for k in ('runtime_manifest_sha256', 'runtime_inventory_sha256')), 'terminal_frozen_identity_differs')
        frozen = terminal['n2_frozen_identity']
        require(terminal['n2_cohort_id'] == frozen['cohort_id'] == COHORT and all(frozen[k] == plan[k] for k in BINDING)
                and frozen['candidate_sha256'] == plan['candidate_profiles']['N2']['sha256']
                and frozen['protocol_sha256'] == plan['n2_cohort']['protocol']['sha256']
                and frozen['accounting_clarification_sha256'] == plan['n2_cohort']['accounting_clarification']['sha256'], 'terminal_cohort_binding_differs')
        if row.get('retry_of'):
            predecessors = [a for a in cell['attempts'] if a['terminal']['attempt_id'] == row['retry_of']]
            require(len(predecessors) == 1 and predecessors[0]['terminal']['outcome_valid'] is False, 'matrix_recovery_link_missing')
        root = inputs.path(terminal['output_dir']); ed = root/'eds_eval'; ep = ed/'decision_evidence/episode_000'
        require(root.parent == inputs.root/'attempts' and Path(refs['terminal']['path']) == root/'attempt-result.json', 'attempt_root_differs')
        for kind, name in (('audit', 'decision-evidence-audit.json'), ('compute', 'episode_compute.jsonl')):
            require(Path(refs[kind]['path']) == ed/name, 'evidence_path_differs')
        audit, compute_rows = inputs.read(refs['audit']), inputs.read(refs['compute'], lines=True)
        require(audit['accepted'] is True and audit['evidence_complete'] is True and audit['errors'] == [] and audit['original_execution_outcome'] == 'completed'
                and audit['episode_dir'] == str(ep) and audit['episode_compute_file'] == str(ed/'episode_compute.jsonl'), 'audit_not_complete_or_linked')
        require(len(compute_rows) == 1, 'multiple_compute_rows'); compute = compute_rows[0]
        identity = {'episode_id': 0, 'task_id': row['task_id'], 'episode_seed': row['env_seed']}
        require(all(compute[k] == v for k, v in identity.items()) and compute['outcome'] == terminal['compute_outcome'] == 'completed', 'compute_identity_differs')
        extra = extra_by_id[terminal['attempt_id']]
        for kind, path in (('metadata', ed/'episode_metadata.jsonl'), ('status', ep/'status.json'), ('index', ep/'events.jsonl')):
            require(Path(extra[kind]['path']) == path, 'chronology_path_differs')
        require(inputs.read(extra['metadata'], lines=True) == [identity], 'metadata_identity_differs')
        status, index = inputs.read(extra['status']), inputs.read(extra['index'], lines=True)
        require(status['schema'] == 'qd-ed-decision-evidence-v1' and status['episode'] == 0 and status['complete'] is True and status['failed'] is False and status['pending_action'] is False, 'collector_not_complete')
        require(len(index) == status['bundles'] and all(x['bundle'] == f'bundle_{i:06d}.pt' for i, x in enumerate(index, 1)), 'bundle_index_invalid')
        stage = extra['stage_events']; stage_path = ed/'stage_events.jsonl'
        if stage['status'] == 'not_recorded':
            require(set(stage) == {'status', 'path'} and inputs.path(stage['path']) == stage_path and not stage_path.exists(), 'absent_stage_declaration_differs')
            inputs.absent.append(stage_path); stage_rows = None
        else:
            require(stage['status'] == 'present' and set(stage) == {'status', 'reference'} and Path(stage['reference']['path']) == stage_path, 'stage_reference_differs')
            stage_rows = inputs.read(stage['reference'], lines=True)
            require(all(all(x.get(k) == v for k, v in identity.items()) for x in stage_rows), 'stage_identity_differs')
        admitted.append({'cell': cell, 'terminal': terminal, 'row': row, 'ep': ep, 'ed': ed, 'status': status, 'index': index, 'compute': compute, 'stage_rows': stage_rows})
    for task in range(10):
        require(len({tuple(x['row'][k] for k in ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256')) for x in admitted[task*3:task*3+3]}) == 1, 'unmatched_task_arms')
    return report, admitted


def motion(helper, steps, previous=None):
    if not steps:
        return {'status': 'not_observed', 'reason': 'no_executed_actions'}
    value = helper.motion_summary(steps, previous)
    value.update(status='observed', gripper_qpos_origin_step=steps[0]['global_step'],
                 gripper_qpos_end_step=steps[-1]['global_step'], command_sign_interval='within_run_only_excludes_start_boundary',
                 precision='descriptive arithmetic on native stored values; no recovered measurement precision')
    return value


def joined_stage(events, decisions, steps):
    if events is None:
        return {'status': 'not_recorded', 'events': None, 'query_status_counts': None, 'trigger_counts': None, 'associations': None}
    by_step = {s['global_step']: s for s in steps}; associations = []
    for index, event in enumerate(events):
        at = [d for d in decisions if d['global_step'] == event.get('global_step')]
        current = at[0] if len(at) == 1 else None
        before = [d for d in decisions if d['executed_prefix_length'] and d['last_executed_step'] == event.get('global_step', -1)-1
                  and current is not None and d['reset_sequence'] == current['reset_sequence']]
        prior = before[0] if len(before) == 1 else None
        first = by_step.get(prior['global_step']) if prior else None
        last = by_step.get(prior['last_executed_step']) if prior else None
        if last and (last['terminated'] or last['truncated']): first = last = None
        used = event.get('gripper_value_used')
        known = first is not None and last is not None and type(used) in (int, float) and math.isfinite(used)
        associations.append({'event_index': index, 'global_step': event.get('global_step'),
            'current_decision_id': current['decision_id'] if current else None,
            'same_step_context_agrees': ((current['stage'], current['use_guidance']) == (event.get('stage_after'), event.get('guidance_after'))) if current else None,
            'preceding_decision_id': prior['decision_id'] if first else None,
            'status': 'exact_recorded_value_comparison' if known else 'Unknown_no_unique_contiguous_prefix_or_logged_value',
            'logged_value_used': used, 'logged_first': event.get('first_gripper_value'), 'logged_last': event.get('last_gripper_value'),
            'first_sent': first['command']['value'][6] if first else None, 'last_sent': last['command']['value'][6] if last else None,
            'matches_first_sent': used == first['command']['value'][6] if known else None,
            'matches_last_sent': used == last['command']['value'][6] if known else None})
    return {'status': 'recorded', 'events': events, 'associations': associations,
            'query_status_counts': dict(Counter(str(x.get('query_status')) for x in events)),
            'trigger_counts': dict(Counter(str(x.get('trigger_reason')) for x in events))}


def chronology(helper, decisions, steps, events):
    by_step = {s['global_step']: s for s in steps}; runs, transitions = [], []
    previous = None
    for d in decisions:
        contiguous = (previous is not None and previous['executed_prefix_length'] > 0 and previous['last_executed_step']+1 == d['global_step']
                      and previous['reset_sequence'] == d['reset_sequence'] and not by_step[previous['last_executed_step']]['terminated'] and not by_step[previous['last_executed_step']]['truncated'])
        signature = (d['stage'], d['use_guidance'], json.dumps(helper.provider_signature(d['providers']), sort_keys=True), d['reset_sequence'])
        if contiguous and (previous['stage'], previous['use_guidance']) != (d['stage'], d['use_guidance']):
            transitions.append({'global_step': d['global_step'], 'previous_decision_id': previous['decision_id'], 'decision_id': d['decision_id'],
                'stage_before': previous['stage'], 'stage_after': d['stage'], 'guidance_before': previous['use_guidance'], 'guidance_after': d['use_guidance']})
        if d['executed_prefix_length']:
            if runs and contiguous and runs[-1]['signature'] == signature:
                runs[-1]['decision_ids'].append(d['decision_id']); runs[-1]['last_step'] = d['last_executed_step']
            else:
                runs.append({'signature': signature, 'first_step': d['global_step'], 'last_step': d['last_executed_step'], 'decision_ids': [d['decision_id']],
                             'stage': d['stage'], 'use_guidance': d['use_guidance'], 'reset_sequence': d['reset_sequence'], 'providers': helper.provider_signature(d['providers'])})
        previous = d
    for run in runs:
        run.pop('signature'); segment = [s for s in steps if run['first_step'] <= s['global_step'] <= run['last_step']]
        run['motion'] = motion(helper, segment, by_step.get(run['first_step']-1))
    components = []
    for step in steps:
        if not components or step['global_step'] != components[-1][-1]['global_step']+1 or step['reset_sequence'] != components[-1][-1]['reset_sequence'] or components[-1][-1]['terminated'] or components[-1][-1]['truncated']:
            components.append([])
        components[-1].append(step)
    off = [t['global_step'] for t in transitions if t['guidance_before'] and not t['guidance_after']]
    on = [t['global_step'] for t in transitions if not t['guidance_before'] and t['guidance_after']]
    guided = [d for d in decisions if d['use_guidance']]
    guided_count = sum(d['executed_prefix_length'] for d in guided)
    suffix = []
    if off:
        for component in components:
            remaining = [s for s in component if s['global_step'] >= off[0]]
            if remaining: suffix.append(motion(helper, remaining, by_step.get(remaining[0]['global_step']-1)))
    return {'initial_guidance': decisions[0]['use_guidance'] if decisions else None,
            'observed_actions': len(steps), 'guided_actions': guided_count, 'guided_action_fraction': guided_count/len(steps) if steps else None,
            'first_on_to_off': {'step': off[0] if off else None, 'status': 'observed' if off else 'not_observed'},
            'all_on_to_off_steps': off, 'all_off_to_on_steps': on, 'state_runs': runs, 'transitions': transitions,
            'last_guided_action': next((d['last_executed_step'] for d in reversed(guided) if d['executed_prefix_length']), None),
            'terminal_step': steps[-1]['global_step'] if steps else None,
            'motion_components': [motion(helper, c) for c in components], 'post_first_off_components': suffix,
            'stage': joined_stage(events, decisions, steps), 'unknown': UNKNOWN}


def extract(admitted, inputs, helper):
    decisions, steps, resets, pending = [], [], [], []
    def finish():
        ctx = helper.one(pending, 'decision_context'); value = ctx['values']; actual = helper.actual_steps(pending)
        providers = [{k: p.get(k) for k in ('ordinal', 'code_sha256', 'original_code_sha256', 'source_text_sha256', 'source_path')} for p in value['providers']]
        d = {k: ctx[k] for k in ('decision_id', 'global_step', 'reset_sequence')}
        d.update(stage=value['stage'], previous_stage=value['previous_stage'], stage_changed=value['stage_changed'], use_guidance=value['use_guidance'],
                 providers=providers, executed_prefix_length=len(actual), last_executed_step=actual[-1]['global_step'] if actual else None)
        d['provider_identity_status'] = ('recorded' if all(p.get(k) is not None for p in providers
            for k in ('original_code_sha256', 'source_text_sha256', 'source_path')) else 'partially_unknown')
        decisions.append(d); steps.extend(actual)
        for event in pending:
            if event['event'] == 'automatic_reset_boundary':
                resets.append({**{k: event[k] for k in ('sequence', 'decision_id', 'global_step', 'reset_sequence')},
                               **{k: event['values'].get(k) for k in ('reset_will_follow', 'reset_completed')}})
    for ref in admitted['index']:
        p = inputs.path(admitted['ep']/ref['bundle']); data = p.read_bytes()
        require(sha(data) == ref['sha256'], 'bundle_sha_mismatch'); inputs.hashes[str(p)] = ref['sha256']
        payload = helper.torch.load(io.BytesIO(data), weights_only=True, map_location='cpu')
        for row in payload['events']:
            if row['event'] not in KEEP: continue
            if pending and row['decision_id'] != pending[0]['decision_id']:
                finish(); pending = []
            pending.append(row)
        del payload, data
    if pending: finish()
    require(len(decisions) == admitted['status']['decisions'] and sum(d['use_guidance'] for d in decisions) == admitted['compute']['guided_chunks'], 'decision_counts_differ')
    require([s['global_step'] for s in steps] == list(range(len(steps))), 'executed_step_gap')
    events = None if admitted['stage_rows'] is None else [{k: row.get(k) for k in helper.STAGE_KEYS} for row in admitted['stage_rows']]
    n2 = admitted['cell'].get('metrics', {}).get('n2')
    fallback = None if n2 is None else [{k: row.get(k) for k in ('global_step', 'qd_quality_applicable', 'qd_quality_reason')} for row in n2['records']]
    t = admitted['terminal']
    return {'identity': t['identity'], 'attempt_id': t['attempt_id'], 'retry_of': t.get('retry_of'), 'plan_sha256': t['plan_sha256'],
            'original_outcome': {k: t.get(k) for k in ('event', 'outcome_valid', 'success', 'task_failure', 'compute_outcome')},
            'task0_previously_exposed': t['identity']['task_id'] == 0, 'matrix_applicability_context_only': fallback,
            'finite_sent_actions': True, 'finite_source': 'frozen accepted audit and finite CPU native tensor extraction',
            'decisions': decisions, 'actual_steps': steps, 'automatic_reset_boundaries': resets,
            'summary': chronology(helper, decisions, steps, events)}


def run(authorization, authorization_sha, output):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'empty_CUDA_mask_required')
    inputs = Inputs(ARTIFACT_ROOT)
    auth = inputs.read({'path': str(Path(authorization).resolve()), 'sha256': authorization_sha})
    require(auth['schema'] == 'n2-dev-chronology-read-authorization-v1' and auth['status'] == 'AUTHORIZED_CPU_READ' and auth['scope_reviewed'] is True, 'read_not_authorized')
    freeze = inputs.read(auth['freeze'])
    require(freeze['status'] == 'CPU_TESTED_FROZEN_BEFORE_FULL_DEV_READ' and freeze['actual_read_authorized'] is False, 'freeze_invalid')
    for name, expected in freeze['local_files'].items():
        require(Path(name).name == name and sha((HERE/name).read_bytes()) == expected, 'reader_definition_changed')
    require({'read_full_dev.py', 'protocol-v1.md', 'input-schema-v1.json', 'dependencies-v1.json', 'test_read_full_dev.py'} <= set(freeze['local_files']), 'freeze_inventory_missing')
    helper, auditor, deps = dependencies()
    manifest = inputs.read(auth['input_manifest'])
    require(auth['matrix_report'] == manifest['matrix_report'], 'authorized_matrix_differs')
    out = inputs.path(output)
    require(out.is_relative_to(inputs.root/'continuation_20260923/full-dev-closed-loop-analysis'), 'output_scope_differs')
    out.mkdir(parents=True, exist_ok=False); started = time.monotonic(); phase = 'admission'; current_cell = None
    try:
        report, admitted = admit(manifest, inputs, deps)
        index = []
        for item in admitted:
            key = f"t{item['row']['task_id']:02d}-{item['row']['profile'].lower()}"
            current_cell = key; phase = 'bundle_verification'
            for ref in item['index']:
                p = inputs.path(item['ep']/ref['bundle'])
                require(sha(p.read_bytes()) == ref['sha256'], 'bundle_sha_mismatch_before_audit')
                inputs.hashes[str(p)] = ref['sha256']
            phase = 'fresh_audit'; before = time.monotonic(); fresh = auditor.audit_episode(item['ep'], item['ed']/'episode_compute.jsonl')
            xjson(out/(key+'-fresh-audit.json'), fresh)
            require(fresh['accepted'] is True and fresh['evidence_complete'] is True and fresh['errors'] == [], 'fresh_audit_incomplete')
            require(not helper.torch.cuda.is_initialized(), 'CUDA_initialized')
            phase = 'extraction'; value = extract(item, inputs, helper); xjson(out/(key+'.json'), value)
            index.append({'cell': key, 'attempt_id': value['attempt_id'], 'identity': value['identity'], 'retry_of': value['retry_of'],
                          'path': key+'.json', 'sha256': sha((out/(key+'.json')).read_bytes()),
                          'audit_and_extraction_wall_s': time.monotonic()-before,
                          **{k: value['summary'][k] for k in ('observed_actions', 'guided_actions', 'guided_action_fraction', 'first_on_to_off', 'all_off_to_on_steps', 'last_guided_action')},
                          'stage_recording': value['summary']['stage']['status']})
        phase = 'final_verification'; current_cell = None
        inputs.finish(); require(not helper.torch.cuda.is_initialized(), 'CUDA_initialized')
        require(all(sha((HERE/name).read_bytes()) == expected for name, expected in freeze['local_files'].items()), 'definition_changed')
        require(all(sha(Path(ref['path']).read_bytes()) == ref['sha256'] for ref in deps['sources'].values()), 'dependency_changed')
        provenance = {'schema': 'n2-dev-chronology-provenance-v1', 'complete': True, 'matrix_authority': manifest['matrix_report'],
            'authorization_sha256': authorization_sha, 'freeze': auth['freeze'], 'input_hashes': inputs.hashes,
            'declared_absent_sources': [str(p) for p in inputs.absent], 'source_dependencies': deps,
            'task0_previously_exposed': True, 'new_quality_computation': False, 'cuda_initialized': False,
            'analysis_wall_s': time.monotonic()-started, 'scientific_authority': 'original matrix report; chronology is descriptive only'}
        xjson(out/'inputs-and-audit.json', provenance)
        xjson(out/'index.json', {'schema': 'n2-dev-closed-loop-chronology-v1', 'complete': True, 'cells': index, 'unknown': UNKNOWN})
        with (out/'overview.md').open('x') as stream:
            stream.write('# Full Dev chronology\n\nDescriptive only. Task0 was already exposed; no outcome/cost/quality or promotion recomputation. See every cell JSON for all transitions, structured queries and native observations.\n\n| Cell | Actions | Guided actions | First OFF | All reactivations | Stage source |\n|---|---:|---:|---|---|---|\n')
            for cell in index:
                stream.write(f"| {cell['cell']} | {cell['observed_actions']} | {cell['guided_actions']} | {cell['first_on_to_off']['step']} | {cell['all_off_to_on_steps']} | {cell['stage_recording']} |\n")
        xjson(out/'status.json', {'complete': True, 'cells': len(index), 'original_task_outcomes_changed': False})
        return out
    except BaseException as error:
        xjson(out/'status.json', {'complete': False, 'error_type': type(error).__name__,
                               'phase': phase, 'cell': current_cell,
                               'error_code': str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Za-z0-9_]+', str(error)) else None,
                               'original_task_outcomes_changed': False, 'scientific_authority': 'unchanged original matrix report'})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization', type=Path, required=True); p.add_argument('--authorization-sha256', required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--execute-reviewed', action='store_true')
    args = p.parse_args(); require(args.execute_reviewed, 'explicit_reviewed_execution_required')
    print(run(args.authorization, args.authorization_sha256, args.output))


if __name__ == '__main__': main()
