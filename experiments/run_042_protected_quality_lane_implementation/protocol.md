# Protocol — Run042 protected-quality secondary-lane implementation

Status: `LOCKED BEFORE CORE/CONFIG/TEST CHANGE`

Parent result commit: `f1d16cc`. Run041 decision: `KEEP_H5_V5_OFFLINE_PASS_AUTHORIZE_IMPLEMENTATION_PROTOCOL_ONLY`.

This protocol authorizes TDD implementation of the single `qd_protected_quality_secondary_v1` mechanism. It authorizes no GPU/API/model/LIBERO/reservation/online/Dev/validation/formal execution.

## Exact implementation

Add explicit config `qd_secondary_lane_mode`, allowed values `none` and `protected_reward_v1`, default `none`. `protected_reward_v1` is legal only with grid archive, capacity1 quality cells, sparse priority, causal envelope, exactly one global-quality anchor and fallback none.

`QDArchive.entries` remains the authoritative capacity-one quality map. In protected mode add a separate at-most-one-per-quality-cell secondary map:

- quality update/rebin/visits, reward maps, occupancy and global-best behavior remain exactly the current path;
- after quality update, choose each cell's best fingerprint-distinct alternate from prior quality+secondary+current candidates;
- after rebin, quality and visits follow the current path; remap prior quality+secondary, discard entries without a resulting quality cell, and choose one alternate per quality cell;
- secondary never contributes visits, occupancy, global-best, final elite tensors or execution;
- parent cell counts are produced by the current 1-anchor + sparse15 allocator using quality only; within each cell, use stateless SHA-256 start and round-robin over quality/secondary;
- both parent types enter normal renoise/rollout/update; total compute remains 16 parents and `176/176/11` per complete chunk.

## Allowed files

Exactly:

- `core/qd_ed.py`
- `core/rdt_policy_steer.py`
- `core/eds_eval_metrics.py`
- `configs/config.yaml`
- `tests/test_qd_ed_archive.py`
- `tests/test_rdt_steer.py`

No runner, evaluator, Stage, guidance, RBF, checkpoint, environment or other file may change.

## Required telemetry

Record configured mode; secondary occupied-cell count by iteration; secondary parent count/ratio/fingerprints and cell counts by iteration; cumulative activations; quality/secondary source labels; rebin discard count; invariant-violation count. Existing quality/anchor/accounting/final-selection telemetry must remain unchanged and authoritative.

## TDD hard gates

1. default/explicit `none` fixed-input archive update/rebin/allocation/snapshot/RNG output identity;
2. fail-closed config legality for protected mode;
3. protected update retains exact quality winner while choosing deterministic alternate; duplicate and no-alternate cases;
4. protected rebin preserves quality/visits exactly, discards secondary-only cells, selects one alternate, and never changes global best;
5. all 1+15 parent cell counts equal mode-none on the same state/coordinates; anchor/final quality unchanged; secondary parents actually selected and source-labeled;
6. deterministic stateless rotation and unchanged global Python/Torch RNG;
7. integrated real RDT/QD loop has 10 allocations, secondary activation, 176 search/176 QD/11 calls, finite/mask/qpos/archive/accounting/final-selection invariants;
8. focused and full applicable QD/RDT/metrics regressions pass.

Implementation commit must be separate from this protocol. PASS authorizes only a new CPU integrated mechanism protocol; it is not success evidence.
