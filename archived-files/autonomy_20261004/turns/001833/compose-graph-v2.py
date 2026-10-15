import os,sys,json,hashlib,copy,subprocess,time,traceback,datetime
from pathlib import Path
T=Path(__file__).resolve().parent.parent; O=Path(__file__).resolve().parent/'composition-v2'; O.mkdir(exist_ok=True); ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
sys.dont_write_bytecode=True
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(O/'tmp'))
(O/'tmp').mkdir(exist_ok=True)
def ref(p):
 p=Path(p);return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(v):
 if isinstance(v,dict):assert ref(v['path'])['sha256']==v['sha256'];v=v['path']
 return json.loads(Path(v).read_text())
def save(n,v):
 p=O/n;assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True,separators=(',',':')));return ref(p)
prior=read(T/'001832/operational-summary-v1.json')
assert datetime.datetime.now(datetime.timezone.utc).isoformat()<'2026-10-11T11:13:13+00:00'
assert not (T.parent/'STOP').exists()
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==prior['current_source']['commit']
assert not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip()
g=read(T/'001784/graph.complete-disabled-v1.json'); n=read(T/'001827/disabled-v3-binding/graph.candidate-disabled-v3.json')
n['specification']=ref(T/'001831/specification.root-reconciled-disabled-v3.json');n['recovery_prefix_contract']=ref(T/'001831/recovery-prefix-contract.root-reviewed-disabled-v3.json');n['controller_semantics']=ref(T/'001832/controller-semantics.root-reviewed-disabled-v1.json')
pairs=[(g[k],n[k]) for k in ('runtime','runtime_closure','source_record','specification','policy','recovery_prefix_contract','controller_semantics')]
oldsource=read(g['source_record']);source=read(n['source_record']);pairs.append((oldsource,source))
def replace(v):
 for a,b in pairs:
  if v==a:return copy.deepcopy(b)
 if isinstance(v,dict):return {k:replace(x) for k,x in v.items()}
 if isinstance(v,list):return [replace(x) for x in v]
 return v
# Rebind structured source records only; preserve historical anchors and recorded reviews.
oldplan=read(g['plan'])
eq=replace(read(g['scientific_equivalence']))
eq['changed_paths']=subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only',eq['base_commit'],source['commit']],text=True).splitlines()
assert all(x.startswith(('scripts/qd_ed_n36_','tests/')) or x=='configs/qd_ed_final/n36_engineering_r1_spec.disabled.json' for x in eq['changed_paths'])
eqr=save('scientific-equivalence.disabled-v1.json',eq);pairs.append((g['scientific_equivalence'],eqr))

os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(n['specification']);sys.path.insert(0,str(ROOT));os.chdir(ROOT)
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
from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_readiness_prepare as prep
for k,doc in [('scope',e.disabled_scope()),('accounting',e.disabled_accounting())]:
 nr=save(k+'.disabled-v1.json',doc);pairs.append((oldplan[k],nr))
nr=save('deployment.disabled-v1.json',e.deployment(replace(oldplan)));pairs.append((oldplan['deployment'],nr))
runtime=read(n['runtime']);audit=replace(read(g['audit']));index=[]
for i,row in enumerate(audit['episodes']):
 key=row['episode_key'];old=audit['expected_manifests'][key]
 nr=save('audit-manifests/%02d.json'%i,e.b.manifest(audit,runtime,row));audit['expected_manifests'][key]=nr
 index.append(dict(row=row,original=old,new=nr,composition='production_manifest_recomposition'))
ar=save('all40-audit.disabled-v1.json',audit);pairs.append((g['audit'],ar))
plan=replace(oldplan)
er=save('engineering-manifest.disabled-v1.json',e.b.engineering_manifest(plan,runtime,e.row(),audit=audit));pairs.append((oldplan['engineering_manifest'],er));plan=replace(oldplan)
pr=save('engineering-plan.disabled-v1.json',plan)
graph=copy.deepcopy(n);graph.update(schema='n36-readiness-recovery-prospective-graph-v1',plan=pr,audit=ar,full40_manifests=save('full40-manifest-index-v1.json',dict(manifests=index)),separate_engineering_manifest=er,scientific_equivalence=eqr,controller_semantics=n['controller_semantics'],source_placement=ref(T/'001832/source-placement-result-v1.json'),root_controller_acceptance=ref(T/'001832/controller-verification-v1.json'),graph_complete=True,graph_verified=False,status='DISABLED_CANDIDATE_PENDING_PRODUCTION_GRAPH_ADMISSION')
gr=save('graph.complete-disabled-v1.json',graph);vr=save('disabled-graph-validator-input-v1.json',dict(graph=dict(plan=pr,runtime=n['runtime']),approved=False,release_enabled=False))
result=dict(schema='n36-focused-graph-admission-v1',graph=gr,validator_input=vr,source=prior['current_source'],gpu_authorized=False,release_enabled=False,independent_review_claimed=False)
t=time.monotonic()
try:
 actual=prep.verify_graph(read(vr),source,read(read(n['specification'])['canonical_runtime']));assert actual==plan
 result.update(status='PASS_STATIC_GRAPH_ADMISSION',graph_verified=True)
except Exception as ex:result.update(status='BLOCKED_STATIC_GRAPH_ADMISSION',graph_verified=False,error=str(ex),traceback=traceback.format_exc())
result['elapsed_seconds']=time.monotonic()-t
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
result['private_ledgers_unchanged']=True
rr=save('graph-admission-result-v1.json',result)
save('composition-record-v1.json',dict(source=prior['current_source'],prior_graph=ref(T/'001784/graph.complete-disabled-v1.json'),inputs={k:n[k] for k in ('specification','source_record','runtime','runtime_closure','controller_semantics','recovery_prefix_contract')},graph=gr,result=rr,scientific_changes=False,release_enabled=False,delegation_failure='spawn_agent failed before creating child: no thread with id; composed operational artifacts locally, no benchmark edits'))
print(json.dumps(result))
