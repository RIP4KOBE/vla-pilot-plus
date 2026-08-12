# Current Status — V3 Concluded, Target Not Met

- Project state: `concluded_no_adoption_v3_target_not_met`. Algorithm and online execution are stopped.
- Primary target `libero_object_swap >=5/10` was not demonstrated. Historical formal EDS-QD best remains `2/10`, target gap 3, and formal episodes remain 0.
- V3 candidate: one global-quality archive parent plus 15 unchanged sparse-QD parents at fixed `176 search / 176 QD / 11 calls`.
- Run033: control `0/3`, candidate `1/3`; gained task 9, lost none.
- Run034 frozen Dev-A: control `0/6`, candidate `0/6`; delta 0; gained/retained/lost all empty. Candidate failed both `>=3/6` and `>=+1` gates.
- Mechanism remained active in Run034—106 records, 1,060 activations and 425 rescues—but produced no task completion. Allocation rescue is not a success surrogate.
- All Run034 validity, safety, compute, latency, artifact, attempt and credential gates passed. Audit SHA is `2e590656…0e68`; its only hard failures are the two task-success gates.
- Final accounting: 66 effective online episodes, 90/143 reservations, 6/19 recovery slots consumed, `5.447063/48 GPU-hours`, validation 0, formal 0.
- Frozen decision: `CONCLUDE_NO_ADOPTION_WITHIN_V3_CYCLE_TARGET_NOT_MET`.
- Immutable decision manifest: mode 0444, SHA `5363af69…75a8`.
- No validation, formal evaluation, fourth candidate or Run034-driven tuning is authorized. Any future execution requires a new versioned design, leakage-safe splits, explicit budget and explicit user approval.
- Final report: `docs/03_evidence/eds_qd_autoresearch/2026-08-12-eds-qd-autoresearch-v3-final-report.md`.
- Full append-only record: `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`.
- Protected untracked design remains untouched, unstaged and uncommitted.
