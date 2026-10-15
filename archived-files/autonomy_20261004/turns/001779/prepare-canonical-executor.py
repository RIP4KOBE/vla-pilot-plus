from pathlib import Path
import json,hashlib,datetime,subprocess,time,os,fcntl,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001779'; O=T/'canonical-path-rebinding'; O.mkdir(exist_ok=False)
def ref(p):
 b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
def put(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def ident(pid):
 s=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
D=json.loads((A/'driver-status.json').read_text());assert D['turn']==1779
for k in ['driver','process']:
 live=ident(D[k]['pid']);assert all(live[x]==D[k][x] for x in ['pid','boot_id','start_ticks'])
P=A/'turns/001778';prior=json.loads((P/'operational-summary-v1.json').read_text());ledgers={}
for n,r in prior['ledger_prefixes'].items():
 f=Path(r['path']);b=f.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[n]=ref(f)
S=Path(prior['current_source']['worktree']);commit=prior['current_source']['commit'];assert subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD'],text=True).strip()==commit
assert not subprocess.check_output(['git','-C',str(S),'status','--porcelain','--untracked-files=no'],text=True).strip()
stops=[A/'STOP',A.resolve()/'STOP'];assert not any(p.exists() for p in stops);assert time.time()<1791717193
put(T/'entry-inspection-v1.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),driver=ident(D['driver']['pid']),coordinator=ident(D['process']['pid']),previous_turn=ref(P/'receipt.json'),ledger_prefixes=ledgers,source=commit,source_worktree=str(S),live_gpu_handles=[],stop_present=False,deadline='2026-10-11T11:13:13Z',resource_isolation='ACTIVE_PASS',previous_turn_completed=True))
auth=dict(schema='n36-disabled-downstream-composition-authority-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),node_id='15.6',standing_authority=ref(A/'user-authorization-v1.json'),worktree=str(S),source=commit,root_scoped_review=ref(A/'turns/001775/scoped-review-result-v1.json'),source_deployment=ref(A/'turns/001774/source-placement-result-v1.json'),prior_bindings=ref(A/'turns/001771/recovery-bindings/affected-graph.prospective-disabled-v1.json'),ledger_prefixes=ledgers,stop_authority=dict(paths=[str(p) for p in stops],deadline='2026-10-11T11:13:13Z'),maximum_executor_seconds=1200,gpu_authorized=False,provider_measurement_authorized=False,source_edits_authorized=False,owning_state_mutation=False,scope='Prospective canonical-path rebinding of preparation policy, specification, runtime source-record and affected runtime/closure/controller references, followed by disabled graph recomposition and exact production static consumers. Preserve successor and both consumed predecessor identities, all charges, scientific settings and source. No release or measurement.',delegation_transport='Official current-login Codex CLI gpt-6-astra bounded Arbor executor')
put(O/'authority-v1.json',auth)
prompt=f'''You are a bounded Arbor artifact executor for ongoing N36 node15.6, not coordinator. Read {O}/authority-v1.json. Exact immutable source {commit} at {S}. Your task is the narrow prospective canonical-path artifact repair identified in {P}/terminal-reconciliation-v1.json and {A}/turns/001776/disabled-graph-composition/final-result/report-v1.json (use final-result, not its superseded top-level report).
Production currently rejects R1 canonical runtime reference path because the runtime reference is lexical home alias, while the production condition requires a resolved canonical path matching pinned policy disabled_runtime_path. You are authorized to prospectively rebind preparation policy, specification, runtime source-record and affected runtime/closure/controller references, then recompose the disabled downstream graph in your new output directory. Use canonical /mnt/data paths in newly bound references where required; preserve old artifacts untouched. Keep n36_readiness_preparation_recovery_001771 and both consumed predecessors, all charged costs, protected reserves, deadline and STOP bindings. Frozen all40 audit episodes/configs, engineering cell, algorithms, scientific thresholds and exact source remain unchanged. Do not copy independent approval to changed bindings. Reuse prior valid narrow evidence; no recursive historical rebuild.
Read prior composition-v3 and final-result under turn001776 as targeted templates. Use source production validators to derive proper bindings, no weakening checks, no monkeypatches. Recompose affected manifests/plan/build/equivalence/graph only as necessary. Run exact focused production static consumers and verify_graph for all41 manifests. If a blocker requires source changes or expanding scope, record exact error and stop. No broad tests. Write report-v1.json, artifact-manifest-v1.json and exact command/result evidence, scientific/ledger preservation checks, next bounded step. Keep release disabled and readiness/provider flags false. This is artifact repair, not independent review, measurement or success.
No source edits or commits, no owning state/checkpoint/ledger writes, GPU/CUDA jobs, provider measurements, cloud, protected validation/formal reads, prohibited 2026-08-10 guidance-transition design reads, credential reads or alternate providers. Do not acquire driver.lock/coordinator.lease or launch other agents. Bound 1200 seconds, two CPU threads. All new outputs under {O}; use {O.resolve()}/tmp for temporary files (create it first), since home filesystem temp may be full.'''
(O/'prompt.txt').write_text(prompt)
# Reconcile actual completed side effects before replacing the stale in-flight record.
terminal=P/'terminal-reconciliation-v1.json'
tr=json.loads(terminal.read_text());assert tr['status']=='TERMINAL_BLOCKED_CANONICAL_RUNTIME_PATH'
for pid in [3444667,3444668]:assert not Path(f'/proc/{pid}').exists()
for entry in json.loads((A/'turns/001776/disabled-graph-composition/final-composition-index-v1.json').read_text()).values():
 if isinstance(entry,dict) and 'path' in entry and 'sha256' in entry:assert ref(Path(entry['path']))['sha256']==entry['sha256']
with (W/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for sp in [W/'research-state.yaml',W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json']:
  isyaml=sp.suffix=='.yaml';d=yaml.safe_load(sp.read_text()) if isyaml else json.loads(sp.read_text())
  old=d['in_flight_executor'];assert old['wrapper']['pid']==3444667 and old['executor']['pid']==3444668
  old['status']='TERMINAL_BLOCKED_CANONICAL_RUNTIME_PATH';old['terminal_reconciliation']=ref(terminal);old['live_handles']=[]
  d['n36_recovery_disabled_graph_composition']=old;d['in_flight_executor']=None
  tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');tmp.replace(sp)
wrapper=(A/'turns/001771/recovery-bindings/run-executor.py').read_text().replace("W=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree')",f'W=Path({str(S)!r})')
(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('wb') as out:
 p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-I','-B',str(O/'run-executor.py')],cwd=S,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(wrapper=ident(p.pid),authority=ref(O/'authority-v1.json')))
for _ in range(30):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
process=json.loads((O/'process-v1.json').read_text())
rec=dict(status='RUNNING_CPU_CANONICAL_PATH_REBINDING',source=commit,worktree=str(S),authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=process['wrapper'],executor=process['executor'],gpu_authorized=False,source_edits_authorized=False,measurement_authorized=False)
nextstep='Monitor turn001779 canonical-path-rebinding executor by boot/start identity; do not duplicate. Reconcile terminal artifact changes and exact static production admission, then independent review of changed bindings and graph before any readiness release. Preserve successor and both consumed preparation identities and charges.'
with (W/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=W/'research-state.yaml';s=yaml.safe_load(sp.read_text());assert s.get('in_flight_executor') is None and not s.get('in_flight_executors');s['n36_canonical_path_rebinding']=rec;s['in_flight_executor']=rec;s['next_action']=nextstep;s['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,allow_unicode=True,sort_keys=False));tmp.replace(sp)
 cp=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';c=json.loads(cp.read_text());c['n36_canonical_path_rebinding']=rec;c['in_flight_executor']=rec;c['next_action']=nextstep;put(cp,c)
summary=dict(schema='autonomy-operational-summary-v1',turn=1779,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),current_source=prior['current_source'],owning_source=prior['owning_source'],scientific_source=prior['scientific_source'],live_handles=dict(driver=ident(D['driver']['pid']),coordinator=ident(D['process']['pid']),composition_wrapper=process['wrapper'],composition_executor=process['executor']),controller_status='NO_LIVE_GPU_COHORT; CPU prospective canonical path rebinding running',ledger_prefixes=ledgers,completed_work=['Verified bound handoff, authorization and completion contract; live driver/coordinator identity, previous successful turn, source deployment and exact ledger prefixes reconciled.','Reconciled prior terminal blocked composition and launched bounded official current-login gpt-6-astra CPU canonical-path artifact executor with no source edits, measurements or GPU authority.','Recorded current handles and continuation step in owning state/checkpoint.'],next_bounded_step=nextstep,unresolved_evidence=['Disabled downstream graph static validation and independent review pending.','Native readiness, scientific promotion, original validation/formal/required ablations unproven.'],deadline_utc='2026-10-11T11:13:13Z',stop_present=False,deadline_passed=False,gpu_dispatches=0,target_met=False,executor=rec)
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps(rec,indent=2))
