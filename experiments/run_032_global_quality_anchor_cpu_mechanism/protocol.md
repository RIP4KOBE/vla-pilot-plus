# Protocol — Run032 Global-Quality Anchor CPU Mechanism Preflight

Status: `LOCKED_BEFORE_HARNESS_IMPLEMENTATION_OR_ARTIFACT_CREATION`
Date: 2026-08-12
Hypothesis: `H4-v3`
Algorithm iteration: 3

## Authorization and order

- Run031 protocol commit: `4dc55c5`
- Run031 implementation commit: `f453e645828d8076d72eee70c84669b385573b70`
- Run031 result commit: `fe1a06b`

This protocol authorizes only a deterministic CPU integrated mechanism harness, its dedicated tests, two immutable JSON artifacts under the owned root, and result documentation. It authorizes no core/config/runner modification, CUDA/GPU admission, runtime credential use, external API/model/VLM call, simulator or LIBERO reset/episode, attempt reservation, Dev, validation, or formal evaluation.

## Frozen scientific identity

The harness must fail closed unless these committed files match:

```text
core/qd_ed.py              4a43cc2db1f1f87eaabf2146058347f119f6059beb4bdf2e67e36f9b6680b653
core/rdt_policy_steer.py    bdc523f602453c402aa290ed40e495952578a5e028e0c9374365161255e7cd41
core/eds_eval_metrics.py    870636edbaf1023b6c8a71f7f0778e6efa29833fc24f64b651e48714a0d61a31
configs/config.yaml         f8a9f07d52ea69ee3a69202ab5b89b4214353208ec27961ebcaef9b3d5b02d57
```

Candidate profile is exactly the frozen 16-particle, 10-iteration `grid_archive + sparse_priority + causal_envelope_v1 + qd_global_quality_anchor_count=1 + qd_degenerate_fallback_policy=none` profile. Comparator changes only the anchor count to zero. All profiles retain fixed QD/EDS settings and final archive-global-reward selection.

## Frozen CPU fixtures

All cases use seed `32032`, `float64`, population `(16,64,128)`, the real `RDTSteer._eds_guided_denoise_loop`, actual QD archive/allocator/metrics code, real action-mask application, deterministic mocked score/renoise/rollout plumbing, and target `(0,0,0)`. CUDA must remain unavailable to the harness and no environment value or absolute runtime path may enter the scientific payload.

Three complete cases are frozen:

1. `candidate_rescue`: four occupied cells; the global-best cell receives 13 of 16 descriptor visits per batch and each other cell receives one. The deterministic reward carrier keeps the dense cell globally best. This forces its 15-slot sparse count to zero while the dedicated slot keeps one descendant.
2. `legacy_rescue_fixture`: identical fixture and seed with anchor count zero. It establishes that the configured comparator remains a valid 16-slot sparse-QD run; it is not used as a success estimate.
3. `candidate_overlap`: four balanced occupied cells with the global-best cell receiving four visits. Its sparse count must be positive, and the dedicated slot must be added without deduplication.

Each case executes ten iterations. Rollout overwrites the synthetic descriptor/reward carrier deterministically so fixture geometry is independent of parent action identity while every input parent still traverses the actual integrated rollout call.

## PASS gates

All gates must pass:

1. exact frozen source/config hashes, CPU-only execution, finite payload, and zero credential matches;
2. candidate cases report configured count one, exactly ten activations, ten 16-parent rollout batches, and per iteration `1 dedicated + 15 sparse = 16`;
3. `candidate_rescue` reports ten rescues, sparse count zero and total count one for the recorded pre-update global-best cell at every iteration;
4. `candidate_overlap` reports zero rescues, positive sparse best-cell count, and total best-cell count exactly sparse plus one at every iteration;
5. comparator reports count/activation/rescue zero, ten 16-parent batches, and ten total 16-slot sparse allocations;
6. all cases report `176 search evaluations / 176 QD evaluations / 11 score calls`, zero nonfinite/action-mask/accounting/elite-monotonicity/final-selection violations, valid causal-envelope/rebin visit accounting, and selected fingerprint equal to final archive global best;
7. candidate parent-source totals are exactly 10 dedicated and 150 sparse QD offspring; comparator retains the preexisting 160 QD archive offspring source without a zero-valued candidate source key;
8. global Torch RNG state is reset per case; repeated case execution and two independent complete suites are byte-identical in every scientific field and checksum;
9. dedicated harness tests, QD archive tests, RDT tests, metrics tests, and py_compile pass without changing a frozen algorithm/config file;
10. canonical and replay JSON are byte-identical, mode `0444`, secret-free, and written only to:

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/
  run_032_global_quality_anchor_cpu_mechanism/analysis/
    mechanism_preflight.v1.json
    mechanism_preflight.replay.json
```

## Implementation boundary

Only these new files may be added before the implementation commit:

- `scripts/eds_qd_global_quality_anchor_preflight.py`
- `tests/test_eds_qd_global_quality_anchor_preflight.py`

Large artifacts may only be created after that implementation commit and only at the exact owned paths above. Existing core/config/runner/audit/Stage/prompt files, protected untracked design, historical artifacts, and other worktrees are read-only.

## Decision

- PASS: `KEEP_H4_V3_CPU_MECHANISM_PASS_AND_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`. A later protocol must freeze the six online mechanism cells, exact profiles/seeds, runner/audit changes, immutable manifest, GPU admission, credential health, safety, latency, artifact, write-boundary, reservation, and budget gates before any reservation.
- Scientific/integration FAIL: `CONCLUDE_H4_V3_MECHANISM_INVALID_NO_ONLINE`. At most one protocol-first repair is permitted only for a demonstrated harness/schema fixture defect; candidate semantics, thresholds, algorithm blobs, and gates cannot change.

Historical formal best remains `2/10`, target gap remains `3`, and accounting remains 48 effective online episodes, 66 reservations, and `3.7471009444444445` GPU-hours.
