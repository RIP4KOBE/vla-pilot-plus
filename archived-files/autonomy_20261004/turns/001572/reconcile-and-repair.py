import json,pathlib,hashlib,subprocess,datetime,os,time,fcntl,yaml
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001572'; P=A/'turns/001569/independent-g7-review'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,v):
 t=p.with_suffix('.tmp-1572');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def ident(pid):
 s=pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
now=datetime.datetime.now(datetime.timezone.utc).isoformat();old=json.loads((A/'turns/001571/operational-summary-v1.json').read_text());r=json.loads((P/'report-v1.json').read_text());E=pathlib.Path(r['worktree'])
assert not os.path.lexists(A/'STOP') and not os.path.lexists(A.resolve()/'STOP')
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert json.loads((P/'exit-v1.json').read_text())['exit']==0
assert all(not pathlib.Path('/proc',str(x['pid'])).exists() for x in old['live_handles'].values())
assert r['decision']=='FAIL' and r['findings'][0]['id']=='G7-R1'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip()==r['source']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=E,text=True).strip()
for v in r['source_files'].values(): assert ref(pathlib.Path(v['path']))==v
for v in old['ledger_prefixes'].values(): assert ref(pathlib.Path(v['path']))==v
for test in r['tests']: assert ref(pathlib.Path(test['evidence']['path']))==test['evidence']
driver=ident(old['driver']['pid']); assert driver['start_ticks']==old['driver']['start_ticks'] and driver['boot_id']==old['driver']['boot_id']
review=dict(schema='g7-independent-review-terminal-reconciliation-v1',at=now,report=ref(P/'report-v1.json'),exit=ref(P/'exit-v1.json'),source=r['source'],decision='FAIL_ACCEPTED_G7_R1',source_and_test_hashes_verified=True,private_ledgers_unchanged=True,old_handles_absent=True,finding=r['findings'][0],source_approved=False,release_enabled=False,target_met=False)
put(T/'terminal-review-v1.json',review)
O=T/'g7-r1-repair';O.mkdir(exist_ok=False)
auth=dict(schema='g7-r1-bounded-repair-authority-v1',at=now,node_id='15.6',source=r['source'],worktree=str(E),failed_review=ref(P/'report-v1.json'),reconciliation=ref(T/'terminal-review-v1.json'),standing_authority=ref(A/'user-authorization-v1.json'),gpu_authorized=False,source_edits_authorized=True,release_enabled=False,timeout_seconds=1200,deadline='2026-10-11T11:13:13Z',scope='Repair G7-R1 only: canonical required module/source/digest and compiled identity bindings; focused CPU regressions. No scientific changes or graph refresh.')
put(O/'authority-v1.json',auth)
(O/'prompt.txt').write_text(f'''Continue explicitly authorized Arbor as bounded executor for existing node 15.6. Read {O/'authority-v1.json'} and failed independent report {P/'report-v1.json'}. Start from exact isolated HEAD {r['source']}. Repair confirmed G7-R1 only: bind required engineering/release/accounting/stop module names to canonical source paths and frozen digests in both loaded phases, and corresponding module/path/digest executable tuples in both execution phases. Preserve explicitly supported worker __main__ identity and all existing audits. Use minimal appropriate changes in worker/source verifier and focused tests/fixture only if needed. Do not weaken checks or alter scientific algorithms, configuration, thresholds, protocol, or frozen cohort. Add negative tests for source substitution and omitted compiled coverage; retain existing positive lifecycle, affected receipt/restart cases. Run bounded CPU tests only, CUDA_VISIBLE_DEVICES empty; no broad repeats. Preserve failed test logs, including prior review's v1 harness failure and v2 confirmed acceptance defect. Commit narrowly scoped tested changes in this isolated branch. No GPU, evaluation, graph/proof refresh, owner source adoption, root release, owner state/tree/ledger writes, foreign study writes, cloud, credential reads, external provider calls, protected validation/formal access, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, Superpowers or further delegation. Existing official gpt-6-astra session only. Check canonical STOP and deadline before work; finish within 1200 seconds. Write report-v1.json under {O} containing starting/final commits, changed paths/file hashes, exact tests/log refs, retained failures, scope and unresolved obligations. This is engineering evidence only; scientific_success/target_met/release_enabled false. Independent corrected-source review and affected graph/B5 refresh remain coordinator obligations. Do not recursively reconstruct provenance.''')
(O/'run-executor.py').write_text((P/'run-executor.py').read_text())
with (O/'wrapper.log').open('wb') as log:
 proc=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python',str(O/'run-executor.py')],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(pid=proc.pid,at=now))
for _ in range(30):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=json.loads((O/'process-v1.json').read_text());operation=dict(status='G7_R1_BOUNDED_CPU_REPAIR_RUNNING',source=r['source'],worktree=str(E),authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=h['wrapper'],executor=h['executor'],gpu_authorized=False,source_edits_authorized=True,release_enabled=False)
nextstep='Monitor turn001572 G7-R1 CPU repair by exact boot/start identity; reconcile terminal source/tests and obtain bounded independent corrected-source review before affected graph/B5 refresh. No GPU release or scientific promotion.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,isy in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if isy else json.loads(path.read_text());d['n36_engineering_g7_independent_review'].update(status='TERMINAL_FAIL_G7_R1_ROOT_ACCEPTED',terminal_review=ref(T/'terminal-review-v1.json'),live_handles=[]);d['n36_engineering_g7_r1_repair']=operation;d['active_executor']=operation;d['next_action']=nextstep;d['updated_at']=now
  if isy:
   tmp=path.with_suffix('.tmp-1572');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));tmp.replace(path)
  else:put(path,d)
 tree=json.loads((C/'idea_tree.json').read_text());tree['nodes']['15.6'].update(result='G7_REVIEW_FAIL_R1_CPU_REPAIR_RUNNING',insight='Independent review confirmed required receipt names can alias contract.py and omit compiled identities. Source blocked; narrow isolated repair running, no GPU/scientific evidence.',g7_r1_repair=operation);put(C/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1572,owner_source=old['owner_source'],scientific_source=old['scientific_source'],isolated_executor_source_observed=r['source'],live_handles={k:h[k] for k in ['wrapper','executor']},driver=driver,stop_exists=False,deadline=auth['deadline'],ledger_prefixes=old['ledger_prefixes'],ledgers_unchanged=True,budget_snapshot=old['budget_snapshot'],terminal_reconciliation=ref(T/'terminal-review-v1.json'),executor_authority=ref(O/'authority-v1.json'),completed_work=['Verified bound authority/handoff and live driver, state/checkpoint/isolation and unchanged private ledger prefixes.','Reconciled normal independent-review termination, exact source/test hashes and confirmed G7-R1 FAIL; retained all evidence.','Launched one bounded official Codex gpt-6-astra CPU repair in existing isolated worktree; owning state/checkpoint/tree updated.'],next_bounded_step=nextstep,unresolved_evidence=['G7-R1 repair and independent source review pending; no source approval or GPU release.','Affected graph/B5 refresh and production readiness outstanding.','Original validation/formal/required ablation goal remains unevidenced.'],target_met=False)
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps(operation,indent=2))
