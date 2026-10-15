from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004';T=A/'turns/001726';P=A/'turns/001723/readiness-recovery-graph';O=T/'independent-recovery-binding-review';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def identity(pid):
 p=Path('/proc')/str(pid)/'stat'
 if not p.exists():return None
 v=p.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(v[19]),state=v[0])
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001726');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
now=datetime.datetime.now(datetime.timezone.utc);prev=json.loads((A/'turns/001725/operational-summary-v1.json').read_text());auth=json.loads((P/'authority-v1.json').read_text());stop=auth['stop_authority']
assert not any(Path(p).exists() for p in stop['paths']);assert not (W/'STOP').exists();assert now<datetime.datetime.fromisoformat(stop['deadline'].replace('Z','+00:00'))
assert json.loads((A/'turns/001725/receipt.json').read_text())['exit']==0
for pid in [3158067,3158068,3116764,3116766]:assert identity(pid) is None
exit_record=json.loads((P/'exit-v1.json').read_text());assert exit_record['exit']==0 and not exit_record['timeout']
report=json.loads((P/'report-v1.json').read_text());assert report['status']=='PROSPECTIVE_DRAFTS_COMPLETE_GRAPH_BLOCKED'
assert (P/'report-v1.sha256').read_text().split()[0]==ref(P/'report-v1.json')['sha256']
for key in ['graph','prospective_policy','prospective_specification','focused_command_evidence','authority']:
 r=report[key];assert ref(Path(r['path']))['sha256']==r['sha256']
handles={};driver=json.loads((A/'driver-status.json').read_text())
for k,r in [('driver',driver['driver']),('coordinator',driver['process'])]:
 v=identity(r['pid']);assert v and all(v[x]==r[x] for x in ['pid','boot_id','start_ticks']);handles[k]={**v,'identity_verified':True}
prefixes={}
for k,r in prev['ledger_prefixes'].items():
 p=Path(r['path']);assert hashlib.sha256(p.read_bytes()[:r['bytes']]).hexdigest()==r['sha256'];prefixes[k]={**ref(p),'prior_prefix_preserved':True}
work=Path(prev['current_source']['worktree']);source=prev['current_source']['commit'];assert subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()==source
assert not subprocess.check_output(['git','-C',str(work),'status','--porcelain','--untracked-files=no'],text=True).strip()
terminal=put(T/'terminal-reconciliation-v1.json',dict(schema='n36-readiness-recovery-terminal-reconciliation-v1',at=now.isoformat(),process_record=ref(P/'process-v1.json'),exit=ref(P/'exit-v1.json'),report=ref(P/'report-v1.json'),source=prev['current_source'],live_handles=[],ledger_prefixes=prefixes,status=report['status'],production_ready=False,source_adopted=False,target_met=False))
O.mkdir()
authority=put(O/'authority-v1.json',dict(schema='n36-recovery-binding-independent-review-authority-v1',at=now.isoformat(),node_id='15.6',standing_authority=ref(A/'user-authorization-v1.json'),terminal_reconciliation=terminal,source=prev['current_source'],report=ref(P/'report-v1.json'),stop_authority=stop,maximum_executor_seconds=1200,output_directory=str(O),source_edits_authorized=False,gpu_authorized=False,provider_measurement_authorized=False,release_enabled=False,owning_state_mutation=False,scope='Independently review exact prospective specification, preparation policy, canonical source-pin diff and graph blockers. Decide whether minimal binding amendment is justified and identify exact required corrections; no source changes or active adoption.'))
prompt=f'''You are an independent bounded Arbor CPU reviewer for continuing node 15.6. Read {O}/authority-v1.json and its directly bound terminal report. Review final CANONICAL prospective artifacts in {P}, their source-pin diff, and the affected current production binding code in {work} at {source}. Verify that the proposed new readiness identity is fresh and cannot replay consumed n36_readiness_preparation_001651; retained charge 0.045194898711310494 GPUh, protected reserves, scientific source/thresholds, audit rules, provider route and STOP/deadline stay unchanged. Check exact path/hash and source-pin amendment semantics, source inventory projection, and whether downstream regeneration after the pin commit avoids circular source/spec binding. Distinguish legitimate prospective audit freeze from runtime/provider readiness or execution permission: no active cohort is running, and root can authorize a prospective audit freeze under standing authority once its exact inputs are reviewed. Do not demand renewed user approval. Recommend the smallest concrete follow-on engineering repair and artifact regeneration, with any blocking defects. Do not recursively audit historical provenance or rerun broad tests. Validate direct refs and read only relevant source slices; no reading Poe credential files, prohibited untracked 2026-08-10 design or protected validation/formal results. No source edits/commits, GPU/model/native build/provider calls, measurements, cloud, other agents, state/checkpoint/tree/ledger/locks or lease changes. Write only {O}. Produce review-v1.json and hash, direct evidence, exact accept/block disposition and bounded next step. This is a REVIEW only; do not claim graph completion, readiness, final B5 or scientific success. Official current-login Codex gpt-6-astra only. Bound 1200s; preserve all old artifacts.'''
(O/'prompt.txt').write_text(prompt+'\n');(O/'run-executor.py').write_text((P/'run-executor.py').read_text())
with (O/'wrapper.log').open('ab') as log:
 p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python',str(O/'run-executor.py')],cwd=W,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
entry=dict(status='CPU_INDEPENDENT_BINDING_REVIEW_RUNNING',source=source,worktree=str(work),authority=authority,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=identity(p.pid),gpu_authorized=False,source_edits_authorized=False)
put(O/'wrapper-launch-v1.json',entry)
nextstep='Monitor turn001726 independent-recovery-binding-review by boot/start identity. Reconcile final review; if accepted, authorize isolated minimal specification-pin repair and prospective audit freeze with downstream regeneration. Do not replay consumed 001651 readiness, adopt incomplete graph, or dispatch GPU before exact release gates.'
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:
  old=d['n36_readiness_recovery_graph_preparation'];old['status']='TERMINAL_PROSPECTIVE_DRAFTS_COMPLETE_GRAPH_BLOCKED';old['terminal_reconciliation']=terminal;old['report']=ref(P/'report-v1.json');old['live_handles']=[]
  d['n36_readiness_recovery_binding_review']=entry;d['next_action']=nextstep;d['last_updated_utc']=now.isoformat()
 tree['nodes']['15.6']['readiness_recovery_graph_preparation']=s['n36_readiness_recovery_graph_preparation'];tree['nodes']['15.6']['readiness_recovery_binding_review']=entry;tree['nodes']['15.6']['insight']=nextstep
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',turn=1726,at=now.isoformat(),current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles={**handles,'review_wrapper':identity(p.pid)},controller_status='Prior CPU artifact executor exited 0 and reconciled; independent CPU binding review running; no GPU controller launched.',ledger_prefixes=prefixes,completed_work=['Verified authority hashes, driver identities, STOP/deadline and owning ledger prefixes.','Reconciled terminal turn001723 outputs and unchanged isolated source; incomplete graph not adopted.','Launched bounded independent official gpt-6-astra review of exact canonical prospective bindings; updated owning state/checkpoint/tree.'],next_bounded_step=nextstep,unresolved_evidence=['Production graph incomplete; binding amendment independent review pending.','Readiness failure charge and unknown telemetry preserved.','Validation/formal/required ablation evidence does not establish original-goal completion.'],deadline_utc=stop['deadline'],stop_present=False,target_met=False)
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps(entry))
