# RDT Debugging Plan Prompt

## Purpose

Use this prompt to convert the current RDT integration analysis into a structured, evidence-driven debugging plan.

This prompt is for **planning only**.
It must **not** directly repair the system.
It must **not** skip to implementation.
It must produce project files inside the workflow directory so the debugging process is durable and auditable.

---

## Workflow root

Assume the workflow root is:

`WORKFLOW_ROOT=.worktrees/feat/rdt-integration/docs/superpowers`

All outputs must be saved under this directory.

---

## Required input files

Read and use these files if they exist:

- `WORKFLOW_ROOT/plans/2026-04-22-rdt1b-integration.md`
- `WORKFLOW_ROOT/plans/2026-04-30-rdt-libero-failure-analysis.md`

If equivalent files exist with different dates but clearly represent:
- the original integration plan
- the current failure analysis

then use those instead and state which files were used.

Do not ignore project-local documents in favor of generic robotics advice.

---

## Task

I am debugging an RDT-1B integration issue in my project.

Current symptom:

- LIBERO evaluation success rate is `0/10`
- rollout videos show robot motion that appears random and task-unrelated

I already have:
1. the original integration plan
2. a failure analysis document
3. relevant project code context if needed

Your task is to generate a **debugging plan**, not a repair plan.

Do **not** write code.
Do **not** apply fixes.
Do **not** assume the integration plan is correct.
Do **not** collapse uncertainty into implementation.

Instead, produce a step-by-step debugging workflow that distinguishes between competing hypotheses using evidence.

---

## Main objective

Create a practical debugging workflow that tells me:

1. what to check first
2. what exact evidence to collect
3. what each result would imply
4. when I have enough evidence to move into repair mode
5. what should not be changed yet

---

## Fragile assumptions first

Before giving conclusions, first identify which assumptions in the existing integration plan are most fragile or most likely to be false in practice.

Examples of the kinds of fragile assumptions that may exist:
- denoising latent dimensionality assumptions
- action chunk semantics assumptions
- language embedding assumptions
- image orientation / camera semantic assumptions
- proprio field assumptions
- scheduler / sampler equivalence assumptions

Do not assume these are correct merely because they were written in the original plan.

---

## Required output artifacts

You must create or update the following files.

### 1. Main plan artifact

Write the full debugging plan to:

- `WORKFLOW_ROOT/plans/2026-04-30-rdt-debugging-plan.md`

If a debugging plan already exists, create a new version instead of overwriting blindly, e.g.:

- `WORKFLOW_ROOT/plans/2026-04-30-rdt-debugging-plan-v2.md`

State clearly which file you created.

### 2. Session log

Write a concise execution/session note to:

- `WORKFLOW_ROOT/runs/2026-04-30-debugging-plan-session-1.md`

This file must include:
- inputs used
- assumptions identified
- output file created
- top 3 debugging priorities
- recommended next prompt to run

If a same-name file already exists, append `-v2` or increment session number.

### 3. Do not leave results only in chat

Do not stop after printing the plan in the conversation.
The primary deliverable is the saved file in `plans/`.
The secondary deliverable is the saved session summary in `runs/`.

---

## Required content for the debugging plan file

The plan file must contain the following sections.

### 1. Debugging objective
Summarize the debugging goal in 3-5 bullets.

### 2. Fragile assumptions in the current integration plan
List the assumptions most likely to be false in practice.

For each assumption include:
- assumption
- where it appears in the integration plan if identifiable
- why it is fragile
- what evidence is needed to verify it

### 3. Current root-cause ranking
Restate the hypotheses as a debugging-priority list.

For each hypothesis include:
- hypothesis
- why it matters
- what evidence would confirm it
- what evidence would weaken or reject it

### 4. Phase-based debugging plan
Use these required phases:

#### Phase 0 — Repro and baseline control
Goal: establish a deterministic and repeatable debug setup.

#### Phase 1 — Non-invasive evidence collection
Goal: collect logs, saved intermediates, and controlled comparisons without changing core inference logic.

#### Phase 2 — Hypothesis discrimination
Goal: determine which root cause is primary.

#### Phase 3 — Entry criteria for repair
Goal: define when it is justified to begin code repair.

For each phase include:
- objective
- concrete tasks
- exact evidence to collect
- expected healthy result
- failure signature
- decision rule for next step
- expected output files under `WORKFLOW_ROOT/evidence/` or `WORKFLOW_ROOT/plans/`

### 5. Ordered checklist
Provide a strict ordered checklist.

For each item include:
- task name
- why it comes at this stage
- what to inspect
- expected healthy behavior
- failure signal
- next action depending on result
- where the result should be saved

### 6. Minimal evidence package
Define the minimum evidence required before attempting repair.

Group into:
- mandatory
- optional

For each evidence item, specify the intended file location.

### 7. Repair readiness criteria
Define explicit criteria for when debugging can stop and repair planning can begin.

### 8. Risk controls and stop-loss rules
Define rules to prevent blind over-editing.

Include:
- what must not be changed during evidence collection
- what must not be changed in the same iteration
- when to revert and reassess
- when not to continue with automatic execution

### 9. Suggested next prompts
At the end, provide:
- one prompt for executing Phase 1 evidence collection
- one prompt for updating analysis after evidence collection
- one prompt for generating a repair plan after evidence is sufficient

Each suggested prompt should mention which file(s) it should read and which file(s) it should write.

---

## Required output format in chat

In your chat response, provide only:

1. the path of the debugging plan file created
2. the path of the session log file created
3. a 5-10 bullet executive summary
4. the exact next prompt I should run

Do not dump the entire full plan only in chat if it has already been saved to file.

---

## Important constraints

- Do not provide code
- Do not propose broad rewrites
- Keep the workflow incremental and falsifiable
- Prioritize high-signal, low-cost checks first
- Explicitly avoid mixing multiple uncertain fixes into one iteration

---

## Governing principle

Follow this principle strictly:

**Do not convert uncertainty into code changes. First convert uncertainty into evidence.**