#!/usr/bin/env python3
"""Report the exact 60-cell N7/C0/Q0 C1 validation gate."""
import argparse
import json
from pathlib import Path

import qd_ed_final_runner as runner
import qd_ed_n7_validation_plan as contract


ROOT = Path(__file__).resolve().parents[1]


def report(plan_path):
    plan, _, _ = runner.validate_plan(plan_path, root=ROOT)
    events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    attempts = [event for event in events
                if event.get('identity', {}).get('iteration') == contract.COHORT
                and event.get('event') in runner.TERMINAL]
    cells = []
    seen_attempts = set()
    for row in plan['episodes']:
        terminals = [item for item in attempts if item['episode_key'] == row['episode_key']]
        runner.require(len([item for item in terminals if item['event'] == 'valid']) <= 1,
                       'N7 validation duplicate valid scientific cell')
        accepted = next((item for item in terminals if item['event'] == 'valid'), None)
        checkpoint = None
        if accepted is not None:
            output = Path(accepted['output_dir'])
            checkpoint_path = output / 'eds_eval/n7-validation-cell-audit.json'
            if checkpoint_path.is_file():
                checkpoint = runner.read_json(checkpoint_path)
                runner.require(checkpoint.get('accepted') is True
                    and checkpoint.get('attempt_id') == accepted['attempt_id']
                    and checkpoint.get('episode_key') == row['episode_key']
                    and checkpoint.get('profile') == row['profile']
                    and checkpoint.get('task_id') == row['task_id']
                    and checkpoint.get('seed_block') == row['seed_block']
                    and checkpoint.get('env_seed') == row['env_seed']
                    and checkpoint.get('init_row_sha256') == row['init_row_sha256']
                    and checkpoint.get('success') == accepted['success']
                    and checkpoint.get('source_commit') == plan['source_commit']
                    and checkpoint.get('plan_sha256') == runner.digest(plan_path),
                    'N7 validation accepted cell audit identity differs')
        seen_attempts.update(item['attempt_id'] for item in terminals)
        cells.append({'task_id': row['task_id'], 'seed_block': row['seed_block'],
                      'env_seed': row['env_seed'], 'init_row_sha256': row['init_row_sha256'],
                      'profile': row['profile'], 'episode_key': row['episode_key'],
                      'status': 'complete_audited' if checkpoint else 'incomplete_or_invalid',
                      'success': accepted['success'] if checkpoint else None,
                      'accepted_attempt_id': accepted['attempt_id'] if checkpoint else None,
                      'guided_chunks': checkpoint['guided_chunks'] if checkpoint else None,
                      'terminal_attempts': [{'attempt_id': item['attempt_id'],
                                            'event': item['event'],
                                            'gpu_process_wall_seconds': item.get('gpu_process_wall_seconds'),
                                            'success': item.get('success')}
                                           for item in terminals]})
    runner.require({x['attempt_id'] for x in attempts} == seen_attempts,
                   'N7 validation out-of-plan terminal attempt')
    complete = all(cell['status'] == 'complete_audited' for cell in cells)
    counts = {arm: sum(c['success'] is True for c in cells if c['profile'] == arm)
              if complete else None for arm in contract.ARMS}
    numeric = complete and counts['N7'] >= 10 and counts['N7'] >= counts['C0'] and counts['N7'] >= counts['Q0']
    return {'schema': 'qd-ed-n7-validation-c1-report-v1',
            'cohort_id': contract.COHORT,
            'plan': {'path': str(plan_path.resolve()), 'sha256': runner.digest(plan_path)},
            'source_commit': plan['source_commit'],
            'accepted_cells': sum(c['status'] == 'complete_audited' for c in cells),
            'expected_cells': 60, 'per_arm_expected': 20,
            'success_counts': counts, 'candidate_numeric_gate': numeric,
            'decision': 'ELIGIBLE_FOR_SEPARATELY_FROZEN_FORMAL' if numeric else
                        'REJECT_VALIDATION' if complete else 'INCOMPLETE_OR_INVALID',
            'formal_authorized': False,
            'new_attempts': len(attempts),
            'new_gpu_process_wall_seconds': sum(x.get('gpu_process_wall_seconds', 0.) for x in attempts),
            'generalization_claim': 'seed_robustness_only',
            'cells': cells}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runner.require(not args.output.exists(), 'N7 validation report output already exists')
    result = report(args.plan)
    destination = runner.owned(args.output, runner.read_json(args.plan)['artifact_root'])
    runner.durable_json(destination, result)
    print(json.dumps({'decision': result['decision'],
                      'accepted_cells': result['accepted_cells'],
                      'success_counts': result['success_counts'],
                      'report': str(destination)}))


if __name__ == '__main__':
    main()
