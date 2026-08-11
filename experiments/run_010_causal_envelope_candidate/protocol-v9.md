# `run_010_causal_envelope_candidate` Dev-B Confirmation Protocol v9

Date: 2026-08-11 UTC

Scope: `QD-1` confirmation of the unchanged causal-envelope candidate on the preregistered independent Dev-B seeds. Parent scientific protocol: `protocol.md` commit `1017bf0212780b2e386764517661cf9970090f8d`. Dev-A PASS artifact: `analysis/dev_a_audit.v2.json`, mode 0444, SHA-256 `9c6d3ecee60d50c7e574b2a795c864483c85c812c0883a96ec81aa5d5d889fa9`.

This protocol authorizes only minimal Dev-B runner/manifest/audit plumbing followed by one paired eight-cell execution. It does not authorize an algorithm/config/threshold change, neighboring candidate, Dev-A reuse, validation, or formal evaluation.

## Target-linked rationale

Dev-A candidate gained task 9 for 1/4 versus paired control 0/4 with zero losses. Historical formal best remains 2/10 and target gap remains 3. Dev-B must test whether an unchanged QD partition/archive mechanism reproduces a real success advantage under independent seeds; mechanism-only repetition is insufficient.

Predicted flips: retain/recover task 9 first, with tasks 3/5/8 allowed as additional gains. Refutation: a success tie, any lost control success, or only proxy improvement.

## Frozen algorithm and matrix

No algorithm/config file may change. Required pre/post implementation SHA-256 identities:

- `core/qd_ed.py`: `1516bb75c3a5dc3894792d6b8f5daf7f777c48b7d58ea96496da47a986a970b9`;
- `core/rdt_policy_steer.py`: `b8806d7a28e42e6e8a9d2959b5b1d7e5b7c9b304526d4022146c3ba23c8c1ff2`;
- `core/eds_eval_metrics.py`: `d8fb4d04271aa801089a1202af8baf658dc270b751224bc28b4816c9a6a83429`;
- `configs/config.yaml`: `b20791a2792a5f7c6b3b61a2af02055462aa447059802aceb1293a7f77ecdaf8`.

Matrix:

| Profile | Tasks | Seeds | Episodes |
| --- | --- | --- | ---: |
| contemporaneous control | `[3,5,8,9]` | `[558482,165717,160148,160312]` | 4 |
| causal-envelope candidate | `[3,5,8,9]` | `[558482,165717,160148,160312]` | 4 |

Both profiles keep full 720-step episodes, strict perturbations, checkpoint, Stage settings, executor, reward/model/VLM calls and EDS/QD compute unchanged.

## Protocol-first implementation boundary

After this commit, only `scripts/eds_qd_autoresearch_runner.py` and `tests/test_eds_qd_autoresearch_runner.py` may change. TDD must first add failing coverage for:

1. exact Dev-B matrix/seeds and continued rejection of formal phase;
2. strict credential detection that rejects actual long tokens/environment equality but does not flag ordinary `Task-Specific` text;
3. immutable `dev_b_manifest.json` binding Dev-A/mechanism PASS hashes, algorithm hashes, checkpoint/LIBERO/runtime cache, exact matrix, attempt/GPU caps and `formal_authorized=false`;
4. `run-dev-b` requiring immutable PASS Dev-A v2 plus the Dev-B manifest before health/admission/reservation;
5. `audit-dev-b` target, pooled Dev-A+Dev-B, validity/safety/mechanism/latency/accounting/credential/budget gates;
6. CLI exposes only freeze/run/audit Dev-B additions and still has no validation/formal command.

The implementation commit must precede manifest/result artifacts. Existing v1/v2 audits and the original immutable manifest are never overwritten.

## Stage A — Dev-B manifest freeze

After targeted and frozen nine-file regression PASS, create exactly one immutable `manifests/dev_b_manifest.json`. It must include current committed runner provenance, unchanged algorithm hashes above, original manifest SHA-256 `cb211e2ed3fe2cfa2512f0982153295c9f23fa9964e3f623d1ef3b1eef10ae34`, mechanism v2 `c7e93f9255aee10f71e2519fa9e539cd537ca4ed89c905cebe334db5c68508ab`, Dev-A v2 hash above, checkpoint/LIBERO/runtime-cache identities, exact matrix, attempt cap 143, GPU-hour cap 48, allowed GPUs 0–7, and `formal_authorized=false`.

## Stage B — Dev-B execution and audit

Only after the manifest is immutable and all pause/storage/service checks pass:

```bash
python scripts/eds_qd_autoresearch_runner.py run-dev-b --gpus auto --timeout-seconds 28800
python scripts/eds_qd_autoresearch_runner.py audit-dev-b
```

Fresh two-snapshot plus immediate GPU admission is mandatory. One worker per eligible GPU; no co-location with external compute. Runtime credential remains ephemeral environment state and is never persisted. Any initialized policy outcome is not retried; only audited exact-cell infrastructure failures can use the remaining three same-cell recovery slots, which cannot cover a full eight-cell matrix.

## Hard gates and decisions

All must pass:

- 8/8 Dev-B cells valid at exact bindings;
- candidate Dev-B success count `>= control + 1`;
- candidate loses zero control-success tasks and Dev-B gained-minus-lost `>=1`;
- pooled Dev-A+Dev-B gained-minus-lost `>=1`;
- candidate safety categories do not exceed control; no qpos/nonfinite/action-mask/fallback/accounting/global-best/visit error;
- resolution improvement median `>=0.20` in at least 3/4 Dev-B tasks; post-envelope overflow P95 `<=0.25`; raw overflow disclosed; archive modes/spread noncollapsed;
- candidate selection latency P95 `<=1.25x` sparse mechanism-preflight reference; no call/evaluation increase;
- attempt count `<=143`, cumulative GPU-hours including incidents `<=48`, artifacts/strict credential audit PASS.

PASS decision: `KEEP_AND_AUTHORIZE_NEW_VALIDATION_PROTOCOL`; validation remains blocked until its protocol/result commit. Any target/safety/validity failure: `REVERT_CAUSAL_ENVELOPE_AND_TRIGGER_OUTER_LOOP`; preserve code/artifacts, do not try neighboring envelope parameters, and do not enter validation.
