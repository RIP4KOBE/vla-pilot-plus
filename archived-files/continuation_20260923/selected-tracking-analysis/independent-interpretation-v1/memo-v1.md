# Selected-tracking final-derived independent interpretation v1

The fixed previous-endpoint residual rule has conditional predictive value in these recorded trajectories, but the results contradict a uniform correction benefit. Q0 improves in 8/10 episode means and N2 in 6/10; C0 worsens in 8/10. Nothing here establishes physical task benefit or a deployable quality correction.

This is a post-data interpretation of all 30 final derived cells. The reader completion, final index and provenance were verified before reading any cell; every derived cell SHA was verified. No original bundle, new projection, keypoint, image, provider or model was read/invoked by this interpretation. Existing matrix results remain the outcome/cost authority.

## Coverage and definitions

There are 2,437 decisions and 19,473 actual actions. All 516 guided selected prefixes are associated, with 4,128 observed actions; all are full eight-action prefixes. The other 1,921 decisions have `Unknown_unguided_no_recorded_selected_projection`, not zero error. Temporal dispositions are 380 eligible adjacent pairs, 2,027 unguided boundaries and 30 first-decision boundaries. Each of the 30 cells has eligible pairs; 12 cells have only one or two. The four terminal partial prefixes (t05-C0:1, t08-C0:4, t08-Q0:2, t08-N2:2) are unguided and remain unprojected.

All projections/cast origins are BF16, source origins FP32, actual EEF responses FP64 and sent commands FP32. Conversion for description does not restore precision. Origin bridge is unavailable at the first decision of each episode (30) and present for the other 486 guided decisions.

`abs` is recorded `mean_i ||p_i-x_i||²`; `disp` is recorded `mean_i ||(p_i-O)-(x_i-x0)||²`. The fixed transport uses only the previous eligible segment’s `e_disp(8)`, multiplied by `i/8`; zero and transport below are the reader’s recorded pair MSEs. Within each episode we average existing prefix/pair MSEs; arm averages give each episode equal weight. Units are squared recorded XYZ coordinate units. No new residual, fit, gain, lag, clipping trajectory, threshold or significance test is computed. Error magnitudes across arms do not isolate arm effects because selected paths, ON/OFF exposure and eligible subsets differ.

## Episode-first arm summaries

| Arm | Guided prefixes | Eligible pairs | Abs MSE | Disp MSE | Zero MSE | Transport MSE | Transport − zero | Lower / higher episode means |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C0 | 200 | 142 | 0.00358642119 | 0.00359431447 | 0.00253968301 | 0.00351709567 | +0.000977412658 | 2 / 8 |
| Q0 | 185 | 141 | 0.00647486128 | 0.00649225313 | 0.00456570931 | 0.00313036748 | -0.00143534183 | 8 / 2 |
| N2 | 131 | 97 | 0.00440596701 | 0.00442078648 | 0.00300996315 | 0.00189212007 | -0.00111784309 | 6 / 4 |

The 380 pairs are correlated observations, not 380 independent trials. The equal-episode pattern is more limited than a universal “past residual helps” claim: for example t01 worsens in every arm, while several cells with lower error have only one pair. No task/window was selected for the summaries.

## Every accepted cell

`G` counts guided tracked prefixes, `P` eligible pairs; all tracking MSEs include every guided prefix. Zero/transport averages include every eligible pair only. Negative Δ denotes lower retrospective prediction error.

| Cell | Actual actions | G | P | Abs MSE | Disp MSE | Zero MSE | Transport MSE | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t00-c0 | 720 | 29 | 21 | 0.0053136377 | 0.0053164794 | 0.0060248037 | 0.0041718919 | -0.0018529118 |
| t00-q0 | 720 | 52 | 46 | 0.0044634422 | 0.0044661291 | 0.0032702252 | 0.0018821536 | -0.0013880716 |
| t00-n2 | 720 | 3 | 2 | 0.0019019699 | 0.0019158501 | 0.00053672069 | 0.0021036768 | +0.0015669561 |
| t01-c0 | 720 | 3 | 2 | 0.0015946275 | 0.0016114682 | 0.00019625053 | 0.0019229231 | +0.0017266726 |
| t01-q0 | 720 | 3 | 2 | 0.0058238476 | 0.0058568586 | 0.0021680548 | 0.0026119147 | +0.00044385981 |
| t01-n2 | 720 | 3 | 2 | 0.0058238476 | 0.0058568586 | 0.0021680548 | 0.0026119147 | +0.00044385981 |
| t02-c0 | 720 | 19 | 15 | 0.0060717691 | 0.0060800256 | 0.0048548098 | 0.0063369827 | +0.0014821729 |
| t02-q0 | 720 | 43 | 31 | 0.0037268112 | 0.0037283347 | 0.0040120272 | 0.00061518038 | -0.0033968468 |
| t02-n2 | 720 | 54 | 48 | 0.0035327313 | 0.0035324942 | 0.0031439667 | 0.00064035247 | -0.0025036142 |
| t03-c0 | 720 | 3 | 2 | 0.0070809185 | 0.0071197778 | 0.00089248511 | 0.006431442 | +0.0055389569 |
| t03-q0 | 720 | 3 | 2 | 0.010065319 | 0.01010874 | 0.0012789857 | 0.0083637953 | +0.0070848096 |
| t03-n2 | 720 | 2 | 1 | 0.0055960606 | 0.0056523004 | 0.0067168662 | 0.0012935372 | -0.005423329 |
| t04-c0 | 720 | 41 | 32 | 0.0020257511 | 0.0020252377 | 0.0020275638 | 0.0026506049 | +0.00062304108 |
| t04-q0 | 720 | 44 | 38 | 0.0032731467 | 0.0032789654 | 0.0024669798 | 0.001363118 | -0.0011038618 |
| t04-n2 | 720 | 19 | 12 | 0.0070710376 | 0.0070696456 | 0.0029561393 | 0.0037147086 | +0.00075856928 |
| t05-c0 | 321 | 5 | 2 | 0.0011899297 | 0.001200385 | 0.0013751088 | 0.0025209856 | +0.0011458768 |
| t05-q0 | 720 | 6 | 2 | 0.0036286106 | 0.0036379647 | 0.0019219904 | 0.0014046507 | -0.00051733969 |
| t05-n2 | 720 | 2 | 1 | 0.0034799711 | 0.0034830087 | 0.0042001026 | 0.001405156 | -0.0027949466 |
| t06-c0 | 720 | 36 | 25 | 0.0033101298 | 0.003312745 | 0.0019629657 | 0.0041322 | +0.0021692343 |
| t06-q0 | 720 | 5 | 3 | 0.0074211666 | 0.0074298317 | 0.0032610324 | 0.0026868247 | -0.00057420772 |
| t06-n2 | 720 | 22 | 17 | 0.005008718 | 0.0050159407 | 0.0040339422 | 0.0010951033 | -0.0029388388 |
| t07-c0 | 720 | 39 | 25 | 0.0060414198 | 0.0060470651 | 0.0060435382 | 0.0030858199 | -0.0029577183 |
| t07-q0 | 720 | 20 | 13 | 0.013596519 | 0.01364947 | 0.01491549 | 0.0084323593 | -0.0064831308 |
| t07-n2 | 720 | 9 | 5 | 0.0030403729 | 0.0030513745 | 0.00036207298 | 0.0027174399 | +0.0023553669 |
| t08-c0 | 204 | 9 | 7 | 0.000831595 | 0.00083331427 | 0.00058867566 | 0.0015969918 | +0.0010083161 |
| t08-q0 | 114 | 2 | 1 | 0.0032551993 | 0.0032771835 | 0.0019491232 | 0.00046173161 | -0.0014873916 |
| t08-n2 | 114 | 2 | 1 | 0.0032551993 | 0.0032771835 | 0.0019491232 | 0.00046173161 | -0.0014873916 |
| t09-c0 | 720 | 16 | 11 | 0.0024044337 | 0.0023966467 | 0.0014306287 | 0.0023211147 | +0.00089048607 |
| t09-q0 | 720 | 7 | 3 | 0.0094945507 | 0.0094890528 | 0.010413184 | 0.0034819465 | -0.0069312377 |
| t09-n2 | 720 | 15 | 8 | 0.0053497617 | 0.0053532085 | 0.0040326429 | 0.0028775801 | -0.0011550628 |

## What is supported and what remains unknown

There is descriptive evidence of some temporally persistent selected-path error: the frozen, unfitted past-residual rule lowers equal-episode average prediction error for Q0 and N2. C0’s opposite direction and the per-cell reversals prevent treating this as a general correction. The current evidence is compatible with investigating a separately specified mechanism; it does not supply a tested pre-decision rule that identifies when correction is safe, prove a change in candidate selection, or justify deploying/advancing such a mechanism.

All 516 tracked prefixes have zero recorded sent-versus-decoded changed steps. Counts of sent components outside adapter-declared unit bounds are C0 1,435, Q0 1,067 and N2 839; these count stored commands only. They do not identify historical resolved controller clipping/scaling or a failure cause. No alternative clipped trajectory was computed.

The origin convention, BF16 storage, physical target identity, controller behavior, OFF-period errors, contact/grasp, normalized Stage inputs, unexecuted-candidate outcomes and eventual benefit of feedback remain unestablished. The task outcome/cost authority and N2 rejection are unchanged. A geometry prediction result is not a task-quality or counterfactual success result.

## Immutable inputs and reproduction

The JSON companion retains all 30 source paths/SHAs, existing-count dispositions, exact (unrounded) episode/arm aggregates, dtype counts, per-step support and partial-prefix records. It references only the completed derived reader output and frozen definition. To reproduce, verify its listed SHA references, take each `summary.abs_mse/disp_mse` from decisions with non-null `tracking`, take each `zero_mse/transported_mse` from `status=retrospective_predictive_check` pairs, average per episode, then average the ten episode means per arm. No original payload access is needed.

- `status.json`: `263f930a951ba98a540255a7d2ff469b37d812c268493aa713d2a1010574d13e`; `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-analysis/read-v1/status.json`
- `index.json`: `d0ed98c7b8dfd4c3c1fd1a584368b5b33a3ff91383dc0e6beb90d04f941fada7`; `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-analysis/read-v1/index.json`
- `inputs-and-source-hashes.json`: `b76e99c0d1985a93ce285c84f0068a04519f09973388082f7aac7aeba3395ba6`; `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-analysis/read-v1/inputs-and-source-hashes.json`
- `protocol-v1.md`: `62da94cd6917dc7f58e08bbc39fd56dc988743d13a8effde8e57c281fb26e23b`; `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-preparation-v1/source-v1/protocol-v1.md`
- `approved-draft-v1.md`: `abb6cf3d725a453397d49bc130d8889028bf59d86ca915abaff7ee48f2f9c539`; `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-preparation-v1/source-v1/approved-draft-v1.md`
- `read_selected_tracking.py`: `a33714747a47415c8a8d64ba3297a016550e95b6f54a174a1654875603deec26`; `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-preparation-v1/source-v1/read_selected_tracking.py`
- `freeze-v1.json`: `248c0e50154c1d0546929a0b7e5bd3368a800aeb86aa13dac8b9c42a06ae6e92`; `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-preparation-v1/source-v1/freeze-v1.json`

Companion JSON SHA256: `3cec485618c40b09faa11098384bf21207b15dbcfebee77d7e50a5d2637f1ab9`.
