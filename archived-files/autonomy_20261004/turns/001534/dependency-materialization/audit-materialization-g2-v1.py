"""Bounded read-only pin preflight and exact production G2 audit. No G3/G4.
Exact dependency tree rejected atomically if it contains symlinks; no partial tree adoption.
"""
import ast, datetime as dt, hashlib, json, os, stat, subprocess, sys, time, traceback, types
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
LEX=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001534/dependency-materialization')
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
HEAD='dcd890474b733743414d2a7711069bb0d2b0337e'
PRIOR=LEX.parents[1]/'001531'
START=time.monotonic()
STOP_PATHS=[LEX.parents[2]/'STOP',OUT.parents[2]/'STOP']
DEADLINE='2026-10-11T11:13:13Z'
os.environ.update(GIT_NO_LAZY_FETCH='1',GIT_OPTIONAL_LOCKS='0',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_ALLOW_PROTOCOL='',CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
CHECKS={}; OUTPUTS={}; INPUTS={}; BLOCKERS=[]
def require(ok,msg):
 if not ok:raise ValueError(msg)
def stop():
 for p in STOP_PATHS:
  try:os.lstat(p)
  except FileNotFoundError:continue
  raise ValueError('STOP present: '+str(p))
 require(dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(DEADLINE.replace('Z','+00:00')),'deadline passed')
 require(time.monotonic()-START<900,'bounded audit time exhausted')
def fence(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='import':require(args[0].split('.')[0] not in {'torch','numpy','scipy','pandas','sklearn','mujoco','robosuite','libero','transformers','diffusers','cv2','hydra','omegaconf'},'native/model import forbidden')
 if event=='subprocess.Popen':
  argv=args[1];require(isinstance(argv,(list,tuple)) and argv[0]=='git' and any(x in argv for x in ['rev-parse','diff','ls-tree','cat-file','merge-base']),'passive Git only')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=Path(os.path.abspath(os.fsdecode(args[0])));low=str(p).lower()
  require(not any(s in low for s in ['2026-08-10-eds-qd-stage-guidance-transition-design.md','/.codex/auth','credential','/validation/','/formal/']),'forbidden file')
  if 'poe' in low:require(p==ROOT/'scripts/qd_ed_poe_launch.py','Poe files forbidden')
  if isinstance(args[2],int) and args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
   require(p.is_relative_to(OUT),'only output writes');stop()
 if event in ('os.mkdir','os.remove','os.rename','os.rmdir','os.chmod','os.symlink'):raise PermissionError('filesystem mutation forbidden except new output files')
sys.addaudithook(fence)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':sha(p)}
def load(p):
 INPUTS[str(p)]=ref(p);return json.loads(Path(p).read_text())
def save(name,value):
 stop();p=OUT/name
 with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
 OUTPUTS[name]=ref(p);return {'path':str(p),'sha256':OUTPUTS[name]['sha256']}
def git(*args):return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args])
def extract(path,names,ns):
 INPUTS[str(path)]=ref(path);tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
 require({n.name for n in nodes}==set(names),'helpers missing');exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
def constant(path,name):
 INPUTS[str(path)]=ref(path);tree=ast.parse(path.read_text());n=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
 return frozenset(ast.literal_eval(n.args[0])) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='frozenset' else ast.literal_eval(n)
def ledgers(review):
 rows={}
 for name,anchor in review['ledger_prefixes'].items():
  p=Path(anchor['path']);require('/study_worktree/data/' in str(p),'not owning state')
  with p.open('rb') as f:prefix=f.read(anchor['bytes'])
  require(len(prefix)==anchor['bytes'] and hashlib.sha256(prefix).hexdigest()==anchor['sha256'],'owner prefix changed')
  rows[name]={'anchor':anchor,'current':ref(p),'prefix_unchanged':True}
 return rows

def main():
 stop();INPUTS[str(Path(__file__))]=ref(Path(__file__))
 a=load(LEX/'authority-v1.json');prior=load(PRIOR/'disabled-graph-preparation/report-v1.json');blocker=load(PRIOR/'disabled-graph-preparation/blocker-v1.json')
 INPUTS[str(PRIOR/'disabled-graph-preparation/prepare-disabled-v1.py')]=ref(PRIOR/'disabled-graph-preparation/prepare-disabled-v1.py')
 review=load(PRIOR/'owner-route-root-review-v1.json');before=ledgers(review)
 require(a['source']==HEAD and a['worktree']==str(ROOT),'authority mismatch')
 require(git('rev-parse','HEAD').decode().strip()==HEAD,'immutable HEAD mismatch')
 require(not git('diff','--name-only','--ignore-submodules=all',HEAD,'--').strip(),'tracked modifications')
 common=Path(git('rev-parse','--git-common-dir').decode().strip())
 inventory=[];dependencies={}
 wn={'Path':Path,'hashlib':hashlib,'json':json,'subprocess':subprocess,'os':os,'require':require}
 extract(ROOT/'scripts/qd_ed_n23_worker.py',{'_source_git','_source_entry','canonical_sha'},wn)
 wn.update(sha=sha);w=types.SimpleNamespace(**wn)
 sp=ROOT/'scripts/qd_ed_n34_source.py'
 sn={'Path':Path,'hashlib':hashlib,'subprocess':subprocess,'os':os,'w':w}
 for name in ['SOURCE_SUFFIXES','RDT','LEROBOT','LIBERO']:sn[name]=constant(sp,name)
 tree=ast.parse(sp.read_text());node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PINNED_SUBMODULES' for t in n.targets))
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(sp),'exec'),sn)
 extract(sp,{'submodule_pin','submodule_paths','dependency_paths','_source_tree','_source_blobs','source_record'},sn)
 for dep,pin in a['dependency_pins'].items():
  stop();actual,db=sn['submodule_pin'](ROOT,dep,HEAD)
  require(actual==pin['commit'] and db==Path(pin['object_database']).resolve(),'pin/database mismatch')
  for p in [ROOT/dep,ROOT/'third_party']:require(not p.is_symlink(),'destination symlink')
  require((ROOT/dep).is_dir() and not list((ROOT/dep).iterdir()),'existing dependency entries require separate mismatch preflight')
  commit=git('--git-dir='+str(db),'cat-file','commit',actual)
  require(hashlib.sha1(b'commit '+str(len(commit)).encode()+b'\0'+commit).hexdigest()==actual,'commit object corruption')
  treeid=commit.splitlines()[0].split()[1].decode()
  tree=git('--git-dir='+str(db),'cat-file','tree',treeid)
  require(hashlib.sha1(b'tree '+str(len(tree)).encode()+b'\0'+tree).hexdigest()==treeid,'tree object corruption')
  entries=sn['_source_tree'](ROOT,actual,db)
  for name,(mode,kind,oid) in entries.items():
   p=Path(name);require(not p.is_absolute() and '..' not in p.parts and str(p)==name and '.git' not in p.parts,'unsafe Git path')
   require(kind=='blob' and mode in ['100644','100755','120000'],'unsupported object')
  blobs=sn['_source_blobs'](ROOT,[x[2] for x in entries.values()],db)
  for name,(mode,kind,oid) in sorted(entries.items()):
   data=blobs[oid];row={'path':dep+'/'+name,'commit':actual,'object_database':str(db),'mode':mode,'kind':kind,'object_id':oid,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'destination_existed':False,'action':'NOT_MATERIALIZED_ATOMIC_PREFLIGHT_REJECTION'}
   if mode=='120000':row['rejection']='SYMLINK_ENTRY';BLOCKERS.append({'path':row['path'],'mode':mode,'object_id':oid,'reason':'Pinned tree symlink forbidden by user; not created, followed or converted.'})
   inventory.append(row)
  dependencies[dep]={'commit':actual,'tree':treeid,'object_database':str(db),'gitlink_verified':True,'commit_and_root_tree_object_ids_verified':True,'files':len(entries),'symlinks':sum(x[0]=='120000' for x in entries.values()),'existing_entries':0}
 require(bool(BLOCKERS),'This rejection-only artifact must not materialize a tree; expected symlink blocker absent')
 save('pinned-object-inventory-v1.json',{'schema':'n36-pinned-object-inventory-v1','dependencies':dependencies,'files':inventory,'all_blob_object_ids_verified':True,'materialized_files':[],'created_directories':[]})
 CHECKS['gitlinks_pins_local_objects']={'status':'PASS','dependencies':dependencies}
 CHECKS['symlink_and_path_preflight']={'status':'BLOCKED','symlink_entries':len(BLOCKERS),'path_traversal_entries':0,'atomic_preflight':True}
 required=constant(ROOT/'scripts/qd_ed_final_runner.py','REQUIRED_CODE')
 required.update(str(p.relative_to(ROOT)) for folder in ('core','utils','vlm_query') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.txt'})
 bn={'ROOT':ROOT,'Path':Path,'runner':types.SimpleNamespace(REQUIRED_CODE=required),'closure':types.SimpleNamespace(**sn)}
 extract(ROOT/'scripts/qd_ed_n36_bridge.py',{'source_paths'},bn)
 paths=bn['source_paths'](ROOT);require('scripts/qd_ed_poe_launch.py' in paths,'full closure omitted launcher')
 missing=sorted(p for p in paths if not (ROOT/p).is_file())
 save('source-paths-v1.json',{'paths':sorted(paths),'required_count':len(paths),'missing':missing,'excluded_paths':[]})
 try:sn['source_record'](ROOT,paths,commit=HEAD)
 except ValueError as exc:CHECKS['G2_exact_production_source_record']={'status':'BLOCKED','message':str(exc),'required_count':len(paths),'missing_count':len(missing),'excluded_paths':[]}
 else:raise ValueError('unexpected G2 pass with absent dependencies')
 # Available subset is diagnostic only. Never label this the complete G2 source record.
 partial=sn['source_record'](ROOT,paths-set(missing),commit=HEAD)
 save('source-inventory.available-diagnostic-v1.json',{'production_g2_accepted':False,'required_count':len(paths),'verified_available_count':len(partial['files']),'missing_count':len(missing),'excluded_paths':[],'diagnostic_record':partial})
 eroot=ROOT/'scripts/qd_ed_n36_engineering.py';base=constant(eroot,'BASE');operational=constant(eroot,'OPERATIONAL_FILES')
 changed=git('diff','--name-only',base,HEAD,'--').decode().splitlines();git('merge-base','--is-ancestor',base,HEAD)
 require(set(changed)==operational,'operational exact delta mismatch')
 CHECKS['G2_BASE_ancestry_and_exact_operational_delta']={'status':'PASS','base':base,'changed_paths':sorted(changed),'operational_files':sorted(operational),'exact_set_equality':True}
 CHECKS['G2_production_scientific_equivalence']={'status':'BLOCKED_NOT_RUN','reason':'Complete source record absent; partial inventory cannot be supplied as full scientific equivalence evidence.'}
 en={};extract(eroot,{'require_dispatch_implementation'},en)
 try:en['require_dispatch_implementation']()
 except RuntimeError as exc:CHECKS['dispatch_veto']={'status':'PASS','message':str(exc)}
 else:raise ValueError('dispatch veto absent')
 require(git('rev-parse','HEAD').decode().strip()==HEAD,'HEAD changed')
 require(not git('diff','--name-only','--ignore-submodules=all',HEAD,'--').strip(),'tracked files changed')
 for dep in a['dependency_pins']:require(not list((ROOT/dep).iterdir()),'dependency files changed')
 after=ledgers(review);require(before==after,'owning ledgers changed during audit')
 save('owning-ledger-preservation-v1.json',{'before':before,'after':after,'all_prefixes_unchanged':True,'whole_files_unchanged':True})
 CHECKS['immutable_HEAD_existing_bytes_and_owning_ledgers']={'status':'PASS','head':HEAD,'checkout_write_operations':0,'ledger_prefixes_unchanged':True,'ledger_whole_files_unchanged':True,'prohibited_untracked_file_opened':False}
 CHECKS['STOP_deadline']={'status':'PASS','paths':[str(x) for x in STOP_PATHS],'deadline':DEADLINE};stop()
 save('blocker-v1.json',{'schema':'n36-dependency-materialization-blocker-v1','status':'BLOCKED_PINNED_TREE_SYMLINKS','symlinks':BLOCKERS,'materialization_changes':[],'missing_source_paths':missing})

status='BLOCKED_PINNED_TREE_SYMLINKS';error=None
try:main()
except BaseException as exc:
 status='BLOCKED_AUDIT_ERROR';error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
report={'schema':'n36-dependency-materialization-report-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'node_id':'15.6','status':status,'source':HEAD,'candidate_worktree':str(ROOT),'checks':CHECKS,'inputs':list(INPUTS.values()),'outputs':OUTPUTS.copy(),'error':error,'materialization_changes':[],'materialized_files':0,'source_edited':False,'source_adopted':False,'owner_state_writes':False,'dispatch_enabled':False,'release_enabled':False,'gpu_used':False,'network_used':False,'native_model_modules_imported':False,'G3_G4_executed':False,'scientific_score_produced':False,'goal_complete':False,'remaining_blockers':['Exact LeRobot tree contains 12 forbidden symlink entries; atomic preflight rejected both dependency trees before checkout writes.','G2 full source_record remains blocked by 537 absent dependency source files.','G2 scientific equivalence cannot be emitted without complete source_record.','G3/G4 and later gates remain outside this task.'],'next_bounded_step':'Resolve the exact-tree versus no-symlink constraint for the 12 enumerated pinned LeRobot entries. A subsequent explicitly scoped executor can materialize an authorized representation from the same local pins, rerun full G2, and retain dispatch veto. Do not call the 573-file available diagnostic complete source evidence.','verification_method':'Unmodified passive production helper functions extracted by AST; exact source_paths; local Git object identity checks; no production imports. All-or-nothing preflight; no dependency bytes written.','elapsed_seconds':time.monotonic()-START,'executor_skill':'/home/hynx/.codex/skills/arbor-agent-executor/SKILL.md','nested_agents':False}
save('report-v1.json',report)
print(json.dumps({'status':status,'report':OUTPUTS['report-v1.json'],'materialized_files':0,'checks':{k:v['status'] for k,v in CHECKS.items()}},indent=2))
