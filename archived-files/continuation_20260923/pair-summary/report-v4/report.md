# Four observed Dev episodes — descriptive summary

Status: closed_incomplete_comparison; complete-valid 3/4, terminal-invalid 1/4, pending 0/4.

| Task | Arm | Status | Original task success (raw) | Audit | Eligible decisions (descriptive) | A episode presence | B episode presence | GPU wall seconds |
|---|---|---|---|---|---|---|---|---|
| 0 | C0/P2 | complete | false | accepted (not success) | 0 | Unknown | Unknown | 1062.548624721001 |
| 0 | Q0 | complete | false | accepted (not success) | 0 | Unknown | Unknown | 786.957195125 |
| 5 | C0/P2 | complete | false | accepted (not success) | 0 | Unknown | Unknown | 731.7467109850004 |
| 5 | Q0 | terminal-invalid | false | not admitted | Unknown | Unknown | Unknown | 1046.0592467280003 |

A = the frozen analyzer’s eligible full-prefix joint step7→8 regression witness. B = its eligible projection-response witness. No eligible prefix means Unknown, not a negative finding.

observed_pairs_t05_q0_20260923: original event=valid, outcome_valid=false, task_failure=True; reason: Codex Stage call failure invalidates the frozen transport condition. The raw task outcome remains recorded; this row is ineligible for the frozen comparison. No A/B analysis is supplied.

Task 0 pair: closed_incomplete_comparison.

Task 5 pair: closed_incomplete_comparison.

Complete-valid GPU wall time: 2581.2525308310014 seconds; terminal-invalid GPU wall time: 1046.0592467280003 seconds; total explicitly recorded terminal cost: 3627.3117775590017 seconds. This is not the study's total budget/cost.

Four planned episodes across two paired tasks do not establish improved success rate or causal effect. Decisions/chunks are correlated within an episode, not independent samples. No p-values, automatic promotion, unexecuted outcome labels, or pooling with observer=false/external GPU2.

Input JSON SHA bindings and frozen analyzer/auditor hashes are preserved in summary.json. The summary does not reopen tensor bundles or turn audit acceptance into task success. Missing inputs remain pending; explicit invalid terminals close without restoring comparison eligibility. No algorithm or promotion decision is made.
