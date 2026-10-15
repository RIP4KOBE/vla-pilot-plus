"""Root CPU delivery acceptance and separately authorized metadata input; no dispatch."""
import ast, hashlib, json, subprocess
from pathlib import Path
from datetime import datetime, timezone

D=Path(__file__).resolve().parent
N=D.parent
I=N/'infrastructure_continuation_implementation'
W=N.parent.parent/'study_worktree'
BASE='5a65ef15968cc68c82314e8c0773b3365ad45fa0'
NEW='6f796358aa84d53e9c8a04859f7d19352c9db7fe'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p): return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read(p): return json.loads(Path(p).read_text())
def write(p,v):
    with Path(p).open('x') as f: json.dump(v,f,indent=2,allow_nan=False); f.write('\n')
def git(root,*a): return subprocess.check_output(['git',*a],cwd=root,text=True).strip()

assert git(W,'rev-parse','HEAD')==BASE
assert git(I,'rev-parse','HEAD')==NEW and not git(I,'status','--porcelain')
delivery=read(D/'cpu-delivery-manifest-v1.json')
assert delivery['source_commit']==NEW and delivery['executable'] is False and delivery['gpu_authorized'] is False
for q in delivery['files']:
    assert sha(q['path'])==q['sha256'] and Path(q['path']).stat().st_size==q['bytes']
    if 'disabled-templates-v1' in q['path']:
        v=read(q['path']); assert v['executable'] is False and v['gpu_authorized'] is False
source=read(D/'source-manifest-v1.json')
old=read(I/'experiments/qd_ed_n25_continuation/original-source-v1.json')
assert source['commit']==NEW and len(source['files'])==271
assert len(old['files'])==257 and old['commit']==BASE
for q in source['files']: assert sha(I/q['path'])==q['sha256']
for q in old['files']: assert sha(W/q['path'])==q['sha256']
reverse=read(I/'experiments/qd_ed_n25_continuation/reverse-routes-v1.json')
routes={'scripts/qd_ed_final_runner.py':{'metered_support','check_budget','check_retry'},'scripts/qd_ed_n23_worker.py':{'validate_context'}}
def funcs(t): return {n.name:ast.get_source_segment(t,n) for n in ast.parse(t).body if isinstance(n,ast.FunctionDef)}
for q in old['files']:
    new=(I/q['path']).read_text()
    if q['path'] not in routes: assert sha(I/q['path'])==q['sha256']; continue
    r=next(x for x in reverse['files'] if x['path']==q['path']); lines=new.splitlines(keepends=True)
    assert r['new_sha256']==sha(I/q['path'])
    for change in reversed(r['edits']):
        a,z=change['new_start'],change['new_end']; assert ''.join(lines[a:z])==change['new']
        lines[a:z]=change['old'].splitlines(keepends=True)
    restored=''.join(lines); assert hashlib.sha256(restored.encode()).hexdigest()==q['sha256']
    a,b=funcs(restored),funcs(new); assert set(a)==set(b) and {k for k in a if a[k]!=b[k]}==routes[q['path']]
tests=read(D/'cpu-test-summary-v1.json')
assert tests['distinct_tests_with_final_passing_evidence']==113 and tests['cuda_initialized'] is False
for run in tests['runs']:
    log=Path(run['log_ref']['path']).read_text(); assert sha(run['log_ref']['path'])==run['log_ref']['sha256']
    guard=json.loads(next(x.split('N25_CONT_CPU_GUARD_V1 ',1)[1] for x in log.splitlines() if x.startswith('N25_CONT_CPU_GUARD_V1 ')))
    assert guard['blocked_count']==run['guard_blocks'] and guard['cuda_initialized'] is False
    assert guard['threads']==guard['interop_threads']==2
draft=read(D/'metadata-input-draft-v1.json'); assert draft['root_authorized'] is False
assert len(draft['files'])==131
for q in draft['files']: assert sha(q['path'])==q['sha256']
review={'schema':'n25-continuation-root-cpu-review-v1','accepted':True,'reviewed_at':datetime.now(timezone.utc).isoformat(),
 'source_manifest':ref(D/'source-manifest-v1.json'),'delivery':ref(D/'cpu-delivery-manifest-v1.json'),
 'report':ref(D/'cpu-implementation-report-v1.md'),'tests':ref(D/'cpu-test-summary-v1.json'),
 'protocol':ref(D/'root-implementation-protocol-v1.md'),'source_commit':NEW,
 'old_source_files_verified':257,'new_source_files_verified':271,'unchanged_original_files':255,
 'allowed_routes':{k:sorted(v) for k,v in routes.items()},'whole_file_reverse_verified':True,
 'production_modules_and_substantive_tests_reviewed':True,'all_failed_test_logs_preserved':True,
 'actual_sealing_authorized':True,'source_integration_authorized_after_seal_review':True,'gpu_authorized':False,
 'provider_constraint':'Current Codex managed chatgpt login only; no Poe or other provider/account fallback; saved credentials preserved.',
 'limitations':['Historical missing native gates remain unknown.','No algorithm efficacy inferred from CPU tests.','Validation and N26 require separate evidence/source adapter.']}
write(D/'root-cpu-review-v1.json',review)
authorized=dict(draft,root_authorized=True,root_cpu_review=ref(D/'root-cpu-review-v1.json'),
 preparation_note='New root-authorized metadata-only input following final CPU/source/inventory review; disabled draft remains immutable.')
write(D/'metadata-input-authorized-v1.json',authorized)
print(json.dumps({'review':ref(D/'root-cpu-review-v1.json'),'authorized_input':ref(D/'metadata-input-authorized-v1.json'),'gpu_authorized':False}))
