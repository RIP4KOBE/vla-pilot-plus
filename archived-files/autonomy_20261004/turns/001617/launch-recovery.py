from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,time,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001617'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
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
prior=read(A/'turns/001616/operational-summary-v1.json'); amendment=A/'turns/001616/prospective-recovery-amendment-v1.json'; am=read(amendment); assert ref(amendment)==prior['recovery_amendment']
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat(am['deadline'].replace('Z','+00:00'))
plan=read(A/'turns/001608/engineering-plan.frozen-v2.json'); assert not any(Path(p).exists() for p in plan['stop_authority']['paths'])
ds=read(A/'driver-status.json');assert ds['turn']==1617
assert all(live(ds[k]) for k in ['driver','process'])
assert read(A/'turns/001616/receipt.json')['exit']==0
assert not any(live(h) for h in prior['terminal_handles'].values())
s=yaml.safe_load((W/'research-state.yaml').read_text()); assert not s['current_owned_workers'];assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
old=s.get('active_executor') or {}; assert not any(live(old[k]) for k in ['wrapper','executor'] if k in old)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
base=am['source_base']; V=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617');V.mkdir();E=V/'implementation_worktree'
subprocess.run(['git','worktree','add','-b','exp/n36-engineering-r1-001617',str(E),base],check=True,capture_output=True,text=True)
O=T/'recovery-implementation';O.mkdir()
a={'schema':'n36-engineering-r1-cpu-executor-authority-v1','at':now.isoformat(),'node_id':'15.6','source_base':base,'worktree':str(E),'amendment':ref(amendment),'standing_authority':ref(A/'user-authorization-v1.json'),'ledger_prefixes':prior['ledger_prefixes'],'timeout_seconds':1200,'gpu_authorized':False,'release_enabled':False,'deadline':am['deadline'],'scope':'Implement exact prospective engineering R1 identity and terminal-prefix admission, focused CPU tests and scoped commit. No owner adoption or graph release.'}; ar=put(O/'authority-v1.json',a)
prompt=f'''You are the single CPU implementation executor for the continuing explicitly authorized Arbor node15.6. Work only in isolated {E} starting {base}, output artifacts in {O}. Read authority {O/'authority-v1.json'} and hash-bound amendment {amendment}, exact parent terminal and canonical-reference diagnosis in turn001615, targeted diagnosis in turn001616. Follow AGENTS. Do not recursively delegate. No GPU/model/provider episode, dependency installations, owner state/checkpoint/tree/journal writes, protected validation/formal results, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, credentials, or Superpowers. Official current-login Codex gpt-6-astra only. Observe STOP and deadline; bounded1200 seconds.
Implement the prospective recovery adapter/source/spec changes required by amendment, not a new scientific method. Preserve parent artifacts/source and native audit/scientific thresholds. Source scripts/qd_ed_n36_engineering.py pins exact identity/spec and reconcile selects broad old engineering events. Fresh R1 identity must be admissible only with exact hash-bound terminal parent prefix, known prior terminal outcomes retained charged; unknown/tampered/live/foreign prefixes or suffixes fail closed. Old exhausted identity must remain exhausted and cannot replay. New recovery one-use task0 C0 row maps to exactly unchanged original science. Canonical runtime reference must pass real DINO consumer while lexical alias remains rejected, using synthetic CPU fixtures as needed; runtime file bytes stay unchanged. No weakened path verifier, source closure, audit predicates, detached releases, resource isolation, protected reserves, one-worker limit, deadline or invalidity stop. Separate parent identity support safely from recovery using prospective amendment; do not merely rename constants while losing parent exhaustion checks.
Read focused code and existing tests; avoid broad provenance reconstruction. Add meaningful focused CPU tests for each amendment requirement, run affected tests, commit scoped changes. Create a separate operational recovery specification if exact source pins require it; do not overwrite frozen parent files. Keep any new plan/release artifacts disabled. Do not refresh entire artifact graph or grant release: report exact affected bindings for root follow-up. Do not claim scientific success from engineering.
Write report-v1.json with start/final commit, changed files, test commands/results and evidence references/hashes, identity/history/canonical-consumer negative coverage, unresolved blockers, smallest required binding refresh, score:null, scientific_success:false,target_met:false,release_enabled:false, unchanged owning ledger hashes. If incomplete, retain fail-closed execution and report useful precise remaining work. Coordinator owns source adoption and independent review/release.
'''
(O/'prompt.txt').write_text(prompt)
wrapper=(A/'turns/001556/independent-b5/run-executor.py').read_text();oldw="W=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')";assert oldw in wrapper;wrapper=wrapper.replace(oldw,'W=Path('+repr(str(E))+')');(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('xb') as log:p=subprocess.Popen(['/usr/bin/python3',str((O/'run-executor.py').resolve())],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',{'pid':p.pid,'authority':ar,'at':now.isoformat()})
for _ in range(50):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=read(O/'process-v1.json');record={'status':'CPU_RECOVERY_IMPLEMENTATION_RUNNING','source':base,'worktree':str(E),'authority':ar,'output_directory':str(O),'process_record_path':str(O/'process-v1.json'),'exit_path':str(O/'exit-v1.json'),'wrapper':h['wrapper'],'executor':h['executor'],'gpu_authorized':False,'source_edits_authorized':True,'release_enabled':False}
nxt='Monitor turn001617 recovery-implementation official CPU executor by boot/start identity; do not duplicate or launch GPU. After exit reconcile exact side effects, scoped commit and focused tests, then independent source review and minimal affected binding refresh before root recovery adoption/release. Parent invalid attempt remains charged. Original validation/formal/ablations remain incomplete.'
summary={**prior,'at':now.isoformat(),'turn':1617,'driver':ident(ds['driver']['pid']),'coordinator':ident(ds['process']['pid']),'active_executor':record,'live_handles':{k:h[k] for k in ['wrapper','executor']},'completed_work':['Verified bound authority, normal previous turn, live driver/coordinator identity, absent terminal GPU handles and unchanged owning ledgers.','Created isolated recovery branch from b8d6b98164f24a599a9aa1fa6ce862b12cb2fcf6.','Launched one official gpt-6-astra CPU-only executor for exact prospective R1 repair and focused tests.'],'next_bounded_step':nxt,'gpu_dispatch_this_turn':False,'controller_launched_this_turn':False,'target_met':False}
sr=put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 with (W/'data/qd-ed-state.lock').open('a') as lock2:
  fcntl.flock(lock2,fcntl.LOCK_EX)
  for path,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
   d=yaml.safe_load(path.read_text()) if isyaml else read(path);d.update(active_executor=record,n36_engineering_r1_implementation=record,next_action=nxt,updated_at=now.isoformat(),latest_operational_summary=sr);tmp=path.with_name(path.name+'.tmp-001617');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
  path=C/'idea_tree.json';d=read(path);d['nodes']['15.6'].update(n36_engineering_r1_implementation=record,result='CPU_ENGINEERING_R1_IMPLEMENTATION_RUNNING_NO_GPU',insight='One isolated executor implementing prospective exact recovery identity and terminal-prefix admission; failed parent preserved and charged. Native evidence and original-goal gates unmet.');tmp=path.with_name(path.name+'.tmp-001617');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
print(json.dumps({'summary':sr,'executor':record}))
