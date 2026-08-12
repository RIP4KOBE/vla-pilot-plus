# Analysis — Run043 protected-quality lane CPU mechanism preflight

Decision: `KEEP_H5_V5_CPU_MECHANISM_PASS_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`

Run043 passed all ten frozen CPU mechanism gates. Protocol `d37da30` preceded
harness implementation `aed3b75`; immutable artifacts were written only after
that implementation. No GPU, credential, API, model, simulator, LIBERO episode,
reservation, Dev, validation, or formal resource was used.

## Mechanism result

- Both protected cases maintained four secondary cells in every iteration and
  selected 72 secondary parents across ten allocations. Their source totals were
  10 quality anchors, 78 quality-lane sparse parents, and 72 secondary-lane
  sparse parents.
- The mode-none comparator recorded zero secondary occupancy, parents and
  activations, with 10 quality anchors and 150 ordinary QD sparse parents.
- Candidate/comparator expanding fixtures had identical authoritative quality
  bounds, visits, occupied cells, elite rewards, parent cell counts, global best,
  final fingerprint, selected reward and execution source. Bounds expanded six
  times; the protected stable case expanded zero times.
- Every case used ten 16-parent rollout batches, 176 search evaluations, 176 QD
  evaluations and 11 score calls. Nonfinite, action-mask, qpos, archive
  accounting, elite monotonicity, secondary invariant and final-selection
  violations were all zero.
- Dedicated tests passed 3/3; full QD/RDT/metrics regression passed 424/424;
  Python compilation passed.

## Immutable evidence

- Canonical/replay are byte-identical, mode `0444`, 33,587 bytes.
- File SHA-256:
  `32a46d78aa467efdbe4564e0cdaccb90dadaae2e8f8dca18629a1de93ff15f3a`.
- Scientific payload SHA-256:
  `f147b905b68d28c8168642fba0b7470753d5daf9bb91535f8d112ac0498dc73c`.
- Credential matches: 0.
- Root: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_043_protected_quality_lane_cpu_mechanism/analysis/`.

This proves integrated role separation, fixed compute and quality-path identity;
it does not prove LIBERO task success. Historical formal best remains 2/10 and
the target gap remains 3. The next authorized action is only a separately
committed four-cell online mechanism protocol for frozen v5 tasks/seeds.
