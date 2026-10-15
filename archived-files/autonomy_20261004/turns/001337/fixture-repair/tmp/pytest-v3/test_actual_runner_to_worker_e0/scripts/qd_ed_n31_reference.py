"""Independent N31 binary64/native-write reference; never imports proposal code."""
import hashlib
import math
import torch


def require(ok, message):
    if not ok:
        raise ValueError('N31 native: ' + message)


def native_id(value):
    require(type(value) is torch.Tensor and value.device.type == 'cpu'
            and value.is_floating_point() and bool(torch.isfinite(value).all()), 'finite CPU native tensor')
    return hashlib.sha256(str((str(value.dtype), tuple(value.shape))).encode()
                          + value.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def same(a, b):
    return type(a) is torch.Tensor and type(b) is torch.Tensor and native_id(a) == native_id(b)


def optional(a, b):
    return a is None and b is None or same(a, b)


def shape(value, expected, native=False):
    native_id(value)
    require(tuple(value.shape) == tuple(expected), 'shape differs')
    if native:
        require(value.dtype in (torch.float32, torch.bfloat16), 'native dtype differs')
    return value


def fingerprint(value):
    native_id(value)
    return hashlib.sha256(value.float().contiguous().numpy().astype('<f4', copy=False).tobytes()).hexdigest()


def terminal_bool(value):
    if type(value) is bool:
        return value
    require(type(value) is torch.Tensor and value.device.type == 'cpu'
            and value.dtype == torch.bool and value.ndim == 0, 'terminal boolean representation')
    return value.item()


def reconstruct(plan, xyz, target, quaternion, qpos):
    """Literal inclusive prism with Python binary64 normalization and fsum.

    Operation order follows the frozen arithmetic specification. Independence
    means this module neither imports nor invokes the production helper.
    """
    shape(plan, (64, 128), True); shape(xyz, (8, 3), True)
    require(plan.dtype == xyz.dtype, 'plan/projection dtype differs')
    vals=[]
    for value,n in ((target,3),(quaternion,4),(qpos,2)):
        vals.append(None if value is None else shape(value,(n,)).double().tolist())
    point,quat,jaw=vals
    if point is None:return None,None,'target_unavailable'
    if quat is None or jaw is None:return None,None,'proprioception_unavailable'
    try:length=math.sqrt(math.fsum(t*t for t in quat))
    except (OverflowError,ValueError) as exc:raise ValueError('N31 native: invalid quaternion norm') from exc
    require(math.isfinite(length) and length>0,'invalid quaternion norm')
    x,y,z,w=[t/length for t in quat]
    matrix=((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
            (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
            (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
    lo,hi=jaw[1]+.0005,jaw[0]-.0005
    require(math.isfinite(lo) and math.isfinite(hi),'jaw interval nonfinite')
    if lo>hi:return None,None,'empty_inner_gap'
    arrival=None
    for j,pos in enumerate(xyz.double().tolist()):
        d=[point[k]-pos[k] for k in range(3)]
        require(all(math.isfinite(t) for t in d),'displacement nonfinite')
        try:a=[math.fsum(matrix[k][axis]*d[k] for k in range(3)) for axis in range(3)]
        except (ValueError,OverflowError) as exc:raise ValueError('N31 native: invalid hand transform') from exc
        require(all(math.isfinite(t) for t in a),'hand transform nonfinite')
        if -.008<=a[0]<=.008 and lo<=a[1]<=hi and -.0116<=a[2]<=.0044:
            arrival=j;break
    if arrival is None:return None,None,'no_projected_entry'
    result=plan.clone()
    # Independent explicit writes preserve every other native byte.
    for j in range(arrival,8):result[j,10]=1
    for j in range(arrival+1,8):
        for axis in range(39,45):result[j,axis]=0
    if same(result,plan):return None,arrival,'no_native_change'
    return result,arrival,'capture_dwell_proposal'
