# Protocol — Run031 Global-Quality Anchor Implementation

Status: `LOCKED_BEFORE_IMPLEMENTATION`
Date: 2026-08-12
Hypothesis: `H4-v3`
Algorithm iteration: 3
Candidate: `qd_global_quality_anchor_v1`

## Purpose and authorization

Run030 passed the preregistered allocation reconstruction. This run implements exactly the frozen compute-neutral QD repair: one dedicated parent from the current archive global-best cell and 15 parents from the unchanged sparse-priority allocator. It is an implementation gate, not an online success test.

This protocol authorizes changes only to:

- `core/qd_ed.py`
- `core/rdt_policy_steer.py`
- `core/eds_eval_metrics.py`
- `configs/config.yaml`
- `tests/test_qd_ed_archive.py`
- `tests/test_rdt_steer.py`

It authorizes no GPU, API, model, simulator, LIBERO episode, reservation, Dev, validation, or formal execution. It also authorizes no artifact outside the repository. A separate protocol and immutable artifact are required for the CPU integrated mechanism gate.

## Frozen inputs

- Parent result commit: `dc3d95541bcbc6e4b8b8e495fd6977bc356e774d`
- V3 design SHA-256: `0a2ea24763ef824010e462bbb76fa25d0e1b51d7217848f2e58b49153aabb742`
- Run030 result artifact SHA-256: `cede7bbb823621e5ac21a3b5eb10c7ceb6e4acdf967d63ab5fb61135f472d812`
- `core/qd_ed.py`: `1516bb75c3a5dc3894792d6b8f5daf7f777c48b7d58ea96496da47a986a970b9`
- `core/rdt_policy_steer.py`: `890068dd804d38771608dbaafd5e38b70a14252f86d7e352b19fa477aca6159e`
- `core/eds_eval_metrics.py`: `cbe31284abf40e4d8ebc54c78b8c534f946e2e1df60f0eab8f898f77b834a450`
- `configs/config.yaml`: `c5844368c803f97540775365a1d5f3211997e6d77f6a0f0f581ffdf0cad63acc`
- QD tests: `e5f2d5a9fd2b987a9efa87b0726b3adedfb81c443c4f3218e44df8741686c3f5`
- RDT tests: `632e694a1cf67188b1afcc30f75f5a92490e767b85baca1d996971e7f65adc5e`

## Frozen implementation contract

1. Add `qd_global_quality_anchor_count`, default `0`, and accept only integer values `0` or `1`. Value `1` is legal only with `qd_archive_mode=grid_archive`, `qd_parent_sampling=sparse_priority`, and the existing fixed grid-archive contract. Value `0` preserves the existing path.
2. Extend `allocate_parent_slots` with an optional anchor count. At `0`, execute the prior 16-slot allocation unchanged. At `1`, call the existing allocator mathematics with residual population 15 and the identical local seed material, then prepend exactly one parent selected by `QDArchive.select_global_best()` using the existing `reward desc, fingerprint asc, cell asc` ordering.
3. Sparse allocation may independently select the same cell. Total slot counts are the sum of the dedicated and sparse counts. All 16 returned parents are normal offspring and enter the existing renoise/rollout path; no action bypasses evaluation.
4. Additive allocation telemetry must expose the dedicated cell/fingerprint/count and sparse-versus-total slot maps. RDT metrics must expose configured count, per-iteration activation, cell, fingerprint, sparse count for that cell, rescue (`sparse count == 0`), sparse slot map, total slot map, and aggregate activation/rescue counts.
5. Parent-source telemetry distinguishes one `qd_global_quality_anchor_offspring` from 15 `qd_archive_offspring` entries. Existing generic EDS anchor telemetry remains zero and is not repurposed.
6. Archive update/rebin/replacement, causal-envelope bounds, masks/qpos handling, checkpoint/Stage/prompt/executor/evaluator, reward calls, and final archive-global-reward selection remain unchanged. `qd_degenerate_fallback_policy` remains `none` for the candidate.
7. The candidate remains exactly `16 initial + 10 * 16 = 176` search/QD evaluations and 11 score calls per complete chunk. No second anchor count, threshold, fallback, reserve ratio, selection heuristic, or parameter sweep is permitted.

## TDD and hard gates

Implementation may begin only after this protocol commit. Failing tests must be written before or with the implementation and must cover:

1. default and explicit anchor `0` preserve all pre-existing allocation tensors, ordering, counts, weights, fingerprints, local-RNG behavior, and existing serialized scientific fields on fixed inputs; new telemetry is zero/empty;
2. anchor `1` selects the deterministic archive global best, including reward/fingerprint/cell tie order;
3. every candidate iteration returns exactly `1 dedicated + 15 sparse = 16`, and the sparse result exactly equals a standalone existing allocation at population 15 with the same seed tuple;
4. a best cell omitted by sparse allocation is marked rescued and receives one total slot; a best cell selected by sparse allocation keeps both sources without deduplication;
5. invalid type/range/mode/sampling combinations fail closed, without silent coercion of booleans;
6. Torch global RNG is unchanged and repeated calls are tensor/telemetry identical;
7. integrated mocked RDT execution preserves finite values, masks/qpos/archive accounting and monotonicity, runs all 16 parents through denoise/rollout, reports complete candidate telemetry and `176/176/11`, and keeps final global-best selection unchanged;
8. all existing dedicated QD/RDT regression tests pass.

## Decision rule

- `PASS`: all eight hard gates pass, only whitelisted files changed, and implementation is committed separately. Authorize only a new CPU integrated mechanism protocol.
- `FAIL`: any scientific/semantic gate fails after bounded infrastructure-only fixes. Revert the uncommitted implementation, record `CONCLUDE_H4_V3_IMPLEMENTATION_FAIL`, and consume zero online episodes.

Target accounting remains historical formal best `2/10`, target gap `3`, 48 effective online episodes, 66 reservations, and `3.7471009444444445` GPU-hours.
