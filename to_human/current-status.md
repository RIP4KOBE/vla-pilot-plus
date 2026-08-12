# Current Status — Run034 Dev-A Valid Target Failure

- Project state: `running / run_034_dev_a_valid_target_fail_outer_reflection_pending`; algorithm and online execution are stopped.
- Primary target: LIBERO-PRO `libero_object_swap >=5/10` was not demonstrated. Historical formal best remains `2/10`, target gap 3, and formal episodes remain 0.
- Run034 paired outcome: control `0/6`, `qd_global_quality_anchor_v1` `0/6` on tasks `[0,1,2,4,6,7]`; delta 0; gained/retained/lost tasks are all empty.
- All twelve episodes were valid and exited 0. Every task failure is conservatively classified `timeout without completion`; no finer unsupported cause is claimed.
- Target gates failed: candidate `0 < 3/6` and improvement `0 < +1`. Audit SHA `2e590656…0e68` contains only those two hard failures.
- Mechanism gates passed: 106 candidate records, 1,060 anchor activations, 425 real rescues, exact `1+15` allocation and `176 search / 176 QD / 11 calls` throughout. Rescue activity did not transfer to a task success.
- Safety/accounting/credential gates passed; latency ratio is `1.052894 <= 1.25`. Latest approved credential exact matches are zero in the complete Run034 artifact tree and tracked worktree.
- Immutable manifest SHA is `206911d7…01f`; exact attempt IDs 79–90 ran after admission on GPUs 2/4. No recovery was required.
- Accounting: 66 effective online episodes, 90/143 global reservations, 6/19 recovery slots consumed, `5.447063/48 GPU-hours`, formal episodes 0.
- Frozen stop rule applies: no validation, formal evaluation, fourth candidate, anchor-count/sparse-ratio/threshold sweep, or Run034-driven tuning is authorized.
- Next action: commit the Run034 result, then freeze an outer-loop conclusion protocol before creating the v3 decision manifest and final report. This next action authorizes documentation only, not algorithm or online execution.
- Full append-only record: `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`.
- Protected untracked design remains untouched, unstaged, and uncommitted.
