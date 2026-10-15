import pathlib,json,hashlib,datetime,decimal,fcntl,os,yaml,subprocess
P=pathlib.Path; root=P.cwd(); base=(root/'../autonomy_20261004').resolve(); out=base/'turns/001879'; job=base/'turns/001876/canonical-successor'; boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 p=P(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def checkref(r):
 b=P(r['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256'];return b
def live(h):
 p=P('/proc')/str(h['pid'])/'stat'; r=dict(h)
 if not p.exists():return dict(r,state='absent',alive=False,identity_verified=False)
 s=p.read_text().rsplit(')',1)[1].split();ok=h['boot_id']==boot and int(h.get('start_ticks',h.get('proc_start_ticks')))==int(s[19]);return dict(r,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
def write(name,d):
 p=out/name
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); contract=json.loads((job/'recovery-prefix-contract.disabled-v1.json').read_text()); prev=json.loads((base/'turns/001878/operational-summary-v1.json').read_text()); driver=json.loads((base/'driver-status.json').read_text()); live_driver={k:live(driver[k]) for k in ('driver','process')};assert all(h['alive'] for h in live_driver.values()); assert not (base/'STOP').exists()
source=prev['current_source'];assert subprocess.check_output(['git','-C',source['worktree'],'rev-parse','HEAD'],text=True).strip()==source['commit']
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 captures={k:checkref(v) for k,v in contract['root_observed_ledger_prefixes'].items()}
 for k,v in contract['root_observed_ledger_prefixes'].items():assert len(captures[k])==v['bytes'] and ref(v['path'])==prev['ledger_prefixes'][k]
 handles={};results=[];total=decimal.Decimal(0)
 for pred in contract['predecessors']:
  raw=checkref(pred['raw_sequence']);assert len(raw)==pred['raw_bytes'];assert raw.endswith(b'\n')
  rows=[json.loads(x) for x in raw.splitlines()];assert rows==pred['rows'];assert [r['event'] for r in rows]==pred['events'];assert len(rows)==3
  assert all(r['resource_id']==pred['resource_id'] for r in rows)
  for label,key in [('global_health_segment','gpu-healthcheck-ledger.jsonl'),('own_journal','readiness-preparation-ledger.jsonl')]:
   seg=pred[label];assert captures[key][seg['start_inclusive']:seg['end_exclusive']]==raw;assert hashlib.sha256(raw).hexdigest()==seg['sha256']
  for line,seg in zip(raw.splitlines(keepends=True),pred['row_segments']):
   assert len(line)==seg['bytes'];assert hashlib.sha256(line).hexdigest()==seg['sha256']
   assert captures['gpu-healthcheck-ledger.jsonl'][seg['global_start_inclusive']:seg['global_end_exclusive']]==line
   assert captures['readiness-preparation-ledger.jsonl'][seg['own_start_inclusive']:seg['own_end_exclusive']]==line
  terminal=rows[-1];assert terminal['event']==pred['terminal_status'];assert terminal['telemetry_complete']==pred['telemetry_complete'];assert terminal['gpu_process_wall_seconds']==pred['retained_charge_gpu_seconds'];assert terminal['provider_calls']==pred['provider_calls_retained']
  for name,b in captures.items():
   matches=[json.loads(line) for line in b.splitlines() if json.loads(line).get('resource_id')==pred['resource_id']]
   assert matches==(rows if name in ('gpu-healthcheck-ledger.jsonl','readiness-preparation-ledger.jsonl') else [])
  for row in rows:
   for k in ('parent','process'):
    if row.get(k):
     h=live(row[k]);assert not h['alive'];handles[str(h['pid'])]=h
  total+=decimal.Decimal(str(pred['retained_charge_gpu_seconds']))
  results.append({k:pred[k] for k in ('resource_id','terminal_status','telemetry_complete','retained_charge_gpu_seconds','retained_charge_gpu_hours','provider_calls_retained','raw_sequence')})
 successor=contract['successor']['resource_id']
 assert all(not any(json.loads(x).get('resource_id')==successor for x in b.splitlines()) for b in captures.values())
 for k,r in contract['original_ledger_prefixes'].items():assert hashlib.sha256(captures[k][:r['bytes']]).hexdigest()==r['sha256']
 review=write('predecessor-owner-review-v1.json',dict(schema='n36-five-predecessor-owner-review-v1',at=now,status='PASS_EXACT_RETAINED_TERMINALS',contract=ref(job/'recovery-prefix-contract.disabled-v1.json'),predecessors=results,retained_charge_gpu_seconds=str(total),provider_calls_retained=sum(p['provider_calls_retained'] for p in results),checks=['Exact complete ledger prefix hashes unchanged','Original amendment prefixes preserved','Five raw three-event sequences byte-identical to own and global ledger slices','Each raw row hash and typed row equals candidate contract','No duplicate predecessor outside retained partitions','All recorded parent/child identities terminal','Successor absent from all four complete ledgers'],unknown_telemetry_preserved=True,gpu_authorized=False,scientific_success=False,scope='Historical resource reconciliation only; no controller binding, graph admission or readiness approval.'))
 reconciliation=write('terminal-reconciliation-v1.json',dict(schema='n36-recovery-binding-review-terminal-reconciliation-v1',at=now,review=review,live_handles=[],terminal_handles=list(handles.values()),root_accepts_blocking_findings=True,ledger_prefixes=contract['root_observed_ledger_prefixes'],retained_predecessors=results,retained_charge_gpu_seconds=str(total),gpu_authorized=False,scientific_success=False))
 next_step='Use turn001879 owner review and terminal reconciliation to bind five consumed predecessors in a fresh disabled graph. Review successor changed controller runtime/closure bindings against historical accepted semantics and resolve eight inherited noncanonical specification references within frozen policy before exact production graph/manifests admission. Do not rerun a known-blocked full audit. Preserve null GPU/release gates until accounting/freshness/independent review pass. No repetition of completed predecessor reconciliation unless ledgers change; deadline2026-10-11T11:13:13Z.'
 summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1879,current_source=source,owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=live_driver,cpu_operation_handles=[],controller_status='NO_LIVE_EXPERIMENT_CONTROLLER_OWNER_PREDECESSOR_RECONCILIATION_PASS',ledger_prefixes=contract['root_observed_ledger_prefixes'],ledgers_unchanged=True,completed_work=['Verified handoff/authority hashes, live driver/coordinator boot/start identities, owning isolation and ledger prefixes.','Independently reconciled exact raw five predecessor lifecycles, retained charges and unknown telemetry; all recorded parent/child identities absent.','Authored hash-bound owner review and terminal reconciliation; no source changes or dispatch.'],review=review,terminal_reconciliation=reconciliation,next_bounded_step=next_step,unresolved_evidence=['Changed controller binding review','Full production graph and manifest admission','Fresh readiness/accounting/release and independent review','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=False,deadline='2026-10-11T11:13:13Z')
 sr=write('operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
 record=dict(status='PASS_FIVE_EXACT_PREDECESSORS_RECONCILED_NOT_GRAPH_ADOPTED',at=now,review=review,terminal_reconciliation=reconciliation,gpu_authorized=False)
 for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d['n36_five_predecessor_owner_reconciliation']=record;d['latest_operational_summary']=sr;d['next_action']=next_step;d['updated_at']=now; tmp=p.with_name(p.name+'.001879.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
 for k,v in contract['root_observed_ledger_prefixes'].items():assert ref(v['path'])==v
print(json.dumps(dict(summary=sr,terminal_reconciliation=reconciliation,retained_gpu_seconds=str(total),terminal_handle_count=len(handles))))
