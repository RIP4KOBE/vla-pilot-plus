# `run_001_allocation_ecology_diagnostic` Protocol v2 Amendment

Status: `PROTOCOL_LOCKED_V2`

Locked UTC: `2026-08-10T15:24:05Z`

Supersedes only the trace-stage accounting statements in protocol v1 commit `dcf234b6999165de0a5bca4a8e44332896cc61dc`. All hypotheses, estimators, thresholds, support/refute gates, task linkage, commands, scope and precommitted decisions in `protocol.md` remain unchanged.

## Reason for amendment

Before analyzer implementation, a read-only schema check found that v1 correctly expected 540 trace files but incorrectly multiplied every file by the original 10 EDS iterations. Budget-study traces preserve their configured `cem_iters` of 15, 20, or 25. No parent-quality/reward result, aggregate margin, bootstrap, slot share or gate outcome was computed before this amendment.

Verified examples:

- original sparse trace: metadata `cem_iters=10`, 10 `full_process_after_rollout` stages;
- budget uniform p32/k15 trace: metadata `cem_iters=15`, 15 stages;
- budget sparse p64/k25 trace: metadata `cem_iters=25`, 25 stages.

## Corrected accounting lock

- Original valid profiles: `9 profiles × 20 traces × 10 stages = 1,800` full-process trace-iterations.
- Budget valid profiles: two families, each with three population sizes and `cem_iters={15,20,25}`: `2 × 3 × (15+20+25) × 20 = 7,200` trace-iterations.
- Correct total: `540` trace files and `9,000` `full_process_after_rollout` stages.

Validity gate 1 is therefore corrected to:

> exact trace accounting: 540 files and 9,000 expected full-process stages; each file's observed stage count must equal its own metadata `cem_iters`; no unsafe load, malformed stage, nonfinite reward, missing rank, or population/slot mismatch.

The H4 saturated-data minimum remains the preregistered `>=2,700` iterations; changing the total accounting does not change that threshold. All other v1 text remains binding.
