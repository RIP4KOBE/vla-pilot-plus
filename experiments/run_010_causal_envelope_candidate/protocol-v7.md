# `run_010_causal_envelope_candidate` Dev-A Gate-Path Recovery Protocol v7

Date: 2026-08-11 UTC

Parent Dev-A binding protocol: `experiments/run_010_causal_envelope_candidate/protocol-v6.md`, commit `dc0b00cc92a79d4ba71620d9488aaa659bf13c97`.

Frozen scientific execution revision/code-state: `d018f8acb12263d81c65f8eb717f9c987459e991` / `3626b52b619d6c951aee48f07c206ce5af44dff8cf12fad40d85ab01c9a9839c`.

Scope: recover exactly once from a local pre-admission control-gate path error. This amendment changes no algorithm, profile, task, seed, checkpoint, immutable run manifest, scientific gate, attempt/GPU budget, runtime cache, or promotion rule.

## Observed boundary

The first v6 Dev-A command exited in 1.5 seconds from `run_phase` before credential validation, service health, job construction, GPU admission, attempt reservation, worker launch, or episode initialization. The frozen runner reads only canonical `analysis/mechanism_preflight_audit.json`, which is the preserved invalid v1 invocation, instead of immutable passing `analysis/mechanism_preflight_audit.v2.json`.

Post-failure assertions:

- attempt ledger remains SHA-256 `5f4971382bc97f25c103a4a904a761cb45fa872412b0c4caa1377d6c4561065c`;
- no `dev_a__*` output directory or Dev-A GPU manifest exists;
- zero Dev-A reservations, service calls, GPU-hours, episodes, task outcomes, or formal uses occurred.

## Exact recovery

After this protocol commit, one process-local recovery is authorized at the frozen revision:

1. import the unchanged frozen runner;
2. set only its in-memory `MECHANISM_AUDIT_PATH` constant to immutable v2 path `analysis/mechanism_preflight_audit.v2.json`;
3. assert that artifact is mode 0444, SHA-256 `c7e93f9255aee10f71e2519fa9e539cd537ca4ed89c905cebe334db5c68508ab`, and `passed=true`;
4. call unchanged `run_phase(DEV_A_LEVEL, gpus="auto", timeout_seconds=28800)` once.

No tracked source or artifact is edited or copied. The v1 and v2 audits remain immutable. Because the failed invocation occurred before reservation, this is a gate-path retry rather than an episode/cell retry and consumes no same-cell recovery slot. All v6 execution/audit bindings and parent Dev-A target gates remain unchanged.
