#!/usr/bin/env python3
"""Describe saved control transitions and measured carry conflicts, without rollout changes."""
import argparse
import json
from pathlib import Path

from c0_trace_replay import STUDY, TRACE


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(folder):
    events = load_rows(folder/'output/eds_eval/stage_events.jsonl')
    historical = load_rows(TRACE)
    tasks = []
    for task in sorted({row['task_id'] for row in events}):
        rows = [row for row in events if row['task_id'] == task]
        changes = []
        previous = None
        for row in rows:
            signature = (row['stage_after'], row['guidance_after'], row.get('contact_phase'))
            if signature != previous:
                changes.append({key: row.get(key) for key in (
                    'global_step', 'stage_after', 'guidance_after', 'contact_phase',
                    'target_distance_m', 'gripper_width_m', 'normalized_reward_diagnostic',
                    'contact_trigger', 'stage_decision_reason', 'sensor_consistency_reason')})
            previous = signature
        carry = [row for row in rows if (row.get('physical_carry_evidence') or {}).get('persistent')]
        guided_carry = [row['global_step'] for row in carry if row['guidance_after']]
        old_off = next((row['global_step'] for row in historical if row['task_id'] == task and not row['guidance_after']), None)
        current_off = next((row['global_step'] for row in rows if not row['guidance_after']), None)
        tasks.append(dict(task=task, last_step=rows[-1]['global_step'], first_unguided_step=current_off,
            historical_first_unguided_step=old_off,
            measured_persistent_carry_steps=[row['global_step'] for row in carry],
            guided_despite_measured_persistent_carry_steps=guided_carry,
            transitions=changes))
    result = dict(run=folder.name,
        note='Measured carry is a proxy, not simulator grasp truth. Historical timing comparisons are descriptive; sampling and online replies may differ. No counterfactual success is inferred.',
        tasks=tasks)
    (folder/'control-timeline.json').write_text(json.dumps(result, indent=2)+'\n')
    for row in tasks:
        print({key: value for key,value in row.items() if key not in ('transitions','measured_persistent_carry_steps')})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    args = parser.parse_args()
    summarize(STUDY/'artifacts/stage_closed_loop_20260929/runs'/args.name)
