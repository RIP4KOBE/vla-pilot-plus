# `run_010_causal_envelope_candidate` Dev-A Execution/Audit Binding Protocol v6

Date: 2026-08-11 UTC

Parent scientific protocol: `experiments/run_010_causal_envelope_candidate/protocol.md`, commit `1017bf0212780b2e386764517661cf9970090f8d`

Mechanism audit recovery protocol/result: `experiments/run_010_causal_envelope_candidate/protocol-v5.md`, commit `adfadeaf3efcf2dfad257edfb3a452fd3028ac9b`; immutable PASS audit SHA-256 `c7e93f9255aee10f71e2519fa9e539cd537ca4ed89c905cebe334db5c68508ab`.

Frozen scientific execution revision/code-state: `d018f8acb12263d81c65f8eb717f9c987459e991` / `3626b52b619d6c951aee48f07c206ce5af44dff8cf12fad40d85ab01c9a9839c`.

Scope: execute and audit only the parent protocol's already-authorized paired Dev-A while preventing the two audit invocation defects proven in mechanism preflight. This amendment changes no EDS+QD algorithm, config, task, seed, checkpoint, runtime cache, immutable manifest, success/safety/mechanism threshold, attempt/GPU budget, or promotion decision.

## Frozen matrix and bindings

- Profiles: contemporaneous control and `eds_quality_diversity_sparse_causal_envelope_v1`.
- Tasks: `[3,5,8,9]`; seeds `[512905,150741,463456,452903]`; four full 720-step episodes per profile.
- Control config fingerprint: `298badf27bc38e5f3fa0ae52c43686beb4e4e81ae39de87caa3c4e086d200e0e`.
- Candidate config fingerprint: `65502f2ad2a42c5dbbb67a18744d8319ca334d8a2f6e7fff5b9286749c69ddf0`.
- Both output roots are absent at protocol lock. No Dev-A cell has been reserved or executed.

The runner must be invoked while detached at the frozen scientific revision with the exact initialized RDT gitlink. It must perform pause/storage/service health, fresh two-snapshot plus immediate GPU admission, then reserve and dispatch the eight unique cells. Runtime credential is ephemeral process state only and cannot enter worker commands, manifests, artifacts, docs, or Git. Any policy outcome is not retried; only the parent's audited exact-cell infrastructure recovery rule applies.

## Dev-A audit procedure

The audit must also run at the frozen scientific revision so the expected bindings match the executed job manifests. The audit-time credential predicate is the strict v2 predicate already validated by mechanism audit v2: equality to a present environment secret, a standalone `sk-` token with at least 20 payload characters, an API-key assignment with at least 20 payload characters, or an Authorization Bearer token with at least 20 payload characters. The immutable runtime cache is not edited. This prevents the known ordinary `Task-Specific` substring false positive without weakening detection of actual credentials.

The unchanged parent Dev-A hard gates remain binding: 8/8 valid cells; candidate success at least control +1; zero loss of control-success tasks; gained-minus-lost at least one; all validity/safety/accounting/mechanism/latency/budget checks pass. A tie or any target-gate failure immediately rejects and reverts the causal-envelope change after preserving evidence. A full PASS authorizes only a new Dev-B protocol; Dev-B, validation, and formal remain unauthorized by this amendment.
