# Node 15.4 N34R2 identity repair

Implemented and committed on `codex/n34-production-integration`. CPU engineering result only, pending root review/adoption.

- Base: `908efa454450a079c5ed6a1b10eff1eb9ef290c1`
- Commit: `82fe104752fa89d56501bbc78bae856e6bd6ad8a`
- Cohort: `N34R2_OBSERVED_JAW_APPROACH_DEV_20261008`
- Fresh matrix: 30 task-major C0/Q0/N34 cells, `n34r2_dev_tXX_PROFILE_20261008` with lowercase profile.
- Mapping: 1 recovery, 9 baseline, 20 development; zero automatic retries.

Task0/C0 explicitly replaces `n34r1_dev_t00_c0_20261008`. The replacement pins `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000624/terminal-closure-v1.json` with SHA-256 `ed88e8a29c196be8bc37f7ca8d00a067bc346d213a7c28647fb89e456ff2fdfc` exactly as supplied by authority-v1.json. The CPU handoff compared these constants against that authority; it did not inspect owning terminal or ledger contents.

Admission requires both historical invalid attempts, with N34 charged to baseline and N34R1 charged to recovery. Unknown outcomes remain unknown, prior resource costs remain global, and unknown GPU durations fail closed. No historical records were rewritten. Historical source remains in Git at the base commit.

Only the contract and release accounting consumer changed in production source. Other identity consumers obtain rows/provenance from the contract. Frozen tasks, seeds, profiles, algorithm, audit requirements, caps, deadline, promotion (30 valid cells, N34 >=5 and >=both controls), and complete-valid-triple futility remain unchanged.

Changed files:

- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_lifecycle.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

Focused verification:

- `PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 TMPDIR="$PWD/../recovery2-identity-repair-v1/tmp" python -B -m pytest -q -p no:cacheprovider --basetemp=../recovery2-identity-repair-v1/pytest-identity tests/test_n34_recovery_identity.py tests/test_n34_lifecycle.py` — 129 passed, exit 0 (2.65s); log `test-identity.log`.
- `PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 TMPDIR="$PWD/../recovery2-identity-repair-v1/tmp" python -B -m pytest -q -p no:cacheprovider --basetemp=../recovery2-identity-repair-v1/pytest-consumers tests/test_n34_release_boundary.py tests/test_n34_production_integration.py` — 379 passed, exit 0 (30.64s); log `test-consumers.log`.

Total: 508 passed. The consumer test run reported six existing invalid-escape SyntaxWarnings in unchanged source. `git diff --check` passed; the worktree is clean. Tests cover all 30 stale N34R1 rows, stale terminal/context/closure bindings, replacement and bucket enforcement, both retained invalid charges, unknown history costs, zero retries, native audit strictness, unchanged promotion and futility. Release documents and dispatch/process records created by tests are synthetic CPU fixtures only; no production approval was generated.

No GPU/provider experiment calls, subagents, protected guidance/results access, owning state/ledger writes, runtime preparation, or production release generation occurred. Scientific score: not measured (CPU identity engineering only).

Turn625 composed runtime closure remains preparation with OLD identities. Root must separately review/adopt this commit, regenerate full runtime composition, and verify accounting/admission before any separately authorized launch.
