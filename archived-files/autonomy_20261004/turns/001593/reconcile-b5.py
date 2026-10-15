import json,pathlib,hashlib,datetime,subprocess,fcntl,os,yaml
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001593'; P=A/'turns/001591/independent-b5'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 q=p.with_name(p.name+'.tmp-001593'); q.write_text(json.dumps(d,indent=2)+'\n'); os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 p=pathlib.Path('/proc')/str(v['pid'])/'stat'; a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 tick=int(a[19]) if a else None; match=bool(a and tick==v['start_ticks'] and boot==v['boot_id'])
 return {**v,'observed_start_ticks':tick,'state':a[0] if a else None,'identity_matches':match,'live':bool(match and a[0]!='Z')}
old=read(A/'turns/001592/operational-summary-v1.json'); proc=read(P/'process-v1.json'); handles={k:ident(proc[k]) for k in ['wrapper','executor']}; assert not any(v['live'] for v in handles.values())
e=read(P/'exit-v1.json'); assert e['exit']==0 and not e['timeout']
r=read(P/'report-v1.json'); assert r['decision']=='PASS' and r['checks']['failed']==0 and r['checks']['passed']==168
assert (P/'report-v1.sha256').read_text().split()[0]==ref(P/'report-v1.json')['sha256']
checks=[]
for v in [*old['ledger_prefixes'].values(),*r['roots'].values(),*r['evidence_refs'].values(),r['b5_inputs'],r['root_controller_binding_attestation'],r['preparation_report']]:
 a=ref(pathlib.Path(v['path'])); assert all(a[k]==v[k] for k in ('sha256','bytes') if k in v),v['path']; checks.append(a)
wt=pathlib.Path(r['worktree']); source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=wt,text=True).strip(); assert source==old['isolated_executor_source_observed']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=wt,text=True).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==old['owner_source']
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
nextstep='Integrate turn001591 independent B5 PASS into exact closed-schema operational review token per validate_authority, with hash-bound detailed-report provenance. Then separately review protocol acceptance, source/accounting adoption and actual native/provider readiness before detached prospective health/episode release. No scientific promotion or GPU dispatch from preparation PASS alone.'
rec=dict(schema='n36-independent-b5-terminal-reconciliation-v1',at=now,status='TERMINAL_INDEPENDENT_B5_PREPARATION_PASS_ROOT_GATES_PENDING',source=source,report=ref(P/'report-v1.json'),process=ref(P/'process-v1.json'),exit=ref(P/'exit-v1.json'),handles=handles,verified_artifacts=checks,checks_passed=168,outstanding_gates=r['outstanding_gates'],consumer_integration=r['consumer_integration'],source_adopted=False,accounting_adopted=False,release_enabled=False,gpu_dispatch=False,target_met=False)
put(T/'terminal-reconciliation-v1.json',rec)
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if isyaml else read(path)
  assert d['n36_engineering_attested_independent_b5']['process_record_path']==str(P/'process-v1.json')
  d['n36_engineering_attested_independent_b5']['status']=rec['status']; d['n36_engineering_attested_independent_b5_terminal_reconciliation']=ref(T/'terminal-reconciliation-v1.json'); d['next_action']=nextstep; d['updated_at']=now
  if isyaml:
   q=path.with_name(path.name+'.tmp-001593'); q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True)); os.replace(q,path)
  else: put(path,d)
 tree=read(C/'idea_tree.json'); tree['nodes']['15.6'].update(result=rec['status'],insight='Independent B5 preparation PASS at exact b8d6b981 source, 168 checks; terminal exit and immediate root/evidence hashes verified. Operational review token integration, protocol acceptance, source/accounting adoption, native readiness and prospective release remain pending. No scientific success or GPU release inferred.'); put(C/'idea_tree.json',tree)
old.update(at=now,turn=1593,live_handles=handles,driver=ident(old['driver']),prior_cohort_handles={k:ident(v) for k,v in old['prior_cohort_handles'].items()},executor_exit_exists=True,stop_exists=(A/'STOP').exists(),next_bounded_step=nextstep,terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),completed_work=['Verified bound handoff and authority; reconciled prior normal turn, exact live handles, controller terminal state and owning ledger prefixes.','Observed reviewer completion; verified exit 0, 168-check preparation PASS and immediate root/evidence artifact hashes.','Recorded terminal acceptance at preparation scope in owning state, checkpoint and Idea Tree; retained all costs, prior failures and outstanding release/scientific gates.'],unresolved_evidence=[x['gate'] for x in r['outstanding_gates']]+['Closed-schema operational review token integration','Original validation/formal/required ablation evidence remains incomplete.'])
put(T/'operational-summary-v1.json',old); (T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
print(json.dumps({'status':rec['status'],'verified_artifacts':len(checks),'summary':ref(T/'operational-summary-v1.json')},indent=2))
