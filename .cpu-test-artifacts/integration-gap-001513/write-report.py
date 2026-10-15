import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

root = Path.cwd()
artifacts = root / '.cpu-test-artifacts/integration-gap-001513'
target = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001513/integration-gap-followup')
def record(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()
first_run = json.loads((artifacts / 'targeted-1.json').read_text())
run = json.loads((artifacts / 'targeted-2.json').read_text())
assert run['exit_code'] == 0, 'Context test must finish before finalizing its pass claim'
now = dt.datetime.now(dt.timezone.utc)
authority = json.loads((target / 'authority-v1.json').read_text())
before = authority['source']
after = git('rev-parse', 'HEAD')
assert after != before
paths = git('diff', '--name-only', before, after).splitlines()
assert paths == ['tests/n36_engineering_cpu_fixture.py', 'tests/test_n36_engineering_integration.py']
assert not git('diff', '--name-only', 'HEAD')
assert not list((root / '.cpu-test-artifacts').glob('ephemeral-engineering-*')), 'Disposable graph must be removed'
arithmetic = {
    'new_arithmetic_boundary_tests': 0,
    'existing_test_not_rerun': 'tests/test_n36_engineering_integration.py::test_clock_and_headroom_edges',
    'static_existing_coverage': [
        'Exact datetime deadline headroom equality and one microsecond short for need=2100,1840,60 seconds; detached issuance also has 2100-second and one-microsecond-short cases.',
        'Nominal health reservation 60 seconds and episode reservation 1840 seconds; local 60/3600 float accepted and (60+1e-8)/3600 rejected by 1900-second engineering cap.',
        'Weekly/protected bound bracketed by adjacent representable floats with protected=44 hours, retained margin=0.23357169027962 hours, total need=1900 for health and need=1840 for episode.'
    ],
    'not_proven': [
        'No literal Decimal equality claim for float 60/3600 or adjacent representable weekly-boundary inputs.',
        'No exhaustive exact-equality/just-over matrix across global, protected, absolute, weekly, local scope and separate health caps.',
        'No integrated admission at each arithmetic boundary; new runner cases use nominal accepted fixture accounting only.',
        'No isolated accepted absolute-cap boundary under the simultaneously active stricter weekly ceiling.'
    ],
    'weekly_hours_unchanged': '221.08404692669838',
    'absolute_hours_unchanged': '224',
    'retained_margin_hours_unchanged': '0.23357169027962',
    'engineering_scope_seconds_unchanged': 1900,
    'health_seconds_unchanged': 60,
    'episode_reservation_seconds_unchanged': 1840,
}
assertions = {
    'fresh_episode': [
        'Real accepted health/release prerequisite using simulated device/provider/import evidence; each episode starts with no local attempt suffix.',
        'STOP inserted after real durable reserved append raises STOP; suffix is reserved only, no Popen call, no process or terminal artifact.',
        'STOP inserted after real durable dispatched append raises STOP; suffix is reserved/dispatched, no Popen call, no process or terminal artifact.',
        'Simulated Popen OSError before child creation produces reserved/dispatched/aborted and INVALID_STOP; outcome_valid=false, success=null, retryable_infrastructure=false, required_cost_telemetry_complete=false.',
        'Aborted terminal matches durable attempt-result artifact; zero seconds is from a stationary simulated clock and is not measured real launch cost.',
        'Every case retains both 1840-second reservation fields and creates no episode child.',
        'Both STOP cases pass all restart assertions: LIVE_OR_UNSETTLED, scope_exhausted=true, continuation_authorized=false, scientific_eligible=false, next_row=null, outcomes=[].',
        'Aborted pre-child launch restart actually returned LIVE_OR_UNSETTLED, failing the initial test expectation INVALID_STOP. Static review identifies existing_handles UNKNOWN classification for absent process.json. Expectation corrected without production changes; this corrected test was not rerun within the remaining budget.',
        'Both STOP restarts leave disposable owner/output bytes unchanged and make no launch. Final aborted-case scope flags/byte equality and the last veto assertion were not reached because of the status mismatch; these remain unverified in the corrected test.'
    ],
    'accepted_context': [
        'Context constructed by real context_for and accepted by real validate_context before mutations; admission=True raises unchanged public dispatch veto.',
        'Ordinary worker-context schema with ordinary field set plus engineering plan/release reaches explicit worker context/release family cross-use rejection after full release transaction verification.',
        'Health release in accepted episode context rejects at engineering detached release fields.',
        'Audit-view plan in operational context rejects at unsupported worker release schema.',
        'Foreign purpose, foreign scope, and foreign audit_plan each reject at engineering context bindings after release validation.',
        'Each of six mutations leaves disposable owner/output file bytes and simulated launch list unchanged; original accepted context still validates afterward.'
    ]
}
gaps = [
    'Fresh episode test failed only at the final aborted-case restart status expectation. Corrected to observed conservative LIVE_OR_UNSETTLED, but no full rerun fits the 1000-second budget. Remaining assertions after that line are unverified for this case.',
    'Arithmetic boundary limitations itemized in arithmetic_coverage remain open.',
    'No reverse cross-family case from an independently accepted production-family graph; coverage starts from accepted engineering context only.',
    'Synthetic retained history and disposable source/runtime graph, closure v1 and interpreter aliases only; no actual owner snapshot, production inventory or generated-module-v2 closure.',
    'Native library bytes and import/bootstrap/device/provider observations are simulated or inert; no actual native/GPU child execution or real launch-admission certification.',
    'Prior broader 49 failures / 43 passes are not rerun or resolved; no global all-tests-pass claim.',
    'Production inventories/manifests, independent B5, owner accounting/source adoption, readiness/releases, GPU execution and scientific promotion remain out of scope.',
    'Original validation/formal/required-ablation completion contract remains unsatisfied.'
]
report = {
    'schema': 'n36-cpu-integration-gap-executor-report-v1', 'node_id': '15.6',
    'at': now.isoformat(), 'status': 'PARTIAL_FRESH_EXPECTATION_CORRECTED_CONTEXT_PASS',
    'before_commit': before, 'after_commit': after, 'worktree': str(root),
    'changed_paths': paths, 'changed_file_records': [record(root / p) for p in paths],
    'authority': record(target / 'authority-v1.json'),
    'prior_review': record(target.parent.parent / '001512/review/root-review-v1.json'),
    'production_code_changes': False, 'source_adopted': False,
    'verification': {'runs': [{**first_run, 'log': record(artifacts / 'targeted-1.log'), 'timing_record': record(artifacts / 'targeted-1.json')}, {**run, 'log': record(artifacts / 'targeted-2.log'), 'timing_record': record(artifacts / 'targeted-2.json')}],
        'total_focused_test_seconds': first_run['elapsed_seconds'] + run['elapsed_seconds'],
        'thread_environment': {k: '2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},
        'focused_test_budget_seconds': 1000, 'command_timeout_seconds': [930, 285],
        'new_tests_only': True,
        'tested_source_note': 'Run 1 used the new uncommitted tests before correcting the aborted restart expectation; its traceback retains that assertion. Run 2 used the final committed test bytes. The corrected fresh test was not rerun.', 'prior_f1_and_restart_matrix_rerun': False,
        'failed_test_logs': [record(artifacts / 'targeted-1.log')], 'tests_running_at_report': False,
        'git_diff_check_passed': True},
    'timing': {'authority_issued_at': authority['at'],
        'elapsed_upper_bound_from_authority_seconds': (now-dt.datetime.fromisoformat(authority['at'])).total_seconds(),
        'note': 'Authority timestamp predates executor work; conservative upper bound, not exact executor start.',
        'report_and_commit_deadline_seconds': 1500, 'total_budget_seconds': 1800},
    'actual_assertions_reached': assertions, 'arithmetic_coverage': arithmetic,
    'unresolved_gaps_and_scope_limitations': gaps,
    'dispatch_veto_retained': True, 'gpu_authorized': False, 'release_enabled': False,
    'native_or_gpu_evidence': False, 'scientific_success_or_promotion': False,
    'owner_research_state_checkpoint_tree_ledgers_mutated': False,
    'disposable_graph_removed': True, 'goal_complete': False,
    'score': None,
    'insight': 'Fresh handoff STOPs remain unsettled and exhaust scope; pre-child failure durably aborts, then restart conservatively reports an unknown handle. Accepted engineering context rejects cross-family schema/release and foreign bindings through real validators.',
    'result': 'New context test passed; fresh episode test reached final restart with a conservative status differing from its initial expectation, corrected but not rerun. No production changes or source adoption.',
    'code_ref': after,
}
assert report['timing']['elapsed_upper_bound_from_authority_seconds'] < 1500
(target / 'report-v1.json').write_text(json.dumps(report, indent=2) + '\n')
text = f'''# Node 15.6 bounded CPU executor report

Status: {report['status']}. CPU engineering evidence only; goal_complete=false.

Commit: `{before}` → `{after}`. No production code changes or owner source adoption.

Changed paths:
''' + ''.join(f'- `{p}`\n' for p in paths)
text += f'''\nContext test passed, exit {run['exit_code']}, {run['elapsed_seconds']:.2f} seconds wall time; initial fresh test failed after {first_run['elapsed_seconds']:.2f} seconds, its final status expectation was corrected but not rerun, CPU affinity {run['cpu_affinity']}, numerical-library thread limits 2. Existing F1/restart tests were not rerun. The failed fresh-test log is retained. Total focused test time: {first_run['elapsed_seconds'] + run['elapsed_seconds']:.2f} seconds. No tests remain running. `git diff --check` passed.

Command: `{' '.join(run['command'])}`

Logs: `{artifacts / 'targeted-1.log'}` (failure) and `{artifacts / 'targeted-2.log'}` (context pass). SHA256 values for both logs are recorded in report-v1.json. Exact timestamps, timing and test-file hashes are in report-v1.json.

Actual assertions reached:
'''
for group, items in assertions.items():
    text += f'\n{group}:\n\n' + ''.join(f'- {x}\n' for x in items)
text += '\nArithmetic accounting (static source review; prior arithmetic tests not rerun):\n\n'
text += ''.join(f'- {x}\n' for x in arithmetic['static_existing_coverage'] + arithmetic['not_proven'])
text += '\nThe unchanged weekly ceiling is 221.08404692669838 hours, stricter than the unchanged 224-hour absolute ceiling. No arithmetic guards or scientific/audit gates were modified.\n\nRemaining gaps and scope limits:\n\n'
text += ''.join(f'- {x}\n' for x in gaps)
text += f'''\nThe disposable graph was removed. Existing untracked CPU artifacts were retained. Only these reports were written at the designated owner report location; no owner research-state/checkpoint/tree/ledger mutation occurred.

The unconditional dispatch veto remains. GPU authorization=false, release_enabled=false, native_or_gpu_evidence=false, scientific_success_or_promotion=false, goal_complete=false.

Report and commit completed within {report['timing']['elapsed_upper_bound_from_authority_seconds']:.2f} seconds measured conservatively from the earlier authority issuance timestamp, below the 1500-second reporting deadline and 1800-second total cap.
'''
(target / 'report-v1.md').write_text(text)
print(json.dumps({'report': str(target / 'report-v1.json'), 'commit': after, 'elapsed_upper_bound': report['timing']['elapsed_upper_bound_from_authority_seconds']}))
