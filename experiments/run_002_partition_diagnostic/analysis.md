# `run_002_partition_diagnostic` Analysis

Status: `COMPLETE`

Decision: `KEEP_DIAGNOSTIC_EVIDENCE_AND_AUTHORIZE_ONE_QD1_PROTOCOL`

## Result

The fixed-initial replay reproduced all 4,567 eligible 4x4 records with zero field or accounting mismatch. The preregistered `causal_envelope_v1` counterfactual passed every validity and scientific gate:

| Metric | Gate | Observed | Result |
| --- | ---: | ---: | --- |
| Input hashes / records | 27 files / 4,705 records exact | 27 / 4,705 | PASS |
| Eligible baseline exactness | zero mismatches | 4,567 / 4,567 exact | PASS |
| Permutation failures | zero | 0 / 4,567 | PASS |
| Unrepresented overflow P95 | `<=0.25` | `0.0` | PASS |
| Raw out-of-initial-bounds P95 | disclose unchanged | `0.875` | PASS |
| Endpoint-resolution improvement, equal chunk | `>=0.20` | `0.300775` | PASS |
| Endpoint-resolution improvement, equal profile | `>=0.20` | `0.309348` | PASS |
| Target task strata at `>=0.20` | at least 2; none `<-0.05` | 4/4; worst `0.273937` | PASS |
| Final occupied-mode ratio median | `>=0.90` | `0.9375` | PASS |
| Archive endpoint-spread ratio median | `>=0.90` | `2.008744` | PASS |
| Global best reward + fingerprint | 100% preserved | `1.0` | PASS |

Target-stratum resolution medians were task 3 `0.273937`, task 5 `0.318165`, task 8 `0.326254`, and task 9 `0.308536`.

## Validity and determinism

- Analyzer implementation commit: `82a9f42d5ac2e80a5390767eb9e3a590f3aa2bf7`.
- Analyzer source SHA-256: `12d09a2a5887d114fc87f597c00e336478f361044f2c2ca997d9f920d2c57911`.
- Canonical analysis SHA-256: `e21d2598981f8dbe538d35da77b33b31585a92b4e960c7056bef7d729e20d9a7`.
- Two independent complete repeats produced the identical analysis hash. Their temporary 11 MiB directories were moved to trash after verification; the canonical 11 MiB artifact remains.
- The first canonical invocation was terminated by an external 120-second shell timeout before any artifact write. The same commit, command, inputs, and thresholds then completed in 149.2 seconds. This is local execution provenance, not an online episode attempt, data-validity failure, or scientific retry.
- Online episodes, GPU-hours, environment/model/reward/VLM/network calls: all zero.

## Interpretation

This result supports the narrow H1 claim that causal envelope expansion improves endpoint partition resolution on the historical common candidate streams without losing the global reward-best action. It does not establish task success: the replay cannot regenerate offspring from changed parent cells, and endpoint geometry is not candidate-level manipulation progress.

Accordingly, the result authorizes exactly one separately protocol-locked QD-1 implementation of `causal_envelope_v1`. No grid, bounds, expansion-rate, or neighboring partition sweep is authorized. The historical best remains 2/10 and the target gap remains three tasks until valid online results change it.

## Artifacts

- Canonical root: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_002_partition_diagnostic`
- `analysis.json`: `e21d2598981f8dbe538d35da77b33b31585a92b4e960c7056bef7d729e20d9a7`
- `input-manifest.json`: `d322720fbc1d3fc69456a38f80fced0090471460a141aa8c15fa349865f8abcd`
- `summary.md`: `7b638e0f40c0dd3220c7c20bf25facce09bf6f4324d231078c237532746a7450`
