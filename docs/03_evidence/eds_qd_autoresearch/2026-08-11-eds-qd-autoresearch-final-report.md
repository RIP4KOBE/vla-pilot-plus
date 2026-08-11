# EDS-QD autoresearch current-cycle final report

Date: `2026-08-11`

Decision: `CONCLUDE_NO_ADOPTION_WITHIN_FROZEN_CYCLE_REQUEST_VERSIONED_REDESIGN`.

## Executive result

The primary objective was not reached. The sole promoted EDS-QD candidate scored `1/10` on the frozen independent validation split, versus contemporaneous control `0/10`, and therefore failed the hard `>=5/10` gate. Formal evaluation was correctly not run.

The candidate's QD mechanism worked as designed: it removed post-envelope overflow, improved partition resolution on all ten validation tasks, preserved archive spread and accounting, and passed safety/latency/credential gates. Those improvements did not translate into robust task completion. H1 is supported as a descriptor-partition mechanism and refuted as a sufficient success mechanism.

Further same-cycle optimization is inadmissible because the fixed validation outcomes are now revealed. Modifying an algorithm and reusing those seeds would violate the frozen evaluation-isolation rule. The current cycle therefore concludes without adoption. A future H2 quality/selection cycle requires a versioned design, new holdout seeds, explicit budget, and user approval.

## Algorithm iteration

Only one online algorithm iteration was admitted:

- baseline QD: fixed initial target-relative endpoint-XY quantile bounds with edge clamp;
- candidate: `causal_envelope_v1`, where only the current scored offspring batch can monotonically expand bounds;
- deterministic incumbent and cumulative-visit re-binning after expansion;
- unchanged capacity-one archive, sparse-priority parent allocation, reward elitism, reward/fingerprint global-best execution, 16 particles, 10 iterations, and 176 evaluations per complete chunk.

Algorithm/config fingerprints remained fixed from mechanism preflight through validation:

- `core/qd_ed.py`: `1516bb75c3a5dc3894792d6b8f5daf7f777c48b7d58ea96496da47a986a970b9`;
- `core/rdt_policy_steer.py`: `b8806d7a28e42e6e8a9d2959b5b1d7e5b7c9b304526d4022146c3ba23c8c1ff2`;
- `core/eds_eval_metrics.py`: `d8fb4d04271aa801089a1202af8baf658dc270b751224bc28b4816c9a6a83429`;
- `configs/config.yaml`: `b20791a2792a5f7c6b3b61a2af02055462aa447059802aceb1293a7f77ecdaf8`.

## Evidence trajectory

| Stage | Result | Decision |
| --- | --- | --- |
| Historical replay | 18 compute variants all 0/10 or 1/10; no scale-success relationship | Reject direct compute scaling |
| Allocation ecology diagnostic | Invalid after two telemetry-schema attempts | Park H4; no online claim |
| Offline partition diagnostic | 4,567 exact 4x4 replays; median resolution +30.1%; global best retained | Authorize one H1 candidate |
| Stage-A / mechanism preflight | Fixed compute/accounting; post-overflow 0; mechanism audit PASS | Run Dev-A |
| Dev-A | Candidate 1/4 (task 9), control 0/4, no losses | Keep |
| Dev-B | Candidate 2/4 (tasks 5,8), control 0/4, no losses | Promote to validation |
| Validation | Candidate 1/10 (task 0), control 0/10 | Target FAIL; no formal |

Development gains on tasks 9/5/8 did not replicate under validation seeds. Validation tasks 1–9 ended as `timeout without completion`; this terminal label is intentionally not interpreted as a causal acquisition/grasp/transport/placement diagnosis.

## Validation hard gates

| Gate | Result |
| --- | --- |
| Candidate success `>=5/10` | **FAIL: 1/10** |
| Not below contemporaneous control | PASS: 1 vs 0 |
| Gained-minus-lost nonnegative | PASS: +1 |
| Valid jobs | PASS: 2/2 |
| Resolution support | PASS: 10/10 tasks |
| Raw/post overflow P95 | disclosed `0.9375` / PASS `0.0` |
| Archive noncollapse | PASS |
| Selection latency | PASS: `1.092159x <=1.25x` |
| Safety / qpos / nonfinite / mask / fallback | PASS: all zero |
| Attempt accounting | PASS: 42 effective, 54 reservations |
| Credential/artifact | PASS |
| GPU-hour budget | PASS: `2.934767/48` |

The immutable validation audit has exactly one hard failure: success below 5/10. Proxy or mechanism metrics cannot override it.

## Infrastructure and recovery record

The study preserved several pre-episode infrastructure failures without treating them as policy outcomes: authentication failure under an obsolete credential; an uninitialized exact RDT gitlink; audit paths that referenced preserved invalid v1 artifacts; a Dev-B binder whitelist omission; and one validation admission window with no eligible GPU. Protocol-first, append-only recoveries were used only within their frozen boundaries.

Validation ultimately ran on fresh GPUs 0/1 (UUIDs `GPU-4c78c923-a68a-8e06-e07b-11bdd642118e` and `GPU-053aaa97-5574-46a0-cb86-83d0518d8877`) after two clean snapshots and an immediate dispatch check. No external process was stopped or shared. The credential supplied at runtime was process-local and is absent from tracked documents and audited artifacts.

## Accounting

- Effective online episodes: 42 (mechanism 6, Dev-A 8, Dev-B 8, validation 20).
- Total reservations including preserved pre-episode incidents: 54 of 143 cap.
- Validation GPU cost: `1.747368 GPU-hours`.
- Cumulative cost including pre-episode incident: `2.934767 of 48 GPU-hours`.
- Formal episodes: 0.
- Historical formal best remains 2/10; its target gap remains 3. The rejected candidate's validation gap was 4.

## Reproducibility anchors

- Frozen design commit: `1aee76489ea8989a832dec49b747239f2db90981`.
- Main candidate protocol: `1017bf0212780b2e386764517661cf9970090f8d`.
- Validation protocol: `4b9c72c0eec68538839195a181bd5128b44ab4d7`.
- Validation implementation/code-state: `838b5550f96dfb9d8dbcf59bfc8052b9e1038350` / `5446d4fd7a1011fc1c1b96a5cd4d1c7abaa4cc976657a0241e802385c8cf5024`.
- Validation result commit: `eca85e69504cb4240e8b059f65f6237d4fb54272`.
- Conclusion protocol: `028e3029ee13a7139b5508d250ec9e9947334b80`.
- Validation audit: mode 0444, SHA-256 `3f72d025b492e24e7f615db7c3207c4927710794797dd228edf0579ab1290774`.
- Cycle decision manifest: mode 0444, SHA-256 `dc443cea6baa1194aead93b289a5aef36dde67de54114aa017c53b25727b06a0`.
- Canonical detailed ledger: `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`.

## Final interpretation and next boundary

The study established that the initial fixed QD partition was mechanically saturated, but fixing that defect alone does not approach the required success rate. Historical compute scaling and generic Stage/guidance transitions also provide no viable shortcut. The most evidence-supported future EDS+QD direction is H2: calibrate QD cell quality, replacement, and archive-to-execution selection against observation-derived manipulation progress while keeping evaluator outcomes unavailable to selection.

That direction is not authorized in this cycle. It requires a new versioned design and leakage-safe validation holdout because the existing validation set has been consumed. Until such approval, the correct state is concluded/no-adoption rather than continued parameter exploration.
