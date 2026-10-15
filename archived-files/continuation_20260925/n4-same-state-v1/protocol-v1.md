# N4 first-decision same-state diagnostic — frozen scope

Authorized by the user's September 25 reply, “批准上述限定诊断”, to the
bounded scope in `continuation_20260924/n4-e1-dev-v1/same-state-diagnostic-scope-draft-v1.md`.
This is one new diagnostic attempt, not a retry or a formal success observation.

- Re-execute the frozen N4-E1 task-9 Dev condition only: env and policy seed
  `1045350852`, init index `0`, init-row SHA256
  `d8309b31899377d1051f6d7da47edc747b294842a6fec748aff6c9b822d8797e`.
  Preserve all prior N4-E1 records. The first guided decision uses the existing
  N4 terminal-population winner and its simultaneous archive-global-best reference.
- Decode each choice to its eight action commands by the existing LIBERO decoder
  and adapter postprocessor. If commands match exactly, report
  `NO_SELECTION_CONTRAST` without executing a diagnostic action.
- Use the same environment with fresh resets to the frozen init row. Record the
  complete initial-state signature, execute two selected-prefix parity dry runs,
  compare every resulting state exactly, reset again, then execute one selected
  and one archive-reference prefix. Any failed initial or parity check reports
  `INFEASIBLE_STATE_RESTORE`; it cannot support an action-effect conclusion.
  A parity mismatch after branch 1 invalidates that branch and suppresses the
  reference branch.
- Stop each prefix at eight commands or task success. The diagnostic action
  transition counter is capped at **32**; four resets including the ordinary
  Main initial reset each use the frozen `num_steps_wait=5`, so the expected
  settling count is **20**, with a hard protocol ceiling of **40**. There is
  one model decision, at most two contrast branches, and no episode continuation.
- Save MuJoCo state, raw observation hashes, available controller state,
  step/time counters, task success predicate, source/basket pose, EEF/gripper
  state, contacts, and sent actions. Privileged state is diagnostic output only.
  Report unknown fields as unknown; never infer contact from video.
- GPU3 only (UUID `GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315`), exclusive
  owned process, same Codex managed-login provider condition, 1800-second
  process cap plus 40-second cleanup. Charge one development attempt and all
  process wall time against the independent N4 240-attempt/48-GPU-hour budget.
  Validation and formal allocations remain closed. No automatic retry.

`result.json` is diagnostic only: it has a null official task success rate.
It cannot promote N4, modify its 1/4 Dev result, or select an N5 by itself.
