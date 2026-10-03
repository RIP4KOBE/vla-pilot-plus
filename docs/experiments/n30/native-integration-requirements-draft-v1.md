# N30 native execution integration requirements (draft; no dispatch authority)

This records the remaining integration work after the initial scientific CPU implementation. It does not authorize a worker, healthcheck, model load, new budget, or protected split.

The base worker scripts/qd_ed_n23_worker.py dispatches cohort validation/native receipt handlers by explicit plan/profile. Merely adding an N30 YAML cannot safely use that worker: N30 needs its own source/profile/plan contract and a receipt path which binds the exact new continuation evidence. Relevant reference modules are scripts/qd_ed_n29_{contract,prepare,supervise,report,preflight}.py and existing general decision-evidence auditing. Their40-cell/four-arm/>=5 rules must NOT be copied unchanged into this12-cell/three-arm/>=3 screen.

Integration should reuse proven low-level process/identity/accounting helpers while keeping old cohorts and scientific paths unchanged. Required new scope:
- exact12 new Dev identities, tasks0..3 in original task order, C0/Q0/N30; C0baseline4, Q0/N30development8; no inherited/retried/resumed cells;
- explicit candidate profile delta from frozenQ0 solely continuation mode, with default-off C0/Q0 behavior and extra native observation events confined toN30;
- one owned admitted GPU process, frozenGPU7 UUID/CUDA0/EGL4/runtime when available, boot/driver/provider/source/runtime identities revalidated; no touching other users;
- exact study-only runner/state/attempt/healthcheck locks and ledgers, current578attempt/100GPUh caps, local6GPUh inclusive bound and protected reservations; source release cannot expand budget;
- successful Main completion is separate from simulator task success; same-worker evidence audit completes in the metered worker lifetime, identity/receipt/hash verification on supervisor without another audit/model pass;
- forN30 independently verify complete8-step actual observation binding, previous native winner provenance, eligibility sign/identity/reset/guidance-gap clearing, row15 exact shifted56+fresh8 copy plus existing mask, and canonical row association. Unchosen continuations are not physical outcomes; an inserted continuation need not become the final selected action;
- new operation is native copy/mask and CPU feedback arithmetic, not a new gradient kernel. Choose the minimal adequate native proof; do not mechanically rerun N29's RBF arithmetic24-case standalone GPUproof. CPU mocks alone do not establish actual production wiring; at least native runtime traces/receipts must independently prove the operation;
- report primary176/11 separately from unchanged Q0 total256provider evaluations/16score batches and other actual counts (observed19RBF,21B16model forwards per guided;5B1per unguided). Validate source and actual counters, and report full-episode differences;
- stop on invalid execution, source/identity/telemetry failure, loss of exclusive GPU admission, or inability to fit the next attempt into the frozen budgets; fail/recovery consumption retained. At complete three-arm task blocks stop numeric futility if wins+remaining_tasks<3. Completed candidate>=3/4 and>=C0/Q0 plus mechanics/validity is screen PASS only;
- keep validation/formal closed; use fixed seed identities from the accepted originalDev plan without inspecting protected outcomes.
- output path must resolve through variants/n30_executed_progress_continuation/artifacts, whose binding is already recorded; frozen plans/source manifests and small audit documents stay under the same variant. Do not put massive output under implementation/outputs.

Root independently reviews the scientific delta and integration code, then freezes a final operational release. Initial CPU implementation remains the only current execution authority.

