"""Exact static source reads + owned synthetic/config-copy writes; no runtime calls."""
import os,sys,time,json,pathlib,signal,tempfile,runpy
HERE=pathlib.Path(__file__).absolute().parent
static={pathlib.Path(x['path']) for x in json.loads((HERE/'static-inputs-v1.json').read_text())['files']}
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
sys.dont_write_bytecode=True
TMP=HERE/'tmp';TMP.mkdir(exist_ok=True);tempfile.tempdir=str(TMP)
allowed=[pathlib.Path(sys.prefix),pathlib.Path(sys.base_prefix),pathlib.Path('/usr/lib'),pathlib.Path('/usr/local/lib')]
denied=[]
def guard(event,args):
 if event=='import' and args and str(args[0]).split('.')[0] in {'torch','tensorflow','jax','robosuite','libero','main','core','scripts'}:
  denied.append([event,str(args[0])]);raise RuntimeError('forbidden runtime import')
 if event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.posix_spawn'}:
  denied.append([event,'operation']);raise RuntimeError('forbidden process/network')
 if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
  p=pathlib.Path(os.fsdecode(args[0])).absolute();flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
  writing=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND));owned=p==HERE or HERE in p.parents
  permitted=p in static or any(p==a or a in p.parents for a in allowed)
  if (writing and not owned) or (not writing and not owned and not permitted):
   denied.append([event,str(p)]);raise RuntimeError('forbidden file '+str(p))
sys.addaudithook(guard);started=time.monotonic();code=1
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('60-second CPU test envelope')));signal.alarm(int(os.environ.get('N27_HYDRA_SECONDS_REMAINING','60')))
try:
 runpy.run_path(str(HERE/'check_hydra_cpu_v1.py'),run_name='__main__');code=0
finally:
 signal.alarm(0);print('GUARD_SUMMARY '+json.dumps({'seconds':time.monotonic()-started,'denied':denied,'exitcode':code,'threads':2,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'torch_imported':'torch' in sys.modules}),flush=True)
if denied:raise SystemExit(91)
