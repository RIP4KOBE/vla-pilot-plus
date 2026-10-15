"""Guarded synthetic scalar checks; exact two external pure dependencies only."""
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
HERE=Path(__file__).resolve().parent
STATIC={str((HERE.parent/'terminal-review-preparation-v1'/name).resolve()) for name in ('bounded_metadata_v1.py','metadata_semantics_v1.py')}
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
(HERE/'tmp').mkdir(exist_ok=True);tempfile.tempdir=str(HERE/'tmp')
ROOTS=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve(),Path('/usr/lib').resolve(),Path('/lib').resolve()]
violations=[]
def under(p,base):return p==base or base in p.parents
def deny(event,path):
    violations.append([event,str(path)]);raise PermissionError('summary CPU scope: '+str(path))
def hook(event,args):
    if event in {'subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind','socket.getaddrinfo','ctypes.dlopen'}:
        if event=='ctypes.dlopen' and args[0] is None:return
        deny(event,args[0] if args else '')
    if event=='import' and str(args[0]).split('.')[0] in {'torch','transformers','mujoco','robosuite','libero','requests','httpx'}:deny(event,args[0])
    if event in {'os.remove','os.rmdir','os.mkdir','os.rename','os.link','os.symlink'}:
        for p in args[:2] if event in {'os.rename','os.link','os.symlink'} else args[:1]:
            if isinstance(p,(str,bytes,os.PathLike)) and not under(Path(os.fsdecode(p)).resolve(),HERE):deny(event,p)
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        p=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1:3]
        write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
        allowed=under(p,HERE) or (not write and (str(p) in STATIC or any(under(p,r) for r in ROOTS) or str(p) in {'/dev/null','/etc/localtime','/etc/ld.so.cache'}))
        if not allowed:deny('write' if write else 'read',p)
sys.addaudithook(hook);signal.alarm(120)
import pytest
log=Path(sys.argv[1]);selection=sys.argv[2:] or ['test_scalar_summary_v1.py']
rc=pytest.main(['-q','-p','no:cacheprovider','--log-file',str(HERE/(log.stem+'-pytest.log')),'--basetemp',str(HERE/('synthetic-'+log.stem)),*selection])
log.write_text(json.dumps({'schema':'n26-scalar-cpu-guard-v1','pytest_exit_code':rc,'violations':violations,'blocked_operations':len(violations),
 'torch_imported':'torch' in sys.modules,'actual_experiment_inputs_read':False,'cpu_threads':2,'cuda_visible_devices':'','external_static_paths':sorted(STATIC)},indent=2)+'\n')
raise SystemExit(rc or bool(violations))
