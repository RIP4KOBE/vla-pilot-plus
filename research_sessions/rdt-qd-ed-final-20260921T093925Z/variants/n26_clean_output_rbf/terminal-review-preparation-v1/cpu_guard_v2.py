"""Synthetic-only test launcher; no experiments, subprocesses, network or CUDA."""
import json
import os
from pathlib import Path
import sys
import signal
HERE=Path(__file__).resolve().parent
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',
                  PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
violations=[]
roots=[Path(sys.base_prefix).resolve(),Path(sys.prefix).resolve(),Path('/usr/lib').resolve(),Path('/lib').resolve()]
def under(p,base):return p==base or base in p.parents
def hook(event,args):
    if event in {'subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind','socket.getaddrinfo','ctypes.dlopen'}:
        if event=='ctypes.dlopen' and args[0] is None:return
        violations.append([event,str(args[0])[:200] if args else '']);raise PermissionError('CPU scope forbids '+event)
    if event=='import' and str(args[0]).split('.')[0] in {'torch','transformers','mujoco','robosuite','libero','requests','httpx'}:
        violations.append([event,args[0]]);raise PermissionError('runtime import blocked')
    if event in {'os.remove','os.rmdir','os.mkdir','os.rename','os.link','os.symlink'}:
        paths=args[:2] if event in {'os.rename','os.link','os.symlink'} else args[:1]
        for path in paths:
            if isinstance(path,(str,bytes,os.PathLike)) and not under(Path(os.fsdecode(path)).resolve(),HERE):
                violations.append([event,str(path)]);raise PermissionError('outside synthetic mutation scope')
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        p=Path(os.fsdecode(args[0])).resolve();mode=args[1];flags=args[2]
        writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
        allowed=under(p,HERE) or (not writing and (any(under(p,r) for r in roots) or str(p) in {'/dev/null','/etc/localtime','/etc/ld.so.cache'}))
        if not allowed:
            violations.append(['write' if writing else 'read',str(p)]);raise PermissionError('outside synthetic CPU scope: '+str(p))
sys.addaudithook(hook)
signal.alarm(180)
import pytest
log=Path(sys.argv[1]);selection=sys.argv[2:] or ['test_terminal_reader_v1.py']
rc=pytest.main(['-q','-p','no:cacheprovider','--log-file',str(HERE/(log.stem+'-pytest.log')),'--basetemp',str(HERE/('synthetic-'+log.stem)),*selection])
report={'schema':'n26-terminal-cpu-guard-v2','pytest_exit_code':rc,'violations':violations,'blocked_operations':len(violations),
        'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'torch_imported':'torch' in sys.modules,'cpu_threads':2,
        'actual_inputs_read':False,'synthetic_root':str(HERE/('synthetic-'+log.stem))}
log.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(rc or bool(violations))

