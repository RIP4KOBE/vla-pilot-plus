from pathlib import Path
import json,yaml,hashlib,datetime,fcntl,os
P=Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=(base/'turns/001876').resolve();work=(out/'canonical-successor').resolve();prev=json.loads((base/'turns/001875/operational-summary-v1.json').read_text());boot=P('/proc/sys/kernel/random/boot_id').read_text().strip();now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):
 p=P(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
def live(h):
 p=P(f"/proc/{h['pid']}/stat")
 if not p.exists():return dict(h,alive=False,state='absent',identity_verified=False)
 t=p.read_text().rsplit(')',1)[1].split();ok=boot==h['boot_id'] and int(t[19])==int(h.get('start_ticks',h.get('proc_start_ticks',-1)))
 return dict(h,state=t[0],alive=ok and t[0]!='Z',identity_verified=ok)
ds=json.loads((base/'driver-status.json').read_text());assert ds['turn']==1876
handles={k:live(ds[k]) for k in ['driver','process']};assert all(x['alive'] for x in handles.values())
proc=json.loads((work/'process-v1.json').read_text());handles['executor']={k:live(proc[k]) for k in ['wrapper','executor']}
ledgers=prev['ledger_prefixes']
for r in ledgers.values():assert ref(r['path'])['sha256']==r['sha256'] and P(r['path']).stat().st_size==r['bytes']
assert not (base/'STOP').exists()
entry=dict(status='RUNNING_CPU_CANONICAL_SUCCESSOR_COMPOSITION',at=now,node_id='15.6',source=prev['current_source'],authority=ref(work/'authority-v1.json'),prompt=ref(work/'prompt.txt'),process_record=ref(work/'process-v1.json'),handles=handles['executor'],output_directory=str(work),exit_path=str(work/'exit-v1.json'),report_path=str(work/'report-final-v1.json'),gpu_authorized=False,measurement_authorized=False,source_edits_authorized=False)
next_action='Monitor the existing CPU canonical-successor executor using exact boot/start identities; do not duplicate. On exit reconcile report and actual artifacts, verify canonical references and all41 scientific payload equivalence, then strict disabled production admission and independent finite release review. Preserve prior frozen release and all charges. No measurement or episode is yet released; no new dispatch after2026-10-11T11:13:13Z.'
rr=put(out/'executor-launch-reconciliation-v1.json',dict(schema='n36-canonical-successor-launch-reconciliation-v1',at=now,entry=entry,ledger_prefixes=ledgers,prior_terminal=prev['diagnosis'],collaboration_transport_failure='spawn_agent failed no thread; no child created by that call; used durable official Codex CLI executor',target_met=False))
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 paths=[(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]
 for p,is_yaml in paths:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());assert d.get('in_flight_executor') is None
  d['n36_canonical_successor_preparation']=entry;d['in_flight_executor']=entry;d['in_flight_executors']=[entry];d['next_action']=next_action;d['updated_at']=now
  tmp=p.with_name(p.name+'.001876.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
 p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(p.read_text());n=d['nodes']['15.6'];n['canonical_successor_preparation']=entry;n['result']='RUNNING_CPU_CANONICAL_SUCCESSOR_COMPOSITION';n['insight']='Readiness producer/consumer rejected noncanonical plan reference in prior frozen release. Prospective path-only successor composition is running; strict audit and fresh finite release remain prerequisites, with no scientific promotion.';tmp=p.with_name(p.name+'.001876.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1876,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=entry['status'],completed_work=['Verified bound authorization/handoff, live driver/coordinator boot/start identity, terminal predecessor records and unchanged private ledger prefixes.','Started one bounded CPU-only official current-login gpt-6-astra executor for fresh canonical successor composition.','Recorded actual launch and continuation in owning state/checkpoint/tree without changing science, frozen release, private charges or protected reserves.'],ledger_prefixes=ledgers,executor=entry,reconciliation=rr,next_bounded_step=next_action,unresolved_evidence=['Canonical successor integrity and strict disabled production admission','Independent finite release review and fresh readiness producer/consumer PASS','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=False,deadline=prev['deadline'])
r=put(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(r['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'summary':r,'handles':handles['executor'],'status':entry['status']}))
