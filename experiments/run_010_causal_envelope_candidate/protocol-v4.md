# `run_010_causal_envelope_candidate` Exact-Gitlink Import-Recovery Protocol v4

Date: 2026-08-11 UTC

Parent scientific protocol: `experiments/run_010_causal_envelope_candidate/protocol.md`, commit `1017bf0212780b2e386764517661cf9970090f8d`

Prior recovery protocol: `experiments/run_010_causal_envelope_candidate/protocol-v3.md`, commit `b344dc850e8d63b2a78438d64d152693e8f7789f`

Frozen scientific execution revision: `d018f8acb12263d81c65f8eb717f9c987459e991`; code-state SHA-256 `3626b52b619d6c951aee48f07c206ce5af44dff8cf12fad40d85ab01c9a9839c`.

Scope: one final six-cell recovery from a deterministic pre-episode RDT git-submodule initialization failure. This amendment supersedes v3's no-third-dispatch stop only for the exact gitlink repair below. It changes no EDS+QD or non-EDS+QD algorithm source, config, task, seed, checkpoint, immutable run manifest, metric, threshold, promotion rule, or formal authorization.

## Observed v3 recovery outcome

The replacement credential passed the pre-reservation Poe health check. Fresh two-snapshot admission selected idle GPUs 0, 1, and 2, then exact-cell recovery attempts 7–12 were reserved and dispatched. All three profile workers independently:

1. started Hydra and the LIBERO adapter;
2. built the frozen task 3 and task 5 environments;
3. resolved the frozen checkpoint path;
4. failed before model construction, episode initialization, reset, action inference, or task observation with `ModuleNotFoundError: No module named 'scripts.maniskill_model'` and the wrapper `ImportError` instructing `git submodule update --init`.

There are zero `results.txt`, video, metrics JSONL, qualitative/mechanism records, episode metadata, stage queries, or task outcomes in all three jobs. Therefore IDs 7–12 are `pre_episode_import_infrastructure`, not policy/task/mechanism results.

Evidence frozen at protocol lock:

- attempt ledger SHA-256 `3702dbc95318685d2e52fcf55e64debe282f7d7f8c589c68a628ae65cacefd3d`;
- recovery GPU admission SHA-256 `70a087481b05263b0946fe0d0de95b58ac2906e56fab119b8a2e4a4f6abb9ed4`;
- phase CSV SHA-256 `d5f2c5e77aed910f8c33809c2e8e475d40d3d78f7719128ad08a4c98cffc05c6`;
- control / sparse / candidate output-tree aggregate SHA-256 values `ad1c60f9c31c98063d92427deda8815f25d157765bcb24cd5bf7df00773fa953`, `bb55001dd70966cc56211bde7222cf9ef79f83bbf5d77cafae90c2f32eef096a`, and `e99a1a409b008c791b2e23de85b6c71536da34a039c5fb4ccc9ad3908a941132`;
- control / sparse / candidate runner-log SHA-256 values `dc00a9b799efe37b8ad47adee239c2e637df763726c91601d19b145b44dc5406`, `f8a4a2c37173f2332dbf0018e00ef708cadf17c27ecb1c4b2c4b7f364618e83c`, and `c613484861d4a9537274b0d225ffd900a720a8d4da9330d5ccb81412f362133e`;
- all three job wall times were 28.174–28.478 seconds; summed admitted-device wall is 84.939 seconds = 0.023594 GPU-hours;
- exact-secret scan of the owned artifact root found no supplied credential bytes.

## Root cause and exact repair

The parent repository pins `third_party/rdt` as gitlink `b896f4dcac8ed1c3fae4a056200db267607f131f`. In this worktree, `git submodule status` reports the same hash with leading `-`, meaning the gitlink is uninitialized and the directory is empty. The read-only baseline worktree has that exact gitlink initialized, contains `third_party/rdt/scripts/maniskill_model.py`, and is clean at the same submodule commit. The missing module is therefore a worktree bootstrap omission, not a source-version or algorithm difference.

Only this repair is authorized:

```bash
git submodule update --init --checkout third_party/rdt
```

It must materialize exactly gitlink `b896f4dcac8ed1c3fae4a056200db267607f131f` inside the current worktree. No submodule file may be edited; no other submodule may be initialized; the baseline or root worktree may not be written.

Before any new reservation, all of the following must pass:

1. parent worktree has no tracked diff and still excludes the protected untracked stage-guidance design;
2. `git submodule status third_party/rdt` is exactly the pinned hash without `+` or `-`, and the submodule worktree is clean;
3. the RDT gitlink and frozen parent HEAD reproduce code-state `3626b52b619d6c951aee48f07c206ce5af44dff8cf12fad40d85ab01c9a9839c` when checked at the scientific revision;
4. a `vla-pilot` import-closure probe can import `scripts.maniskill_model.create_model` and its RDT model dependencies from this exact submodule;
5. immutable manifest, checkpoint, LIBERO inputs, runtime cache, pause/storage, and credential-redaction checks still pass;
6. Poe health check passes before GPU admission and reservation.

## Artifact preservation and final recovery

After this protocol commit and before new output creation:

1. append `dispatch_aborted_pre_episode` for IDs 7–12 with the evidence hashes and `pre_episode_import_infrastructure` classification;
2. move, never delete or overwrite, the three output trees, three runner logs, and phase CSV into an owned `stale/pre_episode_import_failure_<timestamp>/` archive;
3. freeze an archive manifest containing original/destination paths, sizes, SHA-256/tree hashes, v3/v4 protocol commits, attempts 7–12, zero-episode proof, and a credential scan result;
4. rerun dynamic two-snapshot and immediate GPU admission; do not reuse the prior GPU decision or co-locate with external compute;
5. reserve attempts 13–18 for the exact same six cells, each with `recovery_of_attempt_id=7..12`, then dispatch only after all identity assertions pass;
6. execute the unchanged frozen `max_chunks=2` jobs and audit with the original mechanism-preflight gates.

This consumes 12 of the globally authorized 15 same-cell recovery slots across IDs 7–18 and remains below the 143-attempt / 48-GPU-hour caps. The remaining three recovery slots cannot cover the six-cell matrix, so v4 authorizes no further mechanism-preflight retry. Any subsequent pre-episode failure stops this candidate; any initialized policy outcome is never retried.

## Target impact and promotion boundary

Historical EDS-QD best remains `2/10`; target gap remains 3. The import failure supplies no algorithm direction and cannot be used to tune the candidate. A valid recovered mechanism preflight may authorize only the already-frozen Dev-A. Dev-B, validation, and formal evaluation remain unauthorized until their own protocol/result gates.
