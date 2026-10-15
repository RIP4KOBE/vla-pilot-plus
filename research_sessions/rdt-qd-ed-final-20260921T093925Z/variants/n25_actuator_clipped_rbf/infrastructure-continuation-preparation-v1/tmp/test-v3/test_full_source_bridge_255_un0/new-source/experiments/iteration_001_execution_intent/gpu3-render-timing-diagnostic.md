# GPU3 render-timing diagnostic — prospective protocol

Approved within the user-authorized bounded engineering review before dispatch. Subsequent execution is physical GPU3 only, one exclusive worker, stable-idle admission and verified CUDA/EGL mapping; external processes are not interrupted or shared. This supersedes the unlaunched GPU7 draft.

## Evidence and bounded question

N1 Q0 r3 remains an invalid, nonretryable native SIGABRT failure after a successful Codex Stage call and guidance toggle. Its root cause is unknown. Separate GPU6 C0 diagnostic attempt infrastructure-aborted on external contention: 13 completed steps spent 236.709 seconds in visualization and 261.282 seconds in adapter stepping, versus 6.989 seconds in two fresh policy calls. Both slow paths reach production sim.render.

Reuse the completed, accounted GPU6 B1 native probe __gpu6_native_b1__b689d3b01c36: scope, synthetic seed/task, policy configuration, script and common code fingerprints, runtime inventory and evidence digest match the unlaunched GPU7 probe. This proves bare B1 inference only; it proves neither GPU3 binding nor production render/transition correctness. Do not repeat it merely on another device.

Question: which native rendering, pixel readback, observable, physics or controller boundary accounts for the latency, and where does any native abort occur? No algorithm benefit is hypothesized.

## Only intervention

Apply timing patch SHA256 7d62df655c630a318c28f28ea7a99765ab1482880a179e3a63fcd7207ae927da reviewed against source 8771eaa74ede4159efb004e0709232175a6c0b8d. Changes: main.py, core/render_phase_diagnostics.py and two CPU tests. Eighteen CPU tests pass and original main operations have identical AST after removing observational statements. Enable faulthandler and host phase boundaries on existing instances. Production GL/EGL identity-query proposal is NOT applied.

No change to threads, cameras, render calls, simulation steps, actions, image handling, model, search, Stage prompts/triggers, success definition, profile or timeout. Original calls, arguments, result objects and exceptions remain unchanged. No new contexts, make_current calls, renders or simulator branches. Timings are inclusive host intervals, with measured nested observer overhead; never sum parent and child or claim isolated lock wait/kernel time. Original scientific latency metrics remain unchanged. Diagnostic walltime is budgeted.

## Exact recovery and budget

Dispatch at most one recovery of rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00_r1__03c5d2b4a1df, whose terminal infrastructure-abort explicitly allows recovery. New key gpu3_native_c0_t00_r2; retry_of is that full latest attempt ID. The prior parent 6e57273c45b3 recovery was consumed concurrently by the other worktree on physical GPU5 and must not be reused. That run stopped after 132.6506171328947 seconds with GPU5/PID115030-matched Xid31 immediately after the first instrumented pixel-readback entry. All samples and resource costs remain retained; Xid31 alone does not establish hardware rather than application/driver causality. Preserve split dev, iteration GPU6_NATIVE_C0 (legacy identity, not execution device), profile C0, task_id 0, env_seed 1969522881, policy_seed 1969522881, init_index 0, seed_block dev and timeout 1800 seconds. Use recovery bucket. Preserve init-row SHA256 48b759458f7f8b6c4ee24238038db71ab908360b36e58729d053daf269d544ae and frozen scientific inputs.

Do not retry invalid N1 Q0, replace its cohort cell or adopt this diagnostic as a control. One dispatch then coordinator review; no automatic post-dispatch retry. Count all startup, provider wait and cleanup GPU walltime and one of 240 attempts within 48 GPU-hours. Preserve 14-hour validation and 10-hour formal reserves and their 60/40 episode reservations. Account GPU3 zero-step CUDA/EGL healthcheck separately, before freezing the episode runtime.

## Decision

Retain phase timing, native stack, full task outcome and cost evidence. Actual production context identity remains Unknown unless already directly observed; synthetic mapping alone is insufficient. A completed or faster diagnostic is not scientific acceptance. N1, validation and formal promotion stay closed. An evidence-based engineering repair must receive regression validation and a prospectively frozen common-baseline protocol; earlier failures and cohorts remain intact.

## Native fault observation during GPU3 execution

Read only kernel NVIDIA records at or after dispatch for the admitted PCI device and owned worker PID. Retain Xid details as diagnostic evidence. If another Xid31/109 is directly attributable to this worker, interrupt only this owned queue for cleanup and preserve the failed sample; do not automatically recover again. This is a bounded diagnostic stop, not scientific acceptance or proof of hardware fault. Do not reset GPUs, change host drivers, attach debuggers or stop unrelated workers.

Reference: https://docs.nvidia.com/deploy/xid-errors/introduction.html and https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html (accessed 2026-09-22). NVIDIA treats Xid as a debugging starting point with application, software and hardware causes possible.
