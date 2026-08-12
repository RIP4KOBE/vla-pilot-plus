# Protocol — Run033 Global-Quality Anchor Online Mechanism

Status: `LOCKED_BEFORE_RUNNER_IMPLEMENTATION_MANIFEST_HEALTH_ADMISSION_OR_RESERVATION`
Date: 2026-08-12
Hypothesis: `H4-v3`
Algorithm iteration: 3

## Parent evidence

- V3 design commit: `f30e47c`
- Run031 algorithm implementation: `f453e645828d8076d72eee70c84669b385573b70`
- Run032 result commit: `1a29142`
- Run032 immutable artifact SHA-256: `31dd437c377c41af369336f6161f194012143dbcf847a2ae150ac82fdf3de24b`

This stage spends exactly six short online scientific cells to verify real-policy activation, rescue, 1+15 allocation, accounting, safety, latency, artifact, and task-retention behavior. Short-horizon success is diagnostic and cannot positively promote by itself, but losing a contemporaneous control-success task is an immediate frozen FAIL.

## Frozen matrix and profiles

All jobs use LIBERO-PRO `libero_object_swap`, strict perturbations, frozen checkpoint/Stage/cache/executor/evaluator, `max_episode_steps=720`, and `max_chunks=16`.

| Task | Seed |
| ---: | ---: |
| 3 | 955865 |
| 8 | 522754 |
| 9 | 845886 |

The exact Cartesian matrix contains two profiles and three paired task/seed cells each:

1. `p2_stage_on_abs_rbf_control`: unchanged control with `qd_archive_mode=none`.
2. `eds_qd_global_quality_anchor_v1`: `grid_archive + sparse_priority + causal_envelope_v1 + qd_global_quality_anchor_count=1 + qd_degenerate_fallback_policy=none` and otherwise the frozen EDS-QD profile.

No fallback, second anchor, threshold, horizon, task, seed, profile, Stage rule, selection heuristic, or result-dependent rerun may be added.

## Implementation and immutable manifest boundary

Before online work, only these new files may be implemented and committed:

- `scripts/eds_qd_autoresearch_v3_runner.py`
- `tests/test_eds_qd_autoresearch_v3_runner.py`

They may wrap/reuse committed runner infrastructure for exact job binding, commands, runtime/cache/input/checkpoint fingerprints, fresh global attempt accounting, GPU admission, execution, and Run033-specific audit. Existing core/config/v1/v2 runners/audits, Stage/prompt/perception/environment/executor/evaluator, protected design, and historical artifacts may not change.

After runner tests pass, create one immutable `0444` manifest only at:

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/
  run_033_global_quality_anchor_online_mechanism/manifests/mechanism_manifest.json
```

It must bind protocol and runner commits; exact source/config/profile/matrix hashes; Run032 artifact; checkpoint, LIBERO input, runtime cache, GPU reference and code-state hashes; prior global reservations 66; expected IDs 67–72; caps 143 reservations / 48 GPU-hours; prior GPU-hours `3.7471009444444445`; recovery reserve 19; `formal_authorized=false`; and zero credential material. Manifest creation does not authorize Dev-A.

## Transaction and resource order

Execution is fail-closed:

1. pause, worktree/write-boundary, storage and free-space checks;
2. immutable manifest/source/profile/checkpoint/LIBERO/cache/Run032 verification;
3. runtime credential presence plus a bounded real Stage/Poe health check, without logging value or reversible fingerprint;
4. two-snapshot admission across GPU 0–7 with zero external compute process, followed by immediate dispatch snapshot;
5. only then append fresh global IDs 67–72 and dispatch at most two workers, one per admitted GPU;
6. audit, strict credential/write-boundary scan, artifact freeze, task-level result record, and result commit.

No co-location, process termination, reservation before health/admission, or external-process interference is allowed. Pre-reservation failure consumes zero IDs. Infrastructure recovery requires a protocol-first exact-cell amendment and draws only from the 19 recovery slots; scientific/target failure is never retryable.

## Online hard gates

All must pass:

1. Both jobs are complete and valid at the exact manifest/execution/profile/task/seed/horizon/checkpoint/input/cache/code identity; 3/3 metadata and readable videos exist per job.
2. Every control metric record has QD disabled/inactive, fallback unused, 176 search evaluations, 11 score calls, zero QD evaluations, finite/mask/qpos safety, and no QD fingerprint.
3. Every candidate record has QD enabled/active, fallback policy `none` and unused, configured anchor count one, exactly ten activations, 176 search / 176 QD / 11 calls, and zero finite/mask/qpos/archive accounting/monotonicity/final-selection violations.
4. Every candidate record contains ten cells/fingerprints/rescue flags, ten sparse and total slot maps, each sparse map sums to 15 and total map to 16, each recorded anchor cell has `total = sparse + 1`, and source totals are exactly 10 dedicated plus 150 sparse QD offspring.
5. Across candidate records at least one real rescue occurs (`sparse best-cell count=0`, total one). Activation/rescue counts and rates are recorded per task; there is no threshold tuning if rescue is absent.
6. Candidate and control have zero Stage/service fallback, collision/push/drop/wrong-object, credential, artifact, execution, and write-boundary hard failures; candidate cannot exceed control on disallowed safety outcomes.
7. Candidate selection-latency P95 is at most `1.25x` contemporaneous control P95; Run033 and cumulative GPU-hours are finite and cumulative use stays below 48.
8. Exactly six new scientific reservations exist at IDs 67–72 with no duplicate/mutation/recovery; global reservations become 72/143.
9. Candidate lost-control-success task set is empty. Record control/candidate task successes, gained/lost/retained sets, delta, candidate success count, and current gap to 5/10. Success itself is diagnostic at this layer.
10. Every output is inside owned Run033 root; all other worktrees/shared2 history and the protected untracked design remain untouched; manifest/audit/output credential scans return zero.

## Decision

- PASS: `KEEP_H4_V3_ONLINE_MECHANISM_PASS_AND_AUTHORIZE_DEV_A_PROTOCOL_ONLY`.
- Any valid mechanism/safety/accounting/latency/artifact/retention FAIL: `CONCLUDE_H4_V3_ONLINE_MECHANISM_FAIL_NO_ADOPTION`; do not run Dev-A or explore another candidate.
- Pre-episode infrastructure failure: preserve evidence and stop before reservation, or use only an explicit protocol-first exact-cell recovery amendment if reservations were already consumed.

Historical formal best remains `2/10`, target gap remains `3`. Formal and all later splits remain unauthorized.
