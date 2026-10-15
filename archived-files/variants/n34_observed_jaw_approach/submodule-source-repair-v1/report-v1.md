# Node 15.4: N34 dependency source repair

Status: implementation committed and CPU-tested; **release remains blocked**.

Commit: `9f817b7c6b7c3861f4789a2d2ad1ab65af7a66a4`  
Base: `3f4ec9e27aeb139db246831e8ffc0325a8ea731c`  
Owning source: `68c341ef6357887c4ae33ddafad00fab17582302`

## Changes

- `scripts/qd_ed_n34_source.py`: allowlisted RDT/LeRobot gitlink resolution through the registered common object databases; exact pinned regular-blob verification; dependency inventory from committed Python/YAML/JSON paths; LIBERO inventory from its regular superproject tree. Retains RDT helper entrypoints, existing record schema, safe relative-path and symlink checks, no-replace-object/no-lazy-fetch behavior, and fail-closed loaded-source checks.
- `scripts/qd_ed_n34_bridge.py`: operational source paths now include the complete dependency inventory. Scientific inventory selection and controller/algorithm semantics are unchanged.
- `tests/test_n34_dependency_source.py`: 26 focused cases covering pinned inventory, wrong bytes, absent files/inventory/databases/objects, wrong gitlink/object type, unpinned source, unsafe paths/symlinks, loaded-module omission, rehashed incomplete bridge records, and linked-worktree local bytes.

Only these three files changed. Dependency bytes, scientific thresholds/audits, controller code, owning state/ledger, driver/lease locks, and other studies were not modified. Working tree is clean after commit.

## CPU verification

`96 passed in 34.28s`

Command: `/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -p no:cacheprovider tests/test_n34_dependency_source.py tests/test_n34_source_controller.py tests/test_n34_worker_entrypoint.py`

Environment: `CUDA_VISIBLE_DEVICES=''`, `PYTHONDONTWRITEBYTECODE=1`. The entrypoint test stops before dispatch; controller tests use inert fixtures. No model, simulator, GPU or native scientific run was performed.

Exact argv/cwd/environment, output, and result are in `test-command-v1.json`, `test-output-v1.txt`, and `test-result-v1.json`. The initial attempt (21 failed, 75 passed) is retained in `test-*-attempt1-v1.*`: its synthetic LeRobot directory was absent when `git add .` ran, so Git removed the fixture gitlink. Materializing that fixture before committing fixed the setup; production checks were not weakened. `git diff --check` passed.

## Deployed bytes and source coverage

Read-only object comparison found matching dependency entries in owning source and clean base:

| Dependency | Pinned object | Deployed matching files | Production matching / missing |
| --- | --- | ---: | ---: |
| RDT | `b896f4dcac8ed1c3fae4a056200db267607f131f` (gitlink) | 132 | 0 / 132 |
| LeRobot | `715debf6c1723a28f1a57d4274a8c4ec35b6a417` (gitlink) | 405 | 0 / 405 |
| LIBERO | `91576c5720b4b4cd1de45896c11d535772f191a0` (tracked tree) | 145 | 145 / 0 |

All 682 deployed selected Python/config files match exact regular Git blobs; no wrong bytes or symlinked source paths were found. All 41 LeRobot hashes in the explicitly authorized review match both their pin and deployed bytes. LIBERO's stale `.gitmodules` entry does not change the committed regular-tree authority.

LeRobot comparison used the existing standalone object database `/home/hynx/lizhuo/VLA-Pilot++/third_party/lerobot/.git` read-only, with the exact gitlink object, solely for this diagnostic. Production verification has **no fallback** to that adjacent checkout/database. The required registered database is absent; `dependency_paths` correctly rejects both current production and owning roots with `pinned third_party/lerobot object database unavailable`.

`deployed-source-verification-v1.json` records each pinned blob, SHA-256, deployed/production status and review-module comparison. `module-origin-replay-v1.json` records a diagnostic replay with inert module objects pointing at the 41 reviewed LeRobot files and a LIBERO environment wrapper: 42 origins passed, and deleting LeRobot inventory reproduced `loaded source not frozen: lerobot.__version__`. This replay imports no dependency and is not a release source record or real-runtime attestation.

## Materialization and remaining release blockers

1. The required registered LeRobot object database /home/hynx/lizhuo/VLA-Pilot++/.git/modules/third_party/lerobot is absent. Both owning and production dependency_paths fail closed. Provision it offline under separate owning maintenance authorization from the existing standalone database, verifying exact gitlink 715debf6c1723a28f1a57d4274a8c4ec35b6a417; do not use HEAD as the authority.

2. This isolated production_worktree lacks all 132 RDT and 405 LeRobot selected source/config files. Before preparing a release here, materialize missing files from exact pinned regular Git blobs after database provisioning and rerun source_record/verify_source. Never overwrite mismatching or symlinked existing files. Owning study_worktree already has all 682 matching selected dependency files.

3. Integrate the repair into the owning checkout through its coordinator and regenerate/review operational source records and dependent manifests. Existing records omit LeRobot/LIBERO and cannot authorize release.

4. Real loaded-runtime closure, native/GPU execution, scientific audits and release authorization remain separate gates. They were not run or assessed here; no release readiness or scientific score is claimed.

No source materialization or shared object-database writes were performed. The deployed owning source bytes need no correction. Database provisioning and any future materialization must preserve the existing standalone checkout and use exact pinned regular blobs, not adjacent working files, branch HEAD, receipts or downloads. Source-only materialization does not supply model weights, assets or runtime release evidence.

The named review was the only autonomy history artifact read. No protected validation/formal results, prohibited design note, credentials, provider/API calls, installations, downloads, new coordinator or subagents were used. No scientific score is reported.
