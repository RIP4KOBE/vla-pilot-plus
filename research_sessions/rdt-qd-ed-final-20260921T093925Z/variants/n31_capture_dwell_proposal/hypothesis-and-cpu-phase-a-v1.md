# N31 — capture-dwell competing proposal: hypothesis and CPU phase A

Status: prospective algorithm hypothesis; CPU-only phase A. No GPU, new historical measurement, validation, formal, provider/API, training or budget expansion is authorized by this document.

## Evidence and ideation gate

TreeView constraints was read after the N30 pool closure and before this nomination, followed by Arbor ideation instructions. The original Goal remains NOT_MET.

PROBE BLOCK
Q1 First principles: wrong temporal action-space/completion assumption. Evidence 1: N30 task0 decision16 selected row9 is at point-prism distance0 at projected outcome1, then outside at outcomes2..8 despite eight close commands (accepted pool result SHA6f6ca60ea332919099b09886be750aa339aacf2f3c7a4f8dbbbedb1a82ee26b6). Evidence 2: accepted actual handoff H shows this guided prefix withdraws while measured fingers are still closing; fixed video has no sustained visible carry. Evidence 3: task1 decision16 all16 final archive proposals have no close command in first8; earlier search modes remain Unknown.
Q2 Hidden assumption: a policy/QD proposal that briefly approaches a recognized point already contains a temporally usable closure sequence. Dropping it allows a structured competing completion proposal rather than only scalar reranking.
Q3 Elephant: neither approximate point inclusion nor commanded closure establishes physical capture. Controller lag, arbitrary keypoint, future wrist/jaw geometry and contact remain uncertain; external Stage is frozen. We must test actual outcomes and preserve failures.
Q4 Hamming: yes, temporal coordination directly addresses observed retreat during closure and missing close-mode choices. It is a plausible experiment, not an established cause or predicted success.

All four idea moves:
- Assumption inversion: construct a capture-dwell alternative within the existing candidate budget instead of assuming sampling already produced one.
- Backward from success: a successful grasp needs useful pose persistence during actuation before later transport. No hidden grasp label is added.
- Analogical transfer: an option/completion operator in sampling-based control supplies a structured short action alternative that still competes with model proposals.
- Failure reverse engineering: task0 suggests avoiding immediate retreat during closure; task1 suggests supplying coordinated close actions when the final archive lacks them. One operator addresses both at predicted arrival.

Other candidates considered and declined: minimum-point-prism reranking (directly unsupported by the closed pool screen); another positive-gripper/lift scalar bonus (too close to N18–N22 without new support); online fitted dynamics/scorer (new fitting assumptions and scope, and N3 already shows geometric prediction improvement alone is insufficient). No literature algorithm is represented as implemented.

Five-field declaration:
1. Assumption challenged: transient geometric approach in current candidates suffices for temporal grasp completion.
2. Mechanism class: structured proposal construction at the QD–ED interface, a control/action-space intervention.
3. Mechanism + hypothesis: a competing capture-dwell completion of the current archive best may keep a promising approach pose available during commanded closure; success means a valid prospective matched Dev task gain and then the original validation/formal gates, not proposal count.
4. Orthogonality: N22 shapes scores of existing close/lift proposals; N24 retains existing closed content; N30 carries a previous-chunk tail; N31 synthesizes a within-current-search temporally altered pose/close proposal. It changes neither descriptor nor quality.
5. Conflicts: N9's sweep penalty and N23–N29's projection/diversity revisions had weak outcomes. N31 does not claim that better proxy ranking or smaller RBF updates solves capture. Approximate arrival remains a material risk.

Self-check: this is an explicit sequence-construction operator, not a scalar knob, prompt edit, larger search, old rerank or mandatory action override. One candidate only; no parameter sweep.

## Frozen algorithm intent

Base is original Q0, with all N4–N30 scientific toggles off. RDT checkpoint, Stage/cache/perception/prompt, external reward, quality semantics, descriptor, archive update/parents/final archive_global_best, 16 population, 10 iterations, execution8/20Hz/720 and task conditions remain baseline-identical.

Initial16 fresh candidates are unchanged. For each of the10 subsequent canonical offspring batches:
1. Before the iteration, bind the current archive-global-best clean native (64,128) plan and the original recorded/cached canonical first8 projection from the same current decision/provider/target. Use its actual archive identity and canonical source; do not choose a new base from future outcomes or unscored model rows.
2. With the decision's currently observed right_hand xyzw rotation and measured gripper qpos held fixed, evaluate that base's original projected outcome positions1..8 against the previously source-calibrated point prism. Geometry uses CPU binary64 normalized rotation, x in[-.008,.008], z in[-.0116,.0044], y between q2+.0005 and q1-.0005, in meters. The current recognized target snapshot is used. This is an approximate point test, not an object/grasp predicate.
3. Let j in0..7 be the earliest projected outcome inside the inclusive prism (distance exactly0 under the declared arithmetic). If no hit, negative inner gap, unrecognized provider/target, or unavailable valid current proprioception, leave the ordinary offspring unchanged with a reason; malformed/nonfinite data follows an explicit fail-closed contract, never silent fabricated input.
4. Copy that base native plan. Preserve all entries before j. Set native gripper index10 to +1 for j..7. Set native translation/rotation indices39..44 to0 for j+1..7, preserving the arrival command at j. Preserve indices8..63 in time and all other native fields/mask. No change to actual executor, per-action timing or environment interface.
5. If this creates different native content, substitute it into the fixed final offspring slot15 only AFTER the ordinary model rollout/diversity updates and BEFORE that batch's one canonical score. Other15 offspring, all model calls and random draws are unchanged. If no changed proposal exists, retain ordinary slot15.
6. Score the resulting16 once using original Q0 quality and normal archive/parent/final selection. No forced retention, favorable tie rule or mandatory execution is added. This proposal can lose. It is available to later QD/ED evolution if naturally retained.

One operator coordinates pose persistence and gripper closure. It is not two independently tuned modifications. No fitted duration: it uses the remaining part of the existing8-action chunk. No new distance threshold: the physical-source prism defines the geometric trigger. Fixed observed geometry deliberately does not forecast future jaw/wrist dynamics. The raw canonical trajectory remains controller-origin projection; do not call it realized motion.

Preferred cache contract: capture/reuse each canonical batch's already computed original projected_xyz with exact native identity, bounded to the current decision. Do not add scorer, model, provider, RBF or simulator calls. Extra geometry/CPU copying and cache/observer overhead are separately counted. Never borrow a future projection or a previous episode/target. If the existing pipeline cannot support this placement without changing the frozen computation, document the concrete conflict before implementing a different algorithm.

## CPU phase A authorized now

Existing separated executor /root/n22_cpu_executor only. Create an isolated implementation worktree under this variant at implementation, branch codex/n31-capture-dwell, based on source6292fc8cffad2eec0f789e023d835ad3c1df146a. Preserve the owned study worktree and all its dirty/untracked files. No second experiment directory outside the unified umbrella.

Implement the pure proposal helper and focused synthetic tests in that isolated worktree. Inspect production integration sites statically and write a precise integration/cache/observer contract; production hookup and GPU are a later stage after root review. Use only needed source and already accepted result/contracts; no new tensor/video/benchmark-data reads and no additional numerical analysis of exposed episodes.

A bounded CPU test pass may cover earliest/last/no geometric entry, no-change proposal, open/close native signs, changed suffix vs untouched prefix/tail/inactive dimensions, empty/invalid geometry handling, source/dtype preservation, and no extra random draw. Tests must verify action semantics and failure handling rather than mirror implementation. CUDA hidden,2threads/affinity0,1, hard CPU600s and external wall900s for the synthetic suite. Ordinary static preparation separately meter/disclose. No model/scorer/environment import, network/API, simulator, CUDA work or training.

Deliver module/tests, passing test receipt or preserved errors, exact changed-file manifest and commit, source-placement contract with lines, side effects/limitations, and a frozen CPU handoff report. Root owns study/tree/budget/controller state; executor must not edit those. Do not silently redesign the operator after a failed test; fix implementation errors within this protocol.

## Prospective GPU comparison, not released

Preferred Dev is a predeclared complete10-task exposed map, same-round C0/Q0/N31,30 cells in full task blocks. Candidate gate >=5/10 and >=both controls; mathematical futility may stop only after a full task block when successes+unrun<5. This is a new candidate protocol; it does not reopen or relax N30's closed3/4 gate. Valid failures are never rerun. Record every task, gain/loss, invalid, call/compute count and actual proposal/selection traces. No arbitrary activity-count veto; genuine QD/ED activity remains required.

Current state has only2 baseline and8 development slots remaining. Full30-cell plan needs10 baseline+20 development, hence8 additional baseline+12 development slots before release. The100GPUh hard cap and protected reserves remain unchanged; no revision is adopted here. A finite budget request must be concrete and audited before any expanded spending. The pending week-wide224GPUh/1800attempt proposal is not approved.

If subsequently released, protect full original validation20 per arm (candidate>=10 and>=C0/Q0), historical formal10 (candidate>=5 and>=controls), substantive QD/ED and compute-matched removal/replacement evidence. CPU success or exposed-Dev improvement never marks the Goal complete.

