# N22 conditional CPU implementation report

Implementation is complete on `codex/rdt-qd-ed-n22-hold-lift-20260930`, commit `960f90e8b097e7f39c9f2fc5a57da3ac9f617e7c` (base `23dba92`). The implementation worktree is clean. This report is CPU preparation under `protocol-cpu-v1.md`; it is not a Dev success result, GPU release, budget amendment, or promotion decision. N21 remains the coordinator's priority.

## Change and invariants

The new opt-in `close_hold_then_lift_v1` retains existing lift credit only if every deployed binary gripper command from the first eligible near-target close through the eighth action is positive. A release followed by reclosure still invalidates that credit; an earlier close/release outside the 4 cm eligibility radius does not. The original `close_then_lift_v1` path retains its exact computation and default contract value. The 4 cm radius, 5 cm cap, squared bonus, target index zero, raw provider dtype, direction-height descriptor, N7/N5 terminal selector, fixed canonical 176 candidates / 11 batches, and N21 selected-raw Stage binding and archive-spread reference are retained.

Source changes are limited to `core/qd_lift_quality.py`, its opt-in integration in `core/rdt_policy_steer.py`, `scripts/audit_decision_evidence.py`, closed profile expansion in `scripts/qd_ed_final_runner.py`, the exact inherited `configs/qd_ed_final/candidate_n22.json`, and tests. The candidate's parent SHA binds the N21 profile; its only scientific profile delta is `qd_quality_mode`.

The native auditor independently reconstructs command persistence with a scalar suffix check. It does not import the production bonus helper. Its new report field is `n22_hold_lift_quality_audit` / schema `n22-native-close-hold-then-lift-audit-v1`. Old mode identity checks, the old `n18_lift_quality_audit` field, and old error semantics remain intact. No existing budget, admission, GPU, execution supervisor, or protected-data rules were changed.

## Verification

All commands used `/home/hynx/miniconda3/envs/vla-pilot/bin/python`, with `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2`.

- `-m pytest -q tests/test_qd_hold_lift_quality.py tests/test_qd_lift_quality.py tests/test_decision_evidence_audit.py tests/test_qd_terminal_population.py tests/test_qd_ed_final_runner.py tests/test_qd_ed_n11_dev.py tests/test_qd_ed_n5_plan.py tests/test_qd_ed_n7_plan.py tests/test_qd_ed_n6_plan.py`: **140 passed**, `cpu-regressions-v1.log`.
- `-m pytest -q tests/test_rdt_steer.py -k 'n22_hold_condition'`: **6 passed**, `cpu-full-loop-v2.log`.
- `-m pytest -q tests/test_rdt_steer.py -k 'n21_positive_lift or n20_exact_profile or n4_terminal_consumer or n4_real_cpu_scoring or n6_height_descriptor or baseline_rollout or n2_unknown_provider or n2_canonical_uses_existing_projection'`: **16 passed**, `cpu-loop-regressions-v1.log`.
- Python compilation of modified production modules and the new unit file, plus `git diff --check`, passed.

There are **162 distinct passing tests** across those three pytest runs. The earlier 28-test focused run is a subset, not additional coverage. The six new full-loop cases were repeated once with `--basetemp=../cpu-native-evidence-v1` to preserve native bundles and their provider-source paths inside the variant; that repeat is not counted again. All six persisted traces were then independently re-audited, with the expected outcomes below. Tests assert that CUDA was not initialized.

The first full-loop test attempt (`cpu-full-loop-v1.log`) failed six cases because the test-side comparison used the single-selected-chunk decoder for a whole candidate batch. The fixture comparison was corrected to the deployed batch decoder, with no algorithm or audit relaxation. That failed log is preserved. Production and test changes in the committed source passed subsequent checks.

| Synthetic CPU case | Dtype | Native audit | Positive hold bonuses | Batches with ranking changes |
|---|---|---:|---:|---:|
| Held close with projected lift | FP32 | accepted | 93 / 176 | 10 / 11 |
| Held close with projected lift | BF16 | accepted | 50 / 176 | 6 / 11 |
| Lift projection restricted to release trajectories | FP32 | accepted | 0 / 176 | 0 / 11 |
| Lift projection restricted to release trajectories | BF16 | accepted | 0 / 176 | 0 / 11 |
| Deliberately use old unfiltered bonus under N22 identity | FP32 | rejected: `n22_native_bonus_mismatch` | not a valid trace | not a valid trace |
| Deliberately use old unfiltered bonus under N22 identity | BF16 | rejected: `n22_native_bonus_mismatch` | not a valid trace | not a valid trace |

For positive held-close cases, the selected effective reward differs from raw provider reward while Stage receives the exact raw value; archive spread matches its original reference. For release cases, old-mode bonuses are demonstrably positive on some native candidates, while every N22 bonus is exactly zero and effective quality equals raw quality. All four accepted cases retain 176 canonical candidates / 11 score batches; native audit also checks action, raw/effective association, terminal selection, and parent linkage. The negative controls patch only the production N22 bonus call to the old helper and require the independent audit to reject the resulting native bundles.

These are real CPU executions of the guided loop with a stub denoiser, local synthetic provider function, synthetic adapter projection, and invented collector lifecycle. They neither use LIBERO nor establish grasp validity or task success. They do not call a provider service, load a checkpoint, or consume GPU/experiment budget. No study worktree, private research state, attempt ledger, or research tree was modified.

## Can this affect QD/ED despite unchanged fixed-pool terminal choices?

Yes, through within-cell elite identity. `QDArchive._candidate_better` compares effective quality first and stable fingerprint on ties. Initial and subsequent `qd_archive.update` calls receive the modified quality. Removing release credit can therefore replace a cell's incumbent with another candidate; the next `archive_parent_allocation` then returns different native parent actions and raw/effective rewards to ED. That path does not require a global argmax or final fixed-pool terminal selector to change immediately.

The sparse-priority slot **counts and weights** depend on cumulative cell visits, not on effective reward. With identical saved pools and fixed cell assignments, the counts remain unchanged; N22 has no global quality anchor or secondary lane. The immediate mechanism to establish is a different parent fingerprint/action in an allocated slot. Subsequent online changes in descendants, occupancy, and slot counts are possible but cannot be inferred by forcing the original saved offspring pools.

The coordinator's `offline-fixed-pool-rank-v1.json` found zero direct terminal-choice changes in the inspected N20/N17 task0 pools. The subsequent `offline-archive-replay-v1.json` reportedly reproduced N20 original parent identities at 2560 / 2560 slots and found 8 changed parent slots in 1 / 16 decisions under hold filtering. Its hypothetical N17/N7 lift-to-hold comparison found 27 changed slots in 3 / 17 decisions; the successful task9 trace did not change. These results support a nonzero but sparse search-level effect. They are not an expected-success-rate estimate; only the first divergence per decision is locally interpretable, because later saved pools are forced rather than generated under changed parents. The coordinator owns these read-only replay artifacts; this executor did not modify them.

A precise mechanism witness needs SHA-verified, ordered `canonical_candidate_batch` and `scoring_inputs` tensors; raw provider and effective quality; deployed gripper suffix/hold condition; `qd_descriptor_assignment` cell IDs and frozen bounds; replayed incumbent fingerprint before/after each update; and the following `archive_parent_allocation` fingerprints, rewards, costs, raw rewards, cell IDs, slot counts and weights. `parent_allocation.source_population`, indices, and parent fingerprints bind those allocations to actual renoising inputs. Record the first affected insertion/replacement and first actual allocated parent difference. Current evidence explicitly labels original insertion occurrence identity as unavailable (`original_archive_occurrences=None`); equal fingerprints alone must not be overstated as unique lineage provenance.

No candidate-construction, continuous-close action suffix, decoder patch, simulator feedback, or alternative algorithm was implemented. Whether N22 merits a bounded matched-Dev run remains the coordinator's post-N21 decision under a separate prospective plan.

## Artifacts

- `cpu-implementation-results-v1.json`: source/profile/protocol hashes, log hashes, native audit paths and outcomes.
- `cpu-native-evidence-v1/test_n22_hold_condition_full_c0` through `c5`: four accepted and two deliberately rejected native CPU fixtures, including independent `audit-report.json` files.
- `cpu-regressions-v1.log`, `cpu-loop-regressions-v1.log`, `cpu-full-loop-v2.log`, and `cpu-native-evidence-run-v1.log`: passing checks.
- `cpu-unit-v1.log`: initial focused subset; `cpu-full-loop-v1.log`: preserved initial fixture failure.
