# `run_010_causal_envelope_candidate` Protocol

Status: `PROTOCOL_LOCKED`

Label: `CONFIRMATORY`

Scope: `QD-1`; one partition/archive-rebin change through offline preflight, LIBERO mechanism preflight, and Dev-A only

Locked UTC: `2026-08-10T16:08:00Z`

## Objective and target link

Implement and causally test the sole candidate authorized by `run_002`: sparse EDS-QD with a monotonic causal descriptor envelope and coherent archive rebinning. The current historical best is `2/10`; the formal target is `>=5/10`, gap three.

The candidate is intended to retain the historical QD successes 5/8 and recover control-success tasks 3 or 9 by preventing later offspring from being aliased into fixed edge cells. Because Dev-A uses new seeds, the binding task gate is paired: candidate success must exceed contemporaneous control by at least one of tasks `{3,5,8,9}` and may not lose any task that its paired control succeeds on. A success tie, proxy-only gain, or geometry-only gain is a reject for this online iteration.

This protocol ends at Dev-A. It cannot authorize Dev-B, validation, or formal evaluation; those require a result commit and a new protocol.

## Evidence packet

| Evidence | Frozen identity | Observation | Consequence |
| --- | --- | --- | --- |
| `run_002_partition_diagnostic/analysis.json` | SHA-256 `e21d2598981f8dbe538d35da77b33b31585a92b4e960c7056bef7d729e20d9a7` | 4,567 exact 4x4 replays; endpoint resolution +30.1%; mode ratio 0.9375; spread ratio 2.0087; global best 100% | authorizes this one QD-1 mechanism |
| Historical EDS-QD report | SHA-256 `cbaa9df290e40bc8cca4affedd7b17fb46b3d32832f6e68d63eb77ae1340e16c` | control `{3,8,9}`; sparse QD `{5,8}` | sparse QD is the candidate base; retain/recover objective |
| `run_000_baseline_replay` | SHA-256 `6ad1308363a512c9b2529a090682669bb096d5000159571d5798ddd296bad963` | raw overflow P95 0.875; compute scaling max 1/10 | no compute increase or neighboring sweep |
| `core/qd_ed.py` at protocol parent | blob `a9138b1f819d648f0d2b525a0a81e9142c13bd13` | fixed bounds, edge clamp, capacity-one archive | exact implementation boundary |
| `core/rdt_policy_steer.py` at protocol parent | blob `1354e26c1aa351518ef362c568e3fef5f1f9dd95` | archive-only parents and global reward-best execution | parent/quality/final selection remain frozen |

Conflicting evidence remains binding: scalar expand20 and other bounds/grid OFATs did not pass adoption; old Grid5 is invalid rather than positive evidence. No scalar expansion, grid size, descriptor, capacity, parent allocation, reward, continuity, or Stage parameter may be added to this run.

## Frozen algorithm change

Candidate label: `eds_quality_diversity_sparse_causal_envelope_v1`.

Reference label: `eds_quality_diversity_sparse_primary`.

The candidate is byte/config-identical to sparse primary except one new field:

```text
qd_bounds_update_policy = causal_envelope_v1
```

Sparse primary and all existing profiles use:

```text
qd_bounds_update_policy = fixed_initial
```

Candidate semantics per chunk:

1. Initial target-relative endpoint-XY descriptors, quantile bounds, initial archive insertion, 4x4 grid, capacity one, reward elitism, and sparse-priority parent allocation are unchanged.
2. At offspring iteration `i`, generate and score the 16 children exactly as baseline.
3. Before child insertion, expand each bound to the union of the previous bound and the finite component-wise envelope of the current 16 child descriptors. Bounds never shrink.
4. If bounds change, re-bin all incumbent archive elites. Cell collisions keep the existing reward-then-fingerprint winner.
5. Re-map each old cell's cumulative visit count using its incumbent descriptor and sum counts on collision. Total cumulative visits must be preserved; no visit reset or new allocation weight is allowed.
6. Assign and insert the current children under the expanded bounds; then continue the unchanged sparse-priority allocation.
7. Final execution remains the archive global reward-best action with the existing fingerprint/cell tie break.

The envelope uses descriptors only, not reward, future observation, success, privileged simulator state, or Stage output. Full chunks remain `16 + 10*16 = 176` evaluations and 11 score calls.

## Allowed files and change map

| EDS+QD step | State | Allowed change |
| --- | --- | --- |
| EDS initial proposal | Frozen | none |
| EDS rollout/mutation/budget | Frozen | none; population 16, iterations 10 |
| QD descriptor/partition | Changed | causal no-shrink bounds expansion after scored child batch |
| QD archive/replacement | Changed | deterministic incumbent rebin and visit-count remap |
| QD parent/allocation | Frozen semantics | sparse-priority reads coherently remapped existing visits; no weight/rule change |
| QD quality/elitism | Frozen | reward then fingerprint |
| QD final selection | Frozen | global reward best |
| QD cross-chunk state | Frozen | fresh archive per chunk |
| EDS+QD instrumentation | Changed | bounds/rebin/raw-overflow/resolution telemetry and isolated runner/audit |

Algorithm/instrumentation files may be limited to `core/qd_ed.py`, `core/rdt_policy_steer.py`, `core/eds_eval_metrics.py`, `configs/config.yaml`, a dedicated `scripts/eds_qd_autoresearch_runner.py` and audit helper, and targeted tests. The existing baseline runner may be imported read-only but its old matrix/root must not be mutated.

Checkpoint/backbone, perception/grounding, prompts, Stage recognizer/settings, environment/reset, action executor, evaluator, action post-processing, success definition, suite perturbations, 720-step limit, reward provider, and VLM call policy are frozen.

## Required telemetry

Add JSON-serializable fields without changing existing baseline values:

- `qd_bounds_update_policy`;
- initial and per-iteration active bounds/checksums;
- bounds expansion count and per-iteration changed flags;
- rebin collision count and cumulative-visit sum before/after;
- raw out-of-initial-bounds count/ratio per iteration;
- post-envelope unrepresented-overflow count/ratio per iteration;
- per-iteration fixed-initial vs active within-cell endpoint SSE and resolution improvement;
- unchanged evaluation/score/model/reward/VLM accounting, fallback, selected reward/fingerprint/cell, archive mode/spread, trajectory, latency, and safety metrics.

Observer-disabled and `fixed_initial` behavior must remain bitwise passive under existing tests.

## Stage A — implementation and offline preflight

Implementation must be test-driven and committed before any GPU dispatch. Required gates:

1. bounds expand to include the current batch, never shrink, fail closed on nonfinite input, and have permutation-stable checksums;
2. archive rebin is deterministic/permutation-equivariant, keeps reward/fingerprint winner on collision, preserves total cumulative visits, produces only valid cell IDs, and keeps global best;
3. fixed-initial config reproduces prior behavior and metrics; observer ON/OFF remains bitwise passive;
4. causal integration reports zero post-envelope overflow on synthetic outliers, positive raw overflow, 176 evaluations, 11 score calls, no fallback/accounting/source mismatch, and unchanged global best;
5. configuration rejects unknown policies; candidate differs from sparse reference only in `qd_bounds_update_policy`;
6. runner tests enforce owned root, pause sentinel, 50 GiB storage floor, exact phase matrices/seeds, 143-attempt cap, same-cell-only recovery, split leakage prevention, dynamic GPU 0–7 admission, credential redaction, and no formal command;
7. the frozen legacy suite passes:

```bash
pytest -q \
  tests/test_qd_ed_archive.py \
  tests/test_eds_quality_diversity_runner.py \
  tests/test_eds_quality_diversity_audit.py \
  tests/test_rdt_steer.py \
  tests/test_eds_eval_metrics.py \
  tests/test_eds_eval_runner.py \
  tests/test_main_rdt_startup.py \
  tests/test_env_adapters_imports.py \
  tests/test_eds_qd_autoresearch_runner.py
```

Offline preflight command after implementation:

```bash
python scripts/eds_qd_autoresearch_runner.py offline-preflight
```

It must emit code/config/checkpoint/input fingerprints, test evidence, deterministic synthetic mechanism metrics, call/RNG/accounting checks, and a machine-readable PASS under the owned artifact root. Any gate failure blocks all online work. A logic/scientific failure rejects the candidate; a schema-only failure may receive at most one protocol-first repair.

## Stage B — LIBERO mechanism preflight

Only after Stage A PASS and an immutable run manifest:

```bash
python scripts/eds_qd_autoresearch_runner.py freeze-manifest
python scripts/eds_qd_autoresearch_runner.py run-mechanism-preflight --gpus auto --timeout-seconds 28800
python scripts/eds_qd_autoresearch_runner.py audit-mechanism-preflight
```

Frozen six unique cells, each `max_chunks=2`; outcome is not used for candidate ranking:

| Profile | Task | Seed |
| --- | ---: | ---: |
| control | 3 | 512905 |
| control | 5 | 150741 |
| sparse primary reference | 3 | 512905 |
| sparse primary reference | 5 | 150741 |
| causal-envelope candidate | 3 | 512905 |
| causal-envelope candidate | 5 | 150741 |

All 6 must be valid with correct suite/checkpoint/code/config/seed, no qpos/collision/drop/wrong-object safety failure caused during the two-chunk plumbing check, no fallback/nonfinite/accounting/source error, expected model/reward/VLM calls, and candidate mechanism telemetry populated. Candidate post-envelope overflow must be `<=0.25`, raw overflow must remain disclosed, global-best fingerprint consistency must pass, and candidate selection-latency P95 must be `<=1.25x` the sparse reference on paired chunks.

Any policy outcome is not retried. Only audited OOM/Xid/render corruption/API transient/artifact corruption may use an exact same-cell recovery; code/config/task/seed/checkpoint fingerprint may not change.

If measured episode wall time projects the remaining frozen matrix above 48 GPU-hours, pause before Dev-A and record a budget amendment request; do not silently relax the cap.

## Stage C — Dev-A

Only after mechanism-preflight PASS:

```bash
python scripts/eds_qd_autoresearch_runner.py run-dev-a --gpus auto --timeout-seconds 28800
python scripts/eds_qd_autoresearch_runner.py audit-dev-a
```

Frozen eight unique full episodes:

| Profile | Tasks | Seeds |
| --- | --- | --- |
| contemporaneous control | `[3,5,8,9]` | `[512905,150741,463456,452903]` |
| causal-envelope candidate | `[3,5,8,9]` | `[512905,150741,463456,452903]` |

### Dev-A hard validity and safety

- 8/8 cells valid; all candidate and control tasks/seeds/config/code/checkpoint fingerprints exact;
- strict perturbations, Stage settings, executor, success definition, 720 steps, and calls unchanged;
- no qpos execution error; candidate collision/push/drop/wrong-object count may not exceed paired control;
- every complete candidate chunk has 176 evaluations and 11 score calls; no fallback, nonfinite, accounting, source, or final-selection mismatch;
- actual cumulative attempts `<=143` and GPU-hours `<=48`.

### Dev-A target gate

All are required:

1. candidate success count is at least paired control success count plus one;
2. candidate succeeds on every task its paired control succeeds on;
3. gained-minus-lost tasks is at least one;
4. the gain occurs on at least one of the predeclared retain/recover/explore tasks 3, 5, 8, or 9 (the whole Dev-A set).

There is deliberately no success-tie proxy promotion in this protocol. If target gates fail, immediately `REVERT` the active algorithm change after preserving the commit and artifacts; do not spend Dev-B episodes or try neighboring partition parameters.

### Dev-A mechanism/compute guardrails

- candidate per-episode median online resolution improvement is `>=0.20` in at least 3/4 tasks;
- post-envelope unrepresented-overflow P95 `<=0.25`, with raw initial-bound overflow reported separately;
- final occupied-mode ratio and archive endpoint spread are reported per task and must not show a nonfinite/collapse condition;
- global-best reward/fingerprint consistency is 100%; cumulative visit sums are conserved at every rebin;
- candidate QD-core/selection latency P95 is `<=1.25x` the paired sparse-reference mechanism-preflight reference after noting the split limitation;
- no model/reward/VLM/evaluation count increase over the frozen profile.

Mechanism gates cannot override a target-gate failure.

## Budget, admission, storage, and pause

- This run reserves 14 unique online cells: 6 mechanism preflight + 8 Dev-A.
- They consume attempt IDs from the global `0/143` ledger; only audited exact-cell infrastructure recovery can add attempts.
- GPU-hours add across devices against `0/48` at protocol lock.
- Before every dispatch: check `.autoresearch/PAUSE`, validate the owned root/symlink and at least 50 GiB free, run two GPU snapshots plus an immediate dispatch snapshot, and admit only GPU indices 0–7 with no external compute process, utilization `<=5%`, and required VRAM headroom. One worker per GPU, at most eight.
- Never terminate, pause, renice, or modify another process. GPU identity is recorded by index and UUID.
- Runtime credentials come only from environment and are never printed, stored in command/Hydra/manifest, or committed.
- Large artifacts live only under `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_010_causal_envelope_candidate` and the owned outputs subtree.

## Precommitted decisions

- Offline failure: `REJECT_OR_INVALID_BEFORE_ONLINE`, according to taxonomy; no GPU dispatch.
- Mechanism preflight validity/mechanism failure: `REJECT_OR_INVALID_BEFORE_DEV_A`; no Dev-A.
- Dev-A target or safety failure: `REVERT_CAUSAL_ENVELOPE`; preserve all evidence; no adjacent H1 candidate.
- Dev-A target + validity + safety + mechanism PASS: `KEEP_AND_AUTHORIZE_DEV_B_PROTOCOL` only.
- At every outcome, append task-level successes, gains/retentions/losses, failure reason, mechanism metrics, calls, GPU/attempt budget, artifacts/hashes, and next target-linked decision to the canonical iteration ledger before the result commit.
