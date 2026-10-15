"""External synthetic test receipt, no production entrypoint."""
from pathlib import Path
import json,hashlib,subprocess,time,resource,os,sys
p=Path(__file__).resolve().parent;i=p/'implementation';tag=sys.argv[1]
prior=[json.loads(f.read_text()) for f in p.glob('cpu-phase-c-run*-external.json')]
cpu=sum(x['child_cpu_seconds'] for x in prior);wall=sum(x['wall_seconds'] for x in prior)
paths=list((i/'scripts').glob('*.py'))+list((i/'core').rglob('*.py'))+list((i/'tests').glob('*n31*.py'))+[p/'cpu_phase_c_guard_v2.py',Path(__file__).resolve()]
source=[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(set(paths))]
with (p/f'cpu-phase-c-{tag}-source.json').open('x') as f:json.dump(source,f,indent=2)
cmd=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-I','-B',str(p/'cpu_phase_c_guard_v2.py'),tag,str(int(1200-cpu)),str(int(1800-wall)),*sys.argv[2:]]
start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
with (p/f'cpu-phase-c-{tag}.log').open('x') as log:
 child=subprocess.Popen(cmd,cwd=i,stdout=log,stderr=subprocess.STDOUT);pid=child.pid
 print('pid',pid,flush=True);exitcode=child.wait(timeout=int(1800-wall))
after=resource.getrusage(resource.RUSAGE_CHILDREN);record={'argv':cmd,'cwd':str(i),'pid':pid,'exit':exitcode,'wall_seconds':time.monotonic()-start,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime}
with (p/f'cpu-phase-c-{tag}-external.json').open('x') as f:json.dump(record,f,indent=2)
print(record);print((p/f'cpu-phase-c-{tag}.log').read_text()[-9000:])
