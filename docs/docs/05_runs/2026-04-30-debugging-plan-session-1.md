---
session: 2026-04-30-debugging-plan-session-1
type: session-log
status: complete
---

# Session Log — RDT Debugging Plan Generation

**Date:** 2026-04-30  
**Session:** 1

---

## Inputs Used

| File | Role |
|---|---|
| `docs/superpowers/specs/2026-04-22-rdt1b-integration-design.md` | Original integration design spec |
| `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md` | Failure analysis (8-section diagnostic produced earlier in session) |
| `docs/superpowers/prompts/rdt_debugging_plan_prompt.md` | Workflow prompt driving this session |
| `core/rdt_policy_steer.py` | Inspected for denoising loop implementation |
| `core/rdt_obs_processor.py` | Inspected for proprio, image, language embed paths |
| `core/rdt_action_converter.py` | Inspected for FK and denormalization |
| `third_party/rdt/models/rdt_runner.py` | Inspected for official `conditional_sample` reference |
| `third_party/rdt/scripts/maniskill_model.py` | Inspected for MANISKILL_INDICES and DATA_STAT |
| `third_party/lerobot/src/lerobot/processor/env_processor.py` | Inspected for LiberoProcessorStep image flip |

---

## Key Assumptions Identified

| ID | Assumption | Fragility |
|---|---|---|
| A2.1 | `_predict_unguided` initializes `x_t` in 8D (raw action dim), zero-pads to 128D | **HIGH** — official `conditional_sample` uses full 128D noise; zero-padding is OOD for DiT self-attention |
| A2.2 | LiberoProcessorStep 180° image flip is neutral / handled by the model | **HIGH** — ManiSkill checkpoint was trained on upright SAPIEN images, not flipped |
| A2.3 | Language embedding cache key (md5 hash) matches checkpoint cache key (file stem) | **HIGH** — these are structurally different; silent zero fallback is the actual runtime path |
| A2.4 | FK-based EEF delta conversion produces actions in the same scale as LIBERO OSC | **MEDIUM** — `_POS_SCALE=0.05`, `_ORI_SCALE=0.5` are unverified against actual joint velocity magnitudes |
| A2.5 | `observation.state` (EEF-based, 8D) is an equivalent substitute for joint angles as proprio | **MEDIUM** — RDT checkpoint was trained with joint angle proprio in the MANISKILL_INDICES format |
| A2.6 | `encode_inputs` correctly replicates `predict_action:237` state+mask concatenation | **LOW** — verified by source inspection; `state_token = torch.cat([state_tokens, action_mask], dim=2)` matches |

---

## Output File Created

**Primary:** `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md`

---

## Top 3 Debugging Priorities

1. **H1 — Denoising dimensionality mismatch (CRITICAL):** `x_t` initialized as 8D, zero-padded to 128D. The DiT's self-attention receives 120 all-zero dimensions instead of noisy ones. This alone is sufficient to cause fully random output. Verify by logging `x_t.shape` and `x_t[:,:,8:].abs().max()` at the first denoising step entry.

2. **H3 — Language embedding zero fallback (HIGH):** Cache key mismatch means `get_lang_embed()` always falls through to `torch.zeros(1, 1, 4096)`. The model receives a zero conditioning signal for all LIBERO tasks. Verify by adding a `print`/`log` at the fallback line and running one episode.

3. **H2 — Image orientation mismatch (HIGH):** `LiberoProcessorStep` flips images 180° before they reach `RDTSteer`. ManiSkill checkpoint was trained on upright SAPIEN RGB images. Verify by saving the image tensor as PNG at the RDT input boundary and visually inspecting orientation.

---

## Recommended Next Prompt

Run the Phase 1 evidence collection prompt:

```
Read and execute the workflow prompt at:
docs/superpowers/prompts/rdt_phase1_evidence_collection_prompt.md
```

That prompt (to be written) should instruct:
- **Read:** `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md` (Phase 1 tasks)
- **Read:** `core/rdt_policy_steer.py`, `core/rdt_obs_processor.py`, `core/rdt_action_converter.py`
- **Write:** diagnostic instrumentation patches (no logic changes, only logging/saves)
- **Write:** `docs/superpowers/evidence/phase1_loop_comparison.py` (standalone script comparing `_predict_unguided` vs `conditional_sample` noise initialization)
- **Write:** `docs/superpowers/evidence/2026-04-30-phase1-results.md` after a single instrumented episode
- **Do NOT:** change any inference logic, fix anything, merge multiple changes
