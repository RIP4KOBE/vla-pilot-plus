# N27: feasible-ray diversity update

Status: selected for CPU preparation only. No GPU, actual experimental tensor reread, protected phase, or budget extension is released here. Parent source is N26 `6026794cd5d52f3a5054bf2704ebb3c516f9f47e`; active study source stays unchanged during preparation. Tree node 11.3.

## Probe and evidence

Q1 First principles: action-space feasibility mismatch. In the accepted N26 first-guided witnesses, task0 has 0 outside components before versus1076/4224 after diversity; task1 has0 versus1215/4224. All six tasks show update-induced crossings. Across66 N26 witness calls, outside components increase116→7333/25344. All-call geometry-input clipping is only532/780672, yet N26 task outcome is0/6.

Q2 Hidden assumption: actuator-aware gradient inputs make a globally normalized magnitude20 additive update meaningful without constraining the updated action object. Dropping this assumption permits a per-particle feasible step.

Q3 Elephant: search can strongly perturb plausible model proposals while its geometric quality only approximates task progress. Fixing feasibility cannot create absent grasp skill or establish physical progress; outcome evidence must remain decisive.

Q4 Hamming: yes, bounded update feasibility directly affects proposal generation inside the authorized QD/ED surface and preserves the goal's frozen backbone, provider and compute requirements. It is only a testable hypothesis.

Evidence: ../n26_clean_output_rbf/root-closed-measurement-review-v1.json SHA ff5a42314ec219772234c6259874817582082175142c0481a5888ac675b563a7; ../n26_clean_output_rbf/outer-loop-update-feasibility-review-v1.md SHA73960862fea1702218f6bc1a1652d261dbcb3ec392b0a03853e85c90a06a36e8. These are descriptive before-scheduler witnesses, not executed actions or same-state comparisons.

## Ideation moves and filtering

Assumption inversion yields feasible-ray repulsion instead of an unconstrained globally normalized additive step. Backward from success emphasizes preserving viable model proposals while diversifying them; another close-mode rescue is rejected because N24 already tested that capability without gains. The control/optimization analogy is a maximal line step inside a known box. Failure-case reverse engineering contrasts task0/task1 widespread new bound crossings with the weak rounding/alias signature: only83/25215 nonzero N26 operand entries are absorbed and no complete clipped-distinct/projected-equal trajectory pairs occur in these witnesses.

FP32 geometry and equal-particle normalization are distinct alternatives but are not selected: exact alias/absorption evidence is weak and concentration alone is not a task defect. Simply lowering a global scalar is not the selected mechanism. The survivor attacks applied-update feasibility, whereas siblings11.1 and11.2 changed geometry inputs. N3 shows better projected metrics need not improve success; N25/N26 negative outcomes are preserved. No task-specific condition, selector override or physical-success label is added.

## Exact sole algorithm change

At each existing initial/rollout clipped-RBF call, use the same N26 clean prediction, gradient, mask, global normalization and scale20 to form the existing native update operand d. Let b be the original model-output prefix, shape16x8x3, coordinates39/40/41, in FP32 or BF16. Compute one alpha per particle from b.float() and d.float(): min(1, all positive ray distances to the boundary in the direction d). For d>0 use(1-b)/d; for d<0 use(-1-b)/d; zero components impose no bound. Only strictly interior b may have nonzero d, as required by N26's existing strict-interior gradient. Unexpected nonzero d on boundary/exterior is an error, never an implicit repair. Zero-gradient particles use alpha1 and preserve b exactly.

Compute the candidate prefix in FP32 as b+alpha*d, correct only nonzero-update coordinates to[-1,1], then cast to b's original dtype. Zero-update coordinates preserve b's original bytes, including pre-existing outside values and signed zero. The final box correction handles finite rounding; it is explicitly part of the algorithm and may slightly alter exact ray direction at representable boundaries. Do not claim exact collinearity after rounding. No global rescaling, equal-particle renormalization, objective/gradient change, extra model/projector/scheduler call or post-execution action clipping. Gripper, other action dimensions and steps8..63 remain untouched. Legacy/off paths retain original code semantics exactly.

The normalized box is not measured physical displacement and does not guarantee post-scheduler or executed-action bounds. No global precision change to the model, gradient or projector. Inputs must be finite, matching-device native FP32/BF16 with the expected shape. Per-particle alphas and proposed/applied statistics are descriptive telemetry; no new task or Stage inputs.

## Prospective bounded comparison outline

Subject to CPU/integration/native review and a frozen runnable plan, the available attempt buckets support a16-primary screen: tasks0..3 in the existing fixed Dev order, each C0/Q0/N26/N27, with identical original seeds/init rows and conditions. This uses4 baseline+12 development attempts. At most two precisely typed existing Codex-timeout infrastructure recoveries could use recovery; valid failures never rerun. Screen gate: N27>=2/4, >=each same-round control, and strictly exceeds same-round N26, with substantive QD/ED and valid cost/evidence. Otherwise reject this screening candidate without claiming a full10-task result or global impossibility. Gate success permits preparing a separately budgeted full Dev comparison, not automatic validation or protected-set access.

Current ledger snapshot:338/522 attempts and46.47242339669481/100 GPUh; remaining buckets baseline4, development12, validation120, formal40, recovery8. Preserve protected validation/formal allocation; do not reclassify any attempt or silently enlarge a bucket. No GPU launch or amendment is authorized by this outline. Per-episode1800s, screen16+2 gives9h maximum before separately charged bounded health proof; a concrete runtime plan must check current free hours/reserves. Current managed Codex CLI/chatgpt login only, no Poe or alternate account/provider fallback.

## CPU implementation scope

Executor may create an isolated worktree at this variant's implementation/ from source602, branch codex/n27-feasible-ray-update. Root's current study worktree, frozen records, historical sources, runtime environments and journals remain unchanged. Add only a pure numerical helper, focused tests and an implementation note during this phase. Do not integrate into rdt_policy_steer, configs, native auditors, controller, plans, state or ledgers yet. Return the proposed minimal integration surface for review.

Static reads: this document, the two cited N26 summary reports, core/qd_actuator_clipped_rbf.py, core/qd_clean_output_rbf.py, targeted initial/rollout call sites and config declarations in core/rdt_policy_steer.py, and relevant current synthetic test patterns. Do not read actual records, indices, containers, models, credentials or protected files. Two CPU threads, CUDA hidden, <=180s cumulative targeted tests, no network/model/API/sim/GPU execution. Synthetic data only; no package installs.

Tests must cover native FP32/BF16; all-zero/one-nonzero-row, feasible and limited steps, mixed signs, near-boundary values, original exterior with zero update retained, signed-zero preservation, malformed/nonfinite/unsupported shape/type/device, strict-interior violation rejection, noncontiguous inputs, immutable input bytes/strides and RNG preservation. Use an independently written per-particle reference and mathematical bound properties; test both interior/no-op and limiting cases. Do not mirror vectorized implementation as the only oracle. Exact alpha1 native addition equality applies to nonzero coordinates; zero-coordinate preservation is the stated contract. Preserve every failure. Produce a small report/diff/manifest with exact source commit and tests; root reviews before any broader integration or execution.
