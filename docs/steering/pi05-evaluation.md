# π0.5 + VLS evaluation

This evaluation validates the public π0.5 checkpoint in this repository's shared online control framework. It is not a reproduction of the upstream VLS score and is not an ObjectSwap OOD result.

## Registered protocol

Registered before the first episode on 2026-10-16 UTC. The complete formal cohort passed audit; diagnostics are kept separately. The ten-task run uses runtime commit `6d713b28908e58f460c1be18a4c0f51bc9fa270c` and GPU4 / EGL6.

| Item | Setting |
| --- | --- |
| Policy | `lerobot/pi05_libero_finetuned_v044`, revision `dbf8a3f794a9c4297b44f40b752712f50073d945`; strict complete loading with verified tied weights |
| Dependencies | New Python 3.12.12 environment; PyTorch 2.7.1+cu126, Transformers 4.53.3, NumPy 2.2.6, MuJoCo 3.7.0, patched Robosuite 1.4.0; LeRobot commit `715debf6c1723a28f1a57d4274a8c4ec35b6a417`; existing RDT environment untouched |
| Task suite | Standard `libero_object`, tasks 0–9, one episode per task |
| Seeds | 44, 235, 43, 546, 6, 621, 197, 87, 151, 548, respectively |
| Initialization | Official suite initial states; five settling steps; existing `per_seed_v1` policy RNG mode; no RDT ObjectSwap RNG restoration |
| Observations | Two policy cameras at 128×128, checkpoint preprocessing; 640×640 visualization |
| Execution | Ten actions per block, at most 720 environment steps |
| Sampling | Eager BF16 model with FP32 normalization; ten flow steps; twenty particles; gradient scale 80, diversity scale 10; start time 0.8; sigmoid k=25, x0=0.75 |
| FKD | `max`, lambda 10, adaptive ESS, frequency 5; actual integer Euler-step scores at 2, 7, 9 and final particle ordering |
| Online service | Codex CLI / `gpt-6-astra` / `ultra`; 180-second request timeout; eight transport retries, 30-second backoff |
| Stage/reward | Fresh identity, stages and reward per task; current-image online Stage; local reward/gradient scoring; existing common target-distance and controller contracts |
| Diagnostic | Task 0 in a separate directory; excluded from the formal denominator |

The PI05 adapter retains its existing gradient-reward normalization for Stage feedback; RDT uses its own documented policy feedback. `MCMC_steps` is a legacy accepted argument but does not run MCMC in PI05. These backend differences are not controlled cross-model algorithm comparisons.

## Engineering corrections

- The pinned upstream loader can catch loading errors and return a model anyway. The PI05 entrypoint now requires local verified assets, restores only safetensors-declared aliases tied to the same model Parameter, and fails on all missing or incompatible weights.
- PI05 formerly passed float flow times to a resampler that interprets integer scheduler IDs. Resampling calls used integer step indices, so scheduled scoring could be skipped. PI05 now uses those actual Euler-step IDs. This changes the broken PI05 path; it does not change RDT's scheduler or shared FKD implementation.
- FKD trajectory scoring now removes the policy's padded 32-dimensional latent tail before applying the seven-dimensional robot action normalizer. The first diagnostic exposed this previously masked mismatch; it is retained as an invalid engineering attempt.
- Reward/gradient errors now fail visibly instead of silently substituting zero reward or unguided inference.
- The shared guidance-toggle hook now explicitly represents PI05's lack of EDS memory, preserving the stage reward reference. The second diagnostic reached real gradient/FKD execution before exposing this missing interface.
- PI05 supplies a finite continuous gripper command, which the unchanged LIBERO adapter binarizes before simulation. Its audit checks that contract separately; RDT's existing binary-before-adapter check remains required.
- The local PaliGemma tokenizer is explicit. No hidden model or tokenizer download occurs during a cohort.
- Per-chunk evidence records strict loading, model calls/batch rows, gradients, actual FKD scoring and final ordering. The audit reuses shared online-capture/reward/action checks and separately binds the PI05 protocol and assets.

## Evidence and results

The accepted task-0 diagnostic completed in 121 environment steps with success, 13 action chunks, six online Stage queries and 346 passing task-contract checks. Its complete cohort audit passed. It is excluded from formal results. Two preceding diagnostic attempts exposed engineering errors and remain invalid: the padded-action/normalizer mismatch, followed by the missing guidance-toggle compatibility hook.

The independent formal cohort achieved **9/10 (90%)**: all ten episodes are valid, with one task failure, zero episode-level infrastructure errors and zero unfinished episodes. The source was unchanged throughout the run. The single-task diagnostic is excluded.

| Task | Object to place in basket | Seed | Outcome | Steps | Guided / all chunks | Visual Stage queries |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| 0 | alphabet soup | 44 | Success | 121 | 3 / 13 | 5 |
| 1 | cream cheese | 235 | Success | 111 | 3 / 12 | 5 |
| 2 | salad dressing | 43 | Success | 99 | 3 / 10 | 3 |
| 3 | bbq sauce | 546 | Success | 108 | 3 / 11 | 4 |
| 4 | ketchup | 6 | Task failure | 720 | 19 / 72 | 32 |
| 5 | tomato sauce | 621 | Success | 101 | 3 / 11 | 5 |
| 6 | butter | 197 | Success | 126 | 3 / 13 | 4 |
| 7 | milk | 87 | Success | 137 | 5 / 14 | 6 |
| 8 | chocolate pudding | 151 | Success | 125 | 3 / 13 | 6 |
| 9 | orange juice | 548 | Success | 103 | 4 / 11 | 5 |

The run lasted **85.0 wall-clock minutes**, from `2026-10-16T05:21:00.815521+00:00` to `2026-10-16T06:46:00.701567+00:00`. This is elapsed time, not GPU active time. Recorded compute: 1800 model forwards / 36000 batch rows, 49 guided and 131 unguided chunks, 392 reward-gradient and 98 RBF-gradient calls. FKD scored 147 opportunities, performed 49 resamples, and skipped 98 opportunities because ESS was sufficient.

There were 75 successful current-image Stage evaluations and ten fresh identity generations. Codex recorded 95 logical CLI calls and 0 failed logical calls; request-level HTTP retry counts are unavailable. Server input-token cache counters do not indicate local response replay. The cohort audit binds source/configuration/environment/assets, all task identities, fresh online captures, action/reward contracts, real gradient/FKD counters and environment outcomes. All ten videos were decoded completely and matched their recorded step counts.

The ketchup task (task 4) reached the fixed step limit. Its last captured view and robot geometry show the target outside the basket; no service or loader error explains that environment failure. This observation does not isolate a cause or justify changing Stage/reward settings during this cohort.

These are one-seed, standard LIBERO Object results with a LIBERO-adapted checkpoint. They do not establish statistical superiority, upstream-score reproduction, ObjectSwap OOD performance, or a VLS gain over an unguided PI05 control. That control was not part of this validation.

The [compact result receipt](validation/pi05-libero-object-20261016.json) records task outcomes, compute, video hashes and the 120-file runtime snapshot. Final documentation and Git ignore/whitespace rules do not modify that frozen runtime. Raw evidence remains outside Git.


## Installation and regression coverage

A new environment was installed at `/tmp/vla-public-models-20261016/env` from the documented Conda/pip recipe. Existing verified wheel/download caches were reused; no old environment's site-packages or hidden research worktree was imported. The environment uses the current repository's pinned editable LIBERO and LeRobot sources. Matching local model/tokenizer assets were fully hashed; DINO was freshly downloaded and reconstructed. Public LIBERO reconstruction was separately verified in a new directory (2308 matching files).

The initial full CPU suite passed **1471 tests, with 3 staging-only comparisons skipped**. The padded-action and download-preservation fixes passed nine targeted tests; the final controller/contract changes passed **194 tests, with the same three staging-only comparisons skipped**. Strict full model loading, public asset/device preflight, RDT three-mode previews and PI05 preview/configuration also passed. Model/asset downloads and external account steps have the more precise coverage described in [Model assets](model-assets.md); no fresh PaliGemma authorization was obtained during this task.

The RDT scientific path and accepted weight identities were preserved. Shared runtime changes are a PI05-only tokenizer override and a PI05-specific worker manifest branch; shared offline-audit changes distinguish its gripper input contract. The RDT binary-gripper check and frozen numerical regressions remain enforced. The updated auditor also rechecked all three original RDT ten-task cohorts read-only: all remain valid, with VLS 1/10, EDS 3/10 and EDS+QD 0/10. No new RDT ten-task scores are claimed for this task.

## Evidence locations

Maintainer evidence root, relative to this repository:

`.worktrees/exp/repository-maintenance-20261015/public-models-pi05-20261016/`

- `setup-evidence/`: installation commands, environment logs, public metadata, file comparisons and source archives.
- `diagnostic-01/`, `diagnostic-02/`: retained invalid engineering attempts.
- `diagnostic-03/`: accepted successful single-task diagnostic; runtime `02827dc2de9556b2b95c7973d58aadb9d12d29a3`.
- `full10-01/`: independent formal cohort; source differs from the accepted diagnostic only in the public asset installer and its source manifest, to preserve original upstream license files. Model, policy, controller, prompt and evaluator logic are identical.

Each run retains `manifest.json`, `source/`, `resolved-config.yaml`, `environment.json`, `console.log`, online captures, chunk metrics and an audit. Videos are under `output/episode_*/`; task 0's diagnostic video is `diagnostic-03/output/episode_1/episode_1_success_agentview.mp4`. Full recordings remain outside Git. `full10-01-artifacts.json` indexes every raw file by size and SHA-256; `attempts-index.json` distinguishes diagnostics from the formal run. Each formal task’s video path/hash is also in the [committed result receipt](validation/pi05-libero-object-20261016.json). Public metadata/file identities are summarized in [the committed asset receipt](validation/public-models-20261016.json).
