#!/usr/bin/env python3
"""SHA-verified, Dev-only comparison of original N7 and passive repeat."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as runner
import qd_ed_n7_passive_diagnostic as diagnostic

SOURCE_REPORT = diagnostic.ART / 'continuation_20260925/n7-dev-v1/full-dev-report-v1.json'
SOURCE_SHA = 'c6ae8e5864f0e550d8d4c5651422e1b25a38161b2781bc1b7937b93d9edaa463'
HIST_MOTION = HERE / 'target-motion-audit-v1.json'
HIST_MOTION_SHA = '78e495b476429d45f8ef04f9ee80dcf5967179f60e462f961ef5b8d5c1c0ca93'
PLAN = diagnostic.RUN_DIR / 'plan.frozen.v2.json'
OUT = HERE / 'passive-tracking-diagnostic-report-v1.json'
MD = HERE / 'passive-tracking-diagnostic-report-v1.md'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm_delta(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def action_fingerprint(value):
    tensor = value.detach().cpu().contiguous()
    return hashlib.sha256(
        f'{tensor.dtype}:{tuple(tensor.shape)}:'.encode() +
        tensor.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def load_bundle(folder, ref):
    path = folder / ref['bundle']
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ref['sha256']:
        raise ValueError('bundle SHA mismatch: ' + str(path))
    payload = torch.load(path, map_location='cpu', weights_only=True)
    if payload['schema'] != 'qd-ed-decision-evidence-v1':
        raise ValueError('native bundle schema mismatch')
    return payload['events']


def read_episode(output, *, passive):
    folder = Path(output) / 'eds_eval/decision_evidence/episode_000'
    refs = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
    context_refs = {}
    outcome_refs = {}
    for ref in refs:
        for event in ref['events']:
            if event['event'] == 'decision_context':
                context_refs[event['global_step']] = ref
            elif event['event'] == 'pre_reset_outcome':
                outcome_refs[event['global_step']] = ref
    context = {}
    hashed = set()
    for step, ref in context_refs.items():
        events = load_bundle(folder, ref)
        hashed.add(ref['bundle'])
        one = [e for e in events if e['event'] == 'decision_context']
        if len(one) != 1 or one[0]['global_step'] != step:
            raise ValueError('decision-context bundle cardinality mismatch')
        event = one[0]
        values = event['values']
        decode = [e for e in events if e['event'] == 'policy_action_decode']
        final = [e for e in events if e['event'] == 'final_selection']
        if len(decode) > 1 or len(final) > 1:
            raise ValueError('duplicate action or final-selection event')
        snap = values.get('keypoint_tracking_snapshot')
        if passive and values.get('keypoints') is not None:
            if not isinstance(snap, dict) or 'capture_error_type' in snap:
                raise ValueError('passive snapshot absent or capture failed')
        positions = values.get('keypoints')
        target = None if positions is None else positions[0].tolist()
        projection = next((e for e in events if e['event'] == 'projection_origin'), None)
        context[step] = {
            'decision_id': event['decision_id'],
            'stage': values['stage'], 'guided': bool(values['use_guidance']),
            'target0': target, 'snapshot': snap,
            'action_fingerprint': action_fingerprint(decode[0]['values']['action_chunk'])
                                  if decode else None,
            'selected_fingerprint': final[0]['values']['selected_canonical_fingerprint']
                                    if final else None,
            'eef_start': projection['values']['source_eef_position'].tolist()
                         if projection else None,
        }
    return folder, context, outcome_refs, hashed


def target_valid(row):
    snap = row['snapshot']
    return (isinstance(snap, dict) and
            snap.get('targets', {}).get('0') == {'valid': True, 'status': 'tracked'} and
            isinstance(snap.get('instance_id'), int) and
            isinstance(snap.get('generation'), int))


def status(row):
    snap = row['snapshot']
    return None if not isinstance(snap, dict) else snap.get('targets', {}).get('0')


def actual_motion(folder, ref, start):
    if ref is None or start is None:
        return None
    final = [e for e in load_bundle(folder, ref) if e['event'] == 'pre_reset_outcome']
    if len(final) != 1:
        raise ValueError('chunk last-action outcome cardinality mismatch')
    end = final[0]['values']['observation']['robot0_eef_pos'].tolist()
    return norm_delta(end, start)


def compare(old, new):
    common = sorted(set(old) & set(new))
    return {
        'old_decision_count': len(old), 'repeat_decision_count': len(new),
        'common_global_steps': len(common),
        'old_only_steps': sorted(set(old) - set(new)),
        'repeat_only_steps': sorted(set(new) - set(old)),
        'guided_status_mismatches': sum(old[s]['guided'] != new[s]['guided'] for s in common),
        'stage_mismatches': sum(old[s]['stage'] != new[s]['stage'] for s in common),
        'action_fingerprint_matches': sum(old[s]['action_fingerprint'] is not None and
                                         old[s]['action_fingerprint'] == new[s]['action_fingerprint']
                                         for s in common),
        'action_fingerprint_compared': sum(old[s]['action_fingerprint'] is not None and
                                           new[s]['action_fingerprint'] is not None for s in common),
        'selected_latent_fingerprint_matches': sum(old[s]['selected_fingerprint'] is not None and
                                                   old[s]['selected_fingerprint'] == new[s]['selected_fingerprint']
                                                   for s in common),
        'selected_latent_fingerprint_compared': sum(old[s]['selected_fingerprint'] is not None and
                                                    new[s]['selected_fingerprint'] is not None for s in common),
    }


def main():
    if OUT.exists() or MD.exists():
        raise SystemExit('immutable report exists')
    if sha(SOURCE_REPORT) != SOURCE_SHA or sha(HIST_MOTION) != HIST_MOTION_SHA:
        raise ValueError('source N7 Dev evidence changed')
    original = json.loads(SOURCE_REPORT.read_text())
    historical_motion = json.loads(HIST_MOTION.read_text())
    plan, _, _ = runner.validate_plan(PLAN, root=ROOT)
    if plan['phase_authorization'] != {'dev': True, 'validation': False, 'formal': False}:
        raise ValueError('diagnostic split scope changed')
    supervisor = json.loads((diagnostic.RUN_DIR / 'status-v2.json').read_text())
    if supervisor['status'] != 'completed_all_four_audited':
        raise ValueError('four-cell supervisor not complete')
    ledger = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    cells = []
    all_shift_rows = []
    for row in plan['episodes']:
        task = row['task_id']
        old_cell = next(c for c in original['cells'] if c['task_id'] == task)
        terminal = [e for e in ledger if e.get('episode_key') == row['episode_key']
                    and e['event'] in runner.TERMINAL]
        if len(terminal) != 1 or terminal[0]['event'] != 'valid' or not terminal[0]['outcome_valid']:
            raise ValueError(f'task {task} terminal attempt invalid or ambiguous')
        attempt = terminal[0]
        if attempt['plan_sha256'] != sha(PLAN) or attempt['physical_gpu'] != 3:
            raise ValueError(f'task {task} frozen plan/GPU identity mismatch')
        native = Path(attempt['output_dir']) / 'eds_eval/decision-evidence-audit.json'
        tracking = Path(attempt['output_dir']) / 'eds_eval/passive-tracking-audit.json'
        native_report = json.loads(native.read_text())
        tracking_report = json.loads(tracking.read_text())
        if not native_report['accepted'] or not native_report['evidence_complete']:
            raise ValueError(f'task {task} native evidence audit rejected')
        old_folder, old_ctx, _, old_hashes = read_episode(
            diagnostic.ART / 'attempts' / old_cell['accepted_attempt_id'], passive=False)
        folder, ctx, outcomes, hashes = read_episode(attempt['output_dir'], passive=True)
        if len(ctx) != tracking_report['decision_contexts']:
            raise ValueError(f'task {task} passive tracking audit count differs')
        counts = Counter()
        shifts = []
        for step, current in sorted(ctx.items()):
            if target_valid(current):
                counts['tracked_target0'] += 1
            else:
                counts['unknown_target0'] += 1
                counts['status_' + str(status(current))] += 1
            if not current['guided']:
                continue
            counts['guided'] += 1
            if target_valid(current):
                counts['tracked_guided'] += 1
            next_row = ctx.get(step + 8)
            if next_row is None:
                counts['guided_no_next_context'] += 1
                continue
            stable = (target_valid(current) and target_valid(next_row) and
                      current['snapshot']['instance_id'] == next_row['snapshot']['instance_id'] and
                      current['snapshot']['generation'] == next_row['snapshot']['generation'])
            if not stable:
                counts['guided_next_identity_or_tracking_unknown'] += 1
                continue
            counts['stable_tracked_guided_pairs'] += 1
            distance = norm_delta(current['target0'], next_row['target0'])
            if distance < .01:
                continue
            counts['valid_target_shift_ge_1cm'] += 1
            next_same_guided = bool(next_row['guided'] and next_row['stage'] == current['stage'])
            if next_same_guided:
                counts['shift_with_immediate_same_stage_guided_next'] += 1
            shifts.append({'task_id': task, 'global_step': step,
                           'next_global_step': step + 8,
                           'target_shift_m': distance,
                           'same_stage_next_guided': next_same_guided,
                           'tracker_instance_id': current['snapshot']['instance_id'],
                           'tracker_generation': current['snapshot']['generation'],
                           'actual_eef_motion_m': actual_motion(
                               folder, outcomes.get(step + 7), current['eef_start'])})
        all_shift_rows += shifts
        old_shift_steps = sorted(x['global_step'] for x in historical_motion['rows']
                                 if x['task_id'] == task and x['target_shift_m'] >= .01)
        new_shift_steps = sorted(x['global_step'] for x in shifts)
        cells.append({'task_id': task, 'old_success': old_cell['success'],
                      'repeat_success': attempt['success'],
                      'old_attempt_id': old_cell['accepted_attempt_id'],
                      'repeat_attempt_id': attempt['attempt_id'],
                      'repeat_native_audit_sha256': sha(native),
                      'repeat_tracking_audit_sha256': sha(tracking),
                      'old_context_bundle_sha_verified': len(old_hashes),
                      'repeat_context_bundle_sha_verified': len(hashes),
                      'original_shift_steps_ge_1cm': old_shift_steps,
                      'repeat_valid_shift_steps_ge_1cm': new_shift_steps,
                      'same_step_shift_overlap': sorted(set(old_shift_steps) & set(new_shift_steps)),
                      'counts': dict(counts), 'shifts': shifts,
                      'original_vs_repeat': compare(old_ctx, ctx)})
    shifted_episodes = sum(bool(c['shifts']) for c in cells)
    opportunities = sum(c['counts'].get('shift_with_immediate_same_stage_guided_next', 0)
                        for c in cells)
    gate = (shifted_episodes >= 2 and opportunities >= 2)
    report = {'schema': 'n7-passive-tracking-diagnostic-report-v1',
              'scope': 'four original N7 Dev cells repeated; no C1 validation/formal outcome used',
              'plan_sha256': sha(PLAN), 'original_dev_report_sha256': SOURCE_SHA,
              'original_target_motion_audit_sha256': HIST_MOTION_SHA,
              'supervisor_status_sha256': sha(diagnostic.RUN_DIR / 'status-v2.json'),
              'definitions': {
                  'tracked_target0': 'Snapshot valid=true,status=tracked for keypoint index 0.',
                  'stable_tracked_guided_pair': 'Both adjacent decision contexts tracked target0 with identical tracker instance_id and generation.',
                  'target_shift': 'Euclidean world-coordinate keypoint0 displacement from guided decision g to g+8; >=0.01 m fixed before repeat.',
                  'same_stage_opportunity': 'After valid shift, immediately next decision g+8 is guided and has the same recorded stage.',
                  'physical_limit': 'Tracking status attests pose-backed lookup, not object contact or causal effect. No physical counterfactual or contact sensor.',
                  'fingerprint_limit': 'Original/repeat action and selected-latent hashes compare aligned global steps only; drift may reflect provider/simulator nondeterminism, not this passive observer.'},
              'cells': cells,
              'overall': {'shifted_task_episodes': shifted_episodes,
                          'valid_target_shifts_ge_1cm': len(all_shift_rows),
                          'immediate_same_stage_guided_opportunities': opportunities,
                          'design_gate_pass': gate},
              'design_gate': {'requires_shifted_task_episodes_at_least': 2,
                              'requires_immediate_same_stage_guided_opportunities_at_least': 2,
                              'physical_coordinate_definition': 'world-coordinate target keypoint0 from existing pose-backed tracker',
                              'decision': 'eligible_for_separately_frozen_Dev_comparison' if gate else 'stop_feedback_parent_branch'},
              'no_candidate_promotion': True,
              'no_counterfactual_success_claim': True}
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    table = ['| Task | Original → repeat success | Guided tracked / guided | Valid shifts ≥1 cm (same original steps) | Immediate same-stage guided | Matched action fingerprints |',
             '| ---: | :---: | ---: | ---: | ---: | ---: |']
    for cell in cells:
        count = cell['counts']
        comparison = cell['original_vs_repeat']
        table.append(
            f"| {cell['task_id']} | {int(cell['old_success'])} → {int(cell['repeat_success'])} | "
            f"{count.get('tracked_guided', 0)} / {count.get('guided', 0)} | "
            f"{len(cell['shifts'])} ({len(cell['same_step_shift_overlap'])}) | "
            f"{count.get('shift_with_immediate_same_stage_guided_next', 0)} | "
            f"{comparison['action_fingerprint_matches']} / {comparison['action_fingerprint_compared']} |")
    lines = [
        '# N7 passive keypoint tracking diagnostic', '',
        f"Frozen plan SHA-256: `{sha(PLAN)}`. JSON report SHA-256: `{sha(OUT)}`. "
        'All four attempts use the original N7 development seeds, init rows and profile on GPU3.',
        '', *table, '',
        f"Design gate: **{'PASS' if gate else 'FAIL'}**; {shifted_episodes} task episodes "
        f"have valid ≥1 cm shifts and {opportunities} immediate same-stage guided opportunities. "
        'A pass only permits a separately frozen Dev comparison; it does not promote a candidate.',
        '',
        'A tracked status establishes that the existing keypoint lookup returned an object-pose-backed value. '
        'It does not establish contact, grasp, carried-object motion caused by the action, or a physical counterfactual. '
        'Original-vs-repeat action fingerprints compare only shared global steps; nondeterministic Stage/provider or '
        'simulation behavior may cause a mismatch. The original N7 outcomes and repeat outcomes are reported separately.',
        '',
        'Native bundles and per-attempt audits are SHA-verified. No C1 validation or formal outcome was inspected for this report.',
    ]
    MD.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'report': str(OUT), 'sha256': sha(OUT),
                      'markdown': str(MD), 'markdown_sha256': sha(MD),
                      'overall': report['overall']}, sort_keys=True))


if __name__ == '__main__':
    main()
