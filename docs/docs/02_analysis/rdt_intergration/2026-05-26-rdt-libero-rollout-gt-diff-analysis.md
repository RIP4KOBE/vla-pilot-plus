# RDT-LIBERO Rollout GT Difference Analysis

Date: 2026-05-26

Worktree:

```text
.worktrees/feat/rdt-libero-object-ckpt
```

Ground-truth evaluation reference:

```text
third_party/Libero_RDT
commit 84eaafe7df60e922be10bf3b487ad573f314feb8
```

Current project rollout command under investigation:

```bash
python main.py policy.type=rdt
```

Observed current project result examples:

```text
outputs/libero/2026-05-25_12-53-58/results.txt  Success count: 0/10
outputs/libero/2026-05-25_14-48-37/results.txt  Success count: 0/10
outputs/libero/2026-05-26_03-24-48/results.txt  Success count: 0/10
```

## 1. Executive Summary

The current runtime can mechanically run RDT-LIBERO rollouts, load checkpoints, save videos, and report success counts. However, compared against `tj-chen-1209/Libero_RDT` as the ground-truth evaluation implementation, there are several rollout/evaluation differences that are large enough to plausibly explain persistent 0/10 success.

The most important finding is a semantic mismatch in the RDT state/action slots used at inference time.

GT evaluation uses:

```text
State input: 7 arm joint positions + 2 gripper joint positions
RDT state indices: arm_joint_0..6 + gripper_joint_0..1

Action output: 6D EEF velocity / OSC command + gripper
RDT action indices: eef_vel_x/y/z + eef_angular_vel_roll/pitch/yaw + gripper_open
```

Current project runtime uses:

```text
State input: EEF position + EEF 6D rotation + one gripper-open scalar
RDT state indices: eef_pos_x/y/z + eef_angle_0..5 + gripper_open

Action output: EEF position-like slots + 6D rotation slots + gripper-open scalar,
then converts/scales them into LIBERO raw OSC action.
```

This is the highest-risk rollout difference. If the checkpoint was trained/evaluated according to GT semantics, the current project is conditioning the model on the wrong proprio slots and reading actions from the wrong output slots. That alone can make a mechanically valid rollout remain at 0/10.

The second high-risk finding is image history handling. GT updates image history every environment step and uses the two most recent frames at each re-inference. Current runtime only updates `RDTLiberoObsProcessor` history when a new action chunk is generated, so its "previous" frame is separated by the action chunk horizon, not the previous environment step. On the first chunk, current runtime also supplies background/None for the previous frame, while GT duplicates the initial frame into both history slots.

The third high-risk finding is action postprocessing. GT extracts the 7 output action dimensions directly from the RDT unified action vector and only binarizes the gripper. Current project interprets RDT outputs as position deltas and 6D rotations, divides by OSC scales, converts 6D rotation to rotvec, clips, and then binarizes gripper. This is incompatible with GT evaluation behavior.

No source code was modified during this analysis. The only file written is this Markdown report.

## 2. GT Evaluation Pipeline Summary

Primary GT files inspected:

```text
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/libero_rdt_eval.py
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/libero_rdt_eval_with_eef_tracking.py
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/libero_rdt_model.py
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/eval_full_checkpoints_auto.sh
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/config/eval_config.yaml
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/config/eval_config_with_eef.yaml
third_party/Libero_RDT/RDT_libero_finetune/eval_fast/rdt_policy.py
third_party/Libero_RDT/RDT_libero_finetune/eval_fast/eval_rdt_libero.py
```

GT environment setup:

```text
benchmark_dict = get_benchmark_dict()
task_suite = benchmark_dict[dataset_name]()
task = task_suite.get_task(task_id)
bddl_file = get_libero_path("bddl_files") / task.problem_folder / task.bddl_file
env = SubprocVectorEnv([lambda: OffScreenRenderEnv(bddl_file_name=bddl_file,
                                                   camera_heights=128,
                                                   camera_widths=128)
                        for _ in range(num_traj)])
env.seed(seed)
env.reset()
obs = env.set_init_state(init_states_batch)
```

Evidence:

```text
libero_rdt_eval.py:240-280
libero_rdt_eval_with_eef_tracking.py:847-887
```

GT task/init-state behavior:

```text
libero_rdt_eval.py:
  indices = np.zeros(env_num, dtype=int)

libero_rdt_eval_with_eef_tracking.py:
  indices = np.arange(env_num) % num_init_states
```

The auto-eval script calls `libero_rdt_eval_with_eef_tracking.py`, so the practical GT batch evaluation uses init states `0..num_traj-1` modulo available init states.

Evidence:

```text
eval_full_checkpoints_auto.sh:241-250
libero_rdt_eval.py:277-280
libero_rdt_eval_with_eef_tracking.py:884-887
```

GT rollout length and no-op settle:

```text
MAX_EPISODE_STEPS = 720
for _ in range(5):
    env.step(np.zeros((env_num, 7), dtype=np.float32))
```

Evidence:

```text
libero_rdt_eval.py:283-311
libero_rdt_eval_with_eef_tracking.py:890-930
```

Important nuance: GT captures the first observation/history before the 5 no-op settle and does not refresh the history immediately after the settle.

GT observation construction:

```text
agent image key: agentview_image
wrist image key: robot0_eye_in_hand_image
image history length: 2
camera order per history frame: agentview, wrist, None
state source: robot0_joint_pos + robot0_gripper_qpos
state shape before RDT formatting: 9
```

Evidence:

```text
libero_rdt_eval.py:288-307, 341-351, 388-397
libero_rdt_eval_with_eef_tracking.py:895-917, 960-972, 1001-1010
```

GT state/action RDT slots:

```python
LIBERO_STATE_INDICES = [
    STATE_VEC_IDX_MAPPING[f"arm_joint_{i}_pos"] for i in range(7)
] + [
    STATE_VEC_IDX_MAPPING[f"gripper_joint_{i}_pos"] for i in range(2)
]

LIBERO_ACTION_INDICES = [
    STATE_VEC_IDX_MAPPING["eef_vel_x"],
    STATE_VEC_IDX_MAPPING["eef_vel_y"],
    STATE_VEC_IDX_MAPPING["eef_vel_z"],
    STATE_VEC_IDX_MAPPING["eef_angular_vel_roll"],
    STATE_VEC_IDX_MAPPING["eef_angular_vel_pitch"],
    STATE_VEC_IDX_MAPPING["eef_angular_vel_yaw"],
    STATE_VEC_IDX_MAPPING["gripper_open"]
]
```

Evidence:

```text
libero_rdt_model.py:20-35
eval_fast/rdt_policy.py:28-44
```

GT state formatting:

```text
Input joints shape: (B, N, 9)
Normalize last two gripper qpos values:
  (qpos - -0.04245) / (0.05185 - -0.04245)
Insert into LIBERO_STATE_INDICES
Build state_elem_mask only on LIBERO_STATE_INDICES
```

Evidence:

```text
libero_rdt_model.py:268-303
eval_fast/rdt_policy.py:263-283
```

GT action formatting:

```text
Extract action[:, :, LIBERO_ACTION_INDICES]
Binarize gripper:
  if raw gripper < 0 -> -1
  else               -> +1
Return 7D action directly to env.step()
```

Evidence:

```text
libero_rdt_model.py:305-317
libero_rdt_eval.py:368-373
libero_rdt_eval_with_eef_tracking.py:982-987
eval_fast/rdt_policy.py:285-296
```

GT model inference:

```text
config: configs/base.yaml
dtype: torch.bfloat16
text encoder: google/t5-v1_1-xxl or configured local path
vision encoder: google/siglip-so400m-patch14-384
control_frequency: 20
action_chunk_size: 64
num_inference_timesteps: 5
exec_horizon: 8 in config
```

Evidence:

```text
libero_rdt_eval_with_eef_tracking.py:1203-1217
libero_rdt_model.py:80-96, 384-402
configs/base.yaml:1-71
libero_eval/config/eval_config_with_eef.yaml:44-74
```

GT language:

```text
task_name = basename(bddl_file).replace(".bddl", "")
instruction = extract_instruction_from_task_name(task_name)
If outs/libero_embeddings/{dataset_name}/{task_name}.pt exists, load it.
Otherwise encode instruction live with T5.
```

Evidence:

```text
libero_rdt_eval.py:180-218, 250-257
libero_rdt_eval_with_eef_tracking.py:199-237, 857-864
```

GT success metric:

```text
The vector-env done value marks success/termination.
dones[i] = True when done[i].
num_success = sum(dones).
```

Evidence:

```text
libero_rdt_eval.py:399-409
libero_rdt_eval_with_eef_tracking.py:1021-1031
```

## 3. My Evaluation Pipeline Summary

Primary current project files inspected:

```text
main.py
configs/config.yaml
configs/policy.yaml
configs/backend/libero.yaml
core/rdt_policy_steer.py
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
core/env_adapters/libero_adapter.py
```

Current entrypoint:

```text
main.py -> Main.__init__ -> RDTSteer.from_pretrained(...)
main.py -> Main.run -> adapter.reset(...)
main.py -> Main._run_episode -> policy.select_action(...)
main.py -> adapter.step(...)
```

Evidence:

```text
main.py:147-180, 201-208, 499-564, 573-743
```

Current default RDT policy config:

```yaml
policy:
  type: rdt
  rdt:
    pretrained_path: /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000
    weight_variant: ema
    action_chunk_horizon: 8
    control_frequency: 20
    undo_libero_preprocessor_flip: true
```

Evidence:

```text
configs/policy.yaml:29-43
```

Current default LIBERO config:

```yaml
suite_name: libero_object
camera_name: agentview_image, robot0_eye_in_hand_image
observation_width: 128
observation_height: 128
num_steps_wait: 5
max_episode_steps: 600
task_ids_filter: null
```

Evidence:

```text
configs/backend/libero.yaml:14-30
```

Current environment setup:

```text
create_libero_envs(...) creates one LiberoEnv per selected task.
Each LiberoEnv is built with episode_index=0.
LiberoAdapter cycles one episode per task when episode_num == number of tasks.
```

Evidence:

```text
core/env_adapters/libero_adapter.py:771-813, 816-842, 1595-1625
```

Current raw LIBERO env wrapper:

```text
OffScreenRenderEnv(bddl_file_name=..., camera_heights=..., camera_widths=..., camera_depths=True)
reset()
set_init_state(self._init_states[self._init_state_id])
step no-op num_steps_wait times
```

Evidence:

```text
core/env_adapters/libero_adapter.py:613-621, 673-687
```

Current observation processing:

```text
LiberoEnv._format_raw_obs:
  raw HWC uint8 images -> BCHW float [0,1]
  stores robot_state with eef, gripper, joints

LiberoProcessorStep:
  flips images over H and W
  converts robot_state to observation.state = eef_pos + eef_axisangle + gripper_qpos
  removes observation.robot_state

RDTLiberoObsProcessor:
  reads observation.images.image / image2
  optionally flips image back
  builds state_128 from observation.state:
    state_128[30:33] = eef_pos
    state_128[33:39] = rotvec_to_ortho6d(axis_angle)
    state_128[10] = gripper_open
```

Evidence:

```text
core/env_adapters/libero_adapter.py:637-671, 76-96, 925-1001
core/rdt_libero_obs_processor.py:66-92, 94-131
```

Current action conversion:

```text
LIBERO_RDT_INDICES = [30,31,32,33,34,35,36,37,38,10]
RDT slots 30:33 divided by OSC_POS_SCALE [0.05,0.05,0.05]
RDT slots 33:39 converted from ortho6D to rotvec, divided by OSC_ROT_SCALE [0.5,0.5,0.5]
raw[:6] clipped to [-1,1]
gripper-open scalar converted to LIBERO raw gripper
```

Evidence:

```text
core/rdt_libero_action_converter.py:6-13, 83-111
```

Current unguided denoising:

```text
select_action(...) processes observation only when generate_new_chunk is True.
_predict_unguided(...) samples B particles in full 128D space.
_postprocess_actions(...) decodes only particle 0 to (1, H, 7).
```

Evidence:

```text
core/rdt_policy_steer.py:849-891, 895-929, 933-946
main.py:617-669, 723-729
```

Current success metric:

```text
LiberoEnv.step:
  is_success = self._env.check_success()
  terminated = done or is_success

LiberoAdapter.step:
  truncated = self.episode_step >= current_env._max_episode_steps

Main._run_episode:
  if terminated or truncated:
    is_success = info.get("success", False)
    if is_success: success_count += 1
```

Evidence:

```text
core/env_adapters/libero_adapter.py:689-717, 1565-1593
main.py:732-743
```

## 4. Difference Table

| Area | GT behavior | My behavior | Evidence/file paths | Risk level | Why it may cause 0/10 |
|---|---|---|---|---|---|
| RDT proprio/state source | Uses `robot0_joint_pos` plus `robot0_gripper_qpos`, total 9 values. | Uses `observation.state` built from EEF position, EEF axis-angle, gripper qpos, then maps to EEF pose slots. | GT: `libero_rdt_eval.py:304-307`, `libero_rdt_model.py:20-24`, `268-303`; Mine: `libero_adapter.py:76-96`, `rdt_libero_obs_processor.py:113-131`. | High | The model is conditioned on different physical variables and different RDT slots. Wrong proprio conditioning can make every action chunk off-distribution. |
| RDT state active indices | `arm_joint_0..6` and `gripper_joint_0..1`, i.e. indices `[0..6,10,11]`. | `[30,31,32,33,34,35,36,37,38,10]`, i.e. EEF pose/6D rotation plus one gripper scalar. | GT: `libero_rdt_model.py:20-24`; Mine: `rdt_libero_action_converter.py:6-10`, `rdt_libero_obs_processor.py:125-130`. | High | The RDT state mask tells the model a different embodiment/state schema than GT. This is a direct semantic mismatch. |
| RDT action active indices | `eef_vel_x/y/z`, `eef_angular_vel_roll/pitch/yaw`, `gripper_open`, i.e. indices `[39,40,41,42,43,44,10]`. | Reads `[30:39]` pose/rotation slots and gripper slot `10`. | GT: `libero_rdt_model.py:26-35`; Mine: `rdt_libero_action_converter.py:6-13`, `83-111`. | High | The runtime may ignore the actual learned action outputs and instead decode unrelated slots. This alone can produce near-random or saturated OSC commands. |
| Action representation | GT action is 7D normalized OSC command directly extracted from action slots; only gripper is binarized. | Converts pose-like RDT slots to raw actions by dividing by `[0.05,0.05,0.05]`, converting 6D rotation to rotvec, dividing by `[0.5,0.5,0.5]`, and clipping. | GT: `libero_rdt_model.py:305-317`, `libero_rdt_eval.py:368-373`; Mine: `rdt_libero_action_converter.py:83-94`. | High | GT treats action slots as controller command values. Current code treats them as metric deltas/rotation representations. This can yield huge clipping or near-zero actions unrelated to GT outputs. |
| Action mask passed to RDT | Mask is active only on action indices `[39,40,41,42,43,44,10]`. | Mask is active on state mask from current EEF pose slots `[30..38,10]` and reused as action mask. | GT: `libero_rdt_model.py:386-400`; Mine: `rdt_policy_steer.py:363-411`, `928-929`. | High | Even if the denoising loop is numerically correct, it asks the model to denoise the wrong output dimensions. |
| Image history update frequency | `agentview_windows` and `eye_in_hand_windows` are updated after every `env.step`; at inference they contain the last two env-step observations. | `RDTLiberoObsProcessor` updates its previous frame only when `generate_new_chunk=True`; with horizon 8, previous frame is previous chunk's observation, not previous env step. | GT: `libero_rdt_eval.py:385-397`; Mine: `main.py:617-729`, `rdt_libero_obs_processor.py:72-78`. | High | RDT was trained/evaluated with adjacent two-frame history. Chunk-spaced history changes temporal conditioning and may break motion inference. |
| First image history | GT fills both history frames with the initial image before rollout. | First chunk has previous image `None`, which becomes SigLIP mean background, and current image in the second history slot. | GT: `libero_rdt_eval.py:296-303`; Mine: `rdt_libero_obs_processor.py:57-78`, `rdt_policy_steer.py:315-331`. | Medium | First action chunk can be important for task setup. Missing previous frame is off-distribution relative to GT. |
| Observation after reset/no-op settle | GT obtains obs from `set_init_state`, initializes history/proprio, then performs 5 no-op steps without refreshing history before first policy call. | Current wrapper performs no-op settle inside `reset()` and returns the post-settle observation to policy. | GT: `libero_rdt_eval.py:280-311`; Mine: `libero_adapter.py:673-687`. | Medium | This is a real difference from GT. It may or may not help; under "GT is correct", it is an unverified distribution shift. |
| Image tensor orientation | GT uses raw `agentview_image` / `robot0_eye_in_hand_image` arrays from LIBERO. | Current adapter converts to tensor, `LiberoProcessorStep` flips H and W, then RDT processor flips back if `undo_libero_preprocessor_flip=true`. | GT: `libero_rdt_eval.py:297-298`; Mine: `libero_adapter.py:80-85`, `rdt_libero_obs_processor.py:107-111`, `configs/policy.yaml:41`. | Medium | If the double flip is not exactly equivalent for all paths, the model sees rotated/mirrored images. The config intends to undo it, but this needs direct pixel comparison against GT raw obs. |
| Image resolution into env | GT creates env at 128x128. | Current config now uses 128x128, but prior 0/10 run `2026-05-25_12-53-58` used 256x256. | GT: `libero_rdt_eval.py:265-269`; Mine: `configs/backend/libero.yaml:19-20`; observed: `outputs/libero/2026-05-25_12-53-58/.hydra/config.yaml`. | Low/Medium | Current latest run aligns at 128, so this is not the strongest current root cause. Prior 256 runs were a distribution shift. |
| Environment vectorization | GT evaluates all trajectories for one task in one `SubprocVectorEnv`. | Current creates one env per selected task and runs episodes serially, cycling tasks. | GT: `libero_rdt_eval.py:263-273`; Mine: `libero_adapter.py:771-842`, `main.py:505-548`. | Low | Different structure should not change single rollout semantics if resets/actions match. It can hide per-task init-state differences. |
| Init-state coverage | GT `with_eef_tracking` uses `np.arange(env_num) % num_init_states`. | Current every `LiberoEnv` is constructed with `episode_index=0`, so each task uses init state 0 for its episode. | GT: `libero_rdt_eval_with_eef_tracking.py:884-887`; Mine: `libero_adapter.py:794-808`, `515-518`. | Medium | A 10-episode run in current project is one episode per task, all at init state 0. GT standard eval samples several init states per task. This can skew success but probably does not alone explain 0/10. |
| Max episode length | GT uses 720 steps. | Current backend uses 600 steps; main has `main.max_episode_steps=240` but LIBERO truncation is controlled by `LiberoEnv._max_episode_steps`. | GT: `libero_rdt_eval.py:283`; Mine: `configs/backend/libero.yaml:25`, `libero_adapter.py:520-524`, `1585-1587`. | Medium | Some tasks may need more than 600 steps with a weak policy. Not likely to explain all failures if behavior is already wrong. |
| Checkpoint weight variant | GT directory loader prioritizes `ema/pytorch_model.bin`, then root `pytorch_model.bin`, then root `.pt`, then root `.safetensors`. For the current checkpoint layout there is `ema/model.safetensors` and root `pytorch_model.bin`; GT would not select `ema/model.safetensors`. | Current config sets `weight_variant: ema`; loader searches `checkpoint/ema` and can load `ema/model.safetensors`. | GT: `libero_rdt_model.py:184-230`; Mine: `configs/policy.yaml:33-39`, `rdt_policy_steer.py:86-96`, `552-575`; checkpoint listing under `/mnt/data/rdt_checkpoints/.../checkpoint-98000`. | Medium/High | Under GT-as-correct, current may evaluate different weights from GT. If EMA safetensors are stale or otherwise not the intended eval weights, success can collapse. |
| Model wrapper used | GT uses `libero_eval/libero_rdt_model.py`. | Current imports `scripts.maniskill_model.create_model` from `third_party/rdt`, then bypasses many ManiSkill methods with custom `encode_inputs`. | GT: `libero_rdt_model.py`; Mine: `rdt_policy_steer.py:543-546`, `714-731`; third-party `scripts/maniskill_model.py`. | Medium | Architecture may match, but using a ManiSkill-named wrapper is risky. The current custom path avoids some ManiSkill state/action code, but checkpoint loading behavior and wrapper assumptions differ from GT. |
| Sampling batch / particles | GT samples one trajectory per vector env. | Current uses `sample_batch_size=20` even unguided, expands conditioning, then postprocesses only particle 0. | GT: `libero_rdt_model.py:392-403`; Mine: `configs/config.yaml:40`, `rdt_policy_steer.py:874-889`, `933-946`. | Low/Medium | Without guidance, particle 0 is distributionally valid, but RNG sequence and memory/dtype behavior differ. Unlikely alone to cause 0/10. |
| Language source | GT extracts instruction from BDDL filename or loads precomputed embedding by task name. | Current uses `task.language` from the LIBERO benchmark adapter and live T5 encoding. For checked `libero_object` tasks, task language matches BDDL extraction. | GT: `libero_rdt_eval.py:180-218`; Mine: `libero_adapter.py:595-612`, `925-943`, `rdt_policy_steer.py:786-807`; local check showed task 0-2 strings match. | Low | Standard LIBERO language likely matches. Still worth comparing all task strings and embedding shapes. |
| Success detection | GT counts `done[i]`. | Current uses `check_success()` and `done`, then main increments only on `info["success"]`. | GT: `libero_rdt_eval.py:399-409`; Mine: `libero_adapter.py:695-717`, `main.py:732-743`. | Low | Current success detection is at least as explicit as GT. Unlikely to explain false 0/10 if videos show failures. |
| Video/logging | GT video saving optional and uses `VideoWriter.append_vector_obs`. | Current always overlays status and records VLM camera frames through `TrajectoryVideoRecorder`. | GT: `libero_rdt_eval.py:329-383`; Mine: `main.py:671-722`, `739-740`. | Low | Video path should not affect control unless rendering overhead or frame extraction mutates env, which was not observed. |

## 5. Ranked Hypotheses for the 0/10 Rollout Failure

### Hypothesis 1: Current runtime reads/writes the wrong RDT state/action slots

This is the strongest hypothesis.

GT explicitly uses joint-state conditioning indices `[0..6,10,11]` and action output indices `[39..44,10]`. Current runtime uses EEF pose/6D rotation indices `[30..38,10]` for both state and action conversion. This means the policy is not being evaluated with GT semantics even if shapes pass.

Why it explains 0/10:

```text
The model can produce valid tensors, but the control loop executes actions decoded
from unrelated dimensions. The env sees normalized OSC commands, but those commands
are not the ones the GT model intended.
```

Expected symptom:

```text
Actions are near-zero, saturated, or directionally incoherent despite no shape errors.
Videos show mechanical movement but no task completion.
```

This aligns with existing action probe symptoms from earlier debugging, where decoded actions showed saturation in some dimensions and tiny values in others.

### Hypothesis 2: Current action converter incorrectly transforms GT action outputs

GT action postprocessing is simple extraction plus gripper thresholding. Current converter performs metric scaling and 6D-rotation decoding. If GT action slots are already OSC commands, this extra conversion corrupts commands.

Why it explains 0/10:

```text
Even if the model output were good, converting the wrong representation through
position/rotation scaling produces incorrect env.step actions.
```

### Hypothesis 3: Image history in current runtime is chunk-spaced rather than step-spaced

GT updates the two-frame history at every `env.step`, then reuses the latest adjacent frames at re-inference. Current `RDTLiberoObsProcessor` only processes observations when a new chunk is requested, so history frames are separated by 8 environment steps.

Why it explains 0/10:

```text
The model was evaluated with short-term visual history. Feeding long-gap history
or background for the previous frame changes temporal cues and can degrade action
prediction, especially near grasp/contact.
```

This is probably secondary to the state/action slot mismatch, but it is still a serious rollout difference.

### Hypothesis 4: Current checkpoint weight variant differs from GT expected loading

Current runtime uses `weight_variant: ema` and can load `ema/model.safetensors`. GT's directory loader does not select `ema/model.safetensors`; with the current checkpoint layout it would likely select root `pytorch_model.bin`.

Why it explains 0/10:

```text
If root weights and EMA weights differ materially, current runtime may be evaluating
a different checkpoint than GT would evaluate. If EMA is stale or incompatible,
performance could collapse while shape checks still pass.
```

This needs a direct one-sample action comparison between current loader and GT loader.

### Hypothesis 5: Init-state and episode-horizon differences reduce measured success

Current 10-episode run uses one episode per task and init state 0 for each task. GT batch evaluation uses several init states per task and 720 max steps. Current max steps are 600.

Why it may contribute:

```text
A weak policy may need more steps or may succeed only on some init states.
```

Why it is not the top hypothesis:

```text
Using init state 0 and 600 steps should not normally turn a correct policy into
0/10 across all tasks if the action semantics are correct.
```

## 6. Top 5 Most Suspicious Rollout/Evaluation Differences

1. **Wrong RDT state slots in current observation processor**

   GT uses joint positions and two gripper qpos values at joint/gripper indices. Current code uses EEF pose and 6D rotation indices. This should be treated as a blocking semantic mismatch.

2. **Wrong RDT action slots in current action converter**

   GT extracts EEF velocity/action slots `[39,40,41,42,43,44,10]`. Current converter reads `[30..38,10]` and never reads the GT action velocity slots.

3. **Extra action scaling/rotation conversion**

   GT sends extracted 7D actions directly to `env.step()`. Current runtime divides by controller scales, converts 6D rotation to rotvec, clips, and then sends to env. This is incompatible with GT output semantics.

4. **Image history only updates at action-chunk boundaries**

   GT image windows update every env step. Current history updates only every chunk, creating an 8-step gap with `action_chunk_horizon=8`. First previous frame is background/None instead of duplicated initial image.

5. **Different checkpoint weight variant selection**

   Current uses `ema/model.safetensors`; GT's loader would not select that path for the current checkpoint layout and would likely load root `pytorch_model.bin`. The selected weights should be verified by comparing first action chunks under both loaders.

## 7. Concrete Next Verification Probes or Commands

These are proposed probes only. They were not run as fixes and do not require code modification if implemented as temporary one-off commands or separate analysis scripts.

### Probe 1: Print GT vs current active state/action indices

Purpose: fail fast on state/action slot mismatch.

```bash
python - <<'PY'
import sys
sys.path.insert(0, "third_party/Libero_RDT/RDT_libero_finetune")
from libero_eval.libero_rdt_model import LIBERO_STATE_INDICES, LIBERO_ACTION_INDICES
from core.rdt_libero_action_converter import LIBERO_RDT_INDICES, ACTIVE_INDICES_SORTED

print("GT state indices:", LIBERO_STATE_INDICES)
print("GT action indices:", LIBERO_ACTION_INDICES)
print("current LIBERO_RDT_INDICES:", LIBERO_RDT_INDICES)
print("current ACTIVE_INDICES_SORTED:", ACTIVE_INDICES_SORTED)
PY
```

Expected result if hypothesis 1 is correct:

```text
GT state indices should be [0,1,2,3,4,5,6,10,11]
GT action indices should be [39,40,41,42,43,44,10]
current indices should differ.
```

### Probe 2: One observation, GT formatting vs current formatting

Purpose: compare the exact 128D state tensor and mask from the same online LIBERO raw observation.

Suggested checks:

```text
1. Reset one LIBERO task with the same BDDL and init state.
2. Extract raw obs keys:
   robot0_joint_pos
   robot0_gripper_qpos
   robot0_eef_pos
   robot0_eef_quat
3. Format state using GT `RoboticDiffusionTransformerModel._format_joint_to_state`.
4. Format state using current `RDTLiberoObsProcessor`.
5. Print active indices, nonzero values, mask values.
```

Expected result if hypothesis 1 is correct:

```text
The two 128D states will have different active masks and values.
```

### Probe 3: One checkpoint, GT action chunk vs current action chunk on identical inputs

Purpose: isolate model/adapter differences without running a long benchmark.

Suggested checks:

```text
1. Load the same checkpoint with GT `libero_rdt_model.create_model`.
2. Load the same checkpoint with current `RDTSteer.from_pretrained`.
3. Use the same task, same raw observation, same text embedding if possible.
4. Fix torch seed immediately before sampling.
5. Compare:
   GT trajectory[:, :, [39,40,41,42,43,44,10]]
   current raw 128D trajectory before postprocess
   current decoded 7D env actions
```

Expected result:

```text
If current state/action slots are wrong, current decoded 7D actions will not match
GT direct 7D actions even when the underlying model weights/config are the same.
```

### Probe 4: Evaluate current checkpoint with GT eval script on one task

Purpose: separate checkpoint quality from current runtime bugs.

This is the most decisive runtime comparison after the slot mismatch is inspected.

Example command shape:

```bash
cd third_party/Libero_RDT/RDT_libero_finetune
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  libero_eval/libero_rdt_eval_with_eef_tracking.py \
  --pretrained-path /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000 \
  --config libero_eval/config/eval_config_with_eef.yaml \
  --dataset-name libero_object \
  --task-ids 0 \
  --num-traj 1 \
  --seed 20241201 \
  --eef-save-dir outs/eef_probe
```

Notes:

```text
This may need local path fixes for text/vision encoders and LIBERO repo path.
It should be a tiny 1-task/1-trajectory probe, not a full benchmark.
```

Interpretation:

```text
GT succeeds or produces plausible behavior: current rollout adapter is likely root cause.
GT also fails with same bad motion: checkpoint/fine-tuning quality remains likely.
```

### Probe 5: Weight variant comparison

Purpose: determine whether current `ema/model.safetensors` and GT-selected root `pytorch_model.bin` produce materially different action chunks.

Suggested checks:

```text
1. Load current checkpoint with weight_variant=ema.
2. Load current checkpoint with weight_variant omitted or root `pytorch_model.bin`.
3. Same observation, same seed.
4. Compare raw 128D output stats and decoded 7D action stats.
```

Expected:

```text
If action chunks differ substantially, the current eval result is not comparable to GT eval.
```

### Probe 6: Step-spaced vs chunk-spaced image history

Purpose: quantify current temporal-history mismatch.

Suggested checks:

```text
1. During one rollout, log frame IDs or image hashes for the two RDT history slots.
2. GT expected at each re-inference after first chunk:
   history slot 0 = previous env step or second-latest env step
   history slot 1 = latest env step
3. Current expected:
   history slot 0 = previous chunk inference observation
   history slot 1 = current chunk inference observation
```

Expected:

```text
Current frame gap should equal action_chunk_horizon, not 1.
```

### Probe 7: Full task string parity

Purpose: confirm language is not a hidden divergence.

```bash
python - <<'PY'
import os, sys
sys.path.insert(0, "third_party/libero")
from libero.libero import benchmark, get_libero_path

for suite_name in ["libero_object", "libero_goal", "libero_spatial", "libero_10"]:
    suite = benchmark.get_benchmark_dict()[suite_name]()
    print("==", suite_name)
    for tid in range(suite.get_num_tasks()):
        task = suite.get_task(tid)
        bddl = os.path.join(get_libero_path("bddl_files"), task.problem_folder, task.bddl_file)
        gt = os.path.basename(bddl).replace(".bddl", "").replace("_", " ")
        print(tid, gt == task.language, "|", gt, "|", task.language)
PY
```

Expected:

```text
For standard LIBERO suites, strings should match or differ only in known harmless ways.
```

### Probe 8: Success detection parity

Purpose: rule out false 0/10 reporting.

Suggested checks:

```text
For each env.step, log:
  raw done
  env.check_success()
  adapter terminated
  adapter truncated
  info["success"]
Compare against GT on same task/init/action replay if possible.
```

Expected:

```text
If check_success becomes true but results still report failure, success detection is broken.
Existing evidence points more toward actual behavioral failure than metric failure.
```

## 8. No Code Modified Statement

No source code was modified during this rollout/evaluation analysis.

The only file created by this task is:

```text
docs/docs/02_analysis/rdt_intergration/2026-05-26-rdt-libero-rollout-gt-diff-analysis.md
```

No files under these source directories were edited:

```text
core/
configs/
third_party/rdt/
third_party/libero/
third_party/Libero_RDT/
```

Repository status already contained pre-existing modified/untracked files before this report was written; those were not reverted or changed as part of this task.

