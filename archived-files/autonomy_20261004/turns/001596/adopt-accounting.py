import ast,datetime,fcntl,hashlib,json,os,pathlib,subprocess,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001596';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify(r):
 p=pathlib.Path(r['path']);assert ref(p)['sha256']==r['sha256'],str(p)
 if 'bytes' in r:assert p.stat().st_size==r['bytes']
 return p
def put(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def replace(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001596');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 p=pathlib.Path('/proc')/str(v['pid'])/'stat';a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None;t=int(a[19]) if a else None;m=bool(a and t==v['start_ticks'] and boot==v['boot_id']);return {**v,'observed_start_ticks':t,'state':a[0] if a else None,'identity_matches':m,'live':bool(m and a[0]!='Z')}

from decimal import Decimal, localcontext
from types import SimpleNamespace
old=read(A/'turns/001595/operational-summary-v1.json')
assert read(A/'turns/001595/receipt.json')['status']=='completed_turn'
now=datetime.datetime.now(datetime.timezone.utc)
assert not (A/'STOP').exists() and now<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
for v in old['ledger_prefixes'].values():verify(v)
handles={k:ident(v) for k,v in old['live_handles'].items()};cohort={k:ident(v) for k,v in old['prior_cohort_handles'].items()}
assert not any(v['live'] for v in [*handles.values(),*cohort.values()])
driver=ident(old['driver']);assert driver['live']
review=read(verify(old['root_adoption_review']));plan=read(verify(review['reviewed_plan']))
consumer=verify(review['consumer']);module=ast.parse(consumer.read_text())
def literal(name):return ast.literal_eval(next(n.value for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)))
bindings={k:plan[k] for k in literal('BINDINGS')};limits=literal('LIMITS')
for k,v in bindings.items():
 if k not in ['source','scientific_source']:verify(v)
source=pathlib.Path(plan['worktree'])
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==plan['source']['commit']
assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
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
amendment={'schema':'n36-engineering-owning-accounting-v1','approved':True,**bindings,'source_adoption':review['source_adoption'],'caps':caps,'limits':limits,'ledger_prefixes':spec['retained_ledger_prefixes'],'snapshot':retained['retained_snapshot'],'arithmetic':arith,'margin_reference':marginref,'automatic_recoveries':0}
put(T/'accounting-v1.json',amendment)
authority={'schema':'n36-engineering-budget-authority-v1','approved':True,'cohort':plan['cohort'],'purpose':plan['purpose'],**bindings,'b5_review':review['b5_review'],'caps':caps,'limits':limits,'automatic_recoveries':0,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':plan['deadline'],'starts_at':now.isoformat(),'weekly_window':{'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.,'ends_at':plan['deadline']},'approval_basis':ref(A/'user-authorization-v1.json'),'protocol_acceptance':review['protocol_acceptance'],'source_adoption':review['source_adoption'],'amendment':ref(T/'accounting-v1.json'),'ledger_prefixes':spec['retained_ledger_prefixes'],'margin_reference':marginref}
# Check exact authority and amendment dictionaries against the frozen consumer AST.
fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='validate_authority')
env={'bindings':bindings,'plan':{**plan,'b5_review':review['b5_review']},'LIMITS':limits,'c':SimpleNamespace(CAPS=caps,DEADLINE=plan['deadline']),'IDENTITY':plan['cohort'],'PURPOSE':plan['purpose'],'authority':authority,'retained':retained,'spec':spec}
for n in fn.body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='fixed' for t in n.targets):
  fixed=eval(compile(ast.Expression(n.value),str(consumer),'eval'),{},env);assert all(authority[k]==v for k,v in fixed.items())
 if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and getattr(n.value.func,'id',None)=='exact' and len(n.value.args)>2 and isinstance(n.value.args[2],ast.Constant) and n.value.args[2].value=='owning engineering accounting adoption':
  assert amendment==eval(compile(ast.Expression(n.value.args[1]),str(consumer),'eval'),{},env)
put(T/'budget-authority-v1.json',authority)
nextstep='Create separate released engineering plan from unchanged turn001588 disabled plan with turn001596 budget authority and turn001594 B5; run production authority/state validation and runtime/provider/native readiness, then detached health release and fresh admission. No source edits, no automatic retry or scientific promotion. Preserve disabled roots and all ledger history; fresh STOP/deadline checks required.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for v in old['ledger_prefixes'].values():verify(v)
 for file,is_yaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(file.read_text()) if is_yaml else read(file)
  assert not d.get('current_owned_workers') and not d.get('in_flight_executor')
  if is_yaml:
   assert d['resource_isolation']['status']=='ACTIVE' and d['resource_isolation']['validation_status']=='PASS'
   assert d['budget']['gpu_hours_consumed']==75.60616276674473 and d['budget']['dispatched']==506
   d['n36_engineering_previous_budget_amendment']=d['budget']['amendment'];d['budget']['amendment']=ref(T/'accounting-v1.json')
  d['n36_engineering_budget_authority']=ref(T/'budget-authority-v1.json');d['n36_engineering_accounting_adoption']=ref(T/'accounting-v1.json');d['next_action']=nextstep;d['updated_at']=now.isoformat();replace(file,d,is_yaml)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='ENGINEERING_ACCOUNTING_ADOPTED_READINESS_RELEASE_PENDING',insight='Turn001596 adopted finite one-attempt/1900-GPU-second engineering accounting; all 506 historical attempts and costs preserved. No GPU dispatch or scientific promotion. Separate release and actual runtime readiness pending.');replace(C/'idea_tree.json',tree)
for v in old['ledger_prefixes'].values():verify(v)
old.update(at=now.isoformat(),turn=1596,driver=driver,live_handles=handles,prior_cohort_handles=cohort,next_bounded_step=nextstep,completed_work=['Verified prior turn completed, driver identity, dead prior handles and unchanged owning ledgers','Verified exact approved source and immediate bindings','Checked finite arithmetic, retained margin and protected reserves','Adopted exact engineering accounting and authority under owning state lock; updated checkpoint and Idea Tree'],unresolved_evidence=['PRODUCTION_AUTHORITY_STATE_VALIDATION','ACTUAL_RUNTIME_PROVIDER_CUDA_EGL_NATIVE_READINESS','DETACHED_HEALTH_EPISODE_RELEASES','FRESH_ADMISSION_GATES','Original validation/formal/required ablation evidence remains incomplete.'],accounting_adoption=ref(T/'accounting-v1.json'),budget_authority=ref(T/'budget-authority-v1.json'),gpu_dispatch=False,ledgers_unchanged=True)
put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
print(json.dumps({'authority':ref(T/'budget-authority-v1.json'),'summary':ref(T/'operational-summary-v1.json'),'gpu_dispatch':False}))
