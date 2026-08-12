# EDS-QD Autoresearch v2 Final Report

Date: 2026-08-12
Decision: `CONCLUDE_NO_ADOPTION_WITHIN_V2_CYCLE_REQUEST_VERSIONED_REDESIGN`

## Outcome

The v2 H2 candidate did not advance toward the required LIBERO-PRO `libero_object_swap` target of `>=5/10`. In the frozen Run023 online mechanism matrix, contemporaneous EDS control scored `1/3` by succeeding task 9, while the candidate scored `0/3` and lost task 9. Formal evaluation was neither authorized nor run. Historical formal best remains `2/10`, leaving target gap 3.

Run023's sole audit hard failure was `candidate missing fallback record`. The candidate's exact-degenerate guard never activated: all 74 chunks had strictly positive reward spread and used active QD. Tasks 2/3/9 contained `21/50/3` active chunks and zero fallback chunks. This prospectively refutes the routing predicate despite Run020's retrospective exact-zero prevalence and Run021/022's valid offline identity proofs.

## Task and gate results

| Profile | Task 2 | Task 3 | Task 9 | Total |
| --- | --- | --- | --- | --- |
| EDS control | fail | fail | success | 1/3 |
| H2 candidate | fail | fail | fail | 0/3 |

All failed episodes are conservatively labeled `timeout without completion`. The candidate's proxy behavior did not justify promotion: QD remained active, post-envelope overflow was zero, and latency/accounting were clean, yet control-success retention regressed.

All non-mechanism hard gates passed:

- both jobs valid, exit code 0, exact task/seed/config/code/checkpoint bindings;
- control chunks `176 search / 0 QD / 11 calls`;
- candidate chunks `176 search / 176 QD / 11 calls`;
- no safety, nonfinite, mask, qpos, accounting, monotonicity, selection, Stage/service, artifact, or credential failure;
- candidate/control selection-latency P95 ratio `1.001266`, within `1.25x`;
- 3/3 metadata and videos per job.

## Cross-cycle conclusion

H1 established that causal-envelope partitioning improves descriptor resolution, but its validation candidate reached only `1/10`. H2 established an offline exact-equality failure mode, but its prospective switch never activated and active QD lost task 9. Neither cycle reduced the historical formal gap.

The evidence now points beyond partition saturation and exact-zero routing: reward/fingerprint QD quality and final selection remain poorly aligned with task completion and control-success retention. A plausible next direction is observation-derived stage-progress quality/final selection or a guarded control-retention mechanism, still entirely inside EDS+QD. It is only a redesign proposal; no threshold relaxation or second v2 candidate is authorized.

## Accounting and integrity

- Effective online episodes across cycles: `48`.
- Global reservations: `66/143`; Run023 IDs 55–60 are immutable void pre-dispatch records and IDs 61–66 are valid exact-cell recovery records.
- Cumulative GPU usage: `3.747101/48` hours.
- Formal episodes: `0`.
- Run023 audit SHA-256: `7f123ecdf3ffb7fbbb881ffebe197ddb2ae8e4b1237233dd2316f6f67e832c54`.
- V2 cycle decision manifest SHA-256: `4010b620976ee8aa26ee05e6655a60c6ec4bc194511698254e9b2eb0bf9f1334`, mode `0444`.
- Credential scan: zero matches; no value or reversible fingerprint recorded.
- Protected untracked design remained untouched and excluded.

## Continuation boundary

Further algorithm execution requires a versioned design, new leakage-safe holdout seeds, an explicit remaining budget, and explicit user approval. Run023 outcomes cannot be reused for same-cycle tolerance tuning. Until that boundary is approved, Dev-A/B, validation, and formal remain disabled.

The full chronological record is in `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`; detailed Run023 analysis is in `experiments/run_023_reward_degenerate_online_mechanism/analysis.md`.
