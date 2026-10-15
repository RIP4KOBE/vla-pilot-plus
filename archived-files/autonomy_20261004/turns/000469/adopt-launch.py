import sys,pathlib,json,datetime,os,subprocess,yaml
root=pathlib.Path.cwd();sys.path[:0]=[str(root),str(root/'scripts')]
from scripts import qd_ed_n32r3_runner as n, qd_ed_n32r3_contract as c
out=root.parent/'autonomy_20261004/turns/000469';a=json.loads((out/'admission.json').read_text());assert a['status']=='PASS'
p=c.read_ref(a['plan']);c.read_ref(a['release']);authority=c.read_ref(p['authority']);runtime=c.read_ref(p['runtime'])
paths=[root/'research-state.yaml',root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json']
with n.r.locked(root/'data/qd-ed-runner.lock',nonblocking=True),n.r.locked(root/'data/qd-ed-state.lock'):
 assert not (out/'launch.json').exists()
 s,events,resources,reservations=n.snapshot(root,authority)
 assert s['active_controller'] is None and not n.continuation_handles(p,events)
 assert n.journal_prefix(root/'data/attempt-ledger.jsonl')==a['ledger_prefix']
 n.release.admission(p,authority,s,events,resources,reservations,p['episodes'][0],now=datetime.datetime.now(datetime.timezone.utc),gpu_idle=True)
 n.device_check()
 cp=json.loads(paths[1].read_text());tree=json.loads(paths[2].read_text())
 for path in paths:
  backup=out/(path.name+'.before');assert not backup.exists();backup.write_bytes(path.read_bytes())
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 env=n.r.child_environment(runtime)
 # Preserve the established root/scripts import search for legacy queue helpers.
 cmd=[sys.executable,'-B',str(out/'controller-wrapper.py')]
 with (out/'controller.log').open('x') as log:
  child=subprocess.Popen(cmd,cwd=root,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 identity=n.process_identity(child.pid)
 launch={'schema':'n32r3-root-launch-v1','at':stamp,'controller':identity,'argv':cmd,'wrapper':c.ref(out/'controller-wrapper.py'),'plan':a['plan'],'release':a['release'],'admission':c.ref(out/'admission.json'),'status_path':str(out/'controller-status.json'),'exit_path':str(out/'controller-exit.json'),'source':p['source']['commit'],'scientific_source':p['scientific_source']['commit'],'gate':'HANDLE_RECORDED_BEFORE_GO'}
 n.w.atomic_json(out/'launch.json',launch)
 handle={**identity,'launch':c.ref(out/'launch.json'),'status_path':launch['status_path'],'result_path':launch['exit_path'],'plan':a['plan'],'release':a['release']}
 next_step='Monitor sole N32R3 controller via turn469 launch/status/exit and owning ledger. Never duplicate or replay. Inspect terminal native evidence before scientific promotion; validation/formal remain unauthorized.'
 for obj in [s,cp]:
  obj.update(n32r3_release_adoption=c.ref(out/'launch.json'),active_controller=handle,active_plan=a['plan'],active_iteration=c.COHORT,source_commit=p['source']['commit'],scientific_source_commit=p['scientific_source']['commit'],status='N32R3_CONTROLLER_LAUNCHED',phase='DEV_RUNNING',updated_at=stamp,next_action=next_step,current_owned_workers=[])
 cp.update(plan=a['plan'],execution_release=a['release'],automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=c.COHORT)
 tree['nodes']['15.2'].update(status='running',phase='DEV_RUNNING',result=next_step,n32r3_release_adoption=c.ref(out/'launch.json'))
 for path,obj in zip(paths,[s,cp,tree]):
  temp=path.with_name(path.name+'.turn469.tmp')
  with temp.open('x') as f:
   f.write(yaml.safe_dump(obj,sort_keys=False) if path.suffix=='.yaml' else json.dumps(obj,indent=2)+'\n');f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 assert not pathlib.Path(p['stop_path']).exists()
 child.stdin.write(b'G');child.stdin.flush();child.stdin.close()
 print(json.dumps(launch))
