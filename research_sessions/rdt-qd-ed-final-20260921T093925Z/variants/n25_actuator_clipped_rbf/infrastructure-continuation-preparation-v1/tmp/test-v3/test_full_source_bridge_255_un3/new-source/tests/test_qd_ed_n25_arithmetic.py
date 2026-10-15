import copy
from pathlib import Path
import pytest
import torch
from test_rdt_steer import _patch_core_imports,stub_steer,stub_adapter
from test_n25_clipped_rbf import native_adapter


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('case',['strict_interior','exact_boundary','mixed_saturation','distinct_saturated',
                                'coincident_saturated','coincident_interior'])
def test_independent_native_reference_fixed_cases(stub_steer,stub_adapter,monkeypatch,dtype,case):
    from core.qd_actuator_clipped_rbf import clipped_rbf_gradient,applied_evidence
    from scripts.qd_ed_n25_reference import fixed_case,reconstruct,exact,audit_witness
    from scripts.qd_ed_audit_backend import create_backend
    calls=native_adapter(stub_adapter,monkeypatch)
    # Fixed prospective origin, not observed empirical state.
    from types import SimpleNamespace
    x,origins,before=fixed_case(case,dtype)
    monkeypatch.setattr(stub_adapter,'get_ee_pose_world',lambda:SimpleNamespace(position=origins[0].numpy()))
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda v:v,sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    capture={};grad,row=clipped_rbf_gradient(x,project=stub_steer._rdt_sample_to_trajectory_3d,horizon=8,capture_out=capture)
    expected=reconstruct(x[:,:8,(39,40,41)],origins)
    for name in ['cast_origins','projected_xyz','gradient_before','gradient_after']:
        assert exact(capture[name],expected[name]),(case,str(dtype),name)
    operand=-1.*20.*grad[:,:8,(39,40,41)]
    after=before.clone();after+=operand
    capture.update(update_operand=operand,model_output_before=before,model_output_after=after)
    applied_evidence(row,masked=grad,update=operand,phase='initial',iteration=-1,step=0,timestep=4)
    metadata={'call':row}
    assert audit_witness(capture,metadata,create_backend('cpu'))['accepted']
    if case=='strict_interior':
        old=stub_steer._compute_diversity_gradient(x)
        raw=reconstruct(x[:,:8,(39,40,41)],origins,clipped=False)
        assert exact(old,grad) and exact(raw['gradient_after'],capture['gradient_after'])
    mask=(x[:,:8,39:42]<=-1)|(x[:,:8,39:42]>=1)
    assert torch.count_nonzero(capture['gradient_before'][mask])==0
    wrong=copy.deepcopy(capture)
    wrong['model_output_after'][0,0,0]=torch.nextafter(wrong['model_output_after'][0,0,0],torch.tensor(float('inf'),dtype=dtype))
    with pytest.raises(ValueError,match='addition differs'):audit_witness(wrong,metadata,create_backend('cpu'))
    for field in ['projected_xyz','gradient_before','gradient_after','update_operand']:
        wrong=copy.deepcopy(capture)
        wrong[field][0,0,0]=torch.nextafter(wrong[field][0,0,0],torch.tensor(float('inf'),dtype=dtype))
        with pytest.raises(ValueError):audit_witness(wrong,metadata,create_backend('cpu'))
