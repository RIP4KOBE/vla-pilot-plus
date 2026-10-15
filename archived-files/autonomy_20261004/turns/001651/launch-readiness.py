from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,time,yaml
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001651';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def put(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return ref(p)
def ident(pid):
 try:a=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
 except FileNotFoundError:return None
 return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(a[19]),state=a[0])
def live(h):
 x=ident(h['pid']);return x and all(x[k]==h[k] for k in ['pid','boot_id','start_ticks']) and x['state']!='Z'
prior=read(A/'turns/001650/operational-summary-v1.json');amendment=A/'turns/001650/prospective-readiness-amendment-v1.json';am=read(amendment)
assert ref(amendment)['sha256']==prior['amendment']['sha256']
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat(am['deadline'])
assert not any(Path(p).exists() for p in am['deployment']['stop_authority_to_preserve']['paths'])
ds=read(A/'driver-status.json');assert ds['turn']==1651 and all(live(ds[k]) for k in ['driver','process'])
assert read(A/'turns/001650/receipt.json')['exit']==0
s=yaml.safe_load((W/'research-state.yaml').read_text());assert not s['current_owned_workers'];assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
old=s.get('active_executor') or {};assert not any(live(old[k]) for k in ['wrapper','executor'] if k in old)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
E=Path(am['cpu_repair_worktree']);base=am['source_base']
assert subprocess.check_output(['git','-C',str(E),'rev-parse','HEAD'],text=True).strip()==base
assert not subprocess.check_output(['git','-C',str(E),'status','--porcelain','--untracked-files=no'],text=True).strip()
O=T/'readiness-implementation';O.mkdir()
a=dict(schema='n36-readiness-cpu-implementation-authority-v1',at=now.isoformat(),node_id='15.6',source_base=base,worktree=str(E),amendment=ref(amendment),standing_authority=ref(A/'user-authorization-v1.json'),ledger_prefixes=prior['ledger_prefixes'],timeout_seconds=1200,gpu_authorized=False,provider_calls_authorized=False,release_enabled=False,deadline=am['deadline'],scope='Exact prospective readiness policy and preparation-only producer; focused CPU tests and scoped commit. No owner adoption, measurement or release.')
ar=put(O/'authority-v1.json',a)
prompt=f'''You are the single CPU implementation executor for continuing explicitly authorized Arbor node 15.6. Work only in isolated {E} starting {base}; artifacts in {O}. Read authority {O/'authority-v1.json'} and hash-bound amendment {amendment}. Implement its exact bounded scope. Follow AGENTS. No recursive delegation. No GPU, model, provider measurement or episode, dependency installations, owner state/checkpoint/tree/journal writes, protected validation/formal results, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, credentials, Superpowers. Current official logged-in Codex gpt-6-astra only; no account/API fallback. Observe STOP/deadline; bounded 1200 seconds.
Implement exact evidence-derived readiness admission and preparation-only producer, pin new immutable prospective specification externally in your output directory with matching source config. Preserve old artifacts and disabled baseline. Allowed source edits only those listed in amendment (scripts/qd_ed_n36_engineering_r1.py, configs/qd_ed_final/n36_engineering_r1_spec.disabled.json, tests/test_n36_engineering_r1.py, new scripts/qd_ed_n36_readiness_prepare.py and tests/test_n36_readiness_prepare.py). Any necessary broader changes must be reported, not silently implemented. No scientific method change. Read focused existing source/tests. Do not recursively rebuild provenance or refresh 41 manifests. Preserve all audit/native/controller checks and production true-readiness gates. Bootstrap is separate, preparation-only, finite accounting and no episode authority. Implement executable producer/validator path that fails closed absent separate valid release, final-source/native closure, approved evidence and exact accounted terminal sequence. Never fabricate observed evidence; test fixtures explicitly synthetic. Do not invoke producer on hardware. Derive exact allowed changes from evidence, reject boolean-only/stale/replayed/wrong-source/provider/GPU/missing-native/unapproved/unlisted-field changes. Source ancestry, complete committed inventory, loaded module checks and acyclic immutable baseline/final-source references remain enforced. Generic GPU probe cannot be used as-is because it mutates inputs and proves no provider readiness. Health path cannot bootstrap because it already requires readiness. Preserve separate health and episode gates. Exact amendment is authoritative.
Run focused meaningful CPU tests and commit scoped source changes. Write report-v1.json with start/final commit, changed paths, test commands/results/evidence hashes, exact requirements satisfied and unresolved, smallest next binding/review steps, score:null, scientific_success:false,target_met:false,release_enabled:false, unchanged owning ledger hashes. Do not claim complete if producer or integration is partial; clearly identify residual gates. Coordinator performs independent source review, placement and separate measurement release later.
'''
(O/'prompt.txt').write_text(prompt)
(O/'run-executor.py').write_text((A/'turns/001643/affected-binding-refresh/run-executor.py').read_text())
with (O/'wrapper.log').open('xb') as log:p=subprocess.Popen(['/usr/bin/python3',str((O/'run-executor.py').resolve())],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(pid=p.pid,authority=ar,at=now.isoformat()))
for _ in range(50):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=read(O/'process-v1.json');record=dict(status='CPU_READINESS_IMPLEMENTATION_RUNNING',source=base,worktree=str(E),authority=ar,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=h['wrapper'],executor=h['executor'],gpu_authorized=False,source_edits_authorized=True,release_enabled=False)
nxt='Monitor turn001651 readiness-implementation official CPU executor by exact boot/start identity. No duplicate executor or GPU/provider measurement. On exit reconcile scoped commit, meaningful CPU tests, exact side effects and unchanged ledgers, then independent source review. Separate final-source placement, finite preparation accounting/release and measured readiness are required before final graph/B5/adoption and distinct health/episode releases. Original validation/formal/ablation evidence remains incomplete.'
summary=dict(schema='autonomy-operational-summary-v1',turn=1651,at=now.isoformat(),source=base,owning_source=s['source_commit'],deployment_source=prior['deployment_source'],driver=ident(ds['driver']['pid']),coordinator=ident(ds['process']['pid']),active_executor=record,live_handles={k:h[k] for k in ['wrapper','executor']},owned_gpu_workers=0,completed_work=['Verified exact authority/handoff hashes, normal prior exit, live driver/coordinator identities and absent prior executor handles.','Verified unchanged owning ledger prefixes, ACTIVE/PASS resource isolation and STOP/deadline.','Launched one official gpt-6-astra CPU executor for approved readiness policy/producer implementation and focused tests in existing isolated R1 variant.'],next_bounded_step=nxt,unresolved_evidence=prior['unresolved_evidence'],ledger_prefixes=prior['ledger_prefixes'],amendment=ref(amendment),stop_present=False,deadline=am['deadline'],gpu_dispatch_this_turn=False,goal_complete=False,target_met=False)
sr=put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 with (W/'data/qd-ed-state.lock').open('a') as lock2:
  fcntl.flock(lock2,fcntl.LOCK_EX)
  for path,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
   d=yaml.safe_load(path.read_text()) if isyaml else read(path);d.update(active_executor=record,n36_engineering_r1_readiness_implementation=record,next_action=nxt,updated_at=now.isoformat(),latest_operational_summary=sr);tmp=path.with_name(path.name+'.tmp-001651');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
  path=C/'idea_tree.json';d=read(path);d['nodes']['15.6'].update(n36_engineering_r1_readiness_implementation=record,result='CPU_READINESS_IMPLEMENTATION_RUNNING_NO_GPU',insight='Prospective readiness policy repair runs in isolated R1 executor; all measured preparation, native audit and scientific completion gates remain pending.');tmp=path.with_name(path.name+'.tmp-001651');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
print(json.dumps(dict(summary=sr,executor=record)))
