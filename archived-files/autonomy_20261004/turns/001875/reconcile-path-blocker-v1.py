import pathlib,json,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path; root=P.cwd(); base=(root/'../autonomy_20261004').resolve(); out=base/'turns/001875'; prev=json.loads((base/'turns/001874/operational-summary-v1.json').read_text()); now=datetime.datetime.now(datetime.timezone.utc).isoformat(); boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def ref(p):
 p=P(p);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
def live(h):
 p=P(f"/proc/{h['pid']}/stat")
 if not p.exists():return dict(h,alive=False,state='absent',identity_verified=False)
 t=p.read_text().rsplit(')',1)[1].split();ok=boot==h['boot_id'] and int(t[19])==int(h.get('start_ticks',h.get('proc_start_ticks',-1)))
 return dict(h,state=t[0],alive=ok and t[0]!='Z',identity_verified=ok)
ds=json.loads((base/'driver-status.json').read_text());assert ds['turn']==1875
handles={k:live(ds[k]) for k in ['driver','process']};assert all(x['alive'] for x in handles.values());handles['prior_cpu']=[live(h) for h in prev['live_handles']['cpu']];assert not any(h['alive'] for h in handles['prior_cpu'])
ledgers={}
for n,r in prev['ledger_prefixes'].items():
 assert ref(r['path'])['sha256']==r['sha256'] and P(r['path']).stat().st_size==r['bytes'];ledgers[n]=r
resultp=base/'turns/001874/producer-consumer-v1.json';result=json.loads(resultp.read_text());assert result['status']=='BLOCKED_PRODUCER_OR_CONSUMER';assert result['error']=='ValueError: N36 preparation reference path differs'
exitp=base/'turns/001874/cpu-exit-v1.json';assert json.loads(exitp.read_text())['returncode']==0
releasep=base/'turns/001859/successor-disabled-composition/pending-release.json';release=json.loads(releasep.read_text());planref=release['graph']['plan'];pp=P(planref['path']);assert ref(pp)['sha256']==planref['sha256'];assert str(pp.resolve())!=str(pp)
checks=[]
for name,r in [('release',ref(releasep)),('source_record',release['source_record']),('graph.plan',planref),('graph.runtime',release['graph']['runtime']),('specification',release['specification'])]:
 p=P(r['path']);checks.append(dict(field=name,reference=r,resolved_path=str(p.resolve()),canonical=str(p.resolve())==str(p) and not p.is_symlink(),bytes_match=ref(p)['sha256']==r['sha256']))
assert all(x['bytes_match'] for x in checks)
record=dict(schema='n36-readiness-path-blocker-reconciliation-v1',at=now,status='BLOCKED_FROZEN_RELEASE_NONCANONICAL_PLAN_REFERENCE',result=ref(resultp),exit=ref(exitp),release=ref(releasep),reference_checks=checks,interpretation='Process exit0 reports handled failure, not readiness PASS. The released plan reference uses a symlinked ancestor. Exact bytes match, but strict production path identity rejects it. No historical release or receipt may be rewritten.',retained_measurement_reconciliation=ref(base/'turns/001870/terminal-reconciliation-v1.json'),private_ledgers_unchanged=True,episode_authorized=False,health_authorized=False,source_modified=False,target_met=False)
rr=put(out/'path-blocker-reconciliation-v1.json',record)
next_action='Prepare a fresh disabled successor for the noncanonical released plan reference documented in turn001875/path-blocker-reconciliation-v1.json. Canonicalize prospective output paths at creation (resolve the turn directory before ref construction); preserve historical release/proof/charges and all41 scientific payloads. Use a fresh readiness resource identity and proof/acceptance/runtime destinations; verify canonical reference closure before bounded production admission and independent release review. Reconcile the completed preparation as predecessor; document finite accounting before any fresh measurement. Never patch the historical release or relax _preparation_reference. No new dispatch after 2026-10-11T11:13:13Z.'
plan=dict(schema='n36-prospective-canonical-path-recovery-plan-v1',at=now,authority=ref(base/'user-authorization-v1.json'),diagnosis=rr,adopted=False,dispatch_authorized=False,source_change_required=False,steps=[next_action],required_checks=['All externally supplied preparation pins are absolute canonical paths with exact hashes, including release.graph.plan.','All41 scientific payloads unchanged; only prospective operational paths, fresh resource identity and dependency pins rebound.','Existing source verifier accepts graph; no audit weakening.','Fresh measurement at most600 GPU seconds and one official gpt-6-astra provider call, zero automatic retries, only after exact accounting and independently reviewed release.','Readiness producer and consumer must both PASS before downstream measured-graph admission.'],historical_measurement_reusable_as_accepted_readiness=False,deadline='2026-10-11T11:13:13Z')
pr=put(out/'prospective-repair-plan-v1.json',plan)
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,y in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if y else json.loads(p.read_text()); old=d['n36_successor_readiness_producer_consumer'];d['n36_successor_readiness_producer_consumer']=dict(old,status=record['status'],at=now,handles=handles['prior_cpu'],result=ref(resultp),terminal_reconciliation=rr,prospective_repair=pr);d['next_action']=next_action;d['updated_at']=now
  temp=p.with_name(p.name+'.001875.tmp');temp.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(temp,p)
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1875,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=record['status'],completed_work=['Verified authority hashes, resource isolation, driver and prior CPU identities.','Reconciled terminal CPU failure; verified exact offending frozen plan path and retained matching bytes.','Recorded prospective path-only recovery requirements without rewriting historical evidence, dispatching or changing science.'],ledger_prefixes=ledgers,diagnosis=rr,prospective_repair=pr,next_bounded_step=next_action,unresolved_evidence=['Fresh canonical release and full readiness acceptance','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline=prev['deadline'])
sr=put(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n');print(json.dumps(dict(summary=sr,status=record['status'],checks=checks)))
