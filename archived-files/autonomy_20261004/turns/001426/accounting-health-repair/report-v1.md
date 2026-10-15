# Node 15.6 bounded accounting / health repair

CPU repair committed; production release remains blocked.

Source before: `4e632c3bf1afe682d9287a518e531e6f2a6eba42`  
Source after: `d01bc1e2e7acc876653a43ddf157d0b4a641f88a`

Changed files:

- `scripts/qd_ed_n36_release.py`
- `scripts/qd_ed_n36r3_admission.py`
- `scripts/qd_ed_n36r3_preparation.py`
- `tests/test_n36r3_accounting_health_repair.py`

Preparation ledger_snapshot/arithmetic and admission.validate_authority now require exactly 75.53031173955723 GPU hours at the existing 505-attempt baseline. Fixed preparation identity is `n36_healthcheck_n36r3_preparation_001426`; the old identity remains charged and cannot be reused. All three journal prefix checks and source/runtime bindings remain strict.

Episode admission now uses the suffix already validated by live_journals for finite cohort accounting. Previously it reclassified the entire retained health history and would reject the old charged preparation ID. Global accounting still includes every retained charge. Other health consumers already use the shared fixed identity; historical artifacts were not modified.

Arithmetic:

- 75.52725286641478 + 0.00305887314245 = 75.53031173955723 retained hours, 505 attempts.
- Retained + 0.23357169027962 margin + 21 finite cohort hours = 96.76388342983685.
- 221.08404692669838 effective cap − 96.76388342983685 − 44 protected hours = 80.32016349686153 conservative unprotected remainder; this is not live spendable headroom.
- 545 prospective attempts; unchanged 40 cells, 41 health invocations AND 1800 cumulative health seconds, 75600 total seconds, no automatic retries; deadline 2026-10-11T11:13:13Z.

Validation: `python -m pytest -q tests/test_n36r3_accounting_health_repair.py`: **19 passed in 1.72s**. `git diff --check` passed. Tests cover exact/stale/mismatched accounting, attempt counts, all three prefixes, fixed/old/arbitrary/reused identity routing, source/runtime binding rejection, and global retained charges versus verified cohort suffix. Initial fixture failures and corrections are recorded in report-v1.json. Only the new focused tests ran; historical fixtures and evidence were left unchanged. No whole-suite green claim.

Remaining gates, in order:

1. **BINDING_REFRESH**: Refresh every affected exact source/runtime-input/closure/inventory/controller/native/manifests/plan/accounting/health-policy binding to this commit as applicable; old frozen artifacts remain unchanged. No binding generated here.
2. **B5**: Obtain new exact independent B5 for the repaired source and refreshed bindings. Prior CPU B5 does not authorize this delta.
3. **ROOT_ADOPTION**: Root must adopt exact source/runtime, reconcile all three current owner journal prefixes and retained costs, and supply finite budget and detached health authority. No current live headroom established here.
4. **PRODUCTION_HEALTH**: After root adoption, genuinely execute and durably charge n36_healthcheck_n36r3_preparation_001426 under current production source/runtime. Require actual parent/import/controller/native/generated attestation and GPU/provider health; old charged health is neither replayable nor readiness.
5. **FIRST_C0**: Only after valid charged fresh health and root detached episode authority may the first C0 be released.
6. **G3**: Pause at first C0 terminal for root review of actual production and audit evidence; no later cell, retry or automatic recovery.

No production health, GPU/provider/evaluation, protected validation/formal access, owner state or ledger writes, frozen artifact rewrites, binding generation, adoption or release occurred. No credentials or prohibited design document were read. No delegation or alternate model invocation. Test authority/evidence is explicitly synthetic and temporary. Source worktree is clean after commit. Stop at this report; scientific score and readiness remain unestablished.
