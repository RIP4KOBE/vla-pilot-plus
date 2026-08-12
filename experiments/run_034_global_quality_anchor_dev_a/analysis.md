# Run 034 analysis — global-quality-anchor Dev-A transfer

Date: 2026-08-12
Decision: `CONCLUDE_H4_V3_DEV_A_FAIL_NO_ADOPTION`

## Outcome first

Run 034 is a valid negative result. On the frozen paired LIBERO-PRO `libero_object_swap` Dev-A tasks `[0,1,2,4,6,7]`, both the contemporaneous EDS control and `eds_qd_global_quality_anchor_v1` scored `0/6`. The candidate therefore failed both preregistered task gates: it did not reach `>=3/6` and did not improve over control by at least one success. It gained, retained, and lost no success task because neither arm completed any task.

The global-quality anchor remained active and passed every mechanism, compute, validity, safety, latency, artifact, attempt-accounting and credential gate. That cannot override a target failure. The Run033 task-9 gain did not transfer to six frozen unseen task/seed cells, so v3 ends without validation or formal evaluation, without a fourth candidate, and without Run034-driven parameter tuning. Historical formal best remains `2/10`; the required `>=5/10` target remains unmet with gap 3.

## Task-level results and failures

| Task | Control | Candidate | Delta | Audited failure class |
|---|---:|---:|---:|---|
| 0 | fail | fail | 0 | both `timeout without completion` |
| 1 | fail | fail | 0 | both `timeout without completion` |
| 2 | fail | fail | 0 | both `timeout without completion` |
| 4 | fail | fail | 0 | both `timeout without completion` |
| 6 | fail | fail | 0 | both `timeout without completion` |
| 7 | fail | fail | 0 | both `timeout without completion` |

Aggregate: control `0/6`; candidate `0/6`; delta `0`; gained `[]`; retained `[]`; lost `[]`. All twelve cells were valid, exit-code-zero runs with exact frozen tasks/seeds. The only supported automatic failure label is timeout without completion; no finer behavioral cause is asserted.

## Mechanism attribution

The candidate emitted 106 valid chunk records and kept the frozen sparse-priority + causal-envelope + one-global-quality-anchor mechanism active in every record. It logged 1,060 anchor activations and 425 real omissions rescued (`40.09%`):

| Task | Records | Activations | Rescues |
|---|---:|---:|---:|
| 0 | 3 | 30 | 16 |
| 1 | 18 | 180 | 113 |
| 2 | 16 | 160 | 74 |
| 4 | 58 | 580 | 175 |
| 6 | 6 | 60 | 20 |
| 7 | 5 | 50 | 27 |

Every candidate record satisfied the frozen 10 activations, exact `1+15` parent allocation, source/fingerprint/final-selection checks, and `176 search / 176 QD / 11 score calls` accounting. The control produced 124 valid QD-off records. The result separates mechanism activation from task value: 425 rescued lineages across all six failed tasks did not create one completion. Together with Run033, anchor rescue is a real allocation repair but is not a transferable success mechanism under this candidate stack.

## Validity, safety, latency and accounting

- Both jobs exited 0, produced 6/6 metadata records and videos, verified the exact suite and strict perturbations, and were marked valid.
- Candidate/control selection-latency P95 was `3.060999 / 2.907224 s`; ratio `1.052894 <= 1.25`.
- Nonfinite values, action-mask violations, execution qpos errors, QD fallbacks and disallowed safety outcomes were all zero.
- Attempt IDs 79–90 were reserved and dispatched exactly once after health and two-snapshot admission on GPUs 2/4; the attempt gate passed with 12 new reservations and 90 total.
- Run034 scientific device wall was `1.2639597222222223 h`; cumulative usage is `5.447063166666667 / 48 h`.
- Effective online episodes rise from 54 to 66; global reservations are `90/143`; recovery use remains `6/19`, leaving 13; formal episodes remain zero.
- The immutable audit scanned 253 run-root files for credential material and passed. A separate exact scan of the complete Run034 tree and tracked worktree found zero copies of the approved credential. The sole generic tracked match remains a synthetic test fixture.

## Immutable evidence

- Dev-A manifest: mode 0444, SHA-256 `206911d750000f41aeed6e1739fb315b35a21f8f5b1dd78327eca5b32628601f`, payload `94d4a6867cef68fcefb4facda93c8f0e6a376cb97952ba194836b011d1052265`.
- Final audit: mode 0444, SHA-256 `2e590656dd60a18a17bf45ff7a2e1e9209daaaa34980a5d686b9d6f8879a0e68`; hard failures are only `candidate Dev-A success count is below 3/6` and `candidate Dev-A improvement is below +1`.
- Attempt ledger SHA-256: `db07734c1869b10ec29ed735f977be00a7491477871566570a207a060f2224da`.
- GPU admission SHA-256: `4f89f3933ffe26448759c235ce26e6cef103db3ecbcb02540d08ec9506f9359f`.
- Run manifest SHA-256: `9e39ee02bc23b7fa437db0c93ee30cdd586a971fdd66916f0134531c84953342`.
- Control/candidate artifact inventories contain 940/1,084 files and have aggregate SHA-256 `32c8daa954842a2b4b79eb35f8999eff43334b526d6e8bb297b42f09a2bc75e2` / `97666bb52110e5d2348434e29d66860434d3f3df6f91d8e94f8b0662244fecbb`.

## Stop decision

The frozen Run034 protocol states that a valid Dev-A failure ends v3. This result is valid, target-negative, and leaves no ambiguity that would justify exact-cell recovery. Validation and formal evaluation are not authorized. No anchor-count, sparse-ratio, threshold, seed, task or adjacent EDS-QD sweep may be derived from these revealed outcomes inside v3. The next action is an outer-loop conclusion protocol and final report only; it authorizes no additional algorithm or online execution.
