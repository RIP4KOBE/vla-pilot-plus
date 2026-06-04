---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/project_notes/config_analysis.md
summary: Hydra Configuration System Analysis — VLA-Pilot++
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/project_notes/config_analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/project_notes/config_analysis.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/analysis/config_analysis.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/analysis/config_analysis.md
  - .worktrees/feat/rdt-libero-dataset_finetune/analysis/config_analysis.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/analysis/config_analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/analysis/config_analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/analysis/config_analysis.md
  - analysis/config_analysis.md
---

# Hydra Configuration System Analysis — VLA-Pilot++

## Table of Contents

1. [Background: What Is Hydra?](#1-background-what-is-hydra)
2. [Alternative Configuration Systems](#2-alternative-configuration-systems)
3. [Project Configuration Architecture](#3-project-configuration-architecture)
4. [Config File Structure and Contents](#4-config-file-structure-and-contents)
5. [Key Hydra Patterns Used in This Project](#5-key-hydra-patterns-used-in-this-project)
6. [How Scripts Consume Configuration](#6-how-scripts-consume-configuration)
7. [CLI Override System](#7-cli-override-system)
8. [Custom Plugins and Extensions](#8-custom-plugins-and-extensions)
9. [Ablation Study Configs](#9-ablation-study-configs)
10. [Quick Reference](#10-quick-reference)

---

## 1. Background: What Is Hydra?

**Hydra** (developed by Meta Research, open-sourced) is a Python framework for hierarchically composing and overriding application configuration. It was designed to solve the problem of managing complex experiment configurations in ML research, where a single training or evaluation run may depend on dozens of interdependent parameters.

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Config groups** | Directories under `configs/` that each represent a "slot" (e.g., `backend/`, `task/`) — one YAML from each group is selected per run |
| **Defaults list** | A YAML key `defaults:` that specifies which config file from each group to load by default |
| **Interpolation** | `${key.path}` syntax lets one config value reference another; resolved lazily at access time |
| **OmegaConf** | The underlying config container library; Hydra returns `DictConfig` objects backed by OmegaConf |
| **Structured configs** | Python `@dataclass` classes registered with `ConfigStore`, providing type-safety and IDE completion |
| **Plugins** | Extensible via `SearchPathPlugin`, `LauncherPlugin`, `SweepPlugin`, etc. |
| **Multirun / sweeps** | `python main.py --multirun param=1,2,3` runs the app once per combination |

### How Hydra Processes a Run

```
CLI invocation
     │
     ▼
@hydra.main(config_path, config_name)
     │
     ├─ 1. Load root config (config_name.yaml)
     ├─ 2. Walk defaults list → load and merge each sub-config
     ├─ 3. Apply CLI overrides (key=value pairs)
     ├─ 4. Resolve all ${} interpolations
     └─ 5. Pass fully-merged DictConfig to your function
```

### Key Hydra Resolver Builtins

| Resolver | Example | Expands To |
|----------|---------|------------|
| `${hydra:run.dir}` | Output directory | `outputs/calvin/2025-01-15_10-30-00` |
| `${hydra.job.num}` | Current sweep job index | `0`, `1`, `2`, … |
| `${now:%Y-%m-%d}` | Current timestamp | `2025-01-15` |
| `${key.path}` | Cross-config reference | Value of another config node |

---

## 2. Alternative Configuration Systems

Understanding Hydra's position requires comparing it with common alternatives:

### 2.1 argparse (Python stdlib)

```python
# Plain argparse — flat, no hierarchy
parser = argparse.ArgumentParser()
parser.add_argument('--lr', type=float, default=1e-3)
parser.add_argument('--backend', choices=['calvin', 'libero'])
args = parser.parse_args()
```

**Pros:** Zero dependencies, universally understood.
**Cons:** No composition, no interpolation, no config file loading, combinatorial explosion for many parameters.

### 2.2 python-dotenv / environment variables

```bash
BACKEND=libero EPISODE_NUM=10 python main.py
```

**Pros:** Simple, Docker-friendly, secret-safe.
**Cons:** Strings only, no nesting, no validation, no inheritance.

### 2.3 YAML / JSON loaded manually

```python
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)
```

**Pros:** Human-readable, structured.
**Cons:** No CLI overrides, no interpolation, no composition — must build all merge logic yourself.

### 2.4 Gin-config (Google)

```python
@gin.configurable
def train(lr=1e-3, optimizer='adam'):
    ...
```

```bash
python train.py --gin_param="train.lr=1e-4"
```

**Pros:** Decorator-driven, fine-grained per-function control.
**Cons:** Non-standard syntax for gin files, harder to compose large hierarchies, less ecosystem tooling than Hydra.

### 2.5 Hydra (this project)

**Pros:** Hierarchical composition, CLI overrides, interpolation, multirun sweeps, output dir management, logging, plugins.
**Cons:** Learning curve, import-time side effects from `@hydra.main`, output directory behavior can surprise new users.

### 2.6 ML Framework Configs (e.g., mmcv, detectron2 Config)

Framework-specific config registries — tightly coupled to the framework and not reusable outside it.

### Summary Table

| Feature | argparse | dotenv | raw YAML | gin | **Hydra** |
|---------|----------|--------|----------|-----|-----------|
| CLI overrides | ✓ | — | — | ✓ | ✓ |
| Hierarchical composition | — | — | manual | partial | ✓ |
| Interpolation | — | — | — | — | ✓ |
| Type validation | — | — | — | partial | ✓ (structured) |
| Multirun sweeps | — | — | — | — | ✓ |
| Auto output dirs | — | — | — | — | ✓ |
| Config file groups | — | — | — | — | ✓ |

Hydra is the heaviest but most capable option, making it well-suited for robotics/ML experiments where you need to swap backends, tasks, policies, and hyperparameters independently.

---

## 3. Project Configuration Architecture

### Directory Layout

```
VLA-Pilot++/
├── main.py                          # @hydra.main entry point
│
├── configs/                         # config_path="configs"
│   ├── config.yaml                  # Root config (config_name="config")
│   ├── perception.yaml              # Perception module settings
│   ├── policy.yaml                  # Policy type + hyperparameters
│   │
│   ├── backend/                     # Config group: environment backend
│   │   ├── calvin.yaml              # CALVIN PyBullet setup
│   │   └── libero.yaml              # LIBERO MuJoCo setup
│   │
│   └── task/                        # Config group: per-task overrides (CALVIN)
│       └── calvin/
│           ├── button_off.yaml
│           ├── button_on.yaml
│           ├── door_left.yaml
│           ├── door_right.yaml
│           ├── drawer_open.yaml
│           ├── drawer_close.yaml
│           └── push_blue.yaml
│
├── ablations/                       # Standalone flat configs for ablation studies
│   ├── door_left_k10.yaml
│   ├── door_left_no_fkd.yaml
│   ├── door_left_no_gradient.yaml
│   └── door_left_no_rbf.yaml
│
├── scripts/
│   └── run_libero_suites.sh         # Shell script with Hydra CLI override examples
│
└── utils/
    ├── config_utils.py              # OmegaConf utilities: load, merge, resolve
    └── hydra_plugins/
        └── task_searchpath.py       # SearchPathPlugin stub
```

### Config Composition Graph

```
configs/config.yaml  (root)
       │
       │  defaults:
       ├──── backend: libero  ──────► configs/backend/libero.yaml
       │                                        │ (@package backend)
       │                                        └─ Merges under cfg.backend.*
       │
       ├──── perception  ────────────► configs/perception.yaml
       │                                        │ (@package perception)
       │                                        └─ Merges under cfg.perception.*
       │
       ├──── policy  ───────────────► configs/policy.yaml
       │                                        │ (@package policy)
       │                                        └─ Merges under cfg.policy.*
       │
       └──── _self_  ───────────────► Merge root config.yaml last
                                       (allows root to override defaults)
```

When a task is requested (e.g., `task=drawer_open`), the task config uses `@package _global_` to merge its content at the root level, selectively overriding nested values in `main.*`, `backend.calvin.*`, and `perception.*`.

---

## 4. Config File Structure and Contents

### 4.1 Root Config: `configs/config.yaml`

The root config is the entry point Hydra loads first. Its `defaults:` list drives composition:

```yaml
defaults:
  - backend: libero       # Load configs/backend/libero.yaml (swappable via CLI)
  - perception            # Load configs/perception.yaml
  - policy                # Load configs/policy.yaml
  - _self_                # Merge this file's own keys last (highest priority)

# Global scalars — referenced by children via ${device}, ${seed}
device: cuda
seed: 0

main:
  episode_num: 10
  output_dir: ${hydra:run.dir}      # Hydra resolver: runtime output path
  use_guidance: false
  use_vlm_stage_recognition: true
  use_fkd: true
  guide_scale: 80.0
  diversity_scale: 20.0
  MCMC_steps: 4
  fkd:
    potential_type: max
    lmbda: 10.0
    adaptive_resampling: true
    resample_frequency: 5

experiment:
  name: ${backend.backend}          # Cross-group interpolation
  tags:
    - ${backend.backend}

hydra:
  run:
    dir: outputs/${experiment.name}/${now:%Y-%m-%d_%H-%M-%S}
  sweep:
    dir: outputs/${experiment.name}/multirun/${now:%Y-%m-%d_%H-%M-%S}
    subdir: ${hydra.job.num}
  job:
    chdir: false
```

**Design notes:**
- `_self_` appearing last in the defaults list means the root config's keys win over sub-configs — the opposite of the Hydra default (which puts `_self_` first).
- `${hydra:run.dir}` lets child code reference where Hydra put this run's output without hardcoding paths.
- `experiment.name` derived from `backend.backend` means the output directory automatically encodes which environment was used.

---

### 4.2 Backend Configs: `configs/backend/`

Each file begins with `# @package backend`, which tells Hydra to merge its contents under the `backend` key in the merged config (so `cfg.backend.backend`, `cfg.backend.calvin.*`, etc.).

#### `configs/backend/libero.yaml`

```yaml
# @package backend
backend: libero

libero:
  suite_name: libero_object     # libero_goal | libero_spatial | libero_object | libero_10
  task_id: 0
  camera_name: agentview_image, robot0_eye_in_hand_image
  obs_type: pixels_agent_pos
  observation_width: 256
  visualization_width: 640
  vlm_camera: agentview
  auto_apply_perturbations: true
  task_ids_filter: null
```

The minimal, flat structure reflects LIBERO's simpler API: a suite name and task ID are enough to initialize an environment.

#### `configs/backend/calvin.yaml`

```yaml
# @package backend
backend: calvin

calvin:
  id: PlayTableSimEnv
  type: 2
  seed: ${seed}              # Interpolation: inherits global seed
  show_gui: ${main.render}   # Interpolation: linked to render flag

  robot_cfg:
    _target_: calvin_env.robot.robot.Robot   # Hydra instantiation marker
    filename: franka_panda/panda_longer_finger.urdf
    base_position: [-0.34, -0.46, 0.24]
    # ... further robot parameters

  cameras:
    static:
      _target_: calvin_env.camera.static_camera.StaticCamera
      name: static
      # ... camera parameters
    gripper:
      _target_: calvin_env.camera.gripper_camera.GripperCamera
      # ...

  scene_cfg:
    _target_: calvin_env.scene.play_table_scene.PlayTableScene
    _recursive_: false        # Do NOT recursively instantiate nested dicts
    # ... scene parameters
```

CALVIN's config is substantially more complex because the environment's full class hierarchy — robot, cameras, scene — is defined here. The `_target_` fields enable `hydra.utils.instantiate(cfg.backend.calvin.robot_cfg)` to construct the robot object directly from config without any bespoke factory code. The `_recursive_: false` flag prevents Hydra from trying to instantiate nested `_target_` dicts automatically (leaving that control to the adapter code).

---

### 4.3 Perception Config: `configs/perception.yaml`

```yaml
# @package perception
keypoint_detector:
  num_candidates_per_mask: 5
  min_dist_bt_keypoints: 0.05
  max_mask_ratio: 0.5
  device: ${device}           # Inherits global device
  seed: ${seed}
  bounds_min: [-1.0, -0.75, -0.1]
  bounds_max: [1.00, 0.75, 1.2]
  feature_extractor: dinov3_vitb16

vlm_agent:
  [redacted endpoint field]: null
  model: gpt-5.1
  [redacted credential field]: null
  temperature: 1.0
  max_completion_tokens: 2000
  query_template_dir: vlm_query/

sam3:
  enabled: false

gemini_grounding:
  enabled: true
  [redacted credential field]: null
  model: gemini-3-flash-preview
  default_objects:
    - drawer handle
    - slider handle
    - black switch
    - red cube
    - blue cube
    - pink cube

gemini:
  [redacted credential field]: null
  model: gemini-3-flash-preview
```

Keeping perception in a separate file allows it to be swapped or extended independently of the environment backend. Tasks can also partially override `gemini_grounding.default_objects` without touching the rest of perception.

---

### 4.4 Policy Config: `configs/policy.yaml`

```yaml
# @package policy
type: pi05    # Active policy: "diffusion" | "pi05"

diffusion:
  pretrained_path: /path/to/model
  num_inference_steps: 100
  n_obs_steps: 2
  action_chunk_horizon: 16

pi05:
  pretrained_path: lerobot/pi05_libero_finetuned_v044
  num_inference_steps: 10
  action_chunk_horizon: 10
```

Both policy types are defined side-by-side; `type` acts as a selector. The code reads `policy.type` and then accesses `policy[type]` to get the relevant sub-config. Switching the policy at runtime requires only `python main.py policy.type=diffusion`.

---

### 4.5 Task Configs: `configs/task/calvin/`

Task configs use `@package _global_` to merge at the root, enabling selective overrides of deeply nested values across multiple config groups in a single file.

#### Example: `configs/task/calvin/drawer_open.yaml`

```yaml
# @package _global_
task:
  name: drawer_open
  backend: calvin

main:
  instruction: "open the drawer"

backend:
  calvin:
    target_behavior: drawer_open
    scene_cfg:
      objects:
        fixed_objects:
          table:
            joints:
              base__drawer: {initial_state: 0.0}  # Drawer starts closed

perception:
  gemini_grounding:
    default_objects:
      - drawer handle
      - drawer interior
```

This single file overrides `main.instruction`, `backend.calvin.target_behavior`, an initial joint state deep inside the scene graph, and the list of objects the VLM should look for — all in one place. Without `@package _global_`, Hydra would try to merge this config under the `task/calvin` namespace instead.

---

## 5. Key Hydra Patterns Used in This Project

### 5.1 Defaults List Composition

```yaml
defaults:
  - backend: libero     # config group = backend, selected option = libero
  - perception          # no group prefix → loads perception.yaml directly
  - _self_
```

The `backend` group allows swapping the entire backend with a single CLI flag: `backend=calvin`. Non-grouped entries like `perception` load their YAML unconditionally (no swapping).

### 5.2 Package Directives (`@package`)

| Directive | Where Used | Effect |
|-----------|-----------|--------|
| `@package backend` | `backend/*.yaml` | Keys land under `cfg.backend.*` |
| `@package perception` | `perception.yaml` | Keys land under `cfg.perception.*` |
| `@package policy` | `policy.yaml` | Keys land under `cfg.policy.*` |
| `@package _global_` | `task/calvin/*.yaml` | Keys land at the root of `cfg` |

Without package directives, Hydra places config group content under the group name by default. Explicit `@package` declarations make the merge target explicit and stable.

### 5.3 Cross-Config Interpolation

```yaml
# In perception.yaml — references root-level values
keypoint_detector:
  device: ${device}
  seed: ${seed}

# In config.yaml — references content from backend group
experiment:
  name: ${backend.backend}

# Hydra special resolver
hydra:
  run:
    dir: outputs/${experiment.name}/${now:%Y-%m-%d_%H-%M-%S}
```

Interpolations are evaluated lazily; if `device` changes via CLI override, every field referencing `${device}` updates automatically.

### 5.4 `_target_` and `hydra.utils.instantiate`

The `_target_` key is a Hydra/OmegaConf convention that marks a config node for object instantiation:

```yaml
robot_cfg:
  _target_: calvin_env.robot.robot.Robot
  filename: franka_panda/panda_longer_finger.urdf
  base_position: [-0.34, -0.46, 0.24]
```

```python
from hydra.utils import instantiate
robot = instantiate(cfg.backend.calvin.robot_cfg)
# Equivalent to: Robot(filename="franka...", base_position=[...])
```

`_recursive_: false` on `scene_cfg` tells Hydra not to recursively instantiate nested `_target_` fields automatically — the adapter calls `instantiate` selectively instead.

### 5.5 OmegaConf Operations in Code

| Operation | Code | Purpose |
|-----------|------|---------|
| Resolve + convert | `OmegaConf.to_container(cfg.backend.libero, resolve=True)` | Convert to plain dict, resolving all `${}` |
| Merge configs | `OmegaConf.merge(base_cfg, task_cfg)` | Overlay task config onto base |
| YAML dump | `OmegaConf.to_yaml(cfg, resolve=True)` | Serialize for logging |
| Safe access | `cfg.get('seed', 0)` | Access with a default value |
| Direct access | `cfg.backend.backend` | Attribute-style access (raises on missing) |

---

## 6. How Scripts Consume Configuration

### 6.1 Main Entry Point (`main.py`)

```python
@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    env_backend = cfg.backend.backend          # "calvin" or "libero"

    env_config = OmegaConf.to_container(
        cfg.backend.get(env_backend, {}),
        resolve=True                           # Expand ${} before converting
    )

    policy_type = cfg.policy.get('type', 'pi05')
    type_config = cfg.policy.get(policy_type, {})
    pretrained_path = type_config.get('pretrained_path')
```

**`version_base=None`** opts into the latest Hydra behavior (Hydra 1.2+ semantics), avoiding deprecation warnings from older version defaults.

**`config_path="configs"`** is resolved relative to the script's location at startup, not the process working directory.

### 6.2 Dynamic Task Config Loading (`utils/config_utils.py`)

Some task configs are not in the Hydra defaults list and are instead loaded and merged at runtime:

```python
def load_task_config(env_backend: str, task_name: str) -> Optional[DictConfig]:
    config_dir = get_config_dir()
    task_path = config_dir / "task" / env_backend / f"{task_name}.yaml"
    return OmegaConf.load(task_path)   # Load outside of Hydra machinery

def merge_task_config(cfg: DictConfig, task_name: str) -> DictConfig:
    task_cfg = load_task_config(cfg.backend.backend, task_name)
    return OmegaConf.merge(cfg, task_cfg)   # Overlay on top of current cfg
```

This bypasses Hydra's defaults list mechanism, which is appropriate when task names are determined at runtime (e.g., iterating over a LIBERO suite) rather than at process startup.

### 6.3 Adapter Factory Using Config

```python
def create_adapter(backend: str, env_config: dict, **kwargs):
    if backend == "calvin":
        env = create_calvin_env(env_config)
        return CalvinAdapter(env, env_config, **kwargs)
    elif backend == "libero":
        return LiberoAdapter(None, env_config, **kwargs)
```

The factory receives a plain Python dict (post-`to_container`) rather than a `DictConfig`, decoupling the adapter implementations from Hydra's type system.

---

## 7. CLI Override System

Hydra intercepts command-line arguments before `argparse` can see them. The override grammar follows these rules:

### 7.1 Override Syntax

| Intent | Syntax | Example |
|--------|--------|---------|
| Swap config group | `group=option` | `backend=calvin` |
| Override scalar | `key.path=value` | `main.episode_num=50` |
| Override string | `key="value"` | `main.instruction="push the block"` |
| Override list | `key=[a,b,c]` | `backend.libero.task_ids_filter=[0,2,4]` |
| Add new key | `+key=value` | `+debug=true` |
| Force override | `++key=value` | `++new_group.param=1` (add if missing, override if present) |
| Multirun sweep | `--multirun key=a,b,c` | `--multirun backend.libero.suite_name=libero_goal,libero_spatial` |

### 7.2 Real Examples from This Project

From `scripts/run_libero_suites.sh`:

```bash
# Override backend group and a nested string
python main.py backend=libero backend.libero.suite_name="libero_goal"

# Override multiple scalars
python main.py backend=libero \
    backend.libero.suite_name="libero_spatial" \
    main.episode_num=50 \
    main.guide_scale=120

# Filter specific task IDs (list syntax)
python main.py backend.libero.task_ids_filter=[0,2,4,8]
```

From README usage examples:

```bash
# Default run
python main.py

# Switch backend and load task config via defaults list
python main.py backend=calvin task=drawer_open

# Ablation: disable guidance
python main.py main.use_guidance=false

# Switch policy
python main.py policy.type=diffusion

# Full run with task + guidance enabled
python main.py backend=calvin task=door_left main.use_guidance=true main.guide_scale=80
```

### 7.3 Config Group vs. Parameter Override

A key distinction: `backend=calvin` swaps the *entire* backend config file (loading all of `backend/calvin.yaml`), whereas `backend.calvin.seed=42` overrides a single *value* within the already-selected backend config. These can be combined:

```bash
python main.py backend=calvin backend.calvin.seed=99 main.episode_num=20
```

---

## 8. Custom Plugins and Extensions

### 8.1 SearchPath Plugin (`utils/hydra_plugins/task_searchpath.py`)

```python
from hydra.plugins.search_path_plugin import SearchPathPlugin
from hydra.core.config_search_path import ConfigSearchPath

class TaskSearchPathPlugin(SearchPathPlugin):
    """
    Extends Hydra's config search path based on the active backend.
    Goal: allow `task=drawer_open` instead of `task/calvin=drawer_open`
    when the backend is set to calvin.
    """
    def manipulate_search_path(self, search_path: ConfigSearchPath) -> None:
        # Implementation stub — not yet active
        pass
```

This plugin is discovered automatically by Hydra via Python entry points if registered in `setup.py` or `pyproject.toml` under `hydra.searchpath`. Currently a stub, its intent is to dynamically inject the environment-specific task config directory into the search path so that task names need not be prefixed with the backend name.

### 8.2 Resolvers Used

The project relies exclusively on Hydra's built-in resolvers — no `OmegaConf.register_new_resolver()` calls were found:

| Resolver | Used in | Example value |
|----------|---------|---------------|
| `${key.path}` | All YAML files | Value of a sibling/ancestor config key |
| `${hydra:run.dir}` | `config.yaml` | `outputs/libero/2025-01-15_10-30-00` |
| `${now:FORMAT}` | `config.yaml` | `2025-01-15_10-30-00` |
| `${hydra.job.num}` | `config.yaml` (sweep) | `0`, `1`, `2`, … |

---

## 9. Ablation Study Configs

The `ablations/` directory holds standalone flat configs — *not* part of the Hydra defaults hierarchy. They are self-contained YAML files with full configs and use standard YAML anchors for deduplication:

```yaml
# ablations/door_left_k10.yaml
device: &device 'cuda'
seed: &seed 0

main:
  sample_batch_size: 10        # k=10 particles (ablation variable)
  guide_scale: 80.0
  diversity_scale: 10.0
  use_fkd: true

env:
  calvin:
    target_behavior: "door_left"
    robot_cfg:
      _target_: calvin_env.robot.robot.Robot
      # ... full config repeated here
```

**YAML anchors/aliases** (`&device`, `*device`) allow one value to be defined once and referenced multiple times within the same file — a YAML-native alternative to Hydra's `${}` interpolation that works without Hydra being involved.

These configs are loaded via `OmegaConf.load()` directly (not through `@hydra.main`) for one-off ablation runs or for programmatic sweep scripts.

**Differences from main configs:**

| Aspect | Main configs (Hydra) | Ablation configs |
|--------|---------------------|-----------------|
| Entry | `@hydra.main` decorator | `OmegaConf.load()` directly |
| Composition | Defaults list + groups | Single flat file |
| Interpolation | `${key}` OmegaConf | YAML anchors `&`/`*` |
| CLI overrides | Full Hydra override grammar | Manual argument parsing |
| Output dirs | Auto-managed by Hydra | Must handle manually |

---

## 10. Quick Reference

### Config File → Runtime Key Mapping

| File | `@package` | Keys appear at |
|------|-----------|---------------|
| `configs/config.yaml` | (root) | `cfg.*` |
| `configs/backend/libero.yaml` | `backend` | `cfg.backend.*` |
| `configs/backend/calvin.yaml` | `backend` | `cfg.backend.*` |
| `configs/perception.yaml` | `perception` | `cfg.perception.*` |
| `configs/policy.yaml` | `policy` | `cfg.policy.*` |
| `configs/task/calvin/*.yaml` | `_global_` | `cfg.*` (root-level merge) |

### Common CLI Commands

```bash
# Run with LIBERO backend, goal suite, 50 episodes
python main.py backend=libero backend.libero.suite_name=libero_goal main.episode_num=50

# Run with CALVIN, drawer task, guidance enabled
python main.py backend=calvin task=drawer_open main.use_guidance=true main.guide_scale=80

# Multirun sweep over suites
python main.py --multirun backend.libero.suite_name=libero_goal,libero_spatial,libero_object

# Override policy type
python main.py policy.type=diffusion policy.diffusion.num_inference_steps=50

# Disable FKD for ablation
python main.py main.use_fkd=false
```

### Python Config Access Cheatsheet

```python
# Nested read
cfg.backend.backend          # "libero" or "calvin"
cfg.policy.type              # "pi05" or "diffusion"
cfg.main.guide_scale         # 80.0

# Safe read with default
cfg.get('seed', 0)
cfg.main.get('render', False)

# Convert to plain dict (resolves interpolations)
d = OmegaConf.to_container(cfg.backend.libero, resolve=True)

# Log full config
print(OmegaConf.to_yaml(cfg, resolve=True))

# Merge task override at runtime
merged = OmegaConf.merge(cfg, task_cfg)

# Instantiate object from _target_ node
from hydra.utils import instantiate
robot = instantiate(cfg.backend.calvin.robot_cfg)
```

---

*Analysis written against the VLA-Pilot++ codebase as of April 2026.*
