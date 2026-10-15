from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001723'; O=T/'readiness-recovery-graph'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 assert not p.exists(); p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def identity(pid):
 p=Path('/proc')/str(pid)/'stat'
 if not p.exists():return None
 v=p.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(v[19]),state=v[0])
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001723');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
now=datetime.datetime.now(datetime.timezone.utc);prev=json.loads((A/'turns/001722/operational-summary-v1.json').read_text());stop=json.loads((A/'turns/001694/preparation-accounting-repair/prospective-release-v1.json').read_text())['stop_authority']
assert not any(Path(p).exists() for p in stop['paths']);assert now<datetime.datetime.fromisoformat(stop['deadline'].replace('Z','+00:00'))
assert json.loads((A/'turns/001722/receipt.json').read_text())['exit']==0
for pid in [3116764,3116766,3136923,3136931,3147284,3147285]:assert identity(pid) is None
handles={};driver=json.loads((A/'driver-status.json').read_text())
for k,r in [('driver',driver['driver']),('coordinator',driver['process'])]:
 v=identity(r['pid']);assert v and all(v[x]==r[x] for x in ['pid','boot_id','start_ticks']);handles[k]={**v,'identity_verified':True}
prefixes={}
for k,r in prev['ledger_prefixes'].items():
 p=Path(r['path']); assert hashlib.sha256(p.read_bytes()[:r['bytes']]).hexdigest()==r['sha256'];prefixes[k]={**ref(p),'prior_prefix_preserved':True}
work=Path(prev['current_source']['worktree']);source=prev['current_source']['commit'];assert subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()==source
assert not subprocess.check_output(['git','-C',str(work),'status','--porcelain','--untracked-files=no'],text=True).strip()
O.mkdir()
auth=dict(schema='n36-readiness-recovery-disabled-graph-authority-v1',at=now.isoformat(),node_id='15.6',standing_authority=ref(A/'user-authorization-v1.json'),review=ref(A/'turns/001721/independent-import-review/review-v1.json'),source_placement=ref(A/'turns/001722/source-placement-v1.json'),source=prev['current_source'],stop_authority=stop,deadline=stop['deadline'],maximum_executor_seconds=1200,output_directory=str(O),ledger_prefixes=prefixes,fresh_resource_id='n36_readiness_preparation_recovery_001723',recovery_of='n36_readiness_preparation_001651',retained_charge_gpu_hours=0.045194898711310494,source_edits_authorized=False,gpu_authorized=False,provider_measurement_authorized=False,release_enabled=False,owning_state_mutation=False,scope='Prepare fresh prospective recovery specification and disabled artifact graph using reviewed existing builders. Write only this output directory. No active-spec replacement, owner adoption or release. If immutable source-pinned specification prevents a fresh identity, report exact minimal required engineering amendment and emit reviewable prospective drafts; never reuse consumed identity or weaken validation.')
aref=put(O/'authority-v1.json',auth)
prompt=f'''You are a bounded Arbor CPU artifact executor for existing node 15.6, not coordinator. Read {O}/authority-v1.json and directly bound review/source placement. Current reviewed isolated worktree is {work}, source {source}. Prepare the fresh readiness recovery identity n36_readiness_preparation_recovery_001723 and prospective disabled graph. Retain failed n36_readiness_preparation_001651 and its 0.045194898711310494 GPUh charge; NEVER replay it. Use turn001707/disabled-graph-refresh/prepare-graph-v1.py and its report as narrow reference and current source builders. Do not blindly copy old identity/paths. Prospective recovery artifact paths must be fresh under {O}; old source/runtime/spec/release/evidence files immutable. Bind recovery_of and retained charge. Refresh only affected source/identity paths and hashes, preserving scientific thresholds, budgets/reserves, runtime audit rules, GPU7 isolation and exact provider/STOP/deadline. You may draft a prospective specification with these identity/path changes, but may not replace the active specification, edit source, adopt or release it. Use existing builder injection if available. If source-pinned specification prevents generation, report exact minimal follow-on amendment and write reviewable prospective specification/diff; do not weaken audit or fake graph completion. All authorizations, readiness, frozen/release flags false/null. No GPU/model/native build/provider preflight/measurement/health/episodes, state/checkpoint/tree/ledger/lock writes, source edits/commits, cloud, credentials, other agents or leases. Preserve Poe files unopened and never read prohibited untracked 2026-08-10 design or protected results. Check both STOP paths and deadline. Verify direct bindings only, no recursive provenance reconstruction or broad tests. Produce report-v1.json plus report-v1.sha256, manifest of generated files, focused command/check evidence and exact remaining gates. No independent-review claims: review follows this task. Bound 1200s. Continue autonomously within scope.'''
(O/'prompt.txt').write_text(prompt+'\n')
wrapper=(A/'turns/001707/disabled-graph-refresh/run-executor.py').read_text()
wrapper=wrapper.replace("assert time.time() < 1791717193", "assert time.time() < 1791717193\nassert not any(Path(p).exists() for p in json.loads((O/'authority-v1.json').read_text())['stop_authority']['paths'])")
(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('ab') as log:
 p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python',str(O/'run-executor.py')],cwd=W,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
launch=put(O/'wrapper-launch-v1.json',dict(wrapper=identity(p.pid),authority=aref,at=now.isoformat(),gpu_authorized=False))
entry=dict(status='CPU_RECOVERY_ARTIFACT_PREPARATION_RUNNING',source=source,worktree=str(work),authority=aref,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=identity(p.pid),gpu_authorized=False,source_edits_authorized=False)
nextstep='Monitor turn001723 readiness-recovery-graph executor by exact process identity; reconcile terminal side effects and inspect prospective fresh identity/graph or precise binding blocker. Independently review affected bindings before active-spec adoption or finite readiness release. Never replay consumed preparation 001651.'
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:d['n36_readiness_recovery_graph_preparation']=entry;d['next_action']=nextstep;d['last_updated_utc']=now.isoformat()
 tree['nodes']['15.6']['readiness_recovery_graph_preparation']=entry;tree['nodes']['15.6']['insight']=nextstep
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',turn=1723,at=now.isoformat(),current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles={**handles,'artifact_executor_wrapper':identity(p.pid)},controller_status='CPU recovery artifact executor launched; no live GPU measurement controller. Prior failure charged.',ledger_prefixes=prefixes,completed_work=['Verified bound handoff/authority, driver identities, both STOP paths/deadline, previous successful turn and ledger preservation.','Verified prior measurement/import executors absent and reviewed isolated source clean.','Recorded fresh recovery identity and launched bounded official current-login gpt-6-astra CPU artifact preparation; owning state/checkpoint/tree updated.'],next_bounded_step=nextstep,unresolved_evidence=['Fresh prospective graph and independent review pending.','Runtime/native readiness and validation/formal/required ablation completion unproved.'],deadline_utc=stop['deadline'],stop_present=False,target_met=False)
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps(entry))
