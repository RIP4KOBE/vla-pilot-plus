# Arbor leaf 15.2 runtime alias repair

Committed `c427e7acdef0a42fa56c53460dd8587ca3489b1d` on parent `abbdb396439094f034cd859d2d88217072f209d3`. Worktree is clean. CPU-only engineering repair; no efficacy claim or execution authorization.

`validate_release` now includes only the already-validated `runtime['worktree']` compatibility alias alongside the plan worktree and artifact root. The pre-existing exact resolved-checkout identity gate runs first. Generic `verify_files` remains unchanged: lexical AND resolved containment, file SHA-256, optional resolution/link/size bindings remain enforced. Source/task/runtime identities and scientific gates are unchanged.

The only direct N32 `verify_files` call is in the release validator. N32 runner and worker delegate to it. Shared runtime-input inventory checks remain unchanged. Generic runner and N31 contract already include a lexical compatibility worktree root.

Focused tests reproduce the previous rejection with the old allowed roots, accept the legitimate alias without altering frozen records, and reject unrelated lexical aliases (even resolving to the same owner), escaped symlink targets with matching hashes, foreign runtime roots, and SHA/resolution/size/link-target drift. Existing release boundary tests were included; no broad suite was run.

Test command (working directory: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n32_archive_eligible_capture/implementation_worktree`):

```sh
env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n32_archive_eligible_capture/runtime-alias-repair-v1 taskset -c 0,1 python -m pytest -q -p no:cacheprovider --basetemp=/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n32_archive_eligible_capture/runtime-alias-repair-v1/pytest-tmp-v1 tests/test_n32_runtime_alias.py tests/test_n32_production.py::test_detached_release_dag_all30_and_generic_gates tests/test_n32_production.py::test_release_boundary_tamper
```

Exit: `0`. Result: **28 passed in 15.17s**. Wall time: 15.993s. CPU affinity: two CPUs; CUDA hidden; numeric thread limits: two.

Log: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n32_archive_eligible_capture/runtime-alias-repair-v1/focused-tests-v1.log`

Log SHA-256: `a02a94cdfaecb6b1351b9c538c95cfd7d60c1d4c7a3bee4e6f7c565c146a0a7a`

`git diff abbdb396439094f034cd859d2d88217072f209d3 c427e7acdef0a42fa56c53460dd8587ca3489b1d --check`: exit 0.

Changed file SHA-256 values:

- `scripts/qd_ed_n32_release.py`: `76a625532d36994064feaf2ac7a577a4f6e1684925ab037da10359de97965525` (parent: `cfe4ccbfa76c381907b7b93965ad46177c8ca59080e9b13b0532efe16f39d594`).
- `tests/test_n32_runtime_alias.py`: `9c668b861eb41d5658924cb9dd8ecb7357b19b7e71e14959a839a98b6bc4214f` (parent: `new file`).

Limitations:

- Synthetic CPU plumbing evidence only; no efficacy score or execution authorization.
- Actual owning release validation was not rerun. Root retains failed release documents and must review and issue a distinct new source-bound release.
- The synthetic release fixture mocks source verification, downstream runtime-input validation and manifest validation; real file containment and fingerprint verification are exercised. Existing focused boundary tests check gate rejection/forwarding.
- No production fingerprints or manifests regenerated; no owning state/tree/ledger/source changes, adoption, release approval, dispatch, GPU/provider/model/simulator execution, credentials/Poe access, or protected validation/formal result access.
