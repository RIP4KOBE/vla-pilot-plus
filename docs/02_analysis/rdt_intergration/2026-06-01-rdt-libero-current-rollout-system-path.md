---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/rdt_intergration/2026-06-01-rdt-libero-current-rollout-system-path.md
summary: RDT-LIBERO Current Rollout System Path
duplicate_sources: []
---

# RDT-LIBERO Current Rollout System Path

Date: 2026-06-01

Worktree:

```text
/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-gt-rollout-reintegration
```

Command under analysis:

```bash
python main.py policy.type=rdt
```

This document traces the current RDT-LIBERO rollout/evaluation path. It is a code-path analysis only; no rollout jobs were launched for this report.

## 1. Executive Summary

The current command enters through Hydra in `main.py`, loads the default LIBERO backend from `configs/config.yaml` and `configs/backend/libero.yaml`, and selects the RDT policy from `configs/policy.yaml`. The configured checkpoint is the GT LIBERO object checkpoint root:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object
```

with EMA weights:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
```

RDT rollout is integrated through the normal `Main.run()` loop. `Main` creates a `LiberoAdapter`, loads `RDTSteer`, calls `RDTSteer.post_init()`, then repeatedly:

1. Gets a policy observation from `LiberoAdapter.get_policy_observation()`.
2. Calls `RDTSteer.select_action()`.
3. Executes one action from the returned action chunk through `LiberoAdapter.step()`.
4. Records a video frame.
5. Stops an episode on success or truncation and writes videos/results.

The RDT-specific observation path intentionally uses raw LIBERO observation keys preserved by the adapter:

```text
agentview_image
robot0_eye_in_hand_image
robot0_joint_pos
robot0_gripper_qpos
task
```

Those raw keys are consumed by `RDTLiberoObsProcessor`, which builds:

```text
images: 6 slots = 2 history frames x 3 camera slots
state_128: (1, 128)
state_mask_128: (1, 128)
task: str
```

Only two cameras are real; the third camera slot per history frame is `None` and is converted to a SigLIP mean-color background image during RDT encoding.

The action path samples in the full RDT 128D action space, masks invalid dimensions, then decodes slots:

```text
[39, 40, 41, 42, 43, 44, 10] -> LIBERO 7D OSC action
```

The decoded action is passed directly to LIBERO/robosuite as a normalized 7D OSC action. The last gripper value is binarized to `-1` or `+1`.

One important runtime caveat from the current local worktree: `third_party/libero` is not present in this isolated worktree, and `lerobot` is not importable from the active Python environment. The adapter has a local LeRobot fallback, but LIBERO itself must be importable via installation or `PYTHONPATH`.

## 2. Files Inspected

Primary required files:

- `main.py`
- `configs/policy.yaml`
- `configs/backend/libero.yaml`
- `core/rdt_policy_steer.py`
- `core/rdt_libero_obs_processor.py`
- `core/rdt_libero_action_converter.py`
- `core/env_adapters/libero_adapter.py`

Additional helper/config files inspected:

- `configs/config.yaml`
- `core/env_adapters/__init__.py`
- `core/env_adapters/base_adapter.py`
- `core/policy_observation_sampling.py`
- `utils/vis_utils.py`
- `third_party/rdt/scripts/maniskill_model.py`
- `third_party/rdt/models/rdt_runner.py`
- `/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/config.json`

Supporting contract/tests scanned:

- `tests/test_rdt_runtime_contract.py`
- `tests/test_rdt_libero_obs_processor.py`
- `tests/test_rdt_libero_action_converter.py`
- `tests/test_rdt_steer.py`
- `tests/test_env_adapters_imports.py`
- `tests/test_main_rdt_startup.py`

Checked but not present:

- `configs/main.yaml` does not exist. Main settings live in `configs/config.yaml`.

## 3. End-to-End Call Graph

High-level path:

```text
main.py::__main__
  -> hydra.main(config_path="configs", config_name="config")
  -> main(cfg)
  -> Main.__init__(cfg)
     -> create_adapter("libero", env_config)
        -> LiberoAdapter.__init__()
           -> create_libero_envs(...)
              -> _apply_perturbations(...)
              -> _get_suite("libero_object")
              -> LiberoEnv(...)
                 -> LiberoEnv._make_envs_task(...)
                    -> OffScreenRenderEnv(...)
     -> RDTSteer.from_pretrained(...)
        -> _resolve_rdt_weight_file(...)
        -> load checkpoint config.json
        -> third_party/rdt/scripts/maniskill_model.py::create_model(...)
        -> RoboticDiffusionTransformerModel(...)
        -> _RDTModelAdapter(real_model)
     -> RDTSteer.to("cuda")
     -> RDTSteer.post_init(adapter=LiberoAdapter, ...)
     -> RDTSteer.eval()
     -> _init_components(...)
     -> RDTSteer.reset()
  -> Main.run()
     -> for each episode:
        -> RDTSteer.reset()
        -> TrajectoryVideoRecorder.clear()
        -> LiberoAdapter.reset(seed=episode_seed)
           -> LiberoEnv.reset(...)
              -> OffScreenRenderEnv.reset()
              -> set_init_state(...)
              -> no-op settle steps
        -> Main._run_episode(...)
           -> Main._get_policy_observation()
              -> LiberoAdapter.get_policy_observation(sample_num=1)
           -> while not done:
              -> RDTSteer.select_action(...)
                 -> RDTLiberoObsProcessor.observe(...)
                 -> _get_lang_embed(...)
                 -> _predict_unguided(...)
                    -> _RDTModelAdapter.encode_inputs(...)
                    -> scheduler denoising loop
                 -> _postprocess_actions(...)
              -> optional draw_action_trajectory_on_vlm_image(...)
              -> TrajectoryVideoRecorder.add_frame(...)
              -> LiberoAdapter.step(action_chunk[0][action_executed])
                 -> LiberoEnv.step(action_numpy)
                    -> OffScreenRenderEnv.step(...)
                    -> check_success()
              -> Main._get_policy_observation()
              -> on terminated/truncated:
                 -> TrajectoryVideoRecorder.save_video(...)
                 -> success_count += 1 if success
     -> write results.txt
```

## 4. Config and Checkpoint Loading Path

### Hydra defaults

`main.py` registers:

```python
@hydra.main(version_base=None, config_path="configs", config_name="config")
```

`configs/config.yaml` provides defaults:

```yaml
defaults:
  - backend: libero
  - env: null
  - task: null
  - perception
  - policy
  - _self_
```

Therefore `python main.py policy.type=rdt` uses the LIBERO backend unless another override is supplied.

Important `configs/config.yaml` main keys:

```yaml
device: cuda
seed: 0
main.episode_num: 10
main.output_dir: ${hydra:run.dir}
main.use_guidance: false
main.vls_config.sample_batch_size: 20
main.debug_draw_trajectory: true
hydra.run.dir: outputs/${experiment.name}/${now:%Y-%m-%d_%H-%M-%S}
```

The experiment name is `${backend.backend}`, so the default output directory is:

```text
outputs/libero/<timestamp>
```

### Policy selection

`configs/policy.yaml` currently has:

```yaml
type: rdt

rdt:
  pretrained_path: /mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object
  weight_variant: ema
  text_encoder: /mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl
  vision_encoder: /mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384
  num_inference_steps: null
  action_chunk_horizon: 8
  control_frequency: 20
  debug_first_step: true
  undo_libero_preprocessor_flip: false
  fail_on_zero_language_embedding: true
  semantics: libero_gt_rollout
```

`Main.__init__()` reads:

- `policy_type = cfg.policy.type`
- `type_config = cfg.policy[policy_type]`
- `pretrained_path = type_config.pretrained_path`

For `policy_type == "rdt"`, it imports `RDTSteer` lazily and calls:

```python
RDTSteer.from_pretrained(
    pretrained_path,
    num_inference_steps=...,
    vision_encoder=...,
    text_encoder=...,
    weight_variant=...,
    control_frequency=...,
)
```

RDT bypasses LeRobot policy preprocessors:

```python
self.policy_preprocessor = lambda x: x
self.policy_postprocessor = lambda x: x
```

### RDT checkpoint resolution

`RDTSteer.from_pretrained()` in `core/rdt_policy_steer.py`:

1. Adds `third_party/rdt` to `sys.path`.
2. Verifies local checkpoint path exists if it looks like a local path.
3. Resolves the weight file with `_resolve_rdt_weight_file(pretrained_path, weight_variant)`.
4. For the current config, this resolves:

```text
checkpoint_root = /mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object
weight_file     = /mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
```

5. Searches for `config.yaml` or `config.json` near the weight root.
6. Loads `/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/config.json`.
7. Converts the flat HuggingFace config into the RDT script argument layout through `_rdt_flat_config_to_args()`.

Verified checkpoint config values:

```text
pred_horizon: 64
action_dim: 128
state_token_dim: 128
max_lang_cond_len: 1024
lang_token_dim: 4096
img_token_dim: 1152
img_pos_embed_config: [["image", [2, 3, -729]]]
noise_scheduler:
  beta_schedule: squaredcos_cap_v2
  clip_sample: false
  num_inference_timesteps: 5
  num_train_timesteps: 1000
  prediction_type: sample
  type: ddpm
```

If `policy.rdt.num_inference_steps` is `null`, `RDTSteer.from_pretrained()` uses `config["noise_scheduler"]["num_inference_timesteps"]`, currently `5`.

### Encoder path handling

Text encoder:

- Config path: `/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl`
- `_rdt_text_encoder_arg_and_load_path()` maps this cache root to:
  - RDT model argument: `"google/t5-v1_1-xxl"`
  - Transformers load path: resolved local snapshot under the cache root

This is needed because RDT's `T5Embedder` expects the symbolic model ID, while the code monkey-patches Transformers `from_pretrained()` to load the local snapshot.

Vision encoder:

- Config path: `/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384`
- `_resolve_vision_encoder_path()` resolves it to a local snapshot containing `preprocessor_config.json` and `config.json`.

During model construction, `RDTSteer.from_pretrained()` temporarily forces `local_files_only=True` for:

- `T5EncoderModel`
- `AutoTokenizer`
- `AutoConfig`
- `SiglipImageProcessor`
- `SiglipVisionModel`

and sets:

```text
DISABLE_SAFETENSORS_CONVERSION=1
```

to prevent background hub safetensors conversion downloads.

### RDT model construction

`RDTSteer.from_pretrained()` imports `create_model` from:

```text
third_party/rdt/scripts/maniskill_model.py
```

`create_model(args, pretrained=weight_file, ...)` constructs a `RoboticDiffusionTransformerModel` and loads weights into its `policy`:

- `.safetensors` -> `safetensors.torch.load_model(self.policy, pretrained)`
- `.pt` -> `self.policy.load_state_dict(checkpoint["module"])`

`RoboticDiffusionTransformerModel` constructs:

- T5 tokenizer/model via `T5Embedder`
- SigLIP vision tower via `SiglipVisionTower`
- `RDTRunner`

`RDTSteer.from_pretrained()` then wraps the plain Python object in `_RDTModelAdapter`, which exposes:

- `.dit = _RDTDiTAdapter(real_model.policy)`
- `.noise_scheduler = real_model.policy.noise_scheduler_sample`
- `.encode_inputs(...)`
- `.to(...)`
- `.eval(...)`

## 5. LIBERO Backend and Environment Creation Path

`Main.__init__()` builds `env_config` from:

```python
cfg.backend[cfg.backend.backend]
```

For the current default backend, `configs/backend/libero.yaml` supplies:

```yaml
backend: libero

libero:
  suite_name: libero_object
  task_id: 0
  camera_name: agentview_image, robot0_eye_in_hand_image
  obs_type: pixels_agent_pos
  render_mode: rgb_array
  observation_width: 128
  observation_height: 128
  visualization_width: 640
  visualization_height: 640
  init_states: true
  num_steps_wait: 5
  max_episode_steps: 720
  vlm_camera: agentview
  auto_apply_perturbations: true
  task_ids_filter: null
```

`Main.__init__()` adds:

```python
env_config["episode_num"] = cfg.main.episode_num
```

Then calls:

```python
create_adapter("libero", env_config)
```

`core/env_adapters/__init__.py::create_adapter()` instantiates:

```python
LiberoAdapter(None, env_config)
```

`LiberoAdapter.__init__()` calls `create_libero_envs()` with:

- suite name
- camera names
- perturbation flag
- task filter
- observation and visualization sizes
- reset-settle step count
- max episode steps

`create_libero_envs()`:

1. Parses camera names through `_parse_camera_names()`.
2. Applies LIBERO-PRO perturbations if requested and available.
3. Instantiates the suite through `benchmark.get_benchmark_dict()[suite_name]()`.
4. Selects all task IDs if `task_ids_filter is None`.
5. Creates one `LiberoEnv` per selected task.

For `libero_object` with `task_ids_filter: null`, this creates all tasks in the suite. The adapter requires:

```python
episode_num % task_num == 0
```

The default is 10 episodes over 10 LIBERO object tasks, so `episodes_per_task == 1`.

## 6. LIBERO Raw Observation to Policy Observation Path

### Raw observation source

Each `LiberoEnv` wraps:

```python
libero.libero[redacted env file]s.OffScreenRenderEnv
```

The underlying raw observations come from:

- `OffScreenRenderEnv.reset()`
- `OffScreenRenderEnv.set_init_state(...)`
- `OffScreenRenderEnv.step(action)`

`LiberoEnv._make_envs_task()` constructs `OffScreenRenderEnv` with:

```python
env_args = {
    "bddl_file_name": task_bddl_file,
    "camera_heights": self.observation_height,
    "camera_widths": self.observation_width,
    "camera_depths": True,
}
```

With the current config, policy images are rendered at `128 x 128`.

### Reset path

`Main.run()` calls:

```python
self.adapter.reset(seed=episode_seed)
```

`LiberoAdapter.reset()`:

1. Increments `current_episode_idx`.
2. Switches `current_task_idx` after `episodes_per_task` episodes.
3. Resets `episode_step = 0`.
4. Calls `current_env.reset(seed=episode_seed)`.
5. Stores the returned observation in `self._last_obs`.

`LiberoEnv.reset()`:

1. Seeds the underlying `OffScreenRenderEnv`.
2. Calls `self._env.reset()`.
3. If init states are enabled, calls:

```python
self._env.set_init_state(self._init_states[self._init_state_id])
```

4. Executes `num_steps_wait` no-op actions:

```python
get_libero_dummy_action() -> [0, 0, 0, 0, 0, 0, 0]
```

5. Converts the final raw observation through `_format_raw_obs()`.

### `_format_raw_obs()`

`LiberoEnv._format_raw_obs(raw_obs)` produces a mixed observation dict containing both RDT raw keys and LeRobot-style keys.

Raw RDT keys are preserved if present:

```text
agentview_image
robot0_eye_in_hand_image
robot0_joint_pos
robot0_gripper_qpos
task
```

The `task` value is the task language from the LIBERO suite, or BDDL language only for language-changing perturbations.

LeRobot-style image keys are also created:

```text
observation.images.image   <- agentview_image
observation.images.image2  <- robot0_eye_in_hand_image
```

For these keys, `_format_raw_obs()` converts raw images:

```text
np uint8 HWC [0,255] -> torch float32 BCHW [0,1]
```

Robot state is stored as:

```text
observation.robot_state.eef.pos
observation.robot_state.eef.quat
observation.robot_state.eef.mat
observation.robot_state.gripper.qpos
observation.robot_state.gripper.qvel
observation.robot_state.joints.pos
observation.robot_state.joints.vel
```

### `LiberoAdapter.get_policy_observation()`

`Main._get_policy_observation()` asks `policy_observation_sample_num()` for a sample count. For RDT:

```python
policy_observation_sample_num("rdt", configured_sample_batch_size, default=20) -> 1
```

So RDT receives `sample_num=1` regardless of `main.vls_config.sample_batch_size: 20`.

`LiberoAdapter.get_policy_observation(sample_num=1)`:

1. Copies `self._last_obs`.
2. Replaces/sets `obs["task"] = [task_desc] * sample_num`.
3. Saves raw RDT keys into `rdt_raw_obs`.
4. Runs `self[redacted env file]_preprocessor(obs)`.
5. Restores raw RDT keys by `obs.update(rdt_raw_obs)`.
6. Expands tensor batch dimensions only if `sample_num > 1`.

`env_preprocessor` is a `PolicyProcessorPipeline` with one `LiberoProcessorStep`.

If LeRobot is unavailable, the local fallback `LiberoProcessorStep`:

- flips any `observation.images.*` tensor along height and width dims
- converts `observation.robot_state` into `observation.state`
- state layout is:

```text
eef_pos(3) + eef_axisangle(3) + gripper_qpos(2)
```

Important: the RDT raw image keys are restored after this preprocessing. Therefore, for RDT, `agentview_image` and `robot0_eye_in_hand_image` remain raw HWC `uint8` images and are not the flipped BCHW tensors.

## 7. Policy Observation to RDT Observation / Model Input Path

`RDTSteer.post_init()` creates:

```python
RDTLiberoObsProcessor(
    undo_preprocessor_flip=policy.rdt.undo_libero_preprocessor_flip,
    debug_first_step=policy.rdt.debug_first_step,
)
```

Current config:

```yaml
undo_libero_preprocessor_flip: false
debug_first_step: true
```

### `RDTSteer.select_action()`

`Main._run_episode()` calls:

```python
action_chunk = self.policy.select_action(observation, generate_new_chunk=..., use_guidance=False, ...)
```

Because `main.use_guidance: false`, RDT always uses the unguided path.

`RDTSteer.select_action()`:

1. Calls `self._obs_processor.observe(batch)` every environment step.
2. Decides whether to sample a new chunk:

```python
should_sample = (
    generate_new_chunk
    or use_guidance
    or self._cached_action_chunk is None
    or self._cached_action_steps_remaining <= 0
)
```

3. If `should_sample`, gets `converted = self._obs_processor.current()`.
4. For unguided RDT:
   - embeds language with `_get_lang_embed(converted.task)`
   - calls `_predict_unguided(...)`
   - calls `_postprocess_actions(...)`
   - caches the decoded chunk
5. Decrements `_cached_action_steps_remaining`.
6. Returns the cached chunk.

### `RDTLiberoObsProcessor`

`RDTLiberoObsProcessor.observe(obs)` consumes:

```text
agentview_image
robot0_eye_in_hand_image
robot0_joint_pos
robot0_gripper_qpos
task
```

Images:

- Required shape: `(H, W, 3)`
- Required dtype: `uint8`
- Current source resolution: `128 x 128`
- Converted to PIL without resizing in the observation processor.
- `undo_preprocessor_flip` is false, so no flip is applied to raw images.

History:

- Maintains two-frame deques for agent and wrist cameras.
- On first observation, duplicates the current frame into both history slots.
- On later steps, appends the current frame.

The output image list is:

```python
[
    agent_history[0],
    wrist_history[0],
    None,
    agent_history[1],
    wrist_history[1],
    None,
]
```

This matches the checkpoint config `img_pos_embed_config = [["image", [2, 3, -729]]]`: two history frames and three camera slots.

State:

`RDTLiberoObsProcessor._build_state()` validates:

```text
robot0_joint_pos shape: (7,)
robot0_gripper_qpos shape: (2,)
finite values
gripper qpos within [-0.04245, 0.05185] plus tolerance
```

Then normalizes gripper qpos:

```python
gripper_norm = (gripper - GRIPPER_MIN) / (GRIPPER_MAX - GRIPPER_MIN)
```

and builds:

```text
proprio = [7 joint positions, 2 normalized gripper qpos]
state_128 shape: (1, 128)
state_mask_128 shape: (1, 128)
```

The active state slots are:

```text
LIBERO_STATE_INDICES = [0, 1, 2, 3, 4, 5, 6, 10, 11]
```

Language:

`_task_from_obs()` expects a non-empty string. Since `LiberoAdapter.get_policy_observation()` uses `obs["task"] = [task_desc]`, a single-element list is unwrapped to the string.

### RDT encoder condition construction

`RDTSteer._predict_unguided()` calls:

```python
cond = self._rdt_model.encode_inputs(state_128, state_mask_128, images, text_embed)
```

The concrete implementation is `_RDTModelAdapter.encode_inputs()`.

Image encoding:

1. Creates a background image using `real.image_processor.image_mean`.
2. Replaces `None` camera slots with that background image.
3. Optionally resizes only if `real.image_size is not None`.
4. Pads non-square images to square if `args["dataset"]["image_aspect_ratio"] == "pad"`.
5. Calls `real.image_processor.preprocess(img, return_tensors="pt")`.
6. Stacks the six image tensors.
7. Moves them to RDT device and dtype.
8. Runs `real.vision_model(image_tensor)`.
9. Reshapes embeddings to:

```text
image_embeds: (1, image_token_count, 1152)
```

In the observed successful logs for this checkpoint, `image_embed_shape` was:

```text
(1, 4374, 1152)
```

which is `6 * 729` SigLIP image tokens.

State encoding:

1. Validates `state_128.shape == (1, 128)`.
2. Validates `state_mask_128.shape == (1, 128)`.
3. Validates active mask exactly equals:

```text
[0, 1, 2, 3, 4, 5, 6, 10, 11]
```

4. Builds an action mask with active action slots:

```text
LIBERO_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]
```

5. Validates sorted active action mask equals:

```text
[10, 39, 40, 41, 42, 43, 44]
```

6. Sets:

```python
ctrl_freqs = torch.tensor([real.control_frequency], device=device)
```

Current control frequency is `20`.

Language encoding:

`RDTSteer._get_lang_embed(task)` calls:

```python
real.encode_instruction(task, device=str(self.device))
```

from `third_party/rdt/scripts/maniskill_model.py::RoboticDiffusionTransformerModel.encode_instruction()`.

That function tokenizes the raw task instruction with the T5 tokenizer:

```python
self.text_tokenizer(instruction, return_tensors="pt", padding="longest", truncation=True)
```

and returns:

```text
last_hidden_state: (1, token_len, 4096)
```

`RDTSteer._get_lang_embed()` converts the embedding to `float32` on the RDT device, then `_RDTModelAdapter.encode_inputs()` moves it to RDT dtype, currently bfloat16 for the real model.

If `policy.rdt.fail_on_zero_language_embedding` is true, `_get_lang_embed()` raises if the embedding is non-finite or all-zero.

Condition adaptation:

`_RDTModelAdapter.encode_inputs()` concatenates:

```python
state_tokens = torch.cat([states, action_mask.unsqueeze(1)], dim=2)
```

where:

```text
states: (1, 1, 128)
action_mask.unsqueeze(1): (1, 1, 128)
state_tokens: (1, 1, 256)
```

Then it calls:

```python
real.policy.adapt_conditions(text_embeds, image_embeds, state_tokens)
```

`RDTRunner.adapt_conditions()` maps language, image, and state tokens into the RDT hidden size through learned adaptors.

The returned `cond` dict contains:

```text
lang_cond
lang_attn_mask
img_cond
state_traj
action_mask: (1, 1, 128)
ctrl_freqs
action_indices
unified_action_dim: 128
```

## 8. RDT Denoising Path

The unguided path is:

```text
RDTSteer.select_action()
  -> _predict_unguided()
     -> _RDTModelAdapter.encode_inputs()
     -> scheduler.set_timesteps(num_inference_steps)
     -> for t in scheduler.timesteps:
          _RDTDiTAdapter.forward(x_t, t, cond)
          scheduler.step(noise_pred, t, x_t).prev_sample
     -> apply action_mask
```

### Initial noisy action tensor

`RDTSteer._predict_unguided()` hard-codes:

```python
pred_horizon = 64
x_t = torch.randn(B, pred_horizon, unified_action_dim, ...)
```

For current unguided rollout:

```text
B = 1
pred_horizon = 64
unified_action_dim = 128
x_t shape = (1, 64, 128)
```

### Scheduler

`RDTSteer._noise_scheduler` returns:

```python
real_model.policy.noise_scheduler_sample
```

This is `DPMSolverMultistepScheduler` created by `third_party/rdt/models/rdt_runner.py::RDTRunner`.

The scheduler config comes from the checkpoint config:

```text
num_train_timesteps: 1000
beta_schedule: squaredcos_cap_v2
prediction_type: sample
num_inference_timesteps: 5
```

`RDTSteer._predict_unguided()` calls:

```python
scheduler.set_timesteps(self._num_inference_steps)
```

With current config, `_num_inference_steps == 5`.

### DiT adapter

`_RDTDiTAdapter.forward(x_t, t, cond)` receives:

```text
x_t: (B, 64, 128)
t: scalar or (1,)
cond: encoded language/image/state/action-mask dict
```

Since `raw_action_dim == unified_dim == 128`, it does not inflate from a subspace. It uses the full 128D tensor directly.

For each timestep:

1. Expands conditioning tensors to batch `B` if needed.
2. Expands the action mask to `(B, 64, 128)`.
3. Concatenates action and mask:

```text
action_traj = cat([x_unified, action_mask_full], dim=2)
shape: (B, 64, 256)
```

4. Runs `runner.state_adaptor(action_traj)`.
5. Concatenates state token trajectory:

```text
state_action_traj = cat([state_traj, action_traj], dim=1)
```

6. Calls the RDT DiT:

```python
self.runner.model(
    state_action_traj,
    ctrl_freqs,
    t,
    lang_cond,
    img_cond,
    lang_mask=lang_attn_mask,
)
```

7. Returns model output in 128D action space.

After all timesteps, `_predict_unguided()` multiplies by `action_mask`, so inactive action slots are zeroed:

```python
return (x_t * action_mask).float()
```

Final raw RDT output shape:

```text
(1, 64, 128)
```

## 9. RDT Action Chunk to LIBERO OSC Action Path

Action decoding is implemented in `core/rdt_libero_action_converter.py`.

`RDTSteer._postprocess_actions(actions)` expects:

```text
actions shape: (B, 64, 128)
```

It calls:

```python
decode_rdt_libero_action_chunk(actions, self._action_chunk_horizon)
```

Current `self._action_chunk_horizon` from `policy.rdt.action_chunk_horizon` is `8`.

`decode_rdt_libero_action_chunk()`:

1. Validates shape `(B, 64, 128)`.
2. Requires `B >= 1`.
3. Takes only the first particle:

```python
first_particle = pred_actions_128[0:1, :action_chunk_horizon, :]
```

4. Calls `rdt_action_to_libero_raw(first_particle)`.

`rdt_action_to_libero_raw()` selects:

```text
LIBERO_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]
```

and returns:

```text
decoded shape: (1, 8, 7)
```

The first six action dimensions are passed through unchanged from the selected RDT slots:

```text
decoded[..., 0:6] = RDT slots [39, 40, 41, 42, 43, 44]
```

The gripper dimension uses RDT slot `10` and is binarized:

```python
decoded[..., -1] = -1.0 if decoded[..., -1] < 0.0 else +1.0
```

No additional position scaling, rotation conversion, denormalization, or clipping is performed in the RDT converter. The decoded 7D action is treated as the LIBERO/robosuite normalized OSC action.

### Chunk buffering and first action selection

`Main._run_episode()` maintains:

```python
action_executed = 0
action_horizon = self.policy._action_chunk_horizon
generate_new_chunk = (action_executed == 0)
```

The first action executed from a newly decoded chunk is:

```python
action_chunk[0][0]
```

On each loop:

1. `RDTSteer.select_action()` returns the current chunk.
2. `Main` executes `action_chunk[0][action_executed]`.
3. `action_executed += 1`.
4. If `action_executed == action_horizon`, it resets to `0`, forcing a new sample next step.

`RDTSteer` also tracks `_cached_action_steps_remaining`, but the main loop's `generate_new_chunk` is the effective chunk-refresh driver in the unguided path.

## 10. LIBERO OSC Action to Environment / Controller Path

`Main._run_episode()` executes:

```python
obs, reward, terminated, truncated, info = self.adapter.step(action_chunk[0][action_executed])
```

The action entering `LiberoAdapter.step()` is a torch tensor with shape:

```text
(7,)
```

`LiberoAdapter.step()`:

1. Applies `self[redacted env file]_postprocessor`, currently an empty `PolicyProcessorPipeline`.
2. Clones the tensor.
3. Binarizes gripper again:

```python
action[-1] = 1 if action[-1] > 0 else -1
```

4. Converts to CPU numpy float32:

```python
action_numpy = action.float().to("cpu").numpy()
```

5. Calls the current task environment:

```python
current_env.step(action_numpy)
```

`LiberoEnv.step(action_numpy)`:

1. Validates action is 1D.
2. Calls:

```python
raw_obs, reward, done, info = self._env.step(action)
```

where `self._env` is `OffScreenRenderEnv`.

3. Calls:

```python
is_success = self._env.check_success()
terminated = done or is_success
```

4. Adds task/success fields to `info`.
5. Converts `raw_obs` with `_format_raw_obs()`.
6. If terminated, adds `final_info` and calls `self.reset()`.
7. Returns `observation, reward, terminated, truncated, info`.

`LiberoAdapter.step()` then:

1. Increments `self.episode_step`.
2. Stores `self._last_obs = observation`.
3. Overrides truncation with:

```python
truncated = self.episode_step >= current_env._max_episode_steps
```

Current `_max_episode_steps` is `720` from `configs/backend/libero.yaml`.

4. Adds:

```text
info["task_idx"]
info["task_id"]
info["task_description"]
```

5. Returns to `Main._run_episode()`.

`LiberoAdapter.get_action_space_info()` describes the intended action semantics as:

```text
dim: 7
type: delta_ee_pose
bounds: [-1, 1]^7
normalized: True
control_type: controller.control_type or OSC_POSE
control_dim: controller.control_dim or 6
```

Thus the decoded RDT action is assumed to already be in normalized LIBERO OSC delta pose format:

```text
[dx, dy, dz, d_rot0, d_rot1, d_rot2, gripper]
```

The exact controller internals are owned by LIBERO/robosuite `OffScreenRenderEnv.step()`.

## 11. Success, Termination, Video, and Result Recording

### Episode termination

`Main._run_episode()` checks after every environment step:

```python
if terminated or truncated:
    is_success = info.get("success", False)
    if is_success:
        done = True
        self.success_count += 1
    ...
    self.video_recorder.save_video(...)
    break
```

Important behavior:

- Success comes from `LiberoEnv.step()` calling `OffScreenRenderEnv.check_success()`.
- Truncation comes from `LiberoAdapter.step()` when `episode_step >= current_env._max_episode_steps`.
- `Main._run_episode()` breaks on either success or truncation.
- `done = True` is only assigned on success, but the loop exits via `break` either way.

### Video recording

`Main._run_episode()` records one video frame per control step.

Because `configs/config.yaml` currently has:

```yaml
main.debug_draw_trajectory: true
```

the current default path uses:

```python
utils.vis_utils.draw_action_trajectory_on_vlm_image(...)
```

This function gets the raw VLM camera image through `LiberoAdapter.get_vlm_image_raw()` when available, draws the projected action trajectory, then returns an image for overlay/recording.

If trajectory drawing is disabled, `Main` records:

```python
np.array(self.adapter.get_vlm_image())
```

which is the flipped human-viewable VLM camera image.

Then `Main` overlays status text with `add_text_to_image()` and calls:

```python
self.video_recorder.add_frame(self.adapter.vlm_camera, image_with_status)
```

At episode end, `TrajectoryVideoRecorder.save_video()` writes:

```text
episode_<N>_success_agentview.mp4
episode_<N>_fail_agentview.mp4
```

under the episode directory.

`TrajectoryVideoRecorder.save_video()` uses `imageio.mimsave(..., codec="libx264", fps=10)`.

### Results file

After all episodes, `Main.run()` writes:

```text
<hydra output dir>/results.txt
```

with:

```text
Backend: libero
Success count: <success_count>/<episode_num>
Success rate: <percent>%
```

## 12. Key Shapes and Semantics Table

| Stage | Key / tensor | Shape / type | Semantics |
|---|---:|---:|---|
| LIBERO raw obs | `agentview_image` | `(128, 128, 3)`, `uint8` | Main third-person RGB camera for RDT |
| LIBERO raw obs | `robot0_eye_in_hand_image` | `(128, 128, 3)`, `uint8` | Wrist RGB camera for RDT |
| LIBERO raw obs | `robot0_joint_pos` | `(7,)` | Robot joint positions in radians |
| LIBERO raw obs | `robot0_gripper_qpos` | `(2,)` | Raw gripper qpos; normalized by RDT obs processor |
| Adapter policy obs | `task` | list of one string for RDT sample num 1 | LIBERO task language |
| Adapter preprocessed obs | `observation.images.image` | `(1, 3, 128, 128)`, float `[0,1]` | LeRobot-style agentview tensor; flipped by `LiberoProcessorStep`; not the RDT image source |
| Adapter preprocessed obs | `observation.images.image2` | `(1, 3, 128, 128)`, float `[0,1]` | LeRobot-style wrist tensor; flipped; not the RDT image source |
| Adapter preprocessed obs | `observation.state` | `(1, 8)` | EEF pos, EEF axis-angle, gripper qpos; not the RDT proprio source |
| RDT observation | `images` | list length `6` | `[agent_t-1, wrist_t-1, None, agent_t, wrist_t, None]` |
| RDT observation | `state_128` | `(1, 128)`, float32 | Joint/gripper proprio inserted into slots `[0..6, 10, 11]` |
| RDT observation | `state_mask_128` | `(1, 128)`, float32 | Mask active at `[0..6, 10, 11]` |
| Language embed | `text_embeds` | `(1, token_len, 4096)` | T5 encoder output for raw LIBERO task string |
| Image embed | `image_embeds` | `(1, 4374, 1152)` observed | Six SigLIP image streams, `6 * 729` tokens |
| Action mask | `action_mask` | `(1, 1, 128)` | Active at `[39..44, 10]` |
| Denoising latent | `x_t` | `(1, 64, 128)` | Full RDT unified action space |
| RDT raw output | `actions` | `(1, 64, 128)` | Masked to active action slots only |
| Decoded chunk | `action_chunk` | `(1, 8, 7)` | First 8 actions, slots `[39..44, 10]` |
| Executed action | `action_chunk[0][i]` | `(7,)` | Normalized LIBERO OSC delta action |
| Env action | `action_numpy` | `(7,)`, numpy float32 | Passed to `OffScreenRenderEnv.step()` |

## 13. Suspicious or Ambiguous Points

### 13.1 Bare command depends on LIBERO import availability

In the current isolated worktree, `third_party/libero` is missing and `import libero` fails in the active environment unless an external install or `PYTHONPATH` supplies it. `core/env_adapters/libero_adapter.py` does add `third_party/libero` to `sys.path` if it exists, but it does not exist in this worktree.

Impact:

- The semantic path above is valid once LIBERO is importable.
- A truly bare shell invocation may fail before rollout if LIBERO is not installed or exposed via `PYTHONPATH`.

Suggested probe:

```bash
python - <<'PY'
import libero
print(libero.__file__)
PY
```

### 13.2 LeRobot processor availability changes the exact preprocessor implementation

`libero_adapter.py` tries to import LeRobot's `LiberoProcessorStep`. If unavailable, it uses a local fallback with the intended behavior. RDT uses restored raw keys, so this should not affect RDT images/state directly, but it can affect non-RDT paths and diagnostic logs.

Suggested probe:

```bash
python - <<'PY'
import core[redacted env file]_adapters.libero_adapter as la
print(la.LiberoProcessorStep)
PY
```

### 13.3 Diagnostic probes write into the repository tree

`LiberoAdapter.get_policy_observation()` contains P1/P2 diagnostic blocks that append to:

```text
docs/superpowers/03_evidence/rdt_intergration/round-3/20260511_obs_probes.log
```

These probes are pre-existing instrumentation, not required for RDT semantics. They write during normal rollout, although the `.log` file may be ignored by git.

Suggested cleanup later:

- Gate the probes behind an explicit debug flag.
- Redirect them to the Hydra output directory.

### 13.4 `main.debug_draw_trajectory` is true by default

The default `python main.py policy.type=rdt` path draws projected action trajectories on the video frames. This does not change actions, but it adds extra adapter calls for VLM rendering, camera params, and trajectory projection.

Suggested probe:

```bash
python main.py policy.type=rdt main.debug_draw_trajectory=false main.episode_num=1
```

and compare runtime/log behavior against the default.

### 13.5 RDT sample batch size is effectively ignored in unguided rollout

`configs/config.yaml` sets `main.vls_config.sample_batch_size: 20`, but `policy_observation_sample_num("rdt", ...)` returns `1`, and `RDTSteer._predict_unguided(..., B=1)` is hard-coded by the unguided path.

This is consistent with the current original/unguided RDT goal, but it is worth remembering if future VLS/FKD/diversity steering is re-enabled.

### 13.6 RDT action output is not clipped except gripper binarization

The RDT converter does not clip the first six decoded action dimensions to `[-1, 1]`; it only binarizes the gripper. LIBERO's action space is normalized `[-1, 1]^7`, and the environment/controller may clip or saturate internally.

Suggested probe:

- Log per-episode min/max of executed first-six action dimensions.
- Count values outside `[-1, 1]`.
- Decide whether explicit clipping should be added only if GT rollout also clips or if out-of-range values appear.

### 13.7 `LiberoEnv.step()` resets internally on success

`LiberoEnv.step()` calls `self.reset()` if `terminated`. `Main._run_episode()` still calls `_get_policy_observation()` after the step and before breaking. The processed observation is not used after the break, but this is a small inefficiency and can make final-step debugging more confusing.

Suggested probe:

- Add a temporary debug log of whether final-step `_get_policy_observation()` is called after success/truncation.
- If needed, reorder the loop later to check termination before computing the next observation.

### 13.8 Action representation relies on GT slot semantics

The current converter assumes RDT slots `[39, 40, 41, 42, 43, 44, 10]` are already LIBERO normalized OSC action dimensions. This is backed by the GT-aligned integration and tests, but the code does not derive that mapping from checkpoint metadata.

Suggested probe:

- Compare a real dataset action sample from the GT preprocessing path against the same slot mapping.
- Log first decoded chunk from the GT evaluator and this evaluator for the same initial state/task if deterministic seeds can be aligned.

## 14. Open Questions and Suggested Verification Probes

1. Is `third_party/libero` intentionally absent from this isolated worktree?

   Probe:

   ```bash
   python - <<'PY'
   import libero
   print(libero.__file__)
   PY
   ```

2. Does the current command always run with `CUDA_VISIBLE_DEVICES=0` or another GPU filter on this machine?

   Previous successful gates used GPU pinning due local device health. The code itself does not select a GPU ID beyond `device: cuda`.

   Probe:

   ```bash
   python - <<'PY'
   import torch
   print(torch.cuda.is_available(), torch.cuda.device_count())
   print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
   PY
   ```

3. Are any decoded RDT action values outside the normalized LIBERO controller range?

   Probe:

   - Add a first-step or per-chunk debug counter for `abs(action[:6]) > 1`.
   - Keep gripper separate because it is explicitly binarized.

4. Does disabling trajectory drawing affect success rate or runtime stability?

   Probe:

   ```bash
   python main.py policy.type=rdt main.debug_draw_trajectory=false main.episode_num=10
   ```

5. Is the local fallback `LiberoProcessorStep` exactly equivalent to the LeRobot processor for non-RDT state/video paths?

   Probe:

   - Run one synthetic observation through both if LeRobot is available.
   - Compare `observation.images.*` and `observation.state`.

6. Should diagnostic P1/P2 logs remain in normal rollout?

   Probe:

   ```bash
   rm -f docs/superpowers/03_evidence/rdt_intergration/round-3/20260511_obs_probes.log
   python main.py policy.type=rdt main.episode_num=1
   test -f docs/superpowers/03_evidence/rdt_intergration/round-3/20260511_obs_probes.log && echo "probe emitted"
   ```

## 15. Bottom Line

The current RDT-LIBERO rollout path is a direct GT-aligned unguided inference route:

- Hydra selects `backend=libero` and `policy.type=rdt`.
- `LiberoAdapter` creates one LIBERO environment per selected task and preserves raw LIBERO observations.
- `RDTLiberoObsProcessor` builds the GT-style two-history, three-camera-slot observation and 128D state/mask.
- `RDTSteer` loads the GT checkpoint EMA weights, local T5/SigLIP encoders, and runs a 5-step DPMSolver denoising loop in full 128D RDT space.
- `rdt_libero_action_converter` decodes action slots `[39, 40, 41, 42, 43, 44, 10]` into a LIBERO 7D normalized OSC action chunk.
- `Main._run_episode()` executes one action per step, refreshes every 8 actions, records videos, and writes success statistics.

No source files were modified while preparing this analysis except this Markdown report.
