# Protocol v12 — outer-loop cycle-2 conclusion and evidence freeze

Status: locked after validation result commit, before cycle decision manifest/final report.

This protocol authorizes no algorithm/config change, GPU admission, model/API call, LIBERO episode, attempt reservation, validation reuse, or formal evaluation. It freezes the reporting and decision boundary required by validation protocol v11.

## Trigger

Immutable validation audit `3f72d025b492e24e7f615db7c3207c4927710794797dd228edf0579ab1290774` is valid but target-FAIL: candidate `1/10` versus control `0/10`, below the preregistered `>=5/10` gate. Mechanism, safety, latency, accounting, artifact, and credential gates passed. Result commit is `eca85e69504cb4240e8b059f65f6237d4fb54272`.

Protocol v11 requires `CONCLUDE_VALIDATION_NO_FORMAL`, prohibits outcome-driven modification/reuse of the now-exposed validation split, and permits no formal command.

## Read-only outer-loop evidence packet

- Current validation audit and raw artifacts under the owned `run_010_causal_envelope_candidate` root.
- Current result analysis `experiments/run_010_causal_envelope_candidate/analysis.md`, SHA-256 `a6d02543abbb8a00635b83cec954f1cd7bd8499796e4717aa634654f8768c5b3`.
- Search-budget final report `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808/analysis/final_report.md`, SHA-256 `580cf8c007053c497866d80a5e8c643a4a15c3bbb8281f8de5742a5bbff30c1e`: 18 configurations, no `>=5/10`, all valid scores 0/10 or 1/10.
- Stage/guidance-transition final report `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/stage_guidance_transition_20260810/analysis/final_report.md`, SHA-256 `ecc7554c7a14dea6a56a532cdaa0ab99bc65f2d95a0bee212c1292964b4ac426`: FSM 0/20, no gains, one lost success, safety gate failed.
- Existing append-only baseline replay, partition diagnostic, mechanism preflight, Dev-A and Dev-B evidence already indexed in the canonical ledger.

All paths outside this worktree and owned artifact root remain read-only. The protected untracked stage-guidance design remains untouched and excluded.

## Decision rule

1. Reject causal-envelope as insufficient for the primary target; preserve its mechanism evidence.
2. Do not run formal because validation `<5/10`.
3. Do not modify a candidate and reuse validation seeds.
4. Conclude the current frozen cycle because no admissible same-cycle path remains from a revealed validation result to a new formal-eligible candidate.
5. A future H2 QD quality/selection direction is only a redesign candidate, not an authorized continuation. It requires a versioned design, new leakage-safe holdout seeds, an explicit evaluation budget, and user approval before implementation or dispatch.

The outer-loop decision label is frozen as `CONCLUDE_NO_ADOPTION_WITHIN_FROZEN_CYCLE_REQUEST_VERSIONED_REDESIGN`.

## Required outputs

- immutable owned-artifact `manifests/cycle_decision_manifest.json`, mode 0444;
- final report under `docs/03_evidence/eds_qd_autoresearch/`;
- one human progress page;
- append-only state/log/findings/trajectory/ledger updates;
- strict credential scan, Git diff/status verification, and result/reflection commit.

The decision manifest must bind the design/protocol/result commits, manifest/audit hashes, algorithm fingerprints, full task results, attempt/GPU-hour accounting, no-formal status, protected-file exclusion, and redesign boundary. It must contain no credential value or reversible credential fingerprint.
