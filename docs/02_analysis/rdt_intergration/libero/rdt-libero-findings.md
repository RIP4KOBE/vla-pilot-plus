---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: unknown
source_commit: unknown
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/findings.md
summary: RDT-1B LIBERO Integration — Findings
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/findings.md
---

# RDT-1B LIBERO Integration — Findings

**Last updated:** 2026-05-19
**Status:** EEF index fix committed; awaiting first run validation

---

## Current Understanding

**RDT-1B LIBERO-Object** is a 1.2B-parameter Diffusion Transformer fine-tuned on LIBERO Object benchmark. The model uses a 128D unified state/action space where different robot embodiments populate different index subsets.

**The LIBERO-Object checkpoint was trained with EEF-space actions** at indices [30,31,32,33,34,35,10] — corresponding to `right_eef_pos_{x,y,z}`, `right_eef_angle_{0,1,2}`, and `right_gripper_open`. This matches LIBERO's 7D OSC action format `[dx, dy, dz, drx, dry, drz, gripper]`.

**Previous integration bug:** The code was using ManiSkill joint indices [0-6, 10] (arm joint positions), which produced near-zero arm actions because the LIBERO checkpoint's weights are trained to output at EEF indices, not joint position indices.

---

## Patterns and Insights

### 1. RDT Unified State Architecture

The 128D vector unifies multiple robot embodiments. Key index groups:
- **[0-9]**: Right arm joint positions
- **[10]**: Right gripper open (0=closed, 1=open)
- **[30-32]**: Right EEF position (x, y, z) in robot base frame
- **[33-38]**: Right EEF angles (6D rotation representation)

The ManiSkill checkpoint uses indices [0-6, 10] (Franka 7-DOF joints + gripper).
The LIBERO-Object checkpoint uses indices [30-35, 10] (EEF pos + first 3 rotation components + gripper).

### 2. Action Extraction Determines Behavior

Extracting the wrong indices from the 128D output gives near-zero values because the model was never trained to predict at those positions. This explains the diagnostic observations:
- P5: arm_min=-0.0004, arm_max=0.0003 (indices 0-6 are zero for LIBERO checkpoint)
- P7: first LIBERO action saturates at ±1 (FK with near-zero inputs = garbage output)

### 3. LIBERO Action Convention

LIBERO OSC controller expects:
- **Actions in [-1, 1]** (controller handles scaling: ~5cm/unit for position)
- **Gripper convention**: +1 = close, -1 = open
- **RDT convention**: right_gripper_open high = open → must negate before sending to LIBERO

### 4. Image Flip

LiberoProcessorStep applies 180° rotation to all frames. Must undo before SigLIP encoding. Fixed with `_undo_libero_flip` flag.

---

## Lessons and Constraints

- **DO NOT** use `rdt_chunk_to_libero_actions` (FK path) for LIBERO-finetuned checkpoints. It produces garbage output because: (a) wrong indices, and (b) even if correct joints, ManiSkill stats don't match LIBERO training stats.
- **DO** set `libero_mode: true` in config for any LIBERO-finetuned RDT checkpoint.
- Approximate EEF position normalization bounds (derived from FK trajectory probes): x∈[-0.55, 0.15], y∈[-0.05, 0.70], z∈[0.08, 0.60] meters.
- The EEF action output from the model is already in [-1, 1] normalized space, which IS the LIBERO action space. No denormalization needed.
- Gripper must be negated: RDT `right_gripper_open` → LIBERO convention.

---

## Open Questions

1. **Does the approximate EEF position normalization (workspace bounds) match training?** The checkpoint was trained with LIBERO-specific stats we don't have. The approximate normalization may introduce bias.
2. **What is the base task success rate of RDT-LIBERO-Object unguided?** Need to run 3-10 episodes.
3. **Does VLS steering improve over unguided?** The gradient path needs EEF-space adaptation for LIBERO mode.
4. **Rotation representation**: Are indices 33-35 expected to be first 3 components of 6D rotation (first column of R), or axis-angle, or euler? Using first column of R (`R[:,0]`) as approximation.
