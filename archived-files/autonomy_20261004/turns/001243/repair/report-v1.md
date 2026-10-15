# Node 15.6 prospective CPU repair

Committed `e95745853ec2fbb95e55915e99644a4dc0443261` on `codex/n36-cyutility-alias-001243`; direct parent `ca4e6a96d049c7ebb1f302d755883388ddbfdbd8`. Workspace is clean and preserved for coordinator review.

## Changes

- `scripts/qd_ed_n34_source.py`: explicit finite `_cyutility` rule built only from already frozen qualified native path/hash records; current `sys.modules` alias and qualified target must be the same object. Ordinary audits stay strict. Opted-in receipts retain and verify the selected target.
- `scripts/qd_ed_n36_worker.py`: INVALID worker receipts retain actual mismatching runtime origins and identity observations.
- `tests/test_n36_cyutility_alias.py`: focused CPU positives, adversarial negatives, six real import orders, receipt tampering, and before/after-Main diagnostic persistence using inert worker collaborators.

No historical closure was modified. Future prospective construction can explicitly set `module_aliases = build_cyutility_alias_rule(modules)` on a newly reviewed closure; this patch does not authorize its adoption.

## Checks and results

Final command (working directory: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_cyutility_alias_repair_001243/implementation`):

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -s tests/test_n36_cyutility_alias.py tests/test_n34_source_controller.py tests/test_n34_generated_runtime.py tests/test_n34_generated_receipt.py tests/test_n36_audit_repair.py tests/test_n36_production_repair.py --disable-warnings --maxfail=1
```

**239 passed, 74 subtests passed**, exit 0, 64.83 wall seconds and 67.17 CPU seconds. Logs and exact execution metadata: `cpu-checks-final-v1.log` and `cpu-checks-final-v1.json`.

The preceding combined command was identical except that it also included `tests/test_n36_composition.py`. It reached **238 passed and 74 subtests passed**, then failed at fixture setup because the existing contract rejects this checkout's `implementation` directory name. `layout-check-v1.json` records the identical base/working rejection. The layout gate was left unchanged. Full command/output: `cpu-checks-v1.json` and `cpu-checks-v1.log`.

Early focused iterations produced 1 failed/3 passed (qualified-name diagnostic expectation), then 1 failed/33 passed (separately declared required alias), then 39 passed. Those issues were corrected before the final run; exact commands and results are in `report-v1.json`.

`git diff --check ca4e6a96d049c7ebb1f302d755883388ddbfdbd8 e95745853ec2fbb95e55915e99644a4dc0443261` passed. Only the three source/test files above are committed; `git status --porcelain` is empty. Both recorded combined runs used 135.21 CPU seconds total. Earlier development runs took 32.44 wall seconds; their CPU time was not separately measured. All test commands used the required Python, CPU-only visibility, and numerical thread limits of 2.

## Limits and disposition

- CPU engineering evidence only; no evaluation, GPU dispatch, model calls, package installation, source adoption, promotion, or new release.
- N36R1 remains INVALID. Its exact failed-worker native origin remains unknown; no replay or rehabilitation was attempted.
- Independent review and a new recovery identity, accounting, runtime closure, and release are required later before GPU dispatch.
- The prospective rule must be explicitly added to a newly reviewed closure. Existing frozen closures/protocols/releases and owning state/ledgers were not edited.
- Parent verification checks the bound worker identity claim and frozen qualified record; it cannot independently compare objects after process exit.
- The N36 composition fixture rejects this isolated implementation directory name. The identical rejection was reproduced from the supplied base contract; that gate was not changed.
- Real imports exercise pandas and scipy as selected aliases. The sklearn-qualified alias is covered with inert synthetic modules because installed sklearn imports scipy first.
- Full production runtime/recovery acceptance and simulator behavior were not tested. Real-import ordinary inventories are ephemeral test fixtures, not production authority.
