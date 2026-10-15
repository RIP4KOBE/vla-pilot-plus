import json,pathlib,hashlib,datetime,subprocess,fcntl,os,yaml
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001603'; P=A/'turns/001601/attested-readiness-consumers'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 q=p.with_name(p.name+'.tmp-001603');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 p=pathlib.Path('/proc')/str(v['pid'])/'stat'; a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 tick=int(a[19]) if a else None; match=bool(a and tick==v['start_ticks'] and boot==v['boot_id'])
 return {**v,'observed_start_ticks':tick,'state':a[0] if a else None,'identity_matches':match,'live':bool(match and a[0]!='Z')}
old=read(A/'turns/001602/operational-summary-v1.json'); proc=read(P/'process-v1.json'); handles={k:ident(proc[k]) for k in ['wrapper','executor']}; assert not any(v['live'] for v in handles.values())
e=read(P/'exit-v1.json');assert e['exit']==0 and not e['timeout']
checks={}
def verify(v):
 if isinstance(v,dict):
  if 'path' in v and 'sha256' in v:
   p=pathlib.Path(v['path']); assert p.is_relative_to(W.parent) or p.is_relative_to(pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z'))
   a=ref(p);assert all(a[k]==v[k] for k in ['sha256','bytes'] if k in v),str(p);checks[str(p)]=a
  else:
   for x in v.values():verify(x)
 elif isinstance(v,list):
  for x in v:verify(x)
verify(read(P/'artifact-hash-seal-v1.json')); verify(read(P/'finalization-receipt-v1.json'));verify(old['ledger_prefixes'])
h=read(A/'handoff-v2.json')
for k in ['required_continuation_context','completion_contract']:verify(h[k])
r=read(P/'report-v1.json');assert r['graph_reference_refresh_complete'] and r['affected_passive_consumers_pass'];assert not r['full_production_closure_passed']
s=yaml.safe_load((W/'research-state.yaml').read_text());key='n36_engineering_attested_readiness_consumer_refresh';wt=s[key]['worktree'];source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=wt,text=True).strip();assert source==old['current_source'];assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==old['owner_source']
now=datetime.datetime.now(datetime.timezone.utc).isoformat();nextstep='Obtain independent B5 of turn001601 exact disabled graph and sealed inputs; retain executor-fence runtime/full-closure rejections. Then root reattest final reviewed bindings and run actual production closure in authorized runtime before any separately metered health/episode release. Do not rebuild unchanged evidence.'
rec=dict(schema='n36-attested-readiness-consumer-terminal-reconciliation-v1',at=now,status='TERMINAL_CONSUMERS_HASH_VERIFIED_B5_AND_FULL_CLOSURE_PENDING',source=source,report=ref(P/'report-v1.json'),exit=ref(P/'exit-v1.json'),handles=handles,verified_artifacts=list(checks.values()),blockers=r['blockers'],full_production_closure_passed=False,release_enabled=False,gpu_dispatch=False,target_met=False)
put(T/'terminal-reconciliation-v1.json',rec)
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else read(p);assert d[key]['process_record_path']==str(P/'process-v1.json')
  d[key]['status']=rec['status'];d[key]['live_handles']=[];d['n36_engineering_attested_readiness_terminal_reconciliation']=ref(T/'terminal-reconciliation-v1.json');d['next_action']=nextstep;d['updated_at']=now;d['phase']='N36_ENGINEERING_ATTESTED_READINESS_B5_PENDING'
  if d.get('in_flight_executor',{}).get('process_record_path')==str(P/'process-v1.json'):d['in_flight_executor']['status']=rec['status'];d['in_flight_executor']['live_handles']=[]
  if isyaml:
   q=p.with_name(p.name+'.tmp-001603');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,p)
  else:put(p,d)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result=rec['status'],insight='Consumer refresh exited 0; sealed outputs hash verified. Passive consumer checks pass; runtime/full closure rejected under executor import/read fence and remain unresolved. Fresh independent B5 and root release gates pending; no GPU or scientific promotion.');put(C/'idea_tree.json',tree)
ds=read(A/'driver-status.json');old.update(at=now,turn=1603,driver=ident(ds['driver']),coordinator=ident(ds['process']),live_handles=handles,executor_exit_exists=True,stop_exists=(A/'STOP').exists(),terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),next_bounded_step=nextstep,completed_work=['Verified handoff, authority, continuation and completion-contract hashes; prior normal turn exit and private ledger prefixes.','Reconciled consumer executor exit 0 and absent exact process identities; verified sealed immediate artifacts.','Persisted bounded terminal reconciliation in owning state/checkpoint/Idea Tree; kept runtime/full closure failures and release gates.'],unresolved_evidence=[x['id'] for x in r['blockers']]+['Original validation/formal/required ablation evidence incomplete.'])
old['executor_observation']={'exit':e,'report':ref(P/'report-v1.json')};put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps({'status':rec['status'],'verified_artifacts':len(checks),'summary':ref(T/'operational-summary-v1.json')}))
