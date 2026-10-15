import sys,json,pathlib,hashlib,datetime,subprocess
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001416'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_n36_release as release, qd_ed_n36_contract as c, qd_ed_final_runner as r

def ref(p):
 p=pathlib.Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
prior=json.loads((base/'turns/001415/operational-summary-v1.json').read_text())
for v in prior['ledger_prefixes'].values():
 assert ref(v['path'])['sha256']==v['sha256'] and pathlib.Path(v['path']).stat().st_size==v['bytes']
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==prior['candidate_source']
for name,sha in [('handoff-v2.json','3d8267a367e40ba6a3b9fd307fc8371a335e21bbc92df6700d7ecc10fd9669de'),('user-authorization-v1.json','a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c'),('research-continuation-v1.md','5cefad40c22cd57ac522344793c8ce734a51e9c09983d92f6ddd57dfd906710d'),('completion-contract-v1.json','4e825a595c3422824f5160b42690528a03a1ac4d8d2cf4025576a3bb59b2514c')]:assert ref(base/name)['sha256']==sha
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  c.stop.check(need=1840)
  state=r.read_state(root/'research-state.yaml');assert not state['current_owned_workers']
  assert state['resource_isolation']['status']=='ACTIVE'
  health=json.loads((base/'turns/001414/health-release-v1.json').read_text())
  terminal=json.loads((base/'turns/001415/terminal-reconciliation-v1.json').read_text())['terminal']
  terminal={k:terminal[k] for k in ('path','sha256')}
  expected={k:v for k,v in health.items() if k not in ['root_review','healthchecks']}
  expected['schema']='n36-execution-release-v1'
  expected['readiness']={'health_release':ref(base/'turns/001414/health-release-v1.json'),'terminal':terminal}
  review=write(out/'root-first-c0-review-v1.json',{**expected,'schema':'n36-root-production-review-v1','decision':'APPROVED'})
  rel=write(out/'execution-release-v1.json',{**expected,'root_review':review})
  write(out/'first-c0-scope-v1.json',{'source':prior['candidate_source'],'plan':health['plan'],'release':rel,'health_reconciliation':ref(base/'turns/001415/terminal-reconciliation-v1.json'),'authorized_scope':'First C0 only, frozen supervisor mandatory PAUSED_FOR_ROOT_G3 before any later cell','source_plan_science_unchanged':True,'validation_authorized':False,'formal_authorized':False,'goal_complete':False})
print('Validating detached first-C0 release through unchanged production consumer',flush=True)
try:
 release.validate_release(health['plan'],rel)
 result={'status':'PASS','plan':health['plan'],'release':rel,'gpu_dispatched':False}
except Exception as e:
 result={'status':'FAIL_CLOSED','error':type(e).__name__,'reason':str(e),'plan':health['plan'],'release':rel,'gpu_dispatched':False}
write(out/'first-c0-release-consumer-v1.json',result)
print(json.dumps(result),flush=True)
