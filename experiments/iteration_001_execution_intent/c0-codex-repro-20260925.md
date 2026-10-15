# C0 Codex-condition source reproduction, 2026-09-25

## Question and interpretation

The user authorized two C0-only ten-task cohorts on physical GPU2: first the
historical QD-era source, then the current GPU2-study source. Both use one
identical, frozen Codex Stage condition. The observed historical
Gemini/Poe C0 result was 3/10 (tasks 3, 8, 9). Poe is unavailable, so neither
new cohort can be called an exact reproduction of that historical provider
condition. The paired new cohorts test the old-vs-current source under the
same reachable Stage condition. Report their absolute scores, task-level
outcomes, Stage decisions, failures, and environment gaps separately.

## Frozen scientific inputs

- Suite: `libero_object_swap`, tasks 0 through 9 in historical order, strict
  perturbations, one sequential ten-episode process per source, `seed=0`,
  episode environment seeds `[44,235,43,546,6,621,197,87,151,548]`,
  initialization row 0, 720 environment steps, eight actions per chunk.
- C0 is `p2_stage_on_abs_rbf_control`: RDT Object EMA, EDS population 16,
  ten iterations, non-CEM, temperature 0.1, renoise 3-to-1, absolute-EEF
  initial RBF scale 20/start 0.8 and rollout RBF scale 20/start 0.6 at all
  iterations, `qd_archive_mode=none`, Stage ON, grounding OFF, reward normal.
  All remaining command overrides come from the immutable historical C0
  `job_manifest.json`, not an approximation of its fields.
- Reuse the exact six source guidance-cache files from the historical runner's
  `RUNTIME_CACHE_SOURCE`, copied to an owned directory and SHA-256 checked.
  This cache mentions an alphabet-soup can and has a known task-identity
  concern; retaining it is required for this source-condition comparison.
- Use the same historical LIBERO config bytes and checkpoint/encoder paths in
  both cohorts. Output paths and physical CUDA/EGL IDs are operational changes.

## Common Codex Stage condition

- Managed ChatGPT login through installed Codex CLI, `gpt-6-astra`, low
  reasoning, two original PNG images in original order, unchanged Stage
  template. Identical `core/gemini_grounder.py`, `core/codex_stage.py`, and
  `core/codex_stage_policy.py` transport bytes in both source trees.
- JSON-schema output normalized through the legacy Stage parser; completed
  known startup warnings policy v5; no extra tool, skill, plugin, or web use.
  Per-call application timeout 180 seconds. Both use historical trigger
  semantics, 50-query limit, and zero minimum query gap. The Codex output
  format and model necessarily differ from historical Gemini/Poe.
- A complete schema reply with complete usage is required. A Stage error is
  invalid infrastructure, never a scientific task failure. The historical
  main has a minimal Codex-only fail-closed adapter; RDT/ED policy code remains
  the historical commit. No legacy result is rewritten.

## Versions, order, resources, stopping

- Historical policy base: `53187e6ea8b69e9f830c10be0bc25757db5d2794`,
  in the existing `.worktrees/exp/eds-quality-diversity` worktree on branch
  `exp/c0-codex-historical-20260925` with only the transport compatibility
  overlay and event/fail-closed wiring. Current policy base:
  `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc`, in the existing GPU2
  `.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z` worktree.
- First run all ten historical-source C0 episodes. Then run all ten
  current-source C0 episodes with the same inputs and common Stage condition.
  Use a single GPU2 worker; no QD candidate, Q0, validation, or formal run.
- Maximum 20 primary episodes. No valid scientific failure is retried. Any
  invalid run stops for diagnosis; repairs require a new frozen version and
  preserve old bytes. Do not consume protected validation/formal slots or
  hours. The existing study limit remains 250 attempts/48 GPU hours. Of the
  118 previously charged attempts and 12.4873426769 GPU hours, 100 attempts
  and 24 hours are protected for validation/formal. Thus this task may consume
  at most 20 additional primary attempts and at most 11.5126573231 GPU hours
  without a new authorization. A watchdog stops the queue before that limit.
- Freeze source, input, checkpoint, runtime, CLI and plan hashes before GPU
  dispatch. Preserve all original C0 artifacts. Only the owning study's
  worktree, GPU2, and artifact root may be modified. Existing AGENTS.md
  resource-isolation rules apply.

## Evidence and decision

Report each 10-task success count, task IDs, validity, Stage call count and
decisions, guidance-active chunks, exception/timeout counts, and total cost.
Compare historical-source vs current-source task by task and explain online
Stage variability. A `3/10` under Codex does not prove the original Poe
environment has been restored; source parity under the reachable condition
requires both cohorts and input/config hashes to pass. Do not restart QD
algorithm experiments solely from an absolute Codex C0 score.
