# N25 conditional CPU preparation: actuator-clipped EEF RBF geometry

This freezes one mechanism for source-isolated CPU preparation only. N24 remains the active frozen Dev candidate. This document does not register a new online candidate, expand budgets, release GPU/model/API/simulator work, or open protected data. If N24 promotes, its independent validation takes priority; any subsequent N25 online test requires a separate complete prospective protocol, source/compute review and actual capacity check after N24 disposition.

## Rationale and unknowns

Root accepted N24/outer-loop-review-v1/root-review-v1.json (b224db6ea09cd66dc6189e1b58bfd0a4a61d669464df04376252de6ff9677a0a). Existing absolute RBF is already based on projected EEF trajectories, not 128D latent distances. N23 changed internal quality only; the proposed intervention changes the ED proposal gradient geometry. Closed N24 task0 terminal evidence has202/224 rows with out-of-range translation, but actual noisy RBF x_t saturation remains Unknown. CPU N5 clipping eligibility did not rescue the two focal rejected full8 cases. Neither that evidence nor a gradient change proves physical utility.

Hypothesis: differentiating the existing repulsion through actuator-input-equivalent translation can redirect fixed-budget proposals toward differences that survive input clipping. Risks include clipping inappropriate noisy states, identical clipped trajectories and zero gradients, and concentrating the unchanged globally normalized force into fewer unsaturated coordinates. This does not claim accurate physical dynamics or weaker overall force.

## Exactly one scientific intervention

Base source: 3b7afa02757eb3519d95547e4b6e6e939f7068f2, with candidate_n23 profile as scientific parent (N24 parent rescue OFF). Add explicit opt-in descriptor mode actuator_clipped_eef_v1 to both existing initial and rollout RBF descriptor call sites. Leave absolute_eef/direction_normalized_eef/default paths unchanged.

For current x_t, use the first8 translation indices39,40,41 and the existing same-call projection origin. Replace only the RBF projected path with origin+cumsum(clipped_translation*0.01), retaining the native dtype, original horizon convention and existing projection-origin semantics. Define clipping forward as componentwise bounds[-1,1]. Its custom subgradient is1 strictly inside(-1,1),0 at either exact boundary and outside. This is an explicit prospective choice, not torch.clamp default differentiation. Do not use straight-through or raw fallback.

Keep the original inverse-distance potential/epsilons, gradient normalization and threshold, update sign/scales20, timing masks, RNG/noise/scheduler, 16 population/10 iterations/176 canonical evaluations/11 score batches, and all model/provider call counts. Do not change the reward/quality projection, QD descriptor/archive/allocation/N5 final selection, RDT decoder, Stage/perception/cache/prompt/provider, simulation or execution semantics. Do not combine this with mode birth, continuity, forced close, surviving elites or N24 parent rescue.

## CPU preparation deliverables and evidence

Create only variants/n25_actuator_clipped_rbf/implementation as an isolated worktree, new codex/n25-actuator-clipped-rbf branch at the exact base. Preserve all existing worktrees/source/state/ledgers. Prepare the smallest helper/wiring/profile and meaningful CPU tests, plus source/diff manifests and an implementation report. Necessary opt-in enum validation/config forwarding may change; inventory every source edit. No runner/controller/GPU release or budget adoption in this phase.

Tests must independently check strict-interior parity to the original RBF, declared exact +/-1 derivatives, saturated and coincident trajectories, zero-gradient validity and finite handling, batch/dtype/horizon/index binding, nontranslation zero updates, unchanged sign/normalization/schedules/RNG/model-call accounting and default-off/source-profile parity. Use constant synthetic tensors and fake source adapters only; FP32/BF16 CPU correctness is not exact CUDA arithmetic evidence. Run directly relevant existing regression checks; no gratuitous full-suite repetition. Nonfinite is an error. A correctly produced all-zero gradient is a valid mechanism outcome, not a retryable infrastructure failure.

Prepare passive per-call telemetry for the new mode only, separately identifying initial vs rollout, decision/iteration/timestep, source/shape/dtype, clipping/boundary counts, pre/post-normalization and actually applied masked-update finite/zero/norm counters. Derive these from existing computations: no second shadow gradient, model call, scoring, simulator branch or outcome label. Optional minimal input/output capture for independent audit must be proposed and explicitly bounded before implementation; do not copy full latent tensors by default or invent GPU equivalence from rounded summaries. Native production source/cost auditing will be completed in a separately reviewed phase before any deployment.

## Boundaries

CPU only, at most2 threads; hide CUDA and block network/process/model/simulator execution in the test boundary using the existing proven CPU-test practices. Do not claim an OS guard or CPU usage was measured unless it was. Only frozen source, existing closed narrative review and synthetic fixtures; no raw attempts/.pt/Stage/image/observation/protected outcomes/credential data. No Poe client or alternate account. All future online stages remain current-account codex_cli/chatgpt only.

Do not modify W/research-state.yaml, tree, checkpoint, ledgers, live plans or supervisor. Write artifacts only under N25. Keep failed tests/logs and fixes visible; do not modify scientific definition after seeing experiments. Stop CPU phase on completion with exact commit/hash report for root review. This conditional preparation has0 GPU attempts,0API/model/simulator calls and no efficacy claim.
