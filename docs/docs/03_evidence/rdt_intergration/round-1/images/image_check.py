"""
Phase 1 Evidence Collection — Task 4: Image Orientation Inspection
====================================================================
Simulates what RDTObsProcessor receives from LIBERO, saves both:
  1. The raw image as returned by LiberoProcessorStep (includes 180° flip)
  2. A note on whether orientation is correct for the ManiSkill checkpoint

Usage (from project root, vla-pilot env):
  python docs/superpowers/evidence/round-1/images/image_check.py

To use a real LIBERO frame, set REAL_LIBERO=1 and this script will
attempt to init LIBERO, step once with a zero action, and save the actual
agentview frame through the LiberoProcessorStep pipeline.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).parents[5]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "rdt"))

EVIDENCE_DIR = Path(__file__).parent
OUT_FLIP_CHECK = EVIDENCE_DIR / "flip_test_synthetic.png"
OUT_NOTES = EVIDENCE_DIR / "image_check_notes.txt"

REAL_LIBERO = os.environ.get("REAL_LIBERO", "0") == "1"


def _make_test_image():
    """Create a synthetic image with an obvious top/bottom marker."""
    img = Image.new("RGB", (256, 256), (200, 200, 200))
    draw = ImageDraw.Draw(img)
    # Label: TOP in green at top, BOTTOM in red at bottom
    draw.rectangle([0, 0, 256, 20], fill=(0, 200, 0))
    draw.rectangle([0, 236, 256, 256], fill=(200, 0, 0))
    draw.text((90, 3), "TOP (green)", fill=(255, 255, 255))
    draw.text((80, 238), "BOTTOM (red)", fill=(255, 255, 255))
    # Draw a simple triangle pointing UP so orientation is obvious
    draw.polygon([(128, 30), (80, 140), (176, 140)], fill=(0, 0, 200))
    draw.text((110, 145), "triangle\npoints UP", fill=(0, 0, 0))
    return img


def check_libero_preprocessor_flip():
    """
    Trace the LiberoProcessorStep to confirm it applies torch.flip(img, dims=[2, 3]).
    This is a code-path trace — does not require running LIBERO.
    """
    import torch
    lines = []
    lines.append("=== LiberoProcessorStep flip analysis ===\n")

    try:
        sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "lerobot"))
        from lerobot.processor.env_processor import LiberoProcessorStep

        # Inspect source
        import inspect
        src = inspect.getsource(LiberoProcessorStep._process_observation)
        lines.append("LiberoProcessorStep._process_observation source:")
        lines.append("-" * 40)
        lines.append(src)
        lines.append("-" * 40)

        if "torch.flip" in src and "dims=[2, 3]" in src or "dims=[2,3]" in src:
            lines.append("\n*** CONFIRMED: torch.flip(img, dims=[2, 3]) is present.")
            lines.append("    Images are flipped 180° (both H and W axes) before reaching RDTSteer.")
            flip_confirmed = True
        elif "torch.flip" in src:
            lines.append("\n*** torch.flip present but dims may differ — check above source.")
            flip_confirmed = None
        else:
            lines.append("\n*** torch.flip NOT found in _process_observation.")
            flip_confirmed = False

        lines.append(f"\nflip_confirmed: {flip_confirmed}")

    except ImportError as e:
        lines.append(f"Could not import LiberoProcessorStep: {e}")
        lines.append("Tracing manually instead.")
        flip_confirmed = None

    return "\n".join(lines), flip_confirmed


def simulate_flip_effect():
    """
    Show what the 180° flip does to a synthetic image with clear orientation markers.
    Saves side-by-side: original | after LiberoProcessorStep flip.
    """
    import torch

    orig_pil = _make_test_image()
    orig_np = np.array(orig_pil)

    # Simulate LiberoProcessorStep: torch.flip(img, dims=[2, 3])
    # Input convention: (B, C, H, W) with values [0, 255] uint8
    t = torch.from_numpy(orig_np).permute(2, 0, 1).unsqueeze(0).float()  # (1, 3, H, W)
    t_flipped = torch.flip(t, dims=[2, 3])  # flip both H and W → 180°
    flipped_np = t_flipped[0].byte().permute(1, 2, 0).numpy()
    flipped_pil = Image.fromarray(flipped_np)

    # Composite side-by-side
    W, H = orig_pil.size
    combined = Image.new("RGB", (W * 2 + 10, H + 30), (240, 240, 240))
    combined.paste(orig_pil, (0, 30))
    combined.paste(flipped_pil, (W + 10, 30))

    draw = ImageDraw.Draw(combined)
    draw.text((W // 2 - 60, 5), "ORIGINAL (correct)", fill=(0, 0, 0))
    draw.text((W + 10 + W // 2 - 80, 5), "AFTER LIBERO FLIP (wrong)", fill=(200, 0, 0))

    combined.save(OUT_FLIP_CHECK)
    return combined


def get_real_libero_frame():
    """Attempt to get an actual frame from LIBERO with the flip applied."""
    import torch

    # We need to check what libero task and suite to use
    # Try to import the adapter
    try:
        from core.env_adapters.libero_adapter import LiberoAdapter
        from omegaconf import OmegaConf
    except ImportError as e:
        return None, f"LiberoAdapter import failed: {e}"

    try:
        # Minimal config for one LIBERO step
        # Use a simple task from libero_goal
        cfg = OmegaConf.create({
            "suite_name": "libero_goal",
            "task_name": "KITCHEN_SCENE6_put_the_yellow_and_white_mug_to_the_right_of_the_plate",
            "episode_idx": 0,
            "img_height": 128,
            "img_width": 128,
            "use_eye_in_hand": True,
        })

        adapter = LiberoAdapter(cfg)
        obs = adapter.reset()

        # Save the raw (pre-flip) agentview image
        raw_key = "observation.images.image"
        if raw_key not in obs:
            return None, f"Key {raw_key!r} not in obs. Keys: {list(obs.keys())}"

        raw_t = obs[raw_key][0]  # (3, H, W)
        raw_np = (raw_t.detach().cpu().clamp(0, 1) * 255).byte().permute(1, 2, 0).numpy()
        raw_pil = Image.fromarray(raw_np)
        raw_pil_resized = raw_pil.resize((384, 384), Image.BILINEAR)
        raw_pil_resized.save(EVIDENCE_DIR / "libero_raw_frame.png")

        # Apply flip
        t_flip = torch.flip(obs[raw_key], dims=[1, 2])  # (3, H, W) — dims for (C, H, W)
        # Actually LiberoProcessorStep uses (B, C, H, W) so dims=[2, 3]
        t_b = obs[raw_key].unsqueeze(0)
        t_flipped = torch.flip(t_b, dims=[2, 3])[0]
        flip_np = (t_flipped.detach().cpu().clamp(0, 1) * 255).byte().permute(1, 2, 0).numpy()
        flip_pil = Image.fromarray(flip_np).resize((384, 384), Image.BILINEAR)
        flip_pil.save(EVIDENCE_DIR / "libero_flipped_frame.png")

        adapter.close()
        return raw_pil_resized, None
    except Exception as e:
        import traceback
        return None, traceback.format_exc()


def main():
    notes = []
    def log(msg=""):
        print(msg)
        notes.append(msg)

    log("=== Phase 1 Task 4 — Image Orientation Inspection ===\n")

    # Step 1: Source-level trace of the flip
    flip_analysis, flip_confirmed = check_libero_preprocessor_flip()
    log(flip_analysis)

    # Step 2: Synthetic visualization
    log("\nGenerating synthetic flip visualization …")
    simulate_flip_effect()
    log(f"Saved side-by-side flip demo → {OUT_FLIP_CHECK}")
    log("Inspect the image: if the right panel (AFTER LIBERO FLIP) shows green at bottom,")
    log("the 180° flip IS confirmed to invert the scene orientation.")

    # Step 3: Real LIBERO frame if requested
    if REAL_LIBERO:
        log("\nREAL_LIBERO=1 — attempting to capture actual LIBERO frame …")
        frame, err = get_real_libero_frame()
        if err:
            log(f"  Failed: {err}")
        else:
            log("  Saved: libero_raw_frame.png (before flip) and libero_flipped_frame.png (after flip)")
            log("  Visually check: does libero_flipped_frame.png show the table upside-down?")

    # Summary for H3
    log()
    log("─" * 50)
    log("H3 ASSESSMENT:")
    if flip_confirmed is True:
        log("  CONFIRMED (code-level): torch.flip(dims=[2,3]) is applied in LiberoProcessorStep.")
        log("  ALL images reaching RDTSteer are 180°-rotated relative to ManiSkill training data.")
        log("  The ManiSkill SigLIP encoder was NOT trained on inverted SAPIEN images.")
        log("  Impact: Image conditioning provides incorrect/misleading spatial features.")
        log("  However: this bug ALONE would degrade performance, not cause fully random motion.")
    elif flip_confirmed is False:
        log("  REJECTED (code-level): torch.flip not found in LiberoProcessorStep.")
    else:
        log("  UNKNOWN: manual source inspection required.")

    full_text = "\n".join(notes)
    with open(OUT_NOTES, "w") as f:
        f.write(full_text)
    log(f"\nNotes saved → {OUT_NOTES}")
    print(f"\nNotes saved → {OUT_NOTES}")


if __name__ == "__main__":
    main()
