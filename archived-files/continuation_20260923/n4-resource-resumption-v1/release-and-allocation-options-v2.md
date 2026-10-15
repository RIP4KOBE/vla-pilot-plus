# N4 resource release and prospective allocation options

**03:34:10 UTC resource-only finding: the shared lease is released and all
recorded costs are terminal; allocation authority still needs an explicit
consistent prospective record.** This update preserves the earlier review as
a time-specific observation. It does not implement either option or authorize
GPU execution, plan freezing, protocol changes or external intervention.

## Verified resource state

`resource-release-v2.json` pins the exact journal byte snapshots while retaining
only resource fields: event transitions, attempt/resource identifiers used for
grouping, buckets and GPU durations. No success, outcome_valid, failure reason,
metrics or scientific payload was inspected or serialized. It reports:

- 112 dispatched, no unfinished episode or healthcheck group;
- baseline11/development94/recovery7, validation0/formal0;
- 15.739958095529593 settled GPU-hours including0.2602564145160282 healthcheck hours;
- PID2922757 absent and no matching `/proc/locks` entry for the same device2051,
 inode27280417 shared runner lock; no lock acquisition was attempted;
- resource lease log ends with `shared_cohort_lock_releasing` at03:28:17 UTC.

The known authorization, cohort manifest and W coordination document have
unchanged hashes. The coordination document still says launched/priority N1U;
no new release-of-priority or cap rollback record was found at those known
coordination locations. The external lease is no longer held, but that fact
alone does not revise the recorded11/122/60/40/7 allocation. W source/state
still retain20/100/60/40/20. This review establishes no explanation for why the
external queue ended and uses no external scientific outcome.

## Two concrete slot options, same12 scientific cells

Both options retain tasks0,3,6,9 in the frozen task-major C0/Q0/N4 order, all
seeds/init/algorithm/controls and aggregate2/4>=controls gate. A budget bucket
is not a change of arm or scientific split. Historical records stay unchanged.

| Prospective choice | Original-row allocation | After12 originals | Recovery capacity |
| --- | --- | --- | --- |
| A: explicitly restore original20/100/60/40/20 caps |6 baseline+6 development|baseline17,development100,recovery7,total124|at most4 permitted N4 recoveries fit; thenrecovery11,total128|
| B: explicitly retain approved11/122/60/40/7 caps |all12 development|baseline11,development106,recovery7,total124|zero; any required recovery cannot dispatch|

For A, baseline rows are the four original C0 controls and the first two Q0
controls in the pre-existing order (tasks0 and3). Development contains Q0 tasks6
and9 plus all four N4 candidate rows. This is the minimum two-Q0 reassignment
needed with only six development slots left under the original cap; no
candidate is relabeled baseline. Restoring caps means reversing the unused
baseline9/recovery13 transfer from development and must be stated explicitly.
It is not valid to rely on W having accidentally retained those older numbers.

For B, control roles remain C0/Q0 even though their expense is charged to
development, which the generic Dev split/bucket interface permits. All12 fit
within the28 presently unused development slots. The N4 upper bound16 and
at-most-four recovery allowance do not create recovery slots: under this option
actual new episode dispatches can be at most12 and an infrastructure-invalid
cell cannot be replaced. Freeze this resource limitation before execution;
never quietly treat it as a fallback after a failure. If four recovery slots
must also be funded, a separately explicit minimal transfer of four unused
development slots to recovery would yield11/118/60/40/11; this is an arithmetic
alternative only, not an approved amendment or implementation.

Both funded-original options leave100 protected original evaluation slots
untouched and retain240 total slots. Both need a clear cross-session release
or reassignment of the external cohort's unused priority allocation; process
absence is evidence of availability now, not evidence of revocation or a
promise that another queue will not be launched.

## Hours and admission

Remaining unprotected hours are48-24-15.739958095529593 =
**8.260041904470407h**. The old N4 local8.5h cap can only operate as a ceiling
subject to the smaller live global allowance, not a promise of8.5 funded hours.
Twelve full1800+40-second windows consume6.133333333333333h, leaving
7656.150856093467 seconds. Sixteen such windows consume8.177777777777777h,
leaving only296.150856093467 seconds for all newly associated health work at
this snapshot. Existing proof reuse must retain its identity checks and not
charge prior costs again. New external dispatch/health cost reduces this
headroom immediately. Every future admission must preserve the full1800s
scientific timeout plus40s cleanup; no clipping to fit the remainder.

## Remove source/state ambiguity before any dispatch

1. Record one prospective resource decision with predecessor authorization SHA,
   resource-only terminal/lease snapshot, new holder/priority scope, selected
   exact bucket mapping and effective caps. Explicitly state whether the
   external cohort's remaining allocation is released, retained or reassigned.
   Keep previous authorization and all journal records intact.
2. Bind that policy to the next plan/protocol/source inventory and use matching
   authoritative state caps and source caps in every active dispatch route.
   A stale worktree must fail policy-identity checks rather than supply an
   alternative maximum. Do not alter or resume another session's frozen queue.
   A prospective new source revision, not an edit to old frozen artifacts, is
   the place for any authorized enforcement change.
3. Under the actual shared runner lease, refresh the full journals and verify
   no unfinished resource, whole-original-matrix slot capacity, own recovery
   capacity if promised, protected60+40 and14+10h, global240/48 and local limits.
   Freeze and launch only through the reviewed dedicated GPU3 supervisor.

The latest instruction to continue authorizes continued work; it does not by
itself numerically specify whether the separately recorded transfer is being
reversed. The root must decide whether existing user direction already covers
a selected resource/priority amendment or a concrete resource decision must be
obtained. This review does not add an approval requirement to ordinary CPU
preparation or finite preregistered source reading. An explicit consistent
allocation record is required in either case; silent cap rollback is not.

No cap, protocol, plan, source, state, ledger, external process or GPU was changed.
The only new files are this memo and the companion resource metadata evidence
in the independent R3 review directory. No new tests or scientific execution.
