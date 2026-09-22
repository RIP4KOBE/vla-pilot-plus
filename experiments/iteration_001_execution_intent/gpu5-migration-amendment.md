# GPU5 execution migration — user authorized

The user explicitly instructed: 在GPU5上执行任务. This supersedes GPU6-only resource selection for this execution. Use physicalGPU5 only for both CUDA and EGL; do not use GPU6 or another GPU. Keep the existing worktree, branch, artifact root and append-only shared study ledgers; their GPU6-named paths are provenance identifiers, not the active device binding.

The CPU waiting queue32780 was administratively stopped before dispatch, with verified PID/start ticks, a pidfd and the shared runner lock. It had dispatched no recovery. No attempt, GPU cost, external job or prior outcome was removed or changed.

Prospective execution:
1. Observe GPU5 continuously idle for120seconds (no compute process, no detected CUDA reservation, memory<1024MiB), bind NVIDIA UUID/PCI and EGL enumeration, and run an explicitly accounted CUDA/EGL identity/render probe onGPU5. A GPU6 proof cannot substitute forGPU5 evidence.
2. Freeze the hardware-updated runtime and plan. Execute the same not-yet-dispatched recovery identity `gpu6_native_c0_t00_r1` (legacy key retained intentionally): C0/task0, env and policy seed1969522881, init0, iterationGPU6_NATIVE_C0, recovery bucket, retry_of original infrastructure-aborted C0. Do not fabricate a new independent scientific cell by renaming it.
3. Retain720-step/1800-second limits, frozen policy/encoders/provider/algorithms, fine MuJoCo phase observers and prospective Xid31/109 monitoring onGPU5's PCI bus. Exactly one linked diagnostic, then review. A migration is not proof that the runtime is repaired.
4. Continue the approved scientific comparison and conditional iteration only after evidence supports runtime readiness.240 attempts/48GPU-hours cumulative limits, protected validation/formal reserves and all outcome gates remain unchanged.

The existing goal object still has its original GPU6 wording and paused status; the latest explicit user instruction authorizes and governs GPU5 execution. The available goal API does not edit or resume objectives. Do not create a duplicate goal or falsely mark the unfinished goal complete. Current-turn execution and the independent queue can proceed.
