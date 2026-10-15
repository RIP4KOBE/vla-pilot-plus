import os,sys,json,hashlib,datetime as dt,time,resource,signal,ast,subprocess
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(360,360));signal.alarm(420)
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));OUT=Path(__file__).absolute().parent;BASE=OUT.parents[1]
from scripts import qd_ed_n36_stop as stop,qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36r3_admission as a,qd_ed_n23_worker as w,qd_ed_n36_release as release,qd_ed_n36r3_preparation as prep,qd_ed_n34_controller as controller,qd_ed_n36_supervise as sup
stop.check(need=420)
inputs={};checks=[];manifests=[]
def ref(p):
 p=Path(p);raw=p.read_bytes();v={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};inputs[str(p)]=v;return v
def read(r):
 v=ref(r['path']);assert v['sha256']==r['sha256'] and ('bytes' not in r or v['bytes']==r['bytes']);return json.loads(Path(r['path']).read_text())
def load(p):return read(ref(p))
def require(x):assert x

def check(name,fn,expected=None):
 stop.check();start=time.monotonic()
 try:
  value=fn();assert expected is None,'Expected rejection did not occur';entry={'check':name,'status':'PASS','result':value}
 except Exception as e:entry={'check':name,'status':'EXPECTED_BLOCK' if expected and expected in str(e) else 'FAIL','error':type(e).__name__+': '+str(e)}
 entry['seconds']=time.monotonic()-start;checks.append(entry);print(json.dumps(entry),flush=True)
au=load(OUT/'authority-v1.json');plan=read(au['plan']);bindings=read(au['bindings']);runtime=read(plan['runtime']);closure=read(plan['runtime_closure'])
for key in ['standing_authority','controller_review','terminal_reconciliation']:read(au[key])
context={}
for path in ['001334/terminal-reconciliation-v1.json','001340/terminal-reconciliation-v1.json','001358/manifest-refresh/report-v1.json','001422/exact-b5-review/report-v1.json','001425/terminal-reconciliation-v1.json','001426/accounting-health-repair/report-v1.json','001428/terminal-reconciliation-v1.json','001429/binding-refresh/report-v1.json']:
 context[path]=load(BASE/path)
ref(BASE/'001358/manifest-refresh/refresh-v1.py');ref(BASE/'001432/manifest-refresh/refresh-v1.py')
oldreview=context['001422/exact-b5-review/report-v1.json']
oldplan=load(BASE/'001429/binding-refresh/draft/plan.draft.json');priorplan=read(oldreview['exact_plan'])
accounting=load(BASE/'001429/binding-refresh/accounting-snapshot.disabled-v1.json');health=load(BASE/'001429/binding-refresh/health-policy.disabled-v1.json');required=load(BASE/'001429/binding-refresh/required-after.production-v1.json');feasibility=load(BASE/'001429/binding-refresh/production-parent-attestation-feasibility-v1.json')
for name in ['qd_ed_n36_prepare','qd_ed_n36r3_preparation','qd_ed_n36r3_admission','qd_ed_n36_release','qd_ed_n36_bridge','qd_ed_n36_contract','qd_ed_n34_source','qd_ed_n34_controller','qd_ed_n36_build','qd_ed_n36r3_health','qd_ed_n36_healthcheck','qd_ed_n36_accounting','qd_ed_n36_supervise','qd_ed_n36_stop','qd_ed_n36_worker','qd_ed_n36_runner']:
 ref(ROOT/'scripts'/f'{name}.py')
check('exact_authority_BINDINGS',lambda:require(plan['source']['commit']==au['source']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() and all(bindings[k]==plan[k] for k in a.BINDINGS) and bindings['plan']['sha256']==au['plan']['sha256'] and bindings['expected_manifests']==plan['expected_manifests'] and bindings['release_enabled'] is False and bindings['worker_receipts_are_future'] is True))
check('draft_contract_scientific_protocol_and_STOP',lambda:c.validate_draft(plan))
check('lexical_owner_isolated_SOURCE',lambda:str(a.owner_root(plan)))
check('source_complete_exact_commit',lambda:b.verify_sources(plan))
check('runtime_closure_passive',lambda:(b.closure.verify_runtime(closure,plan['runtime']) and {'modules':len(closure['modules']),'required_after':closure['required_after'],'generated':list(closure.get('generated_modules',{}))}))
check('runtime_inventory_passive',lambda:b.runner.verify_files(runtime['files'],allowed_roots=(plan['worktree'],runtime['worktree'],runtime['artifact_root'])))
tree=ast.parse((ROOT/'scripts/qd_ed_n36_build.py').read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='manifest' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REQUIRED' for t in n.targets)];ns={'Path':Path,'w':w};exec(compile(ast.Module(body=nodes,type_ignores=[]),'scripts/qd_ed_n36_build.py','exec'),ns)
check('native_manifest_API_no_library_loading',lambda:len(ns['manifest'](plan['native_build'])['libraries']))
check('controller_exact_001432_review',lambda:controller.verify_semantics(plan['controller_semantics'],plan['runtime'],closure)['status'])
check('required_after_is_future',lambda:require(required['runtime_closure']==plan['runtime_closure'] and required['required_after']==closure['required_after'] and required['observed_loaded_after'] is False and required['process_bound_lifecycle_evidence'] is False and feasibility['production_parent_attestation_executed'] is False))
def all40():
 assert len(plan['episodes'])==len(plan['expected_manifests'])==40
 for row in plan['episodes']:
  rr=plan['expected_manifests'][row['episode_key']];read(rr);b._verify_manifest_bound(rr,plan,runtime,row);manifests.append({'episode_key':row['episode_key'],**ref(rr['path']),'exact':True})
 return {'verified':len(manifests),'arms':{arm:sum(r['profile']==arm for r in plan['episodes']) for arm in c.ARMS}}
check('all_40_exact_manifests',all40)
check('001432_refresh_delta',lambda:require({k:v for k,v in plan.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}=={k:v for k,v in oldplan.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}))
def delta():
 names=subprocess.check_output(['git','diff','--name-only',priorplan['source']['commit'],au['source']],text=True).splitlines()
 assert names==['scripts/qd_ed_n36_release.py','scripts/qd_ed_n36r3_admission.py','scripts/qd_ed_n36r3_preparation.py','tests/test_n36r3_accounting_health_repair.py']
 for k in ('episodes','protocol','protocol_review','accounting','resource_routing','limits','worker_contract','deadline','stop_authority'):assert priorplan[k]==plan[k],k
 oldruntime=read(priorplan['runtime']);oldclosure=read(priorplan['runtime_closure']);x={r['path']:r for r in oldruntime['files']};y={r['path']:r for r in runtime['files']};assert x.keys()==y.keys();changed=[k for k in x if x[k]!=y[k]]
 assert len(changed)==1 and changed[0].endswith('/scripts/qd_ed_n36r3_admission.py'),changed
 assert {k:v for k,v in runtime.items() if k!='files'}=={k:v for k,v in oldruntime.items() if k!='files'}
 assert oldclosure['modules'].keys()==closure['modules'].keys();mods=[k for k in closure['modules'] if closure['modules'][k]!=oldclosure['modules'][k]];assert mods==['scripts.qd_ed_n36r3_admission'],mods
 assert {k:v for k,v in closure.items() if k not in ('runtime','modules')}=={k:v for k,v in oldclosure.items() if k not in ('runtime','modules')}
 assert plan['native_build']['sha256']==priorplan['native_build']['sha256']
 oldproof=read(priorplan['controller_semantics']);proof=read(plan['controller_semantics'])
 for k in ('instance','semantics','source','module','class','physical_gain_certified'):assert oldproof[k]==proof[k]
 return {'source_delta':names,'runtime_delta':changed,'closure_delta':mods,'unchanged_science':True}
check('001422_to_current_exact_delta',delta)
check('finite_arithmetic_repaired',lambda:require(prep.arithmetic(accounting['snapshot'])==accounting['arithmetic']))
check('distinct_health_identity',lambda:require(a.PREPARATION_ID=='n36_healthcheck_n36r3_preparation_001426' and health['healthchecks']==a.HEALTH and health['replay_allowed'] is False and health['deadline']==c.DEADLINE and health['release_enabled'] is False))
check('old_accounting_value_rejected',lambda:prep.arithmetic({**accounting['snapshot'],'gpu_hours_consumed':75.52725286641478}),expected='retained charge differs')
check('bare_draft_release_rejected',lambda:release.validate_plan(plan),expected='N36R3 draft only; separate root bindings required')
check('first_C0_boundary',lambda:require(sup.first_c0_boundary(plan['episodes'][0]) and not sup.first_c0_boundary(plan['episodes'][1])))
check('source_tracked_clean',lambda:require(not subprocess.check_output(['git','diff','--name-only','HEAD'],text=True).strip()))
stop.check()
result={'authority':au,'inputs':inputs,'checks':checks,'manifests':manifests,'accounting_snapshot':accounting,'health_policy':health,'cpu_threads':2,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),'stop_paths':list(stop.STOP_PATHS),'preserved_accepted_repair_tests':context['001428/terminal-reconciliation-v1.json']['tests']}
with (OUT/'checks-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('CHECKS_COMPLETE',flush=True)
