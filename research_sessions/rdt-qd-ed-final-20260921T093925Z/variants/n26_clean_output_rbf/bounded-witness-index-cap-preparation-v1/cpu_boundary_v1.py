"""CPU-only process boundary for this standalone reader and its owned tests."""
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
AS_CAP = 8 * 1024**3
DENIED = []


def establish(seconds=180):
    if 'torch' in sys.modules:
        raise RuntimeError('address-space boundary must precede Torch import')
    resource.setrlimit(resource.RLIMIT_AS, (AS_CAP, AS_CAP))
    resource.setrlimit(resource.RLIMIT_CORE, (0,0))
    if resource.getrlimit(resource.RLIMIT_AS) != (AS_CAP, AS_CAP):
        raise RuntimeError('address-space limit not active')
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
    os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                      OPENBLAS_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2',
                      PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(HERE)
    # The environment's editable/PYTHONPATH entries may name old experiment
    # trees. Torch's optional dependency search must never traverse them.
    roots=tuple(Path(p).resolve() for p in (sys.prefix,sys.base_prefix))
    sys.path[:]=[p for p in sys.path if p and any(Path(p).resolve()==r or r in Path(p).resolve().parents for r in roots)]
    def timeout(_signum, _frame):
        raise TimeoutError('CPU reader/test wall-time cap')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)


def guard(*, inputs=(), writes=(), test_children=()):
    allowed = {str(Path(p).absolute()) for p in inputs}
    writable = {str(Path(p).absolute()) for p in writes}
    dependency_roots = tuple(Path(p).resolve() for p in {sys.prefix, sys.base_prefix, '/usr/lib', '/lib'})
    # Owned test harness may register an exact child argv after hashing its newly
    # written synthetic manifest. The reader itself never supplies this set.
    child_commands = test_children if type(test_children) is set else {tuple(v) for v in test_children}
    devnull=Path('/dev/null');device=devnull.stat()
    if devnull.is_symlink() or not stat.S_ISCHR(device.st_mode) or (os.major(device.st_rdev),os.minor(device.st_rdev))!=(1,3):
        raise RuntimeError('/dev/null is not the expected Linux null character device')
    def reject(event, target):
        DENIED.append({'event':event, 'target':str(target)})
        raise PermissionError(f'CPU guard: {event}: {target}')
    def dependency(p):
        q=p.resolve()
        return any(q==root or root in q.parents for root in dependency_roots)
    def hook(event,args):
        if event=='open':
            raw,mode,flags=args
            if isinstance(raw,int):return
            p=Path(os.fsdecode(raw)).absolute();name=str(p)
            writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
            if p==devnull:return
            if name=='/proc/self/maps' and not writing:
                caller=sys._getframe(1)
                expected=Path(sys.prefix)/'lib/python3.12/site-packages/torch/__init__.py'
                if caller.f_code.co_name=='_load_global_deps' and Path(caller.f_code.co_filename)==expected:
                    return
            if writing:
                if name not in writable or p.is_symlink():reject(event,name)
            elif name not in allowed and not dependency(p) and name not in {'/dev/null','/etc/localtime','/etc/ld.so.cache'} and p!=HERE:
                reject(event,name)
        elif event in {'os.listdir','os.scandir'}:
            raw=args[0]
            if isinstance(raw,int):reject(event,'directory descriptor')
            p=Path(os.fsdecode(raw or '.')).absolute()
            if p!=HERE and not dependency(p):reject(event,p)
        elif event=='os.chdir':
            if Path(args[0]).absolute()!=HERE:reject(event,args[0])
        elif event=='subprocess.Popen':
            if tuple(args[1]) not in child_commands:reject(event,'unlisted child')
        elif event=='ctypes.dlopen':
            if args[0] is not None and not dependency(Path(args[0]).absolute()):reject(event,args[0])
        elif event in {'os.system','os.fork','os.posix_spawn','socket.__new__','socket.connect','socket.bind','socket.getaddrinfo',
                       'os.remove','os.rename','os.rmdir','os.mkdir','os.symlink','os.link','os.truncate','os.chmod','os.chown'}:
            reject(event,'forbidden operation')
        elif event=='import' and args[0].split('.')[0] in {'transformers','mujoco','libero','robosuite','requests','httpx'}:
            reject(event,args[0])
    sys.addaudithook(hook)


def observation():
    t=sys.modules.get('torch')
    return {'rlimit_as_bytes':list(resource.getrlimit(resource.RLIMIT_AS)),
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'rss_is_observed_not_a_hard_cap':True,'cpu_affinity':len(os.sched_getaffinity(0)),
            'module_search_paths':list(sys.path),'core_dump_limit':list(resource.getrlimit(resource.RLIMIT_CORE)),
            'torch_intraop_threads':None if t is None else t.get_num_threads(),
            'torch_interop_threads':None if t is None else t.get_num_interop_threads(),
            'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),
            'cuda_initialized':False if t is None else t.cuda.is_initialized(),
            'guard_denials':list(DENIED)}


if __name__=='__main__':
    start=time.monotonic()
    establish(20)
    guard(inputs=[__file__])
    if sys.argv[1:]!=['--allocation-probe']:raise ValueError('unknown probe')
    refused=False
    try:
        excessive=bytearray(AS_CAP+1)
    except MemoryError:
        refused=True
    if not refused:raise RuntimeError('allocation exceeded OS ceiling')
    print(json.dumps({'allocation_refused':refused,'requested_bytes':AS_CAP+1,
                      'elapsed_seconds':time.monotonic()-start,**observation()}))
