import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,fcntl,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001180').resolve();old=a/'turns/001171/audit-repair';v=o/'repair-review'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def check(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1180
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];s=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(s[19])==h['start_ticks'] and s[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001179/receipt.json')['exit']==0
prior=read(a/'turns/001179/monitor-observation-v1.json');ledgers={}
for name,r in prior['ledger_prefixes'].items():
 p=w/'data'/name;b=p.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[name]={**ref(p),'bytes':len(b),'prior_prefix_matches':True}
for pid in [14201,14203]:assert not pathlib.Path(f'/proc/{pid}').exists()
r=read(old/'report-v1.json');wt=pathlib.Path(r['worktree']);source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();candidate=subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip()
assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774' and candidate==r['final_commit']=='ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557'
assert read(old/'executor-exit-v1.json')['exit']==0
assert not subprocess.check_output(['git','-C',str(wt),'status','--porcelain','--untracked-files=no'],text=True).strip()
for x in r['verified_direct_references'].values():check(x)
check(r['authority'])
for x in r['source_files']:
 assert ref(pathlib.Path(x['absolute_path']))['sha256']==x['sha256']
 assert hashlib.sha256(subprocess.check_output(['git','-C',str(wt),'show',candidate+':'+x['path']])).hexdigest()==x['sha256']
for x in r['tests']:
 check(x['log']);check(x['timing_record'])
for key in ['verification_artifact','static_checks_artifact']:check(r[key])
terminal={'schema':'n36-audit-repair-terminal-reconciliation-v1','at':now.isoformat(),'status':'CPU_REPAIR_COMPLETED_PENDING_INDEPENDENT_REVIEW','source':source,'candidate_source':candidate,'report':ref(old/'report-v1.json'),'exit':ref(old/'executor-exit-v1.json'),'previous_handles':read(old/'executor-process-v1.json'),'old_processes_absent':True,'source_and_test_artifacts_verified':True,'ledger_prefixes':ledgers,'source_adopted':False,'target_met':False}
write(o/'repair-terminal-reconciliation-v1.json',terminal)
v.mkdir()
auth={'schema':'n36-independent-repair-review-authority-v1','at':now.isoformat(),'node_id':'15.6','candidate_source':candidate,'base_commit':r['base_commit'],'repair_report':ref(old/'report-v1.json'),'prior_review':r['verified_direct_references']['review_report'],'protocol':r['verified_direct_references']['protocol'],'root_review':r['verified_direct_references']['root_review'],'user_authority':r['verified_direct_references']['user_authority'],'worktree':str(wt),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False,'wall_cap_seconds':1800,'test_cpu_seconds_limit':300,'threads':2}
write(v/'authority-v1.json',auth)
prompt=f'''You are the independent CPU repair reviewer for continuing explicitly authorized Arbor node 15.6 N36. Read and hash-verify {v/'authority-v1.json'} and its direct references. Inspect actual repaired source at commit {candidate} versus {r['base_commit']} in {wt}. This is a bounded repair review, not a new scientific direction. Prior review found SR-01 stale bytecode breaks actual executable-source binding and SR-02 archive raw origins not joined to actual projection evidence. Verify those repairs end-to-end through actual runner/worker/bootstrap/import receipts and descriptor producer/auditor joins. Assess new source-only loader trust assumptions/exceptions, startup timing, inherited auditor dependencies, runpy execution, raw exact origins and occurrence/order/physical observation joins, unchanged scientific arithmetic and controls. Review collateral changes and any concrete release blocker. Do not accept producer claims or PASS flags alone.

No source edits, commits, source adoption, owning state/checkpoint/tree/ledger changes, GPU, provider/model/simulator/healthcheck calls, protected validation/formal results, historical tensors, credential files, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, Superpowers, API-key/alternate account fallback or further delegation. Use only official current-login gpt-6-astra. Artifacts only {v}. Preserve previous evidence. Reuse targeted test evidence; run a small new CPU reproduction only if needed for a concrete concern, <=300 CPU seconds aggregate with two threads and CUDA disabled. Maximum 1800 seconds wall. Do not demand recursive old provenance rebuilding or repeat broad tests. Distinguish source review from actual pinned runtime/native-build startup and full-episode audit obligations, which remain for later preparation.

Write report-v1.json and report-v1.md in {v}, with PASS/FAIL scoped findings, severity, exact file/line references, source hashes, checks, unresolved runtime obligations and smallest repair if needed. score=null, promotion=false, target_met=false, source_adopted=false. Stop after report. No benchmarking or scientific retuning.'''
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(old/'executor-launch-v1.py').read_text().replace('n36-audit-repair-executor-process-v1','n36-independent-repair-review-process-v1').replace('3600','1800');(v/'executor-launch-v1.py').write_text(wrapper)
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 check(s['n36_audit_repair']['process_record']);check(s['n36_audit_repair']['authority'])
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before'))
 for obj in [s,c]:
  obj['n36_audit_repair']={**obj['n36_audit_repair'],'status':'CPU_REPAIR_COMPLETED_PENDING_INDEPENDENT_REVIEW','report':ref(old/'report-v1.json'),'exit':ref(old/'executor-exit-v1.json'),'terminal_reconciliation':ref(o/'repair-terminal-reconciliation-v1.json')}
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=wt,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}, never retry blindly'
 pr=read(v/'executor-process-v1.json');rec={'status':'CPU_REPAIR_REVIEW_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':str(wt),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False}
 next_step='Monitor exact N36 independent CPU repair reviewer; reconcile terminal report before source adoption and actual pinned runtime/native-build composition. No GPU or protected evaluation release yet.'
 for obj in [s,c]:obj.update(n36_audit_repair_review=rec,in_flight_executor=rec,phase='N36_CPU_REPAIR_REVIEW_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec;t['nodes']['15.6'].update(status='running',score=None,result='CPU_REPAIR_REVIEW_RUNNING_NO_GPU',audit_repair_review=rec,audit_repair_terminal=ref(o/'repair-terminal-reconciliation-v1.json'))
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'candidate_source':candidate,'driver':ds['driver'],'coordinator':ds['process'],'executor':rec,'active_controller':None,'new_gpu_dispatches':0,'ledger_prefixes':ledgers,'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'completed':'Reconciled successful terminal N36 CPU audit repair, verified committed source and all reported test log/timing hashes including retained failures, launched official independent bounded CPU repair review. Owning source unchanged.','next_action':next_step,'unresolved':['Independent repair review','Actual runtime/native-build integration and prospective release','Fresh Dev scientific gates','Original validation/formal/required ablation evidence'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"Owning source {source}; isolated repaired candidate {candidate}. Repair executor exited 0; verified source and reported test artifact hashes, retaining failures. Independent CPU repair review launched with handles {json.dumps(rec['handles'])}. No active GPU controller or new GPU dispatch. Private ledgers unchanged: 502 attempts / 75.24379311215873 GPUh. STOP absent; deadline 2026-10-11T11:13:13Z. Next: {next_step} Original validation/formal/required ablation evidence outstanding; target not met.\n")
print(json.dumps(summary,indent=2))
