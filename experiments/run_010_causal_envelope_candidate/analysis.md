# run_010 causal-envelope candidate — validation result

## Outcome

`CONFIRMATORY / VALID / TARGET FAIL`.

The unchanged EDS-QD causal-envelope candidate scored `1/10` on the preregistered validation split, versus contemporaneous control `0/10`. It gained task 0 and lost none, but missed the frozen `>=5/10` gate by four successes. The audit has exactly one hard failure: `candidate validation success is below 5/10`. Protocol v11 therefore requires `CONCLUDE_VALIDATION_NO_FORMAL`; formal evaluation is not authorized.

| Profile | Success tasks | Success count | Validation gap to 5 |
| --- | --- | ---: | ---: |
| Control | none | 0/10 | 5 |
| Causal-envelope candidate | 0 | 1/10 | 4 |

Tasks 1–9 failed with the non-causal terminal label `timeout without completion` for the candidate. All ten control tasks had the same terminal label. There were no collision/push/drop/wrong-object composites, qpos execution errors, nonfinite values, action-mask violations, or QD fallbacks.

## Frozen intervention and identity

The only algorithm iteration remained H1 `causal_envelope_v1`: current scored offspring may monotonically expand the target-relative endpoint-XY partition; incumbents and visit counts are deterministically re-binned; reward/fingerprint global-best execution and all other EDS settings remain unchanged.

- Protocol v11 commit: `4b9c72c0eec68538839195a181bd5128b44ab4d7`.
- Validation implementation commit: `838b5550f96dfb9d8dbcf59bfc8052b9e1038350`.
- Code-state: `5446d4fd7a1011fc1c1b96a5cd4d1c7abaa4cc976657a0241e802385c8cf5024`.
- Manifest file/payload/matrix SHA-256: `0b9a19fc648bc7b0cf7291bd003387c01be82a015087b684e2d85007d41acd02` / `242833f405d48d282238e7739ff94e8620c733980be72ea8ad080e3e479916a3` / `a2bd300ffd8fe95be554832d7c6c7b1da2f8c6811a77d4fca70799f40cdaba81`.
- Algorithm/config SHA-256: `qd_ed.py 1516bb75…70b9`, `rdt_policy_steer.py b8806d7a…c1ff2`, `eds_eval_metrics.py d8fb4d04…3429`, `config.yaml b20791a2…daf8`.
- Checkpoint/LIBERO-input aggregates: `a2026bcf…6c28` / `259c469e…38b8`.
- Tracked state was clean at execution; the explicitly protected untracked design remained excluded.

## Execution and accounting

The first invocation at `2026-08-11T01:50:20Z` failed closed before reservation because every GPU 0–7 carried an external compute process. It created no admission artifact, attempt, output root, episode, or GPU-hour. After the external jobs released GPUs 0–5, a completely fresh admission selected:

- GPU 0, UUID `GPU-4c78c923-a68a-8e06-e07b-11bdd642118e`;
- GPU 1, UUID `GPU-053aaa97-5574-46a0-cb86-83d0518d8877`.

Both required snapshots and the immediate dispatch snapshot showed 143,149 MiB free, 0% utilization, and no compute processes on the selected devices. Admission artifact SHA-256 is `e03d1e7f7447e4248faf3cedf2c3498f508ec3ba075af10a86814c7774336eda`.

The exact command was `python scripts/eds_qd_autoresearch_runner.py run-validation --gpus auto --timeout-seconds 28800` at the detached implementation commit, with the user-supplied credential present only in the process environment. IDs 35–54 covered control/candidate × tasks 0–9 × frozen seeds `[41678,829779,856474,666150,876784,652882,288157,522484,262295,200894]`.

- Control: GPU 0, `3140.809 s`, 168 metrics records, 10 videos, exit 0, valid.
- Candidate: GPU 1, `3149.717 s`, 184 metrics records, 10 videos, exit 0, valid.
- Validation device-wall cost: `1.747368 GPU-hours`.
- Cumulative cost including the preserved pre-episode incident: `2.934767 / 48 GPU-hours`.
- Attempt audit: expected/actual effective cells `42/42`, dispatched attempts 42, total reservations 54, PASS.
- Final attempt-ledger SHA-256: `df733b977265495e81e6e09dd081d163de4c6648cee88cc5e21ddc904af6da1a`.

## Mechanism and guardrails

H1's local mechanism prediction remained strongly supported but did not produce task-level generalization:

- resolution improvement median exceeded 0.20 on all 10 tasks (`0.486–0.628`);
- raw initial-bound overflow P95 `0.9375`, post-envelope overflow P95 `0.0`;
- occupied-mode ratios remained above 1 and archive endpoint-spread medians were `0.195–0.226 m` across tasks;
- candidate selection-latency P95 `2.991739 s`, or `1.092159x` the sparse preflight reference, within the `1.25x` gate;
- safety, call/accounting, artifact, and credential gates all passed; the strict run-root credential scan covered 947 files with zero failures.

This rules out the explanation that validation failed because the partition mechanism did not activate, collapsed the archive, violated compute, or caused an audited safety/runtime error. It also shows that improved endpoint partition resolution is not sufficient to predict completion under the current reward-only archive quality and final selection.

## Target-gap analysis and decision

Development evidence was candidate `1/4` on Dev-A and `2/4` on Dev-B, both against `0/4` controls, with gained tasks 9/5/8. None of those gained task IDs replicated on validation; only task 0 succeeded. This is a material development-to-validation magnitude mismatch. Validation candidate `1/10` is one below the historical EDS-QD best `2/10`; the observed validation gap is 4, while the historical formal reference gap remains 3 because formal was not run.

Decision: `REJECT_CAUSAL_ENVELOPE_AS_INSUFFICIENT_AND_CONCLUDE_VALIDATION_NO_FORMAL`. Do not modify this candidate and reuse the exposed validation set, do not run formal, and do not use the validation task outcomes for adjacent parameter tuning. The next action is an outer-loop conclusion/redesign decision under the frozen split-isolation and no-progress rules.

## Immutable evidence

- Validation audit: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_010_causal_envelope_candidate/analysis/validation_audit.json`, mode 0444, size 880,602 bytes, SHA-256 `3f72d025b492e24e7f615db7c3207c4927710794797dd228edf0579ab1290774`.
- Run manifest CSV SHA-256: `ed3f6bbf7179abcaa2f0eddd54208c4744575ad254dd50fd43257b32a7e74de2`.
- Control artifact inventory: 1,560 files / 510,844,647 bytes / aggregate `a5e1a953…289`.
- Candidate artifact inventory: 1,800 files / 539,292,113 bytes / aggregate `e43e034c…e0cf`.

No credential value or reversible credential fingerprint is recorded in this analysis.
