"""N28 synthetic-only test boundary. No experimental payload or dispatch."""
import os,sys,time,resource,json,tempfile,pathlib,stat,hashlib
V=pathlib.Path(__file__).resolve().parent;I=V/'implementation'
allowed_cpus=sorted(os.sched_getaffinity(0))[:2];os.sched_setaffinity(0,allowed_cpus)
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key]='2'
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
os.environ['N28_BASE_POLICY']=str(V/'baseline-policy-e21.py')
sys.dont_write_bytecode=True
run=sys.argv[1];assert run.isdecimal()
old=sum(json.loads(p.read_text())['cpu_seconds'] for p in V.glob('cpu-resource-*.json'))
remaining=180-old
assert remaining>0
resource.setrlimit(resource.RLIMIT_CPU,(max(1,int(remaining)),max(2,int(remaining)+1)))
scratch=V/('cpu-fixtures-'+run);scratch.mkdir(exist_ok=False)
(scratch/'tmp').mkdir();tempfile.tempdir=str(scratch/'tmp')
# An owned empty prefix prevents arbitrary historical bytecode imports.
sys.pycache_prefix=str(scratch/'pycache')
assert stat.S_ISCHR(os.stat('/dev/null').st_mode)
interpreter=pathlib.Path(sys.prefix).resolve();maps=f'/proc/{os.getpid()}/maps'
static={str(V/'baseline-policy-e21.py'),str(V/'cpu_guard_v2.py')}
source_roots=[I/x for x in ('core','tests','scripts','configs','utils')]
blocked=[];exceptions=[]
def audit(event,args):
    if event in {'subprocess.Popen','os.system','os.exec','os.fork','socket.connect','socket.bind','socket.getaddrinfo'}:
        blocked.append([event,'blocked']);raise PermissionError(event)
    if event not in {'open','os.listdir','os.scandir'}:return
    p=args[0]
    if isinstance(p,int):return
    try:p=os.path.realpath(os.fsdecode(p))
    except TypeError:return
    mode=args[1] if event=='open' else 'r';flags=args[2] if event=='open' and len(args)>2 else 0
    writing=event=='open' and ((isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
    path=pathlib.Path(p)
    if p=='/dev/null':exceptions.append('dev_null_sink');return
    if path.is_relative_to(scratch):return
    if writing:
        blocked.append([event,p,'write']);raise PermissionError(p)
    if p in {maps,'/proc/cpuinfo'}:exceptions.append(p);return
    if path.is_relative_to(interpreter) or p in {'/etc/localtime','/etc/ld.so.cache'} or p.startswith('/usr/lib/') or p.startswith('/usr/share/zoneinfo/'):
        return
    if p in static:return
    if path==I or any(path==root for root in source_roots):return
    if any(path.is_relative_to(root) for root in source_roots) and (path.suffix in {'.py','.yaml','.yml','.json'} or event!='open'):
        return
    blocked.append([event,p,'read']);raise PermissionError(p)
RESULT_FD=os.open(V/('cpu-resource-'+run+'.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
sys.addaudithook(audit)
sys.path[:]=[p for p in sys.path if p and pathlib.Path(p).is_absolute() and pathlib.Path(p).is_relative_to(interpreter)]
start=time.process_time();wall=time.monotonic();exitcode=1
try:
    import pytest,torch
    torch.set_num_threads(2);torch.set_num_interop_threads(2)
    sys.path[:0]=[str(I/'tests'),str(I)]
    assert not torch.cuda.is_initialized()
    exitcode=pytest.main(['-q','-p','no:cacheprovider','--confcutdir',str(I),'--basetemp',str(scratch/'pytest'),*sys.argv[2:]])
    assert not torch.cuda.is_initialized()
finally:
    elapsed=time.process_time()-start
    result={'run':run,'pytest_exit':int(exitcode),'cpu_seconds':elapsed,'cumulative_cpu_seconds':old+elapsed,
        'wall_seconds':time.monotonic()-wall,'affinity':allowed_cpus,'thread_limit':2,
        'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized':bool(sys.modules.get('torch') and sys.modules['torch'].cuda.is_initialized()),
        'blocked':blocked,'dependency_exceptions':sorted(set(exceptions)),
        'guard_sha256':hashlib.sha256((V/'cpu_guard_v2.py').read_bytes()).hexdigest(),
        'test_argv':sys.argv[2:],'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    # Only this final new record is written outside scratch; use pre-opened FD.
    os.write(RESULT_FD,(json.dumps(result,indent=2)+'\n').encode()) if 'RESULT_FD' in globals() else None
    print('N28_RESOURCE '+json.dumps(result),flush=True)
if blocked or exitcode:raise SystemExit(1)
