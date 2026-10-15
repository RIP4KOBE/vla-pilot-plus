# N23 exact-arithmetic audit correction: CPU diagnosis

Correction commit `7f908c58ef7d1ed7867de38a505f861d3c22151e` changes only the independent auditor, preflight raw/synthetic score reconstruction and focused CPU tests. Production/core/provider/main/scientific profiles and runtime are unchanged. The old source fbe5ac9 and all three failed attempts remain immutable. No GPU or recovery admission is granted by this correction.

The authoritative root-limited failure summary is `native-backend-arithmetic-failure-review-v1.json` SHA2566d9381fe1c0b8631df00a7eebb8f89d3b04869991e7e79fe7e8742f3accf1ada. It reports162/176 real batches accepted,7 clipped-quality/mask mismatch batches,7 other batches containing8 raw-score mismatches, full production-helper and raw-projection agreement, FP32 synthetic rejection and BF16 synthetic acceptance. Only that specifically authorized summary was read; its raw-report/ledger refs were not followed.

## Concrete cause and faithful bounded model

Production/helper/provider use `weights / weights.sum()`. The two independent reconstruction paths and synthetic preflight used `weights / 13`. On pinned PyTorch2.7.1 CUDA, a Python scalar divisor uses rounded reciprocal multiplication while the device-tensor divisor uses division. This operation distinction is explicit in [BinaryDivTrueKernel.cu32–50](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/aten/src/ATen/native/cuda/BinaryDivTrueKernel.cu). CPU scalar division normally does not exercise that CUDA optimization, explaining why prior plain CPU parity tests missed it.

A CPU TorchDispatchMode models only that documented scalar-division branch, replacing FP32 tensor/Python-scalar division with multiplication by an explicitly rounded FP32 reciprocal. All other operations remain CPU. It does not claim to emulate CUDA reductions or prove GPU acceptance.

The coefficient3/13 has FP32 bits1047285445 for division and1047285446 for reciprocal multiplication. A fixed BF16 seven-distance vector `[0.2421875,0.08203125,0.08984375,0.208984375,0.1943359375,0.2890625,0.2890625]` gives FP32 weighted scores -0.0562744140625 versus -0.0562744177877903. At BF16 rounding this becomes -0.05615234375 versus -0.056396484375: one final BF16 ULP from a one-bit FP32 coefficient change.

Fixed seeded synthetic full batches reproduce both failure types without reading native evidence: generator seed230930, batch4 gives `clipped_quality_or_mask`; batch8 gives `raw_score` and `n23_seven_point_raw_provider`, -0.0091552734375 stored versus -0.00921630859375 reconstructed. Exact historical function bodies are loaded from committed fbe5ac9 by AST, then tested under the branch model. Production-helper and raw-projection checks pass. The corrected audit passes the same cases under the same model with zero scalar-divisor operations. This predicts that replacing only the auditor's denominator semantics should eliminate these failures. Failure of a later exact assigned-GPU test would falsify its sufficiency and require further diagnosis.

## Layout/dtype/reduction review and remaining uncertainty

Production scoring is already per candidate, with shape1×7×3; it is not one batched norm over all16 candidates. Advanced translation gather has CPU strides(24,3,1), basic action view has(8192,128,1). The explicit CPU test verifies equal values and cumsums for both FP32 andBF16; the actual summary also reports no raw-projection mismatch. The two independent bounded paths use clamp versus min/max but the same finite[-1,1] componentwise semantics. Norm and square retain native BF16 outputs; FP32 weights promote the weighted reduction, and final casting restores BF16. There is no variance computation in this quality. The [pinned CUDA norm implementation](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/aten/src/ATen/native/cuda/ReduceNormKernel.cu) uses FP32 accumulation for BF16 norm inputs; backend-specific reduction order may still differ from CPU and is not simulated here.

Consequently layout/reduction differences are not ruled out globally. The CPU model did not reproduce the exact original FP32 synthetic GPU discrepancy with unchanged CPU reductions, although it reproduced the weight difference and both live error categories on independent synthetic cases. Do not present the CPU result as162→176 GPU acceptance. The required exact GPU test remains the arbiter; no tolerance or failure exclusion is proposed.

## Minimal correction and validation

Three weight-normalization lines now explicitly build the original seven weights and divide by their same-device tensor sum: independent `reconstruct_n23_arithmetic`, preflight raw-score check, preflight synthetic raw generation. The independent auditor never calls production scoring to compute its expected quality. Raw projection checks, exact equality/native hashes, dtype/shape checks, native mask, nextafter score corruption, wrong-bound rejection and original corpus remain unchanged. The normal worker imports this same corrected auditor, so a future cohort and preflight use the same reviewed source.

Reproduce from arithmetic_repair_implementation:

```sh
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_arithmetic_cpu_pathguard_v1 -q tests/test_qd_ed_n23_backend.py --basetemp=../n23-v2-guarded-fixtures-arithmetic-correction-v1 > ../cpu-arithmetic-correction-v1.log 2>&1
```

Result:147 passed in33.52s; zero denied reads and no CUDA initialization. The ten added tests cover historical-fail/corrected-pass branch cases, coefficient/native rounding, gather/view layout for both dtypes, exact raw/quality/mask/bounds rejection and both original synthetic cases. All earlier UUID/worker/metred-receipt CPU tests remain passing. No model/provider/simulator, actual state/ledger write, source integration or GPU execution occurred.

Exact changed-file records:

```json
{
  "commit": "7f908c58ef7d1ed7867de38a505f861d3c22151e",
  "files": [
    {
      "path": "scripts/audit_decision_evidence.py",
      "sha256": "8c47a4d90fbec4e22329bdab7d53fddc2d01e88c742352e4f9e01a65d1dc8182"
    },
    {
      "path": "scripts/qd_ed_n23_backend_preflight.py",
      "sha256": "fbdd30ac1864ea9d282ce849f45faddda4738c6a5f092351e08bd0d2d13795be"
    },
    {
      "path": "tests/test_qd_ed_n23_backend.py",
      "sha256": "a3ebfff43ef3c7d233e891215ba4f355d9877b564b9ca33c2687807274578dd2"
    }
  ]
}
```

The next task is separately bounded engineering-exception-v3 admission preparation, with no change to this numerical correction unless root reviews a new issue. No validation implementation is underway: validation_implementation remains clean at fbe5ac9.
