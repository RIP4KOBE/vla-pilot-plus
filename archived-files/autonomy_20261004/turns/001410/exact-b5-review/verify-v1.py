import os,sys,json,hashlib,datetime,time,ast,types,resource,signal,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
BASE=OUT.parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_CPU,(300,300)); signal.alarm(420)
from scripts import qd_ed_n36_stop as stop
stop.check(need=420)
checks=[]; inputs={}
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 actual=ref(r['path']);assert actual['sha256']==r['sha256'],str(r);inputs[str(r['path'])]=actual
 return json.loads(Path(r['path']).read_text())
def bindread(p):return read(ref(p))
def check(name,fn):
 start=time.monotonic()
 try:
  result=fn();checks.append({'check':name,'status':'PASS','seconds':round(time.monotonic()-start,3),'result':result}); print(name,'PASS',flush=True)
 except Exception as exc:
  checks.append({'check':name,'status':'FAIL','error':type(exc).__name__+': '+str(exc)});print(name,'FAIL',str(exc),flush=True)
def require(x,message):
 if not x:raise ValueError(message)
def command(*argv):
 p=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,check=True)
 return {'argv':list(argv),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
auth=bindread(OUT/'authority-v1.json')
for k in ('standing_authority','terminal_reconciliation','controller_review'):read(auth[k])
plan=read(auth['plan']);bindings=read(auth['bindings'])
from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36r3_admission as a,qd_ed_n23_worker as w,qd_ed_n36_release as release
runtime=read(plan['runtime']);closure=read(plan['runtime_closure']);native=read(plan['native_build'])
prior=bindread(BASE/'001358/manifest-refresh/plan.draft.json')
parent=bindread(BASE/'001408/binding-refresh/draft/plan.draft.json')
prior_runtime=read(prior['runtime']);prior_closure=read(prior['runtime_closure'])
def exact_bindings():
 require(all(bindings[k]==plan[k] for k in a.BINDINGS),'BINDINGS mismatch')
 require(bindings['plan']['sha256']==auth['plan']['sha256'] and Path(bindings['plan']['path']).resolve()==Path(auth['plan']['path']).resolve(),'plan binding mismatch')
 require(bindings['expected_manifests']==plan['expected_manifests'],'manifest refs')
 require(bindings['release_enabled'] is False and bindings['worker_receipts_are_future'] is True and bindings['score'] is None and bindings['target_met'] is False,'disabled status')
 return list(a.BINDINGS)
check('authority_and_exact_admission_BINDINGS',exact_bindings)
check('git_HEAD',lambda:command('git','rev-parse','HEAD'))
check('tracked_source_status',lambda:command('git','status','--porcelain','--untracked-files=no'))
check('accepted_repair_diff',lambda:command('git','diff','21fc93e5667a83520401282d4ba8e945f954f99b','HEAD','--','scripts/qd_ed_n36_healthcheck.py','scripts/qd_ed_n36_runner.py'))
check('disabled_draft_contract',lambda:c.validate_draft(plan))
check('owner_vs_SOURCE',lambda:str(a.owner_root(plan)))
check('source_and_scientific_source_exact',lambda:b.verify_sources(plan))
check('runtime_closure_prospective_API',lambda:(b.closure.verify_runtime(closure,plan['runtime']),{'modules':len(closure['modules']),'required_after':closure['required_after']})[1])
check('runtime_inventory',lambda:b.runner.verify_files(runtime['files'],allowed_roots=(plan['worktree'],runtime['worktree'],runtime['artifact_root'])))
# Execute the unchanged passive function without importing torch or instantiating a controller.
def load_functions(filename,names,constants=()):
 path=ROOT/'scripts'/filename;inputs[str(path)]=ref(path);tree=ast.parse(path.read_text())
 nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
 import math
 ns={'w':w,'Path':Path,'math':math};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns);return ns
ctrl=load_functions('qd_ed_n34_controller.py',{'verify_semantics'},('FIELDS',))
check('controller_production_semantics_API',lambda:(ctrl['verify_semantics'](plan['controller_semantics'],plan['runtime'],closure), 'ROOT_REVIEWED static source only; actual instance future')[1])
build=load_functions('qd_ed_n36_build.py',{'manifest'},('REQUIRED',))
check('native_build_passive_manifest_API',lambda:len(build['manifest'](plan['native_build'])['libraries']))
def manifests():
 require(len(plan['episodes'])==len(plan['expected_manifests'])==40,'40 expected')
 results=[]
 for row in plan['episodes']:
  r=plan['expected_manifests'][row['episode_key']];read(r)
  b._verify_manifest_bound(r,plan,runtime,row)
  results.append({'episode_key':row['episode_key'],**r,'status':'PASS'})
 return results
check('all_40_exact_production_manifests',manifests)
def unchanged():
 excluded={'controller_semantics','artifact_root','expected_manifests'}
 require({k:v for k,v in plan.items() if k not in excluded}=={k:v for k,v in parent.items() if k not in excluded},'001410 refresh scope')
 for key in ('episodes','limits','worker_contract','deadline','stop_authority','protocol','protocol_review','accounting','resource_routing'):
  require(prior[key]==plan[key],'science/gate changed '+key)
 require(plan['deadline']=='2026-10-11T11:13:13Z','deadline')
 require(native==read(prior['native_build']),'native changed')
 for key in ('required_after','generated_modules','module_aliases','interpreter','versions','distribution_versions'):
  require(closure[key]==prior_closure[key],'closure contract changed '+key)
 old={x['path']:x['sha256'] for x in prior_runtime['files']};new={x['path']:x['sha256'] for x in runtime['files']}
 require(old.keys()==new.keys(),'runtime inventory paths changed')
 delta=[k for k in new if new[k]!=old[k]]
 require({Path(x).name for x in delta}=={'qd_ed_n36_healthcheck.py','qd_ed_n36_runner.py'},'runtime delta')
 md=[k for k in closure['modules'] if closure['modules'][k]!=prior_closure['modules'].get(k)]
 require(set(md)=={'scripts.qd_ed_n36_healthcheck','scripts.qd_ed_n36_runner'},'module delta')
 for key in runtime:
  if key not in ('files','preparation_history'):require(runtime[key]==prior_runtime[key],'runtime field changed '+key)
 return {'runtime_delta':delta,'closure_delta':md,'identities_unchanged':True,'native_unchanged':True,'required_after':closure['required_after']}
check('refresh_scope_and_scientific_continuity',unchanged)
def gate(fn):
 try:fn(auth['plan'],auth['bindings'])
 except ValueError as exc:
  require(str(exc)=='N36R3 draft only; separate root bindings required','unexpected gate '+str(exc))
  return {'result':'EXPECTED_BLOCK','error':str(exc),'parent_attestation_executed':False,'synthetic_governance_used':False,'reservation_executed':False}
 raise ValueError('disabled draft unexpectedly accepted')
check('real_health_release_validator_disabled_rejection',lambda:gate(release.validate_health_release))
check('real_episode_release_validator_disabled_rejection',lambda:gate(release.validate_release))
check('head_and_source_assertion',lambda:require(plan['source']['commit']==auth['source']==command('git','rev-parse','HEAD')['stdout'].strip(),'source changed'))
# Inspect the real callers and unchanged receipt helper without invoking production paths.
def callers():
 result=[]
 for name,fn in [('qd_ed_n36_healthcheck.py','run_healthcheck'),('qd_ed_n36_runner.py','execute_one')]:
  path=ROOT/'scripts'/name;inputs[str(path)]=ref(path);tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==fn)
  call=next(n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='attest')
  kw=next(x.value for x in call.keywords if x.arg=='binding')
  require(isinstance(kw,ast.Call) and kw.func.attr=='runtime_receipt_binding','binding helper')
  require([ast.unparse(v) for v in kw.args]==['release_ref','plan','w.process_identity()',"'runtime_before'"],'parent arguments')
  result.append({'file':str(path),'line':call.lineno,'call':ast.unparse(call)})
 return result
check('accepted_parent_caller_binding_static',callers)
from scripts import qd_ed_n36_supervise as supervisor
check('first_C0_boundary_static_API',lambda:require([r['episode_key'] for r in plan['episodes'] if supervisor.first_c0_boundary(r)]==[plan['episodes'][0]['episode_key']],'first C0 boundary'))
# Direct accepted reports only, no recursive provenance or ledger traversal.
for name in ['001358/manifest-refresh/report-v1.json','001407/health-binding-root-review-v1.json','001408/binding-refresh/report-v1.json','001361/source-adoption-v1.json','001334/admission-independent-review/report-v1.json','001340/terminal-reconciliation-v1.json']:
 bindread(BASE/name)
for name in ['qd_ed_n36_prepare.py','qd_ed_n36r3_preparation.py','qd_ed_n36r3_admission.py','qd_ed_n36_release.py','qd_ed_n36_worker.py','qd_ed_n36_source.py','qd_ed_n36_supervise.py','qd_ed_n36_report.py','qd_ed_n34_source.py','qd_ed_n36_bridge.py','qd_ed_n36_contract.py','qd_ed_n36_stop.py']:
 inputs[str(ROOT/'scripts'/name)]=ref(ROOT/'scripts'/name)
inputs[str(BASE/'001358/manifest-refresh/refresh-v1.py')]=ref(BASE/'001358/manifest-refresh/refresh-v1.py')
stop.check()
check('inputs_unchanged_at_completion',lambda:require(all(ref(p)==r for p,r in inputs.items()),'reviewed input mutated'))
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'inputs':inputs,'cpu_affinity':sorted(os.sched_getaffinity(0)),'production_parent_attestation_executed':False,'release_enabled':False,'score':None,'target_met':False}
with (OUT/'checks-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('FAILED',sum(x['status']=='FAIL' for x in checks),flush=True)
