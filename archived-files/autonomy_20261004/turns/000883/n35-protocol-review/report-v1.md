# N35 independent protocol review

**Disposition: BLOCK.** The scientific protocol is suitable in scope for a future isolated CPU implementation, but the bound accounting needs a separate corrected version and review. This report grants no implementation, GPU, validation or formal release.

## Blocking issues

### B1: Effective cumulative GPU-hour ceiling

approved_budget_proposal: effective cap min(224, 53.08404692669838 + 168); accounting.existing_caps.gpu_hours=224 and arithmetic.unprotected_hours_after_max uses 224.

The frozen accounting omits the independently binding weekly 168-hour increment and its unchanged baseline. Standing permission for future amendments is not a recorded numerical amendment of this bound accounting.

Issue a separately recorded accounting/protocol version carrying the effective 221.08404692669838-hour ceiling and enforcing both caps at future admission, or bind an explicit finite amendment. Do not silently interpret 224 as the sole effective cap.

### B2: Retained healthcheck charge reconciliation

Sum of retained gpu_hours_by_bucket is 69.99568238388726, equal to gpu_hours_consumed within floating precision. Separate gpu_healthcheck_hours is 0.23357169027961985. hours_after_max is only 69.99568238388729 + 21.

The arithmetic neither adds the separately listed retained healthcheck charge nor establishes that it is already included in bucket totals. The approved budget explicitly charges healthchecks; future healthcheck allowance does not cover retained costs.

Bind a cost-only reconciliation proving any inclusion, or add the retained 0.23357169027961985 hours and recompute cumulative/unprotected headroom. Preserve all old charges; do not inspect protected outcomes to reconcile costs.

With separately listed retained healthchecks added, the prospective cumulative charge is 91.2292540741669 hours. Against the approved effective cap 221.08404692669836 and protected remaining 36.24082400243081 hours, conservative unprotected headroom is 93.61396885010065 hours. Thus the cohort appears to fit; that does not repair the frozen accounting.

## Review findings

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
- **Cumulative accounting and reserves — BLOCK:** B1 and B2 prevent acceptance of the bound accounting, despite ample apparent headroom. Protected remaining validation 24.240824002430816 and formal 12 hours are preserved by the proposed correction.
- **Deadline and STOP — PASS:** No new dispatch at/after 2026-10-11T11:13:13Z or with STOP present. Already-running worker drains under frozen timeout; this permits bounded post-deadline drain, not new work. Future admission must include healthcheck/cleanup costs, full 1840-second reservation, one exact idle GPU7/UUID and cohort/private unprotected headroom.

## Nonblocking implementation obligations

- In a separately authorized isolated CPU implementation, prove selected occurrence identity through archive copies/deduplication and decoder/step-return acknowledgements. Equal-content aliases cannot be assigned an N34 origin by content alone; ambiguous origin cannot arm memory.
- Test the single boundary-entry consumption and all ten parent rounds, expiry regardless of winner, every reset/exception path and absence of memory-origin rearming. Preserve source template bytes, other coordinates and other 15 candidates at replacement.
- Keep N35 memory absent in C0/Q0/N34. Verify N34 fallback, same-process mandatory audits across arms, exact runtime/provider/source manifests, native dtype/shape hashes and source adoption before any later release.
- Test complete-quadruple futility and invalidity stopping, partial denominators, zero retries, STOP/deadline drain and atomic charge/reservation admission. Bound cumulative healthcheck allowance and full cleanup time; never borrow protected reserves.
- Report trigger exclusions, native and decoded deltas separately, archive survival, selected direct origins and actual execution. A gate pass is not efficacy or completion and cannot authorize protected phases.

## Exact input bindings

All expected hashes matched. The authority file, AGENTS.md and skill hashes record observed bytes, rather than an independently supplied expected hash. Ledger prefixes were hashed without parsing records.

- review_authority: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000883/n35-protocol-review/authority-v1.json`
  SHA-256 `f0bc3b381f487408922ccc4f9d04c89c197c97bbeee3db026b4ffd496450d65d`.

- user_authority: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/user-authorization-v1.json`
  SHA-256 `a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c`.

- protocol: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000882/n35-prospective-protocol-v1.json`
  SHA-256 `8416d12066d13c768e25642ea2184a6965b2f869a32b503c94cd10569f03df08`.

- accounting: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000882/prospective-accounting-v1.json`
  SHA-256 `d30d86b16cddf31a96683f2a3d8b141bcc980859473b832a27ee1c1e5318574f`.

- hypothesis: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000878/n35-cpu-hypothesis-v1.md`
  SHA-256 `7c2ac4588bdccd21290c8aef88cfafcdd9a80accf715129668cf2d9c04fe855a`.

- cpu_review: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000881/cpu-feasibility-root-review-v1.json`
  SHA-256 `2f326ee0c3258a2f883c436f58b31d63993ea80f60c7e114a7f7490215095c97`.

- completion_contract: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/completion-contract-v1.json`
  SHA-256 `4e825a595c3422824f5160b42690528a03a1ac4d8d2cf4025576a3bb59b2514c`.

- identity_origin: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n34_observed_jaw_approach/root-recovery11-release-v1/plan.frozen-v1.json`
  SHA-256 `22fb58005d3a23168f7f9efd7d190d9142ad4ee2ebf0b7da7fbf97c6ce342743`.

- seed_plan: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/frozen-seed-plan.json`
  SHA-256 `9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1`.

- approved_budget_proposal: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/week-autonomy-budget-proposal-20261004-v3.md`
  SHA-256 `a24254fcc9a61451de0e289694878974a92c22216b5f67181f09137363668d53`.

- worktree_AGENTS: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/AGENTS.md`
  SHA-256 `1e24256700e2f748912dc9eea177408e2f1f8c577e424102d7a5d03849e00e0b`.

- arbor_entrypoint_skill: `/home/hynx/.codex/skills/arbor-research-agent/SKILL.md`
  SHA-256 `3405e1017ce017147b907f22d386165f3a76cb2eef791ea1a0fd312ce6d0f649`.

- attempt-ledger.jsonl: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/attempt-ledger.jsonl`
  SHA-256 `e6bb943ec36f4afa13f006d5232912bfc283158a7e09353979591a1bc8ef71d3`; prefix bytes 7099066.

- gpu-healthcheck-ledger.jsonl: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/gpu-healthcheck-ledger.jsonl`
  SHA-256 `410294ccdc57a5a448584a8d02b3e9fec3bb424281e34276bd0bc2ef19cce5e7`; prefix bytes 66651.

- gpu-hour-reservation-ledger.jsonl: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/data/gpu-hour-reservation-ledger.jsonl`
  SHA-256 `56f71b65976773ab83cb78ead4ef78a2fa494fce118bad10bf01e25d9e2618b8`; prefix bytes 401.

## Limits

- No production code inspected or implementation certified; bound CPU root review relied upon without rebuilding its historical evidence chain.
- Ledger prefixes verified as opaque bytes only; retained numerical snapshots checked for internal arithmetic, not independently derived from outcome-bearing records.
- No protected outcomes read. Seed plan metadata includes phase identities, not outcomes. No init tensors or BDDL files independently rehashed.
- Current session only; no alternate model/account invocation, credentials inspection, external messaging or delegation. Account authentication was not independently inspected.

Only report-v1.json and report-v1.md were written in the authorized review directory. No source fixes, jobs, state changes or tests were performed. No efficacy is established.
