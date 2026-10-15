import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
out=Path(__file__).resolve().parent
name=sys.argv[1];command=sys.argv[2:]
env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1','GIT_NO_LAZY_FETCH':'1'}
start=time.monotonic()
p=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
log=out/(name+'.log');log.write_bytes(p.stdout)
record={'argv':command,'cwd':str(Path.cwd()),'environment':{k:env[k] for k in ('CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONDONTWRITEBYTECODE','GIT_NO_LAZY_FETCH')},'exit':p.returncode,'seconds':time.monotonic()-start,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'log':log.name,'sha256':hashlib.sha256(p.stdout).hexdigest()}
(out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(p.stdout.decode());sys.exit(p.returncode)
