import ast,datetime,fcntl,hashlib,json,os,pathlib,subprocess,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001595';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify(r):
 p=pathlib.Path(r['path']);assert ref(p)['sha256']==r['sha256'],str(p)
 if 'bytes' in r:assert p.stat().st_size==r['bytes']
 return p
def put(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def replace(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001595');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 p=pathlib.Path('/proc')/str(v['pid'])/'stat';a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None;t=int(a[19]) if a else None;m=bool(a and t==v['start_ticks'] and boot==v['boot_id']);return {**v,'observed_start_ticks':t,'state':a[0] if a else None,'identity_matches':m,'live':bool(m and a[0]!='Z')}
old=read(A/'turns/001594/operational-summary-v1.json');receipt=read(A/'turns/001594/receipt.json');assert receipt['exit']==0 and receipt['status']=='completed_turn'
now=datetime.datetime.now(datetime.timezone.utc);assert not (A/'STOP').exists();assert now<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
for v in old['ledger_prefixes'].values():verify(v)
handles={k:ident(v) for k,v in old['live_handles'].items()};cohort={k:ident(v) for k,v in old['prior_cohort_handles'].items()};assert not any(v['live'] for v in [*handles.values(),*cohort.values()])
driver=ident(old['driver']);assert driver['live']
provenance=read(verify(old['b5_operational_integration']));report=read(verify(provenance['independent_report']));assert report['decision']=='PASS' and report['checks']['failed']==0
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
record={'schema':'n36-engineering-root-adoption-review-v1','at':now.isoformat(),'decision':'PROTOCOL_AND_ISOLATED_SOURCE_ADOPTED','authorization':ref(A/'user-authorization-v1.json'),'reviewed_plan':provenance['reviewed_plan'],'independent_review':provenance['independent_report'],'b5_review':review_ref,'protocol_acceptance':ref(p),'source_adoption':ref(s),'consumer':ref(consumer),'source_commit':plan['source']['commit'],'owner_source_unchanged':old['owner_source'],'scientific_changes':False,'changed_operational_paths':changed,'checks':['Exact source HEAD and tracked-clean state','Reviewed immediate bindings hash verified','Independent 168-check PASS retained','Exact production protocol/source dictionary checks','Three owning journal prefixes unchanged','Driver live and no previous cohort/executor live'],'accounting_adopted':False,'release_enabled':False,'gpu_dispatch':False,'target_met':False,'limits':limits,'scope':scope}
put(T/'root-adoption-review-v1.json',record)
nextstep='Adopt exact finite engineering accounting and record n36_engineering_budget_authority under owner state lock using turn001595 protocol/source approvals, unchanged turn001588 bindings and turn001594 B5. Then create separate released plan and verify runtime/provider/native readiness and detached health release; preserve disabled roots. No source edits, no automatic retries, no scientific promotion; STOP/deadline and admission gates must be fresh.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for file,is_yaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(file.read_text()) if is_yaml else read(file)
  if is_yaml:assert d['resource_isolation']['status']=='ACTIVE' and d['resource_isolation']['validation_status']=='PASS' and not d.get('current_owned_workers')
  assert not d.get('in_flight_executor')
  d['n36_engineering_root_protocol_acceptance']=ref(p);d['n36_engineering_root_source_adoption']=ref(s);d['n36_engineering_root_adoption_review']=ref(T/'root-adoption-review-v1.json');d['next_action']=nextstep;d['updated_at']=now.isoformat();replace(file,d,is_yaml)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='ENGINEERING_PROTOCOL_SOURCE_ADOPTED_ACCOUNTING_READINESS_RELEASE_PENDING',insight='Turn001595 root accepted one-C0 engineering protocol and exact isolated source b8d6b981 under independent B5 PASS. No scientific changes, GPU dispatch or success; finite accounting adoption and native readiness/release remain pending.');replace(C/'idea_tree.json',tree)
for v in old['ledger_prefixes'].values():verify(v)
old.update(at=now.isoformat(),turn=1595,driver=driver,live_handles=handles,prior_cohort_handles=cohort,stop_exists=False,next_bounded_step=nextstep,completed_work=record['checks']+['Recorded exact-schema root protocol acceptance and isolated source adoption; state/checkpoint/Idea Tree updated.'],unresolved_evidence=['FINITE_ACCOUNTING_AND_AUTHORITY_ADOPTION','ACTUAL_RUNTIME_PROVIDER_CUDA_EGL_NATIVE_READINESS','DETACHED_HEALTH_EPISODE_RELEASES','FRESH_ADMISSION_GATES','Original validation/formal/required ablation evidence remains incomplete.'],root_adoption_review=ref(T/'root-adoption-review-v1.json'),ledgers_unchanged=True)
put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
print(json.dumps({'protocol':ref(p),'source_adoption':ref(s),'summary':ref(T/'operational-summary-v1.json'),'gpu_dispatch':False},indent=2))
