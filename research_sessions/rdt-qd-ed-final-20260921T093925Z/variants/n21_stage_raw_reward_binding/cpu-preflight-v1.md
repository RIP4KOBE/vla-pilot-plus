# N21 CPU preflight — ready for budget review, no GPU dispatch

N21 fixes one algorithm binding error: when terminal selection uses close-then-lift quality, Stage now consumes the same selected candidate's **raw provider reward**, while retaining the original archive spread for normalization. Search and selection still use the declared effective quality. The N20/N7 descriptor, terminal selector, model, frozen E2 Stage condition, task inputs and 176-candidate/11-batch compute are unchanged. This repair enables a faithful test of the existing hypothesis; it is not evidence that the lift objective improves LIBERO success.

## Evidence and tests

- Exact-profile full CPU guided-loop tests exercise real positive lift bonus, ranking changes, terminal selection, Stage binding and independent native evidence audit in FP32 and BF16. The synthetic action projection deliberately creates the positive-bonus case missing from N20's earlier CPU coverage; it does not simulate physical grasp or lift.
- Negative control restored only the N20 effective-cost Stage call: both positive-bonus tests failed as expected. Source was restored exactly afterward. See `negative-control-v1.json` and `.log`.
- Fixed-source loop regressions: 11 passed (`cpu-loop-regressions-v1.json` and `.log`), covering N21 positive bonus, N20 exact profile, terminal consumers, real CPU scoring and height descriptor paths.
- Earlier preparation checks passed 91 tests for quality/terminal/runner/N11/N21 and 33 tests for native evidence/N5/N6/N7. Following the final E2 admission integration, all 70 N21 and final-runner tests passed again. These overlapping reruns are not counted as additional distinct tests.
- Full draft plan validation passed against the exact proposed state held **only in process memory**. It checked all committed source, profiles, model and input fingerprints, seeds, frozen E2 runtime and GPU7 binding. Actual unapproved state rejected all three initial N21 rows. State and all three ledgers retained identical hashes before/after; see `cpu-plan-preflight-v2.json`.
- The initial plan preview failed because N21 was missing from two global E2 transport-condition allowlists. This was repaired before any dispatch; `plan.preview.v1.gpu7.json` and `cpu-plan-preflight-initial-rejection-v1.json` preserve that failed CPU check. Dispatch telemetry now also records the N21 marker on terminal/reconciliation paths.

## Source and plan

Isolated implementation commits: `e3b8765` and `e2746d4`; owning study integrations: `e003c30` and `23dba929ad012f714765755bb7eefc87a19fcd3b`.

Protocol SHA256: `2f737fd6ab9b45a88bd6f080ff6f4a3a6a49f3089bfa3ab732e10e6672e949cc`.
Review preview: `plan.preview.v2.gpu7.json`, SHA256 `cf08201025de1c9274657821906e21e2f1408fbf39541d4fdeaa19b9368d32b2`.
This is a review draft, **not an authorized execution release**. The live GPU reservation, mapping and reusable proof must pass again after budget approval, before freezing/releasing the execution plan.

## Requested execution

See [budget proposal](../../budget-extension-proposal-20260930-n21.md): cumulative 395→398 attempts; baseline30→31; development125→127; 100 GPU hours, validation180/formal40/recovery20 and validation/formal GPU-hour reserves32/12 unchanged. The complete new four-task C0/Q0/N21 matrix needs four baseline plus eight development slots. Current remaining capacities are three and six.

Run only on idle GPU7, one serial worker, at most12 attempts/6 GPU hours, no retry. Execute task0 C0/Q0/N21 first. Any invalid or rejected native audit stops the cohort; a valid N21 task0 failure rejects it and stops before the remaining nine cells. Only an audited task0 success permits tasks3/6/9. Full promotion requires N21≥3/4, task0 success, strictly better than both same-round controls, active lift/ranking effect and exact canonical compute. Validation and formal remain closed until their separate scientific gates pass.

Current unchanged accounting: **213/395 attempts, 28.842866326560607/100 GPU hours**, baseline27/30, development119/125, validation60/180, formal0/40, recovery7/20, running0. The original research target remains unmet. CPU preparation is complete; the next GPU action awaits the user's explicit new-budget audit, as they requested.
