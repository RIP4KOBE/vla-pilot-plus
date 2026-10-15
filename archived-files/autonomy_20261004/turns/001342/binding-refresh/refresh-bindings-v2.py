import os, sys, json, hashlib, datetime as dt, time, resource, subprocess, traceback, copy, signal
from pathlib import Path
OUT=Path(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_text()); ROOT=Path(A['worktree']); OWNER=Path(A['owner']); BASE=OUT.parents[1]
START=time.monotonic(); sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(240,240));signal.alarm(300)
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='2'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['GIT_OPTIONAL_LOCKS']='0';os.environ['GIT_NO_LAZY_FETCH']='1'
os.environ['TMPDIR']=str(OUT/'tmp')
(OUT/'tmp').mkdir(exist_ok=True)
from scripts import qd_ed_n36_stop as stop
CHECKS={}; ART={}; INPUTS={}; COMMANDS=[]; ERRORS=[]
def guard():
 stop.check();assert time.monotonic()-START<300

def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='subprocess.Popen':
  argv=args[1];assert isinstance(argv,(list,tuple)) and Path(argv[0]).name=='git','only passive Git subprocesses permitted'
  assert any(x in argv for x in ('rev-parse','status','diff','ls-tree','cat-file','config')),'non-read-only Git forbidden'
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.path.abspath(os.fsdecode(args[0])); low=name.lower()
  assert not any(x in low for x in ('/.codex/auth.json','/.git-credentials','credentials.json','2026-08-10-eds-qd-stage-guidance-transition-design.md')),'prohibited read'
  assert not (('/validation/' in low or '/formal/' in low) and ('outcome' in low or '/artifacts/' in low)),'protected outcomes forbidden'
  flags=args[2]
  if isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
   assert name == '/dev/null' or Path(name).resolve().is_relative_to(OUT),'write outside output forbidden'
 if event in ('os.rename','os.remove','os.rmdir','os.mkdir'):
  for name in args[:2] if event=='os.rename' else args[:1]:
   if isinstance(name,(str,bytes)):assert Path(os.fsdecode(name)).resolve().is_relative_to(OUT),'mutation outside output forbidden'
 if event=='exec' and getattr(args[0],'co_filename','')==str(ROOT/'main.py'):raise PermissionError('Main forbidden')
sys.addaudithook(audit)
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb') as f:
  for raw in iter(lambda:f.read(8*1024*1024),b''):h.update(raw)
 return {'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()}
def read(ref):
 b=bind(ref['path']);assert b['sha256']==ref['sha256'] and ('bytes' not in ref or b['bytes']==ref['bytes']);INPUTS[str(ref['path'])]=b
 return json.loads(Path(ref['path']).read_text())
def write(name,value):
 guard();p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
 ART[name]=bind(p);return {'path':str(p),'sha256':ART[name]['sha256']}
def git(root,*args):
 guard();argv=['git','-C',str(root),*args];p=subprocess.run(argv,text=True,capture_output=True);COMMANDS.append({'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==0,p.stderr;return p.stdout.strip()
def check(name,fn):
 guard();t=time.monotonic()
 try:v=fn();CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t};print(name,'PASS',flush=True);return v
 except Exception as e:CHECKS[name]={'status':'FAIL','error':str(e),'traceback':traceback.format_exc()};raise

def main():
 global BEFORE, OLD, PLAN
 guard();integration=read(A['source_integration']);read(A['standing_authority'])
 reviews=[read(x) for x in integration['review_inputs']];review=reviews[0];accepted=read(review['repair_report']);arts=accepted['artifacts']
 oldplan=read(arts['draft/plan.draft.json']);oldruntime=read(arts['runtime.isolated.disabled-v1.json']);oldclosure=read(arts['runtime-closure.isolated.disabled-v1.json'])
 oldcontroller=read(arts['controller-semantics.disabled-v1.json']);read(arts['prepare-repair-v1.py']) if False else None
 # Bind the accepted script without executing or rebuilding its historical inputs.
 INPUTS[arts['prepare-repair-v1.py']['path']]=bind(arts['prepare-repair-v1.py']['path']);assert INPUTS[arts['prepare-repair-v1.py']['path']]==arts['prepare-repair-v1.py']
 OLD={k:bind(v['path']) for k,v in arts.items()};assert all(OLD[k]==v for k,v in arts.items())
 BEFORE={name:bind(v['path']) for name,v in integration['retained_mutable_files'].items()}
 write('immutable-before-v2.json',{'owner_files':BEFORE,'accepted_artifacts':OLD})
 for root in (ROOT,OWNER):assert git(root,'rev-parse','HEAD')==A['source']
 assert not git(ROOT,'status','--porcelain','--untracked-files=no')
 immutable=['core','configs','main.py','scripts/qd_ed_n36_worker.py','scripts/qd_ed_n36_bridge.py','scripts/qd_ed_final_runner.py','scripts/audit_decision_evidence.py','scripts/qd_ed_n36_build.py','scripts/qd_ed_n34_controller.py']
 assert not git(ROOT,'diff','--name-only',review['repair_source'],A['source'],'--',*immutable),'accepted production/science changed'
 baseline=git(ROOT,'rev-parse',A['scientific_source']+'^{commit}')
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36_prepare as prep,qd_ed_n34_source as s,qd_ed_n36r3_preparation as pack,qd_ed_n36r3_admission as admission
 from scripts.qd_ed_n36_build import manifest as native_manifest
 source=check('exact_source_record',lambda:s.source_record(ROOT,b.source_paths(ROOT)));assert source['commit']==A['source'];sr=write('source.complete-v1.json',source)
 write('scientific-source-provenance-v1.json',{'historical_baseline':baseline,'authority_baseline':A['scientific_source'],'accepted_composition_source':review['repair_source'],'current_source':A['source'],'plan_scientific_source_equals_source':True,'immutable_since_accepted_paths':immutable,'note':'Historical baseline is provenance, not substituted for the API-required exact current scientific_source.'})
 runtime=copy.deepcopy(oldruntime);closure=copy.deepcopy(oldclosure);index={str(ROOT/x['path']):x['sha256'] for x in source['files']};changes=[]
 for row in runtime['files']:
  before=copy.deepcopy(row)
  if row['path'] in index:row['sha256']=index[row['path']];row['size_bytes']=Path(row['path']).stat().st_size
  if row!=before:changes.append({'before':before,'after':copy.deepcopy(row)})
 assert runtime['worktree']==str(ROOT)
 runtime['preparation']={'source':A['source'],'source_record':sr,'status':'DISABLED_CPU_BINDING_REFRESH','runtime_ready':False,'release_enabled':False,'historical_runtime':oldplan['runtime'],'historical_readiness_is_not_current':True}
 rr=write('runtime.isolated.disabled-v1.json',runtime);closure['runtime']=rr;module_changes=[]
 for name,row in closure['modules'].items():
  if row['path'] in index and row['sha256']!=index[row['path']]:
   module_changes.append({'module':name,'before':copy.deepcopy(row),'after':{'path':row['path'],'sha256':index[row['path']]}});row['sha256']=index[row['path']]
 cr=write('runtime-closure.isolated.disabled-v1.json',closure)
 write('runtime-rebinding-provenance-v1.json',{'accepted_report':review['repair_report'],'prior_runtime':oldplan['runtime'],'prior_closure':oldplan['runtime_closure'],'changes':changes,'module_changes':module_changes,'inventory_entries_removed':False,'historical_readiness_not_current':True})
 check('runtime_closure',lambda:s.verify_runtime(closure,rr));check('runtime_inventory',lambda:b.runner.verify_files(runtime['files'],allowed_roots=(ROOT,runtime['artifact_root'])))
 assert closure['required_after']==oldclosure['required_after']
 write('required-after.production-v1.json',{'required_after':closure['required_after'],'runtime_closure':cr,'observed_loaded_after':False,'process_bound_lifecycle_evidence':False})
 native=check('native_build_passive_inventory',lambda:native_manifest(oldplan['native_build']));nr=write('native-build.disabled-v1.json',native)
 controller=copy.deepcopy(oldcontroller);controller['runtime']=rr;ctr=write('controller-semantics.disabled-v1.json',controller)
 plan=check('existing_prepare_API',lambda:prep.prepare(OUT/'api-draft',rr,runtime_closure_ref=cr,controller_semantics_ref=ctr,native_build_ref=nr,root=ROOT,recovery_protocol_ref=oldplan['protocol']))
 assert plan['episodes']==oldplan['episodes'] and plan['source']==plan['scientific_source']==source
 # Add exact reviewed SOURCE/OWNER routing, then generate a separate final draft via bridge.manifest.
 plan=copy.deepcopy(plan);plan['resource_routing']={'source_cwd':str(admission.SOURCE),'owner_root':str(admission.OWNER),'physical_gpu':7,'gpu_uuid':c.GPU_UUID}
 plan['artifact_root']=str(OUT/'draft/prospective-artifacts');plan['expected_manifests']={}
 check('isolated_owner_source_routing',lambda:admission.owner_root(plan))
 for row in plan['episodes']:
  guard();name='draft/expected/'+row['episode_key']+'.json';plan['expected_manifests'][row['episode_key']]=write(name,b.manifest(plan,runtime,row))
 check('disabled_final_draft',lambda:c.validate_draft(plan));check('all_40_exact_manifests',lambda:[b._verify_manifest_bound(plan['expected_manifests'][r['episode_key']],plan,runtime,r) for r in plan['episodes']]);check('exact_source_scientific_source',lambda:b.verify_sources(plan))
 pr=write('draft/plan.draft.json',plan);PLAN=plan
 snapshot=check('read_only_current_ledger_snapshot',lambda:pack.ledger_snapshot(OWNER,review));arith=pack.arithmetic(snapshot['snapshot'])
 write('accounting-snapshot.disabled-v1.json',{'release_enabled':False,'owning_accounting_adopted':False,'current_headroom':None,**snapshot,'arithmetic':arith})
 from scripts.qd_ed_n36_supervise import first_c0_boundary
 assert first_c0_boundary(plan['episodes'][0]);assert plan['episodes'][0]['profile']=='C0'
 write('bindings.disabled-v1.json',{'schema':'n36r3-refresh-bindings-draft-v1','status':'DISABLED_PENDING_INDEPENDENT_B5_AND_ROOT_REVIEW','plan':pr,**{k:plan[k] for k in admission.BINDINGS},'expected_manifests':plan['expected_manifests'],'deadline':c.DEADLINE,'stop_authority':stop.binding(),'first_C0':'PAUSED_FOR_ROOT_G3; no later-cell continuation authority','b5_review':None,'source_adoption':None,'owning_accounting':None,'health_release':None,'episode_release':None,'release_enabled':False,'runtime_ready':False,'target_met':False,'score':None})
 return {'source':source['commit'],'scientific_source':source['commit'],'historical_scientific_baseline':baseline,'source_files':len(source['files']),'runtime_files':len(runtime['files']),'runtime_modules':len(closure['modules']),'runtime_rebound_entries':len(changes),'closure_rebound_modules':len(module_changes),'manifest_count':len(plan['expected_manifests']),'required_after':closure['required_after'],'first_C0_pause':True,'retained_attempts':505,'retained_gpu_hours':75.52725286641478}
BEFORE={};OLD={};PLAN=None;summary={}
try:summary=main()
except BaseException as e:
 ERRORS.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 signal.alarm(0)
 try:
  guard();after={k:bind(v['path']) for k,v in BEFORE.items()};oldafter={k:bind(v['path']) for k,v in OLD.items()};assert after==BEFORE and oldafter==OLD
  CHECKS['owner_state_ledgers_and_old_artifacts_unchanged']={'status':'PASS','owner_files':len(BEFORE),'old_artifacts':len(OLD)}
  assert git(ROOT,'rev-parse','HEAD')==A['source'] and not git(ROOT,'status','--porcelain','--untracked-files=no')
  assert git(OWNER,'rev-parse','HEAD')==A['source']
 except BaseException as e:ERRORS.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()})
 write('checks-results-v2.json',{'summary':summary,'checks':CHECKS,'errors':ERRORS,'commands':COMMANDS,'seconds':time.monotonic()-START,'threads':2})
 print(json.dumps({'summary':summary,'errors':ERRORS,'seconds':time.monotonic()-START}),flush=True)
