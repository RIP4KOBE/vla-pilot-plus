"""Prospective FP64 saved-pool sensitivity screen, not a deployed scorer."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import torch

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def maxima(q, eligible=None):
    if eligible:
        mask = torch.zeros(q.numel(), dtype=torch.bool)
        mask[eligible] = True
        q = q.masked_fill(~mask, float('-inf'))
    return [int(x) for x in torch.nonzero(q == q.max()).reshape(-1)]

def main():
    torch.set_num_threads(1)
    source = HERE / 'audit-result-v1.json'
    old = json.loads(source.read_text())
    report = {'schema': 'readonly-clipped-quality-fixed-pool-v1',
              'source': {'path': str(source), 'sha256': sha(source)},
              'protocol_sha256': sha(HERE / 'clipped-ranking-screen-protocol-v1.md'),
              'paths': [], 'production_candidate': False,
              'caveat': 'Hypothetical FP64 seven-point objectives; fixed source origins/pools/N5 eligibility. No lift bonus, controller-instance proof, proposal rollout or alternative physical outcome. N21 comparison is hypothetical, not its actual shaped policy.'}
    weights = torch.tensor([1, 1, 1, 1, 3, 3, 3], dtype=torch.float64) / 13
    for item in old['paths']:
        counts = Counter()
        terminals, batches = [], []
        max_projection_error = 0.
        for ref in item['verified_bundles']:
            path = Path(ref['path'])
            assert sha(path) == ref['sha256']
            ev = torch.load(path, map_location='cpu', weights_only=True)['events']
            desc = [e for e in ev if e['event'] == 'qd_descriptor_assignment']
            if not desc:
                continue
            assert len(desc) == 11
            by = {e['sequence']: e for e in ev}
            final = next(e for e in ev if e['event'] == 'final_selection')
            f = final['values']
            selection = f['terminal_population']['grasp_selection']
            assert selection['target_index'] == 0
            assert selection['recognition_reason'] == 'recognized_weighted_distance_template'
            terminal_id = f['terminal_population']['scoring_batch_id']
            counts['guided_decisions'] += 1
            for event in desc:
                sid = event['values']['scoring_batch_id']
                v = by[sid]['values']
                xyz = v['projected_xyz'].double()
                actions = v['samples'][:, :8, 39:42].double()
                keypoints = v['keypoints'].double()
                origin = xyz[:, :1]
                raw = origin + torch.cumsum(actions * .01, dim=1)
                clipped = origin + torch.cumsum(actions.clamp(-1, 1) * .01, dim=1)
                raw_q = -((raw[:, :7] - keypoints[0]).square().sum(-1) * weights).sum(-1)
                clip_q = -((clipped[:, :7] - keypoints[0]).square().sum(-1) * weights).sum(-1)
                assert torch.isfinite(raw_q).all() and torch.isfinite(clip_q).all()
                no_clip = (actions.abs() <= 1).all(dim=(1, 2))
                assert torch.equal(raw_q[no_clip], clip_q[no_clip])
                raw_ties, clip_ties = maxima(raw_q), maxima(clip_q)
                saturated = (actions.abs() > 1).any(dim=(1, 2))
                counts['canonical_batches'] += 1
                counts['canonical_candidates'] += actions.shape[0]
                counts['saturated_candidates'] += int(saturated.sum())
                counts['changed_first_argmax'] += int(raw_ties[0] != clip_ties[0])
                counts['changed_maximum_set'] += int(raw_ties != clip_ties)
                counts['changed_stable_rank_order'] += int(not torch.equal(
                    torch.argsort(raw_q, descending=True, stable=True),
                    torch.argsort(clip_q, descending=True, stable=True)))
                deviation = float((raw - xyz[:, 1:]).abs().max())
                max_projection_error = max(max_projection_error, deviation)
                batches.append({'step': final['global_step'], 'scoring_batch_id': sid,
                                'raw_maxima': raw_ties, 'clipped_maxima': clip_ties,
                                'saturated_candidates': int(saturated.sum()),
                                'raw_quality': raw_q.tolist(), 'clipped_quality': clip_q.tolist(),
                                'native_to_fp64_projection_max_abs_m': deviation})
                if sid == terminal_id:
                    eligible = selection['eligible_indices']
                    a, b = maxima(raw_q, eligible), maxima(clip_q, eligible)
                    counts['terminal_first_choice_changes'] += int(a[0] != b[0])
                    counts['terminal_maximum_set_changes'] += int(a != b)
                    counts['recorded_selected_differs_from_hypothetical_raw'] += int(int(f['selected_index']) != a[0])
                    terminals.append({'step': final['global_step'],
                                      'fixed_original_eligible_indices': eligible,
                                      'raw_maxima': a, 'clipped_maxima': b,
                                      'recorded_actual_selected_index': int(f['selected_index']),
                                      'recorded_actual_quality_mode': f.get('quality_mode'),
                                      'raw_quality_at_raw_first_choice': float(raw_q[a[0]]),
                                      'clipped_quality_at_raw_first_choice': float(clip_q[a[0]]),
                                      'clipped_quality_at_clipped_first_choice': float(clip_q[b[0]])})
        output = {'label': item['label'], 'attempt_id': item['attempt_id'],
                  'counts': dict(counts), 'max_native_to_fp64_projection_abs_m': max_projection_error,
                  'terminal_records': terminals, 'canonical_batch_records': batches}
        report['paths'].append(output)
        print(json.dumps({'label': item['label'], 'counts': dict(counts),
                          'max_native_to_fp64_projection_abs_m': max_projection_error}), flush=True)
    assert not torch.cuda.is_initialized()
    target = HERE / 'clipped-ranking-result-v1.json'
    assert not target.exists()
    target.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')

if __name__ == '__main__':
    main()
