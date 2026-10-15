import pathlib,json,hashlib,datetime,os,fcntl,copy,subprocess,yaml
root=pathlib.Path.cwd(); base=root.parent/'autonomy_20261004'; out=base/'turns/001451'; prepared=base/'turns/001448/binding-refresh'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');os.replace(t,p)
def verify(r):
 p=pathlib.Path(r['path']);assert ref(p)['sha256']==r['sha256'],str(p);return json.loads(p.read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not (base/'STOP').exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
report=json.loads((prepared/'report-v1.json').read_text()); exitrec=json.loads((prepared/'executor-exit-v1.json').read_text());assert exitrec['exit']==0
assert all(not pathlib.Path(f'/proc/{pid}').exists() for pid in [1622990,1622991])
for r in report['artifacts'].values():
 assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
controller=json.loads((prepared/'controller-semantics.disabled-v1.json').read_text()); parent=verify(controller['inherited_review'])
for k in ['module','class','instance','semantics','source','physical_gain_certified']:assert controller[k]==parent[k],k
verify(controller['runtime']);verify(controller['runtime_closure'])
assert ref(pathlib.Path(controller['source']['path']))['sha256']==controller['source']['sha256']
for key,r in controller['review_evidence'].items():
 evidence=verify(r);prior=verify(evidence['rebound_from'])
 for field in ['sources','findings','native_execution_observed','fixture_only']:assert evidence[field]==prior[field],(key,field)
 for s in evidence['sources']:assert ref(pathlib.Path(s['path']))['sha256']==s['sha256']
prov=json.loads((prepared/'runtime-rebinding-provenance-v1.json').read_text());oldruntime=verify(prov['prior_runtime']);runtime=verify(controller['runtime']);oldclosure=verify(prov['prior_closure']);closure=verify(controller['runtime_closure'])
assert len(oldruntime['files'])==len(runtime['files'])==3300
changed=[{'before':x,'after':y} for x,y in zip(oldruntime['files'],runtime['files']) if x!=y];assert changed==prov['changes']
assert set(oldclosure['modules'])==set(closure['modules']);delta=[k for k in closure['modules'] if closure['modules'][k]!=oldclosure['modules'][k]];assert delta==['scripts.qd_ed_n36_runner']
source=report['summary']['source'];wt=pathlib.Path(json.loads((prepared/'source.complete-v1.json').read_text()).get('worktree', '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree'))
assert subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip()==source
assert not subprocess.check_output(['git','-C',str(wt),'status','--porcelain','--untracked-files=no'],text=True).strip()
approved=copy.deepcopy(controller);approved.update(status='ROOT_REVIEWED',at=now,scope='Root verified exact inherited deployed-controller findings and source hashes, unchanged controller semantics and isolated runtime delta limited to accepted lexical-reference runner repair; reconciled-accounting repair is separately source-bound. Static source review only; actual instance/native evidence remains mandatory at first-C0 G3.',reviewed_draft=ref(prepared/'controller-semantics.disabled-v1.json'),release_enabled=False)
write(out/'controller-semantics.root-reviewed-v1.json',approved)
next_action='Refresh affected disabled manifests using turn 001451 controller review, then independent exact B5 for candidate 711602ac before root source/runtime adoption and current accounting reconciliation. Production parent attestation remains unexecuted until real governance exists; fresh charged health and first-C0 G3 remain required. Never replay old health launch.'
old=json.loads((base/'turns/001450/operational-summary-v1.json').read_text())
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in old['ledger_prefixes'].values(): assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
 rec=dict(schema='n36r3-binding-refresh-terminal-reconciliation-v1',at=now,decision='ACCEPT_DISABLED_BINDING_PREPARATION_AND_STATIC_CONTROLLER_REBINDING',report=ref(prepared/'report-v1.json'),exit=ref(prepared/'executor-exit-v1.json'),process_record=ref(prepared/'executor-process-v1.json'),prior_handles_absent=[1622990,1622991],candidate_source=source,controller_review=ref(out/'controller-semantics.root-reviewed-v1.json'),ledger_prefixes=old['ledger_prefixes'],checks=['All reported artifact hashes verified','Controller semantic fields, inherited findings and deployed source hashes unchanged','Runtime 3300-file inventory changes exactly match one repaired lexical-reference runner; closure delta agrees','Candidate HEAD exact and tracked source clean','All three owning journals unchanged'],release_enabled=False,source_adopted=False,target_met=False,next_action=next_action)
 write(out/'terminal-reconciliation-v1.json',rec)
 for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());v=d['n36r3_reconciled_accounting_binding_refresh'];v.update(status='TERMINAL_BINDINGS_ACCEPTED_CONTROLLER_REVIEWED_PENDING_MANIFEST_REFRESH_AND_B5',live_handles=[],executor_exited=True,report=rec['report'],exit=rec['exit'],terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'))
  d.update(n36r3_reconciled_accounting_controller_review=rec['controller_review'],next_action=next_action,updated_at=now,status='N36R3_BINDINGS_REVIEWED_PENDING_EXACT_B5',phase='N36R3_DISABLED_MANIFEST_REFRESH_PENDING')
  if is_yaml:
   tmp=p.with_suffix('.yaml.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(tmp,p)
  else:write(p,d)
 treepath=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';tree=json.loads(treepath.read_text());tree['nodes']['15.6'].update(result='REPAIRED_BINDINGS_ACCEPTED_CONTROLLER_REVIEWED_PENDING_EXACT_B5',n36r3_accounting_health_binding_terminal=ref(out/'terminal-reconciliation-v1.json'));write(treepath,tree)
summary=dict(schema='arbor-operational-summary-v1',at=now,turn=1451,owning_source='bee9f6a4703e9d5d802d6b8c7950b69beefac4c0',candidate_source=source,live_executor_handles=[],driver=json.loads((base/'driver-status.json').read_text()),completed_work=rec['checks']+['Reconciled successful executor exit and recorded static controller review; updated owning state/checkpoint/tree'],terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'),controller_review=rec['controller_review'],ledger_prefixes=rec['ledger_prefixes'],retained_attempts=505,retained_gpu_hours=75.53335346582918,driver_stop_exists=False,deadline='2026-10-11T11:13:13Z',next_bounded_step=next_action,unresolved_evidence=['Exact B5 and source/runtime adoption','Finite accounting, fresh charged readiness and distinct first-C0 release','Actual first-C0 G3 evidence','Original validation/formal/required ablations'],goal_complete=False)
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'decision':rec['decision'],'controller_review':rec['controller_review'],'next_action':next_action}))
