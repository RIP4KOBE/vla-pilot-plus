from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001740'; O=T/'recovery-graph-refresh'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 assert not p.exists(); p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def identity(pid):
 p=Path('/proc')/str(pid)/'stat'
 if not p.exists():return None
 v=p.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(v[19]),state=v[0])
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001740');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
now=datetime.datetime.now(datetime.timezone.utc);prev=json.loads((A/'turns/001739/operational-summary-v1.json').read_text());stop=json.loads((A/'turns/001694/preparation-accounting-repair/prospective-release-v1.json').read_text())['stop_authority']
assert not any(Path(p).exists() for p in stop['paths']);assert now<datetime.datetime.fromisoformat(stop['deadline'].replace('Z','+00:00'))
assert json.loads((A/'turns/001739/receipt.json').read_text())['exit']==0
for pid in [3229000,3229001,3205462,3205465]:assert identity(pid) is None
handles={};driver=json.loads((A/'driver-status.json').read_text())
for k,r in [('driver',driver['driver']),('coordinator',driver['process'])]:
 v=identity(r['pid']);assert v and all(v[x]==r[x] for x in ['pid','boot_id','start_ticks']);handles[k]={**v,'identity_verified':True}
prefixes={}
for k,r in prev['ledger_prefixes'].items():
 p=Path(r['path']); assert hashlib.sha256(p.read_bytes()[:r['bytes']]).hexdigest()==r['sha256'];prefixes[k]={**ref(p),'prior_prefix_preserved':True}
work=Path(prev['current_source']['worktree']);source=prev['current_source']['commit'];assert subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()==source
assert not subprocess.check_output(['git','-C',str(work),'status','--porcelain','--untracked-files=no'],text=True).strip()
O.mkdir()
auth=dict(schema='n36-readiness-recovery-disabled-graph-authority-v1',at=now.isoformat(),node_id='15.6',standing_authority=ref(A/'user-authorization-v1.json'),review=ref(A/'turns/001737/independent-source-review/review-v1.json'),source_placement=ref(A/'turns/001739/source-placement-v1.json'),source=prev['current_source'],stop_authority=stop,deadline=stop['deadline'],maximum_executor_seconds=1200,output_directory=str(O),ledger_prefixes=prefixes,fresh_resource_id='n36_readiness_preparation_recovery_001723',recovery_of='n36_readiness_preparation_001651',retained_charge_gpu_hours=0.045194898711310494,source_edits_authorized=False,gpu_authorized=False,provider_measurement_authorized=False,release_enabled=False,owning_state_mutation=False,scope='Prepare fresh prospective recovery specification and disabled artifact graph using reviewed existing builders. Write only this output directory. No active-spec replacement, owner adoption or release. If immutable source-pinned specification prevents a fresh identity, report exact minimal required engineering amendment and emit reviewable prospective drafts; never reuse consumed identity or weaken validation.')
auth['scope']='Generate affected disabled graph using final reviewed source and canonical turn001730 prospective specification. No source edits, production adoption, readiness spending or scientific execution.'
auth['canonical_contract']=ref(A/'turns/001730/recovery-prefix-contract/recovery-prefix-contract-v1.json')
auth['canonical_specification']=ref(A/'turns/001730/recovery-prefix-contract/engineering-r1-spec.canonical-prospective-disabled-v2.json')
auth['downstream_slots']=ref(A/'turns/001730/recovery-prefix-contract/downstream-slots-v2.json')
auth['allowed_output_roots']=[str(O),str((A/'turns/001730/recovery-prefix-contract/downstream-v2').resolve())]
# Authority has not been published yet; bind its final scope below.
prompt=f'''You are a bounded Arbor CPU artifact executor for existing node 15.6, not coordinator. Read {O}/authority-v1.json. Worktree {work}, exact reviewed source {source}. Generate only affected disabled downstream N36 recovery graph using canonical prospective specification, preparation policy and recovery-prefix contract in turn001730/recovery-prefix-contract. Read turn001739 operational summary, turn001737 independent-source-review/review-v1.json, and turn001723/readiness-recovery-graph/prepare-graph-v1.py if present or its report; turn001707/disabled-graph-refresh/prepare-graph-v1.py is the earlier builder pattern. Source implementation now consumes recovery-prefix contract; verify exact existing APIs first. Do not edit source or create another repair. Retain resource identity n36_readiness_preparation_recovery_001723, original accounting offsets, exact historical prefix and charged aborted predecessor 001651. Canonical reserved downstream-v2 paths from turn001730 are explicitly authorized for fresh output creation; never overwrite existing evidence. Write reports and supporting builder script in {O}. Generate final-source inventory, runtime, closure, controller/native bindings, scientific equivalence, disabled audit view, all 40 manifests and engineering manifest. Preserve exact scientific plan/rules/provider/GPU7, STOP/deadline, budgets/reserves; no historical readiness reuse. No fake proofs, synthetic production acceptance or release. Any unknown/missing binding is blocking; report precise blocker rather than weaken checks. No active-spec adoption, source edits/commits, state/checkpoint/tree/ledger/lock writes, GPU/model/native build/provider preflight/measurement/health/episodes, credentials, cloud, other agents or leases. All release/readiness/frozen authorization flags stay false/null. Never read prohibited untracked 2026-08-10 design or protected results; preserve Poe files unopened. Use only focused CPU builder/verification checks, no broad test repeats or recursive provenance rebuild. Produce report-v1.json with hash, exact generated-artifact manifest and command evidence, actual status and independent B5/root adoption requirements. Bound 1200 seconds.'''
aref=put(O/'authority-v1.json',auth)
(O/'prompt.txt').write_text(prompt+'\n')
wrapper=(A/'turns/001707/disabled-graph-refresh/run-executor.py').read_text()
wrapper=wrapper.replace("assert time.time() < 1791717193", "assert time.time() < 1791717193\nassert not any(Path(p).exists() for p in json.loads((O/'authority-v1.json').read_text())['stop_authority']['paths'])")
(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('ab') as log:
 p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python',str(O/'run-executor.py')],cwd=W,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
launch=put(O/'wrapper-launch-v1.json',dict(wrapper=identity(p.pid),authority=aref,at=now.isoformat(),gpu_authorized=False))
entry=dict(status='CPU_FINAL_SOURCE_RECOVERY_GRAPH_REFRESH_RUNNING',source=source,worktree=str(work),authority=aref,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=identity(p.pid),gpu_authorized=False,source_edits_authorized=False)
nextstep='Monitor turn001740 recovery-graph-refresh by exact PID/boot/start identity; reconcile terminal artifacts, then independent affected-graph engineering B5 review and root scope/accounting adoption before any readiness release. Preserve predecessor charges and all scientific gates.'
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:d['n36_readiness_recovery_final_graph_refresh']=entry;d['next_action']=nextstep;d['last_updated_utc']=now.isoformat()
 tree['nodes']['15.6']['readiness_recovery_final_graph_refresh']=entry;tree['nodes']['15.6']['insight']=nextstep
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',turn=1740,at=now.isoformat(),current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles={**handles,'artifact_executor_wrapper':identity(p.pid)},controller_status='CPU recovery artifact executor launched; no live GPU measurement controller. Prior failure charged.',ledger_prefixes=prefixes,completed_work=['Verified bound handoff/authority, driver identities, both STOP paths/deadline, previous successful turn and ledger preservation.','Verified prior measurement/import executors absent and reviewed isolated source clean.','Preserved canonical successor identity and launched bounded official current-login gpt-6-astra CPU artifact preparation; owning state/checkpoint/tree updated.'],next_bounded_step=nextstep,unresolved_evidence=['Fresh prospective graph and independent review pending.','Runtime/native readiness and validation/formal/required ablation completion unproved.'],deadline_utc=stop['deadline'],stop_present=False,target_met=False)
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps(entry))
