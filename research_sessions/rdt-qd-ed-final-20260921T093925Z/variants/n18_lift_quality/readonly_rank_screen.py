"""Post-freeze Dev-only rank effect on saved N7 pools; no rollout or tuning."""
import hashlib
import json
from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
sys.path.insert(0, str(SESSION / 'study_worktree'))
from core.rdt_libero_action_converter import rdt_action_to_libero_raw


def episode(path):
    out = {'guided_decisions': 0, 'batches': 0, 'positive_bonus_candidates': 0,
           'best_index_changed_batches': 0, 'top4_set_changed_batches': 0,
           'within_batch_pair_inversions': 0, 'decisions_with_any_rank_change': 0}
    for line in (path / 'events.jsonl').open():
        ref = json.loads(line)
        if not any(row['event'] == 'qd_descriptor_assignment' for row in ref['events']):
            continue
        file = path / ref['bundle']
        if hashlib.sha256(file.read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('native bundle SHA changed')
        events = torch.load(file, map_location='cpu', weights_only=True)['events']
        by_seq = {row['sequence']: row for row in events}
        rows = [row for row in events if row['event'] == 'qd_descriptor_assignment']
        if len(rows) != 11:
            raise ValueError('canonical round count changed')
        out['guided_decisions'] += 1
        decision_changed = False
        for row in rows:
            score_id = row['values']['scoring_batch_id']
            score = by_seq[score_id]['values']
            aggregate = next(item['values']['aggregate_before_reward_mode']
                             for item in events if item['event'] == 'scoring_aggregate'
                             and item['values']['scoring_batch_id'] == score_id)
            samples = score['samples']
            xyz = score['projected_xyz'].float()
            target = score['keypoints'][0].float()
            if samples.shape != (16, 64, 128) or xyz.shape != (16, 9, 3):
                raise ValueError('native canonical shape changed')
            grip = rdt_action_to_libero_raw(samples[:, :8, :])[:, :, 6]
            eligible = (torch.linalg.vector_norm(xyz[:, 1:] - target, dim=2) <= .04) & (grip > 0)
            first = eligible.int().argmax(dim=1)
            contact = xyz[torch.arange(16), first + 1, 2]
            rise = (xyz[:, 8, 2] - contact).clamp(min=0, max=.05)
            bonus = torch.where(eligible.any(dim=1), rise.square(), torch.zeros_like(rise)).to(aggregate.dtype)
            effective = aggregate if not bool((bonus != 0).any()) else aggregate + bonus
            out['batches'] += 1
            out['positive_bonus_candidates'] += int((bonus > 0).sum())
            before = sorted(range(16), key=lambda i: (-aggregate[i].item(), i))
            after = sorted(range(16), key=lambda i: (-effective[i].item(), i))
            if before[0] != after[0]:
                out['best_index_changed_batches'] += 1
                decision_changed = True
            if set(before[:4]) != set(after[:4]):
                out['top4_set_changed_batches'] += 1
                decision_changed = True
            inversions = sum((before.index(i) - before.index(j)) *
                             (after.index(i) - after.index(j)) < 0
                             for i in range(16) for j in range(i+1, 16))
            out['within_batch_pair_inversions'] += inversions
            decision_changed |= bool(inversions)
        out['decisions_with_any_rank_change'] += int(decision_changed)
    return out


def main():
    paths = {}
    for task, pattern in ((0, '*n17_physics_t00_n7_*'),
                          (3, '*n11_dev_t03_n7_*'),
                          (6, '*n11_dev_t06_n7_*'),
                          (9, '*n17_physics_t09_n7_*')):
        found = list((SESSION / 'artifacts/attempts').glob(pattern))
        if len(found) != 1:
            raise ValueError(f'N7 Dev path ambiguous for task {task}')
        paths[str(task)] = episode(found[0] / 'eds_eval/decision_evidence/episode_000')
    result = {'schema': 'n18-postfreeze-dev-readonly-rank-screen-v1',
              'paths': paths,
              'limitation': 'Saved N7 candidate pools only; N18 search changes future pools, archive contents and simulator actions. No counterfactual success claim.'}
    (HERE / 'readonly_rank_screen.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(paths, sort_keys=True))


if __name__ == '__main__':
    main()
