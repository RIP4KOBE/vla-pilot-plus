import sys,os,subprocess,json,datetime,yaml
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root),str(root/'scripts')]
from scripts import qd_ed_n32_runner as n
r,w,c=n.r,n.w,n.c
out=root.parent/'variants/n32_archive_eligible_capture/execution-recovery-v2';release_dir=out.parent/'root-recovery-release-v2'
v=w.read_ref(c.ref(release_dir/'pre-adoption-validation-v1.json'));adoption=w.read_ref(c.ref(release_dir/'root-adoption-v1.json'))
assert not (out/'root-launch-v1.json').exists() and not (out/'controller-start-v1.json').exists()
plan=w.read_ref(v['plan']);authority=w.read_ref(plan['authority'])
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(root/'data/qd-ed-state.lock'):
 state,events,resources,reservations=n.snapshot(root,authority)
 assert not state.get('active_controller') and state['n32r2_release_adoption']==c.ref(release_dir/'root-adoption-v1.json')
 assert not n.existing_handles(plan,events) and r.budget_snapshot(events,resources)==adoption['accounting']
 n.release.admission(plan,authority,state,events,resources,reservations,plan['episodes'][0],now=datetime.datetime.now(datetime.timezone.utc),gpu_idle=True)
 n.device_check()
 with (out/'controller-v1.log').open('xb') as log:
  p=subprocess.Popen([sys.executable,'-B',str(out/'controller-v1.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 identity=n.process_identity(p.pid);stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 launch={'schema':'n32r2-root-controller-launch-v1','at':stamp,'controller':identity,'plan':v['plan'],'release':v['release'],'source':v['source'],'launcher':c.ref(out/'controller-v1.py'),'status_path':str(out/'controller-start-v1.json'),'result_path':str(out/'controller-result-v1.json'),'error_path':str(out/'controller-error-v1.json'),'status':'RUNNING_RELEASE_REVALIDATION','monitoring':'Single current controller. Never restart while valid identity remains live; preserve worker and reconcile ledger on exit.'}
 w.atomic_json(out/'root-launch-v1.json',launch)
 handle={**launch,'launch':c.ref(out/'root-launch-v1.json')}
 state.update(active_controller=handle,current_owned_workers=[{'role':'N32R2 controller','identity':identity}],status='N32R2_CONTROLLER_RUNNING',phase='DEV_EXECUTION',updated_at=stamp,next_action='Monitor execution-recovery-v2 controller identity and owning journal. No duplicate dispatch; review eventual native/generic terminal evidence.')
 checkpoint=json.loads(cp.read_text());checkpoint.update(active_controller=handle,current_owned_workers=state['current_owned_workers'],status=state['status'],phase=state['phase'],updated_at=stamp,next_action=state['next_action'])
 tmp=(root/'research-state.yaml').with_suffix('.yaml.launch-tmp');tmp.write_text(yaml.safe_dump(state,sort_keys=False));os.replace(tmp,root/'research-state.yaml')
 tmp=cp.with_suffix('.json.launch-tmp');tmp.write_text(json.dumps(checkpoint,indent=2)+'\n');os.replace(tmp,cp)
 print(json.dumps(launch,indent=2))
