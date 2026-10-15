# GPU7 render-timing diagnostic — prospective draft

Status: DRAFT, NOT DISPATCH AUTHORIZATION. Prepared while the frozen zero-simulation B1 probe waits for GPU7. Final source/config/plan must be frozen and reviewed after that probe terminates. PhysicalGPU7 only, single exclusive worker; no other users’ processes may be interrupted or shared.

## Evidence and bounded question

The original Q0 r3 failed with nativeSIGABRT after a successful Stage query and a guidance toggle; it remains an invalid, nonretryable scientific sample. Independent B1 inference in the separate GPU6 artifact namespace completed, but cannot establish transition or EGL causality. Its C0 task0 diagnostic later infrastructure-aborted on externalGPU6 contention. For13 completed steps, visualization overlay used236.709seconds and adapter stepping261.282seconds; two fresh policy calls used6.989seconds and diagnostic artifact generation61.351seconds. Both slow paths reach the same production sim.render/context. Production EGL selection is statically expected from environment bindings but lacks direct context identity evidence.

Question: which native rendering, pixel-readback, observable, physics or controller boundary accounts for the measured latency, and where does any native abort occur? No algorithmic benefit is hypothesized or claimed.

## Minimal prospective intervention

Adopt only reviewed observational phase boundaries, faulthandler and a once-only query of an already-current production GL/EGL context if its observational contract passes review. Do not alter threads, cameras, render calls, simulation steps, actions, image handling, model, search parameters, Stage prompts/triggers, success definition or timeout. Instrumentation failures must not hide or replace original operation exceptions. Do not make a new context, make_current, add renders or run simulator branch rollouts.

## Eligible recovery identity and budget

If root authorizes this diagnostic after reviewing the B1 result and patch, the only candidate recovery is the already infrastructure-aborted C0 diagnostic attempt rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00__6e57273c45b3. Preserve its exact scientific identity: splitdev, iterationGPU6_NATIVE_C0 (legacy identifier, not physical device), profileC0, task0, env_seed1969522881, policy_seed1969522881, init_index0. A new row may be named gpu7_native_c0_t00_r1 with explicit retry_of, budget bucketrecovery and the original1800-second timeout. Do not dispatch or recover the invalid Q0 r3, and do not replace the original N1 control cell with this diagnostic result.

Maximum one dispatched recovery, then root review; account all startup/wait/cleanup GPU walltime and one of240 attempts. Retain all earlier failures/aborts and the protected14h validation/10h formal reserves within48 totalGPU hours. No automatic post-dispatch retry, no extra simulator branch rollout, no Stage transport probe beyond normal frozen episode behavior.

## Result discipline

Record phase timings, native stacks, actual context metadata or explicitUnknown, complete cost telemetry and any task outcome separately as diagnostic evidence. A completed native probe or shorter render time is not scientific acceptance. Candidate, validation and formal promotion remain closed. Any engineering repair requires concrete evidence, regression checks and an explicit same-condition baseline protocol; do not erase failed cohorts or tune algorithms based on diagnostic success.
