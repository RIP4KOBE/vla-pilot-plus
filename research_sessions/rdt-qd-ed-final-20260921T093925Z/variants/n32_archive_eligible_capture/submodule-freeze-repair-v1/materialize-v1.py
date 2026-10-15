import hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd().resolve(); out=root.parent/'submodule-freeze-repair-v1'
env={**os.environ,'GIT_NO_LAZY_FETCH':'1','CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
commands=[]
def git(*args):
 command=['git','--no-replace-objects',*args]
 p=subprocess.run(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 commands.append({'argv':command,'exit':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr':p.stderr.decode()})
 p.check_returncode();return p.stdout
super_commit=git('rev-parse','HEAD').decode().strip()
assert super_commit=='79f7cd2790cc667726a7cbe872a0a7f349a0e5b4'
entry=git('ls-tree',super_commit,'third_party/rdt').decode().split()
assert entry[:2]==['160000','commit']
pin=entry[2]
common=Path(git('rev-parse','--git-common-dir').decode().strip());common=(root/common).resolve()
database=common/'modules/third_party/rdt'
# Snapshot shared administrative files; all Git commands below are read-only.
def state():
 return {str(p.relative_to(database)):hashlib.sha256(p.read_bytes()).hexdigest() for p in database.rglob('*') if p.is_file() and not p.is_relative_to(database/'objects')}
before=state()
assert git('--git-dir='+str(database),'cat-file','-t',pin).strip()==b'commit'
relative='scripts/maniskill_model.py'
row=git('--git-dir='+str(database),'ls-tree',pin,'--',relative).decode().split()
assert row[:2]==['100644','blob']
blob=row[2];data=git('--git-dir='+str(database),'cat-file','blob',blob)
path=root/'third_party/rdt'/relative
assert not path.exists() and not path.is_symlink()
assert not any(p.is_symlink() for p in (path.parent,path.parent.parent,path.parent.parent.parent))
path.parent.mkdir(parents=True,exist_ok=True)
with path.open('xb') as stream:stream.write(data)
assert path.read_bytes()==data
assert state()==before
result={'superproject_commit':super_commit,'gitlink_path':'third_party/rdt','gitlink_commit':pin,'object_database':str(database),'blob':blob,'materialized_path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'method':'exclusive regular-file write from pinned local cat-file blob; no submodule checkout/init; no .git pointer created','shared_administration_unchanged':True,'shared_administration_hashes':before,'commands':commands}
(out/'materialization-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('commands','shared_administration_hashes')},indent=2))
