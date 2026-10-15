#!/usr/bin/env python3
"""Durable external lifetime receipt for the already released N31 supervisor."""
from pathlib import Path
import datetime,fcntl,hashlib,json,os,subprocess,sys,time
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree';E=P/'execution'
PY='/home/hynx/miniconda3/envs/vla-pilot/bin/python'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def identity(pid):
 return {'pid':pid,'proc_start_ticks':(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[19],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
def save(p,v):
 tmp=p.with_name(p.name+'.tmp')
 with tmp.open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def monitor():
 E.mkdir(exist_ok=True)
 with (E/'launch.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  assert not (E/'root-launch-v1.json').exists() and not (E/'supervisor-status-v1.json').exists()
  release=json.loads((P/'execution-release-v1.json').read_text());plan=P/'plan.frozen.v1.gpu7.json';assert release['plan']==ref(plan)
  cmd=[PY,'-B',str(W/'scripts/qd_ed_n31_supervise.py'),'--plan',str(plan),'--release',str(P/'execution-release-v1.json'),'--status',str(E/'supervisor-status-v1.json')]
  env=dict(os.environ);env['PYTHONUNBUFFERED']='1';env['PYTHONDONTWRITEBYTECODE']='1';env['CUDA_VISIBLE_DEVICES']=''
  start=time.monotonic()
  with (E/'supervisor.log').open('x') as log:
   child=subprocess.Popen(cmd,cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   launched={'schema':'n31-external-supervisor-launch-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monitor':identity(os.getpid()),'controller':identity(child.pid),'argv':cmd,'cwd':str(W),'plan':ref(plan),'release':ref(P/'execution-release-v1.json'),'admission':ref(P/'root-execution-admission-v1.json'),'source_commit':release['source_commit'],'log':str(E/'supervisor.log'),'GPU_worker_limit':1}
   save(E/'root-launch-v1.json',launched)
   code=child.wait()
  save(E/'root-launch-result-v1.json',{'schema':'n31-external-supervisor-result-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'launch':ref(E/'root-launch-v1.json'),'controller':launched['controller'],'exit_code':code,'wall_seconds':time.monotonic()-start,'controller_reaped':True,'final_status_file':str(E/'supervisor-status-v1.json'),'result_file':str(P/'result-v1.json')})
if __name__=='__main__':
 if sys.argv[1:] == ['--monitor']:monitor()
 else:
  assert not sys.argv[1:];E.mkdir(exist_ok=True)
  assert (P/'execution-release-v1.json').is_file()
  with (E/'external-monitor.log').open('x') as log:
   process=subprocess.Popen([PY,'-I','-B',str(Path(__file__).resolve()),'--monitor'],cwd=W,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  print(json.dumps({'monitor_pid':process.pid,'launch_path':str(E/'root-launch-v1.json')}))

