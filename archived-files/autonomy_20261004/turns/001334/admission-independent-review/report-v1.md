# Independent CPU review: PASS

Node 15.6; exact source `5da91e13a32211ac51ff0bb81d76aaefa0cc583f` from `b86ac1291b08ba2b6bf33e7a6e19326016f4c40e`. This is a CPU integration decision only. No introduced production-blocking defect was found in the reviewed changes. No source adoption, release, live readiness, G3 acceptance, scientific promotion or goal completion is granted.

## Bound inputs and method

The authority’s four direct input byte counts and SHA-256 values match. The source is HEAD, its direct parent is the requested base, tracked status is clean, and all 13 changed working files match the commit. Verified 26 direct/source/log/terminal-child references. The static-check output had a label typo (“27”); its actual count was 26.

Full diff: 71,728 bytes; SHA-256 `0467f8624c53fc251e4ef97723b89d12c4d2d8a27300a03b77736e6c232aff75`. Authority SHA-256 `3683271be33e50e16754eef9581ef129356e68eaade48c00e74f417ebf6c9c92`. Changed Python files parse; `git diff --check` passes.

Reviewed only local authority/report/logs, exact diff and necessary surrounding functions. No new pytest run was necessary: source comparison and retained receipts resolve the failure classifications. No project modules, production commands, GPU/simulator/provider calls, network, installs or agents were invoked. CPU static checks used threads 2, empty CUDA_VISIBLE_DEVICES, PYTHONDONTWRITEBYTECODE=1 and Python -B. No test cache/basetemp was created. The session login/model was not independently probed and no alternate provider/model was invoked.

## Integration assessment

**Real positive admission DAG — PASS by source inspection, synthetic execution evidence scoped.** Frozen plan and exact independent B5/source adoption precede a distinct externally hashed N36R3 health review/release. Health validation omits episode readiness, avoiding a forward cycle. Episode root review/release binds completed health evidence; locked admission additionally requires reserved/dispatched/completed journal equality. Bare plans, draft flags, N36R2 approvals and health releases do not authorize episode dispatch. Evidence: `qd_ed_n36_release.py:55-165; qd_ed_n36r3_admission.py:33-91,148-179; qd_ed_n36_healthcheck.py:42-118`.

**Lexical owner versus source — PASS.** Exact lexical OWNER and isolated SOURCE are distinct and resolve to themselves in this checkout. Owner supplies state, locks and all journals; source supplies cwd/import paths/provider configuration. Owning state worktree must equal OWNER. No live owner journals or state were read by this reviewer. Evidence: `qd_ed_n36r3_admission.py:23-30; qd_ed_n36r2_admission.py:16-28,100-109; qd_ed_n36_runner.py:64-104; qd_ed_n36_release.py:281-295`.

**Exact binding closure — PASS.** Authority, source/scientific source, runtime/closure, native/controller, protocol/accounting, all 40 manifests, adoption and independent/root review remain checked. Health readiness requires matching terminal, probe evidence/frame/script hash, provider flag and authority window; locked journal settlement is checked before episode admission. Actual source/runtime leaves still require refreshed production bindings. Evidence: `qd_ed_n36_release.py:98-165; qd_ed_n36r3_admission.py:19-91; qd_ed_n36_bridge.py:86-95`.

**STOP and deadline — PASS.** Both canonical lexical entries are lstat checked; any entry or non-ENOENT failure vetoes. Deadline is bounded by canonical 2026-10-11T11:13:13Z and authority window. Health requires 60 seconds; episode requires 1840. Guards repeat around reservation/launch. STOP is not a signal to kill a running child. This review never created, removed or touched actual STOP files. Evidence: `qd_ed_n36_stop.py:22-36; qd_ed_n36_contract.py:55-65,223-267; qd_ed_n36r3_health.py:51-56; qd_ed_n36_healthcheck.py:65-88`.

**Finite accounting and no retry — PASS.** 505 previous attempts and exact 75.52725286641478 GPUh baseline are required; all three journal prefixes retained, foreign suffixes rejected, old failed charges and 0.23357169027962 margin retained. Both 41 distinct calls and 1800 cumulative health seconds apply; each admission reserves exactly 20+40=60 seconds. Settled actual costs release headroom, so 30 full-cost calls is not a replacement for the 41-call ceiling. Unknown terminal durations fail; unresolved health blocks admission. Dual 224 and 221.08404692669838 GPUh caps and validation/formal reserves remain. Failed health vetoes further work; duplicate IDs and automatic recoveries rejected. Evidence: `qd_ed_n36r3_health.py:21-67; qd_ed_n36r3_admission.py:70-139; qd_ed_n36_accounting.py:21-53; qd_ed_final_runner.py:1314-1360,1492-1528,1605-1632`.

**Finite allocation — PASS.** 40*1840 + 1800 + 200 = 75600 seconds = 21 GPUh. Episode allocation 73600, separately bounded health 1800, unused 200; health cannot borrow unused seconds. Evidence: `qd_ed_n36_contract.py:25; qd_ed_n36_accounting.py:39-49; docs/n36r3-admission-implementation.md:71`.

**First C0 durable boundary and charge once — PASS by source and scoped retained fixture evidence.** Terminal journal append/state sync and artifact precede PAUSED_FOR_ROOT_G3; restart verifies the recorded terminal and returns pause without dispatch/second charge. Invalid/unsettled paths stop. Health also cannot bypass the first C0 boundary. There is no post-G3 override. Evidence: `qd_ed_n36_runner.py:76-83,150-178; qd_ed_n36_supervise.py:23-56; qd_ed_n36r3_health.py:25-38; tests/test_n36r3_admission.py:264-302`.

## Eight unresolved regressions

The following are source-evidenced pre-existing fixture problems, not newly introduced production defects. They remain unresolved; no baseline or full-suite rerun is claimed.

**F1 P2 — tests/test_n36_stop_guard.py:153.** The AST-extracted _run_in_process namespace omits persist_runtime_observation. Both retained receipts record NameError before the second validate_context call, explaining calls == [True] instead of [True, True]. The real module defines the helper. Test and worker are byte-identical to base; these are not introduced STOP bypasses. Bounded fix: Bind the real persist_runtime_observation helper into the isolated namespace, keeping output under tmp_path; retain both canonical STOP substitutions and assert the rejection reason is STOP. Rerun only these two contained cases. Do not weaken production observation or STOP checks.

**F2 P2 — tests/test_n36_audit_repair.py:133.** bootstrap_tree copies only bootstrap and source modules, while the unchanged bootstrap imports scripts.qd_ed_n36_generated. Four tests terminate with ModuleNotFoundError before their intended assertions. The dependency exists in the production tree and is unchanged from base. Bounded fix: Copy the required generated validator dependency into the temporary bootstrap tree and supply complete synthetic runtime bindings for tests that proceed to attest. Preserve source-only loading and all production checks; re-review containment before a targeted rerun.

**F3 P2 — tests/test_n36_audit_repair.py:236.** test_actual_runner_to_worker_entry_ignores_poisoned_dependencies invokes source.attest(root,frozen,runtime) without a binding; live_importlib_aliases requires a dict. The retained traceback reaches the unchanged alias guard after runner/worker --help succeeds. This demonstrates an incomplete synthetic attestation, not an introduced production loader defect. Bounded fix: Construct the required synthetic live process/interpreter/context alias binding and pass it to attest/receipt verification. Keep identity checks intact; no production evidence may be inferred from the fixture.

**F4 P3 — tests/test_n36r2_draft.py:36.** The test submits only cohort and expects ValueError matching N36R2 draft only. Base validate_plan already indexes schema first and raises KeyError. The new N36R3-only guard does not change the N36R2 branch. Both sources reject the incomplete plan; neither grants release. Bounded fix: Use a complete nonreleased N36R2 draft and assert rejection at its actual contract gate, or explicitly test malformed-input rejection without requiring the obsolete message. Do not restore a blanket ban on separately authorized N36R2 plans.

| Retained failing test | Finding |
|---|---|
| `test_stop_after_worker_entry_prevents_main_and_retains_receipt[0]` | F1 |
| `test_stop_after_worker_entry_prevents_main_and_retains_receipt[1]` | F1 |
| `test_new_identity_cannot_release_or_admit` | F4 |
| `test_stale_cache_repro_and_frozen_source_execution` | F2 |
| `test_unsafe_entry_rejects_and_sourceless_rejects` | F2 |
| `test_actual_runner_to_worker_entry_ignores_poisoned_dependencies` | F3 |
| `test_compiled_bytes_join_rejects_changed_source_and_loader` | F2 |
| `test_main_source_entry_preserves_script_semantics` | F2 |

The two retained worker receipts explicitly record `NameError: name persist_runtime_observation is not defined`; their SHA-256 values are `712f49107d63ee5ee62b06f4d9ff774a1fd7ace3b922723388858343fd821b2e` and `53731177c646741f6920806c025778c54ad75bfdcb67d56c0204819ded781070`. The real helper exists at worker line 203 and is called at line 244. Test and worker are identical to base. Bootstrap/source/generated modules and audit fixtures are also identical to base. Base release.validate_plan already indexes schema before checking the N36R2 protocol.

## STOP containment

**F5 — P1 historical incident; fixed at reviewed source.** The retained incident reports a recovery STOP parameter touching the real relocated session STOP because budget_fixture used the canonical STOP_PATHS without the isolation fixture. The reviewed fix redirects both STOP entries and stop_path before budget_fixture. Controller STOP construction also now uses a temporary path. The incident and its reported removal are retained evidence, not actions repeated or independently reconstructed by this reviewer. Keep the redirects. Require temporary-path review for every future selected test, ideally with a test-harness write boundary that refuses canonical owner/source paths. No broad-suite containment certification is issued. No actual STOP entry was created, removed or touched during this review. The incident removal is an earlier report’s statement, not independently reconstructed or repeated here.

New N36R3 setup uses tmp_path for source, owner, artifacts, refs and both STOP entries; real GPU/provider/process boundaries are substituted. Recovery now patches STOP_PATHS and stop_path before budget_fixture; controller constructs its temporary STOP explicitly. No blanket assertion that all repository tests are safe is made. Since no dynamic tests ran, none could write canonical paths.

## Preserved science and evidence limits

Protected-path diff is empty for core, configs, Main, worker/receipt consumer, source/bootstrap, runtime closure (`scripts/qd_ed_n34_source.py`, imported by bridge/worker), controller, native arithmetic/generic audit, supervisor and STOP. All listed protected paths were checked to exist. No required_after or Main/receipt audit weakening was found. These preservation checks establish neither scientific success nor real worker acceptance.

Retained logs: regression `8 failed, 180 passed` SHA-256 `96051bdadf70a7d80bbc449ef4b33ab610dd63fa3c715be41a22f61f94e0aa65`; scoped `176 passed` SHA-256 `4c3f2c597643f90953d383c336554f5b4f38dcd4cf7e13f683d20208affc1c4d`; scoped `28 passed` SHA-256 `4085fd4debc49112bce2b5cb9dca197f1546c53739800771d70f876c7f692d6b`. Synthetic substitutions are not production Main, readiness or science evidence.

## Actual commands and evidence

- `git status --short --untracked-files=no`: empty tracked status; prohibited untracked file not inspected
- `git rev-parse HEAD`: 5da91e13a32211ac51ff0bb81d76aaefa0cc583f
- `git diff --stat b86ac1291b08ba2b6bf33e7a6e19326016f4c40e 5da91e13a32211ac51ff0bb81d76aaefa0cc583f`: 13 files changed, 883 insertions, 34 deletions
- `git diff b86ac1291b08ba2b6bf33e7a6e19326016f4c40e 5da91e13a32211ac51ff0bb81d76aaefa0cc583f -- scripts docs tests/test_n36_controller.py tests/test_n36_recovery.py`: production/doc/containment diff reviewed; new admission test read separately
- `git diff --check b86ac1291b08ba2b6bf33e7a6e19326016f4c40e 5da91e13a32211ac51ff0bb81d76aaefa0cc583f`: exit 0
- `python -B - <<'PY' (read-only pathlib resolution and git-show base comparisons, inline script in review tool transcript)`: Both actual routes resolve to themselves; seven regression fixture/dependency paths byte-identical to base; base validate_plan printed; retained STOP receipts show missing-helper NameError
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 python -B - <<'PY' (stdlib-only hash/AST/allocation audit, inline script in review tool transcript)`: 26 bound references verified (the output label erroneously said 27 before printing actual count 26); 13 working files match exact commit, changed Python parses, direct parent equals base, protected diff empty, exact allocation 75600. No project modules imported or writes performed.
- `Local cat / nl -ba / sed -n / rg -n on authority, implementation report, named docs, regression log, incident record and specific source/functions cited in this report`: Read-only evidence inspection; no recursive historical reconstruction, no protected artifacts/credentials read

The JSON companion contains the full evidence fingerprint manifest, original retained-test commands, locations and per-failure classification. Inline static-check bodies are preserved in the review tool transcript.

## Still required before real continuation

- Root exact-source review/adoption remains a separate action; this report creates no adoption or runtime bindings.
- Refresh actual source/scientific-source/runtime closure/native/controller/all-manifest and independent review bindings for the accepted exact composition.
- Reconcile current private owner state and all journals, retaining 505 attempts, old 75.52725286641478 GPUh baseline, all subsequent legitimate charges, unknown telemetry, retained margin and protected reserves; create/adopt finite owning authority separately.
- Externally hashed root health review/release, fresh assigned idle GPU7 and official current-login Codex gpt-6-astra readiness, actual CUDA/EGL evidence and charged terminal are still required.
- Root episode review and detached release must bind the successful real health terminal; STOP/deadline/current budget/device/provider checks still apply.
- First actual C0 must run unchanged production Main and receipt consumer with parent PID/boot/start/context binding, immutable before/after observations, complete required_after, monotonic execution including Main, stable generated identities, native/generic/controller/CUDA audits and exact once-only terminal charge.
- Root must reconcile real first-C0 G3 evidence before any later cell; no post-G3 continuation implementation or scientific promotion is supplied. Original scientific success gates and no B_test tuning remain.
- Eight retained regression fixture failures remain unresolved; repair narrowly and review full temporary-path containment before rerunning them. No full-suite pass is claimed.

No synthetic check licenses production or goal completion.
