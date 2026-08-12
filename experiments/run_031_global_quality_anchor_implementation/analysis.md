# Analysis — Run031 Global-Quality Anchor Implementation

Decision: `KEEP_H4_V3_IMPLEMENTATION_PASS_AND_AUTHORIZE_CPU_MECHANISM_PROTOCOL_ONLY`

Run031 implemented the frozen algorithm-iteration-3 mechanism after protocol commit `4dc55c5` and committed the implementation separately as `f453e64`. No GPU, API, model, simulator, LIBERO episode, reservation, Dev, validation, or formal resource was used.

## Test result

- TDD red phase: 11 expected failures because the new allocator argument, allocation telemetry, config field, and validation did not yet exist.
- Focused anchor/config tests after implementation: 11 passed.
- Full QD + RDT + metrics regression: 414 passed in 17.83 seconds.
- Python compilation, diff whitespace, whitelist, and credential scans passed.
- Changed files exactly matched the protocol whitelist: three core files, one config, and two tests.

## Hard-gate result

1. `anchor=0` fixed-input legacy allocation identity: PASS, including tensors, ordering, costs/rewards, fingerprints, counts, weights, and Torch global RNG.
2. deterministic global-best selection: PASS for reward/fingerprint/cell ordering.
3. candidate allocation: PASS; the first parent is the dedicated global best and the remaining tensors exactly equal a same-seed standalone population-15 sparse allocation.
4. rescue/no-dedup: PASS; sparse omission becomes one total slot, while a sparse-selected best cell retains its sparse slots plus the dedicated slot.
5. fail-closed validation: PASS for bool, negative, count 2, non-grid, non-sparse, non-causal-envelope, and enabled-fallback configurations.
6. deterministic local RNG isolation: PASS.
7. integrated mechanism/safety/accounting: PASS; ten candidate iterations each sent 16 parents through rollout, reported dedicated versus sparse sources and rescue telemetry, retained archive accounting/final-global-best selection, and produced 176 search evaluations, 176 QD evaluations, and 11 score calls.
8. QD/RDT/metrics regressions: PASS.

The implementation does not establish task success. Historical formal best remains 2/10 and the target gap remains 3. Per the frozen design, the next authorized action is only to commit a CPU integrated mechanism protocol and then create an immutable zero-GPU artifact.

## Frozen implementation checksums

- `core/qd_ed.py`: `4a43cc2db1f1f87eaabf2146058347f119f6059beb4bdf2e67e36f9b6680b653`
- `core/rdt_policy_steer.py`: `bdc523f602453c402aa290ed40e495952578a5e028e0c9374365161255e7cd41`
- `core/eds_eval_metrics.py`: `870636edbaf1023b6c8a71f7f0778e6efa29833fc24f64b651e48714a0d61a31`
- `configs/config.yaml`: `f8a9f07d52ea69ee3a69202ab5b89b4214353208ec27961ebcaef9b3d5b02d57`
- `tests/test_qd_ed_archive.py`: `7a8c7fc2c456f2d3939cb2ba1d8d4cd0113fd22a6d9c356a1f112646a1776f6b`
- `tests/test_rdt_steer.py`: `91503ddc0a72d31da3ca4c4576f0cd2730fbc00060316a1906e8d73145a162c3`
