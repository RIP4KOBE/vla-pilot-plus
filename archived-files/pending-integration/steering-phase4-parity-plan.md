# Phase 4 minimal interface and EDS parity plan

Status: read-only design, 2026-10-13. Do not implement or run this phase before the
full10 EDS migration gate passes. No runtime/config/tests were changed for this plan.

## Minimal change and ownership

| File / owner | Exact change boundary |
|---|---|
| `core/rdt_policy_steer.py` / policy owner | Add pure `get_stage_reward()` next to `get_normalized_reward():1390`; VLS-only selected-reward cache/reference and optional telemetry. Extend constructor state, `reset():1349`, `reset_stage():1380` only for those new VLS fields. Populate VLS outer score at `_select_particle_for_execution():6820`, consumed after `_vls_guided_denoise_loop():1882` selection. Preserve Tensor return signatures. |
| `core/stage_evidence.py` / controller owner | At `update_stage():207`, prefer callable `get_stage_reward`, otherwise retain legacy getter compatibility. Keep the existing `before_guidance` guard, float conversion and finite check. At capability loop `:232`, call additional gradient assessment only for explicitly RDT+VLS; leave `assess_reward():153` byte-for-byte unchanged for EDS/EDS+QD and other policies. Append VLS-only capability/progress telemetry. |
| `main.py` / integration owner | No necessary algorithm edit: `_update_stage():1321` delegates to shared controller; `_run_episode():1733` updates Stage before `select_action`, with grouped method args at `:1815`. Preserve this ordering. Legacy controller at `:1324` and gradient-scale visualization at `:2089` remain outside this minimal change. Do not silently relabel its internal gradient reward as outer progress. |
| Tests / policy+controller owners | Add focused common-getter tests and mocked real closed-loop differential/reference tests, reusing `test_rdt_steer.py` stubs and `test_main_rdt_startup.py` episode harness. Keep real Stage/handoff/search/reference/cache/postprocessing paths. |

No new engine, profile, QD behavior, hyperparameter, reward prompt, execution horizon,
reference rule or online query behavior is part of this patch. Public EDS+QD remains
EDS with archive configuration; this interface alone does not certify its performance.

## Preserve EDS exactly

EDS already scores the selected candidate. `_eds_update_guidance_metadata_from_cost`
at `:3800`, called `:6804`, computes reward as minus selected cost, saves the first
stage reward reference, and calls `_normalized_reward_from_value():7123`:

`progress = clamp(1 - reward/reference, 0, 1.2)` if `reference < -1e-6`, otherwise zero.

For EDS, `get_stage_reward()` must return the existing getter/value directly. No
Torch operations, re-scoring, casting/re-normalizing, reference writes, extra probes,
RNG calls or compute-counter increments. Getter routing state may be set only when
a guided mode actually generates a chunk; initial/unknown mode must preserve current
zero/default behavior. Repeated reads and cached-action reads are pure.

Do not modify `_eds_guided_denoise_loop`, initial population/RBF, scoring, parent
selection, renoise/rollout, selection or metadata normalization. Preserve dtypes and
operation ordering. In particular `reset_stage()` currently clears the reference
**without clearing the last normalized reward**; do not “clean up” this EDS behavior.

Stage consumes reward before resets and before next sampling. `stage_evidence:307`
passes it to `stage_contact_handoff.apply_handoff():56–63`: fresh prior guidance,
threshold >=0.8, accepted measured distance <=0.10, minimum approach16, grace64.
`normalized_reward_used_for_decision=False` does not mean reward is controller inert.
Keep reference resets at `stage_evidence:325–334`: semantic stage change always;
pure guidance toggles preserve it under the accepted preserve-reference setting.
Unguided prior chunks continue to suppress stale reward at line207.

## VLS outer score and validity

Preserve `_stage_init_reward`, `_last_normalized_reward`, `_last_raw_reward` and
`_compute_keypoint_gradient():7059` for internal gradient guidance. Its reference is
set from gradient reward history at `:1876`; adaptive scales use the internal value
at `:7657/:7672`. The new outer VLS reference must never write these fields or call
the old mutating `_normalized_reward_from_value` helper.

Cache score of the final selected candidate in the original sampling/keypoint/EE
frame, using the already existing selection scoring slice (`fkd`, `p1..p7` for H8).
Do not switch to gradient slice `p0..p7`, include p8, or re-evaluate after eight
executed actions. Ordinary multi-particle selection already computes scores at
`:6832`; reuse its chosen entry. B=1 and FKD reached-terminal early returns currently
skip scoring (`:6828–6831`): add exactly one selected-candidate score only on those
VLS paths, and account for that cost. Keep visualization's existing scoring pass
`:6849` unchanged; removing it is unrelated optimization.

For VLS only, normalize selected reward against its first valid selected reward for
the stage, with the same clamp/negative-reference convention. Store validity/source
separately; unavailable score must not silently fall back to internal gradient reward.
Reset only new VLS outer reference/validity fields on episode/stage reset; preserve
VLS internal reference rules and controller's existing guidance-toggle reset policy.

Retain deterministic finite nonconstant score capability first. Add a separate
VLS-only probe requiring a gradient connected to trajectory, finite gradients, and
a nonzero gradient at at least one nonoptimal probe. Zero gradient at one optimum
is legal. A variable detached/NumPy/rounded score remains valid for EDS but is not
valid VLS guidance. Constant stage2 reward remains unavailable for both. Use the
same deterministic CPU probes, restore Python/NumPy/Torch CPU RNG, and never touch
CUDA RNG in this CPU capability check. Unit-test actual latent->trajectory gradient
connectivity separately; trajectory probes alone cannot certify the full projection.

Telemetry should report selected score/reference/progress/source, gradient capability,
and observed gradient success/failure only for VLS. Reuse computed tensors/scalars;
never call reward, model or RNG just to populate a log. Preserve existing gradient
failure behavior while making effective guidance visible; do not add a new fallback
algorithm or silently change exception policy in this patch.

## Meaningful verification after the gate

1. **Getter purity + reset boundaries.** For real RDTSteer in EDS mode, repeated
   reads equal the legacy value bit-for-bit, with unchanged raw/reference/scale,
   counters, cached tensors, and Python/NumPy/Torch RNG states. Cover nonzero,
   negative-reference guard, clamp, unset reference, stage reset and unguided cache.
   A non-RDT/legacy policy missing the new getter still follows current behavior.

2. **Reference-independent baseline before edits.** After gate approval but before
   coding, run the existing frozen implementation with deterministic CPU stubs and
   save a compact reference transcript (input fixture, exact runtime/library identity,
   action arrays/dtypes, parent indices, scores, counter totals, RNG state hashes,
   Stage transitions and reset reasons). Keep provenance in the fixture; tests must
   not require a research WT, old run path, Git checkout, missing-path skip or API.
   During implementation additionally compare frozen and candidate modules in separate
   fresh processes. Comparing only new getter vs legacy getter on the same modified
   engine is insufficient to detect a shared accidental sampling change.

3. **Mocked full closed loop, real algorithm/controller.** Drive actual
   `Main._run_episode` -> `_update_stage` -> `stage_evidence.update_stage` -> handoff
   -> actual `RDTSteer.select_action`/EDS engine -> postprocess -> fake adapter step.
   Stub only expensive model/encoder outputs, simulator adapter and online service
   replies. Do not stub selected actions, EDS scoring/resampling/normalization, Stage
   decisions, reference resets, or the getter under test. Use accepted H8, B16,
   ten iterations, RBF initial+rollout settings and QD off for at least one test.
   Instrument existing parent/model/reward/denoise/RBF/rollout calls without consuming
   RNG. Assert every action and gripper byte, selected population index/fingerprint,
   random-state snapshot, sample/cache boundary and all scientific compute counts
   match reference exactly; exclude only clocks/latencies/paths from comparison.

4. **Controller branch coverage with the same engine.** Guided progress crossing
   >=0.8 while close -> contact grace -> unguided stale value cannot retrigger ->
   grace expiry -> guided resume with same reference. Also far-distance refusal,
   equality thresholds, semantic stage2 then recovery stage1 reset, episode reset,
   unsuccessful visual query and VLS/legacy getter compatibility. Compare query
   trigger times/counts, raw/executed actions, guidance gate/reset/handoff reasons,
   including all eight cached actions per chunk. Controlled controller-only rewards
   may cover exact boundary values, but cannot replace the real-engine parity test.

5. **VLS isolation.** Multi-particle selected score reused; B1/FKD early-return costs
   explicitly counted; different gradient and selected reward values prove outer
   progress can change without changing internal normalized reward, adaptive scale,
   selected latent or RNG. Non-differentiable-but-scoreable EDS remains admitted;
   VLS rejects it. Check per-optimum zero, finite connected gradient, disconnected/
   nonfinite gradient, and stage/guidance reset semantics. Ensure EDS never invokes
   the gradient capability function (a raising spy is useful).

CPU mocked parity proves the edited execution paths preserve the deterministic
reference under controlled inputs; it does not prove GPU kernels or future fresh
provider replies are bitwise repeatable. Full10 acceptance remains a separate gate.
Run targeted tests first, then the existing CPU suite once after integration. No
phase4 test, candidate implementation, GPU/API run, or source mutation is authorized
by this design-only task.
