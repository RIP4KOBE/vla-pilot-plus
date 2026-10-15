import os,sys,json,hashlib,datetime as dt,time,posixpath
from pathlib import Path
OUT=Path(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_text());ROOT=Path(A['worktree']);BASE=OUT.parents[1];PRIOR=BASE/'001314/production-closure'
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
os.environ['GIT_NO_LAZY_FETCH']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
from scripts import qd_ed_n34_source as s
START=time.monotonic(); records=[]
def guard():
 assert not os.path.lexists(BASE.parent/'STOP')
 assert not os.path.lexists(ROOT.parents[2]/'autonomy_20261004/STOP')
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
def sha(data):return hashlib.sha256(data).hexdigest()
guard()
missing=json.loads((PRIOR/'source-materialization-v1.json').read_text())['missing']
expected={r['path']:r['sha256'] for r in json.loads((PRIOR/'source.git-expected-v1.json').read_text())['files']}
runtime=json.loads((PRIOR/'runtime-materialization-v1.json').read_text())['missing_files']
for r in runtime:
 n=str(Path(r['path']).relative_to(ROOT));assert n not in expected or expected[n]==r['sha256'];expected[n]=r['sha256']
old_plan=json.loads((BASE/'001295/plan.frozen.n36r2-v1.json').read_text())
old_runtime=json.loads(Path(old_plan['runtime']['path']).read_text())
local_index={r['sha256']:r for r in old_runtime['files']}
names=set(missing)|{str(Path(r['path']).relative_to(ROOT)) for r in runtime}
for sub in ['third_party/rdt','third_party/lerobot']:
 guard();pin,db=s.submodule_pin(ROOT,sub,A['source']);tree=s._source_tree(ROOT,pin,db)
 selected={n:tree[n[len(sub)+1:]] for n in names if n.startswith(sub+'/')}
 blobs=s._source_blobs(ROOT,[v[2] for v in selected.values()],db)
 for n,(mode,kind,blob) in sorted(selected.items()):
  guard();assert kind=='blob' and mode in ('100644','100755','120000');data=blobs[blob]
  origin_blob=blob;target=None
  if mode=='120000':
   target=posixpath.normpath(posixpath.join(posixpath.dirname(n[len(sub)+1:]),data.decode()))
   assert not target.startswith('../') and not target.startswith('/')
   target_mode,target_kind,blob=tree[target];assert target_kind=='blob' and target_mode in ('100644','100755')
   data=s._source_blobs(ROOT,[blob],db)[blob]
  local_origin=None
  if sha(data)!=expected[n]:
   assert n not in missing, 'source pin differs'
   local_origin=local_index[expected[n]]
   data=Path(local_origin['path']).read_bytes()
  assert sha(data)==expected[n],n
  p=ROOT/n
  for parent in [p,*p.parents]:
   if parent==ROOT:break
   assert not parent.is_symlink(),str(parent)
  existed=p.exists()
  if existed:assert p.read_bytes()==data
  else:
   p.parent.mkdir(parents=True,exist_ok=True)
   with p.open('xb') as f:f.write(data)
   p.chmod(0o755 if mode=='100755' else 0o644)
  records.append({'path':n,'sha256':sha(data),'bytes':len(data),'pin':pin,'git_database':str(db),'blob':blob,'mode':mode,'symlink_blob':origin_blob if target else None,'pinned_target':target,'inventoried_local_origin':local_origin,'already_present':existed,'isolated_regular_copy':True})
assert len(records)==len(names)
with (OUT/'isolated-materialization-v1.json').open('x') as f:json.dump({'records':records,'count':len(records),'source_missing_before':len(missing),'runtime_missing_before':len(runtime),'seconds':time.monotonic()-START,'network':False,'shared_writes':False},f,indent=2)
print('Materialized',len(records),'exact pinned local blobs',time.monotonic()-START)
