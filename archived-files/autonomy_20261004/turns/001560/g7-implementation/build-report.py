import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess

out = Path(__file__).resolve().parent
a = json.loads((out / 'authority-v1.json').read_text())
root_review = json.loads(Path(a['root_review']['path']).read_text())
now = dt.datetime.now(dt.timezone.utc)
start = dt.datetime.fromisoformat('2026-10-10T18:11:17+00:00')
assert (now-start).total_seconds() < 1200

def ref(path):
    path = Path(path)
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

final = git('rev-parse', 'HEAD')
assert git('rev-parse', 'HEAD^') == a['source']
paths = git('diff-tree', '--no-commit-id', '--name-only', '-r', final).splitlines()
scope = json.loads((out / 'source-scope-v1.json').read_text())
assert paths == scope['changed_paths']
for name, record in scope['files'].items():
    assert ref(name)['sha256'] == record['sha256']
assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
ledgers = {}
for name, expected in a['ledger_prefixes'].items():
    actual = ref(expected['path'])
    raw = Path(expected['path']).read_bytes()
    actual.update(prefix_sha256=hashlib.sha256(raw[:expected['bytes']]).hexdigest(),
                  suffix_bytes=len(raw)-expected['bytes'])
    actual['unchanged'] = actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256']
    assert actual['unchanged']
    ledgers[name] = actual
stops = ['/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP', '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP']
assert all(not os.path.lexists(p) for p in stops)
assert now < dt.datetime.fromisoformat(a['deadline'].replace('Z', '+00:00'))
history = {}
for name, expected in root_review['roots'].items():
    actual = ref(expected['path'])
    assert actual['sha256'] == expected['sha256']
    history[name] = actual
v7 = (out / 'integration-v7.log').read_text()
v8 = (out / 'bindings-v8.log').read_text()
stop_tests = (out / 'timeout-stop-v1.log').read_text()
assert '1 failed, 19 passed' in v7
assert '4 passed, 14 deselected' in v8
assert '20 passed' in stop_tests
assert v7.count(' FAILED [') == 1
assert 'test_restart_crashes_and_terminal_receipt_mismatch FAILED' in v7
base = "PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest "
report = {
 'schema': 'n36-g7-cpu-implementation-report-v1', 'node_id': '15.6', 'at': now.isoformat(),
 'status': 'IMPLEMENTED_CPU_VERIFIED_REQUIRES_FRESH_REVIEW_AND_ROOT_RELEASE',
 'starting_commit': a['source'], 'final_commit': final, 'worktree': a['worktree'],
 'changed_paths': paths, 'source_files': {name: ref(Path.cwd()/name) for name in paths},
 'authority': ref(out/'authority-v1.json'), 'accepted_root_review': a['root_review'], 'prior_b5': a['prior_review'],
 'prior_b5_approves_new_source': False,
 'changes': [
  'Replaced the unconditional dispatch veto with the existing complete executable detached-release/admission/worker/receipt path. No implementation boolean or external record substitutes for those checks.',
  'Released launch guards now require the exact released plan schema; public lifecycle tests use unmodified functions, with no AST veto removal or private function copies.',
  'Health release issuance must precede reservation; episode release issuance must follow settled health. Live episode journals bind the exact release/plan and enforce finite, ordered, prospective timestamps.',
  'Exited episode and health overruns become invalid aborted events with the entire measured charge preserved, never capped to the reservation.',
  'Both before/after loaded-source receipts explicitly require the engineering, release, accounting, STOP and source-attestation modules.',
  'CPU fixtures execute run_worker itself to write start/observations/audit/receipt. Disposable releases use content-addressed names; deterministic composition is memoized by argv and complete config/core content hashes. No production verifier or acceptance result is cached.'
 ],
 'tests': [
  {'command': base + '-vv -p no:cacheprovider --durations=20 tests/test_n36_engineering_integration.py tests/test_n36_engineering.py::test_disabled_artifacts_cannot_override_source_startup_or_released_schema tests/test_n36_engineering.py::test_owner_route_admission_does_not_supply_released_plan',
   'exit_code': 1, 'result': '19 passed; 1 fixture-isolation failure retained. This run used the final production source but the prior fixture release filenames.', 'evidence': ref(out/'integration-v7.log')},
  {'command': base + "-vv -p no:cacheprovider --durations=10 tests/test_n36_engineering_integration.py -k 'accepted_health_reservation_readiness_episode_release or deep_closure_corruption_both_release_families or restart_crashes_and_terminal_receipt_mismatch or worker_receipt_deep_bindings_cannot_be_replaced_by_rehashed_claims'",
   'exit_code': 0, 'result': '4 passed, 14 deselected; all affected lifecycle/closure/restart/receipt cases pass with immutable fixture release filenames.', 'evidence': ref(out/'bindings-v8.log')},
  {'command': base + '-q -p no:cacheprovider tests/test_n36_runner.py::test_timeout_exact_owned_cleanup_retains_charge tests/test_n36_runner.py::test_healthcheck_timeout_cleans_only_owned_child_and_interrupt_drains tests/test_n36_stop_guard.py::test_each_canonical_entry_fails_closed',
   'exit_code': 0, 'result': '20 passed', 'evidence': ref(out/'timeout-stop-v1.log')},
  {'command': 'git diff --check; ast.parse of all seven changed Python files', 'exit_code': 0, 'result': 'PASS'}
 ],
 'test_corrections': [
  'Initial un-memoized fixture runs were interrupted while making source/fixture corrections; logs retained.',
  'The new worker-body fixture initially mismatched real CPU backend metadata. Corrected the simulated audit report; production validator was unchanged.',
  'Fresh release timestamps exposed reused fixture filenames and a snapshot taken before release issuance. Corrected snapshot ordering and made detached fixture release names content-addressed. Historical failed runs remain failed; the affected final rerun passed.'
 ],
 'test_history': [ref(p) for p in sorted(out.glob('integration-v*.log'))],
 'lifecycle_coverage': [
  'Direct public health reservation -> reacquired locked handoff -> dispatch -> settled readiness -> separate episode release -> public runner -> actual run_worker orchestration -> parent terminal verification -> root pause -> no-replay restart.',
  'Real detached authority/B5/adoption schemas, all three retained journal prefixes, private state and protected-reserve accounting, sole health/episode identities, real lock/append/fsync boundaries.',
  'Real before/after receipt production and verification with explicitly simulated source/runtime/native/device/controller observations, inert Main outputs, and simulated generic/native audit observations.',
  'Owned timeout cleanup and interrupt-drain helpers; two canonical STOP paths including dangling links, directories, permission/I/O/not-directory failures.'
 ],
 'negative_checks': [
  'Disabled plans, fake approval fields, missing source-only startup, cross-family contexts/releases and STOP at worker admission.',
  'STOP after reservation/dispatch, failed Popen, exhausted identities, missing terminal artifact, mismatched receipt and invalid restart.',
  'Foreign ledger/resource/reservation suffixes, replay, changed handoff record/state/adoption/run/output/GPU/private-budget/hold.',
  'Exact 2100/1840/60-second headroom edges, Decimal weekly/protected reserve boundaries, nonfinite/backwards/future/pre-release event timestamps.',
  'Corrupted non-C0 manifest, committed source, runtime source, native binary, controller proof and runtime closure rejected in both release families.',
  'Rehashed but invalid loaded engineering source, runtime process binding, compiled source hash, native-after inventory, controller instance and native arithmetic device rejected.',
  'Main and native-audit failures stop invalid; 1841-second episode and 61-second health costs are appended in full and cannot supply continuation/readiness.'
 ],
 'call_graph': ref(out/'call-graph-v1.json'), 'source_scope': ref(out/'source-scope-v1.json'),
 'unresolved_implementation_test_failures': [],
 'unresolved_blockers': [
  'New source is not approved by prior B5. Focused independent review of this exact commit and refreshed affected bindings is mandatory.',
  'Owner source/accounting/state adoption, exact bound authority/protocol acceptance and detached health/episode root releases remain absent and unauthorized in this task.',
  'Production readiness and actual source/runtime/native/controller/postprocessor/decode/native-arithmetic receipts remain unobserved; CPU synthetic evidence cannot authorize execution or establish science.'
 ],
 'next_minimal_graph_refresh_review_obligations': [
  {'bindings': ['source', 'scientific_source', 'scientific_equivalence'], 'action': 'Bind the final commit and seven changed file hashes in the source inventory and operational-only equivalence proof; keep all science/config/threshold bytes unchanged.'},
  {'bindings': ['all40 expected_manifests', 'audit_plan', 'engineering_manifest', 'plan', 'graph'], 'action': 'Regenerate only source-affected manifests and their transitive disabled roots. Exact prior root paths are recorded in preserved_history; preserve prior bytes as history.'},
  {'bindings': ['runtime', 'runtime_closure', 'native_build', 'controller_semantics', 'scope', 'accounting', 'deployment'], 'action': 'Reuse still-valid hash-bound provenance; explicitly review compatibility with the changed source. Refresh a binding only if its contents change. Do not carry prior B5 approval to this commit.'},
  {'bindings': ['b5_review', 'authority', 'protocol_acceptance', 'source_adoption', 'amendment', 'owner_state', 'health_release', 'episode_release'], 'action': 'Coordinator alone obtains fresh independent/root review and any later adoption/releases after current STOP/deadline/readiness/finite-budget checks. This report grants none.'}
 ],
 'preserved_history': history, 'graph_refreshed': False, 'release_enabled': False,
 'unconditional_dispatch_veto_removed': True, 'actual_dispatch_performed': False,
 'unchanged_ledger_checks': {'initial': ref(out/'ledger-check-initial-v1.json'), 'final': ledgers, 'all_unchanged': True, 'new_attempts': 0, 'new_gpu_charge': 0},
 'scientific_gates': {'complete10': 'unchanged and unproven', 'N36>=5': 'unchanged and unproven', 'N36>=C0/Q0/N34': 'unchanged and unproven', 'final_QD_ED_ablations': 'required unchanged', 'validation_formal_promotion': 'required unchanged; no protected access', 'original_goal_contract': 'unchanged', 'engineering_separate_from_science': True},
 'score': None, 'scientific_success': False, 'target_met': False, 'native_execution_proven': False,
 'gpu_used': False, 'model_provider_executed': False, 'native_arithmetic_or_gpu_kernel_execution': False,
 'protected_results_accessed': False, 'credentials_opened': False, 'dependencies_changed': False,
 'owner_state_checkpoint_tree_journal_writes': False, 'source_or_accounting_adopted': False,
 'delegation': False, 'model_policy': {'required': 'official current-login gpt-6-astra', 'execution': 'Existing session only; no additional model/provider launch or authentication revalidation.'},
 'stop_and_budget': {'canonical_stop_paths': stops, 'STOP_absent': True, 'deadline': a['deadline'], 'deadline_open': True, 'started_at': start.isoformat(), 'finished_at': now.isoformat(), 'elapsed_seconds': (now-start).total_seconds(), 'timeout_seconds': 1200},
 'git_status': git('status', '--short'),
}
(out/'report-v1.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
print(json.dumps({'report': ref(out/'report-v1.json'), 'commit': final, 'elapsed_seconds': report['stop_and_budget']['elapsed_seconds']}))
