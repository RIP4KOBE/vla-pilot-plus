import datetime as dt
import hashlib
import json
from pathlib import Path
import re

out = Path(__file__).resolve().parent
root = out.parent / 'implementation_worktree'
verified = json.loads((out / 'committed-verification-v1.json').read_text())


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


runs = [
 ('retained-01.log', 'tests/test_n32_release.py tests/test_n32_release_worker.py', 0),
 ('production-01.log', 'tests/test_n32_production.py', 0),
 ('production-02.log', 'tests/test_n32_production.py', 1),
 ('production-03.log', 'tests/test_n32_production.py tests/test_qd_ed_final_runner.py -k "n32 or budget or frozen_plan_binds or model_mutation"', 0),
 ('production-04.log', 'tests/test_n32_production.py tests/test_n31_admission.py tests/test_n31_controller.py -k "n32 or admission or real_check_budget_then_protected"', 0),
 ('production-05.log', 'tests/test_n32_production.py', 0),
 ('n32-final-01.log', 'tests/test_n32_release.py tests/test_n32_release_worker.py tests/test_n32_production.py', 0),
 ('n32-final-02.log', 'tests/test_n32_release.py tests/test_n32_release_worker.py tests/test_n32_production.py', 0),
 ('n32-final-03.log', 'tests/test_n32_release.py tests/test_n32_release_worker.py tests/test_n32_production.py', 0),
 ('shared-regression-final.log', 'tests/test_qd_ed_final_runner.py tests/test_n31_admission.py tests/test_n31_controller.py -k "budget or frozen_plan_binds or model_mutation or exclusivity or monitor or admission"', 0),
]
prefix = "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 timeout 1200 bash -c 'ulimit -t 1200; exec python -m pytest -q "
tests = []
for name, arguments, exit_code in runs:
    path = out / 'test-logs' / name
    text = path.read_text()
    lines = [line for line in text.splitlines() if re.search(r'\b\d+ passed\b', line)]
    assert lines, name
    tests.append({'command': prefix + arguments + "' > ../production-adapter-v1/test-logs/" + name + ' 2>&1',
                  'cwd': str(root), 'exit_code': exit_code, 'summary': lines[-1], 'log': ref(path)})
assert '143 passed' in tests[-2]['summary'] and '37 passed' in tests[-1]['summary']
inputs = ['scope-v1.md', '../root-release-preparation-review-v1.json', '../release-preparation-v1/report-v1.md',
          '../release-preparation-v1/scope-v1.md', '../root-runtime-cpu-review-v1.json', '../release-preparation-v1/budget-capacity-v1.json']
prerequisites = [
 'Root review of this commit, then explicit adoption/freeze of the actual execution checkout; no owning source was adopted here.',
 'Real approved protocol, approval basis, finite budget authority, plan, detached root review and execution release, supplied with external hashes. No real release/approval object was generated.',
 'Root-bound actual runtime/checkpoint/seed/init-row/BDDL/task-cache inventory and all30 external manifests recomposed for the finally adopted committed checkout; no trace-derived expectations.',
 'Actual adopted private state n32_budget_authority and matching caps/amendment, immutable historical ledger prefixes, and fresh journal-derived accounting under normal runner/state locks.',
 'Existing hash-bound accounted CUDA/EGL proof plus idle GPU7 UUID admission and current-login official Codex provider gates before each launch; no new probe or provider call from this CPU task.',
 'Real GPU/device behavior, provider usage and worst-case720-step same-worker audit latency remain unmeasured. The first root-authorized attempt must retain the1800s plus40s cleanup cap and invalid-stop rules.',
 'Root must settle interrupted/unknown or unkillable live attempts and missing duration telemetry; this adapter blocks further dispatch, never fabricates zero charge, restores a PID handle or automatically recovers.',
]
limitations = [
 'CPU synthetic fixtures only. Production lifecycle tests use temporary real locks/journals/state writes with hardware/provider/Main and receipt boundaries replaced; separate retained tests exercise real synthetic generic/native audits.',
 'Release-DAG fixtures replace committed-source verification and expensive runtime/manifest dependency checks with spies. Existing temporary-Git/source tests, committed545-file verification and selected real generic input-file tests cover those dependencies separately; no complete real-root production cohort was executed.',
 'A real freshly spawned CPU sleeping child validates direct-child cleanup and mismatched-identity refusal. No foreign process/group was signalled. Parent interruption intentionally leaves a durable unsettled handle requiring root reconciliation.',
 'No owning state/ledger/tree/code, driver.lock, coordinator.lease, GPU healthcheck, protected validation/formal result, model/checkpoint load, simulation, new agent, dependency install, cloud, credentials, API key, alternate account/provider or online provider invocation was used.',
 'Scientific efficacy, score, GPU/runtime throughput and HTTP counters are Unknown; no promotion or validation/formal/ablation authorization is claimed.',
]
result = {
 'schema': 'n32-production-adapter-cpu-result-v1', 'recorded_at': dt.datetime.now(dt.timezone.utc).isoformat(),
 'status': 'CPU_PRODUCTION_ADAPTER_IMPLEMENTED_AWAITING_ROOT_REVIEW',
 'executor_role': 'isolated_cpu_executor', 'arbor_node': 'leaf15.2',
 'code_ref': verified['commit'],
 'insight': 'A detached release avoids plan/release hash cycles, while deterministic attempt IDs and durable pre-Main process binding connect the accepted N32 receipts to existing generic accounting without replay or retry fallback.',
 'result': 'CPU production adapter committed;180 focused tests passed,545 committed source hashes verified, no GPU execution or owning-state adoption. Real root artifacts and runtime admission remain prerequisites.',
 'commit': verified['commit'], 'parent': verified['parent'], 'worktree': str(root), 'worktree_clean': True,
 'scope': ref(out / 'scope-v1.md'), 'required_inputs': [ref(out / name) for name in inputs],
 'changed_files': verified['changed_files'], 'changed_files_sha256': canonical(verified['changed_files']),
 'invariant_files': verified['invariant_files'], 'invariant_files_sha256': canonical(verified['invariant_files']),
 'source_inventory': verified['source_inventory'], 'source_inventory_count': 545,
 'changed_source_files': 7, 'invariant_source_files': 538,
 'generic_shared_refactor': {'modified_definitions': verified['generic_modified_definitions'],
                            'new_definitions': verified['generic_new_definitions'],
                            'unchanged_definition_count': len(verified['generic_unchanged_definition_ast_sha256']),
                            'unchanged_definition_ast_sha256': verified['generic_unchanged_definition_ast_sha256']},
 'committed_verification': ref(out / 'committed-verification-v1.json'),
 'original_disabled_draft_unchanged': verified['unchanged_disabled_draft'],
 'tests': tests, 'final_focused_tests': {'n32': 143, 'shared_regression': 37, 'total': 180, 'all_passed': True,
                                     'n32_seconds': 46.22, 'shared_seconds': 2.19, 'inherited_syntax_warnings': 6},
 'resolved_test_failure': 'production-02: os.pidfd_open unavailable in this Python build; replaced with one explicit identity/parent-checked direct-child Popen cleanup contract. Real CPU-child cleanup and all final tests passed.',
 'other_checks': [
   {'command': "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 timeout 1200 bash -c 'ulimit -t 1200; exec python ../production-adapter-v1/verify-delivery-v1.py' > ../production-adapter-v1/test-logs/committed-verification.log 2>&1", 'exit_code': 0, 'log': ref(out / 'test-logs/committed-verification.log')},
   {'command': 'git diff --check HEAD^ HEAD > ../production-adapter-v1/test-logs/git-diff-check.log', 'exit_code': 0, 'log': ref(out / 'test-logs/git-diff-check.log')},
   {'command': 'git show --no-patch --format=fuller HEAD > ../production-adapter-v1/test-logs/commit.log', 'exit_code': 0, 'log': ref(out / 'test-logs/commit.log')},
   {'command': 'git status --porcelain > ../production-adapter-v1/test-logs/git-status.log', 'exit_code': 0, 'log': ref(out / 'test-logs/git-status.log')},
 ],
 'commit_command': 'git add scripts/qd_ed_final_runner.py scripts/qd_ed_n32_supervise.py scripts/qd_ed_n32_worker.py scripts/qd_ed_n32_release.py scripts/qd_ed_n32_runner.py tests/test_n32_production.py && git add -f docs/experiments/n32_production_adapter.md && git commit -m "Add root-bound N32 production lifecycle and accounting adapter"',
 'commit_exit_code': 0,
 'trust_chain': ['external input references -> exact plan -> detached root review -> release -> context -> same-process audits/receipt -> parent-verified terminal',
                 'all30 source/runtime/task/config expectations are frozen before dispatch; no expectations from emitted traces',
                 'deterministic attempt_id=episode_key everywhere; no random-suffix fallback or non-null retries',
                 'actual committed/imported checkout and generic checkpoint/seed/init/BDDL/cache validators; immutable current/history ledger prefixes',
                 'parent durable PID/boot/start before stdin gate, child pre-Main process/context/release verification, parent receipt and generic cost/provider/video verification',
                 'generic journal/health aggregation and cap arithmetic; existing weekly effective ceiling; full1840s admission, protected reserves and cohort5GPUh'],
 'resource_constraints': {'cuda_hidden_for_tests': True, 'cpu_threads': 2, 'test_process_cpu_limit_seconds': 1200,
                          'test_command_wall_timeout_seconds': 1200, 'executor_wall_budget_seconds': 1800,
                          'provider_calls': 0, 'new_agents': 0, 'gpu_execution': False, 'owning_writes': False,
                          'owning_budget_recomputed': False, 'protected_result_reads': False},
 'limitations': limitations, 'remaining_release_prerequisites': prerequisites,
 'gpu_authorized': False, 'source_adopted': False, 'release_enabled': False, 'real_release_created': False,
 'validation_authorized': False, 'formal_authorized': False, 'ablations_authorized': False,
 'new_dev_outcomes': 0, 'score': None, 'score_claimed': False, 'target_met': False, 'http_counters': 'Unknown',
 'automatic_recoveries': 0, 'report_generator': ref(__file__),
}
(out / 'result-v1.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
report = f'''# N32 production adapter — bounded CPU delivery

**Implemented and committed for root review; no release, adoption or GPU execution.**

Commit `{verified['commit']}`; parent `{verified['parent']}`. The isolated implementation worktree is clean. Seven source files changed (three modifications, four additions);538 source files are byte-for-byte invariant against the parent. The545-file committed inventory and exact changed/invariant SHA256 values are recorded in [result-v1.json](result-v1.json) and [committed-verification-v1.json](committed-verification-v1.json).

## Delivered

- Detached root release validation with an acyclic inputs→plan→review→release→context chain. Required real protocol/approval/authority/source/runtime objects are externally hash-bound. The original disabled draft is byte-for-byte unchanged; no real authority/review/release object was created.
- Prospective production runner under only normal runner/state locks: preserve original ledger prefixes; recompute generic accounting; reconcile valid/live/unknown/unsettled/orphan handles; reserve→dispatch→terminal; never replay a valid cell. Exact task-major C0/Q0/N32 identities, all30 manifests, actual committed source and generic checkpoint/task/cache/init/BDDL gates precede dispatch.
- One deterministic identity contract: attempt ID equals episode key. Null non-retry fields are accepted; all non-null retry/recovery values are rejected. Context/output/process/receipt/terminal bindings are tested. The parent records PID/boot/start before opening the child gate; the child verifies that record before Main.
- Original generic and native audits remain in the bounded worker. Parent verification retains generic identity, outcome, cost, Stage/provider and video checks. Missing/malformed audit or terminal evidence stops INVALID with retained charges; it cannot become valid task failure or success. Existing terminal artifacts must agree with the journal on resume.
- Generic historical episode/health accounting, reservation and integer admission functions are reused, including weekly effective ceiling and private/global/bucket/protected/full1840s/cohort5GPUh checks. Only95 otherwise unchanged generic definitions are retained; modified generic definitions are the runtime/budget helper extractions and an optional bounded monitor callback. All N31 scientific source, controls, Main and core policy files are invariant.
- STOP/deadline/coordinator checks precede dispatch and never signal an existing episode. Monitoring errors remain INVALID even after exit0. Monitor queries share the1800s deadline; exact owned-child timeout cleanup is bounded10s TERM+30s KILL, with charge retained. No process group, foreign PID or restored handle is signalled.

Production entrypoint/schema documentation is committed at `docs/experiments/n32_production_adapter.md`. The standalone runner requires externally supplied plan/release paths and digests; it cannot generate or adopt them.

## Validation

Final N32 command exited0: **143 passed**,6 inherited SyntaxWarnings,46.22s.

```sh
{tests[-2]['command']}
```

Focused shared-runner/N31 regression command exited0: **37 passed**,59 deselected,2.19s.

```sh
{tests[-1]['command']}
```

The180 final tests cover retained scientific/config/native-receipt behavior, lifecycle/identity/replay/invalid-stop/STOP cases, all release links, bound cleanup and monitor queries, historical/health/unknown/reserved/inflight accounting, cap boundaries and generic/N31 input/admission regression. Tests use temporary fixtures only. Release-schema dependency gates are spied in the DAG fixtures and checked separately by retained source tests, actual committed-source verification and selected generic input-file tests; this is not a real-root production execution.

One early test failed because this Python build lacks `os.pidfd_open`. The final implementation uses a single explicit direct-child Popen contract with PID/boot/start and parent verification. A real new CPU sleeping child verifies cleanup and identity-mismatch refusal. No foreign process was touched. Every test command, exit and log SHA256, including that resolved failure, is recorded in [result-v1.json](result-v1.json).

Committed verification exited0:545 source files checked against Git,7 changes,538 invariants,95 unchanged generic definition ASTs, original disabled draft unchanged, clean worktree. Final diff whitespace check passed.

## Remaining root prerequisites and limits

''' + '\n'.join(f'{i}. {text}' for i, text in enumerate(prerequisites, 1)) + '''

No owning code/state/tree/ledger, driver or lease was changed. No GPU/probe, model/checkpoint load, simulation, protected validation/formal result read, provider/API/credential access, alternate account/provider, dependency installation, cloud or additional agent was used. Accounting tests charge only synthetic fixtures; actual owning balances were not recomputed or amended here.

Only complete valid triples permit numeric futility; all30 valid cells, N32>=5/10 and matched controls remain necessary for prospective promotion consideration. Unrun cells, score/efficacy and HTTP counters remain Unknown. Validation/formal/ablations and all automatic recoveries remain closed.
'''
# Correct count wording: all95 unmodified definitions, not an upper/lower bound.
report = report.replace('Only95 otherwise unchanged generic definitions are retained;', 'All95 other generic definitions remain unchanged;')
(out / 'report-v1.md').write_text(report)
print(json.dumps({'result': ref(out / 'result-v1.json'), 'report': ref(out / 'report-v1.md'),
                  'commit': verified['commit'], 'final_tests_passed': 180}))
