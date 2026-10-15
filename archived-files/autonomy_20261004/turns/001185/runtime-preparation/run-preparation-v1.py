import os,json,time,resource,subprocess,hashlib,tarfile,io,datetime
from pathlib import Path
OUT=Path(__file__).resolve().parent
start=time.monotonic(); cpu0=time.process_time(); at=datetime.datetime.now(datetime.timezone.utc).isoformat()
a=json.loads((OUT/'authority-v1.json').read_text()); root=Path(a['owning_worktree'])
turns=OUT.parent.parent
old=json.loads((turns/'000916/runtime-v1/runtime-closure-v1.json').read_text())
r=json.loads(Path(old['runtime']['path']).read_text())
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
records=[]
for dep in r['dependencies']:
 target=OUT/'materialized'/Path(dep['target']).name; target.mkdir(parents=True)
 cmd=['git','--no-replace-objects','-C',dep['source'],'archive','--format=tar',dep['commit']]
 t=time.monotonic(); raw=subprocess.check_output(cmd,env={**os.environ,'GIT_NO_LAZY_FETCH':'1'}); digest=hashlib.sha256(raw).hexdigest(); assert digest==dep['archive_sha256']
 arc=OUT/'materialized'/(target.name+'.tar');arc.write_bytes(raw)
 with tarfile.open(fileobj=io.BytesIO(raw)) as tf: tf.extractall(target,filter='data')
 records.append({'dependency':target.name,'pin':dep['commit'],'archive_sha256':digest,'archive_bytes':len(raw),'path':str(target),'prospective_path':dep['target'],'command':cmd,'wall_seconds':time.monotonic()-t})
(OUT/'materialization-v1.json').write_text(json.dumps(records,indent=2)+'\n')
assert sha(old['interpreter']['path'])==old['interpreter']['sha256']
# Existing full environment is read-only; source loader prevents cache reads/writes.
env={k:os.environ[k] for k in ['PATH','LANG','LC_ALL','LD_LIBRARY_PATH'] if k in os.environ}
env.update(r['environment']); env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1',N36_PREPARATION_OUTPUT=str(OUT),TMPDIR=str(OUT/'tmp'),MPLCONFIGDIR=str(OUT/'mpl'),NUMBA_CACHE_DIR=str(OUT/'numba'),XDG_CACHE_HOME=str(OUT/'cache'))
for k in ['TMPDIR','MPLCONFIGDIR','NUMBA_CACHE_DIR','XDG_CACHE_HOME']:Path(env[k]).mkdir(exist_ok=True)
env['PYTHONPATH']=str(OUT)+':'+env['PYTHONPATH']
cpus=sorted(os.sched_getaffinity(0))[:2]
cmd=[old['interpreter']['path'],'-I','-S','-B','-X','pycache_prefix=/dev/null',str(root/'scripts/qd_ed_n36_bootstrap.py'),'startup_probe_v1']
def limits():
 os.sched_setaffinity(0,cpus);resource.setrlimit(resource.RLIMIT_CPU,(750,750))
t=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
with open(OUT/'startup-v1.log','w') as log:
 proc=subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=840,preexec_fn=limits)
after=resource.getrusage(resource.RUSAGE_CHILDREN)
receipt={'schema':'n36-preparation-parent-timing-v1','started_at':at,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':cmd,'cwd':str(root),'environment':env,'affinity':cpus,'exit_code':proc.returncode,'startup_parent_wall_seconds':time.monotonic()-t,'startup_child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'peak_child_rss_kib':after.ru_maxrss,'preparation_parent_wall_seconds':time.monotonic()-start,'preparation_parent_cpu_seconds':time.process_time()-cpu0,'preparation_all_child_cpu_seconds':after.ru_utime+after.ru_stime,'includes_interpreter_bootstrap_imports':True,'materialization':records,'shared_dependencies_mutated':False}
(OUT/'parent-timing-v1.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ['environment','materialization']},indent=2))
