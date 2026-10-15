"""Independent final N30 repair source/Git/byte-scope review; no experiment code."""
from pathlib import Path
import datetime,hashlib,json,subprocess
K=Path(__file__).resolve().parent;I=K/'implementation';P=K.parent;DOC=I/'docs/experiments/n30/r1'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ref=lambda p:{'path':str(Path(p).resolve()),'sha256':sha(p)}
canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=I)
source=read(K/'source-manifest-execution-v1.json');base=read(DOC/'base-source-v1.json');reverse=read(DOC/'reverse-source-v1.json')
head='b2775fa2008a8a88e374c43a5753f8862485af1f';parent='7c0d80d734fa8300173e56d9a8de03415bc55fe2'
assert source['commit']==head and base['commit']==parent
assert source['sha256']==canonical(source['files']) and base['sha256']==canonical(base['files'])
assert len(source['files'])==457 and len(base['files'])==441
assert git('rev-parse','HEAD').decode().strip()==head and git('status','--porcelain')==b''
assert subprocess.run(['git','merge-base','--is-ancestor',parent,head],cwd=I).returncode==0
baseindex={x['path']:x['sha256'] for x in base['files']};index={x['path']:x['sha256'] for x in source['files']}
assert len(baseindex)==441 and len(index)==457
changed=git('diff','--name-only',parent,head).decode().splitlines()
modified=set(changed)&set(baseindex);added=set(changed)-set(baseindex)
assert modified=={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'} and len(added)==16
assert set(index)==set(baseindex)|added
assert all(name.startswith(('docs/experiments/n30/r1/','scripts/qd_ed_n30_r1_','tests/test_n30_r1_','tests/n30_r1_')) for name in added)
for name,digest in index.items():
 assert Path(name).is_absolute() is False and '..' not in Path(name).parts
 assert sha(I/name)==digest==hashlib.sha256(git('show',head+':'+name)).hexdigest(),name
for name,digest in baseindex.items():
 assert hashlib.sha256(git('show',parent+':'+name)).hexdigest()==digest
 if name not in modified:assert index[name]==digest,name
assert set(reverse['files'])==modified
for name in modified:
 e=reverse['files'][name];lines=(I/name).read_text().splitlines(keepends=True)
 assert e['old_sha256']==baseindex[name] and e['new_sha256']==index[name]
 for h in reversed(e['hunks']):
  assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
 assert ''.join(lines).encode()==git('show',parent+':'+name)
assert (DOC/'cpu-integration-scope-v1.md').read_bytes()==(K/'cpu-integration-scope-v1.md').read_bytes()
assert (DOC/'root-cpu-integration-release-v1.json').read_bytes()==(K/'root-cpu-integration-release-v1.json').read_bytes()
assert (DOC/'original-source-v1.json').read_bytes()==(P/'source-manifest-execution-v1.json').read_bytes()
assert index['main.py']=='5209b0ac07362e1df85bf2fd842e57d4786e24c0a625ee5b9e49bee48f528f93'
repair=read(P/'initial-observation-repair-v1/root-cpu-repair-review-v1.json')
assert repair['commit']==parent and repair['disposition']=='ACCEPT_CPU_REPAIR_ONLY'
out={'schema':'n30-r1-root-source-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'ACCEPT_SOURCE_BYTE_SCOPE','commit':head,'repair_base':parent,'source':ref(K/'source-manifest-execution-v1.json'),
 'source_files_rehashed_and_git_bound':457,'repair_base_files_independently_git_bound':441,
 'existing_source_files_unchanged':439,'existing_files_changed':sorted(modified),'added_files':sorted(added),
 'reverse_hunks_independently_reconstruct_full_original_bytes':True,'main_byte_identical_to_accepted_repair':True,
 'initial_repair_review':ref(P/'initial-observation-repair-v1/root-cpu-repair-review-v1.json'),
 'manual_review':'Root read all five new operational modules, both existing-file diffs and CPU regression cases; original algorithm/helper/native/provider/profile bytes unchanged.',
 'scientific_candidate':'N30 unchanged','cpu_or_gpu_numerical_replay':False,'gpu_release':False,'goal_status':'TARGET_NOT_MET'}
with (K/'root-source-review-execution-v1.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({k:out[k] for k in ('decision','commit','source_files_rehashed_and_git_bound','existing_source_files_unchanged','existing_files_changed')}))

