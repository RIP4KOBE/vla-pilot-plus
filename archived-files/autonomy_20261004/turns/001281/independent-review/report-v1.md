# node15.6 independent B5 review

CPU_PREPARATION_ACCEPTED_REFRESH_REQUIRED_EXECUTION_BLOCKED

Accept disabled B5 engineering/accounting/routing preparation within bounded CPU scope. Final-source bindings, coordinator adoption, current readiness and external release remain absent; production is not accepted.

`score: null`; `target_met: false`; `production_accepted: false`; release disabled.

Reviewed `b1d20fc0481721da6ebaab161c5a2ef7c3d50173..30c6321715df86c5bab623db607bab2811aed56d`. Owner remains `ca4e6a96d049c7ebb1f302d755883388ddbfdbd8`. No adoption or token was created.

## Findings

- **F1 — PASS_DISABLED_ADMISSION**: The package is structurally valid as a disabled proposal and fails closed. Draft flags, null authority and null b5_review do not admit execution; allowance-only calls cannot replace detached release verification. No source defect requiring repair was established in the reviewed delta.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_release.py:14-62`; SHA-256 `4a195b1414d4e75c07fe6ec43a0d0454f8d7f8763076246527eccd674d5fcf81`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_contract.py:174-178`; SHA-256 `b3feaf43d33844b8110eddccdb77ecdc36c70784633fcff699b0e6df15441160`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36r2_admission.py:104-113`; SHA-256 `cbf254f2c040c7530c508a0d4bec14b1e87cfef221534fbcab4303376764f102`.
  - `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001276/b5-preparation/plan.unbound-disabled-v1.json:4-4`; SHA-256 `7d19a22d820522cae27ca0f1635db51c5f2f69700fcfa4e2070afae66b64985a`.
- **F2 — PASS_ACCOUNTING**: All three exact private ledger byte sequences are unchanged. Independent production snapshot and Decimal terminal recomputation retain 504 attempts, 75.49265038509455 GPUh and both invalid charges. No cap increase or refund is needed for the proposed cohort. Protected reserves remain enforced.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36r2_admission.py:66-74`; SHA-256 `cbf254f2c040c7530c508a0d4bec14b1e87cfef221534fbcab4303376764f102`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36r2_admission.py:116-171`; SHA-256 `cbf254f2c040c7530c508a0d4bec14b1e87cfef221534fbcab4303376764f102`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_release.py:188-249`; SHA-256 `4a195b1414d4e75c07fe6ec43a0d0454f8d7f8763076246527eccd674d5fcf81`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_accounting.py:21-53`; SHA-256 `796d4135991f3a09302bfd789cbe5fe9d8596c070ea4870f7c4651d5a67f3e5c`.
  - `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001276/b5-preparation/accounting-calculation-v1.json:29-29`; SHA-256 `cc273cba1f7e1b9f59f8f07407b63c38df72c2d3fc44bd79670d5f6144f1c240`.
- **F3 — PASS_PRIVATE_ROUTING**: Owner locks, state and journals route to the exact lexical private owner; worker cwd, source attestation and package imports route to the isolated source. Adjacent checkout paths are excluded by the new bootstrap/search-path policy. Owner HEAD remains ca4e6a96d049c7ebb1f302d755883388ddbfdbd8; no adoption occurred.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36r2_admission.py:6-24`; SHA-256 `cbf254f2c040c7530c508a0d4bec14b1e87cfef221534fbcab4303376764f102`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36r2_admission.py:93-101`; SHA-256 `cbf254f2c040c7530c508a0d4bec14b1e87cfef221534fbcab4303376764f102`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_runner.py:27-35`; SHA-256 `258175e47a3d817c6a7c9fc96336eb8e4a06b54aeb896ac3f4fa3d5195bc065c`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_runner.py:64-110`; SHA-256 `258175e47a3d817c6a7c9fc96336eb8e4a06b54aeb896ac3f4fa3d5195bc065c`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_bootstrap.py:76-96`; SHA-256 `fe7d92193675d587c98977ced4a4e4602e1d2c3f4bf068afe22500acba5f52e6`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_source.py:45-51`; SHA-256 `15092a028d5c317eab34c4dc01942d1b135b8e7ff0d44a26300260899f0460a9`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_healthcheck.py:42-81`; SHA-256 `3c90ab05e35abc8974c8973587513c2c5cc216d7173cbcaaaf4a7bd6550b18d9`.
- **F4 — PASS_STOP_FRESHNESS_AND_FINITE_RESERVATIONS**: Both canonical STOP aliases use lstat, including dangling symlink vetoes; deadline is 2026-10-11T11:13:13Z. Admission requires full 1840s and healthcheck launch up to 1900s including next episode headroom. All 40 fixed episode IDs and output directories and 41 healthcheck IDs are currently unused. Healthcheck timeout is at most20s plus40s cleanup, with1800s aggregate and41 invocations; these are simultaneous ceilings, not a promise that41 maximal60s checks fit.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_stop.py:11-36`; SHA-256 `78f8edc4ebc06bb25d3f2b1f53b66bbe2f1787c6f655c309d70162cc6b9775e2`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_contract.py:179-205`; SHA-256 `b3feaf43d33844b8110eddccdb77ecdc36c70784633fcff699b0e6df15441160`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_accounting.py:69-110`; SHA-256 `796d4135991f3a09302bfd789cbe5fe9d8596c070ea4870f7c4651d5a67f3e5c`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_supervise.py:5-46`; SHA-256 `6706bb138985a0eef7bc5c2d2742d03d2af2421d4120c932c604ba175af7f06f`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_runner.py:98-108`; SHA-256 `258175e47a3d817c6a7c9fc96336eb8e4a06b54aeb896ac3f4fa3d5195bc065c`.
- **F5 — REQUIRED_FINAL_SOURCE_REFRESH**: The complete B5 preparation intentionally carries b1d20fc source/runtime/all40 bindings. They cannot authorize30c6321. The new independent review schema binds exact source, scientific source, protocol, accounting, runtime, closure, native build, controller and routing; this report is review evidence, not that final-source approval token.
  - `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001276/b5-preparation/source-dependent-rebindings-v1.json:6-6`; SHA-256 `60fb0f2c166e6c38fcd46f77bcbc1e5ed0c94b0d623f1cd72fbfafbb95a32c89`.
  - `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001276/b5-preparation/source-dependent-rebindings-v1.json:732-732`; SHA-256 `60fb0f2c166e6c38fcd46f77bcbc1e5ed0c94b0d623f1cd72fbfafbb95a32c89`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36r2_admission.py:104-113`; SHA-256 `cbf254f2c040c7530c508a0d4bec14b1e87cfef221534fbcab4303376764f102`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_release.py:102-141`; SHA-256 `4a195b1414d4e75c07fe6ec43a0d0454f8d7f8763076246527eccd674d5fcf81`.
- **F6 — FUTURE_WORKER_EVIDENCE_NOT_PREDISPATCH_GATE**: Create-once fsynced read-only before/after observations are captured inside the actual admitted worker; final parent validation hashes and compares their content and process/context/source/runtime/native/controller/device continuity. This is hash-bound retention, not WORM storage. Actual receipts cannot exist before the first authorized worker and are not required to approve its dispatch.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_worker.py:198-244`; SHA-256 `f719b22fe54c4beb4ef908040cc130efca7c28ce46fad68243745ac46cda5726`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_worker.py:258-294`; SHA-256 `f719b22fe54c4beb4ef908040cc130efca7c28ce46fad68243745ac46cda5726`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_worker.py:297-369`; SHA-256 `f719b22fe54c4beb4ef908040cc130efca7c28ce46fad68243745ac46cda5726`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_worker.py:384-414`; SHA-256 `f719b22fe54c4beb4ef908040cc130efca7c28ce46fad68243745ac46cda5726`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36_runner.py:145-171`; SHA-256 `258175e47a3d817c6a7c9fc96336eb8e4a06b54aeb896ac3f4fa3d5195bc065c`.
  - `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree/scripts/qd_ed_n36r2_admission.py:104-113`; SHA-256 `cbf254f2c040c7530c508a0d4bec14b1e87cfef221534fbcab4303376764f102`.

## Accounting and checks

All three ledger hashes match preparation. Retained: **504 attempts / 75.49265038509455 GPUh**. Exact Decimal terminal total:271773.541386340166945seconds (production float total retained unchanged). Both invalid charges remain86.40354533703066s and809.4826372319367s.

Proposed cohort:40×1840+1800+200=75600s=21GPUh. With retained margin0.23357169027962GPUh, conservative after-cohort charge96.72622207537417GPUh. Effective cap221.08404692669838GPUh; remaining protected validation/formal36.2408240024308155GPUh; unprotected effective headroom88.1170008488933945GPUh. Attempts after cohort544; remaining1256 including160 protected attempts.

All40 episode IDs/outputs and41 healthcheck IDs are fresh. Both STOP aliases absent at check time. Focused independent CPU check passed in1.857s on2 CPUs; retained11-test/52-negative-case evidence was hash-verified, not rerun. No broad suite or production readiness check.

## Minimal refresh

1. Freeze final isolated commit30c6321715df86c5bab623db607bab2811aed56d (or explicitly review any later delta). Regenerate source.complete inventory and source_files_sha256 for the ten changed/new files; verify scientific_source bytes and all40 scientific identities/settings remain unchanged.
2. Refresh affected entries and hashes in runtime.isolated.draft and runtime-closure.isolated.draft: changed accounting/bootstrap/contract/healthcheck/release/runner/source/worker modules and new n36r2_admission module; sanitize import-search evidence for isolated roots. Rebind controller-semantics runtime/closure references without changing controller semantics. Reuse unchanged native build/checkpoint evidence unless inputs change.
3. Regenerate all40 expected manifests and source/config joins plus full-scientific-config comparison; rebind disabled plan to final source/scientific_source/runtime/closure/controller/protocol/accounting/routing and manifest hashes, then regenerate disabled contexts. Do not reuse old receipt/search-path schemas as evidence for the new source.
4. Review the refreshed dependency graph and focused changed-boundary evidence only; do not rebuild old provenance or repeat broad B2/passive B4 tests. Obtain an external final-source B5 review with the exact fields required by qd_ed_n36r2_admission.independent_review. That review states worker_receipts_are_future:true and release_enabled:false.

## Release and future worker evidence

1. Coordinator separately adopts the reviewed source and owning-state finite authority/accounting references after locked live private-ledger reconciliation. Preserve224GPUh/1800attempt caps, weekly effective221.08404692669838GPUh, bucket ceilings, protected32/12GPUh allocations, both invalid costs and all prefixes. Existing state authority still points to turn001222; this reviewer authorizes no adoption.
2. Under separately authorized readiness work, establish current exclusive GPU7 UUID GPU-48473162-9548-1a19-04aa-ea86c5349187, private ACTIVE/PASS assignment, CUDA logical0/EGL4 mapping and official gpt-6-astra/codex_cli readiness. Reuse only valid hash-bound accounted GPU/EGL proof; otherwise an explicit bounded accounted healthcheck is required before episode dispatch. N36R2 healthcheck invocation must explicitly use timeout_seconds<=20 (the wrapper default60 is rejected). No provider/device/healthcheck work was performed here.
3. Final input-bound B5 review precedes final frozen plan; root production review binds that final plan hash, and detached external execution release binds plan and root review. Regenerate release-bearing contexts only after this external release. No attempt-worker before/after receipt is needed to create this acyclic approval chain.
4. Immediately before every reservation and launch, hold owning locks and reverify release/source/runtime bindings, all charge prefixes and live totals, no live/unsettled handles, exact next fresh ID/output, protected/global/cohort headroom, both STOP aliases and authority window/deadline. Require1840s or up to1900s including maximal healthcheck. Failed or unknown costs block; zero automatic recoveries.
5. During the separately admitted worker, produce and validate the process-bound before/after receipts described in F6. Full actual-worker B4 closure and scientific result acceptance remain contingent on these receipts and native/generic outcome checks; missing evidence never justifies waiving admission or refunding cost.

Actual worker receipts are **future evidence required before attempt acceptance/continuation**, not pre-dispatch evidence. CPU acceptance does not close actual-worker B4 or authorize production.

## Evidence and limits

Checks: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001281/independent-review/check-results-v1.json`; SHA-256 `ef7f06a749fa86fcb25529c8a81d081ba5e3b00505e20d2b6d941dc664c5675a`.
Script: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001281/independent-review/check-review-v1.py`; SHA-256 `93fedf818ad5504081ef11b5a410a6f2cd746a1e8c45e399ecf2977f72d0ea2c`.

- No GPU/Main/simulator/healthcheck/provider/network/package/credential activity, child agents, protected result inspection, owner/state/ledger mutations, source edits, release tokens or adoption. Ledger fields used only for permitted accounting.
- No production happy-path execution. Reused hash-verified11 focused tests and52 package negative cases; independent checks verify exact inputs, arithmetic, freshness and disabled rejections.
- Did not rehash multi-GB model/native assets or reconstruct prior provenance. Prior accepted evidence retained within its original scope.
- Live state/STOP/ledger checks were read-only and not under owner locks; future adoption/dispatch must reconcile again.
- No defect requiring source changes was established by this bounded review; this is not a claim of exhaustive production verification.
