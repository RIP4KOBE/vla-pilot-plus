"""N24 synthetic-only read/write and dispatch guard; installed before collection."""
import atexit,json,os,sys,hashlib
from pathlib import Path
import torch
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
W=HERE/'validation_implementation'
WORKTREES=(W,HERE/'implementation')
STATIC=(HERE.parent/'n22_hold_conditioned_lift/plan.frozen.v1.gpu7.json').resolve()
assert hashlib.sha256(STATIC.read_bytes()).hexdigest()=='30846268778c46f2d9ad25a92abe7869395d3ead218da1a97dbf24fae4d07218'
BLOCKED=[]
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
torch.set_num_threads(2)
torch.set_num_interop_threads(2)
assert not torch.cuda.is_initialized()
def stop_cuda(*args,**kwargs):
    BLOCKED.append('cuda');raise RuntimeError('N24 CPU-only CUDA guard')
torch.cuda._lazy_init=stop_cuda
def audit(event,args):
    if event in {'subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind'}:
        BLOCKED.append(event);raise RuntimeError('N24 CPU-only dispatch guard')
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
    raw=Path(os.fsdecode(args[0])).absolute()
    path=raw.resolve()
    mode=args[1] or '';flags=args[2] if len(args)>2 else 0
    writing=any(c in mode for c in 'wax+') or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
    # Always protect actual evidence/authority paths for BOTH reads and writes.
    def sensitive(candidate):
        if not candidate.is_relative_to(HERE):return False
        parts=candidate.relative_to(HERE).parts
        if not parts:return False
        name=parts[0]
        return name.startswith(('result-', 'root-', 'execution', 'validation-execution', 'plan.frozen', 'adoption', 'validation-adoption')) or name in {
            'final-source-runtime-review-v1.json','source-equivalence-bridge-v1.json',
            'validation-plan.frozen.v1.gpu7.json','validation-dev-promotion-review-v1.json',
            'validation-source-review-v1.json','authority.json'}
    bad=sensitive(raw) or sensitive(path)
    if bad:pass
    elif writing:
        bad=not path.is_relative_to(HERE) and str(path) not in {'/dev/null'}
    elif path.is_relative_to(Path('/mnt')) or path.is_relative_to(Path('/home/hynx/.codex')) or path.name in {'.env','auth.json','credentials.json'}:
        bad=True
    elif path==STATIC:bad=False
    elif path.is_relative_to(ROOT):
        owner=next((root for root in WORKTREES if path.is_relative_to(root)),None)
        if owner is not None:
            rel=path.relative_to(owner);bad=bool(rel.parts) and rel.parts[0] in {'data','outputs','.git','artifacts'}
        else:bad=not path.is_relative_to(HERE)
    if bad:
        BLOCKED.append(str(path));raise PermissionError('N24 synthetic path guard')
sys.addaudithook(audit)
@atexit.register
def result():print('N24_VALIDATION_CPU_GUARD_V3 '+json.dumps({'blocked':BLOCKED,'blocked_count':len(BLOCKED),'cuda_initialized':torch.cuda.is_initialized(),'threads':torch.get_num_threads()}))
