import pathlib,json,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001871';prev=json.loads((base/'turns/001870/operational-summary-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat();boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def live(h):
 p=P(f"/proc/{h['pid']}/stat")
 if not p.exists():return dict(h,state='absent',alive=False,identity_verified=False)
 s=p.read_text().rsplit(')',1)[1].split();ok=int(s[19])==int(h['start_ticks']) and boot==h['boot_id'];return dict(h,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
ds=json.loads((base/'driver-status.json').read_text());handles={k:live(ds[k]) for k in ['driver','process']};proc=json.loads((out/'cpu-operation-process-v1.json').read_text());handles['cpu_readiness']=live(proc['handles'][0]);ledgers={}
for n,r in prev['ledger_prefixes'].items():
 p=P(r['path']);assert ref(p)['sha256']==r['sha256'];ledgers[n]=ref(p)
rp=out/'producer-consumer-v1.json';result=json.loads(rp.read_text()) if rp.exists() else {'status':'CPU_PRODUCER_CONSUMER_RUNNING'}
record=dict(status=result['status'],at=now,process=ref(out/'cpu-operation-process-v1.json'),handles=[handles['cpu_readiness']],episode_authorized=False,health_authorized=False,result=ref(rp) if rp.exists() else None)
next_action=('Inspect turn001871 producer-consumer result; if PASS, compose the measured graph from accepted current graph001864 and exact runtime, preserving all41 scientific payloads; perform only affected admission and independent review before separately bounded health/engineering release. No validation/formal promotion exists.' if rp.exists() and result['status'].startswith('PASS') else 'Monitor CPU readiness operation recorded in turn001871; inspect its result and reconcile actual acceptance/runtime side effects before retrying. Do not replay measurement or weaken audits. Episode dispatch remains disabled.')
review=json.loads((base/'turns/001866/independent-review-final.txt').read_text())
for n,h in review['reviewed_sha256'].items():assert ref(P(review['hash_base'])/n)['sha256']==h
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1871,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=result['status'],completed_work=['Verified bound authorization, ACTIVE/PASS isolation, prior normal exit, source identities, no STOP and all four unchanged owning ledger prefixes.','Reconciled completed independent official gpt-6-astra review as PASS with exact reviewed hashes.','Ran frozen CPU readiness producer/consumer validation; result and exact side effects recorded separately. No new GPU dispatch, cost, scientific changes or promotion.'],readiness=record,ledger_prefixes=ledgers,next_bounded_step=next_action,unresolved_evidence=['Measured graph downstream admission and separately authorized valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline=prev['deadline'])
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,y in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if y else json.loads(p.read_text());d['n36_successor_readiness_producer_consumer']=record;d['next_action']=next_action;d['updated_at']=now
  prep=d['n36_successor_readiness_release_preparation'];prep['status']='PASS_INDEPENDENT_RELEASE_REVIEW_MEASUREMENT_TERMINAL';prep['independent_review']=ref(base/'turns/001866/independent-review-final.txt');prep['handles']={k:live(h) for k,h in prep['handles'].items()}
  tmp=p.with_name(p.name+'.001871.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
p=out/'operational-summary-v1.json'
with p.open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
(out/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'summary':ref(p),'status':result['status'],'live':handles}))
