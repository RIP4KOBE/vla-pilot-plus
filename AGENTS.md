# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project

**VLS** (Vision-Language Steering) performs inference-time adaptation of pretrained diffusion/flow-matching robot policies by using a VLM (GPT-4o or Gemini) to synthesize differentiable reward functions that steer policy sampling. No retraining is required.

## Setup

```bash
# Full one-shot setup (submodules + conda env + third-party installs)
bash setup.sh

# Or manually:
conda env create -f environment.yml && conda activate vls
cd third_party/calvin/calvin_env && pip install -e . && cd -
cd third_party/calvin/calvin_models && pip install -e . && cd -
cd third_party/lerobot && pip install -e . && cd -
cd third_party/libero_pro && pip install -e . && cd -  # optional, for LIBERO
```

Requires a `.env` file with:
```
OPENAI_API_KEY=...      # for GPT-4o VLM guidance
GOOGLE_API_KEY=...      # for Gemini grounding (optional)
HF_TOKEN=...            # for gated HuggingFace models (e.g. PaliGemma)
```

Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` to avoid GPU OOM on large particle batches.

## Running

```bash
# Default (LIBERO backend, config defaults)
python main.py

# Shorthand via run.sh: bash run.sh <backend> <task>
bash run.sh libero libero_spatial
bash run.sh calvin drawer_open

# Hydra CLI overrides
python main.py backend=calvin main.episode_num=5 main.use_guidance=true
python main.py main.guide_scale=80.0 main.sample_batch_size=20 main.MCMC_steps=4
```

There is no test suite — validation is done by running episodes and inspecting logged outputs in `outputs/`.

## Architecture

### Entry Point & Config

`main.py` is the Hydra entry point (~815 lines). It owns the outer episode loop: reset env → VLM query → keypoint detection → policy rollout. All parameters flow through Hydra configs in `configs/`.

Config hierarchy:
- `configs/config.yaml` — top-level defaults (backend, steering params, episode settings)
- `configs/perception.yaml` — keypoint detector, VLM agent, Gemini grounder, SAM
- `configs/policy.yaml` — policy type (`pi05` vs `diffusion`), pretrained path, horizon
- `configs/backend/calvin.yaml` / `libero.yaml` — simulator-specific settings
- `configs/task/calvin/*.yaml` — per-task overrides

### Core Data Flow

```
main.py
  │
  ├─ EnvAdapter (core/env_adapters/)
  │    BaseAdapter → CalvinAdapter (PyBullet) or LiberoAdapter (MuJoCo)
  │    Provides: observations, action execution, camera images, object tracking
  │
  ├─ VLM Guidance (vlm_query/vlm_agent.py)
  │    Sends scene image + task instruction to GPT-4o/Codex
  │    Receives Python reward function code executed at inference time
  │
  ├─ Perception (core/)
  │    KeypointDetector: DINO features + SAM segmentation → 3D keypoints
  │    KeypointTracker: optical-flow tracking across frames
  │    GeminiGrounder: object detection & task-stage recognition
  │
  └─ Policy Steering (core/)
       DiffusionPolicySteer or PI05PolicySteer
       Each step: sample N action particles → project to 3D → evaluate reward
       → Feynman-Kac resampling (fkd_class.py) → MCMC refinement → best action
```

### Key Abstractions

**EnvAdapter** (`core/env_adapters/base_adapter.py`) — all backends implement a common interface. Add a new simulator by subclassing `BaseAdapter`.

**Policy steering classes** (`core/diffusion_policy_steer.py`, `core/pi05_steer.py`) — wrap LeRobot policy inference and inject steering at the denoising level. Diffusion uses 100 steps; PI05 (flow-matching) uses 10 steps. Both support FK resampling via `fkd_class.py`.

**VLM-generated reward functions** — `vlm_query/vlm_agent.py` sends a template prompt and receives executable Python. `utils/guidance_utils.py` loads and validates this code. The reward is evaluated against tracked keypoint positions at each rollout step.

**Feynman-Kac (FK) resampling** (`core/fkd_class.py`) — particle filter that weights and resamples `sample_batch_size` action sequences based on the VLM reward, maintaining diversity via RBF kernel.

### Third-Party Submodules

- `third_party/calvin/` — CALVIN tabletop simulation (PyBullet)
- `third_party/lerobot/` — LeRobot policy base classes (modified fork)
- `third_party/libero_pro/` — LIBERO-PRO benchmark (MuJoCo)

Monkey-patches for third-party library compatibility live in `patches/`.

## Key Steering Parameters

| Parameter | Default | Effect |
|---|---|---|
| `main.guide_scale` | 80.0 | Gradient guidance strength |
| `main.diversity_scale` | 20.0 | RBF particle diversity weight |
| `main.sample_batch_size` | 20 | Number of FK particles |
| `main.MCMC_steps` | 4 | MCMC refinement steps per denoising step |
| `main.start_step` | 70 | Diffusion step at which to begin guidance |
| `main.use_guidance` | true | Enable/disable steering entirely |
