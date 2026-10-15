import json,pathlib,hashlib,datetime,subprocess,os,fcntl,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001582';R=A/'turns/001579/g7-affected-graph-refresh';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def identity(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';o=dict(h)
 if p.exists():
  f=p.read_text().rsplit(')',1)[1].split();o.update(state=f[0],observed_start_ticks=int(f[19]),identity_matches=h['boot_id']==boot and h['start_ticks']==int(f[19]));o['live']=o['identity_matches'] and f[0]!='Z'
 else:o.update(state=None,observed_start_ticks=None,identity_matches=False,live=False)
 return o
old=json.loads((A/'turns/001581/operational-summary-v1.json').read_text());completion=json.loads((R/'completion-v1.json').read_text());report=json.loads(pathlib.Path(completion['canonical_final_report']['path']).read_text());ex=json.loads((R/'exit-v1.json').read_text());proc=json.loads((R/'process-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert ex['exit']==0 and not ex['timeout'];assert report['status']=='PREPARATION_COMPLETE_PENDING_INDEPENDENT_B5'
handles={k:identity(proc[k]) for k in ['wrapper','executor']};assert not any(x['live'] for x in handles.values())
assert identity(old['driver'])['live'];assert not any(identity(h)['live'] for h in old['prior_cohort_handles'].values())
verified={}
def verify(v):
 if isinstance(v,dict):
  if 'path' in v and 'sha256' in v:
   p=pathlib.Path(v['path']);assert '2026-08-10-eds-qd-stage-guidance-transition-design.md' not in str(p)
   actual=ref(p);assert actual['sha256']==v['sha256'],str(p)
   if 'bytes' in v:assert actual['bytes']==v['bytes'],str(p)
   verified[str(p)]=actual
  else:
   for x in v.values():verify(x)
 elif isinstance(v,list):
  for x in v:verify(x)
verify(completion);verify(json.loads((R/'final/artifact-hash-seal-v1.json').read_text()));verify(report['outputs']);verify(report['roots']);verify(report['retained_failed_preparation_attempt'])
for v in old['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))==v
E=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip()==report['source'];assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=E,text=True).strip()
assert all(v.get('pass') is True for v in report['checks'].values());assert report['release_enabled'] is False and report['source_adopted'] is False
stop=any(os.path.lexists(p) for p in [A/'STOP',pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP')]);assert not stop
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
review=dict(schema='n36-g7-refresh-root-terminal-reconciliation-v1',at=now,status='PREPARATION_RECONCILED_INDEPENDENT_B5_PENDING',source=report['source'],worktree=str(E),completion=ref(R/'completion-v1.json'),report=completion['canonical_final_report'],b5_inputs=completion['canonical_independent_b5_inputs'],exit=ref(R/'exit-v1.json'),terminal_handles=handles,verified_direct_artifacts=list(verified.values()),reported_checks=len(report['checks']),reported_checks_all_pass=True,independent_semantic_review=False,failed_first_attempt=report['retained_failed_preparation_attempt'],private_ledgers_unchanged=True,release_enabled=False,source_adopted=False,target_met=False)
put(T/'terminal-reconciliation-v1.json',review)
nextstep='Obtain independent B5 review binding b8d6b981, canonical turn001579 final report, refreshed roots and accepted G7 source review. No GPU/source adoption until review and separate prospective release gates pass.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,is_yaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());d['n36_engineering_g7_affected_graph_refresh'].update(status='TERMINAL_PREPARATION_RECONCILED_B5_PENDING',terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),live_handles=[],report=completion['canonical_final_report']);d['next_action']=nextstep;d['updated_at']=now
  if is_yaml:
   q=p.with_suffix('.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));q.replace(p)
  else:put(p,d)
 p=C/'idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(result='G7_AFFECTED_GRAPH_RECONCILED_B5_PENDING',insight='Finished exact-source refresh reconciled; direct sealed artifact hashes verified, failed preparation retained. Independent B5 and prospective release remain pending; no scientific success.');put(p,d)
summary=dict(old);summary.update(at=now,turn=1582,live_handles={},driver=identity(old['driver']),stop_exists=stop,terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),completed_work=['Verified bound authority, live driver, absent prior cohort/executor identities and unchanged private ledgers.','Reconciled canonical final refresh report and direct sealed artifact hashes on b8d6b981; retained failed first attempt.','Updated owning state/checkpoint/node15.6 to terminal preparation awaiting independent B5.'],next_bounded_step=nextstep,unresolved_evidence=['Independent B5, source/accounting adoption and detached release remain pending.','Original validation/formal/required ablations remain unestablished.']);put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps(dict(verified_artifacts=len(verified),reported_checks=len(report['checks']),reconciliation=ref(T/'terminal-reconciliation-v1.json'))))
