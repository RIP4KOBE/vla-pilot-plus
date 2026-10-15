import pathlib,json,hashlib,datetime,fcntl,yaml
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/001200').resolve();base=root.parent/'autonomy_20261004';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def live(h):
 try:
  a=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();return h['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip() and int(a[19])==h['start_ticks'] and a[0]!='Z'
 except FileNotFoundError:return False
with open(root/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 s=yaml.safe_load((root/'research-state.yaml').read_text());ck=json.loads(cp.read_text());tree=json.loads((cp.parent/'idea_tree.json').read_text());ds=json.loads((base/'driver-status.json').read_text());assert ds['turn']==1200 and live(ds['driver']) and live(ds['process'])
 runner=json.loads((out/'runner-process-v1.json').read_text());controller=json.loads((out/'controller-launch-v1.json').read_text());status=json.loads((out/'controller-status-v1.json').read_text());handles={'controller':controller['handle'],'runner':runner['handle']};observed={k:{**v,'live':live(v)} for k,v in handles.items()}
 terminal=(out/'controller-result-v1.json').exists()
 next_action=('Reconcile turn1200 controller terminal result and exact ledger/native evidence before any recovery; never replay valid outcomes.' if terminal else 'Monitor turn1200 existing N36 controller175364 and bootstrapped runner175399 using recorded boot/start identities and status/result; never launch a duplicate. Reconcile exact ledger and RT-03/04 native/controller/whole-episode obligations at termination; zero automatic recovery. Frozen source/plan immutable while running.')
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 for d in [s,ck]:
  d['active_controller']['handles']=handles;d['active_controller']['runner_process']=ref(out/'runner-process-v1.json');d.update(next_action=next_action,updated_at=now)
 tree['nodes']['15.6'].update(result='N36_FROZEN_BOOTSTRAPPED_CONTROLLER_LAUNCHED',controller_launch=ref(out/'controller-launch-v1.json'),score=None)
 prefixes={}
 for name in ['attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl']:
  p=root/'data'/name;prefixes[name]={**ref(p),'bytes':p.stat().st_size}
 ev=[json.loads(x) for x in (root/'data/attempt-ledger.jsonl').read_text().splitlines()];local=[x for x in ev if x.get('identity',{}).get('iteration')==s['active_iteration']]
 summary={'schema':'autonomy-bounded-operation-summary-v1','at':now,'source':s['source_commit'],'driver':ds['driver'],'coordinator':ds['process'],'live_handles':observed,'active_controller':s['active_controller'],'ledger_prefixes':prefixes,'completed':'Verified bound authority and prior normal exit; adopted exact turn1199 PASS N36 release under runner/state locks and launched one gated operational monitor with frozen source-only bootstrap runner. Scientific source, plan and thresholds unchanged.','controller_status':status,'cohort_events':[{k:x.get(k) for k in ['attempt_id','event','success','output_dir']} for x in local],'next_action':next_action,'unresolved':['N36 development outcomes and RT-03/04 live audit obligations','Original validation/formal/required ablation evidence'],'target_met':False,'stop_present':(base/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z'}
 p=root/'research-state.yaml';tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(p);write(cp,ck);write(cp.parent/'idea_tree.json',tree);write(out/'operational-summary.json',summary)
 (out/'operational-summary.md').write_text(f"Source {s['source_commit']}. Controller175364/start145269523; runner175399/start145269575; boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Live observations in JSON.\n\n{summary['completed']}\n\nStatus: {status['status']}. N36 lifecycle events observed: {len(local)}.\n\nNext: {next_action}\n\nUnresolved: N36 audited outcomes, original validation/formal/ablations. Goal not complete.\n")
print(json.dumps({'summary':ref(out/'operational-summary.json'),'status':status['status'],'cohort_events':summary['cohort_events'],'handles':observed}))
