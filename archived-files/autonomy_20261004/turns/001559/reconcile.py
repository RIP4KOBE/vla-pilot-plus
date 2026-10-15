import pathlib,json,hashlib,datetime,fcntl,yaml,subprocess
owner=pathlib.Path.cwd(); A=owner.parent/'autonomy_20261004'; T=A/'turns/001559'; B=A/'turns/001556/independent-b5'; C=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 x=ref(r['path']);assert x['sha256']==r['sha256'];return x
now=datetime.datetime.now(datetime.timezone.utc).isoformat();r=json.loads((B/'report-v1.json').read_text());f=json.loads((B/'artifact-final-check-v1.json').read_text());e=json.loads((B/'exit-v1.json').read_text());assert e['exit']==0 and not e['timeout'];assert not pathlib.Path('/proc/2247369').exists();assert not pathlib.Path('/proc/2247368').exists()
verify(f['report']);verify(f['review']);roots={k:verify(v) for k,v in r['roots'].items()};assert r['status']=='INDEPENDENT_B5_PASS_DISABLED_PREPARATION_ONLY';assert not r['release_enabled'];assert not r['blockers']
ledgers={}
for n,v in r['unchanged_ledger_checks']['at_report'].items():ledgers[n]=verify(v)
prior=json.loads((A/'turns/001558/receipt.json').read_text());assert prior['status']=='completed_turn'
review=dict(schema='n36-independent-b5-terminal-root-review-v1',at=now,status='ACCEPT_DISABLED_PREPARATION_ONLY',report=ref(B/'report-v1.json'),independent_review=ref(B/'independent-b5-review-v1.json'),exit=ref(B/'exit-v1.json'),final_check=ref(B/'artifact-final-check-v1.json'),source=r['source'],roots=roots,ledgers=ledgers,future_gates=r['future_gates'],release_enabled=False,target_met=False,scope='Terminal reconciliation of independent B5. No source/accounting adoption or release; unchanged source graph only. Future implementation changes require focused transitive binding refresh and review.')
p=T/'terminal-review-v1.json';p.write_text(json.dumps(review,indent=2)+'\n');rr=ref(p)
next_step='Implement G7 dispatch lifecycle in an isolated executor with focused review, retaining fail-closed source/runtime/native/readiness checks; refresh only affected proof/graph/B5 roots. Then evaluate bounded diagnostic adoption/release. No scientific promotion or goal completion is evidenced.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,is_yaml in [(owner/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text()); d['n36_engineering_independent_b5']['status']='TERMINAL_PASS_DISABLED_PREPARATION_ROOT_ACCEPTED';d['n36_engineering_independent_b5']['terminal_review']=rr;d['next_action']=next_step;d['updated_at']=now
  tmp=p.with_suffix('.tmp-001559');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(d,indent=2)+'\n');tmp.replace(p)
 p=C/'idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(result='INDEPENDENT_B5_PASS_DISABLED_PREPARATION_ONLY',insight='Independent exact graph preparation review accepted after exit0 and unchanged ledger verification. Dispatch veto, actual readiness, owner release and original goal evidence remain unresolved.');tmp=p.with_suffix('.tmp-001559');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(p)
s=json.loads((A/'turns/001558/operational-summary-v1.json').read_text());s.update(at=now,turn=1559,completed_work='Verified bound authority and continuation, prior normal exit, exact live identities and unchanged ledgers. Reconciled independent B5 exit0 and hash-bound PASS for disabled preparation; updated owning state/checkpoint/tree without source or resource mutation.',next_bounded_step=next_step,terminal_review=rr,unresolved_evidence=r['future_gates'],STOP_present=(A/'STOP').exists(),executor_observation={'status':'TERMINAL_EXIT0','release_enabled':False,'exit_record_present':True});s['active_executor']['status']='TERMINAL_PASS_DISABLED_PREPARATION_ROOT_ACCEPTED';s['live_handles']=[]
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for role,pid in [('driver',268073),('coordinator',2258846)]:
 p=pathlib.Path('/proc')/str(pid)/'stat'
 if p.exists():
  parts=p.read_text().split(') ')[1].split();s['live_handles'].append(dict(role=role,pid=pid,boot_id=boot,start_ticks=int(parts[19]),state=parts[0]))
p=T/'operational-summary-v1.json';p.write_text(json.dumps(s,indent=2)+'\n');(T/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  '+p.name+'\n');print(json.dumps({'review':rr,'summary':ref(p),'target_met':False},indent=2))
