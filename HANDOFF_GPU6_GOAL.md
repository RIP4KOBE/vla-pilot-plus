# LATEST GPU5 result and next diagnostic

GPU5 C0r1 is terminal INFRASTRUCTURE_ABORT_XID31; child115030 and queue107052 are dead. It ran132.650617s, completed first search5.754640s, then first post-search mjr_readPixels triggered same-PID GRAPHICS Xid31. No environment actions/Stage calls occurred. GPU migration alone did not fix the fault. Audit at artifact`analysis/gpu5-migration/render-fault-audit.json`. Next: separate prospective engineering conditionGPU5_EGL_SERIAL_C0 with opt-in CUDA synchronize+owned-EGL rebinding; see`experiments/iteration_001_execution_intent/gpu5-egl-serialization-diagnostic.md`. Not a replacement for original failed condition; development bucket; one diagnostic then review.

# GPU5 diagnostic dispatched

Actual childPID115030, start ticks374108847, attempt`rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00_r1__03c5d2b4a1df`. CUDA_VISIBLE_DEVICES=5, MUJOCO_EGL_DEVICE_ID=7 verified from allowlisted child environment. Currently initializing Object-Swap; inspect artifact`attempts/rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00_r1__03c5d2b4a1df/runner.log`, `eds_eval/phase_timing.jsonl`, `eds_eval/mujoco_phase_timing.jsonl`, `gpu-kernel-xid.json`, terminal`attempt-result.json`. Do not edit frozen code/HEAD until queue and worker stop. Actual launch1790065657.7Unix;1800s cap.

# ACTIVE GPU5 QUEUE

User explicitly switched to GPU5. New queue PID107052, ticks374086799, frozen HEAD `79cdce092b4e9c32b42634262cc9d1f7e14bec4b`, plan `data/qd-ed-gpu5-c0-xid-plan.json`, SHA256 `e2f82d6afb4bf3f8acbd90675cce631ba59c17caa83a1aeb78a5fc8b553ac940`. Runtime/artifact names retain historicalgpu6 identifier. GPU5 UUIDGPU-048017bf-c58f-b622-ca2e-000b668c651b, EGL7, actual CUDA/EGL probe passed17.995s (resource`rdt-qd-ed-final-20260921T093925Z__gpu5_cuda_egl__e30fffebe9e4`). Queue initial source/model hash check, then30s polls/120s stable idle. Exactly one unchanged legacy recovery key`gpu6_native_c0_t00_r1`, then review. Status/process/log: artifact`runtime/gpu5-c0-xid-queue-*`. Do not edit frozen source or advance HEAD while live. Live progress: tmux`rdt-qd-ed-progress` now displaysGPU5.

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
