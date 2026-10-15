import pathlib,json,hashlib,datetime,fcntl,os,yaml,subprocess
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001846';prev=json.loads((base/'turns/001845/operational-summary-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat();boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def live(h):
 p=P(f"/proc/{h['pid']}/stat");v=dict(h)
 if not p.exists():return dict(v,state='absent',alive=False,identity_verified=False)
 s=p.read_text().rsplit(')',1)[1].split();ticks=int(h.get('start_ticks',h.get('proc_start_ticks')));ok=int(s[19])==ticks and boot==h['boot_id'];return dict(v,start_ticks=ticks,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
ds=json.loads((base/'driver-status.json').read_text());proc=json.loads((base/'turns/001845/measurement-process-v2.json').read_text());childpath=base/'turns/001827/disabled-v3-binding/pending-proof.measurement/child-admitted.json'
handles={k:live(ds[k]) for k in ['driver','process']};handles.update({k:live(proc[k]) for k in ['wrapper','controller']});handles['child']=live(json.loads(childpath.read_text()))
assert handles['driver']['alive'] and handles['process']['alive']
ledgers={};checks={};events={}
for n,r in prev['ledger_prefixes'].items():
 p=P(r['path']);b=p.read_bytes();ok=hashlib.sha256(b[:r['bytes']]).hexdigest()==r['sha256'];assert ok;checks[n]=dict(prior_prefix_preserved=ok,new_bytes=len(b)-r['bytes']);ledgers[n]=ref(p)
 if n in ['readiness-preparation-ledger.jsonl','gpu-healthcheck-ledger.jsonl']:
  events[n]=[{k:v for k,v in row.items() if k in ['event','resource_id','gpu_process_wall_seconds','reserved_gpu_seconds','provider_calls','telemetry_complete','error','process','parent','envelope']} for row in map(json.loads,b.decode().splitlines()) if row.get('resource_id')=='n36_readiness_preparation_recovery_001827']
exitp=base/'turns/001845/measurement-exit-v2.json';exitrecord=json.loads(exitp.read_text()) if exitp.exists() else None
status='MEASUREMENT_RUNNING' if handles['controller']['alive'] else 'MEASUREMENT_TERMINAL_REQUIRES_RECONCILIATION'
next_action='Monitor the existing turn001845 readiness controller3853487/start156801003, wrapper3853486/start156801001, child3859839/start156819381 on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Do not duplicate or replay. At terminal inspect measurement-exit-v2.json, pending-proof.measurement receipts and exact mirrored private readiness/health journals, reconcile charges, then review readiness before downstream adoption. Existing 600-second/one-provider-call release authorizes no episode. Validation/formal/required ablation evidence remains missing.'
record=dict(prev['measurement'],status=status,at=now,handles={k:handles[k] for k in ['wrapper','controller','child']},exit_record=exitrecord,child_admission=ref(childpath))
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1846,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=status,completed_work=['Verified hash-bound handoff, exact user authority, continuation context and completion contract.','Prior coordinator exited normally; reconciled its corrected launch and observed admitted readiness child.','Verified all four historical ledger prefixes preserved; no episode ledger change and no duplicate dispatch.','Monitored existing bounded measurement with matching boot/start identities; native terminal outcome remains pending.'],measurement=record,ledger_prefixes=ledgers,prefix_checks=checks,readiness_events=events,next_bounded_step=next_action,unresolved_evidence=prev['unresolved_evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline=prev['deadline'])
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,y in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if y else json.loads(p.read_text());d['n36_current_readiness_measurement_execution']=record;d['next_action']=next_action;d['updated_at']=now
  tmp=p.with_name(p.name+'.001846.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
p=out/'operational-summary-v1.json'
with p.open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
(out/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=ref(p),status=status,live_handles=handles,prefix_checks=checks)))
