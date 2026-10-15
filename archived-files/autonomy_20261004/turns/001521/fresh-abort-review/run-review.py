from pathlib import Path
import subprocess,json,os,time,datetime
OUT=Path(__file__).parent
WORK=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def put(n,v):
 p=OUT/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def identity(pid):
 a=Path('/proc')/str(pid)/'stat';s=a.read_text().rsplit(')',1)[1].split();return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(s[19]),'state':s[0]}
os.sched_setaffinity(0,{0,1})
env=os.environ.copy()
env.update({k:'2' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']})
env['PYTHONDONTWRITEBYTECODE']='1';env['CUDA_VISIBLE_DEVICES']=''
cmd=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-m','pytest','-q','tests/test_n36_engineering_integration.py::test_fresh_episode_predispatch_abort_and_exhaustion','-x']
start=time.time()
with (OUT/'test.log').open('wb') as log:
 p=subprocess.Popen(cmd,cwd=WORK,env=env,stdout=log,stderr=subprocess.STDOUT)
 put('process-v1.json',{'wrapper':identity(os.getpid()),'test':identity(p.pid),'command':cmd,'started_unix':start,'gpu_authorized':False})
 try: code=p.wait(timeout=1000);timeout=False
 except subprocess.TimeoutExpired:
  p.terminate()
  try:p.wait(timeout=20)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  code=p.returncode;timeout=True
 put('exit-v1.json',{'exit':code,'timeout':timeout,'elapsed_seconds':time.time()-start,'finished_unix':time.time()})
