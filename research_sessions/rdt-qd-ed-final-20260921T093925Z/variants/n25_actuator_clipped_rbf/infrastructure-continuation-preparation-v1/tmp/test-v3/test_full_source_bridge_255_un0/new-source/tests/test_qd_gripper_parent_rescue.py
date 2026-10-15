import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from core.qd_gripper_parent_rescue import CanonicalCloseCache, full_close, MODE
from core.qd_ed import QDArchive, allocate_parent_slots, fingerprint_action


def example(dtype=torch.float32):
    actions = torch.zeros(16,64,128,dtype=dtype)
    actions[:, :8, 10] = -1
    actions[0, :8, 10] = 1
    costs = torch.arange(16,dtype=dtype)
    descriptors = torch.full((16,2), .25)
    bounds = (torch.zeros(2),torch.ones(2))
    return dict(iteration=-1,actions=actions,costs=costs,quality=-costs,raw=-costs-1,
                descriptors=descriptors,cells=torch.full((16,),5,dtype=torch.long),
                context={"stage":1,"reset":0,"target":"a"},bounds=bounds)


def allocation(data):
    archive = QDArchive(grid_shape=(4,4))
    actions = data['actions'].clone(); actions[:, :8,10] = -1
    archive.update(actions=actions,rewards=data['quality'],costs=data['costs'],
        descriptors=data['descriptors'],cell_ids=data['cells'],raw_rewards=data['raw'],source_iter=-1)
    a=allocate_parent_slots(archive,population_size=16,sampling='sparse_priority',sparse_exponent=1.,
        run_seed=0,episode=0,global_step=0,iter_idx=0)
    return a,torch.stack([archive.entries[int(c)].descriptor_xy_m for c in a.parent_cell_ids])


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_rescue_exact_one_slot_native_dtype_and_no_rng(dtype):
    data=example(dtype);cache=CanonicalCloseCache(data['context'],data['bounds'])
    update=cache.observe(**data);assert update['cache']['row']==0
    a,d=allocation(data);a=replace(a,parent_costs=a.parent_costs.clone(),parent_rewards=a.parent_rewards.clone())
    a.parent_costs[3]=a.parent_costs[5]=8;a=replace(a,parent_rewards=-a.parent_costs)
    state=torch.random.get_rng_state().clone()
    out=cache.supply(a,d,iteration=0,context=data['context'],bounds=data['bounds'])
    assert out.slot==3 and out.costs.dtype==torch.float32 and out.actions.dtype==dtype
    assert torch.equal(out.actions[3],data['actions'][0]) and out.raw[3]==data['raw'][0]
    for old,new in ((a.parent_actions,out.actions),(a.parent_costs,out.costs),(a.parent_rewards,out.quality),
                    (a.parent_raw_rewards,out.raw),(a.parent_cell_ids,out.cells),(d,out.descriptors)):
        keep=[i for i in range(16) if i!=3];assert torch.equal(old[keep],new[keep])
    assert torch.equal(state,torch.random.get_rng_state())


@pytest.mark.parametrize('kind',['empty','already_present'])
def test_inactive_returns_original_objects(kind):
    data=example();cache=CanonicalCloseCache(data['context'],data['bounds'])
    if kind=='empty': data['actions'][:,:8,10]=-1
    cache.observe(**data);a,d=allocation(data)
    if kind=='already_present':
        a.parent_actions[4,:8,10]=1
        a=replace(a,parent_fingerprints=tuple(fingerprint_action(r) for r in a.parent_actions))
    out=cache.supply(a,d,iteration=0,context=data['context'],bounds=data['bounds'])
    assert out.slot is None and out.actions is a.parent_actions and out.costs is a.parent_costs
    assert out.quality is a.parent_rewards and out.raw is a.parent_raw_rewards and out.cells is a.parent_cell_ids


def test_earliest_birth_tie_and_no_recorder_dependency():
    data=example();data['actions'][1,:8,10]=1;data['costs'][1]=data['costs'][0];data['quality']=-data['costs']
    caches=[CanonicalCloseCache(data['context'],data['bounds']) for _ in range(2)]
    for i,cache in enumerate(caches):
        cache.observe(**data,**({'canonical_sequence':9,'scoring_batch_id':3,'decision_id':'d'} if i else {}))
        cache.observe(**dict(data,iteration=0))
        assert cache.entry['iteration']==-1 and cache.entry['row']==0
    a,d=allocation(data)
    left,right=[c.supply(a,d,iteration=1,context=data['context'],bounds=data['bounds']) for c in caches]
    assert torch.equal(left.actions,right.actions)
    assert CanonicalCloseCache(data['context'],data['bounds']).entry is None


@pytest.mark.parametrize('fault',['future','duplicate','context_stage','context_reset','context_target','bounds',
                                 'quality','raw_nan','cell','descriptor','nonfinite'])
def test_invalid_source_fails_closed(fault):
    data=example();cache=CanonicalCloseCache(data['context'],data['bounds'])
    if fault=='future':data['iteration']=0
    if fault=='duplicate':cache.observe(**data)
    if fault.startswith('context_'):data['context']={**data['context'],fault[8:]:'changed'}
    if fault=='bounds':data['bounds']=(torch.zeros(2),torch.ones(2)*2)
    if fault=='quality':data['quality']=data['quality']+1
    if fault=='raw_nan':data['raw'][0]=float('nan')
    if fault=='cell':data['cells'][0]=4
    if fault=='descriptor':data['descriptors'][0]=.9
    if fault=='nonfinite':data['actions'][0,10,3]=float('nan')
    with pytest.raises(ValueError):cache.observe(**data)


def test_provider_default_omission_and_n24_profile_closure():
    from core.eds_eval_metrics import EDSChunkMetrics
    from scripts import qd_ed_final_runner as r
    metrics=EDSChunkMetrics().to_jsonable()
    assert 'qd_quality_mode' not in metrics and not any(k.startswith('qd_gripper_rescue_') for k in metrics)
    root=Path(__file__).resolve().parents[1]
    parent=json.loads((root/'configs/qd_ed_final/candidate_n23.json').read_text())
    candidate=json.loads((root/'configs/qd_ed_final/candidate_n24.json').read_text())
    assert {k:v for k,v in candidate['profile'].items() if k!='qd_gripper_rescue_mode'}==parent['profile']
    assert candidate['profile']['qd_gripper_rescue_mode']==MODE
    base=r.read_json(root/'configs/qd_ed_final/baseline_profiles.json')['profiles']['Q0']
    old=r.expand_candidate('N23',parent,base)
    new=r.expand_candidate('N24',candidate,base)
    assert new['resolved_eds_config']=={**old['resolved_eds_config'],'qd_gripper_rescue_mode':MODE}
    assert {k:v for k,v in new['static_override_values'].items() if k!='main.eds_config.qd_gripper_rescue_mode'}==old['static_override_values']
    for fault in ('parent','mode','other'):
        bad=copy.deepcopy(candidate)
        if fault=='parent':bad['parent_candidate']['sha256']='0'*64
        if fault=='mode':bad['profile']['qd_gripper_rescue_mode']='none'
        if fault=='other':bad['profile']['temperature']=.2
        with pytest.raises(r.GateError):r.expand_candidate('N24',bad,base)
