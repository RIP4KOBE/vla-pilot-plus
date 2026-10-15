# VLS completed-task live review

This independent watcher observes the frozen `vls-common-20261013` cohort every 30 seconds. It waits for one completed episode_compute record and one nonempty terminal agentview video, then runs the frozen task contract and VLS chunk/Stage-reference checks. Runtime/configuration/assets and raw cohort outputs are read-only. CUDA is hidden; no worker, provider or model is invoked.

Each task is reviewed once. `taskN-contract.json` is the offline contract output; `taskN-audit.json` includes actual gradient/RBF/FKD counters and Stage consumption checks. `summary.json` aggregates completed tasks only and explicitly does not grant final cohort acceptance. `watch_completed_tasks.py` is an external observer, not part of frozen runtime.

`stage_progress.reward_handoff_events` records Stage boundaries whose existing `reward_used_for_contact_handoff` flag is true. These are occasions when reward was available to the handoff logic, **not a count of newly entered contact-grace windows**. Likewise `fresh_diagnostic_boundaries` includes the initial guided boundary's zero progress before the first selected candidate. The frozen cross-boundary audit checks that initial zero and later cached progress separately. A recorded `contact_trigger` can persist after a prior trigger and must not alone be counted as a fresh transition.

Task outcomes come from completed compute plus the terminal video label and remain provisional until the full cohort audit passes. ESS skips and optimal zero gradients are legitimate algorithm outcomes. Missing or invalid evidence is preserved and reported; no episode is retried by this watcher.
