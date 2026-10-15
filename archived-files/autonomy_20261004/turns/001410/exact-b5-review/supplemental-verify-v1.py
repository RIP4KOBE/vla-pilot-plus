import os,sys,json,hashlib,datetime,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;BASE=OUT.parents[1]
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
from scripts import qd_ed_n36_stop as stop,qd_ed_n36r3_admission as a
stop.check();inputs={}
def ref(p):
 p=Path(p);r={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()};inputs[str(p)]=r;return r
def read(r):
 assert ref(r['path'])['sha256']==r['sha256'];return json.loads(Path(r['path']).read_text())
def br(p):return read(ref(p))
auth=br(OUT/'authority-v1.json');p=read(auth['plan']);old=br(BASE/'001358/manifest-refresh/plan.draft.json');rt=read(p['runtime']);ort=read(old['runtime']);cl=read(p['runtime_closure']);ocl=read(old['runtime_closure'])
checks=[]
assert {k:v for k,v in rt.items() if k not in ('files','preparation')}=={k:v for k,v in ort.items() if k not in ('files','preparation')}
x=rt['preparation'];y=ort['preparation']
assert {k:v for k,v in x.items() if k not in ('source','source_record','historical_runtime')}=={k:v for k,v in y.items() if k not in ('source','source_record','historical_runtime')}
assert x['source']==auth['source']==p['source']['commit'] and read(x['source_record'])==p['source']
assert x['historical_runtime']==old['runtime'] and x['runtime_ready'] is False and x['release_enabled'] is False and x['historical_readiness_is_not_current'] is True
oldfiles={r['path']:r['sha256'] for r in ort['files']};newfiles={r['path']:r['sha256'] for r in rt['files']}
assert oldfiles.keys()==newfiles.keys()
delta=[k for k in newfiles if newfiles[k]!=oldfiles[k]]
assert set(delta)=={str(ROOT/'scripts/qd_ed_n36_healthcheck.py'),str(ROOT/'scripts/qd_ed_n36_runner.py')}
assert cl['modules'].keys()==ocl['modules'].keys()
md=[k for k in cl['modules'] if cl['modules'][k]!=ocl['modules'][k]]
assert set(md)=={'scripts.qd_ed_n36_healthcheck','scripts.qd_ed_n36_runner'}
req=br(BASE/'001408/binding-refresh/required-after.production-v1.json')
assert req=={'required_after':cl['required_after'],'runtime_closure':p['runtime_closure'],'observed_loaded_after':False,'process_bound_lifecycle_evidence':False}
checks.append({'check':'exact_preparation_metadata_and_two_caller_delta','status':'PASS','runtime_changed_files':delta,'closure_changed_modules':md,'preparation_source_record':x['source_record'],'historical_readiness_is_not_current':True,'required_after':req})
controller=read(p['controller_semantics']);oc=read(old['controller_semantics'])
for k in ('schema','module','class','instance','semantics','source','physical_gain_certified'):assert controller[k]==oc[k]
assert controller['runtime']==p['runtime'] and controller['runtime_closure']==p['runtime_closure'] and controller['source_commit']==auth['source']
for k,r in controller['review_evidence'].items():
 e=read(r);oe=read(oc['review_evidence'][k]);assert e['runtime']==p['runtime'] and e['runtime_closure']==p['runtime_closure']
 # root has approved static inherited findings; per-evidence preparation status is not an execution release.
 for key in oe:
  if key not in ('runtime','runtime_closure','source_commit','at','rebound_from','status','release_enabled','binding_review'):assert e[key]==oe[key],key
checks.append({'check':'001410_controller_inherited_semantics_and_findings','status':'PASS','actual_instance_attested':False})
changes=subprocess.check_output(['git','diff','--name-only','21fc93e5667a83520401282d4ba8e945f954f99b','HEAD'],cwd=ROOT,text=True).splitlines()
assert changes==['scripts/qd_ed_n36_healthcheck.py','scripts/qd_ed_n36_runner.py','tests/test_n36_parent_binding.py','tests/test_n36_runner.py']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
checks.append({'check':'no_scientific_gate_or_identity_source_delta','status':'PASS','changed_paths':changes})
initial=br(OUT/'checks-v1.json');fail=[x for x in initial['checks'] if x['status']=='FAIL']
assert len(fail)==1 and fail[0]['check']=='refresh_scope_and_scientific_continuity' and fail[0]['error']=='ValueError: runtime field changed preparation'
b5={'schema':'n36r3-independent-b5-review-v1','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',**{k:p[k] for k in a.BINDINGS},'worker_receipts_are_future':True,'release_enabled':False}
with (OUT/'b5-review-v1.json').open('x') as f:json.dump(b5,f,indent=2);f.write('\n')
b5ref=ref(OUT/'b5-review-v1.json');view={**p,'b5_review':b5ref};a.independent_review(view)
assert view['release_enabled'] is False and view['authority'] is None
checks.append({'check':'exact_admission_independent_review_consumer','status':'PASS','review':b5ref,'mode':'in-memory reference to actual independent review; disabled plan retained; no synthetic root governance'})
stop.check()
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'inputs':inputs,'retained_initial_failure':fail,'resolution':'Initial comparison incorrectly disallowed intended preparation metadata rebinding. Exact fields verified here; no production source or prepared artifact changed. No repeated manifests/runtime/native validation.','b5_review':b5ref,'release_enabled':False,'score':None,'target_met':False}
with (OUT/'supplemental-checks-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks':checks,'resolution':result['resolution']},indent=2))
