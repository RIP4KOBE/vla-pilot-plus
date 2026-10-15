import os,json,subprocess,time,resource,pathlib,hashlib
O=pathlib.Path(__file__).parent;a=json.load(open(O/'authority-v1.json'));d=json.load(open(a['draft']['path']));r=json.load(open(d['runtime']['path']));cl=json.load(open(d['runtime_closure']['path']))
env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',**r['environment'],'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','PYTHONDONTWRITEBYTECODE':'1'}
for k,sub in [('TMPDIR','tmp'),('MPLCONFIGDIR','mpl'),('NUMBA_CACHE_DIR','numba'),('XDG_CACHE_HOME','cache')]:
 p=O/sub;p.mkdir(exist_ok=True);env[k]=str(p)
env['PYTHONPATH']=str(O)+':'+env['PYTHONPATH'];cpus=sorted(os.sched_getaffinity(0))[:2]
def limits():os.sched_setaffinity(0,cpus);resource.setrlimit(resource.RLIMIT_CPU,(100,100))
cmd=[cl['interpreter']['path'],'-I','-S','-B','-X','pycache_prefix=/dev/null',str(pathlib.Path(a['owning_worktree'])/'scripts/qd_ed_n36_bootstrap.py'),'runner_probe_v1']
t=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
with open(O/'runner-probe-v1.log','w') as log:p=subprocess.run(cmd,cwd=a['owning_worktree'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=150,preexec_fn=limits)
after=resource.getrusage(resource.RUSAGE_CHILDREN)
v={'command':cmd,'cwd':a['owning_worktree'],'exit_code':p.returncode,'wall_seconds':time.monotonic()-t,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'affinity':cpus,'CUDA_VISIBLE_DEVICES':'','threads':2,'purpose':'Resolve omitted actual public runner import in preparation, no preparation rerun','environment_values_not_dumped':True}
(O/'runner-parent-timing-v1.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
