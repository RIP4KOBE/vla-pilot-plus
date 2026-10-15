import json,pathlib,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path; root=P.cwd(); base=(root/'../autonomy_20261004').resolve(); out=base/'turns/001861'; prev=json.loads((base/'turns/001860/operational-summary-v1.json').read_text()); boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 p=P(p); b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def live(h):
 p=P('/proc')/str(h['pid'])/'stat'
 if not p.exists(): return dict(h,alive=False,identity_verified=False,state='absent')
 s=p.read_text().rsplit(')',1)[1].split(); ok=boot==h['boot_id'] and int(s[19])==int(h['start_ticks']); return dict(h,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
for r in prev['ledger_prefixes'].values(): assert ref(r['path'])==r
now=datetime.datetime.now(datetime.timezone.utc); driver=json.loads((base/'driver-status.json').read_text()); handles={k:live(driver[k]) for k in ['driver','process']}; job=P(prev['executor']['output_directory']); process=json.loads((job/'process-v1.json').read_text()); jobs={k:live(process[k]) for k in ['wrapper','executor']}
assert all(h['alive'] for h in handles.values()); assert all(not h['alive'] for h in jobs.values())
exit_record=json.loads((job/'exit-v1.json').read_text()); assert exit_record['exit']==0 and not exit_record['timeout']
report=json.loads((job/'report-final-v2.json').read_text())
checked=[]
for k,v in report.get('outputs',{}).items():
 if isinstance(v,dict) and 'path' in v and 'sha256' in v:
  assert ref(v['path'])['sha256']==v['sha256'];checked.append(k)
for k in ['candidate_graph','authority','proposal','composition_integrity','production_verifier_receipt','next_commands']:
 v=report[k];assert ref(v['path'])['sha256']==v['sha256']
record=dict(prev['executor'],at=now.isoformat(),status='COMPLETED_CPU_DISABLED_COMPOSITION_PENDING_OWNER_REVIEW',**jobs,terminal_report=ref(job/'report-final-v2.json'),exit_record=ref(job/'exit-v1.json'))
next_step='Independently reconcile four exact retained predecessor sequences and terminal handles; review successor report-final-v2.json and changed references, then author authentic owner reconciliation and controller binding review before a fresh disabled graph admission. Use next-commands-v2.json. No GPU/measurement release adopted. Preserve source808e27f, scientific gates, all charges and deadline2026-10-11T11:13:13Z.'
summary=dict(prev,at=now.isoformat(),turn=1861,live_handles=handles,cpu_operation_handles=list(jobs.values()),executor=record,controller_status='CPU_SUCCESSOR_COMPOSITION_TERMINAL_OWNER_REVIEW_PENDING',completed_work=['Verified bound handoff/authorization/continuation/completion contract; ACTIVE/PASS owning resource isolation and STOP absent.','Reconciled existing executor exit0/no timeout and absent process identities without restart or duplicate.','Verified final report referenced output hashes and unchanged four complete private ledger prefixes; source HEADs unchanged.','Inspected expected production admission blocks: null owner reconciliation and unreviewed controller binding; these remain gates, not successful admission.'],verified_output_count=len(checked),next_bounded_step=next_step,stop_present=(base/'STOP').exists())
p=out/'operational-summary-v1.json'
with p.open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
sr=ref(p);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());d['n36_fresh_successor_disabled_composition']=record;d['active_executor']=None;d['latest_operational_summary']=sr;d['next_action']=next_step;d['updated_at']=now.isoformat();tmp=p.with_name(p.name+'.001861.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
for r in prev['ledger_prefixes'].values(): assert ref(r['path'])==r
print(json.dumps(dict(summary=sr,handles=jobs,verified_outputs=len(checked),target_met=False)))
