"""N27 preparation only: bounded synthetic pytest runner, no live records/dispatch."""
import os,sys,pathlib,resource,time,json,tempfile,stat
HERE=pathlib.Path(__file__).resolve().parent;I=HERE/'implementation';TMP=HERE/'cpu-phase-b-fixtures';TMP.mkdir(exist_ok=True)
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
sys.dont_write_bytecode=True;sys.pycache_prefix=str(TMP/'unused-bytecode');tempfile.tempdir=str(TMP);sys.path[:0]=[str(I),str(I/'tests')]
DEPS=pathlib.Path(sys.prefix).resolve();denied=[];start=time.monotonic();label=sys.argv[1];tests=sys.argv[2:]
SUMMARY=HERE/(label+'.guard.json');
import signal
spent=sum(json.loads(p.read_text())['elapsed_seconds'] for p in HERE.glob('phase-b-*.guard.json'))
def expire(*a):raise TimeoutError('N27 cumulative CPU300s exceeded')
signal.signal(signal.SIGALRM,expire);signal.setitimer(signal.ITIMER_REAL,max(.001,300-spent))
SELF=pathlib.Path(__file__).resolve()
def reject(event,path):
    denied.append({'event':event,'path':str(path)});raise PermissionError('N27_CPU_GUARD '+event+' '+str(path))
def audit(event,args):
    if event in ('socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system','os.posix_spawn'):reject(event,'disabled')
    if event=='open':
        raw=args[0]
        if isinstance(raw,int):return
        p=pathlib.Path(os.fsdecode(raw)).absolute();resolved=p.resolve();mode=args[1];flags=args[2]
        writing=(isinstance(mode,str) and any(k in mode for k in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if str(p)=='/dev/null' and stat.S_ISCHR(os.stat(p).st_mode):return
        if writing:
            if resolved.is_relative_to(TMP) or resolved==SUMMARY:return
            reject(event,p)
        if resolved.is_relative_to(TMP):return
        if resolved.is_relative_to(DEPS) or resolved.is_relative_to('/usr/lib') or resolved.is_relative_to('/usr/share/zoneinfo'):return
        if str(p) in ('/proc/self/maps','/proc/self/stat','/proc/sys/kernel/random/boot_id',f'/proc/{os.getpid()}/stat','/etc/localtime','/etc/timezone'):return
        if resolved in {SELF, pathlib.Path('/etc/mime.types')} :return
        if resolved.is_relative_to(I):
            rel=resolved.relative_to(I)
            if rel.parts[0] in {'data','outputs','research_sessions'} or rel.name=='research-state.yaml':reject(event,p)
            if rel.suffix in {'.py','.json','.md','.yaml','.yml','.ini','.toml','.cfg'}:return
        reject(event,p)
    if event in ('os.remove','os.rmdir','os.mkdir','os.rename'):
        raw=args[0]
        if isinstance(raw,(str,bytes)) and not pathlib.Path(os.fsdecode(raw)).absolute().resolve().is_relative_to(TMP):reject(event,raw)
sys.addaudithook(audit)
import torch
torch.set_num_threads(2);torch.set_num_interop_threads(2)
def cuda_forbidden(*a,**kw):reject('cuda.initialization','disabled')
torch.cuda._lazy_init=cuda_forbidden
import pytest
code=pytest.main(['-q','--assert=plain','-p','no:cacheprovider','--basetemp',str(TMP/label),*tests])
import torch
result={'schema':'n27-cpu-guard-v1','pytest_exit':code,'elapsed_seconds':time.monotonic()-start,'denied':denied,
 'cpu_affinity':sorted(os.sched_getaffinity(0)),'torch_threads':torch.get_num_threads(),'cuda_visible':os.environ['CUDA_VISIBLE_DEVICES'],
 'cuda_initialized':torch.cuda.is_initialized(),'rlimit_as':list(resource.getrlimit(resource.RLIMIT_AS)),'tests':tests}
SUMMARY.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
raise SystemExit(code if code else (3 if denied or result['cuda_initialized'] else 0))
