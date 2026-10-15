import sys,os,json,datetime,shutil,yaml
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root),str(root/'scripts')]
from scripts import qd_ed_n32_runner as n
r,w,c,rel=n.r,n.w,n.c,n.release
out=root.parent/'variants/n32_archive_eligible_capture/root-recovery-release-v2'
v=w.read_ref(c.ref(out/'pre-adoption-validation-v1.json'));assert v['status']=='PASS'
plan=w.read_ref(v['plan']);runtime=w.read_ref(plan['runtime']);authority=w.read_ref(plan['authority'])
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
tp=cp.with_name('idea_tree.json')
assert not Path(plan['stop_path']).exists() and not Path(plan['stop_path']).is_symlink()
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(root/'data/qd-ed-state.lock'):
 state,events,resources,reservations=n.snapshot(root,authority)
 assert r.budget_snapshot(events,resources)==v['accounting']
 assert state.get('active_controller') is None
 assert state['status']=='N32R2_RELEASE_ADOPTED_READY_TO_DISPATCH'
 adoption=w.read_ref(c.ref(out/'root-adoption-v1.json'));ar=c.ref(out/'root-adoption-v1.json')
 assert state['n32r2_release_adoption']==ar and state['n32_budget_authority']==plan['authority']
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();snap=r.budget_snapshot(events,resources)
 checkpoint=json.loads(cp.read_text());checkpoint.update(n32r2_release_adoption=ar,plan=v['plan'],active_plan=v['plan'],execution_release=v['release'],source_commit=plan['source']['commit'],active_controller=None,current_owned_workers=[],active_workers=[],in_flight_executor=None,in_flight_executors=[],automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=c.COHORT,status=state['status'],phase=state['phase'],next_action=state['next_action'],updated_at=stamp,budget_snapshot=snap)
 tree=json.loads(tp.read_text());nodes=tree['nodes'];nodes=nodes.values() if isinstance(nodes,dict) else nodes
 for node in nodes:
  if node['id']=='15.2':node.update(status='running',phase='DEV_READY',result='N32R2 owning-checkout release validated and adopted; 30 fresh Dev primaries / 5 GPUh maximum. Dispatch pending; no accepted scientific evidence.',n32r2_release_adoption=ar)
 for path,obj in [(cp,checkpoint),(tp,tree)]:
  temp=path.with_suffix('.json.adopt-tmp');temp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(temp,path)
 result={'schema':'n32r2-adoption-reconciliation-v1','at':stamp,'adoption':ar,'reason':'Original adoption updated state and immutable adoption artifact; worker atomic_json correctly refused existing mutable checkpoint. Reconciled actual side effects and completed checkpoint/tree via atomic replacement under owning locks. No launch or journal mutation occurred.','state_adopted':True,'checkpoint_adopted':True,'tree_adopted':True,'gpu_dispatched':False}
 w.atomic_json(out/'adoption-reconciliation-v1.json',result);print(json.dumps(result,indent=2))
