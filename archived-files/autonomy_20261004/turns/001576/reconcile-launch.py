import json,pathlib,hashlib,subprocess,datetime,os,time,fcntl,yaml
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001576'; P=A/'turns/001572/g7-r1-repair'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
r=json.loads((P/'report-v1.json').read_text());old=json.loads((A/'turns/001575/operational-summary-v1.json').read_text()); E=pathlib.Path(r['worktree']);now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not (T/'independent-g7-r1-review/process-v1.json').exists()
assert not os.path.lexists(A/'STOP') and datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert json.loads((P/'exit-v1.json').read_text())['exit']==0
assert all(not pathlib.Path('/proc',str(x['pid'])).exists() for x in old['live_handles'].values())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip()==r['final_commit']
for v in r['changed_files'].values(): assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
for v in old['ledger_prefixes'].values(): assert ref(pathlib.Path(v['path']))==v
for test in r['tests']:
 if 'evidence' in test: assert ref(pathlib.Path(test['evidence']['path']))==test['evidence']
changed=subprocess.check_output(['git','diff','--name-only',r['starting_commit'],r['final_commit']],cwd=E,text=True).splitlines();assert sorted(changed)==sorted(r['changed_paths'])
review=dict(schema='g7-terminal-reconciliation-v1',at=now,report=ref(P/'report-v1.json'),exit=ref(P/'exit-v1.json'),source=r['final_commit'],changed_paths=changed,source_hashes_verified=True,test_log_hashes_verified=True,private_ledgers_unchanged=True,old_handles_absent=True,independent_review_required=True,release_enabled=False,target_met=False)
put(T/'terminal-reconciliation-v1.json',review)
O=T/'independent-g7-r1-review';O.mkdir(exist_ok=True)
auth=dict(schema='g7-independent-source-review-authority-v1',at=now,node_id='15.6',source=r['final_commit'],worktree=str(E),implementation_report=ref(P/'report-v1.json'),reconciliation=ref(T/'terminal-reconciliation-v1.json'),standing_authority=ref(A/'user-authorization-v1.json'),gpu_authorized=False,source_edits_authorized=False,release_enabled=False,timeout_seconds=1200,deadline='2026-10-11T11:13:13Z')
put(O/'authority-v1.json',auth)
(O/'prompt.txt').write_text(f'''Continue the explicitly invoked Arbor task as an independent read-only source reviewer for node15.6. Read {O/'authority-v1.json'} and {P/'report-v1.json'}. Review exact commit {r['final_commit']} against {r['starting_commit']} in this isolated worktree. This is a bounded G7 implementation review, not scientific evaluation or general provenance reconstruction. Verify production public lifecycle/deep-closure dispatch, chronology, full charge retention, receipt/source bindings, fail-closed STOP, and whether fixture corrections actually establish affected tests without bypassing acceptance. Read the two-file repair diff and failed review at /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/../autonomy_20261004/turns/001569/independent-g7-review/report-v1.json. Verify closure of G7-R1 required loaded module names/canonical paths/digests and compiled tuples in both phases, including the __main__ positive case. Reuse prior unaffected review evidence; run only necessary focused CPU tests, CUDA_VISIBLE_DEVICES empty. Identify concrete defects with file/line evidence. Preserve every failed test. No code changes, graph refresh, owner state/tree/ledger writes, GPU dispatch, source adoption, external API, credentials access, protected validation/formal access, or prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md. Superpowers disabled. No delegation. Use existing official gpt-6-astra session only. Check STOP/deadline before work. Write hash-bound report-v1.json under {O} with PASS or FAIL scoped to this source, evidence, blockers, and minimal affected proof/graph/B5 refresh obligations. Prior B5 cannot approve this source; your report grants no GPU release or scientific success. Do not recursively rebuild provenance or repeat broad tests. Finish within 1200 seconds.''')
(O/'run-executor.py').write_text((A/'turns/001556/independent-b5/run-executor.py').read_text())
with (O/'wrapper.log').open('wb') as log:
 proc=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python',str(O/'run-executor.py')],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(pid=proc.pid,at=now))
for _ in range(30):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
handles=json.loads((O/'process-v1.json').read_text()); operation=dict(status='INDEPENDENT_G7_SOURCE_REVIEW_RUNNING',source=r['final_commit'],worktree=str(E),authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=handles['wrapper'],executor=handles['executor'],gpu_authorized=False,release_enabled=False,source_edits_authorized=False)
nextstep='Monitor turn001576 independent G7 source reviewer by boot/start identity; reconcile terminal review before only affected proof/graph/B5 refresh. No owner adoption or GPU release yet; original scientific evidence remains unproven.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,is_yaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if is_yaml else json.loads(path.read_text());d['n36_engineering_g7_r1_repair'].update(status='TERMINAL_CPU_IMPLEMENTATION_RECONCILED_PENDING_REVIEW',source_after=r['final_commit'],terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),live_handles=[]);d['n36_engineering_g7_r1_independent_review']=operation;d['next_action']=nextstep;d['updated_at']=now
  if is_yaml:
   tmp=path.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));tmp.replace(path)
  else:put(path,d)
 tree=json.loads((C/'idea_tree.json').read_text());tree['nodes']['15.6'].update(result='G7_R1_REPAIR_TERMINAL_INDEPENDENT_REVIEW_RUNNING',insight='G7 exact commit and two changed files reconciled; targeted corrected CPU tests documented, private ledgers unchanged. Independent source review required before affected graph refresh or release.');put(C/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1576,owner_source=old['owner_source'],scientific_source=old['scientific_source'],isolated_executor_source_observed=r['final_commit'],live_handles={k:handles[k] for k in ['wrapper','executor']},driver=old['driver'],stop_exists=False,deadline=auth['deadline'],ledger_prefixes=old['ledger_prefixes'],ledgers_unchanged=True,budget_snapshot=old['budget_snapshot'],terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),executor_authority=ref(O/'authority-v1.json'),completed_work=['Verified authority hashes, live driver identity and private ledger prefixes.','Reconciled normal G7 completion, source/file scope and test artifact hashes; retained prior failed test evidence.','Launched one independent read-only G7 source reviewer under official gpt-6-astra; updated owning state/checkpoint/tree.'],next_bounded_step=nextstep,unresolved_evidence=['Independent G7 review and affected graph/B5 refresh pending.','No production readiness, scientific promotion, validation/formal or required ablation completion established.'],target_met=False)
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps(operation,indent=2))
