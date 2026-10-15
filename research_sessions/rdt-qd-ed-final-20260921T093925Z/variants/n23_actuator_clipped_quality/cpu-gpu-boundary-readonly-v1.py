"""CPU replay only of the three explicitly authorized, existing exposed paths."""
import hashlib
import json
from pathlib import Path
import torch

torch.set_num_threads(1)
P = Path(__file__).resolve().parent
R = P.parent.parent
index = R / 'diagnostics/20260930_executed_projection/audit-result-v1.json'
result = {'schema': 'n23-cpu-gpu-arithmetic-boundary-v1', 'index_sha256': hashlib.sha256(index.read_bytes()).hexdigest(), 'paths': []}
for item in json.loads(index.read_text())['paths']:
    origins, scores = {}, {}
    row = {'label': item['label'], 'verified_bundles': 0, 'batches': 0, 'candidates': 0,
           'raw_score_mismatches': 0, 'raw_score_max_abs': 0., 'raw_projection_mismatches': 0,
           'raw_projection_max_abs_m': 0., 'examples': [], 'dtypes': []}
    for ref in item['verified_bundles']:
        path = Path(ref['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256']
        row['verified_bundles'] += 1
        for event in torch.load(path, map_location='cpu', weights_only=True)['events']:
            kind, v = event['event'], event['values']
            if kind == 'projection_origin':
                origins[event['sequence']] = v['source_eef_position']
            elif kind == 'scoring_inputs' and v['scoring_scope']['role'] in {'canonical_initial', 'canonical_offspring', 'canonical_population'}:
                scores[event['sequence']] = v
            elif kind == 'scoring_aggregate' and v['scoring_batch_id'] in scores:
                batch = scores.pop(v['scoring_batch_id']); actions=batch['samples']; xyz=batch['projected_xyz']; target=batch['keypoints'][0]
                raw = v['aggregate_before_reward_mode']; native = []
                w = torch.tensor([1.,1.,1.,1.,3.,3.,3.]) / 13
                for i, a in enumerate(actions):
                    origin=origins[batch['projection_origin_sequences'][i]].to(actions.dtype)
                    projected = origin + torch.cumsum(a[:8,39:42] * .01, dim=0)
                    pdelta=(projected.float()-xyz[i,1:].float()).abs().max().item()
                    row['raw_projection_mismatches'] += int(not torch.equal(projected, xyz[i,1:]))
                    row['raw_projection_max_abs_m'] = max(row['raw_projection_max_abs_m'], pdelta)
                    distance=torch.norm(xyz[i:i+1,1:8] - target, dim=-1)
                    native.append((-(distance ** 2 * w).sum(dim=1)).mean().to(raw.dtype))
                native=torch.stack(native)
                mismatch=native != raw
                row['raw_score_mismatches'] += int(mismatch.sum().item())
                row['raw_score_max_abs'] = max(row['raw_score_max_abs'], (native.float()-raw.float()).abs().max().item())
                for i in torch.nonzero(mismatch).reshape(-1).tolist():
                    if len(row['examples']) < 6:
                        row['examples'].append({'decision_id':event['decision_id'], 'score_sequence':v['scoring_batch_id'], 'candidate':i, 'cpu':native[i].item(), 'recorded_gpu':raw[i].item()})
                row['batches'] += 1; row['candidates'] += len(actions)
                row['dtypes'] = sorted(set(row['dtypes'] + [str(raw.dtype)]))
    assert not scores
    result['paths'].append(row)
    print(json.dumps(row), flush=True)
result['cuda_initialized'] = torch.cuda.is_initialized()
(P/'cpu-gpu-boundary-readonly-v1.json').write_text(json.dumps(result,indent=2)+'\n')
