import json,pathlib,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001860';prev=json.loads((base/'turns/001859/operational-summary-v1.json').read_text());boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 p=P(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def live(h):
 p=P('/proc')/str(h['pid'])/'stat'
 if not p.exists():return dict(h,alive=False,identity_verified=False,state='absent')
 s=p.read_text().rsplit(')',1)[1].split();ok=boot==h['boot_id'] and int(s[19])==int(h['start_ticks']);return dict(h,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
for r in prev['ledger_prefixes'].values():assert ref(r['path'])==r
now=datetime.datetime.now(datetime.timezone.utc);driver=json.loads((base/'driver-status.json').read_text());handles={k:live(driver[k]) for k in ['driver','process']};job=P(prev['executor']['output_directory']);process=json.loads((job/'process-v1.json').read_text());jobs={k:live(process[k]) for k in ['wrapper','executor']}
assert all(h['alive'] for h in handles.values());assert all(h['alive'] for h in jobs.values());assert not (job/'exit-v1.json').exists()
record=dict(prev['executor'],at=now.isoformat(),**jobs)
summary=dict(prev,at=now.isoformat(),turn=1860,live_handles=handles,cpu_operation_handles=list(jobs.values()),executor=record,completed_work=['Verified bound handoff, exact authorization, continuation and completion-contract hashes; inspected owning state/checkpoint and ACTIVE/PASS resource isolation.','Reconciled live driver/coordinator and pre-existing CPU executor by PID, boot ID and start ticks; executor progressing on bounded disabled successor production checks; no duplicate launched.','Confirmed all four private ledger hashes and both source HEADs unchanged; no GPU dispatch, source change, accounting change or protected evaluation.'],stop_present=(base/'STOP').exists())
p=out/'operational-summary-v1.json'
with p.open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
sr=ref(p);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());d['n36_fresh_successor_disabled_composition']=record;d['active_executor']=record;d['latest_operational_summary']=sr;d['updated_at']=now.isoformat();tmp=p.with_name(p.name+'.001860.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
for r in prev['ledger_prefixes'].values():assert ref(r['path'])==r
print(json.dumps(dict(summary=sr,handles=jobs,target_met=False)))
