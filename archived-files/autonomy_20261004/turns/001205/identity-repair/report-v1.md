N36R1 identity repair — IMPLEMENTED_CPU_VALIDATED_COMMITTED_PENDING_ROOT_REVIEW

Node 15.6. Source `ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557` → `066f2bf57e05111fea329ff7c393ac3e002d7c0f` on `codex/n36-nonprogress-tangent`. Isolated commit only; owning study unchanged.

Implemented and committed strict prospective N36R1 operational identity/protocol/accounting inheritance. Final affected coverage: 118 distinct CPU tests pass (117 in run2 plus corrected composition test in targeted run3). No real release, budget adoption, reservation, probe or dispatch.

Score: null. GPU dispatches: 0. GPU seconds: 0. Scientific success: false. Budget adoption/reservations: none.

A fresh identity cohort requires its own detached root release plus exact structural protocol/accounting inheritance. Original scientific hash anchors remain fixed; new manifests and journal bindings prevent old releases/identities from being reused, while the failed primary remains charged.

Validation: run1 109 passed/1 new-test comparison failure; run2 117 passed/1 JSON tuple/list comparison failure; final targeted run3 1 passed. Production source was unchanged between runs2 and3. Final distinct affected coverage is 118 passing tests. Exact commands, environment and log hashes are in report-v1.json. CUDA_VISIBLE_DEVICES was empty for every CPU test. Synthetic test releases are fixtures only.

```
scripts/qd_ed_n36_accounting.py |  15 ++-
 scripts/qd_ed_n36_bridge.py     |   4 +-
 scripts/qd_ed_n36_contract.py   |  56 +++++++--
 scripts/qd_ed_n36_prepare.py    |  18 ++-
 scripts/qd_ed_n36_recovery.py   | 102 ++++++++++++++++
 scripts/qd_ed_n36_release.py    |  55 ++++++---
 scripts/qd_ed_n36_runner.py     |   2 +-
 scripts/qd_ed_n36_supervise.py  |   8 +-
 scripts/qd_ed_n36_worker.py     |   2 +
 tests/test_n36_recovery.py      | 254 ++++++++++++++++++++++++++++++++++++++++
 tests/test_n36_release.py       |   1 +
 11 files changed, 476 insertions(+), 41 deletions(-)
```

Changed files (SHA-256):

- `scripts/qd_ed_n36_accounting.py`: `1d8bb04d332b9078c53624ca5cbbf24e821e4247e3ba91e86fb2be62a4afdd02`
- `scripts/qd_ed_n36_bridge.py`: `a94deace5c862ae9160a91af6a73de176e62839c9a80783a88421a83c63bbb89`
- `scripts/qd_ed_n36_contract.py`: `d6a7d10c3304f4e49f62c676065fa9794c5f230807f4f84cccb51e81552d0bd5`
- `scripts/qd_ed_n36_prepare.py`: `d4813d3fb99d8b6a13c1edcee750637702cd2f098a7918d5aa2afb0c59d4397e`
- `scripts/qd_ed_n36_recovery.py`: `9e746f8e2697dcadaa3b9109b83e9dd1959d518411704319162b8801e43975d2`
- `scripts/qd_ed_n36_release.py`: `1afd0b01617f0645c2ad1187c861cdeab1cdc3ff24eaa28002547ed81cd813c0`
- `scripts/qd_ed_n36_runner.py`: `85a60c60c64bc2a9af8884ab3be99e710dec6670e68636fec3ea62983655ff00`
- `scripts/qd_ed_n36_supervise.py`: `6706bb138985a0eef7bc5c2d2742d03d2af2421d4120c932c604ba175af7f06f`
- `scripts/qd_ed_n36_worker.py`: `42733eb91beaec98a4e2c86378ecb585a3b67d941fe2f886061f6d637a772dad`
- `tests/test_n36_recovery.py`: `6c31c6f8a0281ed333a96260927389dbc235f6d7effb337491dcc5bea8092688`
- `tests/test_n36_release.py`: `0884bb3002b03bb34dbbd12aeb2da6d0c19385ecbab0973711a3c5b9e17ea17a`

Unsigned templates (no approval):

- [protocol.n36r1.unsigned-v1.json](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/protocol.n36r1.unsigned-v1.json): `d76046f9e697831114b04f23e1db3746e614d504a018e2923fdbc4e3f927b3ce`
- [accounting.n36r1.unsigned-v1.json](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/accounting.n36r1.unsigned-v1.json): `7904271b18c0c25d16005bec5712841a072072c8486cfab2d390848421c6c44d`

Retained invariants:

- Scientific N36 algorithm/config values/thresholds/seeds/tasks/arms/order unchanged.
- All40 requirement and prospective complete-quadruple futility/necessary gate unchanged; no promotion from CPU evidence.
- 10 fresh baseline + 30 fresh development, zero automatic recovery, replacement=None, historical IDs never replayed.
- Original failed attempt remains charged at 86.40354533703066 seconds; current study totals supplied as 503 / 75.26779409697457 GPUh, no refund/reset.
- Deadline, STOP, exact GPU7 UUID/device mapping, metering/full1840s reservations, dual cumulative caps and protected reserves unchanged.
- Detached externally hashed root release, source/runtime closure and exact native metadata/library/device before/after attestations remain required.
- Stage provider and native audit machinery unchanged; validation/formal authorization remains false.

Root preparation steps (not performed here):

1. Independently review isolated commit 066f2bf57e05111fea329ff7c393ac3e002d7c0f and the unsigned templates. This executor has not merged/cherry-picked it into the owning study, signed any release, or certified runtime readiness. Any later adoption must create a new immutable source binding; keep the original frozen plan/release/history intact.
2. Review protocol.n36r1.unsigned-v1.json and accounting.n36r1.unsigned-v1.json as structural inheritance only. Preserve fixed original protocol SHA d0d16593af612b073d6a85777eae9f10f7b08d608055cd86ca512a8ceeee5d8e, protocol-review SHA 91391b76195b91bdb0318ae380820959a5bd4c3beaa6b35c6c7b16a65f121fa9, accounting SHA 2c46987e29d9616929fe0c086d3da0761eaf6718a5d1811b58200c18e34d75d0, and allocation SHA fe8d16d01e56a236153e73801e4914b830edde2dc668ac9c33dc1549c10f5358. The allocation proposal anchors exact rows only; its inherited manifests are not new manifests. No plan-supplied expected hash overrides these anchors.
3. Root must freshly reconcile the complete authoritative journals and ledger-prefix hashes/byte lengths before budget adoption. Preserve the original aborted n36_dev_t00_c0_001147 and its exact 86.40354533703066 GPU seconds; include all original episode/healthcheck costs globally and the inherited retained margin 0.23357169027962 GPUh. User-supplied current totals are 503 dispatches / 75.26779409697457 GPUh, not independently recomputed here. New cohort denominators do not erase historical charges.
4. If separately approved, prepare a new n36-budget-authority-v1 with cohort N36R1_NONPROGRESS_TANGENT_DEV_001203; protocol equal the unsigned operational-protocol reference; accounting AND amendment equal the accounting-inheritance reference. Keep exact LIMITS/CAPS, automatic_recoveries=0, validation_authorized=false, formal_authorized=false, starts_at and coordinator/weekly ends within the deadline; retain weekly origin 53.08404692669838 plus 168 and absolute 224 GPUh. Bind a real external approval_basis and current complete attempt/healthcheck ledger prefixes (plus reservation ledger as applicable). Owning state n36_budget_authority and budget.amendment must match those new refs after root authorization, with unchanged protected bucket/hour reserves. No authority or adoption performed here.
5. Recompose the new source inventory, scientific_source, runtime, runtime_closure, controller_semantics and runtime inventory/seed-plan bindings through the existing strict source/runtime audits. Independently review native-build-n36r1.draft-v1.json from 001203; exact metadata equality and library/device before/after attestations remain unchanged. CPU metadata compatibility is not a native/device readiness claim. Stage provider remains official current-login Codex/ChatGPT gpt-6-astra under the frozen recovered-error condition.
6. Generate a new disabled draft in a previously nonexistent directory using scripts/qd_ed_n36_prepare.py with the newly reviewed runtime/native/closure/controller refs and --recovery-protocol /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/protocol.n36r1.unsigned-v1.json --recovery-protocol-sha256 d76046f9e697831114b04f23e1db3746e614d504a018e2923fdbc4e3f927b3ce. All40 actual external manifests/config hashes must be recomputed, never copied from the old cohort. New manifest rows/run IDs/output paths and protocol/protocol_review/accounting refs must match the new plan exactly. If relocating template files, rehash dependent references in DAG order; never modify the original scientific anchors.
7. Complete required plan metadata (run_name, runtime_inventory_path/runtime_inventory_sha256, seed_plan_path/seed_plan_sha256, input_contract_label, attempt_identity=episode_key) from the new reviewed runtime. Only root may later convert the disabled draft to n36-released-plan-v1, frozen=true, release_enabled=true, dev=true/validation=false/formal=false, new authority ref, removing root_review/execution_release placeholders. Retain cohort, protocol, inherited protocol_review, accounting and all40 expected_manifests. Do not change thresholds, tasks/seeds/arms/order, timeout, all40 rule or prospective futility/promotion conditions.
8. After independent review, create a new detached n36-root-production-review-v1 and n36-execution-release-v1 using the exact existing expected-field contract plus cohort/accounting. Both bind the new external plan hash, native_build, authority, operational protocol, inherited protocol_review, source/scientific_source, runtime_closure/controller_semantics/runtime, limits and phases. The old CPU protocol review approves only inherited science; it does not approve this repair or execution. Root supplies the externally trusted release SHA to consumers. The old release cannot authorize the new rows. No real review or release is created here.
9. Only under a later separately authorized metered release may readiness/device/provider probes and actual workers run. N36R1 preparation healthcheck ID is n36_healthcheck_n36r1_preparation_001203; per-cell checks are n36_healthcheck_<fresh episode_key>, with kind n36r1_resource_preparation_v1 and exact operational refs. Preserve resource charge history and all native/source/runtime gates. STOP/deadline, contiguous task-major primary sequence, 10 baseline+30 development, zero automatic recovery and no replay still govern admission. Validation/formal/promotion/ablation remain unauthorized here.

Prospective prepare command template (requires newly reviewed inputs; not executed):

```text
python scripts/qd_ed_n36_prepare.py --output <NEW_NONEXISTENT_DRAFT_DIRECTORY> --runtime <NEW_REVIEWED_RUNTIME> --runtime-sha256 <EXTERNAL_RUNTIME_SHA> --runtime-closure <NEW_REVIEWED_RUNTIME_CLOSURE> --controller-semantics <NEW_REVIEWED_CONTROLLER_SEMANTICS> --native-build /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001203/recovery-preparation/native-build-n36r1.draft-v1.json --native-build-sha256 3e7e4f522f8d463671e7fe83bef4762f45f0ab0e32298959e38b8357998052d7 --recovery-protocol /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/protocol.n36r1.unsigned-v1.json --recovery-protocol-sha256 d76046f9e697831114b04f23e1db3746e614d504a018e2923fdbc4e3f927b3ce
```

Unresolved evidence:

- root_independent_review: PENDING: this is executor implementation evidence only
- budget_adoption: NOT_AUTHORIZED / NOT_PERFORMED
- runtime_recomposition: PENDING: new commit/source/runtime/native/manifests require root preparation and strict audits
- RT-03: UNRESOLVED: no actual same-worker native/library/device arithmetic attestations
- RT-04: UNRESOLVED: no live episode/controller/physical/occurrence/archive/decode/acknowledgement/control-absence evidence
- RT-05: UNRESOLVED: no full episode feasibility evidence
- development: No N36R1 scientific episodes executed; all40 scientific evidence absent
- validation: Not accessed or run; no authorization/evidence
- formal: Not accessed or run; no authorization/evidence
- ablation: Not run; no new ablation evidence
- native_metadata: Prior 001203 draft retained for independent root review; no new probe or device readiness certification

Original frozen plan/release/native manifest hashes still match preparation records. Owning ledger, state, checkpoint and tree were not written or recursively audited; supplied study totals were not independently recomputed. The selected scientific/native/source-audit files remain byte-identical to the prior commit.

STOP absent at final check: True. Deadline not reached. Elapsed since authority: 566.3s / 1800s.
