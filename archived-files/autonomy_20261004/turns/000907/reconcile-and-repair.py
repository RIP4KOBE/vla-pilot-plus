import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/000907').resolve();old=(a/'turns/000904/n35-implementation-review').resolve();v=o/'n35-audit-repair'
R=lambda p:json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def verify(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
now=datetime.datetime.now(datetime.timezone.utc);ds=R(a/'driver-status.json');assert ds['turn']==907
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks']
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert R(a/'turns/000906/receipt.json')['exit']==0
for pid in [2554234,2554235,2303352]:assert not pathlib.Path(f'/proc/{pid}').exists()
assert R(old/'executor-exit-v1.json')['exit']==0
report=R(old/'report-v1.json');auth=R(old/'authority-v1.json');work=pathlib.Path(auth['worktree']);base=auth['source'];commit=auth['implementation_commit']
assert report['disposition']=='BLOCKED' and len(report['blocking_issues'])==2
verify(report['authority'])
for key in ['protocol','accounting','user_authority','implementation_report','root_protocol_acceptance']:verify(auth[key])
for issue in report['blocking_issues']:verify(issue['reproduction']['log'])
for key in ['required_continuation_context','completion_contract']:verify(R(a/'handoff-v2.json')[key])
for name,r in auth['ledger_prefixes'].items():
 b=(w/'data'/name).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==base
assert subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()==commit
assert not subprocess.check_output(['git','-C',str(work),'status','--porcelain','--untracked-files=no'],text=True).strip()
write(o/'terminal-reconciliation-v1.json',dict(schema='n35-review-terminal-reconciliation-v1',at=now.isoformat(),source=base,isolated_commit=commit,review=ref(old/'report-v1.json'),exit=ref(old/'executor-exit-v1.json'),old_handles_absent=True,ledger_prefixes=auth['ledger_prefixes'],disposition='BLOCKED_REPAIR_REQUIRED',blocking_issues=[x['id'] for x in report['blocking_issues']],source_adopted=False,gpu_dispatched=False,target_met=False))
v.mkdir(exist_ok=False)
ra=dict(schema='n35-audit-repair-authority-v1',at=now.isoformat(),node_id='15.5',user_authority=auth['user_authority'],source=base,base_implementation_commit=commit,worktree=str(work),protocol=auth['protocol'],accounting=auth['accounting'],independent_review=ref(old/'report-v1.json'),review_markdown=ref(old/'report-v1.md'),terminal_reconciliation=ref(o/'terminal-reconciliation-v1.json'),ledger_prefixes=auth['ledger_prefixes'],scope='CPU-only isolated audit/reset repair for N35-IR-001 and N35-IR-002. Frozen scientific protocol unchanged. No source adoption/GPU/state/ledger changes.',output_directory=str(v),gpu_authorized=False,source_edits_authorized=True,wall_cap_seconds=1800)
write(v/'authority-v1.json',ra)
(v/'executor-prompt-v1.txt').write_text(f'''You are the isolated CPU repair executor for continuing explicitly authorized Arbor node15.5, not a coordinator. Read and verify {v/'authority-v1.json'} and direct references. Starting commit {commit}, worktree {work}. Repair both independent review blockers N35-IR-001 and N35-IR-002, preserving frozen N35 scientific semantics. Read review JSON/markdown and reproduction tests {old/'test_review_reproductions.py'}. Validate actual ordered automatic-reset, returned-outcome, acknowledgement and memory reset epochs. Require exactly one identity/order-linked terminal reset after a terminal acknowledgement before next boundary/end. Do not weaken reset checks or change scientific thresholds/protocol. Test termination at partial/full prefixes, truncation, missing/duplicate/misplaced resets and relevant lifecycle/native-worker regressions. Preserve original failed logs. Avoid unrelated changes and unnecessary broad test repeats. CPU only: CUDA_VISIBLE_DEVICES empty, PYTHONDONTWRITEBYTECODE=1, bounded threads; no GPU query/episode, runtime installation, protected validation/formal access, source adoption, state/ledger/resource writes, external messages or delegation. Edit only relevant source/tests in isolated worktree, commit a separately reviewable fix. Write report-v1.json and report-v1.md under {v}, with authority/protocol bindings, base/final commit, changed-file hashes, exact test commands/exits/log hashes, limitations and disposition CPU_REPAIRED_PENDING_INDEPENDENT_REVIEW or BLOCKED. Keep scientific score null. Only current-login official gpt-6-astra; no API-key/alternate provider/account or Poe; preserve credentials without reading. Superpowers disabled. Never read prohibited 2026-08-10-eds-qd-stage-guidance-transition-design.md. Read applicable AGENTS. Limit searches to changed paths and direct dependencies, no broad historical/protected searches. Finish within1800s with useful report; no implementation/GPU acceptance claimed by your own tests.''')
wrapper=(old/'executor-launch-v1.py').read_text().replace('n35-implementation-review-executor-process-v1','n35-audit-repair-executor-process-v1')
(v/'executor-launch-v1.py').write_text(wrapper)
sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
with runner.locked(w/'data/qd-ed-state.lock'):
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=runner.read_state(sp);c=R(cp);t=R(tp)
 assert s['n35_implementation_review']['process_record']==ref(old/'executor-process-v1.json')
 assert not s.get('current_owned_workers')
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before'))
 closed=dict(s['n35_implementation_review']);closed.update(status='BLOCKED',executor_exited=True,exit=ref(old/'executor-exit-v1.json'),report=ref(old/'report-v1.json'),terminal_reconciliation=ref(o/'terminal-reconciliation-v1.json'),live_handles=[])
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=work,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; do not retry'
 pr=R(v/'executor-process-v1.json');rec=dict(status='CPU_AUDIT_REPAIR_RUNNING',node_id='15.5',authority=ref(v/'authority-v1.json'),process_record=ref(v/'executor-process-v1.json'),handles={k:pr[k] for k in ['wrapper','executor']},worktree=str(work),output_directory=str(v),gpu_authorized=False,source_edits_authorized=True)
 next_step='Monitor exact N35 audit repair executor; reconcile commit/report/exit, then independently review fixes for N35-IR-001/002 before any adoption/runtime release. No GPU or protected access.'
 for obj in [s,c]:obj.update(n35_implementation_review=closed,n35_audit_repair=rec,in_flight_executor=rec,in_flight_executors=[rec],next_action=next_step,updated_at=now.isoformat())
 c.update(inflight_executor=rec,inflight_executors=[rec])
 t['nodes']['15.5'].update(status='running',result='CPU_IMPLEMENTATION_REVIEW_BLOCKED_AUDIT_REPAIR_RUNNING_NO_GPU',implementation_review=closed,audit_repair=rec)
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
 write(o/'repair-dispatch-v1.json',dict(at=now.isoformat(),executor=rec,next_step=next_step,target_met=False))
print(json.dumps(rec))
