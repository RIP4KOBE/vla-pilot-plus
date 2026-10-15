import ast,datetime,fcntl,hashlib,json,os,pathlib,subprocess,yaml
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001606'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 p=pathlib.Path(r['path']);v=ref(p);assert all(v[k]==r[k] for k in ['bytes','sha256'] if k in r),str(p);return p

def put(p,d):
 assert not p.exists(),str(p)
 p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def replace(p,d,isyaml=False):
 q=p.with_name(p.name+'.tmp-001606');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 p=pathlib.Path('/proc')/str(v['pid'])/'stat';a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None;t=int(a[19]) if a else None;match=bool(a and t==v['start_ticks'] and boot==v['boot_id']);return {**v,'observed_start_ticks':t,'state':a[0] if a else None,'identity_matches':match,'live':bool(match and a[0]!='Z')}
old=read(A/'turns/001605/operational-summary-v1.json');prior=read(A/'turns/001605/receipt.json');assert prior['status']=='completed_turn' and prior['exit']==0
assert not (A/'STOP').exists()
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
for v in old['ledger_prefixes'].values():verify(v)
handles={k:ident(v) for k,v in old['live_handles'].items()};cohort={k:ident(v) for k,v in old['prior_cohort_handles'].items()};assert not any(v['live'] for v in [*handles.values(),*cohort.values()])
P=A/'turns/001604/independent-readiness-b5'
exit_record=read(P/'exit-v1.json');assert exit_record['exit']==0 and not exit_record['timeout']
report_ref=ref(P/'report-v1.json');assert (P/'report-v1.sha256').read_text().split()[0]==report_ref['sha256']
report=read(P/'report-v1.json');assert report['decision']=='PASS' and report['independent_checks']['count']==304 and report['independent_checks']['failures']==[] and report['blocking_defects']==[]
for group in ['roots','evidence_refs']:
 for v in report[group].values():verify(v)
verify(report['input'])
rec={'schema':'n36-readiness-b5-terminal-reconciliation-v1','at':now.isoformat(),'status':'TERMINAL_PREPARATION_PASS_ROOT_ACCEPTED','report':report_ref,'exit':ref(P/'exit-v1.json'),'handles':handles,'source':report['source'],'outstanding_gates':report['outstanding_gates'],'release_enabled':False,'gpu_dispatch':False,'target_met':False}
put(T/'terminal-reconciliation-v1.json',rec);old['terminal_reconciliation']=ref(T/'terminal-reconciliation-v1.json')
plan_ref=report['roots']['plan'];plan=read(verify(plan_ref))
for v in report['roots'].values():verify(v)
source=pathlib.Path(report['worktree']);assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==report['source'];assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==old['owner_source']
consumer=source/'scripts/qd_ed_n36_engineering.py';cr=next(x for x in report['production_code_inspected'] if x['path']==str(consumer));verify(cr)
module=ast.parse(consumer.read_text());binding_assignment=next(n for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BINDINGS' for t in n.targets));keys=ast.literal_eval(binding_assignment.value);assert len(keys)==12
bindings={k:plan[k] for k in keys}
authority_fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='validate_authority')
expected_node=next(n.value.args[1] for n in authority_fn.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='exact')
# Evaluate only the literal expected review dictionary from the pinned consumer.
assert isinstance(expected_node,ast.Dict)
expected=eval(compile(ast.Expression(expected_node),str(consumer),'eval'),{'__builtins__':{}},{'bindings':bindings})
token={'schema':report['consumer_integration']['production_schema'],'decision':report['consumer_integration']['required_decision'],**bindings,'worker_receipts_are_future':True,'release_enabled':False}
assert json.dumps(token,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False)
token_path=T/'independent-b5.operational-v1.json';put(token_path,token)
provenance={'schema':'n36-b5-operational-token-integration-v1','at':now.isoformat(),'status':'PASS_EXACT_CONSUMER_REVIEW_SCHEMA','independent_report':report_ref,'terminal_reconciliation':old['terminal_reconciliation'],'reviewed_plan':plan_ref,'consumer':ref(consumer),'token':ref(token_path),'binding_fields':list(keys),'validation':'Exact review dictionary extracted from hash-verified production validate_authority AST; JSON equality passed. Full validate_authority/readiness not executed.','prior_report_and_plan_unchanged':True,'source_adopted':False,'accounting_adopted':False,'release_enabled':False,'gpu_dispatch':False,'target_met':False,'outstanding_gates':report['outstanding_gates']}
put(T/'b5-integration-provenance-v1.json',provenance)
nextstep='Review and record root protocol acceptance and source/accounting adoption for exact turn001601 plan bindings with turn001606 independent-b5.operational-v1.json (integration provenance accompanies token). Construct a separate prospective released plan/authority only after those reviews; preserve all disabled roots. Verify actual runtime/provider/native readiness and fresh STOP/deadline/budget/headroom before detached health/episode dispatch. No scientific promotion from engineering preparation.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else read(p)
  assert d['resource_isolation']['status']=='ACTIVE' and d['resource_isolation']['validation_status']=='PASS' if isyaml else True
  current=d.get('in_flight_executor')
  if current:
   assert current['process_record_path'].endswith('/001604/independent-readiness-b5/process-v1.json')
   d['n36_engineering_readiness_independent_b5']['historical_in_flight_record']=current
   d['in_flight_executor']=None
  d['n36_engineering_readiness_independent_b5']['status']='TERMINAL_PREPARATION_PASS_OPERATIONAL_TOKEN_INTEGRATED_ROOT_GATES_PENDING'
  d['n36_engineering_readiness_independent_b5']['live_handles']=[]
  d['n36_engineering_b5_operational_integration']=ref(T/'b5-integration-provenance-v1.json')
  d['n36_engineering_b5_operational_review']=ref(token_path)
  d['n36_engineering_readiness_independent_b5_terminal_reconciliation']=ref(T/'terminal-reconciliation-v1.json');d['phase']='N36_ENGINEERING_READINESS_B5_ACCEPTED_ROOT_REATTESTATION_PENDING';d['next_action']=nextstep;d['updated_at']=now.isoformat();replace(p,d,isyaml)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='PREPARATION_PASS_OPERATIONAL_TOKEN_INTEGRATED_ROOT_GATES_PENDING',insight='Turn001604 independent readiness B5 preparation PASS normalized into exact consumer review schema at turn001606, retaining hash-bound report provenance. Protocol/source/accounting adoption, native readiness and detached release pending; no GPU dispatch or scientific success.');replace(C/'idea_tree.json',tree)
for v in old['ledger_prefixes'].values():verify(v)
old.update(at=now.isoformat(),turn=1594,live_handles=handles,prior_cohort_handles=cohort,driver=ident(read(A/'driver-status.json')['driver']),coordinator=ident(read(A/'driver-status.json')['process']),executor_exit_exists=True,stop_exists=(A/'STOP').exists(),next_bounded_step=nextstep,completed_work=['Verified bound authority, prior normal turn receipt, current process identities, terminal controller and unchanged owning ledger prefixes.','Created hash-bound exact-schema B5 operational review token from independent 304-check preparation PASS; checked against pinned consumer AST without invoking dispatch/readiness.','Cleared stale in-flight executor pointer while preserving its full historical record; updated owner state, checkpoint and Idea Tree.'],unresolved_evidence=[x['gate'] for x in report['outstanding_gates']]+['Original validation/formal/required ablation evidence remains incomplete.'],b5_operational_integration=ref(T/'b5-integration-provenance-v1.json'),b5_operational_review=ref(token_path),ledgers_unchanged=True)
put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
print(json.dumps({'summary':ref(T/'operational-summary-v1.json'),'token':ref(token_path),'dispatch':False,'ledgers_unchanged':True},indent=2))
