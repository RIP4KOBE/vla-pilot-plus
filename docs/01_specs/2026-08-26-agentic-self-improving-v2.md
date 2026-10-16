# Agentic Self-Improving v2 implementation contract

This document describes the implementation deployed to **hgpu1 only**.  The
canonical repository is `/shared/hengyil6/vls/repo` and every persistent
runtime artifact is under `/shared/hengyil6/vls/self_improve`.

## Runtime architecture

The controller owns three external routes, while the learned verifier remains
binary:

1. sample 40 policy trajectories;
2. abstract them into DPGMM modes;
3. score safe modes with geometry and Gemini and execute the selected medoid;
4. observe 10 environment steps;
5. after three stagnant chunks or contact, capture the exact post-failure
   simulator snapshot and sample a fresh batch;
6. apply the frozen θ₀ VLM features and the trained two-class output head;
7. route directly by head argmax to `RE-STEER` or `EXPANSION`, without a
   hand-set probability threshold.

`EXECUTE` is controller state, not a third verifier class.  A terminal timeout
creates a ticket but never creates a verifier target after the execution
horizon has expired.  Provider, schema, artifact, and checkpoint failures
abort and are never converted into capability failures.

Verifier retraining uses the independent `fixed_budget_10-v1` evidence
contract: audit, counterfactual replay, factual online retry, and low-weight
demo-match labels. Historical fixed-4 labels are never joined into this set.
Demonstrations enter only after same-snapshot trajectory-to-mode matching;
post-expansion rechecks remain remedy evidence rather than verifier targets.

### Demonstration success authority (2026-09-10 user correction)

`libero-collection-native-success-v1` accepts a demonstration using the native
LIBERO-PRO success recorded during its original collection. Action replay is
optional diagnostics, not a curation/training prerequisite. A missing replay,
a replay infrastructure error, a failed replay or numerical state/qpos/qvel
drift must not reject an originally successful demonstration or create a refill
request. Retain the original trajectory, success signals, videos and replay
results unchanged; never relabel a failed replay as successful. Failed original
collection episodes remain diagnostics only, excluded from success training
data. Bounded physical OSC execution, read-only object poses, no teleportation,
finite/aligned dataset checks and existing diversity/coverage planning remain.

This supersedes earlier mandatory demonstration-replay gates. It does not
change fixed-budget counterfactual RE-STEER replay or verifier label generation.

Each branch has at most ten RE-STEER chunks of ten policy steps (100 steps).
Counterfactual replay starts at 16 branches and stops when at least 95% of the
posterior lies on one side of 0.5; otherwise it extends once to 32. A context
still uncertain at 32 is `AMBIGUOUS/CENSORED` and receives no binary label.
The persisted call ledgers cap factual traffic at 10,000 and counterfactual
traffic at 5,000, for a combined maximum of 15,000 calls. Direct LIBERO
success and terminal signals stop a branch without Gemini confirmation.

The `fixed_budget_10-v1` label contract records
`gemini-robotics-er-2-preview` with `thinking_level=medium` through the
Interactions API. Its structured
response and a real image request are exercised by the blocking provider
canary. The separate text-only ticket planner remains independently versioned.

## Code ownership

| Surface | Implementation |
|---|---|
| chunk state machine and progress | `mode_gate/state_machine.py`, `mode_gate/progress.py` |
| DPGMM, FK diagnostics, 79D/20D features | `mode_gate/mixture.py`, `mode_gate/features.py` |
| geometry, semantic mode scoring | `mode_gate/geometry.py`, `mode_gate/semantic_planner.py` |
| frozen theta0 features and verifier | `mode_gate/scene_encoder.py`, `mode_gate/verifier.py` |
| exact snapshots and counterfactual replay | `mode_gate/snapshots.py`, `mode_gate/offline_replay.py` |
| decisions, late labels, signatures | `mode_gate/incidents.py`, `mode_gate/signatures.py` |
| ticket, teleop, curation, LeRobot export | `mode_gate/tickets.py`, `mode_gate/teleop.py`, `mode_gate/data_pipeline.py` |
| three-source co-FT and full task vectors | `mode_gate/training.py`, `mode_gate/checkpoint_math.py` |
| candidate gates and deployment | `mode_gate/candidates.py`, `mode_gate/promotion.py`, `mode_gate/registry.py` |
| resumable slow loop and GPU jobs | `mode_gate/slow_loop.py`, `mode_gate/slow_worker.py`, `mode_gate/job_runner.py` |
| audit, final seal, throughput, baselines | `mode_gate/audit.py`, `mode_gate/final_evaluation.py`, `mode_gate/throughput.py`, `mode_gate/baselines.py` |
| CLARE PI0.5 injection and training | `mode_gate/clare_integration.py` |

## Versioned protocol

Every self-improvement rollout, audit, regression, trigger recheck, probe, and
final evaluation runs on **LIBERO-PRO**, never an unperturbed LIBERO suite.
The 40 formal cells are balanced across object, spatial-swap, language, and
environment axes (10 each). Original LIBERO is used only as the source of the
pretrained PI0.5 checkpoint and the frozen replay portion of co-FT.

The joint manifest contains 40 LIBERO-PRO cells and disjoint per-task state
shards. Verifier collection is breadth-first across every task, then targeted
toward minority classes and contexts near the decision boundary. The
train/calibration/test counts `500/100/200` are suggested planning targets,
not collection or deployment gates. `final_sealed`
is protected by an access guard and must be opened once, only after all code,
hyperparameters, deployed policy, verifier, and registered baselines are
frozen.

### Initialization-only verifier fit (2026-09-07 user direction)

The current pre-experiment initialization uses
`training_mode=initialization_all_data`, configured in
`configs/verifier_cost_capped_pilot_gpu6.json`. All usable fixed-10 factual
RE-STEER outcomes and counterfactual labels are pooled for fitting on
`cuda:6`: no calibration/test subset, no internal early-stopping holdout,
and no fitted probability calibrator. The final epoch is retained. The
robot policy and cached theta0 features are not retrained or reloaded.

Contexts remain deduplicated, with counterfactual evidence taking priority
over a factual observation of the same context. Explicitly ambiguous replay
contexts, incomplete outcomes, and fixed-4 labels remain excluded. Original
split assignments in source ledgers are provenance only for this run; the
artifact lists every consumed record as training data. None of those records
may subsequently be presented as an independent held-out evaluation of this
initialization or a model descended from it.

Training-set diagnostics establish only that the initializer was fitted and
saved, not generalization quality. The artifact is marked initialization-only
and unevaluated; the absence of held-out metrics does not prevent producing
an initializer. Formal experiments will collect further data and retrain.

Current server artifacts:

- curriculum: `/shared/hengyil6/vls/self_improve/protocol/curriculum.json`
- joint protocol: `/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json`
- baselines: `/shared/hengyil6/vls/self_improve/protocol/baseline_manifest.json`
- blocking preflight: `/shared/hengyil6/vls/self_improve/preflight/preflight.json`

## Candidate mathematics

### Top-level account planner (2026-09-10)

`configs/planner_account.json` binds the active semantic scorer, visual stage/
guidance recognizer, grounding interface and ticket/Chinese-instruction planner
to native Codex task `01a0893c-15b0-7203-881c-de3c5bcee058`, model `gpt-6-astra`,
reasoning `ultra`, using the signed-in ChatGPT account. The task itself supplies
the answer over a dedicated SSH/file request queue; no Google API client,
OpenAI API-key client, nested Codex CLI, credential transfer or scheduler is
used for these roles. The legacy Gemini config/class names remain importable
for historical artifacts and injected-client tests, not a production fallback.

Original prompt content, image pixels, strict output schemas, mode coverage,
Chinese coverage-partition validation and semantic-scoring responsibilities
remain unchanged. Responses bind request hash, task ID, model and reasoning,
and include a declaration of actual image review checked before commit. The
learned binary verifier still decides post-failure RE-STEER/EXPANSION; native
LIBERO-PRO success is authoritative. The demonstration skill planner task and
bounded action-only controller are unchanged. GPT-4o reward-code generation
remains its separate existing OpenAI integration.

Historical fixed10 label contracts/records are not rewritten. New semantic
artifacts additionally record the actual account planner provenance. Cache
keys include the actual model and reasoning; old Gemini semantic cache entries
are not returned as Codex scores. Existing cost ledgers retain their historical
filenames/schema and consumed calls; new reservations explicitly identify the
ChatGPT account and share the same cap rather than resetting it.

### Mandatory demonstrations during the 40-task experiment (2026-09-10)

The editable runtime protocol is `current-task-demonstrations-v1`. Every
EXPANSION follows current-task ticket issuance, Codex-first demonstration
collection, action-only replay validation, curation, co-FT from the active
parent, a new full delta, candidate merging, evaluation, and verifier refresh.
Signature Lookup no longer selects a policy or skips collection/training.
Demonstration collection is triggered by EXPANSION only: a native LIBERO-PRO
success ends the task and a verifier RE-STEER decision continues the fast loop
without demonstrations. Task coverage alone does not trigger collection.
Capability labels, signature features and measured evaluation outcomes remain
persisted with `use_status=record_only`; they do not select a policy during the
experiment. A selected merge is not automatically a validated reusable remedy.
Verifier decision/replay labels and online retraining remain unchanged.
Legacy REUSE jobs/reports cannot resume into evaluation or deployment. Historical
records remain evidence of their original protocol, not successful remediation.
The candidate objective stays current-task gain minus old-task forgetting;
neither strict improvement nor zero forgetting is required. Its winner flag
does not validate transferable capabilities. Post-experiment deployment-time
model selection is deferred and is not implemented by this change.

Production expansion stores the complete task vector
`delta = theta_ft - parent`, fixes vision/action alpha to one, and searches
language alpha over `{0.2, 0.4, 0.6, 0.8}`.  Accepted lineage can always be
reconstructed from theta0 plus immutable full deltas.

The `Always Expansion + RETAIN` control is separate and exact:

```text
candidate = parent + alpha * (theta_ft - parent)
alpha_vision = alpha_language = alpha_action
alpha in {0.2, 0.4, 0.6, 0.8}
```

It always bypasses Signature Lookup and follows the same ticket, demo, SFT,
raw regression, and trigger recheck chain.  It does not mean “keep the old
policy”.

CLARE wraps every PI0.5 action-expert FFN with a parallel bottleneck adapter,
uses per-layer autoencoder novelty to decide expansion, trains adapters before
discriminators, routes without a task ID, and serializes topology, weights,
links, statistics, and provenance as one immutable artifact.

## Operational entry points

All commands use the pinned server interpreter:

```bash
cd /shared/hengyil6/vls/repo
PY=/shared/hengyil6/vls/envs/vla-pilot/bin/python

$PY scripts/self_improve.py preflight \
  --baseline-manifest /shared/hengyil6/vls/self_improve/protocol/baseline_manifest.json
$PY scripts/self_improve.py registry-bootstrap
$PY scripts/self_improve.py collect-verifier-audit --limit 1 --gpu-index 6
$PY scripts/self_improve.py list-jobs
$PY scripts/self_improve.py run-job --job-id JOB_ID
$PY scripts/self_improve.py execute-job-spec --spec JOB_SPEC_JSON
$PY scripts/self_improve.py deployed-dev-evaluate
```

Normal (non-baseline, non-audit) EXPANSION can detach a resumable slow-loop
worker only when `mode_gate.auto_start_expansion_worker=true` is explicitly
selected. Once the ticket is issued, that worker starts the
permanent localhost portal at `http://127.0.0.1:8765/` and a per-ticket
simulation backend on port 8766. The portal relays HTTP/WebSocket traffic
without stepping the simulator; between queues it serves a waiting page.
The worker waits for the queue-completion marker, stops only the owned
simulation backend, and continues into curation. A crashed backend is relaunched on the
same ticket and resumes at the first uncommitted demonstration.  `run-job`
uses this managed behavior only on explicit invocation. No timer or recurring
task is created by the runtime.

EXPANSION is a blocking boundary for the fast loop: while the current ticket
lacks a nonempty demonstration dataset that has passed curation, the resident
policy must not execute another chunk or start another task. UI startup or a
recording-completion marker alone does not release this barrier. Waiting keeps
the models loaded and reports `WAITING_FOR_DEMONSTRATIONS`; resumed experiment
plans must also honor their own outstanding tickets. Local teleoperation
health checks bypass provider proxies explicitly.

The formal driver uses `run-job --full-cycle`: after collection it executes
the generated co-FT, full-delta model merge, raw policy gates, targeted
fixed-budget-10 counterfactual replay, and verifier refresh/deployment jobs.
Its stronger barrier waits until the slow-loop outcome is DEPLOYED or
POLICY_REJECTED, keeping the fast model resident and idle during GPU training.
Insufficient evidence follows the existing fixed-budget-10 fallback; it is
not reported as a passed verifier gate. No final sealed evaluation is opened.
The public page remains online after each collection and can be refreshed
for another ticket. `park.request` cooperatively parks the formal driver;
removing it resumes with the same loaded model and outstanding ticket checks.

All production GPU jobs use physical `cuda:6` without CUDA device remapping.
Raw gate evaluation keeps one model resident across contexts for each
candidate. Co-FT retains batch 4 × accumulation 8, 1000 AdamW optimizer steps,
and source ratios 50/25/25 (50/50 before an old deployed ticket exists).
Original LIBERO replay and new PRO demonstrations keep their native metadata
and action-step ordering; the pinned LeRobot factory computes delta timestamps
independently for each source. Semantic tensor keys/dtypes/shapes must agree;
display names and native FPS are recorded without rewriting original data.

Rollout, replay, canary, audit, and default co-FT jobs use one GPU. Co-FT keeps
per-device batch 4 with eight-way gradient accumulation, preserving the frozen
effective global batch of 32. A two-GPU recipe remains available in training
utilities, but the current formal executor accepts only the user-selected
single physical GPU.

The audit command first supports a stratified pilot.  Formal collection must
not start unless blocking preflight is green.  GPU training and historical
replay execute as code-owned job specifications on physical `cuda:6` without
remapping `CUDA_VISIBLE_DEVICES`; rollout never mutates its live policy.
`active.json` is read only at episode boundaries.

## Promotion and reporting

Promotion uses the editable `configs/policy_promotion.json` and the
`current-task-retention-tradeoff-v2` selection protocol. Evaluate the parent
and **every** trained/merged candidate on the current ticket's held-out task
first. By default this combines that task's alpha-selection and regression
states with two policy-seed repeats; training/demo states and the final seal
are excluded. For the current stove ticket this is nine states × two seeds
= 18 episodes per policy. There is no global-macro top-two pruning and no
seen-demonstration score in candidate ranking.

Old tasks are only earlier completed tasks in this formal continual-learning
experiment, resolved from its plan and completed-context ledger. The main
loop writes completion after the associated slow loop ends. Unvisited
LIBERO-PRO tasks are not old learned tasks. Original LIBERO pretraining
retention is a separate optional diagnostic, not the same population.
For the first stove ticket the history is empty: skip retention, use a
not-applicable forgetting contribution of zero, and select the merged model
with the highest current-task SR (ties use smaller language alpha/policy ID).
This is not a claim of measured zero forgetting. For later tickets, evaluate
parent and all candidates on identical alpha-selection contexts belonging
only to earlier completed tasks, excluding the current task itself.
Old-task success-rate drops are **allowed**, not a hard rejection gate.
Measure forgetting as the task-macro mean of `max(0, parent_SR - candidate_SR)`:
gains on one old task do not hide losses on another. Report net macro SR
change, each task's drop, and paired uncertainty diagnostics separately.

Among **all** trained/merged candidates, directly maximize
`current_task_SR_gain - forgetting_penalty * macro_forgetting`.
The penalty defaults to 1.0 (equal percentage-point weight) and is editable.
Ties prefer less forgetting, then greater current-task gain, then smaller
language alpha and policy ID. Neither strict current-task improvement, zero
forgetting nor a positive combined score is required. A parent already at
100% must not make promotion impossible. Pareto flags are diagnostic only,
not an extra filter before scoring. The trigger report's `passed` field means
the candidate was selected by the difference-score rule, not that its SR
strictly exceeded the parent. Do not demand extra demos merely because all
candidates tie the parent. Small per-task samples do not prove statistical
zero forgetting; per-task significance is not a deployment requirement.

Reports record the complete selection config, paired contexts, parent and
candidate scores, per-task losses, tradeoff scores, and decision. Raw episode
reuse requires identical policy ID/checkpoint digest, manifest, full context
(including seeds), and raw evaluation profile; original rows remain unchanged
and reuse is recorded with provenance. Incompatible, invalidated, deployed,
or final-sealed metrics cannot supply promotion results. Changes to selection
config create a new report identity while reusing compatible raw evidence.
Promotion results, deployed-development results,
and final-sealed results use distinct metric roles and files. A newly
installed policy is fresh-loaded and checked before deployment.  If its new
verifier misses the gate, the policy deploys with fixed-budget-10 and the
verifier is promoted later without rerunning the policy gate.

No formal audit, five-round evolution, baseline headline run, or final-sealed
evaluation may be reported while the preflight file has `passed=false`.

## 2026-09-07 operator guidance and steering limits

The human portal derives Chinese task steps from each LIBERO-PRO environment's
actual BDDL goal predicates, including source/destination container access.
Completed conditions are reevaluated, so a dropped object or undone condition
can become incomplete again. Grasp/lift is an auxiliary manipulation hint,
not a substitute for simulator task success. Unsupported or unreadable
conditions remain unknown. The complete task and demonstration requirements,
coverage instructions, and forbidden actions are shown in Chinese. Legacy
tickets retain their immutable raw content and use a separate Chinese display
cache; future tickets request Chinese operator instructions directly. Stove
controls in this simulator are rotary knobs, not push buttons.

The full-architecture online driver explicitly enables both `use_guidance`
and `use_vlm_stage_recognition`; an unavailable recognizer is an initialization
error, not permission to silently run all task stages with stage-1 guidance.
Stage queries use medium thinking and the shared factual-call budget. This is
separate from the simulator-predicate indicators shown to human operators.

The backend port follows the validated live-service record across queues;
the public URL remains `http://127.0.0.1:8765/`. A UI/backend upgrade must not
discard an uncommitted human trajectory or restart the resident policy.

Absolute steering inputs are limited **after** retry multipliers:
`guide_scale <= 80` and `diversity_scale <= 20`. The ten retry multiplier pairs
are `(1,1)`, `(1.15,1.1)`, `(1.3,1.25)`, `(1.5,1.4)`, `(1.75,1.5)`, `(2,1.6)`,
`(2.25,1.7)`, `(2.5,1.8)`, `(2.75,1.9)`, `(3,2)`. The existing adaptive sigmoid may
reduce effective gradient guidance below this limit. This is an upper bound,
not a requirement to use strength 80 at every denoising step. A task whose
base guide scale is already 80 cannot exceed 80 through retry multiplication.

Explicit runtime steering requests are applied only at an episode boundary or
an EXPANSION barrier with no unfinished factual labels. They preserve policy,
adapter and verifier objects, keep ten chunks of ten steps, and record the full
new contract/hash. Subsequent labels use the new contract; historical labels
and their configuration hashes are not rewritten or silently pooled.
