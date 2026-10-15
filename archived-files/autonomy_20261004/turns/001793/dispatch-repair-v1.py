from pathlib import Path
import json,hashlib,datetime,subprocess,time,os,fcntl,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001793'; O=T/'preparation-binding-repair'; O.mkdir(exist_ok=False)
C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
def read(p):return json.loads(p.read_text())
def put(p,v,y=False):
 t=p.with_name(p.name+'.1793.tmp');t.write_text(yaml.safe_dump(v,sort_keys=False,allow_unicode=True) if y else json.dumps(v,indent=2)+'\n');t.replace(p)
def ident(pid):
 s=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
D=read(A/'driver-status.json');assert D['turn']==1793
for k in ['driver','process']:
 live=ident(D[k]['pid']);assert all(live[x]==D[k][x] for x in ['pid','boot_id','start_ticks'])
P=A/'turns/001792';prior=read(P/'operational-summary-v1.json');assert read(P/'receipt.json')['exit']==0
ledgers={}
for n,r in prior['ledger_prefixes'].items():
 f=Path(r['path']);b=f.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[n]={**ref(f),'prior_prefix_preserved':True}
for pid in [3516666,3516667,3523288]:assert not Path(f'/proc/{pid}').exists()
S=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree');commit='a5b32cdefc0879e98011f86b1559e4250926ba62'
assert subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD'],text=True).strip()==commit
assert not subprocess.check_output(['git','-C',str(S),'status','--porcelain','--untracked-files=no'],text=True).strip()
stops=[A/'STOP',A.resolve()/'STOP'];assert not any(os.path.lexists(p) for p in stops);assert time.time()<1791717193
state=yaml.safe_load((W/'research-state.yaml').read_text());assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS';assert state.get('in_flight_executor') is None and not state.get('current_owned_workers')
auth=dict(schema='n36-preparation-binding-cpu-repair-authority-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),node_id='15.6',standing_authority=ref(A/'user-authorization-v1.json'),worktree=str(S),source=commit,diagnosis=ref(P/'binding-diagnosis-v1.json'),validation=ref(P/'readiness-validation-v2.json'),ledger_prefixes=ledgers,stop_authority=dict(paths=[str(p) for p in stops],deadline='2026-10-11T11:13:13Z'),maximum_executor_seconds=1200,gpu_authorized=False,provider_measurement_authorized=False,source_edits_authorized=True,owning_state_mutation=False,scope='Repair preparation-specific source binding verification with strict external trust anchors and CPU adversarial tests. No receipt rewrite, production adoption, release, GPU/provider measurement, algorithm changes or scientific promotion.',delegation_transport='Official current-login Codex CLI gpt-6-astra bounded Arbor executor')
put(O/'authority-v1.json',auth)
prompt=f'''You are a bounded Arbor engineering executor for ongoing node15.6, not coordinator. Read {O}/authority-v1.json. Work only in isolated engineering worktree {S}, starting source {commit}. Implement the narrow preparation-binding compatibility repair diagnosed at {P}/binding-diagnosis-v1.json and {P}/readiness-validation-v2.json. Producer scripts/qd_ed_n36_readiness_prepare.py preparation_after binding has release/source_record/resource_id/process; generic scripts/qd_ed_n36_source.py only allows episode context/runtime_closure/process/runtime_before-or-after. Follow call path, understand intended invariant, add explicit narrowly scoped preparation verification with external release/source/runtime/process anchors. Never weaken existing episode verification. Bind actual producer/consumer identities and full native source/import alias evidence. Adversarial CPU tests must reject missing/wrong release, source_record, resource_id, process, phase, runtime and receipt linkage; maintain episode rejection semantics. No monkeypatching production checks or rewriting retained receipts. Avoid broad repeated testing. Commit focused repair, tests and report exact source/test provenance.
Read retained proof referenced by prior operational summary as necessary, never protected validation/formal outcomes. Explicitly assess whether existing measured proof can be verified under a newly reviewed consumer without pretending it was produced by new source; if source freeze/strict bindings require fresh measurement, state that and minimal new prospective preparation needed. Do not accept proof, enable release, rebind downstream artifact graph or replay measurement yourself. Independent review and root adoption are later steps. Avoid recursive provenance rebuilds; diagnose and repair this narrow failure only.
Write {O}/report-v1.json with source before/after, changed files, focused tests, remaining blockers, retained-proof eligibility and rationale, exact next bounded step; keep command/test evidence there. All temporary data under {O.resolve()}/tmp. You may edit/commit source only in {S}. No owning or other-study state/ledger/checkpoint writes, credential reads, Poe/API-key/alternate provider use, cloud, GPU/CUDA, provider measurement, protected results, prohibited 2026-08-10-eds-qd-stage-guidance-transition-design.md, Superpowers, child agents or coordinator launches. No driver.lock/coordinator.lease. Preserve all costs/history/reserves/scientific thresholds. Bound1200 seconds, two CPU threads. Stop on STOP/deadline. Report engineering status only, never task success.'''
(O/'prompt.txt').write_text(prompt)
wrapper=(A/'turns/001766/recovery-source-repair/run-executor.py').read_text();(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('wb') as out:p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-I','-B',str(O/'run-executor.py')],cwd=S,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(wrapper=ident(p.pid),authority=ref(O/'authority-v1.json')))
for _ in range(30):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
process=read(O/'process-v1.json')
rec=dict(status='RUNNING_CPU_PREPARATION_BINDING_REPAIR',source=commit,worktree=str(S),authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=process['wrapper'],executor=process['executor'],gpu_authorized=False,source_edits_authorized=True,measurement_authorized=False)
nextstep='Monitor turn001793 preparation-binding-repair official CLI executor by boot/start identity; do not duplicate. Reconcile committed changes/tests and retained-proof eligibility on exit, then independent scoped review before adoption. Preserve rejected measured proof; no health/episode release yet.'
summary=dict(schema='autonomy-operational-summary-v1',turn=1793,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),current_source=prior['current_source'],repair_source=dict(worktree=str(S),commit_before=commit),owning_source=prior['owning_source'],scientific_source=prior['scientific_source'],live_handles=dict(driver=ident(D['driver']['pid']),coordinator=ident(D['process']['pid']),repair_wrapper=process['wrapper'],repair_executor=process['executor']),controller_status='NO_LIVE_GPU_COHORT; CPU preparation binding repair running',ledger_prefixes=ledgers,completed_work=['Verified bound handoff/authority, active driver and coordinator boot/start identity, terminal preparation handles, prior successful turn, exact preserved private ledgers and ACTIVE/PASS resource isolation.','Reviewed preparation producer/consumer mismatch and launched bounded CPU repair through official current-login gpt-6-astra in isolated engineering worktree.'],next_bounded_step=nextstep,unresolved_evidence=['Preparation binding repair, adversarial tests and independent review pending; retained-proof eligibility unresolved.','Native runtime admission, original validation/formal/required ablation goal remain unproven.'],deadline_utc=prior['deadline_utc'],stop_present=False,deadline_passed=False,gpu_dispatches=0,target_met=False,executor=rec,measurement=prior['measurement'])
put(T/'operational-summary-v1.json',summary);sr=ref(T/'operational-summary-v1.json');(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 for sp in [W/'research-state.yaml',C/'checkpoint.json']:
  y=sp.suffix=='.yaml';d=yaml.safe_load(sp.read_text()) if y else read(sp);assert d.get('in_flight_executor') is None
  d.update(in_flight_executor=rec,n36_preparation_binding_repair=rec,latest_operational_summary=sr,next_action=nextstep,updated_at=summary['at']);put(sp,d,y)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result=rec['status'],insight=nextstep,preparation_binding_repair=rec);put(C/'idea_tree.json',tree)
print(json.dumps(dict(summary=sr,executor=rec),indent=2))
