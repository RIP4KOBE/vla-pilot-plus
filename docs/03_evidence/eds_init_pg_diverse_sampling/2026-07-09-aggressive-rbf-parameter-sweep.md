# RBF+EDS Aggressive Initial Diversity Parameter Sweep

Timestamp: `2026-07-09T17:51:31+00:00`

Verdict: `pass`

## Scope

- Level: `level2` online smoke on `libero_object` task filter `[0]`.
- Methods: `iid_baseline`, `rbf_s1_start_null`, and aggressive RBF scale/start-ratio sweep.
- Existing EDS metrics are retained; the EEF trajectory-space fields below are additional diagnostics.
- Evidence root: `docs/03_evidence/eds_init_pg_diverse_sampling`.

## Main Metrics

| Run | Scale | Start Ratio | Complete | Success | Records | Diversity Steps | Fallbacks | Grad Failures | Nonfinite | Action Mask Max | initial_eef_diversity_before_rbf | initial_eef_diversity_after_rbf_phase | initial_eef_diversity_final | initial_eef_diversity_retention_ratio | endpoint_spread_before_rbf | endpoint_spread_after_rbf_phase | endpoint_spread_final | selected_reward | target_distance_after | select_action_latency_s | initial_sampler_latency_s |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `iid_baseline` | 1.0 | null | `True` | 0/3 | 90 | 0.000 | 0 | 0 | 0 | 0.000 | - | - | 0.054 | - | - | - | 0.030 | -0.009 | 0.074 | 2.730 | 0.412 |
| `rbf_s1_start_null` | 1.0 | null | `True` | 0/3 | 90 | 1.000 | 0 | 0 | 0 | 0.000 | 0.141 | 0.140 | 0.055 | 0.390 | 0.065 | 0.065 | 0.030 | -0.009 | 0.074 | 2.754 | 0.426 |
| `rbf_s5_start06` | 5.0 | 0.6 | `True` | 0/3 | 90 | 3.000 | 0 | 0 | 0 | 0.000 | 0.141 | 0.168 | 0.061 | 0.356 | 0.065 | 0.082 | 0.033 | -0.010 | 0.076 | 2.773 | 0.449 |
| `rbf_s10_start06` | 10.0 | 0.6 | `True` | 0/3 | 90 | 3.000 | 0 | 0 | 0 | 0.000 | 0.141 | 0.242 | 0.071 | 0.287 | 0.065 | 0.118 | 0.038 | -0.010 | 0.075 | 2.768 | 0.450 |
| `rbf_s20_start06` | 20.0 | 0.6 | `True` | 0/3 | 90 | 3.000 | 0 | 0 | 0 | 0.000 | 0.141 | 0.395 | 0.091 | 0.228 | 0.065 | 0.191 | 0.048 | -0.010 | 0.079 | 2.785 | 0.454 |
| `rbf_s5_start08` | 5.0 | 0.8 | `True` | 0/3 | 90 | 4.000 | 0 | 0 | 0 | 0.000 | 0.141 | 0.165 | 0.088 | 0.517 | 0.065 | 0.082 | 0.046 | -0.009 | 0.072 | 2.788 | 0.456 |
| `rbf_s10_start08` | 10.0 | 0.8 | `True` | 0/3 | 90 | 4.000 | 0 | 0 | 0 | 0.000 | 0.141 | 0.263 | 0.122 | 0.461 | 0.065 | 0.129 | 0.063 | -0.010 | 0.077 | 2.791 | 0.461 |
| `rbf_s20_start08` | 20.0 | 0.8 | `True` | 1/3 | 77 | 4.000 | 0 | 0 | 0 | 0.000 | 0.142 | 0.456 | 0.156 | 0.340 | 0.065 | 0.223 | 0.082 | -0.010 | 0.078 | 2.785 | 0.461 |

## Safety Gate

| Run | Fallbacks | Grad Failures | Nonfinite | Action Mask Max | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `iid_baseline` | 0 | 0 | 0 | 0.000 | `pass` |
| `rbf_s1_start_null` | 0 | 0 | 0 | 0.000 | `pass` |
| `rbf_s5_start06` | 0 | 0 | 0 | 0.000 | `pass` |
| `rbf_s10_start06` | 0 | 0 | 0 | 0.000 | `pass` |
| `rbf_s20_start06` | 0 | 0 | 0 | 0.000 | `pass` |
| `rbf_s5_start08` | 0 | 0 | 0 | 0.000 | `pass` |
| `rbf_s10_start08` | 0 | 0 | 0 | 0.000 | `pass` |
| `rbf_s20_start08` | 0 | 0 | 0 | 0.000 | `pass` |

## Mechanism Gate

| Run | After RBF > Default RBF | Final EEF >= IID * 1.10 | Endpoint >= IID * 1.10 | Verdict |
| --- | ---: | ---: | ---: | --- |
| `rbf_s5_start06` | 0.028 | 1.139 | 1.119 | `pass` |
| `rbf_s10_start06` | 0.102 | 1.310 | 1.272 | `pass` |
| `rbf_s20_start06` | 0.254 | 1.681 | 1.612 | `pass` |
| `rbf_s5_start08` | 0.025 | 1.627 | 1.561 | `pass` |
| `rbf_s10_start08` | 0.122 | 2.263 | 2.143 | `pass` |
| `rbf_s20_start08` | 0.316 | 2.891 | 2.761 | `pass` |

## Utility Gate

| Run | selected_reward - IID | target_distance_after - IID | Verdict |
| --- | ---: | ---: | --- |
| `rbf_s5_start06` | -0.000 | 0.001 | `pass` |
| `rbf_s10_start06` | -0.000 | 0.001 | `pass` |
| `rbf_s20_start06` | -0.001 | 0.005 | `pass` |
| `rbf_s5_start08` | 0.000 | -0.002 | `pass` |
| `rbf_s10_start08` | -0.000 | 0.003 | `pass` |
| `rbf_s20_start08` | -0.001 | 0.004 | `fail` |

## Delta vs IID Baseline

| Run | Δ initial_eef_diversity_final | Δ endpoint_spread_final | Δ selected_reward | Δ target_distance_after | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `rbf_s1_start_null` | 0.001 | 0.001 | -0.000 | 0.000 | `reference` |
| `rbf_s5_start06` | 0.008 | 0.004 | -0.000 | 0.001 | `pass` |
| `rbf_s10_start06` | 0.017 | 0.008 | -0.000 | 0.001 | `pass` |
| `rbf_s20_start06` | 0.037 | 0.018 | -0.001 | 0.005 | `pass` |
| `rbf_s5_start08` | 0.034 | 0.017 | 0.000 | -0.002 | `pass` |
| `rbf_s10_start08` | 0.068 | 0.034 | -0.000 | 0.003 | `pass` |
| `rbf_s20_start08` | 0.102 | 0.052 | -0.001 | 0.004 | `fail` |

## Delta vs Default RBF

| Run | Δ initial_eef_diversity_final vs s1 | Δ endpoint_spread_final vs s1 | Δ selected_reward vs s1 | Δ target_distance_after vs s1 |
| --- | ---: | ---: | ---: | ---: |
| `rbf_s5_start06` | 0.006 | 0.003 | -0.000 | 0.001 |
| `rbf_s10_start06` | 0.016 | 0.007 | -0.000 | 0.001 |
| `rbf_s20_start06` | 0.036 | 0.018 | -0.001 | 0.005 |
| `rbf_s5_start08` | 0.033 | 0.016 | 0.000 | -0.002 |
| `rbf_s10_start08` | 0.067 | 0.033 | -0.000 | 0.003 |
| `rbf_s20_start08` | 0.101 | 0.052 | -0.001 | 0.004 |

## Output Index

- `iid_baseline`: output `outputs/rdt_eds_eval/level2_libero_object_iid_baseline`, metrics `outputs/rdt_eds_eval/level2_libero_object_iid_baseline/eds_eval/eds_metrics.jsonl`
- `rbf_s1_start_null`: output `outputs/rdt_eds_eval/level2_libero_object_rbf_s1_start_null`, metrics `outputs/rdt_eds_eval/level2_libero_object_rbf_s1_start_null/eds_eval/eds_metrics.jsonl`
- `rbf_s5_start06`: output `outputs/rdt_eds_eval/level2_libero_object_rbf_s5_start06`, metrics `outputs/rdt_eds_eval/level2_libero_object_rbf_s5_start06/eds_eval/eds_metrics.jsonl`
- `rbf_s10_start06`: output `outputs/rdt_eds_eval/level2_libero_object_rbf_s10_start06`, metrics `outputs/rdt_eds_eval/level2_libero_object_rbf_s10_start06/eds_eval/eds_metrics.jsonl`
- `rbf_s20_start06`: output `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start06`, metrics `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start06/eds_eval/eds_metrics.jsonl`
- `rbf_s5_start08`: output `outputs/rdt_eds_eval/level2_libero_object_rbf_s5_start08`, metrics `outputs/rdt_eds_eval/level2_libero_object_rbf_s5_start08/eds_eval/eds_metrics.jsonl`
- `rbf_s10_start08`: output `outputs/rdt_eds_eval/level2_libero_object_rbf_s10_start08`, metrics `outputs/rdt_eds_eval/level2_libero_object_rbf_s10_start08/eds_eval/eds_metrics.jsonl`
- `rbf_s20_start08`: output `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start08`, metrics `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start08/eds_eval/eds_metrics.jsonl`

## Completion Gate

- All aggressive RBF level2 sweep jobs have complete outputs.
- Every EDS job has a non-empty `eds_eval/eds_metrics.jsonl`.

## Notes

- `OPENAI_API_KEY=dummy` may appear in offline cached-guidance runs only to satisfy client initialization; cached-guidance mode does not call an online VLM for reward generation.
- Negative `Δ target_distance_after` is favorable because smaller target distance is better.
- Safety failures must be read together with logs before interpreting mechanism or utility deltas.
