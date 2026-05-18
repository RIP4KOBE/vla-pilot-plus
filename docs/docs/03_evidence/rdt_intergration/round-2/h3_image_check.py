"""
H3 fix validation — save a side-by-side showing what RDT sees before and after
the counter-rotation. Uses the same synthetic approach as image_check.py.
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from core.rdt_obs_processor import RDTObsProcessor

# ── Build a synthetic "LIBERO" frame ────────────────────────────────────────
# Use an asymmetric pattern so rotation is immediately visible.
W, H = 128, 128
arr = np.zeros((H, W, 3), dtype=np.uint8)
arr[:H//2, :, :] = [80, 140, 200]   # top half: blue
arr[H//2:, :, :] = [200, 100, 60]   # bottom half: orange
# Draw a white circle in the top-left to make orientation explicit.
for y in range(H):
    for x in range(W):
        if (x - 20)**2 + (y - 20)**2 < 15**2:
            arr[y, x] = [255, 255, 255]

img_original = Image.fromarray(arr)

# ── Simulate the LiberoProcessorStep flip ───────────────────────────────────
t = torch.from_numpy(arr).permute(2, 0, 1).float() / 255.0  # (C, H, W)
# LiberoProcessorStep: torch.flip(img, dims=[2, 3]) on (B, C, H, W)
#                     = torch.flip(img, dims=[1, 2]) on (C, H, W)
t_flipped = torch.flip(t, dims=[1, 2])

# ── What RDT sees WITHOUT the fix ────────────────────────────────────────────
proc_no_fix = RDTObsProcessor()
proc_no_fix._undo_libero_flip = False
img_no_fix = proc_no_fix._tensor_to_pil(t_flipped)

# ── What RDT sees WITH the fix ────────────────────────────────────────────────
proc_fixed = RDTObsProcessor()
proc_fixed._undo_libero_flip = True
img_fixed = proc_fixed._tensor_to_pil(t_flipped)

# ── Save side-by-side ────────────────────────────────────────────────────────
out_w = 3 * 200 + 40
out = Image.new("RGB", (out_w, 240), (30, 30, 30))
for i, (img, label) in enumerate([
    (img_original, "Original scene"),
    (img_no_fix,   "H3 unfixed (what RDT sees)"),
    (img_fixed,    "H3 fixed (correct orientation)"),
]):
    thumb = img.resize((200, 200), Image.BILINEAR)
    out.paste(thumb, (i * 210, 10))
    draw = ImageDraw.Draw(out)
    draw.text((i * 210 + 5, 215), label, fill=(220, 220, 220))

out_path = "docs/superpowers/evidence/round-2/h3_orientation_check.png"
out.save(out_path)
print(f"Saved: {out_path}")

# ── Verify ────────────────────────────────────────────────────────────────────
orig_arr = np.array(img_original.resize((384, 384), Image.BILINEAR))
no_fix_arr = np.array(img_no_fix)
fixed_arr = np.array(img_fixed)

diff_nf = float(np.abs(orig_arr.astype(float) - no_fix_arr.astype(float)).mean())
diff_fx = float(np.abs(orig_arr.astype(float) - fixed_arr.astype(float)).mean())
print(f"Mean pixel diff vs original: no-fix={diff_nf:.1f}  fixed={diff_fx:.1f}")
print(f"Fixed image matches original: {'YES' if diff_fx < 1.0 else 'NO (unexpected)'}")
