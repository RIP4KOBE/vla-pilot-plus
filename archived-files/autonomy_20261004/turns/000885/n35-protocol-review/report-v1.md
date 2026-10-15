# N35 v2 bounded correction review

**PASS — B1 and B2 resolved.** Ready for separately authorized isolated CPU implementation only. This report grants no implementation, GPU, validation/formal release or scientific promotion. No efficacy is established.

## Corrected accounting

- B1: `min(224, 53.08404692669838 + 168) = 221.08404692669838` GPU-hours in decimal arithmetic. The stored float `221.08404692669836` is consistent rounding. Both caps are explicit in future admission.
- B2: retained attempt hours `69.99568238388729` plus separate healthchecks `0.23357169027961985` conservatively total `70.2292540741669`. Adding the full 21-hour cohort gives `91.2292540741669`.
- Protected validation/formal remainder: `24.240824002430816 + 12` hours. Remaining unprotected headroom after the cohort: `93.61396885010065` hours. No protected borrowing.
- Forty cells × (1800 + 40) seconds = `20.444444444444443` hours; plus 0.5 hours for future healthchecks stays below 21 by 200 seconds. Attempts: `474 + 40 = 514`, leaving 1286; baseline/development become 105/322.

## Science unchanged

Exact JSON comparison found changes only to `schema`, `at`, `review_status`, `accounting`, `admission`, and added `supersedes`. Admission retains the previous text and adds accounting enforcement. Episodes, scientific contract, decision gates, audits, limits, deadline, STOP path and release steps are unchanged. The bound hypothesis, CPU root review and completion contract remain consistent.

- **Scientific falsifiability — PASS:** Discrete one-boundary intervention can fail, remain ineligible or worsen audited task success. Native feasibility, jaw motion and historical observations are explicitly not efficacy. Reused Dev identities mean fresh executions, not unseen-task generalization.
- **Frozen CPU gate and lifecycle — PASS:** Bound root review accepts only native feasibility. Immediately preceding guided chunk, eight positive identity-linked executed commands, same target/Stage/tracker continuity and strictly decreasing finite jaw separation remain required. Missing trigger evidence suppresses eligibility; no task6 threshold relaxation.
- **Origin and aliases — PASS:** Direct native occurrence/content identity is required; ancestry or hash equality alone cannot establish the selected origin. Memory-origin and ambiguous equal-content origins must never rearm. Required occurrence telemetry failure invalidates execution, distinct from an observed ineligible trigger.
- **Ten-round latch — PASS:** Consume once on next boundary entry, immutable latch for ten existing parent rounds, current archive best each round, expire at boundary end independent of selection. Episode/target/Stage changes, unguided operation, incomplete execution, selection failure and exceptions reset.
- **Native versus decoded equality — PASS:** First-round task6 template already decodes close. Native nonidentity meets the frozen feasibility gate only; neither decoded novelty nor benefit follows. Future reporting must retain zero decoded-delta cases.
- **Controls and identities — PASS:** 40 unique Dev cells in exact task-major C0/Q0/N34/N35 order; 10 baseline and 30 development. All identity fields match origin and Dev seed plan. Fresh controls, same source/runtime/Stage, unchanged 16 candidates, ten rounds and scoring/model budgets. N34 memory disabled; N35 fallback retains N34.
- **Necessary gate and promotion — PASS:** All 40 valid, N35 at least 5/10 and at least each control are necessary only. Never-triggered or unauditable mechanism cannot silently promote. Separate independent review and fresh frozen validation remain required; completion contract retains validation 10/20, formal 5/10 and substantive QD/ED, matched ablations, cost, validity and reproducibility checks.
- **Complete-quadruple futility — PASS:** At complete valid task quadruples, s+(10-k) is the candidate upper bound; comparing it with 5 and each control current lower bound is sound. Strict < preserves permissible ties. Incomplete/missing cells cannot be scored as failures.
- **Invalidity — PASS:** Any invalid mandatory audit/unknown execution telemetry stops new dispatch, preserves charge and prefix, and permits no automatic retry or replacement. Valid environment failures count; missing trigger measurements are recorded ineligible cases rather than fabricated evidence.
- **Cohort arithmetic and attempts — PASS:** 40*(1800+40)/3600 = 20.444444444444443 hours; plus 0.5 healthcheck allowance = 20.944444444444443, below 21 by 200 seconds. 474+40=514; 1800-514=1286; baseline 105/400, development 322/1120. Bucket caps sum to 1800; validation/formal/recovery attempts are not borrowed.
- **Deadline and STOP — PASS:** No new dispatch at/after 2026-10-11T11:13:13Z or with STOP present. Already-running worker drains under frozen timeout; this permits bounded post-deadline drain, not new work. Future admission must include healthcheck/cleanup costs, full 1840-second reservation, one exact idle GPU7/UUID and cohort/private unprotected headroom.
- **Corrected cumulative accounting and reserves — PASS:** Both original caps explicitly enforced, separate retained healthchecks conservatively added, protected reserves preserved. Exact live ledger/reservation reconciliation remains mandatory before any later release.

## Blocking issues

None.

## Nonblocking implementation obligations

- In a separately authorized isolated CPU implementation, prove selected occurrence identity through archive copies/deduplication and decoder/step-return acknowledgements. Equal-content aliases cannot be assigned an N34 origin by content alone; ambiguous origin cannot arm memory.
- Test the single boundary-entry consumption and all ten parent rounds, expiry regardless of winner, every reset/exception path and absence of memory-origin rearming. Preserve source template bytes, other coordinates and other 15 candidates at replacement.
- Keep N35 memory absent in C0/Q0/N34. Verify N34 fallback, same-process mandatory audits across arms, exact runtime/provider/source manifests, native dtype/shape hashes and source adoption before any later release.
- Test complete-quadruple futility and invalidity stopping, partial denominators, zero retries, STOP/deadline drain and atomic charge/reservation admission. Bound cumulative healthcheck allowance and full cleanup time; never borrow protected reserves.
- Report trigger exclusions, native and decoded deltas separately, archive survival, selected direct origins and actual execution. A gate pass is not efficacy or completion and cannot authorize protected phases.

## Exact hash-bound inputs

Authority and local instruction/skill digests are observed hashes; all inputs with expected hashes matched. Ledger prefixes were hashed without parsing records. Origin/seed files were hash checked only; prior identity findings are retained.

- review_authority: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000885/n35-protocol-review/authority-v1.json` — SHA-256 `83fa5ebd06f55dcd8fdc2f706bcac527924937abc5af7173789c28328dcb2e77`. full artifact.
- user_authority: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/user-authorization-v1.json` — SHA-256 `a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c`. full artifact.
- protocol_v2: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000884/n35-prospective-protocol-v2.json` — SHA-256 `b8ac519a02623a7f033c5ce4b9c805bf1970f10224e29c0f851ba8568b000345`. full artifact.
- accounting_v2: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000884/prospective-accounting-v2.json` — SHA-256 `0e6925d214c7613ef2f6a7ffe5b8ec04d6f90fb134b40f0e77e111a67204491c`. full artifact.
- prior_review: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000883/n35-protocol-review/report-v1.json` — SHA-256 `323d68a3aaaec996f31c9bbaf338a50c349c60969362519549d15abc55e16453`. full artifact.
- root_corrections: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000884/root-review-v1.json` — SHA-256 `741f38af55c7c7a3ed632784a27c9e0ef60d62bb859905b432777f7802338b0a`. full artifact.
- protocol_v1: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000882/n35-prospective-protocol-v1.json` — SHA-256 `8416d12066d13c768e25642ea2184a6965b2f869a32b503c94cd10569f03df08`. full artifact.
- accounting_v1: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000882/prospective-accounting-v1.json` — SHA-256 `d30d86b16cddf31a96683f2a3d8b141bcc980859473b832a27ee1c1e5318574f`. full artifact.
- hypothesis: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000878/n35-cpu-hypothesis-v1.md` — SHA-256 `7c2ac4588bdccd21290c8aef88cfafcdd9a80accf715129668cf2d9c04fe855a`. full artifact.
- cpu_review: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000881/cpu-feasibility-root-review-v1.json` — SHA-256 `2f326ee0c3258a2f883c436f58b31d63993ea80f60c7e114a7f7490215095c97`. full artifact.
- completion_contract: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/completion-contract-v1.json` — SHA-256 `4e825a595c3422824f5160b42690528a03a1ac4d8d2cf4025576a3bb59b2514c`. full artifact.
- approved_budget_proposal: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/week-autonomy-budget-proposal-20261004-v3.md` — SHA-256 `a24254fcc9a61451de0e289694878974a92c22216b5f67181f09137363668d53`. full artifact.
- identity_origin: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n34_observed_jaw_approach/root-recovery11-release-v1/plan.frozen-v1.json` — SHA-256 `22fb58005d3a23168f7f9efd7d190d9142ad4ee2ebf0b7da7fbf97c6ce342743`. opaque hash only in correction review; unchanged identity findings inherited from prior review.
- seed_plan: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/frozen-seed-plan.json` — SHA-256 `9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1`. opaque hash only in correction review; unchanged identity findings inherited from prior review.
- worktree_AGENTS: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/AGENTS.md` — SHA-256 `1e24256700e2f748912dc9eea177408e2f1f8c577e424102d7a5d03849e00e0b`. full artifact.
- arbor_entrypoint_skill: `/home/hynx/.codex/skills/arbor-research-agent/SKILL.md` — SHA-256 `3405e1017ce017147b907f22d386165f3a76cb2eef791ea1a0fd312ce6d0f649`. full artifact.
- attempt-ledger.jsonl: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/attempt-ledger.jsonl` (first 7099066 bytes) — SHA-256 `e6bb943ec36f4afa13f006d5232912bfc283158a7e09353979591a1bc8ef71d3`. opaque prefix hash only; no records parsed or outcomes inspected.
- gpu-healthcheck-ledger.jsonl: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/gpu-healthcheck-ledger.jsonl` (first 66651 bytes) — SHA-256 `410294ccdc57a5a448584a8d02b3e9fec3bb424281e34276bd0bc2ef19cce5e7`. opaque prefix hash only; no records parsed or outcomes inspected.
- gpu-hour-reservation-ledger.jsonl: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/gpu-hour-reservation-ledger.jsonl` (first 401 bytes) — SHA-256 `56f71b65976773ab83cb78ead4ef78a2fa494fce118bad10bf01e25d9e2618b8`. opaque prefix hash only; no records parsed or outcomes inspected.

## Limits of acceptance

- Bounded correction review; no production code review or broad tests. Prior scientific PASS preserved after structural comparison; no historical provenance reconstruction.
- Ledger prefixes verified as opaque bytes only; retained cost aggregates checked for arithmetic consistency, not independently rebuilt from outcome-bearing records. Exact live ledgers and inflight reservations must be reconciled before later admission.
- Origin/seed artifacts hash verified only in this correction; unchanged identity match findings rely on the bound prior review. No protected outcomes inspected.
- Current session only; no alternate model/account invocation, credentials inspection or fallback. Account/model authentication not independently inspected.

Only these two review reports were written. No source/state/ledger/tree modifications, GPU work, dispatch, delegation, external messaging, prohibited file or credential access, or protected outcomes.
