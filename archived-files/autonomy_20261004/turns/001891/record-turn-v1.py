import pathlib,json,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path;root=P.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001891';prev=json.loads((base/'turns/001890/operational-summary-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat();boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 p=P(p);return dict(path=str(p.absolute()),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
def live(h):
 h=dict(h);h.update(alive=False,identity_verified=False,state='absent')
 try:
  s=P(f"/proc/{h['pid']}/stat").read_text().rsplit(')',1)[1].split();h.update(state=s[0],actual_start_ticks=int(s[19]));h['identity_verified']=h.get('boot_id')==boot and int(h.get('start_ticks',h.get('proc_start_ticks',0)))==int(s[19]);h['alive']=h['identity_verified'] and s[0]!='Z'
 except FileNotFoundError:pass
 return h
ledgers={}
for k,r in prev['ledger_prefixes'].items():
 q=ref(r['path']);assert q['sha256']==r['sha256'] and q['bytes']==r['bytes'];q['previous_prefix_preserved']=True;ledgers[k]=q
result=json.loads((base/'turns/001888/producer-consumer-v1.json').read_text());assert result['status']=='PASS_CPU_PRODUCER_AND_RUNTIME_CONSUMER'
for k in ['proof','root_acceptance','runtime']:assert ref(result[k]['path'])['sha256']==result[k]['sha256']
exit_result=json.loads((base/'turns/001888/cpu-exit-v1.json').read_text());assert exit_result['returncode']==0
oldhandles={k:live(v) for k,v in prev['live_handles'].items() if k!='process'}
assert not oldhandles['readiness_validator']['alive'] and not oldhandles['readiness_validator_wrapper']['alive']
terminal=dict(schema='n36-canonical-readiness-terminal-reconciliation-v1',at=now,status='PASS_CPU_PRODUCER_AND_RUNTIME_CONSUMER',result=ref(base/'turns/001888/producer-consumer-v1.json'),exit=ref(base/'turns/001888/cpu-exit-v1.json'),verified_outputs={k:result[k] for k in ['proof','root_acceptance','runtime']},ledger_prefixes=ledgers,old_handles=oldhandles,episode_authorized=False,health_authorized=False)
tr=put(out/'terminal-reconciliation-v1.json',terminal)
process=json.loads((out/'cpu-operation-process-v1.json').read_text());handles={k:live(v) for k,v in process.items() if isinstance(v,dict) and 'pid' in v};driver=json.loads((base/'driver-status.json').read_text());handles.update({k:live(driver[k]) for k in ['driver','process']})
review=json.loads((out/'measured-graph-v2/audit-result-v1.json').read_text());assert review['status']=='PASS_MEASURED_GRAPH_REBINDING_AND_RETAINED_RECEIPT'
nextstep='Monitor turn001891 CPU production audit via cpu-operation-process-v1.json, audit-result-v1.json and audit-exit-v1.json; no duplicate audit or readiness measurement. Reconcile terminal output, then independently review and prospectively release only if all gates and deadline sufficiency pass. At/after 2026-10-11T11:13:13Z no new dispatch; preserve existing work and root handoff. Original validation/formal/required ablation evidence remains absent.'
record=dict(status='RUNNING_CPU_MEASURED_FULL_PRODUCTION_AUDIT',at=now,graph=review['graph'],process_record=ref(out/'cpu-operation-process-v1.json'),handles=handles,result_path=str(out/'audit-result-v1.json'),exit_path=str(out/'audit-exit-v1.json'),gpu_authorized=False,source=prev['current_source'])
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1891,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=record['status'],ledger_prefixes=ledgers,completed_work=['Verified handoff/authority hashes, owning ACTIVE/PASS resource isolation, prior successful turn receipt, driver/coordinator boot/start identities and four unchanged private ledgers.','Reconciled CPU validator successful exit and exact proof, acceptance and measured runtime hashes; no replay or recovery.','Composed disabled measured graph preserving all41 scientific payloads; retained runtime receipt PASS.','Started one CPU-only production audit of measured bindings; recorded durable wrapper/child identities and output paths.'],terminal_reconciliation=tr,measured_graph_review=review,production_audit=record,next_bounded_step=nextstep,unresolved_evidence=['Full production audit and independent release review','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline=prev['deadline'])
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in ledgers.values():assert ref(r['path'])['sha256']==r['sha256']
 sr=put(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
 for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());v=d['n36_canonical_readiness_producer_consumer'];v.update(status=result['status'],terminal_reconciliation=tr,result=terminal['result'],handles={k:oldhandles[k] for k in ['readiness_validator','readiness_validator_wrapper']});d['n36_canonical_measured_graph_admission']=dict(status=review['status'],at=now,review=ref(out/'measured-graph-v2/audit-result-v1.json'),graph=review['graph'],gpu_authorized=False);d['n36_canonical_measured_full_production_audit']=record;d['latest_operational_summary']=sr;d['next_action']=nextstep;d['updated_at']=now;t=p.with_name(p.name+'.001891.tmp');t.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(t,p)
print(json.dumps(dict(summary=sr,handles=handles)))
