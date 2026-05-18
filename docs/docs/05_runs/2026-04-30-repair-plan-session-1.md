---
session: 2026-04-30-repair-plan-session-1
type: session-log
status: complete
---

# Session Log — Repair Plan Generation

**Date:** 2026-04-30  
**Session:** 1

---

## Inputs Used

| File | Role |
|---|---|
| `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md` | Failure analysis |
| `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md` | Debugging plan |
| `docs/superpowers/evidence/round-1/summary.md` | Evidence round 1 summary |
| `docs/superpowers/evidence/round-1/stats/phase2_hypothesis_discrimination.md` | Hypothesis verdicts |
| `core/rdt_policy_steer.py` | Code to be repaired (read in full) |

---

## Confirmed Root Cause Selected

**H1 — `_predict_unguided` and `_guided_denoise_loop` initialize `x_t` as `(B, 64, 8)` and zero-pad to 128D, while the official `RDTRunner.conditional_sample` uses `(B, 64, 128)` full Gaussian noise.**

This was selected because:
- Quantitative evidence: mean abs diff vs official path = 0.608 in normalized joint space (confirmed by `loop_comparison.py`)
- Mechanism is directly readable in the code (zero-init inflation in `_RDTDiTAdapter.forward`)
- Fix is scoped to one file (`rdt_policy_steer.py`), three locations
- H2 is rejected; H3 is confirmed but secondary

---

## Why Repair Planning Is Justified Now

All Phase 3 entry criteria from the debugging plan are satisfied:
- [x] `loop_comparison_output.txt` exists — H1 confirmed
- [x] `lang_embed_log` captured in comparison output — H2 rejected
- [x] `ext_now.png` / code trace — H3 confirmed
- [x] Action values logged — H4 minor
- [x] `phase2_hypothesis_discrimination.md` exists — primary cause identified
- [x] H1 fix strategy is scoped (2 guard additions + 2 init changes, all in `rdt_policy_steer.py`)

---

## Output File Created

**Repair plan:** `docs/superpowers/plans/2026-04-30-rdt-repair-plan-v1.md`

---

## Recommended Execution Scope

The execution prompt should:
1. Read `core/rdt_policy_steer.py` in full before editing
2. Implement Step 1 (`_RDTDiTAdapter.forward` guard) first
3. Run smoke tests before proceeding
4. Implement Step 2 (`_predict_unguided` 128D init + post-loop projection)
5. Run `loop_comparison.py` and confirm mean abs diff < 0.10
6. Implement Step 3 (`_guided_denoise_loop` same fix)
7. Run smoke tests again
8. Commit (all 3 steps in one commit)
9. Run 1 LIBERO episode; save rollout to `evidence/round-2/rollout_h1_fixed/`
10. Stop — do NOT fix H3 in the same session

**Do not touch:** `rdt_obs_processor.py`, `rdt_action_converter.py`, `main.py`

---

## Next Recommended Prompt

```
Read and execute the repair plan at:
docs/superpowers/plans/2026-04-30-rdt-repair-plan-v1.md

Fix H1 only. Start with Step 1 (the _RDTDiTAdapter.forward guard).
Do not fix H3.
Validate with loop_comparison.py before running a rollout.
```
