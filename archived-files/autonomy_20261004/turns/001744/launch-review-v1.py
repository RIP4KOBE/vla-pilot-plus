from pathlib import Path
import json,hashlib,datetime,subprocess,os,fcntl,yaml
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001744';O=T/'independent-controller-review';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001744');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
def ident(pid):
 st=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(st[19]),state=st[0])
prev=json.loads((A/'turns/001743/operational-summary-v1.json').read_text());old=json.loads((A/'turns/001740/recovery-graph-refresh/authority-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not any(Path(p).exists() for p in old['stop_authority']['paths']);assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
driver=json.loads((A/'driver-status.json').read_text());assert driver['turn']==1744
for k in ['driver','process']:
 v=ident(driver[k]['pid']);assert all(v[x]==driver[k][x] for x in ['pid','boot_id','start_ticks'])
for r in prev['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
for p in [3245423,3245425,3116764,3116766,756298]:assert not Path('/proc',str(p)).exists()
assert subprocess.check_output(['git','-C',old['source']['worktree'],'rev-parse','HEAD'],text=True).strip()==old['source']['commit']
assert not subprocess.check_output(['git','-C',old['source']['worktree'],'status','--porcelain','--untracked-files=no'],text=True).strip()
O.mkdir()
auth=dict(schema='n36-final-controller-independent-review-authority-v1',at=now,node_id='15.6',standing_authority=ref(A/'user-authorization-v1.json'),source=old['source'],boundary_diagnosis=ref(A/'turns/001743/root-boundary-diagnosis-v1.json'),prior_root_acceptance=ref(A/'turns/001713/root-controller-binding-attestation-v1.json'),proposed_artifact_directory=str(A/'turns/001740/recovery-graph-refresh'),stop_authority=old['stop_authority'],maximum_executor_seconds=1200,output_directory=str(O),ledger_prefixes=prev['ledger_prefixes'],scope='Bounded independent static review of final source/runtime/closure/controller bindings. No source edits, graph adoption, root approval, GPU or provider measurement.',gpu_authorized=False,source_edits_authorized=False,owning_state_mutation=False,release_enabled=False)
authref=put(O/'authority-v1.json',auth)
prompt=f'''You are a bounded independent Arbor reviewer for existing node15.6, NOT a coordinator. Read {O}/authority-v1.json and obey it. Use only current official Codex login gpt-6-astra; no alternate credentials/provider. No subagents. Output only under {O}. No state, tree, ledger, source, existing artifact or frozen protocol edits. No GPU, native build, simulation, provider measurement, model loading or evaluation. No prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md or protected results. Preserve unopened Poe credential files; ordinary positively identified tracked source may be hashed, but never execute/import Poe launchers.
Task: independently review ONLY affected final controller/runtime/closure bindings for source {old['source']['commit']} at {old['source']['worktree']}. Read turn001743 boundary diagnosis; compare turn001740 controller-{{set_goal,scale_action,wrapper_and_gripper}}.proposed-disabled-v1.json and the proposed controller/runtime/closure records reached by their exact references. Check prior root acceptance turn001713 for continuity without recursively rebuilding history. Read exact deployed source excerpts supporting delta scaling, zero rotation semantics, wrapper/gripper action forwarding, all fixed instance fields and source identities. Verify relevant reference hashes and runtime/closure agreement. Inspect source validators verify_semantics and necessary adapters. Distinguish static source proof from fresh measured readiness and actual instance attestation. Existing unaccepted projections must not acquire acceptance merely by copied status. Identify whether their semantics and final bindings can be root accepted, with exact provenance. Do not fabricate ROOT_REVIEWED, new measured readiness, B5, graph completeness, scientific success or authorization.
Expected deliverable review-v1.json plus hash-bound file manifest: PASS_SCOPED_STATIC_BINDINGS or BLOCKED with precise findings, source/runtime/closure/controller/proposal references, checks and limitations, exact minimal next construction step. If a source path is ambiguous or protected, report precise blocker rather than weakening source verification. Avoid broad repeat tests and nested provenance review. CPU-only installed library imports are permitted with CUDA_VISIBLE_DEVICES empty and limited threads if truly needed; prefer static reads. All41 manifest composition, B5, root accounting adoption, finite preparation release, fresh measured readiness, health and episode releases remain separate gates. A frozen=True immutable audit-only snapshot is allowed in future graph composition while every execution authorization is false; no graph creation in this review.
Finish within1200seconds. Write review even if blocked.''' 
(O/'prompt.txt').write_text(prompt+'\n')
wrapper=(A/'turns/001737/independent-source-review/run-executor.py').read_text().replace('/variants/n36_engineering_r1_001617/implementation_worktree','/variants/n36_engineering_adapter_001482/implementation_worktree')
(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('wb') as log:
 p=subprocess.Popen(['python',str(O/'run-executor.py')],cwd=W,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
launch=put(O/'wrapper-launch-v1.json',dict(at=now,wrapper=ident(p.pid),authority=authref,gpu_authorized=False))
record=dict(status='RUNNING_CPU_ONLY_INDEPENDENT_CONTROLLER_BINDING_REVIEW',source=old['source']['commit'],worktree=old['source']['worktree'],authority=authref,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=ident(p.pid),gpu_authorized=False,source_edits_authorized=False)
next_step='Monitor turn001744 independent-controller-review process identity and exit; never duplicate. At terminal verify exact review hashes and static controller/runtime/closure findings, then root decide acceptance before fresh graph composition. Preserve all41 manifests, B5/accounting, new measured readiness and scientific gates.'
summary=dict(schema='autonomy-operational-summary-v1',turn=1744,at=now,current_source=old['source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=dict(driver=ident(driver['driver']['pid']),coordinator=ident(driver['process']['pid']),review_wrapper=ident(p.pid)),controller_status='Prior GPU and graph controllers terminal; GPU7 idle. Bounded CPU-only independent static controller review launched.',ledger_prefixes=prev['ledger_prefixes'],review=record,completed_work=['Verified bound authority, driver identities, STOP/deadline, owning state/checkpoint and unchanged four ledger prefixes.','Reconciled prior terminal processes and confirmed exact clean final engineering source.','Launched bounded independent final controller/runtime/closure static binding review using official current-login Codex gpt-6-astra.'],next_bounded_step=next_step,unresolved_evidence=['Static final controller binding acceptance pending.','All41 manifest graph, independent B5, root adoption and fresh measured readiness pending.','Original validation/formal/required ablation goal remains unmet.'],deadline_utc=old['deadline'],stop_present=False,deadline_passed=False,target_met=False)
sr=put(T/'operational-summary-v1.json',summary)
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:d.update(n36_final_controller_independent_review=record,next_action=next_step,latest_operational_summary=sr,last_updated_utc=now)
 tree['nodes']['15.6'].update(result='FINAL_CONTROLLER_BINDING_INDEPENDENT_REVIEW_RUNNING',insight=next_step,final_controller_independent_review=record)
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=sr,launch=launch,wrapper=record['wrapper'])))
