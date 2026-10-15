#!/usr/bin/env python3
"""N31 pure synthetic test runner; no experiment imports or inputs."""
import os,sys,pathlib,time,resource,signal,json,stat,tempfile,traceback
START_CPU=time.process_time();START_WALL=time.monotonic()
os.sched_setaffinity(0,{0,1})
resource.setrlimit(resource.RLIMIT_CPU,(600,600))
resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
P=pathlib.Path(__file__).resolve().parent;I=P/'implementation';TMP=P/'cpu-tmp';tempfile.tempdir=str(TMP);sys.pycache_prefix=str(TMP/'pycache')
DEPS=tuple(pathlib.Path(x).resolve() for x in (sys.prefix,sys.base_prefix,'/usr/lib','/usr/lib64','/usr/local/lib','/lib','/lib64'))
def inside(p,r):return p==r or r in p.parents
# Prevent foreign worktree/PYTHONPATH entries being searched by Torch's dependency loader.
sys.path[:]=[x for x in sys.path if x and any(inside(pathlib.Path(x).resolve(),r) for r in DEPS)]
ALLOWED={str(I/'core/qd_capture_dwell_proposal.py'),str(I/'tests/test_qd_capture_dwell_proposal.py'),str(pathlib.Path(__file__).resolve())}
RUNTIME={'/proc/self/maps','/proc/cpuinfo','/etc/ld.so.cache','/etc/localtime','/etc/os-release','/usr/lib/os-release','/sys/devices/system/cpu/online'}
DENIED=[];READS=set();SCANS=set();TORCH=None;CODE=1;ERROR=None
TAG=sys.argv[1];assert TAG.startswith('run') and TAG.isalnum()
OUT=P/('cpu-'+TAG+'-resource.json');assert not OUT.exists()
def guard(event,args):
 if event=='open':
  raw,mode,flags=args
  if isinstance(raw,int):return
  p=pathlib.Path(os.path.abspath(os.fsdecode(raw)))
  writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
  if str(p)=='/dev/null':
   s=os.stat(p);ok=stat.S_ISCHR(s.st_mode) and os.major(s.st_rdev)==1 and os.minor(s.st_rdev)==3
  elif writing:ok=p==OUT or inside(p,TMP)
  else:
   ok=str(p) in ALLOWED or str(p) in RUNTIME or inside(p,TMP) or (any(inside(p.resolve(),r) for r in DEPS) and p.suffix not in {'.pt','.pth','.pkl','.pickle','.npy','.npz','.safetensors','.ckpt'})
  if not ok:DENIED.append({'event':event,'path':str(p),'writing':writing});raise PermissionError('N31 guard '+str(p))
  if not writing:READS.add(str(p))
 elif event in {'os.listdir','os.scandir'}:
  raw=args[0]
  if isinstance(raw,int):return
  p=pathlib.Path(os.path.abspath(os.fsdecode(raw)))
  ok=inside(p,TMP) or p in (P,I/'tests',I/'core') or any(inside(p.resolve(),r) for r in DEPS)
  if not ok:DENIED.append({'event':event,'path':str(p)});raise PermissionError('N31 guard directory '+str(p))
  SCANS.add(str(p))
 elif event.startswith(('socket.','subprocess.')) or event in {'os.system','os.exec','os.fork','os.posix_spawn','pty.spawn'}:
  DENIED.append({'event':event});raise PermissionError(event)
 elif event=='import' and args[0].split('.')[0] in {'main','core','requests','httpx','robosuite','libero','transformers','diffusers'}:
  DENIED.append({'event':event,'module':args[0]});raise PermissionError('production/network import')
sys.addaudithook(guard)
def deadline(*_):raise TimeoutError('CPU suite deadline')
signal.signal(signal.SIGALRM,deadline);signal.signal(signal.SIGXCPU,deadline);signal.alarm(899)
try:
 import torch
 TORCH=torch;torch.set_num_threads(2);torch.set_num_interop_threads(2)
 assert not torch.cuda.is_initialized()
 import pytest
 CODE=pytest.main(['-q','-p','no:cacheprovider','--noconftest','--confcutdir='+str(I/'tests'),'--rootdir='+str(TMP),str(I/'tests/test_qd_capture_dwell_proposal.py')]+sys.argv[2:])
 assert not torch.cuda.is_initialized()
except BaseException as e:
 ERROR={'type':type(e).__name__,'message':str(e)};traceback.print_exc();CODE=1
finally:
 signal.alarm(0)
 out={'schema':'n31-pure-cpu-test-resource-v1','pid':os.getpid(),'exit_code':int(CODE),'error':ERROR,'cpu_seconds':time.process_time()-START_CPU,'wall_seconds':time.monotonic()-START_WALL,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'cpu_limit':list(resource.getrlimit(resource.RLIMIT_CPU)),'AS_limit':resource.getrlimit(resource.RLIMIT_AS)[0],'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'cuda_initialized':TORCH.cuda.is_initialized() if TORCH is not None else None,'explicit_cuda_tensor_work':0,'guard_clean':not DENIED,'denied':DENIED,'reads':sorted(READS),'scans':sorted(SCANS),'tests_only_synthetic':True,'production_imports':False,'historical_payload_reads':0}
 with OUT.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
if CODE or DENIED:sys.exit(1)
