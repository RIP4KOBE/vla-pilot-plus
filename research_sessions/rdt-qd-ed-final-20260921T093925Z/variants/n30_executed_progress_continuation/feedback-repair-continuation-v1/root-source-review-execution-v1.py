"""Independent root source, delivery, resource and finite metadata review."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys,os,time,resource
L=Path(__file__).resolve().parent;I=L/'implementation';P=L.parent;DOC=I/'docs/experiments/n30/r2'
os.sched_setaffinity(0,{0,1});os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
sys.dont_write_bytecode=True
start=time.process_time();read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ref=lambda p:{'path':str(Path(p).resolve()),'sha256':sha(p)}
canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=I)
def emit(path,data):
 with path.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
head='6292fc8cffad2eec0f789e023d835ad3c1df146a';parent='debda23a0e8eda86a3bb4f398e9596edf05b37e5'
source=read(L/'source-manifest-execution-v1.json');base=read(DOC/'base-source-v1.json');reverse=read(DOC/'reverse-source-v1.json')
assert source['commit']==head and base['commit']==parent
assert source['sha256']==canonical(source['files']) and base['sha256']==canonical(base['files'])
assert len(source['files'])==480 and len(base['files'])==463
assert git('rev-parse','HEAD').decode().strip()==head and git('status','--porcelain')==b''
assert subprocess.run(['git','merge-base','--is-ancestor',parent,head],cwd=I).returncode==0
index={f['path']:f['sha256'] for f in source['files']};old={f['path']:f['sha256'] for f in base['files']}
assert len(index)==480 and len(old)==463
changes=set(git('diff','--name-only',parent,head).decode().splitlines())
modified=changes&set(old);added=changes-set(old)
assert modified=={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'} and len(added)==17
assert set(index)==set(old)|added
assert all(n.startswith(('docs/experiments/n30/r2/','scripts/qd_ed_n30_r2_','tests/test_n30_r2_','tests/n30_r2_')) for n in added)
for n,d in index.items():
 assert not Path(n).is_absolute() and '..' not in Path(n).parts
 assert sha(I/n)==d==hashlib.sha256(git('show',head+':'+n)).hexdigest(),n
for n,d in old.items():
 assert hashlib.sha256(git('show',parent+':'+n)).hexdigest()==d,n
 if n not in modified:assert index[n]==d,n
assert reverse['base_commit']==parent and set(reverse['files'])==modified
for n in modified:
 e=reverse['files'][n];lines=(I/n).read_text().splitlines(keepends=True)
 assert e['old_sha256']==old[n] and e['new_sha256']==index[n]
 for h in reversed(e['hunks']):
  assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
 assert ''.join(lines).encode()==git('show',parent+':'+n)
for n in ('cpu-integration-scope-v1.md','root-cpu-integration-release-v1.json','prospective-continuation-draft-v1.md'):
 assert (DOC/n).read_bytes()==(L/n).read_bytes()
 assert git('show','e641bd0:'+str((DOC/n).relative_to(I)))==(L/n).read_bytes()
assert (DOC/'base-source-v1.json').read_bytes()==(P/'terminal-feedback-binding-repair-v1/source-manifest-v1.json').read_bytes()
assert (DOC/'r1-source-v1.json').read_bytes()==(P/'repair-continuation-v1/source-manifest-execution-v1.json').read_bytes()
assert index['main.py']=='5209b0ac07362e1df85bf2fd842e57d4786e24c0a625ee5b9e49bee48f528f93'
assert index['scripts/qd_ed_n30_native.py']=='c7d8c779f977aaae61976b33d9b52cec5fb068913896f6b09a0d8abecf8067c0'
delivery=read(L/'delivery-manifest-v1.json')
assert delivery['source_commit']==head and delivery['executable'] is False and delivery['gpu_release'] is False
for f in delivery['files']:
 p=Path(f['path']);assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256'],p
tests=[]
for i,count in ((1,56),(2,9),(3,2)):
 resource_path=L/f'cpu-run{i}-resource.json';log_path=L/f'cpu-run{i}.log';v=read(resource_path)
 assert v['pytest_exit']==0 and v['guard_clean'] is True and v['denied']==[]
 assert v['cuda_visible_devices']=='' and v['cuda_initialized'] is False and v['cpu_affinity']==[0,1] and v['threads']==2
 assert f'{count} passed' in log_path.read_text()
 tests.append({'resource':ref(resource_path),'log':ref(log_path),'passed':count,'process_cpu_seconds':v['process_cpu_seconds']})
total=read(L/'cpu-resource-total-v1.json')
assert abs(sum(v['process_cpu_seconds'] for v in tests)-13.962925347)<1e-8
assert total['distinct_passed']==60 and total['executed_assertion_cases']==67 and total['test_failures']==0
templates=sorted((L/'disabled-templates').glob('*.json'));assert len(templates)==5
assert all(read(p)['executable'] is False for p in templates)
# This call reads only the audited finite metadata closure, never episode tensors.
sys.path[:0]=[str(I),str(I/'scripts')]
from scripts import qd_ed_n30_r2_bridge as b
assert Path(b.__file__).resolve()==I/'scripts/qd_ed_n30_r2_bridge.py'
denied=[]
def guard(event,args):
 if event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.exec','os.posix_spawn'}:
  denied.append(event);raise PermissionError(event)
 if event=='open' and not isinstance(args[0],int):
  p=Path(os.fsdecode(args[0]))
  if p.suffix in {'.pt','.pth','.safetensors','.npz','.npy'} or p.name in {'runner.log','main.log','events.jsonl'}:
   denied.append(str(p));raise PermissionError(str(p))
sys.addaudithook(guard)
history_start=time.process_time();h=b.history(I)
assert abs(h['old_seconds']-1445.4208934970666)<1e-8 and len(h['imports'])==2
assert len(b.group(h['events']))==4 and len(h['events'])==12 and h['metadata_bytes_observed']<=64*1024*1024 and not denied
metadata={'schema':'n30-r2-root-actual-history-review-v1','accepted':True,'source_commit':head,
 'refs':h['refs'],'metadata_bytes_observed':h['metadata_bytes_observed'],'imported_valid_controls':2,
 'settled_historical_attempts':4,'preserved_invalid_attempts':[b.ORIGINAL_FAILED,b.FAILED],
 'old_seconds':h['old_seconds'],'historical_trust':h['historical_trust'],'process_cpu_seconds':time.process_time()-history_start,
 'historical_tensors_read':0,'numerical_replays':0,'guard_denied':denied,'gpu_release':False}
emit(L/'root-actual-history-metadata-check-v1.json',metadata)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review={'schema':'n30-r2-root-source-review-v1','at':now,'decision':'ACCEPT_SOURCE_BYTE_SCOPE','commit':head,
 'repair_base':parent,'source':ref(L/'source-manifest-execution-v1.json'),'source_files_rehashed_and_git_bound':480,
 'repair_base_files_independently_git_bound':463,'existing_source_files_unchanged':461,
 'existing_files_changed':sorted(modified),'added_files':sorted(added),
 'reverse_hunks_independently_reconstruct_full_original_bytes':True,'main_and_native_byte_identical_to_accepted_repair':True,
 'accepted_repair_review':ref(P/'terminal-feedback-binding-repair-v1/root-cpu-repair-review-v1.json'),
 'manual_review':'Root reviewed finite history/source binding, final runner/worker diff, report closure, controller/admission and route regression evidence across preparation and final delivery. No online/scientific change.',
 'cpu_or_gpu_numerical_replay':False,'gpu_release':False,'goal_status':'TARGET_NOT_MET'}
emit(L/'root-source-review-execution-v1.json',review)
cpu={'schema':'n30-r2-root-cpu-integration-review-v1','at':now,'disposition':'ACCEPT_CPU_INTEGRATION_ONLY',
 'source_commit':head,'delivery':ref(L/'delivery-manifest-v1.json'),'artifact_references_rehashed':len(delivery['files']),
 'source_review':ref(L/'root-source-review-execution-v1.json'),'actual_history_metadata_review':ref(L/'root-actual-history-metadata-check-v1.json'),
 'tests':tests,'distinct_tests_passed':60,'executed_cases':67,'focused_test_cpu_seconds':sum(v['process_cpu_seconds'] for v in tests),
 'root_metadata_review_self_cpu_seconds':time.process_time()-start,
 'limitations':'Worker tests mock GPU/backend/native arithmetic; routing proof only. Strict Boolean repair real CPU replay has its separate accepted review. Future task efficacy remains unproven.',
 'authoring_deviations':'Retained ignored git-add failure; run2 -k deselected two requested cases, which run3 executed explicitly. Seven run2 cases were justified repeats. Small initial static/schema/Git-child CPU not separately instrumented; no exact whole-task CPU total claimed.',
 'budget_changed':False,'gpu_release':False,'protected_authorized':False,'goal_status':'TARGET_NOT_MET'}
emit(L/'root-cpu-integration-review-v1.json',cpu)
print(json.dumps({'decision':cpu['disposition'],'source':head,'source_files':480,'tests':60,
 'historical_metadata_refs':len(h['refs']),'old_seconds':h['old_seconds'],'gpu_release':False}))

