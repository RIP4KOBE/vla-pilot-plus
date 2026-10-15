# Executed-projection audit: clipping lead, scale substitution rejected

Three native-audited exposed Dev paths supplied243 paired eight-action chunks (37 guided); final unpaired chunks were excluded. Sent actions exactly matched policy-decoded actions and source origins were taken before execution. No new simulator, model, provider or GPU call was made.

| Path | Guided chunks | Raw0.01 mean endpoint error | Clipped0.01 error | Clipped0.05 error | Saturated translation components |
|---|---:|---:|---:|---:|---:|
| n17_n7_task0 | 17 | 5.59cm | 3.35cm | 37.11cm | 121 |
| n17_n7_task9 | 4 | 7.66cm | 2.73cm | 40.31cm | 48 |
| n21_task0 | 16 | 6.14cm | 2.97cm | 41.53cm | 147 |

The installed OSC config has0.05m target increments, but closed-loop dynamics do not realize their direct sum. Merely substituting that scale is rejected by these descriptive errors. Clipping to the declared unit input range at the existing0.01 scale reduces mean guided error on each path. All316 out-of-range translation components occur in guided chunks; none of the paired unguided chunks has such a component. These are component counts, not independent samples.

This is a candidate-dependent actuator-saturation lead, distinct from N3's prior-chunk residual transport (which explicitly excluded actuator-bound correction and failed Dev). N2 only extended the uncorrected projection from7 to8 points. Neither old result establishes whether clipping-aware QD geometry can improve task success. The newly quantified native-valid N7/N21 examples are stronger evidence than a source-default mismatch alone, but show only prediction error, not the effect of choosing alternative actions.

Installed configuration was inspected after these older runs; historical resolved controller bounds were not independently captured in these native traces. A future implementation must bind/check actual applicable controller metadata before claiming exact clipping semantics. This audit does not change the frozen provider, projector, Stage, decoder, N22, or budget. N22 retains execution priority. A separate prospective saved-pool quality/selection screen and an attributable hypothesis would be required before a subsequent candidate.

Result SHA256: `fe49c99ce0c3528c9a1e1f3e30b07a71639eac00282807eff8522a1cf287bcc3`.
