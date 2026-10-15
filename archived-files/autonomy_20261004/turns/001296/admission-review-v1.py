import sys,json,datetime,traceback
from pathlib import Path
out=Path(__file__).resolve().parent
v=json.loads((out/'production-verification-v1.json').read_text());assert v['status']=='PASS_FULL_UNMODIFIED_RELEASE_VERIFICATION'
p=json.loads(Path(v['plan']['path']).read_text());sys.path.insert(0,p['worktree'])
from scripts import qd_ed_n36_runner as runner, qd_ed_n36_release as gate, qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts.qd_ed_n36r2_admission import owner_root
root=owner_root(p);a=w.read_ref(p['authority']);result={'schema':'n36r2-locked-admission-review-v1','plan':v['plan'],'release':v['release'],'dispatch_performed':False}
try:
 with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
  with r.locked(root/'data/qd-ed-state.lock'):
   s,ev,res,reserv=runner.snapshot(root,a)
   assert not s.get('active_controller') and not s.get('current_owned_workers') and not runner.existing_handles(p,ev)
   prospective={**s,'n36_budget_authority':p['authority'],'budget':{**s['budget'],'amendment':a['amendment']}}
   result['accounting']=gate.admission(p,a,prospective,ev,res,reserv,p['episodes'][0],now=datetime.datetime.now(datetime.timezone.utc),gpu_idle=True,release_refs=(v['plan'],v['release']))
   result['device']=runner.device_check()
   runner.check_probe(w.read_ref(p['runtime']),res,root)
   result['status']='PASS_LOCKED_ACCOUNTING_DEVICE_AND_PROBE'
except Exception as e:
 result.update(status='BLOCKED_NO_DISPATCH',error=repr(e),traceback=traceback.format_exc())
result['at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(out/'locked-admission-review-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
