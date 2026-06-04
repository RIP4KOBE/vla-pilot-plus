---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/lerobot/2026-05-11-lerobot-usage-map.md
summary: LeRobot Usage Map in VLA-Pilot++
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/lerobot/2026-05-11-lerobot-usage-map.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/lerobot/2026-05-11-lerobot-usage-map.md
---

# LeRobot Usage Map in VLA-Pilot++

**Date:** 2026-05-11
**Branch:** `feat/rdt-integration`
**Scope:** Inventory every place this project depends on the `lerobot` package, what is imported, how it is used, and whether the dependency is load-bearing or accidental (dead import). Source-anchored, no fix proposals.

---

## 0. TL;DR

LeRobot is depended on at **four** load-bearing levels:

1. **Policy base classes** — `DiffusionPolicySteer` and `PI05PolicySteer` directly subclass `lerobot.policies.diffusion.modeling_diffusion.DiffusionPolicy` / `lerobot.policies.pi05.modeling_pi05.PI05Policy`. The steering logic is implemented as overrides of their sampling methods.
2. **Pre/post processor factories** — `main.py` calls `lerobot.policies.factory.make_pre_post_processors` to build the per-policy preprocessor / postprocessor that wraps env observations and policy actions.
3. **Observation pipeline glue inside LiberoAdapter** — `LiberoAdapter` instantiates `lerobot.processor.pipeline.PolicyProcessorPipeline` with `lerobot.processor[redacted env file]_processor.LiberoProcessorStep` to convert MuJoCo-side observations into LeRobot-canonical format.
4. **String constants** — `OBS_IMAGES`, `OBS_STATE`, `OBS_STR`, `ACTION`, `OBS_LANGUAGE_TOKENS`, `OBS_LANGUAGE_ATTENTION_MASK` etc. from `lerobot.utils.constants` are used as the canonical batch-key vocabulary across adapters and policy wrappers.

RDT does **not** use any LeRobot policy class but **inherits** the LiberoAdapter's `env_preprocessor` (because the adapter is shared across policy types) and then **selectively reverses** its effects (image un-flip; bypass of `observation.state`).

Two **dead imports** in `main.py` (`LeRobotDatasetMetadata`, `make_env_pre_post_processors`) are imported but never invoked.

---

## 1. Where lerobot is installed

### FACT — Source of the package

```bash
# environment.yml:240
- lerobot==0.4.2

# setup.sh
if [ -d "third_party/lerobot" ]; then
    pip install -e third_party/lerobot --quiet
    echo "  ✓ lerobot"
fi
```

The project ships a **vendored editable install** at `third_party/lerobot/` (path `/home/hynx/VLA-Pilot++/third_party/lerobot/`). `environment.yml` declares `lerobot==0.4.2` as a pip dependency, but `setup.sh` overrides that with the local fork via `pip install -e third_party/lerobot`. → **the live import target is the third_party fork**, not the PyPI release.

### FACT — Fork layout

```
third_party/lerobot/src/lerobot/
├── async_inference/
├── cameras/
├── configs/
├── datasets/         # LeRobotDatasetMetadata
├── envs/             # libero.py, factory.py (make_env_pre_post_processors)
├── model/
├── motors/
├── optim/
├── policies/         # diffusion/, pi05/, factory.py (make_pre_post_processors)
├── processor/        # pipeline.py, env_processor.py (LiberoProcessorStep)
├── rl/
├── robots/
├── scripts/
├── teleoperators/
├── templates/
├── transport/
└── utils/            # constants.py (OBS_*)
```

### FACT — `lerobot/...` as HuggingFace Hub org IDs (different from the python package)

The `configs/policy.yaml` `pretrained_path` for PI05 is `lerobot/pi05_libero_finetuned_v044`. This is a **HuggingFace Hub repo ID** under the `lerobot` org, **not** a python import path. It is consumed by `PI05Policy.from_pretrained(...)` (which inherits HuggingFace `HubMixin`). Don't conflate the two namespaces.

---

## 2. Import inventory — every usage site

Exhaustive list outside `third_party/`. Source: `grep -rn "lerobot" --include="*.py"` (excluding `__pycache__` / `third_party/`).

| File | Line | Import | Used? | Purpose |
|---|---|---|---|---|
| [`main.py`](../../../../main.py#L81) | 81 | `from lerobot.policies.diffusion.modeling_diffusion import DiffusionPolicy` | ❌ **DEAD IMPORT** | Imported but never referenced; the actual class used is `DiffusionPolicySteer` (subclass). |
| [`main.py`](../../../../main.py#L82) | 82 | `from lerobot.datasets.lerobot_dataset import LeRobotDatasetMetadata` | ❌ **DEAD IMPORT** | Never invoked. The string "metadata" elsewhere in main.py (lines 375, 385) refers to local dict literals. |
| [`main.py`](../../../../main.py#L83) | 83 | `from lerobot.policies.factory import make_pre_post_processors` | ✅ FACT (load-bearing) | Called at `main.py:178` to build `policy_preprocessor` / `policy_postprocessor` for `diffusion` and `pi05` paths. |
| [`main.py`](../../../../main.py#L84) | 84 | `from lerobot[redacted env file]s.factory import make_env_pre_post_processors` | ❌ **DEAD IMPORT** | Never invoked. |
| [`core/diffusion_policy_steer.py`](../../../../core/diffusion_policy_steer.py#L32) | 32 | `from lerobot.policies.diffusion.configuration_diffusion import DiffusionConfig` | ✅ FACT | Used as the constructor type annotation `def __init__(self, config: DiffusionConfig)` (line 50). |
| [`core/diffusion_policy_steer.py`](../../../../core/diffusion_policy_steer.py#L33) | 33 | `from lerobot.policies.diffusion.modeling_diffusion import DiffusionPolicy` | ✅ FACT | `class DiffusionPolicySteer(DiffusionPolicy)` — direct subclass. |
| [`core/diffusion_policy_steer.py`](../../../../core/diffusion_policy_steer.py#L34) | 34 | `from lerobot.policies.utils import get_device_from_parameters, get_dtype_from_parameters, populate_queues` | ✅ FACT | `populate_queues(self._queues, batch)` at line 146 (frame-history queue); device/dtype getters at lines 267-268 (inside steering sampler). |
| [`core/diffusion_policy_steer.py`](../../../../core/diffusion_policy_steer.py#L35) | 35 | `from lerobot.utils.constants import ACTION, OBS_IMAGES, OBS_STATE` | ✅ FACT (partial) | `ACTION` used at lines 139-140 to pop action key from batch. `OBS_IMAGES` and `OBS_STATE` imported but greps show no direct reads in this file — likely accessed via parent class. |
| [`core/pi05_steer.py`](../../../../core/pi05_steer.py#L17) | 17 | `from lerobot.policies.pi05.modeling_pi05 import PI05Policy, make_att_2d_masks` | ✅ FACT | `class PI05PolicySteer(PI05Policy)` (line 27); `make_att_2d_masks(prefix_pad_masks, prefix_att_masks)` used at line 179 inside the custom guided sampler. |
| [`core/pi05_steer.py`](../../../../core/pi05_steer.py#L18) | 18 | `from lerobot.utils.constants import ACTION, OBS_LANGUAGE_ATTENTION_MASK, OBS_LANGUAGE_TOKENS` | ✅ FACT | `ACTION` at lines 38, 103-104; `OBS_LANGUAGE_TOKENS` at line 164; `OBS_LANGUAGE_ATTENTION_MASK` at line 165 — these drive the language-conditioning slice in PI05's denoising loop. |
| [`core/env_adapters/libero_adapter.py`](../../../../core/env_adapters/libero_adapter.py#L36) | 36 | `from lerobot.processor.pipeline import PolicyProcessorPipeline, ProcessorStep` | ✅ FACT | `PolicyProcessorPipeline(steps=...)` at lines 754-755; `ProcessorStep` used as the type annotation for `env_{pre,post}processor_steps` lists (lines 751-752). |
| [`core/env_adapters/libero_adapter.py`](../../../../core/env_adapters/libero_adapter.py#L37) | 37 | `from lerobot.processor[redacted env file]_processor import LiberoProcessorStep` | ✅ FACT | `env_preprocessor_steps.append(LiberoProcessorStep())` at line 753. The only step actually installed today. |
| [`core/env_adapters/libero_adapter.py`](../../../../core/env_adapters/libero_adapter.py#L38) | 38 | `from lerobot.utils.constants import OBS_ENV_STATE, OBS_IMAGE, OBS_IMAGES, OBS_STATE, OBS_STR` | ⚠️ **PARTIAL** | Only `OBS_IMAGES` (line 571: `f"{OBS_IMAGES}.{mapped_name}"`) and `OBS_STR` (line 574: `f"{OBS_STR}.robot_state"`) are actually used. `OBS_ENV_STATE`, `OBS_IMAGE`, `OBS_STATE` are imported but not referenced in this file. |
| [`tests/pi05_loading.py`](../../../../tests/pi05_loading.py#L11) | 11, 15 | `import lerobot`; `from lerobot.policies.pi05 import PI05Policy` | ✅ FACT | Smoke test that `import lerobot` works and that `PI05Policy.from_pretrained("lerobot/pi05_libero_finetuned_v044")` resolves. Not on the runtime hot path. |
| [`docs/.../round-1/images/image_check.py`](../../../../docs/superpowers/03_evidence/rdt_intergration/round-1/images/image_check.py#L58) | 57-58 | `sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "lerobot"))`; `from lerobot.processor[redacted env file]_processor import LiberoProcessorStep` | ✅ FACT | Evidence script that replays `LiberoProcessorStep` on a synthetic frame to confirm the 180° flip. Not on the runtime hot path. |

**Constants `lerobot.utils.constants`** resolve to strings (per `third_party/lerobot/src/lerobot/utils/constants.py:20-25`):
- `OBS_STR = "observation"`
- `OBS_STATE = "observation.state"`
- `OBS_IMAGE = "observation.image"`
- `OBS_IMAGES = "observation.images"`
- `OBS_ENV_STATE = "observation[redacted env file]ironment_state"` (**INFERENCE** — not directly read in this round, but standard LeRobot convention)
- `ACTION = "action"`
- `OBS_LANGUAGE_TOKENS`, `OBS_LANGUAGE_ATTENTION_MASK` — language conditioning keys (**FACT** for existence; exact string values not opened this round)

---

## 3. How lerobot is used — by use case

### 3.1 Policy base classes (subclassing pattern)

**Location:** `core/diffusion_policy_steer.py`, `core/pi05_steer.py`

```python
# core/diffusion_policy_steer.py:42
class DiffusionPolicySteer(DiffusionPolicy):
    """
    Diffusion Policy as per "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion"
    """
    name = "diffusion_steer"

    def __init__(self, config: DiffusionConfig):
        super().__init__(config)
        ...
```

```python
# core/pi05_steer.py:27
class PI05PolicySteer(PI05Policy):
    """PI05 Policy with gradient-based trajectory steering."""
    name = "pi05_steer"
    ...
```

**Semantics:**
- Both classes **inherit** the full LeRobot policy (config, model architecture, normalization, queue management, `from_pretrained`).
- The VLS additions are **overrides** that hook into the denoising loop to inject (a) VLM-generated reward gradients, (b) FKD particle resampling, (c) RBF diversity, (d) MCMC steps.
- `from_pretrained(pretrained_path)` is called at `main.py:157, 159` — this is the inherited `HubMixin` method, loading checkpoints from HuggingFace Hub.

**FACT — these are policy-class dependencies, not data-structure dependencies.** Replacing LeRobot here would require porting both architectures.

**Symbols imported from inside lerobot.policies.* used at runtime:**
- `DiffusionPolicy.__init__`, `DiffusionPolicy.reset` (called via `super().reset()` at `diffusion_policy_steer.py:80`), the diffusion sampler internals
- `PI05Policy.__init__`, `PI05Policy._preprocess_images` (called at `pi05_steer.py:163`), `PI05Policy.model.sample_noise`, `model.embed_prefix`, `model.paligemma_with_expert` access path
- `make_att_2d_masks` — a stateless helper to build 2D attention masks from 1D pad+attention masks for PaliGemma prefix tokens
- `populate_queues` — manages the observation/action history rolling buffer (Diffusion path)
- `get_device_from_parameters`, `get_dtype_from_parameters` — small helpers to introspect a nn.Module's device/dtype

### 3.2 Pre/post-processor factory (`make_pre_post_processors`)

**Location:** `main.py:174-189`

```python
# main.py:170-189
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

self.policy.post_init(
    adapter=self.adapter,
    postprocessor=self.policy_postprocessor,
    ...
)
```

**Semantics (FACT):**
- For `policy_type in {"diffusion", "pi05"}`: LeRobot builds policy-specific pre/post pipelines from the loaded checkpoint config. These pipelines apply tokenization, normalization, dtype/device casting, etc.
- For `policy_type == "rdt"`: identity functions replace the LeRobot pipeline. RDTSteer handles all obs/action processing inside its `RDTObsProcessor` and `rdt_chunk_to_libero_actions`.

**Where they fire:**
- `self.policy_preprocessor(observation)` at [`main.py:282`](../../../../main.py#L282) — wraps observations before each `policy.select_action(...)` call.
- `self.policy_postprocessor` is **passed into** the steer class via `post_init(postprocessor=...)` (line 186); the steer class invokes it on the predicted action chunk. For RDT this is identity, so it's a no-op.

**INFERENCE — overall flow:**
```
Adapter.get_policy_observation()       ──> obs dict (post LiberoProcessorStep)
   │
   ▼
self.policy_preprocessor(obs)           ──> LeRobot policy-specific obs (tokenization,
   │                                          normalize, device, dtype) [pi05/diffusion]
   │                                       ── or identity [rdt]
   ▼
self.policy.select_action(obs, ...)     ──> action chunk
   │
   ▼
self.policy._postprocessor(action_chunk) ──> action in adapter-friendly format
                                             (called inside PI05/Diffusion steer code)
```

### 3.3 LiberoAdapter's `env_preprocessor` (LiberoProcessorStep)

**Location:** [`core/env_adapters/libero_adapter.py:751-755`](../../../../core/env_adapters/libero_adapter.py#L751-L755)

```python
env_preprocessor_steps: list[ProcessorStep] = []
env_postprocessor_steps: list[ProcessorStep] = []
env_preprocessor_steps.append(LiberoProcessorStep())
self[redacted env file]_preprocessor = PolicyProcessorPipeline(steps=env_preprocessor_steps)
self[redacted env file]_postprocessor = PolicyProcessorPipeline(steps=env_postprocessor_steps)
```

**Where they fire:**
- `env_preprocessor`:
  - `obs = self[redacted env file]_preprocessor(obs)` at [`libero_adapter.py:848`](../../../../core/env_adapters/libero_adapter.py#L848) inside `get_policy_observation`
- `env_postprocessor`:
  - `action_transition = self[redacted env file]_postprocessor(action_transition)` at [`libero_adapter.py:1425`](../../../../core/env_adapters/libero_adapter.py#L1425) inside `step()` — currently empty (no postprocessor steps registered), so a no-op

**What `LiberoProcessorStep` does** (per [`env_processor.py:49-82`](../../../../third_party/lerobot/src/lerobot/processor/env_processor.py#L49-L82)):
1. For every `observation.images.*` key: `torch.flip(img, dims=[2,3])` (180° H+W flip)
2. Pops `observation.robot_state` (nested dict) and writes flat `observation.state` `(B, 8)` = `[eef_pos(3), eef_axisangle(3), gripper_qpos(2)]` via the embedded `_quat2axisangle` helper

**FACT — this is the second-stage adapter→training-convention bridge** documented in detail in the companion doc `2026-05-11-rdt-libero-observation-semantic-chain.md`, §A.5 and §6 of the conversation that produced it.

**Note — CalvinAdapter does NOT use this pipeline.** A `grep` on `core/env_adapters/calvin_adapter.py` shows zero references to `env_preprocessor` / `env_postprocessor` / lerobot processors. LeRobot's processor abstraction is therefore **LIBERO-only** in this repo. CALVIN handles its observation pipeline internally.

### 3.4 LeRobot constants as canonical key vocabulary

**Location:** `core/env_adapters/libero_adapter.py:38`, `core/diffusion_policy_steer.py:35`, `core/pi05_steer.py:18`

The project uses LeRobot's string constants to construct **dict keys** that are then read by both LeRobot's own processors and the steering wrappers. Concretely:

| Constant | Value | Where written | Where read |
|---|---|---|---|
| `OBS_IMAGES` | `"observation.images"` | `libero_adapter.py:571` (`f"{OBS_IMAGES}.{mapped_name}"` → e.g. `"observation.images.image"`) | `LiberoProcessorStep._process_observation` line 55; `DiffusionPolicySteer.select_action` (via parent's config); `RDTObsProcessor._STATIC_KEY` literal |
| `OBS_STR` | `"observation"` | `libero_adapter.py:574` (`f"{OBS_STR}.robot_state"`) | `LiberoProcessorStep` line 63 |
| `OBS_STATE` | `"observation.state"` | `LiberoProcessorStep` line 81 | `DiffusionPolicySteer` (via parent); `RDTObsProcessor._fallback_proprio_from_state` (line 185 — under the literal `_STATE_KEY = "observation.state"`) |
| `ACTION` | `"action"` | LeRobot policies emit it | `DiffusionPolicySteer:139`, `PI05PolicySteer:103` — popped from input batch |
| `OBS_LANGUAGE_TOKENS` / `OBS_LANGUAGE_ATTENTION_MASK` | string keys | LeRobot tokenizer step writes them | `PI05PolicySteer:164-165` — language-conditioning slice |

**INFERENCE — design intent:** Using shared string constants keeps the project's key names compatible with LeRobot's standard pipelines, so steering code can drop into a LeRobot-style data flow without renaming.

---

## 4. RDT's relationship to lerobot — no direct dependency but indirect coupling

### 4.1 Zero direct imports

**FACT:** `core/rdt_policy_steer.py`, `core/rdt_obs_processor.py`, `core/rdt_action_converter.py` — `grep "lerobot"` returns no hits in any of them.

RDT is built on top of:
- `core[redacted env file]_adapters.BaseEnvAdapter` (project-internal abstraction)
- `core.fkd_class.FKD` (project-internal)
- `core.rdt_obs_processor.RDTObsProcessor` (project-internal)
- `third_party.rdt.*` (`maniskill_model.RoboticDiffusionTransformerModel`, `rdt_runner.RDTRunner`, `configs.state_vec.STATE_VEC_IDX_MAPPING`)

No LeRobot base class, no LeRobot processor step, no LeRobot constant import.

### 4.2 Indirect coupling via the shared LiberoAdapter

**FACT — RDT inherits the LeRobot-shaped obs dict by virtue of sharing `LiberoAdapter`:**
- `LiberoAdapter.get_policy_observation` is policy-agnostic and always applies `env_preprocessor` (which contains `LiberoProcessorStep`)
- So even though RDT doesn't import lerobot, the **dict it consumes was shaped by lerobot's processor**
- RDT then **partially undoes** that shaping: `RDTObsProcessor._tensor_to_pil` re-flips images when `_undo_libero_flip=True` (`rdt_obs_processor.py:118-121`); the EEF-pose `observation.state` is ignored in favor of `adapter.get_joint_positions()` / `adapter.get_gripper_state()`

**Consequence (FACT):** Removing/changing `LiberoProcessorStep` would change the obs dict RDT receives, so RDT is *transitively* coupled to LeRobot even with zero imports. The H3 image-flip-undo fix (`rdt_policy_steer.py:557-558`) is in fact a workaround for the LeRobot-applied flip.

### 4.3 LeRobot policy factory is bypassed for RDT

**FACT:** `main.py:170-173` short-circuits `make_pre_post_processors` to identity for `policy_type == "rdt"`. RDT manages its own preprocessing (`RDTObsProcessor.process`) and postprocessing (`_postprocess_actions` → `rdt_chunk_to_libero_actions`).

---

## 5. Summary table — dependency surface area

| Subsystem | Direct lerobot import? | Strength | Replaceable? |
|---|---|---|---|
| DiffusionPolicySteer | ✅ Class inheritance + utility helpers + config type + constants | **Strong** (entire policy architecture) | Not without re-implementing DiffusionPolicy |
| PI05PolicySteer | ✅ Class inheritance + `make_att_2d_masks` + constants | **Strong** | Not without re-implementing PI05Policy |
| RDTSteer | ❌ No direct import | **None directly** | RDT is self-contained against lerobot |
| main.py policy factory call | ✅ `make_pre_post_processors` (used) + 3 dead imports | **Moderate** (gated on policy type) | Could be replaced by manual pre/post construction per policy |
| LiberoAdapter | ✅ `PolicyProcessorPipeline` + `LiberoProcessorStep` + constants | **Strong (LIBERO only)** | Would require rewriting the camera flip + state flattening locally |
| CalvinAdapter | ❌ No direct import | **None** | Already self-contained |
| Configs (`pretrained_path`) | ✅ HuggingFace Hub IDs under `lerobot/` org | **Strong** (checkpoint distribution) | Different from python package; cannot be "replaced" — it's just a checkpoint name |
| Tests (`tests/pi05_loading.py`) | ✅ `lerobot` + `PI05Policy` | **Test-only** | Smoke test |
| Evidence scripts (`image_check.py`) | ✅ `LiberoProcessorStep` | **Test/Audit-only** | Inline replication possible |

---

## 6. FACT / INFERENCE / UNKNOWN summary

### FACT
1. The runtime `lerobot` is the editable install of `third_party/lerobot` (`setup.sh` `pip install -e`).
2. `DiffusionPolicySteer extends DiffusionPolicy` and `PI05PolicySteer extends PI05Policy` (direct subclass).
3. `LiberoAdapter` is the only adapter using LeRobot's processor framework; CalvinAdapter does not.
4. `main.py:170-173` explicitly replaces LeRobot's pre/postprocessors with identity for `policy_type == "rdt"`.
5. `main.py:82, 84, 81` contain three dead imports (`LeRobotDatasetMetadata`, `make_env_pre_post_processors`, `DiffusionPolicy`).
6. RDT modules have **zero** direct `lerobot` imports.
7. The `pretrained_path` strings beginning with `lerobot/` are HuggingFace Hub IDs, distinct from the Python package.
8. `env_postprocessor` is constructed empty and is a no-op today (`libero_adapter.py:752,755,1425`).

### INFERENCE
1. **LiberoProcessorStep was designed for HuggingFaceVLA's LIBERO training pipeline** (docstring says "HuggingFaceVLA/libero camera orientation convention"). The flip + state-flattening match what those policies see at training time, so PI05 and Diffusion on LIBERO benefit from this preprocessing being applied.
2. **LeRobot's processor framework was adopted to keep the obs dict format pluggable across policies** — the `PolicyProcessorPipeline` is a list of steps, suggesting the design supports adding/removing steps per policy. Currently only one step (`LiberoProcessorStep`) is registered for LIBERO.
3. Constants like `OBS_IMAGES` are imported into `libero_adapter.py` partly for forward-compat (some constants like `OBS_ENV_STATE` are imported but unused).

### UNKNOWN
1. **Why `main.py` imports `make_env_pre_post_processors` and `LeRobotDatasetMetadata` without using them** — git history of those lines not inspected this round; could be planned for future use or leftover from refactors.
2. **Whether the LeRobot fork at `third_party/lerobot` diverges from upstream `lerobot==0.4.2`** — `git log` / diff against upstream not inspected this round.
3. **Whether DiffusionPolicySteer's parent class internally reads `OBS_IMAGES`/`OBS_STATE`** — grep in this round only shows the constants imported, not read; their effect is mediated through inherited methods.

---

## 7. Risks worth flagging (no fix proposals)

These are points where the lerobot coupling has produced behavior worth being aware of during debugging:

1. **Shared `env_preprocessor` across policy types causes RDT to inherit a flip it doesn't want.** The H3 image un-flip in `RDTObsProcessor._tensor_to_pil` is necessary purely because the LeRobot processor is unconditionally applied. **FACT** (codepath); see also `2026-05-11-rdt-libero-observation-semantic-chain.md` §E.1.4.

2. **`observation.state` lingers in the obs dict for RDT even though RDT doesn't read it.** `LiberoProcessorStep` always writes this key. The `RDTObsProcessor._fallback_proprio_from_state` path reads it on adapter-error fallback (rdt_obs_processor.py:185-195), and would silently feed EEF-pose values into the joint-angle slot if it fires. **FACT-supported risk**.

3. **Dead imports in `main.py` create false impressions of dataset / env-factory dependencies.** Reading `main.py:81-84` suggests metadata and env factories are in play; greps prove neither is invoked. **FACT (deadness)**.

4. **Pinning `lerobot==0.4.2` in `environment.yml` is overridden by the editable third_party install.** Anyone reading the env file may incorrectly assume the PyPI release is what runs. **FACT (setup.sh:N install order)**.

5. **CalvinAdapter and LiberoAdapter use different processor patterns** — only LiberoAdapter goes through `LiberoProcessorStep`. Any analysis comparing the two backends must remember this. **FACT**.
