#!/usr/bin/env python3
"""Compare first-chunk tensors with historical C0 without altering any rollout."""
import argparse
import json
from pathlib import Path
import torch

from c0_trace_replay import STUDY, ORIGINAL_JOB, digest


def tensor_equal(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a,torch.Tensor) or isinstance(b,torch.Tensor):
        return isinstance(a,torch.Tensor) and isinstance(b,torch.Tensor) and a.dtype==b.dtype and torch.equal(a,b)
    if isinstance(a,(list,tuple)) or isinstance(b,(list,tuple)):
        return type(a) is type(b) and len(a)==len(b) and all(tensor_equal(x,y) for x,y in zip(a,b))
    return type(a) is type(b) and a==b


def compare(output, reference):
    result=[]
    for task in range(10):
        relative=Path(f'eds_eval/qualitative/episode_{task:03d}/chunk_000000')
        a_path=output/relative/'tensors/mechanism_trace.pt'
        b_path=reference/relative/'tensors/mechanism_trace.pt'
        if not a_path.exists() or not b_path.exists():
            result.append(dict(task=task,available=False))
            continue
        a=torch.load(a_path,map_location='cpu',weights_only=False)
        b=torch.load(b_path,map_location='cpu',weights_only=False)
        aa={(s['stage'],s['iter_idx']):s for s in a['stages']}
        bb={(s['stage'],s['iter_idx']):s for s in b['stages']}
        stage_rows=[]
        for key in sorted(set(aa)|set(bb)):
            fields={f:tensor_equal(aa.get(key,{}).get(f),bb.get(key,{}).get(f))
                    for f in ('actions','trajectories','rewards','costs','parent_indices','parent_probabilities')}
            stage_rows.append(dict(stage=key[0],iteration=key[1],available=key in aa and key in bb,**fields))
        csv=relative/'single_step_inner_loop/single_step_particles.csv'
        result.append(dict(task=task,available=True,keypoints_equal=tensor_equal(a['keypoints'],b['keypoints']),
            scoring_keypoint_indices_equal=a['scoring_keypoint_indices']==b['scoring_keypoint_indices'],
            first_particle_csv_equal=(output/csv).exists() and (reference/csv).exists() and digest(output/csv)==digest(reference/csv),
            all_recorded_initial_tensors_equal=all(all(v for k,v in row.items() if k not in ('stage','iteration')) for row in stage_rows),
            stages=stage_rows))
    return dict(output=str(output),reference=str(reference),
        note='First-chunk comparison only. Missing first ED chunk can reflect an online Stage decision; RNG restoration is separately audited.',tasks=result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    parser.add_argument('--reference',type=Path,default=ORIGINAL_JOB.parent)
    args=parser.parse_args()
    folder=STUDY/'artifacts/stage_closed_loop_20260929/runs'/args.name
    result=compare(folder/'output',args.reference)
    (folder/'initialization-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    for row in result['tasks']:
        print({k:v for k,v in row.items() if k!='stages'})
