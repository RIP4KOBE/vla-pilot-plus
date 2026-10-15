# Candidate N1: executable-intent QD representation — preregistration v1

Status: FROZEN BEFORE IMPLEMENTATION OR NEW ONLINE OUTCOMES. Base algorithm source744e08b; study protocol7c5fbcf. Owned engineering baseline fixes apply equally to all arms and are not part of N1.

## Probe and choice

First principles: representation aliases executable actions. Evidence:20/20 historical Q0 trace replays;82 exact gripper-discordant archive eliminations (13 incumbent displacements) and same-cell Z span median0.1084m/P95 0.2852m. Hidden assumption: final EEF XY sufficiently characterizes manipulation-relevant behavior. Elephant: reward is geometric and does not score gripper intent; saved alternatives have no real counterfactual success labels. Hamming: yes, preserving materially different executable action modes is a task-linked bottleneck worth a single bounded test, not proof of benefit.

Four moves considered: invert XY-only equivalence through action-aware representation; work backward from grasp intent plus approach geometry; borrow stratified quality-diversity archives over actuator intent; reverse engineer the actual82 eliminations. Defer reward-window alignment (t7/t8) and cross-chunk memory to avoid stacking changes. No new learned model or extra simulator branches.

## Unique algorithm change

Replace Q0 descriptor with two values: (1) Euclidean distance between projected final EEF position at executed timestep8 and currently observable target keypoint0, in meters; (2) fraction of the8 decoded executed gripper commands that are positive, in[0,1]. Use exact deployed decoder semantics: action128 slot10 <0 ->-1, otherwise+1. Call this positive-command duty, not grasp/close probability. Do not inspect task ID, seed, job label, hidden state or future observation.

Keep4x4 capacity-one grid (maximum16 elites), existing reward quality/tie-break/replacement, sparse-priority parent allocation, population16,10 EDS iterations,176 evaluations/11 batches, all historical later switchesOFF, fresh archive each chunk and unchanged reset. Radial axis uses historical .05/.95 quantiles, .1 expansion and .08m minimum span; duty axis fixed[0,1]. No adaptive threshold sweep. Explicit descriptor metadata must name axis units correctly; never label duty as XY meters.

This is distinct from H1 XY-bound expansion and H5 capacity-two secondary path-distance lanes. It changes behavioral equivalence at constant archive capacity. It deliberately discards azimuth and compresses gripper timing; measure new aliases and disclose them.

## Falsifiable predictions and controls

Prediction: duty partition separates most observed gripper-discordant Q0 elimination pairs, and prospective search retains and actually samples multiple duty classes when the proposal pool contains them; task improvement is assessed separately. Pairwise bin separation is not candidate survival or success. Fixed-pool replay must measure actual survivor/parent lineage changes, new aliases and unchanged global reward maximum under the same pool. No invented counterfactual outcomes.

Controls: contemporary repaired P2(C0), repaired starting sparse QD(Q0); candidate N1 differs only in descriptor/bounds semantics. Same frozen source/runtime and paired env/policy seeds. Restoring old descriptor is the specific-change ablation; disabling QD with matching search budget tests full QD contribution.

## CPU and mechanism validity

Verify exact8-command duty including zero handling; finite radial values; order-stable fixed bounds; edge bins; <=16 elites; best-reward invariant; correct source accounting; unchanged default descriptor behavior; reset/chunk/target freshness; full-loop176/11 and actual new descriptor use. Run relevant QD/RDT steering tests. CPU trace replay must clearly distinguish exact stored quantities from any BF16/projector reconstruction error. If exact3D reconstruction is unavailable, report the limitation rather than accepting approximate endpoint identities as exact evidence.

No arbitrary minimum coverage/rescue rate is a hard gate. If implementation is valid but descriptor does not separate any meaningful real action variants, INVESTIGATE once and reject rather than tune bin counts.

## New online plan and promotion

Only after GPU7 admission, provider binding, CPU checks, complete source/config/input freeze and baseline establishment. Baseline:Q0 andP2 each10 Dev tasks. N1:all10 Dev tasks and paired same-roundP2; first2 tasks serve as implementation/finite-mechanism checks, not success-based stopping. If eligible, run Q0 at the candidate promotion checkpoint (10 more episodes). N1 Dev promotion: >=5/10 and no fewer successes than both same-round controls, all numerical/action/accounting gates pass, descriptor substantively active; no post-reveal rule changes. Lower score does not establish irredeemable mechanism failure, but no validation promotion.

Validation uses next unused frozen cohort,20 episodes per arm; N1>=10/20 and >=P2/Q0. Formal follows global policy; single candidate,>=5/10 and >=controls; no formal re-tuning. Every dispatch uses the global240/48GPUh budget, with100 validation/formal slots reserved. This candidate's Dev allowance at most30 attempts excluding already-reserved baseline; failures/aborts count.

Stop/review: valid Dev failure ->REJECT candidate then outer loop under study rules; implementation error ->INVALID plus bounded repair preserving scientific identity; no budget expansion. GPU/provider blocks are infrastructure prerequisites, not scientific failures.
