# Offline steering contract fixture

This fixture is a cropped real evidence prefix used only for CPU audit regression.
It is **not a completed episode, cohort acceptance, online result, or model cache**.
It must never be used as an online reply, policy, or reward cache.

The exact source run, code commit and all source/file hashes are in `provenance.json`
and `files.json`. The self-contained blob store needs no source worktree, run directory,
model weights, simulator, provider login, GPU, or network connection.

Retained evidence: task 0, episode 0, seed 44; queries at steps 0 and 32; three Stage
captures (identity plus two observations); one fresh reward capture; actions 0–39;
matching adapter enter/exit rows; two original unmarked PNG frames; initial image,
marked current images, exact prompts, replies, generated reward functions and the
saved 64-probe reward-contract result. Fourteen frozen implementation/template files
and the asset manifest/task-map file are read strictly as bytes or AST literals.
Saved reward code is never executed. PNG dimensions and bytes are unchanged.

`files.json` maps logical run paths to SHA-256-named blobs. Equal bytes (for example
repeated public policies and the reward input PNG) share a blob. The source hashes
and exact selected JSONL line numbers explain every retained/cropped artifact.

Test materialization changes only local references and their environment-manifest
hash. The real prefix has synthetic `running` status and no episode-compute receipt.
A separate **explicitly synthetic completed-prefix variant** sets exited status and
sums the four retained request counters to exercise completed-task auditing. It does
not invent model/EDS compute or claim the real episode completed after 40 actions.
Completion-only tests must retain that distinction in their names and assertions.

Recommended destination: `tests/fixtures/steering_contract/`, with helpers and tests
resolving this directory relative to `__file__`. Do not copy the extraction builder
into normal tests: it intentionally records a historical source path and is only a
provenance tool. No missing-path skip is required or acceptable.
