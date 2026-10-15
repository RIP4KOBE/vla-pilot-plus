"""Independent native arithmetic and sparse allocation audit.

Runs on the explicitly supplied device in the metered worker, using the bound
PyTorch build. CPU fixtures use CPU; they never attest CUDA. No policy, provider,
proposal, or archive implementation is imported or invoked here.
"""
from collections import defaultdict
import hashlib
import math
import torch
from scripts.qd_ed_n31_reference import require, same
from scripts.qd_ed_n30_native import provider_target


def verify_scores(events, *, device):
    device=torch.device(device)
    byseq={e['sequence']:e for e in events}
    contexts={e['decision_id']:e for e in events if e['event']=='decision_context'}
    related=defaultdict(list)
    for event in events:
        if event['event'] in ('provider_return','effective_quality','scoring_aggregate'):
            related[(event['event'],event['values']['scoring_batch_id'])].append(event['values'])
    batches=rows=0
    for event in events:
        if event['event']!='scoring_inputs':continue
        v=event['values'];ctx=contexts[event['decision_id']]
        binding=provider_target(ctx)
        require(binding is not None,'native arithmetic needs recognized frozen provider')
        samples=v['samples'].to(device);actual=v['projected_xyz']
        origins=v['projection_origin_sequences']
        projected=[]
        for i,seq in enumerate(origins):
            start=byseq[seq]['values']['source_eef_position'].to(device=device,dtype=samples.dtype)
            # One T x 3 scan per candidate, exactly the deployed operation shape.
            delta=samples[i,:8,39:42]*.01
            projected.append(torch.cat((start[None],start+torch.cumsum(delta,dim=0))))
        projection=torch.stack(projected)
        require(same(projection.cpu(),actual),'native projection recomputation')
        used=projection[:,1:8]
        require(same(used.cpu(),v['provider_input_xyz']),'native provider slice')
        keypoints=v['keypoints'].to(device)
        target=keypoints[binding[0]]
        weights=torch.where(torch.arange(7,device=device)>=int(.7*7),
                            torch.tensor(3.,device=device),torch.tensor(1.,device=device))
        weights=weights/weights.sum()
        returns=related[('provider_return',event['sequence'])]
        require(len(returns)==len(samples),'native provider return coverage')
        stored=torch.zeros(len(samples),dtype=samples.dtype,device=device)
        for i in range(len(samples)):
            distances=torch.norm(used[i][None]-target,dim=-1)
            raw=(-(distances**2*weights).sum(dim=1)).mean()
            observed=returns[i]
            require(observed['candidate_index']==i and observed['provider_ordinal']==0
                and torch.is_tensor(observed['result']) and same(raw.cpu(),observed['result']), 'native frozen provider recomputation')
            stored[i]=raw
        effective=related[('effective_quality',event['sequence'])];aggregate=related[('scoring_aggregate',event['sequence'])]
        require(len(effective)==len(aggregate)==1 and same(stored.cpu(),effective[0]['quality'])
            and same((-stored).cpu(),effective[0]['costs'])
            and same(stored.cpu(),aggregate[0]['aggregate_before_reward_mode']), 'native aggregate/cost recomputation')
        batches+=1;rows+=len(samples)
    return {'device':str(device),'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,
        'torch_build':torch.__config__.show(),'batches':batches,'rows':rows,
        'kind':'native_recomputation','gpu_attested':device.type=='cuda'}


def verify_assignment(actions, keypoints, update, initial, *, device,
                      origin_events, canonical_event, update_event, observed_eef):
    device=torch.device(device)
    geometry=update['geometry']
    origins=geometry['source_origins'];require(len(origins)==16,'archive projection origins')
    iteration=update['iter_idx']
    require(geometry['iter_idx']==iteration and canonical_event['values']['iter_idx']==iteration,
            'archive projection iteration')
    sequences=geometry['projection_origin_sequences']
    require(len(origin_events)==len(sequences)==len(geometry['cast_origins'])==16
        and sequences==[e['sequence'] for e in origin_events]
        and len(set(sequences))==16 and sequences==sorted(sequences), 'ordered archive projection origin coverage')
    require(canonical_event['sequence']<sequences[0] and sequences[-1]<update_event['sequence'],
            'archive projection origin timing')
    for i,event in enumerate(origin_events):
        values=event['values']
        require(event['event']=='projection_origin' and all(event[k]==canonical_event[k]==update_event[k]
            for k in ('episode','decision_id','global_step','reset_sequence')),
            'archive projection decision identity')
        require(values['n36_descriptor_identity']=={'iter_idx':iteration,'candidate_index':i,
            'occurrence_id':(iteration+1)*16+i}, 'archive projection candidate identity')
        require(same(origins[i],values['source_eef_position']), 'archive exact raw origin bytes')
        # The boundary packet is independently joined to the preceding physical
        # observation by the caller. Absence is not permission to invent an anchor.
        require(observed_eef is not None and same(origins[i],observed_eef),
                'archive raw origin cached physical observation')
        require(same(values['action_sequence'],actions[i,:8,[39,40,41,42,43,44,10]])
            and same(values['cast_eef_start'],geometry['cast_origins'][i])
            and same(values['projected_xyz'],geometry['projected_xyz'][i]),
            'archive actual action/cast/projection evidence')
    native=actions.to(device);projected=[]
    for i,origin in enumerate(origins):
        start=origin.to(device=device,dtype=native.dtype)
        require(same(start.cpu(),geometry['cast_origins'][i]), 'archive native origin cast')
        projected.append(torch.cat((start[None],start+torch.cumsum(native[i,:8,39:42]*.01,dim=0))))
    xyz=torch.stack(projected);points=keypoints.to(device)
    require(same(xyz.cpu(),geometry['projected_xyz']),'actual archive projection recomputation')
    desc=xyz[:,-1,:2].float()-points.reshape(-1)[:2].float()[None]
    require(same(desc.cpu(),update['descriptors']),'independent native descriptor')
    if initial:
        q=torch.quantile(desc,torch.tensor([.05,.95],device=device),dim=0)
        span=q[1]-q[0];lo=q[0]-.1*span;hi=q[1]+.1*span
        small=hi-lo<.08
        if bool(small.any()):
            center=torch.quantile(desc,.5,dim=0)
            lo=torch.where(small,center-.04,lo);hi=torch.where(small,center+.04,hi)
        require(same(lo.cpu(),update['bounds_lo']) and same(hi.cpu(),update['bounds_hi']), 'independent initial native bounds')
    lo=update['bounds_lo'].to(device);hi=update['bounds_hi'].to(device)
    normalized=(desc-lo)/(hi-lo)
    x=torch.floor(normalized[:,0]*4).long().clamp(0,3)
    y=torch.floor(normalized[:,1]*4).long().clamp(0,3)
    require(update['cell_ids'].dtype==torch.int64 and torch.equal((4*y+x).cpu(),update['cell_ids']), 'independent native cells')


def verify_parents(archive, visits, allocation, cfg, identity, iteration):
    cells=sorted(archive)
    material=f"{int(cfg['shuffle_seed'])}:{identity['episode']}:{identity['step']}:{iteration}"
    seed=int.from_bytes(hashlib.sha256(material.encode('ascii')).digest()[:8],'big')&((1<<63)-1)
    generator=torch.Generator(device='cpu').manual_seed(seed)
    permutation=torch.randperm(len(cells),generator=generator).tolist()
    rank={cells[offset]:i for i,offset in enumerate(permutation)}
    weights={c:(float(visits[c])+1.)**(-cfg['qd_sparse_exponent']) for c in cells}
    exact={c:16*weights[c]/sum(weights.values()) for c in cells}
    slots={c:int(math.floor(exact[c])) for c in cells}
    for c in sorted(cells,key=lambda c:(-(exact[c]-slots[c]),rank[c]))[:16-sum(slots.values())]:slots[c]+=1
    expected=[c for c in cells for _ in range(slots[c])]
    require(allocation['parent_cell_ids'].tolist()==expected
        and allocation['slot_counts']=={str(c):slots[c] for c in cells}
        and allocation['sparse_slot_counts']=={str(c):slots[c] for c in cells}
        and allocation['weights']=={str(c):weights[c] for c in cells},'independent sparse parent visits/weights/ties')
