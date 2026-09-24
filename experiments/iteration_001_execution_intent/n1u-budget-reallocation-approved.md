# Approved N1U attempt reallocation — 2026-09-24

The user explicitly approved the documented transfer and GPU2 launch:
“批准调拨并启动 GPU2 N1U（建议）”. This supersedes the pending-approval status
in `n1u-budget-reallocation-proposal.md`; preserve that proposal as reviewed.

At authorization verification the shared journal still has110 dispatched:
baseline11, development92, recovery7, validation0, formal0;15.441015923040702
GPU hours consumed, zero workers/probes in flight. N1U has zero reservations
and zero dispatches. The prior capacity-only queue failed without GPU work.

Transfer the remaining baseline9 and recovery13 attempts to development:
new caps baseline11, development122, validation60, formal40, recovery7.
The sum remains240, and the global48 GPU-hour limit is unchanged. Retain
validation14 and formal10 reserved GPU hours; current unprotected time is
8.558984076959298 hours. There are no remaining baseline/recovery attempts.
All historical events, validity classifications, outcomes and costs remain
unchanged. The existing runner must enforce the minimum of the committed
source cap and recorded state cap; the old100 state cannot silently activate122.

This is a resource amendment to the same never-dispatched N1U cohort, not a
scientific restart. Retain all30 exact episode rows, seeds, order, profiles,
task inputs and original Stage180s condition. Copy the frozen plan to a new
administrative revision bound to the new source and this authorization;
preserve the original plan and resource files. Reuse the unchanged runtime
manifest and current-boot CUDA/EGL evidence when their checks pass.

Only GPU2/EGL1, one shared worker,120-second stable idle admission. Hold the
shared runner lease across the cohort; recheck full30 development capacity
under that lease before dispatch. Pause any competing remaining GPU3 queue
at a clean episode boundary if one appears, as already authorized by the user.

Execute all20 valid C0/Q0 controls before N1's10 cells. Any invalid outcome
or infrastructure failure closes this final cohort incomplete; no automatic
retries or replacement cohorts. Legal task failures continue. All original
mechanism, validation and formal gates stay in force. No pooling with N1R,
N1S, N1T, or the other worktree's N2/N3 conditions. Formal target remains
unachieved until independently demonstrated.

CPU checks cover exactly30 newly admissible development cells from the
authorized snapshot, rejection of a31st, exhaustion of both donor buckets,
rejection of state-only cap inflation and preservation of validation/formal
admission. Existing time-protection and source/provider checks also apply.
