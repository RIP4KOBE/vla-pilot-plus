# P2 Adaptive EDS+RBF Storage Preflight

- Timestamp (UTC): `2026-08-02T03:43:26Z`
- Worktree: `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling`
- Branch: `exp/eds-init-pg-diverse-sampling`
- Result: `PASS`
- Scope: runtime/storage preparation only; no implementation code modified and no commit created.

## Dirty-worktree boundary

The worktree was already dirty before this task. The following baseline is the
pre-task boundary and was preserved without reset, checkout, clean, revert, or
overwrite.

Command:

```bash
git status --short
```

Result (exit 0):

```text
 M configs/config.yaml
 M core/eds_eval_metrics.py
 M core/eds_mechanism_trace.py
 M core/gemini_grounder.py
 M core/keypoint_detector.py
 M core/rdt_libero_obs_processor.py
 M core/rdt_policy_steer.py
R  docs/01_specs/rdt_eds_guidance_integration_design.md -> docs/01_specs/2026-06-06-rdt-eds-guidance-integration-design.md
R  docs/01_specs/eds-init-pg-diverse-sampling-design.md -> docs/01_specs/2026-07-04-eds-init-pg-diverse-sampling-design.md
M  docs/01_specs/rdt_eds_evaluation_protocol.md
 D docs/01_specs/rdt_eds_mechanism_validation_plan.md
M  docs/04_plans/2026-07-04-eds-init-pg-diverse-sampling.md
M  docs/superpowers/plans/2026-06-06-rdt-eds-guidance-integration.md
 M main.py
 M scripts/rdt_eds_eval_runner.py
 M tests/test_eds_eval_metrics.py
 M tests/test_eds_eval_runner.py
 M tests/test_eds_mechanism_pretest_vis.py
 M tests/test_main_rdt_startup.py
 M tests/test_rdt_libero_obs_processor.py
 M tests/test_rdt_steer.py
 M utils/eds_mechanism_pretest_vis.py
?? docs/01_specs/2026-07-09-rbf-eds-aggressive-eval-design.md
?? docs/01_specs/2026-07-11-rbf-assisted-truncated-rollout-eds-design.md
?? docs/01_specs/2026-07-31-libero-pro-object-swap-vlm-stage-recognition-ablation-design.md
?? docs/01_specs/2026-08-01-p2-adaptive-eds-rbf-ood-optimization-design.md
?? docs/02_analysis/eds_init_pg_diverse_sampling/
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-09-aggressive-rbf-execution-notes.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-09-aggressive-rbf-parameter-sweep.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-10-rbf-s20-qualitative-diversity-report.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-10-renoise-tmax-ablation-report.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-11-renoise-rt1to1-start08-supplement.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-11-rollout-rbf-level3-parameter-sweep.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-rollout-rbf-main-metrics-analysis.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-31-libero-pro-object-swap-vlm-stage-recognition-ablation-report.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/level4_preflight.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/preflight.md
?? docs/03_evidence/eds_init_pg_diverse_sampling/qualitative_crops/
?? docs/03_evidence/eds_init_pg_diverse_sampling/rdt_eds_eval_status.csv
?? docs/03_evidence/eds_init_pg_diverse_sampling/rdt_eds_final_evaluation_report.md
?? docs/04_plans/2026-07-11-rbf-assisted-truncated-rollout-eds-implementation.md
?? docs/04_plans/2026-08-02-p2-adaptive-eds-rbf-ood-optimization.md
?? docs/04_plans/rdt_eds_mechanism_validation_plan.md
?? docs/05_runs/2026-07-14-libero-pro-object-swap-rbf-handoff.md
?? tests/test_stage_recognition_eval_runner.py
?? tests/test_stage_recognition_trace.py
```

Command:

```bash
git diff --stat
```

Result (exit 0):

```text
 configs/config.yaml                                |    6 +
 core/eds_eval_metrics.py                           |   24 +
 core/eds_mechanism_trace.py                        |    2 +
 core/gemini_grounder.py                            |   49 +-
 core/keypoint_detector.py                          |   19 +-
 core/rdt_libero_obs_processor.py                   |    2 +-
 core/rdt_policy_steer.py                           |  596 ++++
 docs/01_specs/rdt_eds_mechanism_validation_plan.md |  490 ----
 main.py                                            |  229 +-
 scripts/rdt_eds_eval_runner.py                     | 2958 +++++++++++++++++++-
 tests/test_eds_eval_metrics.py                      |   64 +
 tests/test_eds_eval_runner.py                       |  749 ++++-
 tests/test_eds_mechanism_pretest_vis.py             |  163 ++
 tests/test_main_rdt_startup.py                      |   56 +
 tests/test_rdt_libero_obs_processor.py              |    4 +-
 tests/test_rdt_steer.py                             |  372 +++
 utils/eds_mechanism_pretest_vis.py                  |  553 ++++
 17 files changed, 5744 insertions(+), 592 deletions(-)
```

## Capacity and writability

Command:

```bash
df -hT /home/hynx /mnt/data/shared2
```

Result (exit 0):

```text
Filesystem     Type  Size  Used Avail Use% Mounted on
/dev/sda3      ext4  437G  359G   56G  87% /
/dev/sdc1      ext4   14T  9.1T  4.1T  70% /mnt/data/shared2
```

Command:

```bash
df -ih /home/hynx /mnt/data/shared2
```

Result (exit 0):

```text
Filesystem     Inodes IUsed IFree IUse% Mounted on
/dev/sda3         28M  2.4M   26M    9% /
/dev/sdc1        448M  653K  447M    1% /mnt/data/shared2
```

Command:

```bash
test -w /mnt/data/shared2
```

Result: exit 0, so `/mnt/data/shared2` is writable.

Acceptance checks:

- `shared2` free space: 4.1 TiB, greater than the required 20 GiB.
- `shared2` inode use: 1%, below the required 90% ceiling.
- `shared2` writability: confirmed.
- Root capacity recorded as 56 GiB free with 87% use.

## RAM

Command:

```bash
free -h
```

Result (exit 0):

```text
               total        used        free      shared  buff/cache   available
Mem:           1.0Ti       338Gi       154Gi       295Mi       521Gi       669Gi
Swap:          8.0Gi       8.0Gi       1.5Mi
```

## Runtime directory and compatibility symlink

Pre-creation inspection:

```bash
ls -ld outputs/ood_eval/p2_adaptive_eds_rbf
```

Result (exit 2):

```text
ls: cannot access 'outputs/ood_eval/p2_adaptive_eds_rbf': No such file or directory
```

Creation commands:

```bash
mkdir -p /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf/
ln -s /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf outputs/ood_eval/p2_adaptive_eds_rbf
```

Both commands exited 0.

Command:

```bash
readlink -f outputs/ood_eval/p2_adaptive_eds_rbf
```

Result (exit 0):

```text
/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf
```

Command:

```bash
df -hT outputs/ood_eval/p2_adaptive_eds_rbf
```

Result (exit 0):

```text
Filesystem     Type  Size  Used Avail Use% Mounted on
/dev/sdc1      ext4   14T  9.1T  4.1T  70% /mnt/data/shared2
```

Command:

```bash
findmnt -no SOURCE --target outputs/ood_eval/p2_adaptive_eds_rbf
```

Result (exit 0):

```text
/dev/sdc1
```

The resolved target is exact and is backed by `/dev/sdc1`, not `/dev/sda3`.

## Current worktree summary

The pre-existing dirty boundary above remains present. This task adds only:

- Runtime directory `/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf/`.
- Compatibility symlink `outputs/ood_eval/p2_adaptive_eds_rbf` (under the ignored `outputs/` runtime tree).
- This evidence file.

No implementation code was modified. No commit was created.

## Final self-review

- Verification timestamp (UTC): `2026-08-02T03:46:03Z`.
- Fresh directory and symlink type checks exited 0.
- Fresh `readlink -f` returned the exact requested shared2 target.
- Fresh `findmnt -no SOURCE --target outputs/ood_eval/p2_adaptive_eds_rbf`
  returned `/dev/sdc1`.
- Fresh capacity and inode checks remained at 4.1 TiB free and 1% inode use
  on shared2; a fresh writability check exited 0.
- Final `git diff --stat` was unchanged from the pre-task baseline above.
- `git status --short -- docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-storage-preflight.md`
  reported the evidence file as new (`??`).
- `git check-ignore -v outputs/ood_eval/p2_adaptive_eds_rbf` confirmed the
  existing `.gitignore` `outputs/` rule covers the runtime symlink.
- No unexpected task-created paths or implementation changes were found.
