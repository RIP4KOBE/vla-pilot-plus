#!/usr/bin/env python3
"""CPU-only replay of frozen Q0 traces; no environment or model is imported.

This measures proxy/action distinctions and actual archive eliminations, never
the unobserved task outcomes of unexecuted alternatives.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


def fingerprint(action):
    return hashlib.sha256(action.float().contiguous().numpy().astype('<f4').tobytes()).hexdigest()


def gripper_sequence(action):
    # Exact deployed decoder semantics: zero maps to +1.
    return tuple(-1 if v < 0 else 1 for v in action[:8, 10].tolist())


def assign_cells(descriptors, lo, hi):
    xy = ((descriptors.float() - lo) / (hi - lo) * 4).floor().long().clamp(0, 3)
    return (4 * xy[:, 1] + xy[:, 0]).tolist()


def update_archive(archive, batch):
    grouped = collections.defaultdict(list)
    for row in batch:
        grouped[row['cell']].append(row)
    eliminated = []
    for cell, candidates in sorted(grouped.items()):
        incumbent = archive.get(cell)
        pool = candidates + ([incumbent] if incumbent else [])
        winner = min(pool, key=lambda x: (-x['reward'], x['fingerprint']))
        archive[cell] = winner
        for loser in pool:
            if loser['fingerprint'] != winner['fingerprint'] and loser['gripper'] != winner['gripper']:
                eliminated.append({'cell': cell, 'winner': winner, 'loser': loser,
                                   'kind': 'incumbent_displaced' if loser is incumbent else 'candidate_rejected'})
    return eliminated


def audit_trace(path):
    x = torch.load(path, map_location='cpu', weights_only=True)
    q = x['qd_info']
    if q['qd_grid_shape'] != [4, 4] or q['qd_cell_capacity'] != 1:
        raise ValueError('Expected Q0 capacity-one 4x4 archive')
    stages = {s['iter_idx']: s for s in x['stages'] if s['stage'] == 'full_process_after_rollout'}
    stages[-1] = next(s for s in x['stages'] if s['stage'] == 'initial')
    lo, hi = (torch.tensor(z) for z in q['qd_bounds_xy_m'])
    target = x['keypoints'][0].float()
    archive, all_candidates = {}, {}
    counts = collections.Counter()
    events, zspans, xy_end_gaps = [], [], []
    # Uses stored BD(t8) directly. t7 is saved scoring trajectory's final point.
    # This avoids reconstructing t8 from rounded BF16 deltas.
    for stream in q['shadow_qd_candidate_stream']:
        iteration = stream['iter_idx']
        stage = stages[iteration]
        actions = stage['actions'].float()
        bd8 = torch.tensor(stream['descriptors_xy_m'])
        bd7 = stage['trajectories'][:, -1, :2].float() - target[:2]
        ids = assign_cells(bd8, lo, hi)
        ids7 = assign_cells(bd7, lo, hi)
        counts['batches'] += 1
        counts['candidates'] += len(ids)
        counts['t7_t8_cell_differences'] += sum(a != b for a, b in zip(ids, ids7, strict=True))
        counts['nearest_target_xy_identity_differences'] += int(bd7.norm(dim=1).argmin() != bd8.norm(dim=1).argmin())
        xy_end_gaps.extend((bd8 - bd7).norm(dim=1).tolist())
        batch = []
        for i, (cell, reward, fp) in enumerate(zip(ids, stream['rewards'], stream['fingerprints'], strict=True)):
            if fingerprint(actions[i]) != fp:
                raise ValueError(f'Trace fingerprint mismatch {path} iteration {iteration} candidate {i}')
            row = {'cell': cell, 'reward': reward, 'fingerprint': fp, 'gripper': gripper_sequence(actions[i]),
                   'scored_t7_z': float(stage['trajectories'][i, -1, 2]), 'iteration': iteration, 'candidate': i}
            batch.append(row)
            all_candidates[fp] = row
        for cell in set(ids):
            group = [v for v in batch if v['cell'] == cell]
            if len(group) > 1:
                counts['collision_cells'] += 1
                counts['mixed_gripper_sequence_cells'] += int(len({v['gripper'] for v in group}) > 1)
                counts['mixed_final_gripper_cells'] += int(len({v['gripper'][-1] for v in group}) > 1)
                zspans.append(max(v['scored_t7_z'] for v in group) - min(v['scored_t7_z'] for v in group))
        for event in update_archive(archive, batch):
            event['batch_iteration'] = iteration
            events.append(event)
        if iteration >= 0:
            observed = {str(k): v['reward'] for k, v in sorted(archive.items())}
            if observed != q['qd_per_cell_elite_reward_by_iter'][iteration]:
                raise ValueError(f'Archive replay mismatch {path} iteration {iteration}')
    selected = min(archive.values(), key=lambda v: (-v['reward'], v['fingerprint'], v['cell']))
    if selected['fingerprint'] != q['qd_selected_action_fingerprint']:
        raise ValueError(f'Final selection replay mismatch {path}')
    alternatives = [v for v in all_candidates.values() if v['gripper'] != selected['gripper']]
    best_alternative = min(alternatives, key=lambda v: (-v['reward'], v['fingerprint'])) if alternatives else None
    counts['gripper_discordant_eliminations'] = len(events)
    counts['incumbent_gripper_discordant_displacements'] = sum(e['kind'] == 'incumbent_displaced' for e in events)
    counts['equal_reward_gripper_discordant_eliminations'] = sum(e['winner']['reward'] == e['loser']['reward'] for e in events)
    def positive_duty(row):
        return sum(v > 0 for v in row['gripper']) / 8
    def duty_bin(row):
        return min(int(4 * positive_duty(row)), 3)
    counts['discordant_eliminations_with_different_positive_duty'] = sum(positive_duty(e['winner']) != positive_duty(e['loser']) for e in events)
    counts['discordant_eliminations_separated_by_four_fixed_duty_bins'] = sum(duty_bin(e['winner']) != duty_bin(e['loser']) for e in events)
    return {'source': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'task_id': x['metadata']['task_id'], 'episode': x['metadata']['episode'],
            'global_step': x['metadata']['global_step'], 'counts': dict(counts),
            'archive_replay_pass': True, 'final_selection_replay_pass': True,
            'selected': selected, 'best_gripper_discordant_alternative': best_alternative,
            'eliminations': events, 'collision_t7_z_spans_m': zspans, 't7_t8_xy_gaps_m': xy_end_gaps}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.trace_root.glob('episode_*/chunk_*/tensors/mechanism_trace.pt'))
    if not files:
        raise ValueError('No traces')
    rows = [audit_trace(p) for p in files]
    counts = collections.Counter()
    tasks = collections.defaultdict(collections.Counter)
    for row in rows:
        counts.update(row['counts'])
        tasks[row['task_id']].update(row['counts'])
    zspans = [v for r in rows for v in r['collision_t7_z_spans_m']]
    gaps = [v for r in rows for v in r['t7_t8_xy_gaps_m']]
    altrows = [r for r in rows if r['best_gripper_discordant_alternative'] is not None]
    summary = {'traces': len(rows), 'tasks': sorted(tasks), 'counts': dict(counts),
               'per_task': {k: dict(v) for k, v in sorted(tasks.items())},
               'collision_t7_z_span_median_m': float(np.median(zspans)),
               'collision_t7_z_span_p95_m': float(np.percentile(zspans, 95)),
               't7_t8_xy_gap_median_m': float(np.median(gaps)),
               't7_t8_xy_gap_p95_m': float(np.percentile(gaps, 95)),
               'traces_with_gripper_discordant_alternative_to_final_selection': len(altrows),
               'best_discordant_alternative_reward_gap': [r['selected']['reward'] - r['best_gripper_discordant_alternative']['reward'] for r in altrows],
               'all_archive_and_selected_fingerprint_replays_pass': True}
    result = {'schema': 'qd-ed-executable-behavior-diagnostic-v1', 'summary': summary, 'traces': rows,
              'scope': 'Historical Q0 saved proposals only; first two traced chunks per task; CPU only.',
              'limitations': ['No counterfactual task outcomes or grasp/contact labels.',
                             'Grip sign distinction is executable action distinction, not correct grasp.',
                             'Four-bin positive-command duty separation is pairwise only: new 3D-radial collisions and total archive retention require a separate replay.',
                             't7/t8 positions use saved BF16 trajectory and float32 descriptors; geometric boundary counts are descriptive.',
                             'Quality retains highest existing reward; distinct-action rejection alone does not prove harmful selection.',
                             'Trace set inherited a cache identity risk; repeats under corrected baseline are required.'],
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'software': {'torch': torch.__version__, 'numpy': np.__version__},
              'new_episodes': 0, 'gpu_calls': 0, 'model_calls': 0, 'environment_calls': 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
