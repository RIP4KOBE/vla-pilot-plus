import pathlib,json,hashlib,datetime,subprocess,fcntl,os,time,yaml
owner=pathlib.Path.cwd();root=owner.parent/'autonomy_20261004';turn=root/'turns/001292';old=root/'turns/001290/readiness-binding';out=turn/'independent-b5-review';out.mkdir(exist_ok=True)
coord=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator';cp=coord/'checkpoint.json'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 a=ref(r['path']);assert a['sha256']==r['sha256'],r['path'];return a
def write(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat')
 if not p.exists():return dict(pid=pid,absent=True)
 s=p.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
now=datetime.datetime.now(datetime.timezone.utc);ds=json.loads((root/'driver-status.json').read_text());assert ds['turn']==1292
for k in ['driver','process']:
 h=ds[k];a=handle(h['pid']);assert all(a[x]==h[x] for x in ['boot_id','start_ticks'])
assert all(handle(p).get('absent') for p in [721701,721702,391755])
prior=json.loads((root/'turns/001291/entry-reconciliation-v1.json').read_text());ledgers={n:verify(r) for n,r in prior['ledger_prefixes'].items()}
stop=list(prior['STOP']);assert not any(os.path.lexists(p) for p in stop);assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert json.loads((root/'turns/001291/receipt.json').read_text())['status']=='completed_turn'
assert json.loads((old/'executor-exit-v1.json').read_text())['exit']==0
completion=json.loads((old/'completion-v1.json').read_text());report_ref=verify(completion['authoritative_result']);report=json.loads(pathlib.Path(report_ref['path']).read_text());assert report['blocker'] is None and report['release_enabled'] is False
checked=[verify(r) for r in report['outputs'].values()];verify(completion['next_independent_b5_inputs']);verify(completion['preserved_initial_attempt'])
source='30c6321715df86c5bab623db607bab2811aed56d';work=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree')
for w in [owner,work]:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()==source
state=yaml.safe_load((owner/'research-state.yaml').read_text());assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
rec=dict(schema='autonomy-entry-monitor-reconciliation-v1',at=now.isoformat(),source=source,driver=handle(ds['driver']['pid']),coordinator=handle(ds['process']['pid']),prior_turn=ref(root/'turns/001291/receipt.json'),prior_turn_status='completed_turn',controller_status=verify(prior['controller_status']),old_controller_absent=True,old_cpu_handles_absent=[721701,721702],ledger_prefixes=ledgers,STOP={p:False for p in stop},deadline=prior['deadline'],gpu_dispatch=False,target_met=False)
write(turn/'entry-reconciliation-v1.json',rec)
reconcile=dict(schema='n36r2-readiness-binding-terminal-reconciliation-v1',at=now.isoformat(),completion=ref(old/'completion-v1.json'),executor_exit=ref(old/'executor-exit-v1.json'),authoritative_report=report_ref,output_hashes_verified=len(checked),status='CANDIDATE_ACCEPTED_FOR_INDEPENDENT_B5_REVIEW_ONLY',initial_comparison_failure_preserved=completion['preserved_initial_attempt'],scientific_change=False,score=None,release_enabled=False,target_met=False,retained_attempts=504,retained_gpu_hours=75.49265038509455)
write(turn/'terminal-reconciliation-v1.json',reconcile)
inputs=dict(completion=ref(old/'completion-v1.json'),candidate_report=report_ref,b5_input_package=verify(completion['next_independent_b5_inputs']),root_reconciliation=ref(turn/'terminal-reconciliation-v1.json'),standing_authority=ref(root/'user-authorization-v1.json'))
a=dict(schema='n36r2-independent-b5-authority-v1',at=now.isoformat(),node_id='15.6',owner=str(owner),worktree=str(work),output_directory=str(out),base_source=source,inputs=inputs,scope='Independent CPU review of exact readiness-bound candidate inputs; no scientific changes or execution release',allowed=['Verify immediate hash-bound package and readiness-dependent deltas; reuse unchanged accepted source/protocol evidence.','Independently check actual B5 verifier requirements and all40 config/context joins, input equality, runtime/closure/controller bindings and future worker acceptance obligations.','If and only if justified, write input-bound independent B5 review with exact schema/decision required by actual verifier; otherwise record precise blockers.'],forbidden=['No source/candidate/old artifact edits, owner state/ledger/tree writes or child agents.','No GPU, healthcheck, Main, simulator, network, provider/login probes, credential reads, protected validation/formal results or prohibited design.','No final frozen plan, root production approval, execution release or dispatch. No broad tests or historical provenance rebuild.'],wall_cap_seconds=900,test_budget_seconds=120,cpu_threads=2,gpu_authorized=False,source_edits_authorized=False,scientific_edits_authorized=False,release_enabled=False,STOP_paths=stop,deadline=prior['deadline'])
write(out/'authority-v1.json',a)
prompt=f'''You are the independent Arbor B5 reviewer for continuing node15.6. You did not implement the candidate. Read {out/'authority-v1.json'} and hash-bound inputs. Review readiness-bound candidate-v2 on accepted source {source}. Inspect actual qd_ed_n36r2_admission.py verifier requirements and candidate changes, using immediate accepted source/readiness/adoption reviews as evidence; do not recursively rebuild old provenance. Independently verify full scientific config equality for all40 cells, source/runtime/closure/controller/context bindings, fresh cohort IDs, protocol/accounting/protected reserves and readiness semantics. The initial tuple/list comparison failure is preserved; verify candidate-v2 normalization did not alter scientific values. Full native/runtime byte checks remain mandatory at production release/admission; no new device access or giant checkpoint rehash here. Future process-bound worker receipts are mandatory before acceptance but cannot exist before dispatch. If exact inputs warrant it, create an independent input-bound B5 record using the actual verifier's expected schema, decision, review_inputs and additional fields from next-independent-b5-inputs-v1.json. Do not fabricate approval: report BLOCKED with concrete reasons if unsatisfied. Produce report-v1.json/md and, only on PASS, the external B5 record. Include evidence hashes, focused check outcomes, score null,target_met false,release_enabled false. Only output files under {out}. No source edits, owner mutations, scientific edits, broad tests, child agents, GPU/simulator/provider/network/credentials/protected results or prohibited design access. Do not freeze final plan, mint root production review/release, dispatch or edit candidate. CPU checks <=120s two threads; total task900s. Check STOP/deadline. Final plan/root production review/detached release and admission remain coordinator's later duties. Return concrete artifacts.'''
(out/'executor-prompt-v1.txt').write_text(prompt+'\n')
(out/'executor-launch-v1.py').write_text((old/'executor-launch-v1.py').read_text().replace('n36r2-readiness-binding-process-v1','n36r2-independent-b5-process-v1'))
with open(owner/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in ledgers.values():verify(r)
 assert not any(os.path.lexists(p) for p in stop)
 for p in [owner/'research-state.yaml',cp,coord/'idea_tree.json']:(turn/(p.name+'.before')).write_bytes(p.read_bytes())
 with open(out/'wrapper.log','ab') as log:p=subprocess.Popen(['python',str(out/'executor-launch-v1.py')],cwd=work,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 write(out/'wrapper-launch-v1.json',dict(wrapper=handle(p.pid),authority=ref(out/'authority-v1.json'),gpu_authorized=False))
 for _ in range(30):
  if (out/'executor-process-v1.json').exists():break
  time.sleep(.1)
 pr=json.loads((out/'executor-process-v1.json').read_text());item=dict(status='INDEPENDENT_B5_REVIEW_RUNNING_RELEASE_DISABLED',authority=ref(out/'authority-v1.json'),worktree=str(work),output_directory=str(out),gpu_authorized=False,source_edits_authorized=False,handles={k:pr[k] for k in ['wrapper','executor']},process_record=ref(out/'executor-process-v1.json'),wrapper_launch=ref(out/'wrapper-launch-v1.json'))
 nxt='Monitor turn001292 independent B5 reviewer by boot/start identity. Reconcile terminal input-bound review; only on PASS freeze final plan, obtain external root production review and detached release, then recheck admission. No GPU dispatch before all gates pass.'
 d=json.loads(cp.read_text());s=yaml.safe_load((owner/'research-state.yaml').read_text());tree=json.loads((coord/'idea_tree.json').read_text())
 for x in [d,s]:
  x['in_flight_executor']=item;x['in_flight_executors']=[];x['n36r2_readiness_binding_terminal']=ref(turn/'terminal-reconciliation-v1.json');x['n36r2_readiness_b5_review']=item;x['phase']='N36R2_INDEPENDENT_READINESS_B5_REVIEW_RUNNING';x['next_action']=nxt;x['updated_at']=now.isoformat()
 write(cp,d);t=owner/'research-state.yaml.tmp';t.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));t.replace(owner/'research-state.yaml')
 tree['nodes']['15.6']['n36r2_readiness_binding_terminal']=ref(turn/'terminal-reconciliation-v1.json');tree['nodes']['15.6']['n36r2_readiness_b5_review']=item;tree['nodes']['15.6']['status']='running';write(coord/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',turn=1292,at=now.isoformat(),source=source,live_handles=item['handles'],driver=rec['driver'],coordinator=rec['coordinator'],completed_work=f'Reconciled successful readiness-binding executor, preserved initial comparison failure, verified {len(checked)} output hashes and unchanged owning ledgers; launched independent exact-input B5 review on official current-login gpt-6-astra.',next_bounded_step=nxt,unresolved_evidence='B5 review/final-plan/root-production/release gates and actual validation/formal/required ablation evidence remain pending.',retained_attempts=504,retained_gpu_hours=75.49265038509455,release_enabled=False,target_met=False)
write(turn/'operational-summary.json',summary)
md=f"Source {source}. Driver {rec['driver']['pid']} and coordinator {rec['coordinator']['pid']} boot/start verified. CPU B5 review wrapper {pr['wrapper']['pid']} / executor {pr['executor']['pid']} running; no GPU cohort.\n\n{summary['completed_work']} Retained 504 attempts / 75.49265038509455 GPUh, all three ledger prefixes unchanged. STOP absent; deadline 2026-10-11T11:13:13Z.\n\nNext: {nxt}\n\n{summary['unresolved_evidence']} Goal not complete.\n"
(turn/'operational-summary.md').write_text(md);(turn/'operational-summary.sha256').write_text(hashlib.sha256(md.encode()).hexdigest()+'  operational-summary.md\n')
print(json.dumps(summary,indent=2))
