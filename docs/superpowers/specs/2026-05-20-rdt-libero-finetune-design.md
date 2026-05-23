# RDT LIBERO Fine-Tuning Design

## Goal

Fine-tune RDT-1B on the downloaded LIBERO demonstrations, starting with:

```text
/mnt/data/hf_cache/hub/libero_object
```

The resulting checkpoint should be trainable through RDT's existing fine-tuning path and deployable in the local LIBERO benchmark adapter using native LIBERO 7D OSC actions:

```text
[x, y, z, roll, pitch, yaw, gripper]
```

This design is intentionally limited to the dataset, mapping, config, statistics, and smoke-test plan needed for the first RDT-LIBERO fine-tune. It does not implement the loader, change training code, or create the implementation plan.

## Evidence Base

This design uses the following local evidence sources:

```text
third_party/rdt/README.md
third_party/rdt/finetune.sh
third_party/rdt/data/hdf5_vla_dataset.py
third_party/rdt/data/hdf5_maniskill_dataset.py
third_party/rdt/configs/state_vec.py
third_party/rdt/configs/base.yaml
third_party/rdt/train/dataset.py
third_party/rdt/train/train.py
third_party/rdt/data/preprocess.py
third_party/rdt/agent/finetune_analysis.md
third_party/rdt/agent/libero_dataset_semantics_analysis.md
third_party/libero/scripts/create_dataset.py
third_party/libero/libero/libero/envs/bddl_base_domain.py
core/env_adapters/libero_adapter.py
core/pi05_steer.py
core/diffusion_policy_steer.py
core/rdt_policy_steer.py
```

The most important confirmed external facts are:

```text
LIBERO dataset source: yifengzhu-hf/LIBERO-datasets
RDT source: thu-ml/RoboticsDiffusionTransformer
```

When local source and older notes disagree, this design prefers current local source plus direct HDF5 inspection.

## Approved Direction

The approved direction is **RDT-convention first**:

```text
Use RDT's right-EEF position + 6D rotation + right gripper-open slots.
Use LIBERO's native OSC action scale for executable action targets.
Use EEF proprioception rather than joint proprioception.
Use two real LIBERO cameras inside RDT's three-camera contract.
Start with libero_object before broadening to other LIBERO suites.
```

The core active RDT dimensions are:

```text
right_gripper_open: 10
right_eef_pos:      30, 31, 32
right_eef_angle_0:  33
right_eef_angle_1:  34
right_eef_angle_2:  35
right_eef_angle_3:  36
right_eef_angle_4:  37
right_eef_angle_5:  38
```

So the active index list is:

```text
LIBERO_RDT_INDICES = [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
```

## Current RDT Fine-Tuning Contract

For `--load_from_hdf5`, RDT training flows through:

```text
main.py
-> train.train()
-> VLAConsumerDataset(use_hdf5=True)
-> HDF5VLADataset.get_item()
-> HDF5VLADataset.parse_hdf5_file()
-> DataCollatorForVLAConsumerDataset
-> SigLIP + T5 encoders
-> RDTRunner.compute_loss()
```

The LIBERO loader must return samples compatible with the existing HDF5 path:

```text
state:           (1, 128)
actions:         (64, 128)
state_indicator: (128,)
cam_high:        (2, H, W, 3)
cam_right_wrist: (2, H, W, 3)
cam_left_wrist:  missing or zero-shape with mask false
language instruction
dataset_name
```

RDT's base model expects:

```text
state_dim: 128
action_chunk_size: 64
img_history_size: 2
num_cameras: 3
```

Therefore the LIBERO fine-tune should not reduce RDT to one camera at the architecture/config level. Missing cameras should be represented through the existing masking/background path.

## LIBERO HDF5 Facts

Each LIBERO suite directory contains task-level HDF5 files. Each file stores demonstrations under:

```text
data/demo_0
data/demo_1
...
data/demo_49
```

Confirmed per-demo fields include:

```text
actions:                 (T, 7), float64
obs/agentview_rgb:       (T, 128, 128, 3), uint8
obs/eye_in_hand_rgb:     (T, 128, 128, 3), uint8
obs/gripper_states:      (T, 2), float64
obs/joint_states:        (T, 7), float64
obs/ee_states:           (T, 6), float64
obs/ee_pos:              (T, 3), float64
obs/ee_ori:              (T, 3), float64
robot_states:            (T, 9), float64
states:                  (T, 47), float64
rewards/dones:           terminal sparse flags
```

Language is stored in:

```text
json.loads(h5["data"].attrs["problem_info"])["language_instruction"]
```

The environment metadata confirms:

```text
controller type: OSC_POSE
control_delta: true
input_min/input_max: -1, 1
output_min/output_max for EEF pos: [-0.05, 0.05]
output_min/output_max for EEF rot: [-0.5, 0.5]
control_freq: 20
camera_names: robot0_eye_in_hand, agentview
```

## Action Mapping

LIBERO actions are native normalized OSC pose commands:

```text
raw_action = [dx, dy, dz, drot_x, drot_y, drot_z, gripper]
```

The first six dimensions are normalized control inputs, not absolute future EEF poses and not joint targets. They should stay in the LIBERO normalized control scale so deployment can send decoded RDT outputs directly to LIBERO's environment action space.

Training action target:

```text
actions[:, 30:33] = raw_action[:, 0:3]
actions[:, 33:39] = rotvec_to_ortho6d(raw_action[:, 3:6])
actions[:, 10]    = (1 - raw_action[:, 6]) / 2
```

Deployment decode:

```text
raw_action[:, 0:3] = clip(pred[:, 30:33], -1, 1)
raw_action[:, 3:6] = clip(ortho6d_to_rotvec(pred[:, 33:39]), -1, 1)
raw_action[:, 6]   = clip(1 - 2 * pred[:, 10], -1, 1)
```

Gripper rationale:

```text
LIBERO action convention: -1 = open, +1 = close
RDT state_vec convention: right_gripper_open is open-high
```

The affine mapping `(1 - raw_gripper) / 2` preserves both endpoints:

```text
raw -1 open  -> RDT open 1
raw +1 close -> RDT open 0
```

It is preferable to a sign flip because RDT's gripper slot is conceptually an open scalar in `[0, 1]`, not an unbounded signed action.

## Rotation Representation

RDT's EEF angle slots are six-dimensional. LIBERO stores EEF orientation observations as axis-angle and action orientation commands as three normalized rotation-control dimensions.

The design uses the same conversion family for state and action:

```text
3D axis-angle / rotation-vector style input
-> scipy Rotation or existing RDT-compatible rotation utility
-> rotation matrix
-> 6D ortho representation
```

Action orientation uses:

```text
rotvec_to_ortho6d(raw_action[:, 3:6])
```

State orientation uses:

```text
rotvec_to_ortho6d(obs/ee_ori or obs/ee_states[:, 3:6])
```

Implementation must verify the exact 6D convention against existing RDT utilities/tests before writing the loader. The expected convention is the common first-two-rotation-matrix-columns representation. The inverse path for deployment must use the matching convention.

The important semantic decision is that the RDT training tensor uses all six RDT EEF angle slots `[33:39]`, not the older partial `[33:36]` path.

## Proprioception Mapping

Two alternatives were considered:

```text
Option A: LIBERO-common joint + gripper observation.
Option B: RDT-convention EEF pose + gripper observation.
```

LIBERO behavior cloning commonly uses joint positions and gripper state. However, RDT's current training path uses a shared `state_elem_mask`/`action_mask` convention, and upstream RDT preprocessing assembles action and state using the same active robot format. A mixed design with joint-state inputs and EEF-action targets would require broader training-code changes to support distinct state and action masks.

The approved first fine-tune uses Option B:

```text
state[30:33] = current EEF position from obs/ee_pos
state[33:39] = rotvec_to_ortho6d(current EEF orientation from obs/ee_ori)
state[10]    = current gripper-open scalar from obs/gripper_states
```

Recommended gripper state scalar:

```text
state[10] = clip((gripper_states[:, 0] - gripper_states[:, 1]) / 0.08, 0, 1)
```

Direct `libero_object` inspection confirms the two gripper joints are opposite-signed finger positions, roughly `+0.04` and `-0.04` at the open end. The two-finger width formula is therefore preferred over reading only one finger.

No normalization should be applied to action dimensions beyond the gripper convention mapping and 3D-to-6D rotation conversion. This keeps action targets consistent with RDT's README guidance to avoid action normalization except gripper width/open values.

## Image Mapping

LIBERO provides two useful real camera observations:

```text
obs/agentview_rgb
obs/eye_in_hand_rgb
```

The approved mapping is:

```text
cam_high        <- obs/agentview_rgb
cam_right_wrist <- obs/eye_in_hand_rgb
cam_left_wrist  <- missing/empty, mask false
```

This matches both LIBERO's available cameras and RDT's existing three-camera ordering:

```text
[ext_{t-1}, right_wrist_{t-1}, left_wrist_{t-1},
 ext_t,     right_wrist_t,     left_wrist_t]
```

PI05 local LIBERO evaluation also uses two real views:

```text
observation.images.image  <- agentview_image
observation.images.image2 <- robot0_eye_in_hand_image
```

Its checkpoint declares one extra empty camera slot, so it is effectively a two-real-camera policy with one masked empty visual slot. Diffusion Policy camera usage is checkpoint-config dependent, but the local LIBERO adapter still provides the same two real image keys.

This is why RDT should not imitate ManiSkill's single-camera loader for LIBERO. ManiSkill fine-tuning used only one camera because the selected ManiSkill data/config path was simpler and matched that checkpoint's task setup; LIBERO has a meaningful wrist view and local LIBERO policies already consume it.

Deployment implication:

```text
core/rdt_obs_processor.py must later feed observation.images.image2 into RDT's right-wrist slot
when evaluating a checkpoint trained with this design.
```

That deployment edit belongs to the later implementation plan, not this design step.

## Language Mapping

Primary source:

```text
json.loads(h5["data"].attrs["problem_info"])["language_instruction"]
```

Fallbacks, in order:

```text
1. task/problem metadata in HDF5 attrs
2. filename-derived task phrase
3. fail loudly with file path and demo id
```

Because T5-XXL is large, the design should prefer precomputed language embeddings or the repository's existing embedding cache path when running full fine-tuning. Loader implementation should still expose raw language text in the format expected by RDT's current HDF5 data path so the existing collator/encoder path remains usable for smoke tests.

## Loader Architecture

Create a dedicated loader:

```text
third_party/rdt/data/libero_vla_dataset.py
```

Responsibilities:

```text
Discover task HDF5 files under configured suite roots.
Index each `data/demo_i` trajectory as one episode record.
Parse language, control frequency, and suite/task metadata from HDF5 attrs.
Sample timesteps with the same action-chunk semantics as existing RDT HDF5 loaders.
Build 128D RDT state/action tensors using the approved active indices.
Return two real camera histories and one masked missing left-wrist camera.
Expose state-only/action-only access required by dataset-stat computation.
Return suite-level dataset names.
```

Initial target:

```text
RDT_LIBERO_SUITES=libero_object
RDT_LIBERO_DATA_ROOT=/mnt/data/hf_cache/hub
```

Later extension:

```text
RDT_LIBERO_SUITES=libero_object,libero_spatial,libero_goal,libero_90,libero_10
```

Integration should be minimal:

```text
Keep data/hdf5_vla_dataset.py as the import point used by VLAConsumerDataset.
Select the LIBERO loader through an explicit backend/config flag.
Avoid changing train/dataset.py unless unavoidable.
```

Recommended backend switch:

```text
RDT_HDF5_BACKEND=libero
```

This keeps the first implementation scoped and avoids changing the behavior of existing HDF5 datasets.

## Dataset Names and Configs

For logging, sampling, and stats, use suite-level dataset names:

```text
libero_object
libero_spatial
libero_goal
libero_90
libero_10
```

The initial config registration should include only `libero_object` unless the implementation plan explicitly broadens scope.

Expected config touch points:

```text
third_party/rdt/configs/finetune_datasets.json
third_party/rdt/configs/finetune_sample_weights.json
third_party/rdt/configs/dataset_control_freq.json
third_party/rdt/configs/dataset_stat.json
```

Dataset statistics must be generated by the repository's dataset-stat path, not hand-written, except for a clearly marked temporary smoke-test fixture if required.

## Statistics and Normalization

RDT requires state statistics for active dimensions. For LIBERO:

```text
State EEF position stats should be computed from obs/ee_pos.
State 6D rotation stats should be computed after rotvec_to_ortho6d(obs/ee_ori).
State gripper-open stats should be computed after the chosen gripper-state mapping.
Actions should remain in LIBERO normalized OSC command scale.
```

The stats path should generate values for the active RDT slots and neutral values for inactive slots using the same pattern as existing RDT loaders.

If deployment needs any nontrivial state transform metadata, the same generated stats/config should be loaded by deployment preprocessing. LIBERO mode should fail loudly if required stats are missing rather than silently using approximate bounds.

## Training Script

Add a LIBERO-specific fine-tuning script during implementation:

```text
third_party/rdt/finetune_libero.sh
```

It should:

```text
Set RDT_HDF5_BACKEND=libero.
Default RDT_LIBERO_DATA_ROOT to /mnt/data/hf_cache/hub.
Default RDT_LIBERO_SUITES to libero_object.
Use --load_from_hdf5.
Use --dataset_type=finetune.
Point model/text/vision paths at the local cached pretrained assets.
Write checkpoints under a LIBERO-specific checkpoint directory.
Expose smoke-test overrides such as max steps, batch size, and sample period.
```

Do not broaden to all LIBERO suites until the object split has passed loader, stats, one-step training, and small rollout smoke tests.

## Loss Masking Consideration

RDT's current loss averages over the full 128D action vector. LIBERO activates only ten dimensions:

```text
[30,31,32,33,34,35,36,37,38,10]
```

If the existing RDT path does not already mask inactive action dimensions correctly, the implementation plan should include an optional masked action-loss path. The mask must be derived from active action dimensions and should avoid diluting the loss across inactive zeros.

This should be treated as an implementation-time verification item:

```text
First inspect RDTRunner.compute_loss() and batch masks.
If inactive dimensions contribute to loss, add a minimal opt-in masked loss.
If existing masks already cover this, document the evidence and avoid changing loss code.
```

## Semantic Alignment Risks

The main risks are semantic, not just shape-related:

```text
1. Treating LIBERO actions as absolute EEF poses instead of normalized OSC delta commands.
2. Using only three RDT rotation slots even though RDT EEF orientation is 6D.
3. Using a 6D rotation conversion whose column/order convention differs from RDT deployment.
4. Mapping LIBERO gripper `-1=open, +1=close` to the wrong RDT open-high convention.
5. Mixing joint-state proprioception with EEF-action targets without separate state/action masks.
6. Training with wrist images but deploying with only the external camera.
7. Accidentally normalizing action positions/orientations and then sending denormalized values to LIBERO.
8. Inferring language from filenames when HDF5 language metadata exists.
9. Letting `dataset_stat.json` or control-frequency config drift from the loader's dataset names.
10. Expanding from `libero_object` to all suites before the object split is verified.
```

Mitigations:

```text
Use direct HDF5 and LIBERO source evidence for action/controller semantics.
Round-trip test rotvec -> 6D -> rotvec on representative LIBERO values.
Unit-test gripper endpoint mapping with open/close examples.
Assert active indices exactly match [30..38, 10].
Verify one real sample's images appear in the expected RDT order.
Run a one-step training smoke test before any long fine-tune.
Run deployment preprocessing smoke tests with both agentview and wrist images.
```

## Verification Strategy

Verification should proceed in this order:

```text
1. Unit test rotation conversion round trips for representative LIBERO rotvec commands.
2. Unit test gripper action mapping: raw -1 -> open 1, raw +1 -> open 0.
3. Unit test gripper state mapping against observed `obs/gripper_states` ranges.
4. Unit test a tiny synthetic LIBERO-like HDF5 file.
5. Inspect one real `libero_object` HDF5 sample through the loader.
6. Verify one sample returns exact RDT shapes and active masks.
7. Verify image history order and missing left-wrist mask/background behavior.
8. Run `VLAConsumerDataset` + DataLoader batch-size-2 smoke test.
9. Run dataset-stat generation on `libero_object`.
10. Run one-step fine-tune with `--load_from_hdf5`.
11. Run a short object-split fine-tune.
12. Run a small LIBERO benchmark rollout subset.
```

## Success Criteria

The implementation is ready for real `libero_object` fine-tuning when:

```text
The loader indexes all task files and demos under /mnt/data/hf_cache/hub/libero_object.
Language comes from HDF5 `problem_info`.
Control frequency is 20 from HDF5/LIBERO metadata.
Active state/action indices are exactly [30,31,32,33,34,35,36,37,38,10].
State orientation is represented in six RDT rotation slots.
Action orientation targets are represented in six RDT rotation slots.
Action decode can recover native LIBERO 7D OSC commands.
Two real cameras are loaded: agentview as cam_high, eye-in-hand as cam_right_wrist.
cam_left_wrist is masked/missing, not silently filled as a real camera.
Dataset statistics are generated through the RDT stats path.
One-step training completes without shape, dtype, device, or NaN failures.
Deployment preprocessing is updated before evaluating a two-camera-trained checkpoint.
```

## Out of Scope for First Implementation

```text
Training all five LIBERO suites before object-split smoke tests pass.
Changing RDT architecture to one or two cameras.
Joint-state proprioception with EEF actions.
FK conversion from RDT outputs to LIBERO actions.
Hand-authoring final dataset statistics.
Benchmark optimization or hyperparameter search.
```

## Next Step

After this spec is reviewed and approved, move to the Superpowers `writing-plans` workflow and produce a step-by-step implementation plan. Implementation should not begin until that plan is approved.
