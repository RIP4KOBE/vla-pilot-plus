"""
Phase 1 Evidence Collection — Task 3
======================================
Compare official RDT inference path vs. VLS custom denoising loop on identical input.

Hypothesis under test (H1):
  _predict_unguided initialises x_t as (B, 64, 8) and zero-pads to 128D.
  RDTRunner.conditional_sample initialises noisy_action as (B, 64, 128) — full Gaussian.
  If H1 is true, the two paths will produce outputs with very different temporal structure.

Usage (from project root, vla-pilot env active):
  python docs/superpowers/evidence/round-1/stats/loop_comparison.py

Outputs:
  docs/superpowers/evidence/round-1/stats/loop_comparison_output.txt  (stats)
  docs/superpowers/evidence/round-1/stats/loop_comparison_trajectories.pt  (tensors)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image as PILImage

# ── Path setup ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parents[5]  # .worktrees/feat/rdt-integration/
RDT_ROOT     = PROJECT_ROOT / "third_party" / "rdt"
CKPT_ROOT    = Path("/mnt/data/hf_cache/hub/models--robotics-diffusion-transformer--maniskill-model"
                    "/snapshots/9622afab2b7ce2312a6cf1febc526928589b77eb")
CKPT_WEIGHTS = CKPT_ROOT / "rdt" / "mp_rank_00_model_states.pt"
CKPT_LANG    = CKPT_ROOT / "lang_embeds"
BASE_CONFIG  = RDT_ROOT / "configs" / "base.yaml"
EVIDENCE_DIR = Path(__file__).parent
OUT_TXT      = EVIDENCE_DIR / "loop_comparison_output.txt"
OUT_PT       = EVIDENCE_DIR / "loop_comparison_trajectories.pt"

for p in (PROJECT_ROOT, RDT_ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _black_pil():
    return PILImage.fromarray(np.zeros((384, 384, 3), dtype=np.uint8))


def _make_fake_obs():
    """Synthetic frozen observation — deterministic, no GPU needed for creation."""
    torch.manual_seed(42)
    images = [_black_pil()] * 6
    # proprio: 8D — first 7 are Franka home config joint angles (radians), gripper 0
    proprio_np = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785, 0.0], dtype=np.float32)
    proprio = torch.from_numpy(proprio_np).unsqueeze(0)  # (1, 8)
    return images, proprio


def _autocorr(traj: np.ndarray) -> float:
    """
    Mean lag-1 autocorrelation across all dims of a (T, D) trajectory.
    High value → temporally smooth (structured). Low value → white-noise-like.
    """
    T, D = traj.shape
    if T < 2:
        return 0.0
    corrs = []
    for d in range(D):
        x = traj[:, d]
        if x.std() < 1e-9:
            continue
        x = x - x.mean()
        corrs.append(float(np.corrcoef(x[:-1], x[1:])[0, 1]))
    return float(np.mean(corrs)) if corrs else 0.0


def _per_dim_stats(traj: np.ndarray, label: str) -> dict:
    """Compute per-dimension and aggregate stats for a (T, D) trajectory."""
    stats = {
        "label": label,
        "shape": list(traj.shape),
        "mean_abs": float(np.mean(np.abs(traj))),
        "std": float(np.std(traj)),
        "min": float(traj.min()),
        "max": float(traj.max()),
        "has_nan": bool(np.any(np.isnan(traj))),
        "has_inf": bool(np.any(np.isinf(traj))),
        "lag1_autocorr": _autocorr(traj),
        "per_dim_mean": traj.mean(axis=0).tolist(),
        "per_dim_std": traj.std(axis=0).tolist(),
    }
    return stats


def _format_stats(s: dict) -> str:
    lines = [
        f"  Path:       {s['label']}",
        f"  Shape:      {s['shape']}",
        f"  mean|x|:    {s['mean_abs']:.5f}",
        f"  std:        {s['std']:.5f}",
        f"  range:      [{s['min']:.4f}, {s['max']:.4f}]",
        f"  NaN/Inf:    {s['has_nan']}/{s['has_inf']}",
        f"  lag-1 autocorr: {s['lag1_autocorr']:.4f}  (>0.5 = smooth, <0.1 = noisy)",
        f"  per_dim_mean: {[f'{v:.3f}' for v in s['per_dim_mean']]}",
        f"  per_dim_std:  {[f'{v:.3f}' for v in s['per_dim_std']]}",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    lines = []
    def log(msg=""):
        print(msg)
        lines.append(msg)

    log("=" * 70)
    log("RDT Loop Comparison — Phase 1 Evidence Collection")
    log("=" * 70)
    log(f"Checkpoint:  {CKPT_WEIGHTS}")
    log(f"Config:      {BASE_CONFIG}")
    log()

    # ── Load model ────────────────────────────────────────────────────────────
    import yaml
    from scripts.maniskill_model import create_model

    log("Loading RDT model …")
    t0 = time.time()
    with open(BASE_CONFIG) as f:
        args = yaml.safe_load(f)

    os.environ["HF_HUB_OFFLINE"] = "1"
    real_model = create_model(
        args,
        pretrained=str(CKPT_WEIGHTS),
        pretrained_text_encoder_name_or_path="google/t5-v1_1-xxl",
        pretrained_vision_encoder_name_or_path="google/siglip-so400m-patch14-384",
    )
    device = real_model.device
    log(f"Model loaded in {time.time()-t0:.1f}s  device={device}")

    # ── Language embedding ────────────────────────────────────────────────────
    log()
    log("─" * 50)
    log("TASK 2 — Language Embedding Evidence")
    log("─" * 50)

    task_str = "open the top drawer of the cabinet"
    task_key = hashlib.md5(task_str.encode()).hexdigest()
    log(f"Task string:  {task_str!r}")
    log(f"MD5 key:      {task_key}")

    # Check cache
    cache_hit = (CKPT_LANG / f"{task_key}.pt").exists()
    local_cache_hit = (PROJECT_ROOT / "data" / "rdt_lang_embeds" / f"{task_key}.pt").exists()
    log(f"Cache hit (checkpoint lang_embeds): {cache_hit}")
    log(f"Cache hit (data/rdt_lang_embeds):   {local_cache_hit}")

    # Encode via real model's T5
    log("Computing embedding via real_model.encode_instruction …")
    with torch.no_grad():
        text_embed = real_model.encode_instruction(task_str, device=str(device))
    text_embed_cpu = text_embed.float().cpu()
    log(f"text_embed shape: {tuple(text_embed_cpu.shape)}")
    log(f"text_embed norm:  {text_embed_cpu.norm():.4f}")
    log(f"text_embed max:   {text_embed_cpu.abs().max():.4f}")
    log(f"text_embed IS ZERO: {bool(text_embed_cpu.norm() < 0.01)}")

    # Second task to check sensitivity
    task_str2 = "push the plate to the left"
    with torch.no_grad():
        text_embed2 = real_model.encode_instruction(task_str2, device=str(device))
    text_embed2_cpu = text_embed2.float().cpu()
    embed_diff = (text_embed_cpu[0, 0] - text_embed2_cpu[0, 0]).norm().item()
    log(f"\nSecond task:  {task_str2!r}")
    log(f"  norm:       {text_embed2_cpu.norm():.4f}")
    log(f"  first-token diff from task1: {embed_diff:.4f}  (>1 = distinct embeddings)")

    lang_embed_evidence = {
        "task1": task_str,
        "task1_norm": float(text_embed_cpu.norm()),
        "task1_shape": list(text_embed_cpu.shape),
        "task1_is_zero": bool(text_embed_cpu.norm() < 0.01),
        "task2": task_str2,
        "task2_norm": float(text_embed2_cpu.norm()),
        "task1_task2_first_token_diff": embed_diff,
    }

    # ── Proprio evidence ──────────────────────────────────────────────────────
    log()
    log("─" * 50)
    log("TASK 5 — Proprio Input Evidence (synthetic Franka home config)")
    log("─" * 50)
    images, proprio = _make_fake_obs()
    log(f"proprio shape:  {tuple(proprio.shape)}")
    log(f"proprio values: {proprio[0].tolist()}")
    log(f"Expected range for joint angles: [-3.14, 3.14] (most joints)")
    log(f"Values in joint-angle range: {all(abs(v) < 4.0 for v in proprio[0].tolist())}")

    # ── Official inference path ───────────────────────────────────────────────
    log()
    log("─" * 50)
    log("TASK 3 — Official step() path")
    log("─" * 50)
    torch.manual_seed(7)
    log("Running real_model.step() …")
    t0 = time.time()
    with torch.no_grad():
        official_out = real_model.step(
            proprio=proprio.to(device),
            images=images,
            text_embeds=text_embed,
        )
    log(f"  Elapsed: {time.time()-t0:.2f}s")
    log(f"  Output shape: {tuple(official_out.shape)}")
    official_np = official_out[0].float().cpu().numpy()  # (64, 8) or (64, 7)?
    official_stats = _per_dim_stats(official_np, "official_step()")
    log(_format_stats(official_stats))

    # ── Custom inference path ─────────────────────────────────────────────────
    log()
    log("─" * 50)
    log("TASK 3 — Custom _predict_unguided() path")
    log("─" * 50)

    sys.path.insert(0, str(PROJECT_ROOT / "core"))
    from rdt_policy_steer import RDTSteer, _RDTModelAdapter

    rdt_adapter = _RDTModelAdapter(real_model)
    steer = RDTSteer(rdt_adapter, num_inference_steps=55)

    # Encode inputs once (same as production code path)
    with torch.no_grad():
        cond = rdt_adapter.encode_inputs(
            proprio.to(device),
            images,
            text_embed,
        )
    log(f"  cond keys: {list(cond.keys())}")
    if "action_indices" in cond:
        log(f"  action_indices: {cond['action_indices']}")
        log(f"  unified_action_dim: {cond.get('unified_action_dim', '?')}")
        raw_action_dim = len(cond["action_indices"])
        log(f"  raw_action_dim (len(action_indices)): {raw_action_dim}")

    # Log x_t initialization — the critical H1 test point
    log()
    log("  [H1 TEST] x_t initialization:")
    log(f"    custom loop: x_t = randn(B=1, 64, raw_action_dim={raw_action_dim})")
    log(f"    official:    noisy_action = randn(B=1, 64, unified_action_dim=128)")
    log(f"    are these equivalent? {raw_action_dim == 128}")

    # Inspect the DiTAdapter's inflate step
    log()
    log("  [H1 TEST] x_unified inflation in _RDTDiTAdapter.forward:")
    log(f"    x_unified = zeros(B, H, 128)")
    log(f"    x_unified[:, :, action_indices] = x_t[:, :, :{raw_action_dim}]")
    log(f"    → {128 - raw_action_dim} of 128 dims are ZERO throughout denoising")

    torch.manual_seed(7)  # same seed as official run
    log()
    log("  Running _predict_unguided() …")
    t0 = time.time()
    custom_out = steer._predict_unguided(
        proprio.to(device),
        images,
        text_embed,
        B=1,
    )
    log(f"  Elapsed: {time.time()-t0:.2f}s")
    log(f"  Output shape: {tuple(custom_out.shape)}")
    custom_np = custom_out[0].float().cpu().numpy()  # (64, 8) normalized
    custom_stats = _per_dim_stats(custom_np, "custom _predict_unguided()")
    log(_format_stats(custom_stats))

    # ── Side-by-side comparison ───────────────────────────────────────────────
    log()
    log("─" * 50)
    log("COMPARISON: official step() vs custom _predict_unguided()")
    log("─" * 50)

    # Denormalize official output back to joint-angle space for fair comparison
    # official_out from real_model.step() is already denormalized (absolute joint angles)
    # custom_out is normalized ∈ [-1, 1]
    # Bring official back to [-1, 1] for apples-to-apples norm comparison
    from core.rdt_action_converter import RDT_ACTION_MIN, RDT_ACTION_MAX
    official_arm = official_np[:, :7]  # (64, 7)
    official_norm = 2.0 * (official_arm - RDT_ACTION_MIN) / (RDT_ACTION_MAX - RDT_ACTION_MIN) - 1.0

    custom_arm = custom_np[:, :7]  # (64, 7) already ∈ [-1, 1]

    log(f"  official (re-normalized arm, first 3 steps):")
    for i in range(min(3, official_norm.shape[0])):
        log(f"    step {i}: {[f'{v:.3f}' for v in official_norm[i]]}")

    log(f"  custom (normalized arm, first 3 steps):")
    for i in range(min(3, custom_arm.shape[0])):
        log(f"    step {i}: {[f'{v:.3f}' for v in custom_arm[i]]}")

    diff_arr = official_norm - custom_arm
    log(f"\n  Mean abs diff (official_norm vs custom): {np.abs(diff_arr).mean():.5f}")
    log(f"  Official arm autocorr:  {_autocorr(official_norm):.4f}")
    log(f"  Custom arm autocorr:    {_autocorr(custom_arm):.4f}")
    log()
    log("  Interpretation:")
    if _autocorr(official_norm) > 0.5 and _autocorr(custom_arm) < 0.2:
        log("  *** H1 CONFIRMED: official trajectory is smooth/structured;")
        log("      custom trajectory is temporally random (low autocorr).")
        log("      Root cause: x_t initialized in 8D, 120 dims permanently zero.")
    elif _autocorr(official_norm) > 0.3 and _autocorr(custom_arm) > 0.3:
        log("  H1 LIKELY REJECTED: both paths produce temporally structured output.")
        log("  Denoising loop dimensionality may not be the primary cause.")
    elif _autocorr(official_norm) < 0.2 and _autocorr(custom_arm) < 0.2:
        log("  BOTH PATHS ARE RANDOM — model loading may be broken.")
        log("  Check weight loading, device placement, or scheduler setup.")
    else:
        log(f"  MIXED EVIDENCE: official autocorr={_autocorr(official_norm):.3f}, "
            f"custom autocorr={_autocorr(custom_arm):.3f}. Manual inspection needed.")

    # ── Action conversion stats ───────────────────────────────────────────────
    log()
    log("─" * 50)
    log("TASK 6 — Raw action output inspection")
    log("─" * 50)

    from core.rdt_action_converter import rdt_chunk_to_libero_actions, FRANKA_Q_MIN, FRANKA_Q_MAX
    # Use Franka home config as current joints
    current_joints = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785], dtype=np.float64)
    libero_actions = rdt_chunk_to_libero_actions(
        custom_np[:8],    # first 8 steps
        current_joints,
    )
    log(f"  libero_actions shape: {libero_actions.shape}")
    log(f"  pos_delta (first 3 steps):")
    for i in range(min(3, libero_actions.shape[0])):
        log(f"    step {i}: pos={[f'{v:.4f}' for v in libero_actions[i, :3]]}  "
            f"ori={[f'{v:.4f}' for v in libero_actions[i, 3:6]]}  grip={libero_actions[i, 6]:.4f}")
    log(f"  pos abs mean: {np.abs(libero_actions[:, :3]).mean():.5f}")
    log(f"  pos abs max:  {np.abs(libero_actions[:, :3]).max():.5f}")
    saturated = np.abs(libero_actions[:, :3]) > 0.99
    log(f"  pos dims saturated (>0.99): {saturated.sum()}/{saturated.size}")
    if saturated.sum() > libero_actions[:, :3].size * 0.3:
        log("  *** H4 LIKELY: >30% of position dims are saturated — scale too large")
    elif np.abs(libero_actions[:, :3]).mean() < 0.005:
        log("  *** H4 possible: mean position action near zero — scale too small or FK degenerate")
    else:
        log("  H4 not detected: position deltas within reasonable range")

    # ── Summary ───────────────────────────────────────────────────────────────
    log()
    log("=" * 70)
    log("EVIDENCE SUMMARY")
    log("=" * 70)
    log(f"H1 (denoising loop): official autocorr={_autocorr(official_norm):.4f}, "
        f"custom autocorr={_autocorr(custom_arm):.4f}")
    log(f"H2 (lang embed zero): norm={lang_embed_evidence['task1_norm']:.3f}, "
        f"is_zero={lang_embed_evidence['task1_is_zero']}")
    log(f"H3 (image flip): not testable without live LIBERO env — see image_check.py")
    log(f"H4 (action scale): pos_max={np.abs(libero_actions[:, :3]).max():.5f}, "
        f"sat_frac={saturated.sum()}/{saturated.size}")

    # Save tensors
    torch.save({
        "official_out": official_out.cpu(),
        "custom_out": custom_out.cpu(),
        "official_norm_arm": torch.from_numpy(official_norm),
        "custom_arm": torch.from_numpy(custom_arm),
    }, OUT_PT)
    log(f"\nTensor trajectories saved → {OUT_PT}")

    # Save text output
    full_text = "\n".join(lines)
    with open(OUT_TXT, "w") as f:
        f.write(full_text)
    log(f"Text output saved → {OUT_TXT}")

    return {
        "official_autocorr": _autocorr(official_norm),
        "custom_autocorr": _autocorr(custom_arm),
        "lang_norm": lang_embed_evidence["task1_norm"],
        "lang_is_zero": lang_embed_evidence["task1_is_zero"],
        "pos_sat_frac": saturated.sum() / saturated.size,
    }


if __name__ == "__main__":
    main()
