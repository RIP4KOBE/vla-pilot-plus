#!/usr/bin/env python3
"""Single CPU startup preflight; no study data and no reopened geometry scope."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '2'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
sys.dont_write_bytecode = True
import json, hashlib, signal, stat, tempfile, time, traceback
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
PYROOT = Path('/home/hynx/miniconda3/envs/vla-pilot').resolve()
SCOPE_SHA = 'f670a3c2d90838356f2e90cc1481068a9546312293cd3165869537ed932b5de4'
AMENDMENT_SHA = '59fbdf54de44fca33f7a08a52c0b7089cc64aaaaf963b76b22f80c756d37d1e5'
PRIOR_SECONDS = 1.1819649679819122
REMAINING_SECONDS = 28.818035032
EXACT_METADATA_READS = {Path(p) for p in ['/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/tqdm-4.67.3.dist-info', '/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/tqdm-4.67.3.dist-info/METADATA', '/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/tqdm-4.67.3.dist-info/PKG-INFO', '/home/hynx/miniconda3/envs/vla-pilot/lib/python312.zip']}
OWNED_TMP = HERE / 'tmp'
READS = {HERE/'read-scope-v1.json', HERE/'input-manifest-v2.json', HERE/'trusted-metadata-amendment-v1.json', Path(__file__).resolve()}
WRITES = {HERE/'startup-result-v2.json', HERE/'startup-error-v2.json', HERE/'guard-result-v2.json'}
BLOCKED = []
COUNTS = Counter()
START = time.monotonic()
TORCH = None
ERROR = None

def deny(event, path):
    BLOCKED.append({'event':event,'path':str(path)})
    raise PermissionError('startup scope guard: '+event+':'+str(path))

def audit(event, args):
    if event == 'open':
        path, mode, flags = args
        if isinstance(path,int): return
        p=Path(os.fsdecode(path)).absolute(); resolved=p.resolve()
        writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
        if p==resolved==Path('/dev/null') and stat.S_ISCHR(os.stat(p).st_mode):
            COUNTS['dev_null_write' if writing else 'dev_null_read']+=1; return
        if not writing and p==Path('/proc/self/maps') and resolved==Path('/proc')/str(os.getpid())/'maps':
            COUNTS['own_proc_maps_read']+=1; return
        if not writing and p==resolved and p in EXACT_METADATA_READS:
            COUNTS['exact_trusted_metadata_read']+=1; return
        if writing:
            if p not in WRITES or resolved!=p: deny('write',p)
            COUNTS['owned_output_write']+=1;return
        if p in READS and resolved==p: COUNTS['frozen_setup_read']+=1;return
        if resolved in (Path('/proc/meminfo'),Path('/proc/cpuinfo')):
            COUNTS['cpu_metadata_read']+=1;return
        if (resolved.is_relative_to(PYROOT) or resolved.is_relative_to(Path('/usr/lib')) or resolved.is_relative_to(Path('/lib'))) and resolved.suffix in ('.py','.pyc','.so','.pth','.txt'):
            COUNTS['trusted_dependency_read']+=1;return
        deny('read',p)
    if event.startswith(('socket.','subprocess.','os.exec','os.spawn','os.fork')) or event in ('os.system','pty.spawn'):
        deny(event,args[:1])
    if event in ('os.remove','os.rename','os.rmdir','os.mkdir','os.symlink','os.link','os.truncate','os.chmod'):
        deny(event,args[:2])
    if event=='import' and args[0].split('.')[0] in ('core','main','scripts','libero','robosuite','mujoco','transformers','openai','requests','httpx'):
        deny('runtime_import',args[0])
    if event=='ctypes.dlopen' and any(x in str(args[0]).lower() for x in ('libcuda.so','libnvidia')):
        deny('cuda_dlopen',args[0])

sys.addaudithook(audit)

def need(value,message):
    if not value: raise ValueError(message)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(name,data):
    with (HERE/name).open('x') as stream: stream.write(json.dumps(data,indent=2,allow_nan=False)+'\n')

def timeout(*_): raise TimeoutError('one 30-second startup preflight limit')

try:
    signal.signal(signal.SIGALRM,timeout); signal.setitimer(signal.ITIMER_REAL,REMAINING_SECONDS)
    need(sha(HERE/'read-scope-v1.json')==SCOPE_SHA,'scope SHA')
    need(sha(HERE/'trusted-metadata-amendment-v1.json')==AMENDMENT_SHA,'amendment SHA')
    amendment=json.loads((HERE/'trusted-metadata-amendment-v1.json').read_bytes())
    need({Path(p) for p in amendment['additional_exact_read_paths']}==EXACT_METADATA_READS,'exact amendment paths')
    scope=json.loads((HERE/'read-scope-v1.json').read_bytes())
    manifest=json.loads((HERE/'input-manifest-v2.json').read_bytes())
    need(manifest['scope']['sha256']==SCOPE_SHA and manifest['extractor']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'frozen script/manifest')
    need(scope['temporary_directory']==str(OWNED_TMP) and OWNED_TMP.resolve()==OWNED_TMP and OWNED_TMP.is_dir(),'existing owned tmp identity')
    # The sole engineering correction: no tempfile probing or new write permission.
    tempfile.tempdir=str(OWNED_TMP)
    need(tempfile.gettempdir()==str(OWNED_TMP),'configured tempfile identity')
    import torch
    TORCH=torch
    torch.set_num_threads(2);torch.set_num_interop_threads(2)
    need(os.environ['CUDA_VISIBLE_DEVICES']=='' and not torch.cuda.is_initialized(),'invisible uninitialized CUDA')
    def no_cuda(*args,**kwargs): deny('cuda_call','blocked')
    torch.cuda._lazy_init=no_cuda;torch.cuda.init=no_cuda;torch.Tensor.cuda=no_cuda
    # Nine literal synthetic values only; no model, source or experiment tensors.
    x=torch.tensor([[-2.,0.,2.],[.5,-.25,4.],[1.,-1.,0.]],dtype=torch.bfloat16,device='cpu')
    bounded=x.clamp(-1.,1.)
    increments=bounded*.01
    cumulative=torch.cumsum(increments,dim=0)
    distances=torch.linalg.vector_norm(cumulative.float(),dim=-1)
    need(x.device.type=='cpu' and cumulative.dtype==torch.bfloat16 and distances.dtype==torch.float32,'synthetic dtype/device')
    need(bool((bounded.abs()<=1).all()) and bool(torch.isfinite(cumulative).all()) and bool(torch.isfinite(distances).all()),'synthetic finite operations')
    need(not torch.cuda.is_initialized() and not BLOCKED,'guard completion')
    result={'schema':'n24-cpu-startup-preflight-result-v1','status':'PASS_CPU_STARTUP_ONLY','prior_failed_seconds':PRIOR_SECONDS,'cumulative_seconds':PRIOR_SECONDS+time.monotonic()-START,'amendment':{'path':str(HERE/'trusted-metadata-amendment-v1.json'),'sha256':AMENDMENT_SHA},'scope':manifest['scope'],'input_manifest':{'path':str(HERE/'input-manifest-v2.json'),'sha256':sha(HERE/'input-manifest-v2.json')},'extractor':manifest['extractor'],'torch_version':torch.__version__,'cpu_threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads(),'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized':torch.cuda.is_initialized(),'tempfile_tempdir':tempfile.gettempdir(),'tmp_writes_permitted':False,'synthetic':{'source':'nine literal constants in frozen script','shape':list(x.shape),'native_dtype':str(x.dtype),'norm_dtype':str(distances.dtype),'clamped':bounded.float().tolist(),'cumulative':cumulative.float().tolist(),'norm':distances.tolist()},'elapsed_seconds':time.monotonic()-START,'guard_counts':dict(COUNTS),'blocked':BLOCKED,'payload_reads':0,'gpu_api_model_sim_calls':0,'geometry_scope_reopened':False,'geometry_run_authorized':False,'limitations':'CPU import and small synthetic operation coverage only; not CUDA parity, native payload association, extraction readiness or scientific evidence.'}
    write('startup-result-v2.json',result);print(json.dumps(result,sort_keys=True),flush=True)
except BaseException as exc:
    ERROR={'schema':'n24-cpu-startup-preflight-error-v1','type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'elapsed_seconds':time.monotonic()-START,'payload_reads':0,'automatic_retry_authorized':False}
    write('startup-error-v2.json',ERROR);print(json.dumps(ERROR),flush=True)
finally:
    signal.setitimer(signal.ITIMER_REAL,0)
    write('guard-result-v2.json',{'blocked':BLOCKED,'counts':dict(COUNTS),'error':ERROR is not None,'cuda_initialized':None if TORCH is None else TORCH.cuda.is_initialized(),'payload_reads':0,'tmp_write_permission':False})
if ERROR is not None:sys.exit(1)
