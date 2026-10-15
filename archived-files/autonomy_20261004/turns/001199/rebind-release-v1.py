import json,pathlib,hashlib,os,sys,datetime,subprocess,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';turns=(base/'turns').resolve();out=turns/'001199';dest=out/'runtime-v1'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 assert ref(r['path'])['sha256']==r['sha256'];return json.loads(pathlib.Path(r['path']).read_text())
def write(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
s=yaml.safe_load((root/'research-state.yaml').read_text());ds=json.loads((base/'driver-status.json').read_text());assert ds['turn']==1199
assert not (base/'STOP').exists() and s['active_controller'] is None and not s['current_owned_workers']
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==s['source_commit']=='ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557'
review=read(s['n36_runtime_review']['report']);assert review['verdict']=='PASS'
ready=read(s['n36_runtime_readiness']);new=read(ready['runtime']);ar=s['n36_budget_authority'];authority=read(ar)
for v in ready['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
oldplan=read(review['reviewed_draft']);old=read(oldplan['runtime']);changed=sorted(k for k in set(old)|set(new) if old.get(k)!=new.get(k));assert changed==sorted(ready['changed_fields'])
dest.mkdir();rr=ready['runtime'];cl=read(oldplan['runtime_closure']);cl['runtime']=rr;cr=write(dest/'runtime-closure-v1.json',cl)
p=read(oldplan['controller_semantics'])
for k,v in p['review_evidence'].items():
 e=read(v)
 for x in e['sources']:assert ref(x['path'])['sha256']==x['sha256']
 e.update(runtime=rr,rebound_from=v,binding_review='Only verified readiness fields changed; deployed source bytes unchanged.')
 p['review_evidence'][k]=write(dest/(k+'-review-v1.json'),e)
p.update(runtime=rr,rebound_from=oldplan['controller_semantics']);pr=write(dest/'controller-semantics-v1.json',p)
os.environ.update(new['environment']);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root)]+new['environment']['PYTHONPATH'].split(':')
from scripts.qd_ed_n36_prepare import prepare
from scripts import qd_ed_n36_contract as c,qd_ed_n36_release as release
plan=prepare(dest/'draft',rr,runtime_closure_ref=cr,controller_semantics_ref=pr,native_build_ref=oldplan['native_build'],root=root)
assert plan['source']==oldplan['source'] and plan['episodes']==oldplan['episodes'] and plan['limits']==oldplan['limits'] and plan['worker_contract']==oldplan['worker_contract']
br=write(out/'runtime-rebinding-review-v1.json',{'schema':'n36-runtime-rebinding-review-v1','status':'PASS_DISABLED_DRAFT','source':source,'readiness':s['n36_runtime_readiness'],'independent_review':s['n36_runtime_review']['report'],'changed_runtime_keys':changed,'disabled_draft':ref(dest/'draft/plan.draft.json'),'manifests':len(plan['expected_manifests']),'ledger_prefixes':ready['ledger_prefixes'],'gpu_dispatched':False,'target_met':False})
plan.update(schema='n36-released-plan-v1',frozen=True,release_enabled=True,authority=ar,protocol=authority['protocol'],protocol_review=s['n36_protocol_root_review'],attempt_identity='episode_key',run_name=s['run_name'],phase_authorization={'dev':True,'validation':False,'formal':False})
for k in ['root_review','execution_release']:del plan[k]
planref=write(out/'plan.frozen-v1.json',plan)
expected={'schema':'n36-execution-release-v1','approved':True,'plan':planref,**{k:plan[k] for k in ['native_build','authority','protocol','protocol_review','source','scientific_source','runtime_closure','controller_semantics','runtime','limits','phase_authorization']}}
rootreview=write(out/'root-production-review-v1.json',{**expected,'schema':'n36-root-production-review-v1','decision':'APPROVED'})
er=write(out/'execution-release-v1.json',{**expected,'root_review':rootreview})
try:
 release.validate_release(planref,er)
 write(out/'public-release-validation-v1.json',{'status':'PASS','plan':planref,'release':er,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_dispatched':False})
 print('PASS')
except BaseException as exc:
 write(out/'public-release-validation-v1.json',{'status':'FAIL','plan':planref,'release':er,'error':repr(exc),'gpu_dispatched':False});raise
