"""Root review of the CPU-only scalar delivery; no actual experiment inputs."""
import ast, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
W = H.parents[2] / 'study_worktree'
def blob(p):
    p = Path(p)
    assert p.is_file() and not p.is_symlink() and p.stat().st_size <= 16 * 1024 * 1024
    return p.read_bytes()
def sha(p): return hashlib.sha256(blob(p)).hexdigest()
def read(p): return json.loads(blob(p))
def ref(p): return {'path': str(Path(p).resolve()), 'sha256': sha(p)}

manifest = H / 'delivery-manifest-v1.json'
assert sha(manifest) == 'b25c14b314a1787d07e075a8ef45721ce2689ad8bca9b3f8f267b9987b5ce2bc'
delivery = read(manifest)
assert delivery['actual_inputs_read'] is False and delivery['execution_authorized'] is False
assert len(delivery['files']) == 19
for row in delivery['files']:
    assert Path(row['path']).resolve().is_relative_to(H)
    assert sha(row['path']) == row['sha256'] and len(blob(row['path'])) == row['bytes']
source = read(H / 'source-manifest-v1.json')
assert source['experiment_source_unchanged'] is True
for row in source['files'] + source['static_dependencies']:
    assert sha(row['path']) == row['sha256']
    ast.parse(blob(row['path']))
scope = read(H / 'static-read-scope-v1.json')
assert scope['actual_inputs_authorized'] is False
assert scope['experiment_commit'] == '6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
for row in scope['files']:
    assert sha(row['path']) == row['sha256']
for tag, expected in [('final', '27 passed in 0.22s'), ('cli', '1 passed, 27 deselected in 0.05s')]:
    guard = read(H / ('guard-' + tag + '-v1.json'))
    assert guard['pytest_exit_code'] == 0 and guard['blocked_operations'] == 0 and guard['violations'] == []
    assert guard['cuda_visible_devices'] == '' and guard['torch_imported'] is False
    assert guard['cpu_threads'] == 2 and guard['actual_experiment_inputs_read'] is False
    assert expected in blob(H / ('cpu-' + tag + '-v1.log')).decode()
disabled = read(H / 'input-disabled-v1.json')
assert disabled['root_authorized'] is False and disabled['executable'] is False
review = {
    'schema': 'n26-root-scalar-summary-cpu-review-v1',
    'decision': 'ACCEPT_CPU_PREPARATION',
    'reviewed_at': datetime.now(timezone.utc).isoformat(),
    'delivery': ref(manifest), 'source': ref(H / 'source-manifest-v1.json'),
    'protocol': ref(H / 'root-cpu-summary-protocol-v1.md'),
    'contract': ref(H / 'input-contract-v1.md'), 'cpu_report': ref(H / 'cpu-report-v1.md'),
    'disabled_input': ref(H / 'input-disabled-v1.json'),
    'delivery_files_verified': 19, 'static_input_files_verified': len(scope['files']),
    'cpu_tests': {'distinct_cases': 28, 'main_passed': 27, 'targeted_passed': 1,
                  'overlap': 0, 'final_blocked_operations': 0, 'root_reexecuted_tests': False},
    'earlier_failed_test_and_denied_pyc_reads_preserved': True,
    'reviewed_semantics': [
        'exact accepted terminal inventory, all accepted N25/N26 cells including valid failures and zero guided steps',
        'call counts and scalar metrics bound to terminal result and per-decision metadata',
        'explicit call and component denominators, null empty phases and unmatched task reporting',
        'per-arm task and initial/rollout phase summaries without causal or physical efficacy claims',
        'no native tensor, image, raw Stage, credential or protected phase reads',
        'only two exact pure static dependencies and closed bounded metadata input',
    ],
    'actual_experiment_inputs_read_for_this_review': False,
    'actual_summary_execution_authorized': False,
    'future_execution_requires': ['accepted independent N26 terminal review',
        'root-reviewed closed inventory of five control JSON files and all accepted N25/N26 metrics'],
    'gpu_execution_authorized': False, 'validation_authorized': False, 'formal_authorized': False,
    'root_reviewer': ref(__file__),
}
out = H / 'root-cpu-review-v1.json'
with out.open('x') as f:
    json.dump(review, f, indent=2, ensure_ascii=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
cp_path = W / '.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
cp = read(cp_path)
cp.update(n26_scalar_summary_cpu_review=ref(out), in_flight_executor=None,
          updated_at=datetime.now(timezone.utc).isoformat())
cp_path.write_text(json.dumps(cp, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'review': ref(out), 'decision': review['decision'],
                  'delivery_files': 19, 'static_inputs': len(scope['files']), 'distinct_cpu_cases': 28}))
