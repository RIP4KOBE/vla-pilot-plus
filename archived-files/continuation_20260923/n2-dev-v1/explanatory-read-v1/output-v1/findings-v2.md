# Task0 post-outcome sequence findings

This is descriptive Dev exploration of exactly the three authorized, completed task0 arms. It does not change N2, the ongoing cohort or any acceptance rule. All three fresh frozen-source audits accepted complete evidence; each has 90 decisions and 720 actions. All three original outcomes are condition-valid task failures, with the last action returning terminated=false, truncated=true, success=false. CPU only; CUDA remained uninitialized. No model/provider/projector/simulator call, target map, image, free-text Stage reply, invalid attempt or other episode was used.

The data do **not** show an initially earlier N2 guidance cutoff. The first ON-to-OFF boundary is N2 step 24, C0 step 24, and Q0 step 16. The difference is subsequent reactivation: N2 0, C0 7, Q0 5. N2 stays OFF for the remaining 696 actions. At each arm's first OFF, the structured log records “reward rose above 80%”, a successful Stage query, Stage 1 retained and guidance=false; no actual normalized reward value is recorded. Later states and queries have diverged, so this chronology does not establish that keeping guidance on would improve the outcome.

| Arm | All OFF-to-ON boundaries | Last guided action | Successful queries / limit |
|---|---|---:|---:|
| C0 | [72, 136, 200, 304, 400, 472, 544] | 575 | 28 / 50 |
| Q0 | [112, 496, 536, 616, 680] | 711 | 17 / 50 |
| N2 | [] | 23 | 5 / 50 |

N2's five structured queries are at steps 24, 32, 144, 584, 592, all successful. Stage stays 1 at 24, then becomes 2, 0, 2, 0, respectively; guidance remains false after the first query. There is no logged skipped/failed query or limit exhaustion. Between boundaries, lack of a trigger event is not a new decision or failed query. The source uses reward triggers only while guidance is on, alongside boundary gripper-change triggers; this source rule and the observed no-reactivation sequence are separate from any causal explanation of failure.

After N2 goes OFF, the EEF continues moving; it does not stop at the guidance boundary. Using the actual post-action observation at step 23 as the origin, and all contiguous action responses 24–719:

- EEF start [-0.1214705989047193, 0.07669173491483641, 0.08113564616185852]; end [0.09289259908015819, 0.2950918527823514, 0.333611217797917]. Net displacement **0.396729 m**; accumulated path **1.167951 m** over 696 consecutive observed edges. These are spatial displacements, not target progress.
- Command sign changes: 11. Finger qpos at first/last post-OFF observations: [0.040616013532486735, -0.03909246948881644] / [0.03962366333992466, -0.040014993865858044]. Command signs and finger movement do not establish capture/contact.
- The full report retains every Stage/guidance run and its motion. Notably, N2 steps 144–583 are Stage 0/OFF: EEF path 0.447414 m and net 0.116862 m, with negative gripper commands through step 575, a positive two-action interval at 576–577, then negative again. At 584, the logged Stage gripper input is positive even though the previous chunk's last command is negative. This agrees with the source's use of the previous chunk's first command at a fresh boundary; it is not a reconstructed physical gripper event.

All selected guided candidates have unambiguous native-content raw/internal quality associations: C0 29/29, Q0 52/52, N2 3/3. Unguided scores remain Unknown. N2's actual selected scalars are:

| Decision step | Original raw provider quality | Internal Q8 | Selected raw gap to same-final-pool raw best |
|---:|---:|---:|---:|
| 0 | -0.00927734375 | -0.0084228515625 | -0.0009765625 |
| 8 | -0.002777099609375 | -0.0028839111328125 | 0.0 |
| 16 | -0.000457763671875 | -0.000621795654296875 | 0.0 |

No Q8/raw magnitude substitution is made. The earlier checkpoint's step-0 raw tradeoff is retained; this report does not turn selection activity into performance evidence. Actual normalized Stage inputs, unexecuted outcomes and unique archive insertion ancestry remain Unknown.

Keypoints remain available at all 90 decision boundaries in each arm, with 12 points and 89 adjacent same-index links. The following is a complete index-level description for N2 from boundary 0 to 712 (no target/object name is assigned):

| Recorded index | Net displacement (m) | Sampled path (m) |
|---:|---:|---:|
| 0 | 0.310128527 | 0.700858872 |
| 1 | 0.059577431 | 0.236470211 |
| 2 | 0.013453645 | 0.159905183 |
| 3 | 0.017834635 | 0.096880697 |
| 4 | 0.029253578 | 0.202472963 |
| 5 | 0.020187241 | 0.020187241 |
| 6 | 0.020190828 | 0.020190828 |
| 7 | 0.000000001 | 0.000000001 |
| 8 | 0.002500948 | 0.002500948 |
| 9 | 0.002501515 | 0.002501515 |
| 10 | 0.000000000 | 0.000000000 |
| 11 | 0.000000056 | 0.000000056 |

These keypoint coordinates change, but the collector does not record object attachment continuity, background membership or tracker fallback status. They cannot independently prove real object motion, grasp, release or current target progress. Per-step object pose/contact is absent. All target-relative quantities are Unknown because no map was supplied. Optional selected-projection tracking diagnostics were deliberately not evaluated; no projection was recomputed.

`inputs-and-audit.json` contains the complete source/input hash manifest and all three admission/fresh-audit records; `closed-loop-sequence.json` retains full allowlisted Stage events, decision contexts, pre-reset actions/observations, keypoints and native selected-quality joins. `comparison.md` lists every actual state run. `descriptive-extract-v1.json` is derived only from the saved sequence and records this formatter and input hashes. Original source, protocol, terminal results and audit files are unchanged. No new threshold or causal/performance gate was introduced.

Additional existing-output join requested by root: all 50 Stage events agree with the same-step actual decision context's stage/guidance state. Logged `gripper_value_used` matches the previous chunk's first **sent** gripper command in C0 28/28, Q0 17/17 and N2 5/5 events. It differs from that previous chunk's last sent gripper command in C0 7/28, Q0 7/17 and N2 1/5 (N2 step 584). Full event joins and mismatch steps are in `stage-gripper-associations-v1.json`. These are exact recorded-value comparisons; they neither reconstruct an alternative trigger nor show that a Stage reply was wrong. Trigger priority can hide other simultaneous predicates, and normalized reward inputs remain unobserved.

The initial episode pre-action EEF observation is not in this actual-only motion summary; the first run therefore starts at the first post-action observation and omits that first action's displacement. The complete post-OFF summary has the observed step-23 origin and all 696 consecutive response edges. N2 Stage-0/OFF runs cover 440 actions at 144–583 and 128 actions at 592–719. Neither interval is labeled as a grasp state or a motion-failure category.
