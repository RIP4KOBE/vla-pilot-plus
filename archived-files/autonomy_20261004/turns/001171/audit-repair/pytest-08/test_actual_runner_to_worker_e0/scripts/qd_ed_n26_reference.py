"""Independent, native-dtype N26 arithmetic; never imports production RBF helper."""
import torch

from scripts.qd_ed_n25_reference import CASES, DTYPES, XYZ, ReferenceClip, require, exact
from scripts.qd_ed_n25_reference import fixed_case as old_fixed_case

LAYOUTS = {
    'contiguous': ((8192,128,1),0),
    'transpose': ((8192,1,64),0),
    'model_slice': ((8576,128,1),384),
}


def with_layout(values, layout):
    require(layout in LAYOUTS, 'unknown fixed input layout')
    if layout == 'contiguous': result=values.contiguous()
    elif layout == 'transpose': result=values.transpose(1,2).contiguous().transpose(1,2)
    else:
        backing=torch.zeros((16,67,128),device=values.device,dtype=values.dtype)
        result=backing[:,-64:];result.copy_(values)
    require(tuple(result.stride())==LAYOUTS[layout][0] and result.storage_offset()==LAYOUTS[layout][1],
            'synthetic reference layout construction differs')
    return result


def layout_name(stride):
    require(isinstance(stride,(list,tuple)) and len(stride)==3 and all(type(x) is int for x in stride),
            'input stride metadata missing')
    names=[name for name,(expected,_) in LAYOUTS.items() if tuple(stride)==expected]
    require(len(names)==1,'unsupported live input stride')
    return names[0]


def fixed_case(name,dtype,layout):
    values,origins,_=old_fixed_case(name,dtype)
    return with_layout(values,layout),origins


def reconstruct(input_xyz,origins,*,input_stride,clipped=True):
    require(tuple(input_xyz.shape)==(16,8,3) and input_xyz.dtype in DTYPES
        and tuple(origins.shape)==(16,3) and bool(torch.isfinite(input_xyz).all())
        and bool(torch.isfinite(origins).all()),'shape/dtype/nonfinite input')
    device=input_xyz.device;dtype=input_xyz.dtype
    with torch.enable_grad():
        latent=torch.zeros((16,64,128),dtype=dtype,device=device)
        latent[:,:8,XYZ]=input_xyz.detach()
        latent=with_layout(latent,layout_name(input_stride)).requires_grad_(True)
        proposed=latent.clone()
        if clipped:proposed[:,:8,XYZ]=ReferenceClip.apply(latent[:,:8,XYZ])
        trajectory=[]
        for candidate in range(16):
            # Independently retain original projector's seven-action advanced gather.
            actions=proposed[candidate:candidate+1,:8,(39,40,41,42,43,44,10)]
            start=origins[candidate].to(device=device,dtype=dtype)
            deltas=actions[0,:,:3]*.01
            trajectory.append(torch.cat([start[None,:],start+torch.cumsum(deltas,dim=0)],dim=0)[None,:,:])
        paths=torch.cat(trajectory,dim=0)
        flat=paths[:,1:,:3].reshape(16,-1)
        differences=flat.unsqueeze(1)-flat.unsqueeze(0)
        squares=torch.sum(differences**2,dim=2)
        diagonal=~torch.eye(16,dtype=torch.bool,device=device)
        distance=torch.sqrt(squares+1e-6)
        objective=((1./(distance+1e-6))*diagonal.float()).sum()
        gradient=torch.autograd.grad(objective,latent,create_graph=False,allow_unused=False)[0]
        require(bool(torch.isfinite(gradient).all()),'nonfinite gradient')
        norm=torch.norm(gradient).item()
        normalized=gradient/(norm+1e-8) if norm>1e-8 else gradient
    return {'cast_origins':paths[:,0,:].detach(),'projected_xyz':paths[:,1:,:].detach(),
        'gradient_before':gradient[:,:8,XYZ].detach(),
        'gradient_after':normalized[:,:8,XYZ].detach(),'norm':norm}


def audit_witness(tensors,metadata,backend):
    native={k:backend.native(v) for k,v in tensors.items()}
    call=metadata['call']
    require(call.get('input_source')=='model_output_sample_v1' and call.get('prediction_type')=='sample'
        and call.get('input_binding')=='same_forward_unmodified_model_output'
        and call.get('model_jacobian_used') is False, 'N26 clean input semantics missing')
    require(exact(native['input_xyz'],native['model_output_before']), 'N26 clean input/model-before bytes differ')
    expected=reconstruct(native['input_xyz'],native['source_origins'],input_stride=call.get('input_stride'))
    for name in ('cast_origins','projected_xyz','gradient_before','gradient_after'):
        require(exact(native[name],expected[name]),'byte mismatch '+name)
    call=metadata['call']
    require(call['gradient_before_normalization']['norm']==expected['norm'],'normalization scalar differs')
    require(native['model_output_before'].shape==(16,8,3),'model slice shape differs')
    operand=-1.*20.*expected['gradient_after'].to(dtype=native['model_output_before'].dtype)
    require(exact(native['update_operand'],operand),'update operand differs')
    require(exact(native['model_output_after'],native['model_output_before']+operand),'actual output addition differs')
    return {'accepted':True,'dtype':str(native['input_xyz'].dtype),'comparison':'native contiguous uint8; zero tolerance',
            'candidate_rows':16,'input_layout':layout_name(call['input_stride']),
            'live_storage_offset_observed':False,'clean_input_binding_verified':True,'zero_gradient':bool(torch.count_nonzero(expected['gradient_after'])==0)}
