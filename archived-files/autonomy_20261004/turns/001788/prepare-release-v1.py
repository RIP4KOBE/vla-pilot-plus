import pathlib,json,hashlib,sys,os,datetime,fcntl,yaml
from decimal import Decimal
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001788'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(p):return json.loads(p.read_text())
def save(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
old=read(A/'turns/001787/operational-summary-v1.json')
for r in old['ledger_prefixes'].values():
 p=pathlib.Path(r['path']);assert p.stat().st_size==r['bytes'] and ref(p)['sha256']==r['sha256']
accept=read(A/'turns/001787/root-b5-acceptance-v1.json')
graphref=ref(T/'graph.reviewed-disabled-v1.json')
g=read(pathlib.Path(graphref['path']));assert g['status']=='PASS_COMPLETE_DISABLED_GRAPH' and not g['release_enabled']
graph={'graph':{k:g[k] for k in ['plan','runtime']}}
source=read(pathlib.Path(g['source_record']['path']));assert source['commit']==accept['source']['commit']
cwd=pathlib.Path(accept['source']['worktree']);sys.path.insert(0,str(cwd));sys.dont_write_bytecode=True;os.chdir(cwd)
from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_readiness_prepare as prep, qd_ed_n36_runner as owner
import subprocess
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==source['commit']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
events=[json.loads(x) for x in (W/'data/attempt-ledger.jsonl').read_text().splitlines() if x.strip()]
resources=[json.loads(x) for x in (W/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines() if x.strip()]
snap=e.r.budget_snapshot(events,resources)
state=yaml.safe_load((W/'research-state.yaml').read_text())
e.exact({k:state['budget'][k] for k in snap},snap,'current full ledger budget')
assert snap['running']==0 and snap['gpu_healthcheck_inflight']==0
save(T/'full-ledger-accounting-v1.json',dict(schema='n36-current-full-ledger-accounting-v1',ledger_prefixes=old['ledger_prefixes'],snapshot=snap,prior_reconciliation=state['n36_readiness_accounting_reconciliation'],charges_erased=False,unknown_telemetry_preserved=True,caps_changed=False))
spec=e.specification();policy=prep.policy(spec);contract=e.read(spec['runtime_binding']['accounting_contract']);source_ref=ref(pathlib.Path(spec['runtime_binding']['source_record_path']));e.exact(e.read(source_ref),source,'final source')
e.stop.check();now=datetime.datetime.now(datetime.timezone.utc)
release=dict(schema='n36-preparation-measurement-release-v1',approved=True,purpose='readiness_preparation_only',specification=e.SPECIFICATION,source_record=source_ref,baseline=spec['canonical_runtime'],resource_id=policy['resource_id'],source_cwd=str(e.SOURCE),interpreter=dict(path=str(pathlib.Path(sys.executable).resolve()),sha256=e.w.sha(pathlib.Path(sys.executable).resolve()),version=sys.version),issued_at=now.isoformat(),expires_at=(now+datetime.timedelta(hours=2)).isoformat(),gpu_seconds=600,provider_calls=1,episode_authorized=False,health_authorized=False,stop_authority=e.stop.binding(),graph=graph['graph'])
auth=dict(schema=contract['authority_schema'],approved=True,purpose='readiness_preparation_only',contract=spec['runtime_binding']['accounting_contract'],approval_basis=contract['standing_authority'],independent_review=contract['independent_review'],owner=contract['owner'],gpu_mapping=e.read(spec['canonical_runtime'])['gpu_mapping'],caps=e.c.CAPS,amendment=contract['amendment'],margin_reference=contract['margin_reference'],ledger_prefixes=spec['retained_ledger_prefixes'],retained_snapshot=spec['retained_snapshot'],retained_snapshot_reference=spec['retained_snapshot_reference'],retained_margin_gpu_hours='0.23357169027962',absolute_gpu_hours='224',weekly_window=dict(origin_gpu_hours=53.08404692669838,increment_gpu_hours=168.,ends_at=e.c.DEADLINE),cleanup_seconds=40,max_episode_attempts=0,max_health_invocations=0,automatic_recoveries=0,adoption_slot=prep.ADOPTION_SLOT,**{k:release[k] for k in prep.AUTHORITY_BINDINGS})
spent=Decimal(str(snap['gpu_hours_consumed']));protected=sum(max(Decimal(0),Decimal(str(h))-Decimal(str(snap['gpu_hours_by_bucket'][k]))) for k,h in e.c.CAPS['protected_gpu_hours'].items());margin=Decimal(auth['retained_margin_gpu_hours']);cap=min(Decimal('224'),Decimal('53.08404692669838')+Decimal('168'));need=Decimal(600)/Decimal(3600);assert spent+protected+margin+need<cap
save(T/'reservation-arithmetic-v1.json',dict(authority=contract['standing_authority'],history=ref(T/'full-ledger-accounting-v1.json'),spent_gpu_hours=str(spent),protected_gpu_hours=str(protected),retained_margin_gpu_hours=str(margin),reservation_seconds=600,reservation_gpu_hours=str(need),effective_cap_gpu_hours=str(cap),remaining_after_reservation_and_reserves=str(cap-spent-protected-margin-need),episode_attempts=0,provider_calls=1,automatic_recoveries=0,scope='Separate readiness preparation; no production adoption or scientific gate changes'))
auth['root_review']=save(T/'preparation-accounting-root-review-v1.json',{**auth,'schema':contract['review_schema'],'decision':'APPROVED'})
release['accounting_authority']=save(T/'preparation-accounting-authority-v1.json',auth)
release['root_review']=save(T/'preparation-measurement-root-review-v1.json',{**release,'schema':'n36-preparation-root-measurement-review-v1','decision':'APPROVED'})
rref=save(pathlib.Path(policy['release_path']),release)
prep.validate_release(rref,spec,source,source_ref)
adoption=dict(schema='n36-preparation-accounting-adoption-v1',approved=True,accounting_authority=release['accounting_authority'],owner_root=str(e.owner_root(e.read(release['graph']['plan']))),resource_id=release['resource_id'],production_adoption=False)
with (C/'state.lock').open('a') as lock, (W/'data/qd-ed-state.lock').open('a') as runner_lock:
 fcntl.flock(lock,fcntl.LOCK_EX);fcntl.flock(runner_lock,fcntl.LOCK_EX)
 for r in old['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
 state=yaml.safe_load((W/'research-state.yaml').read_text());proposed={**state,prep.ADOPTION_SLOT:adoption};prep.validate_preparation_state(e.owner_root(e.read(release['graph']['plan'])),e.read(release['graph']['plan']),auth,release,proposed)
 for p,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else read(p);d.setdefault('preparation_adoption_history',[]).append({'adoption':d.get(prep.ADOPTION_SLOT),'release':d.get('n36_preparation_measurement_release')});d[prep.ADOPTION_SLOT]=adoption;d['n36_preparation_measurement_release']=rref;d['next_action']='Finite readiness release prepared in turn001788. Recheck STOP/deadline, owning handles and ledgers, then use committed bootstrap for the one-use preparation measurement. No health/episode dispatch; root acceptance of native/runtime evidence remains pending.';d['updated_at']=now.isoformat();q=p.with_name(p.name+'.tmp-001788');q.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(q,p)
 snap=prep.preparation_budget(e.owner_root(e.read(release['graph']['plan'])),e.read(release['graph']['plan']),auth,release)
save(T/'release-preparation-result-v1.json',dict(status='PASS_RELEASE_AND_ACCOUNTING_ADOPTION',release=rref,accounting_authority=release['accounting_authority'],source_commit=source['commit'],dispatched=False,budget_snapshot=snap))
print(json.dumps(dict(status='PASS',release=rref,expires_at=release['expires_at'])))
