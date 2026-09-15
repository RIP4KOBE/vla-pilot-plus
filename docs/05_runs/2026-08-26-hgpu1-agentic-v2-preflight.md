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

## 2026-08-28 automatic EXPANSION teleoperation

Normal non-baseline EXPANSION now launches a detached slow-loop worker at the
point where the persistent job is created.  After lookup and ticket issuance,
the worker automatically starts the localhost FastAPI/uvicorn frontend and
LIBERO-PRO backend, writes immutable job/ticket/round/process ownership, and
transitions `AWAITING_DEMOS -> COLLECTING`.  It polls a render-free health
endpoint, serializes multiple queued jobs on the single operator port, resumes
at the first uncommitted demonstration after a crash, and advances
`COLLECTING -> CURATING` only after a matching atomic completion marker.  Audit
and baseline executions explicitly disable human-service launch.

- operator URL: `http://127.0.0.1:8765/` (localhost/SSH tunnel only)
- automatic service runtime:
  `/shared/hengyil6/vls/self_improve/teleop_runtime/`
- automatic worker launch records:
  `/shared/hengyil6/vls/self_improve/slow_worker_launches/`
- isolated real start/health/owned-stop canary:
  `/shared/hengyil6/vls/self_improve/canaries/auto_teleop_supervisor_v3/canary_report.json`
- canary result: passed; no service or port remained; no policy checkpoint was
  loaded and no CUDA GPU was requested
- final project tests: `240 passed, 3 warnings`
- refreshed snapshot canary: passed on GPU 4, exact first action error `0`
- refreshed 20-step training smoke: passed on GPU 4 only, requested GPU count
  `1`, effective global batch `32`, 812 checkpoint tensors
- regenerated blocking preflight: passed for the exact current source tree

## 2026-09-03 protocol supersession

This page remains a historical record of the fixed-4 canaries. Those labels
and counts are not valid inputs to current training. All new collection,
replay, verifier training, and evaluation use the independent
`fixed_budget_10-v1` contract documented in
`docs/01_specs/2026-08-26-agentic-self-improving-v2.md`.

## 2026-09-07 fixed-10 replay live recovery

The existing hgpu1 replay worker (PID `92507`, policy device `cuda:6`) stopped
making progress after 160 branches across nine of the fourteen selected
contexts. Its last pre-recovery branch was written on September 4 at
15:18 UTC. The process remained alive but had reached its soft open-file
limit: 1024 descriptors, including 927 OBJ asset handles. LIBERO-PRO's
upstream `ControlEnv.reset` used `finally: continue`, suppressing file-limit
errors and looping indefinitely.

At approximately September 7, 01:58 UTC, the existing process's soft
`RLIMIT_NOFILE` was raised from 1024 to 65536; its hard limit remained
1048576. No worker restart, signal, model reload request, label rewrite, or
scheduled task was used for recovery. The same process immediately finished
initializing context 10 and proceeded through its already-scheduled model
loads. At 02:06 UTC a new completed branch was verified in the ledger
(161 total). Its task is
`libero_spatial_env/pick_up_the_black_bowl_on_the_wooden_cabinet_and_place_it_on_the_plate`,
record `0e68d600d80c4b1ab3fc01b6f1c40e5b`.

The following preventive changes were deployed in place for subsequent
application starts; already-imported code in PID 92507 was not hot-replaced:

- Disable only the MuJoCo 3.1.6 compiler asset cache. Its OBJ cache-hit path
  opens a resource but does not read it; the pinned resource-close path does
  not close an unread FILE. Zero cache capacity retains the normal read/close
  path without changing model weights, mesh geometry, or simulation physics.
- Raise the soft open-file limit up to 65536, subject to the existing hard limit.
- Replace the unbounded reset with at most 100 placement retries; other
  exceptions propagate. Add a main-thread initialization deadline of 120 seconds.
- Ensure `LiberoAdapter.close()` closes all owned simulator environments,
  remains idempotent, and still cleans the other environments if one close fails.

Validation on hgpu1: 20 focused tests passed, including fixed-10 and warm-replay
regressions. Recompiling an OBJ mesh 25 times produced identical mesh vertices
and faces and no descriptor growth. A separate, model-free smoke test created
and closed the real context-10 task three times at 64x64 observation resolution:
8.29, 8.04, and 8.42 seconds; descriptor counts after close were `[5, 5, 5]`.
The diagnostic process exited and did not contact either model API.

The replay plan and experiment contract were not changed:

- Plan SHA256: `d989c75c4d17f014cbad692926f8d98c54fc56a63256b3c23f320fe4a06a6475`.
- Label version: `fixed_budget_10-v1`; contract SHA256:
  `25d9231588d66b51f3a207b21b4de264561f3ee5a00b3952943e48336d25b855`.
- Ten retry chunks maximum, ten policy steps per chunk, with context-specific
  remaining budgets regenerated under fixed-10; context 10 starts at retry
  index 1 and has nine remaining chunks / 90 steps.
- Adaptive replay: 16 branches, extend to 32 only when the 95% posterior
  criterion is unmet; unresolved results are excluded from binary labels.
- Gemini thinking: medium; provider-call caps: factual 10000, counterfactual
  5000, total 15000. The live repair itself consumed no provider calls.

Live evidence remains in
`/shared/hengyil6/vls/self_improve/fixed_budget_10/audit/replay_worker_20260904T0935.log`
and
`/shared/hengyil6/vls/self_improve/fixed_budget_10/audit/fixed_budget_10/branches.jsonl`.

## 2026-09-07 fresh formal run and persistent human teleoperation

The user requested a fresh run, a resident teleoperation page at first
EXPANSION, and automatic continuation after demonstrations. The previously
invalidated stopped worker 102395 was replaced once; its deleted experimental
data was not restored. The new formal worker is PID 108592 on physical cuda:6.
It is warm and blocked at context 1/40, LIBERO-PRO `libero_10_lan`, task index 2,
`KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it`, online init 21.
The first EXPANSION occurred at policy step 60, not via a forced trigger.

- Slow job: `0aa4d2669fdb468ea954b12c99bf53f8`; current coordinator PID 111011.
- Ticket: `ticket-0427188102d5f7e4`; queue 1/15, first demo init 11.
- Resident portal PID 110349 on 127.0.0.1:8765; simulation backend PID 110356
  on 127.0.0.1:8766. Mac SSH tunnel PID 62205 exposes the same public localhost
  URL. Browser page and WebSocket status were verified, with zero human steps
  generated by Codex. The task prompt is the actual PRO language instruction.
- `--full-cycle` is active: curation, GPU co-FT, full-delta merge, policy gates,
  targeted fixed10 replay, verifier update and deployment are automatically
  orchestrated. Fast loop waits for the slow-cycle outcome. No scheduled task
  was created. The portal remains running between queues.
- 44 focused tests passed (including live local HTTP/WebSocket relay,
  backend-off portal persistence, barriers, job execution ordering, native-FPS
  source handling and raw evaluation model reuse). This does not claim that
  real co-FT/merge has completed: human demonstrations are still required.

The original replay source was missing on hgpu1. Its public checkpoint-matched
source `HuggingFaceVLA/libero` revision
`86958911c0f959db2bbbdb107eb3e17c5f9c798e` is downloading on the Mac (383 files,
34,926,157,548 bytes) before automatic checksum verification and rsync to
`/shared/hengyil6/vls/data/libero/HuggingFaceVLA/libero`. The explicitly launched
one-shot preparation process is PID 62230; its status is
`/tmp/vls-hf-wpcNOr/status.json`, log `prepare.log` in the same directory.
It publishes `/shared/hengyil6/vls/self_improve/coft_sources.json` only after
transfer completes. Before that, co-FT waits; no synthetic or partial source
is substituted. Native data FPS and observation/action ordering are preserved.

## 2026-09-07 Chinese task progress and warm steering update

The portal now shows general Chinese predicate-based task steps, demonstration
requirements and forbidden actions. Validation covers the 160 available BDDL
variants across the four PRO perturbation families; this is parser/predicate
coverage, not a claim of successful rollouts on 160 tasks. The UI's stove
instruction was corrected against its MuJoCo hinge/turn-on predicate: rotate
the knob, do not press down. Raw ticket identifiers and coverage codes remain
unchanged; the legacy ticket has a separate Chinese operator-display cache.

The upgraded live human backend is PID 111714 on port 8767, with resident portal
PID 112217 on port 8765. The operator has resumed this queue. The old unfinished
62-step draft remains only in the parked PID 110356 (`SIGSTOP`, private port
8766), not in training data. Main PID 108592 and its model/adapter objects were
not replaced. The stateless collection coordinator alone was reloaded as PID
113277 to import the new steering contract; it adopted the existing backend
without resetting the ongoing demonstration. No recurring automation was made.

After an independent hot-process canary, the explicit steering request was
applied once at the existing EXPANSION barrier in PID 108592. No policy action
was sampled, no model weights reloaded, and no human control was sent. The
debugger detached successfully (`TracerPid: 0`). Runtime proof is stored in:

- `fixed_budget_10/formal_experiment/runtime_steering_applied.json`
- `fixed_budget_10/formal_experiment/runtime_steering_settings.events.jsonl`
- `fixed_budget_10/formal_experiment/live_guidance_audit.json`

All paths are relative to `/shared/hengyil6/vls/self_improve`. The complete new
contract has SHA256
`d882da7b89066f19d1db1c259f4ec2479975b9628910be7276c9dded0834db78`.
The true pre-patch contract SHA256 is recorded as `pre_patch_contract_hash`:
`25d9231588d66b51f3a207b21b4de264561f3ee5a00b3952943e48336d25b855`.
Older artifacts retain that hash. `fixed_budget_10-v1` remains the namespace;
strict complete-contract checks distinguish the changed steering semantics.

Live inspection confirmed `core.pi05_steer.PI05PolicySteer` on `cuda:6`,
`use_guidance=true`, `use_diversity=true`, `use_fkd=true`, 40 particles and ten
flow steps. The suspended episode is at step 60, stage 1, with one active
guidance function and 13 three-dimensional keypoints. The most recent FKD
ESS history is nonempty (approximately 39.998/40); no resampling was needed.
Actual gradient-sampling logs show effective guide scales of 80.00, 79.17,
2.69, and 0.39 at steps 0, 10, 20, and 30 respectively. The subsequent reduction
comes from the existing reward-adaptive sigmoid, not disabled guidance.

This task's base guide scale is already 80 (task override of the YAML base 40).
Its ten capped retry inputs therefore retain guide 80 while diversity grows
from 10 through 11, 12.5, 14, 15, 16, 17, 18, 19, to 20. Guidance is still
adaptively reduced inside sampling. The hard limits apply after multiplication
and survive future deployment replacement of the policy object.

Focused remote validation: **58 passed, 105 deselected**, with three dependency
deprecation warnings. This includes Chinese teleoperation, ticket display
immutability, fixed-10 budgets, boundary-safe warm updates, post-deployment
caps, and invalid-scale rejection. It is not a new held-out evaluation or a
claim that the changed caps have reduced EXPANSION frequency. The full driver
remains waiting for demonstrations; the human backend was not restarted by
the steering update.

Outstanding diagnosis from the user's subsequent steering-wiring check:
`run_full_experiment.make_config` explicitly sets
`main.use_vlm_stage_recognition=false`, also present in the actual first
episode's saved config. `Main` therefore leaves `gemini_stage_recognizer=None`;
`_update_stage` has no other path to advance the guidance stage. Three stage
functions are loaded, but this run's guided samples through step 60 all use
stage 1. This is distinct from `use_guidance=true`: gradient steering works,
but automatic multi-stage guidance switching is not enabled. This diagnosis
does not establish the sole cause of EXPANSION, nor was that independent
behavior changed during this check. The Chinese human progress indicators are
separate simulator-predicate logic and are unaffected by this runtime switch.

### Stage-recognition diagnosis resolved at the user's request

At 2026-09-07 09:06:21 UTC, PID 108592 was updated at the existing EXPANSION
barrier: `use_vlm_stage_recognition=true`, `use_guidance=true`, and a real
`GeminiStageRecognizer` initialized with medium thinking and the shared 10000
factual-call ledger. The formal driver's on-disk configuration and its live
`make_config` function were both updated, so future warm contexts remain
enabled. New formal launches also reject a missing stage recognizer before
running an episode. Raw-policy evaluation and historical replay settings were
not changed by this request.

Policy, adapter and verifier identities were preserved; no model was reloaded,
no simulator step or provider request was issued, and backend PID 111714 and
portal PID 112217 remained running. The demonstration barrier was not released.
Proof: `fixed_budget_10/formal_experiment/runtime_stage_recognition_applied.json`
under the same data root, plus its append-only events ledger. Focused validation
passed all 24 tests, including generated context configurations and an injected
stage-1-to-2 response that resets the guidance reward baseline. Actual online
stage switching awaits subsequent fast-loop execution after demonstrations;
it was not fabricated by stepping the simulator during this update.

### 2026-09-07: account-conversation skill collection and diversity

The user replaced manual-first collection with a dedicated projectless Codex
conversation (`01a07b56-d94d-7ff3-ab96-2c2e0cd4e31c`, title
`LIBERO-PRO 技能规划与失败修正`). The conversation itself consumes scene/ticket
JSON over the SSH queue and returns a validated `SkillPlan`; it does not call a
separately billed API, run nested Codex CLI, execute robot actions, or receive
account credentials. No scheduled task was created. The initially drafted API
planner was replaced before making any live API request.

`configs/skill_collection.json` is a changeable experimental configuration.
The server composes generic move/gripper/articulate/predicate-wait skills using
delta OSC, damped-Jacobian IK previews on separate MuJoCo data, contact checks,
and native LIBERO-PRO success. No task sequence or object joint state is set in
code. Object poses are privileged demonstration-planning inputs, not extra
policy observations. The automatic attempt limit is 1200 control steps and
the manual fallback threshold is three consecutive physical-control failures;
these are demonstration settings, not the fixed10 RE-STEER retry budget.

Failures/aborted attempts are diagnostic NPZ plus JSON outside training paths.
Only native successful automatic traces are committed through the existing
T+1-state/T-action HDF5 queue and subsequently physically replay-validated before
LeRobot export. Operator confirmation remains distinct for human-source data.
The existing two successful human demonstrations and the parked 109-step draft
are preserved. The public web portal is launched only for `NEEDS_HUMAN`; one
successful human fallback returns ownership to the automatic collector.

Codex receives up to 24 previous successful actual EE-path summaries and must
plan meaningful, feasible differences in approaches, waypoints, transfer
height or grasp orientation while respecting each ticket coverage cell.
Artifacts record a 24-waypoint RMS path-distance advisory against the same
initial state. This is not a claim of statistical independence. Curation no
longer discards valid automatic paths merely for differing from a single
dominant trajectory mode or being faster than key-driven humans; native success,
finite actions and physical replay validation remain required.

Focused validation passed 52 tests covering the recorder, native success gate,
three-failure fallback, ownership recovery, account queue, portal behavior and
diversity preservation. Isolated actual-simulator evidence lives under
`/tmp/vls-skill-canary-mq3g_dmi` on hgpu1: a bounded Cartesian move passed with
7.21 mm final error; IK preview left live qpos unchanged; failures produced no
training HDF5. The dedicated conversation's first 22-skill plan passed schema
validation and executed 123 real steps before a robot joint-limit check stopped
skill 3. The failed trace was preserved and returned for replanning; no full
automatic task success was claimed by this canary.

The explicit cutover record is
`/shared/hengyil6/vls/self_improve/teleop_runtime/account_collection_cutover.json`.
It identifies the replacement coordinator/backend and preserved human draft;
the original model-bearing Main PID 108592 is reused, not cold-started.

### 2026-09-07: initial dual-camera images and failure keyframes

Skill planning now includes a `libero-skill-visuals-v1` manifest with the
recorded initial external (`agentview`) and wrist (`robot0_eye_in_hand`) RGB
frames. A retry also includes up to three timepoints from the latest failed
attempt, each with both cameras: failure, entry into the failing skill, and
before the last gripper-command transition, with temporal fallback when those
indices overlap. The default is at most eight images per request. The prior
three failures' text diagnostics and successful-path diversity inputs remain.

PNG pixels retain the original 256x256 recording orientation; the webpage's
180-degree CSS display rotation is not applied. Image axes are not world axes.
Every image is identified by attempt, camera, phase and T+1 observation index,
with source initialization/coverage, failure reason and SHA256. Initial images
are taken from `DemoWriter.frames[0]`, with no simulator step or additional
render. Old diagnostic NPZ failures can supply keyframes on resume; failed
episodes still never enter HDF5/LeRobot as successful training examples.

The dedicated account task must download the manifest-designated images,
verify their hashes, actually inspect them with image-viewing tools, and return
`visual_review` outside the unchanged `SkillPlan`. It records the manifest
hash, all viewed image IDs and a Chinese assessment of contact, occlusion,
grasp posture and uncertainty. Queue submission and the collector both reject
missing/stale/incomplete reviews. This is an auditable declaration of image
inspection, not a machine-verifiable proof of looking and not a substitute for
LIBERO-PRO predicates. Review provenance is also recorded in the attempt and
successful HDF5 metadata. There is no per-step model request or additional API.

Sixty focused tests passed, including exact RGB preservation, T+1 keyframe
alignment, legacy NPZ reuse, review validation and the complete account queue
request/response round trip. The live switch was at entry 4/15 with zero
actions: Main PID 108592 and its process start time were unchanged; lightweight
backend 116566 was replaced by 119598. All three committed demonstrations and
the two-failure streak were preserved. New request
`1a42ee2484b94beb9190277963464a06` contains eight images, including the previous
failure's frames 105, 117 and 118. This record confirms visual input delivery,
not yet a successful visually assisted rollout. Details and configuration:
`/shared/hengyil6/vls/self_improve/teleop_runtime/visual_collection_cutover.json`.

The account task subsequently verified and viewed all eight PNGs and returned
a complete visual review with a 25-skill plan; the queue accepted it. Actual
execution still lost the stove grasp, reaching three consecutive failures and
therefore `NEEDS_HUMAN`, not a fabricated visual success or a permission stall.

Repeated command approvals were traced separately to a running task turn that
retained its old workspace/network sandbox after the user selected Full access
at 10:35:16 UTC, plus its continued explicit escalation arguments. A default
SSH probe in that old turn failed with `Operation not permitted`. Ending only
that conversation turn and continuing the same task produced a fresh
10:44:23 UTC context with `approval_policy=never` and `danger-full-access`.
The new default SSH probe completed with exit code 0 without approval. No app
permission database, sandbox enforcement, model process or simulator was
modified for this recovery. Ordinary-operation preferences and the actual
verification are persisted in the planning task's own `AGENTS.md`.

### 2026-09-08 — Resume with 20 automatic attempts and retain success videos

The user resumed collection and raised only the automatic demonstration
collector's consecutive physical-failure limit from 3 to 20. Both the editable
`configs/skill_collection.json` and the dataclass default now use 20; the live
formal plan records it too. `fixed_budget_10-v1`, its ten RE-STEER chunks and
ten actions per chunk, and all existing labels remain unchanged.

The warm policy PID 108592 and its process start time were preserved. Before
updating the lightweight collector, its unsaved 60-action human draft (native
success false) was archived as diagnostic NPZ, not a successful training demo:
`automatic_collection/human-aborted-36a8849e34b1485bab6a1a5810cf3c4a`.
The existing three successes and three physical failures were retained. Backend
119598 was replaced by 121964; the existing coordinator 116873 and dedicated
account task were resumed without an automation. The new service reported
failure_limit=20, failures=3 and no human handoff. Fresh request
`323ac8b91a044dc891fe4aa0f27ced14` included all eight visual inputs; the dedicated
task verified and viewed them, then its corrected plan physically succeeded.
Queue entry 4 was committed as `raw/demo-003-748b45d3.hdf5`. Collection advanced
to entry 5/15 with four successes (two human, two automatic) and a fresh failure
count of zero. Maintenance evidence is in
`/shared/hengyil6/vls/self_improve/teleop_runtime/resume_limit20.json`.

Previously those successes retained complete T+1 dual-camera RGB in HDF5 but
had no standalone MP4. `mode_gate.demo_videos` now creates CPU-only H.264 viewing
copies in each ticket's `videos/` directory: external camera left, wrist right,
20 recorded frames/second, initial and native-success final frame included.
Only the viewing copy is rotated 180 degrees to match the existing webpage;
the original HDF5 pixels, labels and bytes are untouched. Sidecar JSON records
source/video hashes, task, init state, coverage cell, frame count and encoding.
The first four successful demonstrations have been exported and frame-count
verified. Videos reflect native collection success, not a claim that subsequent
replay/curation has already passed.

Newly started backends launch a finite asynchronous export after committing a
human or automatic success. To keep the current collector hot, its dedicated
account task also runs the same idempotent one-shot exporter after actual
success/queue-advance events and before handoff/completion. It is not a timer,
resident watcher or scheduled task. Video errors cannot delete a committed
demonstration or turn a failed attempt into training data.

The user additionally prohibited teleportation/state-edit shortcuts. Deployed
controller, adapter and session hashes matched the inspected local code; the
LIBERO-PRO tracked submodule code had no modifications. The planner schema
rejects teleport/reset/set-state operations and arbitrary qpos/body/code fields.
IK modifies separate scratch `MjData`, while physical motion goes through
`TeleopSession.execute_action` and the native simulator step. These constraints
are persisted in repository and dedicated-task instructions. Seventy-seven
focused regression tests passed, including old 3-to-20 handoff restoration,
the twentieth-failure boundary, original data/video integrity, rejected invalid
plan channels, unchanged live state during scratch IK and a direct-write
source regression check. Static tests are not a general security sandbox;
independent action-only replay is recorded separately as physical evidence.

The independent check completed for the automatic success
`demo-002-46923ab6.hdf5`: all 721 recorded actions were replayed in a separate
CPU-physics environment after exactly one initial-state restoration, with zero
intermediate restorations. Every flattened simulator state, qpos and qvel
matched exactly (maximum error 0.0), and the native success predicate remained
true. The original HDF5 SHA256 stayed
`50f6929299951812b7dccfc1441d152a3a42fecd2cd8081d319f6a60b659a568`.
Diagnostics were written to
`automatic_collection/motion_integrity_audit.json`, not back into the original
training artifact. This was one end-to-end audit of a saved automatic success,
not a claim that all future trajectories have already been audited. The normal
pre-training batch action-replay gate remains required for every demonstration.

### 2026-09-08 — First 15-demo queue completed; repair replay/curation handoff

Round 1 of ticket `ticket-0427188102d5f7e4` reached native `COMPLETE` with 15
committed demonstrations (two human and thirteen automatic) and fifteen
dual-camera MP4s. The final video is `demo-014-3b2c62b6.success.mp4`. The account
planner used at most 13 failed attempts on the difficult twelfth entry before
the following attempt succeeded, within the configured 20-failure handoff.
This does not claim that every path was already replay-validated.

Inspection immediately after collection found a pre-existing wiring omission:
`scripts/validate_teleop_ticket.py` existed, but `SlowLoopWorker._curate` never
called it. Thus curation classified all fifteen `pending_batch_validation`
successes as rejected and started an unnecessary second collection round.
No files were deleted. The second-round backend 143314 was paused at zero
actions and its claimed request `e45cd2c4843b414aa8f28320aa1c0a42` was cancelled
by the existing pause mechanism before any plan was submitted. The account
planner was explicitly placed on handoff pause.

The worker now invokes the batch action validator before curation. Curation
also independently refuses to move/reject a committed success while its
action replay is pending or errored. Validator infrastructure errors stop the
handoff; genuine physical mismatches remain rejectable and never become valid
by changing a flag. Successful validations are resumed without rerunning.
The existing state/qpos/qvel tolerances remain 5e-3/1e-4/5e-3. Validation uses
CPU physics and 32px diagnostic rendering, with no policy reload, provider
request, label rewrite or training-frame change. A per-demo progress artifact
and execution log are written in the slow job directory. Ninety-eight focused
tests passed, including the missing-stage regression and infrastructure-error
protection.

The fifteen exact files were moved back from `rejected/` to `raw/`, with SHA256
checks before and after. The original real round-001 completion was verified;
an append-only `COLLECTING -> CURATING` recovery transition records that empty
round 2 was aborted, without pretending a new collection or a replay succeeded.
Only the lightweight coordinator was replaced (116873 -> 144708). Resident
policy PID 108592 and its start time were unchanged. The recovered coordinator
continues the original full-cycle command and now performs real batch replay
before dataset export, CoFT, model merging and subsequent gates. Recovery
evidence: `teleop_runtime/precuration_replay_recovery.json`; replay status/log:
`slow_work/0aa4d2669fdb468ea954b12c99bf53f8/demo_replay_validation.{json,log}`.
No scheduled task was created. Batch completion and training readiness must be
read from their real outputs, not inferred from the fifteen native successes.

The first validator launch exposed an incorrect new mapping from CUDA GPU 6
to EGL display index 6. These are different namespaces on hgpu1. That override
was removed; a real MuJoCo EGL auto-selection import probe passed, and all
seven handoff-specific tests passed again with a regression that preserves an
existing EGL selection independently of the training GPU. The lightweight
coordinator was refreshed once more, recorded in the same recovery artifact;
no policy model was restarted and no validation failure was bypassed.

At 04:38 UTC the corrected coordinator PID 145304 and validator PID 145435
were live. The first recovered demonstration `demo-000-41d413db.hdf5` had
completed real action replay with maximum state error 0.0; validation was on
`demo-001-80d285c1.hdf5` (1/15 completed, no errors or mismatches). This confirms
that the repaired handoff is executing physics, not merely launching a
process. The dedicated planner resumed bounded waiting for future legitimate
requests; the cancelled empty-round request remains prohibited.

### 2026-09-08 — Completed demo export; repair original replay-source transfer

All fifteen demonstrations passed action-only replay at 05:14 UTC, each with
maximum simulator-state error 0.0. Curation accepted all fifteen across the
five coverage cells (three per cell); the LeRobot v3 export completed at
05:33 UTC with 15 episodes and 10,022 frames. All fifteen viewing videos and
the raw/curated HDF5s remain present. No additional collection is needed for
this ticket.

The next training transition exposed a separate unfinished dependency: the
previous day's public `HuggingFaceVLA/libero` transfer had exhausted its three
attempts after SSH disconnections. Its local copy was complete, but hgpu1 had
only about 14.9 GB of the pinned 34,926,157,548-byte source. Consequently,
`coft_sources.json` had correctly not been published. The old coordinator then
repeated `DATASET_READY -> RETRYABLE_ERROR` instead of expressing the source
wait. No co-FT optimizer step or model merge had run at this point.

The existing finite `/tmp/vls-hf-wpcNOr/prepare_replay.py` was repaired in place:
resume-only mode verifies the complete local copy against the pinned Hub
revision (LFS SHA256 and Git blob IDs), uses four disjoint resumable transfer
shards with SSH keepalives and bounded retries, verifies every remote SHA256,
repairs mismatched files, and atomically publishes the unchanged source spec
only after complete verification. The one-shot process is detached (current
PID 95649), holds a single-instance lock, and exits on completion; no cron or
Codex scheduled task was created. Interrupted chunks were retained when
moving the transfer into this detached process. Local status remains
`/tmp/vls-hf-wpcNOr/status.json`; server-side progress is
`/shared/hengyil6/vls/self_improve/coft_source_transfer_status.json`, whose
size-complete counts are explicitly **not** checksum-validation claims.

`SlowLoopWorker` now remains at `DATASET_READY` while the source spec is absent
and reports `waiting_for.kind=coft_replay_source`. A malformed published spec
still fails visibly. Retry transitions clear stale current-error fields;
the prior errors remain in the event history. Twelve targeted tests passed,
including delayed publication, automatic continuation, real demo-replay
ordering, full-cycle execution order, and unchanged native-FPS source mixing.
Five additional isolated transport tests cover retryable SSH failures,
non-retryable remote contract errors, partial-file/checksum options, absence
of deletion flags and finite retry bounds. Bulk-transfer shards allow up to
100 transport attempts because the existing route continues to disconnect;
this is independent of, and does not change, the twenty-failure robot planner
limit.

Only the idle coordination process was refreshed (145304 -> 147274), after
verifying no training/validation child was running. Main policy PID 108592
and its recorded start ticks were unchanged. The original CoFT recipe,
source proportions, physical GPU 6, full-cycle merge/gates and fixed-budget-10
label contract are unchanged. At 06:02 UTC the transfer was still in progress
(181 size-complete files, 15,923,044,311 bytes); remote integrity verification
and GPU training were **not yet complete**. Coordinator startup was observed
waiting on disk reads of Python dependencies under high server I/O pressure,
not reloading the resident rollout model.

At 06:04 UTC the refreshed coordinator had published `DATASET_READY`,
`error: null`, and `waiting_for.kind: coft_replay_source`. This is the real
running wait state, not only a successful process launch. The server source
progress then recorded 182 size-complete files / 16,022,967,396 bytes, with
`checksum_verified: false` until the final all-file verification.

## 2026-09-09 — resume raw policy gate after masked simulator termination

The original replay source subsequently reached READY: all 383 files
(34,926,157,548 bytes) passed SHA256 verification. Job
`0aa4d2669fdb468ea954b12c99bf53f8` completed GPU-6 CoFT at 1,000 optimizer
steps (last logged loss 0.051, actual new/replay draws 16,000/16,000), validated
its reconstructable delta, and materialized all four language-merge candidates.
These completed training and merge artifacts were retained, not rerun.

At 2026-09-08 14:46 UTC, the raw gate stopped on its fourth alpha-selection
context: `libero_10_env`, task index 3 (black bowl into the bottom drawer and
close it), init state 41. The pinned `BDDLBaseDomain.step` overwrites the
robosuite returned `done` with predicate success. With `ignore_done=False`,
robosuite nevertheless sets its internal `done` at the configured 720-step
horizon. The five reset-settling steps count toward that horizon, while the
adapter counts only policy actions. A non-successful episode therefore needs
to truncate after 715 policy actions; the old adapter missed that signal and
issued an illegal extra action. This was not a model-load or model-merge error.

`LiberoEnv` now reads (never resets or overwrites) the native simulator `done`
flag and propagates horizon truncation. `LiberoAdapter` preserves that flag
in both policy and teleoperation paths. Native predicate success still wins,
including at the horizon. Reset settling fails explicitly if it consumes the
whole horizon instead of attempting another action. No horizon, retry budget,
physics state, reward, success predicate, label version, or policy changed.

`RawPolicyEvaluator` now fsyncs each completed context immediately, including
completed parallel work before propagating an infrastructure error. Failed
executions remain pending instead of becoming binary policy failures. Warm
evaluation records each context/config and simulator step counters, and fixes
resident console handlers retaining closed per-episode log streams. Eighteen
targeted tests passed, including serial/parallel interruption and resume, warm
model reuse, success/timeout distinction, action-interface invariants, and two
actual reset/horizon cycles on the affected LIBERO-PRO task (small test-only
horizon; no policy weights loaded in the canary).
The complete adapter-import/compatibility test file also passed (16 tests).

The three earlier completed contexts had valid `results.txt`, successful
videos, and original global completion logs (234, 255, 247 policy steps), but
no ledger rows because the old evaluator wrote only after the entire batch.
The original candidate checkpoint digest was recomputed and matched
`a91d0d4b8f953e4c4a20f437bec3f6cead00a66219417b1b35c4a5ed596ead2c`.
Those exact three manifest-bound contexts were restored to the ledger with
explicit recovery provenance. Their results were not rerun or relabeled.
The original failed job log, result, interrupted-context diagnostics and
hashed recovery evidence remain under the job's
`policy_gate/recovery_20260909/` directory.

At 02:00 UTC, the existing coordinator PID 147274 consumed a one-shot
`retry.request` and launched gate PID 154343 on physical `cuda:6`, starting at
the interrupted fourth context. Main experiment PID 108592 remained warm and
unchanged. No scheduler, data transfer, demonstration collection, CoFT rerun,
or premature policy deployment was started. Full-gate completion is still
pending; the formal breadth-first experiment remains at context 1/40 while
the existing slow-loop gate executes.

At 02:06 UTC the formerly crashing fourth context completed normally with
`success=false`, 715 policy steps, five settling steps, and native
`simulator_done=true`, `simulator_timestep=simulator_horizon=720`. Its row was
durably appended before the next context started. The alpha-0.2 candidate now
has 4/100 completed alpha-selection contexts (three successes and one genuine
timeout), and the same gate process has entered context 5 without reloading
the model. This verifies recovery past the original failure boundary; it is
not a claim that the whole gate or formal experiment has completed.

## 2026-09-09 current-task gain / old-task forgetting selection update

The user replaced global-macro selection with current-ticket improvement
balanced against old-task forgetting, explicitly allowing old-task sample SR
to decline. `configs/policy_promotion.json` now controls the editable
`current-task-retention-tradeoff-v1` protocol. All four already merged
candidates (language alpha 0.2/0.4/0.6/0.8) are compared; no global top-two
pruning, zero-drop gate, or requirement that the combined score be positive
remains. Eligible candidates must improve the held-out current task. After
removing Pareto-dominated choices, maximize `new_task_SR_gain - lambda * F`,
where `F = mean_task(max(0, parent_SR - candidate_SR))` and lambda defaults
to 1.0. Improvements on other old tasks cannot conceal a task's decline.

For ticket `ticket-0427188102d5f7e4`, the current-task bank is nine independent
init states (12, 15, 20, 23, 29, 30, 36, 44, 5), each with two paired seed
repeats: 18 episodes per policy. The five demo init states (11, 17, 40, 42, 9)
are excluded. The old-task bank has 97 contexts from 39 other task/variant
entries. The parent and all four candidates receive both identical banks.
The sealed final set is not opened. Reports record the full selection config,
per-task forgetting, paired sample diagnostics, and candidate tradeoff scores;
these sample results are not a statistical proof of zero forgetting.

At 03:12 UTC only old gate PID 154343 was stopped, preserving 23 completed raw
episodes. Their profile/context/checkpoint-bound results can be reused with
explicit provenance; three overlap the new current-task bank. Old ledger rows
are not relabeled or changed. The old gate log, result and ledger snapshot plus
code hashes and the selection-change record are retained in
`policy_gate/selection_update_20260909/` under slow job
`0aa4d2669fdb468ea954b12c99bf53f8`. Training at 1000/1000 and the four merged
checkpoints remain untouched; no data transfer or collection was repeated.

Fifty-two targeted tests passed (one opt-in real-simulator test skipped; that
canary had passed in the preceding horizon repair). Tests cover allowed
declines, adjustable penalties, Pareto selection, held-out-only scoring,
paired evaluation of all candidates, config/report identities, strict raw
result reuse, durable resume, warm reuse and deployment compatibility.
The first test invocation mixed EGL and OSMesa settings; rerunning with
consistent test-only OSMesa settings resolved those import errors.

At 03:24 UTC a one-shot retry resumed the existing coordinator PID 147274 and
launched gate PID 156824 on physical `cuda:6`. Main experiment PID 108592
remained warm and unchanged. The gate entered current-task evaluation,
beginning with the `policy_000` parent baseline on the stove task. No new
scheduler was created and no policy was prematurely deployed. Full candidate
evaluation remains in progress; the main experiment is still waiting on this
slow loop at formal context 1/40.

## 2026-09-09 allow ties and correct first-task retention population

The user removed strict current-task improvement as a promotion requirement
and requested the largest difference score among the merged candidates.
`current-task-retention-tradeoff-v2` now selects directly by
`(candidate_current_SR - parent_current_SR) - lambda * old_task_forgetting`
over all candidates. Neither positive current gain, a positive total score,
nor a Pareto filter is an eligibility gate. Old-task forgetting remains the
mean of positive per-task SR drops; the default lambda remains 1.0. Ties
prefer less forgetting, greater current gain, then smaller alpha/policy ID.
The resident slow worker's trigger-check compatibility field now denotes the
winner selected by this rule, with separate honest comparison-complete and
current-task-improved fields; a tied 100% candidate is not rejected downstream.

There are no earlier completed LIBERO-PRO tasks in this first formal context:
the formal completed-context ledger does not yet exist, status records zero
completed contexts, the slow-loop history has no deployed jobs, and the CoFT
source spec has no old-ticket datasets. Its original `HuggingFaceVLA/libero`
source is pretraining replay, not previously learned PRO tickets. The former
97-context / 39-task proposed retention population consisted of unvisited PRO
tasks and must not be called old-task forgetting.

Retention history now comes from the manifest-bound formal plan and its
completed-context ledger. Future tasks and the current task are excluded.
An empty history skips old-task evaluation and records it as not applicable,
not measured zero forgetting. Thus this first gate requires only the existing
18 current-task episodes per model (parent plus all four merges), avoiding
485 unnecessary old-task episode slots. Later gates use identical held-out
states and seeds on actually completed earlier PRO tasks. Optional original
LIBERO pretraining-retention diagnostics remain separate and were not started.

Sixty-two targeted tests passed (one prior-tested real-simulator canary skipped).
Coverage includes full-score ties, choosing the largest difference despite
non-positive individual gains, no hidden trigger rejection, first-task
skipping, later-task history filtering, provenance and missing-history guards,
paired evaluation, warm model reuse and resumable raw result preservation.

At 04:20:58 UTC, the in-flight alpha-0.2 evaluation committed its eleventh
current-task result. Only then was gate PID 156824 stopped for the code
handoff. All 52 ledger rows remained: 23 historical alpha100 rows, 18 parent
current-task rows, and 11 alpha-0.2 current-task rows. Main warm PID 108592
and coordinator PID 147274 were left intact. The v1 log, result, progress
identity, and raw ledger copy are preserved under
`policy_gate/selection_update_20260909_v2/`, alongside the v2 config, explicit
empty history, validation counts and source hashes. A one-shot retry hands
the existing job to the v2 gate; training, merges and completed episodes are
not repeated.

At 04:21 UTC gate PID 161643 resumed under coordinator 147274 on physical
`cuda:6`. Its progress artifact records protocol v2, input hash
`099fd297f92fa14d9e3b7b7e62e1a98abfb24e8fe27893e2e675da8285cd90ae`, and an
explicit empty prior-task history. The parent bank is already complete and
the alpha-0.2 candidate resumes after its first 11 completed current-task
episodes. Main warm PID 108592 remains unchanged. No scheduled task was added.

## 2026-09-10 expansion-only demonstrations and restart from task 2

The user requested that the 40-task formal experiment stop retrieving old
deltas to skip demonstration collection. `current-task-demonstrations-v1`
preserves the fast-loop route: native LIBERO-PRO success ends the task;
verifier RE-STEER continues without demonstrations; only EXPANSION enters the
mandatory current-ticket collection, action replay, curation, training and
new-delta merge path. Candidate scoring remains gain minus old-task forgetting,
including ties and non-positive scores. No deployment-time retrieval system
is added. Legacy REUSE jobs/reports fail closed, and the worker checks current
ticket/task/parent/dataset/training/delta provenance before evaluation and
again before deployment. Capability/signature labels, their visual features,
and measured evaluation outcomes are still saved with record-only provenance.
Being the highest-scoring merge is not labeled transferable remediation.
Verifier factual/replay label collection and online updating remain enabled.

At the user's explicit request, task 2 and task 3 results were invalidated and
moved outside the active experiment to
`/shared/hengyil6/vls/self_improve/invalidated/20260910_task2_restart`.
This is recoverable quarantine, not permanent deletion. The rollback manifest
lists all 77 artifact moves and backups of original ledgers. The active ledger
lost one completed task-2 episode, 12 task-2/3 decision records and 31 dependent
labels, plus the corresponding slow-loop events and reused capability record.
Task-1 snapshot labels produced under the invalidated task-2 policy were also
excluded, not mistaken for clean task-1 evidence. Original labels remain in
the quarantined ledger copies. Task 1's episode bytes, ticket, trained delta,
selected policy, replay result and pre-experiment verifier manifest were hash
checked unchanged; consumed factual/counterfactual API call ledgers were also
hash checked unchanged and were not refunded or reset.

The kept policy is `policy_58c2c59d297f78e3`, trained from task-1 demonstrations
with delta `delta_dbd4ababd6f1894c`. Registry revision 4 was restored through
an auditable new revision 7. Revision 5 was not clean: its verifier already
included ten task-2 contexts. Both later verifiers (`verifier_361f21a3ecbddaeb`
and `verifier_071b184fb80f1df7`) were therefore quarantined. The surviving
incident ledger contains four task-1 decisions, three factual labels and four
new-policy counterfactual labels. A clean GPU verifier refresh warm-started
`verifier_cb46f70e3e963357` using exactly those four task-1 replay contexts;
none of the invalidated formal records entered training. Result
`verifier_59398c18df578ada` is paired with policy 58c at revision 8 in learned
verifier mode. It is explicitly provisional (no independent held-out claim).
Pre-experiment initializer data are retained, not confused with the later
formal experiment's invalidated records.

Old task-3 coordinator 205801 and replay child 225060 were stopped under the
experiment park barrier. Main 108592 then received one controlled shutdown
to rebuild its in-memory completed-context set from the corrected ledger.
Finite supervisor 176566 was preserved, with a brief coordinated suspension
during ledger replacement. No scheduler was created. The existing dedicated
Codex account task was resumed to await new EXPANSION tickets, and explicitly
told not to process the invalidated task-2/3 jobs. Restart target is formal
task 2/40, `KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it`,
environment perturbation (`libero_10_env`, `use_environment`), initial state 37,
using physical `cuda:6` and existing local weights.

The final regression run passed 302 tests (242 core/protocol/registry/supervisor
tests and 60 controller/agent/collection/handoff tests). Coverage includes
EXPANSION-only collection, native-success precedence, ten RE-STEER retries,
legacy-REUSE rejection, current-ticket training evidence, retained record-only
capability labels and idempotent post-deployment label append. At 02:45 UTC the
existing supervisor launched main PID 236045 at task 2/40, initial state 37,
with clean revision 8. The stored plan records capability labels as record-only,
and the bounded Codex collection task confirmed queue waiting after the park
was removed. No external API call ledger was reset.

At 02:46:50 UTC main 236045 entered RUNNING for task 2, with learned verifier,
guidance and VLM stage recognition enabled, fixed10 labels and ten retries.
Its registry synchronization selected the retained task-1 policy 58c (not the
invalidated task-2 reuse policy). Server/source hashes match for the changed
runtime modules and mandatory-demonstration tests.

## 2026-09-10 native Codex account top-level planner

At the user's request, a separate projectless native Codex task,
`LIBERO-PRO 顶层规划` (`01a0893c-15b0-7203-881c-de3c5bcee058`), was created
with model `gpt-6-astra` and reasoning effort `ultra`. It uses the signed-in
account, not a Gemini or OpenAI API key, a nested Codex CLI, or copied account
credentials. The existing demonstration skill-planning task remains separate.
The structured queue is bound to this task/model/effort, checks the request and
image hashes, requires actual review of every supplied image, and validates
the original response schemas before acceptance. Timeout/pause/invalid outputs
fail closed; there is no Gemini fallback and no new scheduled task.

The migrated roles are mode semantic scoring, stage/guidance recognition,
optional visual grounding, and Chinese expansion-ticket collection planning.
Their prompts, evidence and output contracts retain their previous functions.
The learned verifier still selects the fast-loop route, native LIBERO-PRO
predicates remain the success authority, and the existing GPT-4o reward-code
generator is outside this Gemini migration and remains unchanged. Legacy
class/CLI/ledger names are retained only where needed for compatibility;
production client construction and optional startup no longer require Google
credentials. The legacy provider-canary command now validates the account
task and rejects old Gemini evidence as proof of current readiness.

Three real account requests passed: Chinese ticket quotas (15 demonstrations),
semantic scoring of a saved task-2 candidate overlay, and stage/guidance
recognition of a saved task-2 image. Both visual inputs were hash verified and
actually viewed in the native task. These were read-only canaries, with zero
simulator actions or experiment labels written. Their complete provenance is
in `/shared/hengyil6/vls/self_improve/planner_runtime/migration_canary.json`.
The existing factual call ledger counts the new account requests together
with historical calls; it was not reset. Existing fixed10 labels and their
historical configuration were not rewritten. Newly generated evidence records
the actual account planner profile separately from the legacy label contract.

The handoff used the existing finite experiment park barrier. Old main 236045
and old slow coordinator 238071 were retired; demo backend 238238 was retained
throughout, including its physical attempts and diagnostics. Supervisor 176566
resumed the same task-2 job `fce4dc5511ff4318b97b87cd2b7eeb66`, ticket
`ticket-960b3efdcb89f8f5`, under account-enabled coordinator 240409. The ticket
was already in flight through the old client when the migration was requested;
it is preserved as historical input, not reissued or mislabeled as Codex output.
The task-1 policy/verifier at revision 8, completed episode bytes and current
ticket bytes were hash checked unchanged. The migration manifest and source
hashes are stored in `planner_runtime/migration.json`; the owned park files
are retained there as completed handoff records. No demonstrations were
discarded or recollected for the provider switch.

The final startup/account/preflight/mandatory-demo/supervisor regression group
passed 201 tests. Earlier migration groups passed 244 and 129 tests (overlapping
groups, not additive totals). The last startup cleanup replaced only the
wait-only main, before any policy was loaded; it caused no additional policy
cold load. Final main PID 241687 is alive in WAITING_FOR_DEMONSTRATIONS for the
same COLLECTING job, supervisor state is RUNNING, and both coordinator 240409
and demo backend 238238 are alive. One of 40 contexts is complete. Final source
hashes match the server, protected artifact hashes remain unchanged, and both
Codex tasks remain active. Completing collection/validation/training remains
the existing prerequisite to returning to the fast loop.

## 2026-09-10 collection-native success; replay no longer gates demonstrations

The user's explicit correction supersedes the earlier pre-training action-
replay gate: `libero-collection-native-success-v1` uses the LIBERO-PRO native
success recorded in the original collection. A second simulation's success,
failure, missing/error status or numerical divergence is diagnostic only and
cannot reject that demonstration or trigger replacement collection. Actual
failed original collection episodes remain excluded. The physical action-only
controller, no-teleport constraints and fixed10 verifier/counterfactual label
protocol are unchanged. The slow worker no longer launches a mandatory demo
replay subprocess before curation; optional replay tools remain available.

Task 2's job `fce4dc5511ff4318b97b87cd2b7eeb66`, ticket
`ticket-960b3efdcb89f8f5`, had collected 15 native successes. The previous
composite state-consistency gate rejected all 15 even though its batch replay
reported native success for 14. A repeated action replay on a separate copy of
demo 008 reported native failure; this discrepancy remains diagnostic evidence,
not a rewritten success flag or a new collection requirement. All 15 original
HDF5s were restored from rejected to raw with byte-identical whole-file SHA256.
Original action, state, image, success and replay fields were not edited. The
15 two-camera viewing videos, task-1 episode ledger, current ticket and active
policy/verifier registry were hash checked unchanged. Coverage is complete:
five each vertical, angled-front and angled-side approaches; no refill needed.

The owned park barrier was released after stopping only old coordinator 240409
and the empty, expired-request round-002 collection backend 259518. Wait-only
main 241687 and finite supervisor 176566 were preserved. The existing supervisor
resumed CURATING at job sequence 17, copied all 15 curated files and started
LeRobot export; training/merge have not yet completed at this checkpoint. The
dedicated skill task was told to skip expired request
`ce3b73b491114b87b29bfb76c4dec5fc`, collect no replacement for this ticket,
and resume waiting for future valid EXPANSION requests. No scheduler was added,
no physical failure counter reset and no model reloaded for this repair.

Audit and original strict-gate reports are retained under
`/shared/hengyil6/vls/self_improve/native_success_repair/`; `migration.json`
records the complete operation, 15 restored successes, zero collection deficit,
unchanged file hashes and source hashes. The updated regression group passed
248 tests in 17.80 seconds, including accepted original success with pending,
failed or errored replay, rejected original native failure despite replay
success, no mandatory replay subprocess, dataset handoff, physical collection,
video retention and supervisor behavior. A follow-up status-publication fix
clears a stale collection timeout before a resumed long export begins; its
source hash and the current status-only repair are recorded separately in
`native_success_repair/status_publication_fix.json`. Export coordinator 263866
was observed running with newly written training-image files; main 241687 was
not restarted for either change.
