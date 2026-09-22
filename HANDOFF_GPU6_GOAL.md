# Latest update: C0 interrupted by external GPU6 process

The original C0 diagnostic child4130356 is dead. Attempt `...gpu6_native_c0_t00__6e57273c45b3` is infrastructure-aborted after695.836222s, not a robot failure or SIGABRT. It reached step13 visualization; no Stage query occurred. External compute PID4156326 was observed onGPU6. Preserved terminal and journal evidence authorize one explicit linked recovery `gpu6_native_c0_t00_r1` under the user's keep-scanning/direct-use instruction. The GPU6-only CPU queue is being frozen/launched; check its process/status files under the new artifact runtime directory. It must not run any other episode. Shared budget snapshot:6 dispatched,4 infrastructure aborts,2 invalid outcomes,0 valid outcomes,0.660632021 GPU-hours. Full30-cell evaluation has not started.

Partial timings locate repeated ~21-second delays in adapter_step and debug_visualization_overlay; first fresh search3.904s. CPU quotas are unlimited on the inspected cgroup ancestors, sampled GPU clocks show no throttle flag. No cause or repair is established. Render-only profiling/nested GL timing is a possible next diagnostic after the current recovery; do not silently change images, reward, seeds, or algorithm.

Everything below is the earlier launch snapshot; its claim that the child is running is superseded.

# GPU6 goal execution handoff

Updated 2026-09-22T06:53:30Z. User authorized this execution, the conditional next-round plan, and GPU6 only. Do not invoke Arbor/Orchestra/Superpowers. Do not create subagents unless newly authorized.

Worktree: /home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z
Branch: exp/rdt-qd-ed-gpu6-20260922T063626Z
Current frozen source: 5cafac6
Artifacts: /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z

Goal was explicitly created. After the user interrupted to say GPU6 was being released, get_goal returned paused; the API has no resume operation. Current execution continues; UI Goal resume is needed for automatic future goal turns. Do not mark complete while experiments remain.

GPU6 was observed idle for128 seconds. CUDA/EGL proof passed (physical6, logical0, EGL5). Focused tests133 passed. B1 synthetic real-model inference passed (116.848773 GPU seconds, finite [1,64,128]); this did not reproduce or resolve the old full-loop SIGABRT. Phase/startup/Stage tests115 passed; AST stripping of added observers restores original Main.

One full closed-loop diagnostic is running, separate from the30-cell comparison:
- Plan: data/qd-ed-gpu6-c0-native-plan.json
- Iteration GPU6_NATIVE_C0; profile C0; task0; env/policy seed1969522881; init0;720-step/1800-second caps.
- Child PID 4130356, start ticks 373535278; verify lifetime before any intervention.
- Output: /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/attempts/rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00__6e57273c45b3
- Unified exec session37796 was used to launch runner (may be unavailable after continuation; inspect process/ledger).
- Inspect eds_eval/phase_timing.jsonl and runner.log for stage/native failure evidence. Native fault handler emits stacks, no locals.
- No automatic retry; diagnostic is charged to development and excluded from candidate promotion. Existing Q0 invalid samples stay invalid.

Accounting: data episode/healthcheck/reservation ledgers and runner/state locks symlink to parent study data. Do not reset counters or replace symlinks. Another session independently manages a GPU7-only diagnostic in the parent worktree; do not stop it or adopt its GPU7 resource policy. Shared runner lock prevents concurrent study dispatch; any journal/state mismatch requires locked reconciliation, never deleting events. Check for in-flight healthcheck/episode before new work. This branch uses GPU6 only.

Next: monitor the diagnostic and identify slow/crashing phase. Apply only evidence-supported engineering repair with shared conditions; then freeze a separate N1R C0/Q0/N1 30-cell comparison using original Dev identities, preserving old incomplete cohort. Keep all prior counts within240 attempts/48 GPU-hours, development≤100 including diagnostic consumption; validation60/formal40 and14h/10h remain protected. Conditional N2/H and unique validation/formal as in docs/01_specs/2026-09-22-rdt-qd-ed-object-swap-next-round-experiment-plan.md. No baseline outcome yet establishes N1 performance.

Initial ETA for30-cell evaluation:8–15h after engineering readiness, diagnostic time additional and unknown. Recalibrate from first2–3 valid complete episodes.
