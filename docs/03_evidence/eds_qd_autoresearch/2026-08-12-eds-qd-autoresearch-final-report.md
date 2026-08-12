# EDS-QD Autoresearch Final Report

Date: 2026-08-12  
Branch: `exp/eds-qd-autoresearch-libero-swap-ood`  
Decision: `CONCLUDE_NO_ADOPTION_WITHIN_GLOBAL_BUDGET_TARGET_NOT_MET`

## Executive result

The autonomous EDS-QD search did **not** reach the required formal LIBERO-PRO
`libero_object_swap >=5/10` success rate. The strongest admissible formal result
remains the historical `2/10`; the final target gap is three. No new candidate
reached validation or formal because each was stopped by its preregistered
promotion gates. The current control remains the adoption choice.

This is a valid no-adoption conclusion, not an incomplete run. The search
covered the five evidence-backed EDS+QD core directions selected from historical
traces and task outcomes, preserved evaluation isolation, and stopped after two
consecutive versioned cycles produced no task-level gain and no new target-linked
hypothesis. Continuing would optimize QD mechanism proxies after repeated task
failure, contrary to the primary objective and no-progress rules.

## Target-linked trajectory

| Cycle / candidate | Frozen task evidence | Task delta | Decision |
| --- | --- | ---: | --- |
| Historical audited EDS-QD | best valid formal `2/10` | — | Baseline target gap 3 |
| H1 causal envelope | validation candidate `1/10` | no target pass | Reject before formal |
| H2 exact-degenerate fallback | mechanism control `1/3`, candidate `0/3` | `-1` | Reject before Dev |
| H4 global-quality anchor | mechanism `0/3 -> 1/3`; Dev-A `0/6 -> 0/6` | final `0` | Reject before validation |
| H5-v4 capacity-two top2 | offline 17 quality-retention violations | — | Reject before implementation |
| H5-v5 protected secondary lane | mechanism `0/2 -> 0/2` | `0` | Reject before Dev-A |

No formal outcome was used to tune a successor. Validation/formal splits stayed
sealed whenever upstream gates failed.

## What the experiments established

### 1. Partition resolution was a real issue but not the target bottleneck

The causal-envelope archive removed represented overflow and improved within-cell
endpoint resolution while preserving global reward best. It passed offline and
development gates, but the independent validation result was only `1/10`.
Geometric resolution alone was therefore insufficient for object-swap success.

### 2. Sparse allocation can omit the best reward lineage

Historical replay showed the prior global-best archive cell received no sparse
offspring in roughly two thirds of eligible transitions. A dedicated global-best
parent removed that omission without increasing the 176-evaluation/11-score-call
budget. It produced one task-9 gain in a three-task mechanism run, but the frozen
six-task Dev-A was `0/6 -> 0/6`. Frequent lineage rescue did not generalize to
task completion.

### 3. Endpoint-XY capacity one causes substantial behavioral aliasing

Across 4,224 historical candidates, 65.10% lay in collision cells. Reward-near
lineages in the same cell retained materially different approach directions and
trajectory shapes. A naive top-two archive exposed those alternatives but caused
17 quality-retention violations after causal rebin, so it was correctly rejected.

### 4. Protecting quality fixes eviction, not success alignment

The final candidate separated an exact capacity-one quality lane from a
non-evicting secondary lane. Offline replay, TDD and integrated CPU evidence
proved that authoritative quality/allocation/final selection remained unchanged
while secondary parents received 28.89% of sparse slots.

In the valid Run044 online recovery, the candidate produced 1,685 secondary
parents across 41 records. Secondary selection was positive in 407/410 QD
iterations, yet the candidate still scored `0/2`, identical to control. Three
task-5 iterations had zero secondary parents, failing the universal-activation
gate. More importantly for the primary objective, near-universal activation did
not generate any success. The remaining failure is reward/progress-to-task
alignment, not simply QD lineage availability.

## Final Run044 result

- Exact scientific IDs: 95–98; invalid IDs 91–94 remain aborted and excluded.
- Exact execution identities: `(task 5, seed 666847)` and
  `(task 7, seed 87603)` for both profiles.
- Control: `0/2`; candidate: `0/2`; gained/lost tasks: none/none.
- All four outcomes: `timeout without completion`.
- Candidate mechanism: 410 anchors, 1,685 secondary parents, 407/410 positive
  secondary iterations.
- Safety: no fallback, nonfinite, action-mask, qpos, collision/push/drop or
  wrong-object hard failure.
- Selection-latency ratio: `1.045684 <= 1.25`.
- Sole audit failures: three zero-secondary iterations required to be positive
  by the frozen gate.
- Immutable audit SHA-256:
  `57544a8226b00fbf8085a4944a11d4908709be754990fcbce416b241f21c1cc9`.

## Why autonomous iteration stops here

V4 and v5 are consecutive versioned cycles without task-level gain. Run044's
high secondary activation is new mechanism evidence, but it is negative for the
target: 99.27% iteration-level activation still produced `0/2`. A new candidate
that merely guarantees the last 0.73% would be an adjacent proxy repair without
evidence of closing the three-success formal gap. The frozen designs also forbid
capacity/lane/threshold sweeps, Stage/RBF coupling, final secondary execution,
or a sixth evidence-free candidate.

The base target-discipline rule therefore applies: conclude no adoption within
the authorized global budget rather than continue unbounded exploration. The
research can be reopened only through a new user-authorized design with genuinely
new task-linked evidence and fresh leakage-safe splits; it cannot reuse Run044
outcomes for tuning.

## Final accounting and integrity

- Effective online episode attempts: `70`.
- Global reservations: `98/144`.
- Cumulative GPU use: `6.9468320556/48` hours.
- Formal episodes in this autoresearch: `0`.
- Historical formal best / target gap: `2/10 / 3`.
- Run044 complete-tree credential scan: zero matches across 16,642 checked
  files in the final result pass.
- All tracked changes stayed on the owned worktree/branch; large artifacts stayed
  under the owned shared2 root.
- The protected untracked Stage-guidance design was not read, modified, staged
  or committed.
- No external GPU process was terminated or shared; GPU selection used fresh
  admission snapshots.

## Final recommendation

Do not adopt any experimental EDS-QD successor from this run. Retain
`p2_stage_on_abs_rbf_control` as the operational baseline. Preserve the causal
envelope, global-quality anchor and protected-lane implementations as negative
research evidence/default-off components, but do not enable them based on proxy
activity alone.
