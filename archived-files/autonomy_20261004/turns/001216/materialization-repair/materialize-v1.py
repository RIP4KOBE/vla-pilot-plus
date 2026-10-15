import os,sys,json,hashlib,stat,subprocess,datetime,time
from pathlib import Path
BASE=Path(__file__).resolve().parent; ROOT=Path.cwd(); TURNS=BASE.parent.parent
START=time.monotonic(); SOURCE='066f2bf57e05111fea329ff7c393ac3e002d7c0f'
def guard():
 assert not os.path.lexists(ROOT.parent.parent.parent/'autonomy_20261004/STOP')
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
 assert time.monotonic()-START<1200 and os.environ['CUDA_VISIBLE_DEVICES']=='' and os.environ['PYTHONDONTWRITEBYTECODE']=='1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,d):
 guard();p=BASE/n
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
def git(*args):return subprocess.check_output(['git','--no-replace-objects',*args],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_NO_LAZY_FETCH':'1'}).decode()
def status():return {'source':git('rev-parse','HEAD').strip(),'git_status':git('status','--porcelain'),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
guard();before=status();assert before['source']==SOURCE and before['git_status']==''
a=json.loads((BASE/'authority-v1.json').read_text());assert a['implementation_worktree']==str(ROOT) and a['output_directory']==str(BASE)
refs={}
for k in ['standing_authority','source_adoption','prior_terminal']:
 r=a[k];assert sha(r['path'])==r['sha256'];refs[k]={**r,'verified':True}
ledgers={}
for k,r in a['ledger_prefixes'].items():
 assert sha(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['bytes'];ledgers[k]={**r,'unchanged':True}
write('authority-verification-v1.json',{'bindings':refs,'ledgers':ledgers,'before':before,'STOP_present':False,'deadline':'2026-10-11T11:13:13Z'})
sys.path.insert(0,str(ROOT));from scripts import qd_ed_n36_bridge as b
prior=json.loads((TURNS/'001185/runtime-preparation/materialization-v1.json').read_text());rows=[];pins={};conflicts=[]
for sub in b.closure.PINNED_SUBMODULES:
 guard();pin,db=b.closure.submodule_pin(ROOT,sub);name=Path(sub).name;entry=next(x for x in prior if x['dependency']==name);assert pin==entry['pin'];pins[sub]=pin
 entries=b.closure._source_tree(ROOT,pin,db);paths=sorted(b.closure.submodule_paths(ROOT,sub));selected={p:entries[p[len(sub)+1:]] for p in paths}
 blobs=b.closure._source_blobs(ROOT,[v[2] for v in selected.values()],db)
 for rel,v in selected.items():
  src=TURNS/'001185/runtime-preparation/materialized'/name/rel[len(sub)+1:];dst=ROOT/rel
  assert v[0] in ('100644','100755') and v[1]=='blob'
  assert src.is_file() and not any(p.is_symlink() for p in [src,*src.parents])
  data=src.read_bytes();assert data==blobs[v[2]],rel
  if any(p.is_symlink() for p in [dst,*dst.parents]):conflicts.append({'path':rel,'reason':'linked destination'})
  exists=os.path.lexists(dst)
  if exists and (not dst.is_file() or dst.read_bytes()!=data):conflicts.append({'path':rel,'reason':'differing/nonregular existing destination'})
  rows.append({'path':rel,'source_path':str(src),'pin':pin,'git_blob':v[2],'mode':v[0],'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'existed_before':exists,'action':'preserve_identical' if exists else 'copy'})
write('target-inspection-v1.json',{'before':before,'pins':pins,'files':rows,'conflicts':conflicts,'count':len(rows),'all_inspected_before_copy':True})
assert not conflicts,'Conflicts preserved; no copies performed'
for row in rows:
 guard()
 if row['existed_before']:continue
 dst=ROOT/row['path'];src=Path(row['source_path']);data=src.read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
 dst.parent.mkdir(parents=True,exist_ok=True)
 with dst.open('xb') as f:f.write(data)
 dst.chmod(int(row['mode'],8)&0o777);assert sha(dst)==row['sha256']
record=b.closure.source_record(ROOT,b.source_paths(ROOT),commit=SOURCE)
write('source-record-v1.json',record)
write('materialization-v1.json',{'before':before,'after':status(),'pins':pins,'files':rows,'copied_count':sum(not r['existed_before'] for r in rows),'copied_bytes':sum(r['bytes'] for r in rows if not r['existed_before']),'strict_source_record':'PASS','source_count':len(record['files']),'source_record_sha256':sha(BASE/'source-record-v1.json')})
print(json.dumps({'copied':sum(not r['existed_before'] for r in rows),'source_count':len(record['files']),'pins':pins,'after':status()}))
