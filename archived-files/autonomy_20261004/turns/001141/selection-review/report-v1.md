**PASS — bounded ordinary-selection plausibility only.** The registered detour has a credible route through unchanged selection in the three task-0 packets. The three task-6 detours fail the first archive update. Actual prospective archive survival is **UNKNOWN**. This review authorizes neither GPU work nor implementation adoption and is not task success or scientific promotion.

Frozen owning source: `52a87af0bf11f95b21ce17aba456dc98944d9774`. Authority SHA-256: `0fdf745dbecd4218c0c1268b7f8ee10bdb0b149535daba263790fc59ea387416`. All supplied direct reference hashes, the specified ledger prefix, bound packet files, provider text and inspected owning-source blobs matched. The authority itself had no externally supplied expected digest. Source/input/script hashes and complete numeric details are in [report-v1.json](report-v1.json) and [replay-results-v5.json](replay-results-v5.json).

The review independently inspected source and replayed only the six eligible next-decision packets: task 0 at 696/704/712 and task 6 at 568/576/584. It uses each first opportunity (iteration 0, slot 15), the same template selected by feasibility.py, and the exact registered detour arithmetic with clipping followed by one native bf16 cast. Direct proposals were regenerated with frozen N34 code and matched the recorded candidate bytes. No trigger/encoding gate or broad N35 diagnosis was repeated.

**Scoring semantics and native arithmetic.** The hash-bound provider scores negative weighted squared Euclidean target distance. EDS passes trajectory indices `1:8`: positions after actions 1–7, with weights `[1,1,1,1,3,3,3]/13`. The eighth endpoint is excluded from quality but determines the target-relative XY descriptor. Native bf16 scoring keypoints differ from the raw binary64 geometry packet. The projection uses native action channels, a cast origin, multiplication by 0.01, cumulative sums and position addition. It performs no actuator clipping; only the registered proposal commands are clipped before encoding. The loader wrapper leaves scalar-created weights in float32, then the frozen scorer casts the aggregate back to bf16.

Unmodified CPU execution of the frozen projection failed exact control comparison in all 12 batches (maximum batch quality differences from 0.0000152587890625 to 0.00006103515625). The source dependency `torch/include/ATen/native/cuda/ScanUtils.cuh`, lines 270–283 and 446–471, selects sequential `scalar_t` accumulation for this 8x3, dim-0 scan. A CPU reference using that accumulation reproduced **192/192 recorded projections, provider scores and descriptors**. The unchanged provider also reproduced 192/192 scores when given stored projections. All six recorded archive-update control maps matched.

The following are exact bf16-representable **CPU native-reference values under that source-backed accumulation model**. Direct and template values additionally equal the recorded qualities. Detour values are reconstructed, not observed N36 runtime scores. The packets do not attest the historical CUDA binary; no claim of newly measured deployed detour scores is made.

| Task / step | Detour reference | Direct (also recorded) | Template (also recorded) | Detour − direct | Detour − template |
|---|---:|---:|---:|---:|---:|
| 0 / 696 | -7.915496826171875e-05 | -3.695487976074219e-05 | -0.00081634521484375 | -4.220008850097656e-05 | 0.0007371902465820312 |
| 0 / 704 | -7.867813110351562e-05 | -3.695487976074219e-05 | -0.0006103515625 | -4.172325134277344e-05 | 0.0005316734313964844 |
| 0 / 712 | -7.867813110351562e-05 | -3.695487976074219e-05 | -0.0003204345703125 | -4.172325134277344e-05 | 0.00024175643920898438 |
| 6 / 568 | -0.0006866455078125 | -0.0002460479736328125 | -0.00089263916015625 | -0.0004405975341796875 | 0.00020599365234375 |
| 6 / 576 | -0.00069427490234375 | -0.0002460479736328125 | -0.000644683837890625 | -0.0004482269287109375 | -4.9591064453125e-05 |
| 6 / 584 | -0.000701904296875 | -0.0002460479736328125 | -0.0003871917724609375 | -0.0004558563232421875 | -0.0003147125244140625 |

Detour and direct occupy the same cell in every packet, with strictly different qualities: no native score tie rescues the detour. In task 0, native endpoints coincide. Task-6 endpoint z differences are +0.00048828125, +0.000244140625 and −0.00048828125 m; their XY descriptors still coincide. Clipping and native arithmetic were applied explicitly rather than assuming exact tangent cancellation.

**Ordinary archive competition.** The frozen archive keeps one elite per 4x4 cell. It chooses the higher quality, then the lexicographically smaller full-action fingerprint on ties. Final selection uses highest archive quality, then fingerprint, then cell. Fingerprints hash the entire action after canonical little-endian float32 conversion. Fixed-initial bounds, edge clamping, sparse-priority parent sampling, no secondary lane and no global-quality anchor remain unchanged.

The direct approach is the matched alternative in the replacement slot; it is not a mandatory extra competitor. Each conditional update preserves the recorded initial archive and all 15 ordinary offspring, replaces slot 15 with the detour, then calls the unchanged QDArchive implementation. This preserves the first offspring because insertion follows their rollout. It does not freeze later offspring or force selection.

| Task / step | Detour cell | Margin over best same-cell incumbent/ordinary offspring | Retained after first update | Global best after first update |
|---|---:|---:|---|---|
| 0 / 696 | 9 | 0.00026988983154296875 | Yes | Yes |
| 0 / 704 | 5 | 0.0017142295837402344 | Yes | Yes |
| 0 / 712 | 5 | 0.00024175643920898438 | Yes | Yes |
| 6 / 568 | 4 | -0.00016021728515625 | No | No |
| 6 / 576 | 4 | -0.000286102294921875 | No | No |
| 6 / 584 | 4 | -0.0003147125244140625 | No | No |

The three positive task-0 margins establish credible initial selection plausibility despite the direct-approach penalty. The task-6 failures show that an improvement over the template alone is insufficient: at step 568, the detour beats its template but still loses to an ordinary offspring in its cell. If direct approach is present in the same cell at any update, it strictly beats the matched detour in all six packets.

**Limits and missing evidence.** These are three overlapping packets from each of two tasks, not six independent experiments or an estimate of survival probability. The result covers the first insertion only. Changed archive contents can change future parent allocation and denoising, so recorded later rounds cannot establish a counterfactual N36 final archive. Missing evidence is the actual later N36 populations/archives and final selection, runtime scoring of the new candidate on an attested backend, selected/decode/acknowledgement linkage, physical response, actual capture entry and fresh matched task outcomes. None was fabricated or requested through prohibited work. The registered lifecycle and hypothesis were not revised.

The historical CUDA binary is not hash-attested here. Source inspection plus all 192 exact controls supports a bounded native-reference calculation; it does not certify bitwise behavior on every unseen candidate or an implementation that has not been adopted. Consequently this PASS is for scientific plausibility of ordinary selection, not a completed prospective survival audit.

**Preserved failures and audit trail.** [replay-v1.log](replay-v1.log) retains the initial `QDBounds` missing-checksum exception. Version 2 fixed that analysis-only constructor use and exposed the CPU/backend discrepancy. [arithmetic-diagnostic-results-v1.json](arithmetic-diagnostic-results-v1.json) and replay versions 2–4 preserve the intermediate arithmetic evidence; their default-CPU scores are superseded by the explicitly labeled native-reference comparisons. [replay-v5.py](replay-v5.py) is the final bounded script; all artifacts and source dependencies are hashed in the JSON report. The existing prior root failure records were left untouched; this review made no delegation attempt.

All analysis ran on CPU with `CUDA_VISIBLE_DEVICES=""`, Torch intra/inter-op threads 1 and OMP/MKL/OpenBLAS threads 1. No source edits, commits, worktrees, state/ledger/tree changes, resource reservations, simulator episodes, protected data, external messages, credentials, alternate providers or forbidden design document were used. All created files are confined to the authorized selection-review directory. No GPU release, implementation adoption or promotion follows from this PASS.
