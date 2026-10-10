# N36R3 admission and separate health transaction

This is CPU implementation for root review, not adoption or execution authority.
The original source remains frozen. No production release is included.

N36R3 keeps the accepted operational protocol and allocation exactly, including
all 40 task/seed/arm rows. The protocol's draft labels describe scientific inputs;
they confer no authority. A released plan now requires distinct externally bound
N36R3 adoption, accounting and independent review. N36R2 approvals cannot substitute.
The original source/runtime closure, native build, controller, all manifests,
worker Main and receipt consumer, required_after modules, and native/generic
scientific audits remain required and unchanged.

## Root-owned artifact order

1. Independently review the exact committed source and adopt its complete accepted
   composition. Refresh actual source/runtime/native/controller bindings for the
   isolated source path. No historic attestation regeneration is required by this
   implementation. The owner route is the lexical `study_worktree`; source cwd,
   imports and provider configuration come from the isolated N36R3 checkout.
2. Bind a new `n36r3-independent-b5-review-v1` using `BINDINGS` in
   `qd_ed_n36r3_admission.py`. Bind `n36r3-source-adoption-v1` to that review,
   source, runtime and route, with root approval.
3. Under the existing owning locks, reconcile the complete current journals and
   create `n36r3-owning-accounting-v1`. Its fields are checked in
   `validate_authority`: exact 505-attempt/75.52725286641478 GPUh baseline,
   three complete journal prefixes, source adoption, unchanged caps/limits,
   `HEALTH`, full snapshot and `qd_ed_n36r3_preparation.arithmetic(snapshot)`.
   This record is the budget authority's `amendment`; its `accounting` remains
   the accepted N36R3 protocol accounting. Adopt the authority into owning state
   (`n36_budget_authority`, budget amendment/caps/reserves) separately.
4. Bind a frozen released plan, including actual manifests, authority and B5
   review. Its `phase_authorization.dev` is a necessary plan condition, never
   permission to execute without the correct detached release. The plan has no
   root-review/release field and no forward readiness reference.
5. Independently create a `n36r3-root-health-review-v1` and detached
   `n36r3-health-release-v1`. The health release has the common bindings of the
   existing episode release plus `healthchecks: HEALTH`; it has no readiness
   field or reference to an episode release. Root approval is externally hashed.
6. Run exactly one explicitly requested health transaction through the existing
   source-only bootstrap, using the health release, timeout 20 and resource ID
   `n36_healthcheck_n36r3_preparation_001314`. The new health CLI is:

   ```text
   $PYTHON -I -S -B -X pycache_prefix=/dev/null $SOURCE/scripts/qd_ed_n36_bootstrap.py \
     scripts.qd_ed_n36_healthcheck --plan $PLAN --plan-sha256 $PLAN_SHA \
     --release $HEALTH_RELEASE --release-sha256 $HEALTH_SHA \
     --resource-id n36_healthcheck_n36r3_preparation_001314
   ```

   This is a template, not an authorized command for this executor. The health
   transaction consumes the same source/runtime closures, runs the existing
   official Codex provider check from source cwd, and checks assigned GPU identity.
   Historical runtime readiness flags retained in the accepted runtime descriptor
   do not supply fresh readiness: the new transaction must actually complete.
7. Review its actual evidence and charged terminal. Create an episode root review
   and detached `n36-execution-release-v1` using the existing exact release schema
   plus `readiness: {health_release: REF, terminal: REF}`. The terminal is the
   hash-bound `healthcheck-result.json` from that health transaction. The readiness
   validator checks source, authority, runtime, provider check, probe evidence,
   frame hash, and (under admission locks) the completed journal lifecycle.
   The runner rechecks current idle device and provider before dispatch.
8. Invoke the existing episode runner only after independently approving those
   bindings. First C0 terminal settlement still precedes `PAUSED_FOR_ROOT_G3`.
   Every restart reverifies the terminal and returns the pause without a second
   charge. There is no resume override or post-G3 continuation implementation.

## Finite accounting and failure behavior

40 × 1840 + 1800 health + 200 unused = 75600 seconds (21 GPUh). All retained
charges, unknown telemetry handling, the 0.23357169027962 GPUh margin, dual caps,
and protected validation/formal reserves are preserved. Health enforces both
41 calls and 1800 cumulative seconds. Each call reserves exactly 60 seconds
(20 probe + 40 cleanup); only 30 full reservations fit. No automatic retries.

Reservations are fsynced under the owner runner/state locks. During lock
transfer an unsettled health record blocks new work. Settlement reuses the
existing fsynced health journal/state synchronization. A crash or interrupt
leaves unresolved work charged as in flight until root reconciliation; it does
not fabricate a zero-duration completion. A failed settled probe vetoes further
health or episode work. STOP/deadline are checked before reservation and launch;
a running child is never killed merely because STOP appears. Health needs its
own 60-second deadline headroom, not a future episode's 1840 seconds.

New unrelated journal activity or changed reservation policy requires fresh root
accounting. Only correctly bound N36R3 lifecycle suffixes may follow the accepted
baseline. No production journals or owner state were written by this executor.

The disabled JSON example is intentionally incomplete and cannot validate.
Tests with temporary owners exercise the actual release, health, admission and
runner consumers with synthetic runtime/source leaves and substituted GPU,
provider and worker boundaries. They do not establish production G3 acceptance.
