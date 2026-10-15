import os,sys,json,pathlib,datetime,traceback,time,tempfile
P=pathlib.Path;O=P(__file__).resolve().parent;g=json.loads((O/'graph.complete-disabled-v1.json').read_text());sys.dont_write_bytecode=True
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',QD_ED_N36_R1_SPECIFICATION=json.dumps(g['specification']))
(O/'tmp').mkdir(exist_ok=True);tempfile.tempdir=str(O/'tmp');sys.path.insert(0,g['actual_source_worktree']);start=time.monotonic()
def hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]);mode,flags=args[1:3]
  if P(name).name in ('auth.json','credentials.json','.env') or '2026-08-10-eds-qd-stage-guidance-transition-design.md' in name or '/dev/nvidia' in name:raise PermissionError('prohibited input')
  writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
  if writing and name!='/dev/null' and not P(name).resolve().is_relative_to(O):raise PermissionError('read-only production admission')
 if event in ('socket.connect','socket.bind'):raise PermissionError('network disabled')
 if event=='subprocess.Popen' and P(str(args[0])).name not in ('git','uname','ldconfig'):raise PermissionError('CPU subprocess only')
sys.addaudithook(hook)
r=dict(schema='n36-disabled-graph-admission-result-v1',gpu_authorized=False,source=g['actual_source_worktree'],graph=str(O/'graph.complete-disabled-v1.json'))
try:
 from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_readiness_prepare as p
 s=e.specification();r['specification']='PASS';e._recovery_contract(s);r['recovery_contract']='PASS'
 p.verify_graph({'graph':{'plan':g['plan'],'runtime':g['runtime']}},e.read(g['source_record']),e.read(s['canonical_runtime']));r['status']='PASS_DISABLED_GRAPH_ADMISSION_ALL41';r['graph_admission']='PASS'
except Exception as ex:r.update(status='BLOCKED',error=str(ex),error_type=type(ex).__name__,traceback=traceback.format_exc())
r.update(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start)
(O/'audit-result-v1.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));sys.exit(0 if r['status'].startswith('PASS') else 1)
