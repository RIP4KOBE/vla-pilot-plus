"""N30 synthetic test process; no experiment payload or external execution."""
import os,sys,time,json,resource,tempfile,stat
from pathlib import Path
HERE=Path(__file__).resolve().parent
I=HERE/'implementation';TMP=HERE/'cpu-fixtures'
os.sched_setaffinity(0,{0,1})
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='2'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True;tempfile.tempdir=str(TMP)
sys.pycache_prefix=str(TMP/'empty-pycache')
sys.path[:]=[p for p in sys.path if p and (str(Path(p).resolve()).startswith(sys.base_prefix) )]
self_maps=Path('/proc/self/maps').resolve()
run=sys.argv[1];args=sys.argv[2:]
result=HERE/f'cpu-{run}-resource.json'
if result.exists():raise RuntimeError('immutable resource output exists')
resource.setrlimit(resource.RLIMIT_CPU,(1100,1150))
start=time.process_time();wall=time.monotonic();denied=[]
stdlib=Path(sys.base_prefix).resolve();extra=(Path('/usr/lib').resolve(),Path('/lib').resolve())
source_roots=[I/'core',I/'utils',I/'tests',I/'configs',I/'scripts']
allowed_exact={I/'main.py',I/'pytest.ini',I/'pyproject.toml',I/'setup.cfg',I/'tox.ini',I/'AGENTS.md',HERE/'cpu_guard_v1.py'}
def inside(p,r):return p==r or r in p.parents
null=Path('/dev/null');assert stat.S_ISCHR(null.stat().st_mode)
def reject(event,value):
 denied.append({'event':event,'value':str(value)});raise PermissionError('N30 synthetic guard: '+str(value))
def guard(event,args):
 if event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.forkpty','os.exec','os.posix_spawn'}:reject(event,event)
 if event not in {'open','os.listdir','os.scandir'}:return
 raw=args[0]
 if isinstance(raw,int):return
 try:p=Path(os.fsdecode(raw)).absolute().resolve()
 except (TypeError,ValueError):reject(event,'non-path')
 writing=False
 if event=='open':
  mode=args[1];flags=args[2] or 0
  writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
 if p==null:return
 if writing:
  if inside(p,TMP) or p==result:return
  reject(event,p)
 if p==self_maps or p==Path('/proc/cpuinfo'):return
 if inside(p,stdlib) or any(inside(p,r) for r in extra):return
 if inside(p,TMP) or p in allowed_exact:return
 if event!='open':
  if inside(p,I) or p in (HERE,*HERE.parents):return
 elif any(inside(p,r) for r in source_roots) and p.suffix in {'.py','.pyi','.json','.yaml','.yml','.ini'}:return
 reject(event,p)
sys.addaudithook(guard)
os.chdir(I);sys.path[:0]=[str(I),str(I/'tests')]
status=1
try:
 import pytest
 status=pytest.main(['-p','no:cacheprovider','--basetemp',str(TMP/run),*args])
finally:
 torch=sys.modules.get('torch')
 output={'schema':'n30-r1-cpu-resource-v1','run':run,'pytest_exit':int(status),'process_cpu_seconds':time.process_time()-start,
  'wall_seconds':time.monotonic()-wall,'cpu_affinity':sorted(os.sched_getaffinity(0)),
  'threads':2,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],
  'cuda_initialized':None if torch is None else torch.cuda.is_initialized(),
  'denied':denied,'guard_clean':len(denied)==0,'test_args':args,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 result.write_text(json.dumps(output,indent=2)+'\n');print('N30_RESOURCE',json.dumps({**output,'denied_count':len(denied),'denied':denied[:5]}))
if denied:sys.exit(97)
sys.exit(status)
