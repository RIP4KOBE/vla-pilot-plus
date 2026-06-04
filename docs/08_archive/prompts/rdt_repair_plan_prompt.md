---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/agent/prompts/rdt_repair_plan_prompt.md
summary: RDT Repair Plan Prompt
duplicate_sources:
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/prompts/rdt_repair_plan_prompt.md
  - .worktrees/feat/rdt-libero-dataset_finetune/agent/prompts/rdt_repair_plan_prompt.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/prompts/rdt_repair_plan_prompt.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/agent/prompts/rdt_repair_plan_prompt.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/prompts/rdt_repair_plan_prompt.md
---

# RDT Repair Plan Prompt

## Purpose

Use this prompt only after diagnostic analysis and evidence collection are sufficient.

This prompt generates a **minimal repair plan** for a **single confirmed primary root cause**.

It is for planning only.
It is not for direct execution yet.

The plan must be saved into the workflow directory so that repair scope, assumptions, and validation steps are documented before code changes begin.

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
- `WORKFLOW_ROOT/evidence/round-1/summary.md`

If newer versions exist, use the latest relevant versions and state which files were used.

Use relevant project code context if needed.

---

## Preconditions

Only continue if the evidence is sufficient to identify one primary root cause.

If evidence is still ambiguous:
- do not produce a speculative multi-fix repair plan
- explicitly say repair planning is premature
- state what missing evidence is required
- save that conclusion to the session log

---

## Task

We have completed:
1. initial failure analysis
2. debugging plan
3. at least one round of evidence collection
4. updated root-cause ranking

The RDT-LIBERO integration issue is now sufficiently narrowed down.

Your task is to generate a **minimal repair plan**, not to execute it yet.

---

## Goal

Create a low-risk repair plan that addresses only the **single most strongly supported root cause first**.

Do not bundle multiple fixes together.
Do not broaden scope unless absolutely necessary.

---

## Required output artifacts

### 1. Main repair plan

Write the repair plan to:

- `WORKFLOW_ROOT/plans/2026-04-30-rdt-repair-plan-v1.md`

If a repair plan already exists, create a new version:
- `...-v2.md`, etc.

### 2. Session log

Write a concise session note to:

- `WORKFLOW_ROOT/runs/2026-04-30-repair-plan-session-1.md`

This file must include:
- inputs used
- confirmed root cause selected
- why repair planning is justified now
- output file created
- recommended execution scope

Do not leave the plan only in chat.

---

## Required content for the repair plan file

### 1. Confirmed root cause
State the single root cause this repair plan will target.

Also explain why it is sufficiently confirmed.

### 2. Why this should be fixed first
Explain why this fix has:
- highest expected value
- lowest remaining ambiguity
- best chance of improving behavior or observability

### 3. Minimal code-change scope
List the exact files, functions, and logic areas likely involved.

Do not write code.

For each file / logic area include:
- what part is relevant
- what should change
- what must remain unchanged

### 4. Step-by-step repair sequence
Provide a minimal sequence of repair steps.

For each step include:
- intended change
- why it is necessary
- what assumptions it depends on
- what must not be changed in the same step
- how to verify immediately after the step
- what artifact should be saved after verification

### 5. Validation plan
Define validation at increasing levels.

#### A. Unit / local validation
What should be checked immediately after the edit?

#### B. Frozen-sample validation
How should repaired behavior be compared against pre-repair behavior on the same fixed sample?

#### C. Short rollout validation
What should be checked in 1-episode or low-cost rollout tests?

#### D. Broader regression validation
What should be checked to avoid breaking other policies or existing code paths?

For each validation level, specify where evidence should be saved:
- `WORKFLOW_ROOT/evidence/round-2/`
- or another explicitly named path if more appropriate

### 6. Success criteria
Define what evidence would count as successful repair of this root cause.

Be explicit about:
- what should improve
- what may still remain imperfect
- what is acceptable at this stage

### 7. Stop-loss rules
Define when to stop and reassess.

Include:
- what evidence would suggest this fix did not address the primary issue
- when to revert
- when to return to diagnosis mode instead of stacking more fixes

### 8. Next-most-likely cause if this repair fails
If this repair does not improve the evidence, identify the next-most-likely root cause and explain what should be checked next.

### 9. Execution guidance for the next prompt
At the end, provide a short “execution handoff” section that tells the next coding/execution prompt:
- which file(s) to read
- which exact step to implement first
- what not to touch
- what validation must happen before step 2

---

## Required chat output

In your chat response, provide only:

1. the path of the repair plan file created
2. the path of the session log file created
3. a concise summary of the confirmed root cause
4. why repair planning is justified now
5. the exact next execution prompt I should run

Do not output only a conversational repair suggestion if the files were not created.

---

## Important constraints

- Do not provide code
- Do not propose broad rewrites
- Repair only one primary root cause first
- Keep changes minimal and testable
- Explicitly avoid mixing multiple uncertain fixes into one iteration

---

## Governing principle

Follow this principle strictly:

**Repair only what the evidence justifies. Leave everything else unchanged until re-evaluated.**