# `run_010_causal_envelope_candidate` Full Validation Protocol v11

Date: 2026-08-11 UTC

Scope: unchanged `QD-1` causal-envelope candidate versus contemporaneous control on the preregistered ten-task validation split. Parent evidence: Dev-A PASS `9c6d3ecee60d50c7e574b2a795c864483c85c812c0883a96ec81aa5d5d889fa9`; Dev-B PASS `7a73b3ae67d3980147bb48d14198b4de9cbabb14262c82effce656b3f91ff64f`.

This protocol authorizes validation runner/manifest/audit plumbing and one 20-cell validation execution. It does not authorize any algorithm/config/threshold change, second candidate, validation-result tuning, or formal evaluation.

## Goal-linked prediction

Dev-A gained task 9 (`1/4 vs 0/4`); independent Dev-B gained tasks 5/8 (`2/4 vs 0/4`); pooled gains are three with zero losses. The candidate therefore predicts at least 5/10 validation successes while not underperforming paired control. This is a binding target gate, not an exploratory expectation.

If validation candidate is below 5/10, below control, or invalid/unsafe, formal is not run. The revealed validation set cannot be reused after modifying the candidate.

## Frozen matrix and candidate

Tasks: `[0,1,2,3,4,5,6,7,8,9]`.

Validation seeds: `[41678,829779,856474,666150,876784,652882,288157,522484,262295,200894]`.

Profiles: contemporaneous control and unchanged `eds_quality_diversity_sparse_causal_envelope_v1`, one full 720-step episode per task/seed, 20 unique cells total.

Algorithm/config SHA-256 must remain:

- `core/qd_ed.py` `1516bb75c3a5dc3894792d6b8f5daf7f777c48b7d58ea96496da47a986a970b9`;
- `core/rdt_policy_steer.py` `b8806d7a28e42e6e8a9d2959b5b1d7e5b7c9b304526d4022146c3ba23c8c1ff2`;
- `core/eds_eval_metrics.py` `d8fb4d04271aa801089a1202af8baf658dc270b751224bc28b4816c9a6a83429`;
- `configs/config.yaml` `b20791a2792a5f7c6b3b61a2af02055462aa447059802aceb1293a7f77ecdaf8`.

## Protocol-first implementation and manifest

Only the dedicated runner/tests may change. TDD must cover exact validation matrix, real execution-context/manifest binding, validation manifest prerequisites, `>=5/10` plus not-below-control target gate, safety/mechanism/accounting/budget audit, and continued absence of formal CLI.

After dedicated and frozen nine-file tests pass and the implementation is committed, freeze one immutable `manifests/validation_manifest.json` binding:

- implementation commit/code-state and unchanged algorithm hashes;
- original/mechanism/Dev-A/Dev-B evidence hashes and Dev-B manifest v2;
- checkpoint, 20 LIBERO inputs, runtime cache, exact matrix;
- attempt cap 143, GPU-hour cap 48, GPU 0–7, `formal_authorized=false`.

No validation dispatch before the versioned manifest is mode 0444 and self-validating.

## Execution

```bash
python scripts/eds_qd_autoresearch_runner.py run-validation --gpus auto --timeout-seconds 28800
python scripts/eds_qd_autoresearch_runner.py audit-validation
```

Fresh two-snapshot plus immediate GPU admission, one worker per eligible GPU. Runtime credential is ephemeral and never persisted. Any initialized validation outcome is not retried. The remaining three recovery slots cannot cover the 20-cell matrix; there is no full-matrix recovery.

## Hard gates

All must pass:

- 20/20 records valid at exact suite/task/seed/checkpoint/config/code/manifest bindings;
- candidate success `>=5/10` and `>=` contemporaneous control;
- gained-minus-lost `>=0` and no safety-category regression;
- no qpos/nonfinite/action-mask/fallback/accounting/global-best/visit error;
- candidate resolution median `>=0.20` on at least 7/10 tasks, post-envelope overflow P95 `<=0.25`, raw overflow disclosed, archive mode/spread noncollapsed;
- candidate selection latency `<=1.25x` sparse mechanism reference and no call/evaluation increase;
- effective/reserved attempts within 143; all incident + phase GPU-hours within 48; artifact/strict credential audit PASS.

PASS: freeze this single candidate as validation winner and authorize only a new formal protocol/decision manifest. FAIL: `CONCLUDE_VALIDATION_NO_FORMAL`; preserve all evidence, do not tune on validation outcomes, do not run formal, and trigger outer-loop/conclusion according to the frozen design.
