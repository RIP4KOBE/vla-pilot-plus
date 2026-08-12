# Protocol — Run040 within-cell aliasing reconstruction

Status: `LOCKED BEFORE ANALYZER IMPLEMENTATION OR AGGREGATE RESULT`

Parent design: `docs/01_specs/2026-08-12-eds-qd-autoresearch-v4-within-cell-plurality-design.md` at commit `a1b290510966c7c14edd88489a7b8cc9cd30b565`, hypothesis `H5-v4`.

This protocol authorizes one read-only, zero-GPU, zero-API, zero-model, zero-LIBERO reconstruction plus analyzer tests. It does not authorize core/config changes, online dispatch, reservations, Dev, validation, or formal evaluation.

## Frozen inputs and exclusions

`input-manifest.json` binds exactly 24 active-QD trace files, 135,053,624 bytes and 264 shadow candidate streams from owned valid Run023/Run033/Run034 candidate outputs. Every size and SHA-256 must match before parsing. No recursive discovery is allowed after protocol commit.

The analyzer additionally binds:

- `core/qd_ed.py` SHA-256 `4a43cc2db1f1f87eaabf2146058347f119f6059beb4bdf2e67e36f9b6680b653`;
- `core/rdt_policy_steer.py` SHA-256 `bdc523f602453c402aa290ed40e495952578a5e028e0c9374365161255e7cd41`;
- v4 design SHA-256 `c33f9810661f7c56f275f1b5f9082a487f4f5c48e106c1de5bf3227808f2498c`.

Control traces, stale/incident trees, video/success labels, episode outcomes, future observations, evaluator state, formal results and the protected untracked Stage-guidance design are excluded. Torch files load on CPU only.

## Eligible candidate streams

Each trace must declare active grid QD, `qd_cell_capacity=1`, descriptor `target_relative_endpoint_xy`, 4x4 grid, causal-envelope bounds, and exactly 11 shadow streams for `iter_idx=-1,0..9`. The `-1` stream aligns with trace stage `initial`; each `0..9` stream aligns with the unique `full_process_after_rollout` stage of the same iteration. Candidate count, reward count, descriptor count, fingerprint count and trajectory count must all be 16.

For `iter=-1`, cell assignment uses `qd_bounds_xy_m`; for `0..9`, it uses the same-index `qd_bounds_xy_m_by_iter`. Cell IDs are reproduced using production 4x4 floor-and-clamp semantics. Trace fingerprints must match canonical action fingerprints in the aligned stage. All tensors/rewards/descriptors/bounds must be finite.

Normalized trajectory features reproduce the existing Direction-RBF diagnostic arithmetic in FP32 with path epsilon `1e-6`: endpoint direction is `(final-start)/(path_length+eps)` and shape is `(trajectory[1:]-start)/(path_length+eps)`. Pair distances are `0.5*L2(direction)` and `0.5*L2(flattened_shape)/sqrt(horizon)`.

## Capacity-one replay and capacity-two counterfactual

For each trace, replay streams causally in order. Before a noninitial update whose active bounds changed, rebin existing entries by current descriptor and retain the best entries under the target capacity. Capacity-one must reproduce every saved per-cell elite reward map, occupied-cell count, best reward, update accounting and cumulative-visit total. This exact replay is a validity gate, not an optimization result.

Capacity-two uses the same candidate stream, bounds and XY-cell visits. Each cell retains at most two fingerprint-unique entries sorted by `(reward desc, fingerprint asc)`. On rebin, all source entries are regrouped and top two retained. An old cell's cumulative visits move to the new cell containing that old cell's reward-best entry; merged visit counts sum. This makes visit conservation deterministic without duplicating visits.

For each post-update capacity-two state:

1. project one reward-best representative per occupied XY cell and call the unchanged production sparse allocator with population 15 and the trace `(episode, global_step, iter_idx)` coordinates;
2. prepend the unchanged global-quality anchor selected by `(reward desc, fingerprint asc, cell asc, slot asc)`;
3. within each cell, assign its sparse slots round-robin over stored entries, starting from a stateless SHA-256 hash of `(episode, global_step, iter_idx, cell)`; no Torch/Python global RNG may change.

The candidate cell-count map must equal the production 15-slot cell allocation plus one anchor. Secondary activation is the number of sparse slots assigned to slot 1. Coverage retention compares occupied XY cells receiving at least one total slot against a capacity-one replay using the same 1+15 rule and coordinates.

This counterfactual does not replay offspring, future scores, environment interaction or success and cannot estimate success rate.

## Confirmatory gates

PASS requires all of the following:

1. all 24 trace checksums/sizes/stream counts and all three source/design checksums match;
2. exactly 264 eligible streams, at least 3,000 candidates and at least 500 colliding cells;
3. candidates in colliding cells / all candidates is `>=0.40`;
4. across colliding cells, reward top-two direction-distance median is `>=0.20`, shape-distance median `>=0.15`, and reward-gap median `<=0.02`;
5. capacity-one exact replay has zero mismatch against saved reward/occupancy/best/accounting/visit data;
6. capacity-two always retains the capacity-one cell quality winner and global reward best, has no duplicate fingerprint, never exceeds two entries/cell, and preserves visit sums through every rebin;
7. every capacity-two allocation is exactly one anchor plus 15 production sparse slots, has total16, secondary activation ratio `>=0.20`, and median XY-cell allocation coverage retention `>=0.85`;
8. two independent analyses have byte-identical scientific payloads, do not mutate global Torch or Python RNG state, and have zero nonfinite/accounting/write-boundary/credential failure.

PASS authorizes only a new TDD implementation protocol for `qd_within_cell_top2_v1`. FAIL rejects H5-v4 offline and immediately triggers an outer-loop reflection with zero new online episodes.

## Allowed writes and outputs

- New worktree implementation files after this protocol commit: `scripts/eds_qd_within_cell_aliasing_diagnostic.py` and `tests/test_eds_qd_within_cell_aliasing_diagnostic.py` only.
- Result phase may add `analysis.md` and append the common state/findings/log/ledger/trajectory records.
- Large outputs only below owned `run_040_within_cell_aliasing_diagnostic/analysis/` as canonical/replay JSON; after successful creation both become mode 0444.
- Analyzer implementation commit must precede artifact generation and result commit.
- GPU/API/model/LIBERO/reservation/Dev/validation/formal authorization remains zero.
