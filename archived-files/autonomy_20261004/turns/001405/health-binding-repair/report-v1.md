# Node 15.6 bounded CPU binding repair

Status: **CPU repair committed; runtime refresh and independent review required.** This is not completion of the original goal.

- Source before: `21fc93e5667a83520401282d4ba8e945f954f99b`
- Source after: `4347951a24b63cdb7f0c8a585591d89f1be778ae`
- Branch: `exp/n36r3-generated-import-001299`
- Changed files: `scripts/qd_ed_n36_healthcheck.py`, `scripts/qd_ed_n36_runner.py`, `tests/test_n36_parent_binding.py`, `tests/test_n36_runner.py`.

Both callers omitted the mandatory importlib-alias binding. The health failure occurred before resource admission. Both now use the unchanged worker binding helper with the verified detached release reference as context, the validated plan's runtime closure, the actual parent PID/start ticks/boot ID, and `runtime_before`. Release validation already binds the detached release to the plan and source. No audit validation, scientific method, threshold, or operational ordering changed.

## CPU validation

`CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q --tb=short -p no:cacheprovider --basetemp=.pytest_cache/health-binding-repair tests/test_n36_parent_binding.py tests/test_n36_importlib_alias.py tests/test_n36_frozen_alias.py tests/test_n36_runner.py > .pytest_cache/health-binding-repair-tests.log 2>&1`

**239 passed in 28.19s; exit 0.** Both actual caller paths ran under the real source bootstrap and attestor using synthetic files. Missing bindings and wrong process identities failed before the mocked admission/lock boundary; retained context, closure and phase substitutions were rejected. Release governance was stubbed for these CPU tests. Existing alias and lifecycle regression tests also passed.

The first run used the same selection without `--tb=short` or log redirection and returned 127 passes / 112 setup errors because `.pytest_cache` did not exist. After `mkdir -p .pytest_cache`, the full selection passed. Exact commands, statuses and the local test-log hash are retained in report-v1.json. `git diff --check` passed, and git status was clean after commit.

## Required follow-up

The commit changes frozen source identity. An authorized owner must refresh the relevant source/runtime closure, review fresh CPU evidence, and obtain independent source/runtime review and matching adoption/plan/release bindings before any new health attempt. Do not replay the old launch. Episode readiness and execution release remain separate gates. No frozen artifacts were changed here.

No GPU use, episode evaluation, operational health launch, release enablement, provider probe, owning-state/ledger write, or other executor occurred. Protected results and the prohibited design file were not opened; credentials remained unopened. No scientific score or runtime-readiness claim is made.
