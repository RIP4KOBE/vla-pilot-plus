"""N29 synthetic-only runner. Pure helpers; no policy/environment import."""
import os, sys, json, time, resource, stat, tempfile, types
from pathlib import Path
V=Path(__file__).resolve().parent
I=V/'implementation'
PYROOT=Path(sys.prefix).resolve()
TMP=V/'tmp'
tempfile.tempdir=str(TMP)
sys.pycache_prefix=str(TMP/'empty-pycache')
sys.dont_write_bytecode=True
os.sched_setaffinity(0,{0,1})
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'))
resource.setrlimit(resource.RLIMIT_CPU,(90,95))
allowed={I/'tests/test_qd_population_relative_trust.py',I/'core/qd_population_relative_trust.py',I/'core/qd_feasible_ray_update.py',V/'cpu_guard_v2.py'}
allowed={p.resolve() for p in allowed}
summary=V/'cpu-test-run2-guard.json'
denied=[]
def within(p,root):
    return p==root or root in p.parents
def guard(event,args):
    if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn','socket.connect','socket.bind','socket.getaddrinfo'):
        denied.append({'event':event});raise RuntimeError('N29 denied operation '+event)
    if event=='open':
        value=args[0]
        if isinstance(value,int):return
        p=Path(os.fsdecode(value)).absolute().resolve()
        mode=args[1];flags=args[2] or 0
        writing=(isinstance(mode,str) and any(x in mode for x in 'wa+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if p==Path('/dev/null') and stat.S_ISCHR(p.stat().st_mode):return
        if writing:
            ok=within(p,TMP) or p==summary
        else:
            ok=p in allowed or within(p,TMP) or within(p,PYROOT) or p in {Path('/proc/self/maps').resolve(),Path('/proc/cpuinfo'),Path('/usr/share/zoneinfo/Etc/UTC'),Path('/etc/localtime').resolve()}
        if not ok:
            denied.append({'event':'open','path':str(p),'writing':writing});raise RuntimeError('N29 denied file '+str(p))
sys.addaudithook(guard)
# Deliberately bypass side-effecting core.__init__: only pure source modules load.
core=types.ModuleType('core');core.__path__=[str(I/'core')];sys.modules['core']=core
started=time.monotonic();code=1;error=None
try:
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(2)
    import pytest
    code=pytest.main(['--noconftest','--assert=plain','--import-mode=importlib','-p','no:cacheprovider','-q',str(I/'tests/test_qd_population_relative_trust.py')])
except BaseException as exc:
    import traceback
    error=repr(exc);traceback.print_exc()
finally:
    torch_module=sys.modules.get('torch')
    initialized=bool(torch_module.cuda.is_initialized()) if torch_module else None
    r=resource.getrusage(resource.RUSAGE_SELF)
    result={'schema':'n29-cpu-test-guard-v1','pytest_exit_code':int(code),'error':error,'guard_denials':denied,'cpu_seconds':r.ru_utime+r.ru_stime,'wall_seconds':time.monotonic()-started,'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'cuda_initialized':initialized,'peak_rss_kib':r.ru_maxrss,'pure_package_mount':True}
    summary.write_text(json.dumps(result,indent=2)+'\n')
    print('N29_GUARD',json.dumps(result))
    if denied or initialized:code=2
sys.exit(code)
