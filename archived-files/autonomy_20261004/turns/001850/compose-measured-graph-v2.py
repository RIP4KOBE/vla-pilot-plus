import os,sys,json,hashlib,copy,subprocess,datetime,time,traceback
from pathlib import Path
T=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent/'measured-graph-v2';O.mkdir(exist_ok=False)
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
def ref(p):
 p=Path(p);return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(r):
 if isinstance(r,dict):assert ref(r['path'])['sha256']==r['sha256'];r=r['path']
 return json.loads(Path(r).read_text())
def save(n,d):
 p=O/n;p.parent.mkdir(exist_ok=True,parents=True)
 with p.open('x') as f:json.dump(d,f,sort_keys=True,indent=2);f.write('\n')
 return ref(p)
prev=read(T/'001849/operational-summary-v1.json');g=read(T/'001841/composition-v6/graph.complete-disabled-v1.json');root=Path(g['production_required_worktree'])
assert not (T.parent/'STOP').exists();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
for r in prev['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==prev['current_source']['commit']
assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True).strip()
rt=read(T/'001849/producer-consumer-v1.json')['runtime'];runtime=read(rt)
pairs=[(g['runtime'],rt)]
def replace(x):
 for a,b in pairs:
  if x==a:return copy.deepcopy(b)
 if isinstance(x,dict):return {k:replace(v) for k,v in x.items()}
 if isinstance(x,list):return [replace(v) for v in x]
 return x
closure=replace(read(g['runtime_closure']));cr=save('runtime-closure.measured-v1.json',closure);pairs.append((g['runtime_closure'],cr))
ctrl=read(g['controller_semantics']);oldctrl=copy.deepcopy(ctrl);ctrl['runtime']=rt;ctrl['runtime_closure']=cr
for key,r in list(ctrl['review_evidence'].items()):
 ev=read(r);assert ev['source_commit']==prev['current_source']['commit']
 for sr in ev['sources']:assert ref(sr['path'])==sr
 ev['runtime']=rt;ev['runtime_closure']=cr;ev['historical_review']=r;ev['reviewer']='owning_root_coordinator_turn001850';ev['at']=datetime.datetime.now(datetime.timezone.utc).isoformat();ev['review_scope']='Operational reference attestation only: same deployed source and controller semantic content; measured readiness replaces disabled runtime. No new native or independent evidence claimed.'
 ctrl['review_evidence'][key]=save(key+'.measured-binding-v1.json',ev)
acc=read(ctrl['root_acceptance']);acc.update(runtime=rt,runtime_closure=cr,evidence=ctrl['review_evidence'],reviewer='owning_root_coordinator_turn001850',prior=g['controller_semantics']);ctrl['root_acceptance']=save('controller-root-binding-acceptance-v1.json',acc)
ct=save('controller-semantics.measured-v1.json',ctrl);pairs.append((g['controller_semantics'],ct))
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);sys.path.insert(0,str(root));os.chdir(root)
from scripts import qd_ed_n36_engineering_r1 as e
oldplan=read(g['plan']);oldaudit=read(g['audit']);audit=replace(oldaudit)
for i,row in enumerate(audit['episodes']):
 key=row['episode_key'];old=read(oldaudit['expected_manifests'][key]);m=replace(old)
 for k in ['row','argv','resolved_config','composed_config_sha256','source','scientific_source']:assert m[k]==old[k],(key,k)
 mr=save('audit-manifests/%02d.json'%i,m);pairs.append((oldaudit['expected_manifests'][key],mr));audit['expected_manifests'][key]=mr
ar=save('all40-audit.measured-disabled-v1.json',audit);pairs.append((g['audit'],ar))
plan=replace(oldplan);oldem=read(g['separate_engineering_manifest']);em=replace(oldem)
for k in ['row','audit_row','argv','resolved_config','composed_config_sha256','source','scientific_source']:assert em[k]==oldem[k],k
er=save('engineering-manifest.measured-disabled-v1.json',em);pairs.append((g['separate_engineering_manifest'],er));plan=replace(oldplan)
pr=save('engineering-plan.measured-disabled-v1.json',plan)
ng=copy.deepcopy(g);ng.update(plan=pr,audit=ar,runtime=rt,runtime_closure=cr,controller_semantics=ct,separate_engineering_manifest=er,root_controller_acceptance=ctrl['root_acceptance'],full40_manifests=save('manifest-index-v1.json',audit['expected_manifests']),status='MEASURED_GRAPH_PENDING_FULL_AUDIT_AND_B5',runtime_ready=True,provider_ready=True,graph_verified=False,source_adopted=False,authority=None,b5_review=None,root_acceptance=None,release_enabled=False,gpu_authorized=False,prior_graph=ref(T/'001841/composition-v6/graph.complete-disabled-v1.json'))
gr=save('graph.measured-disabled-v1.json',ng)
result=dict(schema='n36-measured-graph-admission-v1',graph=gr,source=prev['current_source'],health_authorized=False,episode_authorized=False,independent_review_claimed=False,all41_scientific_payloads_unchanged=True)
t=time.monotonic()
proof=read(read(T/'001849/producer-consumer-v1.json')['proof'])
proof_release=read(proof['release']);proof_plan=read(proof_release['graph']['plan'])
try:
 e.b.closure.verify_runtime_receipt(read(proof_plan['runtime_closure']),read(proof['runtime_receipt']),binding=proof['runtime_receipt_binding'],after=True)
 result.update(status='PASS_MEASURED_GRAPH_REBINDING_AND_RETAINED_RECEIPT',full_audit_closure_passed=False,manifest_count=len(audit['episodes']),pycache_prefix=sys.pycache_prefix)
except Exception as ex:result.update(status='BLOCKED_RETAINED_RECEIPT',error=str(ex),traceback=traceback.format_exc())
result['elapsed_seconds']=time.monotonic()-t
for r in prev['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
result['private_ledgers_unchanged']=True;save('audit-result-v1.json',result);print(json.dumps(result))
