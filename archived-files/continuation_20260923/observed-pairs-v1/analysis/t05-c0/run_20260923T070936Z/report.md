# Frozen single-episode result

Task 5, seed 970869399. Original execution outcome: **completed**. Captured environment success (any / last): **False / False**. Last step truncated=True; 720 actual steps.

Evidence audit accepted=true, complete=true, errors=[]; 90 decisions, 12 guided and 78 unguided. CUDA remained uninitialized.

Frozen target identity exact matches: **0/12 projected decisions**; source text+path matches: 12. Eligible target-aware decisions: 0. A witnesses=None; B witnesses=None. Null means Unknown; zero eligible decisions cannot establish zero incidence or a negative result.

| Continuous diagnostic | n | median | min | max |
|---|---:|---:|---:|---:|
| eef_projection_rmse_m | 12 | 0.049744263740356884 | 0.013646017085618986 | 0.0904248179628008 |
| endpoint_projection_error_m | 12 | 0.06999746884241091 | 0.022935202601980724 | 0.10076192642974965 |
| projected_motion_tracking_gain | 12 | 0.5600475505827089 | 0.014966547080517995 | 1.1366611166056628 |
| projected_t0_source_cast_error_m | 12 | 0.0003802583099663407 | 0.00011679949338312943 | 0.0007833392841037238 |
| endpoint_precision_floor_m | 12 | 0.0016914568667664815 | 0.0010358019490037315 | 0.002027985341532733 |

| Stage | Guidance | Decisions | Actual steps |
|---|---|---:|---:|
| 1 | True | 12 | 96 |
| 1 | False | 55 | 440 |
| 2 | False | 23 | 184 |

Identity triples and all observed wrapper identities/counts are preserved in interpretation-summary.json, along with the original frozen strata. No normalized code-structure SHA/co_flags/co_consts are recorded; those details remain Unknown. A shared source with different wrapper hashes is not treated as a new reward.

Gripper command patterns for projected decisions: `{"--------": 9, "-----+++": 1, "++++++++": 1, "+++-----": 1}`. Positive/negative are actual postprocessed command signs only; physical grasp is Unknown.

Target distances, progress and tail-target changes remain Unknown wherever frozen identity did not match. Continuous EEF tracking errors alone do not prove a reward failure, collision, grasp failure, or benefit of an unexecuted candidate. This isolated row is not a paired or population performance conclusion. No frozen map, script, threshold, production file or ledger was changed.
