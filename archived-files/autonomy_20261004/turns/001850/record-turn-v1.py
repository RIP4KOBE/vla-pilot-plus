import pathlib,json,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001850';prev=json.loads((base/'turns/001849/operational-summary-v1.json').read_text());entry=json.loads((out/'entry-reconciliation-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat();boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def live(h):
 p=P(f"/proc/{h['pid']}/stat")
 if not p.exists():return dict(h,state='absent',alive=False,identity_verified=False)
 s=p.read_text().rsplit(')',1)[1].split();ok=int(s[19])==int(h.get('start_ticks',h.get('proc_start_ticks'))) and boot==h['boot_id'];return dict(h,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
handles={k:live(v) for k,v in entry['live_handles'].items()};cpu=[live(h) for h in json.loads((out/'cpu-operation-process-v1.json').read_text())['handles']];assert not any(h['alive'] for h in cpu)
for r in prev['ledger_prefixes'].values():assert ref(P(r['path']))['sha256']==r['sha256']
r=json.loads((out/'measured-graph-v2/audit-result-v1.json').read_text())
next_action='Run bounded CPU full production audit closure and separate engineering manifest verification on turn001850/measured-graph-v2/graph.measured-disabled-v1.json using the same interpreter and -B -X pycache_prefix=/dev/null. V1 omission caused generated-origin mismatch, now exact retained-receipt check passes. All41 scientific manifest payloads preserved by structured ref replacement, but full audit closure remains unverified; use production validators without weakening. Only after full PASS obtain exact independent B5 and root protocol/source/accounting adoption, then separate health release/admission. No measurement replay. Deadline 2026-10-11T11:13:13Z; original validation/formal/required ablation missing.'

record=dict(status=r['status'],at=now,review=ref(out/'measured-graph-v2/audit-result-v1.json'),graph=r['graph'],source=prev['current_source'],gpu_authorized=False,independent_review_claimed=False)
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,y in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if y else json.loads(p.read_text());d['n36_measured_graph_admission']=record;d['next_action']=next_action;d['updated_at']=now
  tmp=p.with_name(p.name+'.001850.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
s=dict(schema='autonomy-operational-summary-v1',at=now,turn=1850,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,cpu_operation_handles=cpu,controller_status=r['status'],ledger_prefixes=prev['ledger_prefixes'],next_bounded_step=next_action,completed_work=['Verified bound handoff, exact authority, normal prior completion, live driver identities, absent old GPU handles, resource isolation and four private ledger hashes.','Composed new disabled measured runtime bindings and preserved all41 scientific manifest payloads; no source/threshold changes.','Preserved CPU v1 launch failure; corrected original pycache prefix and passed exact retained runtime receipt validation. Full audit closure still pending. No GPU dispatch or measurement replay.'],readiness_review=prev['readiness_review'],measured_graph_review=record,unresolved_evidence=['Full production audit closure on measured graph','Independent B5 and exact root source/accounting/release admission','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline='2026-10-11T11:13:13Z',ledgers_unchanged=True)
p=out/'operational-summary-v1.json';p.write_text(json.dumps(s,indent=2)+'\n');(out/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  operational-summary-v1.json\n');print(json.dumps(record))
