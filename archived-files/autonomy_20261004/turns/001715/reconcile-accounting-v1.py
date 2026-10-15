import pathlib,json,sys,os,fcntl,yaml,hashlib,datetime
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001715';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator';sys.path.insert(0,'/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree');sys.dont_write_bytecode=True
from scripts import qd_ed_n36_runner as owner,qd_ed_n36_engineering_r1 as e,qd_ed_n36_readiness_prepare as prep
read=lambda p:json.loads(p.read_text())
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def put(p,d):
 q=p.with_name(p.name+'.tmp-001715');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
auth=read(T/'preparation-accounting-authority-v1.json');releasepath=pathlib.Path(prep.policy(e.specification())['release_path']);release=read(releasepath);plan=e.read(release['graph']['plan']);old=read(A/'turns/001714/operational-summary-v1.json')
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in old['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
 state,events,resources,reservations=owner.snapshot(W,auth);snap=e.r.budget_snapshot(events,resources);diff={k:dict(before=state['budget'].get(k),after=v) for k,v in snap.items() if state['budget'].get(k)!=v};assert all(v['before'] is None for v in diff.values())
 put(T/'derived-accounting-reconciliation-v1.json',dict(schema='derived-accounting-reconciliation-v1',ledger_prefixes=old['ledger_prefixes'],changes=diff,charges_erased=False,caps_changed=False,dispatch=False))
 for p,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else read(p)
  if isyaml:d['budget'].update(snap)
  d['budget_snapshot']=snap;d['n36_preparation_accounting_reconciliation']=ref(T/'derived-accounting-reconciliation-v1.json');q=p.with_name(p.name+'.tmp-001715');q.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(q,p)
 prep.preparation_budget(W,plan,auth,release)
put(T/'release-preparation-result-v1.json',dict(status='PASS_RELEASE_AND_ACCOUNTING_ADMISSION',release=ref(releasepath),dispatched=False,source_commit=plan['source']['commit'],reservation_seconds=600))
nextstep='Turn001715 finite readiness release and preparation accounting admission passed after ledger-derived missing-field reconciliation. Before '+release['expires_at']+', recheck STOP/deadline, handles and prefixes, then dispatch the one-use readiness measurement via reviewed committed bootstrap. Record process identities before monitoring; do not regenerate release or replay identity. Native/runtime evidence and independent root acceptance, production B5/adoption, fresh health/episode releases remain pending.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else read(p);d['next_action']=nextstep;d['n36_preparation_release_validation']=ref(T/'release-preparation-result-v1.json');q=p.with_name(p.name+'.tmp-001715');q.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(q,p)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='FINITE_READINESS_RELEASE_ADMISSION_PASS_NOT_DISPATCHED',insight=nextstep);put(C/'idea_tree.json',tree)
old.update(turn=1715,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),driver_status=read(A/'driver-status.json'),completed_work=['Verified authority hashes, PID/boot/start identities and unchanged owning ledger prefixes; prior turn completed normally.','Prepared separately scoped 600-second, one-provider-call readiness release and detached accounting/root reviews.','Documented exact reservation arithmetic preserving 36.240824002430815 protected GPU-hours and retained margin.','Reconciled five missing derived budget fields from unchanged owning ledgers; unchanged preparation accounting admission now passes.'],next_bounded_step=nextstep,readiness_release=ref(releasepath),release_preparation=ref(T/'release-preparation-result-v1.json'),live_executor_handles={},current_owned_workers=[],gpu_authorized=False,target_met=False)
put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps(dict(status='PASS',summary=str(T/'operational-summary-v1.json'))))
