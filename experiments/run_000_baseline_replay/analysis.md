# `run_000_baseline_replay` Analysis

Status: `COMPLETE`

Label: `CONFIRMATORY`

Decision: `KEEP_DIAGNOSTIC_EVIDENCE`

Protocol commit: `5255e924ee925487406e35a27548d9db4e988642`

## Outcome first

All six preregistered support gates passed. This zero-episode `QD-0` run does not change the historical best EDS-QD result (`2/10`) or the `>=5/10` target gap (`3` tasks). It does make one target-linked decision: direct population/iteration scaling is rejected as the next optimization direction, and the next protocol will audit QD allocation/quality retention before changing behavior.

The later budget study supplied 18 valid configurations spanning population `{32,48,64}`, iterations `{15,20,25}`, and `512–1664` candidate evaluations per complete chunk. Every configuration scored `0/10` or `1/10`; the aggregate Spearman correlation between evaluations/chunk and success was exactly `0.0`. The task-success union was `{0,7,8,9}`, but no configuration retained or combined enough successes to approach the gate.

## Original task matrix replay

| Profile | Success tasks | Success | Validity |
| --- | --- | ---: | --- |
| control | `{3,8,9}` | 3/10 | PASS |
| uniform primary | `{}` | 0/10 | PASS |
| sparse primary | `{5,8}` | 2/10 | PASS |

Relative to control, sparse gained task 5, retained task 8, and lost tasks 3 and 9. Uniform lost all control successes. These are historical task outcomes, not new formal observations.

## Budget-study task results

| Configuration | Population | Iterations | Eval/chunk | Success tasks | Success | Safety |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| `eds_qd_sparse_primary_p32_k15` | 32 | 15 | 512 | `{}` | 0/10 | PASS |
| `eds_qd_sparse_primary_p32_k20` | 32 | 20 | 672 | `{0}` | 1/10 | PASS |
| `eds_qd_sparse_primary_p32_k25` | 32 | 25 | 832 | `{8}` | 1/10 | PASS |
| `eds_qd_sparse_primary_p48_k15` | 48 | 15 | 768 | `{}` | 0/10 | PASS |
| `eds_qd_sparse_primary_p48_k20` | 48 | 20 | 1008 | `{}` | 0/10 | PASS |
| `eds_qd_sparse_primary_p48_k25` | 48 | 25 | 1248 | `{}` | 0/10 | PASS |
| `eds_qd_sparse_primary_p64_k15` | 64 | 15 | 1024 | `{}` | 0/10 | PASS |
| `eds_qd_sparse_primary_p64_k20` | 64 | 20 | 1344 | `{0}` | 1/10 | FAIL: one qpos episode |
| `eds_qd_sparse_primary_p64_k25` | 64 | 25 | 1664 | `{8}` | 1/10 | PASS |
| `eds_qd_uniform_expand20_p32_k15` | 32 | 15 | 512 | `{7}` | 1/10 | PASS |
| `eds_qd_uniform_expand20_p32_k20` | 32 | 20 | 672 | `{}` | 0/10 | PASS |
| `eds_qd_uniform_expand20_p32_k25` | 32 | 25 | 832 | `{9}` | 1/10 | PASS |
| `eds_qd_uniform_expand20_p48_k15` | 48 | 15 | 768 | `{}` | 0/10 | PASS |
| `eds_qd_uniform_expand20_p48_k20` | 48 | 20 | 1008 | `{9}` | 1/10 | PASS |
| `eds_qd_uniform_expand20_p48_k25` | 48 | 25 | 1248 | `{9}` | 1/10 | PASS |
| `eds_qd_uniform_expand20_p64_k15` | 64 | 15 | 1024 | `{}` | 0/10 | PASS |
| `eds_qd_uniform_expand20_p64_k20` | 64 | 20 | 1344 | `{}` | 0/10 | PASS |
| `eds_qd_uniform_expand20_p64_k25` | 64 | 25 | 1664 | `{}` | 0/10 | PASS |

The old study's disclosed accounting exception remains attached: an outer tool timeout recovery caused `201` physical attempts against its frozen cap of `200`. This replay does not erase that exception or reinterpret the sweep as a clean acceptance study.

## Mechanism replay

- Catalog checksums: `13/13` matched.
- Metrics files: `27/27` present and parsed.
- QD chunk records: `4,705`; malformed `0`; missing required fields `0`; silently skipped `0`.
- QD archive offspring parent selections: `3,281,360`; direct elite parent selections: `0`.
- Records with zero direct elite carryover: `4,705/4,705 = 1.0`.
- Records with archive-only parents: `4,705/4,705 = 1.0`.
- Raw final coverage median: `1.0`; raw overflow P95: `0.875`; raw turnover median: `0.03125`.
- Across valid replayed profile summaries, coverage median was `1.0` and overflow P95 was `0.98125`.
- The independent `num_elites` audit passed: with CEM disabled, the QD branch uses empty elite indices, so configured `num_elites` does not carry a global-quality reserve.
- Three identical replay hashes were observed, including the protocol-required independent repeat: `6ad1308363a512c9b2529a090682669bb096d5000159571d5798ddd296bad963`.

## Gate decisions

| Gate | Result | Evidence |
| --- | --- | --- |
| catalog checksums | PASS | 13/13 exact SHA-256 matches |
| original task matrix | PASS | exact `{3,8,9}`, `{}`, `{5,8}` replay |
| budget target boundary | PASS | 18 valid configs; max 1/10; none >=5/10 |
| elite and parent ecology | PASS | 100% zero direct carryover; 100% archive-only; no-op audit PASS |
| coverage/overflow saturation | PASS | median 1.0; profile P95 0.98125 |
| parser accounting | PASS | all files present; zero malformed/missing/skipped records |

## Interpretation and limits

Observed: compute growth does not combine task successes; coverage is saturated; overflow remains high; QD uses archive-cell parents without a direct global-quality reserve. These observations support H1 as a descriptor-resolution problem and H4 as an allocation/retention problem.

Inference: allocation ecology is the more direct next audit because it explains the loss of known control-success modes while immutable mechanism traces are available for counterfactual lineage/slot analysis. This is not yet evidence that a particular reserve fraction will improve task success.

H2 remains unresolved because reward has not been calibrated against stage progress. H5 remains unresolved because future value within a cell has not been measured. H3 is deprioritized, not refuted: the clean-tail historical result shows that generic smoothing can reduce jumps while worsening success (`3→2→0`), so continuity alone is not the first target-linked change.

## Artifacts and reproducibility

- Parser: `src/replay_historical_eds_qd.py`, SHA-256 `cd92b3c8e5fcc4720ddb52be07e3d8724d0a54d5a37aea67e0fd5f38cf6e7c39`.
- Canonical analysis: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_000_baseline_replay/analysis.json`, SHA-256 `6ad1308363a512c9b2529a090682669bb096d5000159571d5798ddd296bad963`.
- Human summary: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_000_baseline_replay/summary.md`, SHA-256 `e0defa0b535d27cca8c84a3085d4958cbf1de98baf8d621a6ef82d2eea79f245`.
- Timed deterministic replay: `2026-08-10T15:15:49Z` to `15:15:55Z`; wall `6.16 s`, CPU `5.71 s`, max RSS `271,376 KiB`; identical analysis SHA-256.
- GPU/model/reward/VLM/environment/action calls: all zero.
- New online episodes / physical attempts / GPU-hours: `0 / 0 / 0`.

Decision: `KEEP_DIAGNOSTIC_EVIDENCE`. Next: lock a separate `run_001_allocation_ecology_diagnostic` protocol; do not implement an online candidate yet.
