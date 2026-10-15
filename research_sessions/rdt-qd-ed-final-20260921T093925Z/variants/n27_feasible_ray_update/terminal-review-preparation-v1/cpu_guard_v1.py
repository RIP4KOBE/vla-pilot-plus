"""Synthetic-only guard. Actual inventories remain forbidden during preparation."""
import os,sys,time,json,pathlib,signal,tempfile
HERE=pathlib.Path(__file__).absolute().parent
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
TMP=HERE/'synthetic_tmp';TMP.mkdir(exist_ok=True);tempfile.tempdir=str(TMP)
allowed=[pathlib.Path(sys.prefix),pathlib.Path(sys.base_prefix),pathlib.Path('/usr/lib'),pathlib.Path('/usr/local/lib')]
denied=[]
def guard(event,args):
    if event=='import' and args and str(args[0]).split('.')[0] in {'torch','tensorflow','jax','robosuite'}:
        denied.append([event,str(args[0])]);raise RuntimeError('guard forbidden runtime import')
    if event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.posix_spawn'}:
        denied.append([event,'operation']);raise RuntimeError('guard forbidden process/network')
    if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
        p=pathlib.Path(os.fsdecode(args[0])).absolute();flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
        write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        owned=p==HERE or HERE in p.parents
        install=any(p==a or a in p.parents for a in allowed)
        if (write and not owned) or (not write and not owned and not install):
            denied.append([event,str(p)]);raise RuntimeError('guard forbidden file '+str(p))
sys.addaudithook(guard)
start=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('120-second aggregate test ceiling')));signal.alarm(int(os.environ.get('N27_CPU_SECONDS_REMAINING','120')))
exitcode=1
try:
    import pytest
    exitcode=pytest.main(sys.argv[1:])
finally:
    signal.alarm(0)
    print('GUARD_SUMMARY '+json.dumps({'elapsed_seconds':time.monotonic()-start,'denied':denied,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'torch_imported':'torch' in sys.modules,'thread_cap':2,'exitcode':exitcode}),flush=True)
if denied:raise SystemExit(91)
raise SystemExit(exitcode)
