# Protocol — run_022 reward-degenerate fallback offline mechanism preflight

Status: `LOCKED BEFORE HARNESS IMPLEMENTATION OR ARTIFACT CREATION`

Parent protocol/result order:

- run_021 protocol commit: `7afebccaf02d4f0cbb4da2c930e31e4cb267f30e`
- run_021 implementation commit: `f010e8e4ff1f129e12499b1e0f8d284f505f7455`
- run_021 result commit: `7d131fdc49c108a787b715f95cd62ab46824d6d9`

Hypothesis: H2-v2. Algorithm iteration: `2`; this run changes no algorithm or config.

This protocol authorizes only a deterministic CPU-only integrated mechanism harness, its tests, two immutable JSON artifacts, and result documentation. It authorizes no GPU admission, runtime credential validation, external API/model/VLM call, LIBERO reset/episode, attempt reservation, Dev-A/B, validation, or formal evaluation.

## Frozen scientific identity

The harness must fail closed unless these committed blobs match:

```text
core/rdt_policy_steer.py  890068dd804d38771608dbaafd5e38b70a14252f86d7e352b19fa477aca6159e
core/eds_eval_metrics.py  cbe31284abf40e4d8ebc54c78b8c534f946e2e1df60f0eab8f898f77b834a450
configs/config.yaml        c5844368c803f97540775365a1d5f3211997e6d77f6a0f0f581ffdf0cad63acc
```

The candidate profile is exactly `sparse_priority + causal_envelope_v1 + qd_degenerate_fallback_policy=control_v1` on the frozen 16-particle, 10-iteration QD profile. The legacy comparator changes only the fallback policy to `none`; the EDS control comparator changes only `qd_archive_mode` to `none`.

## Frozen synthetic fixture

All cases use `float64`, population shape `(16,64,128)`, action mask semantics from the real integrated loop, endpoint values `[-0.06,-0.02,0.02,0.06]` distributed over a deterministic 4x4 layout in action dimensions 39/40, target `(0,0,0)`, and ten deterministic rollout batches. Each case resets Python/NumPy/Torch seeds to `22022`; no CUDA is allowed.

The harness must run these cases through `RDTSteer._eds_guided_denoise_loop`, not through a reimplementation of the fallback rule:

1. `candidate_exact_zero`: every scored reward is exactly `0.0`.
2. `control_exact_zero`: case 1 with QD disabled and otherwise identical config/input/RNG.
3. `legacy_qd_exact_zero`: case 1 with fallback policy `none`.
4. `candidate_equal_negative`: every reward is exactly `-0.25`.
5. `candidate_near_equal`: initial rewards are zero except one value exactly `1e-12`; rollout rewards remain deterministic and nondegenerate.
6. `legacy_qd_near_equal`: case 5 with fallback policy `none`.
7. `candidate_nondegenerate`: deterministic distinct rewards derived from the frozen action quality carrier.
8. `legacy_qd_nondegenerate`: case 7 with fallback policy `none`.

For every case record selected-action fingerprint, selected source/index/reward, complete final-action-set fingerprint, archive-active/fallback fields, search/QD evaluation counts, score calls, action-mask/nonfinite/accounting/selection mismatch counters, bounds checksums, cell-visit history, archive snapshots where applicable, and terminal Torch RNG checksum.

## PASS gates

All must pass:

1. Both exact-equal candidate cases trigger with the frozen reason/value, never construct active QD, use no QD selection fingerprint, and report `176` search evaluations / `11` score calls / `0` QD evaluations.
2. `candidate_exact_zero` and `control_exact_zero` have identical selected action, full final action set, selected source, final scores, and terminal Torch RNG state.
3. `legacy_qd_exact_zero` remains archive-active, does not trigger, reports `176/11/176`, and selects from `qd_archive`; its selected fingerprint is explicitly recorded rather than treated as candidate truth.
4. The `1e-12` case does not trigger. Candidate and legacy near-equal cases are identical in selected action, full archive snapshots, bounds checksums, cell visits, accounting, and terminal RNG.
5. Candidate and legacy nondegenerate cases satisfy the same full identity checks.
6. Every complete case has search evaluations `176`, score calls `11`, zero nonfinite/action-mask/accounting/elite-monotonicity/final-selection violations, and no hidden fallback state between cases.
7. Two independent full harness executions serialize byte-identical scientific payloads and produce the same selected/action-set fingerprints. Runtime timestamps, hostnames, environment values, and absolute paths are forbidden from the scientific payload.
8. Dedicated tests, run_021 focused tests, QD archive tests, and py_compile pass. No changed core/config blob is permitted.
9. Canonical and replay artifacts are written only under the owned root:

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/
  run_022_reward_degenerate_mechanism_preflight/analysis/
    mechanism_preflight.v1.json
    mechanism_preflight.replay.json
```

Both files must be mode `0444`, have identical bytes, contain zero credential matches, and include code/test/input/payload hashes plus every gate result.

## Implementation boundary

Only these new files may be added before the result commit:

- `scripts/eds_qd_degenerate_fallback_preflight.py`
- `tests/test_eds_qd_degenerate_fallback_preflight.py`

No existing core, config, runner, audit, Stage, prompt, protected design, or historical artifact may change. Large artifacts may only be written to the exact owned run root above.

## Decision

PASS yields `KEEP_OFFLINE_MECHANISM_PASS_AND_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`. A later protocol must freeze the six online mechanism cells, contemporaneous control/candidate profile binding, runner/audit semantics for configured-but-inactive QD chunks, immutable manifest, admission, safety, latency, credential, write-boundary, attempt, and budget gates before any reservation.

A scientific/integration gate failure yields `CONCLUDE_H2_MECHANISM_INVALID_NO_ONLINE`. At most one protocol-first repair is allowed only for a demonstrably schema/fixture-only defect; thresholds, case rewards, candidate rule, algorithm blobs, and scientific gates may not change.
