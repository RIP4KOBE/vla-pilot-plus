"""N26 synthetic-only guard. Install before Torch/pytest; dependency metadata allowed."""
import atexit,json,os,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
W=HERE/'implementation'
ENV=Path('/home/hynx/miniconda3/envs/vla-pilot').resolve()
BLOCKED=[]
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
tempfile.tempdir=str(HERE/'tmp')
assert Path(tempfile.tempdir).is_dir()
def audit(event,args):
    if event in {'subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind'}:
        BLOCKED.append(event);raise RuntimeError('N26 CPU-only dispatch guard')
    if event=='import' and (args[0].startswith(('mujoco','robosuite','libero.','transformers.','diffusers.','requests','httpx','openai','poe','third_party.'))):
        BLOCKED.append('runtime_import:'+args[0]);raise ImportError('N26 no runtime import')
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
    p=Path(os.fsdecode(args[0])).resolve();mode=args[1] or '';flags=args[2] if len(args)>2 else 0
    writing=any(c in mode for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
    sensitive=any(x in {'execution','validation-execution','data','outputs','artifacts','.git','adoption','authority','validation_implementation'} for x in p.parts)
    if str(p) in {'/dev/null','/proc/self/maps',f'/proc/{os.getpid()}/maps'}:return
    allowed=False
    if p.is_relative_to(HERE):
        allowed=not sensitive
        if p.is_relative_to(W) and writing:allowed=False
    elif not writing and (p.is_relative_to(ENV) or p.is_relative_to(Path('/usr/lib')) or p.is_relative_to(Path('/usr/local/lib'))):
        allowed=True
    if not allowed:
        BLOCKED.append(str(p));raise PermissionError('N26 synthetic path guard: '+str(p))
sys.addaudithook(audit)
import torch
torch.set_num_threads(2);torch.set_num_interop_threads(2)
assert not torch.cuda.is_initialized()
def no_cuda(*args,**kwargs):
    BLOCKED.append('cuda');raise RuntimeError('N26 CPU-only CUDA guard')
torch.cuda._lazy_init=no_cuda
@atexit.register
def summary():
    print('N26_CPU_GUARD_V1 '+json.dumps({'blocked':BLOCKED,'blocked_count':len(BLOCKED),
        'cuda_initialized':torch.cuda.is_initialized(),'threads':torch.get_num_threads(),
        'interop_threads':torch.get_num_interop_threads()}))
