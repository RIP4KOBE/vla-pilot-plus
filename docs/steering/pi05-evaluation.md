# π0.5 + VLS evaluation

This evaluation validates the public π0.5 checkpoint in this repository's shared online control framework. It is not a reproduction of the upstream VLS score and is not an ObjectSwap OOD result.

## Registered protocol

Registered before the first episode on 2026-10-16 UTC. Formal results are pending; diagnostics are kept separately.

| Item | Setting |
| --- | --- |
| Policy | `lerobot/pi05_libero_finetuned_v044`, revision `dbf8a3f794a9c4297b44f40b752712f50073d945`; strict complete loading with verified tied weights |
| Dependencies | New Python 3.12 environment from the steering recipe; pinned LeRobot and Transformers; existing RDT environment untouched |
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

Pending the complete diagnostic and ten-task run. The supported status remains **implemented, not yet accepted** until its evidence passes audit. Runtime source, environment, configuration, assets, fresh online captures, task outcomes and videos are frozen per run; failed attempts are retained.
