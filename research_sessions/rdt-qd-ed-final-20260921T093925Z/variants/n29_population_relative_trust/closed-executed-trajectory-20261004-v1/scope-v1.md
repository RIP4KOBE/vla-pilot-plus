# N29 closed executed-trajectory audit, v1

This is a CPU-only analysis of existing native records from the same 24 accepted Dev cells, task0..5 x C0/Q0/N28/N29. It does not change a method, rerun an episode, open validation/formal, or authorize GPU/model/API/simulator work. Original scientific source d855cfd690482e018bb40ce98edec80fad9700e0 stays read-only.

## Evidence and probe

Metadata audit closed-task-relevance-20261004-v1 is independently accepted in root-metadata-review-v1.json. N29 has465/540 guided decisions, all four arms remain0/6, and all883 guided records have null cross-chunk selected trajectory distance. Its reported terminal selected target distance is also null. The smaller guided-only command jumps are neither actual EEF displacement nor matched timing across arms.

Q1: failure class is missing execution-level credit assignment: proxy changes fail to establish task benefit. Evidence is N29's0/6 despite100684 trust-limited rows, and the accepted metadata audit's883 unavailable continuity fields.
Q2: hidden assumption is that command/projection summaries establish manipulation progress. Drop it by measuring only actually executed commands and observed robot states.
Q3: no counterfactual physical candidate outcomes or contact truth exist in this audit. Even actual gripper closure does not establish holding an object.
Q4: Yes; existing full trajectories can distinguish sustained movement, command oscillation and observed closure patterns before inventing another proxy tweak.

Idea moves: inversion measures realized rather than projected progress; backward from success looks for continuing approach/closure/transport; control-theory analogy compares input to measured response across chunks; reverse engineering contrasts all six matched failures without selecting favorable cells. None is nominated as a GPU algorithm yet.

Scratch declaration: assumption challenged = proxy-to-task implication; mechanism class = verification/feedback measurement; mechanism+hypothesis = a complete observed command/state alignment can locate whether action continuity or physical response is missing, measured on all24 existing Dev cells; orthogonality = whole-episode physical observations rather than node13.2 metadata or earlier first-guided mutation analysis; conflict = N3 residual and N24 within-chunk rescue remain negative, this observational audit neither repeats those methods nor infers unchosen causal effects. This is a diagnostic node, not a success-producing algorithm or parameter change.

## Prospective selection (same rule for every cell)

1. Use all24 exact accepted cell identities from the closed N29 result and accepted metadata manifest. Read their event-index JSONL once to select paths before tensor decoding. No original metrics/stage/raw-response rescan.
2. Select every recorded executed_action and pre_reset_outcome for steps0..719. Both event types live in independent small native bundles, per current source; confirm against the manifest, do not infer if absent.
3. Select decision contexts at fixed chunk starts [0,176,352,528,712]. At these same five starts only, select decision_context, policy_action_decode, decision_committed, first projection_origin (if present), and limited final_selection fields described below.
4. Freeze input-manifest-v1.json with paths, exact byte counts, native index SHA256, event sequence/decision/step/reset identity, and co-resident counts before decoding. Verify containers while reading; no second decode to polish output. No outcome-based task/window selection or extra adaptive window.
5. A .pt bundle must be decoded in full by torch, including co-resident candidate/scoring arrays. This scope explicitly authorizes that full-container CPU decode for the selected paths only, but analysis/export is restricted to the whitelist below. The old 240-container early-window proposal remains unexecuted and is not the input scope.
6. If any bound/identity/schema fails, retain the failure and stop the affected extraction rather than silently expanding scope or retrying a successful read.

## Allowed numeric observations and limits of interpretation

- executed_action: deployed action_numpy values. These are inputs sent to the environment, not measured displacements or necessarily post-controller-clipped values.
- pre_reset_outcome: robot0_eef_pos, robot0_eef_quat, robot0_gripper_qpos, robot0_gripper_qvel; step/reset identity and origin. Do not export evaluator reward/termination/success fields or use them to form features; cohort success is already known from accepted terminal results.
- At five fixed decision starts: stage/use_guidance, keypoints with passive validity/generation, first projection_origin.source_eef_position/cast_eef_start (if present), selected decoded/committed action chunk and execution horizon, selected index/fingerprint/selection rule, terminal_population.grasp_selection.target_index and recognition_reason if present. Do not analyze co-resident unchosen candidate arrays or recompute learned/provider scores.
- Keep keypoint indices explicit. Only name an active target when its recorded native contract establishes it; otherwise report all observed keypoints without guessing object roles. Tracking is the existing benchmark interface and is not an independent physical ground-truth measurement. Do not add environment queries.
- Describe full command changes, actual movement/path/displacement, orientation changes with sourced quaternion convention, actual gripper state range/changes, and positive/negative gripper-command intervals. Use no unsupported contact/grasp threshold. Continuous qpos/span is sufficient.
- Distances at sampled contexts can pair observed EEF with that context's keypoint snapshot; report timestamps, tracking validity, missing initial-state values, and stale/sparse target limitations. A moving target is not assumed fixed over176 steps. Never label projected motion, command continuity, Stage, or closure as successful grasp.
- Temporal correlation is not causation. Different arms reach different states; same initial identity is not a same-state counterfactual. Tasks6..9 remain unrun. No success-rate promotion or hidden contact claims.

## Resource and implementation bounds

Write only in this diagnostic folder. No benchmark/source edits, git commits/worktrees, state/budget/ledger writes, other-study files, protected splits, credential access, image/video decoding, new agent, model, environment, GPU or network/API call.
Allow current relevant source files read-only for schema/convention; never read protected docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md.
All subprocesses: CUDA_VISIBLE_DEVICES empty, PYTHONDONTWRITEBYTECODE=1, OMP/OPENBLAS/MKL threads2, CPU affinity2 cores. CPU cap600 process CPU seconds total measured across preparation/extraction/packaging; enforce remaining RLIMIT_CPU on reader. Max16GiB address space, max4GiB native container bytes, max512MiB original metadata/index bytes, max128MiB own exported data. Reader uses torch.load(weights_only=True,map_location='cpu'), no models or CUDA initialization. No unsafe unpickling fallback. Record imports/paths/resource/guard errors without leaking secrets.
Allowed standard-library/Torch/NumPy dependency reads for CPU decoding; deny network, device access, model assets, unrelated files and source writes. A startup/import failure may be diagnosed from its error with precise accounting; do not automatically loop retries or rerun completed extraction.
Measure actual CPU/wall/bytes/peak memory. Unmeasured overhead remains disclosed, not invented zero. Count each failed attempt. Final report should be concise: 24-row per-cell table, data with timestamped allowed fields, source/manifest/resources, key contrasts, explicit Unknowns, and at most three evidence-supported distinct algorithm hypotheses or NO_JUSTIFIED_CANDIDATE.
No chart or report polishing that delays delivering the evidence. Root reviews before any algorithm or GPU release. This adds0 GPUhours and0 episode attempts and uses existing authorization for ordinary CPU diagnosis.

