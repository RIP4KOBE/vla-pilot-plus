import os,sys,json,hashlib,time,traceback,datetime
from pathlib import Path
O=Path(__file__).resolve().parent
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
def read(r):
 if isinstance(r,dict):
  p=Path(r['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'];return json.loads(p.read_text())
 return json.loads(Path(r).read_text())
prev=read(O.parent/'001890/operational-summary-v1.json');prev['measured_graph_review']=read(O/'measured-graph-v2/audit-result-v1.json');g=read(prev['measured_graph_review']['graph'])
for r in prev['ledger_prefixes'].values():read_bytes=Path(r['path']).read_bytes();assert hashlib.sha256(read_bytes).hexdigest()==r['sha256']
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);root=Path(g['production_required_worktree']);os.chdir(root);sys.path.insert(0,str(root))
from scripts import qd_ed_n36_engineering_r1 as e
result=dict(schema='n36-measured-full-audit-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),graph=prev['measured_graph_review']['graph'],gpu_authorized=False)
t=time.monotonic()
try:
 audit=read(g['audit']);plan=read(g['plan'])
 with e.b.closure.verification_phase('engineering_release'):
  evidence=e.full.verify_audit_closure(audit)
  result['full_audit_closure_passed']=True
  manifest=e.b.verify_engineering_manifest(plan['engineering_manifest'],plan,evidence.runtime,e.row(),audit=audit)
  result.update(status='PASS_FULL_AUDIT_AND_SEPARATE_ENGINEERING_MANIFEST',manifest_count=len(evidence.manifests),engineering_manifest_passed=True)
except Exception as ex:result.update(status='BLOCKED_PRODUCTION_AUDIT',error=str(ex),traceback=traceback.format_exc())
result['elapsed_seconds']=time.monotonic()-t
result['private_ledgers_unchanged']=all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in prev['ledger_prefixes'].values())
(O/'audit-result-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
