# N3 prospective original-arm budget allocation

This amendment is frozen before any N3 episode dispatch. It replaces only the
unlaunched builder's all-development bookkeeping, not the scientific protocol.

The user execution prompt `docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md`
§1 authorizes autonomous protocol and budget planning within 48 GPU-hours and
240 dispatched episode attempts, while protecting validation/formal resources.
`ARBOR_CONTRACT.md` fixes allocations of baseline20, development100, recovery20,
validation60 and formal40; it does not restrict the baseline allocation to the
initial intake. The existing generic runner explicitly permits `split=dev`
with either baseline or development accounting. N3's protocol fixes all30 Dev
cells, arm order, identities, compute and scientific gates without specifying
an arm-to-budget-bucket mapping.

For this one prospective N3 matrix, apply the same fixed mapping to every task:

| Original arm | Cells | Budget bucket |
| --- | ---: | --- |
| C0 (restored P2 contemporaneous baseline) | 10 | baseline |
| Q0 (sparse reference in development comparison) | 10 | development |
| N3 | 10 | development |

Every explicitly approved infrastructure retry, for any arm, remains recovery;
at most four recoveries and one per scientific cell. C0 is a newly measured
contemporaneous baseline under the common frozen source/observer/runtime. It
is not pooled with old outcomes. Selection of this complete arm is prospective
and independent of task outcomes; no per-task or post-outcome bucket switch is
allowed. All original rows retain `split=dev` and the exposed Dev seed block.

The prelaunch snapshot has baseline1, development72, recovery6 and zero
validation/formal dispatches (79 total). Completion with all four allowed
recoveries would give baseline11, development92, recovery10 and 113 total.
These are capacity calculations, not reservations or a guarantee: admission
must recheck the authoritative journal under the real shared runner lease.
The original20/100/20 bucket caps, global48h/240, N3's8h/34 and protected
validation/formal24h/100 remain unchanged. Every healthcheck costs GPU time
without becoming an episode attempt. No reserved evaluation resource is lent.

Preserve the old unlaunched plan (SHA
`c8ce99d952447e8dd5e1542aad30dd801f4eb5ec4b66a95cb805a6b87340cff4`)
as superseded before dispatch. Freeze a new source/plan path, this amendment
hash, and the exact mapping in the new N3 resource identity. Do not relabel any
historical event, alter state bucket caps, rewrite costs, change candidate
formula/profile bytes, or continue a partially dispatched cohort under a new
allocation. This document authorizes no GPU execution by itself.
