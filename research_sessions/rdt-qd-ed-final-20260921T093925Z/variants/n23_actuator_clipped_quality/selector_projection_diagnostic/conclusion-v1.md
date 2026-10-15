# N23/task0: selector versus clipped-quality geometry

**The saved selector still consumes the original unclipped projection.** N23 clipped quality and the unchanged N5 gate use different internal geometries. This is directly supported by source and the15 saved final pools. A bounded fixed-pool CPU screen finds eligibility differences at2/15 decisions, but **no final selected-index change**. This does not show that the inconsistency caused task failure, nor that correcting it would improve success.

The inspected completed attempt is `rdt-qd-ed-final-20260921T093925Z__n23v2_dev_t00_n23_20260930__2cfd86692394`. Its existing metered report accepts15 guided decisions/165 canonical batches/2640 candidates; clipping affected2017 scored-prefix candidates and138 batches changed quality rank. The episode was already exposed as an unsuccessful Dev outcome. No other attempt, protected or in-flight data was read.

## Native source and association

- `core/qd_actuator_clipped_quality.py`: internal quality clips translation components to[-1,1], integrates at0.01 in the native dtype and scores only t1..t7. It returns quality plus a seven-step changed mask, not clipped XYZ. Deployed actions, provider/raw rewards and Stage binding remain original.
- `core/rdt_policy_steer.py:6203–6207`: terminal descriptor projection is captured as `terminal_projected_xyz`; at6916–6920 it is passed unchanged to `select_grasp_timing`.
- `core/qd_grasp_timing.py`: N5 uses all t1..t8 projected points, FP32 distances, a positive binary command, distance<=6cm and distance<=global-best-reach+3cm. The global minimum includes negative-command points too. Selection is the first minimum native cost among eligible rows, falling back to the global native minimum if no row is eligible.
- Linked terminal scoring/canonical/final records contain the same16 native candidate rows. Saved FP32 gate distances and positive masks reproduce the native eligibility and chosen index exactly. CPU distance calculation from the **stored** native projection equals all saved distances exactly. Costs are the original metered N23 effective costs; they were not rescored.
- No clipped XYZ is stored in the selected scoring/effective/final records. Every clipped t1..t8 trajectory below is a hypothetical CPU construction. In particular, t8 is not a recorded native clipped score input and is not evidence for an eight-step quality variant.

## Fifteen final pools

“Raw eligible” is exact saved evidence. “CPU clipped eligible” and its selected index are approximate fixed-pool diagnostics. The conditional rounding-envelope column is not GPU certification. `Unknown` below means the unrecorded clipped GPU geometry was not validated. All indices are zero-based.

| Step | Positive commands /128 | Raw eligible | CPU clipped eligible | Original → CPU index | Uncertain eligibility under envelope | Actual clipped-GPU selection |
|---:|---:|---|---|---|---|---|
| 0 | 0 | ∅ | ∅ | 5 → 5 | ∅ | same for any geometry |
| 8 | 0 | ∅ | ∅ | 1 → 1 | ∅ | same for any geometry |
| 16 | 0 | ∅ | ∅ | 6 → 6 | ∅ | same for any geometry |
| 160 | 0 | ∅ | ∅ | 1 → 1 | ∅ | same for any geometry |
| 232 | 0 | ∅ | ∅ | 1 → 1 | ∅ | same for any geometry |
| 240 | 128 | 2,5,10,14 | 5,14 | 5 → 5 | 2,10 | **Unknown** |
| 304 | 4 | ∅ | ∅ | 12 → 12 | ∅ | **Unknown** |
| 312 | 0 | ∅ | ∅ | 1 → 1 | ∅ | same for any geometry |
| 328 | 0 | ∅ | ∅ | 0 → 0 | ∅ | same for any geometry |
| 344 | 4 | ∅ | ∅ | 0 → 0 | ∅ | **Unknown** |
| 400 | 0 | ∅ | ∅ | 3 → 3 | ∅ | same for any geometry |
| 408 | 120 | 14 | 10,13,14 | 14 → 14 | 13 | **Unknown** |
| 488 | 0 | ∅ | ∅ | 7 → 7 | ∅ | same for any geometry |
| 496 | 0 | ∅ | ∅ | 8 → 8 | ∅ | same for any geometry |
| 504 | 6 | ∅ | ∅ | 15 → 15 | ∅ | **Unknown** |

At step240, rows2 and10 cease to qualify in the CPU point estimate; row5 remains chosen. Row2 has raw absolute/relative margins+0.0764/+0.3326cm; clipping changes the relative margin to−0.4398cm. Row10 is only0.000498cm outside the6cm absolute threshold in the CPU estimate and has relative margin−0.5223cm. Under the conservative envelope both eligibility changes remain Unknown. Row5 is definitely eligible within that model and has native cost0.00148773193359375, below the other competing eligible/uncertain rows.

At step408, row10 changes from raw minimum-positive distance6.0569cm to CPU-clipped1.7118cm. Its clipped absolute/relative margins are+4.2882/+3.0000cm, so this additional eligibility is stable within the stated rounding model. Row13 changes its relative margin from−0.1822cm to+0.2649cm; its eligibility remains Unknown under the envelope. Neither changes the point-estimate choice: original row14 costs0.0012359619140625 versus0.00140380859375 for row10 and0.00244140625 for row13. Row14 remains definitely eligible and cheapest in the modeled set.

Ten pools contain no positive gripper command anywhere in their16×8 decoded command arrays. Their unchanged gate is false regardless of geometry; the selector must retain its native global minimum. Steps304,344 and504 contain some positive commands but none qualifies under either saved raw geometry or the modeled clipping envelope. Across all15 pools, the native chosen row is also the global native cost minimum: True.

## Numerical boundary

The first result preserves the full approximate calculation and its conditional envelope. The numerical supplement deliberately separates that envelope from actual GPU knowledge. Reintegrating **unclipped** commands on CPU in the recorded BF16 dtype was not bitwise equal to the saved projection at any of15 decisions; maximum component difference is1.953125mm. This is an observed backend reconstruction boundary, even though norm calculation from the stored native XYZ is exact. No CUDA was used to resolve it and no tolerance in a deployed/native checker changed.

The envelope centers on FP64 arithmetic applied to exact dequantized recorded commands/origins/target, after componentwise clipping. Let u=2^-8 for BF16, S_k be the cumulative absolute0.01-scaled increments, and γ_(k−1)=(k−1)u/(1−(k−1)u). The per-coordinate modeled error bound is B=(u+γ_(k−1)(1+u))S_k, followed by E=B+u(|origin|+S_k+B). Distance half-width is ||E||₂ plus an explicit FP32 rounding allowance `1e-6m + 16*eps32*max(|point|,|target|)`; observed maximum half-width across decisions ranges4.50–6.12mm.

This is an analytical conservative envelope **under assumptions**: ordinary round-to-nearest native multiplication/addition, at most k−1 accumulation additions (or higher-precision accumulation), normal finite values and ordinary FP32 subtraction/norm error. It is not a directed-rounding interval implementation or an independently certified bound on the exact installed CUDA kernels. The FP32 allowance is a conservative diagnostic allowance, not a measured GPU guarantee. The calculation does not cover new decoder/target/controller policies, physical motion or contact. Therefore five decisions with positive commands retain **Unknown** for actual unrecorded clipped GPU selection; the ten zero-positive decisions have a separate geometry-independent proof of unchanged selection.

Candidate eligibility is definitely true within the envelope only when one positive-command point has its upper distance below6cm and below(minimum lower distance)+3cm. It is definitely false when every positive-command point has a lower distance above6cm or above(minimum upper distance)+3cm. Otherwise it is Unknown. Selection possibilities include every assignment of uncertain eligibility, conservatively ignoring correlations. All15 conditional possibility sets contain only the original chosen index; none supports a different fixed-pool selection within that model. These are descriptive diagnostics, not alternative deployed outcomes.

## Research implication

The source-level geometry split is a falsifiable coherence issue, but this one failed task0 trajectory supplies **no evidence of a terminal-selection improvement** from clipping the gate alone. Gripper-command availability is a visible limitation in ten final pools; the two changed eligibility sets still prefer the same native-cost winner. This supports keeping any later geometry-coherence or candidate-proposal hypothesis separate, prospective and subject to the existing cohort disposition. It does not justify changing the active experiment, claiming contact/success gains, or expanding the current screen. No candidate was created.

## Reproducibility and provenance

`screen_cpu_v1.py` performed one bounded screen, loading15 hash-verified bundles from this attempt. It verified receipt/report/index/bundle links, terminal source associations, native cost and decoded positive-command identity, and source file hashes against the metered worker manifest. It uses CPU only with two PyTorch threads. `screen-result-v1.json` contains each exact event sequence, native tensor dtype/hash, native/approximate distances, margins, uncertain sets and source/evidence references. `decisions-v1.csv` is the compact table. `numerical-caveat-v1.json` is derived only from already exported result tensors and adds the strict Unknown distinction; it does not reread or extend native data. No simulator/model/API/GPU work, ledger/state/budget update or active-source/controller change occurred.

- `screen_cpu_v1.py` SHA256 `754506e05715e2aff67880c43b04cd5c8b160c9021df165c038454c95bcbd63b`.
- `screen-v1.log` SHA256 `eb8471f4a7d7de094bb2362e4b74cadde21c0e98502bd26240ea1bc142ec3259`.
- `screen-result-v1.json` SHA256 `57b13d2e0c77654908845fbc17778b9722385f71f45aca0dd101f23a329b44a8`.
- `decisions-v1.csv` SHA256 `ae80e3d0eee2f998a3048aca91fb92a7b3e6be379fa79d88559f6d6c3bf7a5f0`.
- `numerical-caveat-v1.json` SHA256 `d264b84dd6c5c9e485a7ab4c6186aac1ae8022f454b8577005867b89d14e844e`.
