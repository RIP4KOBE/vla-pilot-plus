---
session: 2026-04-30-phase1-evidence-session-1
type: session-log
status: complete
---

# Session Log — Phase 1 Evidence Collection

**Date:** 2026-04-30  
**Round:** 1

---

## What Was Attempted

1. Verified conda env (`vla-pilot`, torch 2.7.1+cu126, LIBERO importable)
2. Located HF checkpoint at `/mnt/data/hf_cache/hub/models--robotics-diffusion-transformer--maniskill-model/snapshots/9622afab.../`
3. Confirmed 9 md5-named T5 embeddings exist in both `data/rdt_lang_embeds/` and the checkpoint's `lang_embeds/`
4. Wrote and ran `evidence/round-1/stats/loop_comparison.py` — loads model, compares official `step()` vs custom `_predict_unguided()` on a frozen synthetic observation
5. Wrote and ran `evidence/round-1/images/image_check.py` — source-traces `LiberoProcessorStep`, generates flip demo image
6. Wrote `evidence/round-1/stats/phase2_hypothesis_discrimination.md` — interprets all evidence
7. Wrote `evidence/round-1/summary.md` — full evidence package summary

---

## Files Created

| File | Description |
|---|---|
| `evidence/round-1/stats/loop_comparison.py` | Main comparison script |
| `evidence/round-1/stats/loop_comparison_output.txt` | Raw text output from comparison run |
| `evidence/round-1/stats/loop_comparison_trajectories.pt` | Saved tensors for both paths |
| `evidence/round-1/stats/phase2_hypothesis_discrimination.md` | Hypothesis verdict file |
| `evidence/round-1/images/image_check.py` | Image orientation inspection script |
| `evidence/round-1/images/flip_test_synthetic.png` | Side-by-side flip demo |
| `evidence/round-1/images/image_check_notes.txt` | Image check console output |
| `evidence/round-1/summary.md` | Full round summary |
| `runs/2026-04-30-phase1-evidence-session-1.md` | This file |

---

## Key Findings

### H1 — CONFIRMED (revised mechanism)

The custom `_predict_unguided` loop does NOT produce random noise. It produces a smooth, highly autocorrelated trajectory (lag-1 autocorr = 0.98). However, the output is biased to **the wrong joint configuration** compared to the official `real_model.step()` path.

- Normalized mean abs diff between official and custom: **0.608** (large)
- Joint 1 example: official normalized = -0.66, custom = +0.52 (opposite direction)
- Root mechanism: custom loop initializes `x_t = randn(B, 64, 8)` then zero-pads to 128D. The 120 zero-valued inactive dimensions bias the DiT's attention patterns toward a different posterior than full-128D noise.
- Downstream consequence: step-0 FK delta is huge (saturated at ±1.0), steps 1-7 are near-zero (robot stalls).

### H2 — REJECTED

T5 embeddings are real (norm=16.98), task-specific (two tasks have first-token diff=7.45). 9 md5-named embedding files in both cache dirs confirm T5 was working in prior runs.

### H3 — CONFIRMED

`LiberoProcessorStep._process_observation` applies `torch.flip(img, dims=[2, 3])` to all images. All frames reaching `RDTSteer` are 180°-rotated relative to ManiSkill training distribution.

### H4 — MINOR

2/24 position dims saturated at step 0. This is a symptom of H1's wrong joint targets, not an independent scale bug.

---

## Whether Repair Mode Is Justified

**YES.** Both primary causes (H1 biased denoising, H3 image flip) are confirmed with high confidence. No critical unknowns remain.

---

## Exact Next Recommended Prompt

```
Read and execute the workflow prompt at:
docs/superpowers/prompts/rdt_repair_plan_prompt.md
```

That prompt should instruct:
- **Read:** `evidence/round-1/summary.md`, `evidence/round-1/stats/phase2_hypothesis_discrimination.md`
- **Read:** `core/rdt_policy_steer.py`, `core/rdt_obs_processor.py`
- **Task:** Write a repair plan with one task per confirmed hypothesis, one fix per commit, validation step after each
- **Write:** `docs/superpowers/plans/2026-04-30-rdt-repair-plan.md`
- **Constraint:** H1 fix before H3 fix; do not bundle; rollback instructions required
