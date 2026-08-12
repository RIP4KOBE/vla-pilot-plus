# Recovery Protocol v2 — run_023 versioned manifest rebind

Status: `LOCKED BEFORE RUNNER/MANIFEST PLUMBING, HEALTH CHECK, GPU ADMISSION, OR RESERVATION`

Parent protocol: `experiments/run_023_reward_degenerate_online_mechanism/protocol.md` at `73724cec4d8c60096e5c6baed46274c7098964a3`.

Frozen runner implementation: `d3f09b82dcd87ad0cde2038da0200e93287db3b7`.

Parent immutable manifest v1:

- path: owned `run_023_reward_degenerate_online_mechanism/manifests/mechanism_manifest.json`
- file SHA-256: `d51a44042357b129595cc220faeecd5a9029f2424e0b803711a32ed31a8ec718`
- payload SHA-256: `944047076b4347e582f9dd442e685c7b820f358e78dd0a9631fca01d700066c3`
- mode: `0444`

Incident record: `experiments/run_023_reward_degenerate_online_mechanism/pre-reservation-health.md` at result commit `f189621`; the failed transaction consumed zero reservations, episodes, GPU admissions, or GPU-hours. Global attempt IDs 55–60 remain unused.

## Purpose and invariant

This amendment authorizes only a versioned provenance rebind after the pre-reservation authentication incident advanced documentation HEAD. It does not authorize a scientific retry, same-cell recovery, algorithm/config change, matrix change, threshold change, or new experiment.

The following remain byte-for-byte or value-identical to v1: run_021 core/config hashes; run_022 evidence; runner job/command semantics; profiles and their fingerprints; tasks `[2,3,9]`; seeds `[932032,615132,718536]`; `max_chunks=16`; checkpoint; LIBERO inputs; runtime cache; GPU reference; caps; safety/accounting/latency gates; `formal_authorized=false`; and expected attempt IDs 55–60.

Credential values, prefixes, suffixes, hashes, fingerprints, headers, and exception text are forbidden from source, commands, manifests, ledgers, artifacts, documentation, and Git. A credential supplied through chat is not treated as process-environment configuration. Online recovery may proceed only when the execution process can read a valid `OPENAI_API_KEY` through a non-serialized runtime environment channel.

## Authorized implementation boundary

After this protocol commit, only these existing files may change:

- `scripts/eds_qd_autoresearch_v2_runner.py`
- `tests/test_eds_qd_autoresearch_v2_runner.py`

The change may only:

1. preserve the immutable v1 manifest and verify its fixed SHA-256;
2. introduce owned immutable `mechanism_manifest.v2.json` with a versioned schema;
3. bind v2 to this recovery protocol, the incident result, the implementation commit/code state, the v1 manifest identity, and all unchanged scientific inputs;
4. make job binding, execution, and audit consistently use v2;
5. add tests proving v1 preservation, v2 provenance, exact science identity, credential exclusion, and pre-reservation ordering.

No core/config, Stage, prompt, perception, environment, executor, evaluator, v1 runner/audit, or protected untracked design may change.

## Freeze and transaction order

Runner/tests must pass and be committed before v2 is created. The v2 file must then be created once under the owned root, mode `0444`, while v1 remains unchanged. Before any health check, v2 must validate against clean branch HEAD and verify v1 plus every frozen scientific fingerprint.

The resumed transaction remains fail-closed:

1. pause, write-boundary, storage, free-space, v1/v2, code, profile, checkpoint, LIBERO, cache, and run_022 checks;
2. runtime credential presence and one real bounded Stage/Poe health check, without secret serialization;
3. only after health PASS, two-snapshot GPU admission on idle GPU 0–7 and immediate dispatch snapshot;
4. only after admission PASS, append exact global attempt IDs 55–60 and dispatch the unchanged six cells;
5. audit, strict credential scan, immutable result freeze, result commit, task-level analysis, and target-gap reflection.

A failed health or admission check consumes zero attempt and yields no algorithm evidence. If the existing process environment cannot be safely replaced, remain blocked before health rather than moving the chat credential through a logged tool argument.

## Decision boundary

Successful v2 freeze authorizes only the already-frozen Run023 transaction. The original online PASS/FAIL gates and promotion decision remain authoritative. Dev-A, Dev-B, validation, and formal remain unauthorized until Run023 produces a valid PASS and a subsequent protocol explicitly authorizes the next stage.
