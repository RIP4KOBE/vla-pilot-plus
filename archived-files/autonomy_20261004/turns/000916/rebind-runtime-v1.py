import json,pathlib,hashlib,os,sys,datetime,subprocess
root=pathlib.Path.cwd(); turns=(root.parent/'autonomy_20261004/turns').resolve(); out=turns/'000916'; dest=out/'runtime-v1';dest.mkdir(exist_ok=False)
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 assert ref(r['path'])==r,r['path'];return json.load(open(r['path']))
def write(p,d):
 p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
oldplan=json.load(open(turns/'000914/runtime-v1/draft/plan.draft.json')); old=read(oldplan['runtime']); rp=turns/'000915/runtime.gpu-ready-v1.json';new=json.load(open(rp));rr=ref(rp)
changed=[k for k in set(old)|set(new) if old.get(k)!=new.get(k)];assert changed==['cuda_egl_probe'],changed
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774'
prior=json.load(open(turns/'000915/end-reconciliation-v1.json'))
for v in prior['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
cl=read(oldplan['runtime_closure']);cl['runtime']=rr;cr=write(dest/'runtime-closure-v1.json',cl)
p=read(oldplan['controller_semantics'])
for k,v in p['review_evidence'].items():
 e=read(v)
 for s in e['sources']:assert ref(s['path'])==s
 e['runtime']=rr;e['rebound_from']=v;e['binding_review']='Only CUDA/EGL readiness record changed; reviewed source bytes verified unchanged.'
 p['review_evidence'][k]=write(dest/(k+'-review-v1.json'),e)
p['runtime']=rr;p['rebound_from']=oldplan['controller_semantics'];pr=write(dest/'controller-semantics-v1.json',p)
os.environ.update(new['environment']);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root)]+new['environment']['PYTHONPATH'].split(':')
from scripts.qd_ed_n35_prepare import prepare
plan=prepare(dest/'draft',rr,runtime_closure_ref=cr,controller_semantics_ref=pr,root=root)
review={'schema':'n35-runtime-rebinding-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':source,'changed_runtime_keys':changed,'prior_preparation':ref(turns/'000914/runtime-preparation-review-v1.json'),'gpu_preparation':ref(turns/'000915/end-reconciliation-v1.json'),'runtime':rr,'closure':cr,'controller_semantics':pr,'disabled_draft':ref(dest/'draft/plan.draft.json'),'manifests':len(plan['expected_manifests']),'gpu_dispatched':False,'release_enabled':False,'ledger_prefixes':prior['ledger_prefixes'],'status':'PASS_DISABLED_DRAFT','next_step':'Reconcile final N35 prospective accounting including charged preparation probe; freeze all40 root review/plan/detached release and pass public validate_release before Dev dispatch.'}
write(out/'runtime-rebinding-review-v1.json',review);print(json.dumps(review))
