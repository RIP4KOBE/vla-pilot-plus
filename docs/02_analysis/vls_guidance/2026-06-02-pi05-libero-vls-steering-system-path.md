---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/vls_guidance/2026-06-02-pi05-libero-vls-steering-system-path.md
summary: PI0.5 LIBERO VLS Steering System Path
duplicate_sources: []
---

# PI0.5 LIBERO VLS Steering System Path

Date: 2026-06-02

Command analyzed:

```bash
python main.py policy.type=pi05 main.use_guidance=true
```

Scope: read-only code-path and algorithm analysis for the current worktree `.worktrees/feat/rdt-libero-gt-rollout-reintegration`. No rollout, VLM API call, guidance generation, runtime code edit, or config edit was performed.

## 1. Executive summary

With `policy.type=pi05`, `main.py` loads `PI05PolicySteer` from `core/pi05_steer.py` and checkpoint `lerobot/pi05_libero_finetuned_v044` from `configs/policy.yaml`. With `main.use_guidance=true`, `Main._init_components()` constructs the VLS perception stack, `Main.perform_task_for_episode()` prepares keypoints and stage guidance functions, and `Main._run_episode()` passes current keypoints plus current-stage guidance functions into `PI05PolicySteer.select_action()`.

PI0.5 guidance is injected inside `PI05PolicySteer._sample_actions_guided()`. The method mirrors upstream PI0.5 flow-matching inference: sample Gaussian action latents `x_t`, cache the PaliGemma image/language prefix, run a velocity denoiser from time `1.0` to `0.0`, and Euler integrate with `dt=-1/num_steps`. VLS adds two steering mechanisms in this loop: diversity gradient for early timesteps (`time > start_time`) and keypoint reward gradient for later timesteps (`time <= start_time`).

The guidance reward is computed on differentiable 3D end-effector trajectories derived from action samples. A candidate action sample is postprocessed through the LeRobot action unnormalizer, optionally adapter postprocessed, converted to a LIBERO delta-EEF trajectory by `LiberoAdapter.delta_actions_to_ee_trajectory()`, scored by VLM-generated Python functions against tracked keypoints, and differentiated back to the action sample. The velocity update subtracts the reward gradient, and because `dt` is negative, this effectively nudges `x_t` in the reward-increasing direction.

Important suspicious points: `MCMC_steps` is accepted but unused in the PI0.5 path; FKD wiring appears mismatched with this flow-matching timestep loop; guided PI0.5 returns a 10-step chunk while unguided parent PI0.5 returns 50 steps; and gripper-trigger stage recognition appears to inspect `action_chunk[0][0]` at chunk boundaries after the execution counter has reset, not necessarily the just-executed gripper action.

## 2. Files inspected

Required project files inspected:

- `main.py`
- `configs/config.yaml`
- `configs/policy.yaml`
- `configs/backend/libero.yaml`
- `configs/env/libero.yaml`
- `configs/perception.yaml`
- `core/pi05_steer.py`
- `core/env_adapters/libero_adapter.py`
- `core/env_adapters/base_adapter.py`
- `core/env_adapters/__init__.py`
- `core/keypoint_tracker.py`
- `core/keypoint_detector.py`
- `core/sam3_segmenter.py`
- `core/gemini_grounder.py`
- `core/policy_observation_sampling.py`
- `core/fkd_class.py`
- `utils/vis_utils.py`
- `utils/guidance_utils.py`
- `utils/keypoint_utils.py`
- `vlm_query/vlm_agent.py`

Referenced PI0.5 / LeRobot files inspected:

- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py`
- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/policies/pi05/configuration_pi05.py`
- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/policies/pi05/processor_pi05.py`
- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/policies/pretrained.py`
- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/policies/factory.py`
- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/processor/normalize_processor.py`
- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/processor/batch_processor.py`
- `/home/hynx/VLA-Pilot++/third_party/lerobot/src/lerobot/utils/constants.py`
- `/mnt/data/hf_cache/hub/models--lerobot--pi05_libero_finetuned_v044/snapshots/dbf8a3f794a9c4297b44f40b752712f50073d945/{config.json,policy_preprocessor.json,policy_postprocessor.json}`

Note: the target worktree's `third_party/lerobot/` directory is empty/uninitialized, but `core/env_adapters/libero_adapter.py` has a local fallback for `LiberoProcessorStep`. The LeRobot policy source was inspected from the populated parent checkout and the local HF cache.

## 3. End-to-end call graph

Text call graph for `python main.py policy.type=pi05 main.use_guidance=true`:

```text
Hydra
  main.py:@hydra.main(config_path="configs", config_name="config")  # main.py:835
  -> main(cfg)                                                      # main.py:836
  -> Main(cfg)                                                      # main.py:867

Main.__init__
  -> self.config = cfg.main                                         # main.py:97
  -> backend = cfg.backend.backend                                  # main.py:109
  -> create_adapter("libero", cfg.backend.libero + episode_num)      # main.py:113-122
  -> LiberoAdapter(None, env_config)                                # core/env_adapters/__init__.py:69-73
  -> create_libero_envs(...) -> LiberoEnv(...)                      # core/env_adapters/libero_adapter.py:833-844
  -> policy.type = "pi05"                                           # main.py:142-159
  -> PI05PolicySteer.from_pretrained("lerobot/pi05_libero_finetuned_v044")
  -> make_pre_post_processors(policy_cfg, pretrained_path, device)   # main.py:190-199
  -> policy.post_init(adapter, postprocessor, sample_batch_size, policy_config)
  -> _init_components(cfg)                                          # main.py:218-306

Main.run
  -> per episode:
     -> policy.reset(); video_recorder.clear(); adapter.reset(seed) # main.py:519-527
     -> perform_task_for_episode(episode_dir) if main.use_guidance  # main.py:538-540
        -> adapter.get_keypoint_detection_inputs()
        -> keypoint_detector.get_keypoints(...)
        -> keypoint_tracker.register_keypoints(...)
        -> load/generate VLM guidance functions
     -> _run_episode(episode, episode_dir)

Main._run_episode
  -> observation = _get_policy_observation()
     -> sample_num = policy_observation_sample_num("pi05", sample_batch_size)
     -> adapter.get_policy_observation(sample_num)
     -> policy_preprocessor(observation)
  -> loop:
     -> on chunk boundary, get tracked keypoints and update stage
     -> policy.select_action(observation, use_guidance, keypoints, guidance_fns, ...)
        -> PI05PolicySteer._sample_actions_guided(...) if guided
        -> PI05Policy.predict_action_chunk(...) if unguided
     -> optional adapter[redacted env file]_postprocessor(action_chunk)
     -> optional draw_action_trajectory_on_vlm_image(...)
     -> video_recorder.add_frame(...)
     -> adapter.step(action_chunk[0][action_executed])
     -> observation = _get_policy_observation()
     -> save success/fail video on termination/truncation
```

## 4. Config and checkpoint loading path

Hydra loads `configs/config.yaml` from `main.py`'s `@hydra.main(config_path="configs", config_name="config")` decorator (`main.py:835`). The defaults select `backend: libero`, `perception`, and `policy` (`configs/config.yaml:9-15`).

The command override `policy.type=pi05` changes `configs/policy.yaml` from default `rdt` to `pi05`; `main.py` then reads `policy_config.get("type")`, reads `policy.pi05.pretrained_path`, and calls `PI05PolicySteer.from_pretrained(pretrained_path)` (`main.py:142-159`). The PI0.5 config sets:

- `policy.pi05.pretrained_path: lerobot/pi05_libero_finetuned_v044`
- `policy.pi05.num_inference_steps: 10`
- `policy.pi05.action_chunk_horizon: 10`

Source: `configs/policy.yaml:23-26`.

The command override `main.use_guidance=true` is canonical because `Main.__init__` stores `cfg.main` as `self.config` (`main.py:97`), and all guidance gates read `self.config.get("use_guidance", ...)` (`main.py:227`, `main.py:538`, `main.py:612`, `main.py:634`).

LIBERO defaults come from `configs/backend/libero.yaml`: suite `libero_object`, task id `0`, cameras `agentview_image, robot0_eye_in_hand_image`, policy observation size `128x128`, VLM/keypoint/video size `640x640`, `max_episode_steps: 720`, and `vlm_camera: agentview` (`configs/backend/libero.yaml:14-30`).

The PI0.5 HF cache config confirms the loaded checkpoint's feature contract:

- input images: `observation.images.image` and `observation.images.image2`, each `(3,256,256)`
- input state: `observation.state`, shape `(8,)`
- output action: `action`, shape `(7,)`
- internal `chunk_size: 50`, `max_action_dim: 32`, `num_inference_steps: 10`, `image_resolution: [224,224]`, `empty_cameras: 1`, `dtype: bfloat16`

Source: `/mnt/data/hf_cache/.../config.json:1-91`.

The preprocessor JSON loads, in order: rename, add-batch, normalizer, PI0.5 state-tokenizer preparation, PaliGemma tokenizer, device processor (`policy_preprocessor.json:1-87`). The postprocessor JSON loads action unnormalizer then CPU device processor (`policy_postprocessor.json:1-32`).

## 5. LIBERO raw observation to PI0.5 policy observation path

`LiberoAdapter.__init__()` creates one `LiberoEnv` per selected LIBERO task using `create_libero_envs()` (`core/env_adapters/libero_adapter.py:833-844`). `LiberoEnv` wraps LIBERO/robosuite `OffScreenRenderEnv` (`core/env_adapters/libero_adapter.py:613-620`) with a 7D action space (`core/env_adapters/libero_adapter.py:585-587`).

Raw observations are produced by the underlying `OffScreenRenderEnv.reset()` and `OffScreenRenderEnv.step()` calls. `LiberoEnv.reset()` gets `raw_obs = self._env.reset()`, optionally sets the init state, waits `num_steps_wait` no-op steps, and formats the raw observation (`core/env_adapters/libero_adapter.py:686-700`). `LiberoEnv.step(action)` calls `self._env.step(action)`, checks success, formats the new raw observation, and returns Gym-style `(obs, reward, terminated, truncated, info)` (`core/env_adapters/libero_adapter.py:702-730`).

`LiberoEnv._format_raw_obs()` converts raw LIBERO fields into a policy-ish dictionary:

- image keys `agentview_image` and `robot0_eye_in_hand_image` are copied if present.
- task language becomes `observation["task"]`.
- each configured camera image is converted from numpy `(H,W,C) uint8` to torch `(1,C,H,W) float32` in `[0,1]`, stored as `observation.images.image` / `observation.images.image2`.
- robot state is stored as nested `observation.robot_state` with EEF position, EEF quaternion, EEF orientation matrix, gripper qpos/qvel, and joint pos/vel.

Source: `core/env_adapters/libero_adapter.py:637-684`.

`LiberoAdapter.get_policy_observation(sample_num)` copies `_last_obs`, writes `task` as a list of length `sample_num`, preserves several raw RDT helper keys, then calls `self[redacted env file]_preprocessor(obs)` (`core/env_adapters/libero_adapter.py:938-995`). The env preprocessor is a `PolicyProcessorPipeline` containing `LiberoProcessorStep` (`core/env_adapters/libero_adapter.py:861-865`).

`LiberoProcessorStep` flips every `observation.images.*` tensor with `torch.flip(..., dims=[2,3])`, i.e. both image height and width, and converts nested `observation.robot_state` to flat `observation.state = [eef_pos(3), eef_axisangle(3), gripper_qpos(2)]` (`core/env_adapters/libero_adapter.py:76-96`). If LeRobot is importable, the external `LiberoProcessorStep` is intended to provide the same behavior; the worktree fallback is shown directly in this file.

After env preprocessing, `get_policy_observation()` expands every tensor with leading batch `1` to `sample_num` if `sample_num > 1` (`core/env_adapters/libero_adapter.py:1019-1025`). For PI0.5, `policy_observation_sample_num()` returns `main.sample_batch_size` if configured (`core/policy_observation_sampling.py:1-4`), so the default command uses `B=20` particles from `configs/config.yaml:39-44`.

`Main._get_policy_observation()` then applies the LeRobot policy preprocessor (`main.py:308-317`). The cached PI0.5 preprocessor normalizes state and action stats using MEAN_STD, prepares the state into a PaliGemma prompt, tokenizes the task using `google/paligemma-3b-pt-224`, and moves tensors to CUDA (`policy_preprocessor.json:15-85`, `processor_pi05.py:48-89`, `processor_pi05.py:132-151`).

Finally, `PI05Policy._preprocess_images()` consumes the processed image keys from `self.config.image_features`, moves them to model device, converts to `float32`, resizes/pads to `image_resolution=(224,224)` if needed, and maps `[0,1]` images to `[-1,1]` for SigLIP/PaliGemma (`modeling_pi05.py:1103-1167`).

## 6. LIBERO raw observation to VLS/keypoint/trajectory guidance path

VLS perception does not use the PI0.5 policy image tensors. It calls adapter rendering utilities directly.

`LiberoAdapter.get_vlm_image()` renders the current robosuite sim from `self.vlm_camera` at visualization resolution, converts to uint8, and applies `np.flipud()` for a human-viewable top-left image (`core/env_adapters/libero_adapter.py:868-902`). `LiberoAdapter.get_vlm_image_raw()` renders the same image without flipping, and is used for projection overlays (`core/env_adapters/libero_adapter.py:904-936`).

`LiberoAdapter.get_keypoint_detection_inputs()` renders RGB+depth and segmentation from MuJoCo at visualization resolution (`core/env_adapters/libero_adapter.py:1429-1470`). It converts normalized MuJoCo depth to metric depth using near/far planes (`core/env_adapters/libero_adapter.py:1472-1483`), processes segmentation to interactable object segment ids (`core/env_adapters/libero_adapter.py:1485-1486`), computes camera params (`core/env_adapters/libero_adapter.py:1488-1489`), converts depth to a world-frame point cloud (`core/env_adapters/libero_adapter.py:1491-1492`), converts RGB to uint8, then flips RGB/depth/segmentation/points vertically with `np.flipud()` (`core/env_adapters/libero_adapter.py:1502-1509`).

`LiberoAdapter.get_camera_params(camera_name)` computes a 3x3 intrinsic matrix from MuJoCo FOV and selected render size, builds a camera-to-world transform from MuJoCo camera pose, flips the MuJoCo camera Z axis for OpenCV convention, and returns world-to-camera extrinsics (`core/env_adapters/libero_adapter.py:1115-1187`). `BaseEnvAdapter.project_3d_to_2d()` multiplies world points by extrinsics and intrinsics (`core/env_adapters/base_adapter.py:299-324`).

`KeypointDetector.get_keypoints()` takes `(rgb, points, segmentation, segment_id_to_name)`, preprocesses RGB for DINO, converts segmentation to binary masks, extracts DINOv2/DINOv3 features, clusters per object mask, filters by workspace bounds, merges nearby clusters, sorts by mask id, and draws projected keypoint labels (`core/keypoint_detector.py:151-283`). The DINO image preprocessing resizes to a patch-multiple and scales to `[0,1]` (`utils/keypoint_utils.py:170-196`).

`KeypointTracker.register_keypoints()` attaches each detected world keypoint to an object segment by converting its world position into that object's local pose frame (`core/keypoint_tracker.py:62-130`). During rollout, `get_keypoint_positions()` refreshes positions by getting each object's current pose from the adapter and transforming local coordinates back to world coordinates (`core/keypoint_tracker.py:146-182`). This is object-pose tracking, not optical-flow tracking, in the inspected code.

For trajectory scoring, `PI05PolicySteer._sample_to_trajectory_3d()` postprocesses a normalized action sample into executable-scale actions and calls `LiberoAdapter.delta_actions_to_ee_trajectory()` (`core/pi05_steer.py:331-355`). The adapter treats `action[:3]` as normalized delta position, scales it by `ACTION_SCALE_POS = 0.01`, cumulatively sums it from the current EEF world position, and returns `(T+1,3)` (`core/env_adapters/libero_adapter.py:1528-1577`).

## 7. Guidance setup before rollout

`Main._init_components()` is disabled early when `main.use_guidance` is false (`main.py:225-239`). With `main.use_guidance=true`, it initializes:

- `KeypointDetector` from `perception.keypoint_detector` (`main.py:241-247`)
- optional SAM3 segmenter from `perception.sam3` (`main.py:248-258`)
- Gemini grounding from `perception.gemini_grounding` if enabled and an API key exists (`main.py:259-275`)
- `KeypointTracker` (`main.py:277-278`)
- `VLMAgent` using the environment-specific template directory (`main.py:280-289`)
- optional Gemini stage recognizer (`main.py:291-301`)
- `TrajectoryVideoRecorder` (`main.py:303-306`)

Default perception config uses DINOv2 ViT-B/14, Gemini grounding enabled, SAM3 disabled, and Gemini stage model `gemini-2.5-flash` (`configs/perception.yaml:7-63`).

`Main.perform_task_for_episode(episode_dir)` does the per-episode setup (`main.py:319-433`):

1. Calls `adapter.get_keypoint_detection_inputs()` for RGB/depth/points/segmentation/name mapping (`main.py:323-324`).
2. Reads the instruction from `adapter.get_instruction()` (`main.py:326-328`).
3. If adapter segmentation is valid, uses it; otherwise falls back to Gemini box grounding or SAM3 text segmentation (`main.py:332-377`).
4. Runs `KeypointDetector.get_keypoints()` (`main.py:379-385`).
5. Registers keypoints with `KeypointTracker.register_keypoints()` (`main.py:387-392`).
6. Stores the initial keypoint image and keypoint-object map for stage recognition (`main.py:394-397`).
7. If `cached_functions_dir` is set, loads that directory; otherwise calls `VLMAgent.generate_guidance()` with the projected keypoint image, instruction, and keypoint metadata (`main.py:401-416`).
8. Reads `metadata.json`, loads `stage{N}_guidance.txt` functions via `load_functions_from_txt()`, and parses stage descriptions from `output_raw.txt` (`main.py:418-433`).

`VLMAgent.generate_guidance()` writes `query_img.png`, `prompt.txt`, `output_raw.txt`, stage guidance text files, and `metadata.json` under the episode's `vlm_agent` directory (`vlm_query/vlm_agent.py:218-258`). `utils.guidance_utils.load_functions_from_txt()` executes the generated Python in a restricted namespace, rewrites common numpy calls to torch calls, wraps functions for device consistency, and validates with dummy `(keypoints, trajectory)` tensors (`utils/guidance_utils.py:49-116`).

## 8. PI0.5 unguided sampling path

`PI05PolicySteer.select_action()` overrides the parent action selection mainly to support chunk caching and guidance arguments. It removes `ACTION` from the batch, enters CUDA bfloat16 autocast, and if `generate_new_chunk` is true either calls `_sample_actions_guided()` or parent `predict_action_chunk()` depending on `use_guidance and guidance_fns` (`core/pi05_steer.py:78-135`).

Parent `PI05Policy.predict_action_chunk()` prepares images, reads `observation.language.tokens` and `observation.language.attention_mask`, calls `self.model.sample_actions(...)`, then truncates the internal max action dimension to the configured output action dimension (`modeling_pi05.py:1191-1207`).

Parent `PI05Pytorch.sample_actions()`:

- uses `num_steps = config.num_inference_steps` if not overridden (`modeling_pi05.py:746-759`)
- samples Gaussian noise shaped `(B, chunk_size, max_action_dim)` (`modeling_pi05.py:763-770`)
- embeds images and language as a prefix and caches prefix key-values (`modeling_pi05.py:772-785`)
- sets `dt=-1/num_steps`, initializes `x_t=noise`, `time=1.0`, repeatedly calls `denoise_step(...)`, and Euler-updates `x_t += dt * v_t` until time reaches 0 (`modeling_pi05.py:787-830`)
- returns full `x_t` shaped `(B, chunk_size, max_action_dim)`.

For this checkpoint, parent unguided PI0.5 produces 50 internal chunk steps before truncating action dim to 7 (`config.json:55-59`, `modeling_pi05.py:1203-1207`). The local guided path returns only `self._action_chunk_horizon` steps, i.e. 10 (`core/pi05_steer.py:294-295`, `configs/policy.yaml:25-26`).

## 9. Detailed `_sample_actions_guided()` walkthrough

Signature:

```python
_sample_actions_guided(
    batch,
    keypoints=None,
    guidance_fn=None,
    guide_scale=1.0,
    start_ratio=None,
    use_diversity=True,
    diversity_scale=1.0,
    verbose=False,
    use_fkd=False,
    fkd_config=None,
    global_step=0,
    current_stage=1,
    sigmoid_k=12.0,
    sigmoid_x0=0.7,
)
```

Source: `core/pi05_steer.py:137-153`.

Inputs and setup:

- `batch`: LeRobot-preprocessed policy observation containing image tensors and language tokens/masks.
- `keypoints`: current tracked keypoints from `KeypointTracker.get_keypoint_positions()`, numpy `(N,3)` in world coordinates.
- `guidance_fn`: actually a list of callables for the current stage, despite singular name; `main.py` passes `current_guidance_fns` (`main.py:660-678`).
- `guide_scale`, `sigmoid_k`, `sigmoid_x0`: current adaptive guidance parameters.
- `use_diversity`, `diversity_scale`, `use_fkd`, `fkd_config`: particle-level steering controls.
- `global_step`, `current_stage`: only used for logging and reward-baseline state.

Algorithm:

1. Preprocess images with inherited `self._preprocess_images(batch)` and read language tokens/masks (`core/pi05_steer.py:162-165`).
2. Set `num_steps = self._inference_steps`, `bsize = tokens.shape[0]`, `device = tokens.device` (`core/pi05_steer.py:167-170`).
3. Sample initial noise with shape `(B, self.model.config.chunk_size, self.model.config.max_action_dim)` (`core/pi05_steer.py:171-173`). With defaults, this is `(20,50,32)`.
4. Embed the image/language prefix, build 2D/4D attention masks, force eager attention, and cache prefix key-values (`core/pi05_steer.py:175-192`).
5. Set `start_time = start_ratio if provided else 0.8`; convert keypoints to `torch.float32` on the token device; initialize FKD if requested (`core/pi05_steer.py:194-205`).
6. Initialize the flow loop: `dt = -1/num_steps`, `x_t = noise`, `time = 1.0`, `step_idx = 0` (`core/pi05_steer.py:207-214`).
7. While `time >= -dt/2`, run PI0.5 `denoise_step()` to get velocity `v_t` (`core/pi05_steer.py:216-225`).
8. If `use_diversity and time > start_time and B > 1`, compute a diversity gradient on trajectories and add it to `v_t[:, :horizon, :3]` (`core/pi05_steer.py:227-232`).
9. Else if keypoint guidance is available and `time <= start_time`, compute reward gradient and raw reward (`core/pi05_steer.py:233-239`).
10. If a reward gradient exists, normalize reward relative to `self._stage_init_reward`, compute sigmoid guidance strength, set `scale = guide_scale * guidance_strength`, store `_last_normalized_reward` and `_last_scale`, and update velocity first-3 action dimensions with `v_t[:, :horizon, :3] -= scale * kp_grad[:, :horizon, :3]` (`core/pi05_steer.py:241-277`).
11. Euler-update `x_t = x_t + dt * v_t` (`core/pi05_steer.py:278-280`).
12. If FKD exists and `time <= start_time`, call `fkd.resample(sampling_idx=step_idx, latents=x_t, x0_preds=x_t)` (`core/pi05_steer.py:281-284`).
13. Decrement time and increment step index (`core/pi05_steer.py:285-286`).
14. On the first guided chunk of a stage, set `self._stage_init_reward` to the final recorded reward, used as that stage's normalization baseline (`core/pi05_steer.py:288-292`).
15. Return `x_t[:, :self._action_chunk_horizon, :self._original_action_dim]`, i.e. `(B,10,7)` for current config (`core/pi05_steer.py:294-295`).

## 10. Denoising / sampling steering math and code map

PI0.5 parent inference integrates a flow-matching ODE:

```text
x_1 ~ N(0, I)
for t = 1, 1-dt, ..., 0:
    v_t = model(x_t, t, image/language prefix)
    x_{t+dt} = x_t + dt * v_t       # dt = -1 / num_steps
return x_0
```

Source: parent `sample_actions()` in `modeling_pi05.py:787-830`.

Local VLS changes:

```text
if time > start_time:
    v_t[:,:,:3] += diversity_scale * grad_diversity
else:
    reward = sum(fn(keypoints, trajectory_3d(x_t)))
    grad = d reward / d x_t
    grad = grad / ||grad||
    normalized_reward = 1 - reward / stage_init_reward
    guidance_strength = 1 / (1 + exp(sigmoid_k * (normalized_reward - sigmoid_x0)))
    scale = guide_scale * guidance_strength
    v_t[:,:,:3] -= scale * grad[:,:,:3]
x_t = x_t + dt * v_t
```

Because `dt` is negative, the `v_t -= scale * grad` line makes the Euler update include `+ (scale/num_steps) * grad` in the updated sample, assuming `grad` is the gradient of reward with respect to `x_t`. The code implements this at `core/pi05_steer.py:263-280`.

Guidance is applied only to the first 3 action coordinates and only across `self._action_chunk_horizon` timesteps (`core/pi05_steer.py:231`, `core/pi05_steer.py:276`). Orientation and gripper dimensions are not directly gradient-steered.

## 11. Keypoint, trajectory, reward, gradient, diversity, FKD/MCMC data flow

Keypoints:

- `Main._run_episode()` refreshes keypoints only at chunk boundaries when guidance setup exists (`main.py:631-636`).
- `keypoints` is numpy `(N,3)`, converted to torch `float32` on the model device in `_sample_actions_guided()` (`core/pi05_steer.py:197-200`).

Trajectory conversion:

- `_compute_keypoint_gradient()` detaches the sample and re-enables grad locally (`core/pi05_steer.py:375-378`).
- `_sample_to_trajectory_3d(sample_grad)` postprocesses normalized action samples, adapter-postprocesses them if available, and converts each batch sample to a differentiable EEF trajectory (`core/pi05_steer.py:331-355`).
- For keypoint gradients, it slices `[:, :horizon, :3]` from the returned trajectory (`core/pi05_steer.py:377-382`). Since the adapter trajectory has `T+1` points including the start pose, this slice includes the start pose and omits the last future point for a 10-action horizon.

Reward:

- If guidance is a list, rewards are summed: `sum(fn(keypoints_tensor, traj_input) for fn in guidance_fn)` (`core/pi05_steer.py:384-387`).
- Reward is reduced to a scalar if it has dimensions (`core/pi05_steer.py:392-393`).
- If reward is `None` or does not require grad, guidance is skipped (`core/pi05_steer.py:389-390`).

Gradient:

- `torch.autograd.grad(reward, sample_grad)[0]` gives a gradient shaped like the sample, normally `(B,50,7)` for the sliced sample passed in (`core/pi05_steer.py:397`).
- It is normalized by its global norm (`core/pi05_steer.py:398-399`).
- Only `[:, :10, :3]` is applied to PI0.5 velocity (`core/pi05_steer.py:276`).

Diversity:

- `_compute_diversity_gradient()` converts every particle to a 3D trajectory, flattens trajectories, forms pairwise distances, sums inverse distances, differentiates that potential with respect to the sample, and normalizes the gradient (`core/pi05_steer.py:411-433`).
- The code applies this only when `B >= 2` and `time > start_time` (`core/pi05_steer.py:227-232`).

FKD:

- `_init_fkd()` builds a reward function that scores each particle trajectory and constructs `FKD(...)` with `potential_type`, `lambda`, adaptive resampling, and resampling frequency (`core/pi05_steer.py:297-329`).
- `FKD.resample()` computes particle rewards, turns them into Feynman-Kac weights, optionally resamples by `torch.multinomial`, and sorts terminal particles by reward so particle 0 is best (`core/fkd_class.py:191-313`).
- Suspicious: in the current PI0.5 implementation, `_init_fkd()` passes `timesteps=torch.linspace(1.0, 0.0, num_steps + 1, device=device)`, but `FKD.__init__()` casts tensor timesteps to `long` (`core/fkd_class.py:127-132`) and `_sample_actions_guided()` calls `resample(sampling_idx=step_idx, ...)` (`core/pi05_steer.py:281-284`). For `num_steps=10`, the long timesteps collapse to mostly `0`, while `sampling_idx` is an integer loop index. This appears likely to skip most or all FKD resampling in PI0.5.

MCMC:

- `MCMC_steps` is passed from `main.py` into `PI05PolicySteer.select_action()` (`main.py:660-678`) and accepted in the method signature (`core/pi05_steer.py:90`), but it is not forwarded into `_sample_actions_guided()` and no PI0.5 MCMC refinement code was found in `core/pi05_steer.py`. In this path, MCMC is effectively unused.

Cached state:

- `_cached_action_chunk` persists the current chunk between steps (`core/pi05_steer.py:39`, `core/pi05_steer.py:131-134`).
- `_stage_init_reward`, `_last_normalized_reward`, and `_last_scale` persist reward-adaptive guidance state (`core/pi05_steer.py:40-76`).
- `reset()` clears all of the above per episode; `reset_stage()` clears only the stage reward baseline (`core/pi05_steer.py:59-69`).

## 12. Guided action chunk to LIBERO OSC action execution path

`PI05PolicySteer.select_action()` returns a postprocessed action chunk if a postprocessor exists (`core/pi05_steer.py:135`). For PI0.5, `main.py` supplies the LeRobot postprocessor built from `policy_postprocessor.json` (`main.py:190-206`), whose steps are action MEAN_STD unnormalizer and CPU device processor (`policy_postprocessor.json:1-32`). The unnormalizer formula is `action * std + mean` for inverse MEAN_STD (`normalize_processor.py:325-338`).

`Main._run_episode()` then optionally applies `adapter[redacted env file]_postprocessor` to the whole chunk (`main.py:680-683`). In the LIBERO adapter as inspected, `env_postprocessor` is an empty pipeline (`core/env_adapters/libero_adapter.py:861-865`), so this is expected to be a no-op unless processor steps are later added.

The executed action is selected as:

```python
action = action_chunk[0][action_executed]
obs, reward, terminated, truncated, info = self.adapter.step(action)
```

Source: `main.py:737`.

The first index selects particle 0. If FKD sorted terminal particles, particle 0 should be the highest-reward particle; otherwise it is just the first sampled particle. `action_executed` advances from `0` to `action_horizon-1`, then resets to `0` (`main.py:739-742`). `action_horizon` is `policy._action_chunk_horizon`, set to 10 in `PI05PolicySteer.post_init()` (`core/pi05_steer.py:45-58`).

`LiberoAdapter.step(action)`:

1. Wraps the action as `{"action": action}` and runs `env_postprocessor` (`core/env_adapters/libero_adapter.py:1590-1595`).
2. Clones the tensor and binarizes gripper: `action[-1] = 1 if action[-1] > 0 else -1` (`core/env_adapters/libero_adapter.py:1596-1598`).
3. Casts to CPU float32 numpy because PI0.5 may output bfloat16 (`core/env_adapters/libero_adapter.py:1599-1601`).
4. Calls `current_env.step(action_numpy)` (`core/env_adapters/libero_adapter.py:1603-1604`).
5. Caches the new observation and adds task metadata to `info` (`core/env_adapters/libero_adapter.py:1607-1618`).

`LiberoEnv.step(action_numpy)` checks the action is 1D, sends it to `OffScreenRenderEnv.step(action)`, checks success, formats the raw observation, and returns it (`core/env_adapters/libero_adapter.py:702-730`). LIBERO's action space is `Box(low=-1, high=1, shape=(7,), dtype=float32)` (`core/env_adapters/libero_adapter.py:585-587`). `LiberoAdapter.get_action_space_info()` documents the 7D OSC interpretation: 3D delta position, 3D delta orientation, 1D gripper, normalized to `[-1,1]` (`core/env_adapters/libero_adapter.py:1513-1526`).

## 13. Stage recognition and adaptive guidance path

Stage state is initialized in `_run_episode()` as stage 1, guidance on if `main.use_guidance` and `guidance_fns` exist, previous normalized reward `0.0`, previous gripper state `None`, and query count `0` (`main.py:610-629`).

On every new chunk boundary, `_run_episode()`:

- gets current keypoints and mask ids (`main.py:634-636`)
- extracts a gripper value from the current `action_chunk` via `_get_gripper_value()` (`main.py:435-440`, `main.py:638-640`)
- calls `_update_stage(...)` (`main.py:640`)
- selects guidance functions for the resulting stage (`main.py:642-649`)

`_update_stage()` reads `curr_reward = policy.get_normalized_reward()` and compares it to `state["prev_norm_reward"]` (`main.py:442-450`). It interprets gripper action `<0` as open and `>0` as close, then triggers stage recognition on gripper open/close or Schmitt reward threshold crossings (`main.py:452-475`). Reward triggers only apply when `state["use_guidance"]` is true (`main.py:461-463`).

If a trigger occurs and `gemini_stage_recognizer` exists under the query limit, Gemini receives the current VLM image, task description, stage descriptions, initial keypoint image, keypoint-object map, number of stages, and trigger reason (`main.py:476-491`). It returns `(new_stage, need_guidance)`, and if stage changed, `policy.reset_stage()` clears the reward baseline (`main.py:495-504`). The stage recognizer parses text for `stage N` and `guidance: yes/no`, defaulting to `(1, True)` on failure (`core/gemini_grounder.py:154-217`).

Adaptive scale inside `_sample_actions_guided()` depends on stage-local reward baseline:

- First guided chunk of a stage: `_stage_init_reward` is `None`, so `normalized_reward=0.0`; after the loop, it is set to that chunk's final reward (`core/pi05_steer.py:247-252`, `core/pi05_steer.py:288-292`).
- Later chunks: if baseline is negative, `normalized_reward = 1 - reward_value / stage_init_reward`, clipped to `[0,1.2]` (`core/pi05_steer.py:247-250`).
- `guidance_strength = 1 / (1 + exp(sigmoid_k * (normalized_reward - sigmoid_x0)))`; with higher normalized reward, the scale drops (`core/pi05_steer.py:258-266`).

The run default `main.guide_scale` is `40.0` (`configs/config.yaml:40-42`), but `LiberoAdapter.get_task_info()` returns default recommended guide scale `80.0` when no task-specific list is configured (`core/env_adapters/libero_adapter.py:1672-1695`). `Main.__init__()` and per-episode reset use this recommended scale when present (`main.py:124-139`, `main.py:529-534`).

## 14. Video, logging, success, and result recording path

At the start of each episode, `video_recorder.clear()` is called and `episode_dir` is created under Hydra's output dir (`main.py:519-524`). During each rollout step, `_run_episode()` either draws the predicted action trajectory or gets a VLM image (`main.py:685-697`), optionally draws keypoints (`main.py:698-706`), overlays stage/guidance/gripper/reward/scale text (`main.py:708-735`), and stores the frame under `self.adapter.vlm_camera` (`main.py:735-736`).

`draw_action_trajectory_on_vlm_image()` uses `adapter.get_vlm_image_raw()` for LIBERO, projects action-derived 3D trajectories with camera intrinsics/extrinsics, draws lines/markers, then flips the final overlay vertically so it matches `get_vlm_image()` orientation (`utils/vis_utils.py:287-443`).

On termination or truncation, `Main._run_episode()` reads `info["success"]`, increments `success_count` if true, builds `episode_{N}_success` or `episode_{N}_fail`, and calls `video_recorder.save_video(save_path=..., success=...)` (`main.py:746-755`). `TrajectoryVideoRecorder.save_video()` writes one MP4 per camera as `{save_path}_{camera_name}.mp4`, pads frames to a common size, overlays `SUCCESS` or `FAIL`, and uses `imageio.mimsave(..., codec="libx264")` (`utils/vis_utils.py:684-766`).

After all episodes, `Main.run()` computes `success_count / episode_num * 100` and appends backend, success count, and success rate to `results.txt` in the output directory (`main.py:576-585`).

## 15. Tensor/action/observation shape table

| Item | Shape / type | Where established | Notes |
|---|---:|---|---|
| Raw LIBERO action | `(7,) np.float32` | `LiberoEnv.action_space`, `libero_adapter.py:585-587` | OSC normalized action. |
| Raw LIBERO policy camera images | `(H,W,3) uint8` | `LiberoEnv._format_raw_obs`, `libero_adapter.py:654-663` | `H=W=128` from backend config by default. |
| Adapter policy images | `(1,C,H,W) float32 [0,1]` | `libero_adapter.py:659-663` | Camera mapped to `observation.images.image/image2`. |
| Post-env-preprocessor policy images | `(B,C,H,W)` | `libero_adapter.py:993-1025` | `LiberoProcessorStep` flips H and W; batch expands to `sample_batch_size`. |
| Flat robot state | `(B,8)` | `LiberoProcessorStep`, `libero_adapter.py:86-96` | EEF pos 3, EEF axis-angle 3, gripper qpos 2. |
| PI0.5 checkpoint image feature | `(3,256,256)` | HF `config.json:4-35` | Policy then resizes/pads to `(224,224)`. |
| PI0.5 input tokens | `(B,200)` | HF preprocessor tokenizer config | Key `observation.language.tokens`. |
| PI0.5 noise / latent `x_t` | `(B,50,32)` | `pi05_steer.py:171-173`, HF `config.json:55-59` | 50 chunk, 32 max action dim. |
| Guided sample passed to reward | `(B,50,7)` | `pi05_steer.py:234-235` | Sliced to original action dim. |
| Guided return chunk | `(B,10,7)` | `pi05_steer.py:294-295` | 10 from `policy.pi05.action_chunk_horizon`. |
| Unguided parent return chunk | `(B,50,7)` | `modeling_pi05.py:1191-1207` | Main executes first 10. |
| Keypoints | `(N,3) np.ndarray` -> torch `(N,3)` | `keypoint_detector.py:151-283`, `pi05_steer.py:197-200` | World coordinates. |
| Adapter trajectory | `(T+1,3)` | `libero_adapter.py:1528-1577` | Includes current EEF start point. |
| Reward gradient | same as sample, normally `(B,50,7)` | `pi05_steer.py:397-404` | Only `[:,:10,:3]` applied. |
| Executed action | `(7,) torch.Tensor` -> `(7,) np.float32` | `main.py:737`, `libero_adapter.py:1590-1604` | Gripper binarized before environment. |

## 16. System map diagram

```text
Hydra config
  configs/config.yaml
  configs/backend/libero.yaml
  configs/policy.yaml
  configs/perception.yaml
        |
        v
main.py Main
  creates LiberoAdapter
  loads PI05PolicySteer + LeRobot processors
  creates keypoint/VLM/Gemini/video components
        |
        +--> LIBERO env reset/step
        |      raw robosuite obs
        |      -> LiberoEnv._format_raw_obs
        |      -> LiberoAdapter._last_obs
        |
        +--> policy observation path
        |      _last_obs
        |      -> LiberoProcessorStep: image flip + flat state
        |      -> batch expand to sample_batch_size
        |      -> LeRobot PI0.5 preprocessor: normalize, state prompt, tokenize, device
        |      -> PI05PolicySteer.select_action
        |
        +--> VLS perception path
        |      sim.render RGB/depth/segmentation at 640
        |      -> depth-to-world point cloud
        |      -> DINO feature clustering in segmentation masks
        |      -> KeypointTracker local object registration
        |      -> VLM guidance functions per stage
        |
        v
PI05PolicySteer._sample_actions_guided
  x_t Gaussian action latent
  prefix image/language KV cache
  denoise_step loop
  -> diversity gradient before start_time
  -> keypoint reward gradient after start_time
  -> optional FKD resampling
  -> postprocess selected chunk
        |
        v
main executes action_chunk[0][action_executed]
  -> LiberoAdapter.step
  -> gripper sign binarization
  -> float32 numpy 7D OSC action
  -> LiberoEnv.step
  -> robosuite OffScreenRenderEnv.step
```

## 17. Suspicious or ambiguous points

1. The target worktree has an empty `third_party/lerobot/` submodule. `libero_adapter.py` has a fallback for the env processor, but `core/pi05_steer.py` still imports `lerobot.policies.pi05.modeling_pi05`; this requires an external installed LeRobot package or a populated parent/source checkout.

2. Guided PI0.5 returns `(B,10,7)`, while unguided parent PI0.5 returns `(B,50,7)`. Main only executes 10 steps, so both are runnable, but debug drawing and cached chunk semantics differ across guided/unguided stages.

3. `MCMC_steps` is accepted in `PI05PolicySteer.select_action()` but not used. No PI0.5 MCMC refinement code was found.

4. FKD likely does not work as intended in PI0.5. `FKD` expects scheduler-like timesteps, casts the supplied `torch.linspace(1.0,0.0,11)` to long values, and receives integer loop indices as `sampling_idx`. Most resampling calls appear to miss the timestep map.

5. `_compute_keypoint_gradient()` uses `trajectory[:, :horizon, :3]`, which includes the start pose and drops the last future point from a `(T+1,3)` trajectory. `_init_fkd()` uses `[:, 1:horizon, :3]`, which excludes the start but also returns only `horizon-1` future points. These reward input windows are inconsistent.

6. At a chunk boundary, `_run_episode()` sets `generate_new_chunk = (action_executed == 0)` after `action_executed` has reset. `_update_stage()` then receives `_get_gripper_value(action_chunk, action_executed)`, which reads index 0 of the old chunk, not necessarily the most recently executed gripper action.

7. The PI0.5 checkpoint config records image feature shapes `(3,256,256)`, while current LIBERO backend config renders policy observations at `128x128`. The PI0.5 model image preprocessor later resizes to `224x224`, so this may be benign, but the checkpoint feature declaration and adapter default differ.

8. Guidance changes only the first three action dimensions. Orientation and gripper are driven by the unguided PI0.5 prior and action postprocessor.

9. If `sample_batch_size > 1` and FKD is inactive, main always executes particle 0. Diversity and gradient guidance update all particles, but there is no explicit best-particle selection without functioning FKD.

## 18. Open questions and lightweight verification probes

1. Verify whether `PI05PolicySteer.from_pretrained()` in the actual runtime uses the parent checkout, site-packages, or HF-installed LeRobot. Probe: `python -c "import lerobot, inspect; import lerobot.policies.pi05.modeling_pi05 as m; print(lerobot.__file__); print(m.__file__)"` in the intended environment.

2. Verify FKD activity without a rollout. Probe: instantiate a tiny mock `FKD` with the same `timesteps=torch.linspace(1.0,0.0,11)` and call `resample(sampling_idx=2..10)` to confirm which calls are skipped.

3. Verify chunk shape transitions. Probe: monkeypatch `PI05PolicySteer.predict_action_chunk()` / `_sample_actions_guided()` with small tensors and call `select_action(... use_guidance=True/False)` to log returned shapes.

4. Verify trajectory reward window semantics. Probe: log the first and last point passed to guidance functions and compare with `delta_actions_to_ee_trajectory()` for a known constant delta action.

5. Verify stage gripper trigger indexing. Probe: log `action_executed`, previous chunk id, and `_get_gripper_value()` before `_update_stage()` at chunk boundaries.

6. Verify policy image size assumptions. Probe: print shapes before `env_preprocessor`, after `env_preprocessor`, after policy preprocessor, and inside `PI05Policy._preprocess_images()`.

7. Verify actual action ranges after LeRobot unnormalizer and before LIBERO gripper binarization. Probe: log min/max and dtype for `action_chunk[0, :10]` after `policy.select_action()` and just before `LiberoAdapter.step()`.

## 19. No runtime code/config modifications

This investigation did not modify runtime code or configs, did not run rollouts/evaluations, did not launch VLM API calls, and did not generate new guidance functions. The only intended filesystem change is this Markdown analysis document:

```text
docs/docs/02_analysis/vls_guidance/2026-06-02-pi05-libero-vls-steering-system-path.md
```
