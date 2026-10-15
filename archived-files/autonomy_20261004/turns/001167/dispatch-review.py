import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,fcntl,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001167').resolve();v=o/'source-review';wt=w.parent/'variants/n36_nonprogress_tangent/implementation_worktree'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1167
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];s=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(s[19])==h['start_ticks'] and s[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001166/receipt.json')['exit']==0
prior=read(a/'turns/001166/operational-summary.json')
for r in prior['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
for pid in [4087135,4087136,2632351]:assert not pathlib.Path(f'/proc/{pid}').exists()
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();candidate=subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip();assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774' and candidate=='e7cdf2c09a60ffb1d248f073c5639303b2ef01fa'
reportpath=a/'turns/001152/implementation/report-v1.json';report=read(reportpath)
assert ref(reportpath)['sha256']=='d0a370c753d06a3fec7de2e201f6ce1b6311f839e4302fcaef16b815482d56cd'
for r in report['verified_references'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
v.mkdir()
auth={'schema':'n36-independent-cpu-source-review-authority-v1','at':now.isoformat(),'node_id':'15.6','source':source,'candidate_source':candidate,'implementation_report':ref(reportpath),'root_review':report['verified_references']['root_review'],'protocol':report['verified_references']['protocol'],'user_authority':report['verified_references']['user_authority'],'ledger_prefixes':prior['ledger_prefixes'],'worktree':str(wt),'output_directory':str(v),'scope':'Read-only independent review of scientific lifecycle and policy/Main integration, whole-episode native audit and same-device build binding. Root separately reviews release/accounting boundary. No source edits/adoption or GPU.','gpu_authorized':False,'source_edits_authorized':False,'wall_cap_seconds':1800,'test_cpu_seconds_limit':300,'threads':2}
write(v/'authority-v1.json',auth)
prompt=f'''You are a bounded independent CPU source reviewer for continuing explicitly authorized Arbor node15.6 N36. Read and hash-verify {v/'authority-v1.json'} plus its direct implementation report, root protocol review and full protocol. Candidate commit {candidate}, base {source}, isolated worktree {wt}. You did not implement it. Review actual code, not producer claims. Focus scientific lifecycle, tangent construction, ten-update latch/current template, occurrence aliases, policy/Main hooks, independent whole-episode native auditor, same-device arithmetic and external build attestation. Root concurrently reviews release/accounting boundary. Inspect relevant inherited N34/N35 code only as needed. Identify concrete bugs/omissions against frozen protocol, line refs, severity, evidence and minimum repair. No design retuning. Honest PASS or FAIL/partial scope.

Read-only source review: DO NOT edit source, commit, adopt, modify owning state/checkpoint/tree/ledgers, modify other studies, acquire driver locks or dispatch executors. No GPU, simulator, provider calls, healthchecks, protected validation/formal results, historical tensor replay, credential files, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md. Superpowers disabled. Official current-login gpt-6-astra only. No API/account fallback or further delegation. Artifacts only {v}. Use existing targeted test evidence, avoid broad repeats. A specific newly discovered concern may receive a small CPU-only reproduction <=300 CPU seconds aggregate, two threads, CUDA disabled; preserve commands/failures. Maximum1800 seconds wall. No source writes for repro; temporary files only output directory.

Review inactive controls and exact unchanged candidate/remainder/scoring/archive/176/11 behavior, identity reset/one-decision expiry/full8 ack/terminal at8/ordered binary64 dot<=0, deterministic geometry/clipping/native signed-zero bytes, direct/detour origin/final survival proof, independent canonical/archive/parent-allocation/selection replay and physical-response Unknown denominators. Audit must reject required missing/corrupt telemetry and cannot trust self-reported PASS. Explicitly assess actual CUDA recomputation validity (without invoking CUDA), actual device/code/build binding and no arithmetic-tolerance weakening. CPU fixtures do not attest actual GPU performance or outcomes.

Write {v/'report-v1.json'} and report-v1.md with source hashes, inspected files, exact checks/findings and unresolved runtime obligations; score=null, promotion=false, target_met=false. If no bug found, state precise reviewed scope and do not claim native execution or full goal. Stop after report.'''
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(a/'turns/001152/implementation/executor-launch-v1.py').read_text().replace('n36-implementation-executor-process-v1','n36-independent-review-executor-process-v1').replace('3600','1800')
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
 pr=read(v/'executor-process-v1.json');rec={'status':'CPU_SOURCE_REVIEW_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':str(wt),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False}
 next_step='Monitor exact N36 independent CPU source reviewer. Reconcile exit/report and root release/accounting review before adoption; no GPU dispatch without separately frozen runtime/accounting release. Clear historical checkpoint in_flight_executor alias using retained terminal record; do not replay implementation.'
 for obj in [s,c]:obj.update(n36_implementation_review=rec,in_flight_executor=rec,phase='N36_CPU_SOURCE_REVIEW_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec;t['nodes']['15.6'].update(status='running',result='CPU_SOURCE_REVIEW_RUNNING_NO_GPU',implementation_review=rec)
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'candidate_source':candidate,'driver':ds['driver'],'coordinator':ds['process'],'executor':rec,'active_controller':None,'new_gpu_dispatches':0,'ledger_prefixes':prior['ledger_prefixes'],'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'completed':'Verified exact handoff/authority, live driver/coordinator identity, prior normal completion and unchanged private ledger; dispatched bounded official gpt-6-astra independent CPU source review. Reconciled stale checkpoint implementation handle alias against terminal record.','next_action':next_step,'unresolved':['Independent source/native audit review','Root controller/accounting boundary review','Runtime/accounting release and fresh Dev','Original validation/formal/required ablation evidence'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(rec))
