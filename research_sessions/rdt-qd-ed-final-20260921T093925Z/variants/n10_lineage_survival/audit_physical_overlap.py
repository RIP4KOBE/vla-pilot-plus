#!/usr/bin/env python3
"""Read-only exploratory physical-descriptor reach screen on exposed N7 Dev."""
import hashlib
import json
from pathlib import Path

import torch

V = Path(__file__).resolve().parent
R = V.parents[1]
A = R / 'artifacts'
REPORT = A / 'continuation_20260925/n7-dev-v1/full-dev-report-v1.json'
TRANSITIONS = V / 'one-chunk-tabu-feasibility-v2.json'
OUT = V / 'physical-overlap-screen-v1.json'
THRESHOLD_M = 0.03  # exploratory engineering screen; not a preregistered selector


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def one(events, name):
    found = [event for event in events if event['event'] == name]
    if len(found) != 1:
        raise ValueError(f'{name}: expected one, found {len(found)}')
    return found[0]['values']


def main():
    if OUT.exists():
        raise SystemExit(f'output already exists: {OUT}')
    report = json.loads(REPORT.read_text())
    transitions = json.loads(TRANSITIONS.read_text())
    rows = []
    for row in transitions['rows']:
        if not row['conditional_eligible']:
            continue
        task = row['task_id']
        cell = one([{'event': 'cell', 'values': c} for c in report['cells'] if c['task_id'] == task], 'cell')
        folder = A / 'attempts' / cell['accepted_attempt_id'] / 'eds_eval/decision_evidence/episode_000'
        index = {}
        for line in (folder / 'events.jsonl').open():
            entry = json.loads(line)
            for item in entry['events']:
                if item['event'] == 'decision_context':
                    index[item['global_step']] = entry

        def load(step):
            entry = index[step]
            bundle = folder / entry['bundle']
            if sha(bundle) != entry['sha256']:
                raise ValueError('native bundle hash mismatch')
            return torch.load(bundle, map_location='cpu', weights_only=True)['events']

        prior = load(row['perturbing_global_step'])
        following = load(row['next_global_step'])
        selected = one(prior, 'final_selection')['selected_index']
        assignments = [event['values'] for event in prior if event['event'] == 'qd_descriptor_assignment']
        previous = assignments[-1]['descriptors'][selected].tolist()
        initial = [event['values'] for event in following if event['event'] == 'qd_descriptor_assignment'
                   and event['values']['iter_idx'] == -1]
        if len(initial) != 1:
            raise ValueError('next initial descriptor assignment missing')
        descriptors = initial[0]['descriptors'].tolist()
        matched = [i for i, value in enumerate(descriptors)
                   if round(value[0]) == round(previous[0])
                   and abs(value[1] - previous[1]) <= THRESHOLD_M]
        rows.append({'task_id': task, 'prior_global_step': row['perturbing_global_step'],
                     'next_global_step': row['next_global_step'],
                     'prior_selected_quadrant': int(round(previous[0])),
                     'prior_selected_signed_height_m': previous[1],
                     'next_initial_population': len(descriptors),
                     'same_quadrant_within_3cm_initial_count': len(matched),
                     'matching_indices': matched})
    result = {'schema': 'n7-physical-overlap-exploratory-screen-v1',
              'scope': 'already-exposed valid original N7 Dev actions; CPU only',
              'sources_sha256': {'report': sha(REPORT), 'transitions': sha(TRANSITIONS)},
              'threshold_m': THRESHOLD_M,
              'matched_initial_candidates': sum(x['same_quadrant_within_3cm_initial_count'] for x in rows),
              'total_initial_candidates': sum(x['next_initial_population'] for x in rows),
              'rows': rows,
              'limits': 'This is a post hoc reach screen, not causal task evidence. Initial candidates are not archive parent slots; no keypoint validity was native-recorded in the original run.'}
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(OUT, sha(OUT))


if __name__ == '__main__':
    main()
