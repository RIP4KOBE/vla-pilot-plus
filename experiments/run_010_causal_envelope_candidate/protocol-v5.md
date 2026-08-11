# `run_010_causal_envelope_candidate` Frozen-Revision Audit-Recovery Protocol v5

Date: 2026-08-11 UTC

Parent scientific protocol: `experiments/run_010_causal_envelope_candidate/protocol.md`, commit `1017bf0212780b2e386764517661cf9970090f8d`

Final exact-cell recovery protocol: `experiments/run_010_causal_envelope_candidate/protocol-v4.md`, commit `80169057ef170dbe702c5cd25c6f4ac03b14381e`

Frozen scientific execution revision: `d018f8acb12263d81c65f8eb717f9c987459e991`; code-state SHA-256 `3626b52b619d6c951aee48f07c206ce5af44dff8cf12fad40d85ab01c9a9839c`.

Scope: preserve the completed final six-cell recovery, classify the first mechanism audit as an invalid audit invocation, and authorize exactly one evidence-only v2 audit at the frozen scientific revision. This amendment authorizes no episode, retry, GPU dispatch, algorithm/config/task/seed/checkpoint/manifest change, threshold relaxation, promotion change, or formal evaluation.

## Completed final v4 recovery

After the v4 gitlink/import checks and a passing pre-reservation service health check, fresh admission selected idle GPUs 0, 1, and 2. Attempts 13–18 executed the unchanged six frozen cells: control, sparse reference, and causal-envelope candidate on tasks 3 and 5 with seeds 512905 and 150741 and `max_chunks=2`.

- Base runner exit code: 0; wrapper wall: 489.7 seconds.
- Control / sparse / candidate success: 0/2, 0/2, 0/2. All six cells ended as timeout without completion; this two-chunk plumbing phase is not a target-promotion comparison.
- Final-run profile wall: 382.305 / 260.393 / 443.906 seconds = 0.301834 GPU-hours; including the earlier pre-episode import failure, run_010 online infrastructure/device total is 0.325428 GPU-hours.
- Candidate raw-initial-bounds overflow P95: 0.9375; post-envelope overflow P95: 0.0.
- Candidate / sparse selection-latency P95: 2.65048 / 2.73929 seconds; ratio 0.96758.
- Candidate mechanism fields, visit conservation, global-best consistency, score/evaluation accounting, nonfinite/action-mask/fallback and qpos/execution checks passed in the per-job evidence.
- Final GPU admission artifact SHA-256: `209553223e711b95763dba3942d79e97debb1f072dd7f90b3e0a65bbfb559914`.
- Final attempt-ledger SHA-256: `5f4971382bc97f25c103a4a904a761cb45fa872412b0c4caa1377d6c4561065c`; attempts 1–12 remain append-only pre-episode aborts and attempts 13–18 are the only effective six-cell outcomes.
- `run_manifest.csv` SHA-256: `f5ce5dcab7578b39ae8cb20b3ad29132a574366e158a69b0836e819da62751b1`.
- Owned worktree/artifact exact scan found zero copies of the supplied runtime credential. No credential value or reversible credential fingerprint is recorded.

## Invalid first audit invocation

The first `audit-mechanism-preflight` command was mistakenly invoked at documentation/state HEAD `eb9dd7338dd2568505c2c162e74ab29d0967395c`, not at the frozen scientific revision used to bind and execute the jobs. It wrote `analysis/mechanism_preflight_audit.json`, size 287,125 bytes, SHA-256 `d42dee30fad4c9d1ef6e8ffa02b73cb78830e736d7ea7c5e7877be8a9be4d6c7`, with `passed=false`.

That artifact is invalid audit evidence for two independent, non-scientific reasons:

1. job binding at the wrong Git/code-state produced expected config fingerprints `9a7a6edb...`, `6c079ed1...`, and `d423aaa6...`, which cannot match the frozen execution fingerprints;
2. the audit's credential detector flags any case-insensitive `sk-` substring. The immutable cached prompt contains the ordinary heading `Task-Specific`, so the cross-word `sk-` substring was incorrectly classified as credential-like material. The match is only 11 characters; strict token/assignment/Bearer patterns over 192 text artifacts find zero credential-like tokens.

The invalid artifact must be retained at its original path, changed to mode 0444 after this protocol commit, and never overwritten or used for mechanism/promotion conclusions.

## Frozen v2 audit procedure

After this protocol commit, exactly one corrected audit is authorized:

1. temporarily detach the current worktree at `d018f8acb12263d81c65f8eb717f9c987459e991` while keeping `third_party/rdt` at clean gitlink `b896f4dcac8ed1c3fae4a056200db267607f131f`;
2. assert the frozen code-state, immutable run-manifest hash, attempt-ledger hash, and absence of tracked worktree changes;
3. build the three frozen mechanism jobs and require exact config fingerprints:
   - control `7dd8ca75990065be07e878b98b9f54fbee48dbeeeb60b313f4440d8bdd567ed2`;
   - sparse `d083b1b73956939cd0d6c65e89d6e162f5338414c53b5bd526f0b9b5202519f2`;
   - candidate `296f14aee15a39eac941661de852421a3e799f05e24c52a6db94933bfcf2bf83`;
4. replace only the audit-time credential predicate with a strict detector for actual environment-secret equality when present, standalone `sk-` tokens of at least 20 payload characters, API-key assignments with at least 20 payload characters, and Authorization Bearer tokens with at least 20 payload characters; do not edit the immutable runtime cache or scientific runner;
5. call the unchanged mechanism audit logic and write a new immutable artifact at `analysis/mechanism_preflight_audit.v2.json`; preserve all original scientific gates and metrics;
6. restore the target branch and verify that only the protected untracked stage-guidance design remains.

If v2 fails any job validity, mechanism, accounting, safety, latency, budget, attempt-ledger, artifact or strict credential gate, mechanism preflight fails and Dev-A remains blocked. Only a full v2 PASS may unlock the already-frozen Dev-A. No third audit repair is authorized.

## Target and stopping boundary

The historical best remains 2/10 and the target gap remains 3 because mechanism preflight supplies no formal or Dev-A promotion result. A v2 audit PASS permits only the parent protocol's paired Dev-A. It does not authorize Dev-B, validation, or formal evaluation, and it does not permit tuning from the six mechanism outcomes.
