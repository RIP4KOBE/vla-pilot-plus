# N7 task3 first close opportunity: prospective same-state diagnostic

**Status: prepared, inactive, requires separate user approval under the execution specification §5.**
No simulator branch has been run under this scope. This is a diagnostic of an
already exposed Dev state, not a candidate evaluation, validation, or formal
acceptance attempt.

## Why this one state

In the GPU3 N11 matched Dev cohort, N7 failed task3 and N11 succeeded. At N7
task3 global step 16, N7's executed terminal candidate (index 7) had eight
open-gripper commands. Its same terminal pool included candidate index 6 with
eight close-gripper commands and a projected closest target distance of about
5.9 cm, but N5's relative-reach rule excluded index 6. N11's successful
trajectory selected an exact surviving close candidate at a different state,
with about 1.8 cm projected reach. Those episodes diverged before step 16, so
their outcomes do not tell us whether selecting N7's index 6 would have caused
contact, damage, or useful progress. The decision bundle and action identities
are frozen by `prepare_same_state.py` before execution.

## Fixed procedure and limits

1. Use the N7 task3 Dev source attempt identified in the manifest, task/seed
   `3/851784825`, init row 0. Keep its profile, RDT checkpoint, environment,
   perturbation, success predicate, and Stage record unchanged. Replay its
   **recorded first 16 executed actions** after each fresh reset. Before any
   branch, require exact agreement between all four replayed complete MuJoCo,
   controller, raw-observation, object-pose and contact snapshots, and require
   the step-15 EEF/gripper observation to match the original native record.
   Any mismatch yields `INFEASIBLE_STATE_RESTORE`; do not infer an effect.
2. At the restored step-16 state, execute two eight-action dry runs of the
   recorded N7 selected prefix, then one selected-prefix contrast run and one
   candidate-index-6 prefix. Require the two dry runs and selected contrast to
   match at every recorded state. If a branch reaches task success early, stop
   that branch; never continue an episode. Do not adapt the action choice from
   any diagnostic outcome.
3. The hard cap is **96 additional simulator action transitions**: four
   16-step replays plus four prefixes of at most eight steps. Four resets use
   five settling actions each (20 settling actions, cap 40). One diagnostic
   attempt is charged to the GPU3 development bucket; all GPU-process wall
   time counts, including failures. One GPU3 worker, at most 900 seconds plus
   40 seconds cleanup; no automatic retry. Validation/formal remain closed.
4. Record full state signatures, sent actions, EEF/gripper, relevant object
   poses and contacts at every branch step. Report objective contact and object
   displacement only if the simulator records identify the relevant bodies;
   otherwise report Unknown. Record the task predicate only as a diagnostic
   short-prefix observation. `official_task_success_rate` is null.

Interpretation is limited to **one exposed state and eight subsequent actions**.
If index 6 neither makes target contact nor useful physical progress, reject a
terminal-rule relaxation based on this evidence. If it does, a new QD–ED
candidate still needs its own prospective algorithm protocol and full matched
Dev gate; this diagnostic cannot promote any variant or tune the threshold.
