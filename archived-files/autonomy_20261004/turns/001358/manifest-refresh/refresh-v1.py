import os,sys,json,hashlib,copy,datetime,resource,signal
from pathlib import Path
OUT=Path(__file__).resolve().parent
BASE=OUT.parents[1]
prior=BASE/'001355/binding-refresh'
root=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.dont_write_bytecode=True;sys.path.insert(0,str(root));os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(180,180));signal.alarm(240)
from scripts import qd_ed_n36_stop as stop,qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36r3_admission as a
stop.check(need=240)
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 assert ref(r['path'])=={k:r[k] for k in ('path','sha256')};return json.loads(Path(r['path']).read_text())
def write(n,v):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 return ref(p)
old=json.loads((prior/'draft/plan.draft.json').read_text());plan=copy.deepcopy(old)
review=ref(BASE/'001357/controller-semantics.root-reviewed-v1.json');proof=read(review)
assert proof['runtime']==plan['runtime'] and proof['status']=='ROOT_REVIEWED'
plan['controller_semantics']=review
plan['artifact_root']=str(OUT/'prospective-artifacts');plan['expected_manifests']={}
runtime=read(plan['runtime']);closure=read(plan['runtime_closure'])
# Pure source semantics verifier; avoid importing controller's runtime dependencies.
import ast,math,types
src=(root/'scripts/qd_ed_n34_controller.py').read_text();tree=ast.parse(src)
subset=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_semantics' or isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='FIELDS' for x in n.targets)]
def require(x,m):
 if not x:raise ValueError(m)
ns={'w':types.SimpleNamespace(read_ref=read,require=require),'math':math};exec(compile(ast.Module(body=subset,type_ignores=[]),str(root/'scripts/qd_ed_n34_controller.py'),'exec'),ns);ns['verify_semantics'](review,plan['runtime'],closure)
for row in plan['episodes']:plan['expected_manifests'][row['episode_key']]=write('expected/'+row['episode_key']+'.json',b.manifest(plan,runtime,row))
c.validate_draft(plan);a.owner_root(plan);b.verify_sources(plan)
for row in plan['episodes']:b._verify_manifest_bound(plan['expected_manifests'][row['episode_key']],plan,runtime,row)
assert {k:v for k,v in plan.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}=={k:v for k,v in old.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}
pref=write('plan.draft.json',plan)
bref=write('bindings.disabled-v1.json',{'schema':'n36r3-refresh-bindings-draft-v1','plan':pref,**{k:plan[k] for k in a.BINDINGS},'expected_manifests':plan['expected_manifests'],'release_enabled':False,'worker_receipts_are_future':True,'target_met':False,'score':None})
write('report-v1.json',{'status':'PASS_DISABLED_MANIFEST_REFRESH','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':plan['source']['commit'],'prior_plan':ref(prior/'draft/plan.draft.json'),'controller_review':review,'plan':pref,'bindings':bref,'manifest_count':len(plan['expected_manifests']),'checks':['root controller semantics','exact source closure','owner routing','draft contract','all 40 exact manifests','only controller/artifact routing/manifests changed'],'release_enabled':False,'target_met':False,'next':'Independent exact B5 review, then root source/runtime adoption and locked accounting before fresh health release.'})
print(json.dumps({'status':'PASS_DISABLED_MANIFEST_REFRESH','plan':pref,'manifest_count':40}))
