# N32 bounded CPU release preparation

**Partial CPU preparation committed; no release or adoption.**

Commit `1e50517b32b63ef9c6ad58cf56e522a436be01b8`; parent `260f19ed29c38aa1c361fda50acb3abdf7fb0af0`. The isolated checkout is clean. Nine new files were added; no existing tracked file changed. The committed inventory contains541 files:9 additions and532 verified invariants.

Delivered separate N32 command/config/source bridge, external-manifest draft preparation, same-process generic/native audit worker and parent verifier, pure supervisor reconciliation/admission guards, Unknown-preserving report integration, focused CPU tests and engineering documentation.

The public worker/supervisor entrypoints remain unconditionally closed. The owning dispatch/state/ledger adapter and root budget/release integration are unfinished. This is useful committed scaffolding, **not an executable cohort controller**.

## Validation

Final command (exit0;50 passed,6 inherited SyntaxWarnings;38.49s):

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 timeout 1200 bash -c 'ulimit -t 1200; exec python -m pytest -q tests/test_n32_release.py tests/test_n32_release_worker.py' > ../release-preparation-v1/test-logs/release-04.log 2>&1
```

Earlier focused runs:35 passed/2 failed (exit1;test expectations corrected),44 passed (exit0),49 passed (exit0). Exact commands, exits and every log SHA256 are recorded in [result-v1.json](result-v1.json). No unrelated broad suite or real native audit was run.

Preparation and committed-draft verification both exited0. All30 manifests were recomposed against actual committed source. The N31 identity file matched the supplied external file byte-for-byte. Verification confirms no prospective artifact/output directory exists.

## External trust chain

1. Committed541-file source and hash-bound runtime metadata + declared task-major row -> exact existing runner/Hydra command composition -> externally computed resolved policy config.
2. Manifest contains source/runtime/task/argv/composed-config/resolved-config; its file SHA256 is in plan. No manifest self-hash or plan hash inside manifests.
3. Context binds plan and external manifest SHA256; worker revalidates source/config/command/runtime and attests loaded source origins/backing bytes before/after Main.
4. Same PID performs generic audit plus independent N32 audit (candidate) or unchanged N31 native audit (controls); receipt binds manifest, context, source, process, task, evidence and report.
5. Parent verifies externally observed process identity, hash-bound receipt and immutable expected identity, then retains native scalar and unchanged generic result/cost/Stage/video checks. Missing/malformed/contradictory evidence is INVALID with charges retained.

Resolved policy-config hashing deliberately preserves default JSON spaces used by the accepted runtime adapter; general documents use compact canonical JSON. Manifests contain neither their own hash nor plan hashes, and generated documents are excluded from source inventory.

Changed-file inventory hash: `0f7c82b3826a6e6e9441a6b51166148ad29c6e4ed9c713932fa3bde99e54d8d5`. Invariant-file inventory hash: `e7c4dce24d5513cf3afd21bdb104adadc220acab6bc50c52747bcb3e45b68a44`. Individual hashes are in [committed-verification-v1.json](committed-verification-v1.json) and [source-inventory-v1.json](source-inventory-v1.json).

Draft: [plan.draft.json](draft-v1/plan.draft.json), with30 external manifests. Root review, protocol, authority and execution release are null; every phase authorization is false. Its inherited runtime metadata names a different worktree and must be reviewed/rebound before adoption.

## Limitations and required next work

- PARTIAL RELEASE PREPARATION: public worker/supervisor entrypoints fail closed unconditionally. Production dispatch, source adoption and owning runner/state/ledger integration are not delivered. The internal worker is exercised only with synthetic CPU fixtures.
- The pre-dispatch guard consumes a caller-supplied settled allowance snapshot. Exact owning-ledger arithmetic, preserved historical health/episode charges, protected reservations, authority verification and atomic lock/reservation integration remain root-reviewed adapter prerequisites; no budget was adopted or amended.
- The draft uses the hash-bound existing runtime metadata whose declared worktree is /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z. Its commands target the isolated implementation checkout. This is prospective composition, not attested launcher/runtime adoption; root must review/rebind and freeze the real source/runtime inventory.
- Loaded module origins and backing source bytes are checked; arbitrary live bytecode, external installed dependencies, checkpoint identity, real task-cache/init-row identity and actual launcher/process/CUDA identity are not independently established by these CPU tests.
- Same-process worker tests exercise real synthetic recorder and generic/native audit paths. Source Git verification is replaced for synthetic fixtures and separately tested on a temporary Git repository and the actual committed draft. Device/process identities are synthetic; parent generic terminal-validator delegation uses a spy rather than real video/Stage/provider artifacts.
- Prospective config serialization uses the exact source dataclass/constructor/parsers and Main field merge, with parity tests against the complete real policy resolver for all arms. It does not replace runtime validators or certify arbitrary later source changes.
- No GPU, simulation, real model/checkpoint loading, Dev episode, historical native payload audit, protected validation/formal result read, online provider call, credential read, dependency installation, additional agent, foreign-study write, driver/coordinator/owning state/ledger change or actual normal runner/state lock acquisition was performed.
- CUDA transfer/device behavior, actual physical action/outcome efficacy and full720-step audit resource use remain unmeasured. The future runner must include both audits inside1800s plus bounded40s cleanup and preserve charges for all INVALID/missing/malformed evidence; zero automatic recoveries.
- HTTP counters remain Unknown. No score, efficacy, promotion, GPU release, validation or formal authorization is claimed.

Root must complete the reviewed production adapter, freeze the prospective protocol/source/runtime and exact finite ledger arithmetic, and issue real authority/release artifacts. The guard is composed and CPU tested but does not itself calculate authoritative owning-ledger balances or acquire production locks. It never signals a running episode on STOP/deadline.

The draft preserves30 primaries, zero recoveries,5GPUh,1800s episode including audits plus40s cleanup, GPU7 with the existing UUID, and2026-10-10T17:42:00Z. Unrun cells remain Unknown. All validation/formal/ablation gates stay closed.
