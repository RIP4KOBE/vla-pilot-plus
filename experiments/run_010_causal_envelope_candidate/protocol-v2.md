# `run_010_causal_envelope_candidate` Offline-Preflight Repair Protocol v2

Status: `PROTOCOL_LOCKED`

Locked UTC: `2026-08-10T16:44:30Z`

Parent protocol: `experiments/run_010_causal_envelope_candidate/protocol.md`, commit `1017bf0212780b2e386764517661cf9970090f8d`

Implementation commit under test: `930cdb5295b8f9b4ee099298764c3af3c078d6b7`

Scope: the single protocol-authorized Stage-A schema/fixture repair; no algorithm, profile, task, seed, success, safety, compute, promotion, or online threshold change.

## Preserved failed evidence

The first immutable offline artifact is retained at:

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_010_causal_envelope_candidate/analysis/offline_preflight.json
```

SHA-256: `1654574975a02df00be5ac6c78b986b18baf1657bf997a808c1fcb5aa58f9a61`

It is `0444`, reports `781` regression tests passed, checkpoint/input/source fingerprints, 176 evaluations, 11 score calls, zero post-envelope overflow, positive raw overflow, conserved visits at all ten rebins, unchanged global best across every rebin, and unchanged global RNG. Its only hard failure is `synthetic resolution gate failed`.

## Failure classification

This is an offline gate/fixture schema defect, not an algorithm or scientific failure. At synthetic iteration 0, the fixed-initial 4x4 assignment has exactly one descriptor per occupied cell, so fixed within-cell SSE is exactly zero. Resolution improvement is therefore correctly serialized as undefined (`null`), matching the pre-existing fixed-path test semantics. Iterations 1–9 each report finite resolution improvement `1.0`.

The implementation runner incorrectly added an unregistered requirement that every one of ten synthetic iterations have finite improvement `>=0.20`. The frozen parent protocol requires causal integration telemetry and task-linked online median support; it does not define an undefined zero-denominator point as a failure and does not require all synthetic iterations to exceed 20%.

## Sole authorized repair

1. Preserve `offline_preflight.json` unchanged.
2. Change the active offline path to `analysis/offline_preflight.v2.json`.
3. For synthetic resolution only, require at least one finite value and median finite resolution improvement `>=0.20`; continue to record every undefined point explicitly.
4. Keep all other Stage-A checks byte/threshold identical: frozen 781-test command, source/config/checkpoint/LIBERO input fingerprints, 176/11 budget, ten iteration accounting, positive raw overflow, zero post-envelope overflow, visit conservation, global-best rebin preservation, parent slot sum, RNG passivity, storage, pause, credential redaction, and immutable artifact mode.
5. Freeze the online run manifest only from a PASS v2 artifact and bind its SHA-256. The failed v1 hash must also be recorded in that manifest.

No second offline schema repair is authorized. Any v2 hard failure rejects or invalidates the candidate according to the parent protocol, and no GPU dispatch may occur.
