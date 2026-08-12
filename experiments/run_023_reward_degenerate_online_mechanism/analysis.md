# Run023 analysis — online reward-degenerate mechanism

Decision: `CONCLUDE_H2_ONLINE_MECHANISM_FAIL_NO_DEV`

Run023 is a valid negative result. Both frozen profiles completed tasks 2, 3, and 9 at the exact seeds and execution bindings. The candidate never exercised its preregistered exact-degenerate fallback: all 74 candidate chunks remained active QD, so the required active/fallback dual-mode gate failed. Dev-A, Dev-B, validation, and formal are not authorized.

## Result

| Profile | Task 2 | Task 3 | Task 9 | Total |
| --- | --- | --- | --- | --- |
| contemporaneous EDS control | fail | fail | success | 1/3 |
| reward-degenerate fallback candidate | fail | fail | fail | 0/3 |

All five failures are `timeout without completion`; that label is not treated as a finer causal diagnosis. The candidate lost the control-success task 9. Although short-horizon success was diagnostic rather than a formal promotion gate, this regression points away from the `>=5/10` objective and supplies no reason to extend this candidate.

Candidate mode counts were:

| Task | Chunks | Fallback | Active QD | Minimum observed reward spread |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 21 | 0 | 21 | 0.0135803 |
| 3 | 50 | 0 | 50 | 0.0122940 |
| 9 | 3 | 0 | 3 | 0.0351257 |

Every candidate chunk used `176` search evaluations, `176` QD evaluations, and `11` score calls. Every control chunk used `176/0/11`. Candidate post-envelope overflow was zero for every recorded iteration; the median finite partition-resolution improvement was approximately 0.6400 / 0.5741 / 0.6576 on tasks 2/3/9. Those mechanism diagnostics do not override the absent fallback or task regression.

The most important discrepancy is between retrospective and prospective reward support. Run020 found 473 exact-zero historical QD chunks, but the frozen online matrix produced no exact-zero initial reward population: the minimum recorded reward spread was strictly positive on every candidate task. Therefore the threshold-free exact-equality switch is inactive under these prospective observations. This refutes the candidate's online applicability, not the offline identity proof.

## Validity, safety, and resources

- Manifest v3: mode `0444`, file SHA-256 `9429fe7420cfb613565fd83ee537e37fba5c3cd43093bc38f0bc1c7087d8793a`, payload `6160bf2d6f4fcf9c53a0613016dc0cc33efe2246870f38257a5550133a15399c`.
- Execution/recovery implementation: `6374e23a5073f0708ee4345935df024207740258`.
- Final audit: mode `0444`, SHA-256 `7f123ecdf3ffb7fbbb881ffebe197ddb2ae8e4b1237233dd2316f6f67e832c54`; its only hard failure is `candidate missing fallback record`.
- Control and candidate each have 3/3 episode metadata records, readable videos, exit code 0, strict perturbation and suite validity.
- Safety outcomes, nonfinite values, action-mask/qpos/accounting/monotonicity/selection violations, Stage/service fallbacks, and credential matches are all zero.
- Candidate/control selection-latency P95 is 2.98266/2.97889 seconds, ratio `1.001266`, below the `1.25x` limit.
- Run023 added 0.812334 device-wall GPU-hours; cumulative research usage is 3.747101/48 hours.
- IDs 55–60 remain append-only void pre-dispatch infrastructure records. Exact-cell recovery IDs 61–66 are the six dispatched scientific records. Global reservations are 66/143; 6/19 recovery slots are consumed.
- Final attempt-ledger SHA-256 is `3f445b32af0935540a56c3882a11987edb2dc56f7126d1593cd03afe5a55a63c`; final run-manifest SHA-256 is `5a1420038572c55c572b21dc35b1c4b59f8cc079e9c9a48fb6a0731b0d4fb748`.

## Interpretation and next boundary

The result rejects `reward_degenerate_control_fallback_v1` for online promotion. It does not establish that QD quality is adequate: candidate QD remained active everywhere and still lost task 9. It does establish that exact equality is not a reliable prospective routing predicate for this pipeline/matrix, so adjacent tolerance tuning would be an unregistered threshold search and is forbidden.

Historical formal best remains `2/10`; target gap remains 3 because formal was not run. The current v2 design has exhausted its single candidate. Per the frozen stop rules, the cycle must record no adoption and perform an outer-loop conclusion; any further candidate requires a versioned design, new holdout seeds, and explicit authorization.
