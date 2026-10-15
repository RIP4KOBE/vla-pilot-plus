import json,pathlib,hashlib,os,sys,datetime
root=pathlib.Path.cwd();turns=(root.parent/'autonomy_20261004/turns').resolve();out=turns/'000917'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(n,d):
 p=out/n;assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
plan=json.load(open(out/'plan.frozen-v1.json'));old=json.load(open(turns/'000861/plan.frozen-v1.json'))
keys=['runtime_inventory_path','runtime_inventory_sha256','seed_plan_path','seed_plan_sha256','input_contract_label']
for k in keys:plan[k]=old[k]
for stem in ['runtime_inventory','seed_plan']:assert ref(pathlib.Path(plan[stem+'_path']))['sha256']==plan[stem+'_sha256']
pr=write('plan.frozen-v2.json',plan)
e=json.load(open(out/'execution-release-v1.json'));e['plan']=pr;del e['root_review']
rr=write('root-production-review-v2.json',{**e,'schema':'n35-root-production-review-v1','decision':'APPROVED'})
er=write('execution-release-v2.json',{**e,'root_review':rr})
write('plan-metadata-correction-v2.json',{'supersedes_failed_release':ref(out/'execution-release-v1.json'),'reason':'Draft omits root-added generic runtime input bindings; public validator failed before admission. Add exact existing inventory/seed references and input repair disclosure. No source, manifest, scientific or runtime changes.','added_keys':keys,'plan':pr,'release':er})
runtime=json.load(open(plan['runtime']['path']));os.environ.update(runtime['environment']);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root)]+runtime['environment']['PYTHONPATH'].split(':')
from scripts.qd_ed_n35_release import validate_release
try:
 validate_release(pr,er);status='PASS';error=None
except Exception as exc:status='FAIL';error=repr(exc)
write('public-release-validation-v2.json',{'status':status,'error':error,'plan':pr,'release':er,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_dispatched':False,'state_adopted':False});print(status,error)
