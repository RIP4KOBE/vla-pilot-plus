# Strict UUID normalization CPU repair

Infrastructure fix commit: `9822ed48d3049c2258484be65bf53b638be97661`, parent `77302aab40d6b059e85c8d1d8011ea36cb3d3856`. Exactly three files change: scripts/qd_ed_audit_backend.py, scripts/qd_ed_n23_worker.py, tests/test_qd_ed_n23_backend.py. Full patch is cpu-uuid-normalization-source-diff-v1.patch. Existing science/profiles/arithmetic/provider/Stage/controller/admission/cohort/protocols are unchanged.

Root reports the original metered preflight failed before any arithmetic because PyTorch returned the bare UUID while the frozen runtime used GPU- prefix. This executor did not read that actual report or any native/outcome data. The fix accepts only proper hyphenated UUID strings, with optional case-insensitive GPU- prefix; canonical output is GPU- followed by lowercase UUID. Missing, malformed, non-string, repeated-prefix, non-hyphenated, whitespace-padded and MIG values are rejected. Wrong proper UUIDs also fail assignment verification.

assigned_cuda_identity preserves raw actual_uuid exactly as observed and adds canonical physical_uuid. create_backend carries both values into backend metadata. Frozen binding identity remains recorded. CUDA_VISIBLE_DEVICES must identify only physical7 or its exact normalized UUID, exactly one CUDA device must be visible, current logical device must be0, and the observed canonical UUID must equal the frozen identity. UUID format normalization does not substitute another device or bypass ownership checks.

The downstream worker receipt verifier previously compared raw actual_uuid literally and would repeat the same failure. It now independently checks canonical physical_uuid and canonical(raw actual_uuid) against the frozen runtime identity, retaining the raw value. It rejects missing/inconsistent raw/canonical metadata. N23 backend physical_uuid is compared to this canonical worker value. Original v1/v2 arithmetic-preflight proof readers retain their exact canonical physical_uuid == frozen runtime UUID checks; no tolerance or scope changes were made.

CPU verification: **111 passed in29.55 seconds** in tests/test_qd_ed_n23_backend.py, log cpu-uuid-normalization-v1.log. This includes proper bare/prefixed/case spellings, the historical GPU7 form supplied by root, missing/malformed/wrong identifiers, visible environment/count/current-device gates, raw/canonical receipt binding and negative mutations, plus existing worker/backend metering/source/receipt tests. All device/property methods were mocked for identity tests; torch.cuda.is_initialized() remained false. The same historical-data read guard reported zero blocked reads. No provider/model/simulator/GPU call, actual outcome read or real state/ledger/lock mutation occurred.

Reproduce from implementation:

```
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_v2_cpu_pathguard_v1 -q tests/test_qd_ed_n23_backend.py --basetemp=../n23-v2-guarded-fixtures-uuid-review-new
```

This commit grants no retry or release. The original failed preflight remains charged and invalid; existing one-opportunity gates remain closed. The original v2 source_delta allowlist also deliberately rejects these additional infrastructure edits until a separately reviewed prospective engineering exception binds the exact new source. Root requested that separate preparation only after this concrete fix; its implementation and tests will be reported independently. No repaired plan/proof or executable draft is created by this initial fix.
