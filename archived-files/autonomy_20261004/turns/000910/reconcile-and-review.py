import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/000910').resolve();old=(a/'turns/000907/n35-audit-repair').resolve();v=o/'n35-audit-repair-review'
R=lambda p:json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def verify(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
now=datetime.datetime.now(datetime.timezone.utc);ds=R(a/'driver-status.json');assert ds['turn']==910
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks']
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert R(a/'turns/000909/receipt.json')['exit']==0
for pid in [2569906,2569907,2303352]:assert not pathlib.Path(f'/proc/{pid}').exists()
assert R(old/'executor-exit-v1.json')['exit']==0
report=R(old/'report-v1.json');auth=R(old/'authority-v1.json');work=pathlib.Path(auth['worktree']);base=auth['source'];commit=report['final_commit']
assert report['disposition']=='CPU_REPAIRED_PENDING_INDEPENDENT_REVIEW'
verify(report['authority'])
for key in ['protocol','accounting','user_authority','independent_review']:verify(auth[key])
for item in report['tests']:verify(item['log'])
for item in report['changed_files']:
 assert hashlib.sha256((work/item['path']).read_bytes()).hexdigest()==item['sha256']
for name,digest in report['unchanged_scientific_and_recording_files'].items():
 assert hashlib.sha256((work/name).read_bytes()).hexdigest()==digest
for key in ['required_continuation_context','completion_contract']:verify(R(a/'handoff-v2.json')[key])
for name,r in auth['ledger_prefixes'].items():
 b=(w/'data'/name).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==base
assert subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()==commit
assert not subprocess.check_output(['git','-C',str(work),'status','--porcelain','--untracked-files=no'],text=True).strip()
write(o/'terminal-reconciliation-v1.json',dict(schema='n35-review-terminal-reconciliation-v1',at=now.isoformat(),source=base,isolated_commit=commit,review=ref(old/'report-v1.json'),exit=ref(old/'executor-exit-v1.json'),old_handles_absent=True,ledger_prefixes=auth['ledger_prefixes'],disposition='REPAIR_DELIVERED_PENDING_INDEPENDENT_REVIEW',blocking_issues=['N35-IR-001','N35-IR-002'],source_adopted=False,gpu_dispatched=False,target_met=False))
v.mkdir(exist_ok=False)
ra=dict(schema='n35-audit-repair-authority-v1',at=now.isoformat(),node_id='15.5',user_authority=auth['user_authority'],source=base,base_implementation_commit=commit,worktree=str(work),protocol=auth['protocol'],accounting=auth['accounting'],independent_review=ref(old/'report-v1.json'),prior_implementation_review=auth['independent_review'],review_markdown=ref(old/'report-v1.md'),terminal_reconciliation=ref(o/'terminal-reconciliation-v1.json'),ledger_prefixes=auth['ledger_prefixes'],scope='Independent CPU delta review of N35-IR-001/002 repair; no edits/adoption/GPU.',output_directory=str(v),gpu_authorized=False,source_edits_authorized=False,wall_cap_seconds=1800)
write(v/'authority-v1.json',ra)
(v/'executor-prompt-v1.txt').write_text(f"""You are the independent CPU delta reviewer for explicitly authorized Arbor node15.5, not a coordinator. Read/hash verify {v/'authority-v1.json'} and direct references. Review isolated final commit {commit} against base c3730e5287fe659dffc95c40bf6d8b7ba95d1da9 in {work}. Read the original independent review blockers and repair report. Concentrate on changed lifecycle/native audit code and changed tests, actual recorder/Main reset and acknowledgement semantics. Establish whether N35-IR-001 and N35-IR-002 are fixed without weakening fail-closed evidence or rejecting legitimate production paths. Check termination/truncation partial/full prefixes, ordered automatic resets, returned outcomes, acknowledgement adjacency, missing/duplicate/misplaced resets, extra/missing epochs and premature resets. Verify source/log hashes and unchanged scientific files. Use existing final 22-case evidence; only run narrowly targeted CPU tests for specific unresolved concerns, no broad suite repeats. Do not recursively rebuild old provenance. Write report-v1.json and report-v1.md under {v} with PASS/BLOCKED disposition, issue IDs with file/line evidence, exact source/protocol hashes, test evidence and limitations, and remaining installed runtime/release obligations. CPU only; CUDA_VISIBLE_DEVICES empty, PYTHONDONTWRITEBYTECODE=1 and bounded threads. Source read-only; no commits/adoption/state/ledger/resource changes, GPU query/episode, native simulator, protected validation/formal access, external messages or delegation. Write only review artifacts and CPU fixtures under {v}. Only current official current-login gpt-6-astra, no API-key/alternate provider/account/Poe/credential reads. Never read prohibited 2026-08-10-eds-qd-stage-guidance-transition-design.md. Superpowers disabled. Read applicable AGENTS. Limit source searches to changed files/direct dependencies. Scientific score null; PASS does not authorize GPU or scientific promotion. Complete within1800s with useful report.""")
wrapper=(old/'executor-launch-v1.py').read_text().replace('n35-audit-repair-executor-process-v1','n35-audit-repair-review-executor-process-v1')
(v/'executor-launch-v1.py').write_text(wrapper)
sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
with runner.locked(w/'data/qd-ed-state.lock'):
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=runner.read_state(sp);c=R(cp);t=R(tp)
 assert s['n35_audit_repair']['process_record']==ref(old/'executor-process-v1.json')
 assert not s.get('current_owned_workers')
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before'))
 closed=dict(s['n35_audit_repair']);closed.update(status='CPU_REPAIRED_PENDING_INDEPENDENT_REVIEW',executor_exited=True,exit=ref(old/'executor-exit-v1.json'),report=ref(old/'report-v1.json'),terminal_reconciliation=ref(o/'terminal-reconciliation-v1.json'),live_handles=[])
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=work,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; do not retry'
 pr=R(v/'executor-process-v1.json');rec=dict(status='CPU_AUDIT_REPAIR_REVIEW_RUNNING',node_id='15.5',authority=ref(v/'authority-v1.json'),process_record=ref(v/'executor-process-v1.json'),handles={k:pr[k] for k in ['wrapper','executor']},worktree=str(work),output_directory=str(v),gpu_authorized=False,source_edits_authorized=False)
 next_step='Monitor exact N35 independent audit repair reviewer; reconcile report/exit and decide source acceptance before installed runtime/release preparation. No GPU or protected access.'
 for obj in [s,c]:obj.update(n35_audit_repair=closed,n35_audit_repair_review=rec,in_flight_executor=rec,in_flight_executors=[rec],next_action=next_step,updated_at=now.isoformat())
 c.update(inflight_executor=rec,inflight_executors=[rec])
 t['nodes']['15.5'].update(status='running',result='CPU_AUDIT_REPAIR_DELIVERED_REVIEW_RUNNING_NO_GPU',audit_repair=closed,audit_repair_review=rec)
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
 write(o/'repair-dispatch-v1.json',dict(at=now.isoformat(),executor=rec,next_step=next_step,target_met=False))
print(json.dumps(rec))
