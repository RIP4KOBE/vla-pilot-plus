"""Independent final additive CPU delivery review; real terminal inputs remain closed."""
import json,hashlib,subprocess,datetime
from pathlib import Path
H=Path(__file__).resolve().parent;N=H.parents[1];I=N/'downstream_common_implementation';W=N.parents[1]/'study_worktree';D=H.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
commit='ff285373cc69a898cb1f5e6ed9cbbfe370a2972a';base='6f796358aa84d53e9c8a04859f7d19352c9db7fe'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=I,text=True).strip()==commit
assert not subprocess.check_output(['git','status','--porcelain'],cwd=I,text=True).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==base
delivery=read(H/'delivery-manifest-v2.json')
for q in delivery['files']:
 assert sha(q['path'])==q['sha256']
 if 'bytes' in q:assert Path(q['path']).stat().st_size==q['bytes']
source=read(H/'source-manifest-v2.json');old=read(D/'source-manifest-v1.json')
assert source['commit']==commit and old['commit']==base and len(source['files'])==276 and len(old['files'])==271
for q in source['files']:assert sha(I/q['path'])==q['sha256']
for q in old['files']:assert sha(I/q['path'])==sha(W/q['path'])==q['sha256']
tests=read(H/'cpu-test-summary-v2.json');assert tests['distinct_tests_with_passing_evidence']==68
for x in tests['all_clean_logs']+tests['non_clean_runs']:
 assert sha(x['log']['path'])==x['log']['sha256']
 text=Path(x['log']['path']).read_text()
 guard=json.loads(next(line.split('N25_DOWNSTREAM_COMMON_GUARD_V1 ',1)[1] for line in text.splitlines() if line.startswith('N25_DOWNSTREAM_COMMON_GUARD_V1 ')))
 assert guard==x['guard'] and guard['cuda_initialized'] is False and guard['threads']==guard['interop_threads']==2
 if x in tests['all_clean_logs']:assert guard['blocked_count']==0
 else:assert x['accepted_as_guard_clean'] is False and guard['blocked_count']==2
static=read(H/'root-static-source-review-v1.json')
assert static['accepted'] and static['source_commit']==commit and static['historical_objects']==528 and static['historical_source_bytes']==10048546
for p in (H/'disabled-templates-v1').glob('*.json'):
 x=read(p);assert x['executable'] is False
 if 'root_authorized' in x:assert x['root_authorized'] is False
review={'schema':'n25-downstream-root-cpu-review-v2','accepted':True,'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source_commit':commit,'source_manifest':ref(H/'source-manifest-v2.json'),'delivery':ref(H/'delivery-manifest-v2.json'),
 'report':ref(H/'cpu-implementation-report-v2.md'),'tests':ref(H/'cpu-test-summary-v2.json'),'static_source_review':ref(H/'root-static-source-review-v1.json'),
 'all271_active_source_files_unchanged':True,'total_additive_source_files':276,'production_module_contract_and_tests_reviewed':True,
 'transitive_helper_gap_fixed_and_verified':True,'distinct_synthetic_cases_with_passing_evidence':68,'isolation_failed_log_preserved':True,
 'actual_experiment_metadata_read':False,'actual_metadata_execution_authorized':False,'active_source_integration_authorized':False,
 'validation_authorized':False,'n26_authorized':False,'gpu_authorized':False,
 'remaining_conditions':['Continuation must close under6f and independently pass terminal review.','Root must freeze explicit Dev/resource projections and closed input inventory.','Current matching journal checks must be wired into separately reviewed future admission.','Distinct downstream source bridges, gates, actual budget and releases remain required.']}
with (H/'root-cpu-review-v2.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({'review':ref(H/'root-cpu-review-v2.json'),'accepted_cpu_only':True,'active_source':base,'gpu_release':False}))
