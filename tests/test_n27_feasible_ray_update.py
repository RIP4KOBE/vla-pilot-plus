"""Standalone guarded CPU checks; does not import any production policy/model."""
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import struct
import sys
import time
import traceback
import unittest

HERE = Path(__file__).resolve()
WORKTREE = HERE.parents[1]
VARIANT = WORKTREE.parent
HELPER = WORKTREE / 'core/qd_feasible_ray_update.py'
DENIED = []


def guarded_start():
    if 'torch' in sys.modules:
        raise RuntimeError('guard must precede Torch')
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3,8*1024**3))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
    os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',
        OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    sys.dont_write_bytecode=True
    import tempfile
    tempfile.tempdir=str(VARIANT)
    dependency_roots=tuple(Path(p).resolve() for p in (sys.prefix,sys.base_prefix,'/usr/lib','/lib'))
    sys.path[:]=[p for p in sys.path if p and any(Path(p).resolve()==r or r in Path(p).resolve().parents for r in dependency_roots)]
    results=VARIANT/'cpu-results-v1.json'
    prior=json.loads(results.read_text()) if results.exists() else []
    remaining=180-sum(x['wall_seconds'] for x in prior)
    if remaining<=0:raise RuntimeError('cumulative CPU budget exhausted')
    def expire(_sig,_frame):raise TimeoutError('cumulative CPU test bound')
    signal.signal(signal.SIGALRM,expire);signal.setitimer(signal.ITIMER_REAL,remaining)
    log=VARIANT/'cpu-checks-v1.log'
    allowed={str(HERE),str(HELPER)}
    writes={str(log),str(results)}
    null=Path('/dev/null');s=null.stat()
    if null.is_symlink() or not stat.S_ISCHR(s.st_mode) or s.st_rdev!=os.makedev(1,3):raise RuntimeError('invalid null sink')
    def dependency(p):
        q=p.resolve()
        return any(q==r or r in q.parents for r in dependency_roots)
    def reject(event,target):
        DENIED.append({'event':event,'target':str(target)})
        raise PermissionError('N27 CPU guard: '+event+': '+str(target))
    def hook(event,args):
        if event=='open':
            raw,mode,flags=args
            if isinstance(raw,int):return
            p=Path(os.fsdecode(raw)).absolute();name=str(p)
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if p==null:return
            if name=='/proc/self/maps' and not writing:
                caller=sys._getframe(1)
                if caller.f_code.co_name=='_load_global_deps' and Path(caller.f_code.co_filename)==Path(sys.prefix)/'lib/python3.12/site-packages/torch/__init__.py':return
            if writing:
                if name not in writes or p.is_symlink():reject(event,name)
            elif name not in allowed and not dependency(p) and name not in {'/etc/localtime','/etc/ld.so.cache'} and p!=VARIANT:
                reject(event,name)
        elif event in {'os.listdir','os.scandir'}:
            if isinstance(args[0],int):reject(event,'directory descriptor')
            p=Path(args[0] or '.').absolute()
            if p!=VARIANT and not dependency(p):reject(event,p)
        elif event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn','socket.__new__','socket.connect','socket.bind','socket.getaddrinfo',
                       'os.remove','os.rename','os.rmdir','os.mkdir','os.symlink','os.link','os.truncate','os.chmod','os.chown'}:reject(event,'forbidden')
        elif event=='import' and args[0].split('.')[0] in {'transformers','mujoco','libero','robosuite','requests','httpx'}:reject(event,args[0])
    sys.addaudithook(hook)
    return prior,log,results


START=time.monotonic()
PRIOR,LOG,RESULTS=guarded_start()
import torch
if torch.cuda.is_initialized():raise RuntimeError('CUDA initialized')
torch.set_num_threads(2);torch.set_num_interop_threads(2)
spec=importlib.util.spec_from_loader('n27_helper',loader=None)
helper=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helper
exec(compile(HELPER.read_bytes(),str(HELPER),'exec'),helper.__dict__)
update=helper.feasible_ray_update


def byte_equal(a,b):
    return a.dtype==b.dtype and a.shape==b.shape and torch.equal(a.detach().contiguous().view(torch.uint8),b.detach().contiguous().view(torch.uint8))


def f32(value):
    try:return struct.unpack('f',struct.pack('f',value))[0]
    except OverflowError:return math.copysign(math.inf,value)


def scalar_reference(before,operand):
    # Independent scalar particle/coordinate loop, explicit FP32 roundings;
    # not a vectorized helper call or an oracle built from its output.
    bs=before.detach().float().reshape(16,24).tolist()
    ds=operand.detach().float().reshape(16,24).tolist()
    alphas=[];rows=[]
    for b,d in zip(bs,ds):
        limits=[1.0]
        for x,v in zip(b,d):
            if v>0:limits.append(f32(f32(1.0-x)/v))
            elif v<0:limits.append(f32(f32(-1.0-x)/v))
        a=min(limits);alphas.append(a)
        row=[]
        for x,v in zip(b,d):
            if v==0:row.append(x)
            else:row.append(max(-1.0,min(1.0,f32(x+f32(a*v)))))
        rows.append(row)
    return torch.tensor(rows,dtype=torch.float32).reshape(16,8,3).to(before.dtype),torch.tensor(alphas,dtype=torch.float32)


def layout(value,kind):
    if kind=='contiguous':return value.clone()
    if kind=='transpose':
        out=torch.empty((16,3,8),dtype=value.dtype).transpose(1,2);out.copy_(value);return out
    if kind=='model_slice':
        out=torch.empty((16,67,128),dtype=value.dtype)[:,-64:,:][:,:8,39:42];out.copy_(value);return out
    raise AssertionError(kind)


class FeasibleTests(unittest.TestCase):
    def verify(self,b,d):
        original_b=b.detach().clone();original_d=d.detach().clone()
        b_identity=(b.stride(),b.storage_offset(),b.data_ptr(),b.requires_grad)
        d_identity=(d.stride(),d.storage_offset(),d.data_ptr(),d.requires_grad)
        rng=torch.get_rng_state().clone()
        out,alpha=update(b,d)
        expected,a=scalar_reference(b,d)
        self.assertTrue(byte_equal(out,expected))
        self.assertTrue(byte_equal(alpha,a))
        self.assertEqual(alpha.dtype,torch.float32)
        self.assertEqual(tuple(alpha.shape),(16,))
        self.assertTrue(bool(((alpha>=0)&(alpha<=1)).all()))
        self.assertTrue(bool(torch.isfinite(out).all()))
        self.assertTrue(byte_equal(b,original_b));self.assertTrue(byte_equal(d,original_d))
        self.assertEqual((b.stride(),b.storage_offset(),b.data_ptr(),b.requires_grad),b_identity)
        self.assertEqual((d.stride(),d.storage_offset(),d.data_ptr(),d.requires_grad),d_identity)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        moving=d!=0
        self.assertTrue(bool(((out[moving]>=-1)&(out[moving]<=1)).all()))
        self.assertTrue(byte_equal(out[~moving],b[~moving]))
        self.assertFalse(out.requires_grad);self.assertFalse(alpha.requires_grad)
        return out,alpha

    def test_invalid_type_shape_dtype_layout_device(self):
        b=torch.zeros((16,8,3));d=b.clone()
        bad=[(None,d),(b,[]),(b[:15],d),(b,d[:,:7]),
             (b.double(),d.double()),(b.half(),d.half()),(b.long(),d.long()),
             (b,d.bfloat16()),(b.to_sparse(),d),
             (torch.empty((16,8,3),device='meta'),d),
             (torch.empty((16,8,3),device='meta'),torch.empty((16,8,3),device='meta'))]
        for x,y in bad:
            with self.subTest(type=type(x),dtype=getattr(x,'dtype',None),shape=getattr(x,'shape',None)):
                with self.assertRaises(ValueError):update(x,y)
        self.assertFalse(torch.cuda.is_initialized())

    def test_fp32_rounding_box_correction_is_observable(self):
        # Locate one predetermined finite synthetic scalar grid rounding case,
        # independently of helper output. This is arithmetic coverage, not an
        # experimental sample/threshold selection.
        witness=None
        for bi in range(-97,98):
            x=f32(bi/100.)
            for di in range(21,121):
                v=f32(di/7.)
                a=f32(f32(1.-x)/v)
                raw=f32(x+f32(a*v))
                if 0<a<1 and raw>1.:
                    witness=(x,v,a,raw);break
            if witness is not None:break
        self.assertIsNotNone(witness)
        x,v,a,raw=witness
        b=torch.zeros((16,8,3));d=torch.zeros_like(b)
        b[0,0,0]=x;d[0,0,0]=v
        out,alpha=self.verify(b,d)
        self.assertEqual(float(alpha[0]),a)
        self.assertGreater(float((b.float()+alpha[:,None,None]*d.float())[0,0,0]),1.)
        self.assertEqual(float(out[0,0,0]),1.)

    def test_aliasing_inputs_remain_immutable(self):
        b=torch.full((16,8,3),.25)
        self.verify(b,b)

    def test_grad_enabled_inputs_do_not_create_model_jacobian(self):
        b=torch.full((16,8,3),.25,requires_grad=True)
        d=torch.full((16,8,3),.5,requires_grad=True)
        enabled=torch.is_grad_enabled()
        self.verify(b,d)
        self.assertEqual(torch.is_grad_enabled(),enabled)
        self.assertIsNone(b.grad);self.assertIsNone(d.grad)


def scenario(dtype,kind):
    def test(self):
        b=torch.zeros((16,8,3),dtype=dtype);d=torch.zeros_like(b)
        if kind=='all_zero':
            vals=torch.tensor([-3.,-1.,-0.,0.,1.,3.],dtype=dtype)
            b=vals.repeat(64).reshape(16,8,3);d.fill_(-0.)
        elif kind=='one_row':
            b.fill_(.25);d[5,0,0]=4.;d[5,1,1]=-2.
        elif kind=='feasible':
            b.fill_(.25);d.fill_(-.125)
        elif kind=='mixed_limited':
            b.fill_(.25);d[:,:,0]=4.;d[:,:,1]=-2.;d[:,:,2]=.25
        elif kind=='near_boundary':
            near=torch.nextafter(torch.tensor(1.,dtype=dtype),torch.tensor(0.,dtype=dtype))
            b[:,:,0]=near;b[:,:,1]=-near;d[:,:,0]=1.;d[:,:,1]=-1.
        elif kind=='extreme_finite':
            d.fill_(torch.finfo(dtype).max)
        elif kind=='tiny_nonzero':
            d.fill_(torch.finfo(dtype).tiny/128)
        elif kind=='signed_zero':
            b[0,0,0]=-0.;b[0,0,1]=0.;d.fill_(-0.)
            b[1,0,0]=-2.;b[1,0,1]=2.;d[2,0,0]=4.
        else:raise AssertionError(kind)
        out,a=self.verify(b,d)
        if kind in ('all_zero','feasible','tiny_nonzero'):
            self.assertTrue(torch.equal(a,torch.ones(16)))
        if kind=='one_row':
            self.assertLess(float(a[5]),1)
            self.assertTrue(torch.equal(torch.cat((a[:5],a[6:])),torch.ones(15)))
        if kind=='mixed_limited':
            self.assertTrue(torch.equal(a,torch.full((16,),.1875)))
            self.assertTrue(torch.equal(out[:,:,0],torch.ones((16,8),dtype=dtype)))
    return test


def native_parity(dtype,kind):
    def test(self):
        x=torch.arange(384,dtype=torch.float32).reshape(16,8,3)
        b=layout(((x%17)-8).div(32).to(dtype),kind)
        d=layout(((x%7)-3).div(64).to(dtype),kind)
        out,a=self.verify(b,d)
        self.assertTrue(torch.equal(a,torch.ones(16)))
        moving=d!=0
        self.assertTrue(byte_equal(out[moving],(b+d)[moving]))
    return test


def property_test(dtype,kind):
    def test(self):
        g=torch.Generator().manual_seed(113)
        b=layout((torch.rand((16,8,3),generator=g)*1.8-.9).to(dtype),kind)
        d=layout((torch.rand((16,8,3),generator=g)*16-8).to(dtype),kind)
        out,a=self.verify(b,d)
        self.assertTrue(bool((a<1).all()))
        # At least one limiting coordinate reaches the representable boundary;
        # roundoff may alter exact ray direction, so check mathematical alpha
        # maximality with a bounded FP32 increment separately from output bytes.
        bf=b.float();df=d.float()
        for row in range(16):
            bumped=float(a[row])+2e-6
            self.assertTrue(bool(((bf[row]+bumped*df[row]).abs()>1).any()))
    return test


def violation_test(dtype):
    def test(self):
        for x in (-2.,-1.,1.,2.):
            for v in (-.5,.5):
                b=torch.zeros((16,8,3),dtype=dtype);d=torch.zeros_like(b)
                b[3,2,1]=x;d[3,2,1]=v
                with self.subTest(x=x,v=v),self.assertRaisesRegex(ValueError,'strict-interior'):update(b,d)
        for target in ('before','operand'):
            for x in (math.nan,math.inf,-math.inf):
                b=torch.zeros((16,8,3),dtype=dtype);d=torch.zeros_like(b)
                (b if target=='before' else d)[0,0,0]=x
                with self.subTest(target=target,x=x),self.assertRaisesRegex(ValueError,'nonfinite'):update(b,d)
    return test

for dtype,name in ((torch.float32,'fp32'),(torch.bfloat16,'bf16')):
    for case in ('all_zero','one_row','feasible','mixed_limited','near_boundary','extreme_finite','tiny_nonzero','signed_zero'):
        setattr(FeasibleTests,'test_'+name+'_'+case,scenario(dtype,case))
    for kind in ('contiguous','transpose','model_slice'):
        setattr(FeasibleTests,'test_'+name+'_alpha1_byte_parity_'+kind,native_parity(dtype,kind))
        setattr(FeasibleTests,'test_'+name+'_limited_reference_'+kind,property_test(dtype,kind))
    setattr(FeasibleTests,'test_'+name+'_support_and_nonfinite_rejection',violation_test(dtype))


def main():
    success=False;count=0;error=None
    with LOG.open('a') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        print('RUN',len(PRIOR)+1)
        try:
            suite=(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:],sys.modules[__name__])
                   if len(sys.argv)>1 else unittest.defaultTestLoader.loadTestsFromTestCase(FeasibleTests))
            r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            success=r.wasSuccessful() and not DENIED;count=r.testsRun
        except BaseException as exc:error=type(exc).__name__+': '+str(exc);traceback.print_exc()
        finally:signal.setitimer(signal.ITIMER_REAL,0)
    elapsed=time.monotonic()-START
    row={'passed':success,'tests':count,'selection':sys.argv[1:] or ['ALL'],
         'wall_seconds':elapsed,'cumulative_seconds':sum(x['wall_seconds'] for x in PRIOR)+elapsed,
         'guard_denials':DENIED,'error':error,'cpu_affinity_count':len(os.sched_getaffinity(0)),
         'torch_threads':torch.get_num_threads(),'torch_interop_threads':torch.get_num_interop_threads(),
         'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized':torch.cuda.is_initialized(),
         'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest(),
         'actual_experiment_reads':False,'model_api_simulator_calls':0,'score':'Unknown/not evaluated'}
    PRIOR.append(row);RESULTS.write_text(json.dumps(PRIOR,indent=2)+'\n')
    print(json.dumps({k:row[k] for k in ('passed','tests','wall_seconds','cumulative_seconds','guard_denials','error')}))
    return 0 if success else 1


if __name__=='__main__':raise SystemExit(main())
