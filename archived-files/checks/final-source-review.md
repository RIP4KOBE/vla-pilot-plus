# Frozen steering source review

Reviewed 2026-10-13 UTC. Scientific source: `33954ead452927fc3168efb610487a688f89169e`.
Scope: launcher/worker lifetime, frozen provenance, RNG restoration, Stage control, mode separation, and archive portability. No runtime, configuration, model/cache, local-config, or raw-run files were changed. No GPU/model API/simulator calls or full test-suite reruns were made.

Two actionable integration findings were confirmed. Neither is evidence that the three currently running cohorts are scientifically invalid. No additional blocking defect was found in the inspected RNG/Stage/mode paths. This is a focused review, not proof of absence of defects or final cohort acceptance.

## P2 — Launcher termination strands the worker and drops its lock

- `scripts/run_steering.py:48–49` holds the GPU flock only in the launcher.
- `scripts/run_steering.py:103–104` starts the worker without an inherited lock or a managed worker lifetime.
- `scripts/run_steering.py:110–127` has no `try/finally`/signal finalization surrounding monitoring. Final status and audit are written only on the normal polling exit path.

Trigger: terminate the launcher PID alone (for example, a supervising job runner sends SIGTERM to the command it launched). The child remains alive, the launcher's file descriptor closes and releases the GPU lock, and `status.json` remains `running`; no final audit is produced. This is a real interruption/recovery defect, not a false-validity path: the current auditor requires a finished/exited status and exit code zero. The GPU memory check often prevents a second busy launch, but does not preserve ownership or finalize the orphaned run.

The CPU repro executes the actual frozen `run()` function, stubbing only configuration/assets/GPU queries and substituting an owned Python sleep child for the scientific worker. SIGTERM is sent only to this synthetic launcher; its surviving sleep child is then cleaned up. Result: launcher exit `-15`, child alive, GPU lock acquirable, status still `running`, no audit. No real launcher/worker receives a signal.

Recommended post-cohort change: define explicit cancellation semantics, retain lock ownership until owned workers have exited, supervise/reap the worker and its owned provider descendants, and always record an interrupted/failed terminal status on handled termination. Alternatively require and provide an external durable supervisor with equivalent ownership/finalization guarantees. Do not represent an orphaned worker's eventual files as a normally audited completed run without explicit recovery evidence.

Current-run scope: a read-only host `/proc` inspection confirmed all three launchers and workers alive, with no controlling TTY and one detached session per launcher:

| Method | Launcher PID / SID / PGID | Worker PID | Worker SID / PGID |
|---|---|---|---|
| EDS | 98936 / 98936 / 98936 | 103967 | 98936 / 98936 |
| VLS | 96745 / 96745 / 96745 | 97978 | 96745 / 96745 |
| EDS+QD | 96870 / 96870 / 96870 | 98765 | 96870 / 96870 |

The initial sandbox PID namespace could not see these host PIDs; that absence was not treated as process death. The separate host read established the table above. At approximately 13:33 UTC all three persisted `state=running`, zero recorded episode errors, task 0, progressing steps 432 / 520 / 432 respectively. These are live-prefix observations only.

## P2 — Complete archive re-auditing is tied to original machine paths

Three dependencies prevent a run directory by itself from being a portable offline audit bundle:

1. `scripts/audit_steering.py:69` reconstructs `hydra.run.dir` from the archive's **present** folder. `:378` then requires byte-level configuration values to equal the frozen resolved config, whose output path records the original execution directory. Moving an unchanged archive to another parent is rejected. Renaming the archive additionally changes reconstructed `job_id` at `:62` and metric binding at `:407`.
2. `scripts/audit_steering_contract.py:129–146`, specifically `:139`, reads the task-map file from `environment.json`'s original absolute `libero.root`. It verifies the bytes against the frozen asset manifest, but cannot use an equivalent verified task map at a different location.
3. `scripts/audit_steering.py:339–340` reads the RNG fixture manifest from the auditor's **current checkout** rather than the original recorded/hashed fixture manifest. A new checkout without that fixture or with a later fixture cannot independently re-audit the old run from the run archive alone.

The minimal CPU relocation repro uses the actual frozen `protocol_config` function extracted by AST, the actual immutable EDS common-run manifest/config, and copied frozen profile YAMLs. The original path compares equal. A same-basename archive under `/tmp` compares unequal, and replacing only the reconstructed `hydra` field restores equality. No live evidence was modified, and no full completed-cohort claim was made from this prefix.

This requires an audit/archive interface fix, **not a change to policy, Stage, simulator, or scientific runtime**. A minimal external archive adapter can preserve the original configuration as execution provenance, validate its original output root against a hash-bound receipt, and supply explicit original-root → archive-root bindings solely for finding saved files. Preserve original `job_id` when checking metric rows. Include a hash-checked task-map and RNG-manifest sidecar (the latter must match the config's pinned manifest SHA); do not rewrite frozen configuration or manifests to new absolute paths. Avoid unrestricted basename searches or silently trusting whichever current checkout asset is available.

Other existing handling is already useful: `evaluation_directory` rejects absolute/traversal paths and symlink escapes; target-marker raw image lookup has a run-relative fallback (`scripts/audit_steering_contract.py:437–441`) and verifies both PNG and decoded-RGB hashes. The scope above is therefore narrower than a general failure of all archive lookup.

## Valid post-cohort re-audit procedure

An audit-only commit made **after all frozen cohorts finish** can validly re-audit preserved snapshots. Record the original tested commit and source/config/environment digests separately from the new auditor commit/source SHA and invocation. Preserve original manifests, raw streams, images, videos, status, and original audit; emit a new sidecar report. Validate the saved `source/` tree against the original manifest, not against a new checkout's scientific source. Include and hash any auxiliary archived task-map/RNG-manifest and the explicit path-binding receipt.

A path-resolution correction does not itself change the scientific stimulus or action-generation code. The run remains a `33954ea` experiment; it must never be relabeled as an experiment performed with the later audit commit. A changed scientific gate must be disclosed and justified separately. Do not loosen numeric or mechanism criteria because an observed result failed, and do not edit frozen source merely to make the original runtime-source check match a later checkout.

## Scientific fidelity observations

- Worker pre-start source/config verification is explicit (`scripts/steering_worker.py:20–22`); v2 additionally verifies the copied local config and active LIBERO path binding (`:23–31`). Launcher end-of-run source-set/hash comparison and archive source-copy checks are present (`scripts/run_steering.py:117–125`; `scripts/audit_steering.py:338`). Runtime vendor revisions/cleanliness and model bytes are checked by preflight; these are not a full hash of every dependency file or an in-memory attestation throughout the run.
- RNG hooks restore only the declared prepare and rollout phases, verify manifest/hash/task/seed/phase, confine fixture paths, and compare resulting state signatures (`core/episode_rng_hooks.py:26–40,56–76`; `core/episode_rng_fixture.py:52–71`). CUDA stream-count mismatch fails instead of silently remapping. Hook installation is one-time and default configuration performs no RNG capture/restore.
- VLS gradient capability probing is restricted to VLS (`core/stage_evidence.py:290–298`); it preserves Python/NumPy/CPU Torch state (`:214–247`) and uses CPU inputs. It is local capability evidence, not a guarantee about every possible trajectory or an arbitrary generated function with explicit external side effects.
- Stage reward is consumed only when the previous chunk was guided (`core/stage_evidence.py:254–264`). Semantic-stage changes reset the reference; guidance-only toggles preserve it under the frozen profile and clear EDS chunk memory (`:389–398`). `RDTSteer.get_stage_reward()` uses a separate VLS final-selected-candidate progress value and retains the EDS normalized reward path (`core/rdt_policy_steer.py:1412–1421`). No additional RNG/math change was found in these reviewed paths.
- Mode profiles are explicit. VLS uses its dedicated route, while EDS and EDS+QD share EDS guidance with archive-off/on profiles. The wrapper cross-checks mode/config and rejects mixed metric streams; per-chunk mechanism evidence is bound to Stage task/episode/step identities (`scripts/audit_steering.py:385–429`). Independent live QD/VLS mechanism review is being handled separately, so it was not duplicated here.
- Independent initial EDS comparison already saved as `checks/eds-common-initial-comparison.json`: both RNG restores matched migration; first reward image/prompt and Stage identity image/prompt matched; first two EDS pretest traces matched all 258 tensor leaves; first 104 completed actions matched exactly. The first observation prompt legitimately differs in fresh identity-response wording. This supports migration fidelity for that prefix only.

## Historical-name comment

`core/codex_stage_policy.py:48–49` still mentions an older CLI version and the historical `N1V` runner in a comment. It does not change executable behavior or the CLI version recorded in environment evidence. It is a naming-policy/documentation cleanup, not an experiment-invalidating issue. Leave the frozen live source unchanged; after all cohorts finish a comment-only cleanup can use neutral wording and identify the provenance exception in README. Preserve already-hashed historical fixture blobs and their original source identity rather than silently rewriting archive bytes. The parent's note that a mirrored fixture blob contains this comment was not independently re-expanded in this review.

## Reproduction artifacts and limitations

- `checks/final-source-review-repros.json`, SHA-256 `f0554d47e89abf08462ca21243e6b02c167768984499c38a411bde49184d93f2`.
- `/tmp/steering-final-review-repro.py`, SHA-256 `8a4bf5a4c135cbc667242f1f5732e7f93e6f7796ce2dfcbfabffc3f5b3e36bc3`; preserved copy beside this report.
- Command: `CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python /tmp/steering-final-review-repro.py --output .worktrees/exp/steering-integration/checks/final-source-review-repros.json`.
- The first helper attempt had an incomplete subprocess stub (`STDOUT` absent), failed before spawning the synthetic worker, and wrote no report. After correcting the helper only, the recorded command exited 0. No repository code was patched.
- Reviewed file SHA-256: `scripts/run_steering.py` = `f00e946a7596ade61b782a33734f95e446f6e447fbc56d34b4adc409a115d5d7`; `scripts/audit_steering.py` = `e213b8684a25460f731e2cb0e287adfeff3731464526ea694805d3b6d6759d9d`; `scripts/audit_steering_contract.py` = `5297fd8f74640adb700d19aadf66e8cd2e5e760b56ce4c5c671b1d257f0a0290`.

The review did not repeat full CPU tests, run GPU probes, send provider requests, terminate live workers, or assess final success rates. Final cohort validity remains pending complete task/contract/method evidence and original frozen-source checks.

## Follow-up: isolated fixes prepared, not applied

At the parent's request, reviewer-ready changes now exist under `checks/post-cohort-fixes/`. See its `README.md`, `post-cohort-fixes.patch`, and `validation.json`. Thirty new CPU regressions and 140 existing runner/offline-contract tests passed against the external candidate. The three public modes' resolved scientific configurations remained equal to the frozen baseline, apart from the external staging copy's installation-root paths. All 113 frozen root-source files still match; no patch has been applied to root.

Independent review exposed an additional aspect of the archive finding: the original `scripts/audit_steering_contract.py:437–439` prefers the old absolute PNG while it exists. Thus a copied archive missing a raw frame can borrow the original machine's frame instead of proving self-containment. The staged fix always selects and hashes the archive-relative episode/step frame; missing, corrupt, and escaping-symlink frames fail even if the original file still exists. This does not indicate incorrect PNG selection in the unchanged live run.

Independent review also caught and closed an output-directory ownership race in the first proposed lifecycle implementation. The final staged launcher claims its new directory before entering any status-writing lifecycle, and the losing claimant's negative test proves the winner's status remains unchanged. These were candidate-review corrections, not changes to live frozen source.

Final proposal patch SHA-256: `a0727612e7d9faf89caa402cc19bb6dba23b9b1db24f71787e97b4413afe41d5`. Final validation receipt SHA-256: `c0512c82a10549c993e35be392b374c9c3f7702c2f28aff3add8114b18653626`. Both proposed patches pass `git apply --check`; application is deferred until all cohorts finish.
