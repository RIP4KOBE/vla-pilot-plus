import os,sys,json,hashlib,copy,time,datetime,subprocess,traceback
from pathlib import Path
O=Path(__file__).resolve().parent; B=O.parent/'001779/canonical-path-rebinding'; R=O.parent/'001783'; ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
sys.dont_write_bytecode=True
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(O/'tmp'))
(O/'tmp').mkdir(exist_ok=True)
def ref(p):
 p=Path(p);return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(v):
 if isinstance(v,dict): assert ref(v['path'])['sha256']==v['sha256'];v=v['path']
 return json.loads(Path(v).read_text())
def save(n,v):
 p=O/n;assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n');return ref(p)
prior=read(R/'operational-summary-v1.json'); authority=read(B/'authority-v1.json')
assert datetime.datetime.now(datetime.timezone.utc).isoformat()<authority['stop_authority']['deadline'];assert all(not os.path.lexists(p) for p in authority['stop_authority']['paths'])
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==prior['current_source']['commit']
assert not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip()
graph=read(B/'graph.complete-disabled-v1.json');oldcontroller=graph['controller_semantics'];newcontroller=ref(R/'controller-semantics.root-reviewed-disabled-v1.json');attestation=ref(R/'root-controller-binding-attestation-v1.json');newcontroller=read(attestation)['controller'];read(newcontroller)
changes=[]
def replace(v, pairs):
 for old,new in pairs:
  if v==old:return copy.deepcopy(new)
 if isinstance(v,dict):return {k:replace(x,pairs) for k,x in v.items()}
 if isinstance(v,list):return [replace(x,pairs) for x in v]
 return v
pairs=[(oldcontroller,newcontroller)]
audit=read(graph['audit']);oldaudit=copy.deepcopy(audit)
for i,(key,r) in enumerate(audit['expected_manifests'].items()):
 m=read(r);new=replace(m,pairs)
 if new!=m:
  nr=save('audit-manifests/%02d.json'%i,new);pairs.append((r,nr));changes.append(dict(old=r,new=nr));audit['expected_manifests'][key]=nr
audit=replace(audit,pairs);ar=save('all40-audit.disabled-v1.json',audit);pairs.append((graph['audit'],ar))
oldplan=read(graph['plan']);er=save('engineering-manifest.disabled-v1.json',replace(read(oldplan['engineering_manifest']),pairs));pairs.append((oldplan['engineering_manifest'],er))
plan=replace(oldplan,pairs);pr=save('engineering-plan.disabled-v1.json',plan);pairs.append((graph['plan'],pr))
index=replace(read(graph['full40_manifests']),pairs);ir=save('full40-manifest-index-v1.json',index);pairs.append((graph['full40_manifests'],ir))
rel=read(graph['relocation_map'])
for x in rel['relocations'].values():x['new']=replace(x['new'],pairs)
for x in rel['full40']:x['new']=replace(x['new'],pairs)
rel['reused_exact']['controller']=newcontroller
relref=save('disabled-relocation-map-v1.json',rel);pairs.append((graph['relocation_map'],relref))
graph=replace(graph,pairs);graph.update(root_controller_acceptance=attestation,status='DISABLED_CANDIDATE_PENDING_PRODUCTION_GRAPH_ADMISSION',graph_verified=False)
gr=save('graph.complete-disabled-v1.json',graph)
vr=save('disabled-graph-validator-input-v1.json',dict(graph=dict(plan=pr,runtime=graph['runtime']),approved=False,release_enabled=False))
save('composition-record-v1.json',dict(schema='n36-controller-binding-refresh-v1',source=prior['current_source'],prior_graph=ref(B/'graph.complete-disabled-v1.json'),root_controller_acceptance=attestation,graph=gr,replacements=[dict(old=x,new=y) for x,y in pairs],scientific_changes=False,release_enabled=False,b5_review=None))
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(graph['specification']);sys.path.insert(0,str(ROOT));os.chdir(ROOT)
# Restrict this static validator to local artifact writes and audit subprocesses.
def hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]);low=name.lower();base=Path(low).name
  if ('poe' in base and base!='qd_ed_poe_launch.py') or '2026-08-10' in low or base in ('auth.json','credentials.json','.env') or '/.ssh/' in low or '/dev/nvidia' in low:raise PermissionError('prohibited input '+name)
  mode,flags=args[1:3];writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
  if writing and name!='/dev/null' and not str(Path(name).resolve()).startswith(str(O)+'/'):raise PermissionError('out of scope write '+name)
 if event in ('socket.connect','socket.bind'):raise PermissionError('network prohibited')
 if event=='import' and 'poe' in args[0].lower():raise PermissionError('Poe import prohibited')
 if event=='subprocess.Popen' and Path(str(args[0])).name not in ('git','uname','ldconfig'):raise PermissionError('non-audit subprocess')
sys.addaudithook(hook)
t=time.monotonic();result=dict(schema='n36-focused-graph-admission-v1',graph=gr,validator_input=vr,source=prior['current_source'],gpu_authorized=False,release_enabled=False,independent_review_claimed=False,b5_review=None)
try:
 from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_readiness_prepare as prep
 spec=read(graph['specification']);actual=prep.verify_graph(read(vr),read(graph['source_record']),read(spec['canonical_runtime']))
 assert actual==plan
 result.update(status='PASS_STATIC_GRAPH_ADMISSION',graph_verified=True)
except Exception as ex:result.update(status='BLOCKED_STATIC_GRAPH_ADMISSION',graph_verified=False,error=str(ex),traceback=traceback.format_exc())
result['elapsed_seconds']=time.monotonic()-t
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
result['private_ledgers_unchanged']=True
rr=save('graph-admission-result-v1.json',result);print(json.dumps(dict(result=rr,status=result['status'],error=result.get('error'))),flush=True)
