"""Root packaging/source review only; no experiment evidence or execution."""
import ast, hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
N = H.parent
W = N.parents[1] / 'study_worktree'
COMMIT = '6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
def blob(p):
    p = Path(p)
    assert p.is_file() and not p.is_symlink() and p.stat().st_size <= 16 * 1024 * 1024
    return p.read_bytes()
def sha(p): return hashlib.sha256(blob(p)).hexdigest()
def read(p): return json.loads(blob(p))
def ref(p): return {'path': str(Path(p).resolve()), 'sha256': sha(p)}

manifest = H / 'delivery-manifest-v1.json'
assert sha(manifest) == 'e25c70ab0cddfad32e07fa0f9896f03c001da277067c21ae92896d7a9d08c4e6'
delivery = read(manifest)
assert delivery['status'] == 'CPU_PREPARATION_ONLY'
assert delivery['experiment_source_commit'] == COMMIT
assert len(delivery['files']) == 35
for row in delivery['files']:
    p = Path(row['path'])
    assert p.resolve().is_relative_to(H)
    data = blob(p)
    assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
modules = read(H / 'reader-source-manifest-v1.json')
assert modules['experiment_commit'] == COMMIT
assert {Path(x['path']).name for x in modules['source_files']} == {
    'terminal_reader_v1.py', 'bounded_metadata_v1.py', 'metadata_semantics_v1.py'}
for row in modules['source_files']:
    assert sha(row['path']) == row['sha256']
    tree = ast.parse(blob(row['path']))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): names = [x.name for x in node.names]
        elif isinstance(node, ast.ImportFrom): names = [node.module or '']
        else: continue
        assert all(x.split('.')[0] not in {'torch','scripts','core','transformers','mujoco','requests','httpx'} for x in names)

for tag, expected in [('sixth', '65 passed in 6.70s'), ('cli', '20 passed, 49 deselected in 4.71s')]:
    guard = read(H / ('guard-' + tag + '-v1.json'))
    assert guard['pytest_exit_code'] == 0 and guard['blocked_operations'] == 0 and guard['violations'] == []
    assert guard['cuda_visible_devices'] == '' and guard['torch_imported'] is False
    assert guard['cpu_threads'] == 2 and guard['actual_inputs_read'] is False
    assert expected in blob(H / ('cpu-' + tag + '-v1.log')).decode()
disabled = read(H / 'metadata-input-disabled-v1.json')
assert disabled['root_authorized'] is False and disabled['executable'] is False
static_count = 0
for name in ('static-source-index-v1.json', 'static-source-index-supplement-v1.json'):
    for row in read(H / name)['files']:
        assert sha(row['path']) == row['sha256']
        static_count += 1
source_path = N / 'conditional-controller-cpu-v1/source-manifest-v1.json'
source = read(source_path)
assert source['commit'] == COMMIT and len(source['files']) == 315
assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=W, text=True).strip() == COMMIT
for row in source['files']:
    p = W / row['path']
    assert p.resolve().is_relative_to(W) and sha(p) == row['sha256']
review = {
    'schema': 'n26-root-external-terminal-reader-cpu-review-v1',
    'decision': 'ACCEPT_CPU_PREPARATION',
    'reviewed_at': datetime.now(timezone.utc).isoformat(),
    'delivery': ref(manifest), 'protocol': ref(H / 'root-implementation-protocol-v1.md'),
    'source_manifest': ref(H / 'reader-source-manifest-v1.json'),
    'contract': ref(H / 'reader-contract-v1.md'), 'cpu_report': ref(H / 'cpu-implementation-report-v1.md'),
    'disabled_input': ref(H / 'metadata-input-disabled-v1.json'),
    'delivery_files_verified': 35, 'static_input_files_verified': static_count,
    'owning_source': ref(source_path), 'owning_source_commit': COMMIT, 'owning_files_verified': 315,
    'cpu_tests': {'distinct_cases': 69, 'main_passed': 65, 'targeted_passed': 20,
                  'overlap': 16, 'guard_blocked_operations_final': 0, 'root_reexecuted_tests': False},
    'earlier_failures_retained': True,
    'reviewed_semantics': [
        'bounded typed metadata and explicit attestation trust boundaries',
        'ordered task-major first-valid attempts and at most two exact typed recoveries',
        'first complete-quad futility prevents later reservations',
        'same-source36 proof metadata and same-process native receipts without tensor replay',
        'all attempt costs, partial token usage and unsettled Unknown',
        'original cell40 status/writer inconsistency remains INVALID',
        'missing PID remains Unknown and closes downstream cleanup gate',
        'existing locks and immutable independent review; no result repair',
    ],
    'actual_experiment_metadata_read_for_this_review': False,
    'actual_terminal_reader_execution_authorized': False,
    'future_execution_requires': ['controller terminated', 'source602 intact',
        'root reviewed exact bounded input inventory', 'original source/runtime precheck',
        'current matching projections and public cleanup under original locks'],
    'gpu_execution_authorized': False, 'validation_authorized': False, 'formal_authorized': False,
    'root_reviewer': ref(__file__),
}
out = H / 'root-cpu-review-v1.json'
with out.open('x') as f:
    json.dump(review, f, indent=2, ensure_ascii=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
cp_path = W / '.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
cp = read(cp_path)
cp.update(n26_terminal_reader_cpu_review=ref(out), in_flight_executor=None,
          updated_at=datetime.now(timezone.utc).isoformat())
cp_path.write_text(json.dumps(cp, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'review': ref(out), 'decision': review['decision'], 'verified_files': 35,
                  'source_files': 315, 'static_inputs': static_count, 'distinct_cpu_cases': 69}))
