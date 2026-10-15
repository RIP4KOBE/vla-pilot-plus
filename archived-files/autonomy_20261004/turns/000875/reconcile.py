import pathlib,json,hashlib,datetime,sys,subprocess,shutil,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/000875').resolve(); base=out.parent/'000861'; sp=root/'research-state.yaml'; cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
def read(p):return json.loads(pathlib.Path(p).read_text())
def ref(p):return {'path':str(pathlib.Path(p).resolve()),'sha256':hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()}
def write(p,x):
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(x,indent=2)+'\n');q.replace(p)
def verify(v):assert ref(v['path'])['sha256']==v['sha256'];return read(v['path'])
now=datetime.datetime.now(datetime.timezone.utc).isoformat();driver=read(root.parent/'autonomy_20261004/driver-status.json');assert driver['turn']==875
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(); handles=[]
for k in ['driver','process']:
 e=driver[k];a=pathlib.Path(f'/proc/{e["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert e['boot_id']==boot and e['start_ticks']==int(a[19]);handles.append(dict(e,observed_state=a[0]))
assert not pathlib.Path('/proc/2303352').exists() and not pathlib.Path('/proc/2324175').exists()
p=read(base/'plan.frozen-v1.json');result=read(base/'controller-result-v1.json')['result'];assert result['status']=='NUMERIC_FUTILITY';assert not pathlib.Path(p['stop_path']).exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(p['deadline'].replace('Z','+00:00'))
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==p['source']['commit']
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  s=r.read_state(sp);c=read(cp);assert s['active_controller']==c['active_controller'];active=s['active_controller']
  for k in ['launch','plan','release']:verify(active[k])
  assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
  prefixes={}
  for name,e in p['ledger_prefixes'].items():
   b=(root/'data'/name).read_bytes();assert hashlib.sha256(b[:e['bytes']]).hexdigest()==e['sha256'];prefixes[name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
  previous=read(out.parent/'000874/monitor-reconciliation-v1.json')['ledger'];raw=(root/'data/attempt-ledger.jsonl').read_bytes();assert hashlib.sha256(raw[:previous['bytes']]).hexdigest()==previous['sha256']
  events=r.read_events(root/'data/attempt-ledger.jsonl');snap=r.budget_snapshot(events,r.read_events(root/'data/gpu-healthcheck-ledger.jsonl'));assert snap['running']==0
  native=[]
  for o in result['outcomes']:
   rows=[e for e in events if e.get('attempt_id')==o['attempt_id']];valid=[e for e in rows if e['event']=='valid'];assert len(valid)==1 and sum(e['event']=='dispatched' for e in rows)==1
   e=valid[0];assert e['success']==o['success'] and e['identity']['split']=='dev'
   receipt=verify(e['n34_worker_receipt']);native.append({'attempt_id':o['attempt_id'],'success':e['success'],'receipt':e['n34_worker_receipt'],'required_cost_telemetry_complete':e.get('required_cost_telemetry_complete')})
  successes={arm:sum(o['success'] for o in result['outcomes'] if o['profile']==arm) for arm in ['C0','Q0','N34']};assert successes=={'C0':0,'Q0':0,'N34':1};assert len(native)==21 and 1+3<p['gates']['candidate_min_successes']
  protected={k:max(0,v-snap['gpu_hours_by_bucket'][k]) for k,v in s['budget']['gpu_hour_reservations'].items()}
  review={'schema':'n34-continuation-terminal-root-review-v1','at':now,'source':p['source']['commit'],'handles':handles,'closed_controller':active,'controller_result':ref(base/'controller-result-v1.json'),'plan':active['plan'],'release':active['release'],'prior_turn_exit':read(out.parent/'000874/receipt.json')['exit'],'ledger_prefixes':prefixes,'prior_prefix_intact':True,'snapshot':snap,'protected_gpu_hours_remaining':protected,'native_receipts':native,'summary':result['summary'],'disposition':'NUMERIC_FUTILITY_NO_PROMOTION','arithmetic':'N34 1/7; C0 0/7; Q0 0/7. Three unobserved tasks give upper bound 1+3=4 < frozen 5/10 necessary gate. Tasks7-9 Unknown, not failures.','interpretation':p['scientific_interpretation'],'continuation_increment':{'attempts':snap['dispatched']-472,'gpu_hours':snap['gpu_hours_consumed']-69.38354303190809},'next_step':'Bounded Dev-only mechanism comparison of N34 task5 success and task6 failure: native selected proposal survival, observed jaw/target motion and close/dwell timing. Form a falsifiable next hypothesis only after reviewing constraints; no replay or threshold change.','validation_authorized':False,'formal_authorized':False,'target_met':False,'scientific_source_changed':False}
  write(out/'terminal-reconciliation-v1.json',review);rr=ref(out/'terminal-reconciliation-v1.json')
  for f in [sp,cp,tp]:shutil.copyfile(f,out/(f.name+'.before'))
  closed=dict(active,terminal_status='NUMERIC_FUTILITY_NO_PROMOTION',live_handles=[],terminal_review=rr)
  for obj in [s,c]:
   obj.update(active_controller=closed,closed_n34_continuation11_controller=closed,n34_continuation_terminal_review=rr,n34_continuation_status='NUMERIC_FUTILITY_NO_PROMOTION',status='N34_CONTINUATION11_TERMINAL_RECONCILED',phase='DEV_TERMINAL_RECONCILED_PROSPECTIVE_REVIEW',budget_snapshot=snap,automatic_gpu_dispatch_authorized=False,current_owned_workers=[],next_action=review['next_step'],target_met=False,updated_at=now)
  for k in ['dispatched','aborted','valid','running','invalid','completed','gpu_hours_consumed']:s['budget'][k]=snap[k]
  t=read(tp);n=t['nodes']['15.4'];n.update(status='done',execution_authorized=False,score=1/7,result=review['arithmetic'],insight='Observed jaw-centered proposal achieved one Dev success but failed the frozen necessary gate. Outcome-aware amended screen; not confirmatory or independent replication. Native mechanism diagnosis required before next hypothesis.',terminal_review=rr)
  tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
  write(out/'closure-adoption-v1.json',{'at':now,'review':rr,'state':ref(sp),'checkpoint':ref(cp),'tree':ref(tp),'ledger_unchanged':hashlib.sha256((root/'data/attempt-ledger.jsonl').read_bytes()).hexdigest()==prefixes['attempt-ledger.jsonl']['sha256']})
(out/'operational-summary.md').write_text(f'''Turn875 — {now}\n\nSource {p['source']['commit']} unchanged. Driver268073/start97715947 and coordinator2400582/start140219444 verified on boot {boot}; controller2303352 and worker2324175 exited. GPU7 observed 0MiB/0% before closure. STOP absent; deadline2026-10-11T11:13:13Z.\n\nReconciled native receipts for all21 amended Dev cells and intact owning ledger prefixes. N34=1/7, C0=0/7, Q0=0/7; remaining3 tasks Unknown; upper bound4<5. Numeric futility accepted, no promotion/replay/restart. State/checkpoint/tree closed under ordinary runner/state locks; no driver locks acquired.\n\nAccounting: {snap['dispatched']} attempts, {snap['gpu_hours_consumed']} GPUh cumulative; all failures/history retained. Protected remaining GPUh {protected}.\n\nNext bounded step: {review['next_step']}\nUnresolved: mechanism attribution, scientific promotion, matched validation/formal and required ablations. Original goal unmet; no completion record.\n''')
print(json.dumps({'review':rr,'snapshot':snap,'protected':protected}))
