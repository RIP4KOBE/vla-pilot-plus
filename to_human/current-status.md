# Current Status — Run033 PASS, Dev-A Protocol Authorized

- Project state: `running / run_033_online_mechanism_pass_dev_a_protocol_authorized`.
- Primary target: LIBERO-PRO `libero_object_swap >=5/10`; it has not yet been demonstrated. Historical formal best/gap remain `2/10 / 3`; formal episodes remain 0.
- Run033 paired outcome: control `0/3`, `qd_global_quality_anchor_v1` `1/3`; gained task `[9]`, lost tasks `[]`, direct delta `+1`.
- Failures: both profiles timed out without completion on tasks 3/8; control also timed out on task 9. Candidate completed task 9. No unsupported finer behavioral label is claimed.
- Mechanism: 110 candidate records, 1,100 anchor activations and 751 real rescues; all records preserved the frozen 1+15 allocation and `176 search / 176 QD / 11 calls`.
- Interpretation: 738 rescues across failed tasks 3/8 show rescue frequency is not a success proxy. Promotion is based on the task-9 gain and zero retention loss, not on maximizing rescue count.
- Hard gates: safety/accounting/final-selection/credential gates all passed; latency ratio `1.060499 <= 1.25`; immutable audit SHA `b5f4c671…f96b` has zero hard failures.
- Infrastructure: IDs 67–72 are preserved pre-episode DINO-cache failures. Protocol-first runner repair reused the audited offline cache; exact-cell science used IDs 73–78 after fresh health/admission on GPUs 2/4.
- Accounting: 54 effective online episodes, 78/143 global reservations, 6/19 recovery slots consumed, `4.183103/48 GPU-hours`, formal episodes 0.
- Credential integrity: latest approved credential exact matches are zero in the full Run033 artifact tree and tracked worktree. It was injected only into child process environment.
- Next gate: commit a Dev-A protocol before any runner change or reservation. Frozen paired tasks/seeds are `[0,1,2,4,6,7] / [307995,262892,731741,14859,648306,960581]`; candidate must reach `>=3/6`, beat control by at least 1, lose no control-success task, and pass unchanged hard gates.
- A valid Dev-A failure ends v3 without validation/formal. A PASS authorizes validation protocol only.
- Full append-only record: `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`.
- Protected untracked design remains untouched, unstaged, and uncommitted.
