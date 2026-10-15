import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,fcntl,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001171').resolve();v=o/'audit-repair';wt=w.parent/'variants/n36_nonprogress_tangent/implementation_worktree'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1171
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];s=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(s[19])==h['start_ticks'] and s[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001170/receipt.json')['exit']==0
prior=read(a/'turns/001170/operational-summary.json')
for r in prior['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
for pid in [4167858,4167865,2632351]:assert not pathlib.Path(f'/proc/{pid}').exists()
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();candidate=subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip();assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774' and candidate=='e7cdf2c09a60ffb1d248f073c5639303b2ef01fa'
reportpath=a/'turns/001152/implementation/report-v1.json';report=read(reportpath)
assert ref(reportpath)['sha256']=='d0a370c753d06a3fec7de2e201f6ce1b6311f839e4302fcaef16b815482d56cd'
for r in report['verified_references'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
v.mkdir()
auth={'schema':'n36-cpu-audit-repair-authority-v1','at':now.isoformat(),'node_id':'15.6','source':source,'candidate_source':candidate,'implementation_report':ref(reportpath),'root_review':report['verified_references']['root_review'],'protocol':report['verified_references']['protocol'],'user_authority':report['verified_references']['user_authority'],'ledger_prefixes':prior['ledger_prefixes'],'worktree':str(wt),'output_directory':str(v),'review_report':ref(a/'turns/001167/source-review/report-v1.json'),'scope':'Repair only SR-01 executing Python-code binding and SR-02 exact raw archive projection-origin joins. Preserve frozen scientific semantics; isolated CPU source edits and commit, no adoption or GPU.','gpu_authorized':False,'source_edits_authorized':True,'wall_cap_seconds':3600,'test_cpu_seconds_limit':900,'threads':2}
write(v/'authority-v1.json',auth)
prompt=f"""You are the isolated CPU audit repair executor for continuing explicitly authorized Arbor node 15.6 N36. Read and verify {v/'authority-v1.json'} and its direct references (independent review, implementation report, root protocol review and full frozen protocol). Work in {wt}, starting at candidate {candidate}. Repair SR-01 and SR-02 concretely; commit only intended repair source/tests/docs. You are not the coordinator. Output artifacts only {v}; no owning state/checkpoint/tree/ledger writes or source adoption. Read relevant AGENTS instructions. No further delegation, API keys, account/provider fallback, credential reads, Superpowers, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, protected validation/formal results, historical tensor replay, GPU/healthcheck, simulator/model/provider calls. Current official-login gpt-6-astra only.

SR-01: Bind actual executing Python code to the reviewed frozen source from process startup, including worker and auditor dependencies. Independent reviewer reproduced standard SourceFileLoader accepting timestamp/size-valid stale bytecode while on-disk source hash remains correct. PYTHONDONTWRITEBYTECODE alone does not prevent reading stale bytecode. Use a robust minimal source-only startup/import mechanism or independent live executable binding with explicit reviewed exceptions; preserve actual module/runtime/native-build path attestation. Cover actual runner-to-worker entry as well as policy and auditor dependencies. Do not weaken audits or trust producer flags. Reuse review repro-v1.py as evidence; add targeted stale timestamp/size-cache negative and positive integration checks of frozen code execution. Do not modify globally shared dependencies.

SR-02: Archive geometry source_origins are only cast/recomputed currently; changing raw binary64 1.0 to 1.001 can pass in bf16. Record and independently join each descriptor/archive projection to its ordered projection_origin evidence with decision/iteration/candidate identity and exact raw-origin bytes, plus native casts and projection bytes. Bind to applicable cached physical observation where required. Add cast-equivalent raw-origin corruption negatives, missing/reordered/wrong identity origin negatives and valid integration path. Keep exact native comparisons and all frozen arithmetic unchanged.

Preserve N36 science: hypothesis, proposal geometry, lifecycle memory, latch, scoring, other15/remainder, budgets, provider condition, task/init identities and thresholds. Audit instrumentation may add required provenance but must not alter scientific policy behavior. Preserve older controls' behavior. Do not widen scope to redesign. Independent source review was partial; report honest unresolved source/runtime/native obligations, not a comprehensive PASS. No benchmark or protected evaluation is authorized here.

CPU tests only with CUDA disabled, two threads, <=900 aggregate test CPU seconds, <=3600 wall seconds. Use meaningful narrow regression/integration tests, preserve each command, timing, failures and outcomes; avoid broad repeated suites. Commit coherent repair in isolated worktree, record base/final commits, per-file hashes, changes, tests, SR-01/SR-02 coverage and limitations in {v/'report-v1.json'} and report-v1.md. score=null, promotion=false,target_met=false. If blocked, preserve coherent partial work and explain precisely. Stop after report. Root requires independent repair review before adoption/runtime/prospective release.
"""
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(a/'turns/001152/implementation/executor-launch-v1.py').read_text().replace('n36-implementation-executor-process-v1','n36-audit-repair-executor-process-v1')
(v/'executor-launch-v1.py').write_text(wrapper)
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None and not s.get('current_owned_workers') and not s.get('in_flight_executor')
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before-review'))
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=wt,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; never retry blindly'
 pr=read(v/'executor-process-v1.json');rec={'status':'CPU_AUDIT_REPAIR_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':str(wt),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':True}
 next_step='Monitor exact N36 isolated CPU audit repair executor; reconcile terminal report/commit and request independent repair review before source adoption or actual runtime/native-build composition. No GPU/protected evaluation release yet.'
 for obj in [s,c]:obj.update(n36_audit_repair=rec,in_flight_executor=rec,phase='N36_CPU_AUDIT_REPAIR_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec;t['nodes']['15.6'].update(status='running',result='CPU_AUDIT_REPAIR_RUNNING_NO_GPU',audit_repair=rec)
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'candidate_source':candidate,'driver':ds['driver'],'coordinator':ds['process'],'executor':rec,'active_controller':None,'new_gpu_dispatches':0,'ledger_prefixes':prior['ledger_prefixes'],'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'completed':'Verified bound handoff/authority, current driver/coordinator identities, prior normal completion, closed reviewer handles and unchanged private ledger. Dispatched bounded isolated official gpt-6-astra CPU audit repair for confirmed SR-01/SR-02; no scientific retuning, adoption or GPU dispatch.','next_action':next_step,'unresolved':['Independent source/native audit review','Root controller/accounting boundary review','Runtime/accounting release and fresh Dev','Original validation/formal/required ablation evidence'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(rec))
