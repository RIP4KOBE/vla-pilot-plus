#!/usr/bin/env python3
"""Reproduce the fail-closed two-cell N7 diagnostic report, Dev evidence only."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_decision_evidence as native_audit
import qd_ed_final_runner as runner
import report_passive_diagnostic as helpers

PLAN = helpers.PLAN
RUN = helpers.diagnostic.RUN_DIR
OUT = HERE / 'passive-diagnostic-stopped-v1.json'
MD = HERE / 'passive-diagnostic-stopped-v1.md'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(task, repeat, old, old_motion):
    old_folder, old_contexts, _, old_hashes = helpers.read_episode(
        helpers.diagnostic.ART / 'attempts' / old['accepted_attempt_id'], passive=False)
    output = Path(repeat['output_dir'])
    folder, contexts, outcomes, hashes = helpers.read_episode(output, passive=True)
    evidence = native_audit.audit_episode(folder, output / 'eds_eval/episode_compute.jsonl')
    if not evidence['accepted'] or not evidence['evidence_complete']:
        raise ValueError(f'task {task} native decision evidence incomplete')
    counts = Counter()
    shifts = []
    for step, current in sorted(contexts.items()):
        counts['decisions'] += 1
        if helpers.target_valid(current):
            counts['tracked_decisions'] += 1
        else:
            counts['unknown_decisions'] += 1
        if not current['guided']:
            continue
        counts['guided'] += 1
        if helpers.target_valid(current):
            counts['tracked_guided'] += 1
        next_row = contexts.get(step + 8)
        if next_row is None:
            counts['guided_without_next_context'] += 1
            continue
        stable = (helpers.target_valid(current) and helpers.target_valid(next_row) and
                  current['snapshot']['instance_id'] == next_row['snapshot']['instance_id'] and
                  current['snapshot']['generation'] == next_row['snapshot']['generation'])
        if not stable:
            counts['adjacent_tracking_unknown'] += 1
            continue
        counts['stable_tracked_adjacent_guided'] += 1
        distance = helpers.norm_delta(current['target0'], next_row['target0'])
        if distance < .01:
            continue
        same_stage_next_guided = bool(next_row['guided'] and next_row['stage'] == current['stage'])
        counts['valid_shift_ge_1cm'] += 1
        if same_stage_next_guided:
            counts['immediate_same_stage_guided_opportunity'] += 1
        shifts.append({'global_step': step, 'target_shift_m': distance,
                       'immediate_same_stage_guided_next': same_stage_next_guided,
                       'actual_eef_motion_m': helpers.actual_motion(
                           folder, outcomes.get(step + 7), current['eef_start'])})
    old_shift_steps = sorted(x['global_step'] for x in old_motion['rows']
                             if x['task_id'] == task and x['target_shift_m'] >= .01)
    new_shift_steps = sorted(x['global_step'] for x in shifts)
    stage_file = output / 'eds_eval/stage_events.jsonl'
    stage = [json.loads(line) for line in stage_file.read_text().splitlines()]
    failures = [x for x in stage if x['query_ok'] is False]
    return {
        'task_id': task,
        'original_success': old['success'],
        'repeat_success': repeat['success'],
        'scientifically_valid_under_frozen_Stage_condition': repeat['outcome_valid'],
        'terminal_failure_class': repeat.get('failure_class'),
        'terminal_reason': repeat.get('reason'),
        'attempt_id': repeat['attempt_id'],
        'gpu_process_wall_seconds': repeat['gpu_process_wall_seconds'],
        'full_native_bundle_audit_accepted': True,
        'native_bundle_count': evidence['observed_counts']['decision_context'] and
                               json.loads((folder / 'status.json').read_text())['bundles'],
        'native_event_index_sha256': sha(folder / 'events.jsonl'),
        'native_status_sha256': sha(folder / 'status.json'),
        'stage_event_index_sha256': sha(stage_file),
        'stage_call_count': len(stage),
        'stage_failed_calls': [{'global_step': x['global_step'],
                                'query_status': x['query_status'],
                                'error': x['error'],
                                'event_types': x['transport']['event_types'],
                                'item_types': x['transport']['item_types'],
                                'process_returncode': x['transport']['lifecycle']['returncode'],
                                'complete_usage_observed': x['transport']['lifecycle']['complete_usage_observed']}
                               for x in failures],
        'old_context_bundle_sha_verified': len(old_hashes),
        'repeat_context_bundle_sha_verified': len(hashes),
        'tracking_counts': dict(counts),
        'original_shift_steps_ge_1cm_tracking_status_unknown': old_shift_steps,
        'repeat_valid_shift_steps_ge_1cm': new_shift_steps,
        'same_step_shift_overlap': sorted(set(old_shift_steps) & set(new_shift_steps)),
        'repeat_shifts': shifts,
        'original_vs_repeat': helpers.compare(old_contexts, contexts),
    }


def main():
    if OUT.exists() or MD.exists():
        raise SystemExit('immutable stopped report already exists')
    if sha(helpers.SOURCE_REPORT) != helpers.SOURCE_SHA or sha(helpers.HIST_MOTION) != helpers.HIST_MOTION_SHA:
        raise ValueError('historical N7 Dev evidence hash changed')
    plan, _, _ = runner.validate_plan(PLAN, root=ROOT)
    if sha(PLAN) != 'c068373479272eb682d774192126ed7d09ddc36b1743548960d823ea1705dc80':
        raise ValueError('frozen v2 diagnostic plan changed')
    if plan['phase_authorization'] != {'dev': True, 'validation': False, 'formal': False}:
        raise ValueError('protected split scope changed')
    supervisor = json.loads((RUN / 'status-v2.json').read_text())
    if supervisor != {'status': 'failed', 'completed_keys': ['n7_passive_t00_20260928'],
                      'reason': 'GateError', 'physical_gpu': 3}:
        raise ValueError('supervisor fail-closed record differs')
    ledger = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    relevant = [x for x in ledger if str(x.get('episode_key', '')).startswith('n7_passive_')]
    if {x['episode_key'] for x in relevant} != {
            'n7_passive_t00_20260928', 'n7_passive_t03_20260928'}:
        raise ValueError('unexpected passive diagnostic dispatch')
    terminal = {x['episode_key']: x for x in relevant if x['event'] in runner.TERMINAL}
    if len(terminal) != 2 or any(x['physical_gpu'] != 3 or
                                 x['plan_sha256'] != sha(PLAN) for x in terminal.values()):
        raise ValueError('attempt count or identity mismatch')
    original = json.loads(helpers.SOURCE_REPORT.read_text())
    old_motion = json.loads(helpers.HIST_MOTION.read_text())
    cells = []
    for task in (0, 3):
        repeat = terminal[f'n7_passive_t{task:02d}_20260928']
        old = next(x for x in original['cells'] if x['task_id'] == task)
        cells.append(summarize(task, repeat, old, old_motion))
    if (not cells[0]['scientifically_valid_under_frozen_Stage_condition'] or
            cells[1]['scientifically_valid_under_frozen_Stage_condition']):
        raise ValueError('frozen Stage verdict changed')
    gpu_seconds = sum(x['gpu_process_wall_seconds'] for x in cells)
    state = runner.read_state(ROOT / 'research-state.yaml')
    snapshot = runner.budget_snapshot(ledger, runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'))
    if (snapshot['running'] or snapshot['dispatched'] != state['budget']['dispatched'] or
            abs(snapshot['gpu_hours_consumed'] - state['budget']['gpu_hours_consumed']) > 1e-8):
        raise ValueError('private state/ledger reconciliation failed')
    report = {
        'schema': 'n7-passive-diagnostic-stopped-v1',
        'scope': 'two dispatched N7 Dev repeats only; task6/9 not run; no C1 validation/formal outcome used',
        'source_commit': plan['source_commit'], 'plan_sha256': sha(PLAN),
        'release_sha256': sha(RUN / 'execution-release-v2.json'),
        'supervisor_status_sha256': sha(RUN / 'status-v2.json'),
        'original_dev_report_sha256': helpers.SOURCE_SHA,
        'original_target_motion_audit_sha256': helpers.HIST_MOTION_SHA,
        'cells': cells,
        'budget_after': {'dispatched': snapshot['dispatched'],
                         'development_dispatched': snapshot['by_bucket']['development'],
                         'gpu_hours_consumed': snapshot['gpu_hours_consumed'],
                         'diagnostic_dispatches': 2,
                         'diagnostic_gpu_process_seconds': gpu_seconds,
                         'running': snapshot['running']},
        'design_gate': {'accepted_shifted_task_episodes': 1,
                        'requires_at_least': 2,
                        'status': 'not_met_stopped_after_invalid_Stage_cell',
                        'candidate_promotion': False},
        'interpretation': 'Task3 native keypoint evidence is complete, but one Codex Stage error event makes the full cell scientifically invalid under its frozen transport contract. Its tracking shifts are descriptive only. Tracked status attests existing object-pose lookup, not contact, grasp, causal motion, or a counterfactual.',
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    rows = ['| Task | Original → repeat outcome | Frozen Stage valid | Guided tracked | Stable adjacent pairs | ≥1 cm shifts (same original steps) | Immediate same-stage next guided | Action hashes equal |',
            '| ---: | :---: | :---: | ---: | ---: | ---: | ---: | ---: |']
    for cell in cells:
        c = cell['tracking_counts']; m = cell['original_vs_repeat']
        rows.append(f"| {cell['task_id']} | {int(cell['original_success'])} → {int(cell['repeat_success'])} | "
                    f"{'yes' if cell['scientifically_valid_under_frozen_Stage_condition'] else 'no'} | "
                    f"{c.get('tracked_guided',0)}/{c.get('guided',0)} | "
                    f"{c.get('stable_tracked_adjacent_guided',0)} | "
                    f"{c.get('valid_shift_ge_1cm',0)} ({len(cell['same_step_shift_overlap'])}) | "
                    f"{c.get('immediate_same_stage_guided_opportunity',0)} | "
                    f"{m['action_fingerprint_matches']}/{m['action_fingerprint_compared']} |")
    MD.write_text('\n'.join([
        '# Passive N7 diagnostic stopped after task3', '',
        f"Report SHA-256: `{sha(OUT)}`. Frozen plan SHA-256: `{sha(PLAN)}`. "
        'Both repeats ran serially on GPU3.', '', *rows, '',
        'Task0 replicated all 90 action fingerprints and 17 selected-latent fingerprints from the original N7 Dev run. '
        'Task3 had a Codex Stage stream/item error at global step 24. Although its 90 decision contexts and all native bundles audit cleanly, '
        'the frozen transport gate marks the full cell invalid. Its six tracked shifts cannot count toward the design gate.',
        '',
        f"Two Dev dispatches consumed {gpu_seconds:.3f} GPU-process seconds ({gpu_seconds/3600:.6f} h). "
        f"The private ledger and state reconcile at {snapshot['dispatched']} total, "
        f"{snapshot['by_bucket']['development']} development attempts, and {snapshot['gpu_hours_consumed']:.6f}/48 GPUh. "
        'No retry or task6/9 dispatch occurred; validation and formal splits remained closed.',
        '',
        '**Design gate not met:** only task0 is scientifically valid. No N10 algorithm is promoted from this diagnostic. '
        'Object-pose tracking status does not prove physical contact or a causal counterfactual.',
    ]) + '\n')
    print(json.dumps({'report': str(OUT), 'sha256': sha(OUT),
                      'markdown': str(MD), 'markdown_sha256': sha(MD)}, sort_keys=True))


if __name__ == '__main__':
    main()
