# N24 task0 clipping-reference eligibility — completed CPU-only screen

The fixed CPU reference changed eligibility in **5/14 pools**, adding **5/224 candidate rows** and removing **5/224 rows**. Among full8-positive rows it added **4** and removed **5**. Crucially, **steps304 and408 still had empty eligible sets**: this reference did not make either previously unselected full8 row eligible. All five originally selected full8 rows remained eligible in the CPU reference. No cost, quality or provider return was consulted, and no new selection was computed.

These are CPU reference memberships, **not hypothetical CUDA results**. Every hypothetical CUDA membership remains **Unknown**. The reference changes both the geometric formula and the backend used to reconstruct it; the bounded result cannot isolate backend rounding from the clipping intervention at a threshold. It supplies no physical grasp or success claim and does not establish that the frozen two-consumer design is a bug.

## Coverage and provenance

Exactly the original 14 bundles / 243123318 bytes were read once each, hashed from those same bytes and loaded with `torch.load(BytesIO(...), map_location='cpu', weights_only=True)`. All 14 terminal pools and 224 candidate rows are retained. Two CPU and interop threads, CUDA invisible/uninitialized, no guard rejections, network, subprocess, API, model or simulator calls. Extraction elapsed **6.088635009 seconds**; the four preserved earlier startup attempts plus this run total **9.582421372 seconds** inside the frozen 120-second envelope. Old failed scopes and logs remain closed and unchanged.

The current scope explicitly fixes task0/N24 attempt `rdt-qd-ed-final-20260921T093925Z__n24_dev_t00_n24_20260930__169d5a090d1b`; its historical predecessor's null top-level attempt field was never wildcard authorization. Same-call canonical/scoring IDs, all event headers, terminal selected occurrence/fingerprint, closed command/membership witnesses and the 16 directly linked origins per pool passed the frozen checks. Each captured origin, cast to the population dtype, was byte-identical to its recorded t0. Full candidate identity uses recorded fingerprints; other latent dimensions were not rehashed.

## Arithmetic boundary

All native populations were BF16. The reference used each candidate's first8 translation dimensions39:42, componentwise `clamp(-1,1) * 0.01`, native-dtype CPU cumulative sum, and the captured origin. Distances then used FP32 norm, exactly the original absolute0.06m and global-minimum-plus0.03m rule over all16×8 points, conjoined with the recorded binary positive commands. No thresholds were tuned.

FP32 distances computed directly from **recorded native raw xyz** matched the recorded original distances exactly in all14 pools (maximum absolute error0); original eligibility also matched in all14. In contrast, **CPU raw projection reconstructed from original translations** was not byte-identical for any pool, with maximum absolute coordinate difference **0.001953125m (1.953125mm)**. That mismatch is reported rather than hidden, fitted away or used as a runtime defect claim. No additional CUDA check was performed.

Across the224 rows, 191 rows / 605 coordinate components differed in the CPU raw reconstruction. 202 rows had first7 clipping and 202 had full8 clipping; t8-only clipping count was 0. Nevertheless the reference explicitly extends geometric eligibility through t8, whereas production N23 quality uses t1..t7.

## Complete14-pool table

`F8` counts rows with eight positive commands. `Raw E` is the authoritative recorded eligible set; `CPU E` is the hypothetical CPU reference. `+`/`−` are candidate indices gained/lost. Original selected membership is shown without calculating any new selected action.

| Step | Original category | F8 | Raw E | CPU E | + / − | Original selected index: raw→CPU eligible |
|---:|---|---:|---|---|---|---|
| 0 | No full8 | 0 | ∅ | ∅ | ∅ / ∅ | 5: 0→0 |
| 8 | No full8 | 0 | ∅ | ∅ | ∅ / ∅ | 1: 0→0 |
| 16 | No full8 | 0 | ∅ | ∅ | ∅ / ∅ | 6: 0→0 |
| 160 | No full8 | 0 | ∅ | ∅ | ∅ / ∅ | 1: 0→0 |
| 232 | No full8 | 0 | ∅ | ∅ | ∅ / ∅ | 1: 0→0 |
| 240 | Selected full8 | 16 | 2,5,10,14 | 5,14 | ∅ / 2,10 | 5: 1→1 |
| 304 | Full8 all ineligible | 1 | ∅ | ∅ | ∅ / ∅ | 8: 0→0 |
| 312 | Selected full8 | 15 | 1,3,11,14 | 3 | ∅ / 1,11,14 | 3: 1→1 |
| 320 | Selected full8 | 16 | 0,3,7,9,11 | 0,3,7,9,11,14 | 14 / ∅ | 9: 1→1 |
| 328 | Selected full8 | 16 | 0,1,2,3,4,5,7,8,9,15 | 0,1,2,3,4,5,7,8,9,10,13,14,15 | 10,13,14 / ∅ | 9: 1→1 |
| 392 | No full8 | 0 | ∅ | ∅ | ∅ / ∅ | 11: 0→0 |
| 400 | No full8 | 0 | ∅ | ∅ | ∅ / ∅ | 0: 0→0 |
| 408 | Full8 all ineligible | 1 | ∅ | ∅ | ∅ / ∅ | 2: 0→0 |
| 416 | Selected full8 | 5 | 6 | 3,6 | 3 / ∅ | 6: 1→1 |

The table preserves all **7 no-full8**, **5 selected-full8** and **2 full8-all-ineligible** pools. Losses occurred at step240(indices2,10) and312(indices1,11,14); full8 gains occurred at320(index14) and328(indices10,13,14). Step416 gained a non-full8 row(index3). These set changes are not a ranking or efficacy comparison.

`all-candidates-v1.csv` and `result-v1.json` contain all224 original/reference memberships, both clipping masks, raw reconstruction differences, original selected flags, occurrence/fingerprint bindings and explicit Unknown CUDA fields. `all-decisions-v1.csv` gives all14 full summaries including native source sequence/hash references.

No additional payload reading, candidate implementation or online intervention is authorized by this closure. Current frozen N24 scientific/controller source, experiment, budget and ledger were not changed.
