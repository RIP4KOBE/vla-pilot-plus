"""Independent, native-dtype N25 arithmetic; never imports production RBF helper."""
import torch

CASES=('strict_interior','exact_boundary','mixed_saturation','distinct_saturated',
       'coincident_saturated','coincident_interior')
DTYPES=(torch.float32,torch.bfloat16)
XYZ=(39,40,41)


def require(ok,message):
    if not ok:raise ValueError('N25 arithmetic: '+message)


def exact(left,right):
    return (torch.is_tensor(left) and torch.is_tensor(right) and left.shape==right.shape
        and left.dtype==right.dtype and torch.equal(left.detach().contiguous().view(torch.uint8),
                                                    right.detach().contiguous().view(torch.uint8)))


class ReferenceClip(torch.autograd.Function):
    @staticmethod
    def forward(ctx,value):
        ctx.save_for_backward(value.gt(-1).logical_and(value.lt(1)))
        return torch.maximum(torch.minimum(value,torch.ones_like(value)),-torch.ones_like(value))

    @staticmethod
    def backward(ctx,upstream):
        (mask,)=ctx.saved_tensors
        return upstream*mask.to(upstream.dtype)


def fixed_case(name,dtype):
    require(name in CASES and dtype in DTYPES,'unknown preregistered case')
    x=torch.zeros(16,64,128,dtype=dtype)
    rows=torch.arange(16,dtype=dtype)
    x[:,:8,39]=((rows-8)/16)[:,None]
    x[:,:8,40]=((7-rows)/32)[:,None]
    x[:,:8,41]=torch.arange(8,dtype=dtype)[None,:]/32
    if name=='exact_boundary':
        x[::2,:8,39]=-1;x[1::2,:8,39]=1
    elif name=='mixed_saturation':
        x[::2,:8,39]=2;x[1::2,:8,40]=-2;x[::3,:8,41]=1
    elif name=='distinct_saturated':
        x[:,:8,39:42]=torch.tensor([2.,-2.],dtype=dtype).repeat(8)[:,None,None]
    elif name=='coincident_saturated':x[:,:8,39:42]=2
    elif name=='coincident_interior':x[:,:8,39:42]=.25
    origins=torch.tensor([[.125,-.25,.375]]*16,dtype=torch.float64)
    before=torch.full((16,8,3),.125,dtype=dtype)
    return x,origins,before


def reconstruct(input_xyz,origins,*,clipped=True):
    require(tuple(input_xyz.shape)==(16,8,3) and input_xyz.dtype in DTYPES
        and tuple(origins.shape)==(16,3) and bool(torch.isfinite(input_xyz).all())
        and bool(torch.isfinite(origins).all()),'shape/dtype/nonfinite input')
    device=input_xyz.device;dtype=input_xyz.dtype
    with torch.enable_grad():
        latent=torch.zeros((16,64,128),dtype=dtype,device=device)
        latent[:,:8,XYZ]=input_xyz.detach()
        latent.requires_grad_(True)
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
    expected=reconstruct(native['input_xyz'],native['source_origins'])
    for name in ('cast_origins','projected_xyz','gradient_before','gradient_after'):
        require(exact(native[name],expected[name]),'byte mismatch '+name)
    call=metadata['call']
    require(call['gradient_before_normalization']['norm']==expected['norm'],'normalization scalar differs')
    require(native['model_output_before'].shape==(16,8,3),'model slice shape differs')
    operand=-1.*20.*expected['gradient_after'].to(dtype=native['model_output_before'].dtype)
    require(exact(native['update_operand'],operand),'update operand differs')
    require(exact(native['model_output_after'],native['model_output_before']+operand),'actual output addition differs')
    return {'accepted':True,'dtype':str(native['input_xyz'].dtype),'comparison':'native contiguous uint8; zero tolerance',
            'candidate_rows':16,'zero_gradient':bool(torch.count_nonzero(expected['gradient_after'])==0)}
