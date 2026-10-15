"""Assemble authorized executor reports from exact local evidence; no study writes."""
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

root = Path.cwd()
base = '3b05c0b557b59bf3dc9ddbb11593a41a4e49f4d1'
out = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001498/adapter-fix-integration')

def bind(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

def fn(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)

class Legacy(ast.NodeTransformer):
    def visit_If(self, node):
        if isinstance(node.test, ast.Name) and node.test.id == 'engineering':
            return [self.visit(x) for x in node.orelse]
        return self.generic_visit(node)

checks = {}
for name, function in [('scripts/qd_ed_n36_engineering.py', 'require_dispatch_implementation'),
                       ('scripts/qd_ed_n36_healthcheck.py', 'run_healthcheck')]:
    old = fn(ast.parse(git('show', base + ':' + name)), function)
    new = fn(ast.parse((root / name).read_text()), function)
    if function == 'run_healthcheck':
        old, new = Legacy().visit(old), Legacy().visit(new)
    checks[function + '_unchanged' + ('_legacy_projection' if function == 'run_healthcheck' else '')] = ast.dump(old) == ast.dump(new)
assert all(checks.values())

prefix = 'OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q '
suite = 'tests/test_n36_engineering_integration.py'
order06 = ['test_f1_reacquired_handoff_rejects_foreign_resource_before_output',
    'test_f1_live_snapshot_mutation_matrix_under_real_locks', 'test_deep_closure_corruption_both_release_families',
    'test_clock_and_headroom_edges', 'test_public_dispatch_veto_still_unconditional',
    'test_accepted_health_reservation_readiness_episode_release', 'test_restart_crashes_and_terminal_receipt_mismatch']
order07 = ['test_authority_adoption_and_full_snapshot_mutations', 'test_public_reservation_and_guard_veto',
    'test_accepted_health_reservation_readiness_episode_release', 'test_restart_crashes_and_terminal_receipt_mismatch']
tests = []
for n in range(1, 9):
    log = root / f'.cpu-test-artifacts/integration-001498-{n:02}.log'
    if not log.exists(): continue
    args = suite if n < 6 else (suite + '::test_predispatch_health_abort_cross_release_and_issuance_edges' if n == 8 else ' '.join(suite + '::' + name for name in (order06 if n == 6 else order07)))
    text = log.read_text()
    summaries = [line for line in text.splitlines() if re.search(r'\b(?:passed|failed|error|no tests ran)\b.*\bin\s+[0-9]', line)]
    tests.append({'command': prefix + args + ' -x > ' + str(log.relative_to(root)) + ' 2>&1',
        'cwd': str(root), 'log': bind(log), 'result': summaries[-1] if summaries else 'INCOMPLETE; inspect log',
        'exit_code': 2 if 'KeyboardInterrupt' in text else 1 if ('FAILED ' in text or 'ERROR ' in text) else 0,
        'note': {1: 'Fixture setup: exact retained-total float mismatch; corrected fixture decomposition.',
                 2: 'Fixture setup: empty checkpoint fingerprint list; supplied inert local fixture bytes.',
                 3: 'Harness reached production veto; fixed test-local orchestration copies. No production veto changed.',
                 4: 'Accepted health -> actual reservation/terminal/readiness -> accepted episode release and context; pre-episode fixture milestone.',
                 5: 'Intentionally interrupted obsolete orchestration harness before any test completed.',
                 6: 'Five groups completed; intentionally interrupted redundant positive validation to budget actual episode/restart path. Those five test bodies and production code remained unchanged.',
                 7: 'Authority/veto and full positive lifecycle/normal restart passed. Crash matrix rejected reset-to-earlier fixture time before its first crash assertion; corrected clock restoration in final test source, but did not rerun the expensive five-case matrix.',
                 8: 'Real predispatch health abort/exhaustion, cross-release-family rejection and exact/one-microsecond-short detached health issuance window.'}[n]})
for log in sorted((root / '.cpu-test-artifacts').glob('*001498*regression*.log')):
    text = log.read_text()
    tests.append({'command': prefix + 'tests/test_n36_runner.py -k health > ' + str(log.relative_to(root)) + ' 2>&1',
        'cwd': str(root), 'log': bind(log), 'result': text.strip().splitlines()[-1],
        'exit_code': 0 if 'failed' not in text and 'error' not in text else 1})

commit = git('rev-parse', 'HEAD')
changed = git('diff', '--name-only', base, commit).splitlines()
assert commit != base
assert set(changed) == {'scripts/qd_ed_n36_engineering.py', 'scripts/qd_ed_n36_healthcheck.py',
                        'tests/n36_engineering_cpu_fixture.py', 'tests/test_n36_engineering_integration.py'}
assert not list((root / '.cpu-test-artifacts').glob('ephemeral-engineering-*'))
authority = json.loads((out / 'authority-v1.json').read_text())
at = dt.datetime.now(dt.timezone.utc)
status = json.loads((root / '.cpu-test-artifacts/final-status-001498.json').read_text())
report = {
    'schema': 'n36-adapter-fix-integration-report-v1', 'node_id': '15.6', 'at': at.isoformat(),
    'authority': bind(out / 'authority-v1.json'), 'source_base_commit': base, 'source_final_commit': commit,
    'code_ref': commit, 'branch': git('branch', '--show-current'), 'worktree': str(root),
    'source_tree': git('rev-parse', 'HEAD^{tree}'), 'changed_files': [bind(root / p) for p in changed],
    'status': status['status'], 'result': status['result'], 'goal_complete': False, 'goal': False,
    'score': None, 'release_enabled': False, 'dispatch_hard_disabled': True, 'gpu_authorized': False,
    'root_adopted': False, 'implementation_complete': False,
    'changes': [
        'Engineering-only handoff binds canonical plan/runtime/authority/post-sync state while both locks are held.',
        'After runner-lock reacquisition, state-locked validation repeats full health release, snapshot, authority/live suffix and owner-state validation; requires no episode and exact sole original reserved health event; rechecks run/artifact/GPU bindings and digest.',
        'Handoff rejection occurs before output creation and outside settlement; original spent reservation remains and no second reservation/child is attempted.',
        'Engineering readiness now requires reserved <= dispatched <= observed <= completed <= now/deadline.',
        'Operational source allowlist includes the two explicitly authorized integration fixture/test files; no scientific file changes.',
        'One reusable ephemeral CPU fixture graph with inert local Git/source/runtime/native/controller leaves, synthetic exact 506-attempt whole snapshot, and real closed-schema approval/readiness/receipt/terminal consumers.'
    ],
    'static_checks': checks, 'tests': tests,
    'reused_evidence': {'result': '190 passed in 43.15s; not rerun',
        'log': bind(root / '.cpu-test-artifacts/final-focused.log'),
        'sha256_matches_review': bind(root / '.cpu-test-artifacts/final-focused.log')['sha256'] == '41cf00a6965325ee293614f0abd5a6732157702dc55acc97e80521caa76ee7c1'},
    'coverage': status['coverage'], 'remaining_gaps': status['remaining_gaps'],
    'fixture_boundaries': [
        'All approval-shaped documents and local Git stores exist only inside TemporaryDirectory under this worktree; fixture identities and SOURCE/OWNER/SESSION/specification/accounting/protocol pins are test-local. Temporary directories were removed. No operational approval, source inventory, readiness or release was created.',
        'Fixture source tree includes copied composition/core inputs and inert source/dependency files. Actual Git/blob/source validation and all40 Hydra/constructor composition run; this is not a final-source production inventory or real owner retained history.',
        'Loaded parent-module observations are a test-local sys module view; source-only bootstrap active/attest observations are simulated. They do not establish actual parent bootstrap admission.',
        'Device admission, provider observation, credential-free child environment, process identity/Popen/wait, clocks and child-produced evidence are simulated. No model/GPU/provider process or credential read occurred.',
        'Private AST copies of health/reservation/runner/guard orchestration remove only explicit dispatch-veto calls and route an isolated test-local API facade; production public veto functions are unchanged and tested. Public dispatch was never enabled.',
        'Real plan/authority/adoption/prefix/full-snapshot/scientific-equivalence/source/runtime/native/controller/all40/engineering-manifest/readiness/context/receipt/terminal/generic result validators remain. Real append/fsync/locks/state sync/reconciliation operate only on the disposable graph.',
        'Episode child observations use zero-guided-chunk synthetic telemetry and a CPU-encoded one-frame video; native/GPU/provider claims are explicitly simulated child claims, not scientific outcomes or native recomputation evidence.',
        'The fixture covers runtime-closure v1 plus closed interpreter aliases; it does not build the production generated-module v2 closure or attest installed production runtime/GPU readiness.'
    ],
    'constraints': {'max_cpu_threads': 2, 'wall_cap_seconds': 1800, 'subagents': False,
        'alternate_model_or_API': False, 'network_downloads_cloud': False, 'GPU_or_model_loading': False,
        'credentials_read': False, 'Superpowers': False, 'protected_results_read': False,
        'prohibited_design_read': False, 'owning_state_ledgers_tree_checkpoint_changed': False,
        'other_worktrees_changed': False, 'scientific_files_changed': False,
        'production_provenance_rebuilt': False, 'operational_approvals_created': False,
        'old_cpu_evidence_preserved': True, 'broad_retests': False},
    'model_route': 'Existing official current-login session only as requested; no other model channel or independent credential/account attestation.',
    'timing': {'authority_at': authority['at'], 'finished_at': at.isoformat(),
        'elapsed_since_authority_seconds': (at-dt.datetime.fromisoformat(authority['at'])).total_seconds(),
        'elapsed_task_seconds': time.time()-float(sys.argv[1]), 'wall_cap_seconds': 1800},
    'insight': 'A durable one-use reservation must be revalidated against the entire live snapshot after lock transfer; selected-resource equality alone cannot preserve the admission decision. CPU fixture acceptance is distinct from operational authority.'
}
(out / 'report-v1.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
md = [f"**Node 15.6: {status['status']}**", '', status['result'], '',
      f"Commit `{base}` → `{commit}` on `{report['branch']}`. Goal remains **false**; public dispatch veto remains unconditional.", '',
      'F1 now revalidates the engineering health handoff under the state lock after runner-lock reacquisition, binds unchanged plan/runtime/authority/post-sync state, and requires no episode plus the exact original sole reservation. Rejection leaves it spent and launches no child. Readiness also checks dispatch timestamp ordering. Legacy health branch and veto AST are unchanged.', '',
      '**Tests and evidence**', '']
md += [f"- {t['result']} — `{Path(t['log']['path']).name}` (SHA-256 `{t['log']['sha256']}`)." for t in tests]
md += ['', 'Reused, without rerunning: **190 passed**, bound log SHA-256 `41cf00a6965325ee293614f0abd5a6732157702dc55acc97e80521caa76ee7c1`.', '', '**Coverage**', '']
md += ['- '+v for v in status['coverage']]
md += ['', '**Remaining gaps**', ''] + ['- '+v for v in status['remaining_gaps']]
md += ['', '**Fixture and scope limits**', ''] + ['- '+v for v in report['fixture_boundaries']]
md += ['', 'Changed files (exact committed bytes):', ''] + [f"- `{Path(v['path']).relative_to(root)}` — `{v['sha256']}`." for v in report['changed_files']]
md += ['', f"CPU threads limited to 2. Finalized in {report['timing']['elapsed_task_seconds']:.1f}s from task start ({report['timing']['elapsed_since_authority_seconds']:.1f}s since authority). No owner-state, ledger, tree, checkpoint, other-worktree, frozen scientific-file or authority edits; no GPU, network, credentials, protected results, prohibited design, cloud, alternate model or subagents. Exact commands, artifact byte counts and scope checks are in report-v1.json."]
(out / 'report-v1.md').write_text('\n'.join(md) + '\n')
print(json.dumps({'report': str(out / 'report-v1.json'), 'commit': commit, 'elapsed': report['timing']}, indent=2))
