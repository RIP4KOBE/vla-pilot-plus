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

Verifier retraining keeps the existing evidence contract: audit,
counterfactual replay, factual online retry, and low-weight demo-match labels.
Demonstrations enter only after same-snapshot trajectory-to-mode matching;
post-expansion rechecks remain remedy evidence rather than verifier targets.

The visual trajectory planner is frozen to
`gemini-robotics-er-2-preview` through the Interactions API. Its structured
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

## Frozen protocol

Every self-improvement rollout, audit, regression, trigger recheck, probe, and
final evaluation runs on **LIBERO-PRO**, never an unperturbed LIBERO suite.
The 40 formal cells are balanced across object, spatial-swap, language, and
environment axes (10 each). Original LIBERO is used only as the source of the
pretrained PI0.5 checkpoint and the frozen replay portion of co-FT.

The joint manifest contains 40 LIBERO-PRO cells and disjoint per-task state shards for
policy alpha-selection (100), regression (250), final-sealed (500), verifier
train/calibration/test, development probe, and demo/online use.  `final_sealed`
is protected by an access guard and must be opened once, only after all code,
hyperparameters, deployed policy, verifier, and registered baselines are
frozen.

Current server artifacts:

- curriculum: `/shared/hengyil6/vls/self_improve/protocol/curriculum.json`
- joint protocol: `/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json`
- baselines: `/shared/hengyil6/vls/self_improve/protocol/baseline_manifest.json`
- blocking preflight: `/shared/hengyil6/vls/self_improve/preflight/preflight.json`

## Candidate mathematics

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
CUDA_VISIBLE_DEVICES=4 $PY scripts/self_improve.py collect-verifier-audit \
  --limit 1 --gpu-index 4
$PY scripts/self_improve.py list-jobs
$PY scripts/self_improve.py run-job --job-id JOB_ID
$PY scripts/self_improve.py execute-job-spec --spec JOB_SPEC_JSON
$PY scripts/self_improve.py deployed-dev-evaluate
```

Rollout, replay, canary, audit, and default co-FT jobs use one GPU. Co-FT keeps
per-device batch 4 with eight-way gradient accumulation, preserving the frozen
effective global batch of 32. A two-GPU/four-way-accumulation profile remains
supported, but job specs never allocate more than two GPUs and always record
the physical selection.

The audit command first supports a stratified pilot.  Formal collection must
not start unless blocking preflight is green.  GPU training and historical
replay execute as code-owned job specifications; rollout never mutates its
live policy.  `active.json` is read only at episode boundaries.

## Promotion and reporting

Alpha-selection is 100 raw episodes, top-two regression is 250 paired raw
episodes, and every surviving candidate must beat its parent on the paired
seen/unseen trigger recheck.  Promotion results, deployed-development results,
and final-sealed results use distinct metric roles and files.  A newly
installed policy is fresh-loaded and checked before deployment.  If its new
verifier misses the gate, the policy deploys with fixed-budget-4 and the
verifier is promoted later without rerunning the policy gate.

No formal audit, five-round evolution, baseline headline run, or final-sealed
evaluation may be reported while the preflight file has `passed=false`.
