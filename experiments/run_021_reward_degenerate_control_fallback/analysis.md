# Result — run_021 reward-degenerate QD control fallback implementation

Status: `PASS — OFFLINE IMPLEMENTATION ONLY`

Protocol commit: `7afebccaf02d4f0cbb4da2c930e31e4cb267f30e`

Implementation commit: `f010e8e4ff1f129e12499b1e0f8d284f505f7455`

## Change and target rationale

Algorithm iteration 2 adds one H2/QD-quality rule. When configured QD sees a non-empty, finite initial reward vector whose values are exactly equal, the current chunk does not build or use its reward-indifferent QD archive. It instead reuses the existing non-QD EDS parent/final-selection path at the same complete search budget. The rule is evaluated independently on every chunk and uses no epsilon, Stage/task/job label, evaluator outcome, future state, or additional model call.

This directly removes the run_020 failure mode in which a task-agnostic action fingerprint determined archive replacement and execution despite absent quality preference. It is still an offline mechanism candidate: no success-rate improvement is claimed before paired online evaluation.

## Frozen behavior contract verified

- Default `qd_degenerate_fallback_policy=none` retains the exact-zero legacy QD path.
- Candidate `control_v1` triggers only on exact equality; an absolute difference of `1e-12` does not trigger.
- Equal nonzero rewards trigger; nonfinite input fails closed.
- A fallback chunk does not construct QD archive state and cannot select `qd_archive` as its population source.
- A complete fallback chunk records `search_evaluation_count=176`, `score_call_count=11`, and `qd_evaluation_count=0`.
- A complete active-QD chunk records both search and QD evaluations as 176 with 11 score calls.
- On a fixed nondegenerate input, `none` and `control_v1` produce bit-identical selected actions and identical selected fingerprints, bounds checksums, cell-visit history, initial archive, and per-iteration archive snapshots.
- `qd_archive_mode=none` never invokes the fallback detector and remains unaffected.
- New metrics serialize through JSON without changing legacy missing-field readers.

## Verification

- Focused candidate tests: `6 passed, 361 deselected`.
- QD archive/metrics/QD runner/QD audit/autoresearch runner/calibration/full RDTSteer regression: `463 passed in 48.03s`.
- General EDS eval runner regression: `237 passed in 38.09s`.
- Combined non-overlapping regression count: `700 passed`.
- `python -m py_compile` for changed Python files: PASS.
- `git diff --check`: PASS.
- Implementation whitelist: exact four files from protocol.
- Credential scan of the implementation diff: 0 matching long key patterns.
- Protected untracked design: still untracked, not read, modified, staged, or committed.

Committed blob SHA-256:

- `core/rdt_policy_steer.py`: `890068dd804d38771608dbaafd5e38b70a14252f86d7e352b19fa477aca6159e`
- `core/eds_eval_metrics.py`: `cbe31284abf40e4d8ebc54c78b8c534f946e2e1df60f0eab8f898f77b834a450`
- `configs/config.yaml`: `c5844368c803f97540775365a1d5f3211997e6d77f6a0f0f581ffdf0cad63acc`
- `tests/test_rdt_steer.py`: `632e694a1cf67188b1afcc30f75f5a92490e767b85baca1d996971e7f65adc5e`

## Budget and target impact

Online episodes, GPU hours, attempt reservations, validation cells, and formal uses added by run_021: all zero. Historical formal best remains `2/10`, target gap remains 3, and the v1 validation result remains historical-only evidence.

## Decision

`KEEP_IMPLEMENTATION_PASS_AND_REQUIRE_PROTOCOL_FIRST_OFFLINE_MECHANISM_PREFLIGHT`.

This result authorizes only a separately committed, deterministic offline mechanism preflight that freezes exact-zero/nondegenerate outputs, action fingerprints, archive activity, and 176/11 accounting. GPU admission, API/model use, LIBERO episodes, Dev-A, Dev-B, validation, and formal remain unauthorized until their own promotion protocols and immutable manifests exist.
