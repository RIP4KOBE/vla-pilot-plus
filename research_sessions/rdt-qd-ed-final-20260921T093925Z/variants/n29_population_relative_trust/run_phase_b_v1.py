from pathlib import Path
import os,sys,json,resource,subprocess,time
V=Path(__file__).resolve().parent
num=int(sys.argv[1]);d=json.loads((V/'phase-b-resource-v1.json').read_text())
used=d['prior_phase_a_cpu_seconds']+d['preparation_allowance_seconds']+sum(x.get('children_cpu_seconds',0)+x.get('self_cpu_seconds',0) for x in d['calls'])
assert used+85<180
cmd=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B',str(V/f'phase_b_guard_v{num}.py')]
env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
t=time.monotonic();c=time.process_time();a=resource.getrusage(resource.RUSAGE_CHILDREN)
with (V/f'phase-b-run{num}.log').open('x') as log:
 try:p=subprocess.run(cmd,env=env,cwd=V,stdout=log,stderr=subprocess.STDOUT,timeout=100);code=p.returncode
 except subprocess.TimeoutExpired:code=124;log.write('\nTIMEOUT\n')
b=resource.getrusage(resource.RUSAGE_CHILDREN)
record={'phase':f'phase_b_run{num}','argv':cmd,'environment':{k:env[k] for k in ('PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE','CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},'children_cpu_seconds':b.ru_utime+b.ru_stime-a.ru_utime-a.ru_stime,'self_cpu_seconds':time.process_time()-c,'wall_seconds':time.monotonic()-t,'exit_code':code}
d['calls'].append(record);d['cumulative_n29_cpu_seconds']=used+record['children_cpu_seconds']+record['self_cpu_seconds'];d['tests_started']=True
(V/'phase-b-resource-v1.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(record));print('CUMULATIVE',d['cumulative_n29_cpu_seconds']);sys.exit(code)
