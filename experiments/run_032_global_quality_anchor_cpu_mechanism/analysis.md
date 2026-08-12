# Analysis — Run032 Global-Quality Anchor CPU Mechanism Preflight

Decision: `KEEP_H4_V3_CPU_MECHANISM_PASS_AND_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`

Run032 passed all ten frozen CPU mechanism gates. Protocol `a252ad1` preceded harness implementation `83a9715`, and immutable artifacts were created only after that implementation commit. No GPU, API, model, simulator, LIBERO episode, attempt reservation, Dev, validation, or formal resource was used.

## Mechanism result

- `candidate_rescue`: 10/10 anchor activations and 10/10 rescues. At every iteration the recorded global-best cell had zero sparse slots and exactly one total slot.
- `candidate_overlap`: 10/10 activations and zero rescues. At every iteration the global-best cell had a positive sparse count and total count exactly sparse plus one, proving no deduplication.
- `legacy_rescue_fixture`: configured/observed anchor count zero, zero activations/rescues, and ten 16-slot sparse allocations with the preexisting source schema.
- Both candidate cases reported exactly 10 dedicated plus 150 sparse QD offspring across the chunk; the comparator reported 160 sparse QD offspring.
- Every case used ten 16-parent rollout batches, 176 search evaluations, 176 QD evaluations, and 11 score calls.
- Finite, action-mask, qpos, archive accounting, elite monotonicity, causal-rebin visit preservation, final-selection, source, RNG, frozen-hash, and secret gates passed.
- Dedicated plus QD/RDT/metrics regression: 417 passed. Python compilation passed.

## Immutable evidence

- Canonical/replay: byte-identical, mode `0444`, 11,411 bytes.
- File SHA-256: `31dd437c377c41af369336f6161f194012143dbcf847a2ae150ac82fdf3de24b`.
- Scientific payload SHA-256: `f147193e1589b09c178706c0c94890242393e84a12fe5612b151bb7f0ab8ddf4`.
- Credential matches: 0.
- Root: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_032_global_quality_anchor_cpu_mechanism/analysis/`.

This proves the implemented mechanism and accounting under deterministic CPU integration; it does not prove task success. Historical formal best remains 2/10 and target gap remains 3. The next authorized action is only a separately committed six-cell online mechanism protocol and immutable manifest workflow.
