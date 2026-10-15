import os,sys,json,hashlib,copy,subprocess,time,traceback,datetime
from pathlib import Path
T=Path(__file__).resolve().parent.parent; O=Path(__file__).resolve().parent/'composition-v5'; O.mkdir(exist_ok=False); ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
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
prior=read(T/'001839/operational-summary-v1.json')
assert datetime.datetime.now(datetime.timezone.utc).isoformat()<'2026-10-11T11:13:13+00:00'
assert not (T.parent/'STOP').exists()
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==prior['current_source']['commit']
assert not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip()
g=read(T/'001784/graph.complete-disabled-v1.json'); n=read(T/'001827/disabled-v3-binding/graph.candidate-disabled-v3.json')
n['specification']=ref(T/'001831/specification.root-reconciled-disabled-v3.json');n['recovery_prefix_contract']=ref(T/'001831/recovery-prefix-contract.root-reviewed-disabled-v3.json');n['controller_semantics']=ref(T/'001832/controller-semantics.root-reviewed-disabled-v1.json')
# Prospectively apply the recorded one-row canonical amendment; historical artifacts remain intact.
old_n=copy.deepcopy(n)
sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n34_source as src
old_source=read(n['source_record'])
source=src.source_record(ROOT,[x['path'] for x in old_source['files']],commit=prior['current_source']['commit'])
n['source_record']=save('source-record.json',source)
amendment=read(n['amendment']);amendment['source']=n['source_record'];n['amendment']=save('source-scope-amendment.disabled-v1.json',amendment)

spec=read(n['specification']);spec['canonical_runtime']=ref(T/'001834/runtime.canonical.prospective-disabled-v2.json')
spec['runtime_binding']['amendment']=n['amendment']
spec['runtime_binding']['source_record_path']=n['source_record']['path']
spec['canonical_inventory_amendment']=ref(T/'001834/prospective-runtime-inventory-amendment-v1.json')
policy=read(n['policy']);previous_ref=policy['previous_specification'];previous=read(previous_ref)
previous['canonical_runtime']=spec['canonical_runtime']
previous['prospective_inventory_derivation']={'historical_original':previous_ref,'amendment':spec['canonical_inventory_amendment'],'scope':'New disabled prospective snapshot; historical original is unchanged and not represented as amended.'}
policy['previous_specification']=save('previous-specification.prospective-inventory-v1.json',previous)
policy['baseline']=spec['canonical_runtime'];policy['disabled_runtime_path']=str(O/'runtime.prospective-disabled-v4.json')
n['policy']=save('preparation-policy.prospective-disabled-v4.json',policy)
spec['runtime_binding']['preparation']=n['policy']
n['specification']=save('specification.prospective-disabled-v4.json',spec)
runtime=read(n['runtime']);canonical=read(spec['canonical_runtime'])
changed=[i for i,(a,b) in enumerate(zip(runtime['files'],canonical['files'])) if a!=b]
assert len(runtime['files'])==len(canonical['files']) and len(changed)==1
assert runtime['files'][changed[0]]['path'].endswith('/scripts/qd_ed_n36_source.py')
runtime['files']=canonical['files']
runtime['preparation'].update(source=source['commit'],source_record=n['source_record'])
n['runtime']=save('runtime.prospective-disabled-v4.json',runtime)
closure=read(n['runtime_closure']);closure['runtime']=n['runtime']
idx={r['path']:r['sha256'] for r in source['files']}
for row in closure['modules'].values():
 p=Path(row['path'])
 for root in (ROOT,ROOT.parent.parent/'n36_engineering_r1_001617/implementation_worktree'):
  if p.is_relative_to(root):
   rel=str(p.relative_to(root));row.update(path=str(ROOT/rel),sha256=idx[rel]);break
n['runtime_closure']=save('runtime-closure.prospective-disabled-v4.json',closure)
controller=read(n['controller_semantics']);controller['runtime']=n['runtime'];controller['runtime_closure']=n['runtime_closure']
controller['source_commit']=source['commit']
controller['historical_review_only']=old_n['controller_semantics']
controller['binding_amendment']=spec['canonical_inventory_amendment']
for key,evref in list(controller['review_evidence'].items()):
 ev=read(evref);ev['runtime']=n['runtime'];ev['source_commit']=source['commit'];ev['historical_review']=evref
 controller['review_evidence'][key]=save(key+'-runtime-rebound-v1.json',ev)
# Controller implementation and semantics unchanged; source binding reflects reviewed engineering repair.
# This is a root operational binding review, not new independent or native evidence.
save('controller-binding-review-v1.json',dict(prior=old_n['controller_semantics'],amendment=spec['canonical_inventory_amendment'],runtime=n['runtime'],runtime_closure=n['runtime_closure'],scope='Only runtime inventory/source fingerprint and reference bindings changed; semantics and source evidence preserved.',gpu_authorized=False,independent_review_claimed=False))
n['controller_semantics']=save('controller-semantics.prospective-disabled-v4.json',controller)
pairs=[(g[k],n[k]) for k in ('runtime','runtime_closure','source_record','specification','policy','recovery_prefix_contract','controller_semantics')]
pairs += [(old_n[k],n[k]) for k in ('runtime','runtime_closure','specification','controller_semantics','policy','source_record','amendment')]
oldsource=read(g['source_record']);source=read(n['source_record']);pairs.extend([(oldsource,source),(old_source,source)])
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
graph=copy.deepcopy(n);graph.update(schema='n36-readiness-recovery-prospective-graph-v1',plan=pr,audit=ar,full40_manifests=save('full40-manifest-index-v1.json',dict(manifests=index)),separate_engineering_manifest=er,scientific_equivalence=eqr,controller_semantics=n['controller_semantics'],source_placement=ref(T/'001839/source-placement-result-v1.json'),root_controller_acceptance=ref(T/'001832/controller-verification-v1.json'),graph_complete=True,graph_verified=False,status='DISABLED_CANDIDATE_PENDING_PRODUCTION_GRAPH_ADMISSION')
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
save('composition-record-v1.json',dict(source=prior['current_source'],prior_graph=ref(T/'001784/graph.complete-disabled-v1.json'),inputs={k:n[k] for k in ('specification','source_record','runtime','runtime_closure','controller_semantics','recovery_prefix_contract')},graph=gr,result=rr,scientific_changes=False,release_enabled=False,operational_composition='Applied recorded canonical inventory amendment to new disabled artifacts; no benchmark edits'))
print(json.dumps(result))
