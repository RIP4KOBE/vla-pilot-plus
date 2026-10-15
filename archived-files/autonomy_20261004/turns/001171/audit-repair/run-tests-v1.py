import sys,os,json,time,subprocess,resource
from pathlib import Path
out=Path(__file__).parent
number=sys.argv[1]
args=sys.argv[2:]
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(out/'tmp'))
start=time.monotonic(); before=resource.getrusage(resource.RUSAGE_CHILDREN)
with (out/('test-'+number+'.log')).open('w') as log:
 result=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
after=resource.getrusage(resource.RUSAGE_CHILDREN)
record=dict(command=args,exit_code=result.returncode,wall_seconds=time.monotonic()-start,cpu_user_seconds=after.ru_utime-before.ru_utime,cpu_system_seconds=after.ru_stime-before.ru_stime,environment={k:env[k] for k in ['CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','PYTHONDONTWRITEBYTECODE','TMPDIR']})
(out/('test-'+number+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record));print((out/('test-'+number+'.log')).read_text()[-18000:])
sys.exit(result.returncode)
