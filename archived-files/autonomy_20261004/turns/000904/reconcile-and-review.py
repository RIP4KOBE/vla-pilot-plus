import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/000904').resolve();old=(a/'turns/000886/n35-cpu-implementation').resolve();v=o/'n35-implementation-review'
R=lambda p:json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def verify(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
now=datetime.datetime.now(datetime.timezone.utc);ds=R(a/'driver-status.json');assert ds['turn']==904
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks']
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert R(a/'turns/000903/receipt.json')['exit']==0
for pid in [2470968,2470970,2303352]:assert not pathlib.Path(f'/proc/{pid}').exists()
assert R(old/'executor-exit-v1.json')['exit']==0
report=R(old/'report-v1.json');auth=R(old/'authority-v1.json');work=pathlib.Path(report['worktree']);base=report['base_commit'];commit=report['commit']
for r in [report['authority'],report['authority_verification'],auth['protocol'],auth['accounting'],auth['root_review'],auth['independent_review'],auth['user_authority']]:verify(r)
handoff=R(a/'handoff-v2.json')
for k in ['required_continuation_context','completion_contract']:verify(handoff[k])
for name,r in auth['ledger_prefixes'].items():
 b=(w/'data'/name).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==base
assert subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()==commit
assert not subprocess.check_output(['git','-C',str(work),'status','--porcelain','--untracked-files=no'],text=True).strip()
files=subprocess.check_output(['git','-C',str(work),'diff','--name-only',base,commit],text=True).splitlines()
assert sorted(files)==sorted(x['path'] for x in report['changed_files'])
for r in report['changed_files']:
 p=work/r['path'];assert ref(p)['sha256']==r['sha256'];assert hashlib.sha256(subprocess.check_output(['git','-C',str(work),'show',commit+':'+r['path']])).hexdigest()==r['sha256']
verify(report['tests']['inventory'])
for r in report['tests']['commands_results']:verify(r['log'])
reconciliation=dict(schema='n35-implementation-terminal-reconciliation-v1',at=now.isoformat(),turn=904,source=base,isolated_commit=commit,executor_exit=ref(old/'executor-exit-v1.json'),report=ref(old/'report-v1.json'),old_handles_absent=True,driver=ds,prior_turn_status='completed_turn',ledger_prefixes=auth['ledger_prefixes'],changed_files_verified=len(files),test_artifact_hashes_verified=True,reported_n35_passing_coverage=130,coverage_caveat='Overlapping focused CPU runs; no independent implementation acceptance or installed runtime proof.',disposition='IMPLEMENTATION_EXITED_REVIEW_REQUIRED',source_adopted=False,gpu_dispatched=False,target_met=False)
write(o/'terminal-reconciliation-v1.json',reconciliation)
v.mkdir(exist_ok=False)
review_auth=dict(schema='n35-independent-implementation-review-authority-v1',at=now.isoformat(),node_id='15.5',user_authority=auth['user_authority'],source=base,implementation_commit=commit,worktree=str(work),protocol=auth['protocol'],accounting=auth['accounting'],implementation_authority=ref(old/'authority-v1.json'),implementation_report=ref(old/'report-v1.json'),terminal_reconciliation=ref(o/'terminal-reconciliation-v1.json'),root_protocol_acceptance=auth['root_review'],ledger_prefixes=auth['ledger_prefixes'],scope='Independent CPU-only read-only implementation/native-audit/controller review; write review artifacts and targeted CPU reproduction fixtures only in output directory. No source/state/ledger changes or GPU.',output_directory=str(v),gpu_authorized=False,source_edits_authorized=False,wall_cap_seconds=1800)
write(v/'authority-v1.json',review_auth)
prompt=f'''You are an independent CPU implementation reviewer for the explicitly authorized ongoing Arbor task, node15.5, not a coordinator. Review exact isolated commit {commit} in {work} against frozen N35 protocol. Read and hash-verify {v/'authority-v1.json'} and its direct references. Write report-v1.json and report-v1.md in {v}, with disposition PASS or BLOCKED, blocking_issues with concrete file/line evidence, nonblocking obligations, source/protocol hashes and tests/limitations. No source edits, commits, merge/adoption, state/ledger changes, resource reservations, GPU, native simulator episodes, protected validation/formal access, external messages or further delegation. Only current official gpt-6-astra session; no API-key/alternate providers/accounts, Poe or credential reads. Superpowers disabled. Never read 2026-08-10-eds-qd-stage-guidance-transition-design.md. Limit searches to named changed source/test/config files and direct source dependencies; no recursive study/docs/data/results searches. Bound protocol is sufficient scientific authority, do not rebuild historical provenance.

Audit all critical paths end to end: direct occurrence transport through archive dedup/clone/ties and native selection; no content-alias ancestry origin; actual decoder and post-adapter.step returned acknowledgement identity; eight nonterminal positive-command acknowledgements; immediate-boundary jaw/target/Stage/provider/tracker conditions and reset/exception paths; one-time consumption/all-ten-round latch/expiry and no memory-origin rearm; unchanged template coordinates/other15 and N34 fallback; independent lifecycle/native audits, all-arm same-process verifier and fail-closed missing evidence; C0/Q0/N34 compatibility; real runner/worker argument/wiring/import semantics; detached release DAG/source-runtime closure; atomic1840s reservation, separate bounded healthcheck accounting, both cumulative caps and protected reserves; no replay and quadruple futility, invalidity stop, STOP/deadline drain. Verify test claims against recorded logs and identify mocking blind spots. Read actual implementation, not just report. CPU tests already have overlapping passing coverage; do not rerun broad suites without a specific unresolved concern. Targeted CPU reproduction tests allowed only as needed, CUDA_VISIBLE_DEVICES empty, PYTHONDONTWRITEBYTECODE=1, bounded threads and fixtures under {v}. Preserve observed failures and distinguish implementation acceptance from installed runtime/GPU proof and scientific promotion. Do not approve deficient audits to expedite execution. Complete within1800s; record useful partial review if needed. No source adoption or GPU authority is granted by PASS.
'''
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(a/'turns/000885/n35-protocol-review/executor-launch-v1.py').read_text().replace(str(w),str(work)).replace('n35-protocol-review-executor-process-v1','n35-implementation-review-executor-process-v1').replace('1200','1800').replace("CUDA_VISIBLE_DEVICES=''","CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'")
(v/'executor-launch-v1.py').write_text(wrapper)
sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
with runner.locked(w/'data/qd-ed-state.lock'):
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=runner.read_state(sp);c=R(cp);t=R(tp)
 assert s['n35_cpu_implementation']['process_record']==ref(old/'executor-process-v1.json')
 assert not s.get('current_owned_workers')
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before'))
 closed=dict(s['n35_cpu_implementation']);closed.update(status='CPU_IMPLEMENTED_PENDING_INDEPENDENT_REVIEW',executor_exited=True,exit=ref(old/'executor-exit-v1.json'),report=ref(old/'report-v1.json'),commit=commit,terminal_reconciliation=ref(o/'terminal-reconciliation-v1.json'),live_handles=[])
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=work,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; do not retry'
 pr=R(v/'executor-process-v1.json');rec=dict(status='CPU_IMPLEMENTATION_REVIEW_RUNNING',node_id='15.5',authority=ref(v/'authority-v1.json'),process_record=ref(v/'executor-process-v1.json'),handles={k:pr[k] for k in ['wrapper','executor']},worktree=str(work),output_directory=str(v),gpu_authorized=False,source_edits_authorized=False)
 next_step='Monitor exact independent N35 CPU implementation reviewer; reconcile review/exit before root acceptance, source adoption and separately frozen runtime release. No GPU or protected access. Do not repeat broad CPU tests without new concern.'
 for obj in [s,c]:obj.update(n35_cpu_implementation=closed,n35_implementation_review=rec,in_flight_executor=rec,in_flight_executors=[rec],next_action=next_step,updated_at=now.isoformat())
 c.update(inflight_executor=rec,inflight_executors=[rec])
 t['nodes']['15.5'].update(status='running',result='CPU_IMPLEMENTED_INDEPENDENT_REVIEW_RUNNING_NO_GPU',cpu_implementation=closed,implementation_review=rec)
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
 write(o/'review-dispatch-v1.json',dict(at=now.isoformat(),reconciliation=ref(o/'terminal-reconciliation-v1.json'),executor=rec,next_step=next_step,target_met=False))
print(json.dumps(rec))
