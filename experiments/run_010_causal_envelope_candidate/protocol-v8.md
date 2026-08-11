# `run_010_causal_envelope_candidate` Dev-A Audit-Upstream Recovery Protocol v8

Date: 2026-08-11 UTC

Parent Dev-A protocols: scientific `protocol.md` commit `1017bf0212780b2e386764517661cf9970090f8d`; binding `protocol-v6.md` commit `dc0b00cc92a79d4ba71620d9488aaa659bf13c97`; pre-admission recovery `protocol-v7.md` commit `bcf4e4ffae795c6f1225637ac9b62d845f21ca62`.

Frozen scientific execution revision/code-state: `d018f8acb12263d81c65f8eb717f9c987459e991` / `3626b52b619d6c951aee48f07c206ce5af44dff8cf12fad40d85ab01c9a9839c`.

Scope: preserve a completed valid Dev-A execution and correct one audit-only upstream path. This amendment authorizes no API call, GPU admission, attempt, episode, algorithm/config/task/seed/checkpoint/manifest change, threshold change, or promotion change.

## Frozen Dev-A execution

The v7 process-local gate recovery passed health/admission and executed attempts 19–26 on GPUs 0 and 1. Both job manifests are valid.

- Control tasks 3/5/8/9: fail/fail/fail/fail = 0/4.
- Candidate tasks 3/5/8/9: fail/fail/fail/success = 1/4.
- Gained `[9]`, retained `[]`, lost `[]`; target gain is +1 with zero loss.
- Candidate resolution median by task: 3 `0.62347`, 5 `0.65301`, 8 `0.53008`, 9 `0.49968`; mechanism support 4/4.
- Candidate raw/post-envelope overflow P95 `0.9375/0`; selection-latency ratio to sparse preflight `0.96824`.
- Candidate/control collision-push-drop-wrong-object counts 0/0; candidate qpos/nonfinite/action-mask/fallback counts all 0.
- Dev-A device-wall sum 1,601.047 seconds = 0.444735 GPU-hours; mechanism + Dev-A audit cumulative 0.746570 GPU-hours; including preserved pre-episode import incident total 0.770164 GPU-hours.
- Attempt ledger SHA-256 `591be9196ef53bdd77dfc895100b304cb7b4be1202124dd49724de3ee392ade7`; 14 effective phase cells, 26 append-only reservations, audit PASS.
- Dev-A GPU admission SHA-256 `0bd1214cc3c38c2eb94748698e6c1a95a456c8aa310768c2ad0f359057c61b1b`; `run_manifest.csv` SHA-256 `34482e0edf516200f3593fa70d3863920ced0f22a04efc0adae87f805b108280`.

These task outcomes are immutable and cannot be retried.

## Invalid first Dev-A audit

The first frozen-revision audit used the strict credential predicate but did not remap its internal `MECHANISM_AUDIT_PATH`; it therefore read preserved invalid mechanism v1. Artifact `analysis/dev_a_audit.json`, size 361,984 bytes, SHA-256 `95d7d1fbb8fe0f076267cdc4af2aedcad8c7822be6128b53f948d7e8e23e3d4a`, has exactly one hard failure: `mechanism preflight audit is not PASS`. All Dev-A validity, target, mechanism, safety, latency, attempt, credential, and budget components in the same artifact pass.

After this protocol commit, freeze that artifact mode 0444 and never overwrite or use it as the final promotion decision.

## Sole corrected audit

Exactly one no-episode v2 audit is authorized at the frozen revision:

1. assert clean tracked state, exact RDT gitlink, Dev-A job validity, immutable result/ledger/admission hashes, and absence of `analysis/dev_a_audit.v2.json`;
2. import the unchanged frozen runner and set its in-memory `MECHANISM_AUDIT_PATH` to immutable passing `analysis/mechanism_preflight_audit.v2.json` (SHA-256 `c7e93f9255aee10f71e2519fa9e539cd537ca4ed89c905cebe334db5c68508ab`);
3. use the same strict credential predicate validated by mechanism audit v2;
4. call unchanged `audit_dev_a(path=analysis/dev_a_audit.v2.json)` and freeze the new artifact mode 0444.

Every parent Dev-A hard gate remains unchanged. Any v2 hard failure rejects the candidate. A full v2 PASS freezes run_010 as a Dev-A success and permits only a new Dev-B protocol; it does not authorize Dev-B, validation, or formal by itself. No further Dev-A audit repair is allowed.
