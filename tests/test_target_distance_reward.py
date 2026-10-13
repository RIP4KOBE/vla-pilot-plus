import torch
from core.target_distance_reward import audit, reference


def reaching(kp,x):
    t=x.shape[1];weights=torch.where(torch.arange(t)>=int(.7*t),3.,1.);weights/=weights.sum()
    return -(torch.norm(x-kp[0],dim=-1).square()*weights).sum(-1).mean()


def zero(kp,x):return torch.tensor(0.)


def test_original_norm_squared_is_consistent_with_the_contract():
    rng=torch.get_rng_state().clone()
    result=audit({1:[reaching],2:[zero]},[[.1,.2,.3],[.3,.4,.5]])
    assert result['valid'] and result['probe_count']==64
    assert torch.equal(rng,torch.get_rng_state())


def test_xy_anisotropy_is_not_silently_accepted_as_c0():
    def changed(kp,x):
        shifted=x.clone();shifted[...,:2]=kp[0,:2]+2*(x[...,:2]-kp[0,:2])
        return reaching(kp,shifted)
    result=audit({1:[changed],2:[zero]},[[.1,.2,.3],[.3,.4,.5]])
    assert not result['valid'] and result['reason']=='formula_drift'


def test_wrong_object_and_nonzero_transport_reward_fail_contract():
    kp=[[.1,.2,.3],[.3,.4,.5]]
    assert not audit({1:[lambda k,x:reference(k,x,1)],2:[zero]},kp)['valid']
    assert not audit({1:[reaching],2:[lambda k,x:torch.tensor(1.)]},kp)['valid']


def test_hardcoded_initial_target_fails_translated_scene_check():
    def hardcoded(kp,x):
        return reaching(torch.tensor([[.1,.2,.3]]),x)
    assert not audit({1:[hardcoded],2:[zero]},[[.1,.2,.3],[.3,.4,.5]])['valid']


def test_rejected_stochastic_reward_cannot_pollute_policy_rng():
    import random
    import numpy as np
    p,n,t=random.getstate(),np.random.get_state(),torch.get_rng_state().clone()
    def stochastic(kp,x):
        random.random();np.random.random()
        return torch.rand(())
    result=audit({1:[stochastic],2:[zero]},[[.1,.2,.3],[.3,.4,.5]])
    assert not result['valid'] and result['reason']=='non_deterministic'
    assert p==random.getstate() and np.array_equal(n[1],np.random.get_state()[1])
    assert n[2:]==np.random.get_state()[2:] and torch.equal(t,torch.get_rng_state())


def test_task_gate_resolves_current_target_and_retains_rejected_evidence(tmp_path):
    import json
    import pytest
    from types import SimpleNamespace
    from core.target_distance_reward import validate_task
    runner=SimpleNamespace(adapter=SimpleNamespace(get_task_description=lambda:'pick up the bbq sauce and place it in the basket'),
        keypoint_id_to_object={0:'basket_1_main',1:'bbq_sauce_1_main'},
        guidance_fns={1:[lambda k,x:reference(k,x,1)],2:[zero]})
    assert validate_task(runner,[[0.,0.,0.],[.1,.2,.3]],tmp_path)['target_index']==1
    runner.guidance_fns={1:[reaching],2:[zero]}
    with pytest.raises(ValueError,match='violates'):
        validate_task(runner,[[0.,0.,0.],[.1,.2,.3]],tmp_path)
    saved=json.loads((tmp_path/'vlm_agent/target_distance_reward.json').read_text())
    assert not saved['valid'] and saved['target_index']==1


def test_float32_equivalent_rewrite_is_not_execution_precision_equivalent():
    def rewritten(kp,x):
        t=x.shape[1];w=torch.where(torch.arange(t)>=int(.7*t),3.,1.);w/=w.sum()
        return -((x-kp[0]).square().sum(-1)*w).sum(-1).mean()
    result=audit({1:[rewritten],2:[zero]},[[.1,.2,.3],[.3,.4,.5]])
    assert not result['valid']
    assert all(x['consistent'] for x in result['checks'] if x['dtype']=='torch.float32')
    assert any(not x['consistent'] for x in result['checks'] if x['dtype']=='torch.bfloat16')
