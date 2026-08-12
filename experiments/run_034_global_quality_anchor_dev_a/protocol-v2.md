# Protocol v2 — outer-loop v3 conclusion and evidence freeze

Status: `LOCKED AFTER RUN034 RESULT COMMIT AND BEFORE V3 DECISION MANIFEST OR FINAL REPORT`

This protocol authorizes documentation and immutable evidence freezing only. It authorizes no algorithm/config/test change, new candidate, anchor-count or sparse-ratio adjustment, threshold/seed/task sweep, API/model call, GPU admission, LIBERO episode, attempt reservation, exact-cell recovery, validation, or formal evaluation.

## Trigger

Run034 immutable audit `2e590656dd60a18a17bf45ff7a2e1e9209daaaa34980a5d686b9d6f8879a0e68` is a valid Dev-A target FAIL. On frozen paired tasks `[0,1,2,4,6,7]`, control and `eds_qd_global_quality_anchor_v1` both scored `0/6`. The candidate therefore failed both preregistered task gates (`>=3/6` and at least `+1` versus control) despite 1,060 anchor activations and 425 real rescues. Result commit `79a2de70bfad50e0d4cb597a844bc85c2965b82f` binds analysis SHA-256 `b8f94f6c27daa4d35130275dde62adac8d2bcccccf326835808fb30a47d1c4c3`.

The v3 design permits one H4-v3 candidate and states that any valid Dev-A failure ends the cycle. It explicitly forbids a fourth candidate and outcome-driven adjacent tuning. Validation and formal are therefore unavailable.

## Read-only evidence packet

- V3 design and Run030 allocation reconstruction: 3,205 exact transitions, 67.11% global-best omission, exact 1+15 repair and median coverage retention 1.0.
- Run031 implementation and Run032 integrated CPU mechanism evidence.
- Run033 initial pre-episode DINO incident, protocol-first exact-cell recovery, paired task outcomes and immutable audit.
- Run034 protocol/runner/manifest, attempt ledger, admission, raw metrics, videos, task outputs, audit and analysis.
- V1 H1 and v2 H2 results and their immutable cycle manifests, retained only as historical evidence.
- Canonical append-only state, log, findings, trajectory and unified iteration ledger.

All other workspace/worktree/shared2 paths remain read-only. The protected untracked Stage-transition design remains unread, unmodified, unstaged and uncommitted.

## Deterministic synthesis and decision

1. Preserve the allocation finding: sparse QD often omits the archive global-best lineage, and one dedicated anchor reliably repairs that omission at fixed 176/176/11 compute.
2. Preserve Run033 as limited positive evidence: candidate `1/3` versus control `0/3`, gained task 9 and lost none.
3. Give the frozen unseen Dev-A result priority for transfer: `0/6` versus `0/6`, no gained task, and every task timed out without completion.
4. Do not reinterpret 425 Dev-A rescues, clean safety, acceptable latency or exact mechanism accounting as success progress.
5. Do not tune anchor count, allocation ratio, reward threshold, seeds or tasks from Run034 outcomes, and do not enter validation/formal.
6. Conclude v3 with no adopted successor. Historical formal best remains `2/10`, target gap 3, and formal episodes remain zero.
7. Any future execution requires a new versioned design, leakage-safe splits, explicit budget and explicit user approval. It may use v3 only as historical evidence and must not continue this revealed Dev-A search.

The frozen decision label is `CONCLUDE_NO_ADOPTION_WITHIN_V3_CYCLE_TARGET_NOT_MET`.

The evidence-supported research diagnosis remains inside EDS+QD: global-best lineage retention is not sufficient when archive reward/final selection is weakly aligned with manipulation completion. This is a diagnosis for a future design, not authorization for an additional candidate.

## Required outputs

- immutable owned `run_034.../manifests/cycle_decision_manifest.json`, mode `0444`;
- v3 final report under `docs/03_evidence/eds_qd_autoresearch/`;
- updated human current status;
- append-only state/log/findings/trajectory/unified-ledger reflection;
- strict credential scan, artifact hashes, Git/write-boundary verification;
- one result/reflection commit after this protocol commit.

The decision manifest must bind the v3 design, protocol/result commits, Run030–034 manifests/audits/analyses, algorithm fingerprints, task-level outcomes, reservation/GPU accounting, zero validation/formal use, protected-file exclusion and continuation boundary. It must contain no credential value or reversible fingerprint.
