import os,sys,json,hashlib,time,traceback
from pathlib import Path
O=Path(__file__).resolve().parent;g=json.loads((O/'graph.complete-disabled-v1.json').read_text());sys.dont_write_bytecode=True
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1',QD_ED_N36_R1_SPECIFICATION=json.dumps(g['specification']),TMPDIR=str(O/'tmp'))
(O/'tmp').mkdir(exist_ok=True);sys.path.insert(0,g['actual_source_worktree'])
def hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]);p=Path(name);mode,flags=args[1:3]
  if p.name in ('auth.json','credentials.json','.env','state.json','checkpoint.json','research-state.yaml') or '2026-08-10-eds-qd-stage-guidance-transition-design.md' in name or '/dev/nvidia' in name or ('/results/' in name and any(s in name for s in ('formal','validation'))):raise PermissionError('prohibited input')
  writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
  if writing and name!='/dev/null' and not p.resolve().is_relative_to(O):raise PermissionError('out of scope write')
 if event in ('socket.connect','socket.bind'):raise PermissionError('network prohibited')
 if event=='subprocess.Popen' and Path(str(args[0])).name not in ('git','uname','ldconfig'):raise PermissionError('CPU subprocess only')
sys.addaudithook(hook)
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_readiness_prepare as prep
checks=[]
def check(name,fn):
 t=time.monotonic()
 try:fn();checks.append(dict(check=name,status='PASS',elapsed_seconds=time.monotonic()-t))
 except Exception as ex:checks.append(dict(check=name,status='BLOCKED',error_type=type(ex).__name__,error=str(ex),elapsed_seconds=time.monotonic()-t))
spec=e.read(g['specification'])
if '--preflight' in sys.argv:
 check('production preparation policy',lambda:prep.policy(spec))
 check('production recovery contract',lambda:e._recovery_contract(spec))
 check('production specification entrypoint',e.specification)
 from scripts.qd_ed_n34_controller import verify_semantics
 check('production controller semantics',lambda:verify_semantics(g['controller_semantics'],g['runtime'],e.read(g['runtime_closure'])))
else:
 def full():
  s=e.specification();prep.verify_graph({'graph':{'plan':g['plan'],'runtime':g['runtime']}},e.read(g['source_record']),e.read(s['canonical_runtime']))
 check('strict production disabled graph admission all41',full)
r=dict(status='PASS' if all(x['status']=='PASS' for x in checks) else 'BLOCKED',checks=checks,full_graph_audit_run='--preflight' not in sys.argv,measurement_run=False,source_monkeypatched=False,graph=dict(path=str(O/'graph.complete-disabled-v1.json'),sha256=hashlib.sha256((O/'graph.complete-disabled-v1.json').read_bytes()).hexdigest()))
name='production-preflight-result-v1.json' if '--preflight' in sys.argv else 'strict-production-admission-result-v1.json'
with (O/name).open('x') as f:json.dump(r,f,indent=2)
print(json.dumps(r));sys.exit(0 if r['status']=='PASS' else 1)
