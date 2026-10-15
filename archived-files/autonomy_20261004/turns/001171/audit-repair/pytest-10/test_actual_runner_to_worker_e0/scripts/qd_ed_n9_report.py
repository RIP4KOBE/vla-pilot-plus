#!/usr/bin/env python3
"""Report N9's prospective 16-cell exposed-Dev gate without releasing validation."""
import argparse
import json
from pathlib import Path

import qd_ed_final_runner as runner
import qd_ed_n9_plan as contract

ROOT = Path(__file__).resolve().parents[1]


def report(plan_path):
    plan, _, _ = runner.validate_plan(plan_path, root=ROOT)
    events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    attempts = [event for event in events
                if event.get('identity', {}).get('iteration') == contract.COHORT
                and event.get('event') in runner.TERMINAL]
    cells = []
    seen = set()
    changed = []
    for row in plan['episodes']:
        terminals = [event for event in attempts if event['episode_key'] == row['episode_key']]
        runner.require(len(terminals) <= 1, 'N9 repeated original cell')
        accepted = terminals[0] if terminals and terminals[0]['event'] == 'valid' else None
        checkpoint = None
        if accepted is not None:
            path = Path(accepted['output_dir']) / 'eds_eval/n9-cell-audit.json'
            if path.is_file():
                checkpoint = runner.read_json(path)
                runner.require(checkpoint['accepted'] is True
                               and checkpoint['attempt_id'] == accepted['attempt_id']
                               and checkpoint['episode_key'] == row['episode_key']
                               and checkpoint['profile'] == row['profile']
                               and checkpoint['success'] == accepted['success']
                               and checkpoint['source_commit'] == plan['source_commit']
                               and checkpoint['plan_sha256'] == runner.digest(plan_path),
                               'N9 accepted audit identity differs')
                if row['profile'] == 'N9':
                    changed.extend(checkpoint['changed_decisions'])
        seen.update(event['attempt_id'] for event in terminals)
        cells.append({'task_id': row['task_id'], 'profile': row['profile'],
                      'episode_key': row['episode_key'], 'env_seed': row['env_seed'],
                      'init_row_sha256': row['init_row_sha256'],
                      'status': 'complete_audited' if checkpoint else 'incomplete_or_invalid',
                      'success': accepted['success'] if checkpoint else None,
                      'accepted_attempt_id': accepted['attempt_id'] if checkpoint else None,
                      'guided_chunks': checkpoint['guided_chunks'] if checkpoint else None,
                      'terminal_attempts': [{'attempt_id': event['attempt_id'],
                                             'event': event['event'],
                                             'gpu_process_wall_seconds': event.get('gpu_process_wall_seconds')}
                                            for event in terminals]})
    runner.require({event['attempt_id'] for event in attempts} == seen,
                   'N9 out-of-plan terminal attempt')
    complete = all(c['status'] == 'complete_audited' for c in cells)
    counts = {arm: sum(c['success'] is True for c in cells if c['profile'] == arm)
              if complete else None for arm in contract.ARMS}
    numeric = complete and counts['N9'] >= 3 and counts['N9'] > counts['N7'] \
        and counts['N9'] >= counts['C0'] and counts['N9'] >= counts['Q0']
    sweep_reduction = sum(c['sweep_reduction_m'] for c in changed) / len(changed) if changed else None
    max_reach_loss = max((c['reach_loss_m'] for c in changed), default=None)
    activity = complete and len(changed) >= 4 and sweep_reduction is not None \
        and sweep_reduction >= 0.01 and max_reach_loss is not None and max_reach_loss <= 0.02 + 1e-7
    eligible = bool(numeric and activity)
    return {'schema': 'qd-ed-n9-dev-report-v1', 'cohort_id': contract.COHORT,
            'plan': {'path': str(plan_path.resolve()), 'sha256': runner.digest(plan_path)},
            'source_commit': plan['source_commit'], 'accepted_cells': sum(c['status'] == 'complete_audited' for c in cells),
            'expected_cells': 16, 'per_arm_expected': 4, 'success_counts': counts,
            'candidate_numeric_gate': bool(numeric), 'mechanism_activity_gate': bool(activity),
            'changed_guided_decisions': len(changed), 'mean_changed_sweep_reduction_m': sweep_reduction,
            'max_changed_reach_loss_m': max_reach_loss,
            'dev_promotion_eligible': eligible,
            'decision': 'ELIGIBLE_FOR_FRESH_VALIDATION_BUDGET_DECISION' if eligible else
                        'REJECT_DEV' if complete else 'INCOMPLETE_OR_INVALID',
            'validation_authorized': False, 'formal_authorized': False,
            'new_attempts': len(attempts),
            'new_gpu_process_wall_seconds': sum(x.get('gpu_process_wall_seconds', 0.) for x in attempts),
            'comparison_scope': 'Previously exposed Dev identities rerun prospectively in matched four-arm order; no independent validation claim.',
            'cells': cells}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runner.require(not args.output.exists(), 'N9 report already exists')
    result = report(args.plan)
    runner.durable_json(runner.owned(args.output, runner.read_json(args.plan)['artifact_root']), result)
    print(json.dumps({'decision': result['decision'], 'success_counts': result['success_counts'],
                      'accepted_cells': result['accepted_cells'], 'report': str(args.output)}))


if __name__ == '__main__':
    main()
