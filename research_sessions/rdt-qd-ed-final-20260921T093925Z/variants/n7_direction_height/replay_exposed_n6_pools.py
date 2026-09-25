#!/usr/bin/env python3
"""Read-only N7 cell replay on N6's already exposed canonical candidate pools."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'artifacts'
REPORT = ART / 'continuation_20260925/n6-dev-v1/full-dev-report-v1.json'
OUT = ART / 'continuation_20260925/n7-prerequisite-readonly-v1.json'


def xy_bounds(values):
    q = torch.quantile(values, torch.tensor([.05, .95]), dim=0)
    span = q[1] - q[0]
    lo, hi = q[0] - .1 * span, q[1] + .1 * span
    small = hi - lo < .08
    center = torch.quantile(values, .5, dim=0)
    return torch.where(small, center - .04, lo), torch.where(small, center + .04, hi)


def bins(values, lo, hi):
    return torch.floor((values - lo) / (hi - lo) * 4).long().clamp(0, 3)


def pairs_split(reference, proposed):
    return sum(reference[i] == reference[j] and proposed[i] != proposed[j]
               for i in range(16) for j in range(i + 1, 16))


def main():
    if OUT.exists():
        raise SystemExit(f'Existing immutable result: {OUT}')
    report = json.loads(REPORT.read_text())
    rows = []
    for cell in report['cells']:
        task = cell['task_id']
        folder = ART / 'attempts' / cell['accepted_attempt_id'] / 'eds_eval/decision_evidence/episode_000'
        for line in (folder / 'events.jsonl').open():
            summary = json.loads(line)
            if not any(e['event'] == 'qd_descriptor_assignment' for e in summary['events']):
                continue
            bundle_path = folder / summary['bundle']
            assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == summary['sha256']
            events = torch.load(bundle_path, map_location='cpu', weights_only=True)['events']
            context = [e for e in events if e['event'] == 'decision_context']
            assignments = [e for e in events if e['event'] == 'qd_descriptor_assignment']
            scoring = {e['sequence']: e for e in events if e['event'] == 'scoring_inputs'}
            assert len(context) == 1 and len(assignments) == 11
            assert [e['values']['iter_idx'] for e in assignments] == list(range(-1, 10))
            old_bounds = None
            h_bounds = None
            old_split = n6_split = 0
            for assignment in assignments:
                v = assignment['values']
                source = scoring[v['scoring_batch_id']]['values']
                assert source['scoring_scope']['iter_idx'] == v['iter_idx']
                xyz = source['projected_xyz'][:, 8, :3].float()
                target = source['keypoints'][0].float()
                assert xyz.shape == (16, 3) and target.shape == (3,)
                delta = xyz - target
                old_xy = delta[:, :2]
                height = delta[:, 2]
                if old_bounds is None:
                    old_bounds = xy_bounds(old_xy)
                    h_bounds = (v['bounds_lo'][1].float(), v['bounds_hi'][1].float())
                    calculated_height = xy_bounds(height.unsqueeze(1))
                    assert abs(h_bounds[0] - calculated_height[0][0]) <= 1e-6
                    assert abs(h_bounds[1] - calculated_height[1][0]) <= 1e-6
                old_b = bins(old_xy, *old_bounds)
                old_cell = (old_b[:, 1] * 4 + old_b[:, 0]).tolist()
                quadrant = (2 * (delta[:, 0] >= 0).long() + (delta[:, 1] >= 0).long())
                new_cell = (4 * bins(height, *h_bounds) + quadrant).tolist()
                n6_cell = v['cell_ids'].tolist()
                old_split += pairs_split(old_cell, new_cell)
                n6_split += pairs_split(n6_cell, new_cell)
            rows.append({'task_id': task, 'global_step': context[0]['global_step'],
                         'old_xy_same_cell_n7_split_pairs': old_split,
                         'n6_same_cell_n7_split_pairs': n6_split})
    assert rows and len(rows) == 40
    payload = {'schema': 'n7-prerequisite-readonly-v1',
               'scope': 'SHA-verified N6 native canonical candidate pools only; no rejected-candidate outcome',
               'source_report_sha256': hashlib.sha256(REPORT.read_bytes()).hexdigest(),
               'decisions': len(rows),
               'old_xy_split_witness_decisions': sum(r['old_xy_same_cell_n7_split_pairs'] > 0 for r in rows),
               'n6_split_witness_decisions': sum(r['n6_same_cell_n7_split_pairs'] > 0 for r in rows),
               'old_xy_split_pairs': sum(r['old_xy_same_cell_n7_split_pairs'] for r in rows),
               'n6_split_pairs': sum(r['n6_same_cell_n7_split_pairs'] for r in rows),
               'rows': rows}
    OUT.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({k: v for k, v in payload.items() if k != 'rows'}))
    print(f'path={OUT} sha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
