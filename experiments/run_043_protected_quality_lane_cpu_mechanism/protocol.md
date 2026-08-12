# Protocol — Run043 protected-quality lane CPU mechanism preflight

Status: `LOCKED_BEFORE_HARNESS_IMPLEMENTATION_OR_ARTIFACT_CREATION`
Date: 2026-08-12
Hypothesis: `H5-v5`
Algorithm iteration: 5

## Authorization and order

- Run042 protocol commit: `d92311d`
- Run042 implementation commit: `e75516a36b10041b1a652bde8175302c9a7e896a`

This protocol authorizes only a deterministic CPU integrated mechanism harness,
its dedicated tests, two immutable JSON artifacts under the owned root, and
result documentation. It authorizes no core/config/runner modification,
CUDA/GPU admission, credential use, external API/model/VLM call, simulator or
LIBERO reset/episode, reservation, Dev, validation, or formal evaluation.

## Frozen scientific identity

The harness must fail closed unless these committed files match:

```text
core/qd_ed.py              2246193f87a27dc8568f434e3c9933aa4cf354e770417c62e463f7c565e1247e
core/rdt_policy_steer.py    5afaf8ed4fed0da04f22a7e7b9ec19c8c77b5647a1b57a8fa15963101c2c26f6
core/eds_eval_metrics.py    c621c579a411ac4d4f88a38e33f86a91b60e5d6e7c8b6b424886603ff0d89049
configs/config.yaml         be98e1127a93b30864c0f42832ba71adc11b115c34b1e2e0f748e2f3cb5bd55a
```

Candidate is exactly the frozen 16-particle, 10-iteration
`grid_archive + sparse_priority + causal_envelope_v1 + one quality anchor +
qd_secondary_lane_mode=protected_reward_v1 + fallback none` profile.
Comparator changes only `qd_secondary_lane_mode` to `none`. Both retain
quality-only occupancy, visits, bounds, global best, final tensors and execution.

## Frozen CPU fixtures

All cases use seed `43043`, `float64`, population `(16,64,128)`, the real
`RDTSteer._eds_guided_denoise_loop`, actual QD archive/allocator/metrics code,
real action-mask application, deterministic mocked score/renoise/rollout
plumbing, and target `(0,0,0)`. Every batch has four occupied descriptor cells
with four fingerprint-distinct same-cell candidates. Parent actions traverse the
integrated loop, while the next deterministic fixture batch does not depend on
parent identity.

Three complete cases are frozen:

1. `candidate_expanding`: protected mode; endpoint magnitude grows each
   iteration, causally expanding bounds and exercising quality+secondary rebin.
2. `comparator_expanding`: identical fixture/seed with secondary mode `none`.
3. `candidate_stable`: protected mode with fixed endpoint magnitude and no bound
   expansion, exercising update and rotation without rebin.

## PASS gates

All gates must pass:

1. exact frozen hashes, CPU-only execution, finite payload, zero credentials;
2. both candidate cases report protected mode, secondary occupancy and parent
   activation on every iteration, distinct secondary fingerprints, and
   quality+secondary source labels;
3. comparator reports mode none, zero secondary occupancy/parents/activations,
   empty secondary fingerprints, and no secondary source key;
4. every allocation is exactly `1 anchor + 15 sparse = 16`; candidate and
   comparator parent cell counts are identical for the expanding fixture;
5. `candidate_expanding` and comparator have identical authoritative quality
   bounds, visits, occupancy, elite rewards, global best, final selection and
   execution; secondary rebin telemetry has ten entries and zero violations;
6. stable case has no bounds expansion; expanding cases do expand; rebin visit
   sums are preserved in every case;
7. every case reports exactly 10 rollout batches of 16, `176/176/11`, and zero
   nonfinite, action-mask, qpos, accounting, elite-monotonicity,
   secondary-invariant and final-selection violations;
8. reset global Torch RNG, repeated per-case execution and two complete suites
   are byte-identical in every scientific field and checksum;
9. dedicated harness plus full applicable QD/RDT regression and Python
   compilation pass without changing frozen algorithm/config files;
10. canonical and replay artifacts are byte-identical, mode `0444`, secret-free,
    and written only to:

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/
  run_043_protected_quality_lane_cpu_mechanism/analysis/
    mechanism_preflight.v1.json
    mechanism_preflight.replay.json
```

## Implementation boundary

Only these new files may be added before the implementation commit:

- `scripts/eds_qd_protected_quality_lane_preflight.py`
- `tests/test_eds_qd_protected_quality_lane_preflight.py`

Large artifacts may be created only after that implementation commit. Existing
core/config/runner/audit/Stage/prompt files, protected untracked design,
historical artifacts and other worktrees remain read-only.

## Decision

- PASS: `KEEP_H5_V5_CPU_MECHANISM_PASS_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`.
- Scientific/integration FAIL:
  `CONCLUDE_H5_V5_MECHANISM_INVALID_NO_ONLINE`. At most one protocol-first repair
  is allowed for a demonstrated harness/schema defect; candidate semantics and
  gates cannot change.

Historical formal best remains `2/10`, target gap `3`, accounting 66 effective
online episodes, 90 reservations and `5.447063166666667` GPU-hours.
