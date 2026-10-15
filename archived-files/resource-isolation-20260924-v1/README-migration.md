# One-time private resource migration

Status: prepared and CPU tested; **not executed by the executor**. This file does
not authorize GPU work. The exact new user authorization is `authorization.json`
SHA `4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47`.

Frozen script SHA:
`296e9ec22313c031d1f838cb5d6f4e081a5cc419974cbcb307beb5753b5d4ff9`.
Fixture tests SHA:
`eff5abe1fcdfd3d1cd87e8c503a0532458c36a8982b8d93b691001b5ead1c1da`.
18 CPU fixtures pass, including a genuine temporary subprocess holding a
fixture flock (no worktree resource lock or GPU is used by that test).
`cpu-validation.json` also records a read-only current-resource preflight:
207 immutable file fingerprints and both HEADs match; the real migration helper
holds the old W runner lease; the virtual owner partitions and new states pass.
No migration, archive creation, resource-file replacement or GPU work was done.

The root may execute exactly once, after independent review:

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3 \
  /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/resource-isolation-20260924-v1/migrate-private-resources.py \
  --execute-reviewed \
  --expected-script-sha256 296e9ec22313c031d1f838cb5d6f4e081a5cc419974cbcb307beb5753b5d4ff9
```

The script requires the reviewed independent drain helper to remain alive with
the old W runner flock: PID/boot/start ticks, `/proc/locks` PID and device/inode,
and a separately opened lock's inability to acquire all agree. The prior queue
must be dead (or a reaped-work zombie), every episode and health group terminal,
and the reservation ledger exactly empty. No process is signalled or launched.

It archives exact shared journal bytes, both original states, X's five original
symlink mappings and lease/process metadata. Whole groups are assigned by
stable `output_dir` ancestry, never GPU number or the common run-name prefix.
Every original line keeps its bytes and order. Group/line SHA records prove the
partition; Decimal duration sums prove exact-once cost accounting. The old
cross-owner C0 recovery chain remains linked via the immutable shared archive;
its foreign parent is not copied into another chargeable ledger.

W keeps the original runner/state lock inodes. X replaces its five shared links
with three owner-only journal files and two new local locks. Both state views
are recomputed from their private histories; W has 240/48 and original caps,
X retains 250/48, exact N1W caps and frozen N1W authorization. Both keep 14/10
protected GPU hours, their singleton GPU selection, and the actual
`max_concurrent_gpu_workers=1` field. Prior shared authority text is archived or
explicitly made historical; the latest user instruction supplies the new
private-budget authority. No previous cost or task result is reclassified.

All destination files are prepared and fsynced before a durable
`migration-prepared.json`. Replacement is atomic **per file**, under the old
state lock and the independently held old runner lease; it is not a filesystem
transaction spanning all files. Every applied replacement has a durable
progress record. Source HEADs, frozen source/plan/profile/runtime/input metadata,
W resource pointer/contract and X N1W authorization are checked before and after.

On success, `migration.json` records `MIGRATED_PENDING_VALIDATION`. The script
does not set ACTIVE, create a new execution release, launch either queue, or
release the old migration lease. Root must independently check:

- Exact owner partition/conservation and archived source SHA; the foreign retry
  reference remains accessible without duplicate charging.
- Private journal counters equal each state's budget/runner counters, no
  episode/health is unfinished, reservation ledgers remain empty, and all
  required readiness proof IDs remain with their owner.
- W old lock identities unchanged, X locks local/different, no surviving shared
  writable links, owner-only modes, correct singleton GPUs/worker field/caps.
- All frozen identities and the two completed N4 control records unchanged;
  current plans and source heads still validate. Any original full model-byte
  admission verification is still required by the runners themselves.

Only then may root record ACTIVE, write the helper's separately validated lease
release, and resume the exact pending keys through the original supervisors.
`MIGRATED_PENDING_VALIDATION` is a coordination marker; the old frozen runners do
not implement a new status gate. Both coordinators must honor the explicit
DRAINING/PENDING instructions until root acceptance; do not infer automatic
permission from newly available private lock files.

If a failure occurs after replacements start, `migration-partial.json` records
which destinations changed and the exception type. Keep the drain helper/old
lease held, stop admission and review archive/progress/staged files manually.
An earlier preparation failure changes no destination, but may leave archive or
staged artifacts; those also require review. The script refuses rerun once an
archive/prepared/final/partial marker exists. No automatic rollback or retry is
provided, and the script never rewrites an old episode result.
