#!/usr/bin/env python3
"""Prospective N5 Dev gate from all four original cells and immutable N4 triplets."""
import argparse
import json
from pathlib import Path

import qd_ed_final_runner as runner
import qd_ed_n5_plan as n5


ROOT = Path(__file__).resolve().parents[1]


def report(plan_path):
    plan, _, _ = runner.validate_plan(plan_path, root=ROOT)
    prior = runner.read_json(n5.PRIOR_REPORT)
    runner.require(runner.digest(n5.PRIOR_REPORT) == n5.PRIOR_REPORT_SHA256
                   and prior['matrix'] == 'complete_valid_12',
                   'N5 comparator report differs')
    controls = {profile: 0 for profile in ('C0', 'Q0', 'N4')}
    for cell in prior['cells']:
        identity = cell['identity']
        runner.require(cell['status'] == 'complete_valid'
                       and identity['task_id'] in n5.TASKS
                       and identity['profile'] in controls,
                       'N5 historical comparator cell invalid')
        controls[identity['profile']] += int(cell['success'])
    runner.require(controls == {'C0': 0, 'Q0': 0, 'N4': 1},
                   'N5 prior matched success counts differ')
    events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    attempts = [event for event in events if event.get('identity', {}).get('iteration') == n5.COHORT
                and event.get('event') in runner.TERMINAL]
    cells = []
    seen_attempts = set()
    for row in plan['episodes']:
        terminals = [item for item in attempts if item['episode_key'] == row['episode_key']]
        runner.require(len([item for item in terminals if item['event'] == 'valid']) <= 1,
                       'N5 duplicate valid scientific cell')
        accepted = next((item for item in terminals if item['event'] == 'valid'), None)
        checkpoint = None
        if accepted is not None:
            output = Path(accepted['output_dir'])
            checkpoint_path = output / 'eds_eval/n5-cell-audit.json'
            if checkpoint_path.is_file():
                checkpoint = runner.read_json(checkpoint_path)
                runner.require(checkpoint.get('accepted') is True
                               and checkpoint.get('attempt_id') == accepted['attempt_id']
                               and checkpoint.get('episode_key') == row['episode_key']
                               and checkpoint.get('success') == accepted['success']
                               and checkpoint.get('source_commit') == plan['source_commit']
                               and checkpoint.get('plan_sha256') == runner.digest(plan_path),
                               'N5 accepted cell audit identity differs')
        seen_attempts.update(item['attempt_id'] for item in terminals)
        cells.append({'task_id': row['task_id'], 'episode_key': row['episode_key'],
                      'status': 'complete_audited' if checkpoint else 'incomplete_or_invalid',
                      'success': accepted['success'] if checkpoint else None,
                      'accepted_attempt_id': accepted['attempt_id'] if checkpoint else None,
                      'terminal_attempts': [{'attempt_id': item['attempt_id'], 'event': item['event'],
                                             'gpu_process_wall_seconds': item.get('gpu_process_wall_seconds'),
                                             'success': item.get('success')}
                                            for item in terminals],
                      'native_argmin_actual_prefix_different_decisions':
                          checkpoint['native_argmin_actual_prefix_different_decisions'] if checkpoint else None})
    runner.require({x['attempt_id'] for x in attempts} == seen_attempts,
                   'N5 out-of-plan terminal attempt')
    complete = all(cell['status'] == 'complete_audited' for cell in cells)
    successes = sum(bool(cell['success']) for cell in cells if cell['status'] == 'complete_audited')
    changed = sum(cell['native_argmin_actual_prefix_different_decisions'] or 0 for cell in cells)
    numeric = complete and successes >= 2 and all(successes >= value for value in controls.values())
    activity = complete and changed >= 1
    promotion = bool(numeric and activity)
    return {'schema': 'qd-ed-n5-dev-report-v1', 'cohort_id': n5.COHORT,
            'plan': {'path': str(plan_path.resolve()), 'sha256': runner.digest(plan_path)},
            'source_commit': plan['source_commit'], 'cells': cells,
            'accepted_cells': sum(cell['status'] == 'complete_audited' for cell in cells),
            'candidate_successes': successes if complete else None,
            'candidate_denominator': 4 if complete else None,
            'matched_prior_controls': controls,
            'native_argmin_actual_prefix_different_decisions': changed,
            'numeric_dev_gate': numeric, 'activity_gate': activity,
            'dev_promotion_eligible': promotion,
            'decision': 'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promotion else
                        'REJECT_DEV' if complete else 'INCOMPLETE_OR_INVALID',
            'validation_authorized': False, 'formal_authorized': False,
            'new_attempts': len(attempts),
            'new_gpu_process_wall_seconds': sum(item.get('gpu_process_wall_seconds', 0.) for item in attempts),
            'comparison_scope': 'Previously exposed, accepted N4-E1 same-cell triplets; no controls rerun or independent-test claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runner.require(not args.output.exists(), 'N5 report output already exists')
    result = report(args.plan)
    destination = runner.owned(args.output, runner.read_json(args.plan)['artifact_root'])
    runner.durable_json(destination, result)
    print(json.dumps({'decision': result['decision'], 'accepted_cells': result['accepted_cells'],
                      'candidate_successes': result['candidate_successes'], 'report': str(destination)}))


if __name__ == '__main__':
    main()
