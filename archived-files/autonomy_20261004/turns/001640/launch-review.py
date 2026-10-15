from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,time,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001640'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def put(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return ref(p)
def ident(pid):
 p=Path('/proc')/str(pid)/'stat';a=p.read_text().rsplit(')',1)[1].split() if p.exists() else []
 return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(a[19]) if a else None,'state':a[0] if a else None}
def live(h):
 x=ident(h['pid']);return all(x[k]==h[k] for k in ['pid','boot_id','start_ticks']) and x['state'] not in [None,'Z']
prior=read(A/'turns/001639/operational-summary-v1.json'); amendment=A/'turns/001616/prospective-recovery-amendment-v1.json'; am=read(amendment)
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat(am['deadline'].replace('Z','+00:00'))
plan=read(A/'turns/001608/engineering-plan.frozen-v2.json'); assert not any(Path(p).exists() for p in plan['stop_authority']['paths'])
ds=read(A/'driver-status.json');assert ds['turn']==1640
assert all(live(ds[k]) for k in ['driver','process'])
assert read(A/'turns/001639/receipt.json')['exit']==0
assert not prior['live_handles']
s=yaml.safe_load((W/'research-state.yaml').read_text()); assert not s['current_owned_workers'];assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
old=s.get('active_executor') or {}; assert not any(live(old[k]) for k in ['wrapper','executor'] if k in old)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
base='bd5dd4dabcb5a1f7823a9e2f51c849cd67767cb6'; E=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip()==base
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=E,text=True).strip()
O=T/'independent-source-review';O.mkdir()
a={'schema':'n36-engineering-r1-independent-review-authority-v1','at':now.isoformat(),'node_id':'15.6','source_base':base,'worktree':str(E),'amendment':ref(amendment),'standing_authority':ref(A/'user-authorization-v1.json'),'ledger_prefixes':prior['ledger_prefixes'],'timeout_seconds':1200,'gpu_authorized':False,'release_enabled':False,'deadline':am['deadline'],'scope':'Independent read-only review of canonical runtime repair f256fec..bd5dd4d and minimum affected helper refresh; no source edits, owner adoption, GPU or release.'}; ar=put(O/'authority-v1.json',a)
prompt=f"""You are an independent CPU source reviewer for the continuing explicitly authorized Arbor node15.6. Work read-only in {E} at {base}; write only review artifacts under {O}. No recursive delegation. Bound1200 seconds.
Read authority-v1.json here, then {A/'turns/001635/canonical-runtime-repair/authority-v1.json'}, report-v1.json and binding-verification-v1.json in that same directory, plus {A/'turns/001639/terminal-reconciliation-v1.json'} and {A/'turns/001630/prospective-runtime-binding-amendment-v1.json'}. Verify immediate reference hashes. Review the exact three-file git diff f256fecedbcf0d47b807aeaa196407cb24933a41..{base}. Do not rebuild old provenance or repeat broad tests.
Assess whether canonical runtime specification/source repair correctly binds the distinct prospective runtime and authority while preserving exact path/hash/source checks. Check the specification, runtime consumer routing, source closure, and unchanged release predicates. Old artifacts and exhausted identities remain immutable; retained charges, unknown telemetry, protected reserves, scientific thresholds, STOP/deadline, task0 C0 mapping, and audit matrix must remain intact. Evaluate the reported257 CPU tests; run only narrowly targeted additional tests if a concrete uncertainty requires one. Identify the minimum affected helper regeneration; do not perform that regeneration. PASS is scoped source acceptance, not production readiness or scientific success.
No source edits/commits, source placement, GPU/model/provider calls, installation, owner/peer state/checkpoint/tree/ledger writes, releases/adoptions, protected validation/formal result access, credential reads, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, or Superpowers. Official current-login Codex gpt-6-astra only. Preserve all historical outputs and charges. Observe STOP paths in turn001608/engineering-plan.frozen-v2.json and deadline2026-10-11T11:13:13Z.
Write review-v1.json with PASS/FAIL verdict, exact base/source hashes, checked evidence references, concrete findings and file/line severity, required fixes, minimum affected binding refresh, unchanged ledger hashes, release_enabled:false, target_met:false, scientific_success:false. Independent final B5, root adoption, readiness and release gates remain mandatory. Give concise final summary.
"""
(O/'prompt.txt').write_text(prompt)
wrapper=(A/'turns/001556/independent-b5/run-executor.py').read_text();oldw="W=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')";assert oldw in wrapper;wrapper=wrapper.replace(oldw,'W=Path('+repr(str(E))+')');(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('xb') as log:p=subprocess.Popen(['/usr/bin/python3',str((O/'run-executor.py').resolve())],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',{'pid':p.pid,'authority':ar,'at':now.isoformat()})
for _ in range(50):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=read(O/'process-v1.json');record={'status':'INDEPENDENT_CANONICAL_RUNTIME_REVIEW_RUNNING','source':base,'worktree':str(E),'authority':ar,'output_directory':str(O),'process_record_path':str(O/'process-v1.json'),'exit_path':str(O/'exit-v1.json'),'wrapper':h['wrapper'],'executor':h['executor'],'gpu_authorized':False,'source_edits_authorized':False,'release_enabled':False}
nxt='Monitor turn001640 independent-source-review official CPU reviewer by PID/boot/start identity; do not duplicate or launch GPU. Reconcile review verdict after exit; if PASS refresh only affected bindings before independent B5 and root source/accounting adoption/release. Preserve parent invalid charges, original scientific gates and frozen source.'
summary={**prior,'status':'INDEPENDENT_CANONICAL_RUNTIME_REVIEW_RUNNING','source':base,'at':now.isoformat(),'turn':1640,'driver':ident(ds['driver']['pid']),'coordinator':ident(ds['process']['pid']),'active_executor':record,'live_handles':{k:h[k] for k in ['wrapper','executor']},'completed_work':['Verified bound authority, normal previous turn, live driver/coordinator identity, absent terminal GPU handles and unchanged owning ledgers.','Verified clean isolated canonical runtime repair bd5dd4dabcb5a1f7823a9e2f51c849cd67767cb6 and prior normal terminal reconciliation.','Launched one official gpt-6-astra independent read-only CPU source reviewer.'],'next_bounded_step':nxt,'gpu_dispatch_this_turn':False,'controller_launched_this_turn':False,'target_met':False}
sr=put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 with (W/'data/qd-ed-state.lock').open('a') as lock2:
  fcntl.flock(lock2,fcntl.LOCK_EX)
  for path,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
   d=yaml.safe_load(path.read_text()) if isyaml else read(path);d.update(active_executor=record,n36_engineering_r1_canonical_runtime_review=record,next_action=nxt,updated_at=now.isoformat(),latest_operational_summary=sr);tmp=path.with_name(path.name+'.tmp-001640');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
  path=C/'idea_tree.json';d=read(path);d['nodes']['15.6'].update(n36_engineering_r1_canonical_runtime_review=record,result='INDEPENDENT_CANONICAL_RUNTIME_REVIEW_RUNNING_NO_GPU',insight='Independent scoped source review running on isolated R1 commit; failed parent preserved and charged. Native evidence and original-goal gates unmet.');tmp=path.with_name(path.name+'.tmp-001640');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
print(json.dumps({'summary':sr,'executor':record}))
