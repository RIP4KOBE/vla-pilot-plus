# Frozen single-episode result

Task 0, seed 1969522881. Original execution outcome: **completed**. Captured environment success (any / last): **False / False**. Last step truncated=True; 720 actual steps.

Evidence audit accepted=true, complete=true, errors=[]; 90 decisions, 52 guided and 38 unguided. CUDA remained uninitialized.

Frozen target identity exact matches: **0/52 projected decisions**; source text+path matches: 52. Eligible target-aware decisions: 0. A witnesses=None; B witnesses=None. Null means Unknown; zero eligible decisions cannot establish zero incidence or a negative result.

| Continuous diagnostic | n | median | min | max |
|---|---:|---:|---:|---:|
| eef_projection_rmse_m | 52 | 0.04528999973193432 | 0.009429752761836517 | 0.19592402666914738 |
| endpoint_projection_error_m | 52 | 0.06315689577322492 | 0.00828226431238422 | 0.24611155978654312 |
| projected_motion_tracking_gain | 52 | 0.28065806205635363 | 0.0056119002790592605 | 1.3005743768893416 |
| projected_t0_source_cast_error_m | 52 | 0.0003284301731893955 | 3.442445650879209e-05 | 0.0009246259318548966 |
| endpoint_precision_floor_m | 52 | 0.0012912470731648717 | 0.0009846363640687058 | 0.0028049632297548967 |

| Stage | Guidance | Decisions | Actual steps |
|---|---|---:|---:|
| 1 | True | 52 | 416 |
| 1 | False | 5 | 40 |
| 2 | False | 22 | 176 |
| 0 | False | 11 | 88 |

Identity triples and all observed wrapper identities/counts are preserved in interpretation-summary.json, along with the original frozen strata. No normalized code-structure SHA/co_flags/co_consts are recorded; those details remain Unknown. A shared source with different wrapper hashes is not treated as a new reward.

Gripper command patterns for projected decisions: `{"--------": 8, "+-------": 7, "++------": 4, "+++++++-": 2, "+++++---": 2, "++++++++": 26, "++++++--": 3}`. Positive/negative are actual postprocessed command signs only; physical grasp is Unknown.

Target distances, progress and tail-target changes remain Unknown wherever frozen identity did not match. Continuous EEF tracking errors alone do not prove a reward failure, collision, grasp failure, or benefit of an unexecuted candidate. This isolated row is not a paired or population performance conclusion. No frozen map, script, threshold, production file or ledger was changed.
