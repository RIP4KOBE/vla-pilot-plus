from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,time,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001643'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
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
prior=read(A/'turns/001642/operational-summary-v1.json'); amendment=A/'turns/001616/prospective-recovery-amendment-v1.json'; am=read(amendment)
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat(am['deadline'].replace('Z','+00:00'))
plan=read(A/'turns/001608/engineering-plan.frozen-v2.json'); assert not any(Path(p).exists() for p in plan['stop_authority']['paths'])
ds=read(A/'driver-status.json');assert ds['turn']==1643
assert all(live(ds[k]) for k in ['driver','process'])
assert read(A/'turns/001642/receipt.json')['exit']==0
assert not prior['live_handles']
s=yaml.safe_load((W/'research-state.yaml').read_text()); assert not s['current_owned_workers'];assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
old=s.get('active_executor') or {}; assert not any(live(old[k]) for k in ['wrapper','executor'] if k in old)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
base='bd5dd4dabcb5a1f7823a9e2f51c849cd67767cb6'; E=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip()==base
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=E,text=True).strip()
O=T/'affected-binding-refresh';O.mkdir()
a={'schema':'n36-engineering-r1-affected-binding-refresh-authority-v1','at':now.isoformat(),'node_id':'15.6','source_base':base,'worktree':str(E),'amendment':ref(amendment),'standing_authority':ref(A/'user-authorization-v1.json'),'ledger_prefixes':prior['ledger_prefixes'],'timeout_seconds':1200,'gpu_authorized':False,'release_enabled':False,'deadline':am['deadline'],'scope':'CPU-only minimum affected disabled binding refresh for independently accepted bd5dd4d. New artifacts only; no source edits or placement, owner adoption, GPU, readiness claims or release.'}; ar=put(O/'authority-v1.json',a)
prompt=f"""You are the bounded CPU binding-preparation executor for ongoing explicitly authorized Arbor node15.6. Work at {E}, source {base}. Write new artifacts only under {O}. No recursive delegation. Bound1200 seconds. Read authority-v1.json here, accepted independent review {A/'turns/001640/independent-source-review/review-v1.json'} (minimum_affected_binding_refresh), root reconciliation {A/'turns/001642/terminal-reconciliation-v1.json'}, and {A/'turns/001635/canonical-runtime-repair/report-v1.json'} plus binding-verification-v1.json. Verify immediate input hashes. Read prior {A/'turns/001632/runtime-binding-refresh/refresh-disabled-v1.py'} and report only for necessary reuse; avoid broad provenance recursion.
Perform the minimum affected disabled graph refresh the review specifies. Reuse exact prepared specification, bd5dd4d inventory and derived runtime in turn001635 after hash verification; do not regenerate just for timestamps. Refresh scope/accounting references without changing values, scientific-equivalence evidence and deployment validation for exact reviewed variant source. Refresh runtime closure and controller semantics PROPOSAL/reference chain, full40-row disabled audit view and all40 helper-certified manifests, distinct R1 task0 C0 engineering manifest, disabled R1 plan/bindings and affected validator evidence. Preserve rows/settings, identity, scientific protocol and accounting. Use existing helpers unmodified; do not forge root/independent acceptance or readiness. Keep owner deployment/location adoption pending where applicable. Reuse unchanged evidence if exact and valid. If validators require independent/root review or readiness, record honest blocked outputs; prepare all independently possible work and explain the smallest next action. Disabled template is not readiness evidence. Do not change policy to admit readiness; that needs separate prospective reviewed amendment.
No source edits/commits/placement, GPU/model/provider calls, installs, owner/peer state/checkpoint/tree/ledger writes, driver launches, enabled releases, protected validation/formal access, credential reads, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md or Superpowers. Official current-login Codex gpt-6-astra only. Preserve historical outputs including001632, all charges, failures and protected reserves. STOP paths from turn001608/engineering-plan.frozen-v2.json and deadline2026-10-11T11:13:13Z prohibit new dispatch. Remain CPU-only and do not launch any evaluator. No broad test repeats; run affected validators on exact graph.
Write report-v1.json with source hash, exact inputs/outputs and hashes, validator outcomes, retained ledger prefixes, remaining review/readiness/adoption gates, next bounded action, gpu_authorized:false, release_enabled:false, goal_complete:false, scientific_success:false. Distinguish prepared bindings from final production acceptance. Provide concise final summary.
"""
(O/'prompt.txt').write_text(prompt)
wrapper=(A/'turns/001556/independent-b5/run-executor.py').read_text();oldw="W=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')";assert oldw in wrapper;wrapper=wrapper.replace(oldw,'W=Path('+repr(str(E))+')');(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('xb') as log:p=subprocess.Popen(['/usr/bin/python3',str((O/'run-executor.py').resolve())],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',{'pid':p.pid,'authority':ar,'at':now.isoformat()})
for _ in range(50):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=read(O/'process-v1.json');record={'status':'AFFECTED_DISABLED_BINDING_REFRESH_RUNNING','source':base,'worktree':str(E),'authority':ar,'output_directory':str(O),'process_record_path':str(O/'process-v1.json'),'exit_path':str(O/'exit-v1.json'),'wrapper':h['wrapper'],'executor':h['executor'],'gpu_authorized':False,'source_edits_authorized':False,'release_enabled':False}
nxt='Monitor turn001643 affected-binding-refresh CPU executor by PID/boot/start identity; do not duplicate. Reconcile artifacts and validators after exit. Then resolve readiness policy through separate prospective reviewed amendment, final independent B5 and root adoption; no GPU or scientific promotion until exact release gates pass.'
summary={**prior,'status':'AFFECTED_DISABLED_BINDING_REFRESH_RUNNING','source':base,'at':now.isoformat(),'turn':1643,'driver':ident(ds['driver']['pid']),'coordinator':ident(ds['process']['pid']),'active_executor':record,'live_handles':{k:h[k] for k in ['wrapper','executor']},'completed_work':['Verified bound authority, normal previous turn, live driver/coordinator identity, absent terminal GPU handles and unchanged owning ledgers.','Verified clean isolated canonical runtime repair bd5dd4dabcb5a1f7823a9e2f51c849cd67767cb6 and prior normal terminal reconciliation.','Launched one official gpt-6-astra CPU executor for minimum affected disabled binding refresh.'],'next_bounded_step':nxt,'gpu_dispatch_this_turn':False,'controller_launched_this_turn':False,'target_met':False}
sr=put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 with (W/'data/qd-ed-state.lock').open('a') as lock2:
  fcntl.flock(lock2,fcntl.LOCK_EX)
  for path,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
   d=yaml.safe_load(path.read_text()) if isyaml else read(path);d.update(active_executor=record,n36_engineering_r1_affected_binding_refresh=record,next_action=nxt,updated_at=now.isoformat(),latest_operational_summary=sr);tmp=path.with_name(path.name+'.tmp-001643');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
  path=C/'idea_tree.json';d=read(path);d['nodes']['15.6'].update(n36_engineering_r1_affected_binding_refresh=record,result='AFFECTED_DISABLED_BINDING_REFRESH_RUNNING_NO_GPU',insight='Affected disabled bindings being refreshed on reviewed isolated R1 source; failed parent remains charged. Readiness and original-goal gates remain unmet.');tmp=path.with_name(path.name+'.tmp-001643');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
print(json.dumps({'summary':sr,'executor':record}))
