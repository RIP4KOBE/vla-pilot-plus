import os,sys,time,resource,json,hashlib,pathlib,runpy,traceback
P=pathlib.Path(__file__).resolve().parent;start=time.process_time();wall=time.monotonic();os.sched_setaffinity(0,{0,1});resource.setrlimit(resource.RLIMIT_CPU,(120,120))
sys.dont_write_bytecode=True;os.environ['PYTHONDONTWRITEBYTECODE']='1';denied=[]
source={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ('driver_v1.py','test_driver_v1.py','run_cpu_tests_v1.py')}
deps=[pathlib.Path(sys.prefix).resolve(),pathlib.Path(sys.base_prefix).resolve(),pathlib.Path('/usr/lib'),pathlib.Path('/lib')]
def inside(p,r):return p==r or r in p.parents
def guard(event,args):
 if event=='open':
  name,mode,flags=args
  if isinstance(name,int):return
  p=pathlib.Path(os.path.abspath(os.fsdecode(name)));write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
  ok=inside(p,P) or (not write and (any(inside(p.resolve(),r) for r in deps) or str(p)=='/proc/sys/kernel/random/boot_id' or (str(p).startswith('/proc/') and p.name=='stat' and p.parent.name.isdigit())))
  if not ok:denied.append({'event':event,'path':str(p)});raise PermissionError(str(p))
 elif event.startswith('socket.') or event in {'os.system','os.exec','os.posix_spawn'}:denied.append({'event':event});raise PermissionError(event)
 elif event=='subprocess.Popen':
  executable,argv,cwd,env=args
  if pathlib.Path(executable).resolve()!=pathlib.Path(sys.executable).resolve() or not inside(pathlib.Path(cwd),P):denied.append({'event':event});raise PermissionError('only synthetic Python child in owned scratch')
sys.addaudithook(guard);code=0
try:
 sys.argv=[str(P/'test_driver_v1.py')];runpy.run_path(str(P/'test_driver_v1.py'),run_name='__main__')
except SystemExit as e:code=int(e.code or 0)
except BaseException:traceback.print_exc();code=1
r={'schema':'autonomy-driver-cpu-test-resource-v1','source_hashes':source,'exit':code,'guard_clean':not denied,'denied':denied,'cpu_seconds':time.process_time()-start,'child_cpu_seconds':resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,'wall_seconds':time.monotonic()-wall,'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'official_cli_calls':0,'gpu_api_model_sim_calls':0}
with (P/'cpu-test-resource-v1.json').open('x') as f:json.dump(r,f,indent=2);f.write('\n')
sys.exit(code or bool(denied))
