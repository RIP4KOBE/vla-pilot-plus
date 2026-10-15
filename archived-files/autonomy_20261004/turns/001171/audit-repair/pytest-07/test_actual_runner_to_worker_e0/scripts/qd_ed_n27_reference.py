"""Independent N27 native feasible-ray oracle; never imports production helper."""
import torch
from scripts.qd_ed_n26_reference import reconstruct,require,exact,CASES,DTYPES,LAYOUTS,layout_name,fixed_case,with_layout


def reconstruct_update(before,operand):
    require(before.shape==operand.shape==(16,8,3) and before.dtype==operand.dtype
        and before.dtype in DTYPES and before.device==operand.device
        and bool(torch.isfinite(before).all()) and bool(torch.isfinite(operand).all()),'N27 reference inputs differ')
    rows=[];alphas=[]
    for original,proposed in zip(before,operand):
        x=original.detach().float();v=proposed.detach().float()
        active=v!=0
        require(not bool((active&((x<=-1)|(x>=1))).any()),'N27 reference support violation')
        choices=[torch.ones((),device=x.device,dtype=torch.float32)]
        positive=v>0;negative=v<0
        if bool(positive.any()):choices.append(((1.-x[positive])/v[positive]).amin())
        if bool(negative.any()):choices.append(((-1.-x[negative])/v[negative]).amin())
        alpha=torch.stack(choices).amin()
        translated=x+alpha*v
        bounded=torch.maximum(torch.minimum(translated,torch.ones_like(x)),-torch.ones_like(x)).to(original.dtype)
        rows.append(torch.where(active,bounded,original.detach()));alphas.append(alpha)
    return torch.stack(rows),torch.stack(alphas)


def audit_witness(tensors,metadata,backend):
    native={k:backend.native(v) for k,v in tensors.items()};call=metadata['call']
    require(call.get('schema')=='n27-rbf-call-summary-v1' and call.get('source')=='core.qd_feasible_ray_rbf:feasible_ray_v1'
        and call.get('input_source')=='model_output_sample_v1' and call.get('prediction_type')=='sample'
        and call.get('input_binding')=='same_forward_unmodified_model_output' and call.get('model_jacobian_used') is False
        and call.get('update_operand_semantics')=='unconstrained_native_proposal_before_feasible_ray', 'N27 clean/proposed semantics absent')
    require(exact(native['input_xyz'],native['model_output_before']),'N27 clean input/model-before bytes differ')
    expected=reconstruct(native['input_xyz'],native['source_origins'],input_stride=call.get('input_stride'))
    for name in ('cast_origins','projected_xyz','gradient_before','gradient_after'):
        require(exact(native[name],expected[name]),'N27 geometry byte mismatch '+name)
    require(call['gradient_before_normalization']['norm']==expected['norm'],'N27 gradient norm differs')
    operand=-1.*20.*expected['gradient_after'].to(dtype=native['model_output_before'].dtype)
    require(exact(native['update_operand'],operand),'N27 proposed operand differs')
    after,alpha=reconstruct_update(native['model_output_before'],operand)
    require(exact(native['model_output_after'],after),'N27 actual assigned prefix differs')
    declared=torch.tensor(call['alpha'],device=alpha.device,dtype=torch.float32)
    require(exact(alpha,declared),'N27 native FP32 alpha differs')
    before=native['model_output_before'];delta=after.float()-before.float();active=operand!=0
    measured={'limited_rows':int((alpha<1).sum().item()),
        'before_outside_components':int(((before<-1)|(before>1)).sum().item()),
        'after_outside_components':int(((after<-1)|(after>1)).sum().item()),
        'realized_nonzero_delta_components':int(torch.count_nonzero(delta).item()),
        'realized_delta_norm_fp32':float(torch.norm(delta).item())}
    require(all(call.get(k)==v for k,v in measured.items()),'N27 realized update statistics differ')
    require(exact(after[~active],before[~active]) and call.get('zero_update_bytes_preserved') is True,'N27 zero-update bytes differ')
    return {'accepted':True,'dtype':str(before.dtype),'comparison':'native contiguous uint8; zero tolerance',
        'candidate_rows':16,'input_layout':layout_name(call['input_stride']),'live_storage_offset_observed':False,
        'clean_input_binding_verified':True,'feasible_ray_verified':True,'alpha_dtype':'torch.float32',
        'zero_gradient':bool(torch.count_nonzero(expected['gradient_after'])==0),**measured}
