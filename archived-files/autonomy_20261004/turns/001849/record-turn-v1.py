import pathlib,json,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001849';prev=json.loads((base/'turns/001848/operational-summary-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat();boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def live(h):
 p=P(f"/proc/{h['pid']}/stat")
 if not p.exists():return dict(h,state='absent',alive=False,identity_verified=False)
 s=p.read_text().rsplit(')',1)[1].split();ok=int(s[19])==int(h.get('start_ticks',h.get('proc_start_ticks'))) and boot==h['boot_id'];return dict(h,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
ds=json.loads((base/'driver-status.json').read_text());handles={k:live(ds[k]) for k in ['driver','process']};handles.update({k:live(prev['live_handles'][k]) for k in ['wrapper','controller','child']})
ledgers={}
for n,r in prev['ledger_prefixes'].items():
 p=P(r['path']);b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[n]=ref(p)
r=json.loads((out/'producer-consumer-v1.json').read_text())
next_action=('CPU-only immutable measured runtime producer and exact downstream runtime consumer passed. Next compose and validate prospective engineering health release against this measured runtime, preserving source/plan scientific invariants and separate owner/accounting admission before dispatch.' if r['status']=='PASS_CPU_PRODUCER_AND_RUNTIME_CONSUMER' else 'Continue bounded diagnosis from turn001849/producer-consumer-v1.json; producer may already have written immutable runtime. Never rerun producer if runtime exists; inspect consumer traceback and preserve frozen evidence.')+' Deadline 2026-10-11T11:13:13Z; original validation/formal/required ablation remains missing.'
record=dict(status=r['status'],at=now,review=ref(out/'producer-consumer-v1.json'),runtime=r.get('runtime'),episode_authorized=False,health_authorized=False)
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,y in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if y else json.loads(p.read_text());d['n36_measured_readiness_validation']=record;d['next_action']=next_action;d['updated_at']=now
  tmp=p.with_name(p.name+'.001849.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
s=dict(prev,at=now,turn=1849,live_handles=handles,controller_status=record['status'],ledger_prefixes=ledgers,next_bounded_step=next_action,completed_work=['Verified authorization, driver identity, terminal experiment handles, STOP/deadline and private ledger prefixes.','Ran frozen CPU-only immutable readiness producer and downstream runtime consumer; exact outcome is hash-bound in review.','No measurement replay, GPU dispatch, scientific edits or promotion.'],readiness_review=record,stop_present=(base/'STOP').exists())
p=out/'operational-summary-v1.json';p.write_text(json.dumps(s,indent=2)+'\n');(out/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  operational-summary-v1.json\n');print(json.dumps(record))
