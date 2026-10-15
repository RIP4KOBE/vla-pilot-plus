import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
sys.path.insert(0, str(root))
from scripts import qd_ed_n36_engineering as e
out = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001482/engineering-adapter-implementation')
base = e.BASE
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
changed = subprocess.check_output(['git', 'diff', '--name-only', base, commit, '--'], text=True).splitlines()
assert set(changed) == e.OPERATIONAL_FILES

def anchor(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def create(name, value, canonical=False):
    path = out / name
    text = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) if canonical
            else json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    with path.open('x') as stream: stream.write(text)
    return anchor(path)

scope_ref = create('scope.disabled-v1.json', e.disabled_scope(), canonical=True)
accounting_ref = create('accounting.disabled-v1.json', e.disabled_accounting(), canonical=True)
e.validate_scope_reference({key: scope_ref[key] for key in ('path', 'sha256')})
e.validate_accounting_reference({key: accounting_ref[key] for key in ('path', 'sha256')})

old = ast.parse(subprocess.check_output(['git', 'show', base + ':scripts/qd_ed_n36_release.py'], text=True))
new = ast.parse((root / 'scripts/qd_ed_n36_release.py').read_text())
a = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == '_verify_release_contents').body
start = next(i for i, n in enumerate(a) if ast.unparse(n).startswith("w.require(Path(plan['worktree']).resolve()"))
end = next(i for i, n in enumerate(a[start:], start) if isinstance(n, ast.If) and ast.unparse(n.test) == 'n36r3 and (not health)')
b = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == 'verify_audit_closure').body
first = next(i for i, n in enumerate(b) if ast.unparse(n).startswith("w.require(Path(plan['worktree']).resolve()"))
identical = [ast.dump(n, include_attributes=False) for n in a[start:end]] == [ast.dump(n, include_attributes=False) for n in b[first:-1]]
assert identical
science = subprocess.run(['git', 'diff', '--quiet', base, commit, '--', 'core', 'configs', 'main.py', 'utils', 'vlm_query', 'third_party', 'scripts/qd_ed_n36_contract.py', 'scripts/qd_ed_n36_supervise.py', 'scripts/qd_ed_n36_native.py', 'scripts/qd_ed_n36_arithmetic.py', 'scripts/qd_ed_n36_dino.py', 'scripts/qd_ed_n36_source.py'], check=False).returncode == 0
assert science
proof = create('source-equivalence-v1.json', {
    'schema': 'n36-engineering-implementation-source-check-v1', 'source_base': base,
    'source_final': commit, 'changed_paths': changed,
    'audit_closure_ast_exact_extraction': identical, 'retained_closure_top_level_statements': end - start,
    'all_changes_within_operational_allowlist': True, 'scientific_paths_unchanged': science,
    'full_contract_limits_identities_expected_rows_unchanged': True,
    'supervisor_thresholds_stopping_rules_unchanged': True,
    'source_inventory_refreshed_for_release': False,
    'independent_review': False, 'release_enabled': False})

runs = [
    ('engineering-01', 'tests/test_n36_engineering.py', '18 passed, 59 setup errors in 12.83s', 1,
     'Fixed Hydra-consumed hydra.run.dir normalization; no validator removed.'),
    ('engineering-02', 'tests/test_n36_engineering.py', '18 passed, 59 setup errors in 14.06s', 1,
     'Fixed only authorized mechanism_pretest output_dir/run_id normalization; scientific comparison retained.'),
    ('regression-01', 'tests/test_n36r4_admission.py tests/test_n36_release.py tests/test_n36_runner.py', '76 passed in 13.38s', 0, None),
    ('engineering-03', 'tests/test_n36_engineering.py', '77 passed in 29.93s', 0, None),
    ('engineering-04', 'tests/test_n36_engineering.py', '101 passed in 30.81s', 0, None),
    ('shared-02', 'tests/test_n36_production_repair.py tests/test_n36_parent_binding.py tests/test_n36_stop_guard.py', '49 failed, 43 passed in 11.22s (pytest includes subtest failures)', 1,
     '47 production-repair fixture errors omit owner_root; base standalone reproduction also has 47 errors. Two stop-guard fixtures omit bind_dino, which is already called by the base worker. No production guard or existing test was weakened.'),
    ('focused-05', 'tests/test_n36_engineering.py tests/test_n36r4_admission.py tests/test_n36_release.py tests/test_n36_runner.py', '189 passed in 42.76s', 0, None),
    ('final-focused', 'tests/test_n36_engineering.py tests/test_n36r4_admission.py tests/test_n36_release.py tests/test_n36_runner.py', '190 passed in 43.15s', 0, None),
]
tests = []
for name, selection, result, code, note in runs:
    tests.append({'command': f'PYTHONDONTWRITEBYTECODE=1 python -m pytest -q {selection} --basetemp=.cpu-test-artifacts/{name} > .cpu-test-artifacts/{name}.log 2>&1',
                  'cwd': str(root), 'result': result, 'exit_code': code,
                  'log': anchor(root / '.cpu-test-artifacts' / (name + '.log')), 'note': note})
tests.append({'command': 'PYTHONDONTWRITEBYTECODE=1 python .cpu-test-artifacts/base-regression/tests/test_n36_production_repair.py > .cpu-test-artifacts/base-production-repair.log 2>&1',
              'cwd': str(root), 'result': 'Ran 6 tests; FAILED (errors=47); owner_root missing from pre-existing AST fixture namespace', 'exit_code': 1,
              'log': anchor(root / '.cpu-test-artifacts/base-production-repair.log'),
              'fixture_source': 'Exact git-show copies from ' + base + ' of the test and four referenced source modules; no production files replaced.'})
now = dt.datetime.now(dt.timezone.utc)
authority = json.loads((out / 'authority-v1.json').read_text())
report = {
    'schema': 'n36-engineering-adapter-implementation-report-v1', 'node_id': '15.6', 'at': now.isoformat(),
    'status': 'PARTIAL_DISABLED_IMPLEMENTATION_COMMITTED', 'implementation_complete': False,
    'goal_complete': False, 'release_enabled': False, 'root_adopted': False, 'gpu_authorized': False,
    'dispatch_hard_disabled': True,
    'dispatch_veto': 'require_dispatch_implementation() unconditionally raises. Engineering execute_one, runner private route, health route/reservation and worker launch guard all enforce it; no artifact or environment override.',
    'source_base_commit': base, 'source_final_commit': commit,
    'branch': subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
    'worktree': str(root), 'changed_paths': changed,
    'authority': anchor(out / 'authority-v1.json'), 'specification': anchor(Path(e.SPECIFICATION['path'])),
    'artifacts': {'disabled_scope': scope_ref, 'disabled_accounting': accounting_ref, 'source_equivalence': proof},
    'coverage': [
        {'area': 'Separate engineering schemas and exact scope', 'status': 'IMPLEMENTED_CPU_BOUNDARY_TESTED', 'details': 'Exact specification hash, canonical separate scope/accounting hashes, task0/C0 seed/init/timeout identity, strict field sets, engineering-only purpose, one attempt/one health resource, non-scientific eligibility and no continuation.'},
        {'area': 'Full audit closure extraction and manifests', 'status': 'IMPLEMENTED_PARTIALLY_VERIFIED', 'details': 'Existing 21 top-level source/loaded/runtime/controller/native/runtime-files/runtime-inputs/all-manifests statements extracted with AST equality. Full release gates remain before helper. Audit view is disabled, retains exact 40-row order/limits/worker rules/original scientific references. All 40 real Hydra manifests plus separate engineering manifest compared in CPU fixtures; NON-C0 corruption rejected. Complete refreshed production closure was not assembled.'},
        {'area': 'Bridge/worker/health routes', 'status': 'IMPLEMENTED_DISPATCH_DISABLED', 'details': 'Explicit schema dispatch, separate worker context and receipt/terminal tags, exact audit-row reference, six permitted command changes (two identities/four routes), no legacy cohort fabrication, same-process DINO/native/runtime receipt machinery preserved. Separate health route uses unchanged 20-second probe and 40-second cleanup mechanics.'},
        {'area': 'Authority and accounting', 'status': 'IMPLEMENTED_PARTIALLY_VERIFIED', 'details': 'Separate exact B5, protocol acceptance, source adoption, owner accounting adoption; three retained prefixes, whole snapshot, margin reference, exact live suffixes; unchanged global/weekly/protected gates plus 1900 GPU seconds, 60 health seconds and 2100 wall envelope. No actual owner journals or adoption records were read/revalidated.'},
        {'area': 'One-use lifecycle', 'status': 'IMPLEMENTED_JOURNAL_PRIMITIVES_TESTED_NOT_RELEASED_PATH_VERIFIED', 'details': 'Shared runner lifecycle wired without global monkeypatching. Strict single reservation lifecycle, fail-closed crash/abort, valid terminal then permanent pause, no next row, editable pause/G3 flags cannot restore the slot. Temporary real locks/fsync/journal/state/terminal artifacts tested, with synthetic outcomes; full new released execute_one/health path remains unverified and hard-vetoed.'},
        {'area': 'Scientific aggregation', 'status': 'IMPLEMENTED_CPU_BOUNDARY_TESTED', 'details': 'Engineering purpose/cohort rejected by N36 report aggregator; engineering reconciliation returns no scientific outcomes. Scientific identities/limits, thresholds, supervisor and configs are unchanged.'},
    ],
    'tests': tests,
    'final_focused_result': {'passed': 190, 'failed': 0, 'new_engineering_cases': 114, 'existing_regression_cases': 76},
    'additional_checks': {
        'syntax': anchor(root / '.cpu-test-artifacts/syntax-final.json'),
        'diff_check_command': 'git diff --cached --check (before commit); git diff --check',
        'diff_check_result': 'PASS',
        'source_equivalence': proof,
        'final_commit_contains_only_intended_source_test_files': True,
        'untracked_test_artifacts': str(root / '.cpu-test-artifacts'),
        'applicable_AGENTS': 'Provided global instructions applied. Explicit lexical ancestor and scripts/tests searches found no additional AGENTS.md.',
        'skill': '/home/hynx/.codex/skills/arbor-agent-executor/SKILL.md',
        'skill_scope_override': 'User CPU-only executor authority overrides skill coordinator/tree-state, evaluation and dispatch workflows.'},
    'fixture_limitations': [
        'New fixture plans, scopes and accounting artifacts remain disabled. No new root/B5 approval or enabled plan was manufactured.',
        'Composition fixtures bind the old disabled preparation runtime/source metadata, and do not attest the new final commit, installed runtime, DINO construction or native/GPU success.',
        'New mutation/composition/suffix tests use actual production validators. Journal fixtures use actual runner append/locking/state primitives but synthetic terminal outcomes and a local artifact-equality callback, not the production GPU receipt verifier.',
        'Existing regression suites retain their pre-existing mocks of source/runtime/device/release dependencies. Their passing results are CPU regression evidence only.',
        'Complete engineering health/episode release acceptance and deep source/runtime/native/controller mutation matrix behind a valid full closure remain unverified.',
        'Two stop-guard failures are attributed to the pre-existing missing bind_dino fixture method by exact base-source inspection; unlike production-repair errors, those two full tests were not separately rerun on a base checkout.'
    ],
    'remaining_gaps': [
        'Build non-authorizing CPU integration fixtures that exercise complete engineering release acceptance and every required NON-C0/source/runtime-closure/native-build/controller mutation for both health and episode using unchanged validators.',
        'Exercise actual new released engineering execute_one and run_healthcheck/reserve_health paths, including valid receipt-to-terminal equality, readiness freshness, crashes at reservation/dispatched/terminal-before-artifact, abort exhaustion, and full deadline/headroom boundaries. Current new tests stop at real journal primitives and pure reconciliation.',
        'Exercise full engineering authority/adoption/whole retained snapshot and readiness pipelines without touching owner state or generating deployable synthetic approvals.',
        'Resolve/update the separately identified stale pre-existing fixtures under a subsequent bounded test-maintenance task; do not weaken owner routing or DINO guards to make them pass.',
        'Retain the dispatch veto until the remaining integration work is complete and independently reviewed. Removing it requires a new source commit and fresh exact source/runtime/native/manifest bindings; no root/G3 flag can override this commit.',
        'Actual final-source inventories, full 40 refreshed audit manifests and engineering manifest, independent B5, root protocol/source/accounting adoption and separate releases/readiness are future owner/reviewer work, not created here.'
    ],
    'next_independent_review_needs': [
        'Review schema/DAG bindings for cycles, field completeness, lexical source/owner/output routes, both STOP entries, source equivalence and scope/legacy cross-use.',
        'Review every launch/receipt/terminal boundary and global versus one-use accounting under restart, lock transfer, malformed/foreign/unsettled suffixes and aborted health.',
        'Review the behavior-preserving shared refactor and the explicit dispatch veto before assigning bounded follow-up CPU fixture/implementation work.',
        'Only after a reviewed follow-up commit may the owner refresh bindings and decide prospective adoption. This report is neither B5 nor root approval.'
    ],
    'constraints': {'cpu_only': True, 'gpu_model_download_evaluation': False, 'protected_validation_formal_outcomes_read': False,
        'prohibited_untracked_design_read': False, 'credentials_read_or_used': False, 'other_agents_launched': False,
        'foreign_writes': False, 'owner_state_ledger_writes': False, 'driver_lease_acquisition': False,
        'root_B5_self_approval': False, 'release_or_adoption_fabrication': False,
        'existing_scientific_gates_weakened': False},
    'model_route_provenance': 'Existing executor session only; requested official current-login gpt-6-astra route. No additional model/provider tools, credential inspection or independent account-route attestation performed.',
    'timing': {'wall_cap_seconds': 1800, 'authority_at': authority['at'],
        'elapsed_since_authority_seconds': (now - dt.datetime.fromisoformat(authority['at'])).total_seconds(),
        'reason_for_partial': 'Remaining full closure-backed engineering lifecycle fixtures and independent integration assessment exceed the remaining bounded CPU implementation window; commit remains hard-disabled.'},
    'score': None,
    'insight': 'The diagnostic can reuse unchanged scientific closure and journal primitives only through separate authority and operational identity bindings. Composition and pure one-use journals are CPU-testable, but they do not establish a released engineering worker lifecycle.',
    'result': 'Committed a hard-disabled partial engineering adapter with 190 passing focused CPU tests and explicit integration gaps; no execution or adoption.',
    'code_ref': commit,
}
create('report-v1.json', report)
md = f'''# Node 15.6 — disabled partial implementation

**Status: PARTIAL_DISABLED_IMPLEMENTATION_COMMITTED.** No completion, release, adoption, B5 acceptance or runtime success is claimed.

Base `{base}` → commit `{commit}` on `{report['branch']}`.

Implemented separate pinned scope/accounting schemas, exact task0/C0 mapping, the full 40-manifest audit view and separate engineering manifest, strict worker/health schema routes, prospective authority/accounting checks, and one-use journal reconstruction. The shared scientific closure is an exact AST extraction of 21 top-level statements. Scientific source/configs, full-cohort identities/limits, thresholds and stopping rules remain unchanged. Changed paths and exact evidence are in [report-v1.json](report-v1.json).

**Dispatch is unconditionally vetoed in code.** The engineering runner route, public one-shot entry, health route/reservation and worker launch guard cannot run, even with approval-like flags. A subsequent reviewed implementation commit is required to lift the veto.

**CPU checks:** final focused command passed **190 tests** (114 new engineering cases, 76 unchanged regressions), in 43.15 seconds:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_n36_engineering.py tests/test_n36r4_admission.py tests/test_n36_release.py tests/test_n36_runner.py --basetemp=.cpu-test-artifacts/final-focused > .cpu-test-artifacts/final-focused.log 2>&1
```

All 40 audit manifests and the extra engineering manifest were composed/compared with production Hydra/comparison code. Temporary actual lock/fsync/journal/state primitives cover reservation, dispatch, abort and terminal-before-artifact crashes. Synthetic outcomes are not GPU receipts. The fixtures contain stale/disabled runtime/source metadata and cannot establish final-source runtime closure, DINO construction or native/GPU validity.

Broader shared tests reported **43 passed / 49 failed including subtests**. The production-repair fixture omits `owner_root`; exact base copies reproduce its 47 errors across six unittest tests. Two stop-guard fixtures omit `bind_dino`, whose call already exists at the base; those two full tests were not separately rerun on a base checkout. Existing tests and production guards were not weakened. All commands, failed iterations, hashes and fixture limitations are retained in the JSON report.

**Remaining implementation/verification work:** complete closure-backed health/episode release mutation tests; actual released engineering runner/health lifecycle and receipt/readiness fixtures; full authority/adoption/snapshot checks; independent review of routing, one-use accounting, lock transfer and crash semantics. This exceeds the remaining bounded window, so the partial commit stays disabled. Future final-source inventories, 40 refreshed audit manifests plus engineering manifest, B5/root adoptions and separate releases remain owner/reviewer responsibilities.

Disabled inputs: [scope](scope.disabled-v1.json), [accounting](accounting.disabled-v1.json). Source checks: [source-equivalence-v1.json](source-equivalence-v1.json). These grant no authority.

No GPU/model/download/evaluation, protected outcomes, prohibited design file, credentials, extra agents, foreign writes, owner-state/ledger writes or driver/lease acquisition occurred. Only intended source/test files were committed; new test artifacts remain under the authorized checkout. The executor skill was followed within the user's CPU-only override; no coordinator/tree-state workflow ran.
'''
with (out / 'report-v1.md').open('x') as stream: stream.write(md)
print(json.dumps({'report': anchor(out / 'report-v1.json'), 'markdown': anchor(out / 'report-v1.md'), 'commit': commit, 'status': report['status'], 'elapsed_seconds': report['timing']['elapsed_since_authority_seconds']}, indent=2))
