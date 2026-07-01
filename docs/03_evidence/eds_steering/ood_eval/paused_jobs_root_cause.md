# OOD Evaluation Pause And Root-Cause Notes

Date: 2026-06-10

## Actions Taken

- Stopped the stale `rdt_eds_ood_eval` tmux runner and killed only the repeated stuck job process trees.
- Added `paused` support to `ood_eval_runner.py`.
- Changed job claiming so only `pending` jobs are automatically claimed. `failed`, `timeout`, and `paused` jobs are now terminal until explicitly resumed.
- Paused the three repeatedly stuck jobs:
  - `libero_goal_vls`
  - `libero_goal_eds_p16_c10`
  - `libero_goal_eds_p16_c20`
- Restarted the remaining queue on GPUs `0,1,2,3`.
- Detected and fixed a separate `libero_10` asset-cache failure before resuming `libero_10` jobs.

## Root Cause: Repeated Stuck `libero_goal` Jobs

The three paused jobs each had repeated 8-hour timeout cycles:

- `docs/03_evidence/eds_steering/ood_eval/logs/libero_goal_vls.log`
- `docs/03_evidence/eds_steering/ood_eval/logs/libero_goal_eds_p16_c10.log`
- `docs/03_evidence/eds_steering/ood_eval/logs/libero_goal_eds_p16_c20.log`

Observed pattern:

- Each job hit `timeout 28800` and exited with `exit=124` twice.
- Each was immediately claimed again because the original runner treated `failed` and `timeout` as claimable states.
- Output directories showed only early episode artifacts, typically `episode_1_fail_agentview.mp4` and `episode_2_fail_agentview.mp4`.
- Logs showed successful early Poe/VLM calls and no Python exception before the long no-progress window.

Conclusion:

- The root queueing bug was automatic retry of `timeout` jobs, which caused the same unhealthy jobs to monopolize GPUs.
- The per-job hang itself is not yet conclusively isolated. Current evidence points to an in-episode stall after early VLM/env progress in the `libero_goal` guided paths, not to an immediate API-key or import failure.

## Root Cause: `libero_10` Immediate Failures

After the queue advanced, `libero_10_unguided` and `libero_10_vls` failed immediately with:

```text
ValueError: Error opening file '/home/hynx/.cache/libero/assets/turbosquid_objects/red_coffee_mug/red_coffee_mug_texture.png'
```

Evidence:

- `docs/03_evidence/eds_steering/ood_eval/logs/libero_10_unguided.log`
- `docs/03_evidence/eds_steering/ood_eval/logs/libero_10_vls.log`

Diagnosis:

- The LIBERO asset metadata and lock file existed, but the actual texture file was missing.
- `huggingface-cli download --force-download` failed on metadata/HEAD handling, but the direct HuggingFace resolve URL was reachable.

Fix:

- Downloaded `red_coffee_mug_texture.png` directly from `jadechoghari/libero-assets`.
- Verified file:
  - Size: about `9.4M`
  - SHA256: `056fe075297343bd294678be0f8df694a4f4e0563f42033bb167ce6b5bd0b3a9`
  - Type: `PNG image data, 4096 x 4096, 8-bit/color RGB`

Validation:

- A lightweight `libero_10` initialization run built all 10 task envs successfully.
- That validation run ended with `ZeroDivisionError` because it used `main.episode_num=0`; this is unrelated to the texture fix and occurred after env creation succeeded.

## Current Queue Semantics

- `pending`: claimable
- `running`: currently executing
- `done`: completed with `results.txt`
- `timeout`: terminal until resumed
- `failed`: terminal until resumed
- `paused`: terminal until resumed

This prevents one bad job from starving the rest of the evaluation queue.
