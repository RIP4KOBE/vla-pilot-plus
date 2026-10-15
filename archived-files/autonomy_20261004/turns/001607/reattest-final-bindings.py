import ast,datetime,fcntl,hashlib,json,os,pathlib,subprocess,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001607';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify(r):
 p=pathlib.Path(r['path']);assert ref(p)['sha256']==r['sha256'],str(p)
 if 'bytes' in r:assert p.stat().st_size==r['bytes']
 return p
def put(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def replace(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001607');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 p=pathlib.Path('/proc')/str(v['pid'])/'stat';a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None;t=int(a[19]) if a else None;m=bool(a and t==v['start_ticks'] and boot==v['boot_id']);return {**v,'observed_start_ticks':t,'state':a[0] if a else None,'identity_matches':m,'live':bool(m and a[0]!='Z')}
old=read(A/'turns/001606/operational-summary-v1.json');receipt=read(A/'turns/001606/receipt.json');assert receipt['exit']==0 and receipt['status']=='completed_turn'
now=datetime.datetime.now(datetime.timezone.utc);assert not (A/'STOP').exists();assert now<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
for v in old['ledger_prefixes'].values():verify(v)
handles={k:ident(v) for k,v in old['live_handles'].items()};cohort={k:ident(v) for k,v in old['prior_cohort_handles'].items()};assert not any(v['live'] for v in [*handles.values(),*cohort.values()])
driver=ident(old['driver']);assert driver['live']
provenance=read(verify(old['b5_operational_integration']));report=read(verify(provenance['independent_report']));assert report['decision']=='PASS' and report['independent_checks']['failures']==[] and report['independent_checks']['count']==304
plan=read(verify(provenance['reviewed_plan']));token=read(verify(old['b5_operational_review']));source=pathlib.Path(plan['worktree'])
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==plan['source']['commit']
assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==old['owner_source']
consumer=verify(provenance['consumer']);module=ast.parse(consumer.read_text())
def literal(name):return ast.literal_eval(next(n.value for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)))
keys=literal('BINDINGS');limits=literal('LIMITS');bindings={k:plan[k] for k in keys}
for k in keys:
 if k not in ['source','scientific_source']:verify(bindings[k])
assert {k:token[k] for k in keys}==bindings
scope=read(verify(bindings['scope']))['scope'];assert scope['purpose']=='engineering_diagnostic_only' and not any(scope[k] for k in ['scientific_eligible','promotion_eligible','matched_improvement_eligible','pool_with_past_or_future_controls','automatic_continuation'])
assert limits==plan['limits'] and limits['attempts']==limits['healthchecks']==1 and limits['automatic_recoveries']==0
assert plan['phase_authorization']=={'engineering':False,'dev':False,'validation':False,'formal':False}
eq=read(verify(bindings['scientific_equivalence']));assert eq['scientific_changes'] is False
changed=subprocess.check_output(['git','-C',str(source),'diff','--name-only',eq['base_commit'],plan['source']['commit']],text=True).splitlines();assert changed==eq['changed_paths']
review_ref={k:old['b5_operational_review'][k] for k in ['path','sha256']}
protocol={'schema':'n36-engineering-root-protocol-acceptance-v1','approved':True,**bindings,'b5_review':review_ref,'limits':limits}
p=T/'root-protocol-acceptance-v1.json';put(p,protocol)
adoption={'schema':'n36-engineering-source-adoption-v1','approved':True,**bindings,'b5_review':review_ref,'protocol_acceptance':ref(p),'owner_root':str(W),'source_cwd':str(source)}
s=T/'root-source-adoption-v1.json';put(s,adoption)
# Validate the two exact consumer dictionaries without imports or dispatch.
fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='validate_authority')
expected={}
for n in fn.body:
 if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='exact' and len(n.value.args)>2:
  label=n.value.args[2]
  if isinstance(label,ast.Constant) and label.value in ['root engineering protocol acceptance','root engineering source adoption']:
   expected[label.value]=eval(compile(ast.Expression(n.value.args[1]),str(consumer),'eval'),{'__builtins__':{},'str':str},{'bindings':bindings,'plan':{**plan,'b5_review':review_ref},'LIMITS':limits,'authority':{'protocol_acceptance':ref(p)},'OWNER':W,'SOURCE':source})
assert expected['root engineering protocol acceptance']==protocol
assert expected['root engineering source adoption']==adoption
record={'schema':'n36-engineering-root-adoption-review-v1','at':now.isoformat(),'decision':'PROTOCOL_AND_ISOLATED_SOURCE_ADOPTED','authorization':ref(A/'user-authorization-v1.json'),'reviewed_plan':provenance['reviewed_plan'],'independent_review':provenance['independent_report'],'b5_review':review_ref,'protocol_acceptance':ref(p),'source_adoption':ref(s),'consumer':ref(consumer),'source_commit':plan['source']['commit'],'owner_source_unchanged':old['owner_source'],'scientific_changes':False,'changed_operational_paths':changed,'checks':['Exact source HEAD and tracked-clean state','Reviewed immediate bindings hash verified','Independent 304-check PASS retained','Exact production protocol/source dictionary checks','Three owning journal prefixes unchanged','Driver live and no previous cohort/executor live'],'accounting_adopted':False,'release_enabled':False,'gpu_dispatch':False,'target_met':False,'limits':limits,'scope':scope}
put(T/'root-adoption-review-v1.json',record)

from decimal import Decimal, localcontext
from types import SimpleNamespace
disabled=read(verify(plan['accounting']));spec=read(verify(disabled['specification']));retained=read(verify(disabled['retained_snapshot_reference']))
marginref=read(A/'turns/001276/b5-preparation/accounting.prospective-disabled-v1.json')['inherited_accounting']
margin=read(verify(marginref));assert marginref['sha256']=='2c46987e29d9616929fe0c086d3da0761eaf6718a5d1811b58200c18e34d75d0'
for name,v in margin['ledger_prefixes'].items():
 b=(W/'data'/name).read_bytes()[:v['bytes']];assert hashlib.sha256(b).hexdigest()==v['sha256']
assert Decimal(str(margin['cost_reconciliation']['retained_admission_margin_gpu_hours']))==Decimal('0.23357169027962')
state=yaml.safe_load((W/'research-state.yaml').read_text());caps={'attempts':1800,'gpu_hours':224.0,'buckets':state['budget']['reserved'],'protected_gpu_hours':state['budget']['gpu_hour_reservations']}
arith=spec['accounting_proposal']
with localcontext() as ctx:
 ctx.prec=40
 before=Decimal('75.60616276674473')+Decimal('0.23357169027962');reservation=Decimal(1900)/3600;after=before+reservation
 assert str(after)==arith['conservative_after_gpu_hours_decimal']
 assert Decimal('221.08404692669838')-after-Decimal('24.2408240024308155')-Decimal('12')==Decimal(arith['unprotected_effective_remaining_after_gpu_hours'])
assert arith['prospective_attempts_max']==506+1 and arith['baseline_before_after_cap']==[106,107,400]
assert (datetime.datetime.fromisoformat(plan['deadline'].replace('Z','+00:00'))-now).total_seconds()>2100
amendment={'schema':'n36-engineering-owning-accounting-v1','approved':True,**bindings,'source_adoption':record['source_adoption'],'caps':caps,'limits':limits,'ledger_prefixes':spec['retained_ledger_prefixes'],'snapshot':retained['retained_snapshot'],'arithmetic':arith,'margin_reference':marginref,'automatic_recoveries':0}
put(T/'accounting-v1.json',amendment)
authority={'schema':'n36-engineering-budget-authority-v1','approved':True,'cohort':plan['cohort'],'purpose':plan['purpose'],**bindings,'b5_review':record['b5_review'],'caps':caps,'limits':limits,'automatic_recoveries':0,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':plan['deadline'],'starts_at':now.isoformat(),'weekly_window':{'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.,'ends_at':plan['deadline']},'approval_basis':ref(A/'user-authorization-v1.json'),'protocol_acceptance':record['protocol_acceptance'],'source_adoption':record['source_adoption'],'amendment':ref(T/'accounting-v1.json'),'ledger_prefixes':spec['retained_ledger_prefixes'],'margin_reference':marginref}
# Check exact authority and amendment dictionaries against the frozen consumer AST.
fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='validate_authority')
env={'bindings':bindings,'plan':{**plan,'b5_review':record['b5_review']},'LIMITS':limits,'c':SimpleNamespace(CAPS=caps,DEADLINE=plan['deadline']),'IDENTITY':plan['cohort'],'PURPOSE':plan['purpose'],'authority':authority,'retained':retained,'spec':spec}
for n in fn.body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='fixed' for t in n.targets):
  fixed=eval(compile(ast.Expression(n.value),str(consumer),'eval'),{},env);assert all(authority[k]==v for k,v in fixed.items())
 if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and getattr(n.value.func,'id',None)=='exact' and len(n.value.args)>2 and isinstance(n.value.args[2],ast.Constant) and n.value.args[2].value=='owning engineering accounting adoption':
  assert amendment==eval(compile(ast.Expression(n.value.args[1]),str(consumer),'eval'),{},env)
put(T/'budget-authority-v1.json',authority)

nextstep='Construct a separate prospective engineering plan from the exact turn001601 disabled plan using turn001607 authority and turn001606 B5. Run unmodified production authority/state and actual runtime/audit closure in authorized root context. Preserve prior fenced failures; credentials.py library provenance is distinct from prohibited Poe credential files, which must remain unopened. Only after runtime closure passes issue separate health release, fresh metered healthcheck and settlement, then episode release with fresh STOP/deadline/headroom checks. No scientific promotion or automatic recovery.'
review={'schema':'n36-root-final-binding-reattestation-v1','at':now.isoformat(),'decision':'PROTOCOL_SOURCE_ACCOUNTING_REATTESTED','prior_protocol':ref(A/'turns/001595/root-protocol-acceptance-v1.json'),'prior_source_adoption':ref(A/'turns/001595/root-source-adoption-v1.json'),'prior_accounting':ref(A/'turns/001596/accounting-v1.json'),'prior_authority':ref(A/'turns/001596/budget-authority-v1.json'),'reviewed_plan':provenance['reviewed_plan'],'independent_report':provenance['independent_report'],'protocol_acceptance':ref(T/'root-protocol-acceptance-v1.json'),'source_adoption':ref(T/'root-source-adoption-v1.json'),'accounting':ref(T/'accounting-v1.json'),'authority':ref(T/'budget-authority-v1.json'),'changed_bindings':[],'arithmetic':arith,'source':plan['source']['commit'],'release_enabled':False,'gpu_dispatch':False,'scientific_promotion':False,'full_runtime_closure_verified':False}
prior=read(verify(review['prior_authority']))
review['changed_bindings']=[k for k in bindings if prior[k]!=bindings[k]]
assert set(review['changed_bindings'])=={'audit_plan','engineering_manifest','runtime','runtime_closure','controller_semantics'}
assert all(prior[k]==authority[k] for k in ['caps','limits','weekly_window','ledger_prefixes','margin_reference','approval_basis'])
put(T/'root-final-binding-reattestation-v1.json',review)
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for file,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(file.read_text()) if isyaml else read(file)
  assert not d.get('in_flight_executor')
  if isyaml:
   assert d['resource_isolation']['status']=='ACTIVE' and d['resource_isolation']['validation_status']=='PASS' and not d.get('current_owned_workers')
   assert d['budget']['gpu_hours_consumed']==75.60616276674473 and d['budget']['dispatched']==506
   d['n36_engineering_previous_budget_amendment']=d['budget']['amendment'];d['budget']['amendment']=ref(T/'accounting-v1.json')
  for key,name in [('root_protocol_acceptance','root-protocol-acceptance-v1.json'),('root_source_adoption','root-source-adoption-v1.json'),('root_adoption_review','root-adoption-review-v1.json'),('budget_authority','budget-authority-v1.json'),('accounting_adoption','accounting-v1.json'),('final_binding_reattestation','root-final-binding-reattestation-v1.json')]: d['n36_engineering_'+key]=ref(T/name)
  d['phase']='N36_ENGINEERING_FINAL_BINDINGS_ADOPTED_RUNTIME_CLOSURE_PENDING';d['next_action']=nextstep;d['updated_at']=now.isoformat();replace(file,d,isyaml)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='FINAL_BINDINGS_ADOPTED_RUNTIME_CLOSURE_PENDING',insight='Turn001607 reattested five changed engineering bindings under 304-check independent B5; adopted exact protocol/source/accounting with unchanged caps and retained history. One engineering C0 only, no scientific eligibility. Actual runtime closure and separate health/episode releases pending.');replace(C/'idea_tree.json',tree)
for v in old['ledger_prefixes'].values():verify(v)
status=read(A/'driver-status.json')
old.update(at=now.isoformat(),turn=1607,driver=ident(status['driver']),coordinator=ident(status['process']),live_handles=handles,prior_cohort_handles=cohort,stop_exists=False,next_bounded_step=nextstep,completed_work=['Verified authorization, prior normal exit, live driver/coordinator identities, no live prior cohort/executor, and unchanged owning ledgers.','Reattested five changed final bindings against independent 304-check CPU review, unchanged exact source and production dictionary schema.','Adopted protocol, isolated source and exact finite accounting: 506+1=507 attempts; 1900/3600 GPU-hour reservation; protected reserves and all history retained.','Updated owning state/checkpoint/Idea Tree; no dispatch, source change, ledger mutation or scientific promotion.'],unresolved_evidence=['Actual unmodified runtime and audit closure','Separate health release, metered native healthcheck and episode release','Original validation/formal/required ablation evidence incomplete'],root_final_binding_reattestation=ref(T/'root-final-binding-reattestation-v1.json'),root_adoption_review=ref(T/'root-adoption-review-v1.json'),accounting_adoption=ref(T/'accounting-v1.json'),budget_authority=ref(T/'budget-authority-v1.json'),ledgers_unchanged=True,gpu_dispatch=False,target_met=False)
put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
print(json.dumps({'summary':ref(T/'operational-summary-v1.json'),'decision':review['decision'],'changed_bindings':review['changed_bindings'],'dispatch':False}))
