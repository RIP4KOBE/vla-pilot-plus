from pathlib import Path
import json,hashlib,subprocess,datetime
P=Path(__file__).resolve().parent;I=P/'implementation';base='6292fc8cffad2eec0f789e023d835ad3c1df146a';commit='7428ce8a51f76c5f641537be9a7614631d82b0d9'
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':sha(b),'bytes':len(b)}
old=json.loads((I/'docs/experiments/n31/base-source-v1.json').read_text());reverse=json.loads((I/'docs/experiments/n31/reverse-source-v1.json').read_text())
assert old['commit']==base and len(old['files'])==480
changed={'main.py','core/rdt_policy_steer.py','configs/config.yaml','scripts/audit_decision_evidence.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
assert reverse['base_commit']==base and set(reverse['files'])==changed
diff=subprocess.check_output(['git','diff','--name-status',base,commit],cwd=I).decode().splitlines()
mods={l.split('\t')[1] for l in diff if l.startswith('M\t')};adds={l.split('\t')[1] for l in diff if l.startswith('A\t')}
assert mods==changed and len(diff)==len(mods)+len(adds)
paths={x['path'] for x in old['files']}|adds
assert not any('2026-08-10-eds-qd-stage-guidance-transition-design' in x for x in paths)
files=[]
for path in sorted(paths):
 b=(I/path).read_bytes();assert b==subprocess.check_output(['git','show',commit+':'+path],cwd=I)
 files.append({'path':path,'sha256':sha(b)})
for row in old['files']:
 path=row['path'];b=(I/path).read_bytes()
 if path in changed:
  e=reverse['files'][path];assert e['new_sha256']==sha(b) and e['old_sha256']==row['sha256']
  lines=b.decode().splitlines(keepends=True)
  for h in reversed(e['hunks']):
   assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
  b=''.join(lines).encode()
  assert b==subprocess.check_output(['git','show',base+':'+path],cwd=I)
 assert sha(b)==row['sha256'],path
assert not subprocess.check_output(['git','status','--porcelain'],cwd=I)
out={'schema':'n31-root-phase-c-source-bytes-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':commit,'base_commit':base,'base_files':480,'unchanged_base_files':474,'changed_existing':sorted(changed),'new_files':len(adds),'complete_source_files':files,'git_blobs_verified':len(files),'reverse':ref(I/'docs/experiments/n31/reverse-source-v1.json'),'source_clean':True,'byte_equivalence_is_not_new_algorithm_validity':True,'root_numerical_replay':False,'gpu_authorized':False,'budget_changed':False,'target_achieved':False}
p=P/'root-phase-c-source-bytes-review-v1.json'
with p.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'review':ref(p),'files':len(files),'new':len(adds),'old_unchanged':474,'reversed':6}))

