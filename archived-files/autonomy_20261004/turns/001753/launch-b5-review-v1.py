from pathlib import Path
import json,hashlib,datetime,subprocess,os,fcntl,yaml
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001753';O=T/'independent-b5-review';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001753');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
def ident(pid):
 st=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(st[19]),state=st[0])
prev=json.loads((A/'turns/001752/operational-summary-v1.json').read_text());old=json.loads((A/'turns/001740/recovery-graph-refresh/authority-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not any(Path(p).exists() for p in old['stop_authority']['paths']);assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
driver=json.loads((A/'driver-status.json').read_text());assert driver['turn']==1753
for k in ['driver','process']:
 v=ident(driver[k]['pid']);assert all(v[x]==driver[k][x] for x in ['pid','boot_id','start_ticks'])
for r in prev['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
for p in [3245423,3245425,3116764,3116766,756298]:assert not Path('/proc',str(p)).exists()
assert subprocess.check_output(['git','-C',old['source']['worktree'],'rev-parse','HEAD'],text=True).strip()==old['source']['commit']
assert not subprocess.check_output(['git','-C',old['source']['worktree'],'status','--porcelain','--untracked-files=no'],text=True).strip()
O.mkdir()
indexpath=A/'turns/001748/disabled-graph-composition/final-composition-index-v1.json'
index=json.loads(indexpath.read_text())
for key in ['graph','final_report','generated_artifact_manifest']:
 r=index[key];assert ref(Path(r['path']))['sha256']==r['sha256']
auth=dict(schema='n36-independent-b5-review-authority-v1',at=now,node_id='15.6',standing_authority=ref(A/'user-authorization-v1.json'),source=index['source'],final_index=ref(indexpath),graph=index['graph'],report=index['final_report'],root_controller_acceptance=ref(A/'turns/001747/root-controller-binding-attestation-v1.json'),stop_authority=old['stop_authority'],maximum_executor_seconds=1200,output_directory=str(O),ledger_prefixes=prev['ledger_prefixes'],scope='Independent CPU-only B5 review of exact complete disabled graph. No source or graph edits, state mutation, adoption, GPU or provider measurement.',gpu_authorized=False,source_edits_authorized=False,owning_state_mutation=False,release_enabled=False)
authref=put(O/'authority-v1.json',auth)
prompt=f"""You are the independent B5 reviewer for the continuing explicitly authorized Arbor study, node15.6; you are NOT a coordinator. Read {O}/authority-v1.json and obey scope. Use only official current-login Codex gpt-6-astra; no API keys, alternate accounts/providers or subagents. Write only under {O}. No source, frozen plans, graph, existing artifacts, owning state/tree/ledger edits. No GPU, simulation, native build, model loading, provider measurement or evaluation. Never open the prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, protected validation/formal results or credential files (including Poe). Never execute Poe launchers.
Task: independent CPU-only B5 review of EXACT final graph and final composition index bound in authority. Verify graph/index/report hashes, source commit {index['source']['commit']}, current ledger prefixes, disabled authorizations, frozen scientific equivalence, all40 manifest index and separate engineering manifest, recovery identity/prefix contract, retained charges, budget/reserves/deadline, runtime/closure/controller consistency and relocation bindings. Reuse composition-v3's exact production validator command evidence; do NOT rebuild old provenance or rerun the full all41 verification without an identified evidence gap. Follow only necessary bounded references and inspect relevant production B5/adoption validator source to make output directly consumable if a defined review schema exists. Do not count audit-only frozen snapshots as execution authority. Existing root controller acceptance is an input; this review must independently determine graph correctness and must not confer root adoption or readiness.
Output review-v1.json, hash sidecar and hash-bound file-manifest-v1.json. Report PASS_SCOPED_B5 or BLOCKED (or exact required production schema verdict if defined), exact reviewed graph reference, source, checks/evidence, precise blockers/limitations, and minimal next step. Clearly separate static B5 acceptance from root accounting/adoption, new finite preparation release, fresh measured readiness and external acceptance, separate health and episode releases. All remain pending; no scientific success, protected promotion or GPU authorization is granted. Preserve unknown telemetry and all old charges; retained preparation charge is 0.045194898711310494 GPUh. Stop/deadline prohibits new dispatch. Bound review to 1200seconds. If blocked write precise actionable findings instead of broad reconstruction. Finish promptly once the specific review is complete.
"""
(O/'prompt.txt').write_text(prompt+'\n')
wrapper=(A/'turns/001737/independent-source-review/run-executor.py').read_text().replace('/variants/n36_engineering_r1_001617/implementation_worktree','/variants/n36_engineering_adapter_001482/implementation_worktree')
(O/'run-executor.py').write_text(wrapper)
with (O/'wrapper.log').open('wb') as log:
 p=subprocess.Popen(['python',str(O/'run-executor.py')],cwd=W,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
launch=put(O/'wrapper-launch-v1.json',dict(at=now,wrapper=ident(p.pid),authority=authref,gpu_authorized=False))
record=dict(status='RUNNING_CPU_ONLY_INDEPENDENT_B5_REVIEW',source=old['source']['commit'],worktree=old['source']['worktree'],authority=authref,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=ident(p.pid),gpu_authorized=False,source_edits_authorized=False)
next_step='Monitor turn001753 independent-b5-review exact process identity and exit; never duplicate. At terminal verify exact B5 review and graph bindings, then root accounting/adoption and separately released fresh measured readiness before health or episode release. No GPU dispatch currently authorized.'
summary=dict(schema='autonomy-operational-summary-v1',turn=1753,at=now,current_source=old['source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=dict(driver=ident(driver['driver']['pid']),coordinator=ident(driver['process']['pid']),review_wrapper=ident(p.pid)),controller_status='Prior GPU and graph controllers terminal; GPU7 idle. Bounded CPU-only independent B5 graph review launched.',ledger_prefixes=prev['ledger_prefixes'],review=record,completed_work=['Verified bound authority, driver identities, STOP/deadline, owning state/checkpoint and unchanged four ledger prefixes.','Reconciled prior terminal processes and confirmed exact clean final engineering source.','Launched bounded independent complete disabled graph B5 review using official current-login Codex gpt-6-astra.'],next_bounded_step=next_step,unresolved_evidence=['Independent B5 review pending.','Complete disabled all41 graph composed; root accounting/adoption and fresh measured readiness pending.','Original validation/formal/required ablation goal remains unmet.'],deadline_utc=old['deadline'],stop_present=False,deadline_passed=False,target_met=False)
sr=put(T/'operational-summary-v1.json',summary)
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:d.update(n36_final_graph_b5_review=record,next_action=next_step,latest_operational_summary=sr,last_updated_utc=now)
 tree['nodes']['15.6'].update(result='FINAL_GRAPH_INDEPENDENT_B5_REVIEW_RUNNING',insight=next_step,final_graph_b5_review=record)
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=sr,launch=launch,wrapper=record['wrapper'])))
