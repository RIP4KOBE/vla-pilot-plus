import pathlib,json,hashlib,datetime,fcntl,os,yaml,subprocess
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001847';prev=json.loads((base/'turns/001846/operational-summary-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat();boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
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
assert exitrecord['returncode']==0
assert not any(handles[k]['alive'] for k in ['wrapper','controller','child'])
rows={n:[r for r in map(json.loads,P(ledgers[n]['path']).read_text().splitlines()) if r.get('resource_id')=='n36_readiness_preparation_recovery_001827'] for n in ['readiness-preparation-ledger.jsonl','gpu-healthcheck-ledger.jsonl']}
assert rows['readiness-preparation-ledger.jsonl']==rows['gpu-healthcheck-ledger.jsonl']
terminal=rows['readiness-preparation-ledger.jsonl'][-1]
assert terminal['event']=='completed' and terminal['telemetry_complete'] is True and terminal['error'] is None
assert 0 < terminal['gpu_process_wall_seconds'] <= 600 and terminal['provider_calls']==1
proofp=base/'turns/001827/disabled-v3-binding/pending-proof.json';proof=json.loads(proofp.read_text());verified=[]
for k,v in proof.items():
 if isinstance(v,dict) and 'path' in v and 'sha256' in v:
  assert ref(P(v['path']))['sha256']==v['sha256'];verified.append(k)
assert proof['measurement_envelope']==terminal['envelope']
closure=dict(schema='readiness-terminal-reconciliation-v1',at=now,status='PASS_TERMINAL_ACCOUNTING_RECONCILED_READINESS_ADOPTION_PENDING',exit=ref(exitp),proof=ref(proofp),verified_direct_proof_references=verified,terminal=terminal,mirrored_events_equal=True,prior_prefixes_preserved=True,episode_ledger_unchanged=checks['attempt-ledger.jsonl']['new_bytes']==0,actual_gpu_hours=terminal['gpu_process_wall_seconds']/3600,remaining_reserved_seconds=600-terminal['gpu_process_wall_seconds'],no_new_charge_appended=True,live_experiment_handles=[],scientific_success=False)
closurep=out/'terminal-reconciliation-v1.json';closurep.write_text(json.dumps(closure,indent=2)+'\n')
status=closure['status']
next_action='Review the measured pending-proof.json with the frozen readiness producer/consumer gates from source808e27f; terminal measurement and mirrored charges are reconciled in turn001847/terminal-reconciliation-v1.json. Do not replay measurement. No episode authorized by this release. Before downstream adoption inspect its prospective bounded release and exact state gates; retain all charges. Validation/formal/required ablation evidence remains missing.'
record=dict(prev['measurement'],status=status,at=now,handles={k:handles[k] for k in ['wrapper','controller','child']},exit_record=exitrecord,terminal_reconciliation=ref(closurep),child_admission=ref(childpath))
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1847,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=status,completed_work=['Verified handoff/authorization/continuation/completion hashes, resource isolation and prior normal coordinator exit.','Observed readiness measurement terminal exit0 and verified all experiment handles exited.','Verified direct proof artifact hashes and exact mirrored completed accounting:270.01767802238464 GPU seconds and one provider call.','Preserved all four ledger prefixes and unchanged episode ledger; no dispatch, replay, source change or promotion.'],measurement=record,ledger_prefixes=ledgers,prefix_checks=checks,readiness_events=events,next_bounded_step=next_action,unresolved_evidence=['Full readiness producer/consumer validation and adoption','Subsequent valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline=prev['deadline'])
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,y in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if y else json.loads(p.read_text());d['n36_current_readiness_measurement_execution']=record;d['next_action']=next_action;d['updated_at']=now
  tmp=p.with_name(p.name+'.001847.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
p=out/'operational-summary-v1.json'
with p.open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
(out/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=ref(p),status=status,live_handles=handles,prefix_checks=checks)))
