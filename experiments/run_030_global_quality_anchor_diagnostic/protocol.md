# Protocol — run_030 global-quality anchor allocation reconstruction

Status: `LOCKED BEFORE ANALYZER IMPLEMENTATION OR AGGREGATE RESULT`

Hypothesis: `H4-v3` in `docs/01_specs/2026-08-12-eds-qd-autoresearch-v3-global-quality-anchor-design.md`.

This protocol authorizes one read-only, zero-GPU, zero-API, zero-model, zero-LIBERO reconstruction plus analyzer tests. It does not authorize core/config changes, online dispatch, reservations, Dev, validation, or formal evaluation.

## Frozen inputs

Exactly five owned causal-envelope candidate metric files are confirmatory inputs:

| Input | Rows | SHA-256 |
| --- | ---: | --- |
| `run_010.../preflight__eds_quality_diversity_sparse_causal_envelope_v1/eds_eval/eds_metrics.jsonl` | 41 | `09a77e9063f062c566cd0306a73b47d9662032e3f39ab7b23565e35ff27e7eca` |
| `run_010.../dev_a__eds_quality_diversity_sparse_causal_envelope_v1/eds_eval/eds_metrics.jsonl` | 71 | `535be5764288863a691fb289a95ac51a5fdf4a1bdc74fac20d13508d3c7d6e84` |
| `run_010.../dev_b__eds_quality_diversity_sparse_causal_envelope_v1/eds_eval/eds_metrics.jsonl` | 49 | `6f948370a66d68e41e35eb112f7db0c92bfce8e9edcb42d0b82cf4972ac7048d` |
| `run_010.../validation__eds_quality_diversity_sparse_causal_envelope_v1/eds_eval/eds_metrics.jsonl` | 184 | `7afb70e26f7725b18dcc9c76338b326c21b5dab1108fdd457d6f81ffa8c200bd` |
| `run_023.../mechanism__eds_qd_reward_degenerate_control_fallback_v1/eds_eval/eds_metrics.jsonl` | 74 | `f18e2fcff5b852c8683f7ad869e1b9eea4a6fcc7ac3cfb4d527fb3c194767273` |

All paths resolve below `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood` and are read-only. The analyzer also binds production allocator `core/qd_ed.py` SHA `1516bb75c3a5dc3894792d6b8f5daf7f777c48b7d58ea96496da47a986a970b9` and v3 design SHA `0a2ea24763ef824010e462bbb76fa25d0e1b51d7217848f2e58b49153aabb742`.

No recursive discovery, stale/recovery tree, control profile, outcome video, success label, future observation, evaluator state, formal result, or protected untracked design may enter the confirmatory computation.

## Eligible transitions

For each valid row, only iteration `i=1..9` is eligible. Its prior archive state is:

- rewards: `qd_per_cell_elite_reward_by_iter[i-1]`;
- cumulative visits: `qd_cumulative_cell_visits_by_iter[i-1]`;
- observed allocation: `qd_parent_slots_by_cell_by_iter[i]`;
- allocator coordinates: frozen `run_seed=0`, row `episode`, row `global_step`, `iter_idx=i`, `sparse_exponent=1.0`.

The transition is valid only if all fields are correctly typed/finite, archive keys equal occupied visit cells, visits are nonnegative, observed slots contain exactly the archive cells and sum to 16, and the maximum reward is unique. Equal-maximum transitions are excluded rather than resolving an unavailable fingerprint tie. Every exclusion reason is counted.

## Frozen reconstructions

Baseline reconstruction creates a synthetic 4x4 `QDArchive` with the saved reward/visit state and calls the unchanged production `allocate_parent_slots(... population_size=16, sampling="sparse_priority")`. Its complete slot map must equal the observed map.

Candidate reconstruction uses the same prior state and RNG coordinates:

1. identify the unique global-best reward cell;
2. reserve one dedicated anchor slot for that cell;
3. call the unchanged production allocator with `population_size=15` for sparse slots;
4. add the anchor to the total slot map while retaining separate dedicated/sparse counts.

This is an allocation-only counterfactual. It does not replay actions, rewards, success, or future archive updates and cannot estimate success rate.

## Confirmatory gates

PASS requires all of the following:

1. all five input checksums/row counts and production source/design checksums match;
2. at least 300 valid transitions across at least 3 task IDs;
3. baseline reconstruction equals the saved slot map for 100% of valid transitions;
4. baseline global-best zero-slot ratio is `>=0.25` overall, and at least two tasks with at least 20 valid transitions each have ratio `>=0.20`;
5. candidate has exactly one dedicated anchor, 15 sparse slots, 16 total slots, and global-best total slots `>=1` for 100% of valid transitions;
6. candidate median ratio `occupied cells receiving >=1 slot / baseline occupied cells receiving >=1 slot` is `>=0.85`;
7. two full independent analyses produce byte-identical scientific payloads and no global Torch RNG-state mutation;
8. no nonfinite/negative count/accounting/write-boundary/credential failure.

PASS authorizes only a new protocol for TDD implementation of `qd_global_quality_anchor_v1`. FAIL concludes H4-v3 offline with zero new online episodes.

## Allowed writes and required outputs

- New worktree files: `scripts/eds_qd_global_quality_anchor_diagnostic.py`, `tests/test_eds_qd_global_quality_anchor_diagnostic.py`, and later `analysis.md` plus append-only research records.
- Large outputs only below owned `run_030_global_quality_anchor_diagnostic/analysis/` as canonical/replay JSON, mode 0444 after successful generation.
- Implementation commit must precede any result/reflection commit.
- GPU/API/model/LIBERO/reservation/Dev/validation/formal authorization remains zero.
