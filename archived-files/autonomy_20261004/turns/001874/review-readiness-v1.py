import os,sys,json,pathlib,hashlib,datetime,traceback,time
P=pathlib.Path; O=P(__file__).resolve().parent; B=O.parent
sys.dont_write_bytecode=True
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
def ref(p):
 p=P(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def put(p,v):
 with P(p).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return ref(p)
prior=json.loads((B/'001870/operational-summary-v1.json').read_text())
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
g=json.loads((B/'001864/canonical-v2/graph.complete-disabled-v1.json').read_text());os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);root=P(g['production_required_worktree']);sys.path.insert(0,str(root));os.chdir(root)
from scripts import qd_ed_n36_readiness_prepare as m
e=m.e
record=dict(schema='n36-readiness-producer-consumer-review-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),episode_authorized=False,health_authorized=False)
try:
 spec=e.specification();source_ref=g['source_record'];source=e.read(source_ref);proof=ref(m.policy(spec)['proof_path']);record['proof']=proof
 runtime=m.derive(spec,source,source_ref,proof)
 data=json.dumps(runtime,sort_keys=True,separators=(',',':'),allow_nan=False).encode();rr=dict(path=spec['runtime_binding']['runtime_path'],sha256=hashlib.sha256(data).hexdigest())
 acceptance=dict(schema='n36-preparation-root-acceptance-v1',approved=True,specification=e.SPECIFICATION,proof=proof,runtime=rr,release_enabled=False,health_authorized=False,episode_authorized=False)
 ap=P(m.policy(spec)['acceptance_path'])
 if ap.exists():assert json.loads(ap.read_text())==acceptance
 else:put(ap,acceptance)
 record['root_acceptance']=ref(ap);record['runtime']=rr
 put(O/'derived-readiness-review-v1.json',dict(record,status='PASS_DERIVATION_ACCEPTANCE'))
 out=m.produce(proof);assert out==rr
 plan=e.read(g['plan']);plan['runtime']=out;e.validate_runtime_binding(plan)
 record['status']='PASS_CPU_PRODUCER_AND_RUNTIME_CONSUMER'
except Exception as ex:record.update(status='BLOCKED_PRODUCER_OR_CONSUMER',error=type(ex).__name__+': '+str(ex),traceback=traceback.format_exc())
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
record['private_ledgers_unchanged']=True
put(O/'producer-consumer-v1.json',record);print(json.dumps(record),flush=True)
