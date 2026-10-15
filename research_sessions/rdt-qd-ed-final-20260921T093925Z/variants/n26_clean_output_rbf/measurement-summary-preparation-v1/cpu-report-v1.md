# N26 scalar summary — CPU preparation

Completed a small external descriptive summarizer. It reads five root-bound control JSON files and every accepted N25/N26 metric ref, without reading receipt bodies, tensors, Stage responses, full journals or protected data. All actual experiment inputs remain closed. Frozen 602 source, previous terminal reader, live controller/state/budget and original evidence remain unchanged.

`summarize` is a pure aggregation function; `build` validates the finite input associations and original native/scalar denominators. The optional CLI is bounded to 60 seconds, immutable owned output and 128 MiB including its input manifest. It preserves INVALID/prefix status and all missing-phase/unequal-count limitations. The disabled template is not an execution authorization.

Validation:

* Initial run: 20 passed, 1 failed in 0.18 s; guard blocked two attempted dependency `.pyc` reads, so this run is **not guard-clean**. No bytes were read from those denied paths. The assertion failure was a test-fixture shallow-copy restoration error, preserving a forbidden filename into the next negative check.
* Final aggregation run: **27 passed in 0.22 s**, guard violations 0, no Torch import, CPU 2, CUDA invisible. Fixed deep-copy fixture restoration; dependency loading compiles the exact already-hashed two pure sources, without widening the guard to `__pycache__` or the whole sibling directory.
* Final minimal CLI follow-up: **1 passed, 27 deselected**, guard violations 0. Checks disabled input, owned successful output and refusal to overwrite. The prior 27 aggregation cases were not rerun for this CLI-only addition.

The final 28 distinct cases include independent hand-calculated mixed-arm/phase norms and ratios, per-task denominators, unequal call counts, zero-guided/null phases, legal all-zero gradients, missing/extra/duplicate cells or calls, accepted receipt scope, attested absence versus positive-guided absence, nonfinite data, inconsistent components/source, hash drift, finite file/byte caps and no raw-event fallback. No science/model/math suite was run.

Exact final aggregation command, from this directory:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python cpu_guard_v1.py guard-final-v1.json
```

CLI follow-up uses `cpu_guard_v1.py guard-cli-v1.json test_scalar_summary_v1.py -k cli_disabled` under the same environment. Preserve the supplied logs; use different log names for any independent rerun.

All artifacts are local to this preparation directory. The static input inventory records the allowed source/serializer references and accepted pure dependencies. Source/delivery manifests include every failure and final log; synthetic basetemp trees are retained but excluded from the compact manifest. No actual scalar result, native arithmetic, causal benefit or next-method recommendation is claimed. Root review and a separately frozen complete accepted-prefix input manifest are required before any real read.
