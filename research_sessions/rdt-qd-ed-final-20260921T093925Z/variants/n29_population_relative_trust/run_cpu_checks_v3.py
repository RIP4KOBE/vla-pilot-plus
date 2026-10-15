from pathlib import Path
import os,sys,time,json,subprocess,resource,math
V=Path(__file__).resolve().parent
ledger=V/'cpu-phase-a-resource-v1.json'
data=json.loads(ledger.read_text())
# Includes bounded uninstrumented stdlib/tool-startup preparation conservatively.
data['additional_preparation_allowance_seconds']=10
used=data.get('startup_allowance_seconds',0)+data['additional_preparation_allowance_seconds']+sum(x.get('self_cpu_seconds',0)+x.get('children_cpu_seconds',0) for x in data['calls'])
assert used+95<180
cmd=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B',str(V/'cpu_guard_v3.py')]
env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
a=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic();c=time.process_time()
with (V/'cpu-test-run3.log').open('x') as f:
    try:p=subprocess.run(cmd,env=env,cwd=V,stdout=f,stderr=subprocess.STDOUT,timeout=100);exit_code=p.returncode
    except subprocess.TimeoutExpired:exit_code=124;f.write('\nTIMEOUT\n')
b=resource.getrusage(resource.RUSAGE_CHILDREN)
record={'phase':'focused_synthetic_run3','command':cmd,'environment':{k:env[k] for k in ['PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE','CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']},'self_cpu_seconds':time.process_time()-c,'children_cpu_seconds':b.ru_utime+b.ru_stime-a.ru_utime-a.ru_stime,'wall_seconds':time.monotonic()-start,'exit_code':exit_code,'log':str(V/'cpu-test-run3.log')}
data['calls'].append(record);data['tests_started']=True
data['cumulative_accounted_cpu_seconds']=used+record['self_cpu_seconds']+record['children_cpu_seconds']
ledger.write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(record));print('CUMULATIVE',data['cumulative_accounted_cpu_seconds'])
sys.exit(exit_code)
