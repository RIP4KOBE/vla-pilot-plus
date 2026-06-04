---
archived_on: 2026-06-04
source_worktree: .worktrees/feat/rdt-libero-dataset_finetune
source_branch: feat/rdt-libero-object-ckpt
source_commit: 1be4afbf17ea
source_path: .worktrees/feat/rdt-libero-dataset_finetune/third_party/rdt/agent/libero_dataset_semantics_analysis.md
summary: LIBERO Dataset Semantics Analysis
duplicate_sources: []
---

# LIBERO Dataset Semantics Analysis

This document records the confirmed semantics of the LIBERO HDF5 demonstrations used for RDT/VLA fine-tuning. It combines three evidence sources:

1. Direct inspection of a local HDF5 file under `/mnt/data/hf_cache/hub`.
2. Local official LIBERO source code under `third_party/libero`.
3. The Hugging Face dataset repo page for `yifengzhu-hf/LIBERO-datasets`.

The goal is to provide deterministic evidence for implementing `libero_vla_dataset.py` and adapting existing HDF5 dataset loaders. Claims below distinguish direct HDF5 evidence from LIBERO source-code evidence and external HF repository evidence.

## 1. Inspected Dataset File

The main inspected file was:

```text
/mnt/data/hf_cache/hub/libero_10/KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it_demo.hdf5
```

Basic facts:

```text
file size: 1,319,613,988 bytes, about 1.229 GiB
category: libero_10
task name inferred from filename:
  KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it
```

The HDF5 file itself stores the language instruction in `data.attrs["problem_info"]`:

```json
{
  "problem_name": "libero_kitchen_tabletop_manipulation",
  "domain_name": "robosuite",
  "language_instruction": "turn on the stove and put the moka pot on it"
}
```

So for this file, language does not need to be inferred from the filename. Filename parsing should only be a fallback.

## 2. Hugging Face Repository Evidence

The official HF repo page `https://huggingface.co/datasets/yifengzhu-hf/LIBERO-datasets` confirms the high-level dataset organization:

```text
libero_object/
libero_spatial/
libero_goal/
libero_90/
libero_10/
```

It also states that demonstrations of each task are stored in an HDF5 file. The HF page is useful for repository layout and download provenance, but it does not provide field-level HDF5 semantics. Field semantics should be taken from direct HDF5 inspection and the local LIBERO source.

Local LIBERO download code confirms the same HF repo id:

```text
HF_REPO_ID = "yifengzhu-hf/LIBERO-datasets"
```

in:

```text
third_party/libero/libero/libero/utils/download_utils.py
```

The same file checks for these local dataset directories:

```text
libero_object
libero_goal
libero_spatial
libero_10
libero_90
```

with 10 task files for most suites and 90 task files for `libero_90`.

## 3. HDF5 Tree Structure

The inspected HDF5 has a top-level `data` group and no root attributes.

`data` group attributes include:

```text
bddl_file_name
env_args
env_name
macros_image_convention
num_demos
problem_info
tag
total
```

Observed values:

```text
data.attrs["num_demos"] = 50
data.attrs["total"] = 13298
data.attrs["env_name"] = "Libero_Kitchen_Tabletop_Manipulation"
data.attrs["tag"] = "libero-v1"
data.attrs["macros_image_convention"] = "opengl"
```

Parsed `data.attrs["env_args"]` includes:

```text
robots = ["Panda"]
controller_configs.type = "OSC_POSE"
controller_configs.control_delta = true
controller_configs.input_min = -1
controller_configs.input_max = 1
controller_configs.output_min = [-0.05, -0.05, -0.05, -0.5, -0.5, -0.5]
controller_configs.output_max = [0.05, 0.05, 0.05, 0.5, 0.5, 0.5]
camera_names = ["robot0_eye_in_hand", "agentview"]
camera_heights = 128
camera_widths = 128
control_freq = 20
use_camera_obs = true
camera_depths = false
reward_shaping = true
```

Each demonstration is stored under:

```text
data/demo_0
data/demo_1
...
data/demo_49
```

Each demo has an `obs` subgroup and the same dataset schema.

Per-demo datasets:

| Path Pattern | Shape | Dtype |
|---|---:|---|
| `data/demo_i/actions` | `(T, 7)` | `float64` |
| `data/demo_i/dones` | `(T,)` | `uint8` |
| `data/demo_i/rewards` | `(T,)` | `uint8` |
| `data/demo_i/states` | `(T, 47)` | `float64` |
| `data/demo_i/robot_states` | `(T, 9)` | `float64` |
| `data/demo_i/obs/agentview_rgb` | `(T, 128, 128, 3)` | `uint8` |
| `data/demo_i/obs/eye_in_hand_rgb` | `(T, 128, 128, 3)` | `uint8` |
| `data/demo_i/obs/ee_pos` | `(T, 3)` | `float64` |
| `data/demo_i/obs/ee_ori` | `(T, 3)` | `float64` |
| `data/demo_i/obs/ee_states` | `(T, 6)` | `float64` |
| `data/demo_i/obs/gripper_states` | `(T, 2)` | `float64` |
| `data/demo_i/obs/joint_states` | `(T, 7)` | `float64` |

Per-demo attributes include:

```text
init_state
model_file
num_samples
```

For the inspected file, `demo_0.attrs["num_samples"] = 272`, and `demo_0.attrs["init_state"]` has shape `(47,)`.

## 4. Episode Organization

Direct HDF5 evidence:

```text
number of demo groups: 50
demo keys: demo_0 ... demo_49
sum of action lengths: 13298
data.attrs["total"]: 13298
```

The trajectory length is the first dimension of `actions` and all observation datasets. It can be read from:

```text
data/demo_i/actions.shape[0]
data/demo_i.attrs["num_samples"]
```

The inspected file has variable-length demonstrations:

```text
min length: 219
max length: 340
mean length: 265.96
std: 27.65
```

For `demo_0`, the following fields all have length 272 and are timestep-aligned:

```text
actions
states
robot_states
rewards
dones
obs/agentview_rgb
obs/eye_in_hand_rgb
obs/ee_pos
obs/ee_ori
obs/ee_states
obs/gripper_states
obs/joint_states
```

LIBERO source evidence:

`scripts/check_dataset_integrity.py` iterates over `demo_file["data"].keys()`, counts demo groups, expects 50 demos per task file, and reads trajectory lengths from:

```python
demo_file["data/{}/actions".format(demo_name)].shape[0]
```

## 5. Final Dataset Generation Pipeline

The final learning HDF5 is generated by:

```text
third_party/libero/scripts/create_dataset.py
```

This script reads raw demo states/actions, replays them in the LIBERO/robosuite environment, records observations, and writes the final learning dataset.

Important source-confirmed behavior:

1. It reads raw actions from:

```python
actions = np.array(f["data/{}/actions".format(ep)][()])
```

2. It skips the first `cap_index = 5` steps while recording final training observations.

3. It writes final actions after slicing by `valid_index`:

```python
actions = actions[valid_index]
ep_data_grp.create_dataset("actions", data=actions)
```

4. It writes final simulator states:

```python
states = states[valid_index]
ep_data_grp.create_dataset("states", data=states)
```

5. It writes final rewards and dones as sparse terminal flags:

```python
dones = np.zeros(len(actions)).astype(np.uint8)
dones[-1] = 1
rewards = np.zeros(len(actions)).astype(np.uint8)
rewards[-1] = 1
```

6. It writes per-demo metadata:

```python
ep_data_grp.attrs["num_samples"] = len(agentview_images)
ep_data_grp.attrs["model_file"] = model_xml
ep_data_grp.attrs["init_state"] = states[init_idx]
```

## 6. Observation Semantics

### RGB Images

Confirmed HDF5 evidence:

```text
data/demo_0/obs/agentview_rgb
shape: (272, 128, 128, 3)
dtype: uint8
sample min/max: 0 / 255
channel-last likely: true
```

```text
data/demo_0/obs/eye_in_hand_rgb
shape: (272, 128, 128, 3)
dtype: uint8
sample min/max: 2 / 240
channel-last likely: true
```

Source-confirmed mapping in `scripts/create_dataset.py`:

```python
agentview_images.append(obs["agentview_image"])
eye_in_hand_images.append(obs["robot0_eye_in_hand_image"])

obs_grp.create_dataset("agentview_rgb", data=np.stack(agentview_images, axis=0))
obs_grp.create_dataset("eye_in_hand_rgb", data=np.stack(eye_in_hand_images, axis=0))
```

Source-confirmed mapping in `libero/configs/data/default.yaml`:

```yaml
obs:
  modality:
    rgb: ["agentview_rgb", "eye_in_hand_rgb"]

obs_key_mapping:
  agentview_rgb: agentview_image
  eye_in_hand_rgb: robot0_eye_in_hand_image
```

Semantics:

```text
agentview_rgb: external/static agent-view RGB camera
eye_in_hand_rgb: wrist / eye-in-hand RGB camera
```

`data.attrs["macros_image_convention"] = "opengl"` was observed. The images are HWC uint8. If visual orientation matters, verify with a saved frame before final training.

### Proprioception

Source-confirmed mapping in `scripts/create_dataset.py`:

```python
gripper_states.append(obs["robot0_gripper_qpos"])
joint_states.append(obs["robot0_joint_pos"])
ee_states.append(
    np.hstack(
        (
            obs["robot0_eef_pos"],
            T.quat2axisangle(obs["robot0_eef_quat"]),
        )
    )
)

obs_grp.create_dataset("gripper_states", data=np.stack(gripper_states, axis=0))
obs_grp.create_dataset("joint_states", data=np.stack(joint_states, axis=0))
obs_grp.create_dataset("ee_states", data=np.stack(ee_states, axis=0))
obs_grp.create_dataset("ee_pos", data=np.stack(ee_states, axis=0)[:, :3])
obs_grp.create_dataset("ee_ori", data=np.stack(ee_states, axis=0)[:, 3:])
```

Confirmed semantics:

| HDF5 Field | Source Observation | Shape | Semantics |
|---|---|---:|---|
| `obs/gripper_states` | `obs["robot0_gripper_qpos"]` | `(T, 2)` | Panda gripper finger qpos |
| `obs/joint_states` | `obs["robot0_joint_pos"]` | `(T, 7)` | Panda arm joint positions |
| `obs/ee_states` | `[robot0_eef_pos, quat2axisangle(robot0_eef_quat)]` | `(T, 6)` | EEF position plus axis-angle orientation |
| `obs/ee_pos` | `ee_states[:, :3]` | `(T, 3)` | EEF position |
| `obs/ee_ori` | `ee_states[:, 3:]` | `(T, 3)` | EEF orientation in axis-angle form |

Official LIBERO default training config uses:

```yaml
low_dim: ["gripper_states", "joint_states"]
use_ee: false
```

So the official BC baselines default to gripper and joint states, not EEF state. However, the final HDF5 includes EEF state, and RDT adaptation may use it if it maps cleanly to RDT's 128-dimensional unified vector.

### `robot_states`

Source-confirmed definition in `libero/envs/bddl_base_domain.py`:

```python
def get_robot_state_vector(self, obs):
    return np.concatenate(
        [obs["robot0_gripper_qpos"], obs["robot0_eef_pos"], obs["robot0_eef_quat"]]
    )
```

Therefore:

```text
robot_states shape: (T, 9)
robot_states layout:
  0:2  robot0_gripper_qpos
  2:5  robot0_eef_pos
  5:9  robot0_eef_quat
```

### `states`

Raw demo collection source describes `states` as flattened MuJoCo states:

```text
states (dataset) - flattened mujoco states
```

The final dataset keeps sliced simulator states as:

```python
states = states[valid_index]
ep_data_grp.create_dataset("states", data=states)
```

For the inspected file:

```text
states shape: (T, 47)
init_state shape: (47,)
```

This field is useful for replay/debugging and environment reset, but it is not the same as compact policy proprioception.

## 7. Action Semantics

Direct HDF5 evidence:

```text
actions shape: (T, 7)
dtype: float64
```

For `demo_0`, first three actions:

```text
[[ 0.       0.05625 -0.01875  0.       0.      -0.      -1.     ]
 [ 0.00268  0.07232 -0.01339  0.       0.      -0.      -1.     ]
 [ 0.       0.08304 -0.00804  0.       0.      -0.      -1.     ]]
```

Across all 13,298 transitions in the inspected file:

| Dim | Min | Max | Mean | Std |
|---:|---:|---:|---:|---:|
| 0 | -0.7741 | 0.9321 | 0.0393 | 0.2622 |
| 1 | -0.8866 | 0.8759 | 0.0566 | 0.3086 |
| 2 | -0.9375 | 0.9375 | -0.0919 | 0.3705 |
| 3 | -0.1479 | 0.2357 | 0.0124 | 0.0351 |
| 4 | -0.2336 | 0.2904 | -0.0058 | 0.0590 |
| 5 | -0.1104 | 0.3750 | 0.0634 | 0.1028 |
| 6 | -1.0 | 1.0 | -0.1781 | 0.9840 |

The final action dimension is binary in the inspected file:

```text
unique(action[:, 6]) = [-1.0, 1.0]
```

Source-confirmed controller metadata:

```text
controller_configs.type = "OSC_POSE"
controller_configs.control_delta = true
controller_configs.input_min = -1
controller_configs.input_max = 1
controller_configs.output_min = [-0.05, -0.05, -0.05, -0.5, -0.5, -0.5]
controller_configs.output_max = [0.05, 0.05, 0.05, 0.5, 0.5, 0.5]
```

Semantics conclusion:

```text
actions are normalized 7-dimensional robosuite OSC_POSE control actions.
```

High-confidence interpretation, based on LIBERO/robosuite controller metadata:

```text
action[0:3]  normalized delta position command
action[3:6]  normalized delta orientation command
action[6]    gripper command
```

The HDF5 dataset does not store per-dimension labels for `actions`, so the exact internal order and scaling should ultimately follow robosuite's `OSC_POSE` controller implementation. However, the metadata is strong enough to treat the action as normalized delta EEF pose plus gripper for RDT adaptation.

LIBERO dataset info script enforces action bounds:

```python
if (action_min < -1.0) or (action_max > 1.0):
    raise Exception("Dataset should have actions in [-1., 1.] ...")
```

## 8. Reward, Done, Success, Terminal

Direct HDF5 evidence for `demo_0`:

```text
rewards shape: (272,), dtype uint8
unique_counts: [(0, 271), (1, 1)]
nonzero_reward_idx: [271]

dones shape: (272,), dtype uint8
unique_counts: [(0, 271), (1, 1)]
done_idx: [271]
```

The same pattern was observed in sampled demos near the beginning and end of the file.

Source-confirmed final dataset generation:

```python
dones = np.zeros(len(actions)).astype(np.uint8)
dones[-1] = 1
rewards = np.zeros(len(actions)).astype(np.uint8)
rewards[-1] = 1
```

No `success`, `terminal`, `terminated`, or `truncated` datasets were observed in the inspected HDF5. For behavior cloning / RDT diffusion training, `rewards` and `dones` are mainly useful for episode boundary and debugging, not as the core training target.

## 9. Language Semantics

Language is parsed from the BDDL problem file.

Source-confirmed BDDL parser in `libero/envs/bddl_utils.py`:

```python
elif t == ":language":
    group.pop(0)
    language_instruction = group

return {
    "problem_name": problem_name,
    "domain_name": domain_name,
    "language_instruction": " ".join(language_instruction),
}
```

The final dataset generation script writes this metadata into:

```python
grp.attrs["problem_info"] = f["data"].attrs["problem_info"]
```

For the inspected file:

```text
data.attrs["problem_info"].language_instruction
  = "turn on the stove and put the moka pot on it"
```

Use this HDF5 attribute as the primary language source. Filename parsing is only a fallback.

## 10. Official LIBERO Training Read Path

LIBERO's official lifelong dataset wrapper uses robomimic `SequenceDataset`:

```python
dataset = SequenceDataset(
    hdf5_path=dataset_path,
    obs_keys=shape_meta["all_obs_keys"],
    dataset_keys=["actions"],
    load_next_obs=False,
    frame_stack=frame_stack,
    seq_length=seq_len,
    pad_frame_stack=True,
    pad_seq_length=True,
    get_pad_mask=False,
    hdf5_cache_mode=hdf5_cache_mode,
)
```

Default observation config:

```yaml
data_modality:
  - "image"
  - "proprio"
seq_len: 10
frame_stack: 1
use_eye_in_hand: true
use_gripper: true
use_joint: true
use_ee: false

obs:
  modality:
    rgb: ["agentview_rgb", "eye_in_hand_rgb"]
    depth: []
    low_dim: ["gripper_states", "joint_states"]
```

This confirms that the official baselines train on:

```text
images: agentview_rgb, eye_in_hand_rgb
low-dimensional proprio: gripper_states, joint_states
target: actions
```

RDT adaptation may additionally use `ee_pos` and `ee_ori` because their semantics are now source-confirmed.

## 11. RDT/VLA Mapping Recommendation

Recommended mapping for `libero_vla_dataset.py`:

| RDT/VLA Field | LIBERO HDF5 Source | Transform | Notes |
|---|---|---|---|
| `meta.dataset_name` | Dataset folder or configured suite name | string, e.g. `libero_10` | Must be registered in RDT config JSON files |
| `meta.instruction` | `json.loads(data.attrs["problem_info"])["language_instruction"]` | string | Primary language source |
| `meta.episode_id` | `demo_i` | string/int | Debug and reproducibility |
| `meta.step_id` | sampled timestep `t` | int | Index inside demo |
| `cam_high` | `data/demo_i/obs/agentview_rgb` | history slice, HWC uint8 | RDT external camera |
| `cam_right_wrist` | `data/demo_i/obs/eye_in_hand_rgb` | history slice, HWC uint8 | RDT wrist camera |
| `cam_left_wrist` | none | padded image | LIBERO has one wrist camera in this dataset |
| `cam_high_mask` | source availability | `(img_history_size,)` | Pad invalid history at episode start |
| `cam_right_wrist_mask` | source availability | `(img_history_size,)` | Pad invalid history at episode start |
| `cam_left_wrist_mask` | none | zeros | Missing camera |
| joint state | `obs/joint_states` | map to RDT right-arm joint slots | 7 Panda joints |
| gripper state | `obs/gripper_states` | map to RDT right gripper slot | May compress two finger qpos into one scalar |
| EEF pose | `obs/ee_pos`, `obs/ee_ori` | map to RDT right EEF slots if used | `ee_ori` is axis-angle |
| compact robot state | `robot_states` | optional, source-confirmed layout | `[gripper_qpos, eef_pos, eef_quat]` |
| simulator state | `states` | generally not policy input | replay/debug only |
| action chunk | `actions[t:t+action_chunk_size]` | map 7-d actions to RDT 128-d action vector | Do not cross demo boundary |
| `state_indicator` | active RDT dimensions | binary `(128,)` | Must match chosen state/action slots |
| `state_mean/std/norm` | computed over mapped active dimensions | arrays `(128,)` | Store in `dataset_stat.json` |
| `ctrl_freq` | `env_args.env_kwargs.control_freq` | numeric, observed 20 | Register in `dataset_control_freq.json` |
| reward/done | `rewards`, `dones` | optional debug/boundary check | Not needed for diffusion BC target |

For a single-arm Panda task, use RDT's right-arm portion of the 128-dimensional unified state/action vector. Keep inactive dimensions zero and mark only active dimensions in `state_indicator`.

Suggested active content:

```text
state:
  joint_states(7)
  gripper state
  optionally ee_pos(3) + ee_ori axis-angle(3)

action:
  actions[0:6] as normalized OSC_POSE delta EEF command
  actions[6] as gripper command
```

If using RDT's EEF action slots, ensure that the chosen RDT slot semantics align with normalized delta EEF actions rather than absolute EEF state.

## 12. Loader Changes Needed For LIBERO

An existing ManiSkill-style HDF5 loader should not assume ManiSkill field names or episode layout. LIBERO support requires:

1. File discovery:

```text
/mnt/data/hf_cache/hub/libero_*/*.hdf5
```

or a configurable LIBERO data root.

2. Demo traversal:

```text
for demo_key in h5["data"].keys():
    if demo_key.startswith("demo_"):
        ...
```

3. Episode length:

```text
T = h5[f"data/{demo_key}/actions"].shape[0]
```

or:

```text
T = h5[f"data/{demo_key}"].attrs["num_samples"]
```

4. Observation key mapping:

```text
agentview_rgb      -> primary/external RGB camera
eye_in_hand_rgb    -> wrist RGB camera
gripper_states     -> robot0_gripper_qpos
joint_states       -> robot0_joint_pos
ee_pos             -> robot0_eef_pos
ee_ori             -> quat2axisangle(robot0_eef_quat)
```

5. Image handling:

```text
HWC uint8, shape (T, 128, 128, 3)
```

Do not treat these as CHW arrays.

6. Language:

```text
json.loads(h5["data"].attrs["problem_info"])["language_instruction"]
```

7. Action chunk slicing:

```text
raw_action_chunk = actions[t : t + action_chunk_size]
```

Do not cross a `demo_i` boundary. Near the episode end, pad according to the RDT dataset contract and keep masks/statistics consistent.

8. Camera history:

RDT expects two history timesteps and three cameras. LIBERO provides two cameras. Fill the missing left-wrist camera with the existing RDT padding mechanism and set its mask to zero.

9. Normalization:

Compute statistics after mapping LIBERO fields into RDT's 128-dimensional vector, not on raw 7-d actions or raw 47-d simulator states alone.

10. Loss masking:

LIBERO will activate only a small subset of RDT's 128 action dimensions. If training quality is poor, audit `RDTRunner.compute_loss()` because the current RDT loss may compute unmasked MSE over all 128 dimensions.

## 13. Remaining Uncertainties

Resolved by local source:

```text
ee_ori is axis-angle, not unknown.
robot_states is [gripper_qpos, eef_pos, eef_quat], not unknown.
language is present in HDF5 problem_info, not filename-only.
```

Still worth validating before final training:

1. Visual orientation of `agentview_rgb` and `eye_in_hand_rgb` under the stored `opengl` convention.
2. Exact robosuite `OSC_POSE` internal action ordering and scaling if mapping actions to EEF-specific RDT slots.
3. Best conversion from two-finger `gripper_states` to a single RDT gripper scalar.
4. Whether to train RDT state condition from joint/gripper only, or include EEF state as well.
5. Whether to use masked action loss in RDT to avoid inactive 128-d dimensions diluting LIBERO's 7-d action signal.

## 14. Evidence Summary

The final, source-confirmed LIBERO learning dataset semantics are:

```text
One HDF5 file = one task.
Each file has data/demo_0 ... data/demo_49.
Each demo is a variable-length trajectory.
Each timestep has:
  actions: 7-d normalized OSC_POSE + gripper action
  images:
    agentview_rgb: HWC uint8 external RGB
    eye_in_hand_rgb: HWC uint8 wrist RGB
  proprio:
    gripper_states: robot0_gripper_qpos, 2-d
    joint_states: robot0_joint_pos, 7-d
    ee_states: [robot0_eef_pos, quat2axisangle(robot0_eef_quat)], 6-d
    ee_pos: first 3 dims of ee_states
    ee_ori: last 3 dims of ee_states
  robot_states:
    [robot0_gripper_qpos, robot0_eef_pos, robot0_eef_quat], 9-d
  states:
    flattened MuJoCo simulator state
  rewards/dones:
    zeros except final timestep equals 1
Task language:
  data.attrs["problem_info"].language_instruction
Control frequency:
  data.attrs["env_args"].env_kwargs.control_freq = 20
```

## 2026-05-23 RDT LIBERO Loader Smoke Result

`libero_10` loader, statistics generation, and short RDT fine-tuning were verified through the RDT HDF5 path. Training used `RDT_HDF5_BACKEND=libero`, `RDT_LIBERO_SUITES=libero_10`, and `--load_from_hdf5`. Verification was limited to dataset handling, statistics, and RDT fine-tuning; LIBERO benchmark rollout code was not touched.

Observed verification:

```text
loader tests: 10 passed
consumer smoke: consumer.states (2, 1, 128), consumer.actions (2, 64, 128), consumer.images (2, 6, 3, 384, 384)
one-step fine-tune: completed 1/1 step and saved ./checkpoints/rdt-libero-smoke
sampled fine-tune: completed 10/10 steps and logged overall_avg_sample_mse at sample steps 5 and 10
```
