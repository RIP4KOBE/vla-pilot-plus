import sys,json,pathlib,hashlib,datetime,subprocess
root=pathlib.Path.cwd(); base=root.parent/'autonomy_20261004'; out=base/'turns/001363'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as release, qd_ed_n36r3_admission as a, qd_ed_final_runner as r

def ref(p):
 p=pathlib.Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(v):
 assert ref(v['path'])==v;return json.loads(pathlib.Path(v['path']).read_text())
def write(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
old=json.loads((base/'turns/001362/accounting-adoption-v1.json').read_text());plan=read(old['reviewed_plan']);plan['b5_review']=old['b5_review'];plan['authority']=old['authority']
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==old['source']
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  c.stop.check(need=60)
  state=r.read_state(root/'research-state.yaml');assert not state['current_owned_workers']
  for v in old['ledger_prefixes'].values():
   assert ref(v['path'])['sha256']==v['sha256'] and pathlib.Path(v['path']).stat().st_size==v['bytes']
  authority=read(old['authority']);release.validate_state(plan,authority,state);a.validate_authority(plan,authority)
  plan.update(schema='n36-released-plan-v1',frozen=True,release_enabled=True,phase_authorization={'dev':True,'validation':False,'formal':False})
  plan.pop('root_review',None);plan.pop('execution_release',None)
  release.validate_plan(plan);a.independent_review(plan)
  pref=write(out/'plan.frozen-v1.json',plan)
  expected={'schema':'n36r3-health-release-v1','approved':True,'plan':pref,**{k:plan[k] for k in ['native_build','authority','protocol','protocol_review','source','scientific_source','runtime_closure','controller_semantics','runtime','phase_authorization']},'limits':c.LIMITS,**c.operational_binding(plan),'healthchecks':a.HEALTH}
  review=write(out/'root-health-review-v1.json',{**expected,'schema':'n36r3-root-health-review-v1','decision':'APPROVED'})
  rel=write(out/'health-release-v1.json',{**expected,'root_review':review})
  write(out/'health-release-bindings-v1.json',{'plan':pref,'release':rel,'source':old['source'],'accounting_adoption':ref(base/'turns/001362/accounting-adoption-v1.json'),'gpu_dispatched':False})
print('Detached health release prepared; running full production consumer.',flush=True)
try:
 release.validate_health_release(pref,rel)
 result={'status':'PASS','plan':pref,'release':rel,'gpu_dispatched':False}
except Exception as e:
 result={'status':'FAIL_CLOSED','error':type(e).__name__,'reason':str(e),'plan':pref,'release':rel,'gpu_dispatched':False}
write(out/'health-release-consumer-v1.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['plan','release']}),flush=True)
