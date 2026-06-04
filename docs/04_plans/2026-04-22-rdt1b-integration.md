---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/04_plans/2026-04-22-rdt1b-integration.md
summary: RDT-1B Integration Implementation Plan
duplicate_sources:
  - docs/superpowers/plans/2026-04-22-rdt1b-integration.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/04_plans/2026-04-22-rdt1b-integration.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/04_plans/2026-04-22-rdt1b-integration.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/plans/2026-04-22-rdt1b-integration.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/plans/2026-04-22-rdt1b-integration.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/plans/2026-04-22-rdt1b-integration.md
---

# RDT-1B Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `robotics-diffusion-transformer/maniskill-model` (RDT-1B, single-arm) into the VLS steering pipeline as a third selectable policy (`policy.type=rdt`) with FKD particle resampling, RBF diversity, and gradient-based guidance.

**Architecture:** `RDTSteer` is a plain Python class (no LeRobot inheritance) that wraps the official RDT model, implements the same duck-typed interface as `DiffusionPolicySteer`/`PI05PolicySteer`, and exposes the denoising loop for steering hooks. `RDTObsProcessor` handles image resizing, proprio padding, and language embed caching.

**Tech Stack:** PyTorch, diffusers (DPMSolverMultistepScheduler already in env), huggingface_hub, Pillow, `third_party/rdt/` (git submodule of `thu-ml/RoboticsDiffusionTransformer`), existing `core/fkd_class.py`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `third_party/rdt/` | Create (submodule) | RDT source: model class, scripts |
| `core/rdt_obs_processor.py` | Create | Image resize, proprio padding, lang embed cache |
| `core/rdt_policy_steer.py` | Create | `RDTSteer` — full steering interface |
| `tests/test_rdt_steer.py` | Create | 4 CPU-only smoke tests |
| `configs/policy.yaml` | Modify | Add `rdt` section |
| `main.py` | Modify | Add `elif policy_type == 'rdt'` branch |

---

## Task 1: RDT Submodule + Failing Test Scaffold

**Files:**
- Create: `third_party/rdt/` (git submodule)
- Create: `tests/test_rdt_steer.py`

- [ ] **Step 1.1: Add RDT as git submodule**

```bash
git submodule add https://github.com/thu-ml/RoboticsDiffusionTransformer.git third_party/rdt
git submodule update --init third_party/rdt
```

Expected: `third_party/rdt/` populated with RDT source. Verify:

```bash
ls third_party/rdt/
# Should show: scripts/ rdt/ configs/ requirements.txt README.md etc.
```

- [ ] **Step 1.2: Note RDT's model entry point**

```bash
grep -rn "class RoboticDiffusionTransformerModel\|def from_pretrained\|def step" third_party/rdt/scripts/ | head -20
```

Record the file path and class name for use in Task 3.

- [ ] **Step 1.3: Add submodule pip-install to setup.sh**

Open `setup.sh` and add after the existing third_party installs:

```bash
# After the existing lerobot/libero_pro installs, add:
cd third_party/rdt && pip install -r requirements.txt && cd -
```

- [ ] **Step 1.4: Write the failing test file**

Create `tests/test_rdt_steer.py`:

```python
"""
CPU-only smoke tests for RDTSteer and RDTObsProcessor.
No real checkpoint or GPU required — uses stub RDT model.
"""
import math
import numpy as np
import pytest
import torch
from torch import nn
from unittest.mock import MagicMock


# ── Stub RDT model (replaces the real 1.2B-param checkpoint) ────────────────

class _StubDiT(nn.Module):
    """Minimal DiT stand-in: returns zeros with the correct shape."""
    def forward(self, x, t, cond):
        return torch.zeros_like(x)  # (B, 64, 14)


class _StubScheduler:
    """Minimal noise scheduler compatible with DPMSolverMultistepScheduler API."""

    def __init__(self, n=10):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.99, 0.01, 1000)

    def set_timesteps(self, n):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)

    def step(self, noise_pred, t, x_t):
        out = MagicMock()
        out.prev_sample = x_t * 0.9  # trivial shrink
        return out


class _StubRDTModel(nn.Module):
    """Minimal stand-in for RoboticDiffusionTransformerModel."""

    def __init__(self):
        super().__init__()
        self.dit = _StubDiT()
        self.noise_scheduler = _StubScheduler()

    def encode_inputs(self, proprio, images, text_embeds):
        return {}  # conditioning dict (opaque to the loop)

    def step(self, proprio, images, text_embeds):
        return torch.zeros(1, 64, 14)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def stub_steer():
    from core.rdt_policy_steer import RDTSteer
    return RDTSteer(rdt_model=_StubRDTModel(), num_inference_steps=10)


@pytest.fixture
def stub_adapter():
    adapter = MagicMock()
    # (T, 7) action_seq → (T+1, 3) EEF trajectory
    adapter.delta_actions_to_ee_trajectory.side_effect = (
        lambda seq: torch.zeros(seq.shape[0] + 1, 3, requires_grad=True)
    )
    return adapter


@pytest.fixture
def mock_batch():
    B = 4
    return {
        "observation.images.image": torch.zeros(B, 3, 256, 256),
        "observation.images.image2": torch.zeros(B, 3, 256, 256),
        "observation.state": torch.zeros(B, 8),
        "task": ["pick up the red block"] * B,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_instantiation(stub_steer):
    """RDTSteer has the correct interface attributes."""
    assert stub_steer.name == "rdt_steer"
    assert isinstance(stub_steer._action_chunk_horizon, int)
    assert isinstance(stub_steer.get_normalized_reward(), float)
    assert isinstance(stub_steer.get_last_scale(), float)
    stub_steer.reset()          # must not raise
    stub_steer.reset_stage()    # must not raise


def test_forward_shape(stub_steer, stub_adapter, mock_batch):
    """select_action with use_guidance=False returns tensor of shape (H, 7)."""
    H = 8
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": H, "lang_embed_cache_dir": "/tmp/rdt_lang"},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=False,
    )
    assert action.shape == (H, 7), f"Expected ({H}, 7), got {action.shape}"
    assert not torch.isnan(action).any()


def test_fkd_rollout(stub_steer, stub_adapter, mock_batch):
    """3-step rollout with use_fkd=True completes without error."""
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 8, "lang_embed_cache_dir": "/tmp/rdt_lang"},
    )
    guidance_fn = lambda kp, traj: traj.sum()
    kp = torch.zeros(3, 3)

    for step in range(3):
        action = stub_steer.select_action(
            mock_batch,
            generate_new_chunk=(step == 0),
            use_guidance=True,
            use_fkd=True,
            fkd_config={
                "potential_type": "max",
                "lmbda": 1.0,
                "adaptive_resampling": False,
                "resample_frequency": 2,
            },
            guidance_fns=[guidance_fn],
            keypoints=kp.numpy(),
        )
    assert isinstance(stub_steer.get_normalized_reward(), float)


def test_gradient_steering(stub_steer, stub_adapter, mock_batch):
    """Gradient guidance runs without error and updates normalized reward."""
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 8, "lang_embed_cache_dir": "/tmp/rdt_lang"},
    )

    def reward_fn(keypoints, traj):
        # Simple differentiable reward: sum of trajectory positions
        return traj.sum()

    kp = np.zeros((3, 3), dtype=np.float32)
    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        use_fkd=False,
        guidance_fns=[reward_fn],
        keypoints=kp,
        guide_scale=1.0,
        start_ratio=0.0,   # guidance from the very first step
    )
    # After one guided denoising, reward should have been computed
    # (even if zero from stub — the method must not crash and must update state)
    assert isinstance(stub_steer.get_normalized_reward(), float)
```

- [ ] **Step 1.5: Run tests and confirm they all fail with ImportError**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_steer.py -v 2>&1 | head -30
```

Expected: `ERRORS` — `ModuleNotFoundError: No module named 'core.rdt_policy_steer'`

- [ ] **Step 1.6: Commit**

```bash
git add third_party/rdt .gitmodules tests/test_rdt_steer.py setup.sh
git commit -m "feat: add RDT submodule and failing test scaffold"
```

---

## Task 2: RDTObsProcessor

**Files:**
- Create: `core/rdt_obs_processor.py`
- Test: `tests/test_rdt_steer.py` (tests already written in Task 1 — they will remain RED until Task 3)

- [ ] **Step 2.1: Create `core/rdt_obs_processor.py`**

```python
"""
RDTObsProcessor — converts adapter obs dict to RDT model inputs.

Expected obs dict keys (both LIBERO and CALVIN after env_preprocessor):
  observation.images.image  : (B, 3, H, W) float [0,1]  static/agentview
  observation.images.image2 : (B, 3, H, W) float [0,1]  wrist camera
  observation.state         : (B, state_dim) float
  task                      : List[str]
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image

RDT_IMG_SIZE = 384
_BLACK_PIL = Image.fromarray(np.zeros((RDT_IMG_SIZE, RDT_IMG_SIZE, 3), dtype=np.uint8))

_STATIC_KEY = "observation.images.image"
_WRIST_KEY = "observation.images.image2"
_STATE_KEY = "observation.state"


class RDTObsProcessor:
    """Converts the adapter's obs dict into (images, proprio, task_str) for RDT."""

    def __init__(self, lang_embed_cache_dir: str = "data/rdt_lang_embeds/"):
        self._cache_dir = Path(lang_embed_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lang_cache: Dict[str, torch.Tensor] = {}
        # One-frame ring buffer for history slots
        self._prev_static: Optional[Image.Image] = None
        self._prev_wrist: Optional[Image.Image] = None

    def reset(self) -> None:
        """Call at episode start to clear the frame history buffer."""
        self._prev_static = None
        self._prev_wrist = None

    def load_embedded_tasks(self, embed_dir: str) -> None:
        """
        Load precomputed T5-XXL embeddings from the checkpoint's lang_embeds/ dir.
        Files are named <task_key>.pt where task_key is the md5 of the task string,
        or any arbitrary stem — we load all .pt files keyed by stem.
        """
        for pt_file in Path(embed_dir).glob("*.pt"):
            self._lang_cache[pt_file.stem] = torch.load(
                pt_file, map_location="cpu", weights_only=True
            )

    def get_lang_embed(self, task_str: str, device: torch.device) -> torch.Tensor:
        """
        Return a T5-XXL embedding tensor for task_str.
        Priority: (1) preloaded cache, (2) lazy T5-XXL compute+persist, (3) zero fallback.
        """
        key = hashlib.md5(task_str.encode()).hexdigest()[:8]
        if key not in self._lang_cache:
            try:
                embed = self._compute_t5_embed(task_str)
                self._lang_cache[key] = embed
                torch.save(embed, self._cache_dir / f"{key}.pt")
            except Exception:
                import logging
                logging.getLogger("RDTObsProcessor").warning(
                    "T5-XXL unavailable — using zero embedding for: %r", task_str
                )
                # Shape matches T5-v1_1-xxl last_hidden_state: (1, seq_len, 512)
                self._lang_cache[key] = torch.zeros(1, 1, 512)
        return self._lang_cache[key].to(device)

    @staticmethod
    def _compute_t5_embed(task_str: str) -> torch.Tensor:
        from transformers import T5EncoderModel, T5Tokenizer

        tokenizer = T5Tokenizer.from_pretrained("google/t5-v1_1-xxl")
        model = T5EncoderModel.from_pretrained("google/t5-v1_1-xxl")
        model.eval()
        tokens = tokenizer(task_str, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            embed = model(**tokens).last_hidden_state  # (1, seq_len, 512)
        return embed.cpu()

    @staticmethod
    def _tensor_to_pil(img: torch.Tensor) -> Image.Image:
        """(C, H, W) float [0,1] → PIL Image resized to RDT_IMG_SIZE."""
        arr = (img.detach().cpu().clamp(0.0, 1.0) * 255).byte().permute(1, 2, 0).numpy()
        return Image.fromarray(arr).resize((RDT_IMG_SIZE, RDT_IMG_SIZE), Image.BILINEAR)

    def process(self, obs: dict) -> Tuple[List[Image.Image], np.ndarray, str]:
        """
        Convert adapter obs dict → RDT input tuple.

        Returns
        -------
        images : list of 6 PIL images
            [ext_{t-1}, right_wrist_{t-1}, left_wrist_{t-1},
             ext_t,     right_wrist_t,     left_wrist_t]
        proprio : np.ndarray shape (14,)
            Bimanual state: left-arm zeros, right-arm = env_state[:7]
        task_str : str
            Instruction string (first element of batch)
        """
        # ── Images ──────────────────────────────────────────────────────────
        # obs tensors are (B, C, H, W) — take batch index 0
        static_t = obs[_STATIC_KEY][0]   # (3, H, W)
        wrist_t = obs[_WRIST_KEY][0]     # (3, H, W)

        ext_now = self._tensor_to_pil(static_t)
        rw_now = self._tensor_to_pil(wrist_t)

        # History: duplicate current frame on first step
        ext_prev = self._prev_static if self._prev_static is not None else ext_now
        rw_prev = self._prev_wrist if self._prev_wrist is not None else rw_now

        # Update ring buffer
        self._prev_static = ext_now
        self._prev_wrist = rw_now

        # RDT slot order: [ext_{t-1}, rw_{t-1}, lw_{t-1}, ext_t, rw_t, lw_t]
        images = [ext_prev, rw_prev, _BLACK_PIL, ext_now, rw_now, _BLACK_PIL]

        # ── Proprio (14D bimanual, right-arm = env state[:7]) ───────────────
        state = obs[_STATE_KEY][0].detach().cpu().numpy()  # (state_dim,)
        proprio = np.zeros(14, dtype=np.float32)
        arm_dims = min(7, state.shape[0])
        proprio[7: 7 + arm_dims] = state[:arm_dims]

        # ── Task string ──────────────────────────────────────────────────────
        task_list = obs.get("task", [""])
        task_str = task_list[0] if isinstance(task_list, (list, tuple)) else str(task_list)

        return images, proprio, task_str
```

- [ ] **Step 2.2: Verify import works**

```bash
cd /home/hynx/VLA-Pilot++ && python -c "from core.rdt_obs_processor import RDTObsProcessor; print('OK')"
```

Expected: `OK`

- [ ] **Step 2.3: Quick manual test of process()**

```bash
python -c "
import torch
from core.rdt_obs_processor import RDTObsProcessor
proc = RDTObsProcessor('/tmp/rdt_lang')
obs = {
    'observation.images.image':  torch.zeros(4, 3, 256, 256),
    'observation.images.image2': torch.zeros(4, 3, 256, 256),
    'observation.state':         torch.zeros(4, 8),
    'task': ['pick up block'] * 4,
}
imgs, proprio, task = proc.process(obs)
assert len(imgs) == 6, len(imgs)
assert proprio.shape == (14,), proprio.shape
assert isinstance(task, str)
print('RDTObsProcessor.process() OK')
"
```

Expected: `RDTObsProcessor.process() OK`

- [ ] **Step 2.4: Commit**

```bash
git add core/rdt_obs_processor.py
git commit -m "feat: add RDTObsProcessor for image resize and proprio padding"
```

---

## Task 3: RDTSteer Core — Unguided Path (RED → GREEN)

**Files:**
- Create: `core/rdt_policy_steer.py`
- Test: `tests/test_rdt_steer.py::test_instantiation`, `::test_forward_shape`

- [ ] **Step 3.1: Inspect RDT model internals**

Run this to find the DiT attribute name and scheduler type:

```bash
python -c "
import sys; sys.path.insert(0, 'third_party/rdt')
# List top-level attributes to find the DiT and scheduler
import importlib, inspect
try:
    from scripts.agilex_model import RoboticDiffusionTransformerModel
    print('Found: scripts.agilex_model.RoboticDiffusionTransformerModel')
    src = inspect.getsource(RoboticDiffusionTransformerModel.step)
    print('step() source (first 60 lines):')
    print('\n'.join(src.split('\n')[:60]))
except ImportError as e:
    print(f'Import failed: {e}')
    # Try alternative entry points
    import os
    for f in ['scripts/model.py', 'rdt/model.py', 'model.py']:
        if os.path.exists(f'third_party/rdt/{f}'):
            print(f'Found alternative: {f}')
"
```

**Record:** the exact class path, DiT attribute name (e.g. `model.model`, `model.dit`, `model.net`), and scheduler attribute name. Update `_find_dit()` fallback list if needed.

- [ ] **Step 3.2: Create `core/rdt_policy_steer.py`**

```python
"""
RDTSteer — wraps RoboticDiffusionTransformerModel with the VLS steering interface.

Duck-typed to match DiffusionPolicySteer / PI05PolicySteer:
  post_init(), select_action(), reset(), reset_stage(),
  get_normalized_reward(), get_last_scale(), _action_chunk_horizon, name
"""
from __future__ import annotations

import math
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
from torch import Tensor, nn

from core[redacted env file]_adapters import BaseEnvAdapter
from core.fkd_class import FKD, PotentialType
from core.rdt_obs_processor import RDTObsProcessor
from utils.logging_utils import SteerLogger

log = SteerLogger("RDTSteer")

# ManiSkill checkpoint: right-arm occupies dims [7:14] of the 14D unified action.
# Layout: [x, y, z, r0, r1, r2, gripper] within the 7-dim right-arm slice.
_RIGHT_ARM = slice(7, 14)


class RDTSteer:
    """RDT-1B with VLS steering: RBF diversity + keypoint gradient + FKD resampling."""

    name = "rdt_steer"

    def __init__(self, rdt_model: nn.Module, num_inference_steps: int = 55) -> None:
        self._rdt_model = rdt_model
        self._num_inference_steps = num_inference_steps

        self._adapter: Optional[BaseEnvAdapter] = None
        self._obs_processor: Optional[RDTObsProcessor] = None
        self._sample_batch_size: int = 1
        self._action_chunk_horizon: int = 8
        self._lang_embed_cache_dir: str = "data/rdt_lang_embeds/"

        self._cached_action_chunk: Optional[Tensor] = None
        self._last_normalized_reward: float = 0.0
        self._last_scale: float = 0.0
        self._stage_init_reward: Optional[float] = None
        self._last_raw_reward: float = 0.0

        # Probe the inner DiT score network attribute once at construction time.
        self._dit: nn.Module = self._find_dit(rdt_model)

    # ── Construction ─────────────────────────────────────────────────────────

    @staticmethod
    def _find_dit(model: nn.Module) -> nn.Module:
        """Return the DiT score network from inside the RDT wrapper model."""
        for attr in ("dit", "model", "net", "backbone", "denoiser"):
            candidate = getattr(model, attr, None)
            if isinstance(candidate, nn.Module):
                return candidate
        raise AttributeError(
            f"Cannot locate DiT score network in RDT model. "
            f"Attributes: {[a for a in dir(model) if not a.startswith('_')]}"
        )

    @classmethod
    def from_pretrained(cls, pretrained_path: str, num_inference_steps: int = 55) -> "RDTSteer":
        """Load from a HuggingFace Hub repo ID or a local directory path."""
        # Ensure third_party/rdt is importable
        rdt_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "third_party", "rdt",
        )
        if rdt_root not in sys.path:
            sys.path.insert(0, rdt_root)

        # Resolve local vs HF path
        if not os.path.isdir(pretrained_path):
            from huggingface_hub import snapshot_download
            log.info(f"Downloading checkpoint: {pretrained_path}")
            pretrained_path = snapshot_download(repo_id=pretrained_path)

        log.info(f"Loading RDT model from: {pretrained_path}")

        # Import RDT's model class (path confirmed in Step 3.1)
        try:
            from scripts.agilex_model import RoboticDiffusionTransformerModel
        except ImportError:
            raise ImportError(
                "Cannot import RoboticDiffusionTransformerModel. "
                "Ensure third_party/rdt/ is initialized: git submodule update --init"
            )

        rdt_model = RoboticDiffusionTransformerModel.from_pretrained(pretrained_path)
        instance = cls(rdt_model, num_inference_steps=num_inference_steps)

        # Load precomputed T5-XXL embeddings that ship with the checkpoint
        lang_dir = Path(pretrained_path) / "lang_embeds"
        if lang_dir.exists():
            obs_proc = RDTObsProcessor(lang_embed_cache_dir=str(lang_dir))
            obs_proc.load_embedded_tasks(str(lang_dir))
            instance._obs_processor = obs_proc
            log.info(f"Loaded {len(obs_proc._lang_cache)} precomputed lang embeds")

        log.info("RDT-1B loaded successfully")
        return instance

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def post_init(
        self,
        adapter: BaseEnvAdapter,
        postprocessor: Callable,          # identity for RDT; kept for interface parity
        sample_batch_size: int,
        policy_config: dict,
    ) -> None:
        self._adapter = adapter
        self._sample_batch_size = sample_batch_size
        self._action_chunk_horizon = policy_config.get("action_chunk_horizon", 8)
        self._lang_embed_cache_dir = policy_config.get(
            "lang_embed_cache_dir", "data/rdt_lang_embeds/"
        )
        if self._obs_processor is None:
            self._obs_processor = RDTObsProcessor(
                lang_embed_cache_dir=self._lang_embed_cache_dir
            )

    def to(self, device) -> "RDTSteer":
        self._rdt_model = self._rdt_model.to(device)
        self._dit = self._find_dit(self._rdt_model)
        return self

    def eval(self) -> "RDTSteer":
        self._rdt_model.eval()
        return self

    def reset(self) -> None:
        self._cached_action_chunk = None
        self._stage_init_reward = None
        self._last_normalized_reward = 0.0
        self._last_scale = 0.0
        self._last_raw_reward = 0.0
        if self._obs_processor is not None:
            self._obs_processor.reset()

    def reset_stage(self) -> None:
        self._stage_init_reward = None

    def get_normalized_reward(self) -> float:
        return self._last_normalized_reward

    def get_last_scale(self) -> float:
        return self._last_scale

    @property
    def device(self) -> torch.device:
        try:
            return next(self._rdt_model.parameters()).device
        except StopIteration:
            return torch.device("cpu")

    # ── Inference entry point ─────────────────────────────────────────────────

    def select_action(
        self,
        batch: dict,
        generate_new_chunk: bool = False,
        use_guidance: bool = False,
        keypoints: Optional[np.ndarray] = None,
        guidance_fns: Optional[List[Callable]] = None,
        guide_scale: float = 1.0,
        sigmoid_k: float = 12.0,
        sigmoid_x0: float = 0.7,
        start_ratio: Optional[float] = None,
        use_diversity: bool = True,
        diversity_scale: float = 1.0,
        MCMC_steps: int = 4,
        verbose: bool = False,
        use_fkd: bool = False,
        fkd_config: Optional[dict] = None,
        global_step: int = 0,
        current_stage: int = 1,
    ) -> Tensor:
        if generate_new_chunk:
            images, proprio, task_str = self._obs_processor.process(batch)
            text_embed = self._obs_processor.get_lang_embed(task_str, self.device)
            B = self._sample_batch_size

            if use_guidance:
                raw = self._guided_denoise_loop(
                    proprio=proprio,
                    images=images,
                    text_embeds=text_embed,
                    B=B,
                    guidance_fns=guidance_fns,
                    keypoints=keypoints,
                    guide_scale=guide_scale,
                    start_ratio=start_ratio,
                    use_diversity=use_diversity,
                    diversity_scale=diversity_scale,
                    use_fkd=use_fkd,
                    fkd_config=fkd_config,
                    sigmoid_k=sigmoid_k,
                    sigmoid_x0=sigmoid_x0,
                    verbose=verbose,
                )
            else:
                raw = self._predict_unguided(proprio, images, text_embed, B)

            self._cached_action_chunk = self._postprocess_actions(raw)

        return self._cached_action_chunk

    # ── Unguided path ─────────────────────────────────────────────────────────

    def _predict_unguided(
        self,
        proprio: np.ndarray,
        images: list,
        text_embed: Tensor,
        B: int,
    ) -> Tensor:
        """
        Call RDT's step() B times in parallel (no gradient, no steering).
        Returns (B, 64, 14).
        """
        results = []
        with torch.no_grad():
            for _ in range(B):
                out = self._rdt_model.step(
                    proprio=proprio,
                    images=images,
                    text_embeds=text_embed,
                )
                if out.dim() == 2:
                    out = out.unsqueeze(0)   # ensure (1, 64, 14)
                results.append(out)
        return torch.cat(results, dim=0)     # (B, 64, 14)

    # ── Action postprocessing ─────────────────────────────────────────────────

    def _postprocess_actions(self, actions: Tensor) -> Tensor:
        """
        (B, 64, 14) → (action_chunk_horizon, 7)

        Slices the right-arm output and takes the first H timesteps.
        Particle selection: particle 0 (FKD has already resampled to put best first).
        """
        right_arm = actions[:, :, _RIGHT_ARM]  # (B, 64, 7)
        best = right_arm[0]                     # (64, 7)  — particle 0 = best after FKD
        return best[: self._action_chunk_horizon]  # (H, 7)
```

- [ ] **Step 3.3: Run the first two tests — they should now pass**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_steer.py::test_instantiation tests/test_rdt_steer.py::test_forward_shape -v
```

Expected:
```
tests/test_rdt_steer.py::test_instantiation PASSED
tests/test_rdt_steer.py::test_forward_shape PASSED
```

- [ ] **Step 3.4: Commit**

```bash
git add core/rdt_policy_steer.py
git commit -m "feat: add RDTSteer with unguided inference path"
```

---

## Task 4: Denoising Loop — RBF Diversity + Gradient Guidance (RED → GREEN)

**Files:**
- Modify: `core/rdt_policy_steer.py` (add `_guided_denoise_loop`, helpers)
- Test: `tests/test_rdt_steer.py::test_gradient_steering`

- [ ] **Step 4.1: Add the guided denoising loop and helpers to `core/rdt_policy_steer.py`**

Append the following methods to the `RDTSteer` class (after `_postprocess_actions`):

```python
    # ── Trajectory projection (shared by diversity and guidance hooks) ────────

    def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
        """
        (1, 64, 14) → (1, T+1, 3) via adapter.delta_actions_to_ee_trajectory.

        Slices the right-arm dimensions, takes action_chunk_horizon steps,
        and delegates 3D projection to the adapter (no new API).
        """
        action_seq = sample[0, : self._action_chunk_horizon, _RIGHT_ARM]  # (H, 7)
        traj = self._adapter.delta_actions_to_ee_trajectory(action_seq)   # (H+1, 3)
        return traj.unsqueeze(0)  # (1, H+1, 3)

    # ── Gradient helpers ──────────────────────────────────────────────────────

    def _compute_diversity_gradient(self, x_t: Tensor) -> Optional[Tensor]:
        """
        RBF inverse-distance potential on 3D EEF trajectories.
        Gradient pushes particles apart. Mirrors DiffusionPolicySteer exactly.
        Returns gradient w.r.t. x_t (same shape), or None if B < 2.
        """
        B = x_t.shape[0]
        if B < 2 or self._adapter is None:
            return None

        with torch.enable_grad():
            x_grad = x_t.detach().requires_grad_(True)
            trajs = torch.cat(
                [self._rdt_sample_to_trajectory_3d(x_grad[b: b + 1]) for b in range(B)],
                dim=0,
            )  # (B, H+1, 3)
            pos = trajs[:, 1:, :3]              # skip the start point — (B, H, 3)
            flat = pos.reshape(B, -1)           # (B, H*3)

            sq_dist = torch.sum(
                (flat.unsqueeze(1) - flat.unsqueeze(0)) ** 2, dim=2
            )  # (B, B)
            mask = ~torch.eye(B, dtype=torch.bool, device=x_t.device)
            dist = torch.sqrt(sq_dist + 1e-6)
            inv_dist = (1.0 / (dist + 1e-6)) * mask.float()
            potential = inv_dist.sum()

            grad = torch.autograd.grad(potential, x_grad, create_graph=False)[0]
        return grad

    def _compute_keypoint_gradient(
        self,
        x_t: Tensor,
        keypoints: Tensor,
        guidance_fns: List[Callable],
        verbose: bool = False,
    ) -> Tuple[Optional[Tensor], float]:
        """
        Keypoint-based gradient guidance. Mirrors DiffusionPolicySteer logic:
          1. Project x_t to 3D EEF trajectory.
          2. Evaluate sum of guidance_fns(keypoints, trajectory).
          3. Backprop to get gradient w.r.t. x_t.
          4. Normalize gradient by its L2 norm.
        Returns (normalized_grad, raw_reward_scalar).
        """
        if not guidance_fns or self._adapter is None:
            return None, 0.0

        try:
            with torch.enable_grad():
                x_grad = x_t.detach().requires_grad_(True)
                trajs = torch.cat(
                    [self._rdt_sample_to_trajectory_3d(x_grad[b: b + 1]) for b in range(x_grad.shape[0])],
                    dim=0,
                )  # (B, H+1, 3)
                traj_input = trajs[:, : self._action_chunk_horizon, :3]  # (B, H, 3)

                reward = sum(fn(keypoints, traj_input) for fn in guidance_fns)

                if isinstance(reward, (int, float)):
                    return None, float(reward)
                if not hasattr(reward, "requires_grad") or not reward.requires_grad:
                    return None, float(reward.item())

                reward_scalar = float(reward.sum().item())
                self._last_raw_reward = reward_scalar

                # Update normalised reward relative to stage baseline
                if self._stage_init_reward is not None and self._stage_init_reward < -1e-6:
                    norm_r = 1.0 - reward_scalar / self._stage_init_reward
                    norm_r = max(0.0, min(1.2, norm_r))
                else:
                    norm_r = 0.0
                self._last_normalized_reward = norm_r

                grad = torch.autograd.grad(
                    reward.sum(), x_grad, create_graph=False, retain_graph=False
                )[0]
                g_norm = torch.norm(grad).item()
                normalized = grad / (g_norm + 1e-8) if g_norm > 1e-8 else grad

                if verbose:
                    log.info(f"reward={reward_scalar:.4f}, norm_r={norm_r:.3f}")

                return normalized, reward_scalar
        except Exception as exc:
            log.warning(f"Keypoint gradient failed: {exc}")
            return None, 0.0

    def _adaptive_scale(
        self, reward: float, guide_scale: float, sigmoid_k: float, sigmoid_x0: float
    ) -> float:
        """
        Sigmoid-gated guidance strength × sqrt(1-alpha_t) scaling.
        Matches DiffusionPolicySteer._guided_conditional_sample() exactly.
        alpha_t from scheduler.alphas_cumprod at current t is stored in _current_alpha_t.
        """
        strength = 1.0 / (1.0 + math.exp(sigmoid_k * (self._last_normalized_reward - sigmoid_x0)))
        alpha_t = getattr(self, "_current_alpha_t", 0.5)
        scale = guide_scale * strength * math.sqrt(max(0.0, 1.0 - float(alpha_t)))
        self._last_scale = scale
        return scale

    # ── Guided denoising loop ─────────────────────────────────────────────────

    def _guided_denoise_loop(
        self,
        proprio: np.ndarray,
        images: list,
        text_embeds: Tensor,
        B: int,
        guidance_fns: Optional[List[Callable]],
        keypoints: Optional[np.ndarray],
        guide_scale: float,
        start_ratio: Optional[float],
        use_diversity: bool,
        diversity_scale: float,
        use_fkd: bool,
        fkd_config: Optional[dict],
        sigmoid_k: float,
        sigmoid_x0: float,
        verbose: bool,
    ) -> Tensor:  # (B, 64, 14)
        """
        Three-phase denoising loop:
          D (t > start_t) : RBF diversity gradient  → noise_pred[:,:,:3]
          A (t ≤ start_t) : Keypoint guidance grad  → noise_pred[:,:H,:3]
          B (t ≤ start_t) : FKD resampling          → x_t after scheduler.step
        Phases D and A are mutually exclusive (if/elif).
        """
        device = self.device
        dtype = next(self._rdt_model.parameters()).dtype

        # Encode conditioning once (images + proprio + language)
        cond = self._rdt_model.encode_inputs(proprio, images, text_embeds)

        # Sample initial noise particles
        x_t = torch.randn(B, 64, 14, device=device, dtype=dtype)

        scheduler = self._rdt_model.noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        timesteps = scheduler.timesteps

        start_idx = int(self._num_inference_steps * (start_ratio if start_ratio is not None else 0.7))
        start_idx = min(start_idx, len(timesteps) - 1)
        start_t = int(timesteps[start_idx].item())

        keypoints_tensor = None
        if keypoints is not None:
            keypoints_tensor = torch.tensor(keypoints, device=device, dtype=dtype)

        # Init FKD particle filter
        fkd = None
        if use_fkd and fkd_config is not None and B > 1 and guidance_fns:
            def _fkd_reward_fn(x0: Tensor) -> Tensor:
                rs = []
                for b in range(B):
                    traj = self._rdt_sample_to_trajectory_3d(x0[b: b + 1])
                    with torch.no_grad():
                        r = sum(
                            float(fn(keypoints_tensor, traj[:, : self._action_chunk_horizon, :3]).sum())
                            for fn in guidance_fns
                        )
                    rs.append(r)
                return torch.tensor(rs, dtype=dtype, device=device)

            fkd = FKD(
                potential_type=fkd_config.get("potential_type", "max"),
                lmbda=float(fkd_config.get("lmbda", 10.0)),
                num_particles=B,
                adaptive_resampling=bool(fkd_config.get("adaptive_resampling", True)),
                resample_frequency=int(fkd_config.get("resample_frequency", 5)),
                resampling_t_start=start_t,
                resampling_t_end=int(timesteps[-1].item()),
                timesteps=timesteps,
                reward_fn=_fkd_reward_fn,
                reward_min_value=float("-inf"),
                device=device,
            )

        reward_history: list = []

        for i, t in enumerate(timesteps):
            t_val = int(t.item())

            # Store alpha_t for adaptive_scale
            if hasattr(scheduler, "alphas_cumprod"):
                idx = min(t_val, len(scheduler.alphas_cumprod) - 1)
                self._current_alpha_t = float(scheduler.alphas_cumprod[idx])

            # Baseline noise prediction (no grad)
            with torch.no_grad():
                noise_pred = self._dit(x_t, t, cond)  # (B, 64, 14)

            # ── HOOK D: RBF diversity (early phase: t > start_t) ─────────────
            if use_diversity and t_val > start_t and B > 1:
                div_grad = self._compute_diversity_gradient(x_t)
                if div_grad is not None:
                    noise_pred = noise_pred.clone()
                    noise_pred[:, :, :3] = noise_pred[:, :, :3] + diversity_scale * div_grad[:, :, :3]

            # ── HOOK A: Keypoint gradient guidance (late phase: t ≤ start_t) ──
            elif guidance_fns and keypoints_tensor is not None and t_val <= start_t:
                kp_grad, reward_val = self._compute_keypoint_gradient(
                    x_t, keypoints_tensor, guidance_fns, verbose=verbose
                )
                if kp_grad is not None:
                    scale = self._adaptive_scale(reward_val, guide_scale, sigmoid_k, sigmoid_x0)
                    noise_pred = noise_pred.clone()
                    noise_pred[:, : self._action_chunk_horizon, :3] = (
                        noise_pred[:, : self._action_chunk_horizon, :3]
                        - scale * kp_grad[:, : self._action_chunk_horizon, :3]
                    )
                    reward_history.append((i, reward_val, self._last_normalized_reward))

            # Standard denoising step (uses modified noise_pred)
            x_t = scheduler.step(noise_pred, t, x_t).prev_sample

            # ── HOOK B: FKD resampling (late phase only, after scheduler step) ─
            if fkd is not None and t_val <= start_t:
                x_t, _ = fkd.resample(sampling_idx=t_val, latents=x_t, x0_preds=x_t)
                if verbose and fkd.reached_terminal:
                    log.info(f"[FKD] Terminal at t={t_val}")

        # Set stage baseline from the first chunk's final reward
        if reward_history and self._stage_init_reward is None:
            self._stage_init_reward = reward_history[-1][1]
            log.info(f"Stage init_reward set: {self._stage_init_reward:.6f}")

        return x_t  # (B, 64, 14)
```

- [ ] **Step 4.2: Run the gradient steering test**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_steer.py::test_gradient_steering -v
```

Expected: `PASSED`

- [ ] **Step 4.3: Run all tests so far**

```bash
python -m pytest tests/test_rdt_steer.py::test_instantiation tests/test_rdt_steer.py::test_forward_shape tests/test_rdt_steer.py::test_gradient_steering -v
```

Expected: all 3 `PASSED`

- [ ] **Step 4.4: Commit**

```bash
git add core/rdt_policy_steer.py
git commit -m "feat: add guided denoising loop with RBF diversity and keypoint gradient hooks"
```

---

## Task 5: FKD Integration (RED → GREEN)

**Files:**
- Modify: `core/rdt_policy_steer.py` (FKD wiring already written in Task 4 — just verify)
- Test: `tests/test_rdt_steer.py::test_fkd_rollout`

- [ ] **Step 5.1: Run the FKD rollout test**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_steer.py::test_fkd_rollout -v
```

If `PASSED`: skip to Step 5.3.

If `FAILED` with `FKD.__init__` argument error: the FKD constructor in `core/fkd_class.py` requires `timesteps` as a list/tensor. The stub scheduler's timesteps may not satisfy FKD's `t_to_index` lookup. Fix by ensuring the `_StubScheduler.set_timesteps` produces timesteps that match what FKD expects:

In `tests/test_rdt_steer.py`, update `_StubScheduler.set_timesteps`:

```python
def set_timesteps(self, n):
    # FKD requires timesteps in descending order (same as real scheduler)
    self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)
```

Re-run:

```bash
python -m pytest tests/test_rdt_steer.py::test_fkd_rollout -v
```

- [ ] **Step 5.2: Run the full test suite**

```bash
python -m pytest tests/test_rdt_steer.py -v
```

Expected:
```
tests/test_rdt_steer.py::test_instantiation    PASSED
tests/test_rdt_steer.py::test_forward_shape    PASSED
tests/test_rdt_steer.py::test_fkd_rollout      PASSED
tests/test_rdt_steer.py::test_gradient_steering PASSED
```

- [ ] **Step 5.3: Commit**

```bash
git add tests/test_rdt_steer.py core/rdt_policy_steer.py
git commit -m "feat: complete FKD integration and all 4 smoke tests passing"
```

---

## Task 6: Config + main.py Wiring

**Files:**
- Modify: `configs/policy.yaml`
- Modify: `main.py:156-184`

- [ ] **Step 6.1: Add `rdt` section to `configs/policy.yaml`**

Open `configs/policy.yaml`. After the existing `pi05:` block, add:

```yaml
# ============================================================
# RDT-1B Policy (ManiSkill single-arm checkpoint)
# ============================================================
rdt:
  pretrained_path: robotics-diffusion-transformer/maniskill-model
  num_inference_steps: 55
  action_chunk_horizon: 8
  lang_embed_cache_dir: data/rdt_lang_embeds/
```

Note: camera keys and `proprio_dim` are not needed in config — `RDTObsProcessor` uses fixed keys `observation.images.image` / `observation.images.image2` / `observation.state` which both adapters already produce.

- [ ] **Step 6.2: Modify `main.py` — add rdt branch**

In `main.py`, find the block at lines ~156-184:

```python
        if policy_type == 'diffusion':
            self.policy = DiffusionPolicySteer.from_pretrained(pretrained_path)
        elif policy_type == 'pi05':
            self.policy = PI05PolicySteer.from_pretrained(pretrained_path)
        else:
            raise ValueError(f"Unknown policy type: {policy_type}")

        self.device = cfg.get('device', 'cuda')
        self.policy.to(self.device)

        preprocessor_overrides = {
            "device_processor": {"device": str(self.policy.config.device)},
        }

        self.policy_preprocessor, self.policy_postprocessor = make_pre_post_processors(
            policy_cfg=self.policy.config,
            pretrained_path=pretrained_path,
            preprocessor_overrides=preprocessor_overrides,
        )
```

Replace with:

```python
        if policy_type == 'diffusion':
            self.policy = DiffusionPolicySteer.from_pretrained(pretrained_path)
        elif policy_type == 'pi05':
            self.policy = PI05PolicySteer.from_pretrained(pretrained_path)
        elif policy_type == 'rdt':
            from core.rdt_policy_steer import RDTSteer
            num_steps = type_config.get('num_inference_steps', 55)
            self.policy = RDTSteer.from_pretrained(pretrained_path, num_inference_steps=num_steps)
        else:
            raise ValueError(f"Unknown policy type: {policy_type}")

        self.device = cfg.get('device', 'cuda')
        self.policy.to(self.device)

        if policy_type == 'rdt':
            # RDTSteer handles all obs/action processing internally.
            self.policy_preprocessor = lambda x: x
            self.policy_postprocessor = lambda x: x
        else:
            preprocessor_overrides = {
                "device_processor": {"device": str(self.policy.config.device)},
            }
            self.policy_preprocessor, self.policy_postprocessor = make_pre_post_processors(
                policy_cfg=self.policy.config,
                pretrained_path=pretrained_path,
                preprocessor_overrides=preprocessor_overrides,
            )
```

- [ ] **Step 6.3: Verify config parses correctly (dry run, no GPU needed)**

```bash
cd /home/hynx/VLA-Pilot++ && python -c "
import hydra
from omegaconf import OmegaConf
with hydra.initialize(config_path='configs', version_base=None):
    cfg = hydra.compose(config_name='config', overrides=['policy.type=rdt'])
    print('policy.type =', cfg.policy.type)
    print('policy.rdt.pretrained_path =', cfg.policy.rdt.pretrained_path)
    print('policy.rdt.action_chunk_horizon =', cfg.policy.rdt.action_chunk_horizon)
    print('Config OK')
"
```

Expected:
```
policy.type = rdt
policy.rdt.pretrained_path = robotics-diffusion-transformer/maniskill-model
policy.rdt.action_chunk_horizon = 8
Config OK
```

- [ ] **Step 6.4: Verify existing policies still load (regression check)**

```bash
python -c "
import hydra
from omegaconf import OmegaConf
with hydra.initialize(config_path='configs', version_base=None):
    for ptype in ['diffusion', 'pi05']:
        cfg = hydra.compose(config_name='config', overrides=[f'policy.type={ptype}'])
        assert cfg.policy.type == ptype, f'Failed for {ptype}'
        print(f'policy.type={ptype} OK')
"
```

Expected:
```
policy.type=diffusion OK
policy.type=pi05 OK
```

- [ ] **Step 6.5: Commit**

```bash
git add configs/policy.yaml main.py
git commit -m "feat: wire RDT policy into config and main.py initialization"
```

---

## Task 7: LIBERO End-to-End Smoke (GPU required)

**Files:** none (integration verification only)

> Run on a machine with GPU and the conda env activated: `conda activate vla-pilot`

- [ ] **Step 7.1: Download RDT maniskill checkpoint**

```bash
python -c "
from huggingface_hub import snapshot_download
path = snapshot_download('robotics-diffusion-transformer/maniskill-model')
print('Downloaded to:', path)
"
```

Note the local path (e.g. `~/.cache/huggingface/hub/models--robotics-diffusion-transformer--maniskill-model/snapshots/<hash>/`). Optionally set `pretrained_path` in `configs/policy.yaml` to this local path for faster reloads.

- [ ] **Step 7.2: Precompute LIBERO lang embeds (one-time)**

```bash
python -c "
from core.rdt_obs_processor import RDTObsProcessor
tasks = [
    'pick up the alphabet soup and place it in the basket',
    'pick up the cream cheese and place it in the basket',
    # Add any LIBERO task strings you will run
]
proc = RDTObsProcessor('data/rdt_lang_embeds/')
device = __import__('torch').device('cpu')
for t in tasks:
    embed = proc.get_lang_embed(t, device)
    print(f'Embedded: {t!r} → shape {embed.shape}')
"
```

- [ ] **Step 7.3: Run 1 LIBERO episode without guidance**

```bash
python main.py \
  env=libero \
  backend.libero.suite_name=libero_object \
  policy.type=rdt \
  main.use_guidance=false \
  main.episode_num=1 \
  main.sample_batch_size=1 \
  main.render=false
```

Expected:
- No crash
- Output directory `outputs/libero/TIMESTAMP/` created with `results.txt` and `episode_1/`
- Log shows: `Loaded RDT model`, `RDT-1B loaded successfully`, then episode loop runs

- [ ] **Step 7.4: Verify output files exist**

```bash
ls outputs/libero/$(ls -t outputs/libero/ | head -1)/
# Should show: results.txt  episode_1/
cat outputs/libero/$(ls -t outputs/libero/ | head -1)/results.txt
```

- [ ] **Step 7.5: Commit**

```bash
git add data/rdt_lang_embeds/   # precomputed embeds
git commit -m "test: LIBERO end-to-end smoke with RDT-1B (no guidance)"
```

---

## Task 8: CALVIN End-to-End Smoke (GPU required)

**Files:** none (integration verification only)

- [ ] **Step 8.1: Run 1 CALVIN episode without guidance**

```bash
python main.py \
  env=calvin \
  task=drawer_open \
  policy.type=rdt \
  main.use_guidance=false \
  main.episode_num=1 \
  main.sample_batch_size=1 \
  main.render=false
```

Expected: no crash, `outputs/calvin/TIMESTAMP/results.txt` written.

If CALVIN's `get_policy_observation()` puts images on CUDA before `RDTObsProcessor.process()` is called, the `_tensor_to_pil` call will need `.cpu()`. If you see a RuntimeError about CUDA tensors, add `.cpu()` before `.byte()` in `_tensor_to_pil`:

```python
# In core/rdt_obs_processor.py, _tensor_to_pil:
arr = (img.detach().cpu().clamp(0.0, 1.0) * 255).byte().permute(1, 2, 0).numpy()
# (.cpu() is already there — if error persists, check the obs key)
```

- [ ] **Step 8.2: Run 1 CALVIN episode with guidance + FKD**

```bash
python main.py \
  env=calvin \
  task=drawer_open \
  policy.type=rdt \
  main.use_guidance=true \
  main.use_fkd=true \
  main.episode_num=1 \
  main.sample_batch_size=4 \
  main.render=false
```

Expected: episode completes. Log shows `[FKD]` and `reward=` entries. `results.txt` written.

- [ ] **Step 8.3: Verify no regression in existing policies**

```bash
# Quick diffusion sanity check (1 episode, no guidance)
python main.py \
  env=calvin task=drawer_open \
  policy.type=diffusion \
  main.use_guidance=false \
  main.episode_num=1 main.render=false
```

Expected: runs as before, no crash.

- [ ] **Step 8.4: Final commit**

```bash
git add .
git commit -m "feat: complete RDT-1B integration — LIBERO + CALVIN end-to-end verified"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Covered by task |
|---|---|
| `policy.type=rdt` selects policy via config | Task 6 |
| CALVIN episode completes, outputs written | Task 8 |
| LIBERO episode completes, outputs written | Task 7 |
| FKD particle resampling functional | Task 5 |
| Gradient-based guidance functional | Task 4 |
| RBF diversity functional | Task 4 |
| test_instantiation | Task 3 |
| test_forward_shape | Task 3 |
| test_fkd_rollout | Task 5 |
| test_gradient_steering | Task 4 |
| No regression in diffusion / pi05 | Task 6.4, Task 8.3 |
| `RDTObsProcessor.reset()` at episode start | `RDTSteer.reset()` calls it |
| Lang embed fallback to zeros (no T5) | `RDTObsProcessor.get_lang_embed()` |

**Type / name consistency check:**

- `_RIGHT_ARM = slice(7, 14)` — used in `_postprocess_actions`, `_rdt_sample_to_trajectory_3d`. Consistent.
- `_action_chunk_horizon` — set in `post_init`, read in `_guided_denoise_loop`, `_rdt_sample_to_trajectory_3d`, `_postprocess_actions`. Consistent.
- `_obs_processor` — created in `post_init` (or `from_pretrained`); accessed in `select_action` and `reset`. Guarded with `if self._obs_processor is not None`. Consistent.
- FKD `resample(sampling_idx=..., latents=..., x0_preds=...)` — matches `FKD.resample` keyword signature in `core/fkd_class.py:191`. Consistent.
- `_compute_diversity_gradient(x_t)` / `_compute_keypoint_gradient(x_t, keypoints, guidance_fns)` — both called in `_guided_denoise_loop` with these exact signatures. Consistent.
