# hgpu1 Agentic Self-Improving v2 preflight

Canonical code and artifacts:

- repository: `/shared/hengyil6/vls/repo`
- branch: `codex/agentic-self-improving-v2`
- artifacts: `/shared/hengyil6/vls/self_improve`
- Python: `/shared/hengyil6/vls/envs/vla-pilot/bin/python`
- deployment target: hgpu1 only

## Frozen experiment boundary

- Formal online episodes, audits, counterfactual replay, policy regression,
  fixed probes, baselines, and final evaluation use **LIBERO-PRO only**.
- Original LIBERO is limited to PI0.5 theta0 pretraining provenance and the
  frozen replay source used during co-fine-tuning.
- `final_sealed` remains unopened.
- Robot visual reasoning is frozen to
  `gemini-robotics-er-2-preview`. The controller reuses the semantic planner's
  stage output in formal rollouts, while LIBERO-PRO simulator segmentation
  replaces a duplicate visual-grounding call.
- The production training profile uses one GPU with per-device batch 4 and
  gradient accumulation 8, preserving effective global batch 32. Two GPUs are
  an optional ceiling, not the default.

## Verified results

- Current blocking preflight is green for source revision
  `6df49d6111dbaad2bce316bb035b5f40ed69e539+source:4b59653cd1aaf1bc96fbd76beddc0d03cb8a9e898a3abce324e57b26be647ebc`:
  **213 passed, 3 warnings in 47.04 seconds**. The preflight file SHA256
  bound into the completed replay plan is
  `b002d2149329fa3d2798f7566716f18304c836556729a4a105c6e3b0d9dcc5f9`.
- Hardware: 8 × NVIDIA RTX 6000D, about 85.7 GiB each. Existing unrelated jobs
  on GPUs 0–3 were left untouched.
- Storage: about 37 TiB free under `/shared` at verification time.
- theta0: 812 tensors; vision 439, language 164, action 209; digest
  `56ca8804c5595afe970e1ee5eaa7e0ef530b56eb511e53b5f37773e29100fe80`.
- Two-rank NCCL canary on GPUs 4 and 6 passed with isolated ranks.
- One-GPU co-FT smoke on GPU 4 passed: 20 optimizer steps, 640 effective
  samples, final loss 2.754, gradient norm 2.066, complete 812-tensor
  checkpoint, 221.21 seconds, and about 33.7 GiB observed GPU memory.
- The 2-GPU full-model DDP diagnostic reproduced a CUDA illegal-memory failure
  during initial parameter synchronization on multiple free GPU pairs. Small
  2-rank NCCL is healthy, so this is recorded as a host/driver/full-model DDP
  limitation; it does not block the one-GPU production profile.
- LIBERO-PRO snapshot-v2 canary (`libero_10_lan`, task index 2, init state 28):
  exact qpos/qvel/MuJoCo-model restore, identical first PI0.5 action
  (`max_error=0`), `[1,50,7]` action chunk, and stable 2048D theta0 features.
- T2 browser teleoperation canary on the same LIBERO-PRO context passed: EGL,
  dual 256×256 cameras, 8D state, exact undo, and localhost-only binding.
- Gemini Robotics v2 canary passed all three real Interactions API paths in
  103.66 seconds: semantic planner, visual grounding, and stage recognition.
  The exact model is `gemini-robotics-er-2-preview`. The visual calls used a
  synthetic red rectangle; grounding returned one detection and stage
  recognition returned stage 2 with guidance off.
- Synthetic FKD preflight performed a real resample.

## Fail-closed audit history

All three audit attempts below use the frozen LIBERO-PRO context
`libero_goal_lan`, task index 3, init state 36. Invalid attempts remain in the
append-only ledgers and do not contribute labels.

- Attempt 5 was invalidated with
  `descriptive_gemini_stage_alias_false_advance`. A descriptive stage string
  had incorrectly been treated as a stage transition. Stage output is now
  canonicalized to `UNKNOWN` or `stage_N`; the correction and episode
  invalidation are append-only.
- Attempt 6 completed the intended controller route but was invalidated with
  `cross_process_mujoco_model_body_pos_not_captured`. Exact qpos/qvel alone did
  not reproduce static randomized fixtures in a new process. Snapshot-v2 now
  captures and strictly restores 53 allowlisted MuJoCo model arrays, including
  `body_pos` and `body_quat`. In the independent two-process check,
  `body_pos` error changed from `0.0151948597` before restore to `0`, and RGB
  mean absolute error was `0.00707682` (limit `2.0`). Legacy snapshots fail
  closed for exact counterfactual replay.
- Attempt 7 committed successfully after snapshot-v2. Its route was
  `EXECUTE x3 -> RE-STEER x4 -> EXPANSION`, with stage fixed at `stage_1`.
  The five post-failure decision snapshots carry pre-route remaining budgets
  `4,3,2,1,0`. Snapshot sidecars include all 53 model fields.

Before replay, two further fail-closed integration defects were found and
covered by tests: serialized medoid actions are converted back to float32
Torch policy actions at the environment boundary, and loaded guidance
functions remain a list rather than a tuple. FKD ESS is now reduced in float64;
non-finite or material invariant violations still raise, while machine-level
rounding is bounded to `[0,1]` for verifier diagnostics.

## Round-7 exact counterfactual closure

The minimal replay canary uses attempt 7 record
`b30f31bbfcfe41f1bf68b85495cfc3e3`, snapshot
`17ccb98232dd45e1bc504d9034f28ab3`, and one remaining retry chunk. It ran on
GPU 5 only. Every branch restored the same post-failure snapshot, sampled
fresh candidates with an independent seed, recomputed DPGMM/geometry/Gemini
semantics, executed the selected medoid for 10 steps, and observed progress.

- immutable plan SHA256:
  `fc60ea225aed828412947febc1f2d36b122f24b52f32c5d9d0ba669f316a51b8`
- adaptive schedule: `16 -> 32 -> 64`
- completed branches: 64; unique branch seeds: 64; unique event IDs: 64
- successes/stage advances: 0
- soft target: `p_expansion=1.0`
- Beta posterior 95% interval: `[0.9448283657, 0.9996105711]`; this remains a
  soft training target and is not used as a production routing threshold
- attached label: exactly one, source `counterfactual_replay`, weight `1.0`,
  `weak=false`, `M=64`, `m_success=0`
- result SHA256:
  `dad9e6cf9a738f32839de28bf2768cafd14c8df652df6696768ebd7d46ade2ef`
- branch ledger SHA256:
  `4b1c7fc79468c0e3c2a1767a11796e48e3b051880ac5db110fc8e36fd8964e7f`

Re-executing the same immutable plan returned the completed result without
loading models or adding events. Branch count remained 64, matching-label
count remained one, and both result and ledger hashes were unchanged. The
verifier feature records both the historical capture revision
`source:15f1acb9...` and replay revision `source:4b59653c...`.

## Frozen LIBERO-PRO protocol

- 40 formal cells, balanced at exactly 10 cells for each perturbation axis:
  object, swap, language, and environment.
- 16 suite resources were generated from four base suites and four variants.
- All 80 BDDL/init-state resources were hash-verified; each task has 50 init
  states.
- curriculum manifest SHA256:
  `e0db4ee7d7cbfbb184aa0feadbffca4bc681965b4ecaf45b95a0d24d6feb2a37`
- joint protocol manifest SHA256:
  `9360c991526337b554947b4b119b04c49783c99c37eed81b89ff7bc008602d5f`
- baseline manifest SHA256:
  `9f467b80994287b5b37a925fac80341ce0048d71dc966f8566f3b36d21208043`
- Registry revision 2 activates `policy_000` in `fixed_budget_4` mode with no
  learned verifier and is bound to the current joint protocol hash. Revision 1
  remains immutable in history.

Earlier base-LIBERO protocol files were moved, without deletion, to
`/shared/hengyil6/vls/self_improve/protocol/archive/20260826_base_libero_invalid/`.
The accidental base-LIBERO audit attempt produced no episode, decision, or
label and was moved to
`/shared/hengyil6/vls/self_improve/audit/invalid/20260826_base_libero/`.

## Machine-readable artifacts

- blocking preflight:
  `/shared/hengyil6/vls/self_improve/preflight/preflight.json`
- Gemini canary:
  `/shared/hengyil6/vls/self_improve/preflight/gemini_canary/result.json`
- training smoke:
  `/shared/hengyil6/vls/self_improve/preflight/training_smoke/result.json`
- snapshot canary:
  `/shared/hengyil6/vls/self_improve/preflight/snapshot_canary/result.json`
- teleoperation canary:
  `/shared/hengyil6/vls/self_improve/preflight/teleop_canary/result.json`
- round-7 replay plan/result/ledger:
  `/shared/hengyil6/vls/self_improve/audit/replay_canary_round7_v3/`

Formal audit or slow-loop work may start only after the machine-readable
blocking preflight is regenerated and every check is green for the exact
current source fingerprints.

This checkpoint validates the fast-loop route, exact snapshot replay, adaptive
counterfactual target, and append-only label closure for one LIBERO-PRO
context. It is not the full 1000/200/500-context verifier dataset, five-round
rolling experiment, regression suite, or final-sealed evaluation.
