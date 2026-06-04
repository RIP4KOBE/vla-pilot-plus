---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/project_notes/project_overview.md
summary: VLA-Pilot++ Project Overview
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/project_notes/project_overview.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/project_notes/project_overview.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/analysis/project_overview.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/analysis/project_overview.md
  - .worktrees/feat/rdt-libero-dataset_finetune/analysis/project_overview.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/analysis/project_overview.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/analysis/project_overview.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/analysis/project_overview.md
  - analysis/project_overview.md
---

# VLA-Pilot++ Project Overview

> **VLS: Vision-Language Steering of Pretrained Robot Policies**
> Inference-time adaptation of diffusion/flow-matching robot policies via VLM-synthesized reward functions.
> Paper: https://arxiv.org/abs/2602.03973
> Results: +31% on CALVIN, +13% on LIBERO-PRO, real-world Franka deployment.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Data Flow & Execution Pipeline](#2-data-flow--execution-pipeline)
3. [Core Scripts](#3-core-scripts)
4. [VLM Query](#4-vlm-query)
5. [Environment Adapters](#5-environment-adapters)
6. [Utilities](#6-utilities)
7. [Configuration Files](#7-configuration-files)
8. [Key Algorithms](#8-key-algorithms)
9. [Running the Project](#9-running-the-project)

---

## 1. Project Structure

```
VLA-Pilot++/
├── main.py                          # Main entry point & orchestrator (815 lines)
├── environment.yml                  # Conda environment
├── requirements.txt                 # Pip dependencies
│
├── configs/                         # Hydra configuration
│   ├── config.yaml                  # Main config (steering params, episode settings)
│   ├── perception.yaml              # Perception pipeline (keypoints, VLM, SAM)
│   ├── policy.yaml                  # Policy selection (diffusion or pi05)
│   ├── backend/
│   │   ├── calvin.yaml              # CALVIN (PyBullet) environment
│   │   └── libero.yaml              # LIBERO-PRO (MuJoCo) environment
│   └── task/calvin/                 # Per-task configs (drawer_open, door_left, ...)
│
├── core/                            # Core algorithm implementations
│   ├── diffusion_policy_steer.py    # Steerable diffusion policy (545 lines)
│   ├── pi05_steer.py                # Steerable PI05/flow-matching policy (300+ lines)
│   ├── fkd_class.py                 # Feynman-Kac particle resampler (320 lines)
│   ├── keypoint_detector.py         # DINO-based keypoint detection (650 lines)
│   ├── keypoint_tracker.py          # Multi-frame keypoint tracking (223 lines)
│   ├── gemini_grounder.py           # Gemini visual grounding (200+ lines)
│   ├── sam_segmenter.py             # SAM-based segmentation
│   ├── sam3_segmenter.py            # SAM3 segmentation variant
│   ├── sam_refiner.py               # SAM mask refinement
│   └── env_adapters/
│       ├── base_adapter.py          # Abstract adapter interface (400+ lines)
│       ├── calvin_adapter.py        # CALVIN backend (400+ lines)
│       └── libero_adapter.py        # LIBERO-PRO backend (400+ lines)
│
├── vlm_query/
│   └── vlm_agent.py                 # GPT-4o guidance function generator (350+ lines)
│
├── utils/
│   ├── guidance_utils.py            # Load & validate VLM-generated guidance code
│   ├── vis_utils.py                 # Trajectory & keypoint visualization
│   ├── keypoint_utils.py            # Keypoint projection utilities
│   ├── logging_utils.py             # Colored logging helpers
│   ├── plot_results.py              # Results plotting
│   ├── config_utils.py              # Config helpers
│   └── hydra_plugins/               # Hydra searchpath plugin
│
├── patches/
│   └── light.py                     # CALVIN Light class patch for initial_state support
│
├── scripts/
│   └── run_libero_suites.sh         # Shell script to run all LIBERO suites
│
├── ablations/                       # Ablation study configs
└── third_party/                     # Git submodules
    ├── calvin/                      # CALVIN environment
    ├── lerobot/                     # LeRobot (policy base classes)
    └── libero_pro/                  # LIBERO-PRO benchmark
```

---

## 2. Data Flow & Execution Pipeline

```
python main.py  (Hydra @hydra.main decorator)
    │
    ├─ [1] Create Adapter  (CALVIN or LIBERO)
    │       Provides: RGB/depth/seg, robot state, object poses, action space
    │
    ├─ [2] Load Policy  (DiffusionPolicySteer or PI05Steer)
    │       └─ post_init(adapter, batch_size)
    │
    └─ [3] Episode Loop  (episode_num times)
            │
            ├─ [3a] env.reset()  (seed-based reproducibility)
            │
            ├─ [3b] Keypoint Detection & Guidance Generation  (once per episode)
            │       ├─ KeypointDetector: DINO features → cluster → keypoints (N×3)
            │       ├─ KeypointTracker: register keypoints to object poses
            │       └─ VLMAgent: RGB + instruction → GPT-4o → Python reward functions
            │               saved to: outputs/{backend}/{ts}/episode_N/vlm_agent/
            │
            └─ [3c] Step Loop  (until done or max_steps)
                    ├─ If new action chunk needed:
                    │   ├─ Update stage via Gemini (trigger-based recognition)
                    │   ├─ KeypointTracker: get current keypoint world positions
                    │   └─ policy.select_action(guidance_fns, keypoints, ...)
                    │       └─ _guided_conditional_sample()
                    │           Phase 1 (high noise): RBF diversity gradient
                    │           Phase 2 (refinement): keypoint reward gradient + adaptive scale
                    │           Optional FKD: particle resampling by reward
                    │           → action chunk (B, T, action_dim)
                    ├─ env.step(action[t])
                    ├─ Record frame, update reward tracking
                    └─ Check stage transition triggers
```

**Output per episode**:
```
outputs/{backend}/{timestamp}/
├── episode_N/
│   ├── vlm_agent/
│   │   ├── query_img.png, prompt.txt, output_raw.txt
│   │   ├── stage1_guidance.txt, stage2_guidance.txt, ...
│   │   └── metadata.json  (num_stages, stage_names, keypoints)
│   ├── episode_N_success.mp4  (or _fail.mp4)
│   └── keypoints_tracking.mp4
└── results.txt  (success rate)
```

---

## 3. Core Scripts

### `main.py` — Main Orchestrator (815 lines)

Central coordination of the entire VLS pipeline.

**Class `Main(cfg)`**:

| Method | Description |
|--------|-------------|
| `__init__()` | Init adapter, policy, perception components from Hydra config |
| `_init_components()` | Lazy-init keypoint detector, VLM agent, Gemini grounder |
| `perform_task_for_episode()` | Detect keypoints, call VLM to generate guidance functions for all stages |
| `_run_episode()` | Single episode loop: step environment, apply guidance, record video |
| `_update_stage()` | Schmitt-trigger stage recognition via Gemini queries |
| `_get_policy_observation()` | Format observation dict for policy input |
| `run()` | Outer loop: reset env, run episode, log results |
| `run_test()` | Debug mode for segmentation and keypoint visualization |

**Entry point**: `@hydra.main(config_path="configs", config_name="config")`

---

### `core/diffusion_policy_steer.py` — Steerable Diffusion Policy (545 lines)

Extends LeRobot's `DiffusionPolicy` with gradient-based and particle-based steering during denoising.

| Method | Description |
|--------|-------------|
| `select_action(batch, use_guidance, keypoints, guidance_fns, ...)` | Main action selection; caches chunks across horizon steps |
| `_predict_action_chunk_guided(obs, ...)` | Wraps obs into batch tensor, triggers guided sampling |
| `_guided_conditional_sample(batch, guidance_fns, ...)` | Core denoising loop with two-phase guidance |
| `_compute_keypoint_gradient(sample, ...)` | `torch.autograd` grad of reward w.r.t. diffusion sample |
| `_compute_diversity_gradient(samples)` | RBF repulsion gradient to spread particles |
| `_sample_to_trajectory_3d(sample)` | Converts diffusion sample → 3D EE trajectory tensor |

**Two-phase guidance**:
- **Phase 1** (`t > start_step`, high noise): Diversity gradient pushes particles apart
- **Phase 2** (`t ≤ start_step`, refinement): Keypoint reward gradient steers toward target

**Reward normalization**:
- First chunk's final reward → baseline (`_stage_init_reward`)
- `normalized_r = clamp(1 - reward/baseline, 0, 1.2)`
- Sigmoid-gated guidance strength: softer as target is approached

---

### `core/pi05_steer.py` — Steerable PI05 Policy (300+ lines)

Extends LeRobot's `PI05Policy` (flow-matching) with identical two-phase guidance as `diffusion_policy_steer.py` but adapted to the flow-matching ODE solver.

| Method | Description |
|--------|-------------|
| `select_action(...)` | Same interface as `DiffusionPolicySteer` |
| `_sample_actions_guided(...)` | Flow-matching loop with phase 1/2 gradient injection |

---

### `core/fkd_class.py` — Feynman-Kac Diffusion Resampler (320 lines)

Non-gradient particle filtering: maintains a swarm of trajectory particles and resamples based on reward potentials.

**`PotentialType` enum**:

| Value | Potential Function |
|-------|--------------------|
| `DIFF` | `reward_t - reward_{t-1}` (incremental improvement) |
| `MAX` | `max(reward_t, running_max)` (best so far) |
| `ADD` | `Σ reward_t` (cumulative) |
| `RT` | `reward_t` (instantaneous) |

**`FKD` class**:

| Method | Description |
|--------|-------------|
| `__init__(reward_fn, lmbda, resample_frequency, ...)` | Init particles, register reward function |
| `resample(x, t)` | At specified timesteps: compute rewards → weights → multinomial resample if ESS low |

**Resampling logic**:
```
weights = exp(λ * potential)
ESS = 1 / Σ(normalized_weights²)
if ESS < 0.5 * num_particles:  resample via multinomial
at terminal:  sort by reward, return best particle
```

---

### `core/keypoint_detector.py` — DINO Keypoint Detector (650 lines)

Detects semantically meaningful 3D keypoints on objects using DINOv2/v3 dense features + spatial clustering.

**Algorithm**:
1. Extract per-pixel DINO features (DINOv2 via `torch.hub` or DINOv3 via HuggingFace)
2. For each segmented object mask:
   - Collect foreground features → PCA to 3D → K-means clustering
   - Select pixel closest to each cluster center
3. Merge nearby keypoints via MeanShift
4. Filter by workspace bounds
5. Guarantee ≥1 keypoint per object

| Method | Description |
|--------|-------------|
| `get_keypoints(rgb, points, segmentation, segment_id_to_name)` | Main entry; returns `(keypoints N×3, projected_image, mask_ids N)` |
| `_get_features(rgb)` | Extract DINO features (handles DINOv2 and DINOv3) |
| `_cluster_features(features, mask)` | K-means on features, returns pixel coords |
| `_merge_clusters(keypoints)` | MeanShift merging to de-duplicate nearby points |
| `get_keypoints_with_visualization(...)` | Detection + returns annotated image |
| `visualize_dino_features(rgb, seg)` | PCA of features → RGB heatmap overlay |

**Config params** (`configs/perception.yaml`):
- `num_candidates_per_mask: 5` — keypoints per object
- `min_dist_bt_keypoints: 0.05` — MeanShift bandwidth (meters)
- `max_mask_ratio: 0.5` — ignore masks covering >50% of image
- `feature_extractor: dinov3_vitb16` — DINO model variant
- `bounds_min/max` — workspace filtering bounds

---

### `core/keypoint_tracker.py` — Keypoint Tracker (223 lines)

Tracks 3D keypoints across frames as objects move, using object-relative coordinates.

**Algorithm**:
1. **Register**: For each keypoint, compute its position in the object's local frame
2. **Track**: Each frame, query adapter for current object pose → transform local → world

**`KeypointInfo` dataclass**: `index`, `initial_world_pos`, `local_pos`, `segment_index`, `object_name`

| Method | Description |
|--------|-------------|
| `register_keypoints(keypoints, mask_ids, seg_id_to_name)` | One-time init per episode |
| `get_keypoint_positions()` | Returns current world positions (N×3) |
| `get_object_name_by_keypoint(idx)` | Lookup object name for keypoint |
| `get_mask_ids()` | Return mask IDs of all tracked keypoints |

Background keypoints (`segment_index=0`) return their fixed initial position.

---

### `core/gemini_grounder.py` — Gemini Visual Grounder (200+ lines)

Uses Gemini's spatial understanding to detect objects and generate segmentation masks (alternative to SAM).

| Method | Description |
|--------|-------------|
| `detect_objects(image, object_names)` | Query Gemini for bounding boxes (normalized [0,1000]) |
| `detect_to_segmentation(image, object_names)` | Bboxes → segmentation mask + `segment_id_to_name` dict |
| `detect_points(image, object_names)` | Return center points of detected objects |

**Advantage over SAM**: Better semantic understanding; can target task-relevant parts (e.g., "drawer handle").

---

## 4. VLM Query

### `vlm_query/vlm_agent.py` — GPT-4o Guidance Generator (350+ lines)

Queries GPT-4o (or Azure OpenAI) with a visual prompt to synthesize Python reward functions for trajectory steering.

| Method | Description |
|--------|-------------|
| `__init__()` | Init OpenAI client; load prompt templates from `vlm_query/` |
| `generate_guidance(image, instruction, metadata)` | Main call: returns dir with guidance files |
| `_build_prompt(image, instruction, metadata)` | Base64-encode image + fill template placeholders |
| `_parse_and_save_guidance_functions(output)` | Extract Python blocks from GPT output → stage files |
| `_parse_other_metadata(output)` | Extract `num_stages`, `stage_names` |
| `plan_segmentation(image, instruction)` | Ask VLM which objects to segment |

**Generated guidance function signature**:
```python
def stage1_guidance_1(keypoints: Tensor, trajectory_3d: Tensor) -> Tensor:
    """
    keypoints:      (N, 3)    - tracked keypoint world positions
    trajectory_3d:  (B, T, 3) - predicted EE trajectory
    returns:        scalar tensor (higher = better)
    """
```

**Outputs saved to** `{episode_dir}/vlm_agent/`:
- `query_img.png` — image sent to VLM
- `prompt.txt` — full prompt text
- `output_raw.txt` — raw GPT response
- `stage{N}_guidance.txt` — parsed reward functions per stage
- `metadata.json` — keypoints, objects, num_stages, stage_names

---

## 5. Environment Adapters

### `core/env_adapters/base_adapter.py` — Abstract Interface (400+ lines)

Unified `gym.Env` interface that all backends must implement.

**Key data classes**:

| Class | Fields |
|-------|--------|
| `Pose3D` | `position (3,)`, `quaternion [w,x,y,z] (4,)`; methods: `to_transformation_matrix()`, `inverse()` |
| `CameraParams` | `intrinsic`, `extrinsic`, `width`, `height` |
| `TrackedObject` | `name`, `pose: Pose3D`, `obj_ref` |
| `InteractableObject` | `name`, `object_id`, `link_index`, `segment_index` |

**Required adapter methods**:

| Category | Methods |
|----------|---------|
| Robot state | `get_ee_pose()`, `get_ee_pose_world()`, `get_robot_base_pose()`, `get_joint_positions()`, `get_gripper_state()` |
| Action | `delta_actions_to_ee_trajectory(action_sequence)`, `get_action_space_info()` |
| Camera | `get_vlm_image()`, `get_camera_params(name)`, `get_camera_names()`, `project_3d_to_2d(pts, cam)` |
| Scene | `get_scene_objects()`, `get_object_pose(name)`, `get_object_pose_by_segment(idx)` |
| Segmentation | `get_interactable_objects()`, `process_segmentation(seg_image)` |

---

### `core/env_adapters/calvin_adapter.py` — CALVIN Backend (400+ lines)

Binds PyBullet-based CALVIN simulator to the adapter interface.

- **Action space**: 7D delta (`dx, dy, dz, droll, dpitch, dyaw, gripper`)
- **Camera**: Static overhead (200×200) + gripper camera
- **Objects**: Table, drawers, buttons, switches, colored cubes
- **Tasks**: `drawer_open`, `door_left`, `light_on`, `slider_left`, etc.

---

### `core/env_adapters/libero_adapter.py` — LIBERO-PRO Backend (400+ lines)

Binds MuJoCo-based LIBERO-PRO benchmark to the adapter interface.

- **Suites**: `libero_goal`, `libero_spatial`, `libero_object`, `libero_10`
- **Perturbations**: Object swaps, language variations, OOD evaluation
- **Policy**: PI05 flow-matching (10 inference steps, 10-step action chunks)

---

## 6. Utilities

### `utils/guidance_utils.py` — Guidance Code Loader (300+ lines)

Safely loads and validates VLM-generated guidance functions before execution.

- Parses `stage{N}_guidance.txt` files
- `exec()`s Python code in a sandboxed namespace
- Returns callable `(keypoints, trajectory_3d) → reward`
- Validates function signature and output type

### `utils/vis_utils.py` — Visualization (300+ lines)

- Trajectory drawing on RGB images (colored lines per action chunk)
- Keypoint overlay with labels and tracking trails
- Heatmap generation for reward landscapes
- Video compilation from frame sequences

### `utils/keypoint_utils.py` — Keypoint Projection

- Project 3D keypoints to 2D image coordinates using camera intrinsics/extrinsics
- Handle batched projections across multiple camera views

### `utils/logging_utils.py` — Colored Logging

- ANSI-colored log levels (DEBUG=cyan, INFO=green, WARNING=yellow, ERROR=red)
- Consistent prefix format for episode/step tracking

### `scripts/run_libero_suites.sh` — LIBERO Suite Runner

Shell script that iterates over LIBERO suites and task indices, calling `python main.py` with appropriate overrides for systematic benchmarking.

---

## 7. Configuration Files

### `configs/config.yaml` — Main Config

```yaml
device: cuda
seed: 0
defaults: [backend: libero, perception, policy]

main:
  episode_num: 10
  use_guidance: false        # Enable/disable steering
  guide_scale: 80.0          # Gradient guidance strength
  diversity_scale: 20.0      # RBF diversity repulsion strength
  start_ratio: null          # Fraction of denoising steps before guidance starts
  MCMC_steps: 4              # Gradient steps per denoising step
  sigmoid_k: 25.0            # Sigmoid steepness for adaptive scaling
  sigmoid_x0: 0.75           # Sigmoid midpoint
  use_fkd: true              # Enable Feynman-Kac resampling
  sample_batch_size: 1       # Number of particles
```

### `configs/perception.yaml`

```yaml
keypoint_detector:
  num_candidates_per_mask: 5
  min_dist_bt_keypoints: 0.05   # meters
  max_mask_ratio: 0.5
  feature_extractor: dinov3_vitb16
  bounds_min: [-1.0, -0.75, -0.1]
  bounds_max: [1.00, 0.75, 1.2]

vlm_agent:
  model: gpt-4o
  temperature: 1.0
  max_completion_tokens: 2000

gemini_grounding:
  enabled: true
  model: gemini-2.5-flash

gemini:
  model: gemini-2.5-flash    # Stage recognition
```

### `configs/policy.yaml`

```yaml
type: pi05                   # or "diffusion"

diffusion:
  pretrained_path: Vision-Language-Steering/vls_calvin_base
  num_inference_steps: 100
  action_chunk_horizon: 16

pi05:
  pretrained_path: lerobot/pi05_libero_finetuned_v044
  num_inference_steps: 10
  action_chunk_horizon: 10
```

### `configs/backend/calvin.yaml` / `libero.yaml`

Backend-specific: environment path, camera resolution, task list, perturbation settings.

---

## 8. Key Algorithms

### 8.1 Gradient-Based Guidance (in `_guided_conditional_sample`)

```python
# Phase 1: t > start_step — diversity (spread particles)
diversity_grad = ∇_sample Σ_ij exp(-||sample_i - sample_j||² / 2σ²)
model_output += diversity_scale * diversity_grad

# Phase 2: t ≤ start_step — keypoint reward guidance
with torch.enable_grad():
    trajectory = sample_to_3d_trajectory(sample)      # (B, T, 3)
    reward = Σ guidance_fn(keypoints, trajectory)
    grad = ∇_sample reward

# Adaptive scaling via sigmoid
normalized_r = clamp(1 - reward / baseline, 0, 1.2)
strength = sigmoid(k * (normalized_r - x0))
scale = guide_scale * strength * sqrt(1 - alpha_cumprod[t])
model_output -= scale * grad
```

### 8.2 Feynman-Kac Resampling (in `fkd_class.py`)

```python
# At each resampling timestep:
rewards = reward_fn(x0_predictions)          # shape: (num_particles,)
potentials = potential_fn(rewards)           # DIFF, MAX, ADD, or RT
weights = softmax(λ * potentials)
ESS = 1 / Σ(weights²)
if ESS < 0.5 * num_particles:
    indices = multinomial(weights, num_particles, replacement=True)
    particles = particles[indices]

# At terminal timestep:
return particles[argsort(rewards, descending=True)[0]]  # best particle
```

### 8.3 Stage Recognition (Schmitt Trigger in `main.py`)

```python
# Trigger VLM stage query when:
# - gripper closes AND reward rises above upper_threshold
# - gripper opens  AND reward falls below lower_threshold

# Gemini stage query input:
#   current RGB + keypoints + stage_names + trigger_reason
# Output: new_stage_index, need_guidance boolean
```

---

## 9. Running the Project

### Setup

```bash
conda env create -f environment.yml
conda activate vla-pilot
cd third_party/lerobot && pip install -e . && cd ../..
cd third_party/calvin/calvin_env && pip install -e . && cd ../../..
cd third_party/libero_pro && pip install -e . && cd ..
```

### Basic Usage

```bash
# LIBERO (default)
python main.py

# LIBERO with guidance enabled
python main.py main.use_guidance=true main.guide_scale=80

# CALVIN task
python main.py backend=calvin backend.calvin.target_behavior=drawer_open policy=diffusion

# More episodes, custom steering
python main.py main.episode_num=50 main.guide_scale=120 main.diversity_scale=30 main.use_fkd=true

# Debug/test mode
python main.py main.mode=test
```

### Environment Variables Required

```bash
[redacted credential configuration example]
[redacted credential configuration example]
```

---

## Quick Reference: Script Roles

| Script | Role | Key Input | Key Output |
|--------|------|-----------|------------|
| `main.py` | Orchestrator | Hydra config | Episode videos, results.txt |
| `diffusion_policy_steer.py` | Guided denoising | Obs + guidance_fns | Action chunk (B,T,D) |
| `pi05_steer.py` | Guided flow-matching | Obs + guidance_fns | Action chunk (B,T,D) |
| `fkd_class.py` | Particle resampling | Diffusion samples | Best particle |
| `keypoint_detector.py` | 3D keypoint extraction | RGB + depth + seg | Keypoints (N,3) |
| `keypoint_tracker.py` | Keypoint tracking | Keypoints + obj poses | Current positions (N,3) |
| `vlm_agent.py` | Reward code generation | RGB + instruction | Python reward functions |
| `gemini_grounder.py` | Object detection | RGB + object names | Segmentation mask |
| `calvin_adapter.py` | CALVIN env binding | CALVIN env | Unified adapter API |
| `libero_adapter.py` | LIBERO env binding | LIBERO env | Unified adapter API |
| `guidance_utils.py` | Code loader | stage_guidance.txt | Callable reward fn |
| `vis_utils.py` | Visualization | Frames + keypoints | Annotated videos |
