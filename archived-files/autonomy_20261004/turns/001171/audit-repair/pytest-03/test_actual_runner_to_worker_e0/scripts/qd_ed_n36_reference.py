"""Independent N36 binary64 geometry and explicit native writes; no core imports."""
import math
import torch
from scripts.qd_ed_n31_reference import shape, same


def reconstruct(plan, target, eef, quaternion, qpos, *, eligible=False):
    shape(plan, (64, 128), True)
    values = (target, eef, quaternion, qpos)
    if any(v is not None and not bool(torch.isfinite(v).all()) for v in values):
        return None, None, 'nonfinite_observation', None
    if any(v is None for v in values):
        return None, None, 'observation_unavailable', None
    p, origin, q, jaw = [shape(v, (n,)).double().tolist() for v, n in zip(values, (3, 3, 4, 2))]
    try:
        length = math.sqrt(math.fsum(v*v for v in q))
    except (OverflowError, ValueError):
        return None, None, 'invalid_quaternion', None
    if not math.isfinite(length) or length == 0:
        return None, None, 'invalid_quaternion', None
    x,y,z,w = [v/length for v in q]
    matrix = ((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
              (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
              (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
    lo, hi = jaw[1]+0.0005, jaw[0]-0.0005
    if lo > hi: return None, None, 'empty_inner_gap', None
    d = [a-b for a,b in zip(p, origin)]
    if not all(math.isfinite(v) for v in d): return None, None, 'nonfinite_observation', None
    local = [math.fsum(matrix[k][j]*d[k] for k in range(3)) for j in range(3)]
    hit = -.008 <= local[0] <= .008 and lo <= local[1] <= hi and -.0116 <= local[2] <= .0044
    center = (0., (lo+hi)/2, -.0036)
    error=[d[k]-math.fsum(matrix[k][j]*center[j] for j in range(3)) for k in range(3)]
    translation=[0.,0.,0.] if hit else [max(-1.,min(1.,v/.08)) for v in error]
    path=None
    reason='observed_close_dwell' if hit else 'observed_open_approach'
    halves=[translation,translation]
    if eligible and not hit:
        n=math.hypot(*error)
        if n==0. or not math.isfinite(n) or not all(math.isfinite(v) for v in error):
            return None,None,'invalid_tangent_error',None
        axis=sorted(range(3),key=lambda k:(abs(error[k]),k))[0]
        basis=[float(k==axis) for k in range(3)]
        cross=[error[1]*basis[2]-error[2]*basis[1],error[2]*basis[0]-error[0]*basis[2],error[0]*basis[1]-error[1]*basis[0]]
        n=math.hypot(*cross)
        if n==0. or not math.isfinite(n):return None,None,'invalid_tangent_cross',None
        tangent=[v/n for v in cross]
        b=[v*math.hypot(*translation) for v in tangent]
        raw=[[translation[k]+b[k] for k in range(3)],[translation[k]-b[k] for k in range(3)]]
        halves=[[max(-1.,min(1.,v)) for v in half] for half in raw]
        path=dict(error=error,axis=axis,tangent=tangent,a=translation,b=b,preclip=raw,clipped=halves)
        reason='nonprogress_tangent'
    out=plan.clone()
    for slot in range(8):
        for axis in range(3):
            out[slot,39+axis]=halves[slot//4][axis]
            out[slot,42+axis]=0.
        out[slot,10]=1. if hit else -1.
    if path is not None:
        commands=out[:8,[39,40,41,42,43,44,10]].clone()
        sums=[]
        for k in range(3):
            total=0.
            for j in range(8):total=total+float(commands[j,k])
            sums.append(.01*total)
        path.update(native_commands=commands,decoded_translation=sums,proxy_endpoint=[origin[k]+sums[k] for k in range(3)])
    arrival=0 if hit else None
    return (None,arrival,'no_native_change',path) if same(out,plan) else (out,arrival,reason,path)


def observation_same(a, b):
    """Exact nonfinite packet preservation, without relaxing finite plan checks."""
    if not torch.is_tensor(a) or not torch.is_tensor(b): return a is b is None
    return (a.dtype == b.dtype and a.shape == b.shape and
        torch.equal(a.contiguous().reshape(-1).view(torch.uint8), b.contiguous().reshape(-1).view(torch.uint8)))
