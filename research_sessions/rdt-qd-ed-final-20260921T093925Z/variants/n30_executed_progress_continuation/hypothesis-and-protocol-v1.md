# N30: executed-progress-conditioned continuation proposal

Status: hypothesis and CPU implementation authorized, GPU dispatch not yet released. Parent science is the frozen Q0 profile on d855cfd690482e018bb40ce98edec80fad9700e0, not the rejected N29 settings. C0/Q0 semantics remain exact when the new option is off. The original validation/formal goals are unchanged.

## Evidence and first-principles probe

Q1 bottleneck class: loss of useful receding-horizon planning state is a testable proposal-generation question, distinct from whether the robot moves at all. Accepted N29 closed-executed-trajectory audit contains17280 actual action/outcome pairs. All883 earlier guided metrics were fresh, with no carried selected plan. Q0's six matched first chunks reduced EEF distance to their initial keypoint0 snapshot by [0.104881751,0.107894455,0.123555774,0.083243525,0.104914983,0.140847023]m; every next decision atstep8 was still guided Stage1. N29's six first reductions were only [0.017896328,0.015285461,0.045766220,0.007766233,0.045244950,0.032473915]m. These are real observed first-prefix measurements at matched starts, not proof of why later failures occurred.
Q2 hidden assumption: each new guided search should discard the unexecuted suffix of the particular plan whose prefix just made observed progress. Invert it by making that suffix compete as one candidate, without forcing its execution.
Q3 elephant: a promising prefix does not establish that its suffix is correct; object motion, stale plans, Stage handoff and grasp failure remain possible. No unchosen physical outcomes are known. Elevated-keypoint examples in Q0 task2/5 occurred off-guidance, so N30 does not claim to repair those periods.
Q4 Hamming: yes, the question concerns proposal continuity during observed approach and uses an already available deployment signal. It is worth a bounded experiment rather than another diversity-amplitude adjustment.

The executor's diagnostic verdict NO_JUSTIFIED_CANDIDATE is preserved verbatim: it established no causal algorithm benefit. Root's decision here nominates an unproven, falsifiable experiment using observed approach progress and immediate next-guided availability; it does not overrule the diagnostic facts or manufacture a grasp label.

Four idea moves: inversion -> retain a competing continuation after observed progress; backward from success -> approach must make progress across successive plans before grasp/transport can matter; analogy -> receding-horizon plan reuse with feedback validity; failure-case reverse engineering -> Q0 initial approach exists on all six tasks, N29 prolonged search can remain distant, and N14 object-motion gates missed early approach. Three distinct options were considered: this continuation proposal; grasp-frame/orientation-aware quality (defer: no current evidence identifies an orientation defect); objective-aligned diversity gradient (defer: no sampled mutation/quality conflict proof and risks repeating geometric proxy tuning). Only continuation is nominated.

Scratch declaration: assumption=always-fresh guided proposal suffices; class=planning/control plus QD proposal state; mechanism+hypothesis=offer the previous executed winner's remaining plan only after measured approach progress, to reduce repeated loss of a useful approach route, tested by same-cohort task success; orthogonality=across actual executions and chunk boundaries, not N24 within-search command rescue or N29 amplitude cap; prior conflicts and limits below. The number one is a fixed continuation slot, not a sweep over population/memory fractions.

## Single primary modification

Name executed_progress_continuation_v1. New option defaults off/fresh. Only the Q0-derived N30 profile enables it.

At a guided decision with a recognized unchanged single-target distance-provider contract, valid same target/tracker instance/generation and episode/reset identity, retain the selected native (1,64,128) plan and its actual decision identity. Bind it to the exact decoded/committed eight actions; receive the existing actual post-action EEF observations, never call an environment or provider again to collect them.

At the immediately following guided decision, after exactly those eight actions have completed in order, allow one continuation only if the Stage/provider/target/tracker identities remain valid and unchanged, and actual EEF endpoint distance to the previous decision's recorded target snapshot is strictly lower than its actual start distance. This is measured approach to the old snapshot, not a holding or moving-object truth label. Use finite CPU float64 bookkeeping for this sign comparison; no tunable centimetre threshold, no success/reward/contact field. Current target coordinates still participate in ordinary current scoring; no immobility assumption. Missing/nonfinite/unrecognized/interrupted/stale history never licenses continuation. Clearly distinguish invalid evidence from normal inactive reasons.

Make the ordinary fresh population of16 exactly as Q0 does. Before its one canonical initial score, replace only row15 by concatenating previous selected latent rows8:64 (56 steps) and that same fresh row15's rows56:64 (8 new tail steps), then apply the existing native action mask. Preserve native dtype/device. Keep the other15 fresh rows unchanged, use no extra RNG, score batch, model forward, denoising pass, or simulator step. The later QD archive, parent allocation, ED iterations and global archive final selection remain Q0. Thus this is a competing initial proposal; selection may discard it. It never forces a gripper command or bypasses the current score.

The stored plan must be the actual previous executed winner, not an unexecuted archive member or lowest-cost proposal that was never chosen. Exactly one prior chunk of history; no rollout-horizon extension. On episode/reset, target/provider/tracker/Stage change, any guidance gap, incomplete dispatch, stale age or missing binding, clear eligibility. No memory applies to unguided prediction. Existing warm_start_mix stays off; its two additional scoring batches and adapted-memory denoise are not used. Existing N3 residual quality and all N4..N29 scientific toggles stay off in the Q0-derived method.

The sole new mechanism is this feedback-conditioned initial proposal path with its necessary identity/validity guards. Do not add orientation costs, gripper hysteresis, dynamic model calibration, changed descriptors/rewards/Stage or multiple simultaneous optimizations.

## Falsifiable claims and controls

Prediction: continuation can be admitted at real next-guided approach decisions and can participate in ordinary canonical QD selection without extra model/score work; if it improves preservation of useful approaches, whole-task success should improve in a fresh matched Dev screen. Null/rejection: no activation, invalid/stale associations, no task-success gate, or numerical/compute violation. Activity or shorter paths alone are not KEEP.

Proposed Dev screen is original task order0,1,2,3, original frozen Dev identities, three fresh arms C0/Q0/N30, total12 attempts. No inherited results, retries of valid failures, changed seeds, hidden simulator branches, or task-specific code. Candidate must succeed at least3/4 and at least the same C0/Q0 counts, with substantive QD/ED and continuation activity plus valid telemetry. At complete task blocks, reject if even all remaining candidate tasks cannot reach3. Unrun tasks remain Unknown. This smaller Dev screen is a prospective screening design, not a substitute for the mandatory independent20-episode validation or10-task formal. It uses first four tasks by frozen order, not observed favorable tasks.

If the screen passes, freeze the entire method and a separate previously unexposed validation identity plan; candidate/C0/Q0 each20, candidate>=10 and>=both. Only after that may the single formal candidate and matched QD ablation be released. Validation/formal stay closed during CPU/Dev work. Formal failure retains the original no-repeated-tuning rule.

## Finite resource allocation, no expansion

Current cumulative395 dispatched /53.08404692669838GPUh, caps578/100. Current remaining buckets baseline4, development12, validation120, formal40, recovery7. C0 uses baseline; Q0/N30 use development. Proposed12-cell screen consumes at most baseline4 +development8, within these existing caps. Reserve at most6GPUh for N30 preparation/native proof/Dev/exit/API waits including failures; stop new dispatch if that local or global cap cannot accommodate the next attempt. This fits the existing10.675129070870807 unprotectedGPUh; protected validation/formal remainder36.240824002430815 is untouched. Week expansion remains pending, not adopted.

No GPU execution is authorized by this file. First complete isolated implementation and CPU review; then root freezes final sources, interfaces, protocol, actual runtime/availableGPU binding and releases one worker. Current preferred frozen deviceGPU7; no other user's process is touched. Online Stage uses current managed Codex login only, no Poe or alternate credentials.

## Implementation review requirements

Use an isolated worktree under this variant's implementation directory from d855. Meaningful CPU tests must establish copy/shift/mask exactness in FP32 and BF16, progress sign and missing/incomplete observations, consecutive-step bindings, default-off Q0 parity/RNG and no extra score/model calls, same/new Stage/target/provider/tracker/reset/episode invalidation, unguided gap, and association of memory row to canonical initial batch. An integration fixture should exercise the actual Main/policy callback path with fake model/environment; it may not start a simulator, real model, GPU or API.

Record actual source changes, test failures and fixes, source identity and test resource usage. Do not claim simulated mocks establish native GPU behavior or task benefit. Avoid repeating already successful tests without code change or a new concern. CPU implementation/testing cap600 processCPU seconds for the initial delivery, two threads, no heavyweight installs. If a concrete integration requirement makes the one-change/fixed-cost contract impossible, report it before silently broadening method scope.

All artifacts stay within this variant. The diagnostic reports and prior negatives stay immutable. No state/budget/ledger writes by executor. Root reviews the code and native evidence before online release.

