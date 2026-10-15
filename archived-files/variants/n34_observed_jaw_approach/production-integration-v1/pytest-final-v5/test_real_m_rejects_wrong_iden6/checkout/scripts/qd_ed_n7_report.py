#!/usr/bin/env python3
"""Prospective N7 Dev gate against immutable same-cell C0/Q0/N4/N5/N6 results."""
import argparse
import json
from pathlib import Path

import qd_ed_final_runner as runner
import qd_ed_n7_plan as n7


ROOT = Path(__file__).resolve().parents[1]


def report(plan_path):
    plan, _, _ = runner.validate_plan(plan_path, root=ROOT)
    prior = runner.read_json(n7.PRIOR_REPORT)
    runner.require(runner.digest(n7.PRIOR_REPORT) == n7.PRIOR_REPORT_SHA256
                   and prior['decision'] == 'REJECT_DEV' and prior['accepted_cells'] == 4
                   and prior['candidate_successes'] == 1,
                   'N7 N6 comparator report differs')
    controls = dict(prior['matched_prior_controls'])
    controls['N6'] = prior['candidate_successes']
    for cell in prior['cells']:
        runner.require(cell['status'] == 'complete_audited'
                       and cell['task_id'] in n7.TASKS,
                       'N7 N6 comparator cell invalid')
    runner.require(controls == {'C0': 0, 'Q0': 0, 'N4': 1, 'N5': 1, 'N6': 1},
                   'N7 matched comparator success counts differ')
    events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    attempts = [event for event in events if event.get('identity', {}).get('iteration') == n7.COHORT
                and event.get('event') in runner.TERMINAL]
    cells = []
    seen_attempts = set()
    for row in plan['episodes']:
        terminals = [item for item in attempts if item['episode_key'] == row['episode_key']]
        runner.require(len([item for item in terminals if item['event'] == 'valid']) <= 1,
                       'N7 duplicate valid scientific cell')
        accepted = next((item for item in terminals if item['event'] == 'valid'), None)
        checkpoint = None
        if accepted is not None:
            output = Path(accepted['output_dir'])
            checkpoint_path = output / 'eds_eval/n7-cell-audit.json'
            if checkpoint_path.is_file():
                checkpoint = runner.read_json(checkpoint_path)
                runner.require(checkpoint.get('accepted') is True
                               and checkpoint.get('attempt_id') == accepted['attempt_id']
                               and checkpoint.get('episode_key') == row['episode_key']
                               and checkpoint.get('success') == accepted['success']
                               and checkpoint.get('source_commit') == plan['source_commit']
                               and checkpoint.get('plan_sha256') == runner.digest(plan_path),
                               'N7 accepted cell audit identity differs')
        seen_attempts.update(item['attempt_id'] for item in terminals)
        cells.append({'task_id': row['task_id'], 'episode_key': row['episode_key'],
                      'status': 'complete_audited' if checkpoint else 'incomplete_or_invalid',
                      'success': accepted['success'] if checkpoint else None,
                      'accepted_attempt_id': accepted['attempt_id'] if checkpoint else None,
                      'terminal_attempts': [{'attempt_id': item['attempt_id'], 'event': item['event'],
                                             'gpu_process_wall_seconds': item.get('gpu_process_wall_seconds'),
                                             'success': item.get('success')}
                                            for item in terminals],
                      'old_xy_same_cell_new_split_pairs':
                          checkpoint['old_xy_same_cell_new_split_pairs'] if checkpoint else None,
                      'n6_same_cell_new_split_pairs':
                          checkpoint['n6_same_cell_new_split_pairs'] if checkpoint else None,
                      'parent_slots_from_split_cells':
                          checkpoint['parent_slots_from_split_cells'] if checkpoint else None})
    runner.require({x['attempt_id'] for x in attempts} == seen_attempts,
                   'N7 out-of-plan terminal attempt')
    complete = all(cell['status'] == 'complete_audited' for cell in cells)
    successes = sum(bool(cell['success']) for cell in cells if cell['status'] == 'complete_audited')
    splits = sum(cell['old_xy_same_cell_new_split_pairs'] or 0 for cell in cells)
    n6_splits = sum(cell['n6_same_cell_new_split_pairs'] or 0 for cell in cells)
    parents = sum(cell['parent_slots_from_split_cells'] or 0 for cell in cells)
    numeric = complete and successes >= 2 and all(successes >= value for value in controls.values())
    activity = complete and splits >= 1 and n6_splits >= 1 and parents >= 1
    promotion = bool(numeric and activity)
    return {'schema': 'qd-ed-n7-dev-report-v1', 'cohort_id': n7.COHORT,
            'plan': {'path': str(plan_path.resolve()), 'sha256': runner.digest(plan_path)},
            'source_commit': plan['source_commit'], 'cells': cells,
            'accepted_cells': sum(cell['status'] == 'complete_audited' for cell in cells),
            'candidate_successes': successes if complete else None,
            'candidate_denominator': 4 if complete else None,
            'matched_prior_controls': controls,
            'old_xy_same_cell_new_split_pairs': splits,
            'n6_same_cell_new_split_pairs': n6_splits,
            'parent_slots_from_split_cells': parents,
            'numeric_dev_gate': numeric, 'activity_gate': activity,
            'dev_promotion_eligible': promotion,
            'decision': 'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promotion else
                        'REJECT_DEV' if complete else 'INCOMPLETE_OR_INVALID',
            'validation_authorized': False, 'formal_authorized': False,
            'new_attempts': len(attempts),
            'new_gpu_process_wall_seconds': sum(item.get('gpu_process_wall_seconds', 0.) for item in attempts),
            'comparison_scope': 'Previously exposed, accepted N4-E1/N5/N6 same-cell comparisons; no fresh independent-control claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runner.require(not args.output.exists(), 'N7 report output already exists')
    result = report(args.plan)
    destination = runner.owned(args.output, runner.read_json(args.plan)['artifact_root'])
    runner.durable_json(destination, result)
    print(json.dumps({'decision': result['decision'], 'accepted_cells': result['accepted_cells'],
                      'candidate_successes': result['candidate_successes'], 'report': str(destination)}))


if __name__ == '__main__':
    main()
