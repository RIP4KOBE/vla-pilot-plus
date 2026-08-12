# Protocol — Run044 protected-quality lane online mechanism

Status: `LOCKED_BEFORE_RUNNER_IMPLEMENTATION_MANIFEST_HEALTH_ADMISSION_OR_RESERVATION`
Date: 2026-08-12
Hypothesis: `H5-v5`
Algorithm iteration: 5

## Parent evidence

- V5 design commit: `97c0418`
- Run042 algorithm implementation: `e75516a36b10041b1a652bde8175302c9a7e896a`
- Run043 result commit: `1e1fef41de31bf2742e6176f424b2725a2cf9236`
- Run043 immutable artifact SHA-256:
  `32a46d78aa467efdbe4564e0cdaccb90dadaae2e8f8dca18629a1de93ff15f3a`
- Run043 scientific payload SHA-256:
  `f147b905b68d28c8168642fba0b7470753d5daf9bb91535f8d112ac0498dc73c`

This stage spends exactly four paired online cells to determine whether the
protected secondary lane activates in the real policy without losing a
contemporaneous control success. Mechanism proxies cannot override the task
retention gate and do not count toward the final `>=5/10` target.

## Frozen matrix and profiles

All jobs use LIBERO-PRO `libero_object_swap`, strict perturbations, the frozen
checkpoint/Stage/cache/executor/evaluator, `max_episode_steps=720`, and
`max_chunks=16`.

| Task | Seed |
| ---: | ---: |
| 7 | 87603 |
| 5 | 666847 |

The Cartesian matrix is exactly two profiles by two paired cells:

1. `p2_stage_on_abs_rbf_control`: unchanged control with QD disabled.
2. `eds_qd_protected_quality_secondary_v1`: the frozen v3
   `grid_archive + sparse_priority + causal_envelope_v1 + one global-quality
   anchor + fallback none` profile plus exactly
   `qd_secondary_lane_mode=protected_reward_v1`.

No lane count, rotation, reward threshold, horizon, task, seed, profile, Stage,
RBF, guidance, selection rule, or outcome-dependent rerun may be added.

## Implementation and immutable manifest boundary

Before online work, only these new files may be implemented and committed:

- `scripts/eds_qd_autoresearch_v5_runner.py`
- `tests/test_eds_qd_autoresearch_v5_runner.py`

They may reuse committed runner/audit infrastructure for exact job binding,
runtime/cache/input/checkpoint fingerprints, global attempt accounting, GPU
admission, execution and Run044 audit. Existing core/config/runners/tests,
Stage/prompt/perception/environment/executor/evaluator, protected design and
historical artifacts may not change.

After runner tests pass, create one immutable mode-`0444` manifest only at:

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/
  run_044_protected_quality_lane_online_mechanism/manifests/mechanism_manifest.json
```

It must bind this protocol/runner, exact algorithm/config/dependency/profile/
matrix hashes, Run043 artifact, checkpoint, LIBERO inputs, runtime cache,
audited local DINO seed, GPU reference, code state, prior reservations `90`,
expected IDs `91–94`, caps `143` and `48 GPU-hours`, prior GPU-hours
`5.447063166666667`, recovery reserve `3`, and `formal_authorized=false`.
Credential material is forbidden.

## Transaction and resource order

Execution is fail-closed:

1. pause/worktree/write-boundary/storage/free-space and immutable manifest checks;
2. exact source/profile/checkpoint/LIBERO/cache/DINO/Run043 verification;
3. runtime-only credential presence and bounded real Stage/Poe health check,
   without logging value or reversible fingerprint;
4. fresh two-snapshot admission on GPU 0–7 with zero external compute process;
5. only then append exact IDs 91–94 and dispatch at most two workers, one per
   admitted GPU;
6. audit, strict credential/write-boundary scan, artifact freeze, task-level
   record and result commit.

No co-location, process termination, pre-health reservation, or interference is
allowed. A pre-reservation failure consumes zero IDs. A pre-episode
infrastructure failure may use only a protocol-first exact-cell recovery from the
three reserved slots; scientific/target failure is never retryable.

## Online hard gates

All gates must pass:

1. Both jobs are complete and valid at exact identity; each has 2/2 metadata,
   readable videos, strict suite and perturbation evidence.
2. Every control metric record has QD disabled/inactive, secondary mode none,
   176 search / 0 QD / 11 calls, finite/mask/qpos safety, and no QD fingerprint.
3. Every candidate record has QD enabled/active, protected secondary mode,
   fallback none/unused, anchor count one, exactly ten anchor activations,
   176/176/11 and zero accounting/monotonicity/secondary/final violations.
4. Every candidate record has ten sparse/total/secondary slot maps, parent counts
   and secondary fingerprint lists; each sparse map sums 15, total map 16,
   secondary count is positive and equals its map/fingerprint count, and source
   totals are 10 anchor plus 150 quality+secondary sparse parents with both
   sparse sources positive.
5. Across candidate records secondary activation is positive on both task cells;
   secondary occupancy is positive, final selected/global-best fingerprints
   match and final execution source remains the quality archive.
6. Candidate/control have zero Stage/service fallback, collision/push/drop/
   wrong-object, credential, artifact, execution and write-boundary hard
   failures; candidate cannot exceed control disallowed-safety outcomes.
7. Candidate selection-latency P95 is at most `1.25x` control; Run044 and
   cumulative GPU-hours are finite and cumulative use stays below 48.
8. Exactly four new reservations exist at IDs 91–94 with no duplicate, mutation
   or recovery; global reservations become 94/143.
9. Candidate success count is not below control and lost-control-success tasks
   are empty. Record per-task successes/failures, gained/retained/lost, delta and
   candidate diagnostic gap to five.
10. Every output is under the owned Run044 root; all other worktrees/shared2
    history and the protected untracked design remain untouched; manifest/audit/
    output/committed-worktree credential scans are zero.

## Decision

- PASS:
  `KEEP_H5_V5_ONLINE_MECHANISM_PASS_AND_AUTHORIZE_DEV_A_PROTOCOL_ONLY`.
- Any valid mechanism/safety/accounting/latency/artifact/retention FAIL:
  `CONCLUDE_H5_V5_ONLINE_MECHANISM_FAIL_NO_ADOPTION`; do not run Dev-A,
  validation, formal, or create a sixth candidate.
- Pre-episode infrastructure failure: preserve evidence and stop before
  reservation, or use only a protocol-first exact-cell recovery if IDs were
  already consumed.

Historical formal best remains `2/10`, target gap remains `3`; formal and all
later splits are unauthorized.
