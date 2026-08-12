# Analysis — Run044 invalid task/seed identity incident

Classification: `INVALID_INFRASTRUCTURE_NO_SCIENTIFIC_OUTCOME`

The Run044 scientific matrix was not executed at its frozen identity. The runner
supplied task IDs `[7,5]` and aligned seeds `[87603,666847]`, but the LIBERO
backend enumerated the filtered task set as `[5,7]` while preserving seed-list
order. Live metadata therefore showed `(5,87603)` and `(7,666847)`, not the
frozen pairs `(7,87603)` and `(5,666847)`.

The discrepancy was detected during execution. The agent terminated only the
owned Run044 process group, verified GPU release, excluded all partial metrics,
videos and outcomes from algorithm evidence, and preserved IDs 91–94
append-only. Protocol v2 `5f94fd4` preceded runner repair `fd1a5f3`; the repair
now derives the seed schedule from task-sorted frozen pairs and its runner suite
passes 9/9, with 103/103 combined runner/audit regressions.

## Preserved evidence

- Original manifest: mode `0444`, file SHA
  `b6ae5091344aba325e1d5b698c8d19707e6aaf5aaef43ad5125721e423d1ff97`,
  payload `1f5374857469a8d00be00eb1562fcb8ed8b5b3d0ef11b3f3a08c1256a24773cf`.
- Final append-only ledger SHA:
  `447ac12776cc882024450d4e3a9166c46bd3318259ef574c90be5c7e43562371`;
  it contains IDs 91–94, the original dispatch, and one identity-abort event.
- Incident archive manifest: mode `0444`, file SHA
  `b22ace40178d355fc0146c35b3c9c9e7e2e8d1eb3798f26282ba0e64647d4661`,
  payload `5fc0cb554b7cce6965ac0f94a9562e39a88d5b680924731987e74517255e727f`.
- Archive: 15,938 files, 1,116,752,862 bytes, credential matches 0, under
  `run_044_protected_quality_lane_online_mechanism/incidents/invalid_task_seed_ids_91_94/`.
- Conservative owned-device wall from dispatch to terminal process evidence:
  approximately `0.28934` GPU-hours; cumulative approximately `5.73640/48`.

No effective online episode, task success/failure, target-gap movement or H5-v5
decision is claimed. Global reservations are now 94/143. Four exact recovery
cells are required, but the frozen v5 plan left only three recovery slots. The
repaired runner is ready, but further reservation/GPU/API/LIBERO execution is
unauthorized unless the user explicitly increases the cap from 143 to 144 for
the fourth exact recovery cell. Formal remains unauthorized; historical best and
gap remain 2/10 and 3.
