import os,sys,json,hashlib,time,signal,resource,ast,datetime as dt,subprocess
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]); resource.setrlimit(resource.RLIMIT_CPU,(360,360));signal.alarm(420)
sys.dont_write_bytecode=True
OUT=Path(__file__).absolute().parent; BASE=OUT.parents[1]; ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n36_stop as stop,qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36r3_admission as a,qd_ed_n23_worker as w
from scripts import qd_ed_n34_controller as controller,qd_ed_n36_release as release,qd_ed_n36r3_preparation as prep
stop.check(need=420)
inputs={}; checks=[]; manifests=[]
def ref(p):
 p=Path(p);raw=p.read_bytes();v={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};inputs[str(p)]=v;return v
def read(r):
 got=ref(r['path']);assert got['sha256']==r['sha256'];assert 'bytes' not in r or got['bytes']==r['bytes'];return json.loads(Path(r['path']).read_text())
def load(p):return read(ref(p))
def check(name,fn,expected=None):
 stop.check();t=time.monotonic()
 try:
  v=fn();assert expected is None,'expected rejection did not occur';x={'check':name,'status':'PASS','result':v}
 except Exception as e:
  x={'check':name,'status':'EXPECTED_BLOCK' if expected and expected in str(e) else 'FAIL','error':type(e).__name__+': '+str(e)}
 x['seconds']=time.monotonic()-t;checks.append(x);print(json.dumps(x),flush=True)
def require(x):assert x
au=load(OUT/'authority-v1.json');plan=read(au['plan']);bindings=read(au['bindings']);runtime=read(plan['runtime']);closure=read(plan['runtime_closure'])
for k in ['standing_authority','controller_review','terminal_reconciliation']:read(au[k])
prior=load(BASE/'001413/source-adoption-v1.json'); repair=load(BASE/'001418/root-repair-review-v1.json')
context=load(BASE/'001358/manifest-refresh/report-v1.json');ref(BASE/'001358/manifest-refresh/refresh-v1.py')
for p in ['001334/terminal-reconciliation-v1.json','001340/terminal-reconciliation-v1.json']:load(BASE/p)
preparation=load(BASE/'001419/binding-refresh/report-v1.json');oldplan=read(preparation['plan']);oldruntime=read(prior['runtime']);oldclosure=read(prior['runtime_closure'])
required=load(BASE/'001419/binding-refresh/required-after.production-v1.json')
accounting=load(BASE/'001419/binding-refresh/accounting-snapshot.disabled-v1.json')
for name in ['qd_ed_n36_prepare','qd_ed_n36r3_preparation','qd_ed_n36r3_admission','qd_ed_n36_contract','qd_ed_n36_bridge','qd_ed_n34_source','qd_ed_n34_controller','qd_ed_n36_build','qd_ed_n36_release','qd_ed_n36_supervise','qd_ed_n36_runner','qd_ed_n36r3_health','qd_ed_n36_healthcheck','qd_ed_n36_worker','qd_ed_n36_stop']:
 ref(ROOT/'scripts'/f'{name}.py')
check('authority_exact_plan_bindings_source',lambda:require(plan['source']['commit']==au['source']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() and all(bindings[k]==plan[k] for k in a.BINDINGS) and bindings['expected_manifests']==plan['expected_manifests'] and bindings['plan']['sha256']==au['plan']['sha256'] and bindings['release_enabled'] is False and bindings['worker_receipts_are_future'] is True))
check('draft_contract',lambda:c.validate_draft(plan))
check('owner_source_routing',lambda:str(a.owner_root(plan)))
check('exact_source_closure',lambda:b.verify_sources(plan))
check('runtime_closure_generated_alias_interpreter_distributions',lambda: (b.closure.verify_runtime(closure,plan['runtime']) and {'modules':len(closure['modules']),'required_after':closure['required_after']}))
check('runtime_inventory_bytes',lambda:b.runner.verify_files(runtime['files'],allowed_roots=(plan['worktree'],runtime['worktree'],runtime['artifact_root'])))
# Execute the exact passive manifest API body without importing Torch or loading native libraries.
source=ROOT/'scripts/qd_ed_n36_build.py'; tree=ast.parse(source.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='manifest' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REQUIRED' for t in n.targets)]
ns={'Path':Path,'w':w};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
check('native_build_passive_manifest_API',lambda:len(ns['manifest'](plan['native_build'])['libraries']))
check('root_controller_semantics_API',lambda:controller.verify_semantics(plan['controller_semantics'],plan['runtime'],closure)['status'])
check('required_after_exact',lambda:require(required['runtime_closure']==plan['runtime_closure'] and required['required_after']==closure['required_after'] and not required['observed_loaded_after'] and not required['process_bound_lifecycle_evidence']))
def all_manifests():
 assert len(plan['episodes'])==len(plan['expected_manifests'])==40
 for row in plan['episodes']:
  r=plan['expected_manifests'][row['episode_key']];read(r);b._verify_manifest_bound(r,plan,runtime,row);manifests.append({'episode_key':row['episode_key'],**ref(r['path']),'exact':True})
 return {'verified':len(manifests),'profiles':{p:sum(r['profile']==p for r in plan['episodes']) for p in c.ARMS}}
check('all_40_exact_manifest_consumers',all_manifests)
check('001421_refresh_delta_only',lambda:require({k:v for k,v in plan.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}=={k:v for k,v in oldplan.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}))
def delta():
 changed=subprocess.check_output(['git','diff','--name-only',prior['source']['commit'],au['source']],text=True).splitlines()
 assert changed==['scripts/qd_ed_n36_healthcheck.py','scripts/qd_ed_n36r3_admission.py','tests/test_n36r3_admission.py']
 for k in ('protocol','protocol_review','accounting','resource_routing'):assert prior[k]==plan[k]
 def index(rows):return {r['path']:r for r in rows}
 x,y=index(oldruntime['files']),index(runtime['files']);assert x.keys()==y.keys()
 rt=[k for k in x if x[k]!=y[k]];assert len(rt)==1 and rt[0].endswith('/scripts/qd_ed_n36_healthcheck.py')
 assert {k:v for k,v in runtime.items() if k!='files'}=={k:v for k,v in oldruntime.items() if k!='files'}
 assert oldclosure['modules'].keys()==closure['modules'].keys()
 mods=[k for k in closure['modules'] if closure['modules'][k]!=oldclosure['modules'][k]];assert len(mods)==1 and mods[0]=='scripts.qd_ed_n36_healthcheck'
 assert {k:v for k,v in closure.items() if k not in ('runtime','modules')}=={k:v for k,v in oldclosure.items() if k not in ('runtime','modules')}
 assert plan['native_build']['sha256']==prior['native_build']['sha256']
 oldproof=read(prior['controller_semantics']);proof=read(plan['controller_semantics'])
 for k in ('instance','semantics','source','module','class','physical_gain_certified'):assert oldproof[k]==proof[k]
 return {'source_changed':changed,'runtime_changed':rt,'closure_changed':mods,'scientific_protocol_and_controller_unchanged':True}
check('accepted_001413_to_001418_001419_delta',delta)
check('disabled_plan_release_rejection',lambda:release.validate_plan(plan),expected='N36R3 draft only; separate root bindings required')
check('future_accounting_stale_constant_rejection',lambda:prep.arithmetic(accounting['snapshot']),expected='retained charge differs')
stop.check()
result={'authority':au,'inputs':inputs,'checks':checks,'manifests':manifests,'accounting_snapshot':accounting,'cpu_threads':2,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),'stop_paths':list(stop.STOP_PATHS)}
with (OUT/'checks-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('CHECKS_COMPLETE',flush=True)
