#!/usr/bin/env python3
"""Root acceptance of already-run, bounded CPU delivery. No experiment invocation."""
import hashlib,json,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent; I=H.parent/'conditional_implementation'
R=H.parent.parent.parent; W=R/'study_worktree'
D=R/'variants/n25_actuator_clipped_rbf/infrastructure-continuation-preparation-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def get(p):return json.loads(Path(p).read_text())
def main():
    delivery=H/'delivery-manifest-v1.json'
    assert sha(delivery)=='8bbfc3b49e27371077561677d5452fc0c3d607dceed41f78ab9082abd1321ab5'
    value=get(delivery)
    assert value['source_commit']=='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
    assert value['file_count']==len(value['files'])==39
    for q in value['files']:assert sha(q['path'])==q['sha256']
    static=get(H/'root-static-source-review-v1.json');source=get(H/'source-manifest-v1.json')
    assert static['accepted'] and static['source']==source
    packaged=get(H/'source-composition-bridge-v1.json'); composition=static['composition']
    assert packaged['source']==ref(H/'source-manifest-v1.json')
    assert packaged['accepted_n26_commit']==composition['accepted_n26_source']['commit']
    assert packaged['common_commit']==composition['historical_common_source']['commit']
    assert packaged['current_commit']==source['commit']
    assert packaged['accepted_n26_exact_files']==composition['accepted_unchanged']
    assert packaged['common_administrative_exact_files']==composition['common_administrative_unchanged']
    assert all(q in composition['accepted_unchanged'] for q in packaged['scientific_reference_native_exact'])
    scopes={q['path']:q['changed_functions'] for q in packaged['reviewed_changed_functions']}
    assert scopes=={**composition['provenance_functions'],
      'scripts/qd_ed_final_runner.py':['check_budget','check_retry','metered_support'],
      'scripts/qd_ed_n23_worker.py':['validate_context']}
    assert packaged['reversals']==[composition['shared_reverse'],composition['provenance_reverse']]
    assert packaged['source_only'] is True and packaged['actual_proof_or_runtime_read'] is packaged['gpu_authorized'] is False
    assert sha(H/'root-static-source-review-v1.json')=='c4c8f1ceae6c41e5fd29411773ee40dd2cee8c4f3ba6c2af401ca7af50b9b4da'
    assert len(source['files'])==315
    for q in source['files']:assert sha(I/q['path'])==q['sha256']
    assert subprocess.check_output(['git','status','--porcelain=v1'],cwd=I,text=True)==''
    summary=get(H/'cpu-test-summary-v1.json');assert summary['passed_total_nonoverlapping']==129
    assert [x['passed'] for x in summary['runs']]==[31,98]
    for run in summary['runs']:
        assert sha(run['reference']['path'])==run['reference']['sha256']
        text=Path(run['reference']['path']).read_text()
        assert str(run['passed'])+' passed' in text
        assert run['guard']=={'blocked':[],'blocked_count':0,'cuda_initialized':False,'threads':2,'interop_threads':2}
    invocation=get(H/'test-invocations-v1.json')
    assert invocation['environment']['PYTEST_DISABLE_PLUGIN_AUTOLOAD']=='1'
    templates=[q for q in value['files'] if '/disabled-templates-v1/' in q['path']]
    assert len(templates)==10
    for q in templates:
        v=get(q['path']);assert v['executable'] is v['root_authorized'] is v['actual_evidence_read'] is False
    active=get(D/'source-manifest-v1.json')
    assert active['commit']=='6f796358aa84d53e9c8a04859f7d19352c9db7fe' and len(active['files'])==271
    for q in active['files']:assert sha(W/q['path'])==q['sha256']
    out=H/'root-cpu-review-v1.json'
    record={'schema':'n26-root-conditional-controller-cpu-review-v1','accepted':True,
      'source':ref(H/'source-manifest-v1.json'),'delivery':ref(delivery),
      'static_source_review':ref(H/'root-static-source-review-v1.json'),
      'cpu_report':ref(H/'cpu-implementation-report-v1.md'),'test_summary':ref(H/'cpu-test-summary-v1.json'),
      'test_invocations':ref(H/'test-invocations-v1.json'),'protocol':ref(D/'downstream-adapter-design-v1/root-conditional-controller-cpu-protocol-v1.md'),
      'source_files':315,'independent_actual_git_composition_verified':True,
      'focused_checks_nonoverlapping':129,'source_delta_reviewed':True,
      'guard_and_synthetic_fixture_reviewed':True,'packaging_error_preserved':True,
      'root_review_helper_correction':ref(H/'root-review-helper-error-v1.txt'),
      'active_6f_source_files_unchanged':271,'tensor_reads':0,'real_history_reads':0,
      'source_integration_authorized':False,'actual_predecessor_authorized':False,
      'budget_adoption_authorized':False,'gpu_authorized':False,
      'remaining':'Actual independent continuation closure and logical evidence; separately reviewed finite adoption, same-source one-shot arithmetic proof, runtime/provider/current-event gates and root release.',
      'reviewer':ref(__file__)}
    with out.open('x') as f:json.dump(record,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(ref(out)))
if __name__=='__main__':main()

