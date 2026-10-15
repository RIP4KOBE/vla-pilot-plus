import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
tmp = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001793/preparation-binding-repair/tmp')
out = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001793/preparation-binding-repair/report-v1.json')
def ref(path):
    data = Path(path).read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
authority_path = out.parent/'authority-v1.json'
authority = json.loads(authority_path.read_text())
for name in ('diagnosis', 'validation'):
    assert ref(authority[name]['path']) == authority[name]
stop = {path: Path(path).exists() for path in authority['stop_authority']['paths']}
assert not any(stop.values()), 'STOP present'
now = dt.datetime.now(dt.timezone.utc)
assert now < dt.datetime.fromisoformat(authority['stop_authority']['deadline'].replace('Z','+00:00'))
commit = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
assert commit == 'f5fc546e08d41049949bbcbaecb79515c822e0e9'
status = subprocess.check_output(['git','status','--porcelain'],text=True)
assert not status
inspection = json.loads((tmp/'retained-identity-inspection.json').read_text())
provenance = json.loads((tmp/'source-test-provenance.json').read_text())
env = f'OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 TMPDIR={tmp}'
commands = [
    {'purpose': 'initial bounded CPU implementation check', 'command': f'{env} python -B -m pytest -q -p no:cacheprovider tests/test_n36_preparation_binding.py --basetemp={tmp}/pytest-first > {tmp}/test-first.log 2>&1',
     'result': '70 passed in 7.07s', 'exit_code': 0, 'log': ref(tmp/'test-first.log'),
     'source_provenance': 'Exploratory uncommitted first version; superseded by the committed 88-case run. Not claimed as final-commit validation.'},
    {'purpose': 'preparation and existing episode/import alias regression checks', 'command': f"{env} python -B -m pytest -q -p no:cacheprovider tests/test_n36_preparation_binding.py tests/test_n36_importlib_alias.py tests/test_n36_frozen_alias.py -k 'not live_rejects_substitution and not producer_rejects_substitution' --basetemp={tmp}/pytest-focused > {tmp}/test-focused.log 2>&1",
     'result': '230 passed, 49 deselected in 21.09s', 'exit_code': 0, 'log': ref(tmp/'test-focused.log'),
     'source_provenance': {'base': authority['source'], 'exact_changed_files': provenance['focused_run_files'],
         'unchanged_tests': provenance['unchanged_regression_tests'],
         'snapshot_method': 'Reconstructed from final commit by removing only the subsequently added typed receipt-process check and six process-shape tests. No production behavior is patched in these tests.'},
     'selection_reason': 'Exclude existing live-module substitution tests that monkeypatch production internals; retain receipt adversaries and real fresh bootstrap-process tests.'},
    {'purpose': 'committed repair and one legacy fixture compatibility check', 'command': f'{env} taskset -c 0,1 python -B -m pytest -q -p no:cacheprovider tests/test_n36_preparation_binding.py tests/test_n36_readiness_prepare.py::test_exact_measured_derivation_and_disabled_baseline --basetemp={tmp}/pytest-committed > {tmp}/test-committed.log 2>&1',
     'result': '88 passed, 1 error in 8.43s', 'exit_code': 1, 'log': ref(tmp/'test-committed.log'),
     'source_provenance': {'commit': commit, 'exact_changed_files': provenance['committed_files']},
     'passed': 'All 88 standalone new preparation-binding, envelope linkage, source/native/runtime/alias and episode-isolation cases.',
     'error': {'test': 'tests/test_n36_readiness_prepare.py::test_exact_measured_derivation_and_disabled_baseline',
               'stage': 'fixture setup at e.specification(), before the repaired execution verifier',
               'message': 'ValueError: foreign resource identity outside retained recovery partition',
               'location': 'scripts/qd_ed_n36_engineering_r1.py:793',
               'handling': 'Preserved the failure. No recovery partition, ledger, specification, source scope or owning state was repaired or bypassed.'}},
    {'purpose': 'whitespace and working tree checks', 'commands': ['git diff --check', 'git status --porcelain', 'git rev-parse HEAD'],
     'result': {'diff_check_exit': 0, 'working_tree_porcelain': status, 'head': commit}},
    {'purpose': 'passive retained identity and exact source/test provenance capture',
     'command': f'OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 taskset -c 0,1 python -B {tmp}/record_evidence.py',
     'script': ref(tmp/'record_evidence.py'), 'exit_code': 0,
     'outputs': [ref(tmp/'retained-identity-inspection.json'), ref(tmp/'source-test-provenance.json')]},
    {'purpose': 'focused source commit', 'command': "git commit -m 'fix(n36): verify preparation receipts with external execution anchors'",
     'exit_code': 0, 'commit': commit}
]
report = {
    'schema': 'n36-preparation-binding-engineering-report-v1', 'node_id': '15.6', 'at': now.isoformat(),
    'engineering_status': 'FOCUSED_REPAIR_COMMITTED; INDEPENDENT_REVIEW_AND_ROOT_ADOPTION_PENDING',
    'task_success_claimed': False, 'authority': ref(authority_path),
    'diagnosis': authority['diagnosis'], 'prior_readiness_validation': authority['validation'],
    'worktree': str(root), 'source_before': authority['source'], 'source_after': commit,
    'working_tree_clean': True,
    'changed_files': inspection['source_versions'],
    'repair': {
        'failure': 'Preparation producer emits release/source_record/resource_id/process/preparation_after; generic alias consumer only accepts episode context/runtime_closure/process/runtime_before-or-after.',
        'call_path': 'derive -> verify_envelope -> verify_execution_receipts -> verify_preparation_receipt -> shared source/import-alias verification; native and complete after-runtime receipts are also verified.',
        'preparation_scope': 'Separate public entrypoint, exact preparation_after binding reconstructed from external anchors; no public mode switch on episode APIs.',
        'anchors': ['hash-pinned external release and released plan', 'hash-pinned source record and source root',
                    'hash-pinned runtime closure and runtime reference joined to released graph',
                    'external resource identity and terminal process identity',
                    'envelope/proof native and runtime receipt reference equality, pinned source receipt, common binding'],
        'producer_identity': 'Exact module name, canonical source path and frozen source digest required for readiness_prepare, n36_source, n34_source, n36_build, engineering_r1 and gpu_probe. All compiled/startup records and all observed Python modules still pass shared byte/origin coverage.',
        'consumer_identity': 'This committed worktree is the tested consumer. The deployed verify_graph/verify_source/attest_loaded checks remain unchanged and require the consumer checkout/loaded bytes to match the released source. No mixed-source exemption was added.',
        'native_and_alias_evidence': 'Native manifest and required mapped-library receipt are checked with after=True; runtime receipt uses after=True completeness and existing generated/native-alias rules; os.path/posixpath and both frozen importlib identity claims retain exact rule/interpreter/binding/inventory/boolean checks.',
        'episode_invariant': 'verify_alias, verify_importlib_aliases and verify_receipt retain exact episode binding validation and original required worker/native/arithmetic/audit/source coverage. Preparation receipts still fail all three episode entrypoints.',
        'fixture_change': 'Removed legacy execution.verify_receipt no-op monkeypatch; populated complete inert source/runtime/native evidence instead. Existing unrelated legacy graph-fixture isolation was not broadened; its setup is blocked by current recovery partition and was not used as passing evidence.',
        'retained_worker_coverage_correction': 'Retained preparation receipt does contain episode modules transitively; missing worker coverage was not a confirmed second retained-proof failure. Explicit preparation coverage avoids relying on incidental imports.'
    },
    'focused_tests': commands,
    'test_provenance': ref(tmp/'source-test-provenance.json'),
    'interpreter': dict(provenance['interpreter'], version=sys.version),
    'retained_proof_eligibility': {
        'status': 'NOT_ELIGIBLE_FOR_READINESS_ADOPTION_UNDER_REPAIRED_SOURCE_WITH_CURRENT_STRICT_BINDINGS',
        'inspection': ref(tmp/'retained-identity-inspection.json'),
        'proof': inspection['references']['proof'],
        'historical_producer_commit': inspection['historical_producer_commit'],
        'new_consumer_commit': commit,
        'historical_verification_assessment': 'A separately identified, independently reviewed consumer can in principle check immutable historical preparation receipt syntax/evidence against the OLD source and OLD release/runtime/process anchors using the new dedicated entrypoint. This is historical compatibility verification, not a claim that the new source produced the measurement. This executor did not run readiness derivation or accept the retained proof.',
        'strict_binding_reason': 'validate_release binds the exact source_record; verify_graph binds plan/source/deployed checkout and calls verify_sources plus attest_loaded; validate_runtime_binding verifies the committed full source inventory. Both readiness_prepare.py and n36_source.py have new hashes, and the new test expands the full source inventory. Leaving old anchors fails the new loaded-source freeze; replacing anchors makes immutable old proof/release/compiled receipts disagree. Receipt rewrite or downstream rebinding is not a repair.',
        'fresh_measurement_required_for_current_route': True,
        'minimum_prospective_preparation': 'After independent review and explicit root adoption/scope admission, freeze the final consumer/producer source once, use a new one-use preparation resource and immutable output paths with a source-bound disabled plan/runtime/closure/native inventory, and obtain the separate finite preparation-only release/accounting authority. Then one prospective zero-transition CUDA/EGL preparation observation and the existing single approved-provider call must collect fresh native/runtime/source/transport/envelope/accounting evidence under that source. Preserve all old costs/history/reserves; no episode or health release follows automatically. This executor did not prepare or dispatch that transaction.',
        'proof_accepted': False, 'retained_receipts_rewritten': False, 'measurement_replayed': False
    },
    'remaining_blockers': [
        'Independent review of this commit and its external-anchor/episode-isolation invariants remains outstanding.',
        'Root adoption remains outstanding; no deployed checkout, release, source record or downstream artifact graph was rebound.',
        'Legacy readiness fixture is blocked at current recovery-partition validation; no broader readiness/integration pass is claimed.',
        'Current source freeze and source-change allowlists are unchanged. scripts/qd_ed_n36_source.py and the new test path are outside the current engineering OPERATIONAL_FILES / readiness NEW_FILES union; later adoption requires an explicit reviewed scope decision, not a silent allowlist expansion here.',
        'Operational readiness under the repaired source requires the new bounded prospective preparation described above; no existing measured proof is promoted.'
    ],
    'exact_next_bounded_step': {
        'action': 'Independent read-only CPU review of commit '+commit+' against '+authority['source'],
        'inputs': ['the four changed files', 'this report', 'hashed command logs and exact source/test provenance', 'immutable retained identity inspection'],
        'focus': ['external release/source/runtime/process trust boundary', 'full native/source/import-alias evidence linkage', 'unchanged episode rejection behavior', 'strict source-freeze retained-proof ineligibility'],
        'output': 'Independent engineering review with explicit accept/reject and any bounded defects; only root may later decide adoption/scope and a fresh preparation transaction.',
        'not_authorized_by_this_report': ['accept retained proof', 'enable release', 'rebind artifact graph', 'dispatch GPU/provider/health/episode work']
    },
    'scope_accounting': {
        'production_adopted': False, 'release_enabled': False, 'gpu_or_cuda_initialized': False,
        'provider_measurement_called': False, 'protected_validation_or_formal_outcomes_inspected': False,
        'credentials_read': False, 'owning_state_or_ledger_writes': False,
        'child_agents_or_coordinators_launched': False, 'costs_history_reserves_thresholds_changed': False,
        'source_writes_and_commit_only_in_worktree': True, 'temporary_root': str(tmp),
        'report_write_exception': str(out), 'test_thread_limits': {'OMP_NUM_THREADS': 2, 'MKL_NUM_THREADS': 2, 'OPENBLAS_NUM_THREADS': 2},
        'final_test_cpu_affinity': [0, 1], 'start_observed_utc': '2026-10-11T04:46:58Z',
        'maximum_executor_seconds': 1200, 'deadline': authority['stop_authority']['deadline'],
        'stop_paths_at_report': stop
    }
}
out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
print(json.dumps({'report': ref(out), 'engineering_status': report['engineering_status']}))
