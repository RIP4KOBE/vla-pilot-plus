# Arbor 15.2 — N32R2 prospective release candidates

Status: **CPU PREPARATION COMPLETE; PRODUCTION BLOCKED, ROOT REVIEW REQUIRED**.
Source and code reference: `1065f38122379a515b60a9a424f574330405b66f`. Score: null (no scientific evaluation). No source edits, GPU dispatch, coordinator/agent launch, owning state/checkpoint/ledger changes, provider/network access, or prior outcome reuse.

## Frozen artifacts

- `payload/draft-v1/plan.draft.json`: official `qd_ed_n32_prepare.prepare` output, disabled draft with all 30 fresh manifests.
- `protocol.candidate-v1.json`: exact prospective N32R2 protocol, all-valid 30-cell promotion gate, at least five N32 successes, matched controls, complete-valid-triple futility.
- `payload/runtime.n32r2.candidate-v1.json` and `runtime-provenance-v1.json`: fresh reference binding this implementation checkout; existing task/cache/provider fingerprints retained. GPU/EGL/provider readiness fields are inherited historical claims, **not fresh checks**.
- `source-closure-v1.json`: exact 551-file closure, Git object and local-byte verification, including pinned RDT worker dependency and current repaired worker entrypoint.
- `budget-authority.candidate-v1.json`, `plan.frozen.CANDIDATE-v1.json`, `root-production-review.CANDIDATE-v1.json`, `execution-release.CANDIDATE-v1.json`: detached prospective DAG. Authority/review/release approval is false; plan release and all phase authorizations are false. The root-review candidate says PENDING_INDEPENDENT_ROOT_REVIEW. Frozen means hash-bound candidate bytes only.
- `worker-entrypoints.CANDIDATE-v1.json` and 30 payload contexts: exact Python `-m scripts.qd_ed_n32_worker` command, cwd, context path and digest for each primary. None is production-authorized.
- `validation-v1.json`, `runtime-inventory-check-v1.json`, `entrypoint-negative-v1.json`, `validation-commands-v1.json`: API checks, blockers, commands and hashes. `artifact-index-v1.json` lists every sealed executor-produced artifact.

Payload physical storage: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n32_archive_eligible_capture/prospective-recovery-release-v2`. Logical link: `payload`. No weights/checkpoints were copied; prospective attempt output directories remain absent.

## Preserved authority and science

Cohort `N32R2_ARCHIVE_ELIGIBLE_CAPTURE_DEV_20261004` uses 30 fresh `n32r2_dev_*_20261004` identities: ten C0 baseline and twenty Q0/N32 development cells, at most 18,000 GPU seconds (5 GPUh), zero automatic recoveries. Task identities, seeds, 720-step schedule, 20 Hz control, horizon eight, source/run/task bindings and same-process generic/native audits remain fixed. Episode bound is 1,800 seconds including audits plus 40 seconds cleanup. Unknown HTTP telemetry stays Unknown; missing cost/exclusivity telemetry cannot become zero or a valid result.

The root accounting amendment retains **423 attempts / 56.92968407644514 GPUh**, including all old failures and health costs. Maximum after the fresh cohort is 453 attempts / 61.92968407644514 GPUh; effective weekly ceiling is 221.08404692669836 GPUh. Remaining protected hours are 24.240824002430816 validation and 12 formal; remaining protected attempts are 120 validation and 40 formal. Global caps remain 1,800 attempts / 224 GPUh with unchanged bucket ceilings. No reserve borrowing or protected-phase authorization.

Weekly deadline remains `2026-10-10T17:42:00Z`; coordinator end remains `2026-10-11T11:13:13Z`. STOP remains `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP`. Full-attempt time, settled accounting, exact GPU7 UUID, exclusive/private allocation and live admission must still pass immediately before production dispatch.

## Checks and evidence

- Clean HEAD at required commit; exact 551-file source closure and current worker origin/spec/hash attestation passed.
- Official draft contract passed. Released-plan structural validation passed on an in-memory enabled shape only; no approved review was generated or passed to execution.
- All 30 external manifests recompose byte-equivalently; fresh task/source/run binding and output paths verified. No old result payloads were read or reused.
- All 3,291 runtime inventory entries were preserved. **2,595 verified; 696 failed because files are missing**: 155 RDT and 541 LeRobot. Full failure paths and expected hashes are in `runtime-inventory-check-v1.json`.
- Task/input/seed/cache validators passed with `require_frozen=False`. Full checkpoint/encoder/DINO weight hashing was deliberately not rerun; root must run the unmodified production validator with its default frozen checks before release.
- Hash-only historical ledger-prefix verification passed against the accounting amendment; no historical or protected outcome analysis was performed.
- `validate_release` rejects the disabled plan. Actual `python -m scripts.qd_ed_n32_worker` with the frozen candidate context and parent gate byte `G` rejected with `released plan contract`, exit 1, before Main/model/provider/GPU execution. This is negative CPU admission evidence, not a successful episode or native outcome audit.
- No broad test suite rerun. Preparation API work took 23.190 seconds. Delivery preparation elapsed upper bound at report creation: 407.5 seconds, within 1,200 seconds.

Exact validation commands, scripts, logs and SHA-256 values are in `validation-commands-v1.json`; per-artifact SHA-256 values are in `artifact-index-v1.json` and `delivery-v1.json`. Prior provenance is referenced directly, not recursively rebuilt.

## Remaining root operation and blockers

1. Independently review the actual source, scientific protocol, accounting amendment, runtime provenance and all candidate digests. No current document grants production approval.
2. Settle the execution checkout. This implementation checkout lacks 696 frozen runtime dependencies; its detached artifacts are reviewable but not runnable. Do not silently omit entries or substitute an adjacent checkout. Root may separately authorize dependency provisioning, or regenerate checkout-specific runtime/manifests/plan for the owning checkout at the same exact source. Any source repair requires a separate implementation report and authorization; none was made here.
3. For the settled checkout, root must independently verify all frozen runtime/model bytes, source closure and worker entrypoint, current accounting prefixes and settled reservations. Root alone can finalize the budget authority, enabled Dev-only plan, new digest-bound root review (`decision: APPROVED`) and detached release (`approved: true`) in dependency order. Recompute affected references and manifests whenever runtime/worktree/source changes; do not approve stale candidate hashes.
4. Root must call unmodified `qd_ed_n32_release.validate_release` on the final refs and independently adopt the exact authority/plan/release into owning state under the normal locks, preserving all historical charges. Owning ledgers/state are not staged or edited by this delivery.
5. Only after those operations may root perform current STOP/deadline/private GPU7/probe/exclusivity/accounting admission through the existing production adapter. Validation/formal remain unauthorized. Existing production scientific/native/telemetry gates must not be weakened.

## Executor result

Idea: prepare fresh N32R2 release artifacts after accepted identity and worker repairs.
Result: 30 prospective manifests, runtime and source references, protocol/accounting candidates, detached disabled release DAG and exact worker contexts prepared; checks passed within their stated scopes, with runtime completeness and root approval still blocking production.
Insight: source closure can verify while the execution dependency inventory remains incomplete; both gates are necessary. Earlier outcomes remain retained and unreused.
