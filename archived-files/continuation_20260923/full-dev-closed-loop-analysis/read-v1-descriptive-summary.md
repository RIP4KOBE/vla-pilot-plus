# Final Dev descriptive chronology

All30 accepted representatives, 30 fresh audits; CPU reader exit0, no outcome changes. Task0 had been exposed earlier. Matrix report remains outcome/cost authority and N2 remains rejected.

| Arm | Guided / actual actions | Coverage | OFF→ON events | Stage state match/mismatch/Unknown | First sent match/mismatch/Unknown | Last sent match/mismatch/Unknown |
|---|---:|---:|---:|---|---|---|
| C0 | 1600/6285 | 25.4574% | 48 | 201/0/0 | 201/0/0 | 160/41/0 |
| Q0 | 1480/6594 | 22.4446% | 34 | 193/0/0 | 193/0/0 | 150/43/0 |
| N2 | 1048/6594 | 15.8932% | 24 | 149/0/0 | 149/0/0 | 126/23/0 |

Every episode started ON and had an observed first OFF. Recorded Stage query status is ok for all543 events; no cap event is recorded, maximum count44 with limit50. State and command matches are telemetry association facts, not semantic Stage correctness.

| Cell | Success | Actions | Guided | First OFF | All OFF→ON steps | Last guided | Final OFF tail | Partial final chunk | Stage ok |
|---|---|---:|---:|---:|---|---:|---:|---|---:|
| t00-c0 | False | 720 | 232 | 24 | [72, 136, 200, 304, 400, 472, 544] | 575 | 144 | [] | 28 |
| t00-q0 | False | 720 | 416 | 16 | [112, 496, 536, 616, 680] | 711 | 8 | [] | 17 |
| t00-n2 | False | 720 | 24 | 24 | [] | 23 | 696 | [] | 5 |
| t01-c0 | False | 720 | 24 | 24 | [] | 23 | 696 | [] | 3 |
| t01-q0 | False | 720 | 24 | 24 | [] | 23 | 696 | [] | 11 |
| t01-n2 | False | 720 | 24 | 24 | [] | 23 | 696 | [] | 11 |
| t02-c0 | False | 720 | 152 | 32 | [152, 488, 576] | 591 | 128 | [] | 12 |
| t02-q0 | False | 720 | 344 | 24 | [56, 200, 344, 440, 464, 480, 496, 512, 528, 568, 600] | 631 | 88 | [] | 37 |
| t02-n2 | False | 720 | 432 | 16 | [112, 168, 192, 624, 704] | 719 | 0 | [] | 20 |
| t03-c0 | False | 720 | 24 | 24 | [] | 23 | 696 | [] | 3 |
| t03-q0 | False | 720 | 24 | 24 | [] | 23 | 696 | [] | 3 |
| t03-n2 | False | 720 | 16 | 16 | [] | 15 | 704 | [] | 3 |
| t04-c0 | False | 720 | 328 | 72 | [184, 248, 320, 368, 424, 480, 544, 640] | 719 | 0 | [] | 32 |
| t04-q0 | False | 720 | 352 | 24 | [176, 224, 320, 440, 664] | 719 | 0 | [] | 29 |
| t04-n2 | False | 720 | 152 | 24 | [232, 264, 344, 456, 616, 680] | 695 | 24 | [] | 26 |
| t05-c0 | True | 321 | 40 | 24 | [40, 136] | 143 | 177 | [1] | 17 |
| t05-q0 | False | 720 | 48 | 16 | [352, 368, 448] | 463 | 256 | [] | 26 |
| t05-n2 | False | 720 | 16 | 16 | [] | 15 | 704 | [] | 17 |
| t06-c0 | False | 720 | 288 | 40 | [48, 88, 192, 288, 336, 384, 456, 536, 608, 696] | 719 | 0 | [] | 34 |
| t06-q0 | False | 720 | 40 | 24 | [64] | 79 | 640 | [] | 6 |
| t06-n2 | False | 720 | 176 | 24 | [88, 216, 232, 336] | 447 | 272 | [] | 18 |
| t07-c0 | False | 720 | 312 | 24 | [64, 128, 184, 248, 328, 352, 392, 448, 488, 512, 560, 616, 672] | 679 | 40 | [] | 44 |
| t07-q0 | False | 720 | 160 | 24 | [104, 208, 360, 456, 600, 704] | 711 | 8 | [] | 28 |
| t07-n2 | False | 720 | 72 | 24 | [48, 104, 184] | 207 | 512 | [] | 13 |
| t08-c0 | True | 204 | 72 | 24 | [64] | 111 | 92 | [4] | 4 |
| t08-q0 | True | 114 | 16 | 16 | [] | 15 | 98 | [2] | 2 |
| t08-n2 | True | 114 | 16 | 16 | [] | 15 | 98 | [2] | 2 |
| t09-c0 | False | 720 | 128 | 32 | [88, 152, 296, 552] | 599 | 120 | [] | 24 |
| t09-q0 | False | 720 | 56 | 24 | [288, 376, 584] | 591 | 128 | [] | 34 |
| t09-n2 | False | 720 | 120 | 32 | [120, 208, 288, 440, 488, 608] | 631 | 88 | [] | 34 |

The four early-success final chunks executed1 action (t05-C0),4 (t08-C0),2 (t08-Q0),2 (t08-N2). They are retained; no episode is padded. All reset boundaries and full native-precision observations remain in each derived cell JSON.

- Step indices are zero-based actual action indices. Coverage denominator is actual executed actions, including partial final chunks.
- Aggregate coverage is summed guided actions / summed actual actions; early success lengths differ and this is not a standardized treatment effect.
- EEF motion origin uses previous contiguous post-action observation when available, otherwise the first post-action observation; gripper qpos origin remains first post-action observation. Command sign changes within runs exclude the run-entry boundary.
- Known state match means logged after-state agrees with the same-step decision, not correctness of the Stage semantic assessment. Exact gripper matches compare recorded value_used with actual sent first/last command; normalized Stage input is unobserved.
- State runs retain stage/provider/reset splits even when guidance does not change. No target geometry/projection/native ancestry was added.
- Guided-prefix/selection mechanisms can directly act only while guidance is enabled; unequal exposure is a concrete closed-loop boundary to study prospectively.
- Long OFF periods and fewer reactivations in N2 are descriptive, not demonstrated causes of failure. Task8 Q0/N2 succeeded with only16 guided actions; more sustained guidance is not established as necessary or sufficient.
- First sent command matches all543 recorded Stage values_used, whereas last differs in107 events. This identifies a precise input convention to review, not proof that changing it improves outcomes.
- No Stage query cap was reached in recorded streams (max44, limit50), and all recorded queries were ok. This does not validate replies or count hidden HTTP retries.
- No projection or tracking diagnostic was performed; any prospective mechanism requires a separately authorized test. N2 REJECT and matrix outcomes/cost authority remain unchanged.

Fresh-audit binding is in `read-v1-fresh-audit-bindings.json`. The completed provenance schema is `n2-dev-chronology-provenance-v1`; `input_hashes` maps every verified canonical input path (including original index and all bundles) to SHA256. Fresh audits use `qd-ed-decision-evidence-audit-v1`, name the exact episode/compute paths, and require this provenance binding for reuse. No new projection values were read for this summary.
