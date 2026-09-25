#!/usr/bin/env python3
"""Read-only 4x2x2 direction/radius/height cell replay on N7 Dev pools."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch

ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'artifacts'
REPORT=ART/'continuation_20260925/n7-dev-v1/full-dev-report-v1.json'
OUT=ART/'continuation_20260925/n8-prerequisite-readonly-v1.json'


def bounds(values):
    q=torch.quantile(values,torch.tensor([.05,.95]),dim=0)
    span=q[1]-q[0]
    lo,hi=q[0]-.1*span,q[1]+.1*span
    small=hi-lo<.08
    median=torch.quantile(values,.5,dim=0)
    return torch.where(small,median-.04,lo),torch.where(small,median+.04,hi)


def bins(values,lo,hi,n):
    return torch.floor((values-lo)/(hi-lo)*n).long().clamp(0,n-1)


def pair_counts(reference,proposed):
    resolved=conflated=0
    for i in range(16):
        for j in range(i+1,16):
            resolved+=int(reference[i]==reference[j] and proposed[i]!=proposed[j])
            conflated+=int(reference[i]!=reference[j] and proposed[i]==proposed[j])
    return resolved,conflated


def main():
    if OUT.exists():
        raise SystemExit(f'immutable result exists: {OUT}')
    report=json.loads(REPORT.read_text())
    assert report['decision']=='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
    rows=[]
    for cell in report['cells']:
        folder=ART/'attempts'/cell['accepted_attempt_id']/'eds_eval/decision_evidence/episode_000'
        for line in (folder/'events.jsonl').open():
            summary=json.loads(line)
            if not any(e['event']=='qd_descriptor_assignment' for e in summary['events']):
                continue
            bundle=folder/summary['bundle']
            assert hashlib.sha256(bundle.read_bytes()).hexdigest()==summary['sha256']
            events=torch.load(bundle,map_location='cpu',weights_only=True)['events']
            contexts=[e for e in events if e['event']=='decision_context']
            assignments=[e for e in events if e['event']=='qd_descriptor_assignment']
            scoring={e['sequence']:e for e in events if e['event']=='scoring_inputs'}
            assert len(contexts)==1 and len(assignments)==11
            assert [e['values']['iter_idx'] for e in assignments]==list(range(-1,10))
            radial_bounds=height_bounds=None
            totals={'n7_same_cell_n8_split_pairs':0,'n7_different_cell_n8_conflated_pairs':0,
                    'n6_same_cell_n8_split_pairs':0,'n6_different_cell_n8_conflated_pairs':0}
            for assignment in assignments:
                v=assignment['values']
                source=scoring[v['scoring_batch_id']]['values']
                assert source['scoring_scope']['iter_idx']==v['iter_idx']
                xyz=source['projected_xyz'][:,8,:3].float()
                target=source['keypoints'][0].float()
                assert xyz.shape==(16,3) and target.shape==(3,)
                delta=xyz-target
                radius=torch.sqrt(delta[:,0].square()+delta[:,1].square())
                height=delta[:,2]
                quadrant=2*(delta[:,0]>=0).long()+(delta[:,1]>=0).long()
                if radial_bounds is None:
                    radial_bounds=bounds(radius.unsqueeze(1))
                    height_bounds=(v['bounds_lo'][1].float(),v['bounds_hi'][1].float())
                    expected_height=bounds(height.unsqueeze(1))
                    assert abs(height_bounds[0]-expected_height[0][0])<=1e-6
                    assert abs(height_bounds[1]-expected_height[1][0])<=1e-6
                radial2=bins(radius,*radial_bounds,2)
                height2=bins(height,*height_bounds,2)
                proposed=(quadrant+4*radial2+8*height2).tolist()
                n7=(quadrant+4*bins(height,*height_bounds,4)).tolist()
                assert n7==v['cell_ids'].tolist()
                n6=(bins(radius,*radial_bounds,4)+4*bins(height,*height_bounds,4)).tolist()
                a,b=pair_counts(n7,proposed)
                c,d=pair_counts(n6,proposed)
                totals['n7_same_cell_n8_split_pairs']+=a
                totals['n7_different_cell_n8_conflated_pairs']+=b
                totals['n6_same_cell_n8_split_pairs']+=c
                totals['n6_different_cell_n8_conflated_pairs']+=d
            rows.append({'task_id':cell['task_id'],'global_step':contexts[0]['global_step'],**totals})
    assert rows
    summary={key:sum(x[key] for x in rows) for key in totals}
    payload={'schema':'n8-prerequisite-readonly-v1',
        'scope':'SHA-verified already-exposed N7 Dev native canonical candidate pools; no unexecuted candidate outcome',
        'source_report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        'proposed_cell_rule':'quadrant4 + 4*radial2 + 8*height2; fixed initial quantile bounds; 16 capacity-one cells',
        'decisions':len(rows),
        'n7_resolution_witness_decisions':sum(x['n7_same_cell_n8_split_pairs']>0 for x in rows),
        'n6_resolution_witness_decisions':sum(x['n6_same_cell_n8_split_pairs']>0 for x in rows),
        **summary,'rows':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps({k:v for k,v in payload.items() if k!='rows'}))
    print('path',OUT,'sha256',hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__=='__main__':
    main()
