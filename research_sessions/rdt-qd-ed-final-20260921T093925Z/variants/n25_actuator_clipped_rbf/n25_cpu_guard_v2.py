"""Phase B synthetic fixture roots only; immutable live inputs remain closed."""
import atexit,json,os,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE/'implementation';ENV=Path('/home/hynx/miniconda3/envs/vla-pilot').resolve();BLOCKED=[]
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
tempfile.tempdir=str(HERE/'tmp');assert Path(tempfile.tempdir).is_dir()
PUBLIC={'/dev/null','/proc/self/maps',f'/proc/{os.getpid()}/maps','/proc/self/stat',f'/proc/{os.getpid()}/stat','/proc/sys/kernel/random/boot_id'}
def audit(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind'}:
  BLOCKED.append(event);raise RuntimeError('N25 CPU-only dispatch guard')
 if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
 p=Path(os.fsdecode(args[0])).resolve();mode=args[1] or '';flags=args[2] if len(args)>2 else 0
 writing=any(c in mode for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
 if str(p) in PUBLIC and (not writing or str(p)=='/dev/null'):return
 allowed=False
 if p.is_relative_to(HERE):
  parts=p.relative_to(HERE).parts
  synthetic=bool(parts) and (parts[0].startswith('fixtures-') or parts[0]=='tmp')
  sensitive=any(x in {'execution','validation-execution','data','outputs','artifacts','.git','worker','adoption-v1',
    'budget-adoption-v1','arithmetic-preflight','arithmetic-preflight-adoption-v1'} for x in parts)
  sensitive=sensitive or p.name in {'result-v1.json','plan.frozen.v1.gpu7.json','predecessor-review-v1.json','final-source-runtime-review-v1.json',
    'arithmetic-preflight-release-v1.json','execution-release-v1.json','source-equivalence-bridge-v1.json','arithmetic-preflight-source-review-v1.json'}
  allowed=synthetic or not sensitive
  if p.is_relative_to(W) and writing:allowed=False
 elif not writing and any(p.is_relative_to(q) for q in (ENV,Path('/usr/lib'),Path('/usr/local/lib'))):allowed=True
 if not allowed:BLOCKED.append(str(p));raise PermissionError('N25 synthetic path guard: '+str(p))
sys.addaudithook(audit)
import torch
torch.set_num_threads(2);torch.set_num_interop_threads(2);assert not torch.cuda.is_initialized()
def no_cuda(*args,**kwargs):BLOCKED.append('cuda');raise RuntimeError('N25 CPU-only CUDA guard')
torch.cuda._lazy_init=no_cuda
@atexit.register
def summary():print('N25_CPU_GUARD_V2 '+json.dumps({'blocked':BLOCKED,'blocked_count':len(BLOCKED),
 'cuda_initialized':torch.cuda.is_initialized(),'threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads()}))
