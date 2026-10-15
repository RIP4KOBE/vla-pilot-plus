# N36R1 engineering recovery preparation — partial, release blocked

Node 15.6; executor only. `release_enabled=false`, `approved=false`. No scientific score, promotion, task-success claim, or RT-03/04 native evidence.

The prospective GPU7-visible native manifest changes only `torch_build`. Both narrow CPU probes left `torch.cuda.is_initialized()==False`. In a separate comparison process, the exact metadata predicate extracted from the unchanged attestor accepted the new manifest and rejected the original. All 75 inherited binary SHA-256 values were reverified. No full attestor, worker, CUDA allocation, healthcheck or GPU dispatch ran.

New manifest: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001203/recovery-preparation/native-build-n36r1.draft-v1.json` (SHA-256 `3e7e4f522f8d463671e7fe83bef4762f45f0ab0e32298959e38b8357998052d7`). Original manifest and all original frozen records remain unchanged.

Fresh proposal: recovery `N36R1_001203`, cohort `N36R1_NONPROGRESS_TANGENT_DEV_001203`; 40 attempt IDs `n36r1_dev_t{00..09}_{c0,q0,n34,n36}_001203`, ordered by task then C0/Q0/N34/N36. Exact rows, inherited manifest references and new output paths are in `attempt-allocation.draft-v1.json`. Proposal: 10 baseline, 30 development, zero recovery-bucket attempts; no reservation, budget adoption or automatic retries. It includes a fresh first C0 and 39 fresh remaining cells, never replaying original IDs.

**Blocker:** immutable `qd_ed_n36_contract.py` hard-codes the original cohort and episode keys (lines 11, 46–58); draft/release validation requires those exact rows. `qd_ed_n36_release.py` also pins original protocol/review/accounting bindings (lines 55–72). N36R1 cannot be released under unchanged source. No edit or monkeypatch was made. The plan uses an explicitly non-executable proposal schema; fresh external manifests/composed-config hashes remain pending rather than being invented.

Source `ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557`, task order, profiles, dev seeds, init identities, scientific settings, protocol/gates, worker audits, exact metadata/binary checks and metering semantics are inherited unchanged. Only proposed cohort/episode identities and prospective output paths differ. Direct inherited artifact hashes were checked; deep provenance, weights and protected inputs were not reread.

The ledger remained byte-identical: `0114e1900a3a815a66a29ed91da695783ce3d8123fdd707d4544be7e305363f8`. Invalid attempt `n36_dev_t00_c0_001147` and its **86.40354533703066 GPU seconds** remain charged. User-supplied study totals stay **503 dispatches / 75.26779409697457 GPUh**; no reserve was consumed.

CPU commands, environments, exit codes, timing, exact comparison expression and results are retained in `cpu-commands-v1.json` and `metadata-comparison-v1.json`. Both metadata commands use the pinned Python interpreter, `-I -S -B`, and `CUDA_VISIBLE_DEVICES=7`. Binary hashes and narrow source checks are in `input-verification-v1.json`. The report JSON binds all artifacts by SHA-256.

Remaining steps:

1. Independent review of new native manifest, binary hashes, CPU evidence, prospective identities and this blocker report.
2. Root decision on separately authorized minimal source-contract support for a fresh cohort and exact protocol/accounting identity bindings; immutable ab8e8c6 remains untouched in this task. If source must stay immutable, release cannot proceed.
3. After that decision, regenerate all 40 external manifests and actual composed-config hashes with fresh run IDs/output paths; rebind only affected source/runtime-closure/controller artifacts through normal strict audits. No original expected manifest may masquerade as a fresh one.
4. Root independently reconciles finite accounting and authorizes any prospective allocation; preserve the invalid attempt and its charge, cumulative study totals and protected reserves. The 40-cell proposal does not grant a new budget or reset spent resources.
5. Reassess current runtime/provider/device readiness under separately authorized scope, then freeze plan, independent root review and detached release with new hash bindings. Old approvals do not transfer.
6. Only a later authorized metered release may produce actual worker before/after native receipts, assigned-device arithmetic, full episode/controller/physical/occurrence/archive/decode/acknowledgement/control-absence evidence (RT-03/04), and episode feasibility evidence (RT-05).

RT-03/04 remain unresolved; CPU metadata equality establishes no native device execution or live audit result. RT-05 full episode feasibility also remains unresolved. Stop after this report; independent review and root adoption are subsequent tasks.
