"""Bounded exact pinned materialization and production G2 only. All trees preflight before writes.
"""
import ast, posixpath, signal, datetime as dt, hashlib, json, os, stat, subprocess, sys, time, traceback, types
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
LEX=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001536/dependency-materialization')
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
HEAD='dcd890474b733743414d2a7711069bb0d2b0337e'
PRIOR=LEX.parents[1]/'001531'
START=time.monotonic()
STOP_PATHS=[LEX.parents[2]/'STOP',OUT.parents[2]/'STOP']
DEADLINE='2026-10-11T11:13:13Z'
os.environ.update(GIT_NO_LAZY_FETCH='1',GIT_OPTIONAL_LOCKS='0',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_ALLOW_PROTOCOL='',CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
CHECKS={}; OUTPUTS={}; INPUTS={}; BLOCKERS=[]
CHANGES=[]; DIRS=[]; ACTIVE=None; REPORTING=False
signal.alarm(1000)
def require(ok,msg):
 if not ok:raise ValueError(msg)
def stop():
 for p in STOP_PATHS:
  try:os.lstat(p)
  except FileNotFoundError:continue
  raise ValueError('STOP present: '+str(p))
 require(dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(DEADLINE.replace('Z','+00:00')),'deadline passed')
 require(time.monotonic()-START<1000,'bounded audit time exhausted')
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
   require(p.is_relative_to(OUT) or (ACTIVE==args[0] and args[2]&os.O_EXCL and args[2]&os.O_NOFOLLOW),'unauthorized write')
   if not REPORTING:stop()
 if event in ('os.mkdir','os.symlink'):
  require(ACTIVE is not None,'mutation outside bounded materializer');stop()
 if event in ('os.remove','os.rename','os.rmdir','os.chmod'):raise PermissionError('mutation forbidden')
sys.addaudithook(fence)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':sha(p)}
def load(p):
 INPUTS[str(p)]=ref(p);return json.loads(Path(p).read_text())
def save(name,value):
 
 if not REPORTING:stop()
 p=OUT/name
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
def parent_fd(relative, create=False):
 global ACTIVE
 fd=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  parts=Path(relative).parts
  for i,name in enumerate(parts[:-1]):
   try:nxt=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
   except FileNotFoundError:
    require(create,'missing parent '+relative);stop();ACTIVE=name
    try:os.mkdir(name,0o755,dir_fd=fd)
    finally:ACTIVE=None
    DIRS.append(str(Path(*parts[:i+1])))
    nxt=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
   os.close(fd);fd=nxt
  return fd
 except BaseException:
  os.close(fd);raise

def inspect_existing(row,data):
 p=ROOT/row['path']
 for ancestor in p.parents:
  if ancestor==ROOT:break
  if os.path.lexists(ancestor):require(stat.S_ISDIR(os.lstat(ancestor).st_mode),'linked/non-directory parent '+str(ancestor))
 if not os.path.lexists(p):return False
 st=os.lstat(p)
 if row['mode']=='120000':require(stat.S_ISLNK(st.st_mode) and os.fsencode(os.readlink(p))==data,'existing symlink mismatch '+str(p))
 else:
  require(stat.S_ISREG(st.st_mode),'existing nonregular destination '+str(p))
  fd=parent_fd(row['path'])
  try:
   readfd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
   with os.fdopen(readfd,'rb') as f:actual=f.read()
  finally:os.close(fd)
  require(actual==data and stat.S_IMODE(st.st_mode)==int(row['mode'][-3:],8),'existing bytes/mode mismatch '+str(p))
 return True

def main():
 global ACTIVE
 stop();INPUTS[str(Path(__file__))]=ref(Path(__file__))
 a=load(LEX/'authority-v1.json')
 for name in ('report-v1.json','blocker-v1.json'):load(PRIOR/'disabled-graph-preparation'/name)
 INPUTS[str(PRIOR/'disabled-graph-preparation/prepare-disabled-v1.py')]=ref(PRIOR/'disabled-graph-preparation/prepare-disabled-v1.py')
 load(LEX.parents[1]/'001534/dependency-materialization/report-v1.json')
 review=load(PRIOR/'owner-route-root-review-v1.json');before=ledgers(review)
 save('owning-ledgers.before-v1.json',before)
 require(a['source']==HEAD and a['worktree']==str(ROOT),'authority mismatch')
 require(git('rev-parse','HEAD').decode().strip()==HEAD,'immutable HEAD mismatch')
 require(not git('diff','--name-only','--ignore-submodules=all',HEAD,'--').strip(),'tracked modifications')
 wn={'Path':Path,'hashlib':hashlib,'json':json,'subprocess':subprocess,'os':os,'require':require}
 extract(ROOT/'scripts/qd_ed_n23_worker.py',{'_source_git','_source_entry','canonical_sha'},wn)
 wn.update(sha=sha);w=types.SimpleNamespace(**wn)
 sp=ROOT/'scripts/qd_ed_n34_source.py'
 sn={'Path':Path,'hashlib':hashlib,'subprocess':subprocess,'os':os,'w':w}
 for name in ['SOURCE_SUFFIXES','RDT','LEROBOT','LIBERO']:sn[name]=constant(sp,name)
 tree=ast.parse(sp.read_text());node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PINNED_SUBMODULES' for t in n.targets))
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(sp),'exec'),sn)
 extract(sp,{'submodule_pin','submodule_paths','dependency_paths','_source_tree','_source_blobs','source_record'},sn)
 exceptions={x['path']:x for x in a['symlink_exception']};require(len(exceptions)==12,'exception cardinality')
 inventory=[];dependencies={};payload={};seen_links=set()
 for dep,pin in a['dependency_pins'].items():
  stop();actual,db=sn['submodule_pin'](ROOT,dep,HEAD)
  require(actual==pin['commit'] and db==Path(pin['object_database']).resolve(),'pin/database mismatch')
  for p in [ROOT/dep,ROOT/'third_party']:require(stat.S_ISDIR(os.lstat(p).st_mode),'destination not regular directory')
  commit=git('--git-dir='+str(db),'cat-file','commit',actual)
  require(hashlib.sha1(b'commit '+str(len(commit)).encode()+b'\0'+commit).hexdigest()==actual,'commit object corruption')
  treeid=commit.splitlines()[0].split()[1].decode();tree=git('--git-dir='+str(db),'cat-file','tree',treeid)
  require(hashlib.sha1(b'tree '+str(len(tree)).encode()+b'\0'+tree).hexdigest()==treeid,'tree object corruption')
  entries=sn['_source_tree'](ROOT,actual,db)
  for name,(mode,kind,oid) in entries.items():
   p=Path(name);require(not p.is_absolute() and '..' not in p.parts and str(p)==name and '.git' not in p.parts,'unsafe Git path')
   require(kind=='blob' and mode in ['100644','100755','120000'],'unsupported object')
  blobs=sn['_source_blobs'](ROOT,[x[2] for x in entries.values()],db)
  for name,(mode,kind,oid) in sorted(entries.items()):
   data=blobs[oid];relative=dep+'/'+name
   row={'path':relative,'commit':actual,'object_database':str(db),'mode':mode,'kind':kind,'object_id':oid,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
   if mode=='120000':
    require(relative in exceptions,'unapproved symlink');e=exceptions[relative];seen_links.add(relative)
    require(oid==e['object_id'] and data==e['target'].encode(),'link identity/target mismatch')
    target=posixpath.normpath(posixpath.join(posixpath.dirname(name),e['target']))
    require(not posixpath.isabs(e['target']) and target==e['resolved'] and target in entries and not target.startswith('../'),'link containment mismatch')
    tm,tk,to=entries[target];require(tm in ('100644','100755') and tk=='blob','link target not regular in pinned tree')
    require(f'{tm} {tk} {to}\t{target}'==e['target_entry'],'link target entry mismatch')
    row.update(target=e['target'],resolved=target,target_object_id=to,target_sha256=hashlib.sha256(blobs[to]).hexdigest())
   row['destination_existed']=inspect_existing(row,data);row['action']='PRESERVED' if row['destination_existed'] else 'CREATE'
   inventory.append(row);payload[relative]=data
  expected=set(entries)
  for current,dirs,files in os.walk(ROOT/dep,followlinks=False):
   for name in dirs+files:
    p=Path(current)/name;relative=p.relative_to(ROOT/dep).as_posix();st=os.lstat(p)
    if stat.S_ISDIR(st.st_mode):require(any(n.startswith(relative+'/') for n in expected),'unexpected existing directory')
    else:require(relative in expected,'unexpected existing dependency entry')
  dependencies[dep]={'commit':actual,'tree':treeid,'object_database':str(db),'gitlink_verified':True,'commit_and_root_tree_object_ids_verified':True,'files':len(entries),'symlinks':sum(x[0]=='120000' for x in entries.values())}
 require(seen_links==set(exceptions),'symlink exception set differs')
 CHECKS['gitlinks_pins_local_objects']={'status':'PASS','dependencies':dependencies}
 CHECKS['atomic_preflight']={'status':'PASS','blob_identities_verified':len(inventory),'exact_symlinks':12,'existing_mismatches':0,'path_traversal':0}
 save('pinned-object-preflight-v1.json',{'files':inventory,'dependencies':dependencies,'all_blob_object_ids_verified':True})
 print('Preflight PASS:',len(inventory),'entries; materializing regular files before links',flush=True)
 os.umask(0o022)
 for row in sorted(inventory,key=lambda x:(x['mode']=='120000',x['path'])):
  stop();data=payload[row['path']]
  if row['destination_existed']:require(inspect_existing(row,data),'existing entry disappeared');continue
  fd=parent_fd(row['path'],create=True);name=Path(row['path']).name
  try:
   if row['mode']=='120000':
    dep=next(d for d in dependencies if row['path'].startswith(d+'/'))
    targetrow=next(x for x in inventory if x['path']==dep+'/'+row['resolved'])
    require(inspect_existing(targetrow,payload[targetrow['path']]),'regular target not materialized')
    ACTIVE=name
    try:os.symlink(row['target'],name,dir_fd=fd)
    finally:ACTIVE=None
   else:
    ACTIVE=name
    try:outfd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,int(row['mode'][-3:],8),dir_fd=fd)
    finally:ACTIVE=None
    with os.fdopen(outfd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
   CHANGES.append({'path':row['path'],'action':'created_symlink' if row['mode']=='120000' else 'created_regular','object_id':row['object_id'],'sha256':row['sha256'],'bytes':row['bytes']})
  finally:os.close(fd)
 for row in inventory:require(inspect_existing(row,payload[row['path']]),'post-materialization entry missing')
 inv=save('materialized-inventory-v1.json',{'dependencies':dependencies,'files':inventory,'changes':CHANGES,'created_directories':DIRS,'all_final_bytes_and_modes_verified':True,'symlink_hash_semantics':'SHA256 and Git blob identity of literal target bytes; not dereferenced content'})
 CHECKS['exact_materialized_inventory']={'status':'PASS','entries':len(inventory),'created':len(CHANGES),'preserved':sum(x['destination_existed'] for x in inventory),'inventory':inv}
 required=constant(ROOT/'scripts/qd_ed_final_runner.py','REQUIRED_CODE')
 required.update(str(p.relative_to(ROOT)) for folder in ('core','utils','vlm_query') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.txt'})
 bn={'ROOT':ROOT,'Path':Path,'runner':types.SimpleNamespace(REQUIRED_CODE=required),'closure':types.SimpleNamespace(**sn)}
 extract(ROOT/'scripts/qd_ed_n36_bridge.py',{'source_paths','scientific_paths'},bn)
 paths=bn['source_paths'](ROOT);require('scripts/qd_ed_poe_launch.py' in paths,'launcher omitted');require(paths==bn['scientific_paths'](ROOT),'scientific inventory differs')
 require(not (paths & set(exceptions)),'documentation exception in source closure')
 save('source-paths-v1.json',{'paths':sorted(paths),'required_count':len(paths),'missing':[],'excluded_paths':[]})
 source=sn['source_record'](ROOT,paths,commit=HEAD)
 require(len(source['files'])==len(paths),'inventory incomplete')
 sr=save('source.complete-v1.json',source)
 CHECKS['G2_exact_production_source_record']={'status':'PASS','required_count':len(paths),'verified_count':len(source['files']),'excluded_paths':[],'source':sr,'production_invocations':1}
 eroot=ROOT/'scripts/qd_ed_n36_engineering.py';base=constant(eroot,'BASE');operational=constant(eroot,'OPERATIONAL_FILES')
 changed=git('diff','--name-only',base,HEAD,'--').decode().splitlines();git('merge-base','--is-ancestor',base,HEAD)
 require(set(changed)==operational,'operational exact delta mismatch')
 CHECKS['G2_BASE_ancestry_and_exact_operational_delta']={'status':'PASS','base':base,'changed_paths':sorted(changed),'operational_files':sorted(operational),'exact_set_equality':True}
 eq={'schema':'n36-engineering-scientific-equivalence-v1','base_commit':base,'source':source,'changed_paths':sorted(changed),'scientific_changes':False}
 eqref=save('scientific-equivalence-v1.json',eq)
 def read(r):
  require(sha(r['path'])==r['sha256'],'reference mismatch');return json.loads(Path(r['path']).read_text())
 en={'SOURCE':ROOT,'BASE':base,'OPERATIONAL_FILES':operational,'subprocess':subprocess,'w':w,'read':read}
 extract(eroot,{'exact','scientific_equivalence','require_dispatch_implementation'},en)
 en['scientific_equivalence']({'source':source,'scientific_equivalence':eqref})
 CHECKS['G2_production_scientific_equivalence']={'status':'PASS','reference':eqref,'source_and_scientific_record_identical':True}
 try:en['require_dispatch_implementation']()
 except RuntimeError as exc:CHECKS['dispatch_veto']={'status':'PASS','message':str(exc)}
 else:raise ValueError('dispatch veto absent')
 save('source-delta-v1.json',{'base_commit':base,'base_ancestor':True,'source_commit':HEAD,'changed_paths':sorted(changed),'operational_files':sorted(operational),'exact_set_equality':True,'source':sr,'scientific_equivalence':eqref,'inventory_files':len(source['files']),'source_and_scientific_record_identical':True})
 require(git('rev-parse','HEAD').decode().strip()==HEAD,'HEAD changed')
 require(not git('diff','--name-only','--ignore-submodules=all',HEAD,'--').strip(),'tracked files changed')
 after=ledgers(review);require(before==after,'owning ledgers changed')
 save('owning-ledger-preservation-v1.json',{'before':before,'after':after,'all_prefixes_unchanged':True,'whole_files_unchanged':True})
 CHECKS['immutable_HEAD_existing_bytes_and_owning_ledgers']={'status':'PASS','head':HEAD,'ledger_prefixes_unchanged':True,'ledger_whole_files_unchanged':True,'existing_entries_never_opened_for_write':True,'prohibited_untracked_file_opened':False}
 forbidden={'torch','numpy','scipy','pandas','sklearn','mujoco','robosuite','libero','transformers','diffusers','cv2','hydra','omegaconf'}
 require(not any(n.split('.')[0] in forbidden for n in sys.modules),'prohibited import')
 CHECKS['no_native_model_imports']={'status':'PASS'}
 stop();CHECKS['STOP_deadline']={'status':'PASS','paths':[str(x) for x in STOP_PATHS],'deadline':DEADLINE}

status='PASS_DEPENDENCY_MATERIALIZATION_AND_G2';error=None
try:main()
except BaseException as exc:
 status='BLOCKED_MATERIALIZATION_OR_G2';error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
REPORTING=True
report={'schema':'n36-dependency-materialization-report-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'node_id':'15.6','status':status,'source':HEAD,'candidate_worktree':str(ROOT),'checks':CHECKS,'inputs':list(INPUTS.values()),'outputs':OUTPUTS.copy(),'error':error,'materialization_changes':CHANGES,'created_directories':DIRS,'materialized_files':len(CHANGES),'source_edited':False,'source_adopted':False,'owner_state_writes':False,'dispatch_enabled':False,'release_enabled':False,'gpu_used':False,'network_used':False,'native_model_modules_imported':False,'G3_G4_executed':False,'scientific_score_produced':False,'goal_complete':False,'bounded_source_closure_task_complete':error is None,'remaining_blockers':([error['message']] if error else [])+['G3 runtime rebind and G4 generated module closure remain unexecuted.','G5 disabled audit/manifests, G6 graph/B5 verification, and G7 reviewed implementation/adoption remain unresolved; dispatch veto retained.'],'next_bounded_step':'Review this exact G2 closure, then separately scope disabled G3/G4 preparation using source.complete-v1.json; retain unconditional dispatch veto. No source adoption or dispatch authorized.','verification_method':'Unmodified production helpers extracted via AST; complete exact source_paths including tracked launcher hashed only; all pinned blobs and 12 literal symlink targets verified; exclusive descriptor-relative no-follow writes after whole-tree preflight; no production imports or G3/G4.','elapsed_seconds':time.monotonic()-START,'executor_skill':'/home/hynx/.codex/skills/arbor-agent-executor/SKILL.md','nested_agents':False}
save('report-v1.json',report)
print(json.dumps({'status':status,'error':error,'report':OUTPUTS['report-v1.json'],'materialized_files':len(CHANGES),'checks':{k:v['status'] for k,v in CHECKS.items()}},indent=2))
sys.exit(1 if error else 0)
