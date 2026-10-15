# N29 CPU Phase A — prepared, not integrated

Commit `427b98703938f4e2a14ff810ff56ed5b7bcbd715`, base `52b9eb0a8a365ee2ea12daffdb7a98c76bec0a72`; clean isolated worktree `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n29_population_relative_trust/implementation`. Exactly three new files; no existing tracked source changed. Source manifest and patch are adjacent. Score/task benefit: **Unknown**. No policy/config/runner/native-audit wiring, GPU execution, API, model, simulator or actual tensor evidence read occurred.

The proposed rule is coherent enough for prospective testing: bound each raw proposal by the same-call population RMS radius before applying the unchanged N27 box ray. It is distinct from N27 box-only scaling and N28 relocation, and from the existing inactive reference-band/reward-confidence/decay controller. It is not the repository's first adaptive mechanism. The existing 88 first-active observations motivate a magnitude test, not a causal success claim. N27 task2 success remains counterevidence against universal magnitude harm.

The principal risk is self-limiting exploration: duplicates, a collapsed population, or a concentrated but wrong OOD prediction can suppress needed search. Outliers can conversely inflate the shared radius. Population RMS is not uncertainty calibration or model probability. Smaller deltas/fewer boundary coordinates must not become efficacy gates. No threshold, coefficient, phase-specific policy, fallback or parameter sweep was added.

`core/qd_population_relative_trust.py` accepts only matching finite FP32/BF16 strided16×8×3 prefixes, computes the literal FP32 mean/square/sum/mean/sqrt and per-row beta, casts the scaled operand once, and calls the unchanged box helper once. It returns prefix, alpha, beta, radius, raw operand norms and scaled operand for later explicit evidence binding. Raw support is checked before scaling. Nonzero norm/spread underflow and any nonfinite intermediate fail closed; these are prospective finite-precision input-domain restrictions and possible future invalidity, not retrospective findings. No epsilon or silent tiny-operand fallback. BF16 casting may exceed the exact-real radius; a counterexample is retained in tests, so no strict post-cast norm bound is claimed.

## Focused evidence

| Run | Result | Boundary |
|---|---|---|
| 1 | Collection error; no test accepted | Guard blocked Python's attempted read of an unowned `__pycache__` path. Original log/guard retained. No payload read. |
| 2 | 34 passed, 0.07s pytest | Owned empty `sys.pycache_prefix`; guard0; CUDA uninitialized. |
| 3 | 4 passed,34 deselected,0.05s pytest | Only appended nonzero-mean and active-box composition cases; guard0; CUDA uninitialized. |

There are38 distinct passing parameter cases. Run2's34 test definitions were unchanged when the final4 cases were appended; unchanged suites were not repeated. Independent Python `fsum`/`sqrt` hand cases check radius/beta/scaled values; exact byte comparisons cover inactive old-ray parity, signed zeros and FP32/BF16 model-like strided/transposed views. Other cases cover genuine zero spread/operand, raw illegal support before beta0, underflow/overflow/nonfinite rejection, centered nonzero mean and active box correction. CPU RNG and inputs are unchanged and outputs carry no autograd graph. The guard mounts an empty `core` package to import only the two pure helpers; it deliberately does not test the production package initializer or complete policy.

Reproducible invocation (run2 now selects all38 in the final test file; historical log contains34):

```sh
taskset -c 0,1 env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n29_population_relative_trust/run_cpu_checks_v2.py
```

The wrapper retains its exclusive historical log and therefore must be copied to a new output version before an authorized repeat. Exact child command/environment are in the resource ledger. Direct guarded test argv is `--noconftest --assert=plain --import-mode=importlib -p no:cacheprovider -q tests/test_qd_population_relative_trust.py`; run3 adds `-k 'nonzero_mean_is_removed or population_cap_then_active'`. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, bytecode disabled, owned tempfile and empty pycache prefix. The original guard was not widened to permit external cached code. Both final runs used affinity[0,1] and Torch intra/inter-op2. No CUDA probe warning was emitted in these logs; CUDA initialization remained false.

Cumulative accounted CPU: **21.522822s /180s**, including all failed test CPU, worktree/Git work, and11s conservative startup/preparation allowance. Measured test child CPU: 8.230861s. Maximum observed test RSS447440KiB; this is an observation, not an enforced RSS claim. Test-process CPU limits90/95s plus100s wall timeout were separately bounded within remaining cumulative allowance; only one test child existed at a time.

## Remaining integration work

Future root-reviewed scope must preserve N28's14 call locations, route both initial/parent through this helper with accurate raw/scaled/applied evidence, retain tail/nontranslation/Stage/provider/model/score schedules, and independently verify the exact FP32 formula/casts on the assigned CUDA backend. CPU layout results do not prove CUDA reduction parity. Native profile/source gates, runtime-domain invalidity treatment, matched Dev plan and finite capacity remain unimplemented and unauthorized here. Current Codex login-only/Poe-disabled behavior and stored credentials are untouched.

Root hypotheses/domain/overlap clarifications are hash-bound in the committed arithmetic spec and input manifest. All artifacts remain under N29; no source merge or online release is implied.
