# RDT EDS Steering Evaluation Evidence

Date: 2026-06-06

Worktree: `/home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration`

## Summary

This evaluation verifies whether the new RDT EDS steering path is active, whether it improves over VLS on the same 10-episode LIBERO Object setup, and how sensitive it is to EDS parameters.

Result: EDS is implemented and active. The formal EDS run with `population_size=16`, `cem_iters=10`, `use_cem=false` achieved `8/10` success rate, compared with timed VLS at `4/10`. This passes the minimum gate (`EDS SR != 0`) and the target gate (`EDS is within 10-15 percentage points of VLS`, in fact +40 points). It does not outperform the unguided RDT baseline in this run (`9/10`), so this is evidence of EDS integration and VLS-relative improvement, not evidence that EDS improves the already strong base RDT policy on this benchmark.

## Acceptance Gates

| Gate | Result | Evidence |
| --- | ---: | --- |
| Minimum: formal EDS SR is not zero | Pass | `8/10`, `80.00%` in `outputs/formal_eds_10_p16_c10_poe_20260606_124847/results.txt` |
| Target: EDS comparable to VLS | Pass | EDS `8/10` vs timed VLS `4/10` on same setup |
| EDS loop is actually entered | Pass | Runtime log has `guidance_type=eds ... eds_loop=true` at `outputs/eds_steering_eval_logs/formal_eds_10_p16_c10_poe_20260606_124847.log:500`; routing is in `core/rdt_policy_steer.py:1154` and `core/rdt_policy_steer.py:1166` |
| Reward-driven effect, not only unguided denoising | Weak pass | Normal EDS `8/10`; zero-reward EDS `7/10`. Difference exists but is small |

## Setup

Common benchmark overrides:

```bash
conda run -n vla-pilot python main.py \
  policy.type=rdt \
  main.episode_num=10 \
  backend.libero.max_episode_steps=240 \
  main.use_vlm_stage_recognition=false \
  perception.gemini_grounding.enabled=false \
  perception.vlm_agent.base_url=https://api.poe.com/v1 \
  perception.vlm_agent.model=GPT-4o \
  perception.vlm_agent.temperature=0.0 \
  main.render=false \
  main.visualize_trajectory=false \
  main.debug_draw_trajectory=false
```

The Poe API key was passed only through `OPENAI_API_KEY=<redacted>` at runtime and is not written here.

The action chunk horizon used by the RDT policy is 8, set in `core/rdt_policy_steer.py:565` and wired during `post_init()` at `core/rdt_policy_steer.py:886`.

## Mechanism Evidence

The integration is not modifying the VLS denoise loop. `main.guidance_type` accepts `vls` or `eds` in `configs/config.yaml:37`, with policy-independent grouped configs under `main.vls_config` and `main.eds_config` in `configs/config.yaml:41` and `configs/config.yaml:57`.

`main.py` reads `guidance_type`, `vls_config`, and `eds_config` at `main.py:694`, `main.py:701`, and `main.py:702`, then passes grouped configs into RDT `select_action()` at `main.py:738` through `main.py:744`. Non-RDT policies still reject EDS explicitly at `main.py:747`.

Inside RDT, `select_action()` routes guided calls into `_predict_guided()` at `core/rdt_policy_steer.py:1012` through `core/rdt_policy_steer.py:1027`; unguided calls use `_predict_unguided()` at `core/rdt_policy_steer.py:1028` through `core/rdt_policy_steer.py:1036`.

`_predict_guided()` selects VLS via `_vls_guided_denoise_loop()` at `core/rdt_policy_steer.py:1154`, and selects EDS via `_eds_guided_denoise_loop()` at `core/rdt_policy_steer.py:1166`. This confirms EDS is a peer steering path, not a replacement for FKD resampling inside VLS.

The EDS loop performs the expected core algorithm:

| EDS operation | Code evidence |
| --- | --- |
| Initial action population | `core/rdt_policy_steer.py:1555` |
| Action mask application | `core/rdt_policy_steer.py:1556` |
| Population scoring as cost | `core/rdt_policy_steer.py:1558` |
| `cem_iters` loop | `core/rdt_policy_steer.py:1570` |
| CEM elite branch | `core/rdt_policy_steer.py:1572` |
| MPPI-style probability sampling | `core/rdt_policy_steer.py:1582` |
| Resampling with `torch.multinomial` | `core/rdt_policy_steer.py:1586` |
| Reference-style renoise | `core/rdt_policy_steer.py:1593` |
| Rollout denoise after renoise | `core/rdt_policy_steer.py:1595` |
| Best-score action selection | `core/rdt_policy_steer.py:1611` |

Targeted tests cover the important mechanics:

| Test | Evidence |
| --- | --- |
| EDS routing does not call VLS | `tests/test_rdt_steer.py:524` |
| EDS uses cond once plus action population batch | `tests/test_rdt_steer.py:791` |
| EDS calls rollout after each renoise | `tests/test_rdt_steer.py:820` |
| EDS candidate cache is best-first | `tests/test_rdt_steer.py:1036` |

Runtime evidence: the formal EDS log contains repeated `[RDT_GUIDE] enabled=true guidance_type=eds B=16 ... eds_population_size=16 eds_loop=true`, beginning at `outputs/eds_steering_eval_logs/formal_eds_10_p16_c10_poe_20260606_124847.log:500`.

## Results

Latency columns are end-to-end wall-clock values from `/usr/bin/time -p`, including model loading, keypoint/guidance setup, simulation, cached action execution, and policy inference. The code does not currently log isolated `select_action()` or pure model-forward latency; therefore `sec/chunk` is a coarse estimate using `ceil(episode_steps / 8)`.

| Run | Guidance | EDS params | Success | Wall-clock | Avg ep | Steps | Est. chunks | Sec/chunk | Output |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Unguided | none | n/a | `9/10` | `159.17s` | `15.92s` | 1546 | 197 | `0.81s` | `outputs/formal_unguided_10_20260606_124553` |
| VLS timed | VLS | default VLS | `4/10` | `398.12s` | `39.81s` | 2032 | 256 | `1.56s` | `outputs/formal_vls_10_poe_timed_20260606_131742` |
| EDS main | EDS | `pop=16,cem_iters=10,use_cem=false` | `8/10` | `744.95s` | `74.50s` | 1611 | 206 | `3.62s` | `outputs/formal_eds_10_p16_c10_poe_20260606_124847` |
| Zero-reward EDS | EDS | `pop=16,cem_iters=10,use_cem=false,zero_reward=true` | `7/10` | `746.09s` | `74.61s` | 1781 | 225 | `3.32s` | `outputs/formal_zero_reward_eds_10_p16_c10_20260606_130543` |
| EDS sweep | EDS | `pop=16,cem_iters=20,use_cem=false` | `5/10` | `1348.58s` | `134.86s` | 1818 | 229 | `5.89s` | `outputs/formal_eds_10_p16_c20_poe_20260606_125119` |
| EDS sweep | EDS | `pop=32,cem_iters=10,use_cem=false` | `6/10` | `1450.87s` | `145.09s` | 1853 | 235 | `6.17s` | `outputs/formal_eds_10_p32_c10_poe_20260606_125119` |
| EDS sweep | EDS | `pop=32,cem_iters=20,use_cem=false` | `6/10` | `2549.78s` | `254.98s` | 1979 | 251 | `10.16s` | `outputs/formal_eds_10_p32_c20_poe_20260606_130636` |
| EDS CEM | EDS | `pop=32,cem_iters=10,use_cem=true,num_elites=32` | `6/10` | `1479.08s` | `147.91s` | 1903 | 241 | `6.14s` | `outputs/formal_eds_10_p32_c10_cem_poe_20260606_131537` |

Historical debug-only run: `outputs/formal_eds_10_poe_p2_c1_20260606_122521` achieved `5/10`, but it violates the formal constraints (`population_size < 16`, `cem_iters < 10`) and is not used for acceptance.

## Episode Outcomes

| Run | Outcomes |
| --- | --- |
| Unguided | S,S,S,S,S,S,F,S,S,S |
| VLS timed | S,S,F,F,F,S,F,F,S,F |
| EDS `p16_c10` | F,F,S,S,S,S,S,S,S,S |
| Zero-reward EDS `p16_c10` | S,F,S,S,S,S,F,S,S,F |
| EDS `p16_c20` | S,F,S,S,F,F,F,S,S,F |
| EDS `p32_c10` | F,S,S,S,F,S,S,S,F,F |
| EDS `p32_c20` | S,S,S,F,S,S,F,S,F,F |
| EDS CEM `p32_c10` | S,F,S,S,S,F,S,S,F,F |

## Analysis

EDS is not falling through to unguided denoising. Runtime logs show `guidance_type=eds`, `B=16`, and `eds_loop=true`; code routing reaches `_eds_guided_denoise_loop()`; and targeted tests verify score/resample/renoise/rollout behavior. The implementation therefore enters the intended EDS steering path.

EDS improves strongly over VLS on this 10-episode setup: `8/10` vs `4/10`. The timed VLS run reproduced the previous VLS result exactly, so the comparison is not dependent on an old untimed run.

The zero-reward ablation is important. Normal EDS `p16_c10` reached `8/10`, while zero-reward EDS reached `7/10` with almost identical runtime. This suggests the reward function can affect selection, but the small one-episode gap means this experiment alone is not enough to claim the reward is the dominant cause of success. Some gains may come from population denoising/resampling dynamics or stochastic variation.

Larger EDS settings did not improve performance here. Increasing `cem_iters` from 10 to 20 at population 16 reduced SR from `8/10` to `5/10` and increased wall-clock from `744.95s` to `1348.58s`. Increasing population from 16 to 32 at `cem_iters=10` reduced SR from `8/10` to `6/10` and increased wall-clock to `1450.87s`. The largest tested setting, `p32_c20`, stayed at `6/10` but cost `2549.78s`.

CEM-style selection did not help in this run. `p32_c10,use_cem=true` and `p32_c10,use_cem=false` both achieved `6/10`, with similar wall-clock (`1479.08s` vs `1450.87s`).

Unguided RDT remains the strongest result on this particular small benchmark (`9/10`). That means the current EDS implementation passes integration and VLS-relative gates, but the next evaluation should include harder/OOD settings where steering has room to improve the base policy.

## Caveats

- The run is small (`10` episodes), so one episode is 10 percentage points. Interpret differences of one episode cautiously.
- The benchmark is `libero_object`, where unguided RDT already achieved `9/10`; this is not a stress test for steering.
- There is no isolated action-chunk latency instrumentation around `policy.select_action()` in `main.py:754`; reported latency is end-to-end wall-clock.
- A first zero-reward attempt failed before policy execution because `OPENAI_API_KEY` was not set for VLM client initialization. It was excluded and rerun with the same zero-reward cache plus the required environment variable.
- GPU2 had an unrelated idle `dreamzero` process using memory. The `p32_c20` run still completed without OOM, but GPU2 was not a perfectly isolated card.

## Verification Commands

The following checks were run after generating this document:

```bash
conda run -n vla-pilot python -m py_compile main.py core/rdt_policy_steer.py
conda run -n vla-pilot pytest -q \
  tests/test_rdt_steer.py::test_rdt_guidance_type_eds_routes_to_eds_loop \
  tests/test_rdt_steer.py::test_eds_loop_uses_cond_once_and_action_population_batch \
  tests/test_rdt_steer.py::test_eds_loop_calls_rollout_after_renoise_each_iteration \
  tests/test_rdt_steer.py::test_eds_loop_caches_visualization_candidates_best_first
conda run -n vla-pilot pytest tests/test_rdt_steer.py -q
```

Verification results:

| Check | Result |
| --- | --- |
| Document exists | `154` lines at `docs/03_evidence/eds_steering/rdt_eds_steering_evaluation.md` |
| `py_compile` | exit code `0` |
| Targeted EDS tests | `4 passed in 1.13s` |
| Full RDT steer tests | `78 passed, 1 warning in 2.76s` |
