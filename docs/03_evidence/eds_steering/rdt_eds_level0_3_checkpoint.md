# RDT+EDS Level 0-3 Checkpoint

Timestamp: `2026-06-11T14:29:36+00:00`

## Status

- Level 0 deployment unit checks: complete
- Level 1 mechanism probe: complete
- Level 2 online smoke: complete
- Level 3 `libero_object` evaluation: complete
- Level 4 LIBERO-PRO OOD: not started

## Reports

- `docs/03_evidence/eds_steering/level_0_deployment_correctness.md`
- `docs/03_evidence/eds_steering/level_1_mechanism_probe.md`
- `docs/03_evidence/eds_steering/level_2_online_smoke.md`
- `docs/03_evidence/eds_steering/level_3_libero_object_success.md`

## Key Findings

- EDS deployment is correct: counters, finite scores, selected-best consistency, and online metrics passed across Level 2 and Level 3.
- EDS is not just unguided denoising: every guided chunk records score/resample/renoise/rollout counts matching `cem_iters`.
- Algorithmic effectiveness is mixed:
  - Unguided RDT: `9/10` on Level 3 `libero_object`.
  - Best normal EDS: `p32_c20 = 8/10`, within 10 percentage points of unguided but much slower.
  - Common lower-cost EDS settings: `p16_c10`, `p16_c20`, `p32_c10` all `6/10`.
  - CEM setting: `p32_c10_cem = 7/10`.
  - Ablations: `zero = 6/10`, `shuffled = 6/10`, `inverted = 3/10`.
- Current evidence suggests the EDS loop is deployed, but reward/keypoint semantics and trajectory-selection quality need further debugging before claiming robust guidance benefits.

## Level 4 Gate

Level 4 remains blocked/pending until user approval. Earlier preflight also reported missing local LIBERO-PRO files:

- `third_party/libero_pro/perturbation.py`
- `third_party/libero_pro/evaluation_config.yaml`

No `outputs/rdt_eds_eval/level4_*` directories were generated in this run.
