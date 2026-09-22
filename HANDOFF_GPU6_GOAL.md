# LATEST: user switches to GPU5

GPU5-only now supersedes all older GPU6-only instructions below. The old CPU queue32780 was stopped before any recovery dispatch. Keep this worktree/branch/artifact root and legacy episode key; no budget/outcome reset. Read `experiments/iteration_001_execution_intent/gpu5-migration-amendment.md`. GPU5 stability/context check and new frozen plan are being prepared. No external processes stopped. Goal object wording/status is stale (GPU6/paused); latest user instruction governsGPU5.

Verified queue status `waiting` at 2026-09-22T07:42:19.986313+00:00; GPU6 external PID4156326, 78745MiB. Full progress report: artifact `analysis/gpu6-progress-20260922.md`.

# Active frozen queue

New GPU6-only queue PID32780, start ticks373818892. Frozen HEAD `3f50b356ebcaab22814896fdfa873471feb2dd96`, plan `data/qd-ed-gpu6-c0-xid-plan.json`, SHA256 `9f5eaf4b19329e44f297cc54c04bf698f111912630e8db0ead7cec84b7942dd7`. Status/process/log: artifact `runtime/gpu6-c0-xid-queue-*`. Initial startup hashes model bytes; then scans every30s and requires120s continuously free. Exactly one `gpu6_native_c0_t00_r1`; no automatic second attempt or30-cell dispatch. Do not advance HEAD or edit frozen code/config/protocol while queue/worker is alive.280 relevant CPU tests passed; actual journal monitor smoke passed without a GPU context.

# GPU6 execution handoff

Current worktree/branch: `/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z` / `exp/rdt-qd-ed-gpu6-20260922T063626Z`.
Artifacts: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z`.

User authorized tests/conditional iteration and GPU6 only. Keep scanning and use it once free. No external-process termination, other GPU, device reset or system driver change. No Arbor/Orchestra/Superpowers or subagents invoked. Goal API remains paused after user interruption; current work continues, automatic goal turns need UI resume.

## Current evidence

CUDA/EGL identity probe and synthetic real-model B1 inference passed. C0 diagnostic `...gpu6_native_c0_t00__6e57273c45b3` was infrastructure-aborted when an external GPU6 PID appeared after695.836s. It completed13 steps and no Stage calls. Fresh model search3.9s; adapter and visualization phases repeatedly~21s each. New kernel audit binds five Xid31/109 events to its PID4130356 and five to previous Q0 PID4006998. These establish graphics failures, not the exact code/driver/hardware root. Do not change the existing terminal attempt records.

Audit: `analysis/gpu6-xid-audit/audit.json` and raw journal JSONL in the artifact root. Historical same-driver evidence used two GPUs to isolate CUDA/EGL; do not apply under current GPU6-only scope.

## Current action

Old waiting queue4171021 was stopped before dispatch for an observer upgrade; zero new attempts/cost. Commit and refreeze a new plan for exactly `gpu6_native_c0_t00_r1`, same identity, explicit retry_of C0, recovery budget. Use new MuJoCo scalar timing wrappers and prospective kernel Xid31/109 monitor. Read `experiments/iteration_001_execution_intent/gpu6-kernel-xid-amendment.md`. Relaunch30s polling/120s idle on GPU6, one recovery only, stop for review. Do not change HEAD/frozen code while the new queue is alive.

## Scientific scope and accounting

All three ledgers and runner/state locks are symlinked to the parent study. Preserve shared append-only costs; synchronize cached state under the state lock if another session adds events. Parent worktree has an independent GPU7-only session; do not stop it or adopt its GPU policy.

Latest accounted snapshot:6 dispatched,4 infrastructure aborts,2 invalid outcomes,0 valid,0 running;0.660632021GPU-hours. Tally may change through the shared ledger. Limits240 attempts/48GPU-hours; development100 includes diagnostics; validation60/formal40 and14h/10h protected.

First30 cells C0/Q0/N1×10 tasks are in `data/gpu6-first-round-matrix.csv`, PENDING_ENGINEERING_READY_NOT_DISPATCHABLE. N1 is CPU-ready, not evaluated. Preserve old incomplete cohorts; a separate N1R comparison requires evidence-supported common-runtime repair, not just relabeling failures. Follow updated next-round plan gates. Target≥5/10 is unachieved. ETAunknown until runtime works;8–15h is only a conditional reservation after repair.

Earlier detailed handoff is preserved in artifact `analysis/gpu6-xid-audit/HANDOFF_before_xid_audit.md`.
