# Node 15.6 independent CPU source review

**Source verdict: PASS. Runtime closure and recovery release acceptance: BLOCKED.**

Reviewed commit `e95745853ec2fbb95e55915e99644a4dc0443261` against `ca4e6a96d049c7ebb1f302d755883388ddbfdbd8`. No source-blocking alias bypass found within the bounded review. This is prospective source acceptance only.

N36R1 remains INVALID, with all charges retained. No replay, rehabilitation, promotion or dispatch.

## Findings

- **F1 — INFO**: Finite authority is preserved: only _cyutility, only nonempty subsets of pandas._libs._cyutility, scipy._cyutility and sklearn._cyutility, exact equality to existing closure.modules records, canonical regular native-extension path and current SHA-256. No observed-import expansion or blanket exemption. Locations: `scripts/qd_ed_n34_source.py:41`, `scripts/qd_ed_n34_source.py:71`, `scripts/qd_ed_n34_source.py:86`, `scripts/qd_ed_n34_source.py:124`.

- **F2 — INFO**: Live alias requires the actual current sys.modules alias object to be the identical qualified target object, with frozen path/hash and qualified module/spec name/origin. Receipt construction rechecks identity and inventory equality. Ordinary auditing and no-rule v2 behavior remain strict within existing auditor exceptions (fileless modules, two Torch virtual namespaces, Git-bound local source and separately validated generated modules). Locations: `scripts/qd_ed_n34_source.py:106`, `scripts/qd_ed_n34_source.py:425`, `scripts/qd_ed_n34_source.py:497`.

- **F3 — INFO**: v3 parent validation requires exact schema/binding, alias evidence names, frozen target and qualified inventory equality, strict boolean identity claim and required-after presence. N36 production parent invokes this validator for both process/closure/context/phase-bound receipts; source-execution receipt handling is compatible with native paths. Parent identity remains a trusted worker's point-in-time claim, not post-exit independent object inspection. Locations: `scripts/qd_ed_n34_source.py:510`, `scripts/qd_ed_n36_worker.py:196`, `scripts/qd_ed_n36_worker.py:327`, `scripts/qd_ed_n36_worker.py:338`, `scripts/qd_ed_n36_source.py:127`.

- **F4 — LOW**: Failure-origin persistence covers RuntimeOriginError inside the worker try block, retaining file, resolved path/hash, module name, spec origin, expected binding and qualified identity comparisons. Diagnostic does not include actual spec.name even though it is checked; pre-try context/dispatch failures are outside this receipt persistence path. These are diagnostic coverage limits, not alias acceptance bypasses. Locations: `scripts/qd_ed_n34_source.py:54`, `scripts/qd_ed_n34_source.py:117`, `scripts/qd_ed_n36_worker.py:204`, `scripts/qd_ed_n36_worker.py:264`, `tests/test_n36_cyutility_alias.py:224`. Follow-up: Consider retaining spec_name and explicit diagnostic stage in a separately authorized diagnostics follow-up; do not claim all possible worker failures produce runtime_failure_origin.

- **F5 — PRODUCTION_GATE**: No production call site constructs module_aliases; only test fixtures opt in. prepare consumes an externally supplied closure. This is deliberate prospective engineering, not an installed runtime repair. A new independently reviewed closure must explicitly add the finite rule using already frozen qualified records and retain the complete strict ordinary inventory. Locations: `scripts/qd_ed_n34_source.py:71`, `scripts/qd_ed_n36_prepare.py:12`, `scripts/qd_ed_n36_prepare.py:19`, `tests/test_n36_cyutility_alias.py:164`.

- **F6 — PRODUCTION_GATE**: Existing recovery cohort/episode identity remains N36R1 with fixed n36r1/001203 names. This source commit does not implement or authorize a fresh recovery release. Future bounded work must provide a distinct reviewed recovery identity and applicable contract/protocol/accounting/release bindings, preserving all N36R1 charges and INVALID disposition. Locations: `scripts/qd_ed_n36_contract.py:11`, `scripts/qd_ed_n36_contract.py:49`, `scripts/qd_ed_n36_contract.py:61`, `scripts/qd_ed_n36_prepare.py:34`.

- **F7 — VALIDATION_LIMIT**: Composition fixture rejects this implementation directory because stop_path supports study_worktree, implementation_worktree or production_worktree only. Identical base/head failure independently reproduced by executing just the unchanged AST-extracted stop_path. Composition remains unverified in this layout; no gate was bypassed. Locations: `scripts/qd_ed_n36_contract.py:35`, `tests/test_n36_composition.py:58`.

## Exact checks and evidence

- HEAD matched; source worktree clean; diff check passed; only the three reported source/test files changed.
- Focused CPU tests: **34 passed, 10 deselected**, 3.671 s wall / 3.722 s child CPU. Command:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n36_cyutility_alias.py -k 'rejections or rejects or no_rule or finite_subset or snapshot or worker_persists' --disable-warnings --maxfail=1
```

- Four additional rejection probes passed: wrong phase, stripped required alias/evidence, live symlink alias, noncanonical frozen target. Probe self usage: 1.270 s wall / 1.360 s CPU.
- Base and head AST-extracted stop_path both reject this checkout layout. The full composition suite was not rerun and remains unverified here.
- All 44 new tests and fixture semantics inspected; positive real-import permutations not rerun. Executor-reported 239-test success is not an independent review result.
- Both CPU commands inherited RLIMIT_CPU=600; pytest had a 150 s timeout. CUDA_VISIBLE_DEVICES was empty; thread environment limits were 2; no bytecode/pytest cache writes. The exact supplementary command is preserved in report-v1.json.

## Hash bindings

- Reviewed tree: `1bce7da3611ab3237c65ac755fac9ac59e4afbf9`.
- Commit object SHA-256: `d648645cf13fd5e4944dfb2dd4b6783a08faf211e05999bc7f361bf7449b2d48`.
- Binary diff SHA-256: `6c3ef5bd1a6493d043496089e54b9e105e2bf9b0f00bab2306353a068a762f82`.

- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/scripts/qd_ed_n34_source.py`: `b2f0532b826868fe035f3dffaf5d136987c9fdfb2a7a5c801975a5b2f502b2f2`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/scripts/qd_ed_n36_worker.py`: `f2b523a3b482a754b17fd5678ccc313bcceadc59dc28be87a5cdee420f8bb7ae`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/tests/test_n36_cyutility_alias.py`: `116031ce54010afd16e7aa66ff75bfe6e2776e7536ffb890cb640d5766a44f8d`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/tests/test_n34_generated_runtime.py`: `c59a44b3bb71518c5183550f29a0dab0e7829f1d39b4c67d5fc2a74a4aa07e90`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/tests/test_n36_composition.py`: `f85c64f0cc54d0b36f1c3e5ab885a9df82f2db7a17f44f6c85de7585a1688f9e`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/scripts/qd_ed_n36_contract.py`: `d6a7d10c3304f4e49f62c676065fa9794c5f230807f4f84cccb51e81552d0bd5`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/scripts/qd_ed_n36_prepare.py`: `d4813d3fb99d8b6a13c1edcee750637702cd2f098a7918d5aa2afb0c59d4397e`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation/scripts/qd_ed_n36_source.py`: `a28f09cb8f899bf0001684f6edcb3b3e52a2ec75d632ba5a5f01b7acd417c771`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/AGENTS.md`: `1e24256700e2f748912dc9eea177408e2f1f8c577e424102d7a5d03849e00e0b`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001243/repair/authority-v1.json`: `f8a1a491c42182683c1d79e85a1355c9d77dfc3381f0f5ef769b27ac25d79ada`.
- `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001243/repair/report-v1.json`: `da55613b7f35127f877dad4157ee3d80c0056c5a8e9f6fd7bff864042f957249`.

Interpreter resolved to `/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12`, SHA-256 `6004c39d3577b31a592ef0af49b4d928d493a9aee4fdec439e19413586937f97`.

## Limitations

- Source PASS is limited to prospective alias-validator changes at the hash-bound commit; no new production closure, scientific result, release or dispatch is accepted.
- No end-to-end production bootstrap/simulator/native GPU evaluation was run. Worker diagnostic test AST-executes intact worker function with inert collaborators.
- Composition fixture layout limitation remains explicit and unresolved.
- Object identity attestation is point-in-time; this is not continuous monitoring or protection against arbitrary in-process tampering.
- All tests used synthetic fixtures; installed import-order coverage was inspected but not repeated. No historical failed native origin was recovered.
- Prohibited design document, protected validation/formal results, credentials, Poe files and Superpowers were not opened.

## Next bounded production requirements

1. Create and independently review a new hash-bound runtime closure with explicit finite module_aliases opt-in against frozen qualified native records; do not modify or relax historical closures.
2. Bind the reviewed operational source commit, complete ordinary inventory, generated rule, interpreter/distributions and native build into the new production artifacts; verify process-bound v3 receipts through the actual source-only bootstrap and parent path with bounded authorized CPU evidence.
3. Resolve or use the supported composition checkout layout and run the focused composition gate without weakening STOP/layout validation.
4. Separately authorize and review fresh recovery identity/episode names, protocol, accounting, source/closure/native bindings and detached release. Existing N36R1 paths cannot be reused.
5. Preserve N36R1 INVALID and every retained charge. No replay, rehabilitation, promotion or GPU dispatch is authorized by this review.

Only these reports and SHA256SUMS were written as review deliverables; source, owning state/ledgers and frozen artifacts were not changed.
