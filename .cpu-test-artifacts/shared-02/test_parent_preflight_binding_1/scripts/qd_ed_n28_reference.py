"""N28 independent parent-domain reference; unchanged N27 arithmetic is explicit."""
import torch
from scripts.qd_ed_n27_reference import reconstruct, reconstruct_update, require, exact, fixed_case, with_layout, CASES, DTYPES
from scripts.qd_ed_n26_reference import LAYOUTS as OLD_LAYOUTS, layout_name
LAYOUTS={k:OLD_LAYOUTS[k] for k in ('contiguous','model_slice')}
SOURCE='core.qd_parent_before_renoise:parent_before_renoise_v1'
INPUT='current_chunk_selected_parent_offspring'


def audit_witness(tensors,metadata,backend):
    x={k:backend.native(v) for k,v in tensors.items()};row=metadata['call']
    require(row.get('schema')=='n28-parent-rbf-call-summary-v1' and row.get('source')==SOURCE
        and row.get('input_source')==INPUT and row.get('input_binding')=='selected_offspring_before_original_renoise'
        and row.get('phase')=='parent' and row.get('denoising_step') is None and row.get('timestep') is None
        and row.get('prediction_type')=='sample' and row.get('model_jacobian_used') is False
        and row.get('rollout_diversity_placement')=='parent_before_renoise_v1'
        and row.get('update_operand_semantics')=='unconstrained_native_parent_proposal_before_feasible_ray',
        'N28 parent semantics absent')
    before=x['parent_offspring_before'];require(exact(x['input_xyz'],before),'N28 parent input/before bytes differ')
    ref=reconstruct(x['input_xyz'],x['source_origins'],input_stride=row['input_stride'])
    for k in ('cast_origins','projected_xyz','gradient_before','gradient_after'):
        require(exact(x[k],ref[k]),'N28 independent geometry differs '+k)
    require(row['gradient_before_normalization']['norm']==ref['norm'],'N28 native gradient norm differs')
    operand=-1.*20.*ref['gradient_after'].to(before.dtype)
    require(exact(x['update_operand'],operand),'N28 proposed operand differs')
    after,alpha=reconstruct_update(before,operand)
    require(exact(x['parent_offspring_after'],after) and exact(torch.tensor(row['alpha'],device=alpha.device,dtype=torch.float32),alpha),
            'N28 assigned prefix/alpha differs')
    delta=after.float()-before.float();moving=operand!=0
    measured={'limited_rows':int((alpha<1).sum()),'before_outside_components':int(((before<-1)|(before>1)).sum()),
      'after_outside_components':int(((after<-1)|(after>1)).sum()),'realized_nonzero_delta_components':int(torch.count_nonzero(delta)),
      'realized_delta_norm_fp32':float(torch.norm(delta))}
    require(all(row.get(k)==v for k,v in measured.items()) and exact(after[~moving],before[~moving]),'N28 realized stats/zero bytes differ')
    return {'accepted':True,'candidate_rows':16,'comparison':'native contiguous uint8; zero tolerance',
      'dtype':str(before.dtype),'input_layout':layout_name(row['input_stride']),'parent_input_binding_verified':True,
      'feasible_ray_verified':True,'zero_gradient':bool(torch.count_nonzero(ref['gradient_after'])==0),**measured}
