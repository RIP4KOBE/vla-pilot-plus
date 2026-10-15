"""N29 independent exact-native formula. Never calls production trust helper."""
import torch
from scripts.qd_ed_n27_reference import reconstruct,reconstruct_update,require,exact
from scripts.qd_ed_n26_reference import DTYPES,layout_name,with_layout
from scripts.qd_ed_n28_reference import LAYOUTS
SOURCE='core.qd_population_relative_rbf:population_relative_trust_v1'
INPUT='current_chunk_selected_parent_offspring'
MODE='population_relative_trust_v1'
EXTRA={'scaled_operand':(16,8,3),'beta':(16,),'radius':(),'operand_norms':(16,)}
CASES=('mixed','zero_spread','zero_operand','active_box','duplicate_rows','strict_interior')


def bytes_equal(a,b):
    return a.dtype==b.dtype and a.shape==b.shape and torch.equal(a.reshape(-1).contiguous().view(torch.uint8),b.reshape(-1).contiguous().view(torch.uint8))


def reconstruct_trust(before,operand):
    require(before.shape==operand.shape==(16,8,3) and before.dtype==operand.dtype and before.dtype in DTYPES
        and before.device==operand.device and bool(torch.isfinite(before).all()) and bool(torch.isfinite(operand).all()),'N29 reference input domain')
    require(not bool(((operand!=0)&((before<=-1)|(before>=1))).any()),'N29 raw support before scaling')
    b=before.detach().to(torch.float32).reshape(16,24);p=operand.detach().to(torch.float32).reshape(16,24)
    mu=b.mean(dim=0);centered=b-mu;square=centered*centered;energies=square.sum(dim=1);average=energies.mean();s=average.sqrt()
    psquare=p*p;penergy=psquare.sum(dim=1);n=penergy.sqrt()
    require(all(bool(torch.isfinite(x).all()) for x in (mu,centered,square,energies,average,s,psquare,penergy,n)), 'N29 nonfinite independent intermediate')
    require(not (bool((centered!=0).any()) and bool(s==0)) and not bool(((p!=0).any(dim=1)&(n==0)).any()),'N29 independent nonzero underflow')
    # Reduction order is deliberately identical to the frozen formula; independent
    # implementation shares no production helper or result, and uses masked branches.
    denominator=n.clone();denominator[n==0]=1
    ratio=s/denominator;require(bool(torch.isfinite(ratio).all()),'N29 reference ratio overflow')
    beta=torch.minimum(ratio,torch.ones_like(ratio));beta[n==0]=1
    scaled_fp32=p*beta[:,None];scaled=scaled_fp32.reshape(16,8,3).to(before.dtype)
    require(bool(torch.isfinite(scaled_fp32).all()) and bool(torch.isfinite(scaled).all()),'N29 scaled overflow')
    after,alpha=reconstruct_update(before,scaled)
    return {'prefix':after,'alpha':alpha,'beta':beta,'radius':s,'operand_norms':n,'scaled_operand':scaled}


def audit_witness(tensors,metadata,backend):
    x={k:backend.native(t) for k,t in tensors.items()};row=metadata['call'];parent=row.get('phase')=='parent'
    require(row.get('phase') in {'parent','initial'} and row.get('schema')==('n29-parent-rbf-call-summary-v1' if parent else 'n29-rbf-call-summary-v1')
        and row.get('source')==SOURCE and row.get('diversity_update_mode')==MODE
        and row.get('input_source')==(INPUT if parent else 'model_output_sample_v1')
        and row.get('input_binding')==('selected_offspring_before_original_renoise' if parent else 'same_forward_unmodified_model_output')
        and row.get('prediction_type')=='sample' and row.get('model_jacobian_used') is False
        and row.get('update_operand_semantics')==('unconstrained_native_parent_proposal_before_population_trust_and_feasible_ray' if parent else 'unconstrained_native_proposal_before_population_trust_and_feasible_ray'), 'N29 native semantics differ')
    before=x['parent_offspring_before' if parent else 'model_output_before'];after=x['parent_offspring_after' if parent else 'model_output_after']
    require(bytes_equal(x['input_xyz'],before),'N29 input/preassignment bytes differ')
    geometry=reconstruct(x['input_xyz'],x['source_origins'],input_stride=row['input_stride'])
    for k in ('cast_origins','projected_xyz','gradient_before','gradient_after'):require(bytes_equal(x[k],geometry[k]),'N29 native geometry differs '+k)
    require(row['gradient_before_normalization']['norm']==geometry['norm'],'N29 native norm differs')
    operand=-1.*20.*geometry['gradient_after'].to(before.dtype)
    require(bytes_equal(operand,x['update_operand']),'N29 raw operand differs')
    ref=reconstruct_trust(before,operand)
    for k in EXTRA:require(bytes_equal(x[k],ref[k]),'N29 independent trust differs '+k)
    require(bytes_equal(after,ref['prefix']),'N29 assigned prefix differs')
    for k in ('alpha','beta','operand_norms'):
        require(bytes_equal(torch.tensor(row[k],device=before.device,dtype=torch.float32),ref[k]),'N29 scalar tensor differs '+k)
    require(row.get('radius')==float(ref['radius']),'N29 scalar radius differs')
    delta=after.float()-before.float();moving=ref['scaled_operand']!=0
    measured={'limited_rows':int((ref['alpha']<1).sum()),'trust_limited_rows':int((ref['beta']<1).sum()),
        'before_outside_components':int(((before<-1)|(before>1)).sum()),'after_outside_components':int(((after<-1)|(after>1)).sum()),
        'realized_nonzero_delta_components':int(torch.count_nonzero(delta)),'realized_delta_norm_fp32':float(torch.norm(delta)),
        'scaled_operand_norm_fp32':float(torch.norm(ref['scaled_operand'].float()))}
    require(all(row.get(k)==val for k,val in measured.items()) and bytes_equal(after[~moving],before[~moving]),'N29 measured update stats differ')
    return {'accepted':True,'dtype':str(before.dtype),'comparison':'native contiguous uint8; zero tolerance','candidate_rows':16,
        'input_layout':layout_name(row['input_stride']),'population_trust_verified':True,'feasible_ray_verified':True,
        'input_binding_verified':True,'zero_gradient':bool(torch.count_nonzero(geometry['gradient_after'])==0),**measured}


def fixed_case(name,dtype,layout):
    require(name in CASES,'N29 fixed case unknown')
    x=torch.zeros((16,64,128),dtype=dtype)
    # Deterministic distinct rows, no model/RNG; nontranslation/tail sentinels.
    x[:,:,0]=.125;x[:,8:,39:42]=.375
    row=torch.arange(16,dtype=torch.float32).reshape(16,1,1)
    xyz=((row-7.5)/32).expand(16,8,3).clone()
    if name=='mixed':xyz[:,0,0]=torch.linspace(-1.25,1.25,16)
    elif name=='zero_spread':xyz.fill_(.125)
    elif name=='zero_operand':xyz.fill_(1.25)
    elif name=='active_box':xyz=((row-7.5)/8.01).expand(16,8,3).clone()
    elif name=='duplicate_rows':xyz[:8]=-.125;xyz[8:]=.125
    elif name=='strict_interior':xyz*=.25
    x[:,:8,39:42]=xyz.to(dtype)
    origins=torch.tensor([.1,.2,.3],dtype=torch.float32).repeat(16,1)
    return with_layout(x,layout),origins
