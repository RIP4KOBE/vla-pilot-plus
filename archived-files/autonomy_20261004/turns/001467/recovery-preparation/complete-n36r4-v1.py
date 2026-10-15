"""Bounded artifact-only N36R4 preparation. Never authorizes or executes a cell."""
import os,sys,json,hashlib,copy,datetime as dt,time,resource,signal,subprocess,ast,types,traceback
from decimal import Decimal as D
from pathlib import Path
OUT=Path(__file__).absolute().parent
BASE=OUT.parents[2]
A=json.loads((OUT/'authority-v1.json').read_text());ROOT=Path(A['worktree'])
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(600,600));signal.alarm(700)
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
os.environ.update(CUDA_VISIBLE_DEVICES='',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
START=time.monotonic();INPUTS={};ART={};CHECKS={};ERRORS=[]
def fence(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='subprocess.Popen':
  argv=args[1]
  assert isinstance(argv,(list,tuple)) and Path(argv[0]).name=='git','only passive Git allowed'
  assert any(x in argv for x in ('rev-parse','status','diff','ls-tree','cat-file','config'))
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.path.abspath(os.fsdecode(args[0]));low=name.lower()
  assert not any(x in low for x in ('/.codex/auth.json','/.git-credentials','credentials.json','2026-08-10-eds-qd-stage-guidance-transition-design.md'))
  flags=args[2]
  if isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):assert name=='/dev/null' or Path(name).resolve().is_relative_to(OUT.resolve()),'outside output write'
 if event in ('os.rename','os.remove','os.rmdir','os.mkdir'):
  for name in args[:2] if event=='os.rename' else args[:1]:
   if isinstance(name,(str,bytes)):assert Path(os.fsdecode(name)).resolve().is_relative_to(OUT.resolve())
sys.addaudithook(fence)
from scripts import qd_ed_n36_stop as stop
stop.check(need=700)
def guard():
 stop.check();assert time.monotonic()-START<700
 launch=json.loads((OUT/'executor-process-v1.json').read_text());assert time.time()-launch['started_unix']<900

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for raw in iter(lambda:f.read(8*1024*1024),b''):h.update(raw)
 return h.hexdigest()
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':sha(p)}
def load(p):
 p=Path(p);r=ref(p);INPUTS[str(p)]=r;return json.loads(p.read_text())
def read(r):
 assert sha(r['path'])==r['sha256'];return load(r['path'])
def write(name,v):
 guard();p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 ART[name]=ref(p);return ART[name]
def git(*args):
 p=subprocess.run(['git','-C',str(ROOT),*args],capture_output=True,text=True);assert p.returncode==0,p.stderr;return p.stdout.strip()
def check(name,fn):
 guard();t=time.monotonic();v=fn();CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t};print(name,'PASS',flush=True);return v
def require(x,m):
 if not x:raise ValueError(m)
def main():
 global PLAN,ARITH
 oldreport=load(BASE/'turns/001451/manifest-refresh/report-v1.json');old=read(oldreport['plan'])
 # Execute unchanged passive source functions, excluding imports that load Torch.
 def extract(path, names, ns):
  tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns);return ns
 wn={'Path':Path,'hashlib':hashlib,'json':json,'subprocess':subprocess,'os':os,'require':require}
 extract(ROOT/'scripts/qd_ed_n23_worker.py',{'_source_git','_source_entry','canonical_sha'},wn)
 wn.update(require=require,sha=sha,read_ref=read);w=types.SimpleNamespace(**wn)
 sn={'__file__':str(ROOT/'scripts/qd_ed_n34_source.py'),'__name__':'passive_source','w':w}
 tree=ast.parse((ROOT/'scripts/qd_ed_n34_source.py').read_text())
 nodes=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module=='scripts')]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),sn['__file__'],'exec'),sn);s=types.SimpleNamespace(**sn)
 cn={'__file__':str(ROOT/'scripts/qd_ed_n36_contract.py'),'__name__':'passive_contract','w':w}
 tree=ast.parse((ROOT/'scripts/qd_ed_n36_contract.py').read_text());nodes=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module=='scripts' and any(a.name=='qd_ed_n23_worker' for a in n.names))]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),cn['__file__'],'exec'),cn);c=types.SimpleNamespace(**cn)
 rt=ast.parse((ROOT/'scripts/qd_ed_final_runner.py').read_text())
 required=ast.literal_eval(next(n.value for n in rt.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REQUIRED_CODE' for t in n.targets)))
 required.update(str(p.relative_to(ROOT)) for folder in ('core','utils','vlm_query') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.txt'})
 bn={'ROOT':ROOT,'Path':Path,'runner':types.SimpleNamespace(REQUIRED_CODE=required,canonical_sha=w.canonical_sha),'closure':s}
 extract(ROOT/'scripts/qd_ed_n36_bridge.py',{'source_paths'},bn)
 from dataclasses import dataclass,asdict
 from typing import Optional
 from numbers import Integral,Real
 import math
 bn.update(ast=ast,copy=copy,dataclass=dataclass,asdict=asdict,Optional=Optional,Integral=Integral,Real=Real,math=math,w=w,__name__=__name__)
 extract(ROOT/'scripts/qd_ed_n32_bridge.py',{'compose_launch','resolve_constructor'},bn);b=types.SimpleNamespace(**bn)
 an={'SOURCE':ROOT,'OWNER':Path(old['resource_routing']['owner_root']),'w':w,'c':c}
 extract(ROOT/'scripts/qd_ed_n36r3_admission.py',{'owner_root'},an)
 an['BINDINGS']=('source','scientific_source','protocol','protocol_review','accounting','runtime','runtime_closure','native_build','controller_semantics','resource_routing');admission=types.SimpleNamespace(**an)
 source=load(OUT/'source.complete-v1.json');index={str(ROOT/x['path']):x['sha256'] for x in source['files']}
 runtime=load(OUT/'runtime.isolated.disabled-v1.json');closure=load(OUT/'runtime-closure.isolated.disabled-v1.json');native=load(OUT/'native-build.disabled-v1.json')
 deltas=load(OUT/'runtime-rebinding-provenance-v1.json')['source_updates'];modules=load(OUT/'runtime-rebinding-provenance-v1.json')['module_updates'];dino=load(OUT/'dino-passive-inventory-v1.json')['files']
 plan=copy.deepcopy(old);PLAN=plan
 plan.update(cohort='N36R4_NONPROGRESS_TANGENT_DEV_001467',source=source,scientific_source=source,artifact_root=str(OUT/'prospective-artifacts-001467'),expected_manifests={})
 for key,name in [('runtime','runtime.isolated.disabled-v1.json'),('runtime_closure','runtime-closure.isolated.disabled-v1.json'),('native_build','native-build.disabled-v1.json'),('controller_semantics','controller-semantics.disabled-v1.json'),('protocol','protocol.disabled-v1.json'),('accounting','accounting.disabled-v1.json')]:plan[key]=ref(OUT/name)
 plan['episodes']=load(OUT/'allocation.disabled-v1.json')['episodes'];ARITH=load(OUT/'accounting.disabled-v1.json')
 # Draft command compositions only: preserve every scientific argument; replace exact identities/output/source bindings.
 # These are explicitly NOT production external manifests and cannot substitute for bridge.manifest validation.
 prospective={}
 for oldrow,row in zip(old['episodes'],plan['episodes']):
  m=read(old['expected_manifests'][oldrow['episode_key']]);oldout=m['output_dir'];newout=str(Path(plan['artifact_root'])/'attempts'/row['episode_key'])
  argv=[v.replace(oldout,newout).replace(oldrow['episode_key'],row['episode_key']).replace(old['source']['commit'],A['source']) for v in m['argv']]
  # All prospective output destinations belong to this output, including the legacy report destination.
  argv=[('main.eds_eval.report_dir='+str(OUT/'prospective-reports-001467')) if v.startswith('main.eds_eval.report_dir=') else v for v in argv]
  config,resolved=b.compose_launch(argv,ROOT)
  expected=copy.deepcopy(m['expected_runtime'])
  if expected is not None:
   expected['binding']={'task_id':row['task_id'],'source_commit':A['source'],'run_id':row['episode_key']}
   expected['config_sha256']=hashlib.sha256(json.dumps(resolved,sort_keys=True,allow_nan=False).encode()).hexdigest()
   expected['source_hashes']={name:index[str(ROOT/name)] for name in expected['source_hashes']}
  manifest={**{k:plan[k] for k in ('resource_routing','cohort','protocol','protocol_review','accounting','source','scientific_source','native_build','runtime','runtime_closure','controller_semantics')},'schema':'n36r4-external-runtime-PROSPECTIVE-UNVALIDATED-v1','row':row,'argv':argv,'output_dir':newout,'composed_config_sha256':b.runner.canonical_sha(config) if hasattr(b.runner,'canonical_sha') else hashlib.sha256(json.dumps(config,sort_keys=True,allow_nan=False).encode()).hexdigest(),'resolved_config':resolved,'expected_runtime':expected,'release_enabled':False,'production_manifest_validation':'BLOCKED_UNSUPPORTED_COHORT','parent_manifest':old['expected_manifests'][oldrow['episode_key']]}
  # Exact identity substitution accounts for the only allowed resolved-config differences.
  def transform(x):
   if isinstance(x,str):return x.replace(oldout,newout).replace(oldrow['episode_key'],row['episode_key']).replace(old['source']['commit'],A['source'])
   if isinstance(x,dict):return {k:transform(v) for k,v in x.items()}
   if isinstance(x,list):return [transform(v) for v in x]
   return x
  assert json.loads(json.dumps(resolved))==transform(m['resolved_config']), 'scientific resolved configuration changed'
  assert config['backend']['libero']['max_episode_steps']==720 and config['policy']['rdt']['control_frequency']==20 and config['policy']['rdt']['action_chunk_horizon']==8
  prospective[row['episode_key']]=write('prospective-manifests/'+row['episode_key']+'.json',manifest)
 plan['prospective_manifests']=prospective
 plan['preparation_status']='BLOCKED_SOURCE_CONTRACT_NO_N36R4_SUPPORT'
 pr=write('plan.draft.json',plan)
 write('bindings.disabled-v1.json',{'plan':pr,**{k:plan[k] for k in admission.BINDINGS},'prospective_manifests':prospective,'production_expected_manifests':{},'release_enabled':False,'root_adopted':False,'worker_receipts_are_future':True})
 CHECKS['40_draft_compositions_scientific_equality']={'status':'PASS','count':40,'production_manifest_validation':False}
 CHECKS['fresh_identity_seed_order_limits']={'status':'PASS','count':40,'old_controls_pooled':False}
 assert 'torch' not in sys.modules, 'unexpected Torch import'
 CHECKS['no_model_or_torch_import']={'status':'PASS'}
 write('consistency-v1.json',{'source':A['source'],'cohort':plan['cohort'],'source_files':len(source['files']),'runtime_files':len(runtime['files']),'runtime_modules':len(closure['modules']),'DINO_files':len(dino),'runtime_source_updates':deltas,'closure_module_updates':modules,'native_libraries':len(native['libraries']),'expected_production_manifests':0,'prospective_composed_drafts':40,'owner_routing':plan['resource_routing'],'source_dependent_references_replaced':['source','scientific_source','runtime','runtime_closure','controller_semantics and direct evidence','protocol','accounting','episode and output identities','prospective manifest expected source hashes'],'immutable_references_preserved':['scientific protocol review','native inventory bytes','runtime dependency/model file inventories','DINO admission manifest file set','controller source findings','accepted root repair and terminal accounting anchors'],'release_enabled':False})
PLAN=None;ARITH=None
try:main()
except BaseException as e:
 ERRORS.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 signal.alarm(0)
 try:
  assert all(sha(p)==r['sha256'] for p,r in INPUTS.items())
  assert git('rev-parse','HEAD')==A['source'] and not git('status','--porcelain','--untracked-files=no')
  CHECKS['inputs_ledgers_source_unchanged']={'status':'PASS','input_count':len(INPUTS)}
 except BaseException as e:ERRORS.append({'type':type(e).__name__,'message':str(e)})
 write('checks-results-v3.json',{'checks':CHECKS,'errors':ERRORS,'seconds':time.monotonic()-START,'cpu_threads':2})
 write('input-bindings-v3.json',{'inputs':list(INPUTS.values()),'tooling_ancestry':[ref(BASE/'turns/001448/binding-refresh/refresh-bindings-v1.py'),ref(BASE/'turns/001451/manifest-refresh/refresh-v1.py')],'adaptation':'New artifact-only tool; no stale script execution, production monkeypatching, source editing, or recursive historical reconstruction.'})
 print(json.dumps({'errors':ERRORS,'artifacts':len(ART),'checks':CHECKS},indent=2))
