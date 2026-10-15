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
 assert not n.existing_handles(plan,events)
 for g in r.event_groups(events).values():assert g[-1]['event'] in r.TERMINAL
 n.check_probe(runtime,resources,root)
 device=n.device_check()
 env=r.child_environment(runtime);r.verify_provider(runtime,env,root=root);r.runtime_gpu(runtime,state)
 candidate=dict(state);candidate['n32_budget_authority']=plan['authority']
 snap=rel.admission(plan,authority,candidate,events,resources,reservations,plan['episodes'][0],now=datetime.datetime.now(datetime.timezone.utc),gpu_idle=True)
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 for path in [root/'research-state.yaml',cp,tp]:
  dest=out/(path.name+'.before');assert not dest.exists();shutil.copyfile(path,dest)
 adoption={'schema':'n32r2-root-release-adoption-v1','at':stamp,'source':plan['source']['commit'],'plan':v['plan'],'release':v['release'],'authority':plan['authority'],'validation':c.ref(out/'pre-adoption-validation-v1.json'),'accounting':snap,'device_admission':device,'previous_release_adoption':state.get('n32r1_release_adoption'),'gpu_dispatched':False,'scientific_promotion':False}
 w.atomic_json(out/'root-adoption-v1.json',adoption);ar=c.ref(out/'root-adoption-v1.json')
 state.update(n32_budget_authority=plan['authority'],n32_dev_authority=plan['authority'],n32r2_release_adoption=ar,active_plan=v['plan'],active_iteration=c.COHORT,status='N32R2_RELEASE_ADOPTED_READY_TO_DISPATCH',phase='DEV_READY',updated_at=stamp,current_owned_workers=[],next_action='Launch exactly one N32R2 controller from root-recovery-release-v2; repeat current admission in unmodified runner. No protected phase promotion.')
 checkpoint=json.loads(cp.read_text());checkpoint.update(n32r2_release_adoption=ar,plan=v['plan'],active_plan=v['plan'],execution_release=v['release'],source_commit=plan['source']['commit'],active_controller=None,current_owned_workers=[],active_workers=[],in_flight_executor=None,in_flight_executors=[],automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=c.COHORT,status=state['status'],phase=state['phase'],next_action=state['next_action'],updated_at=stamp,budget_snapshot=snap)
 tree=json.loads(tp.read_text());nodes=tree['nodes'];nodes=nodes.values() if isinstance(nodes,dict) else nodes
 for node in nodes:
  if node['id']=='15.2':node.update(status='running',phase='DEV_READY',result='N32R2 owning-checkout release validated and adopted; 30 fresh Dev primaries / 5 GPUh maximum. Dispatch pending; no accepted scientific evidence.',n32r2_release_adoption=ar)
 tmp=(root/'research-state.yaml').with_suffix('.yaml.adopt-tmp');tmp.write_text(yaml.safe_dump(state,sort_keys=False));os.replace(tmp,root/'research-state.yaml')
 w.atomic_json(cp,checkpoint);w.atomic_json(tp,tree)
 print(json.dumps(adoption,indent=2))
