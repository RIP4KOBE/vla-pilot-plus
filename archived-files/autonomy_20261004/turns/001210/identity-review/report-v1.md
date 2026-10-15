# Node 15.6 independent CPU review — PASS

Reviewed `066f2bf57e05111fea329ff7c393ac3e002d7c0f` against `ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557`. No blocking defect found in the operational repair. PASS covers CPU review only; it grants no adoption, release, native readiness or scientific promotion.

## Findings

- **R1 PASS.** Original protocol, protocol review, accounting and allocation SHA anchors are fixed in source. Exact structural wrappers reject extra science/authority fields and arbitrary plan-supplied expected hashes. Both unsigned templates match their reported bytes and inherited anchors; neither grants execution authority. Evidence: `scripts/qd_ed_n36_recovery.py:13`, `scripts/qd_ed_n36_recovery.py:25`, `scripts/qd_ed_n36_recovery.py:41`, `scripts/qd_ed_n36_contract.py:15`.

- **R2 PASS.** All 40 allocation mappings were independently compared with original protocol rows. Only iteration and episode_key change; tasks, seeds, init and BDDL hashes, arms, order, timeouts and buckets remain identical. Exactly 10 baseline and 30 development; no replacements. Inherited allocation manifests are historical references, not fresh release manifests; preparation recomposes all 40. Evidence: `scripts/qd_ed_n36_contract.py:49`, `scripts/qd_ed_n36_recovery.py:16`, `scripts/qd_ed_n36_prepare.py:34`, `tests/test_n36_recovery.py:157`.

- **R3 PASS.** Fresh cohort selection rejects mixed/spoofed identities. Reconciliation requires unique contiguous task-major groups, rejects retry/recovery pointers, stops on invalid/unsettled history, and retains all40/futility rules. Global journal-key and pre-existing output checks prevent replay; fresh healthcheck IDs are separately bounded and non-replayable. Evidence: `scripts/qd_ed_n36_contract.py:93`, `scripts/qd_ed_n36_supervise.py:5`, `scripts/qd_ed_n36_runner.py:99`, `scripts/qd_ed_n36_accounting.py:80`, `scripts/qd_ed_n36_recovery.py:86`.

- **R4 PASS.** Admission requires the original reserved/dispatched/aborted attempt and exact 86.40354533703066 seconds. Global budget_snapshot includes original episode and healthcheck costs before fresh cohort accounting. Ledger-prefix checks and inherited retained margin 0.23357169027962 GPUh remain required. This review did not recompute live cumulative totals or read protected outcome histories. Evidence: `scripts/qd_ed_n36_recovery.py:75`, `scripts/qd_ed_n36_release.py:153`, `scripts/qd_ed_n36_runner.py:26`, `scripts/qd_ed_n36_accounting.py:21`.

- **R5 PASS.** New operational refs propagate to detached review/release, all manifests, journal lifecycle and terminal validation; healthcheck lifecycle inherits its reservation binding. Old release cannot bind new plan hash/rows. Source/runtime closure, controller semantics, inventory, strict native build validation and same-worker before/after attestations remain mandatory and unchanged. Evidence: `scripts/qd_ed_n36_release.py:43`, `scripts/qd_ed_n36_release.py:89`, `scripts/qd_ed_n36_bridge.py:80`, `scripts/qd_ed_n36_worker.py:368`, `scripts/qd_ed_n36_healthcheck.py:67`.

- **R6 PASS.** Unchanged caps: 1800 total attempts, 224 GPUh absolute, weekly origin 53.08404692669838 + 168 GPUh, protected validation/formal 180/40 attempts and 32/12 GPUh, fresh cohort 75600s and healthchecks 1800s. Full1840s episode reservation, GPU7 UUID, authority interval, STOP including dangling symlink, and 2026-10-11T11:13:13Z deadline are preserved. Validation/formal remain unauthorized. Evidence: `scripts/qd_ed_n36_contract.py:18`, `scripts/qd_ed_n36_contract.py:144`, `scripts/qd_ed_n36_release.py:132`, `scripts/qd_ed_n36_accounting.py:39`, `scripts/qd_ed_n36_runner.py:119`.

- **R7 PASS.** Prior native draft changes only torch_build by adding CUDA Runtime/NVCC/CuDNN/Magma metadata lines. All 75 library path/hash entries, torch version and CUDA version match the original inventory. Draft metadata exactly matches the referenced prior CPU capture. Strict actual metadata equality and before/after library/device requirements were not relaxed. Libraries were not rehashed or loaded by this reviewer; draft compatibility is not native readiness. Evidence: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001203/recovery-preparation/native-build-n36r1.draft-v1.json:5`, `scripts/qd_ed_n36_build.py:43`, `scripts/qd_ed_n36_worker.py:296`.

- **R8 PASS.** Actual commit diff has 11 files, 476 insertions and 41 deletions, solely operational support and tests. Scientific implementation/config files and native/arithmetic/source audits are unchanged. Complete-quadruple futility and all40 necessary gate N36 >= max(5,C0,Q0,N34) remain unchanged; CPU tests cannot establish efficacy or promotion. Evidence: `core/qd_nonprogress_tangent.py:1`, `scripts/qd_ed_n36_supervise.py:50`, `scripts/qd_ed_n36_report.py:14`.

## Checks and limits

Verified hashes and read all three logs: run1 109 pass/1 fail; run2 117 pass/1 fail (tuple/list comparison); corrected targeted run3 1 pass. 118 distinct passes supported across run2/run3, not a single all-green full-suite invocation. Executor reports no production-source change between those runs. Final test uses canonical JSON comparison and checks all40 actual compositions.

All changed files match the reviewed commit and reported SHA-256 values. `git diff --check` passed; tracked worktree was clean. All 40 mapping ordinals and identities were independently compared. No new test, native/library load, provider call, GPU probe, ledger read/rebuild or adoption was performed. Current live ledger totals and fresh-ID absence remain root gates.

Diff SHA-256: `ad45705e580a68c4bdc56d697e98b77386bb1bd893994cd07c143c8126a5c242`.

## Evidence hashes

- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001210/identity-review/authority-v1.json` — `d261fd277c6d71be588ac18b6d9df3e85c8969cfd1abe523343acfac42fdd697` (1573 bytes).
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/report-v1.json` — `ca00079a0d512fec60e6489b2dcae6276c4deb17a72270f378ae4f0be1420b82` (31116 bytes).
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/user-authorization-v1.json` — `a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c` (1942 bytes).
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001210/repair-terminal-reconciliation-v1.json` — `9e0eeb87813da57cbfc47ba7368326cb8eab0e9391647e6976930f10d398d3b2` (1075 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001203/recovery-preparation/report-v1.json` — `2a8216ac0e7d2d24d20c1701f22dac149206f52470e97c25060f4951f4adf888` (25364 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/protocol.n36r1.unsigned-v1.json` — `d76046f9e697831114b04f23e1db3746e614d504a018e2923fdbc4e3f927b3ce` (27984 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/accounting.n36r1.unsigned-v1.json` — `7904271b18c0c25d16005bec5712841a072072c8486cfab2d390848421c6c44d` (826 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001147/protocol-preparation/protocol-v1.json` — `d0d16593af612b073d6a85777eae9f10f7b08d608055cd86ca512a8ceeee5d8e` (68182 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001151/protocol-root-review-v1.json` — `91391b76195b91bdb0318ae380820959a5bd4c3beaa6b35c6c7b16a65f121fa9` (7026 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001203/recovery-preparation/attempt-allocation.draft-v1.json` — `fe8d16d01e56a236153e73801e4914b830edde2dc668ac9c33dc1549c10f5358` (60602 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001147/protocol-preparation/prospective-accounting-v1.json` — `2c46987e29d9616929fe0c086d3da0761eaf6718a5d1811b58200c18e34d75d0` (10204 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001203/recovery-preparation/native-build-n36r1.draft-v1.json` — `3e7e4f522f8d463671e7fe83bef4762f45f0ab0e32298959e38b8357998052d7` (18083 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001199/plan.frozen-v2.json` — `a69d2e9ac6f2bbad6470fdffb55558a7be8ed9671e675c5077747568d986b6b6` (411758 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001185/runtime-preparation/native-build-v2.json` — `7a8d1da930ab7b39f8e91ea75ecc87f08b36f5a21d7e6260b84abf6942c768ac` (17743 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001199/execution-release-v2.json` — `a29b532478acc7163c8f1d9499bbe9bae3b82ad8d7a043203506a6e1c17fe57c` (372081 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/tests-1.log` — `5989304908391af8194b3d6b812f51c639fbdc907fec96e6aab11182a24075f3` (3646 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/tests-2.log` — `907e412c0ebf872bffcca37bf9def81d41e9a662d84133dc015f68a18119b021` (3184 bytes).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/tests-3.log` — `5bee0e0b02df086185c0ab9237fc362e3cad067d5b506edc64631b933dfc84de` (99 bytes).

## Remaining gates

- Root alone may adopt the isolated commit and issue a new immutable source binding; this independent CPU PASS is not root approval, budget adoption or a production review/release.
- Root must freshly reconcile complete authoritative journals/prefix hashes and byte lengths, including the original aborted charge and all resource costs, before budget adoption. Supplied 503 dispatches / 75.26779409697457 GPUh were not independently recomputed. Fresh-ID absence in current live journals must be rechecked at adoption/admission.
- Recompose source/scientific_source, runtime/closure/controller/inventory/seed bindings and all40 actual manifests for the adopted source; keep original frozen artifacts immutable. New authority must bind both accounting/amendment to the new accounting wrapper and preserve all caps/reserves/deadline.
- Obtain a new externally hashed detached root production review and execution release; inherited CPU protocol review and unsigned templates cannot authorize execution.
- RT-03 unresolved: actual same-worker native metadata, mapped libraries, GPU7 UUID/device and arithmetic attestations before/after require a later separately authorized metered run. This review performed no GPU/provider probe.
- RT-04 unresolved: live controller/physical/occurrence/archive/decode/acknowledgement and control-absence evidence. RT-05 unresolved: full episode feasibility.
- No N36R1 all40 scientific evidence reviewed or generated. Necessary Dev gate is not scientific promotion; validation, formal and ablation remain unauthorized/unrun here. STOP/deadline prohibit new work.

STOP absent; deadline unexpired; elapsed from review authority 147.2s of 1800s. Only report-v1.json and report-v1.md written. Full per-file hashes and all40 mappings are in the JSON report.
