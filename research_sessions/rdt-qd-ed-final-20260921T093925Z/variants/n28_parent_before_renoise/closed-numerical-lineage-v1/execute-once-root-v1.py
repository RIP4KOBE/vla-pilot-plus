import datetime,json,os,pathlib,resource,subprocess,time
d=pathlib.Path("/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n28_parent_before_renoise/closed-numerical-lineage-v1")
out=d/'execution-v1';out.mkdir(exist_ok=True)
env=dict(os.environ);env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
start=time.monotonic();usage0=resource.getrusage(resource.RUSAGE_CHILDREN)
with (out/'console-v1.log').open('xb') as log:
 p=subprocess.Popen(["/home/hynx/miniconda3/envs/vla-pilot/bin/python",str(d/'reader-v1.py'),'--release',str(d/'execution-release-v1.json')],cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT)
 with (out/'process-v1.json').open('x') as f:json.dump({'pid':p.pid,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'start_ticks':pathlib.Path(f'/proc/{p.pid}/stat').read_text().rsplit(')',1)[1].split()[19]},f,indent=2)
 timed_out=False
 try:code=p.wait(timeout=max(.001,120-(time.monotonic()-start)))
 except subprocess.TimeoutExpired:
  timed_out=True;p.kill();code=p.wait()
elapsed=time.monotonic()-start;usage=resource.getrusage(resource.RUSAGE_CHILDREN)
r={'schema':'n28-numerical-lineage-external-process-v1','exit_code':code,'timed_out':timed_out,'whole_process_wall_seconds':elapsed,'whole_process_cpu_seconds':usage.ru_utime+usage.ru_stime-usage0.ru_utime-usage0.ru_stime,'gpu_api_simulator_calls_launched_by_wrapper':0,'reader_result_present':(out/'result-v1.json').exists(),'no_automatic_retry':True}
with (out/'external-process-result-v1.json').open('x') as f:json.dump(r,f,indent=2);f.write('\n')
print(json.dumps(r))

