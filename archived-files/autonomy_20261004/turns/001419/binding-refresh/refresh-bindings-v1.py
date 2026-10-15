import os, sys, json, hashlib, datetime as dt, time, resource, subprocess, traceback, copy, signal
from pathlib import Path
OUT=Path(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_text()); ROOT=Path(A['worktree']); OWNER=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree'); BASE=OUT.parents[1]
START=time.monotonic(); sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(600,600));signal.alarm(720)
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='2'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['GIT_OPTIONAL_LOCKS']='0';os.environ['GIT_NO_LAZY_FETCH']='1'
os.environ['TMPDIR']=str(OUT/'tmp')
(OUT/'tmp').mkdir(exist_ok=True)
from scripts import qd_ed_n36_stop as stop
CHECKS={}; ART={}; INPUTS={}; COMMANDS=[]; ERRORS=[]
def guard():
 stop.check();assert time.monotonic()-START<720

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
 guard();stop.check(need=720)
 standing=read(A['authority']);accept=read(A['repair_acceptance']);adopt=read(A['prior_adoption']);oldplan=read(A['parent_plan'])
 assert standing['approved'] and standing['continuous_window']['end_utc']==stop.DEADLINE
 assert accept['source_after']==A['source'] and accept['status']=='ACCEPTED_BOUNDED_ENGINEERING_REPAIR_NOT_EXECUTION_RELEASE'
 assert adopt['source']['commit']==accept['source_before']=='4347951a24b63cdb7f0c8a585591d89f1be778ae'
 INPUTS[A['repair_acceptance']['path']]=bind(A['repair_acceptance']['path']) # Root acceptance is the bounded review anchor; no recursive reconstruction.
 for key in ('source','scientific_source','runtime','runtime_closure','native_build','controller_semantics','resource_routing'):
  assert adopt[key]==oldplan[key],key
 oldruntime=read(oldplan['runtime']);oldclosure=read(oldplan['runtime_closure']);oldcontroller=read(oldplan['controller_semantics'])
 for r in oldplan['expected_manifests'].values():read(r)
 for r in oldcontroller['review_evidence'].values():read(r)
 retained=json.loads((BASE/'001355/binding-refresh/immutable-before-v1.json').read_text())['owner_files']
 BEFORE={k:bind(v['path']) for k,v in retained.items()}
 for name,ref in accept['ledger_prefixes'].items(): assert all(bind(ref['path'])[k]==ref[k] for k in ('path','bytes','sha256'))
 OLD={p:dict(v) for p,v in INPUTS.items()}
 write('immutable-before-v1.json',{'owner_files':BEFORE,'parent_artifacts':OLD})
 assert git(ROOT,'rev-parse','HEAD')==A['source']
 assert git(OWNER,'rev-parse','HEAD')=='bee9f6a4703e9d5d802d6b8c7950b69beefac4c0'
 assert not git(ROOT,'status','--porcelain','--untracked-files=no')
 changed=git(ROOT,'diff','--name-only',accept['source_before'],A['source']).splitlines()
 assert changed==['scripts/qd_ed_n36_healthcheck.py','scripts/qd_ed_n36r3_admission.py','tests/test_n36r3_admission.py']
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n34_source as s,qd_ed_n36r3_preparation as pack,qd_ed_n36r3_admission as admission
 source=check('exact_source_record',lambda:s.source_record(ROOT,b.source_paths(ROOT)));assert source['commit']==A['source'];sr=write('source.complete-v1.json',source)
 write('scientific-source-provenance-v1.json',{'current_source':A['source'],'scientific_source':A['source'],'prior_adoption':A['prior_adoption'],'historical_baseline':'1065f38122379a515b60a9a424f574330405b66f','changed_paths':changed,'production_Main_science_receipts_audits_unchanged':True})
 runtime=copy.deepcopy(oldruntime);closure=copy.deepcopy(oldclosure);index={str(ROOT/x['path']):x['sha256'] for x in source['files']};changes=[];module_changes=[]
 for row in runtime['files']:
  before=copy.deepcopy(row)
  if row['path'] in index:row['sha256']=index[row['path']];row['size_bytes']=Path(row['path']).stat().st_size
  if row!=before:changes.append({'before':before,'after':copy.deepcopy(row)})
 assert runtime['worktree']==str(ROOT)
 runtime['preparation']={'source':A['source'],'source_record':sr,'status':'DISABLED_CPU_BINDING_REFRESH','runtime_ready':False,'release_enabled':False,'historical_runtime':oldplan['runtime'],'historical_readiness_is_not_current':True}
 rr=write('runtime.isolated.disabled-v1.json',runtime);closure['runtime']=rr
 for name,row in closure['modules'].items():
  if row['path'] in index and row['sha256']!=index[row['path']]:
   module_changes.append({'module':name,'before':copy.deepcopy(row),'after':{'path':row['path'],'sha256':index[row['path']]}});row['sha256']=index[row['path']]
 cr=write('runtime-closure.isolated.disabled-v1.json',closure)
 write('runtime-rebinding-provenance-v1.json',{'parent_plan':A['parent_plan'],'prior_runtime':oldplan['runtime'],'prior_closure':oldplan['runtime_closure'],'changes':changes,'module_changes':module_changes,'inventory_entries_removed':False,'historical_readiness_not_current':True})
 check('runtime_closure',lambda:s.verify_runtime(closure,rr));check('runtime_inventory',lambda:b.runner.verify_files(runtime['files'],allowed_roots=(ROOT,runtime['artifact_root'])))
 assert closure['required_after']==oldclosure['required_after']
 write('required-after.production-v1.json',{'required_after':closure['required_after'],'runtime_closure':cr,'observed_loaded_after':False,'process_bound_lifecycle_evidence':False})
 # Execute the unchanged pure native inventory API without importing Torch.
 import ast,types,math
 def require(x,m):
  if not x:raise ValueError(m)
 wn=types.SimpleNamespace(read_ref=read,require=require,sha=lambda p:bind(p)['sha256'])
 def pure_api(path,names,constants,namespace):
  tree=ast.parse(path.read_text());subset=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name in names) or (isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id in constants for x in n.targets))]
  exec(compile(ast.Module(body=subset,type_ignores=[]),str(path),'exec'),namespace);return namespace
 ns=pure_api(ROOT/'scripts/qd_ed_n36_build.py',{'manifest'},{'REQUIRED'},{'w':wn,'Path':Path})
 native=check('native_build_passive_inventory',lambda:ns['manifest'](oldplan['native_build']));nr=write('native-build.disabled-v1.json',native)
 ns=pure_api(ROOT/'scripts/qd_ed_n34_controller.py',{'verify_semantics'},{'FIELDS'},{'w':wn,'math':math})
 check('inherited_root_controller_semantics',lambda:ns['verify_semantics'](oldplan['controller_semantics'],oldplan['runtime'],closure))
 controller=copy.deepcopy(oldcontroller)
 controller.update(runtime=rr,runtime_closure=cr,status='DISABLED_PENDING_ROOT_REVIEW',release_enabled=False,source_commit=A['source'],inherited_review=oldplan['controller_semantics'],at=dt.datetime.now(dt.timezone.utc).isoformat())
 controller.pop('reviewed_draft',None)
 controller['scope']='Exact draft rebinding of unchanged root-reviewed semantics; new root approval required. No actual instance evidence.'
 controller['review_evidence']={}
 for key,ref in oldcontroller['review_evidence'].items():
  ev=read(ref)
  for src in ev['sources']:assert bind(src['path'])['sha256']==src['sha256']
  ev=copy.deepcopy(ev);ev.update(runtime=rr,runtime_closure=cr,source_commit=A['source'],at=dt.datetime.now(dt.timezone.utc).isoformat(),rebound_from=ref,status='DISABLED_PENDING_ROOT_REVIEW',release_enabled=False,binding_review='CPU draft rebinding only; inherited findings unchanged, new root review required.')
  controller['review_evidence'][key]=write('controller-evidence/'+key+'.disabled-v1.json',ev)
 ctr=write('controller-semantics.disabled-v1.json',controller)
 try:ns['verify_semantics'](ctr,rr,closure)
 except ValueError as exc:
  assert str(exc)=='reviewed controller semantics required'
  CHECKS['candidate_controller_release_gate']={'status':'EXPECTED_BLOCK','error':str(exc),'reason':'Executor cannot issue ROOT_REVIEWED approval for refreshed runtime.'}
 else:raise AssertionError('disabled controller unexpectedly accepted')
 plan=copy.deepcopy(oldplan);plan.update(source=source,scientific_source=source,runtime=rr,runtime_closure=cr,native_build=nr,controller_semantics=ctr,artifact_root=str(OUT/'draft/prospective-artifacts'),expected_manifests={})
 check('isolated_owner_source_routing',lambda:admission.owner_root(plan))
 for row in plan['episodes']:
  guard();plan['expected_manifests'][row['episode_key']]=write('draft/expected/'+row['episode_key']+'.json',b.manifest(plan,runtime,row))
 check('disabled_final_draft',lambda:c.validate_draft(plan));check('all_40_exact_manifests',lambda:[b._verify_manifest_bound(plan['expected_manifests'][r['episode_key']],plan,runtime,r) for r in plan['episodes']]);check('exact_source_scientific_source',lambda:b.verify_sources(plan))
 allowed={'source','scientific_source','runtime','runtime_closure','native_build','controller_semantics','artifact_root','expected_manifests'}
 assert {k:v for k,v in plan.items() if k not in allowed}=={k:v for k,v in oldplan.items() if k not in allowed}
 assert len(plan['episodes'])==40
 pr=write('draft/plan.draft.json',plan);PLAN=plan
 return {'source':source['commit'],'scientific_source':source['commit'],'owner_adopted_source':accept['source_before'],'source_files':len(source['files']),'runtime_files':len(runtime['files']),'runtime_modules':len(closure['modules']),'runtime_rebound_entries':len(changes),'closure_rebound_modules':len(module_changes),'manifest_count':40,'first_C0_pause':True,'deadline':c.DEADLINE,'retained_attempts':505,'retained_gpu_hours':75.53031173955723,'synthetic_fixtures_used':False,'accepted_repair_tests_rerun':False}
BEFORE={};OLD={};PLAN=None;summary={}
try:summary=main()
except BaseException as e:
 ERRORS.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 signal.alarm(0)
 try:
  guard();assert {k:bind(v['path']) for k,v in BEFORE.items()}==BEFORE
  assert {k:bind(v['path']) for k,v in OLD.items()}==OLD
  assert git(ROOT,'rev-parse','HEAD')==A['source'] and not git(ROOT,'status','--porcelain','--untracked-files=no')
  assert git(OWNER,'rev-parse','HEAD')=='bee9f6a4703e9d5d802d6b8c7950b69beefac4c0'
  CHECKS['owner_state_ledgers_and_old_artifacts_unchanged']={'status':'PASS','owner_files':len(BEFORE),'old_artifacts':len(OLD)}
 except BaseException as e:ERRORS.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()})
 write('checks-results-v1.json',{'summary':summary,'checks':CHECKS,'errors':ERRORS,'commands':COMMANDS,'seconds':time.monotonic()-START,'threads':2})
 print(json.dumps({'summary':summary,'errors':ERRORS,'seconds':time.monotonic()-START}),flush=True)
