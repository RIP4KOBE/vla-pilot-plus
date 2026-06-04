---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/agent/prompts/rdt_phase1_evidence_collection_prompt.md
summary: RDT Phase-1 Evidence Collection Prompt
duplicate_sources:
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/prompts/rdt_phase1_evidence_collection_prompt.md
  - .worktrees/feat/rdt-libero-dataset_finetune/agent/prompts/rdt_phase1_evidence_collection_prompt.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/prompts/rdt_phase1_evidence_collection_prompt.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/agent/prompts/rdt_phase1_evidence_collection_prompt.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/prompts/rdt_phase1_evidence_collection_prompt.md
---

# RDT Phase-1 Evidence Collection Prompt

## Purpose

Use this prompt to execute the first round of evidence collection for the RDT-LIBERO integration failure.

This prompt is for:
- instrumentation
- controlled comparison
- evidence collection
- diagnosis update

This prompt is **not** for repair yet.

The output must be saved into the workflow directory so that the debugging process is reproducible and cumulative.

---

## Workflow root

Assume the workflow root is:

`WORKFLOW_ROOT=.worktrees/feat/rdt-integration/docs/superpowers`

All outputs must be saved under this directory.

---

## Required inputs

Read and use these files:

- `WORKFLOW_ROOT/plans/2026-04-22-rdt1b-integration.md`
- `WORKFLOW_ROOT/plans/2026-04-30-rdt-libero-failure-analysis.md`
- `WORKFLOW_ROOT/plans/2026-04-30-rdt-debugging-plan.md`

If versioned variants exist, use the latest relevant versions and state which files were used.

Also use relevant code files as needed.

---

## Round and output convention

This execution is **evidence round 1** unless I explicitly say otherwise.

Create and use this directory:

- `WORKFLOW_ROOT/evidence/round-1/`

Inside it, create subdirectories as needed:

- `WORKFLOW_ROOT/evidence/round-1/logs/`
- `WORKFLOW_ROOT/evidence/round-1/images/`
- `WORKFLOW_ROOT/evidence/round-1/stats/`

Also create:

- `WORKFLOW_ROOT/evidence/round-1/summary.md`
- `WORKFLOW_ROOT/runs/2026-04-30-phase1-evidence-session-1.md`

If these files already exist, create versioned variants instead of silently overwriting.

---

## Task

I am debugging an RDT-1B integration issue.

Current symptom:

- LIBERO evaluation success rate is `0/10`
- rollout videos show robot motion that appears random and task-unrelated

I want you to execute **Phase 1 evidence collection only**.

---

## Operating mode

You are in **diagnostic mode**.

Do **not** fix the system yet.
Do **not** refactor.
Do **not** modify multiple core modules.
Do **not** implement speculative changes.

Only make the smallest changes necessary to collect decisive evidence.

If you add instrumentation:
- keep it minimal
- keep it easy to revert
- document every instrumentation point in the summary
- distinguish observability-only changes from behavior-changing changes

Prefer no behavior-changing changes unless absolutely necessary to make evidence observable.

---

## Primary hypotheses to discriminate

Your evidence collection should help distinguish among these possible causes:

1. custom denoising loop uses the wrong latent dimensionality or wrong semantics
2. language embeddings are silently zero or invalid
3. image inputs are flipped or semantically mismapped
4. proprio inputs are malformed or mismatched
5. action conversion outputs are saturated, clipped, or invalid
6. official checkpoint inference itself is not behaving as expected on the given input

---

## Required tasks

Execute the following in order unless blocked.

### Task 1 — Establish a repeatable debug case
If practical, create a deterministic setup using:
- one frozen observation
- one fixed instruction
- one fixed seed

If full freezing is not practical, explain why and create the closest stable approximation.

Save details in:
- `WORKFLOW_ROOT/evidence/round-1/summary.md`
- and any auxiliary artifact paths you create

### Task 2 — Collect language embedding evidence
Collect:
- embedding shape
- embedding norm
- whether zero fallback is active
- whether embeddings differ for clearly different instructions

Save raw logs/stats under:
- `WORKFLOW_ROOT/evidence/round-1/logs/`
- `WORKFLOW_ROOT/evidence/round-1/stats/`

### Task 3 — Compare official inference vs integrated custom inference
On the same input:
- run the official RDT inference path
- run the integrated custom path
- compare output shape, magnitude, temporal structure, and basic statistics

Do not repair differences yet. Only measure and analyze them.

Save outputs and comparison notes under:
- `WORKFLOW_ROOT/evidence/round-1/stats/`
- `WORKFLOW_ROOT/evidence/round-1/summary.md`

### Task 4 — Inspect visual input before encoding
Save one representative image that is actually fed into the RDT image encoder.

Confirm whether:
- orientation looks correct
- camera semantics appear correct
- preprocessing seems consistent with expectation

Save the image under:
- `WORKFLOW_ROOT/evidence/round-1/images/`

Record interpretation in:
- `WORKFLOW_ROOT/evidence/round-1/summary.md`

### Task 5 — Inspect proprio input
Log:
- first-step proprio values
- dimensionality
- basic ranges
- any obvious anomalies

Determine whether the values look like expected joint-space or expected robot-state inputs.

Save supporting evidence under:
- `WORKFLOW_ROOT/evidence/round-1/logs/`
- `WORKFLOW_ROOT/evidence/round-1/stats/`

### Task 6 — Inspect raw action outputs
Before environment stepping or final control conversion:
- log raw action statistics
- check range
- clipping
- NaN / Inf
- per-dimension magnitude
- if useful, compare custom vs official output statistics

Save supporting evidence under:
- `WORKFLOW_ROOT/evidence/round-1/logs/`
- `WORKFLOW_ROOT/evidence/round-1/stats/`

---

## Required summary artifact

Write a full round summary to:

- `WORKFLOW_ROOT/evidence/round-1/summary.md`

This file must contain the following sections.

### 1. Inputs used
List:
- plan files used
- code files touched
- commands/scripts run if relevant

### 2. Instrumentation changes
For each change include:
- file / location
- why it was necessary
- whether it changes runtime behavior or only observability
- whether it should be reverted later

### 3. Evidence collected
For each required task include:
- raw observations
- artifact file paths
- interpretation
- which hypotheses it supports
- which hypotheses it weakens

### 4. Updated root-cause ranking
Re-rank the hypotheses based on collected evidence.

For each hypothesis include:
- confidence level
- evidence supporting it
- evidence against it
- missing evidence

### 5. Repair readiness
State clearly whether evidence is now sufficient to enter repair mode.

If **yes**:
- identify the single root cause that should be repaired first
- explain why other fixes should wait

If **no**:
- list exactly what additional evidence is required
- explain why repair would still be premature

### 6. Risks and ambiguities
List any places where evidence is still ambiguous and where a careless fix could make the system harder to debug.

### 7. Recommended next step
Choose one:
- proceed to analysis update
- collect round-2 evidence
- proceed to repair planning

---

## Required session log

Write a concise session record to:

- `WORKFLOW_ROOT/runs/2026-04-30-phase1-evidence-session-1.md`

This file must include:
- what was attempted
- what files were created
- key findings
- whether repair mode is justified
- exact next recommended prompt

---

## Required chat output

In your chat response, provide only:

1. paths of files created or updated
2. a concise evidence summary
3. updated top root-cause ranking
4. whether repair mode is justified
5. the exact next prompt I should run

Do not stop with a conversational diagnosis only.
The primary deliverable must be the saved evidence package.

---

## Constraints

- Only add minimal diagnostic instrumentation and targeted checks
- Keep changes small and easy to revert
- Prefer logs, saved artifacts, tensor statistics, and side-by-side comparisons
- Avoid changing core inference behavior
- Avoid mixing “collect evidence” with “apply a fix”

---

## Important stop rule

If one hypothesis becomes overwhelmingly supported, do **not** fix it yet unless I explicitly ask for a repair plan.

Stop after evidence collection and updated diagnosis.

---

## Governing principle

Follow this principle strictly:

**Do not convert uncertainty into code changes. First convert uncertainty into evidence.**