---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/project_notes/customized_simulation_backend.md
summary: How to Add a New Simulation Backend
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/project_notes/customized_simulation_backend.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/project_notes/customized_simulation_backend.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/analysis/customized_simulation_backend.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/analysis/customized_simulation_backend.md
  - .worktrees/feat/rdt-libero-dataset_finetune/analysis/customized_simulation_backend.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/analysis/customized_simulation_backend.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/analysis/customized_simulation_backend.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/analysis/customized_simulation_backend.md
  - analysis/customized_simulation_backend.md
---

# How to Add a New Simulation Backend

This guide explains how to integrate a new simulation backend (e.g., Isaac Sim, Genesis, Gazebo) into VLA-Pilot++ using the `BaseEnvAdapter` interface.

## Overview

The adapter pattern decouples simulation backends from the rest of the system. All upper-level modules (policy steering, VLM perception, particle filtering) interact only with `BaseEnvAdapter`. Adding a new backend requires **zero changes to existing code** — only additions.

## Step-by-Step Instructions

### Step 1: Create the Adapter File

Create `core/env_adapters/<your_backend>_adapter.py` and implement all abstract methods from `BaseEnvAdapter`:

```python
import numpy as np
from .base_adapter import BaseEnvAdapter

class YourBackendAdapter(BaseEnvAdapter):

    def __init__(self, env, env_config: dict):
        super().__init__(env, env_config)
        # Backend-specific initialization here

    # --- Robot State ---
    def get_ee_pose(self) -> np.ndarray:
        # Return [x, y, z, qx, qy, qz, qw] in robot base frame
        ...

    def get_ee_pose_world(self) -> np.ndarray:
        # Return end-effector pose in world frame
        ...

    def get_robot_base_pose(self) -> np.ndarray:
        # Return robot base pose in world frame
        ...

    def get_joint_positions(self) -> np.ndarray:
        ...

    def get_gripper_state(self) -> np.ndarray:
        ...

    # --- Action Processing ---
    def delta_actions_to_ee_trajectory(self, action_sequence: np.ndarray) -> np.ndarray:
        # Convert delta action sequence to absolute EE trajectory (N x 3)
        ...

    def get_action_space_info(self) -> dict:
        ...

    def unnormalize_action(self, action: np.ndarray) -> np.ndarray:
        # Denormalize from [-1, 1] to actual action space
        ...

    # --- Camera & Perception ---
    def get_vlm_image(self) -> np.ndarray:
        # Return RGB uint8 image for VLM input
        ...

    def get_camera_params(self, camera_name: str) -> dict:
        # Return intrinsics and extrinsics
        ...

    def get_camera_names(self) -> list:
        ...

    # --- Scene Objects ---
    def get_interactable_objects(self) -> list:
        ...

    def get_scene_objects(self) -> dict:
        # Return {object_name: pose} for all tracked objects
        ...

    def get_object_pose(self, name: str) -> np.ndarray:
        ...

    def get_object_pose_by_segment(self, segment_index: int) -> np.ndarray:
        ...

    # --- Segmentation ---
    def process_segmentation(self, seg_image: np.ndarray) -> np.ndarray:
        # Filter segmentation to interactable objects only
        ...

    def get_keypoint_detection_inputs(self) -> dict:
        # Return dict with rgb, depth, point_cloud, segmentation
        ...

    # --- Policy & Task ---
    def get_policy_observation(self, sample_num: int = 1) -> dict:
        # Return observation in policy format
        ...

    def check_success(self) -> bool:
        ...

    def get_behavior_static(self) -> dict:
        ...

    def get_task_info(self) -> dict:
        # Return task-specific guidance metadata (e.g., guide_scale)
        ...

    # --- Environment ---
    def step(self, action: np.ndarray):
        ...

    def reset(self, **kwargs):
        ...

    def get_obs(self) -> dict:
        ...
```

### Step 2: Register in the Factory Function

Edit `core/env_adapters/__init__.py` and add two lines:

```python
from .your_backend_adapter import YourBackendAdapter   # add import

def create_adapter(backend: str, env_config: dict) -> BaseEnvAdapter:
    if backend == "calvin":
        env = create_calvin_env(env_config)
        return CalvinAdapter(env, env_config)
    elif backend == "libero":
        return LiberoAdapter(None, env_config)
    elif backend == "your_backend":                    # add branch
        return YourBackendAdapter(None, env_config)
    else:
        raise ValueError(f"Unknown backend: {backend}. Supported: calvin, libero, your_backend")
```

### Step 3: Add a Hydra Config File

Create `configs/env/your_backend.yaml`:

```yaml
backend: your_backend

your_backend:
  # Environment-specific parameters
  scene_path: null
  camera_name: main_camera
  max_episode_steps: 300
  vlm_camera: main_camera
  observation_width: 256
  observation_height: 256
  visualization_width: 640
  visualization_height: 640
  episode_num: 50
```

### Step 4: Run

```bash
python main.py env=your_backend
```

No other files need to be changed.

---

## Key Differences Between Existing Backends (Reference)

| Aspect | CalvinAdapter | LiberoAdapter |
|--------|--------------|---------------|
| Physics Engine | PyBullet | MuJoCo (via Robosuite) |
| Tasks | Single scene, 12 behaviors | Multi-task (10–90), auto-rotation |
| Action Scale | 0.02 m/unit, 0.05 rad/unit | 0.01 m/unit (OSC internal) |
| Cameras | 1 fixed static camera | 2 cameras (agentview + wrist) |
| Segmentation | PyBullet body_id encoding | MuJoCo geom IDs |
| Success Check | Behavior state machine | BDDL task validation |
| OOD Perturbations | None | LIBERO-PRO variants |

Use these as reference implementations when building your adapter.

---

## Correctness Check

> After adding the new backend, if you need to modify `main.py` or any policy/perception module, the adapter is incomplete — logic has leaked into the upper layers.

All backend-specific logic must be fully encapsulated inside the adapter class.
