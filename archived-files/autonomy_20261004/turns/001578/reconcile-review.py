import json,pathlib,hashlib,datetime,subprocess,os,fcntl,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001578';R=A/'turns/001576/independent-g7-r1-review';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def identity(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';o=dict(h)
 if p.exists():
  fields=p.read_text().rsplit(')',1)[1].split();o.update(state=fields[0],observed_start_ticks=int(fields[19]),identity_matches=h['boot_id']==boot and h['start_ticks']==int(fields[19]));o['live']=o['identity_matches'] and fields[0]!='Z'
 else:o.update(state=None,observed_start_ticks=None,identity_matches=False,live=False)
 return o
old=json.loads((A/'turns/001577/operational-summary-v1.json').read_text());report=json.loads((R/'report-v1.json').read_text());ex=json.loads((R/'exit-v1.json').read_text());proc=json.loads((R/'process-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert ex['exit']==0 and not ex['timeout'];assert report['status']=='PASS'
handles={k:identity(proc[k]) for k in ['wrapper','executor']};assert not any(x['live'] for x in handles.values())
assert (R/'report-v1.sha256').read_text().split()[0]==ref(R/'report-v1.json')['sha256']
verified=[]
for group in ['source_files','unaffected_reviewed_source_files']:
 for v in report[group].values():assert ref(pathlib.Path(v['path']))==v;verified.append(v['path'])
for k in ['authority','implementation_report','prior_independent_review','standing_authority','terminal_reconciliation']:
 v=report[k];assert ref(pathlib.Path(v['path']))==v
for test in report['tests']:
 for k in ['evidence','result_record']:
  v=test[k];assert ref(pathlib.Path(v['path']))==v
for v in old['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))==v
E=pathlib.Path(report['worktree']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip()==report['source']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=E,text=True).strip()
prior={k:identity(v) for k,v in old['prior_cohort_handles'].items()};assert not any(x['live'] for x in prior.values())
v=old['prior_controller_result'];assert ref(pathlib.Path(v['path']))==v
stops=[A/'STOP',pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP')];stop=any(os.path.lexists(p) for p in stops)
review=dict(schema='n36-g7-r1-root-terminal-review-v1',at=now,status='PASS_BOUNDED_SOURCE_REVIEW',source=report['source'],report=ref(R/'report-v1.json'),exit=ref(R/'exit-v1.json'),handles=handles,source_and_direct_evidence_hashes_verified=True,private_ledgers_unchanged=True,focused_tests='4 passed, 14 deselected',scope=report['source_approval_scope'],remaining_obligations=report['minimal_affected_proof_graph_B5_refresh_obligations'],release_enabled=False,target_met=False)
put(T/'terminal-review-v1.json',review)
nextstep='Refresh only G7-source-affected equivalence proof/manifests/disabled graph roots for b8d6b981, reusing explicitly compatible unchanged evidence; obtain fresh exact-source B5 review before owner adoption or any detached GPU release. Preserve all historical roots and failed tests.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,is_yaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());d['n36_engineering_g7_r1_independent_review'].update(status='TERMINAL_PASS_BOUNDED_SOURCE_ROOT_ACCEPTED',terminal_review=ref(T/'terminal-review-v1.json'),live_handles=[]);d['next_action']=nextstep;d['updated_at']=now
  if is_yaml:
   q=p.with_suffix('.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));q.replace(p)
  else:put(p,d)
 p=C/'idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(result='G7_R1_SOURCE_REVIEW_PASS_AFFECTED_GRAPH_B5_PENDING',insight='Independent review closes G7-R1 on b8d6b981; four focused CPU tests passed. Source approval only; exact-source affected proof/graph refresh and B5 remain required. No scientific success or GPU release.');put(p,d)
summary=dict(old);summary.update(at=now,turn=1578,live_handles={},reviewer_terminal_handles=handles,driver=identity(old['driver']),stop_exists=stop,terminal_reconciliation=ref(T/'terminal-review-v1.json'),review_report_exists=True,review_exit_exists=True,prior_cohort_handles=prior,completed_work=['Verified bound authority, current driver/reviewer identities, owning ledger prefixes and prior controller terminal evidence.','Reconciled reviewer exit 0; verified report, exact source and direct test/source evidence hashes; accepted bounded G7-R1 source PASS with four focused CPU tests.','Updated owning state/checkpoint/tree with exact-source graph and B5 obligations; no GPU dispatch or source adoption.'],next_bounded_step=nextstep,unresolved_evidence=report['blockers']+['Original validation/formal/required ablation completion remains unproven.'])
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps({'review':ref(T/'terminal-review-v1.json'),'summary':ref(T/'operational-summary-v1.json'),'next':nextstep},indent=2))
