# Task0 recorded-candidate tail availability

Both authorized CPU runs completed using the unchanged reviewed script `5ed4a49c0e9b62e43e5b98915e8bca252c6f598ce23a339d68b154e22906a839` and protocol `981534d1e561dfe888b8cbeac92e4b14ba7fa3ecdaef04d498b7e1760d7f0ff5`. Root execution authorization is `authorization-v1.json` SHA `733c0d505254d2b23c0cbe2eadbe95b4d5dcea5e7220e271b3d69ed0732924d1`. Explicit manifests bind it separately from the earlier post-data identity-v3 authorization. Fresh complete audits and all frozen input/source hashes passed. No real-data schema exception or relaxed gate was needed. CUDA remained uninitialized; no provider, model, projector, simulator or GPU ran.

Every guided eligible decision had a recorded, distinct-latent candidate not flagged by the original projected tail-regression screen. This does **not** imply a quality-preserving alternative: Q0 had no distinct-latent nonflagged candidate with original effective quality at least as high as its selected candidate. In all 17 Q0 A-witness decisions, even the best recorded nonflagged candidate had strictly lower original quality. C0 had a distinct quality-preserving historical candidate in 4 of its 5 A-witness decisions. These are historical pool observations, not evidence that the candidates remained in the final archive or that executing them would succeed.

“Nonflagged” below means only `d8 − d7 <= u(p7) + u(p8)` using the unchanged frozen native-storage ULP screen. It does not establish physical non-regression. A/non-A are the original supplemental actual-witness labels and are used only for descriptive stratification; all eligible decisions were analyzed.

| Episode / stratum | Decisions | Distinct-latent nonflagged exists | Any nonflagged quality ≥ selected, including same latent | Distinct-latent nonflagged quality ≥ selected | Best nonflagged quality delta < 0 |
|---|---:|---:|---:|---:|---:|
| C0, all eligible | 29 | 29 | 25 | 23 | 4 |
| C0, A | 5 | 5 | 4 | 4 | 1 |
| C0, non-A | 24 | 24 | 21 | 19 | 3 |
| Q0, all eligible | 52 | 52 | 21 | 0 | 31 |
| Q0, A | 17 | 17 | 0 | 0 | 17 |
| Q0, non-A | 35 | 35 | 21 | 0 | 14 |

C0 retained 5,104 canonical occurrences and Q0 retained 9,152, including repeats. Candidate identity ambiguity, ineligible candidate occurrences, unknown candidate tail classifications and A-Unknown eligible decisions were all zero. The original episode-level excluded decisions remain 61 for C0 and 38 for Q0; they were not silently added to eligibility. Original B counts are 1 for C0 and 14 for Q0. Both original episode outcomes remain valid failures (`success=false`).

The best-known nonflagged quality minus actual selected quality ranges from `-0.00250244140625` to `0.0185546875` for C0, and from `-0.009765625` to `0` for Q0. Within A witnesses, the ranges are `[-0.00005340576171875, 0.009429931640625]` for C0 and `[-0.0012054443359375, -0.0000019073486328125]` for Q0. Every exact tied maximum, original occurrence, fingerprint and signed delta is retained in the per-episode JSON; `summary-v1.json` retains every decision summary. No weight, tolerance or selection rule was fitted.

Candidates were observed in canonical scoring records before final selection, so their saved features were available at those scoring calls. This analysis neither replays archive replacement nor establishes continued availability at final selection. C0's historical quality improvements cannot be treated as final-population alternatives. Repeated occurrences and decisions are correlated within the two episodes, not independent samples. There are no counterfactual success labels, p-values, algorithm changes, promotion or claims of success-rate improvement. Task5, observer=false and external GPU2 evidence were not read or pooled.

The CPU script sections took 23.865459388 s (C0) and 43.731013382 s (Q0); total child wall times were 25.636974408 s and 45.889123505 s. Cumulative parent peak RSS after analysis was 963,660 KiB and 1,402,580 KiB. These process peaks include imports and audits; differences of peaks are not exclusive analysis memory. Original W sources, queue, ledger and input evidence were unchanged. `promotion_status=NOT_EVALUATED`.

Evidence files (relative to this directory):

- `input-t00-c0-v1.json`: SHA `f60b197ede888ce6c7f7c7ba7a0d6bbb3cf6e2181a87089cbb5de9808d194693`.
- `input-t00-q0-v1.json`: SHA `49b8e39a3412c43526267ee0d851096ac6aaa8be13e65601a5e5a3832e736df0`.
- `t00-c0-v1/candidate-tail-availability.json`: SHA `f60ad2353dbc181e77d2fb8a01d67fdf71fa3f41a386512eee7f08bb096dbf68`.
- `t00-q0-v1/candidate-tail-availability.json`: SHA `eb4619939885ec83f7744f6e39f1cd62214c8b0f98f15797373b84b8e4a44348`.
- `summary-v1.json` is reproducible from those two digest-bound JSON files with `CUDA_VISIBLE_DEVICES='' python summarize-written-reports-v1.py` into an absent summary destination; the script refuses an existing output. It does not reread bundles.
- Per-episode invocation, stdout, stderr and process-result files preserve the exact command and exit status.
