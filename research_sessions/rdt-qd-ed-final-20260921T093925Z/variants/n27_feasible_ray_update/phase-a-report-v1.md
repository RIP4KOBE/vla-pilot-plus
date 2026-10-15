# N27 pure feasible-ray helper — CPU phase complete

Commit `bcec3e5e37ee90374c44ca794c81b86eafcb40d6` on `codex/n27-feasible-ray-update`, based exactly on `6026794cd5d52f3a5054bf2704ebb3c516f9f47e`. The isolated worktree is clean. Only three added files are committed: numerical helper, standalone guarded tests and implementation note. All existing science/config/policy/audit/controller files remain unchanged. Score: **Unknown / not evaluated**.

The helper computes FP32 per-particle alpha from the original finite native `[16,8,3]` prefix and existing operand, rejects nonzero updates outside strict-interior support, applies the stated finite-rounding box correction and native cast, and preserves zero-update original bytes. All-zero alpha is1; positive-infinite directional ratios from tiny updates are nonbinding. This is maximal according to specified FP32 ratio arithmetic, not a claim of exact-real maximality or exact rounded collinearity.

34 distinct checks passed: 33 in the initial matrix (1.0959708350s), followed only by the newly added explicit FP32 correction-edge test (1.0814277281s). Cumulative test wall time including dependency startup: **2.1773985630s /180s**. No failures or guard denials occurred. Both runs used CPU affinity2, Torch intra/inter-op2, CUDA hidden/uninitialized; no actual evidence, model, network/API, simulator, production import, state/ledger or GPU action. Logs and summaries are retained unedited. CPU results do not prove future CUDA arithmetic parity or task efficacy.

Independent scalar FP32 reference, fixed examples and bound properties cover FP32/BF16, contiguous/transposed/model-like sliced layouts, native alpha1 byte parity on nonzero coordinates, zero/exterior/signed-zero retention, one-active-row and mixed-sign limited steps, near-boundary and extreme/tiny finite values, immutable input bytes/strides/storage/RNG, no model-Jacobian construction and malformed/nonfinite/support/device rejection. Large unrelated numerical ranges or old science suites were not explored.

Exact initial command:

```text
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -I -B /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n27_feasible_ray_update/implementation/tests/test_n27_feasible_ray_update.py
```

The second command adds only `FeasibleTests.test_fp32_rounding_box_correction_is_observable`. `cpu-results-v1.json` records selections, per-run source digest, memory/thread/device boundary and cumulative duration. The guard's sole `/proc` allowance is installed Torch's own `_load_global_deps` reading self/maps; no process inventory or actual-record access occurred.

The minimal proposed next integration is documented in the committed note: preserve the same N26 geometry/normalization/native proposed operand, use the helper only in explicit N27 branches at the two existing initial/rollout update sites, assign returned prefix directly, and preserve other coordinates/tail plus literal legacy `+=` paths. Future N27 evidence must separately identify raw proposed operand, alpha and actual before/after; it must not call the proposed operand the applied delta. A subsequent native reference may reuse unchanged N26 geometry reconstruction, but independently verify the new update and source binding. None of that integration is implemented or released by this delivery.

The accepted scope's conditional16-primary screening plan, protected reservations and Codex-only runtime remain root-owned and unopened. This helper's normalized feasibility cannot establish post-scheduler action bounds or physical success.
